from django.db import models, transaction
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from . import audit
from .models import AuditLog
from .permissions import HasPermissionCode


class AuditedModelViewSet(viewsets.ModelViewSet):
    """ModelViewSet that records create/update/delete in the audit log with before/after values."""

    permission_classes = [HasPermissionCode]
    #: set False on models whose history must never be deleted
    allow_destroy = True

    def perform_create(self, serializer):
        with transaction.atomic():
            extra = {}
            if any(f.name == "created_by" for f in serializer.Meta.model._meta.fields):
                extra["created_by"] = self.request.user
            instance = serializer.save(**extra)
            audit.record(AuditLog.Action.CREATE, instance, new=audit.snapshot(instance))

    def perform_update(self, serializer):
        with transaction.atomic():
            old = audit.snapshot(serializer.instance)
            instance = serializer.save()
            before, after = audit.diff(old, audit.snapshot(instance))
            audit.record(AuditLog.Action.UPDATE, instance, old=before, new=after)

    def perform_destroy(self, instance):
        if not self.allow_destroy:
            raise ValidationError("Records of this type cannot be deleted; deactivate or end-date them instead.")
        with transaction.atomic():
            old = audit.snapshot(instance)
            try:
                instance.delete()
            except models.ProtectedError:
                raise ValidationError("This record is referenced by other records and cannot be deleted.")
            audit.record(AuditLog.Action.DELETE, instance, old=old)
