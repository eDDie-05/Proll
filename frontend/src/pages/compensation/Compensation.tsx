import { CrudPage } from "../../components/CrudPage";
import { Alert } from "../../components/ui";
import { date, humanize, money } from "../../lib/format";
import { employeeLabel, useOptions } from "../../lib/hooks";

const yes = (b: boolean) => (b ? "Yes" : "No");

export function AllowanceTypes() {
  return (
    <CrudPage<any>
      title="Allowance types"
      entityName="allowance type"
      endpoint="/allowance-types/"
      managePermission="allowances.manage"
      defaults={{ category: "ALLOWANCE", calculation_type: "FIXED", is_recurring: true, is_cash_emolument: true, prorate: true, is_active: true }}
      before={<div className="mb-4"><Alert kind="warning">Tax and contribution treatment is never assumed. Set it explicitly for each allowance based on current TRA/NSSF guidance and record the basis.</Alert></div>}
      columns={[
        { key: "code", header: "Code", className: "font-medium" },
        { key: "name", header: "Name" },
        { key: "category", header: "Category", render: (r) => humanize(r.category) },
        { key: "calculation_type", header: "Calculation", hideOnMobile: true, render: (r) => humanize(r.calculation_type) },
        { key: "is_taxable", header: "Taxable", render: (r) => yes(r.is_taxable) },
        { key: "is_social_security_base", header: "SS base", hideOnMobile: true, render: (r) => yes(r.is_social_security_base) },
        { key: "is_active", header: "Active", render: (r) => yes(r.is_active) },
      ]}
      fields={[
        { name: "code", label: "Code", required: true },
        { name: "name", label: "Name", required: true },
        { name: "category", label: "Category", type: "select", required: true, options: ["ALLOWANCE", "OVERTIME", "BONUS", "COMMISSION", "OTHER"].map((v) => ({ value: v, label: humanize(v) })) },
        { name: "calculation_type", label: "Calculation type", type: "select", required: true, options: [
          { value: "FIXED", label: "Fixed amount" }, { value: "PERCENT_OF_BASIC", label: "% of basic salary" }, { value: "HOURS_X_RATE", label: "Quantity × rate" }] },
        { name: "default_amount", label: "Default amount (TZS)", type: "number", min: "0", showIf: (v) => v.calculation_type === "FIXED" },
        { name: "default_rate", label: "Default rate (% or rate per unit)", type: "number", min: "0", step: "0.0001", showIf: (v) => v.calculation_type !== "FIXED" },
        { name: "is_taxable", label: "Taxable (included in PAYE taxable income)", type: "checkbox" },
        { name: "is_social_security_base", label: "Included in social-security base", type: "checkbox" },
        { name: "is_cash_emolument", label: "Cash emolument (employer levies e.g. SDL/WCF)", type: "checkbox" },
        { name: "is_recurring", label: "Recurring", type: "checkbox" },
        { name: "prorate", label: "Pro-rate for partial months", type: "checkbox" },
        { name: "is_active", label: "Active", type: "checkbox" },
        { name: "treatment_reference", label: "Basis for tax treatment", colSpan: 2, placeholder: "e.g. TRA guidance ref / Income Tax Act section" },
        { name: "description", label: "Description", type: "textarea", colSpan: 2 },
      ]}
    />
  );
}

export function EmployeeAllowances() {
  const employees = useOptions("/employees/", employeeLabel);
  const types = useOptions("/allowance-types/", (t) => `${t.name} (${humanize(t.calculation_type)})`, true, { is_active: true });
  return (
    <CrudPage<any>
      title="Employee allowances"
      entityName="allowance"
      endpoint="/employee-allowances/"
      managePermission="allowances.manage"
      deletable
      defaults={{ is_recurring: true }}
      columns={[
        { key: "employee_number", header: "Emp. ID" },
        { key: "employee_name", header: "Employee" },
        { key: "allowance_name", header: "Allowance" },
        { key: "amount", header: "Amount / rate", align: "right", render: (r) => (r.amount ? money(r.amount) : r.rate ? `${Number(r.rate)}${r.quantity ? ` × ${Number(r.quantity)}` : "%"}` : "Default") },
        { key: "is_recurring", header: "Recurring", hideOnMobile: true, render: (r) => (r.is_recurring ? "Yes" : "One-off") },
        { key: "effective_from", header: "From", render: (r) => date(r.effective_from) },
        { key: "effective_to", header: "To", hideOnMobile: true, render: (r) => date(r.effective_to) },
      ]}
      fields={[
        { name: "employee", label: "Employee", type: "select", required: true, options: employees },
        { name: "allowance_type", label: "Allowance type", type: "select", required: true, options: types },
        { name: "amount", label: "Amount (TZS) — overrides default", type: "number", min: "0" },
        { name: "rate", label: "Rate — overrides default", type: "number", min: "0", step: "0.0001" },
        { name: "quantity", label: "Quantity (hours/units)", type: "number", min: "0", step: "0.01" },
        { name: "is_recurring", label: "Recurring every period", type: "checkbox", help: "Untick for one-off payments (paid in the period containing the start date)." },
        { name: "effective_from", label: "Effective from", type: "date", required: true },
        { name: "effective_to", label: "Effective to", type: "date" },
        { name: "notes", label: "Notes", colSpan: 2 },
      ]}
    />
  );
}

