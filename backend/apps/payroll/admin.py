from django.contrib import admin

from .models import BankExportFormat, Payment, PayrollAdjustment, PayrollPeriod, PayrollRun, PayrollStatusChange, Payslip


@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "status")
    readonly_fields = ("status",)


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


for m in (PayrollRun, PayrollStatusChange, Payment, Payslip):
    admin.site.register(m, ReadOnlyAdmin)
admin.site.register(PayrollAdjustment)
admin.site.register(BankExportFormat)
