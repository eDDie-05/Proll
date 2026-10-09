import { CrudPage } from "../../components/CrudPage";
import { date, money } from "../../lib/format";
import { employeeLabel, useOptions } from "../../lib/hooks";

export default function Salaries() {
  const employees = useOptions("/employees/", employeeLabel, true, { status: "ACTIVE" });
  return (
    <CrudPage<any>
      title="Salary history"
      subtitle="Append-only, effective-dated basic salaries. Existing records cannot be edited or deleted."
      entityName="salary record"
      endpoint="/salaries/"
      managePermission="salary.manage"
      editable={() => false}
      columns={[
        { key: "employee_number", header: "Emp. ID", className: "font-medium" },
        { key: "employee_name", header: "Employee" },
        { key: "basic_salary", header: "Basic salary", align: "right", render: (r) => money(r.basic_salary) },
        { key: "effective_from", header: "From", render: (r) => date(r.effective_from) },
        { key: "effective_to", header: "To", render: (r) => (r.effective_to ? date(r.effective_to) : "Current") },
        { key: "reason", header: "Reason", hideOnMobile: true, render: (r) => r.reason || "-" },
      ]}
      fields={[
        { name: "employee", label: "Employee", type: "select", required: true, options: employees, colSpan: 2 },
        { name: "basic_salary", label: "Basic salary (TZS)", type: "number", required: true, min: "0" },
        { name: "effective_from", label: "Effective from", type: "date", required: true },
        { name: "reason", label: "Reason", colSpan: 2 },
      ]}
    />
  );
}
