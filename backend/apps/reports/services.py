"""
Report builders. Each returns a `Report` (title, columns, rows, totals) that can be rendered as JSON,
CSV, Excel or PDF by `exporters`.
"""
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Count, Q, Sum

from apps.core.utils import ZERO
from apps.employees.models import Employee, SalaryRecord
from apps.payroll import pdf
from apps.payroll.models import Payment, PayrollItem, PayrollLine, PayrollPeriod, PayrollRun


@dataclass
class Report:
    title: str
    subtitle: str
    columns: list  # [(key, label, type)] type in text|money|int|date
    rows: list = field(default_factory=list)
    totals: dict | None = None
    summary: list | None = None  # [(label, value)]
    landscape: bool = False

    def as_dict(self):
        return {
            "title": self.title, "subtitle": self.subtitle,
            "columns": [{"key": k, "label": l, "type": t} for k, l, t in self.columns],
            "rows": [{k: _json(v) for k, v in r.items()} for r in self.rows],
            "totals": {k: _json(v) for k, v in (self.totals or {}).items()} or None,
            "summary": [{"label": l, "value": _json(v)} for l, v in (self.summary or [])] or None,
        }


def _json(v):
    if isinstance(v, Decimal):
        return str(v)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def _sum(rows, keys):
    return {k: sum((r.get(k) or ZERO for r in rows), ZERO) for k in keys}


def current_items(period, department_id=None):
    qs = PayrollItem.objects.filter(run__period=period, run__is_current=True)
    if department_id:
        qs = qs.filter(department_id=department_id)
    return qs


def payroll_summary(period, department_id=None):
    items = current_items(period, department_id)
    agg = items.aggregate(
        employees=Count("id"), gross=Sum("gross_earnings"), deductions=Sum("total_deductions"),
        paye=Sum("paye"), statutory=Sum("total_statutory_deductions"), other=Sum("total_other_deductions"),
        net=Sum("net_salary"), employer=Sum("total_employer_contributions"), cost=Sum("employer_total_cost"),
    )
    agg = {k: (v if v is not None else (0 if k == "employees" else ZERO)) for k, v in agg.items()}
    return agg


def summary_report(period, department_id=None):
    a = payroll_summary(period, department_id)
    by_code = OrderedDict()
    for row in (PayrollLine.objects.filter(item__in=current_items(period, department_id))
                .values("category", "code", "name").annotate(total=Sum("amount")).order_by("category", "code")):
        by_code[(row["category"], row["code"])] = row
    cat_label = {"EARNING": "Earning", "DEDUCTION": "Employee deduction", "EMPLOYER": "Employer contribution"}
    rows = [{"category": cat_label[r["category"]], "code": r["code"], "name": r["name"], "total": r["total"]}
            for r in by_code.values()]
    return Report(
        "Payroll Summary", f"{period.name} ({period.status})",
        [("category", "Category", "text"), ("code", "Code", "text"), ("name", "Component", "text"), ("total", "Total (TZS)", "money")],
        rows,
        summary=[
            ("Total employees", a["employees"]), ("Gross payroll", a["gross"]), ("PAYE", a["paye"]),
            ("Statutory employee deductions (incl. PAYE)", a["statutory"]), ("Other deductions", a["other"]),
            ("Total deductions", a["deductions"]), ("Total net salary", a["net"]),
            ("Employer contributions", a["employer"]), ("Total employer cost", a["cost"]),
        ],
    )


def payroll_summary_pdf(period):
    r = summary_report(period)
    return pdf.summary_pdf(r.title, r.subtitle, r.summary,
                           (["Category", "Code", "Component", "Total (TZS)"],
                            [[x["category"], x["code"], x["name"], x["total"]] for x in r.rows], None))


def department_report(period, department_id=None):
    rows = []
    for d in (current_items(period, department_id).values("department_id", "department_name")
              .annotate(employees=Count("id"), gross=Sum("gross_earnings"), paye=Sum("paye"),
                        deductions=Sum("total_deductions"), net=Sum("net_salary"),
                        employer=Sum("total_employer_contributions"), cost=Sum("employer_total_cost"))
              .order_by("department_name")):
        rows.append({"department": d["department_name"], **{k: d[k] for k in
                     ("employees", "gross", "paye", "deductions", "net", "employer", "cost")}})
    totals = _sum(rows, ["gross", "paye", "deductions", "net", "employer", "cost"])
    totals["employees"] = sum(r["employees"] for r in rows)
    totals["department"] = "TOTAL"
    return Report(
        "Department Payroll Report", period.name,
        [("department", "Department", "text"), ("employees", "Employees", "int"), ("gross", "Gross", "money"),
         ("paye", "PAYE", "money"), ("deductions", "Total deductions", "money"), ("net", "Net", "money"),
         ("employer", "Employer contrib.", "money"), ("cost", "Employer cost", "money")],
        rows, totals, landscape=True,
    )


