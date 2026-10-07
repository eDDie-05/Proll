"""Audit logging service. All modules record significant events through `record()`."""
import datetime
import decimal
import uuid

from django.db import models
from django.db.models.fields.files import FieldFile

from .middleware import get_client_ip, get_current_request
from .models import AuditLog

# Never store these in audit payloads.
REDACTED_FIELDS = {"password", "token", "refresh", "access"}


def _serialize(value):
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, FieldFile):
        return value.name or None
    if isinstance(value, models.Model):
        return value.pk
    return value


def snapshot(instance):
    """Return a JSON-safe dict of concrete field values for an instance."""
    if instance is None:
        return None
    data = {}
    for field in instance._meta.concrete_fields:
        name = field.attname
        if name in REDACTED_FIELDS:
            continue
        data[name] = _serialize(getattr(instance, name))
    return data


def diff(old, new):
    """Reduce two snapshots to only the fields that changed."""
    if old is None or new is None:
        return old, new
    changed = {k for k in set(old) | set(new) if old.get(k) != new.get(k)}
    changed.discard("updated_at")
    return {k: old.get(k) for k in changed}, {k: new.get(k) for k in changed}


def record(action, instance=None, *, user=None, old=None, new=None, message="", model=None, object_id=None, request=None):
    request = request or get_current_request()
    if user is None and request is not None and getattr(request, "user", None) is not None:
        if request.user.is_authenticated:
            user = request.user
    return AuditLog.objects.create(
        user=user,
        username=getattr(user, "username", "") or "",
        action=action,
        model=model or (instance._meta.label if instance is not None else ""),
        object_id=str(object_id if object_id is not None else getattr(instance, "pk", "") or ""),
        object_repr=str(instance)[:255] if instance is not None else "",
        old_values=old,
        new_values=new,
        ip_address=get_client_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:255] if request is not None else ""),
        message=message,
    )
