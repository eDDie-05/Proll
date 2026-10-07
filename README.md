# Bravado Company Ltd — Payroll Management System

A secure, auditable payroll system for Bravado Company Ltd (Tanzania). It covers the payroll lifecycle from employee and salary setup through calculation, approval, payment recording, payslips and reporting.

> **Statutory disclaimer.** PAYE, social-security (NSSF/PSSSF), WCF, SDL and other statutory amounts come from **configurable, versioned rules**. None are hard-coded. The rules shipped as seed data are marked **UNVERIFIED**. An authorised administrator must check them against current official Tanzanian sources (TRA, NSSF, PSSSF, WCF) before payroll is finalized. By default, payroll approval is blocked while it uses an unverified rule. See [docs/statutory-rules.md](docs/statutory-rules.md).

---

## Contents

1. [Features](#features)
2. [Technology stack](#technology-stack)
3. [Project structure](#project-structure)
4. [Quick start (local development)](#quick-start-local-development)
5. [Environment variables](#environment-variables)
6. [Database setup & migrations](#database-setup--migrations)
7. [Creating an admin user](#creating-an-admin-user)
8. [Running the backend](#running-the-backend)
9. [Running the frontend](#running-the-frontend)
10. [Running with Docker](#running-with-docker)
11. [Running tests](#running-tests)
12. [Payroll workflow & generating payslips](#payroll-workflow--generating-payslips)
13. [Backup and restore](#backup-and-restore)
14. [Deployment](#deployment)
15. [Further documentation](#further-documentation)

---

## Features

| Area | Highlights |
|---|---|
| **Authentication** | JWT access tokens (15 min, memory only) and a rotating refresh token in an httpOnly, SameSite=Strict cookie. Includes logout with token blacklisting, password reset by email, password change, account activation/deactivation, login rate limiting, and PBKDF2 password hashing. |
| **Role-based access** | Super Administrator, HR Manager, Payroll Officer, Finance Officer, Manager and Employee roles. Each role is a configurable set of permission codes, and every change to a role's permissions is audited. |
| **Employees** | Full employee records. Bank, TIN, social-security and personal data are only visible to roles with `employees.view_sensitive`. Employees are never hard-deleted. |
| **Contracts** | Permanent, contract, temporary, part-time or any configured employment type. Old contracts are kept as history. Uploaded documents are checked by magic number, capped at 5 MB, and downloadable only through the API with authorisation. |
| **Salary history** | Append-only, effective-dated salary records. A new record closes the previous one; nothing is overwritten or deleted. |
| **Allowances** | Configurable types: fixed, % of basic, or quantity × rate (overtime). Tax, social-security and cash-emolument treatment is set **explicitly** per type. Supports recurring and one-off items. |
| **Deductions** | Configurable: fixed, % of basic or % of gross, with caps, start/end dates, and statutory and pre-tax flags. |
| **Loans & advances** | Principal, flat interest, installments and balance. Approval is separate from recording (segregation of duties). Installments are deducted automatically, and the repayment history is kept. |
| **Leave** | Configurable leave types. Only types configured as unpaid reduce basic pay, pro-rata. |
| **Statutory rules engine** | Versioned rules with effective dates. Supports progressive brackets, flat rates and fixed amounts; base selection, ceilings, min/max amounts; residency, scheme and headcount conditions; source provenance; and verification. |
| **Payroll engine** | Pro-ration for joiners and leavers, mid-period salary changes, unpaid leave, allowances, adjustments, loans, and statutory, PAYE and other deductions. Employer contributions are kept separate. Every component is stored with its derivation. |
| **Workflow** | DRAFT → CALCULATED → REVIEW → APPROVED → PAID → CLOSED. Transitions are permission-checked and segregation of duties is enforced. There is a full status history with comments. Closed payroll is immutable, and corrections go through approved adjustments. |
| **Payslips** | Professional PDF payslips. Employees see and download only their own released payslips. |
| **Reports** | Payroll summary, department, register, PAYE, statutory contributions, deductions, payments, payroll history and employee salary history, plus an individual salary statement. All exportable as PDF, Excel and CSV, and printable. |
| **Bank payments** | Payment instructions are created on approval, and payment status and transaction references are recorded. Bank export files use **configurable** layouts; no bank format is assumed. |
| **Dashboard** | Key figures, plus charts for payroll by month and by department, employee count, salary distribution and cost trend. |
| **Audit log** | Append-only, enforced by the ORM **and** a PostgreSQL trigger. Records user, action, time, IP, affected record, and old/new values. Passwords and tokens are never logged. |
| **Security** | HTTPS/HSTS, CSP, secure cookies, throttling, input validation, ORM-only queries, CSV-injection protection, secrets from environment, and encrypted off-site backups. |

## Technology stack

- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS, TanStack Query, React Router, Recharts, Vitest + Testing Library
- **Backend:** Python 3.12, Django 5.1, Django REST Framework, SimpleJWT, drf-spectacular (OpenAPI), django-filter, ReportLab (PDF), openpyxl (Excel)
- **Database:** PostgreSQL 16
- **Deployment:** Docker, Docker Compose, Nginx (TLS termination), Gunicorn, cron-based encrypted backups with rclone off-site copy

## Project structure

```
backend/                 Django project
  config/                settings, urls, wsgi
  apps/
    core/                company settings, audit log, permissions, shared utilities
    accounts/            users, roles, permissions, authentication
    employees/           departments, positions, employment types, employees, contracts, salary history
    compensation/        allowances, deductions, loans & repayments
    leave/               leave types & records
    statutory/           statutory rules, tax brackets, rule calculator, TZ seed data
    payroll/             periods, runs, items, lines, engine, workflow, payments, payslips, PDFs
    reports/             report builders, CSV/XLSX/PDF exporters, dashboard
  conftest.py            shared pytest fixtures
frontend/                React + TypeScript app
  src/api/               axios client (token handling, downloads)
  src/auth/              auth context
  src/components/        layout, tables, forms, dialogs, toasts
  src/pages/             pages by module
  src/test/              Vitest tests
database/                schema reference (schema.sql) & notes
docker/                  Dockerfiles, nginx config, backup container
docs/                    technical documentation & OpenAPI spec
scripts/                 backup.sh, restore.sh
tests/                   pointer to where tests live
docker-compose.yml
.env.example
```

## Quick start (local development)

Prerequisites: Python 3.12, Node 20+ (24 recommended), PostgreSQL 16.

```bash
# 1. Database
createuser -P bravado            # choose a password
createdb -O bravado bravado_payroll

# 2. Backend
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cat > .env <<'EOF'
DJANGO_DEBUG=true
DJANGO_SECRET_KEY=dev-only-change-me
DATABASE_URL=postgres://bravado:<password>@localhost:5432/bravado_payroll
EOF
set -a; . ./.env; set +a
python manage.py migrate
python manage.py seed_reference_data            # departments, types, allowance/deduction/leave types, draft TZ rules
DEMO_PASSWORD='Choose-A-Demo-Pass-1' python manage.py seed_reference_data --demo   # optional sample data + demo users
python manage.py runserver

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev            # http://localhost:5173 (proxies /api to :8000)
```

With `--demo`, you can log in as `admin`, `hr`, `payroll`, `finance`, `manager` or `employee`, using the `DEMO_PASSWORD` you set. **Do not use demo data in production.**

## Environment variables

All configuration comes from environment variables. See [`.env.example`](.env.example) for the full list with comments. The important ones:

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | **Required** in production. Long random string. |
| `JWT_SIGNING_KEY` | Signing key for JWTs (defaults to the secret key). |
| `DJANGO_DEBUG` | `false` in production. |
| `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS` | Your domain(s). |
| `DATABASE_URL` | `postgres://user:pass@host:5432/db` (built automatically in Docker from `POSTGRES_*`). |
| `FRONTEND_URL` | Used in password-reset links. |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL` | SMTP for password reset. |
| `JWT_ACCESS_MINUTES`, `JWT_REFRESH_HOURS` | Token lifetimes (default 15 min / 12 h). |
| `THROTTLE_*` | API rate limits. |
| `BACKUP_ENCRYPTION_PASSPHRASE`, `RCLONE_REMOTE`, `BACKUP_*` | Backup encryption and off-site target. |

Never commit `.env`, certificates, `rclone.conf` or backups; `.gitignore` excludes them.

## Database setup & migrations

The schema is managed entirely by Django migrations (normalized tables with primary keys, foreign keys, unique, NOT NULL and CHECK constraints, and indexes). There is a reference dump in [`database/schema.sql`](database/schema.sql).

```bash
python manage.py migrate                 # apply
python manage.py makemigrations          # after model changes
python manage.py showmigrations
```

Migrations also:
- seed the permission catalogue and default roles (`accounts/0002`)
- install a PostgreSQL trigger that rejects UPDATE/DELETE on `audit_logs` (`core/0002`)

## Creating an admin user

```bash
cd backend
ADMIN_PASSWORD='a-strong-password' python manage.py create_admin --username admin --email admin@bravado.co.tz
# or omit ADMIN_PASSWORD to be prompted
```

In Docker:

```bash
docker compose exec backend python manage.py create_admin --username admin --email admin@bravado.co.tz
```

Then sign in and:
1. **Company settings:** set the name, address, TIN and logo.
2. **Statutory rules:** review each rule against official sources and **Verify** it.
3. **Organisation setup:** departments, positions and employment types.
4. **Users:** create accounts and link employee records for self-service.

## Running the backend

```bash
cd backend && . .venv/bin/activate && set -a; . ./.env; set +a
python manage.py runserver                      # development
gunicorn config.wsgi:application -b 0.0.0.0:8000 --workers 3   # production-style
```

- API docs (Swagger UI): `http://localhost:8000/api/docs/`
- ReDoc: `/api/redoc/`, raw schema: `/api/schema/` (also committed at [`docs/openapi.yaml`](docs/openapi.yaml))

## Running the frontend

```bash
cd frontend
npm run dev        # dev server with API proxy (VITE_API_PROXY overrides the target, default http://127.0.0.1:8000)
npm run build      # type-check + production build into dist/
npm run preview
```

## Running with Docker

```bash
cp .env.example .env          # fill in every "change-me" value
# put TLS cert + key in docker/nginx/certs/ (fullchain.pem, privkey.pem) — see Deployment
docker compose up -d --build
docker compose exec backend python manage.py seed_reference_data
docker compose exec backend python manage.py create_admin --username admin --email admin@bravado.co.tz
```

Services: `postgres`, `backend` (Gunicorn), `frontend` (builds the SPA into a shared volume, then exits), `nginx` (TLS, static and SPA, `/api` proxy) and `backup` (scheduled encrypted dumps).

## Running tests

```bash
# Backend (needs a PostgreSQL user with CREATEDB; the test database is created automatically)
cd backend && set -a; . ./.env; set +a
pytest                 # 83 tests: auth, permissions, employees, salary history, allowances, deductions,
                       # loans, statutory rules, payroll engine scenarios, workflow, payslips, reports, audit
pytest --create-db     # after migration changes

# Frontend
cd frontend
npm test               # Vitest: login, forms, dashboard, payroll workflow, reports, formatting
npx tsc -p .           # type-check
```

Payroll scenarios covered: basic salary only; taxable and non-taxable allowances; % allowances; multiple, capped and pre-tax deductions; overtime; bonus (one-off); commission; loan repayment (including final-installment capping); joining and leaving mid-period; salary change during the year and mid-period; statutory rule selected by effective date; base ceilings; non-resident rules; scheme-specific rules; headcount-threshold levies; unpaid leave; adjustments; negative-net detection; 30-day pro-ration basis.

## Payroll workflow & generating payslips

1. **Payroll Officer** creates a period (e.g. *September 2026*, 01/09/2026 to 30/09/2026). Overlapping periods are rejected.
2. **Calculate.** Every eligible employee is calculated with the rules in force on the period end date. Warnings are shown, such as unverified rules, missing bank details or a negative net. Recalculating keeps previous runs as history.
3. Review each employee's breakdown (click a row), then **Submit for review**.
4. **Manager / approver** approves or rejects (a reason is required to reject). Approval is blocked if a used rule is unverified, a net is negative, or the approver prepared the payroll.
5. On approval, payment instructions are created and loan repayments are posted.
6. **Generate payslips** (Payroll period page → *Generate payslips*). Staff download them from **Payslips**; employees get them under **My payslips**.
7. **Finance** exports the bank file (configurable format), records payments with the transaction reference, then **Mark as paid**.
8. **Close** the payroll. It becomes read-only. Later corrections are **payroll adjustments** targeting an open period.

## Backup and restore

The `backup` container runs [`scripts/backup.sh`](scripts/backup.sh) on `BACKUP_SCHEDULE` (default 02:30 daily). Each run:

- `pg_dump` (custom format) → AES-256 encryption (`openssl`, PBKDF2) → `.sha256` checksum
- local retention of `BACKUP_RETENTION_DAYS` (default 14)
- **off-site copy via rclone** to `RCLONE_REMOTE` (S3, B2, Google Drive, SFTP, …) with its own retention. **Backups must never exist only on the database server**, and the script warns loudly if no remote is configured.

Configure off-site storage by putting `rclone.conf` in `docker/backup/rclone/` and setting `RCLONE_REMOTE=remote:bucket` in `.env`. Keep a copy of `BACKUP_ENCRYPTION_PASSPHRASE` offline; backups cannot be restored without it.

Run a backup now:

```bash
docker compose exec backup backup.sh
```

**Restore** (stop the backend first):

```bash
docker compose stop backend
docker compose exec backup restore.sh /backups/bravado_payroll-YYYYMMDD-HHMMSS.dump.enc
# confirms by asking you to type the database name; verifies the checksum first
docker compose start backend
```

To restore from off-site, first copy the file back: `docker compose exec backup rclone copy "$RCLONE_REMOTE/<file>" /backups/`.
Test restores regularly into a scratch database: `restore.sh <file> restore_test`.

## Deployment

See **[docs/deployment.md](docs/deployment.md)** for the full Linux server guide (Docker install, firewall, Let's Encrypt, upgrades, monitoring). In short:

1. Ubuntu 22.04/24.04 server with Docker Engine and the Compose plugin; open ports 80 and 443 only.
2. Clone the repo, `cp .env.example .env`, and set strong secrets and your domain.
3. Obtain TLS certificates (Let's Encrypt `certbot certonly --standalone -d payroll.bravado.co.tz`) and point `TLS_CERT_DIR` at `/etc/letsencrypt/live/<domain>`.
4. `docker compose up -d --build`, then seed reference data and create the admin.
5. Configure off-site backups and test a restore.
6. Verify and activate statutory rules before the first live payroll.

## Further documentation

- [docs/payroll-engine.md](docs/payroll-engine.md): how the calculation engine works, step by step
- [docs/statutory-rules.md](docs/statutory-rules.md): rule model, versioning, verification, and the seeded draft values with sources
- [docs/api.md](docs/api.md): API overview and endpoint map ([OpenAPI spec](docs/openapi.yaml))
- [docs/security.md](docs/security.md): security controls
- [docs/deployment.md](docs/deployment.md): production deployment
- [database/README.md](database/README.md): data model overview
