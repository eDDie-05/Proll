from django.db import migrations


def seed(apps, schema_editor):
    from apps.accounts.catalog import PERMISSIONS, ROLES

    Permission = apps.get_model("accounts", "Permission")
    Role = apps.get_model("accounts", "Role")
    perms = {}
    for code, desc in PERMISSIONS.items():
        perms[code], _ = Permission.objects.update_or_create(code=code, defaults={"description": desc})
    for code, spec in ROLES.items():
        role, created = Role.objects.get_or_create(code=code, defaults={"name": spec["name"], "is_system": True})
        if created:
            role.permissions.set([perms[c] for c in spec["permissions"]])


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
