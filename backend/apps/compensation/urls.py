from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("allowance-types", views.AllowanceTypeViewSet)
router.register("employee-allowances", views.EmployeeAllowanceViewSet)
router.register("deduction-types", views.DeductionTypeViewSet)
router.register("employee-deductions", views.EmployeeDeductionViewSet)
router.register("loans", views.LoanViewSet)
router.register("loan-repayments", views.LoanRepaymentViewSet)

urlpatterns = router.urls
