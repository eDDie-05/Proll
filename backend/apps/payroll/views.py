from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import audit
from apps.core.models import AuditLog
from apps.core.permissions import HasPermissionCode, crud_permissions
from apps.core.views_mixins import AuditedModelViewSet

from . import engine, services, workflow
from .models import BankExportFormat, Payment, PayrollAdjustment, PayrollItem, PayrollLine, PayrollPeriod, Payslip
from .serializers import (
    BankExportFormatSerializer,
    CommentSerializer,
    PaymentSerializer,
    PayrollAdjustmentSerializer,
    PayrollItemDetailSerializer,
    PayrollItemListSerializer,
    PayrollLineSerializer,
    PayrollPeriodSerializer,
    PayslipSerializer,
    RecordPaymentsSerializer,
    StatusChangeSerializer,
)

S = PayrollPeriod.Status
VIEW_ANY = ["payroll.view", "payroll.view_approved", "payroll.approve", "payroll.prepare"]


def visible_periods(user):
    """Payroll periods a user may see. Full viewers see everything; approvers see REVIEW and released ones."""
    qs = PayrollPeriod.objects.all()
    if user.has_code("payroll.view") or user.has_code("payroll.prepare"):
        return qs
    statuses = []
    if user.has_code("payroll.view_approved"):
        statuses += list(PayrollPeriod.RELEASED_STATUSES)
    if user.has_code("payroll.approve"):
        statuses += [S.REVIEW, *PayrollPeriod.RELEASED_STATUSES]
    return qs.filter(status__in=set(statuses))


