"""
Payroll approval workflow:  DRAFT -> CALCULATED -> REVIEW -> APPROVED -> PAID -> CLOSED

Every transition is permission-checked, recorded in PayrollStatusChange and the audit log.
"""
from django.db import transaction
from django.utils import timezone

from apps.compensation.models import Loan, LoanRepayment
from apps.core import audit
from apps.core.models import AuditLog, CompanySettings
from apps.statutory.models import StatutoryRule

from . import engine
from .models import Payment, PayrollAdjustment, PayrollLine, PayrollPeriod, PayrollStatusChange

S = PayrollPeriod.Status


class WorkflowError(Exception):
    pass


class PermissionDenied(WorkflowError):
    pass


def _require(user, code):
    if not user.has_code(code):
        raise PermissionDenied(f"Requires permission '{code}'.")


def _transition(period, user, to_status, action, comment="", audit_action=AuditLog.Action.PAYROLL_STATUS):
    old = period.status
    period.status = to_status
    period.save()
    PayrollStatusChange.objects.create(period=period, from_status=old, to_status=to_status, action=action,
                                       user=user, comment=comment)
    audit.record(audit_action, period, user=user, old={"status": old}, new={"status": to_status},
                 message=comment or action)


def _lock(period):
    return PayrollPeriod.objects.select_for_update().get(pk=period.pk)


@transaction.atomic
def calculate(period, user):
    _require(user, "payroll.prepare")
    period = _lock(period)
    run = engine.calculate_period(period, user)
    period.refresh_from_db()
    period.calculated_by, period.calculated_at = user, timezone.now()
    _transition(period, user, S.CALCULATED, "calculate",
                comment=f"Run {run.run_number}: {run.employee_count} employees, net {run.total_net}",
                audit_action=AuditLog.Action.PAYROLL_CALCULATE)
    return run


@transaction.atomic
def submit_for_review(period, user, comment=""):
    _require(user, "payroll.prepare")
    period = _lock(period)
    if period.status != S.CALCULATED:
        raise WorkflowError("Only calculated payroll can be submitted for review.")
    if not period.current_run:
        raise WorkflowError("Payroll has not been calculated.")
    period.submitted_by, period.submitted_at = user, timezone.now()
    _transition(period, user, S.REVIEW, "submit", comment)
    return period


@transaction.atomic
def reject(period, user, reason):
    _require(user, "payroll.approve")
    if not reason:
        raise WorkflowError("A reason is required to reject payroll.")
    period = _lock(period)
    if period.status != S.REVIEW:
        raise WorkflowError("Only payroll in review can be rejected.")
    period.submitted_by = period.submitted_at = None
    _transition(period, user, S.CALCULATED, "reject", reason)
    return period


def approval_blockers(period, user=None):
    """List reasons approval is not currently possible (also shown in the UI before approving)."""
    blockers = []
    run = period.current_run
    if period.status != S.REVIEW:
        blockers.append("Payroll must be in REVIEW.")
    if run is None:
        blockers.append("Payroll has not been calculated successfully.")
        return blockers
    if run.items.filter(net_salary__lt=0).exists():
        blockers.append("One or more employees have a negative net salary.")
    company = CompanySettings.load()
    if company.require_verified_rules_for_approval:
        unverified = StatutoryRule.objects.filter(
            payroll_lines__item__run=run
        ).exclude(verification_status=StatutoryRule.Verification.VERIFIED).distinct()
        for rule in unverified:
            blockers.append(f"Statutory rule {rule.code} v{rule.version} is not verified.")
    if user is not None and company.enforce_segregation_of_duties and not user.is_superuser:
        if user.pk in (run.calculated_by_id, period.submitted_by_id):
            blockers.append("Segregation of duties: the preparer cannot approve this payroll.")
    return blockers


@transaction.atomic
def approve(period, user, comment=""):
    _require(user, "payroll.approve")
    period = _lock(period)
    blockers = approval_blockers(period, user)
    if blockers:
        raise WorkflowError(" ".join(blockers))
    run = period.current_run
    period.approved_by, period.approved_at = user, timezone.now()

    # Create payment instructions from the approved (snapshotted) items.
    for item in run.items.all():
        account = item.bank_account_number if item.payment_method == "BANK" else item.mobile_money_number
        Payment.objects.create(
            item=item, amount=item.net_salary, method=item.payment_method, bank_name=item.bank_name,
            account_name=item.bank_account_name or item.employee_name, account_number=account or "",
        )

    # Post loan repayments so balances reflect this payroll.
    for line in PayrollLine.objects.filter(item__run=run, source_type=PayrollLine.Source.LOAN):
        loan = Loan.objects.select_for_update().get(pk=line.source_id)
        amount = min(line.amount, loan.remaining_balance)
        if amount > 0:
            LoanRepayment.objects.create(loan=loan, amount=amount, date=period.pay_date or period.end_date,
                                         source=LoanRepayment.Source.PAYROLL, payroll_period=period,
                                         reference=f"Payroll {period.name}", recorded_by=user)
        if loan.remaining_balance <= 0:
            loan.status = Loan.Status.COMPLETED
            loan.save(update_fields=["status", "updated_at"])

    PayrollAdjustment.objects.filter(target_period=period, status=PayrollAdjustment.Status.APPROVED).update(
        status=PayrollAdjustment.Status.APPLIED)

    _transition(period, user, S.APPROVED, "approve", comment, audit_action=AuditLog.Action.PAYROLL_APPROVE)
    return period


@transaction.atomic
def mark_paid(period, user, comment=""):
    _require(user, "payments.manage")
    period = _lock(period)
    if period.status != S.APPROVED:
        raise WorkflowError("Only approved payroll can be marked as paid.")
    outstanding = Payment.objects.filter(item__run=period.current_run).exclude(status=Payment.Status.PAID).count()
    if outstanding:
        raise WorkflowError(f"{outstanding} payment(s) are not yet recorded as PAID.")
    period.paid_by, period.paid_at = user, timezone.now()
    _transition(period, user, S.PAID, "mark_paid", comment)
    return period


@transaction.atomic
def close(period, user, comment=""):
    _require(user, "payroll.close")
    period = _lock(period)
    if period.status != S.PAID:
        raise WorkflowError("Only paid payroll can be closed.")
    period.closed_by, period.closed_at = user, timezone.now()
    _transition(period, user, S.CLOSED, "close", comment, audit_action=AuditLog.Action.PAYROLL_CLOSE)
    return period


@transaction.atomic
def record_payments(period, user, payment_ids, status, payment_date=None, reference="", notes=""):
    _require(user, "payments.manage")
    period = _lock(period)
    if period.status != S.APPROVED:
        raise WorkflowError("Payments can only be recorded for approved payroll.")
    qs = Payment.objects.select_for_update().filter(item__run=period.current_run)
    if payment_ids:
        qs = qs.filter(pk__in=payment_ids)
    updated = []
    for p in qs:
        old = {"status": p.status, "payment_date": str(p.payment_date) if p.payment_date else None, "reference": p.reference}
        p.status = status
        p.payment_date = payment_date if status == Payment.Status.PAID else None
        p.reference = reference or p.reference
        p.notes = notes or p.notes
        p.recorded_by, p.recorded_at = user, timezone.now()
        p.save()
        audit.record(AuditLog.Action.PAYMENT_RECORD, p, user=user, old=old,
                     new={"status": p.status, "payment_date": str(p.payment_date) if p.payment_date else None,
                          "reference": p.reference})
        updated.append(p)
    return updated
