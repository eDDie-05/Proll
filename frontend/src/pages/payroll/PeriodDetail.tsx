import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Calculator, CheckCircle2, FileDown, Lock, Receipt, Send, Undo2, Wallet } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, download, errorMessage } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { DataTable, Pagination, SearchBox } from "../../components/DataTable";
import { useToast } from "../../components/Toast";
import { Alert, Card, ConfirmDialog, Disclaimer, Modal, PageHeader, PageLoader, Stat, StatusBadge } from "../../components/ui";
import { date, dateTime, money } from "../../lib/format";
import { useList } from "../../lib/hooks";
import type { PayrollItem, PayrollPeriod, PeriodStatus } from "../../lib/types";
import { ItemBreakdown } from "./ItemBreakdown";

const STEPS: PeriodStatus[] = ["DRAFT", "CALCULATED", "REVIEW", "APPROVED", "PAID", "CLOSED"];

function Stepper({ status }: { status: PeriodStatus }) {
  const idx = STEPS.indexOf(status);
  return (
    <ol className="flex flex-wrap items-center gap-1 text-xs" aria-label="Payroll workflow">
      {STEPS.map((s, i) => (
        <li key={s} className="flex items-center gap-1">
          <span className={clsx("rounded-full px-2.5 py-1 font-semibold",
            i < idx ? "bg-emerald-100 text-emerald-800" : i === idx ? "bg-brand-700 text-white" : "bg-slate-100 text-slate-500")}>
            {i + 1}. {s.charAt(0) + s.slice(1).toLowerCase()}
          </span>
          {i < STEPS.length - 1 && <span className="text-slate-300">→</span>}
        </li>
      ))}
    </ol>
  );
}

type ActionKey = "calculate" | "submit" | "approve" | "reject" | "mark-paid" | "close";

const ACTIONS: Record<ActionKey, { label: string; message: string; comment?: "optional" | "required"; danger?: boolean }> = {
  calculate: { label: "Calculate payroll", message: "Calculate pay for all eligible employees using the statutory rules in force at the period end. A previous calculation (if any) is kept as history." },
  submit: { label: "Submit for review", message: "Submit this payroll to an authorised approver.", comment: "optional" },
  approve: { label: "Approve payroll", message: "Approving creates payment instructions and posts loan repayments. This cannot be undone.", comment: "optional" },
  reject: { label: "Reject payroll", message: "Return this payroll to the preparer for correction.", comment: "required", danger: true },
  "mark-paid": { label: "Mark as paid", message: "Confirm that all salary payments have been made.", comment: "optional" },
  close: { label: "Close payroll", message: "Closing locks this payroll permanently. Later corrections must be made through adjustments.", comment: "optional", danger: true },
};

