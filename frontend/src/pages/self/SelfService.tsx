import { useQuery } from "@tanstack/react-query";
import { Eye, FileDown } from "lucide-react";
import { useState } from "react";
import { api, download, errorMessage } from "../../api/client";
import { DataTable } from "../../components/DataTable";
import { useToast } from "../../components/Toast";
import { Alert, Card, Modal, PageHeader, PageLoader, StatusBadge } from "../../components/ui";
import { date, humanize, money } from "../../lib/format";
import { ItemBreakdown } from "../payroll/ItemBreakdown";

function useSelf<T>(path: string) {
  return useQuery({ queryKey: ["self", path], queryFn: async () => (await api.get<T>(path)).data, retry: false });
}

export function MyProfile() {
  const notify = useToast();
  const p = useSelf<any>("/self/profile/");
  const h = useSelf<any[]>("/self/salary-history/");
  if (p.isLoading) return <PageLoader />;
  if (p.isError) return <Alert kind="info">{errorMessage(p.error)}</Alert>;
  const e = p.data;
  const row = (l: string, v: any) => (
    <div><dt className="text-xs uppercase text-slate-500">{l}</dt><dd className="text-sm text-slate-800">{v || "-"}</dd></div>
  );
  return (
    <div className="space-y-4">
      <PageHeader title="My profile" subtitle={`${e.employee_number} · ${e.department_name}`} actions={
        <button className="btn-secondary" onClick={() => download("/reports/employee-statement/?export=pdf", "salary-statement.pdf").catch((x) => notify(errorMessage(x), "error"))}>
          <FileDown className="h-4 w-4" /> Salary statement (PDF)
        </button>
      } />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Personal & employment">
          <dl className="grid grid-cols-2 gap-3">
            {row("Name", e.full_name)}{row("Status", <StatusBadge status={e.status} />)}
            {row("Job title", e.position_title)}{row("Department", e.department_name)}
            {row("Employment type", e.employment_type_name)}{row("Start date", date(e.employment_start_date))}
            {row("Email", e.email)}{row("Phone", e.phone)}
          </dl>
        </Card>
        <Card title="Pay details">
          <dl className="grid grid-cols-2 gap-3">
            {row("Current basic salary", money(e.current_basic_salary))}{row("Payment method", humanize(e.payment_method))}
            {row("Bank", e.bank_name)}{row("Account", e.bank_account_number ? "••••" + e.bank_account_number.slice(-4) : "-")}
            {row("TIN", e.tin)}{row("Social security no.", e.social_security_number)}
          </dl>
        </Card>
      </div>
      <Card title="Salary history">
        <DataTable loading={h.isLoading} rows={h.data} columns={[
          { key: "basic_salary", header: "Basic salary", align: "right", render: (r: any) => money(r.basic_salary) },
          { key: "effective_from", header: "From", render: (r: any) => date(r.effective_from) },
          { key: "effective_to", header: "To", render: (r: any) => (r.effective_to ? date(r.effective_to) : "Current") },
          { key: "reason", header: "Reason", render: (r: any) => r.reason || "-" },
        ]} />
      </Card>
    </div>
  );
}

export function MyPayslips() {
  const notify = useToast();
  const q = useSelf<any[]>("/self/payslips/");
  const [viewing, setViewing] = useState<any>(null);
  return (
    <div>
      <PageHeader title="My payslips" subtitle="Payslips appear here once payroll is approved." />
      <Card>
        {q.isError && <Alert kind="info">{errorMessage(q.error)}</Alert>}
        <DataTable loading={q.isLoading} rows={q.data} empty="No payslips available yet." columns={[
          { key: "period_name", header: "Period", className: "font-medium" },
          { key: "payslip_number", header: "Payslip no.", hideOnMobile: true },
          { key: "gross_earnings", header: "Gross", align: "right", hideOnMobile: true, render: (r) => money(r.gross_earnings) },
          { key: "total_deductions", header: "Deductions", align: "right", hideOnMobile: true, render: (r) => money(r.total_deductions) },
          { key: "net_salary", header: "Net pay", align: "right", render: (r) => money(r.net_salary) },
          { key: "a", header: "", align: "right", render: (r) => (
            <div className="flex justify-end gap-1">
              <button className="btn-secondary btn-sm" onClick={() => setViewing(r)} aria-label="View"><Eye className="h-3.5 w-3.5" /></button>
              <button className="btn-primary btn-sm" onClick={() => download(`/self/payslips/${r.id}/pdf/`, `${r.payslip_number}.pdf`).catch((e) => notify(errorMessage(e), "error"))}>
                <FileDown className="h-3.5 w-3.5" /> PDF
              </button>
            </div>
          ) },
        ]} />
      </Card>
      <Modal open={!!viewing} onClose={() => setViewing(null)} title={`Payslip — ${viewing?.period_name ?? ""}`} wide>
        {viewing && <ItemBreakdown itemId={viewing.item} url={`/self/payslips/${viewing.id}/`} />}
      </Modal>
    </div>
  );
}

export function MyDeductions() {
  const q = useSelf<any[]>("/self/deductions/");
  return (
    <div>
      <PageHeader title="My deductions" subtitle="Deductions from approved payroll periods." />
      <Card>
        {q.isError && <Alert kind="info">{errorMessage(q.error)}</Alert>}
        <DataTable loading={q.isLoading} rows={q.data} columns={[
          { key: "period_name", header: "Period" },
          { key: "name", header: "Deduction" },
          { key: "is_statutory", header: "Type", render: (r) => (r.is_statutory ? "Statutory" : "Other") },
          { key: "amount", header: "Amount", align: "right", render: (r) => money(r.amount) },
        ]} />
      </Card>
    </div>
  );
}