def employee_register(period, department_id=None):
    items = current_items(period, department_id).order_by("employee_number")
    rows = [{
        "employee_number": i.employee_number, "employee_name": i.employee_name, "department": i.department_name,
        "basic": i.basic_earned, "gross": i.gross_earnings, "paye": i.paye,
        "statutory": i.total_statutory_deductions - i.paye, "other": i.total_other_deductions,
        "net": i.net_salary, "employer": i.total_employer_contributions,
    } for i in items]
    totals = _sum(rows, ["basic", "gross", "paye", "statutory", "other", "net", "employer"])
    totals["employee_number"] = "TOTAL"
    return Report(
        "Payroll Register", period.name,
        [("employee_number", "Emp. ID", "text"), ("employee_name", "Employee", "text"), ("department", "Department", "text"),
         ("basic", "Basic", "money"), ("gross", "Gross", "money"), ("paye", "PAYE", "money"),
         ("statutory", "Other statutory", "money"), ("other", "Other deductions", "money"), ("net", "Net", "money"),
         ("employer", "Employer contrib.", "money")],
        rows, totals, landscape=True,
    )


def deduction_report(period, department_id=None):
    lines = (PayrollLine.objects.filter(item__in=current_items(period, department_id), category="DEDUCTION")
             .select_related("item").order_by("code", "item__employee_number"))
    rows = [{"code": l.code, "name": l.name, "statutory": "Yes" if l.is_statutory else "No",
             "employee_number": l.item.employee_number, "employee_name": l.item.employee_name, "amount": l.amount}
            for l in lines]
    by_code = defaultdict(lambda: ZERO)
    for r in rows:
        by_code[r["name"]] += r["amount"]
    totals = _sum(rows, ["amount"])
    totals["code"] = "TOTAL"
    return Report(
        "Deduction Report", period.name,
        [("code", "Code", "text"), ("name", "Deduction", "text"), ("statutory", "Statutory", "text"),
         ("employee_number", "Emp. ID", "text"), ("employee_name", "Employee", "text"), ("amount", "Amount", "money")],
        rows, totals, summary=[(k, v) for k, v in sorted(by_code.items())],
    )


def tax_report(period, department_id=None):
    items = current_items(period, department_id).order_by("employee_number")
    rows = [{"employee_number": i.employee_number, "employee_name": i.employee_name, "tin": i.tin or "-",
             "gross": i.gross_earnings, "taxable": i.taxable_income, "paye": i.paye} for i in items]
    totals = _sum(rows, ["gross", "taxable", "paye"])
    totals["employee_number"] = "TOTAL"
    return Report(
        "PAYE Tax Report", period.name,
        [("employee_number", "Emp. ID", "text"), ("employee_name", "Employee", "text"), ("tin", "TIN", "text"),
         ("gross", "Gross", "money"), ("taxable", "Taxable income", "money"), ("paye", "PAYE", "money")],
        rows, totals,
    )


def contribution_report(period, department_id=None):
    lines = (PayrollLine.objects.filter(item__in=current_items(period, department_id), is_statutory=True)
             .exclude(sub_category="TAX").select_related("item", "statutory_rule"))
    per_emp = OrderedDict()
    codes = []
    for l in lines.order_by("item__employee_number", "category", "code"):
        key = l.item.employee_number
        row = per_emp.setdefault(key, {"employee_number": key, "employee_name": l.item.employee_name,
                                       "ss_number": l.item.social_security_number or "-",
                                       "base": l.item.social_security_base})
        col = f"{l.code}"
        if col not in codes:
            codes.append(col)
        row[col] = row.get(col, ZERO) + l.amount
    rows = list(per_emp.values())
    for r in rows:
        r["total"] = sum((r.get(c, ZERO) for c in codes), ZERO)
    totals = _sum(rows, codes + ["total", "base"])
    totals["employee_number"] = "TOTAL"
    return Report(
        "Statutory Contribution Report", period.name,
        [("employee_number", "Emp. ID", "text"), ("employee_name", "Employee", "text"),
         ("ss_number", "SS number", "text"), ("base", "SS base", "money")]
        + [(c, c.replace("_", " "), "money") for c in codes] + [("total", "Total", "money")],
        rows, totals, landscape=True,
    )


