import { useState } from "react";
import { errorMessage } from "../../api/client";
import { DataTable, Pagination, SearchBox } from "../../components/DataTable";
import { Alert, Card, Modal, PageHeader } from "../../components/ui";
import { dateTime, humanize } from "../../lib/format";
import { useList } from "../../lib/hooks";

const ACTIONS = ["LOGIN", "LOGIN_FAILED", "LOGOUT", "PASSWORD_RESET", "PASSWORD_CHANGE", "CREATE", "UPDATE", "DELETE", "PAYROLL_CALCULATE",
  "PAYROLL_STATUS", "PAYROLL_APPROVE", "PAYROLL_CLOSE", "PAYSLIP_GENERATE", "PAYMENT_RECORD", "PERMISSION_CHANGE", "EXPORT"];

export default function AuditLogs() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [action, setAction] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [selected, setSelected] = useState<any>(null);
  const q = useList<any>("/audit-logs/", { page, search, action, date_from: from, date_to: to });
  return (
    <div>
      <PageHeader title="Audit logs" subtitle="Append-only record of security and payroll events. Records cannot be edited or deleted." />
      <Card>
        <div className="mb-3 flex flex-col gap-2 lg:flex-row">
          <SearchBox value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="User, record, message..." />
          <select className="input lg:w-52" value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }} aria-label="Action">
            <option value="">All actions</option>
            {ACTIONS.map((a) => <option key={a} value={a}>{humanize(a)}</option>)}
          </select>
          <input type="date" className="input lg:w-40" value={from} onChange={(e) => setFrom(e.target.value)} aria-label="From date" />
          <input type="date" className="input lg:w-40" value={to} onChange={(e) => setTo(e.target.value)} aria-label="To date" />
        </div>
        {q.isError && <Alert>{errorMessage(q.error)}</Alert>}
        <DataTable loading={q.isLoading} rows={q.data?.results} onRowClick={setSelected} columns={[
          { key: "timestamp", header: "When", render: (r) => dateTime(r.timestamp) },
          { key: "username", header: "User", render: (r) => r.username || "-" },
          { key: "action", header: "Action", render: (r) => humanize(r.action) },
          { key: "model", header: "Record", render: (r) => (r.model ? `${r.model.split(".").pop()} #${r.object_id}` : "-") },
          { key: "object_repr", header: "Description", hideOnMobile: true, render: (r) => <span className="block max-w-xs truncate">{r.message || r.object_repr || "-"}</span> },
          { key: "ip_address", header: "IP", hideOnMobile: true, render: (r) => r.ip_address || "-" },
        ]} />
        {q.data && <Pagination page={page} count={q.data.count} onPage={setPage} />}
      </Card>
      <Modal open={!!selected} onClose={() => setSelected(null)} title="Audit record" wide>
        {selected && (
          <div className="space-y-3 text-sm">
            <p><strong>{humanize(selected.action)}</strong> by {selected.username || "system"} on {dateTime(selected.timestamp)} from {selected.ip_address || "unknown IP"}</p>
            <p>{selected.model} #{selected.object_id} — {selected.object_repr}</p>
            {selected.message && <p className="text-slate-600">{selected.message}</p>}
            <div className="grid gap-3 md:grid-cols-2">
              <div><h3 className="mb-1 font-semibold text-red-700">Old values</h3><pre className="max-h-80 overflow-auto rounded bg-slate-50 p-2 text-xs">{JSON.stringify(selected.old_values, null, 2) ?? "—"}</pre></div>
              <div><h3 className="mb-1 font-semibold text-emerald-700">New values</h3><pre className="max-h-80 overflow-auto rounded bg-slate-50 p-2 text-xs">{JSON.stringify(selected.new_values, null, 2) ?? "—"}</pre></div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
