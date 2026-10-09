from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from .validators import validate_image_upload


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        abstract = True


class CompanySettings(models.Model):
    """Singleton holding company identity and payroll processing preferences."""

    class ProrationBasis(models.TextChoices):
        CALENDAR_DAYS = "CALENDAR_DAYS", "Calendar days in period"
        FIXED_30_DAYS = "FIXED_30_DAYS", "Fixed 30-day month"

    name = models.CharField(max_length=200, default="Bravado Company Ltd")
    address = models.TextField(blank=True, default="Dar es Salaam, Tanzania")
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    website = models.CharField(max_length=200, blank=True)
    tin = models.CharField("Company TIN", max_length=50, blank=True)
    nssf_employer_number = models.CharField(max_length=50, blank=True)
    wcf_registration_number = models.CharField(max_length=50, blank=True)
    logo = models.ImageField(upload_to="company/", blank=True, null=True, validators=[validate_image_upload])
    currency = models.CharField(max_length=3, default="TZS")
    proration_basis = models.CharField(
        max_length=20, choices=ProrationBasis.choices, default=ProrationBasis.CALENDAR_DAYS
    )
    rounding_decimals = models.PositiveSmallIntegerField(default=2)
    require_verified_rules_for_approval = models.BooleanField(
        default=True,
        help_text="Block payroll approval when a statutory rule used in the calculation is not verified.",
    )
    enforce_segregation_of_duties = models.BooleanField(
        default=True, help_text="The user who calculated a payroll may not approve it."
    )
    payslip_footer = models.TextField(
        blank=True, default="This is a computer-generated payslip and does not require a signature."
    )
    statutory_disclaimer = models.TextField(
        default=(
            "Statutory calculations (PAYE, social security, WCF, SDL and other levies) are driven by "
            "configurable rules. They must be reviewed against current official Tanzanian requirements "
            "(TRA, NSSF, PSSSF, WCF) before payroll is finalized."
        )
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "company_settings"
        verbose_name_plural = "company settings"
        constraints = [
            models.CheckConstraint(condition=models.Q(rounding_decimals__lte=4), name="company_rounding_lte_4"),
        ]

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Company settings cannot be deleted.")

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return self.name


class AuditLog(models.Model):
    """Append-only audit trail. Updates and deletes are refused at the ORM and DB level."""

    class Action(models.TextChoices):
        LOGIN = "LOGIN"
        LOGIN_FAILED = "LOGIN_FAILED"
        LOGOUT = "LOGOUT"
        PASSWORD_RESET = "PASSWORD_RESET"
        PASSWORD_CHANGE = "PASSWORD_CHANGE"
        CREATE = "CREATE"
        UPDATE = "UPDATE"
        DELETE = "DELETE"
        PAYROLL_CALCULATE = "PAYROLL_CALCULATE"
        PAYROLL_STATUS = "PAYROLL_STATUS"
        PAYROLL_APPROVE = "PAYROLL_APPROVE"
        PAYROLL_CLOSE = "PAYROLL_CLOSE"
        PAYSLIP_GENERATE = "PAYSLIP_GENERATE"
        PAYMENT_RECORD = "PAYMENT_RECORD"
        PERMISSION_CHANGE = "PERMISSION_CHANGE"
        EXPORT = "EXPORT"

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    username = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=32, choices=Action.choices, db_index=True)
    model = models.CharField(max_length=100, blank=True, db_index=True)
    object_id = models.CharField(max_length=64, blank=True, db_index=True)
    object_repr = models.CharField(max_length=255, blank=True)
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    message = models.TextField(blank=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-timestamp", "-id"]
        indexes = [models.Index(fields=["model", "object_id"])]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Audit records are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit records cannot be deleted.")

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} {self.username} {self.action} {self.model}#{self.object_id}"


def money_field(**kwargs):
    """Standard non-negative money column (TZS, 2dp)."""
    kwargs.setdefault("max_digits", 16)
    kwargs.setdefault("decimal_places", 2)
    validators = kwargs.pop("validators", [MinValueValidator(Decimal("0"))])
    return models.DecimalField(validators=validators, **kwargs)