def payment_report(period, department_id=None):
    qs = Payment.objects.filter(item__in=current_items(period, department_id)).select_related("item").order_by(
        "item__employee_number")
    rows = [{"employee_number": p.item.employee_number, "employee_name": p.item.employee_name,
             "method": p.method, "bank": p.bank_name or "-",
             "account": ("*" * max(len(p.account_number) - 4, 0) + p.account_number[-4:]) if p.account_number else "-",
             "amount": p.amount, "status": p.status, "payment_date": p.payment_date, "reference": p.reference or "-"}
            for p in qs]
    totals = _sum(rows, ["amount"])
    totals["employee_number"] = "TOTAL"
    counts = defaultdict(int)
    for r in rows:
        counts[r["status"]] += 1
    return Report(
        "Payment Report", period.name,
        [("employee_number", "Emp. ID", "text"), ("employee_name", "Employee", "text"), ("method", "Method", "text"),
         ("bank", "Bank", "text"), ("account", "Account", "text"), ("amount", "Amount", "money"),
         ("status", "Status", "text"), ("payment_date", "Paid on", "date"), ("reference", "Reference", "text")],
        rows, totals, summary=[(f"{k} payments", v) for k, v in sorted(counts.items())], landscape=True,
    )


def payroll_history(statuses=None, year=None):
    runs = PayrollRun.objects.filter(is_current=True).select_related("period").order_by("-period__start_date")
    if statuses:
        runs = runs.filter(period__status__in=statuses)
    if year:
        runs = runs.filter(period__start_date__year=year)
    rows = [{"period": r.period.name, "status": r.period.status, "start": r.period.start_date,
             "employees": r.employee_count, "gross": r.total_gross, "deductions": r.total_employee_deductions,
             "net": r.total_net, "employer": r.total_employer_contributions, "cost": r.total_employer_cost,
             "period_id": r.period_id} for r in runs]
    totals = _sum(rows, ["gross", "deductions", "net", "employer", "cost"])
    totals["period"] = "TOTAL"
    return Report(
        "Payroll History", f"Year {year}" if year else "All periods",
        [("period", "Period", "text"), ("status", "Status", "text"), ("start", "Start", "date"),
         ("employees", "Employees", "int"), ("gross", "Gross", "money"), ("deductions", "Deductions", "money"),
         ("net", "Net", "money"), ("employer", "Employer contrib.", "money"), ("cost", "Employer cost", "money")],
        rows, totals, landscape=True,
    )


def employee_salary_report(employee_id=None, department_id=None):
    qs = SalaryRecord.objects.select_related("employee__department").order_by("employee__employee_number", "effective_from")
    if employee_id:
        qs = qs.filter(employee_id=employee_id)
    if department_id:
        qs = qs.filter(employee__department_id=department_id)
    rows = []
    prev = {}
    for s in qs:
        before = prev.get(s.employee_id)
        change = (s.basic_salary - before) if before is not None else None
        rows.append({"employee_number": s.employee.employee_number, "employee_name": s.employee.full_name,
                     "department": s.employee.department.name, "basic_salary": s.basic_salary,
                     "effective_from": s.effective_from, "effective_to": s.effective_to,
                     "change": change, "reason": s.reason or "-"})
        prev[s.employee_id] = s.basic_salary
    return Report(
        "Employee Salary Report", "Salary history",
        [("employee_number", "Emp. ID", "text"), ("employee_name", "Employee", "text"),
         ("department", "Department", "text"), ("basic_salary", "Basic salary", "money"),
         ("effective_from", "From", "date"), ("effective_to", "To", "date"), ("change", "Change", "money"),
         ("reason", "Reason", "text")],
        rows, landscape=True,
    )


