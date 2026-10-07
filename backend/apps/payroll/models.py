from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.core.models import TimeStampedModel, money_field
from apps.employees.models import Department, Employee

User = settings.AUTH_USER_MODEL
SIGNED_MONEY = dict(max_digits=16, decimal_places=2)


class PayrollPeriod(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        CALCULATED = "CALCULATED", "Calculated"
        REVIEW = "REVIEW", "In review"
        APPROVED = "APPROVED", "Approved"
        PAID = "PAID", "Paid"
        CLOSED = "CLOSED", "Closed"

    #: statuses in which payroll inputs for the period may still change
    EDITABLE_STATUSES = (Status.DRAFT, Status.CALCULATED)
    #: statuses visible to employees and managers with "view approved" permission
    RELEASED_STATUSES = (Status.APPROVED, Status.PAID, Status.CLOSED)

    name = models.CharField(max_length=60, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    pay_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    notes = models.TextField(blank=True)

    calculated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    calculated_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    paid_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payroll_periods"
        ordering = ["-start_date"]
        constraints = [
            models.CheckConstraint(condition=Q(end_date__gte=F("start_date")), name="period_end_after_start"),
            models.UniqueConstraint(fields=["start_date", "end_date"], name="uniq_period_dates"),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValidationError({"end_date": "End date cannot be before start date."})
            if (self.end_date - self.start_date).days > 31:
                raise ValidationError({"end_date": "A payroll period cannot exceed 31 days."})
            overlap = PayrollPeriod.objects.exclude(pk=self.pk).filter(
                start_date__lte=self.end_date, end_date__gte=self.start_date
            )
            if overlap.exists():
                raise ValidationError(f"Period overlaps existing period '{overlap.first().name}'.")
        if self.pay_date and self.start_date and self.pay_date < self.start_date:
            raise ValidationError({"pay_date": "Pay date cannot be before the period starts."})

    @property
    def current_run(self):
        return self.runs.filter(is_current=True).first()

    @property
    def is_locked(self):
        return self.status not in self.EDITABLE_STATUSES


class PayrollRun(models.Model):
    """One calculation of a period. Recalculation creates a new run; earlier runs are kept for audit."""

    period = models.ForeignKey(PayrollPeriod, on_delete=models.PROTECT, related_name="runs")
    run_number = models.PositiveIntegerField()
    is_current = models.BooleanField(default=True)
    calculated_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    calculated_at = models.DateTimeField(auto_now_add=True)
    employee_count = models.PositiveIntegerField(default=0)
    total_gross = money_field(default=Decimal("0"))
    total_employee_deductions = money_field(default=Decimal("0"))
    total_paye = money_field(default=Decimal("0"))
    total_net = models.DecimalField(default=Decimal("0"), **SIGNED_MONEY)
    total_employer_contributions = money_field(default=Decimal("0"))
    total_employer_cost = money_field(default=Decimal("0"))
    warnings = models.JSONField(default=list, blank=True)
    rules_used = models.JSONField(default=list, blank=True, help_text="Snapshot of statutory rule versions applied")

    class Meta:
        db_table = "payroll_runs"
        ordering = ["period", "-run_number"]
        constraints = [
            models.UniqueConstraint(fields=["period", "run_number"], name="uniq_run_number"),
            models.UniqueConstraint(fields=["period"], condition=Q(is_current=True), name="one_current_run_per_period"),
        ]

    def __str__(self):
        return f"{self.period.name} run {self.run_number}"


class PayrollItem(models.Model):
    """Per-employee payroll result with a snapshot of the employee's details at calculation time."""

    run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name="items")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="payroll_items")
    employee_number = models.CharField(max_length=30)
    employee_name = models.CharField(max_length=250)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="+")
    department_name = models.CharField(max_length=120)
    job_title = models.CharField(max_length=120, blank=True)
    payment_method = models.CharField(max_length=10, choices=Employee.PaymentMethod.choices)
    bank_name = models.CharField(max_length=120, blank=True)
    bank_branch = models.CharField(max_length=120, blank=True)
    bank_account_name = models.CharField(max_length=150, blank=True)
    bank_account_number = models.CharField(max_length=40, blank=True)
    mobile_money_number = models.CharField(max_length=30, blank=True)
    tin = models.CharField(max_length=30, blank=True)
    social_security_number = models.CharField(max_length=40, blank=True)

    days_in_period = models.DecimalField(max_digits=5, decimal_places=2)
    days_employed = models.DecimalField(max_digits=5, decimal_places=2)
    proration_factor = models.DecimalField(max_digits=7, decimal_places=6)
    monthly_basic_salary = money_field()
    basic_earned = money_field()
    gross_earnings = money_field()
    taxable_income = money_field()
    social_security_base = money_field()
    cash_emoluments = money_field()
    paye = money_field()
    total_statutory_deductions = money_field()
    total_other_deductions = money_field()
    total_deductions = money_field()
    net_salary = models.DecimalField(**SIGNED_MONEY)
    total_employer_contributions = money_field()
    employer_total_cost = money_field()
    warnings = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "payroll_items"
        ordering = ["run", "employee_number"]
        constraints = [models.UniqueConstraint(fields=["run", "employee"], name="uniq_item_per_run_employee")]

    def __str__(self):
        return f"{self.run} {self.employee_number}"

    @property
    def period(self):
        return self.run.period


