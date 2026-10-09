from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core import audit
from apps.core.models import AuditLog
from apps.core.permissions import crud_permissions
from apps.core.views_mixins import AuditedModelViewSet

from .models import LeaveRecord, LeaveType
from .serializers import LeaveRecordSerializer, LeaveTypeSerializer


class LeaveTypeViewSet(AuditedModelViewSet):
    queryset = LeaveType.objects.all()
    serializer_class = LeaveTypeSerializer
    required_permissions = crud_permissions("leave.view", "leave.manage")
    pagination_class = None


class LeaveRecordViewSet(AuditedModelViewSet):
    queryset = LeaveRecord.objects.select_related("employee", "leave_type").all()
    serializer_class = LeaveRecordSerializer
    required_permissions = crud_permissions("leave.view", "leave.manage", approve="leave.manage",
                                            reject="leave.manage", cancel="leave.manage")
    filterset_fields = ["employee", "leave_type", "status"]
    search_fields = ["employee__employee_number", "employee__first_name", "employee__last_name"]
    ordering_fields = ["start_date", "end_date"]
    allow_destroy = False

    def perform_update(self, serializer):
        if serializer.instance.status != LeaveRecord.Status.PENDING:
            raise ValidationError("Only pending leave can be edited.")
        super().perform_update(serializer)

    def _transition(self, request, allowed_from, to):
        rec = self.get_object()
        if rec.status not in allowed_from:
            raise ValidationError(f"Cannot change leave from {rec.status} to {to}.")
        old = rec.status
        rec.status = to
        if to == LeaveRecord.Status.APPROVED:
            rec.approved_by, rec.approved_at = request.user, timezone.now()
        rec.save()
        audit.record(AuditLog.Action.UPDATE, rec, old={"status": old}, new={"status": to})
        return Response(LeaveRecordSerializer(rec).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._transition(request, [LeaveRecord.Status.PENDING], LeaveRecord.Status.APPROVED)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._transition(request, [LeaveRecord.Status.PENDING], LeaveRecord.Status.REJECTED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._transition(request, [LeaveRecord.Status.PENDING, LeaveRecord.Status.APPROVED],
                                LeaveRecord.Status.CANCELLED)
