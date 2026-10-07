# Tests

Tests live next to the code they cover:

- Backend: `backend/apps/*/tests/` (pytest + pytest-django, run against PostgreSQL). Shared fixtures in `backend/conftest.py`.
  - `payroll/tests/test_engine.py`: payroll calculation scenarios
  - `payroll/tests/test_workflow.py`: approval workflow, payslips, bank export, reports, permissions
  - `accounts/tests/test_auth.py`: login, refresh rotation, logout, password reset, user/role management
  - `employees/tests/test_employees.py`: employee CRUD, sensitive-field access, salary history, contracts, uploads, loans
  - `statutory/tests/test_statutory.py`: rule math, validation, verification, versioning, seed data
  - `core/tests/test_audit.py`: audit immutability, company settings, schema
- Frontend: `frontend/src/test/` (Vitest + Testing Library)

Run: `cd backend && pytest` and `cd frontend && npm test`.
