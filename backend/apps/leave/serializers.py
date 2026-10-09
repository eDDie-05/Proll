from rest_framework import serializers

from apps.core.serializers import ModelCleanMixin

from .models import LeaveRecord, LeaveType


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        exclude = ["created_by"]
        read_only_fields = ["created_at", "updated_at"]


class LeaveRecordSerializer(ModelCleanMixin, serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)
    payroll_effect = serializers.CharField(source="leave_type.payroll_effect", read_only=True)
    days = serializers.DecimalField(max_digits=5, decimal_places=1, required=False)

    class Meta:
        model = LeaveRecord
        exclude = ["created_by"]
        read_only_fields = ["status", "approved_by", "approved_at", "created_at", "updated_at"]
