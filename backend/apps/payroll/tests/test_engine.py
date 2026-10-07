"""Payroll calculation scenarios. Rates are synthetic test fixtures (see conftest.test_rules)."""
import datetime
from datetime import date
from decimal import Decimal as D

import pytest

from apps.compensation.models import AllowanceType, DeductionType, EmployeeAllowance, EmployeeDeduction, Loan
from apps.core.models import CompanySettings
from apps.employees.models import Employee, SalaryRecord
from apps.leave.models import LeaveRecord, LeaveType
from apps.payroll import engine
from apps.payroll.models import PayrollAdjustment, PayrollPeriod
from apps.statutory.models import StatutoryRule
from conftest import make_rule

pytestmark = pytest.mark.django_db

SEPT = dict(name="September 2026", start_date=date(2026, 9, 1), end_date=date(2026, 9, 30))


def period(**kw):
    return PayrollPeriod.objects.create(**(kw or SEPT))


def calc_one(emp, p=None):
    p = p or period()
    c = engine.PayrollCalculator(p)
    c.headcount = len(c.eligible_employees())
    return c.calculate_employee(emp)


def line(result, code):
    matches = [l for l in result.lines if l.code == code]
    assert matches, f"no line {code}: {[l.code for l in result.lines]}"
    return matches[0].amount


def allowance_type(code, **kw):
    defaults = dict(name=code.title(), is_taxable=True, is_social_security_base=True, is_cash_emolument=True)
    defaults.update(kw)
    return AllowanceType.objects.create(code=code, **defaults)


def test_basic_salary_only(make_employee, test_rules):
    r = calc_one(make_employee(1_000_000))
    assert r.gross == D("1000000.00")
    assert line(r, "SS_EE") == D("100000.00")
    assert r.taxable_income == D("900000.00")
    # 0 on 100k, 10% of 400k = 40,000, 20% of 400k = 80,000
    assert r.paye == D("120000.00")
    assert r.total_deductions == D("220000.00")
    assert r.net == D("780000.00")
    assert line(r, "SS_ER") == D("100000.00")
    assert line(r, "LEVY") == D("10000.00")
    assert r.employer_total == D("110000.00")


def test_employer_contributions_do_not_reduce_net(make_employee, test_rules):
    r = calc_one(make_employee(1_000_000))
    assert r.net == r.gross - r.total_deductions
    assert all(l.category != "EMPLOYER" for l in r.lines if l.category == "DEDUCTION")


def test_allowances_taxable_and_non_taxable(make_employee, test_rules):
    emp = make_employee(1_000_000)
    housing = allowance_type("HOUSING")
    transport = allowance_type("TRANSPORT", is_taxable=False, is_social_security_base=False)
    EmployeeAllowance.objects.create(employee=emp, allowance_type=housing, amount=D("200000"), effective_from=date(2026, 1, 1))
    EmployeeAllowance.objects.create(employee=emp, allowance_type=transport, amount=D("100000"), effective_from=date(2026, 1, 1))
    r = calc_one(emp)
    assert r.gross == D("1300000.00")
    assert line(r, "SS_EE") == D("120000.00")
    assert r.taxable_income == D("1080000.00")
    assert r.paye == D("156000.00")
    assert r.net == D("1024000.00")
    assert line(r, "LEVY") == D("13000.00")


def test_percentage_allowance(make_employee, test_rules):
    emp = make_employee(1_000_000)
    t = allowance_type("RESP", calculation_type="PERCENT_OF_BASIC", default_rate=D("15"))
    EmployeeAllowance.objects.create(employee=emp, allowance_type=t, effective_from=date(2026, 1, 1))
    assert line(calc_one(emp), "RESP") == D("150000.00")


def test_multiple_deductions(make_employee, test_rules):
    emp = make_employee(1_000_000)
    ins = DeductionType.objects.create(code="INS", name="Insurance", category="INSURANCE", default_amount=D("50000"))
    union = DeductionType.objects.create(code="UNION", name="Union", category="UNION", calculation_type="PERCENT_OF_BASIC",
                                         default_rate=D("2"))
    capped = DeductionType.objects.create(code="WELF", name="Welfare", calculation_type="PERCENT_OF_GROSS",
                                          default_rate=D("5"), max_amount=D("10000"))
    for t in (ins, union, capped):
        EmployeeDeduction.objects.create(employee=emp, deduction_type=t, start_date=date(2026, 1, 1))
    r = calc_one(emp)
    assert line(r, "INS") == D("50000.00")
    assert line(r, "UNION") == D("20000.00")
    assert line(r, "WELF") == D("10000.00")  # capped
    assert r.paye == D("120000.00")  # post-tax deductions do not change PAYE
    assert r.total_deductions == D("300000.00")
    assert r.net == D("700000.00")


