from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models, transaction
from django.db.models import F, Q

from apps.core.models import TimeStampedModel, money_field
from apps.core.validators import validate_document_upload

phone_validator = RegexValidator(r"^\+?[0-9 ()-]{7,20}$", "Enter a valid phone number.")


class Department(TimeStampedModel):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "departments"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Position(TimeStampedModel):
    title = models.CharField(max_length=120)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.PROTECT, related_name="positions")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "positions"
        ordering = ["title"]
        constraints = [models.UniqueConstraint(fields=["title", "department"], name="uniq_position_per_department")]

    def __str__(self):
        return self.title


class EmploymentType(TimeStampedModel):
    """Permanent, Contract, Temporary, Part-time, ... configurable."""

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=80, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "employment_types"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Employee(TimeStampedModel):
    class Gender(models.TextChoices):
        MALE = "MALE", "Male"
        FEMALE = "FEMALE", "Female"
        UNSPECIFIED = "UNSPECIFIED", "Prefer not to say"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        ON_LEAVE = "ON_LEAVE", "On leave"
        SUSPENDED = "SUSPENDED", "Suspended"
        TERMINATED = "TERMINATED", "Terminated"
        RESIGNED = "RESIGNED", "Resigned"
        RETIRED = "RETIRED", "Retired"

    #: statuses that are eligible for payroll processing
    PAYABLE_STATUSES = (Status.ACTIVE, Status.ON_LEAVE)

    class SocialSecurityScheme(models.TextChoices):
        NSSF = "NSSF", "NSSF"
        PSSSF = "PSSSF", "PSSSF"
        NONE = "NONE", "Not a member"
        OTHER = "OTHER", "Other"

    class PaymentMethod(models.TextChoices):
        BANK = "BANK", "Bank transfer"
        MOBILE = "MOBILE", "Mobile money"
        CASH = "CASH", "Cash / cheque"

    employee_number = models.CharField("Employee ID", max_length=30, unique=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="employee"
    )
    first_name = models.CharField(max_length=80)
    middle_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80)
    gender = models.CharField(max_length=12, choices=Gender.choices, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True, validators=[phone_validator])
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)

    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="employees")
    position = models.ForeignKey(Position, null=True, blank=True, on_delete=models.PROTECT, related_name="employees")
    employment_type = models.ForeignKey(EmploymentType, on_delete=models.PROTECT, related_name="employees")
    employment_start_date = models.DateField()
    employment_end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE, db_index=True)

    # Payment details (sensitive)
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.BANK)
    bank_name = models.CharField(max_length=120, blank=True)
    bank_branch = models.CharField(max_length=120, blank=True)
    bank_account_name = models.CharField(max_length=150, blank=True)
    bank_account_number = models.CharField(max_length=40, blank=True)
    bank_swift_code = models.CharField(max_length=20, blank=True)
    mobile_money_number = models.CharField(max_length=30, blank=True, validators=[phone_validator])

    # Statutory identifiers (sensitive)
    tin = models.CharField("TIN", max_length=30, blank=True)
    is_tax_resident = models.BooleanField(default=True)
    social_security_scheme = models.CharField(
        max_length=10, choices=SocialSecurityScheme.choices, default=SocialSecurityScheme.NSSF
    )
    social_security_number = models.CharField(max_length=40, blank=True)
    wcf_number = models.CharField("WCF number", max_length=40, blank=True)
    national_id = models.CharField("NIDA number", max_length=40, blank=True)

    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True, validators=[phone_validator])
    emergency_contact_relationship = models.CharField(max_length=60, blank=True)

    class Meta:
        db_table = "employees"
        ordering = ["employee_number"]
        indexes = [models.Index(fields=["last_name", "first_name"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(employment_end_date__isnull=True) | Q(employment_end_date__gte=F("employment_start_date")),
                name="employee_end_after_start",
            ),
        ]

    SENSITIVE_FIELDS = (
        "bank_name", "bank_branch", "bank_account_name", "bank_account_number", "bank_swift_code",
        "mobile_money_number", "tin", "social_security_number", "wcf_number", "national_id", "date_of_birth",
        "address", "emergency_contact_name", "emergency_contact_phone", "emergency_contact_relationship",
    )

    @property
    def full_name(self):
        return " ".join(p for p in (self.first_name, self.middle_name, self.last_name) if p)

    def __str__(self):
        return f"{self.employee_number} - {self.full_name}"

    def clean(self):
        if self.employment_end_date and self.employment_end_date < self.employment_start_date:
            raise ValidationError({"employment_end_date": "End date cannot be before start date."})
        if self.payment_method == self.PaymentMethod.BANK and self.status in self.PAYABLE_STATUSES:
            if not self.bank_account_number:
                raise ValidationError({"bank_account_number": "Bank account number is required for bank payments."})
        if self.payment_method == self.PaymentMethod.MOBILE and not self.mobile_money_number:
            raise ValidationError({"mobile_money_number": "Mobile money number is required for mobile payments."})

    def salary_records_in(self, start, end):
        return self.salary_records.filter(effective_from__lte=end).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=start)
        )

    def current_salary(self, on_date=None):
        from django.utils import timezone

        on_date = on_date or timezone.localdate()
        return self.salary_records_in(on_date, on_date).order_by("-effective_from").first()


