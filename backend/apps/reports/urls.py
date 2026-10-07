from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("reports/payroll-summary/", views.PayrollSummaryReportView.as_view(), name="report-payroll-summary"),
    path("reports/department/", views.DepartmentReportView.as_view(), name="report-department"),
    path("reports/register/", views.PayrollRegisterView.as_view(), name="report-register"),
    path("reports/deductions/", views.DeductionReportView.as_view(), name="report-deductions"),
    path("reports/tax/", views.TaxReportView.as_view(), name="report-tax"),
    path("reports/contributions/", views.ContributionReportView.as_view(), name="report-contributions"),
    path("reports/payments/", views.PaymentReportView.as_view(), name="report-payments"),
    path("reports/history/", views.PayrollHistoryView.as_view(), name="report-history"),
    path("reports/employee-salary/", views.EmployeeSalaryReportView.as_view(), name="report-employee-salary"),
    path("reports/employee-statement/", views.EmployeeStatementView.as_view(), name="report-employee-statement"),
]
