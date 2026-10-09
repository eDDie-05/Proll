import os

from drf_spectacular.utils import extend_schema

from django.http import FileResponse
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import audit
from apps.core.models import AuditLog
from apps.core.permissions import HasPermissionCode, crud_permissions
from apps.core.views_mixins import AuditedModelViewSet

from .models import Department, Employee, EmploymentContract, EmploymentType, Position, SalaryRecord
from .serializers import (
    DepartmentSerializer,
    EmployeeListSerializer,
    EmployeeSelfSerializer,
    EmployeeSerializer,
    EmploymentContractSerializer,
    EmploymentTypeSerializer,
    PositionSerializer,
    SalaryRecordSerializer,
)

LOOKUP_READ = ["employees.view", "employees.manage", "payroll.view", "reports.view", "reports.view_department"]


class DepartmentViewSet(AuditedModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    required_permissions = crud_permissions("employees.view", "employees.manage",
                                            list=LOOKUP_READ, retrieve=LOOKUP_READ)
    search_fields = ["code", "name"]
    filterset_fields = ["is_active"]
    pagination_class = None


class PositionViewSet(AuditedModelViewSet):
    queryset = Position.objects.select_related("department").all()
    serializer_class = PositionSerializer
    required_permissions = crud_permissions("employees.view", "employees.manage")
    search_fields = ["title"]
    filterset_fields = ["department", "is_active"]
    pagination_class = None


class EmploymentTypeViewSet(AuditedModelViewSet):
    queryset = EmploymentType.objects.all()
    serializer_class = EmploymentTypeSerializer
    required_permissions = crud_permissions("employees.view", "employees.manage")
    search_fields = ["code", "name"]
    pagination_class = None


class EmployeeViewSet(AuditedModelViewSet):
    queryset = Employee.objects.select_related("department", "position", "employment_type", "user").all()
    required_permissions = crud_permissions("employees.view", "employees.manage")
    search_fields = ["employee_number", "first_name", "middle_name", "last_name", "email", "phone"]
    filterset_fields = ["department", "status", "employment_type", "position"]
    ordering_fields = ["employee_number", "last_name", "employment_start_date", "department__name"]
    allow_destroy = False
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_serializer_class(self):
        if getattr(self, "swagger_fake_view", False):
            return EmployeeSerializer
        user = self.request.user
        if self.action in ("create", "update", "partial_update"):
            return EmployeeSerializer
        if user.has_code("employees.view_sensitive"):
            return EmployeeSerializer
        return EmployeeListSerializer

    @action(detail=True, methods=["get"], url_path="salary-history")
    def salary_history(self, request, pk=None):
        if not request.user.has_code("salary.view"):
            self.permission_denied(request)
        employee = self.get_object()
        return Response(SalaryRecordSerializer(employee.salary_records.all(), many=True).data)


class EmploymentContractViewSet(AuditedModelViewSet):
    queryset = EmploymentContract.objects.select_related("employee", "employment_type", "department", "position")
    serializer_class = EmploymentContractSerializer
    required_permissions = crud_permissions("contracts.manage", "contracts.manage")
    filterset_fields = ["employee", "status", "employment_type", "department"]
    search_fields = ["contract_number", "employee__first_name", "employee__last_name", "employee__employee_number"]
    ordering_fields = ["start_date", "end_date", "contract_number"]
    allow_destroy = False
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @action(detail=True, methods=["get"])
    def document(self, request, pk=None):
        """Stream the contract document to authorised users only (documents are never served publicly)."""
        contract = self.get_object()
        if not contract.document:
            raise NotFound("No document uploaded.")
        audit.record(AuditLog.Action.EXPORT, contract, message="Contract document downloaded")
        return FileResponse(contract.document.open("rb"), as_attachment=True,
                            filename=f"{contract.contract_number}{os.path.splitext(contract.document.name)[1]}")


class SalaryRecordViewSet(AuditedModelViewSet):
    """Salary history is append-only: no update/delete endpoints. Corrections = new record or payroll adjustment."""

    queryset = SalaryRecord.objects.select_related("employee", "created_by").all()
    serializer_class = SalaryRecordSerializer
    required_permissions = crud_permissions("salary.view", "salary.manage")
    filterset_fields = ["employee"]
    search_fields = ["employee__employee_number", "employee__first_name", "employee__last_name"]
    ordering_fields = ["effective_from", "basic_salary"]
    http_method_names = ["get", "post", "head", "options"]

    def perform_create(self, serializer):
        employee = serializer.validated_data["employee"]
        if employee.status not in Employee.PAYABLE_STATUSES:
            raise ValidationError({"employee": "Salary can only be set for active employees."})
        super().perform_create(serializer)


def _self_employee(request):
    emp = getattr(request.user, "employee", None)
    if emp is None:
        raise NotFound("Your user account is not linked to an employee record.")
    return emp


class SelfProfileView(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode]
    required_permissions = {"get": "self.view"}
    serializer_class = EmployeeSelfSerializer

    def get(self, request):
        return Response(EmployeeSelfSerializer(_self_employee(request), context={"request": request}).data)


class SelfSalaryHistoryView(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode]
    required_permissions = {"get": "self.view"}

    @extend_schema(responses=SalaryRecordSerializer(many=True))
    def get(self, request):
        emp = _self_employee(request)
        return Response(SalaryRecordSerializer(emp.salary_records.all(), many=True).data)