class EmploymentContract(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        EXPIRED = "EXPIRED", "Expired"
        TERMINATED = "TERMINATED", "Terminated"
        SUPERSEDED = "SUPERSEDED", "Superseded"

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="contracts")
    contract_number = models.CharField(max_length=40, unique=True)
    employment_type = models.ForeignKey(EmploymentType, on_delete=models.PROTECT, related_name="contracts")
    position = models.ForeignKey(Position, null=True, blank=True, on_delete=models.PROTECT, related_name="contracts")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="contracts")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    basic_salary = money_field()
    working_hours_per_week = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("40"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("168"))],
    )
    document = models.FileField(upload_to="contracts/%Y/", null=True, blank=True, validators=[validate_document_upload])
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "employment_contracts"
        ordering = ["-start_date"]
        constraints = [
            models.CheckConstraint(condition=Q(basic_salary__gte=0), name="contract_salary_non_negative"),
            models.CheckConstraint(
                condition=Q(end_date__isnull=True) | Q(end_date__gte=F("start_date")), name="contract_end_after_start"
            ),
        ]

    def __str__(self):
        return self.contract_number

    def clean(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before start date."})


class SalaryRecord(TimeStampedModel):
    """Effective-dated basic salary. Records are never deleted; a new record closes the previous one."""

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="salary_records")
    basic_salary = money_field()
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    contract = models.ForeignKey(
        EmploymentContract, null=True, blank=True, on_delete=models.SET_NULL, related_name="salary_records"
    )

    class Meta:
        db_table = "salary_history"
        ordering = ["employee", "-effective_from"]
        constraints = [
            models.UniqueConstraint(fields=["employee", "effective_from"], name="uniq_salary_effective_from"),
            models.CheckConstraint(condition=Q(basic_salary__gte=0), name="salary_non_negative"),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True) | Q(effective_to__gte=F("effective_from")),
                name="salary_to_after_from",
            ),
        ]

    def __str__(self):
        return f"{self.employee.employee_number} {self.basic_salary} from {self.effective_from}"

    @classmethod
    @transaction.atomic
    def create_new(cls, employee, basic_salary, effective_from, reason="", user=None, contract=None):
        """Add a salary record, closing the currently open one the day before `effective_from`."""
        # Lock employee's salary rows to avoid concurrent overlapping inserts.
        existing = list(cls.objects.select_for_update().filter(employee=employee).order_by("-effective_from"))
        if existing and effective_from <= existing[0].effective_from:
            raise ValidationError(
                {"effective_from": f"Must be after the latest salary effective date ({existing[0].effective_from}). "
                                   "Use a payroll adjustment for retroactive corrections."}
            )
        if existing and existing[0].effective_to is None:
            existing[0].effective_to = effective_from - timedelta(days=1)
            existing[0].save(update_fields=["effective_to", "updated_at"])
        elif existing and existing[0].effective_to >= effective_from:
            raise ValidationError({"effective_from": "Overlaps an existing salary record."})
        return cls.objects.create(
            employee=employee, basic_salary=basic_salary, effective_from=effective_from,
            reason=reason, created_by=user, contract=contract,
        )
