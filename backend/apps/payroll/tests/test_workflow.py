import datetime
from datetime import date
from decimal import Decimal as D

import pytest

from apps.compensation.models import Loan
from apps.core.models import AuditLog, CompanySettings
from apps.payroll.models import Payment, PayrollPeriod, Payslip
from apps.statutory.models import StatutoryRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup(make_user, make_employee, test_rules, client_for):
    officer = make_user("PAYROLL_OFFICER")
    manager = make_user("MANAGER")
    finance = make_user("FINANCE_OFFICER")
    hr = make_user("HR_MANAGER")
    emp_user = make_user("EMPLOYEE", "johnd")
    other_user = make_user("EMPLOYEE", "janed")
    e1 = make_employee(1_000_000, user=emp_user)
    e2 = make_employee(2_000_000, user=other_user)
    return dict(officer=officer, manager=manager, finance=finance, hr=hr, emp_user=emp_user, other_user=other_user,
                e1=e1, e2=e2, c=client_for)


def create_period(c, user, name="September 2026", start="2026-09-01", end="2026-09-30"):
    r = c(user).post("/api/payroll-periods/", {"name": name, "start_date": start, "end_date": end, "pay_date": end})
    assert r.status_code == 201, r.data
    return r.data["id"]


def post(c, user, url, data=None):
    return c(user).post(url, data or {}, format="json")


def test_full_lifecycle(setup):
    s, c = setup, setup["c"]
    pid = create_period(c, s["officer"])
    base = f"/api/payroll-periods/{pid}"

    r = post(c, s["officer"], f"{base}/calculate/")
    assert r.status_code == 200, r.data
    assert r.data["status"] == "CALCULATED"
    assert r.data["current_run"]["employee_count"] == 2

    assert post(c, s["officer"], f"{base}/submit/").data["status"] == "REVIEW"

    # manager can see the period in review, and the approval check passes
    chk = c(s["manager"]).get(f"{base}/approval-check/")
    assert chk.data["can_approve"] is True, chk.data
    r = post(c, s["manager"], f"{base}/approve/", {"comment": "OK"})
    assert r.status_code == 200, r.data
    assert r.data["status"] == "APPROVED" and r.data["approved_by_name"] == "manager"

    period = PayrollPeriod.objects.get(pk=pid)
    assert Payment.objects.filter(item__run=period.current_run).count() == 2

    # cannot mark paid until all payments recorded
    assert post(c, s["finance"], f"{base}/mark-paid/").status_code == 400
    r = post(c, s["finance"], f"{base}/record-payments/", {"status": "PAID", "payment_date": "2026-09-30", "reference": "TRX-1"})
    assert r.data["updated"] == 2
    assert post(c, s["finance"], f"{base}/mark-paid/").data["status"] == "PAID"

    assert post(c, s["officer"], f"{base}/close/").data["status"] == "CLOSED"

    # closed payroll cannot be recalculated or edited
    assert post(c, s["officer"], f"{base}/calculate/").status_code == 400
    r = c(s["officer"]).patch(f"{base}/", {"notes": "change"}, format="json")
    assert r.status_code == 400

    history = c(s["officer"]).get(f"{base}/history/").data
    assert [h["to_status"] for h in history] == ["CALCULATED", "REVIEW", "APPROVED", "PAID", "CLOSED"]
    assert AuditLog.objects.filter(action="PAYROLL_APPROVE", object_id=str(pid)).exists()
    assert AuditLog.objects.filter(action="PAYROLL_CLOSE", object_id=str(pid)).exists()


def test_cannot_approve_without_calculation(setup):
    s, c = setup, setup["c"]
    pid = create_period(c, s["officer"])
    r = post(c, s["officer"], f"/api/payroll-periods/{pid}/submit/")
    assert r.status_code == 400
    r = post(c, s["manager"], f"/api/payroll-periods/{pid}/approve/")
    assert r.status_code in (400, 404)


def test_reject_returns_to_calculated_with_reason(setup):
    s, c = setup, setup["c"]
    pid = create_period(c, s["officer"])
    post(c, s["officer"], f"/api/payroll-periods/{pid}/calculate/")
    post(c, s["officer"], f"/api/payroll-periods/{pid}/submit/")
    assert post(c, s["manager"], f"/api/payroll-periods/{pid}/reject/").status_code == 400  # reason required
    r = post(c, s["manager"], f"/api/payroll-periods/{pid}/reject/", {"comment": "Check overtime"})
    assert r.data["status"] == "CALCULATED"


def test_segregation_of_duties(setup, admin_user, make_user):
    s, c = setup, setup["c"]
    # a user who can both prepare and approve
    from apps.accounts.models import Permission, Role

    role = Role.objects.create(code="BOTH", name="Both")
    role.permissions.set(Permission.objects.filter(code__in=["payroll.prepare", "payroll.approve", "payroll.view"]))
    both = make_user("EMPLOYEE", "both")
    both.role = role
    both.save()
    pid = create_period(c, both)
    post(c, both, f"/api/payroll-periods/{pid}/calculate/")
    post(c, both, f"/api/payroll-periods/{pid}/submit/")
    r = post(c, both, f"/api/payroll-periods/{pid}/approve/")
    assert r.status_code == 400 and "Segregation" in str(r.data)


