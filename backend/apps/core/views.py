import django_filters
from django.db import transaction
from rest_framework import mixins, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import audit
from .models import AuditLog, CompanySettings
from .permissions import HasPermissionCode
from .serializers import AuditLogSerializer, CompanySettingsSerializer


class CompanySettingsView(APIView):
    """Any authenticated user may read company identity; only company.manage may change it."""

    parser_classes = [JSONParser, MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated, HasPermissionCode]
    required_permissions = {"get": "self.view", "put": "company.manage", "patch": "company.manage"}
    serializer_class = CompanySettingsSerializer

    def get(self, request):
        return Response(CompanySettingsSerializer(CompanySettings.load(), context={"request": request}).data)

    def patch(self, request):
        obj = CompanySettings.load()
        ser = CompanySettingsSerializer(obj, data=request.data, partial=True, context={"request": request})
        ser.is_valid(raise_exception=True)
        with transaction.atomic():
            old = audit.snapshot(obj)
            ser.save()
            before, after = audit.diff(old, audit.snapshot(obj))
            audit.record(AuditLog.Action.UPDATE, obj, old=before, new=after)
        return Response(ser.data)

    put = patch


class AuditLogFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="timestamp", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="timestamp", lookup_expr="date__lte")

    class Meta:
        model = AuditLog
        fields = ["action", "model", "object_id", "user"]


class AuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Read-only. There is intentionally no create/update/delete endpoint for audit records."""

    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [HasPermissionCode]
    required_permissions = {"*": "audit.view"}
    filterset_class = AuditLogFilter
    search_fields = ["username", "object_repr", "message", "model"]
    ordering_fields = ["timestamp", "action", "username"]
