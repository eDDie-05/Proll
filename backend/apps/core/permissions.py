"""
Permission-code based authorization.

Each user has one Role; a Role grants a set of permission codes (e.g. "payroll.approve").
Views declare the codes they need per action via `required_permissions`.
"""
from rest_framework.permissions import BasePermission


def user_has_perm(user, code):
    if not user or not user.is_authenticated or not user.is_active:
        return False
    return code in user.permission_codes()


class HasPermissionCode(BasePermission):
    """
    View attribute `required_permissions` maps an action (or HTTP method) to a code or list of codes.
    Any one listed code grants access. `"*"` key is the fallback.

        required_permissions = {"list": "employees.view", "create": "employees.manage", "*": "employees.manage"}
    """

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        mapping = getattr(view, "required_permissions", None)
        if mapping is None:
            return True
        key = getattr(view, "action", None) or request.method.lower()
        codes = mapping.get(key, mapping.get(request.method.lower(), mapping.get("*")))
        if codes is None:
            return False
        if isinstance(codes, str):
            codes = [codes]
        user_codes = request.user.permission_codes()
        return any(c in user_codes for c in codes)


def crud_permissions(view_code, manage_code, **extra):
    """Standard mapping: read actions require view_code, write actions require manage_code."""
    mapping = {
        "list": [view_code, manage_code],
        "retrieve": [view_code, manage_code],
        "create": manage_code,
        "update": manage_code,
        "partial_update": manage_code,
        "destroy": manage_code,
        "*": manage_code,
    }
    mapping.update(extra)
    return mapping