def test_pre_tax_deduction_reduces_taxable_income(make_employee, test_rules):
    emp = make_employee(1_000_000)
    pension = DeductionType.objects.create(code="VPEN", name="Voluntary pension", default_amount=D("100000"),
                                           reduces_taxable_income=True)
    EmployeeDeduction.objects.create(employee=emp, deduction_type=pension, start_date=date(2026, 1, 1))
    r = calc_one(emp)
    assert r.taxable_income == D("800000.00")
    assert r.paye == D("100000.00")


def test_ended_deduction_not_applied(make_employee, test_rules):
    emp = make_employee(1_000_000)
    t = DeductionType.objects.create(code="OLD", name="Old", default_amount=D("5000"))
    EmployeeDeduction.objects.create(employee=emp, deduction_type=t, start_date=date(2026, 1, 1), end_date=date(2026, 8, 31))
    assert "OLD" not in [l.code for l in calc_one(emp).lines]


def test_overtime(make_employee, test_rules):
    emp = make_employee(1_000_000)
    ot = allowance_type("OT", category="OVERTIME", calculation_type="HOURS_X_RATE", default_rate=D("5000"))
    EmployeeAllowance.objects.create(employee=emp, allowance_type=ot, quantity=D("10"), effective_from=date(2026, 9, 1),
                                     is_recurring=False)
    r = calc_one(emp)
    assert line(r, "OT") == D("50000.00")
    assert r.gross == D("1050000.00")
    assert r.paye == D("129000.00")
    assert r.net == D("816000.00")


def test_bonus_non_recurring_only_in_its_period(make_employee, test_rules):
    emp = make_employee(1_000_000)
    bonus = allowance_type("BONUS", category="BONUS", is_recurring=False)
    EmployeeAllowance.objects.create(employee=emp, allowance_type=bonus, amount=D("300000"), effective_from=date(2026, 9, 15),
                                     is_recurring=False)
    sept = calc_one(emp)
    assert line(sept, "BONUS") == D("300000.00")
    octo = calc_one(emp, period(name="October 2026", start_date=date(2026, 10, 1), end_date=date(2026, 10, 31)))
    assert "BONUS" not in [l.code for l in octo.lines]


def test_commission(make_employee, test_rules):
    emp = make_employee(1_000_000)
    com = allowance_type("COMM", category="COMMISSION")
    EmployeeAllowance.objects.create(employee=emp, allowance_type=com, amount=D("75000"), effective_from=date(2026, 9, 1),
                                     is_recurring=False)
    assert calc_one(emp).gross == D("1075000.00")


def test_loan_repayment(make_employee, test_rules):
    emp = make_employee(1_000_000)
    loan = Loan.objects.create(employee=emp, reference="LN-1", principal=D("250000"), installment_amount=D("100000"),
                               number_of_installments=3, start_date=date(2026, 9, 1), status=Loan.Status.ACTIVE)
    r = calc_one(emp)
    assert line(r, "LOAN_LN-1") == D("100000.00")
    assert r.net == D("680000.00")
    # Final installment is capped at the outstanding balance.
    loan.repayments.create(amount=D("200000"), date=date(2026, 8, 31), source="MANUAL")
    r2 = calc_one(emp, PayrollPeriod.objects.create(name="Oct", start_date=date(2026, 10, 1), end_date=date(2026, 10, 31)))
    assert line(r2, "LOAN_LN-1") == D("50000.00")


def test_pending_loan_not_deducted(make_employee, test_rules):
    emp = make_employee(1_000_000)
    Loan.objects.create(employee=emp, reference="LN-2", principal=D("100000"), installment_amount=D("50000"),
                        number_of_installments=2, start_date=date(2026, 9, 1))
    assert not [l for l in calc_one(emp).lines if l.code.startswith("LOAN_")]


def test_employee_joining_mid_period(make_employee, test_rules):
    emp = make_employee(1_000_000, start=date(2026, 9, 16))
    r = calc_one(emp)
    assert r.days_employed == 15
    assert line(r, "BASIC") == D("500000.00")


