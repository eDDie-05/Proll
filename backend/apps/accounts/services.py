from django.db import transaction

from .catalog import PERMISSIONS, ROLES
from .models import Permission, Role


@transaction.atomic
def sync_permissions_and_roles(reset_role_permissions=False):
    """Create/refresh the permission catalog and the default system roles.

    Existing role permission sets are left alone unless `reset_role_permissions` is True,
    so administrators' customisations survive upgrades.
    """
    perms = {}
    for code, description in PERMISSIONS.items():
        perm, _ = Permission.objects.update_or_create(code=code, defaults={"description": description})
        perms[code] = perm
    for code, spec in ROLES.items():
        role, created = Role.objects.get_or_create(code=code, defaults={"name": spec["name"], "is_system": True})
        if created or reset_role_permissions:
            role.permissions.set([perms[c] for c in spec["permissions"]])
    return perms
