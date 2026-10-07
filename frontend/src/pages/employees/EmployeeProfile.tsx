import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { FileDown, Pencil, Plus } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { api, download, errorMessage, fieldErrors } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { DataTable } from "../../components/DataTable";
import { FormFields, toPayload, type FieldDef } from "../../components/Form";
import { useToast } from "../../components/Toast";
import { Alert, Card, Modal, PageHeader, PageLoader, Spinner, StatusBadge } from "../../components/ui";
import { date, humanize, money } from "../../lib/format";
import { useList } from "../../lib/hooks";
import type { Employee } from "../../lib/types";

function Detail({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-800">{value || "-"}</dd>
    </div>
  );
}

const SALARY_FIELDS: FieldDef[] = [
  { name: "basic_salary", label: "Basic salary (TZS)", type: "number", required: true, min: "0", step: "0.01" },
  { name: "effective_from", label: "Effective from", type: "date", required: true },
  { name: "reason", label: "Reason", colSpan: 2, placeholder: "e.g. Annual review 2027" },
];

function SalaryTab({ employee }: { employee: Employee }) {
  const { can } = useAuth();
  const notify = useToast();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<Record<string, any>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const history = useQuery({
    queryKey: ["salary-history", employee.id],
    queryFn: async () => (await api.get(`/employees/${employee.id}/salary-history/`)).data as any[],
  });
  const save = useMutation({
    mutationFn: () => api.post("/salaries/", { employee: employee.id, ...toPayload(SALARY_FIELDS, values) }),
    onSuccess: () => {
      notify("Salary record added. Previous record retained in history.");
      setOpen(false);
      qc.invalidateQueries({ queryKey: ["salary-history", employee.id] });
      qc.invalidateQueries({ queryKey: ["/employees/", String(employee.id)] });
    },
    onError: (e) => { setErrors(fieldErrors(e)); setError(errorMessage(e)); },
  });
  return (
    <Card
      title="Salary history"
      actions={can("salary.manage") && (
        <button className="btn-primary btn-sm" onClick={() => { setValues({}); setErrors({}); setError(""); setOpen(true); }}>
          <Plus className="h-4 w-4" /> New salary
        </button>
      )}
    >
      <p className="mb-3 text-xs text-slate-500">Salary records are never overwritten. A new record closes the previous one the day before it takes effect.</p>
      <DataTable
        loading={history.isLoading}
        rows={history.data}
        columns={[
          { key: "basic_salary", header: "Basic salary", align: "right", render: (r) => money(r.basic_salary) },
          { key: "effective_from", header: "From", render: (r) => date(r.effective_from) },
          { key: "effective_to", header: "To", render: (r) => (r.effective_to ? date(r.effective_to) : <span className="text-emerald-700">Current</span>) },
          { key: "reason", header: "Reason", render: (r) => r.reason || "-" },
          { key: "created_by_name", header: "Recorded by", hideOnMobile: true, render: (r) => r.created_by_name || "-" },
        ]}
      />
      <Modal open={open} onClose={() => setOpen(false)} title="New salary record" footer={
        <>
          <button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
          <button className="btn-primary" onClick={() => save.mutate()} disabled={save.isPending}>
            {save.isPending && <Spinner className="h-4 w-4 text-white" />} Save
          </button>
        </>
      }>
        {error && <div className="mb-3"><Alert>{error}</Alert></div>}
        <FormFields fields={SALARY_FIELDS} values={values} errors={errors} onChange={(n, v) => setValues((s) => ({ ...s, [n]: v }))} />
      </Modal>
    </Card>
  );
}

function ListTab({ title, endpoint, employee, columns }: { title: string; endpoint: string; employee: number; columns: any[] }) {
  const q = useList<any>(endpoint, { employee, page_size: 100 });
  return (
    <Card title={title}>
      {q.isError && <Alert>{errorMessage(q.error)}</Alert>}
      <DataTable loading={q.isLoading} rows={q.data?.results} columns={columns} />
    </Card>
  );
}