function PaymentsTab({ period }: { period: PayrollPeriod }) {
  const { can } = useAuth();
  const notify = useToast();
  const qc = useQueryClient();
  const [selected, setSelected] = useState<number[]>([]);
  const [form, setForm] = useState({ status: "PAID", payment_date: new Date().toISOString().slice(0, 10), reference: "" });
  const [exportFmt, setExportFmt] = useState("");
  const q = useQuery({ queryKey: ["payments", period.id], queryFn: async () => (await api.get(`/payroll-periods/${period.id}/payments/`)).data as any[] });
  const formats = useList<any>("/bank-export-formats/", {}, can("payments.export"));
  const record = useMutation({
    mutationFn: () => api.post(`/payroll-periods/${period.id}/record-payments/`, { ...form, payment_ids: selected }),
    onSuccess: (r) => {
      notify(`${r.data.updated} payment(s) updated.`);
      setSelected([]);
      qc.invalidateQueries({ queryKey: ["payments", period.id] });
    },
    onError: (e) => notify(errorMessage(e), "error"),
  });
  const editable = period.status === "APPROVED" && can("payments.manage");
  const rows = q.data || [];
  return (
    <Card title="Salary payments">
      {can("payments.export") && (
        <div className="no-print mb-3 flex flex-wrap items-end gap-2">
          <select className="input sm:w-64" value={exportFmt} onChange={(e) => setExportFmt(e.target.value)} aria-label="Bank file format">
            <option value="">Bank file format…</option>
            {formats.data?.results.filter((f: any) => f.is_active).map((f: any) => <option key={f.id} value={f.id}>{f.name}</option>)}
          </select>
          <button className="btn-secondary" disabled={!exportFmt}
            onClick={() => download(`/payroll-periods/${period.id}/bank-export/?export_format=${exportFmt}`, "bank.csv").catch((e) => notify(errorMessage(e), "error"))}>
            <FileDown className="h-4 w-4" /> Export bank file
          </button>
        </div>
      )}
      {editable && (
        <div className="no-print mb-3 grid gap-2 rounded-md bg-slate-50 p-3 sm:grid-cols-4">
          <select className="input" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} aria-label="Payment status">
            <option value="PAID">Paid</option><option value="FAILED">Failed</option><option value="PENDING">Pending</option>
          </select>
          <input type="date" className="input" value={form.payment_date} onChange={(e) => setForm({ ...form, payment_date: e.target.value })} aria-label="Payment date" />
          <input className="input" placeholder="Transaction reference" value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} />
          <button className="btn-primary" onClick={() => record.mutate()} disabled={record.isPending}>
            Record for {selected.length ? `${selected.length} selected` : "all"}
          </button>
        </div>
      )}
      <DataTable
        loading={q.isLoading}
        rows={rows}
        columns={[
          ...(editable ? [{
            key: "sel", header: <input type="checkbox" aria-label="Select all" checked={selected.length === rows.length && rows.length > 0}
              onChange={(e) => setSelected(e.target.checked ? rows.map((r: any) => r.id) : [])} />,
            render: (r: any) => <input type="checkbox" aria-label={`Select ${r.employee_name}`} checked={selected.includes(r.id)}
              onChange={(e) => setSelected((s) => (e.target.checked ? [...s, r.id] : s.filter((x) => x !== r.id)))} />,
          }] : []),
          { key: "employee_number", header: "Emp. ID" },
          { key: "employee_name", header: "Employee" },
          { key: "method", header: "Method", hideOnMobile: true },
          { key: "bank_name", header: "Bank", hideOnMobile: true, render: (r: any) => r.bank_name || "-" },
          { key: "amount", header: "Amount", align: "right", render: (r: any) => money(r.amount) },
          { key: "status", header: "Status", render: (r: any) => <StatusBadge status={r.status} /> },
          { key: "payment_date", header: "Paid on", render: (r: any) => date(r.payment_date) },
          { key: "reference", header: "Reference", hideOnMobile: true, render: (r: any) => r.reference || "-" },
        ]}
        empty="Payment instructions are created when payroll is approved."
      />
    </Card>
  );
}

