from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q, Sum

from apps.core.models import TimeStampedModel, money_field
from apps.core.utils import money
from apps.employees.models import Employee

PERCENT = dict(max_digits=14, decimal_places=4, validators=[MinValueValidator(Decimal("0"))])


class CalculationType(models.TextChoices):
    FIXED = "FIXED", "Fixed amount"
    PERCENT_OF_BASIC = "PERCENT_OF_BASIC", "Percentage of basic salary"
    PERCENT_OF_GROSS = "PERCENT_OF_GROSS", "Percentage of gross earnings"
    HOURS_X_RATE = "HOURS_X_RATE", "Quantity x rate (e.g. overtime hours)"


class AllowanceType(TimeStampedModel):
    """Configurable earning type. Tax/contribution treatment is explicit, never assumed."""

    class Category(models.TextChoices):
        ALLOWANCE = "ALLOWANCE", "Allowance"
        OVERTIME = "OVERTIME", "Overtime"
        BONUS = "BONUS", "Bonus"
        COMMISSION = "COMMISSION", "Commission"
        OTHER = "OTHER", "Other earning"

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=12, choices=Category.choices, default=Category.ALLOWANCE)
    calculation_type = models.CharField(
        max_length=20, choices=[c for c in CalculationType.choices if c[0] != "PERCENT_OF_GROSS"],
        default=CalculationType.FIXED,
    )
    default_amount = money_field(default=Decimal("0"))
    default_rate = models.DecimalField(default=Decimal("0"), help_text="Percent (e.g. 10 = 10%) or rate per unit", **PERCENT)
    is_taxable = models.BooleanField(help_text="Included in taxable income for PAYE.")
    is_social_security_base = models.BooleanField(
        help_text="Included in the base for social-security contributions (e.g. NSSF)."
    )
    is_cash_emolument = models.BooleanField(
        default=True, help_text="Counts as gross cash emolument for employer levies (e.g. SDL/WCF)."
    )
    is_recurring = models.BooleanField(default=True)
    prorate = models.BooleanField(
        default=True, help_text="Pro-rate recurring amounts when the employee joins/leaves mid-period."
    )
    is_active = models.BooleanField(default=True)
    treatment_reference = models.CharField(
        max_length=255, blank=True, help_text="Legal/regulatory basis for the tax treatment chosen."
    )

    class Meta:
        db_table = "allowance_types"
        ordering = ["category", "name"]

    def __str__(self):
        return self.name


class EmployeeAllowance(TimeStampedModel):
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="allowances")
    allowance_type = models.ForeignKey(AllowanceType, on_delete=models.PROTECT, related_name="assignments")
    amount = money_field(null=True, blank=True, help_text="Overrides the type default for FIXED.")
    rate = models.DecimalField(null=True, blank=True, help_text="Overrides the type default rate.", **PERCENT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                   validators=[MinValueValidator(Decimal("0"))], help_text="Hours/units for HOURS_X_RATE")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_recurring = models.BooleanField(
        default=True, help_text="Non-recurring items are paid once, in the period containing effective_from."
    )
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "employee_allowances"
        ordering = ["employee", "allowance_type"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__isnull=True) | Q(amount__gte=0), name="emp_allowance_amount_gte_0"),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True) | Q(effective_to__gte=F("effective_from")),
                name="emp_allowance_to_after_from",
            ),
        ]

    def __str__(self):
        return f"{self.employee.employee_number} {self.allowance_type.code}"

    def clean(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "End date cannot be before start date."})
        if self.allowance_type_id and self.allowance_type.calculation_type == CalculationType.HOURS_X_RATE:
            if self.quantity is None:
                raise ValidationError({"quantity": "Quantity is required for quantity x rate allowances."})

    def applies_to(self, start, end):
        if self.is_recurring:
            return self.effective_from <= end and (self.effective_to is None or self.effective_to >= start)
        return start <= self.effective_from <= end

    def compute(self, basic):
        t = self.allowance_type
        if t.calculation_type == CalculationType.FIXED:
            return money(self.amount if self.amount is not None else t.default_amount)
        rate = self.rate if self.rate is not None else t.default_rate
        if t.calculation_type == CalculationType.PERCENT_OF_BASIC:
            return money(basic * rate / Decimal("100"))
        if t.calculation_type == CalculationType.HOURS_X_RATE:
            return money((self.quantity or 0) * rate)
        raise ValidationError(f"Unsupported calculation type {t.calculation_type}")


class DeductionType(TimeStampedModel):
    """Configurable non-statutory (or manually-applied statutory) deduction type."""

    class Category(models.TextChoices):
        STATUTORY = "STATUTORY", "Statutory"
        LOAN = "LOAN", "Loan repayment"
        ADVANCE = "ADVANCE", "Salary advance"
        INSURANCE = "INSURANCE", "Insurance"
        PENSION = "PENSION", "Pension / voluntary social security"
        UNION = "UNION", "Union dues"
        OTHER = "OTHER", "Other"

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=12, choices=Category.choices, default=Category.OTHER)
    calculation_type = models.CharField(max_length=20, choices=[c for c in CalculationType.choices if c[0] != "HOURS_X_RATE"],
                                        default=CalculationType.FIXED)
    default_amount = money_field(default=Decimal("0"))
    default_rate = models.DecimalField(default=Decimal("0"), **PERCENT)
    max_amount = money_field(null=True, blank=True, help_text="Cap per period, if any.")
    is_statutory = models.BooleanField(default=False)
    reduces_taxable_income = models.BooleanField(
        default=False, help_text="Deducted before PAYE is computed (only where the law permits)."
    )
    is_recurring = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "deduction_types"
        ordering = ["category", "name"]

    def __str__(self):
        return self.name


