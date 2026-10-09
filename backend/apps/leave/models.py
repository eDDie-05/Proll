from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.core.models import TimeStampedModel
from apps.employees.models import Employee


class LeaveType(TimeStampedModel):
    """Leave categories. Payroll effect is configured explicitly - no legal assumptions are built in."""

    class PayrollEffect(models.TextChoices):
        NONE = "NONE", "No payroll effect (paid leave)"
        DEDUCT_BASIC_PRORATA = "DEDUCT_BASIC_PRORATA", "Deduct basic salary pro-rata for leave days"

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    payroll_effect = models.CharField(max_length=24, choices=PayrollEffect.choices, default=PayrollEffect.NONE)
    annual_entitlement_days = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))]
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "leave_types"
        ordering = ["name"]

    def __str__(self):
        return self.name


class LeaveRecord(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="leave_records")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name="records")
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.DecimalField(
        max_digits=5, decimal_places=1, validators=[MinValueValidator(Decimal("0.5"))],
        help_text="Leave days counted (defaults to calendar days in range).",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    reason = models.TextField(blank=True)
    approved_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "leave_records"
        ordering = ["-start_date"]
        constraints = [
            models.CheckConstraint(condition=Q(end_date__gte=F("start_date")), name="leave_end_after_start"),
        ]

    def __str__(self):
        return f"{self.employee.employee_number} {self.leave_type.code} {self.start_date}..{self.end_date}"

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before start date."})
        if self.start_date and self.end_date and self.days is not None:
            span = (self.end_date - self.start_date).days + 1
            if self.days > span:
                raise ValidationError({"days": f"Cannot exceed the {span} calendar days in the range."})

    def save(self, *args, **kwargs):
        if self.days is None:
            self.days = Decimal((self.end_date - self.start_date).days + 1)
        super().save(*args, **kwargs)

    def days_within(self, start, end):
        """Leave days falling inside [start, end], scaled if `days` < calendar span."""
        s, e = max(self.start_date, start), min(self.end_date, end)
        if e < s:
            return Decimal("0")
        span = Decimal((self.end_date - self.start_date).days + 1)
        return (Decimal((e - s).days + 1) * self.days / span).quantize(Decimal("0.01"))
