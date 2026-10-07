from django.contrib import admin

from .models import AuditLog, CompanySettings


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "username", "action", "model", "object_id", "ip_address")
    list_filter = ("action", "model")
    search_fields = ("username", "object_repr", "message")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(CompanySettings)
