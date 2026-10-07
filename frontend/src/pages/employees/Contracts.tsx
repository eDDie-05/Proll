import { CrudPage } from "../../components/CrudPage";
import { StatusBadge } from "../../components/ui";
import { date, money } from "../../lib/format";
import { employeeLabel, useOptions } from "../../lib/hooks";

export default function Contracts() {
  const employees = useOptions("/employees/", employeeLabel);
  const types = useOptions("/employment-types/", (t) => t.name);
  const depts = useOptions("/departments/", (d) => d.name);
  const positions = useOptions("/positions/", (p) => p.title);
  return (
    <CrudPage<any>
      title="Employment contracts"
      subtitle="Contracts are kept as history — supersede or terminate instead of deleting."
      entityName="contract"
      endpoint="/contracts/"
      managePermission="contracts.manage"
      defaults={{ status: "ACTIVE", working_hours_per_week: "40" }}
      toForm={(r) => ({ ...r, document: null })}
      columns={[
        { key: "contract_number", header: "Contract no.", className: "font-medium" },
        { key: "employee_name", header: "Employee" },
        { key: "employment_type_name", header: "Type", hideOnMobile: true },
        { key: "start_date", header: "Start", render: (r) => date(r.start_date) },
        { key: "end_date", header: "End", render: (r) => date(r.end_date) },
        { key: "basic_salary", header: "Basic", align: "right", render: (r) => money(r.basic_salary) },
        { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
      ]}
      fields={[
        { name: "employee", label: "Employee", type: "select", required: true, options: employees },
        { name: "contract_number", label: "Contract number", required: true },
        { name: "employment_type", label: "Employment type", type: "select", required: true, options: types },
        { name: "department", label: "Department", type: "select", required: true, options: depts },
        { name: "position", label: "Position", type: "select", options: positions },
        { name: "status", label: "Status", type: "select", required: true, options: ["DRAFT", "ACTIVE", "EXPIRED", "TERMINATED", "SUPERSEDED"].map((s) => ({ value: s, label: s })) },
        { name: "start_date", label: "Start date", type: "date", required: true },
        { name: "end_date", label: "End date", type: "date" },
        { name: "basic_salary", label: "Basic salary (TZS)", type: "number", required: true, min: "0" },
        { name: "working_hours_per_week", label: "Working hours / week", type: "number", min: "0" },
        { name: "document", label: "Contract document (PDF/JPG/PNG, max 5 MB)", type: "file" },
        { name: "create_salary_record", label: "Create salary record from this contract", type: "checkbox",
          help: "Adds an effective-dated salary record starting on the contract start date." },
        { name: "notes", label: "Notes", type: "textarea", colSpan: 2 },
      ]}
    />
  );
}