class PayrollLine(models.Model):
    """One calculation component: an earning, an employee deduction, or an employer contribution."""

    class Category(models.TextChoices):
        EARNING = "EARNING", "Earning"
        DEDUCTION = "DEDUCTION", "Employee deduction"
        EMPLOYER = "EMPLOYER", "Employer contribution"

    class Source(models.TextChoices):
        SALARY = "SALARY"
        LEAVE = "LEAVE"
        ALLOWANCE = "ALLOWANCE"
        DEDUCTION = "DEDUCTION"
        LOAN = "LOAN"
        ADJUSTMENT = "ADJUSTMENT"
        STATUTORY = "STATUTORY"

    item = models.ForeignKey(PayrollItem, on_delete=models.CASCADE, related_name="lines")
    category = models.CharField(max_length=10, choices=Category.choices, db_index=True)
    sub_category = models.CharField(max_length=20, blank=True, help_text="e.g. ALLOWANCE, OVERTIME, TAX, SOCIAL_SECURITY")
    code = models.CharField(max_length=40)
    name = models.CharField(max_length=150)
    amount = models.DecimalField(**SIGNED_MONEY)
    is_taxable = models.BooleanField(default=False)
    is_social_security_base = models.BooleanField(default=False)
    is_cash_emolument = models.BooleanField(default=False)
    is_statutory = models.BooleanField(default=False)
    reduces_taxable_income = models.BooleanField(default=False)
    statutory_rule = models.ForeignKey(
        "statutory.StatutoryRule", null=True, blank=True, on_delete=models.PROTECT, related_name="payroll_lines"
    )
    source_type = models.CharField(max_length=12, choices=Source.choices)
    source_id = models.PositiveBigIntegerField(null=True, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "payroll_lines"
        ordering = ["item", "category", "sort_order", "id"]
        indexes = [models.Index(fields=["category", "code"]), models.Index(fields=["source_type", "source_id"])]

    def __str__(self):
        return f"{self.code} {self.amount}"


class PayrollStatusChange(models.Model):
    period = models.ForeignKey(PayrollPeriod, on_delete=models.PROTECT, related_name="status_history")
    from_status = models.CharField(max_length=12, blank=True)
    to_status = models.CharField(max_length=12)
    action = models.CharField(max_length=20)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    timestamp = models.DateTimeField(auto_now_add=True)
    comment = models.TextField(blank=True)

    class Meta:
        db_table = "payroll_status_history"
        ordering = ["period", "timestamp", "id"]


class PayrollAdjustment(TimeStampedModel):
    """Approved correction applied in a future (open) period, e.g. arrears for a closed period."""

    class Category(models.TextChoices):
        EARNING = "EARNING", "Additional earning / arrears"
        DEDUCTION = "DEDUCTION", "Recovery / deduction"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        APPLIED = "APPLIED", "Applied"

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="payroll_adjustments")
    target_period = models.ForeignKey(PayrollPeriod, on_delete=models.PROTECT, related_name="adjustments")
    original_period = models.ForeignKey(
        PayrollPeriod, null=True, blank=True, on_delete=models.PROTECT, related_name="corrections",
        help_text="The period being corrected, if any.",
    )
    category = models.CharField(max_length=10, choices=Category.choices)
    name = models.CharField(max_length=150)
    amount = money_field()
    is_taxable = models.BooleanField(default=True)
    is_social_security_base = models.BooleanField(default=True)
    is_cash_emolument = models.BooleanField(default=True)
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payroll_adjustments"
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="adjustment_amount_gt_0")]

    def clean(self):
        if self.target_period_id and self.target_period.status not in PayrollPeriod.EDITABLE_STATUSES:
            raise ValidationError({"target_period": "Adjustments can only target a DRAFT or CALCULATED period."})
        if self.original_period_id and self.original_period_id == self.target_period_id:
            raise ValidationError({"original_period": "Original and target periods must differ."})


