# Payroll Calculation Engine

Code: `backend/apps/payroll/engine.py` (calculation), `backend/apps/statutory/calculator.py` (a single rule), `backend/apps/payroll/workflow.py` (state machine).

## Principles

1. **No statutory rate lives in code.** PAYE, social security, WCF, SDL and any other levy are `StatutoryRule` rows selected by effective date.
2. **Every component is stored.** Each employee result (`PayrollItem`) has `PayrollLine` rows for every earning, deduction and employer contribution. Each line has a `detail` JSON explaining its derivation: salary segments, pro-ration factor, tax bands, rule version, base amount and cap applied.
3. **Employer contributions never affect net pay.** They are stored as `EMPLOYER` lines and summed into *employer total cost*.
4. **History is immutable.** Recalculation creates a new `PayrollRun` (older runs are kept). Items snapshot the employee's name, department, job title and bank details at calculation time. Approved and closed payroll is never recalculated; corrections are `PayrollAdjustment`s applied in an open period.
5. **Decimal arithmetic** throughout, rounded half-up to `CompanySettings.rounding_decimals` (default 2).

## Rule selection

`StatutoryRule.in_force(period.end_date)` returns active rules whose `effective_from ≤ end_date ≤ effective_to (or open)`. Overlapping active versions of the same code are rejected on save, so at most one version per code applies.

A rule applies to an employee only if all of these hold:

| Condition | Field |
|---|---|
| Residency matches (`ALL` / `RESIDENT` / `NON_RESIDENT`) | `residency` vs `Employee.is_tax_resident` |
| Scheme matches (empty list = everyone) | `applies_to_schemes` vs `Employee.social_security_scheme` |
| Payroll headcount ≥ threshold | `min_employee_count` (e.g. SDL for 10+ employees) |

## Eligibility

An employee is included when their employment dates overlap the period **and** either:
- status is `ACTIVE` or `ON_LEAVE`, or
- their `employment_end_date` falls inside the period (leavers are paid up to their last day).

Suspended employees, and those who left before the period, are excluded. Exclusions appear as run warnings.

## Step-by-step calculation (per employee)

```
window   = [max(period.start, employment_start), min(period.end, employment_end or period.end)]
days     = calendar days in window
factor   = 1                         if days == calendar days in period
         = days / basis_days         otherwise   (basis = calendar days, or 30 — CompanySettings.proration_basis)
```

### 1. Basic salary
Salary records overlapping the window are weighted by the calendar days each covers, then multiplied by `factor` once:

```
basic = Σ salary_i × (days_i / days_in_window) × factor
```

- A full month with a mid-month raise pays a blended monthly salary, e.g. 1,000,000 for 15 days + 1,300,000 for 15 days = 1,150,000.
- A joiner on 16 September (30-day month) with 1,000,000 → 15/30 → 500,000.
- A leaver on 10 September → 10/30 → 333,333.33.

### 2. Unpaid leave
For approved leave whose type has `payroll_effect = DEDUCT_BASIC_PRORATA`, a negative earning line of `monthly_basic / basis_days × leave_days_in_window` is added, capped at the basic earned. It reduces gross, taxable income and contribution bases. Paid leave types have no effect.

### 3. Allowances and other earnings
Each `EmployeeAllowance` that applies to the period is included. Recurring allowances apply while effective; non-recurring ones apply only in the period containing `effective_from`.
- `FIXED`: amount (pro-rated by the employment factor if the type has `prorate`)
- `PERCENT_OF_BASIC`: rate × basic earned (already pro-rated)
- `HOURS_X_RATE`: quantity × rate (overtime)

Each line carries its type's flags: `is_taxable`, `is_social_security_base`, `is_cash_emolument`.

### 4. Earning adjustments
Approved `PayrollAdjustment`s of category EARNING targeting this period, with their own tax/contribution flags.

