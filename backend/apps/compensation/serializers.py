from rest_framework import serializers

from apps.core.serializers import ModelCleanMixin

from .models import AllowanceType, DeductionType, EmployeeAllowance, EmployeeDeduction, Loan, LoanRepayment


class AllowanceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AllowanceType
        exclude = ["created_by"]
        read_only_fields = ["created_at", "updated_at"]


class EmployeeAllowanceSerializer(ModelCleanMixin, serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    allowance_name = serializers.CharField(source="allowance_type.name", read_only=True)
    calculation_type = serializers.CharField(source="allowance_type.calculation_type", read_only=True)
    is_taxable = serializers.BooleanField(source="allowance_type.is_taxable", read_only=True)

    class Meta:
        model = EmployeeAllowance
        exclude = ["created_by"]
        read_only_fields = ["created_at", "updated_at"]


class DeductionTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeductionType
        exclude = ["created_by"]
        read_only_fields = ["created_at", "updated_at"]


class EmployeeDeductionSerializer(ModelCleanMixin, serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    deduction_name = serializers.CharField(source="deduction_type.name", read_only=True)
    is_statutory = serializers.BooleanField(source="deduction_type.is_statutory", read_only=True)

    class Meta:
        model = EmployeeDeduction
        exclude = ["created_by"]
        read_only_fields = ["created_at", "updated_at"]


class LoanRepaymentSerializer(serializers.ModelSerializer):
    period_name = serializers.CharField(source="payroll_period.name", read_only=True, default=None)

    class Meta:
        model = LoanRepayment
        fields = ["id", "loan", "amount", "date", "source", "payroll_period", "period_name", "reference", "created_at"]
        read_only_fields = ["source", "payroll_period", "created_at"]

    def validate(self, attrs):
        loan = attrs["loan"]
        if loan.status != Loan.Status.ACTIVE:
            raise serializers.ValidationError("Manual repayments can only be recorded against active loans.")
        if attrs["amount"] > loan.remaining_balance:
            raise serializers.ValidationError({"amount": f"Exceeds remaining balance {loan.remaining_balance}."})
        return attrs


class LoanSerializer(ModelCleanMixin, serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    amount_repaid = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    remaining_balance = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.username", read_only=True, default=None)
    repayments = LoanRepaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Loan
        exclude = ["created_by"]
        read_only_fields = ["status", "approved_by", "approved_at", "total_repayable", "created_at", "updated_at"]

    def validate(self, attrs):
        if self.instance and self.instance.status != Loan.Status.PENDING:
            locked = {"principal", "interest_rate", "installment_amount", "number_of_installments", "employee"}
            changed = [k for k in locked if k in attrs and attrs[k] != getattr(self.instance, k)]
            if changed:
                raise serializers.ValidationError(f"Cannot change {', '.join(changed)} after approval.")
        return super().validate(attrs)
