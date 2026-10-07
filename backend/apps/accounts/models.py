from django.contrib.auth.models import AbstractUser
from django.db import models


class Permission(models.Model):
    code = models.CharField(max_length=64, unique=True)
    description = models.CharField(max_length=255)

    class Meta:
        db_table = "permissions"
        ordering = ["code"]

    def __str__(self):
        return self.code


class Role(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(Permission, related_name="roles", blank=True, db_table="role_permissions")
    is_system = models.BooleanField(default=False, help_text="System roles cannot be deleted.")

    class Meta:
        db_table = "roles"
        ordering = ["name"]

    def __str__(self):
        return self.name


class User(AbstractUser):
    email = models.EmailField(unique=True)
    role = models.ForeignKey(Role, null=True, blank=True, on_delete=models.PROTECT, related_name="users")
    phone = models.CharField(max_length=30, blank=True)
    must_change_password = models.BooleanField(default=False)

    class Meta:
        db_table = "users"
        ordering = ["username"]

    def permission_codes(self):
        if not self.is_active:
            return frozenset()
        cache = getattr(self, "_perm_codes", None)
        if cache is None:
            if self.is_superuser:
                from .catalog import PERMISSIONS

                cache = frozenset(PERMISSIONS)
            elif self.role_id:
                cache = frozenset(self.role.permissions.values_list("code", flat=True))
            else:
                cache = frozenset()
            self._perm_codes = cache
        return cache

    def has_code(self, code):
        return code in self.permission_codes()

    @property
    def employee_profile(self):
        return getattr(self, "employee", None)