class EmployeeDeduction(TimeStampedModel):
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="deductions")
    deduction_type = models.ForeignKey(DeductionType, on_delete=models.PROTECT, related_name="assignments")
    amount = money_field(null=True, blank=True)
    rate = models.DecimalField(null=True, blank=True, **PERCENT)
    max_amount = money_field(null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_recurring = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    reference = models.CharField(max_length=100, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "employee_deductions"
        ordering = ["employee", "deduction_type"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__isnull=True) | Q(amount__gte=0), name="emp_deduction_amount_gte_0"),
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=F("start_date")), name="emp_deduction_end_after_start"
            ),
        ]

    def __str__(self):
        return f"{self.employee.employee_number} {self.deduction_type.code}"

    def clean(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before start date."})

    def applies_to(self, start, end):
        if not self.is_active:
            return False
        if self.is_recurring:
            return self.start_date <= end and (self.end_date is None or self.end_date >= start)
        return start <= self.start_date <= end

    def compute(self, basic, gross):
        t = self.deduction_type
        if t.calculation_type == CalculationType.FIXED:
            value = self.amount if self.amount is not None else t.default_amount
        else:
            rate = self.rate if self.rate is not None else t.default_rate
            base = basic if t.calculation_type == CalculationType.PERCENT_OF_BASIC else gross
            value = base * rate / Decimal("100")
        cap = self.max_amount if self.max_amount is not None else t.max_amount
        if cap is not None:
            value = min(value, cap)
        return money(value)


class Loan(TimeStampedModel):
    class LoanType(models.TextChoices):
        LOAN = "LOAN", "Loan"
        ADVANCE = "ADVANCE", "Salary advance"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending approval"
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="loans")
    loan_type = models.CharField(max_length=10, choices=LoanType.choices, default=LoanType.LOAN)
    reference = models.CharField(max_length=40, unique=True)
    principal = money_field()
    interest_rate = models.DecimalField(default=Decimal("0"), help_text="Flat interest % on principal", **PERCENT)
    total_repayable = money_field(editable=False, default=Decimal("0"))
    installment_amount = money_field()
    number_of_installments = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    start_date = models.DateField(help_text="First payroll period that includes this date starts deductions.")
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    approved_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "loans"
        ordering = ["-start_date"]
        constraints = [
            models.CheckConstraint(condition=Q(principal__gt=0), name="loan_principal_gt_0"),
            models.CheckConstraint(condition=Q(installment_amount__gt=0), name="loan_installment_gt_0"),
        ]

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        self.total_repayable = money(self.principal * (Decimal("1") + self.interest_rate / Decimal("100")))
        super().save(*args, **kwargs)

    def clean(self):
        if self.principal is not None and self.installment_amount is not None and self.number_of_installments:
            total = money(self.principal * (Decimal("1") + (self.interest_rate or 0) / Decimal("100")))
            if self.installment_amount * self.number_of_installments < total:
                raise ValidationError(
                    {"installment_amount": f"Installments ({self.number_of_installments} x {self.installment_amount}) "
                                           f"do not cover total repayable {total}."}
                )

    @property
    def amount_repaid(self):
        return self.repayments.aggregate(t=Sum("amount"))["t"] or Decimal("0")

    @property
    def remaining_balance(self):
        return money(self.total_repayable - self.amount_repaid)

    def repaid_excluding(self, period=None):
        qs = self.repayments.all()
        if period is not None:
            qs = qs.exclude(payroll_period=period)
        return qs.aggregate(t=Sum("amount"))["t"] or Decimal("0")

    def next_installment(self, exclude_period=None):
        """Amount to deduct in a payroll, never more than the outstanding balance."""
        balance = self.total_repayable - self.repaid_excluding(exclude_period)
        return money(max(min(self.installment_amount, balance), Decimal("0")))


class LoanRepayment(models.Model):
    class Source(models.TextChoices):
        PAYROLL = "PAYROLL", "Payroll deduction"
        MANUAL = "MANUAL", "Manual payment"

    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name="repayments")
    amount = money_field()
    date = models.DateField()
    source = models.CharField(max_length=10, choices=Source.choices)
    payroll_period = models.ForeignKey(
        "payroll.PayrollPeriod", null=True, blank=True, on_delete=models.PROTECT, related_name="loan_repayments"
    )
    reference = models.CharField(max_length=100, blank=True)
    recorded_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "loan_repayments"
        ordering = ["loan", "date"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="loan_repayment_gt_0"),
            models.UniqueConstraint(fields=["loan", "payroll_period"], condition=Q(payroll_period__isnull=False),
                                    name="uniq_loan_repayment_per_period"),
        ]

    def __str__(self):
        return f"{self.loan.reference} {self.amount} {self.date}"
