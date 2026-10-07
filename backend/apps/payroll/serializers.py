from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.serializers import ModelCleanMixin

from .models import (
    BankExportFormat,
    Payment,
    PayrollAdjustment,
    PayrollItem,
    PayrollLine,
    PayrollPeriod,
    PayrollRun,
    PayrollStatusChange,
    Payslip,
)


def _username(field):
    return serializers.CharField(source=f"{field}.username", read_only=True, default=None)


class PayrollRunSerializer(serializers.ModelSerializer):
    calculated_by_name = _username("calculated_by")

    class Meta:
        model = PayrollRun
        exclude = []


class PayrollPeriodSerializer(ModelCleanMixin, serializers.ModelSerializer):
    current_run = serializers.SerializerMethodField()
    calculated_by_name = _username("calculated_by")
    submitted_by_name = _username("submitted_by")
    approved_by_name = _username("approved_by")
    paid_by_name = _username("paid_by")
    closed_by_name = _username("closed_by")

    class Meta:
        model = PayrollPeriod
        exclude = ["created_by"]
        read_only_fields = [
            "status", "calculated_by", "calculated_at", "submitted_by", "submitted_at", "approved_by",
            "approved_at", "paid_by", "paid_at", "closed_by", "closed_at", "created_at", "updated_at",
        ]

    @extend_schema_field(PayrollRunSerializer(allow_null=True))
    def get_current_run(self, obj):
        run = obj.current_run
        return PayrollRunSerializer(run).data if run else None

    def validate(self, attrs):
        if self.instance and self.instance.status != PayrollPeriod.Status.DRAFT:
            changed = [k for k in ("start_date", "end_date") if k in attrs and attrs[k] != getattr(self.instance, k)]
            if changed:
                raise serializers.ValidationError("Period dates can only be changed while in DRAFT.")
            if self.instance.is_locked:
                raise serializers.ValidationError(f"Payroll in status {self.instance.status} cannot be modified.")
        return super().validate(attrs)


class PayrollLineSerializer(serializers.ModelSerializer):
    statutory_rule_version = serializers.IntegerField(source="statutory_rule.version", read_only=True, default=None)

    class Meta:
        model = PayrollLine
        exclude = ["item"]


class PayrollItemListSerializer(serializers.ModelSerializer):
    payment_status = serializers.CharField(source="payment.status", read_only=True, default=None)
    has_payslip = serializers.SerializerMethodField()

    class Meta:
        model = PayrollItem
        fields = [
            "id", "employee", "employee_number", "employee_name", "department", "department_name", "job_title",
            "days_employed", "days_in_period", "monthly_basic_salary", "basic_earned", "gross_earnings",
            "taxable_income", "paye", "total_statutory_deductions", "total_other_deductions", "total_deductions",
            "net_salary", "total_employer_contributions", "employer_total_cost", "warnings", "payment_status",
            "has_payslip",
        ]

    def get_has_payslip(self, obj) -> bool:
        return hasattr(obj, "payslip")


class PayrollItemDetailSerializer(PayrollItemListSerializer):
    lines = PayrollLineSerializer(many=True, read_only=True)
    period = serializers.SerializerMethodField()

    class Meta(PayrollItemListSerializer.Meta):
        fields = PayrollItemListSerializer.Meta.fields + [
            "lines", "period", "social_security_base", "cash_emoluments", "proration_factor", "payment_method",
            "bank_name",
        ]

    def get_period(self, obj) -> dict:
        p = obj.run.period
        return {"id": p.id, "name": p.name, "status": p.status, "start_date": p.start_date, "end_date": p.end_date,
                "run_number": obj.run.run_number, "is_current_run": obj.run.is_current}


class StatusChangeSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = PayrollStatusChange
        fields = ["id", "from_status", "to_status", "action", "username", "timestamp", "comment"]


class PayrollAdjustmentSerializer(ModelCleanMixin, serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    target_period_name = serializers.CharField(source="target_period.name", read_only=True)
    original_period_name = serializers.CharField(source="original_period.name", read_only=True, default=None)
    approved_by_name = _username("approved_by")
    created_by_name = _username("created_by")

    class Meta:
        model = PayrollAdjustment
        exclude = []
        read_only_fields = ["status", "approved_by", "approved_at", "created_by", "created_at", "updated_at"]


class PaymentSerializer(serializers.ModelSerializer):
    employee_number = serializers.CharField(source="item.employee_number", read_only=True)
    employee_name = serializers.CharField(source="item.employee_name", read_only=True)
    department_name = serializers.CharField(source="item.department_name", read_only=True)
    period_name = serializers.CharField(source="item.run.period.name", read_only=True)
    period = serializers.IntegerField(source="item.run.period_id", read_only=True)
    recorded_by_name = _username("recorded_by")

    class Meta:
        model = Payment
        fields = "__all__"


class RecordPaymentsSerializer(serializers.Serializer):
    payment_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=True)
    status = serializers.ChoiceField(choices=Payment.Status.choices)
    payment_date = serializers.DateField(required=False)
    reference = serializers.CharField(required=False, allow_blank=True, max_length=100)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate(self, attrs):
        if attrs["status"] == Payment.Status.PAID and not attrs.get("payment_date"):
            raise serializers.ValidationError({"payment_date": "Payment date is required when marking as PAID."})
        return attrs


class BankExportFormatSerializer(ModelCleanMixin, serializers.ModelSerializer):
    class Meta:
        model = BankExportFormat
        exclude = ["created_by"]
        read_only_fields = ["created_at", "updated_at"]


class PayslipSerializer(serializers.ModelSerializer):
    employee_number = serializers.CharField(source="item.employee_number", read_only=True)
    employee_name = serializers.CharField(source="item.employee_name", read_only=True)
    department_name = serializers.CharField(source="item.department_name", read_only=True)
    period_name = serializers.CharField(source="item.run.period.name", read_only=True)
    period = serializers.IntegerField(source="item.run.period_id", read_only=True)
    period_start = serializers.DateField(source="item.run.period.start_date", read_only=True)
    net_salary = serializers.DecimalField(source="item.net_salary", max_digits=16, decimal_places=2, read_only=True)
    gross_earnings = serializers.DecimalField(source="item.gross_earnings", max_digits=16, decimal_places=2, read_only=True)
    total_deductions = serializers.DecimalField(source="item.total_deductions", max_digits=16, decimal_places=2, read_only=True)
    generated_by_name = _username("generated_by")

    class Meta:
        model = Payslip
        fields = [
            "id", "item", "payslip_number", "employee_number", "employee_name", "department_name", "period",
            "period_name", "period_start", "gross_earnings", "total_deductions", "net_salary", "generated_at",
            "generated_by_name", "download_count",
        ]


class CommentSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True)
