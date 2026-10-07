from django.contrib import admin

from .models import Department, Employee, EmploymentContract, EmploymentType, Position, SalaryRecord

for m in (Department, Position, EmploymentType, EmploymentContract):
    admin.site.register(m)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("employee_number", "first_name", "last_name", "department", "status")
    search_fields = ("employee_number", "first_name", "last_name")
    list_filter = ("status", "department")


@admin.register(SalaryRecord)
class SalaryRecordAdmin(admin.ModelAdmin):
    list_display = ("employee", "basic_salary", "effective_from", "effective_to")

    def has_delete_permission(self, request, obj=None):
        return False