export default function PeriodDetail() {
  const { id } = useParams();
  const { can } = useAuth();
  const notify = useToast();
  const qc = useQueryClient();
  const [tab, setTab] = useState("employees");
  const [action, setAction] = useState<ActionKey | null>(null);
  const [comment, setComment] = useState("");
  const [itemId, setItemId] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");

  const q = useQuery({ queryKey: ["period", id], queryFn: async () => (await api.get<PayrollPeriod>(`/payroll-periods/${id}/`)).data });
  const period = q.data;
  const items = useQuery({
    queryKey: ["period-items", id, page, search, period?.current_run?.id],
    enabled: !!period?.current_run,
    queryFn: async () => (await api.get(`/payroll-periods/${id}/items/`, { params: { page, q: search || undefined } })).data,
  });
  const check = useQuery({
    queryKey: ["approval-check", id, period?.status],
    enabled: period?.status === "REVIEW",
    queryFn: async () => (await api.get(`/payroll-periods/${id}/approval-check/`)).data as { can_approve: boolean; blockers: string[] },
  });
  const history = useQuery({
    queryKey: ["period-history", id, period?.status],
    enabled: tab === "history",
    queryFn: async () => (await api.get(`/payroll-periods/${id}/history/`)).data as any[],
  });

  const run = useMutation({
    mutationFn: (a: ActionKey) => api.post(`/payroll-periods/${id}/${a}/`, { comment }),
    onSuccess: (_, a) => {
      notify(`${ACTIONS[a].label}: done.`);
      setAction(null);
      setComment("");
      qc.invalidateQueries({ queryKey: ["period", id] });
      qc.invalidateQueries({ queryKey: ["period-items", id] });
      qc.invalidateQueries({ queryKey: ["/payroll-periods/"] });
      qc.invalidateQueries({ queryKey: ["payments"] });
    },
    onError: (e) => notify(errorMessage(e), "error"),
  });
  const payslips = useMutation({
    mutationFn: () => api.post(`/payroll-periods/${id}/generate-payslips/`),
    onSuccess: (r) => {
      notify(`${r.data.generated} payslip(s) generated.`);
      qc.invalidateQueries({ queryKey: ["period-items", id] });
    },
    onError: (e) => notify(errorMessage(e), "error"),
  });

  if (q.isLoading) return <PageLoader />;
  if (q.isError || !period) return <Alert>{errorMessage(q.error)}</Alert>;
  const r = period.current_run;
  const st = period.status;
  const released = ["APPROVED", "PAID", "CLOSED"].includes(st);

  const buttons: { key: ActionKey; show: boolean; icon: any; cls: string }[] = [
    { key: "calculate", show: can("payroll.prepare") && (st === "DRAFT" || st === "CALCULATED"), icon: Calculator, cls: st === "DRAFT" ? "btn-primary" : "btn-secondary" },
    { key: "submit", show: can("payroll.prepare") && st === "CALCULATED", icon: Send, cls: "btn-primary" },
    { key: "reject", show: can("payroll.approve") && st === "REVIEW", icon: Undo2, cls: "btn-secondary" },
    { key: "approve", show: can("payroll.approve") && st === "REVIEW", icon: CheckCircle2, cls: "btn-success" },
    { key: "mark-paid", show: can("payments.manage") && st === "APPROVED", icon: Wallet, cls: "btn-primary" },
    { key: "close", show: can("payroll.close") && st === "PAID", icon: Lock, cls: "btn-primary" },
  ];
  const cfg = action ? ACTIONS[action] : null;

  return (
    <div className="space-y-4">
      <PageHeader
        title={period.name}
        subtitle={`${date(period.start_date)} – ${date(period.end_date)} · Pay date ${date(period.pay_date)}`}
        actions={
          <>
            {buttons.filter((b) => b.show).map((b) => (
              <button key={b.key} className={b.cls} onClick={() => setAction(b.key)}
                disabled={b.key === "approve" && check.data && !check.data.can_approve}>
                <b.icon className="h-4 w-4" /> {ACTIONS[b.key].label}
              </button>
            ))}
            {released && can("payslips.generate") && (
              <button className="btn-secondary" onClick={() => payslips.mutate()} disabled={payslips.isPending}>
                <Receipt className="h-4 w-4" /> Generate payslips
              </button>
            )}
            {r && (can("reports.view") || can("payroll.view")) && (
              <button className="btn-secondary" onClick={() => download(`/payroll-periods/${id}/summary-pdf/`, "summary.pdf").catch((e) => notify(errorMessage(e), "error"))}>
                <FileDown className="h-4 w-4" /> Summary PDF
              </button>
            )}
          </>
        }
      />
      <Card><Stepper status={st} /></Card>

      {st === "REVIEW" && check.data && !check.data.can_approve && check.data.blockers.length > 0 && (
        <Alert kind="warning">
          <strong>Approval blocked:</strong>
          <ul className="ml-4 list-disc">{check.data.blockers.map((b) => <li key={b}>{b}</li>)}</ul>
          {check.data.blockers.some((b) => b.includes("not verified")) && (
            <p className="mt-1">Verify the rules under <Link className="underline" to="/admin/statutory-rules">Administration → Statutory rules</Link>, then recalculate.</p>
          )}
        </Alert>
      )}

      {r ? (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Employees" value={r.employee_count} hint={`Run #${r.run_number} by ${r.calculated_by_name} · ${dateTime(r.calculated_at)}`} />
            <Stat label="Gross payroll" value={money(r.total_gross)} />
            <Stat label="Total deductions" value={money(r.total_employee_deductions)} hint={`PAYE ${money(r.total_paye)}`} />
            <Stat label="Net payroll" value={money(r.total_net)} accent />
            <Stat label="Employer contributions" value={money(r.total_employer_contributions)} />
            <Stat label="Total employer cost" value={money(r.total_employer_cost)} />
            <Stat label="Approved by" value={period.approved_by_name || "—"} hint={dateTime(period.approved_at)} />
            <Stat label="Prepared / submitted" value={period.calculated_by_name || "—"} hint={period.submitted_by_name ? `Submitted by ${period.submitted_by_name}` : undefined} />
          </div>
          {r.warnings.length > 0 && (
            <Alert kind="warning">
              <details>
                <summary className="cursor-pointer font-semibold">{r.warnings.length} calculation warning(s)</summary>
                <ul className="ml-4 mt-1 list-disc">{r.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
              </details>
            </Alert>
          )}
        </>
      ) : (
        <Alert kind="info">This payroll has not been calculated yet.</Alert>
      )}

      <div className="no-print flex gap-1 border-b border-slate-200">
        {["employees", "payments", "history"].map((t) => (
          <button key={t} onClick={() => setTab(t)} className={clsx("border-b-2 px-3 py-2 text-sm font-medium capitalize",
            tab === t ? "border-brand-700 text-brand-800" : "border-transparent text-slate-500 hover:text-slate-800")}>{t}</button>
        ))}
      </div>

      {tab === "employees" && r && (
        <Card>
          <div className="mb-3"><SearchBox value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Employee name or ID" /></div>
          <DataTable<PayrollItem>
            loading={items.isLoading}
            rows={items.data?.results}
            onRowClick={(it) => setItemId(it.id)}
            columns={[
              { key: "employee_number", header: "Emp. ID", className: "font-medium text-brand-700" },
              { key: "employee_name", header: "Employee", render: (it) => <span>{it.employee_name}{it.warnings.length > 0 && <span className="ml-1 text-amber-600" title={it.warnings.join(" ")}>⚠</span>}</span> },
              { key: "department_name", header: "Department", hideOnMobile: true },
              { key: "basic_earned", header: "Basic", align: "right", hideOnMobile: true, render: (it) => money(it.basic_earned, "") },
              { key: "gross_earnings", header: "Gross", align: "right", render: (it) => money(it.gross_earnings, "") },
              { key: "paye", header: "PAYE", align: "right", hideOnMobile: true, render: (it) => money(it.paye, "") },
              { key: "total_deductions", header: "Deductions", align: "right", hideOnMobile: true, render: (it) => money(it.total_deductions, "") },
              { key: "net_salary", header: "Net", align: "right", className: "font-semibold", render: (it) => money(it.net_salary, "") },
              { key: "total_employer_contributions", header: "Employer", align: "right", hideOnMobile: true, render: (it) => money(it.total_employer_contributions, "") },
              { key: "payment_status", header: "Payment", hideOnMobile: true, render: (it) => <StatusBadge status={it.payment_status} /> },
            ]}
          />
          {items.data && <Pagination page={page} count={items.data.count} onPage={setPage} />}
        </Card>
      )}
      {tab === "payments" && <PaymentsTab period={period} />}
      {tab === "history" && (
        <Card title="Approval trail">
          <DataTable
            loading={history.isLoading}
            rows={history.data}
            columns={[
              { key: "timestamp", header: "When", render: (h: any) => dateTime(h.timestamp) },
              { key: "username", header: "User" },
              { key: "action", header: "Action", render: (h: any) => h.action.replace("_", " ") },
              { key: "change", header: "Status", render: (h: any) => <span className="flex items-center gap-1"><StatusBadge status={h.from_status} /> → <StatusBadge status={h.to_status} /></span> },
              { key: "comment", header: "Comment", render: (h: any) => <span className="whitespace-normal">{h.comment || "-"}</span> },
            ]}
          />
        </Card>
      )}
      <Disclaimer />

      <Modal open={itemId !== null} onClose={() => setItemId(null)} title="Payroll calculation breakdown" wide
        footer={itemId !== null && released ? <Link className="btn-secondary" to={`/payslips/${itemId}`}>Open payslip</Link> : undefined}>
        {itemId !== null && <ItemBreakdown itemId={itemId} />}
      </Modal>

      <ConfirmDialog
        open={!!action}
        title={cfg?.label || ""}
        message={cfg?.message}
        confirmLabel={cfg?.label}
        danger={cfg?.danger}
        busy={run.isPending}
        onConfirm={() => action && run.mutate(action)}
        onCancel={() => { setAction(null); setComment(""); }}
      >
        {cfg?.comment && (
          <div className="mt-3">
            <label className="label" htmlFor="wf-comment">Comment {cfg.comment === "required" && <span className="text-red-600">*</span>}</label>
            <textarea id="wf-comment" className="input" value={comment} onChange={(e) => setComment(e.target.value)} />
          </div>
        )}
      </ConfirmDialog>
    </div>
  );
}