def test_joining_mid_period_prorates_fixed_allowance(make_employee, test_rules):
    emp = make_employee(1_000_000, start=date(2026, 9, 16))
    t = allowance_type("HOUSING")
    EmployeeAllowance.objects.create(employee=emp, allowance_type=t, amount=D("200000"), effective_from=date(2026, 9, 16))
    assert line(calc_one(emp), "HOUSING") == D("100000.00")


def test_employee_leaving_mid_period(make_employee, test_rules):
    emp = make_employee(1_000_000, employment_end_date=date(2026, 9, 10), status=Employee.Status.RESIGNED)
    p = period()
    c = engine.PayrollCalculator(p)
    assert emp in c.eligible_employees()
    r = c.calculate_employee(emp)
    assert line(r, "BASIC") == D("333333.33")


def test_terminated_before_period_excluded(make_employee, test_rules):
    emp = make_employee(1_000_000, employment_end_date=date(2026, 8, 31), status=Employee.Status.TERMINATED)
    assert emp not in engine.PayrollCalculator(period()).eligible_employees()


def test_suspended_employee_excluded(make_employee, test_rules):
    emp = make_employee(1_000_000, status=Employee.Status.SUSPENDED)
    assert emp not in engine.PayrollCalculator(period()).eligible_employees()


def test_salary_change_during_year(make_employee, test_rules):
    emp = make_employee(1_500_000, start=date(2026, 1, 1))
    SalaryRecord.create_new(emp, D("1800000"), date(2027, 1, 1))
    dec = calc_one(emp, period(name="Dec 2026", start_date=date(2026, 12, 1), end_date=date(2026, 12, 31)))
    jan = calc_one(emp, period(name="Jan 2027", start_date=date(2027, 1, 1), end_date=date(2027, 1, 31)))
    assert line(dec, "BASIC") == D("1500000.00")
    assert line(jan, "BASIC") == D("1800000.00")
    history = list(emp.salary_records.order_by("effective_from"))
    assert len(history) == 2 and history[0].effective_to == date(2026, 12, 31)


def test_salary_change_mid_period_is_split(make_employee, test_rules):
    emp = make_employee(1_000_000, start=date(2026, 1, 1))
    SalaryRecord.create_new(emp, D("1300000"), date(2026, 9, 16))
    assert line(calc_one(emp), "BASIC") == D("1150000.00")


def test_salary_cannot_be_backdated(make_employee):
    from django.core.exceptions import ValidationError

    emp = make_employee(1_000_000, start=date(2026, 1, 1))
    with pytest.raises(ValidationError):
        SalaryRecord.create_new(emp, D("900000"), date(2025, 12, 1))


def test_statutory_rule_selected_by_effective_date(make_employee, test_rules):
    old = test_rules["ss_ee"]
    old.effective_to = date(2026, 12, 31)
    old.save()
    make_rule(code="SS_EE", version=2, name="Social security (employee) v2", category="SOCIAL_SECURITY", rate=D("5"),
              base="SOCIAL_SECURITY_BASE", reduces_taxable_income=True, effective_from=date(2027, 1, 1))
    emp = make_employee(1_000_000)
    dec = calc_one(emp, period(name="Dec 2026", start_date=date(2026, 12, 1), end_date=date(2026, 12, 31)))
    jan = calc_one(emp, period(name="Jan 2027", start_date=date(2027, 1, 1), end_date=date(2027, 1, 31)))
    assert line(dec, "SS_EE") == D("100000.00")
    assert line(jan, "SS_EE") == D("50000.00")


def test_base_ceiling_and_max_amount(make_employee, test_rules):
    rule = test_rules["ss_ee"]
    rule.base_ceiling = D("2000000")
    rule.save()
    assert line(calc_one(make_employee(3_000_000)), "SS_EE") == D("200000.00")


def test_non_resident_uses_non_resident_rule(make_employee, test_rules):
    make_rule(code="PAYE_NR", name="PAYE non-resident", category="TAX", rate=D("15"), base="TAXABLE_INCOME",
              residency="NON_RESIDENT", calculation_order=50)
    r = calc_one(make_employee(1_000_000, is_tax_resident=False))
    assert "PAYE" not in [l.code for l in r.lines]
    assert line(r, "PAYE_NR") == D("135000.00")  # 15% of 900,000


