from django.contrib import admin

from .models import LeaveRecord, LeaveType

admin.site.register(LeaveType)
admin.site.register(LeaveRecord)
