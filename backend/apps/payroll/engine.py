"""
Payroll calculation engine.

    Earnings   = basic earned (pro-rated, less unpaid leave) + allowances + overtime + bonus + commission + adjustments
    Taxable    = taxable earnings - employee contributions/deductions that legally reduce taxable income
    Deductions = statutory employee contributions + PAYE + other deductions + loan installments
    Net        = Gross - Deductions
    Employer contributions are computed separately and never touch net salary.

All rates come from `StatutoryRule` records in force on the period end date. Every component is stored as a
`PayrollLine` with a `detail` explaining how it was derived.
"""
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from apps.compensation.models import EmployeeAllowance, EmployeeDeduction, Loan
from apps.core.models import CompanySettings
from apps.core.utils import ZERO, money, overlap_days
from apps.employees.models import Employee
from apps.leave.models import LeaveRecord, LeaveType
from apps.statutory import calculator
from apps.statutory.models import StatutoryRule

from .models import PayrollAdjustment, PayrollItem, PayrollLine, PayrollPeriod, PayrollRun

Line = PayrollLine
CAT = PayrollLine.Category
SRC = PayrollLine.Source


class PayrollError(Exception):
    pass


@dataclass
class LineData:
    category: str
    code: str
    name: str
    amount: Decimal
    source_type: str
    sub_category: str = ""
    source_id: int | None = None
    is_taxable: bool = False
    is_social_security_base: bool = False
    is_cash_emolument: bool = False
    is_statutory: bool = False
    reduces_taxable_income: bool = False
    statutory_rule: StatutoryRule | None = None
    detail: dict = field(default_factory=dict)


@dataclass
class EmployeeResult:
    employee: Employee
    days_in_period: Decimal
    days_employed: Decimal
    proration_factor: Decimal
    monthly_basic: Decimal
    lines: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def total(self, category, predicate=lambda line: True):
        return money(sum((l.amount for l in self.lines if l.category == category and predicate(l)), ZERO))

    @property
    def basic_earned(self):
        return self.total(CAT.EARNING, lambda l: l.source_type in (SRC.SALARY, SRC.LEAVE))

    @property
    def gross(self):
        return self.total(CAT.EARNING)

    @property
    def taxable_earnings(self):
        return self.total(CAT.EARNING, lambda l: l.is_taxable)

    @property
    def social_security_base(self):
        return self.total(CAT.EARNING, lambda l: l.is_social_security_base)

    @property
    def cash_emoluments(self):
        return self.total(CAT.EARNING, lambda l: l.is_cash_emolument)

    @property
    def pre_tax_deductions(self):
        return self.total(CAT.DEDUCTION, lambda l: l.reduces_taxable_income)

    @property
    def taxable_income(self):
        return max(money(self.taxable_earnings - self.pre_tax_deductions), ZERO)

    @property
    def paye(self):
        return self.total(CAT.DEDUCTION, lambda l: l.sub_category == StatutoryRule.Category.TAX)

    @property
    def statutory_deductions(self):
        return self.total(CAT.DEDUCTION, lambda l: l.is_statutory)

    @property
    def other_deductions(self):
        return self.total(CAT.DEDUCTION, lambda l: not l.is_statutory)

    @property
    def total_deductions(self):
        return self.total(CAT.DEDUCTION)

    @property
    def net(self):
        return money(self.gross - self.total_deductions)

    @property
    def employer_total(self):
        return self.total(CAT.EMPLOYER)


