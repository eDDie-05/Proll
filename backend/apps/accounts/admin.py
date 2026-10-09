from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Permission, Role, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (("Payroll", {"fields": ("role", "phone", "must_change_password")}),)
    list_display = ("username", "email", "role", "is_active", "last_login")
    list_filter = ("role", "is_active")


admin.site.register(Role)
admin.site.register(Permission)
