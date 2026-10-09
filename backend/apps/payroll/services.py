import csv
import io

from django.db import transaction
from django.db.models import F

from apps.core import audit
from apps.core.models import AuditLog, CompanySettings

from . import pdf
from .models import BankExportFormat, PayrollItem, PayrollPeriod, Payslip


class ServiceError(Exception):
    pass


def payslip_number(item):
    return f"PS-{item.run.period.start_date:%Y%m}-{item.employee_number}"


@transaction.atomic
def generate_payslips(period, user, items=None):
    """Create payslip records for a released period. Idempotent: existing payslips are kept."""
    if period.status not in PayrollPeriod.RELEASED_STATUSES:
        raise ServiceError("Payslips can only be generated for approved payroll.")
    run = period.current_run
    qs = items if items is not None else run.items.all()
    created = []
    for item in qs.select_related("run__period"):
        slip, was_created = Payslip.objects.get_or_create(
            item=item, defaults={"payslip_number": payslip_number(item), "generated_by": user}
        )
        if was_created:
            created.append(slip)
    if created:
        audit.record(AuditLog.Action.PAYSLIP_GENERATE, period, user=user,
                     message=f"Generated {len(created)} payslip(s)",
                     new={"payslips": [s.payslip_number for s in created][:500]})
    return created


def render_payslip(slip: Payslip, user, count_download=True):
    item = PayrollItem.objects.select_related("run__period").prefetch_related("lines").get(pk=slip.item_id)
    content = pdf.payslip_pdf(item, slip.payslip_number)
    if count_download:
        Payslip.objects.filter(pk=slip.pk).update(download_count=F("download_count") + 1)
        audit.record(AuditLog.Action.EXPORT, slip, user=user, message="Payslip downloaded")
    return content


def _field_value(item, field, fmt: BankExportFormat, company):
    period = item.run.period
    payment = getattr(item, "payment", None)
    values = {
        "employee_number": item.employee_number,
        "employee_name": item.employee_name,
        "bank_name": item.bank_name,
        "bank_branch": item.bank_branch,
        "bank_account_name": item.bank_account_name or item.employee_name,
        "bank_account_number": item.bank_account_number,
        "mobile_money_number": item.mobile_money_number,
        "amount": f"{item.net_salary:.{fmt.amount_decimals}f}",
        "currency": company.currency,
        "reference": (payment.reference if payment and payment.reference else f"SAL{period.start_date:%Y%m}{item.employee_number}"),
        "period_name": period.name,
        "pay_date": (period.pay_date or period.end_date).strftime(fmt.date_format),
        "department_name": item.department_name,
        "narration": fmt.narration_template.format(period_name=period.name, employee_number=item.employee_number),
    }
    return values[field]


def _safe_cell(value):
    """Prevent CSV/spreadsheet formula injection."""
    s = "" if value is None else str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@") and not s.replace(".", "", 1).lstrip("-").isdigit() else s


def bank_export(period, fmt: BankExportFormat, user):
    if period.status not in (PayrollPeriod.Status.APPROVED, PayrollPeriod.Status.PAID, PayrollPeriod.Status.CLOSED):
        raise ServiceError("Bank files can only be exported for approved payroll.")
    company = CompanySettings.load()
    items = period.current_run.items.filter(payment_method=fmt.payment_method, net_salary__gt=0).select_related(
        "run__period", "payment").order_by("employee_number")
    delimiter = "\t" if fmt.delimiter in ("\\t", "\t") else fmt.delimiter
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=delimiter, quoting=csv.QUOTE_MINIMAL)
    if fmt.include_header:
        writer.writerow([c["header"] for c in fmt.columns])
    for item in items:
        writer.writerow([
            _safe_cell(_field_value(item, c["field"], fmt, company) if "field" in c else c["value"])
            for c in fmt.columns
        ])
    audit.record(AuditLog.Action.EXPORT, period, user=user,
                 message=f"Bank payment file '{fmt.name}' exported ({items.count()} rows)")
    return buf.getvalue()
