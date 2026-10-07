from django.db import transaction
from rest_framework import serializers

from apps.core.serializers import ModelCleanMixin

from .models import Department, Employee, EmploymentContract, EmploymentType, Position, SalaryRecord


class DepartmentSerializer(serializers.ModelSerializer):
    employee_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = ["id", "code", "name", "description", "is_active", "employee_count"]

    def get_employee_count(self, obj) -> int:
        return obj.employees.filter(status__in=Employee.PAYABLE_STATUSES).count()


class PositionSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)

    class Meta:
        model = Position
        fields = ["id", "title", "department", "department_name", "description", "is_active"]


class EmploymentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmploymentType
        fields = ["id", "code", "name", "description", "is_active"]


class EmployeeListSerializer(serializers.ModelSerializer):
    """Directory view: no bank, tax or social-security data."""

    full_name = serializers.CharField(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    position_title = serializers.CharField(source="position.title", read_only=True, default=None)
    employment_type_name = serializers.CharField(source="employment_type.name", read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id", "employee_number", "first_name", "middle_name", "last_name", "full_name", "email", "phone",
            "department", "department_name", "position", "position_title", "employment_type",
            "employment_type_name", "employment_start_date", "employment_end_date", "status",
        ]


class EmployeeSerializer(ModelCleanMixin, serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    position_title = serializers.CharField(source="position.title", read_only=True, default=None)
    employment_type_name = serializers.CharField(source="employment_type.name", read_only=True)
    current_basic_salary = serializers.SerializerMethodField()
    username = serializers.CharField(source="user.username", read_only=True, default=None)

    class Meta:
        model = Employee
        exclude = ["created_by"]
        read_only_fields = ["created_at", "updated_at"]

    def get_current_basic_salary(self, obj) -> str | None:
        request = self.context.get("request")
        if request and not request.user.has_code("salary.view") and getattr(request.user, "employee", None) != obj:
            return None
        rec = obj.current_salary()
        return str(rec.basic_salary) if rec else None

    def validate_employee_number(self, value):
        value = value.strip().upper()
        clash = Employee.objects.filter(employee_number__iexact=value).exclude(pk=getattr(self.instance, "pk", None))
        if clash.exists():
            raise serializers.ValidationError("An employee with this Employee ID already exists.")
        return value

    def validate_user(self, value):
        if value and Employee.objects.filter(user=value).exclude(pk=getattr(self.instance, "pk", None)).exists():
            raise serializers.ValidationError("This user account is already linked to another employee.")
        return value


class EmployeeSelfSerializer(EmployeeSerializer):
    """What an employee sees about themself."""

    class Meta(EmployeeSerializer.Meta):
        exclude = ["created_by", "user"]


class EmploymentContractSerializer(ModelCleanMixin, serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employment_type_name = serializers.CharField(source="employment_type.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    position_title = serializers.CharField(source="position.title", read_only=True, default=None)
    document_url = serializers.SerializerMethodField()
    create_salary_record = serializers.BooleanField(
        write_only=True, required=False, default=False,
        help_text="Also create an effective-dated salary record from the contract basic salary and start date.",
    )

    class Meta:
        model = EmploymentContract
        exclude = ["created_by"]
        read_only_fields = ["created_at", "updated_at"]

    def get_document_url(self, obj) -> str | None:
        return f"/contracts/{obj.pk}/document/" if obj.document else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["document"] = bool(instance.document)  # never expose the storage path
        return data

    def validate_basic_salary(self, value):
        if value < 0:
            raise serializers.ValidationError("Salary cannot be negative.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        create_salary = validated_data.pop("create_salary_record", False)
        contract = super().create(validated_data)
        if create_salary:
            SalaryRecord.create_new(
                contract.employee, contract.basic_salary, contract.start_date,
                reason=f"Contract {contract.contract_number}", user=validated_data.get("created_by"), contract=contract,
            )
        return contract

    def update(self, instance, validated_data):
        validated_data.pop("create_salary_record", None)
        return super().update(instance, validated_data)


class SalaryRecordSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    employee_number = serializers.CharField(source="employee.employee_number", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True, default=None)

    class Meta:
        model = SalaryRecord
        fields = [
            "id", "employee", "employee_name", "employee_number", "basic_salary", "effective_from",
            "effective_to", "reason", "contract", "created_at", "created_by_name",
        ]
        read_only_fields = ["effective_to", "created_at"]

    def validate_basic_salary(self, value):
        if value < 0:
            raise serializers.ValidationError("Salary cannot be negative.")
        return value

    def create(self, validated_data):
        return SalaryRecord.create_new(
            validated_data["employee"], validated_data["basic_salary"], validated_data["effective_from"],
            reason=validated_data.get("reason", ""), user=validated_data.get("created_by"),
            contract=validated_data.get("contract"),
        )
