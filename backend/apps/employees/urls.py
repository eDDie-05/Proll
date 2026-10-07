from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("departments", views.DepartmentViewSet)
router.register("positions", views.PositionViewSet)
router.register("employment-types", views.EmploymentTypeViewSet)
router.register("employees", views.EmployeeViewSet)
router.register("contracts", views.EmploymentContractViewSet)
router.register("salaries", views.SalaryRecordViewSet)

urlpatterns = [
    path("self/profile/", views.SelfProfileView.as_view(), name="self-profile"),
    path("self/salary-history/", views.SelfSalaryHistoryView.as_view(), name="self-salary-history"),
] + router.urls
