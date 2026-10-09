import { useNavigate } from "react-router-dom";
import { CrudPage } from "../../components/CrudPage";
import { StatusBadge } from "../../components/ui";
import { date, money } from "../../lib/format";
import type { PayrollPeriod } from "../../lib/types";

export default function Periods() {
  const navigate = useNavigate();
  return (
    <CrudPage<PayrollPeriod>
      title="Payroll periods"
      subtitle="Draft → Calculated → Review → Approved → Paid → Closed"
      entityName="payroll period"
      endpoint="/payroll-periods/"
      managePermission="payroll.prepare"
      editable={(p) => p.status === "DRAFT" || p.status === "CALCULATED"}
      deletable
      onRowClick={(p) => navigate(`/payroll/${p.id}`)}
      columns={[
        { key: "name", header: "Period", className: "font-medium text-brand-700" },
        { key: "start_date", header: "Dates", render: (p) => `${date(p.start_date)} – ${date(p.end_date)}` },
        { key: "pay_date", header: "Pay date", hideOnMobile: true, render: (p) => date(p.pay_date) },
        { key: "employees", header: "Employees", align: "right", hideOnMobile: true, render: (p) => p.current_run?.employee_count ?? "-" },
        { key: "gross", header: "Gross", align: "right", hideOnMobile: true, render: (p) => money(p.current_run?.total_gross) },
        { key: "net", header: "Net", align: "right", render: (p) => money(p.current_run?.total_net) },
        { key: "status", header: "Status", render: (p) => <StatusBadge status={p.status} /> },
      ]}
      fields={[
        { name: "name", label: "Name", required: true, placeholder: "September 2026", colSpan: 2 },
        { name: "start_date", label: "Start date", type: "date", required: true },
        { name: "end_date", label: "End date", type: "date", required: true },
        { name: "pay_date", label: "Pay date", type: "date" },
        { name: "notes", label: "Notes", type: "textarea", colSpan: 2 },
      ]}
    />
  );
}
