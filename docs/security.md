# Security Controls

| Control | Implementation |
|---|---|
| Password storage | Django PBKDF2-SHA256 (`PASSWORD_HASHERS`). Minimum 10 characters; common, numeric and user-similar passwords are rejected. |
| Authentication | SimpleJWT. The **access token** (15 min) is held in memory only. The **refresh token** (12 h) is an `httpOnly`, `Secure`, `SameSite=Strict` cookie scoped to `/api/auth/`. It is rotated on every refresh, and rotated-out tokens are blacklisted. |
| Logout | Blacklists the refresh token and clears the cookie. |
| Session expiry | Access tokens expire after 15 minutes; refresh tokens after `JWT_REFRESH_HOURS`. Deactivated users are rejected immediately, both for access tokens and for refresh. |
| Password reset | Single-use Django token, expires after `PASSWORD_RESET_TIMEOUT` (1 h). The response never reveals whether an email exists, and requests are throttled. |
| Authorisation | Permission codes per role (`apps/accounts/catalog.py`). Every API view declares required codes per action (`HasPermissionCode`). Querysets are scoped too: approvers see only REVIEW and released payroll, employees see only their own payslips, and managers see only their own department's reports. |
| Sensitive data | Bank, TIN, NIDA, social-security, date of birth and address are returned only to `employees.view_sensitive`. Account numbers are masked in payslips and payment reports. |
| CSRF | The API uses bearer tokens (not cookie auth), and the refresh cookie is SameSite=Strict on a narrow path. Django CSRF middleware stays on for the admin. |
| Injection | Only the Django ORM is used; there is no raw SQL except migration DDL. CSV and XLSX exports neutralise formula injection (`=`, `+`, `-`, `@`). |
| Input validation | Model `clean()` rules run through serializers: non-negative money, date ordering, overlapping periods, unique employee ID (case-insensitive), contiguous brackets, loan coverage. Database CHECK and UNIQUE constraints back them up. |
| Rate limiting | DRF throttles (anonymous, user, login, password-reset) plus nginx `limit_req` on `/api/auth/` and `/api/`. |
| File uploads | Extension allow-list (PDF/PNG/JPG), 5 MB limit, and a magic-number check. Contract documents are **not** publicly served; nginx returns 404 for `/media/` except the company logo, and documents download through an authorised, audited API endpoint. |
| Transport | nginx TLS 1.2/1.3, HSTS, HTTP→HTTPS redirect, `SECURE_SSL_REDIRECT`, secure cookies. |
| Headers | CSP, X-Frame-Options DENY, nosniff, Referrer-Policy, Permissions-Policy. |
| Audit | `audit_logs` is append-only. The ORM refuses save-on-existing and delete, and a PostgreSQL trigger rejects UPDATE/DELETE. The API is read-only and the Django admin read-only. Passwords and tokens are redacted. |
| Segregation of duties | A payroll cannot be approved by its calculator or submitter (configurable). Loans and adjustments cannot be approved by their creator. |
| Secrets | Everything comes from environment variables (`.env`, git-ignored). The settings refuse to start without `DJANGO_SECRET_KEY` when `DEBUG` is false. |
| Backups | Encrypted with AES-256 (PBKDF2), checksummed, and copied off-site. |
| Django admin | Available at `/django-admin/`, restricted to private networks by nginx. |
| Container | The backend runs as a non-root user; the database is on an internal Docker network only. |

## Operational recommendations

- Rotate `DJANGO_SECRET_KEY` and `JWT_SIGNING_KEY` if they are exposed. Rotation invalidates all sessions.
- Review the audit log regularly, especially `LOGIN_FAILED`, `PERMISSION_CHANGE` and `EXPORT`.
- Keep the backup passphrase in a password manager and offline.
- Apply OS and container updates monthly (`docker compose pull && docker compose up -d --build`).