class PayrollCalculator:
    def __init__(self, period: PayrollPeriod, company: CompanySettings | None = None):
        self.period = period
        self.company = company or CompanySettings.load()
        self.places = self.company.rounding_decimals
        self.start, self.end = period.start_date, period.end_date
        self.calendar_days = Decimal((self.end - self.start).days + 1)
        if self.company.proration_basis == CompanySettings.ProrationBasis.FIXED_30_DAYS:
            self.basis_days = Decimal("30")
        else:
            self.basis_days = self.calendar_days
        self.rules = [r for r in StatutoryRule.in_force(self.end)]
        self.headcount = 0

    # ------------------------------------------------------------------ eligibility
    def eligible_employees(self):
        """Employees whose employment overlaps the period and who are payable (or left during the period)."""
        qs = Employee.objects.select_related("department", "position").filter(
            employment_start_date__lte=self.end
        ).filter(Q(employment_end_date__isnull=True) | Q(employment_end_date__gte=self.start))
        payable = Q(status__in=Employee.PAYABLE_STATUSES) | Q(
            employment_end_date__gte=self.start, employment_end_date__lte=self.end
        )
        return list(qs.filter(payable).order_by("employee_number"))

    def excluded_employees(self):
        eligible = {e.pk for e in self.eligible_employees()}
        return Employee.objects.filter(employment_start_date__lte=self.end).filter(
            Q(employment_end_date__isnull=True) | Q(employment_end_date__gte=self.start)
        ).exclude(pk__in=eligible)

    # ------------------------------------------------------------------ helpers
    def _m(self, v):
        return money(v, self.places)

    def _employment_window(self, emp):
        s = max(emp.employment_start_date, self.start)
        e = min(emp.employment_end_date or self.end, self.end)
        return s, e

    def _factor(self, days):
        """Pro-ration factor for `days` calendar days of employment within the period."""
        days = Decimal(days)
        if days >= self.calendar_days:
            return Decimal("1")
        return min(days / self.basis_days, Decimal("1"))

    def _rule_applies(self, rule, emp):
        if rule.residency == StatutoryRule.Residency.RESIDENT and not emp.is_tax_resident:
            return False
        if rule.residency == StatutoryRule.Residency.NON_RESIDENT and emp.is_tax_resident:
            return False
        if rule.applies_to_schemes and emp.social_security_scheme not in rule.applies_to_schemes:
            return False
        if rule.min_employee_count and self.headcount < rule.min_employee_count:
            return False
        return True

    def _base_amount(self, rule, r: EmployeeResult):
        return {
            StatutoryRule.Base.BASIC: r.basic_earned,
            StatutoryRule.Base.GROSS: r.gross,
            StatutoryRule.Base.SOCIAL_SECURITY_BASE: r.social_security_base,
            StatutoryRule.Base.TAXABLE_INCOME: r.taxable_income,
            StatutoryRule.Base.CASH_EMOLUMENTS: r.cash_emoluments,
        }[rule.base]

    # ------------------------------------------------------------------ per-employee
    def calculate_employee(self, emp: Employee) -> EmployeeResult:
        win_start, win_end = self._employment_window(emp)
        days_employed = Decimal(max((win_end - win_start).days + 1, 0))
        factor = self._factor(days_employed)
        r = EmployeeResult(emp, self.calendar_days, days_employed, factor, ZERO)

        self._basic_salary(r, win_start, win_end)
        self._unpaid_leave(r, win_start, win_end)
        self._allowances(r, win_start, win_end)
        self._adjustments(r, PayrollAdjustment.Category.EARNING)
        self._statutory(r, StatutoryRule.Party.EMPLOYEE, pre_tax=True)
        self._other_deductions(r, pre_tax=True)
        self._statutory(r, StatutoryRule.Party.EMPLOYEE, pre_tax=False)
        self._other_deductions(r, pre_tax=False)
        self._loans(r)
        self._adjustments(r, PayrollAdjustment.Category.DEDUCTION)
        self._statutory(r, StatutoryRule.Party.EMPLOYER, pre_tax=None)

        if r.net < 0:
            r.warnings.append(f"Net salary is negative ({r.net}). Review deductions before approval.")
        if emp.payment_method == Employee.PaymentMethod.BANK and not emp.bank_account_number:
            r.warnings.append("Missing bank account number.")
        return r

    def _basic_salary(self, r, win_start, win_end):
        records = list(r.employee.salary_records_in(win_start, win_end).order_by("effective_from"))
        if not records:
            r.warnings.append("No salary record effective in this period; basic salary is zero.")
            return
        r.monthly_basic = records[-1].basic_salary
        # Split the employment window across salary records by calendar days, then apply the employment
        # pro-ration factor once. A full period therefore always pays exactly one blended monthly salary.
        employment_factor = r.proration_factor
        segments = []
        total = ZERO
        for rec in records:
            d = overlap_days(win_start, win_end, rec.effective_from, rec.effective_to or win_end)
            if not d:
                continue
            weight = Decimal(d) / r.days_employed
            amount = rec.basic_salary * weight * employment_factor
            total += amount
            segments.append({"salary_record": rec.pk, "monthly_basic": str(rec.basic_salary),
                             "from": max(rec.effective_from, win_start).isoformat(),
                             "to": min(rec.effective_to or win_end, win_end).isoformat(),
                             "days": d, "amount": str(self._m(amount))})
        r.lines.append(LineData(
            CAT.EARNING, "BASIC", "Basic salary", self._m(total), SRC.SALARY, sub_category="BASIC",
            source_id=records[-1].pk, is_taxable=True, is_social_security_base=True, is_cash_emolument=True,
            detail={"segments": segments, "days_in_period": str(self.calendar_days),
                    "days_employed": str(r.days_employed), "proration_basis": self.company.proration_basis,
                    "proration_factor": str(employment_factor.quantize(Decimal("0.000001")))},
        ))

    def _unpaid_leave(self, r, win_start, win_end):
        leaves = LeaveRecord.objects.filter(
            employee=r.employee, status=LeaveRecord.Status.APPROVED,
            leave_type__payroll_effect=LeaveType.PayrollEffect.DEDUCT_BASIC_PRORATA,
            start_date__lte=win_end, end_date__gte=win_start,
        ).select_related("leave_type")
        basic = r.basic_earned
        for lv in leaves:
            days = lv.days_within(win_start, win_end)
            if days <= 0 or r.monthly_basic <= 0:
                continue
            daily = r.monthly_basic / self.basis_days
            amount = min(self._m(daily * days), basic)
            basic -= amount
            r.lines.append(LineData(
                CAT.EARNING, f"LEAVE_{lv.leave_type.code}", f"{lv.leave_type.name} (unpaid)", -amount, SRC.LEAVE,
                sub_category="UNPAID_LEAVE", source_id=lv.pk, is_taxable=True, is_social_security_base=True,
                is_cash_emolument=True,
                detail={"days": str(days), "daily_rate": str(self._m(daily)), "leave_record": lv.pk},
            ))

    def _allowances(self, r, win_start, win_end):
        items = EmployeeAllowance.objects.filter(employee=r.employee, allowance_type__is_active=True).select_related(
            "allowance_type")
        for a in items:
            if not a.applies_to(self.start, self.end):
                continue
            t = a.allowance_type
            amount = a.compute(r.basic_earned)
            detail = {"calculation_type": t.calculation_type, "base_amount": str(amount)}
            if a.is_recurring and t.prorate:
                a_start = max(win_start, a.effective_from)
                a_end = min(win_end, a.effective_to or win_end)
                d = max((a_end - a_start).days + 1, 0)
                f = self._factor(d)
                if f < 1 and t.calculation_type != "PERCENT_OF_BASIC":  # % of basic is already pro-rated
                    amount = self._m(amount * f)
                    detail["proration_factor"] = str(f.quantize(Decimal("0.000001")))
            if amount == 0:
                continue
            r.lines.append(LineData(
                CAT.EARNING, t.code, t.name, amount, SRC.ALLOWANCE, sub_category=t.category, source_id=a.pk,
                is_taxable=t.is_taxable, is_social_security_base=t.is_social_security_base,
                is_cash_emolument=t.is_cash_emolument, detail=detail,
            ))

    def _adjustments(self, r, category):
        adjs = PayrollAdjustment.objects.filter(
            employee=r.employee, target_period=self.period, category=category,
            status__in=[PayrollAdjustment.Status.APPROVED, PayrollAdjustment.Status.APPLIED],
        )
        for adj in adjs:
            detail = {"reason": adj.reason, "original_period": adj.original_period_id}
            if category == PayrollAdjustment.Category.EARNING:
                r.lines.append(LineData(
                    CAT.EARNING, f"ADJ{adj.pk}", adj.name, adj.amount, SRC.ADJUSTMENT, sub_category="ADJUSTMENT",
                    source_id=adj.pk, is_taxable=adj.is_taxable, is_social_security_base=adj.is_social_security_base,
                    is_cash_emolument=adj.is_cash_emolument, detail=detail,
                ))
            else:
                r.lines.append(LineData(CAT.DEDUCTION, f"ADJ{adj.pk}", adj.name, adj.amount, SRC.ADJUSTMENT,
                                        sub_category="ADJUSTMENT", source_id=adj.pk, detail=detail))

    def _statutory(self, r, party, pre_tax):
        """pre_tax=True: employee rules not based on taxable income; False: tax-based rules; None: employer."""
        for rule in sorted(self.rules, key=lambda x: (x.calculation_order, x.code)):
            if rule.party != party:
                continue
            if pre_tax is True and rule.base == StatutoryRule.Base.TAXABLE_INCOME:
                continue
            if pre_tax is False and rule.base != StatutoryRule.Base.TAXABLE_INCOME:
                continue
            if not self._rule_applies(rule, r.employee):
                continue
            base = self._base_amount(rule, r)
            amount, detail = calculator.calculate(rule, base)
            amount = self._m(amount)
            if amount == 0 and base == 0:
                continue
            r.lines.append(LineData(
                CAT.DEDUCTION if party == StatutoryRule.Party.EMPLOYEE else CAT.EMPLOYER,
                rule.code, rule.name, amount, SRC.STATUTORY, sub_category=rule.category, source_id=rule.pk,
                is_statutory=True, reduces_taxable_income=rule.reduces_taxable_income, statutory_rule=rule,
                detail=detail,
            ))

    def _other_deductions(self, r, pre_tax):
        items = EmployeeDeduction.objects.filter(
            employee=r.employee, is_active=True, deduction_type__is_active=True,
            deduction_type__reduces_taxable_income=pre_tax,
        ).select_related("deduction_type")
        for d in items:
            if not d.applies_to(self.start, self.end):
                continue
            t = d.deduction_type
            amount = d.compute(r.basic_earned, r.gross)
            if amount == 0:
                continue
            r.lines.append(LineData(
                CAT.DEDUCTION, t.code, t.name, amount, SRC.DEDUCTION, sub_category=t.category, source_id=d.pk,
                is_statutory=t.is_statutory, reduces_taxable_income=t.reduces_taxable_income,
                detail={"calculation_type": t.calculation_type, "reference": d.reference},
            ))

    def _loans(self, r):
        loans = Loan.objects.filter(employee=r.employee, status=Loan.Status.ACTIVE, start_date__lte=self.end)
        for loan in loans:
            amount = loan.next_installment(exclude_period=self.period)
            if amount <= 0:
                continue
            r.lines.append(LineData(
                CAT.DEDUCTION, f"LOAN_{loan.reference}",
                f"{loan.get_loan_type_display()} repayment ({loan.reference})", amount, SRC.LOAN,
                sub_category=loan.loan_type, source_id=loan.pk,
                detail={"installment": str(loan.installment_amount), "total_repayable": str(loan.total_repayable),
                        "balance_before": str(loan.total_repayable - loan.repaid_excluding(self.period))},
            ))


