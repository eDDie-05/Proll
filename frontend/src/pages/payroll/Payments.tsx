import { useState } from "react";
import { errorMessage } from "../../api/client";
import { DataTable, Pagination, SearchBox } from "../../components/DataTable";
import { Alert, Card, PageHeader, StatusBadge } from "../../components/ui";
import { date, money } from "../../lib/format";
import { useList, useOptions } from "../../lib/hooks";

export default function Payments() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [period, setPeriod] = useState("");
  const [status, setStatus] = useState("");
  const periods = useOptions("/payroll-periods/", (p) => p.name);
  const q = useList<any>("/payments/", { page, search, item__run__period: period, status });
  return (
    <div>
      <PageHeader title="Payments" subtitle="Salary payment status. Record payments from the payroll period page." />
      <Card>
        <div className="mb-3 flex flex-col gap-2 sm:flex-row">
          <SearchBox value={search} onChange={(v) => { setSearch(v); setPage(1); }} />
          <select className="input sm:w-56" value={period} onChange={(e) => { setPeriod(e.target.value); setPage(1); }} aria-label="Period">
            <option value="">All periods</option>
            {periods.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
          <select className="input sm:w-40" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} aria-label="Status">
            <option value="">All statuses</option><option>PENDING</option><option>PAID</option><option>FAILED</option>
          </select>
        </div>
        {q.isError && <Alert>{errorMessage(q.error)}</Alert>}
        <DataTable loading={q.isLoading} rows={q.data?.results} columns={[
          { key: "period_name", header: "Period" },
          { key: "employee_number", header: "Emp. ID" },
          { key: "employee_name", header: "Employee" },
          { key: "bank_name", header: "Bank", hideOnMobile: true, render: (r) => r.bank_name || r.method },
          { key: "account_number", header: "Account", hideOnMobile: true, render: (r) => (r.account_number ? "••••" + r.account_number.slice(-4) : "-") },
          { key: "amount", header: "Amount", align: "right", render: (r) => money(r.amount) },
          { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
          { key: "payment_date", header: "Paid on", render: (r) => date(r.payment_date) },
          { key: "reference", header: "Reference", hideOnMobile: true, render: (r) => r.reference || "-" },
        ]} />
        {q.data && <Pagination page={page} count={q.data.count} onPage={setPage} />}
      </Card>
    </div>
  );
}