def test_unverified_rules_block_approval(setup):
    s, c = setup, setup["c"]
    StatutoryRule.objects.filter(code="PAYE").update(verification_status="UNVERIFIED")
    pid = create_period(c, s["officer"])
    post(c, s["officer"], f"/api/payroll-periods/{pid}/calculate/")
    post(c, s["officer"], f"/api/payroll-periods/{pid}/submit/")
    r = post(c, s["manager"], f"/api/payroll-periods/{pid}/approve/")
    assert r.status_code == 400 and "not verified" in str(r.data)
    cs = CompanySettings.load()
    cs.require_verified_rules_for_approval = False
    cs.save()
    assert post(c, s["manager"], f"/api/payroll-periods/{pid}/approve/").status_code == 200


def test_overlapping_period_rejected(setup):
    s, c = setup, setup["c"]
    create_period(c, s["officer"])
    r = c(s["officer"]).post("/api/payroll-periods/", {"name": "Overlap", "start_date": "2026-09-15", "end_date": "2026-10-14"})
    assert r.status_code == 400


def test_approval_posts_loan_repayments(setup):
    s, c = setup, setup["c"]
    loan = Loan.objects.create(employee=s["e1"], reference="LN-9", principal=D("100000"), installment_amount=D("100000"),
                               number_of_installments=1, start_date=date(2026, 9, 1), status="ACTIVE")
    pid = create_period(c, s["officer"])
    post(c, s["officer"], f"/api/payroll-periods/{pid}/calculate/")
    post(c, s["officer"], f"/api/payroll-periods/{pid}/submit/")
    post(c, s["manager"], f"/api/payroll-periods/{pid}/approve/")
    loan.refresh_from_db()
    assert loan.remaining_balance == 0
    assert loan.status == "COMPLETED"


def test_role_restrictions(setup):
    s, c = setup, setup["c"]
    pid = create_period(c, s["officer"])
    # HR cannot calculate, manager cannot calculate, finance cannot create periods
    assert post(c, s["hr"], f"/api/payroll-periods/{pid}/calculate/").status_code == 403
    assert post(c, s["manager"], f"/api/payroll-periods/{pid}/calculate/").status_code in (403, 404)
    assert c(s["finance"]).post("/api/payroll-periods/", {"name": "x", "start_date": "2026-11-01",
                                                          "end_date": "2026-11-30"}).status_code == 403
    # manager does not see DRAFT periods
    assert c(s["manager"]).get("/api/payroll-periods/").data["count"] == 0
    # employee has no access to payroll periods
    assert c(s["emp_user"]).get("/api/payroll-periods/").status_code == 403


def _approved_period(s):
    c = s["c"]
    pid = create_period(c, s["officer"])
    post(c, s["officer"], f"/api/payroll-periods/{pid}/calculate/")
    post(c, s["officer"], f"/api/payroll-periods/{pid}/submit/")
    post(c, s["manager"], f"/api/payroll-periods/{pid}/approve/")
    return pid


def test_payslip_generation_and_employee_access(setup):
    s, c = setup, setup["c"]
    pid = _approved_period(s)
    r = post(c, s["officer"], f"/api/payroll-periods/{pid}/generate-payslips/")
    assert r.data["generated"] == 2
    assert post(c, s["officer"], f"/api/payroll-periods/{pid}/generate-payslips/").data["generated"] == 0  # idempotent

    own = c(s["emp_user"]).get("/api/self/payslips/").data
    assert len(own) == 1 and own[0]["employee_number"] == s["e1"].employee_number
    slip_id = own[0]["id"]
    pdf = c(s["emp_user"]).get(f"/api/self/payslips/{slip_id}/pdf/")
    assert pdf.status_code == 200 and pdf["Content-Type"] == "application/pdf"
    assert pdf.content[:4] == b"%PDF"

    # another employee cannot download it
    assert c(s["other_user"]).get(f"/api/self/payslips/{slip_id}/pdf/").status_code == 404
    assert c(s["emp_user"]).get(f"/api/payslips/{slip_id}/pdf/").status_code == 403
    assert Payslip.objects.get(pk=slip_id).download_count == 1
    assert AuditLog.objects.filter(action="PAYSLIP_GENERATE").exists()

    deductions = c(s["emp_user"]).get("/api/self/deductions/").data
    assert {d["code"] for d in deductions} >= {"PAYE", "SS_EE"}


def test_payslips_not_available_before_approval(setup):
    s, c = setup, setup["c"]
    pid = create_period(c, s["officer"])
    post(c, s["officer"], f"/api/payroll-periods/{pid}/calculate/")
    assert post(c, s["officer"], f"/api/payroll-periods/{pid}/generate-payslips/").status_code == 400