@transaction.atomic
def calculate_period(period: PayrollPeriod, user) -> PayrollRun:
    """Calculate every eligible employee and persist a new current run for the period."""
    period = PayrollPeriod.objects.select_for_update().get(pk=period.pk)
    if period.status not in PayrollPeriod.EDITABLE_STATUSES:
        raise PayrollError(f"Payroll in status {period.status} cannot be recalculated.")
    calc = PayrollCalculator(period)
    employees = calc.eligible_employees()
    if not employees:
        raise PayrollError("No eligible employees for this period.")
    calc.headcount = len(employees)

    results = [calc.calculate_employee(emp) for emp in employees]

    run_warnings = []
    for rule in calc.rules:
        if rule.verification_status != StatutoryRule.Verification.VERIFIED:
            run_warnings.append(f"Statutory rule {rule.code} v{rule.version} is UNVERIFIED.")
    for emp in calc.excluded_employees():
        run_warnings.append(f"{emp.employee_number} excluded: status {emp.status}.")
    for res in results:
        run_warnings.extend(f"{res.employee.employee_number}: {w}" for w in res.warnings)

    last = period.runs.aggregate(n=Max("run_number"))["n"] or 0
    period.runs.filter(is_current=True).update(is_current=False)
    run = PayrollRun.objects.create(
        period=period, run_number=last + 1, calculated_by=user, employee_count=len(results),
        warnings=run_warnings,
        rules_used=[{"id": r.pk, "code": r.code, "version": r.version, "verification_status": r.verification_status,
                     "effective_from": r.effective_from.isoformat()} for r in calc.rules],
    )
    totals = dict(gross=ZERO, ded=ZERO, paye=ZERO, net=ZERO, er=ZERO)
    for res in results:
        emp = res.employee
        item = PayrollItem.objects.create(
            run=run, employee=emp, employee_number=emp.employee_number, employee_name=emp.full_name,
            department=emp.department, department_name=emp.department.name,
            job_title=emp.position.title if emp.position else "", payment_method=emp.payment_method,
            bank_name=emp.bank_name, bank_branch=emp.bank_branch, bank_account_name=emp.bank_account_name,
            bank_account_number=emp.bank_account_number, mobile_money_number=emp.mobile_money_number,
            tin=emp.tin, social_security_number=emp.social_security_number,
            days_in_period=res.days_in_period, days_employed=res.days_employed,
            proration_factor=res.proration_factor.quantize(Decimal("0.000001")),
            monthly_basic_salary=res.monthly_basic, basic_earned=max(res.basic_earned, ZERO),
            gross_earnings=max(res.gross, ZERO), taxable_income=res.taxable_income,
            social_security_base=max(res.social_security_base, ZERO), cash_emoluments=max(res.cash_emoluments, ZERO),
            paye=res.paye, total_statutory_deductions=res.statutory_deductions,
            total_other_deductions=res.other_deductions, total_deductions=res.total_deductions,
            net_salary=res.net, total_employer_contributions=res.employer_total,
            employer_total_cost=max(res.gross, ZERO) + res.employer_total, warnings=res.warnings,
        )
        PayrollLine.objects.bulk_create([
            PayrollLine(item=item, sort_order=i, category=l.category, sub_category=l.sub_category, code=l.code,
                        name=l.name, amount=l.amount, is_taxable=l.is_taxable,
                        is_social_security_base=l.is_social_security_base, is_cash_emolument=l.is_cash_emolument,
                        is_statutory=l.is_statutory, reduces_taxable_income=l.reduces_taxable_income,
                        statutory_rule=l.statutory_rule, source_type=l.source_type, source_id=l.source_id,
                        detail=l.detail)
            for i, l in enumerate(res.lines)
        ])
        totals["gross"] += item.gross_earnings
        totals["ded"] += item.total_deductions
        totals["paye"] += item.paye
        totals["net"] += item.net_salary
        totals["er"] += item.total_employer_contributions
    run.total_gross = totals["gross"]
    run.total_employee_deductions = totals["ded"]
    run.total_paye = totals["paye"]
    run.total_net = totals["net"]
    run.total_employer_contributions = totals["er"]
    run.total_employer_cost = totals["gross"] + totals["er"]
    run.save()
    return run
