from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core import audit
from apps.core.models import AuditLog
from apps.core.permissions import crud_permissions
from apps.core.views_mixins import AuditedModelViewSet

from .models import AllowanceType, DeductionType, EmployeeAllowance, EmployeeDeduction, Loan, LoanRepayment
from .serializers import (
    AllowanceTypeSerializer,
    DeductionTypeSerializer,
    EmployeeAllowanceSerializer,
    EmployeeDeductionSerializer,
    LoanRepaymentSerializer,
    LoanSerializer,
)

READ_TYPES = ["allowances.manage", "deductions.manage", "payroll.view", "employees.view"]


class AllowanceTypeViewSet(AuditedModelViewSet):
    queryset = AllowanceType.objects.all()
    serializer_class = AllowanceTypeSerializer
    required_permissions = crud_permissions("allowances.manage", "allowances.manage", list=READ_TYPES, retrieve=READ_TYPES)
    search_fields = ["code", "name"]
    filterset_fields = ["category", "is_active", "is_taxable"]
    pagination_class = None


class EmployeeAllowanceViewSet(AuditedModelViewSet):
    queryset = EmployeeAllowance.objects.select_related("employee", "allowance_type").all()
    serializer_class = EmployeeAllowanceSerializer
    required_permissions = crud_permissions("allowances.manage", "allowances.manage")
    search_fields = ["employee__employee_number", "employee__first_name", "employee__last_name", "allowance_type__name"]
    filterset_fields = ["employee", "allowance_type", "is_recurring"]
    ordering_fields = ["effective_from", "employee__employee_number"]


class DeductionTypeViewSet(AuditedModelViewSet):
    queryset = DeductionType.objects.all()
    serializer_class = DeductionTypeSerializer
    required_permissions = crud_permissions("deductions.manage", "deductions.manage", list=READ_TYPES, retrieve=READ_TYPES)
    search_fields = ["code", "name"]
    filterset_fields = ["category", "is_active", "is_statutory"]
    pagination_class = None


class EmployeeDeductionViewSet(AuditedModelViewSet):
    queryset = EmployeeDeduction.objects.select_related("employee", "deduction_type").all()
    serializer_class = EmployeeDeductionSerializer
    required_permissions = crud_permissions("deductions.manage", "deductions.manage")
    search_fields = ["employee__employee_number", "employee__first_name", "employee__last_name", "deduction_type__name"]
    filterset_fields = ["employee", "deduction_type", "is_active", "is_recurring"]
    ordering_fields = ["start_date", "employee__employee_number"]


class LoanViewSet(AuditedModelViewSet):
    queryset = Loan.objects.select_related("employee", "approved_by").prefetch_related("repayments__payroll_period")
    serializer_class = LoanSerializer
    required_permissions = crud_permissions("loans.view", "loans.manage", approve="loans.manage", cancel="loans.manage")
    search_fields = ["reference", "employee__employee_number", "employee__first_name", "employee__last_name"]
    filterset_fields = ["employee", "status", "loan_type"]
    ordering_fields = ["start_date", "principal", "reference"]
    allow_destroy = False

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        loan = self.get_object()
        if loan.status != Loan.Status.PENDING:
            raise ValidationError("Only pending loans can be approved.")
        if loan.created_by_id == request.user.id and not request.user.is_superuser:
            raise ValidationError("A loan cannot be approved by the user who recorded it.")
        loan.status = Loan.Status.ACTIVE
        loan.approved_by = request.user
        loan.approved_at = timezone.now()
        loan.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        audit.record(AuditLog.Action.UPDATE, loan, old={"status": "PENDING"}, new={"status": "ACTIVE"}, message="Loan approved")
        return Response(LoanSerializer(loan).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        loan = self.get_object()
        if loan.status not in (Loan.Status.PENDING, Loan.Status.ACTIVE):
            raise ValidationError("Loan cannot be cancelled in its current state.")
        old = loan.status
        loan.status = Loan.Status.CANCELLED
        loan.save(update_fields=["status", "updated_at"])
        audit.record(AuditLog.Action.UPDATE, loan, old={"status": old}, new={"status": "CANCELLED"},
                     message=request.data.get("reason", "Loan cancelled")[:500])
        return Response(LoanSerializer(loan).data)


class LoanRepaymentViewSet(AuditedModelViewSet):
    """Manual repayments only; payroll repayments are created automatically on payroll approval."""

    queryset = LoanRepayment.objects.select_related("loan", "payroll_period").all()
    serializer_class = LoanRepaymentSerializer
    required_permissions = crud_permissions("loans.view", "loans.manage")
    filterset_fields = ["loan", "source", "payroll_period"]
    http_method_names = ["get", "post", "head", "options"]

    def perform_create(self, serializer):
        with transaction.atomic():
            Loan.objects.select_for_update().get(pk=serializer.validated_data["loan"].pk)
            instance = serializer.save(source=LoanRepayment.Source.MANUAL, recorded_by=self.request.user)
            audit.record(AuditLog.Action.CREATE, instance, new=audit.snapshot(instance))
            loan = instance.loan
            if loan.remaining_balance <= 0:
                loan.status = Loan.Status.COMPLETED
                loan.save(update_fields=["status", "updated_at"])