def test_bank_export_configurable(setup, admin_user):
    s, c = setup, setup["c"]
    pid = _approved_period(s)
    fmt = c(admin_user).post("/api/bank-export-formats/", {
        "name": "Generic CSV", "delimiter": ";", "columns": [
            {"header": "ACCOUNT", "field": "bank_account_number"}, {"header": "NAME", "field": "employee_name"},
            {"header": "AMOUNT", "field": "amount"}, {"header": "CCY", "value": "TZS"}],
    }, format="json")
    assert fmt.status_code == 201, fmt.data
    r = c(s["finance"]).get(f"/api/payroll-periods/{pid}/bank-export/?export_format={fmt.data['id']}")
    assert r.status_code == 200
    lines = r.content.decode().strip().splitlines()
    assert lines[0] == "ACCOUNT;NAME;AMOUNT;CCY"
    assert len(lines) == 3 and lines[1].endswith(";780000.00;TZS")

    bad = c(admin_user).post("/api/bank-export-formats/", {"name": "Bad", "columns": [{"header": "X", "field": "password"}]},
                             format="json")
    assert bad.status_code == 400


def test_payroll_item_breakdown(setup):
    s, c = setup, setup["c"]
    pid = create_period(c, s["officer"])
    post(c, s["officer"], f"/api/payroll-periods/{pid}/calculate/")
    items = c(s["officer"]).get(f"/api/payroll-periods/{pid}/items/").data["results"]
    detail = c(s["officer"]).get(f"/api/payroll-items/{items[0]['id']}/").data
    cats = {l["category"] for l in detail["lines"]}
    assert cats == {"EARNING", "DEDUCTION", "EMPLOYER"}
    assert "bank_account_number" not in items[0]


def test_adjustment_workflow(setup):
    s, c = setup, setup["c"]
    closed_pid = _approved_period(s)
    pid = create_period(c, s["officer"], "October 2026", "2026-10-01", "2026-10-31")
    r = c(s["officer"]).post("/api/payroll-adjustments/", {
        "employee": s["e1"].id, "target_period": pid, "original_period": closed_pid, "category": "EARNING",
        "name": "September arrears", "amount": "50000", "reason": "Missed allowance"}, format="json")
    assert r.status_code == 201, r.data
    adj = r.data["id"]
    assert post(c, s["officer"], f"/api/payroll-adjustments/{adj}/approve/").status_code == 403
    assert post(c, s["manager"], f"/api/payroll-adjustments/{adj}/approve/").data["status"] == "APPROVED"
    calc = post(c, s["officer"], f"/api/payroll-periods/{pid}/calculate/")
    assert calc.status_code == 200, calc.data
    items = c(s["officer"]).get(f"/api/payroll-periods/{pid}/items/?q={s['e1'].employee_number}").data["results"]
    assert D(items[0]["gross_earnings"]) == D("1050000.00")
    # cannot target an approved period
    r = c(s["officer"]).post("/api/payroll-adjustments/", {
        "employee": s["e1"].id, "target_period": closed_pid, "category": "EARNING", "name": "x", "amount": "1",
        "reason": "x"}, format="json")
    assert r.status_code == 400


def test_reports_and_exports(setup):
    s, c = setup, setup["c"]
    pid = _approved_period(s)
    for name in ["payroll-summary", "department", "register", "deductions", "tax", "contributions", "payments"]:
        r = c(s["finance"]).get(f"/api/reports/{name}/?period={pid}")
        assert r.status_code == 200, (name, r.data)
        for fmt, ctype in [("csv", "text/csv"), ("xlsx", "spreadsheetml"), ("pdf", "application/pdf")]:
            e = c(s["finance"]).get(f"/api/reports/{name}/?period={pid}&export={fmt}")
            assert e.status_code == 200 and ctype in e["Content-Type"], (name, fmt)
    summary = c(s["finance"]).get(f"/api/reports/payroll-summary/?period={pid}").data
    labels = {x["label"]: x["value"] for x in summary["summary"]}
    assert labels["Total employees"] == 2
    assert D(labels["Gross payroll"]) == D("3000000.00")
    assert c(s["finance"]).get("/api/reports/history/").status_code == 200
    assert c(s["finance"]).get("/api/dashboard/").status_code == 200
    stmt = c(s["emp_user"]).get("/api/reports/employee-statement/?export=pdf")
    assert stmt.status_code == 200 and stmt.content[:4] == b"%PDF"
    assert c(s["emp_user"]).get(f"/api/reports/tax/?period={pid}").status_code == 403
    assert c(s["officer"]).get(f"/api/payroll-periods/{pid}/summary-pdf/").status_code == 200


def test_manager_department_report_scoped(setup, make_employee, org):
    s, c = setup, setup["c"]
    make_employee(500_000, department=org["ops"], user=s["manager"])
    pid = _approved_period(s)
    r = c(s["manager"]).get(f"/api/reports/department/?period={pid}")
    assert r.status_code == 200
    assert [row["department"] for row in r.data["rows"]] == ["Operations"]
    assert c(s["manager"]).get(f"/api/reports/tax/?period={pid}").status_code == 403
