from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("audit-logs", views.AuditLogViewSet)

urlpatterns = [path("company-settings/", views.CompanySettingsView.as_view(), name="company-settings")] + router.urls