class BankExportFormat(TimeStampedModel):
    """Configurable bank payment file layout (no bank format is assumed)."""

    AVAILABLE_FIELDS = {
        "employee_number": "Employee ID",
        "employee_name": "Employee name",
        "bank_name": "Bank name",
        "bank_branch": "Bank branch",
        "bank_account_name": "Account name",
        "bank_account_number": "Account number",
        "mobile_money_number": "Mobile money number",
        "amount": "Net amount",
        "currency": "Currency",
        "reference": "Payment reference",
        "period_name": "Payroll period",
        "pay_date": "Pay date",
        "department_name": "Department",
        "narration": "Narration",
    }

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    delimiter = models.CharField(max_length=2, default=",")
    include_header = models.BooleanField(default=True)
    columns = models.JSONField(
        help_text='Ordered list of {"header": "...", "field": "<available field>"} or {"header": "...", "value": "<constant>"}'
    )
    date_format = models.CharField(max_length=20, default="%Y-%m-%d")
    amount_decimals = models.PositiveSmallIntegerField(default=2)
    narration_template = models.CharField(max_length=140, default="Salary {period_name}")
    payment_method = models.CharField(max_length=10, default="BANK", help_text="Only include items with this payment method")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bank_export_formats"
        ordering = ["name"]

    def clean(self):
        if not isinstance(self.columns, list) or not self.columns:
            raise ValidationError({"columns": "Provide at least one column."})
        for col in self.columns:
            if not isinstance(col, dict) or "header" not in col or ("field" not in col and "value" not in col):
                raise ValidationError({"columns": "Each column needs a header and a field or constant value."})
            if "field" in col and col["field"] not in self.AVAILABLE_FIELDS:
                raise ValidationError({"columns": f"Unknown field '{col['field']}'."})
        if self.delimiter not in (",", ";", "|", "\t", "\\t"):
            raise ValidationError({"delimiter": "Use comma, semicolon, pipe or tab."})


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        FAILED = "FAILED", "Failed"

    item = models.OneToOneField(PayrollItem, on_delete=models.PROTECT, related_name="payment")
    amount = money_field()
    method = models.CharField(max_length=10)
    bank_name = models.CharField(max_length=120, blank=True)
    account_name = models.CharField(max_length=150, blank=True)
    account_number = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    payment_date = models.DateField(null=True, blank=True)
    reference = models.CharField(max_length=100, blank=True, help_text="Bank transaction / reference number")
    notes = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    recorded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payments"
        ordering = ["item__employee_number"]


class Payslip(models.Model):
    item = models.OneToOneField(PayrollItem, on_delete=models.PROTECT, related_name="payslip")
    payslip_number = models.CharField(max_length=40, unique=True)
    generated_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    generated_at = models.DateTimeField(auto_now_add=True)
    download_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "payslips"
        ordering = ["-generated_at"]

    def __str__(self):
        return self.payslip_number