export default function EmployeeProfile() {
  const { id } = useParams();
  const { can } = useAuth();
  const [tab, setTab] = useState("overview");
  const q = useQuery({ queryKey: ["/employees/", id], queryFn: async () => (await api.get<Employee>(`/employees/${id}/`)).data });
  if (q.isLoading) return <PageLoader />;
  if (q.isError) return <Alert>{errorMessage(q.error)}</Alert>;
  const e = q.data!;
  const sensitive = "tin" in e;

  const tabs = [
    { key: "overview", label: "Overview", show: true },
    { key: "salary", label: "Salary", show: can("salary.view") },
    { key: "contracts", label: "Contracts", show: can("contracts.manage") },
    { key: "allowances", label: "Allowances", show: can("allowances.manage") },
    { key: "deductions", label: "Deductions", show: can("deductions.manage") },
    { key: "loans", label: "Loans", show: can("loans.view") },
    { key: "leave", label: "Leave", show: can("leave.view") },
  ].filter((t) => t.show);

  return (
    <div>
      <PageHeader
        title={e.full_name}
        subtitle={<span className="flex flex-wrap items-center gap-2">{e.employee_number} · {e.position_title || "—"} · {e.department_name} <StatusBadge status={e.status} /></span>}
        actions={
          <>
            {can("reports.view") && (
              <button className="btn-secondary" onClick={() => download(`/reports/employee-statement/?employee=${e.id}&export=pdf`, "statement.pdf")}>
                <FileDown className="h-4 w-4" /> Salary statement
              </button>
            )}
            {can("employees.manage") && <Link to={`/employees/${e.id}/edit`} className="btn-primary"><Pencil className="h-4 w-4" /> Edit</Link>}
          </>
        }
      />
      <div className="no-print mb-4 flex gap-1 overflow-x-auto border-b border-slate-200">
        {tabs.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={clsx("whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium",
              tab === t.key ? "border-brand-700 text-brand-800" : "border-transparent text-slate-500 hover:text-slate-800")}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Personal">
            <dl className="grid grid-cols-2 gap-4">
              <Detail label="Full name" value={e.full_name} />
              <Detail label="Gender" value={humanize(e.gender)} />
              <Detail label="Phone" value={e.phone} />
              <Detail label="Email" value={e.email} />
              {sensitive && <Detail label="Date of birth" value={date(e.date_of_birth)} />}
              {sensitive && <Detail label="NIDA" value={e.national_id} />}
              {sensitive && <Detail label="Address" value={e.address} />}
            </dl>
          </Card>
          <Card title="Employment">
            <dl className="grid grid-cols-2 gap-4">
              <Detail label="Department" value={e.department_name} />
              <Detail label="Job title" value={e.position_title} />
              <Detail label="Employment type" value={e.employment_type_name} />
              <Detail label="Status" value={<StatusBadge status={e.status} />} />
              <Detail label="Start date" value={date(e.employment_start_date)} />
              <Detail label="End date" value={date(e.employment_end_date)} />
              {e.current_basic_salary !== undefined && <Detail label="Current basic salary" value={money(e.current_basic_salary)} />}
            </dl>
          </Card>
          {sensitive ? (
            <>
              <Card title="Payment">
                <dl className="grid grid-cols-2 gap-4">
                  <Detail label="Method" value={humanize(e.payment_method)} />
                  <Detail label="Bank" value={e.bank_name} />
                  <Detail label="Branch" value={e.bank_branch} />
                  <Detail label="Account name" value={e.bank_account_name} />
                  <Detail label="Account number" value={e.bank_account_number} />
                  <Detail label="Mobile money" value={e.mobile_money_number} />
                </dl>
              </Card>
              <Card title="Tax & statutory">
                <dl className="grid grid-cols-2 gap-4">
                  <Detail label="TIN" value={e.tin} />
                  <Detail label="Tax resident" value={e.is_tax_resident ? "Yes" : "No"} />
                  <Detail label="Scheme" value={e.social_security_scheme} />
                  <Detail label="Social security no." value={e.social_security_number} />
                  <Detail label="WCF number" value={e.wcf_number} />
                  <Detail label="Emergency contact" value={e.emergency_contact_name ? `${e.emergency_contact_name} (${e.emergency_contact_relationship || "-"}) ${e.emergency_contact_phone || ""}` : "-"} />
                </dl>
              </Card>
            </>
          ) : (
            <Alert kind="info">Bank, tax and social-security details are hidden for your role.</Alert>
          )}
        </div>
      )}
      {tab === "salary" && <SalaryTab employee={e} />}
      {tab === "contracts" && (
        <ListTab title="Contracts" endpoint="/contracts/" employee={e.id} columns={[
          { key: "contract_number", header: "Contract no." },
          { key: "employment_type_name", header: "Type" },
          { key: "start_date", header: "Start", render: (r: any) => date(r.start_date) },
          { key: "end_date", header: "End", render: (r: any) => date(r.end_date) },
          { key: "basic_salary", header: "Basic", align: "right", render: (r: any) => money(r.basic_salary) },
          { key: "status", header: "Status", render: (r: any) => <StatusBadge status={r.status} /> },
          { key: "document", header: "Document", render: (r: any) => (r.document_url ? <button className="text-brand-600 hover:underline" onClick={() => download(r.document_url, "contract")}>Download</button> : "-") },
        ]} />
      )}
      {tab === "allowances" && (
        <ListTab title="Allowances" endpoint="/employee-allowances/" employee={e.id} columns={[
          { key: "allowance_name", header: "Allowance" },
          { key: "amount", header: "Amount / rate", align: "right", render: (r: any) => (r.amount ? money(r.amount) : r.rate ? `${Number(r.rate)}` : "Default") },
          { key: "is_taxable", header: "Taxable", render: (r: any) => (r.is_taxable ? "Yes" : "No") },
          { key: "is_recurring", header: "Recurring", render: (r: any) => (r.is_recurring ? "Yes" : "One-off") },
          { key: "effective_from", header: "From", render: (r: any) => date(r.effective_from) },
          { key: "effective_to", header: "To", render: (r: any) => date(r.effective_to) },
        ]} />
      )}
      {tab === "deductions" && (
        <ListTab title="Deductions" endpoint="/employee-deductions/" employee={e.id} columns={[
          { key: "deduction_name", header: "Deduction" },
          { key: "amount", header: "Amount / rate", align: "right", render: (r: any) => (r.amount ? money(r.amount) : r.rate ? `${Number(r.rate)}%` : "Default") },
          { key: "start_date", header: "Start", render: (r: any) => date(r.start_date) },
          { key: "end_date", header: "End", render: (r: any) => date(r.end_date) },
          { key: "is_active", header: "Active", render: (r: any) => (r.is_active ? "Yes" : "No") },
        ]} />
      )}
      {tab === "loans" && (
        <ListTab title="Loans & advances" endpoint="/loans/" employee={e.id} columns={[
          { key: "reference", header: "Reference" },
          { key: "loan_type", header: "Type", render: (r: any) => humanize(r.loan_type) },
          { key: "total_repayable", header: "Total", align: "right", render: (r: any) => money(r.total_repayable) },
          { key: "installment_amount", header: "Installment", align: "right", render: (r: any) => money(r.installment_amount) },
          { key: "remaining_balance", header: "Balance", align: "right", render: (r: any) => money(r.remaining_balance) },
          { key: "status", header: "Status", render: (r: any) => <StatusBadge status={r.status} /> },
        ]} />
      )}
      {tab === "leave" && (
        <ListTab title="Leave records" endpoint="/leave-records/" employee={e.id} columns={[
          { key: "leave_type_name", header: "Type" },
          { key: "start_date", header: "From", render: (r: any) => date(r.start_date) },
          { key: "end_date", header: "To", render: (r: any) => date(r.end_date) },
          { key: "days", header: "Days", align: "right" },
          { key: "status", header: "Status", render: (r: any) => <StatusBadge status={r.status} /> },
        ]} />
      )}
    </div>
  );
}
