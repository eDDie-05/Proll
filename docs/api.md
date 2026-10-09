# API Overview

Base path: `/api/`. Interactive docs: `/api/docs/` (Swagger UI) and `/api/redoc/`. Full spec: [`openapi.yaml`](openapi.yaml), regenerated with `python manage.py spectacular --file ../docs/openapi.yaml`.

**Auth:** send `Authorization: Bearer <access>`. Obtain the token from `POST /api/auth/login/`. Renew it with `POST /api/auth/refresh/`, which uses the httpOnly cookie.
**Lists** are paginated (`?page=`, `?page_size=` up to 500) and support `?search=`, `?ordering=` and per-endpoint filters.
**Errors** use DRF format: `{"field": ["message"]}` or `{"detail": "message"}`.

| Area | Endpoints | Permission(s) |
|---|---|---|
| Authentication | `auth/login/`, `auth/refresh/`, `auth/logout/`, `auth/me/`, `auth/change-password/`, `auth/password-reset/`, `auth/password-reset/confirm/` | public / authenticated |
| Users | `users/` CRUD (no delete), `users/{id}/activate/`, `users/{id}/deactivate/` | `users.manage` |
| Roles | `roles/`, `permissions/` | `roles.manage` |
| Company | `company-settings/` (GET all users; PATCH) | `company.manage` |
| Audit | `audit-logs/` (read-only; filters `action`, `model`, `object_id`, `user`, `date_from`, `date_to`) | `audit.view` |
| Organisation | `departments/`, `positions/`, `employment-types/` | `employees.view` / `employees.manage` |
| Employees | `employees/` (no delete), `employees/{id}/salary-history/` | `employees.view`, `employees.manage`, `employees.view_sensitive`, `salary.view` |
| Contracts | `contracts/` (no delete), `contracts/{id}/document/` | `contracts.manage` |
| Salaries | `salaries/` (GET/POST only; append-only) | `salary.view` / `salary.manage` |
| Allowances | `allowance-types/`, `employee-allowances/` | `allowances.manage` |
| Deductions | `deduction-types/`, `employee-deductions/` | `deductions.manage` |
| Loans | `loans/` (+ `approve/`, `cancel/`), `loan-repayments/` | `loans.view` / `loans.manage` |
| Leave | `leave-types/`, `leave-records/` (+ `approve/`, `reject/`, `cancel/`) | `leave.view` / `leave.manage` |
| Statutory rules | `statutory-rules/` (+ `verify/`, `new-version/`, `preview/`, `in-force/?date=`) | `statutory.view` / `statutory.manage` / `statutory.verify` |
| Payroll periods | `payroll-periods/` CRUD; actions `calculate/`, `submit/`, `approve/`, `reject/`, `mark-paid/`, `close/`, `approval-check/`, `history/`, `items/?q=&department=`, `payments/`, `record-payments/`, `bank-export/?export_format=`, `generate-payslips/`, `summary-pdf/` | `payroll.*`, `payments.*`, `payslips.generate` |
| Payroll items | `payroll-items/{id}/` (full line-by-line breakdown) | payroll viewers |
| Adjustments | `payroll-adjustments/` (+ `approve/`, `reject/`) | `payroll.adjust` / `payroll.approve` |
| Payments | `payments/` (read-only list) | `payments.view` |
| Bank formats | `bank-export-formats/`, `bank-export-formats/available-fields/` | `payments.export` |
| Payslips | `payslips/?item=&item__run__period=`, `payslips/{id}/pdf/` | `payslips.generate` / `payroll.view` |
| Self-service | `self/profile/`, `self/salary-history/`, `self/payslips/`, `self/payslips/{id}/`, `self/payslips/{id}/pdf/`, `self/deductions/` | `self.view` (own data only) |
| Reports | `reports/payroll-summary/`, `department/`, `register/`, `tax/`, `contributions/`, `deductions/`, `payments/` (all `?period=&department=`), `reports/history/?year=`, `reports/employee-salary/?employee=`, `reports/employee-statement/?employee=&year=`; add `&export=csv|xlsx|pdf` to download | `reports.view` / `reports.view_department` (own department, released periods) |
| Dashboard | `dashboard/` | reports or payroll viewers |

### Example: calculate and approve

```http
POST /api/payroll-periods/          {"name": "September 2026", "start_date": "2026-09-01", "end_date": "2026-09-30", "pay_date": "2026-09-28"}
POST /api/payroll-periods/1/calculate/
POST /api/payroll-periods/1/submit/ {"comment": "Ready"}
GET  /api/payroll-periods/1/approval-check/    -> {"can_approve": false, "blockers": ["Statutory rule PAYE_RESIDENT v1 is not verified."]}
POST /api/payroll-periods/1/approve/ {"comment": "Approved"}      (different user)
```
