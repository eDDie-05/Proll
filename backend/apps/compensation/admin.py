from django.contrib import admin

from .models import AllowanceType, DeductionType, EmployeeAllowance, EmployeeDeduction, Loan, LoanRepayment

for m in (AllowanceType, DeductionType, EmployeeAllowance, EmployeeDeduction, Loan, LoanRepayment):
    admin.site.register(m)