def _pdf_response(content, filename):
    resp = HttpResponse(content, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


def _run_workflow(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except workflow.PermissionDenied as e:
        raise PermissionDenied(str(e))
    except (workflow.WorkflowError, engine.PayrollError, services.ServiceError) as e:
        raise ValidationError({"detail": str(e)})


class PayrollPeriodViewSet(AuditedModelViewSet):
    serializer_class = PayrollPeriodSerializer
    required_permissions = {
        "list": VIEW_ANY, "retrieve": VIEW_ANY, "items": VIEW_ANY, "history": VIEW_ANY,
        "approval_check": VIEW_ANY, "summary_pdf": VIEW_ANY + ["reports.view"],
        "create": "payroll.prepare", "update": "payroll.prepare", "partial_update": "payroll.prepare",
        "destroy": "payroll.prepare", "calculate": "payroll.prepare", "submit": "payroll.prepare",
        "approve": "payroll.approve", "reject": "payroll.approve", "mark_paid": "payments.manage",
        "close": "payroll.close", "record_payments": "payments.manage", "payments": ["payments.view", "payments.manage"],
        "bank_export": "payments.export", "generate_payslips": "payslips.generate",
    }
    filterset_fields = ["status"]
    search_fields = ["name"]
    ordering_fields = ["start_date", "name", "status"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PayrollPeriod.objects.none()
        return visible_periods(self.request.user).select_related(
            "calculated_by", "submitted_by", "approved_by", "paid_by", "closed_by")

    def perform_destroy(self, instance):
        if instance.status != S.DRAFT or instance.runs.exists():
            raise ValidationError("Only DRAFT periods that were never calculated can be deleted.")
        super().perform_destroy(instance)

    def _comment(self, request):
        ser = CommentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return ser.validated_data.get("comment", "")

    def _period_response(self, period):
        period.refresh_from_db()
        return Response(PayrollPeriodSerializer(period).data)

    @action(detail=True, methods=["post"])
    def calculate(self, request, pk=None):
        period = self.get_object()
        _run_workflow(workflow.calculate, period, request.user)
        return self._period_response(period)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        period = self.get_object()
        _run_workflow(workflow.submit_for_review, period, request.user, self._comment(request))
        return self._period_response(period)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        period = self.get_object()
        _run_workflow(workflow.approve, period, request.user, self._comment(request))
        return self._period_response(period)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        period = self.get_object()
        _run_workflow(workflow.reject, period, request.user, self._comment(request))
        return self._period_response(period)

    @action(detail=True, methods=["post"], url_path="mark-paid")
    def mark_paid(self, request, pk=None):
        period = self.get_object()
        _run_workflow(workflow.mark_paid, period, request.user, self._comment(request))
        return self._period_response(period)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        period = self.get_object()
        _run_workflow(workflow.close, period, request.user, self._comment(request))
        return self._period_response(period)

    @action(detail=True, methods=["get"], url_path="approval-check")
    def approval_check(self, request, pk=None):
        period = self.get_object()
        blockers = workflow.approval_blockers(period, request.user)
        return Response({"can_approve": not blockers and request.user.has_code("payroll.approve"), "blockers": blockers})

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        period = self.get_object()
        return Response(StatusChangeSerializer(period.status_history.select_related("user"), many=True).data)

    @action(detail=True, methods=["get"])
    def items(self, request, pk=None):
        period = self.get_object()
        run = period.current_run
        if not run:
            return Response([])
        qs = run.items.select_related("payment").prefetch_related("payslip")
        dept = request.query_params.get("department")
        if dept:
            qs = qs.filter(department_id=dept)
        search = request.query_params.get("q")
        if search:
            qs = qs.filter(Q(employee_name__icontains=search) | Q(employee_number__icontains=search))
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(PayrollItemListSerializer(page, many=True).data)
        return Response(PayrollItemListSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"])
    def payments(self, request, pk=None):
        period = self.get_object()
        run = period.current_run
        qs = Payment.objects.filter(item__run=run).select_related("item__run__period", "recorded_by") if run else Payment.objects.none()
        return Response(PaymentSerializer(qs, many=True).data)

    @extend_schema(request=RecordPaymentsSerializer)
    @action(detail=True, methods=["post"], url_path="record-payments")
    def record_payments(self, request, pk=None):
        period = self.get_object()
        ser = RecordPaymentsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        updated = _run_workflow(workflow.record_payments, period, request.user, d.get("payment_ids"), d["status"],
                                d.get("payment_date"), d.get("reference", ""), d.get("notes", ""))
        return Response({"updated": len(updated)})

    @action(detail=True, methods=["get"], url_path="bank-export")
    def bank_export(self, request, pk=None):
        period = self.get_object()
        fmt = get_object_or_404(BankExportFormat, pk=request.query_params.get("export_format"), is_active=True)
        content = _run_workflow(services.bank_export, period, fmt, request.user)
        resp = HttpResponse(content, content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="bank-{slugify(period.name)}-{slugify(fmt.name)}.csv"'
        return resp

    @action(detail=True, methods=["post"], url_path="generate-payslips")
    def generate_payslips(self, request, pk=None):
        period = self.get_object()
        created = _run_workflow(services.generate_payslips, period, request.user)
        return Response({"generated": len(created)})

    @action(detail=True, methods=["get"], url_path="summary-pdf")
    def summary_pdf(self, request, pk=None):
        from apps.reports import services as report_services

        period = self.get_object()
        if not period.current_run:
            raise ValidationError("Payroll has not been calculated.")
        content = report_services.payroll_summary_pdf(period)
        audit.record(AuditLog.Action.EXPORT, period, message="Payroll summary PDF")
        return _pdf_response(content, f"payroll-summary-{slugify(period.name)}.pdf")


class PayrollItemViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Calculation breakdown of one employee in a payroll run (read-only)."""

    serializer_class = PayrollItemDetailSerializer
    permission_classes = [HasPermissionCode]
    required_permissions = {"*": VIEW_ANY}

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PayrollItem.objects.none()
        return PayrollItem.objects.filter(run__period__in=visible_periods(self.request.user)).select_related(
            "run__period", "payment").prefetch_related("lines__statutory_rule")


class PayrollAdjustmentViewSet(AuditedModelViewSet):
    queryset = PayrollAdjustment.objects.select_related("employee", "target_period", "original_period",
                                                        "approved_by", "created_by")
    serializer_class = PayrollAdjustmentSerializer
    required_permissions = crud_permissions(["payroll.view", "payroll.adjust"], "payroll.adjust",
                                            approve="payroll.approve", reject="payroll.approve")
    filterset_fields = ["employee", "target_period", "original_period", "status", "category"]
    search_fields = ["employee__employee_number", "employee__first_name", "employee__last_name", "name"]

    def perform_update(self, serializer):
        if serializer.instance.status != PayrollAdjustment.Status.PENDING:
            raise ValidationError("Only pending adjustments can be edited.")
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        if instance.status != PayrollAdjustment.Status.PENDING:
            raise ValidationError("Only pending adjustments can be deleted.")
        super().perform_destroy(instance)

    def _decide(self, request, to):
        adj = self.get_object()
        if adj.status != PayrollAdjustment.Status.PENDING:
            raise ValidationError("Adjustment already decided.")
        if adj.created_by_id == request.user.id and not request.user.is_superuser:
            raise ValidationError("Segregation of duties: you cannot approve your own adjustment.")
        if adj.target_period.status not in PayrollPeriod.EDITABLE_STATUSES:
            raise ValidationError("Target period is no longer open; retarget the adjustment first.")
        with transaction.atomic():
            adj.status = to
            adj.approved_by, adj.approved_at = request.user, timezone.now()
            adj.save()
            audit.record(AuditLog.Action.UPDATE, adj, old={"status": "PENDING"}, new={"status": to})
        return Response(PayrollAdjustmentSerializer(adj).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._decide(request, PayrollAdjustment.Status.APPROVED)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._decide(request, PayrollAdjustment.Status.REJECTED)


class BankExportFormatViewSet(AuditedModelViewSet):
    queryset = BankExportFormat.objects.all()
    serializer_class = BankExportFormatSerializer
    required_permissions = crud_permissions(["payments.view", "payments.export"], "payments.export")
    pagination_class = None

    @action(detail=False, methods=["get"], url_path="available-fields")
    def available_fields(self, request):
        return Response(BankExportFormat.AVAILABLE_FIELDS)


class PaymentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Payment.objects.select_related("item__run__period", "recorded_by").filter(item__run__is_current=True)
    serializer_class = PaymentSerializer
    permission_classes = [HasPermissionCode]
    required_permissions = {"*": ["payments.view", "payments.manage"]}
    filterset_fields = {"status": ["exact"], "item__run__period": ["exact"], "method": ["exact"]}
    search_fields = ["item__employee_number", "item__employee_name", "reference", "account_number"]
    ordering_fields = ["amount", "payment_date", "status"]


class PayslipViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = PayslipSerializer
    permission_classes = [HasPermissionCode]
    required_permissions = {"*": ["payslips.generate", "payroll.view"]}
    filterset_fields = {"item": ["exact"], "item__run__period": ["exact"], "item__department": ["exact"]}
    search_fields = ["payslip_number", "item__employee_number", "item__employee_name"]
    ordering_fields = ["generated_at", "payslip_number"]

    def get_queryset(self):
        return Payslip.objects.select_related("item__run__period", "generated_by").filter(item__run__is_current=True)

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        slip = self.get_object()
        return _pdf_response(services.render_payslip(slip, request.user), f"{slip.payslip_number}.pdf")


# ---------------------------------------------------------------- employee self-service
class _SelfMixin:
    permission_classes = [IsAuthenticated, HasPermissionCode]
    required_permissions = {"get": "self.view"}

    def employee(self, request):
        emp = getattr(request.user, "employee", None)
        if emp is None:
            raise NotFound("Your user account is not linked to an employee record.")
        return emp

    def own_payslips(self, request):
        return Payslip.objects.filter(
            item__employee=self.employee(request), item__run__is_current=True,
            item__run__period__status__in=PayrollPeriod.RELEASED_STATUSES,
        ).select_related("item__run__period", "generated_by")


class SelfPayslipListView(_SelfMixin, APIView):
    @extend_schema(operation_id="self_payslips_list", responses=PayslipSerializer(many=True))
    def get(self, request):
        return Response(PayslipSerializer(self.own_payslips(request).order_by("-item__run__period__start_date"), many=True).data)


class SelfPayslipDetailView(_SelfMixin, APIView):
    @extend_schema(responses=PayrollItemDetailSerializer)
    def get(self, request, pk):
        slip = get_object_or_404(self.own_payslips(request), pk=pk)
        item = PayrollItem.objects.prefetch_related("lines").select_related("run__period").get(pk=slip.item_id)
        data = PayrollItemDetailSerializer(item).data
        data["payslip"] = PayslipSerializer(slip).data
        return Response(data)


class SelfPayslipPdfView(_SelfMixin, APIView):
    @extend_schema(responses={(200, "application/pdf"): OpenApiTypes.BINARY})
    def get(self, request, pk):
        slip = get_object_or_404(self.own_payslips(request), pk=pk)
        return _pdf_response(services.render_payslip(slip, request.user), f"{slip.payslip_number}.pdf")


class SelfDeductionsView(_SelfMixin, APIView):
    @extend_schema(responses=PayrollLineSerializer(many=True))
    def get(self, request):
        lines = PayrollLine.objects.filter(
            item__employee=self.employee(request), item__run__is_current=True,
            item__run__period__status__in=PayrollPeriod.RELEASED_STATUSES,
            category=PayrollLine.Category.DEDUCTION,
        ).select_related("item__run__period").order_by("-item__run__period__start_date", "sort_order")
        data = []
        for l in lines:
            row = PayrollLineSerializer(l).data
            row["period_name"] = l.item.run.period.name
            row["period_start"] = l.item.run.period.start_date
            row.pop("detail", None)
            data.append(row)
        return Response(data)
