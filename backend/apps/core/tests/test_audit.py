import pytest
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.utils import DatabaseError

from apps.core import audit
from apps.core.models import AuditLog, CompanySettings

pytestmark = pytest.mark.django_db


def test_audit_record_immutable_in_orm(admin_user):
    log = audit.record(AuditLog.Action.CREATE, admin_user, user=admin_user, new={"a": 1})
    log.message = "tamper"
    with pytest.raises(ValidationError):
        log.save()
    with pytest.raises(ValidationError):
        log.delete()


@pytest.mark.skipif(connection.vendor != "postgresql", reason="trigger is PostgreSQL-only")
def test_audit_record_immutable_in_database(admin_user):
    log = audit.record(AuditLog.Action.CREATE, admin_user, user=admin_user)
    with pytest.raises(DatabaseError), transaction.atomic():
        AuditLog.objects.filter(pk=log.pk).update(message="tamper")
    with pytest.raises(DatabaseError), transaction.atomic():
        AuditLog.objects.filter(pk=log.pk).delete()


def test_audit_api_read_only(admin_user, client_for, make_user):
    c = client_for(admin_user)
    audit.record(AuditLog.Action.LOGIN, admin_user, user=admin_user)
    r = c.get("/api/audit-logs/")
    assert r.status_code == 200 and r.data["count"] >= 1
    lid = r.data["results"][0]["id"]
    assert c.delete(f"/api/audit-logs/{lid}/").status_code == 405
    assert c.patch(f"/api/audit-logs/{lid}/", {"message": "x"}).status_code == 405
    assert c.post("/api/audit-logs/", {}).status_code == 405
    assert client_for(make_user("HR_MANAGER", "hr")).get("/api/audit-logs/").status_code == 403


def test_password_never_in_audit(admin_user, client_for):
    c = client_for(admin_user)
    c.post("/api/users/", {"username": "u1", "email": "u1@x.test", "password": "Very-Strong-Pass-7", "role": "EMPLOYEE"},
           format="json")
    log = AuditLog.objects.filter(model="accounts.User", action="CREATE").latest("id")
    assert "password" not in log.new_values


def test_company_settings(admin_user, client_for, make_user):
    c = client_for(admin_user)
    assert c.get("/api/company-settings/").data["name"] == "Bravado Company Ltd"
    r = c.patch("/api/company-settings/", {"tin": "100-200-300"}, format="json")
    assert r.status_code == 200 and CompanySettings.load().tin == "100-200-300"
    emp = client_for(make_user("EMPLOYEE", "e"))
    assert emp.get("/api/company-settings/").status_code == 200
    assert emp.patch("/api/company-settings/", {"tin": "x"}, format="json").status_code == 403


def test_api_schema_available(admin_user, client_for):
    r = client_for(admin_user).get("/api/schema/")
    assert r.status_code == 200
