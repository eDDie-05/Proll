"""
Configurable statutory rules (PAYE, social security, WCF, SDL, ...).

No rate lives in code. Each rule is versioned and effective-dated; the payroll engine selects the rule
in force on the payroll period end date. Rules record their legal source and a verification status.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.core.models import TimeStampedModel, money_field

RATE = dict(max_digits=7, decimal_places=4,
            validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))])


class StatutoryRule(TimeStampedModel):
    class Category(models.TextChoices):
        TAX = "TAX", "Income tax (PAYE)"
        SOCIAL_SECURITY = "SOCIAL_SECURITY", "Social security"
        LEVY = "LEVY", "Employer levy"
        OTHER = "OTHER", "Other statutory"

    class Party(models.TextChoices):
        EMPLOYEE = "EMPLOYEE", "Employee deduction"
        EMPLOYER = "EMPLOYER", "Employer contribution"

    class Method(models.TextChoices):
        PROGRESSIVE = "PROGRESSIVE", "Progressive tax brackets"
        FLAT_RATE = "FLAT_RATE", "Flat percentage of base"
        FIXED_AMOUNT = "FIXED_AMOUNT", "Fixed amount per period"

    class Base(models.TextChoices):
        BASIC = "BASIC", "Basic salary (after proration/unpaid leave)"
        GROSS = "GROSS", "Gross earnings"
        SOCIAL_SECURITY_BASE = "SOCIAL_SECURITY_BASE", "Earnings flagged for social security"
        TAXABLE_INCOME = "TAXABLE_INCOME", "Taxable income (taxable earnings less pre-tax deductions)"
        CASH_EMOLUMENTS = "CASH_EMOLUMENTS", "Gross cash emoluments"

    class Residency(models.TextChoices):
        ALL = "ALL", "All employees"
        RESIDENT = "RESIDENT", "Tax residents only"
        NON_RESIDENT = "NON_RESIDENT", "Non-residents only"

    class Verification(models.TextChoices):
        UNVERIFIED = "UNVERIFIED", "Unverified"
        VERIFIED = "VERIFIED", "Verified against official source"

    code = models.CharField(max_length=40, db_index=True,
                            help_text="Stable identifier shared by all versions, e.g. PAYE_RESIDENT")
    version = models.PositiveIntegerField(default=1)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    party = models.CharField(max_length=10, choices=Party.choices)
    method = models.CharField(max_length=15, choices=Method.choices)
    base = models.CharField(max_length=24, choices=Base.choices)
    rate = models.DecimalField(null=True, blank=True, help_text="Percent, for FLAT_RATE", **RATE)
    fixed_amount = money_field(null=True, blank=True)
    base_ceiling = money_field(null=True, blank=True, help_text="Maximum base the rate applies to (cap).")
    min_amount = money_field(null=True, blank=True)
    max_amount = money_field(null=True, blank=True, help_text="Maximum contribution per period.")
    reduces_taxable_income = models.BooleanField(
        default=False, help_text="Employee contribution deducted before computing taxable income."
    )
    residency = models.CharField(max_length=12, choices=Residency.choices, default=Residency.ALL)
    applies_to_schemes = models.JSONField(
        default=list, blank=True,
        help_text='Social-security schemes this rule applies to, e.g. ["NSSF"]. Empty = all employees.',
    )
    min_employee_count = models.PositiveIntegerField(
        null=True, blank=True, help_text="Rule only applies when the payroll has at least this many employees."
    )
    calculation_order = models.PositiveSmallIntegerField(default=100)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # Provenance
    source_name = models.CharField(max_length=200, blank=True, help_text="e.g. Tanzania Revenue Authority")
    source_url = models.URLField(max_length=500, blank=True)
    source_reference = models.CharField(max_length=255, blank=True, help_text="Act/section/notice reference")
    source_retrieved_on = models.DateField(null=True, blank=True)
    verification_status = models.CharField(
        max_length=12, choices=Verification.choices, default=Verification.UNVERIFIED, db_index=True
    )
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)

    class Meta:
        db_table = "statutory_rules"
        ordering = ["calculation_order", "code", "-effective_from"]
        constraints = [
            models.UniqueConstraint(fields=["code", "version"], name="uniq_rule_code_version"),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True) | Q(effective_to__gte=F("effective_from")),
                name="rule_to_after_from",
            ),
        ]

    #: fields that may still change after the rule has been used in a payroll
    MUTABLE_AFTER_USE = {
        "effective_to", "is_active", "verification_status", "verified_by", "verified_at", "verification_notes",
        "source_name", "source_url", "source_reference", "source_retrieved_on", "description", "updated_at",
    }

    def __str__(self):
        return f"{self.code} v{self.version} ({self.effective_from}..{self.effective_to or 'open'})"

    @property
    def is_used(self):
        return self.payroll_lines.exists() if self.pk else False

    def clean(self):
        errors = {}
        if self.effective_to and self.effective_to < self.effective_from:
            errors["effective_to"] = "Effective-to cannot be before effective-from."
        if self.method == self.Method.FLAT_RATE and self.rate is None:
            errors["rate"] = "A rate is required for flat-rate rules."
        if self.method == self.Method.FIXED_AMOUNT and self.fixed_amount is None:
            errors["fixed_amount"] = "An amount is required for fixed-amount rules."
        if self.reduces_taxable_income and self.party != self.Party.EMPLOYEE:
            errors["reduces_taxable_income"] = "Only employee deductions can reduce taxable income."
        if self.reduces_taxable_income and self.base == self.Base.TAXABLE_INCOME:
            errors["base"] = "A rule that reduces taxable income cannot itself be based on taxable income."
        if not isinstance(self.applies_to_schemes, list):
            errors["applies_to_schemes"] = "Must be a list of scheme codes."
        if errors:
            raise ValidationError(errors)
        if self.is_active and self.effective_from:
            overlapping = StatutoryRule.objects.filter(code=self.code, is_active=True).exclude(pk=self.pk).filter(
                Q(effective_to__isnull=True) | Q(effective_to__gte=self.effective_from)
            )
            if self.effective_to:
                overlapping = overlapping.filter(effective_from__lte=self.effective_to)
            if overlapping.exists():
                raise ValidationError(
                    {"effective_from": f"Overlaps active version(s) of {self.code}: "
                                       + ", ".join(str(r) for r in overlapping[:3])}
                )

    def validate_brackets(self):
        if self.method != self.Method.PROGRESSIVE:
            return
        brackets = list(self.brackets.order_by("lower_bound"))
        if not brackets:
            raise ValidationError("Progressive rules need at least one bracket.")
        if brackets[0].lower_bound != 0:
            raise ValidationError("The first bracket must start at 0.")
        for prev, cur in zip(brackets, brackets[1:]):
            if prev.upper_bound is None or prev.upper_bound != cur.lower_bound:
                raise ValidationError(
                    f"Brackets must be contiguous: {prev.lower_bound}-{prev.upper_bound} then {cur.lower_bound}."
                )
        if brackets[-1].upper_bound is not None:
            raise ValidationError("The last bracket must be open-ended (no upper bound).")

    @classmethod
    def in_force(cls, on_date):
        return cls.objects.filter(is_active=True, effective_from__lte=on_date).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=on_date)
        ).prefetch_related("brackets")


class TaxBracket(models.Model):
    """Marginal band: `rate`% applies to the portion of income between lower_bound and upper_bound."""

    rule = models.ForeignKey(StatutoryRule, on_delete=models.CASCADE, related_name="brackets")
    lower_bound = money_field()
    upper_bound = money_field(null=True, blank=True, help_text="Blank = no upper limit")
    rate = models.DecimalField(**RATE)

    class Meta:
        db_table = "tax_brackets"
        ordering = ["rule", "lower_bound"]
        constraints = [
            models.UniqueConstraint(fields=["rule", "lower_bound"], name="uniq_bracket_lower"),
            models.CheckConstraint(
                condition=Q(upper_bound__isnull=True) | Q(upper_bound__gt=F("lower_bound")),
                name="bracket_upper_gt_lower",
            ),
        ]

    def __str__(self):
        return f"{self.lower_bound}-{self.upper_bound or '...'} @ {self.rate}%"
