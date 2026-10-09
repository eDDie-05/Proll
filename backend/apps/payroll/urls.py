from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("payroll-periods", views.PayrollPeriodViewSet, basename="payrollperiod")
router.register("payroll-items", views.PayrollItemViewSet, basename="payrollitem")
router.register("payroll-adjustments", views.PayrollAdjustmentViewSet)
router.register("bank-export-formats", views.BankExportFormatViewSet)
router.register("payments", views.PaymentViewSet)
router.register("payslips", views.PayslipViewSet, basename="payslip")

urlpatterns = [
    path("self/payslips/", views.SelfPayslipListView.as_view(), name="self-payslips"),
    path("self/payslips/<int:pk>/", views.SelfPayslipDetailView.as_view(), name="self-payslip-detail"),
    path("self/payslips/<int:pk>/pdf/", views.SelfPayslipPdfView.as_view(), name="self-payslip-pdf"),
    path("self/deductions/", views.SelfDeductionsView.as_view(), name="self-deductions"),
] + router.urls
