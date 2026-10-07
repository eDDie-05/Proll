from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import audit
from apps.core.models import AuditLog
from apps.core.permissions import HasPermissionCode
from apps.employees.models import Employee
from apps.payroll.models import PayrollPeriod

from . import exporters, services

EXPORT_PARAM = OpenApiParameter("export", str, enum=["csv", "xlsx", "pdf"], required=False,
                                description="Download format; omit for JSON")
PERIOD_PARAM = OpenApiParameter("period", int, required=True)
DEPT_PARAM = OpenApiParameter("department", int, required=False)
REPORT_RESPONSES = {(200, "application/json"): OpenApiTypes.OBJECT, (200, "application/pdf"): OpenApiTypes.BINARY,
                    (200, "text/csv"): OpenApiTypes.BINARY}


class ReportAccessMixin:
    """reports.view = all departments/periods; reports.view_department = own department, released periods."""

    permission_classes = [HasPermissionCode]
    required_permissions = {"get": ["reports.view", "reports.view_department"]}
    department_scoped_allowed = True

    def scope(self, request):
        user = request.user
        if user.has_code("reports.view"):
            dept = request.query_params.get("department")
            return (int(dept) if dept and dept.isdigit() else None), False
        if not self.department_scoped_allowed:
            raise PermissionDenied("Requires permission 'reports.view'.")
        emp = getattr(user, "employee", None)
        if emp is None:
            raise PermissionDenied("Department reports require a linked employee record.")
        return emp.department_id, True

    def period(self, request, released_only):
        pid = request.query_params.get("period")
        if not pid:
            raise ValidationError({"period": "This query parameter is required."})
        qs = PayrollPeriod.objects.all()
        if released_only:
            qs = qs.filter(status__in=PayrollPeriod.RELEASED_STATUSES)
        period = get_object_or_404(qs, pk=pid)
        if not period.current_run:
            raise ValidationError({"period": "Payroll has not been calculated for this period."})
        return period

    def render(self, request, report):
        export = request.query_params.get("export")
        if export:
            if not request.user.has_code("reports.export") and not request.user.has_code("reports.view_department"):
                raise PermissionDenied("Requires permission 'reports.export'.")
            resp = exporters.respond(report, export)
            if resp is None:
                raise ValidationError({"export": "Use csv, xlsx or pdf."})
            audit.record(AuditLog.Action.EXPORT, model="reports", message=f"{report.title} - {report.subtitle} ({export})")
            return resp
        return Response(report.as_dict())


def _period_report_view(builder, scoped=True):
    class View(ReportAccessMixin, APIView):
        department_scoped_allowed = scoped

        @extend_schema(responses=REPORT_RESPONSES, parameters=[PERIOD_PARAM, DEPT_PARAM, EXPORT_PARAM])
        def get(self, request):
            dept, restricted = self.scope(request)
            period = self.period(request, released_only=restricted)
            return self.render(request, builder(period, dept))

    View.__name__ = f"{builder.__name__.title().replace('_', '')}View"
    return View


PayrollSummaryReportView = _period_report_view(services.summary_report)
DepartmentReportView = _period_report_view(services.department_report)
PayrollRegisterView = _period_report_view(services.employee_register, scoped=False)
DeductionReportView = _period_report_view(services.deduction_report, scoped=False)
TaxReportView = _period_report_view(services.tax_report, scoped=False)
ContributionReportView = _period_report_view(services.contribution_report, scoped=False)
PaymentReportView = _period_report_view(services.payment_report, scoped=False)


class PayrollHistoryView(ReportAccessMixin, APIView):
    @extend_schema(responses=REPORT_RESPONSES, parameters=[OpenApiParameter("year", int), EXPORT_PARAM])
    def get(self, request):
        _, restricted = self.scope(request)
        year = request.query_params.get("year")
        statuses = PayrollPeriod.RELEASED_STATUSES if restricted else None
        return self.render(request, services.payroll_history(statuses, int(year) if year and year.isdigit() else None))


class EmployeeSalaryReportView(ReportAccessMixin, APIView):
    department_scoped_allowed = False
    required_permissions = {"get": "reports.view"}

    @extend_schema(responses=REPORT_RESPONSES, parameters=[OpenApiParameter("employee", int), DEPT_PARAM, EXPORT_PARAM])
    def get(self, request):
        dept, _ = self.scope(request)
        emp = request.query_params.get("employee")
        return self.render(request, services.employee_salary_report(int(emp) if emp and emp.isdigit() else None, dept))


class EmployeeStatementView(ReportAccessMixin, APIView):
    """Salary statement for an employee. Employees may request their own (employee param ignored)."""

    required_permissions = {"get": ["reports.view", "self.view"]}

    @extend_schema(responses=REPORT_RESPONSES, parameters=[OpenApiParameter("employee", int), OpenApiParameter("year", int), EXPORT_PARAM])
    def get(self, request):
        if request.user.has_code("reports.view") and request.query_params.get("employee"):
            employee = get_object_or_404(Employee, pk=request.query_params["employee"])
        else:
            employee = getattr(request.user, "employee", None)
            if employee is None:
                raise NotFound("Your user account is not linked to an employee record.")
        year = request.query_params.get("year")
        report = services.employee_statement(employee, int(year) if year and year.isdigit() else None)
        export = request.query_params.get("export")
        if export:
            resp = exporters.respond(report, export)
            if resp is None:
                raise ValidationError({"export": "Use csv, xlsx or pdf."})
            audit.record(AuditLog.Action.EXPORT, employee, message=f"Salary statement ({export})")
            return resp
        return Response(report.as_dict())


class DashboardView(ReportAccessMixin, APIView):
    required_permissions = {"get": ["reports.view", "reports.view_department", "payroll.view", "payroll.prepare"]}

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        user = request.user
        if user.has_code("reports.view") or user.has_code("payroll.view") or user.has_code("payroll.prepare"):
            return Response(services.dashboard())
        emp = getattr(user, "employee", None)
        if emp is None:
            raise PermissionDenied("Department dashboard requires a linked employee record.")
        return Response(services.dashboard(department_id=emp.department_id, released_only=True))