def employee_statement(employee: Employee, year=None):
    """Salary statement for one employee across released payroll periods."""
    items = PayrollItem.objects.filter(
        employee=employee, run__is_current=True, run__period__status__in=PayrollPeriod.RELEASED_STATUSES
    ).select_related("run__period").order_by("run__period__start_date")
    if year:
        items = items.filter(run__period__start_date__year=year)
    rows = [{"period": i.run.period.name, "basic": i.basic_earned, "gross": i.gross_earnings, "paye": i.paye,
             "statutory": i.total_statutory_deductions - i.paye, "other": i.total_other_deductions,
             "net": i.net_salary} for i in items]
    totals = _sum(rows, ["basic", "gross", "paye", "statutory", "other", "net"])
    totals["period"] = "TOTAL"
    return Report(
        "Employee Salary Statement",
        f"{employee.full_name} ({employee.employee_number}) - {employee.department.name}" + (f" - {year}" if year else ""),
        [("period", "Period", "text"), ("basic", "Basic", "money"), ("gross", "Gross", "money"),
         ("paye", "PAYE", "money"), ("statutory", "Other statutory", "money"), ("other", "Other deductions", "money"),
         ("net", "Net pay", "money")],
        rows, totals,
    )


def dashboard(department_id=None, released_only=False):
    periods = PayrollPeriod.objects.all()
    if released_only:
        periods = periods.filter(status__in=PayrollPeriod.RELEASED_STATUSES)
    current = periods.order_by("-start_date").first()
    emp_qs = Employee.objects.filter(status__in=Employee.PAYABLE_STATUSES)
    if department_id:
        emp_qs = emp_qs.filter(department_id=department_id)
    data = {
        "total_employees": emp_qs.count(),
        "current_period": None,
        "pending_approvals": PayrollPeriod.objects.filter(status=PayrollPeriod.Status.REVIEW).count(),
        "status_counts": {r["status"]: r["n"] for r in PayrollPeriod.objects.values("status").annotate(n=Count("id"))},
    }
    if current:
        s = payroll_summary(current, department_id) if current.current_run else None
        data["current_period"] = {"id": current.id, "name": current.name, "status": current.status,
                                  "summary": {k: _json(v) for k, v in s.items()} if s else None}

    runs = (PayrollRun.objects.filter(is_current=True, period__in=periods).select_related("period")
            .order_by("-period__start_date")[:12])
    monthly = []
    for r in reversed(list(runs)):
        if department_id:
            s = payroll_summary(r.period, department_id)
            monthly.append({"period": r.period.name, "gross": _json(s["gross"]), "net": _json(s["net"]),
                            "deductions": _json(s["deductions"]), "employer": _json(s["employer"]),
                            "cost": _json(s["cost"]), "employees": s["employees"]})
        else:
            monthly.append({"period": r.period.name, "gross": _json(r.total_gross), "net": _json(r.total_net),
                            "deductions": _json(r.total_employee_deductions),
                            "employer": _json(r.total_employer_contributions), "cost": _json(r.total_employer_cost),
                            "employees": r.employee_count})
    data["payroll_by_month"] = monthly

    by_dept = []
    if current and current.current_run:
        for d in (current_items(current, department_id).values("department_name")
                  .annotate(gross=Sum("gross_earnings"), net=Sum("net_salary"), employees=Count("id"))
                  .order_by("department_name")):
            by_dept.append({"department": d["department_name"], "gross": _json(d["gross"]), "net": _json(d["net"]),
                            "employees": d["employees"]})
    data["payroll_by_department"] = by_dept
    data["employees_by_department"] = [
        {"department": r["department__name"], "count": r["n"]}
        for r in emp_qs.values("department__name").annotate(n=Count("id")).order_by("department__name")
    ]

    # Salary distribution (current basic salaries) in bands.
    bands = [(0, 500_000), (500_000, 1_000_000), (1_000_000, 2_000_000), (2_000_000, 5_000_000), (5_000_000, None)]
    counts = OrderedDict((f"{lo/1e6:g}M-{hi/1e6:g}M" if hi else f"{lo/1e6:g}M+", 0) for lo, hi in bands)
    salaries = SalaryRecord.objects.filter(employee__in=emp_qs, effective_to__isnull=True).values_list("basic_salary", flat=True)
    for sal in salaries:
        for (lo, hi), label in zip(bands, counts):
            if sal >= lo and (hi is None or sal < hi):
                counts[label] += 1
                break
    data["salary_distribution"] = [{"band": k, "count": v} for k, v in counts.items()]
    data["recent_periods"] = [
        {"id": p.id, "name": p.name, "status": p.status, "start_date": p.start_date.isoformat(),
         "net": _json(p.current_run.total_net) if p.current_run else None}
        for p in periods.order_by("-start_date")[:6]
    ]
    return data
