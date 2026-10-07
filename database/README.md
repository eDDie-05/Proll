# Database

PostgreSQL 16. The schema is owned by Django migrations (`backend/apps/*/migrations/`). `schema.sql` is a **reference dump**; do not apply it by hand.

Regenerate it after migrations:

```bash
pg_dump -s --no-owner --no-privileges bravado_payroll > database/schema.sql
```

## Main tables

| Table | Purpose |
|---|---|
| `users`, `roles`, `permissions`, `role_permissions` | Accounts and role-based access |
| `company_settings` | Singleton: identity, pro-ration basis, approval safeguards |
| `audit_logs` | Append-only audit trail (trigger `audit_logs_no_update_delete`) |
| `departments`, `positions`, `employment_types` | Organisation reference data |
| `employees` | Employee master (unique `employee_number`) |
| `employment_contracts` | Contract history (unique `contract_number`) |
| `salary_history` | Effective-dated basic salary (unique per employee + effective_from) |
| `allowance_types`, `employee_allowances` | Configurable earnings and assignments |
| `deduction_types`, `employee_deductions` | Configurable deductions and assignments |
| `loans`, `loan_repayments` | Loans/advances and repayments (one payroll repayment per loan per period) |
| `leave_types`, `leave_records` | Leave with configurable payroll effect |
| `statutory_rules`, `tax_brackets` | Versioned statutory rules (unique code + version) |
| `payroll_periods` | Periods and workflow state (unique dates; no overlaps) |
| `payroll_runs` | Calculation runs (one current run per period, enforced by a partial unique index) |
| `payroll_items` | Per-employee results with snapshot data |
| `payroll_lines` | Every earning / employee deduction / employer contribution (category column); links to `statutory_rules` |
| `payroll_status_history` | Workflow trail |
| `payroll_adjustments` | Approved corrections applied in open periods |
| `payments` | Payment instruction and status per item |
| `payslips` | Generated payslip register |
| `bank_export_formats` | Configurable bank file layouts |

`payroll_lines.category` (EARNING / DEDUCTION / EMPLOYER) covers what would otherwise be separate `payroll_earnings`, `payroll_deductions`, `employee_contributions` and `employer_contributions` tables. That keeps one uniform, auditable structure for every component.

CHECK constraints enforce non-negative money, date ordering, positive loan and adjustment amounts, and bracket bounds.
