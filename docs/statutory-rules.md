# Statutory Rules

Tanzanian statutory obligations are modelled as **data**, not code. Code: `backend/apps/statutory/`.

## Rule model (`statutory_rules`, `tax_brackets`)

| Field | Meaning |
|---|---|
| `code`, `version` | Stable identifier shared by versions (e.g. `PAYE_RESIDENT`) and an auto-incremented version |
| `category` | TAX, SOCIAL_SECURITY, LEVY, OTHER |
| `party` | EMPLOYEE (deduction from pay) or EMPLOYER (contribution on top of pay) |
| `method` | PROGRESSIVE (brackets), FLAT_RATE (% of base), FIXED_AMOUNT |
| `base` | BASIC, GROSS, SOCIAL_SECURITY_BASE, TAXABLE_INCOME, CASH_EMOLUMENTS |
| `rate`, `fixed_amount` | For flat and fixed methods |
| `base_ceiling`, `min_amount`, `max_amount` | Caps and floors |
| `reduces_taxable_income` | Employee contribution deducted before PAYE |
| `residency`, `applies_to_schemes`, `min_employee_count` | Applicability conditions |
| `calculation_order` | Ordering within a stage |
| `effective_from`, `effective_to` | Validity window (no overlapping active versions per code) |
| `source_name`, `source_url`, `source_reference`, `source_retrieved_on` | Provenance |
| `verification_status`, `verified_by`, `verified_at`, `verification_notes` | Verification trail |

Brackets must start at 0, be contiguous, and end open-ended.

## Lifecycle

1. **Create or edit.** The rule is saved as **UNVERIFIED**. Any change to calculation fields resets verification.
2. **Verify.** A user with `statutory.verify` checks the rule against the official source and records notes. The rule becomes **VERIFIED** and the action is audited.
3. **Use.** Once a rule version appears in any payroll line, its calculation fields are **locked**. Only its end date, active flag and provenance can change.
4. **Change the law.** Use *New version* with the new effective date. The current version is end-dated the day before, and the new version copies the brackets and starts UNVERIFIED.

`CompanySettings.require_verified_rules_for_approval` (default **on**) blocks payroll approval while any rule used in the run is unverified.

## Seeded draft rules — MUST be verified before use

`python manage.py seed_tz_statutory` (also run by `seed_reference_data`) creates the rules below as **UNVERIFIED** drafts, effective 2026-07-01. The figures come from sources consulted on **2026-09-26**. The TRA website could not be reached from the build environment, so no figure below has been confirmed against TRA directly.

| Code | Draft configuration | Source consulted | Notes |
|---|---|---|---|
| `PAYE_RESIDENT` | Monthly brackets on taxable income: 0–270,000 @ 0%; 270,000–520,000 @ **8%**; 520,000–760,000 @ 20%; 760,000–1,000,000 @ 25%; above 1,000,000 @ 30% | [PwC Worldwide Tax Summaries — Tanzania, individual taxes](https://taxsummaries.pwc.com/tanzania/individual/taxes-on-personal-income) (last reviewed 09 Sep 2026) | **Conflict:** some secondary calculators list **9%** for the 270,000–520,000 band. Confirm with [TRA](https://www.tra.go.tz) and the latest Finance Act. |
| `PAYE_NON_RESIDENT` | Flat 15% of taxable income | PwC (same page) | Confirm with TRA. |
| `NSSF_EMPLOYEE` | 10% of social-security base; scheme NSSF; reduces taxable income | [NSSF — Rate of contributions](https://www.nssf.go.tz/pages/rate-of-contributions) | NSSF states 20% of gross salary jointly, employee share not exceeding 10%. Confirm which earnings form the base and the PAYE deductibility. |
| `NSSF_EMPLOYER` | 10% of social-security base; scheme NSSF | NSSF (same page) | |
| `WCF` | Employer 0.5% of gross cash emoluments | [PwC — Tanzania, other taxes](https://taxsummaries.pwc.com/tanzania/individual/other-taxes) | Reported private-sector rate; confirm with [WCF](https://www.wcf.go.tz). |
| `SDL` | Employer 3.5% of gross cash emoluments when the payroll has ≥ 10 employees | PwC (same page) | Some employers are exempt; confirm with TRA. |

PSSSF members are not covered by the seeded NSSF rules (`applies_to_schemes = ["NSSF"]`). Add PSSSF rules if any employees are PSSSF members.

**These seeded values are not authoritative.** They are a starting point for an authorised administrator to review, correct and verify.

## Allowance tax treatment

Allowance types carry explicit `is_taxable`, `is_social_security_base` and `is_cash_emolument` flags, plus a `treatment_reference` field for the legal basis. `seed_reference_data` creates common allowance types as taxable, with the note "REVIEW REQUIRED". Adjust each one to match current TRA/NSSF guidance.