### 5. Bases
```
gross                 = Σ earnings
taxable earnings      = Σ earnings where is_taxable
social security base  = Σ earnings where is_social_security_base
cash emoluments       = Σ earnings where is_cash_emolument
```

### 6. Pre-tax employee deductions
- Employee statutory rules whose base is **not** taxable income (e.g. NSSF employee share), in `calculation_order`.
- `EmployeeDeduction`s whose type has `reduces_taxable_income` (only where the law permits).

```
taxable income = max(taxable earnings − Σ deductions with reduces_taxable_income, 0)
```

### 7. Tax
Employee rules whose base is `TAXABLE_INCOME` (PAYE). Progressive rules apply each bracket's marginal rate to the slice of income inside it:

```
tax = Σ over brackets: (min(income, upper) − lower) × rate   for income > lower
```
Flat-rate rules (e.g. non-resident) apply `rate × base`. `base_ceiling`, `min_amount` and `max_amount` are honoured.

### 8. Post-tax deductions
- Other `EmployeeDeduction`s: fixed, % of basic, or % of gross; capped by `max_amount`.
- **Loans/advances:** for each ACTIVE loan whose start date ≤ period end, `min(installment, outstanding balance)`.
- Approved DEDUCTION adjustments.

### 9. Net
```
total deductions = Σ deduction lines
net salary       = gross − total deductions
```
A negative net raises a warning and **blocks approval**.

### 10. Employer contributions
Employer rules (NSSF employer share, WCF, SDL, …) are computed on their configured base and stored as `EMPLOYER` lines.
```
employer total cost = gross + Σ employer contributions
```

## Worked example (synthetic rates — used in the test suite)

Test fixture rules: social security 10% employee + 10% employer (pre-tax); levy 1% of cash emoluments; PAYE 0% to 100k, 10% to 500k, 20% above.

| Component | Amount (TZS) |
|---|---|
| Basic salary | 1,000,000.00 |
| Housing allowance (taxable, SS base) | 200,000.00 |
| Transport allowance (non-taxable, not SS base) | 100,000.00 |
| **Gross** | **1,300,000.00** |
| Social security 10% × 1,200,000 | 120,000.00 |
| Taxable income 1,200,000 − 120,000 | 1,080,000.00 |
| PAYE: 0 + 40,000 + 20% × 580,000 | 156,000.00 |
| **Total deductions** | **276,000.00** |
| **Net salary** | **1,024,000.00** |
| Employer social security 10% | 120,000.00 |
| Employer levy 1% × 1,300,000 | 13,000.00 |
| **Employer total cost** | **1,433,000.00** |

(See `apps/payroll/tests/test_engine.py::test_allowances_taxable_and_non_taxable`.)

## Workflow

| From | Action | To | Permission | Guards |
|---|---|---|---|---|
| DRAFT/CALCULATED | calculate | CALCULATED | `payroll.prepare` | eligible employees exist |
| CALCULATED | submit | REVIEW | `payroll.prepare` | a current run exists |
| REVIEW | reject (reason required) | CALCULATED | `payroll.approve` | |
| REVIEW | approve | APPROVED | `payroll.approve` | no negative net; all used rules VERIFIED (configurable); approver ≠ calculator/submitter (configurable) |
| APPROVED | mark paid | PAID | `payments.manage` | every payment recorded PAID |
| PAID | close | CLOSED | `payroll.close` | |

On **approve**, the engine creates one `Payment` per item from the snapshot bank details, posts `LoanRepayment`s (marking loans completed when cleared) and marks included adjustments APPLIED.

Every transition writes a `PayrollStatusChange` (who, when, from, to, comment) and an `AuditLog` entry.

## Extending

- **New statutory levy:** add a `StatutoryRule` in the UI. No code change is needed.
- **Rate change:** use *New version* on the rule, with the new effective date. Earlier periods keep using the old version, and rules already used in payroll are locked.
- **New allowance treatment:** set the flags on the allowance type and record the legal basis in `treatment_reference`.