def test_scheme_specific_rule(make_employee, test_rules):
    rule = test_rules["ss_ee"]
    rule.applies_to_schemes = ["NSSF"]
    rule.save()
    r = calc_one(make_employee(1_000_000, social_security_scheme="PSSSF"))
    assert "SS_EE" not in [l.code for l in r.lines]


def test_min_employee_count_rule(make_employee, test_rules):
    make_rule(code="SDL_T", name="Levy 10+", party="EMPLOYER", category="LEVY", rate=D("3.5"), base="CASH_EMOLUMENTS",
              min_employee_count=10)
    r = calc_one(make_employee(1_000_000))
    assert "SDL_T" not in [l.code for l in r.lines]


def test_unpaid_leave_reduces_basic(make_employee, test_rules):
    emp = make_employee(1_000_000)
    unpaid = LeaveType.objects.create(code="UNPAID", name="Unpaid leave", payroll_effect="DEDUCT_BASIC_PRORATA")
    paid = LeaveType.objects.create(code="ANNUAL", name="Annual leave")
    LeaveRecord.objects.create(employee=emp, leave_type=unpaid, start_date=date(2026, 9, 7), end_date=date(2026, 9, 9),
                               status="APPROVED")
    LeaveRecord.objects.create(employee=emp, leave_type=paid, start_date=date(2026, 9, 14), end_date=date(2026, 9, 18),
                               status="APPROVED")
    r = calc_one(emp)
    assert line(r, "LEAVE_UNPAID") == D("-100000.00")
    assert r.gross == D("900000.00")


def test_adjustment_included(make_employee, test_rules, admin_user):
    emp = make_employee(1_000_000)
    p = period()
    PayrollAdjustment.objects.create(employee=emp, target_period=p, category="EARNING", name="Arrears", amount=D("50000"),
                                     reason="Missed allowance", status="APPROVED")
    PayrollAdjustment.objects.create(employee=emp, target_period=p, category="EARNING", name="Pending", amount=D("99999"),
                                     reason="Not approved")
    r = calc_one(emp, p)
    assert r.gross == D("1050000.00")


def test_no_salary_record_warns(make_employee, test_rules):
    r = calc_one(make_employee(None))
    assert r.gross == 0
    assert any("No salary record" in w for w in r.warnings)


def test_negative_net_warns(make_employee, test_rules):
    emp = make_employee(100_000)
    t = DeductionType.objects.create(code="BIG", name="Big", default_amount=D("500000"))
    EmployeeDeduction.objects.create(employee=emp, deduction_type=t, start_date=date(2026, 1, 1))
    r = calc_one(emp)
    assert r.net < 0 and any("negative" in w for w in r.warnings)


def test_fixed_30_day_basis(make_employee, test_rules):
    cs = CompanySettings.load()
    cs.proration_basis = "FIXED_30_DAYS"
    cs.save()
    emp = make_employee(3_000_000, start=date(2026, 10, 22))  # 10 days in a 31-day month
    r = calc_one(emp, period(name="Oct", start_date=date(2026, 10, 1), end_date=date(2026, 10, 31)))
    assert line(r, "BASIC") == D("1000000.00")


def test_calculate_period_persists_breakdown(make_employee, test_rules, admin_user):
    make_employee(1_000_000)
    make_employee(2_000_000)
    p = period()
    run = engine.calculate_period(p, admin_user)
    assert run.employee_count == 2
    assert run.total_gross == D("3000000.00")
    item = run.items.get(monthly_basic_salary=D("1000000"))
    assert item.net_salary == D("780000.00")
    codes = set(item.lines.values_list("code", flat=True))
    assert {"BASIC", "SS_EE", "PAYE", "SS_ER", "LEVY"} <= codes
    paye_line = item.lines.get(code="PAYE")
    assert paye_line.statutory_rule == test_rules["paye"]
    assert len(paye_line.detail["bands"]) == 3
    # recalculation creates a new current run and keeps the old one
    run2 = engine.calculate_period(p, admin_user)
    assert run2.run_number == 2
    assert p.runs.count() == 2 and p.runs.filter(is_current=True).get() == run2


def test_unverified_rule_flagged_in_run(make_employee, test_rules, admin_user):
    StatutoryRule.objects.filter(code="PAYE").update(verification_status="UNVERIFIED")
    make_employee(1_000_000)
    run = engine.calculate_period(period(), admin_user)
    assert any("PAYE" in w and "UNVERIFIED" in w for w in run.warnings)
