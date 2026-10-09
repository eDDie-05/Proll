import clsx from "clsx";
import { useState } from "react";
import { CrudPage } from "../../components/CrudPage";
import { humanize } from "../../lib/format";
import { useOptions } from "../../lib/hooks";

const yes = (b: boolean) => (b ? "Yes" : "No");

function Departments() {
  return <CrudPage<any> title="Departments" entityName="department" endpoint="/departments/" managePermission="employees.manage" deletable
    defaults={{ is_active: true }}
    columns={[{ key: "code", header: "Code" }, { key: "name", header: "Name" }, { key: "employee_count", header: "Active employees", align: "right" },
      { key: "is_active", header: "Active", render: (r) => yes(r.is_active) }]}
    fields={[{ name: "code", label: "Code", required: true }, { name: "name", label: "Name", required: true },
      { name: "description", label: "Description", type: "textarea", colSpan: 2 }, { name: "is_active", label: "Active", type: "checkbox" }]} />;
}

function Positions() {
  const depts = useOptions("/departments/", (d) => d.name);
  return <CrudPage<any> title="Positions / job titles" entityName="position" endpoint="/positions/" managePermission="employees.manage" deletable
    defaults={{ is_active: true }}
    columns={[{ key: "title", header: "Title" }, { key: "department_name", header: "Department", render: (r) => r.department_name || "-" },
      { key: "is_active", header: "Active", render: (r) => yes(r.is_active) }]}
    fields={[{ name: "title", label: "Title", required: true }, { name: "department", label: "Department", type: "select", options: depts },
      { name: "description", label: "Description", type: "textarea", colSpan: 2 }, { name: "is_active", label: "Active", type: "checkbox" }]} />;
}

function EmploymentTypes() {
  return <CrudPage<any> title="Employment types" entityName="employment type" endpoint="/employment-types/" managePermission="employees.manage" deletable
    defaults={{ is_active: true }}
    columns={[{ key: "code", header: "Code" }, { key: "name", header: "Name" }, { key: "is_active", header: "Active", render: (r) => yes(r.is_active) }]}
    fields={[{ name: "code", label: "Code", required: true }, { name: "name", label: "Name", required: true },
      { name: "description", label: "Description", type: "textarea", colSpan: 2 }, { name: "is_active", label: "Active", type: "checkbox" }]} />;
}

function LeaveTypes() {
  return <CrudPage<any> title="Leave types" entityName="leave type" endpoint="/leave-types/" managePermission="leave.manage" deletable
    subtitle="Payroll effect is configured per leave type — no legal assumption is built in."
    defaults={{ is_active: true, payroll_effect: "NONE" }}
    columns={[{ key: "code", header: "Code" }, { key: "name", header: "Name" }, { key: "payroll_effect", header: "Payroll effect", render: (r) => humanize(r.payroll_effect) },
      { key: "annual_entitlement_days", header: "Entitlement (days)", align: "right", render: (r) => r.annual_entitlement_days ?? "-" }]}
    fields={[{ name: "code", label: "Code", required: true }, { name: "name", label: "Name", required: true },
      { name: "payroll_effect", label: "Payroll effect", type: "select", required: true, options: [
        { value: "NONE", label: "None (paid leave)" }, { value: "DEDUCT_BASIC_PRORATA", label: "Deduct basic salary pro-rata" }] },
      { name: "annual_entitlement_days", label: "Annual entitlement (days)", type: "number", min: "0" },
      { name: "description", label: "Description", type: "textarea", colSpan: 2 }, { name: "is_active", label: "Active", type: "checkbox" }]} />;
}

const TABS = [
  { key: "departments", label: "Departments", el: <Departments /> },
  { key: "positions", label: "Positions", el: <Positions /> },
  { key: "types", label: "Employment types", el: <EmploymentTypes /> },
  { key: "leave", label: "Leave types", el: <LeaveTypes /> },
];

export default function Organisation() {
  const [tab, setTab] = useState("departments");
  return (
    <div>
      <div className="no-print mb-4 flex gap-1 overflow-x-auto border-b border-slate-200">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)} className={clsx("whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium",
            tab === t.key ? "border-brand-700 text-brand-800" : "border-transparent text-slate-500")}>{t.label}</button>
        ))}
      </div>
      {TABS.find((t) => t.key === tab)?.el}
    </div>
  );
}
