import { Eye, FileDown } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { download, errorMessage, openPdf } from "../../api/client";
import { DataTable, Pagination, SearchBox } from "../../components/DataTable";
import { useToast } from "../../components/Toast";
import { Alert, Card, PageHeader } from "../../components/ui";
import { dateTime, money } from "../../lib/format";
import { useList, useOptions } from "../../lib/hooks";

export default function PayslipList() {
  const notify = useToast();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [period, setPeriod] = useState("");
  const periods = useOptions("/payroll-periods/", (p) => p.name, true, { status: "" });
  const q = useList<any>("/payslips/", { page, search, item__run__period: period });
  return (
    <div>
      <PageHeader title="Payslips" subtitle="Generate payslips from an approved payroll period." />
      <Card>
        <div className="mb-3 flex flex-col gap-2 sm:flex-row">
          <SearchBox value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Payslip no., employee..." />
          <select className="input sm:w-56" value={period} onChange={(e) => { setPeriod(e.target.value); setPage(1); }} aria-label="Period">
            <option value="">All periods</option>
            {periods.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
        </div>
        {q.isError && <Alert>{errorMessage(q.error)}</Alert>}
        <DataTable loading={q.isLoading} rows={q.data?.results} columns={[
          { key: "payslip_number", header: "Payslip no.", className: "font-medium" },
          { key: "period_name", header: "Period" },
          { key: "employee_name", header: "Employee" },
          { key: "department_name", header: "Department", hideOnMobile: true },
          { key: "net_salary", header: "Net", align: "right", render: (r) => money(r.net_salary) },
          { key: "generated_at", header: "Generated", hideOnMobile: true, render: (r) => dateTime(r.generated_at) },
          { key: "actions", header: "", align: "right", render: (r) => (
            <div className="flex justify-end gap-1">
              <Link className="btn-secondary btn-sm" to={`/payslips/${r.item}`} aria-label="Preview"><Eye className="h-3.5 w-3.5" /></Link>
              <button className="btn-secondary btn-sm" aria-label="Download PDF"
                onClick={() => download(`/payslips/${r.id}/pdf/`, `${r.payslip_number}.pdf`).catch((e) => notify(errorMessage(e), "error"))}>
                <FileDown className="h-3.5 w-3.5" />
              </button>
              <button className="btn-secondary btn-sm" onClick={() => openPdf(`/payslips/${r.id}/pdf/`)}>Print</button>
            </div>
          ) },
        ]} empty="No payslips generated yet." />
        {q.data && <Pagination page={page} count={q.data.count} onPage={setPage} />}
      </Card>
    </div>
  );
}