export function DeductionTypes() {
  return (
    <CrudPage<any>
      title="Deduction types"
      entityName="deduction type"
      endpoint="/deduction-types/"
      managePermission="deductions.manage"
      subtitle="Statutory contributions and PAYE are configured under Statutory rules. Use these for other approved deductions."
      defaults={{ category: "OTHER", calculation_type: "FIXED", is_recurring: true, is_active: true }}
      columns={[
        { key: "code", header: "Code", className: "font-medium" },
        { key: "name", header: "Name" },
        { key: "category", header: "Category", render: (r) => humanize(r.category) },
        { key: "calculation_type", header: "Calculation", hideOnMobile: true, render: (r) => humanize(r.calculation_type) },
        { key: "max_amount", header: "Cap", align: "right", hideOnMobile: true, render: (r) => money(r.max_amount) },
        { key: "reduces_taxable_income", header: "Pre-tax", render: (r) => yes(r.reduces_taxable_income) },
        { key: "is_active", header: "Active", render: (r) => yes(r.is_active) },
      ]}
      fields={[
        { name: "code", label: "Code", required: true },
        { name: "name", label: "Name", required: true },
        { name: "category", label: "Category", type: "select", required: true, options: ["STATUTORY", "LOAN", "ADVANCE", "INSURANCE", "PENSION", "UNION", "OTHER"].map((v) => ({ value: v, label: humanize(v) })) },
        { name: "calculation_type", label: "Calculation type", type: "select", required: true, options: [
          { value: "FIXED", label: "Fixed amount" }, { value: "PERCENT_OF_BASIC", label: "% of basic" }, { value: "PERCENT_OF_GROSS", label: "% of gross" }] },
        { name: "default_amount", label: "Default amount (TZS)", type: "number", min: "0", showIf: (v) => v.calculation_type === "FIXED" },
        { name: "default_rate", label: "Default rate (%)", type: "number", min: "0", step: "0.0001", showIf: (v) => v.calculation_type !== "FIXED" },
        { name: "max_amount", label: "Maximum per period (TZS)", type: "number", min: "0" },
        { name: "is_statutory", label: "Statutory deduction", type: "checkbox" },
        { name: "reduces_taxable_income", label: "Deduct before PAYE (only where the law permits)", type: "checkbox" },
        { name: "is_recurring", label: "Recurring", type: "checkbox" },
        { name: "is_active", label: "Active", type: "checkbox" },
        { name: "description", label: "Description", type: "textarea", colSpan: 2 },
      ]}
    />
  );
}

export function EmployeeDeductions() {
  const employees = useOptions("/employees/", employeeLabel);
  const types = useOptions("/deduction-types/", (t) => t.name, true, { is_active: true });
  return (
    <CrudPage<any>
      title="Employee deductions"
      entityName="deduction"
      endpoint="/employee-deductions/"
      managePermission="deductions.manage"
      deletable
      defaults={{ is_recurring: true, is_active: true }}
      columns={[
        { key: "employee_number", header: "Emp. ID" },
        { key: "employee_name", header: "Employee" },
        { key: "deduction_name", header: "Deduction" },
        { key: "amount", header: "Amount / rate", align: "right", render: (r) => (r.amount ? money(r.amount) : r.rate ? `${Number(r.rate)}%` : "Default") },
        { key: "start_date", header: "Start", render: (r) => date(r.start_date) },
        { key: "end_date", header: "End", hideOnMobile: true, render: (r) => date(r.end_date) },
        { key: "is_active", header: "Active", render: (r) => yes(r.is_active) },
      ]}
      fields={[
        { name: "employee", label: "Employee", type: "select", required: true, options: employees },
        { name: "deduction_type", label: "Deduction type", type: "select", required: true, options: types },
        { name: "amount", label: "Amount (TZS)", type: "number", min: "0" },
        { name: "rate", label: "Rate (%)", type: "number", min: "0", step: "0.0001" },
        { name: "max_amount", label: "Maximum per period", type: "number", min: "0" },
        { name: "reference", label: "Reference" },
        { name: "start_date", label: "Start date", type: "date", required: true },
        { name: "end_date", label: "End date", type: "date" },
        { name: "is_recurring", label: "Recurring", type: "checkbox" },
        { name: "is_active", label: "Active", type: "checkbox" },
        { name: "notes", label: "Notes", colSpan: 2 },
      ]}
    />
  );
}
