import re

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.core.models import AuditLog
from conftest import PASSWORD

pytestmark = pytest.mark.django_db


def login(client, username, password=PASSWORD):
    return client.post("/api/auth/login/", {"username": username, "password": password}, format="json")


def test_login_returns_access_and_sets_httponly_refresh_cookie(make_user):
    make_user("HR_MANAGER", "hr")
    c = APIClient()
    r = login(c, "hr")
    assert r.status_code == 200
    assert r.data["access"]
    assert "employees.manage" in r.data["user"]["permissions"]
    cookie = r.cookies["bravado_refresh"]
    assert cookie["httponly"] and cookie["samesite"] == "Strict"
    assert "refresh" not in r.data
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    assert c.get("/api/auth/me/").data["username"] == "hr"
    assert AuditLog.objects.filter(action="LOGIN", username="hr").exists()


def test_wrong_password_and_audit(make_user):
    make_user("HR_MANAGER", "hr")
    r = login(APIClient(), "hr", "wrong")
    assert r.status_code == 401
    assert AuditLog.objects.filter(action="LOGIN_FAILED").exists()


def test_inactive_user_cannot_login_or_use_token(make_user):
    user = make_user("HR_MANAGER", "hr")
    c = APIClient()
    access = login(c, "hr").data["access"]
    user.is_active = False
    user.save()
    assert login(APIClient(), "hr").status_code == 401
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    assert c.get("/api/auth/me/").status_code == 401
    assert c.post("/api/auth/refresh/").status_code == 401


def test_refresh_rotates_and_logout_blacklists(make_user):
    make_user("HR_MANAGER", "hr")
    c = APIClient()
    login(c, "hr")
    old = c.cookies["bravado_refresh"].value
    r = c.post("/api/auth/refresh/")
    assert r.status_code == 200 and r.data["access"]
    new = c.cookies["bravado_refresh"].value
    assert new != old
    # the rotated-out token no longer works
    c2 = APIClient()
    c2.cookies["bravado_refresh"] = old
    assert c2.post("/api/auth/refresh/").status_code == 401
    assert c.post("/api/auth/logout/").status_code == 204
    c3 = APIClient()
    c3.cookies["bravado_refresh"] = new
    assert c3.post("/api/auth/refresh/").status_code == 401
    assert AuditLog.objects.filter(action="LOGOUT").exists()


def test_unauthenticated_access_denied():
    assert APIClient().get("/api/employees/").status_code == 401


def test_password_reset_flow(make_user, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    make_user("EMPLOYEE", "emp")
    c = APIClient()
    r = c.post("/api/auth/password-reset/", {"email": "emp@bravado.test"}, format="json")
    assert r.status_code == 200
    # unknown address gives identical response and sends nothing
    assert c.post("/api/auth/password-reset/", {"email": "nobody@x.test"}, format="json").data == r.data
    assert len(mail.outbox) == 1
    m = re.search(r"uid=([^&]+)&token=(\S+)", mail.outbox[0].body)
    uid, token = m.group(1), m.group(2)
    weak = c.post("/api/auth/password-reset/confirm/", {"uid": uid, "token": token, "new_password": "123"}, format="json")
    assert weak.status_code == 400
    ok = c.post("/api/auth/password-reset/confirm/", {"uid": uid, "token": token, "new_password": "N3w-Secure-Pass!"},
                format="json")
    assert ok.status_code == 204
    assert login(APIClient(), "emp", "N3w-Secure-Pass!").status_code == 200
    # token cannot be reused
    again = c.post("/api/auth/password-reset/confirm/", {"uid": uid, "token": token, "new_password": "Other-Pass-99!"},
                   format="json")
    assert again.status_code == 400


def test_change_password(make_user, client_for):
    user = make_user("EMPLOYEE", "emp")
    c = client_for(user)
    assert c.post("/api/auth/change-password/", {"current_password": "bad", "new_password": "X-Strong-Pass-1"}).status_code == 400
    assert c.post("/api/auth/change-password/", {"current_password": PASSWORD, "new_password": "X-Strong-Pass-1"}).status_code == 204


def test_password_is_hashed(make_user):
    user = make_user("EMPLOYEE", "emp")
    assert PASSWORD not in user.password and user.check_password(PASSWORD)


def test_user_management_requires_permission(make_user, client_for, admin_user):
    hr = make_user("HR_MANAGER", "hr")
    assert client_for(hr).get("/api/users/").status_code == 403
    c = client_for(admin_user)
    r = c.post("/api/users/", {"username": "newbie", "email": "n@b.test", "password": "Very-Strong-Pass-7",
                               "role": "FINANCE_OFFICER", "is_active": True}, format="json")
    assert r.status_code == 201, r.data
    assert "password" not in r.data
    uid = r.data["id"]
    assert c.post(f"/api/users/{uid}/deactivate/").data["is_active"] is False
    assert c.post(f"/api/users/{admin_user.id}/deactivate/").status_code == 400
    r = c.patch(f"/api/users/{uid}/", {"role": "PAYROLL_OFFICER"}, format="json")
    assert r.status_code == 200
    assert AuditLog.objects.filter(action="PERMISSION_CHANGE", object_id=str(uid)).exists()
    assert c.delete(f"/api/users/{uid}/").status_code == 400


def test_role_permission_change_audited(admin_user, client_for, roles):
    c = client_for(admin_user)
    role = roles["MANAGER"]
    r = c.patch(f"/api/roles/{role.id}/", {"permissions": ["payroll.view_approved"]}, format="json")
    assert r.status_code == 200
    assert AuditLog.objects.filter(action="PERMISSION_CHANGE", object_id=str(role.id)).exists()
    assert c.delete(f"/api/roles/{role.id}/").status_code == 400  # system role
