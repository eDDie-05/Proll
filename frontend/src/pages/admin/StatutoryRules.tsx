import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CopyPlus, Pencil, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { useState } from "react";
import { api, errorMessage, fieldErrors } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { DataTable } from "../../components/DataTable";
import { FormFields, toPayload, type FieldDef } from "../../components/Form";
import { useToast } from "../../components/Toast";
import { Alert, Card, Disclaimer, Modal, PageHeader, Spinner, StatusBadge } from "../../components/ui";
import { date, humanize, money } from "../../lib/format";

interface Bracket { lower_bound: string; upper_bound: string | null; rate: string }

const FIELDS: FieldDef[] = [
  { name: "code", label: "Code", required: true, help: "Shared by all versions, e.g. PAYE_RESIDENT" },
  { name: "name", label: "Name", required: true },
  { name: "category", label: "Category", type: "select", required: true, options: [
    { value: "TAX", label: "Income tax (PAYE)" }, { value: "SOCIAL_SECURITY", label: "Social security" }, { value: "LEVY", label: "Employer levy" }, { value: "OTHER", label: "Other" }] },
  { name: "party", label: "Borne by", type: "select", required: true, options: [{ value: "EMPLOYEE", label: "Employee (deduction)" }, { value: "EMPLOYER", label: "Employer (contribution)" }] },
  { name: "method", label: "Method", type: "select", required: true, options: [
    { value: "PROGRESSIVE", label: "Progressive brackets" }, { value: "FLAT_RATE", label: "Flat % of base" }, { value: "FIXED_AMOUNT", label: "Fixed amount" }] },
  { name: "base", label: "Base", type: "select", required: true, options: [
    { value: "GROSS", label: "Gross earnings" }, { value: "BASIC", label: "Basic salary" }, { value: "SOCIAL_SECURITY_BASE", label: "Social-security earnings" },
    { value: "TAXABLE_INCOME", label: "Taxable income" }, { value: "CASH_EMOLUMENTS", label: "Gross cash emoluments" }] },
  { name: "rate", label: "Rate (%)", type: "number", step: "0.0001", min: "0", showIf: (v) => v.method === "FLAT_RATE" },
  { name: "fixed_amount", label: "Fixed amount (TZS)", type: "number", min: "0", showIf: (v) => v.method === "FIXED_AMOUNT" },
  { name: "base_ceiling", label: "Base ceiling / cap (TZS)", type: "number", min: "0" },
  { name: "max_amount", label: "Maximum amount per period", type: "number", min: "0" },
  { name: "min_amount", label: "Minimum amount per period", type: "number", min: "0" },
  { name: "residency", label: "Applies to", type: "select", options: [{ value: "ALL", label: "All employees" }, { value: "RESIDENT", label: "Tax residents" }, { value: "NON_RESIDENT", label: "Non-residents" }] },
  { name: "applies_to_schemes", label: "Schemes (JSON list, [] = all)", type: "json", help: 'e.g. ["NSSF"]' },
  { name: "min_employee_count", label: "Minimum employee count", type: "number", min: "0", help: "e.g. levy only for 10+ employees" },
  { name: "calculation_order", label: "Calculation order", type: "number", min: "0" },
  { name: "reduces_taxable_income", label: "Deducted before PAYE (employee contributions only)", type: "checkbox" },
  { name: "effective_from", label: "Effective from", type: "date", required: true },
  { name: "effective_to", label: "Effective to", type: "date" },
  { name: "is_active", label: "Active", type: "checkbox" },
  { name: "source_name", label: "Source (authority)", colSpan: 2 },
  { name: "source_url", label: "Source URL", colSpan: 2 },
  { name: "source_reference", label: "Legal reference (Act/section/notice)", colSpan: 2 },
  { name: "source_retrieved_on", label: "Source retrieved on", type: "date" },
  { name: "description", label: "Description", type: "textarea", colSpan: 2 },
];

function BracketEditor({ brackets, onChange, disabled }: { brackets: Bracket[]; onChange: (b: Bracket[]) => void; disabled?: boolean }) {
  const set = (i: number, k: keyof Bracket, v: string) => onChange(brackets.map((b, j) => (j === i ? { ...b, [k]: v === "" && k === "upper_bound" ? null : v } : b)));
  return (
    <div className="mt-4">
      <h3 className="mb-2 text-sm font-semibold text-slate-700">Tax brackets (marginal rates)</h3>
      <p className="mb-2 text-xs text-slate-500">Rate applies to the portion of income between the bounds. First bracket starts at 0; last has no upper bound.</p>
      {brackets.map((b, i) => (
        <div key={i} className="mb-2 grid grid-cols-[1fr_1fr_90px_auto] gap-2">
          <input className="input" aria-label="Lower bound" type="number" value={b.lower_bound} disabled={disabled} onChange={(e) => set(i, "lower_bound", e.target.value)} />
          <input className="input" aria-label="Upper bound" type="number" placeholder="No limit" value={b.upper_bound ?? ""} disabled={disabled} onChange={(e) => set(i, "upper_bound", e.target.value)} />
          <input className="input" aria-label="Rate %" type="number" step="0.01" value={b.rate} disabled={disabled} onChange={(e) => set(i, "rate", e.target.value)} />
          <button className="btn-secondary btn-sm" disabled={disabled} aria-label="Remove bracket" onClick={() => onChange(brackets.filter((_, j) => j !== i))}><Trash2 className="h-3.5 w-3.5" /></button>
        </div>
      ))}
      {!disabled && (
        <button className="btn-secondary btn-sm" onClick={() => {
          const last = brackets[brackets.length - 1];
          onChange([...brackets, { lower_bound: last?.upper_bound ?? "0", upper_bound: null, rate: "0" }]);
        }}><Plus className="h-3.5 w-3.5" /> Add bracket</button>
      )}
    </div>
  );
}

export default function StatutoryRules() {
  const { can } = useAuth();
  const notify = useToast();
  const qc = useQueryClient();
  const canManage = can("statutory.manage");
  const rules = useQuery({ queryKey: ["/statutory-rules/"], queryFn: async () => (await api.get("/statutory-rules/")).data as any[] });
  const [editing, setEditing] = useState<any | null>(null);
  const [values, setValues] = useState<Record<string, any>>({});
  const [brackets, setBrackets] = useState<Bracket[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState("");
  const [verifying, setVerifying] = useState<any | null>(null);
  const [notes, setNotes] = useState("");
  const [versioning, setVersioning] = useState<any | null>(null);
  const [newFrom, setNewFrom] = useState("");
  const [preview, setPreview] = useState<{ rule: any; base: string; result?: any } | null>(null);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["/statutory-rules/"] });
  const open = (r: any | null) => {
    setEditing(r || {});
    const v = r ? { ...r, applies_to_schemes: JSON.stringify(r.applies_to_schemes) } : { method: "FLAT_RATE", party: "EMPLOYEE", category: "SOCIAL_SECURITY", base: "GROSS", residency: "ALL", is_active: true, calculation_order: 100, applies_to_schemes: "[]" };
    setValues(v);
    setBrackets(r?.brackets || [{ lower_bound: "0", upper_bound: null, rate: "0" }]);
    setErrors({});
    setFormError("");
  };
  const save = useMutation({
    mutationFn: async () => {
      const payload: any = toPayload(FIELDS, values);
      if (values.method === "PROGRESSIVE") payload.brackets = brackets;
      if (editing?.is_used) {
        // Only provenance / end-date fields may change on a used rule.
        const allowed = ["effective_to", "is_active", "source_name", "source_url", "source_reference", "source_retrieved_on", "description"];
        for (const k of Object.keys(payload)) if (!allowed.includes(k)) delete payload[k];
      }
      return editing?.id ? api.patch(`/statutory-rules/${editing.id}/`, payload) : api.post("/statutory-rules/", payload);
    },
    onSuccess: () => { notify("Statutory rule saved (unverified until reviewed)."); setEditing(null); invalidate(); },
    onError: (e) => { setErrors(fieldErrors(e)); setFormError(errorMessage(e)); },
  });
  const verify = useMutation({
    mutationFn: () => api.post(`/statutory-rules/${verifying.id}/verify/`, { verification_notes: notes }),
    onSuccess: () => { notify("Rule marked as verified."); setVerifying(null); setNotes(""); invalidate(); },
    onError: (e) => notify(errorMessage(e), "error"),
  });
  const newVersion = useMutation({
    mutationFn: () => api.post(`/statutory-rules/${versioning.id}/new-version/`, { effective_from: newFrom }),
    onSuccess: (r) => { notify(`Version ${r.data.version} created — edit its rates, then verify it.`); setVersioning(null); invalidate(); open(r.data); },
    onError: (e) => notify(errorMessage(e), "error"),
  });
  const runPreview = useMutation({
    mutationFn: () => api.post(`/statutory-rules/${preview!.rule.id}/preview/`, { base_amount: preview!.base }),
    onSuccess: (r) => setPreview((p) => p && { ...p, result: r.data }),
    onError: (e) => notify(errorMessage(e), "error"),
  });

  return (
    <div className="space-y-4">
      <PageHeader
        title="Statutory rules"
        subtitle="Versioned, effective-dated PAYE, social security and employer levy rules. Payroll uses the version in force on the period end date."
        actions={canManage && <button className="btn-primary" onClick={() => open(null)}><Plus className="h-4 w-4" /> New rule</button>}
      />
      <Disclaimer />
      <Alert kind="info">
        Rates must be verified against current official sources before use. Each rule records its source, effective dates and verification status.
        Payroll approval is blocked while unverified rules are used (configurable in Company settings).
      </Alert>
      <Card>
        {rules.isError && <Alert>{errorMessage(rules.error)}</Alert>}
        <DataTable
          loading={rules.isLoading}
          rows={rules.data}
          columns={[
            { key: "code", header: "Code", render: (r) => <span className="font-medium">{r.code} <span className="text-xs text-slate-400">v{r.version}</span></span> },
            { key: "name", header: "Name", hideOnMobile: true },
            { key: "party", header: "Party", render: (r) => humanize(r.party) },
            { key: "rate", header: "Rate", render: (r) => (r.method === "PROGRESSIVE" ? `${r.brackets.length} brackets` : r.method === "FLAT_RATE" ? `${Number(r.rate)}%` : money(r.fixed_amount)) },
            { key: "base", header: "Base", hideOnMobile: true, render: (r) => humanize(r.base) },
            { key: "effective", header: "Effective", render: (r) => `${date(r.effective_from)} → ${r.effective_to ? date(r.effective_to) : "open"}` },
            { key: "verification_status", header: "Verification", render: (r) => <span title={r.verification_notes}><StatusBadge status={r.verification_status} /></span> },
            { key: "is_active", header: "Active", hideOnMobile: true, render: (r) => (r.is_active ? "Yes" : "No") },
            {
              key: "actions", header: "", align: "right", render: (r) => (
                <div className="flex justify-end gap-1">
                  <button className="btn-secondary btn-sm" onClick={() => setPreview({ rule: r, base: "1000000" })}>Test</button>
                  {can("statutory.verify") && r.verification_status !== "VERIFIED" && (
                    <button className="btn-success btn-sm" onClick={() => { setVerifying(r); setNotes(""); }}><ShieldCheck className="h-3.5 w-3.5" /> Verify</button>
                  )}
                  {canManage && <button className="btn-secondary btn-sm" aria-label="New version" title="New version" onClick={() => { setVersioning(r); setNewFrom(""); }}><CopyPlus className="h-3.5 w-3.5" /></button>}
                  {canManage && <button className="btn-secondary btn-sm" aria-label="Edit" onClick={() => open(r)}><Pencil className="h-3.5 w-3.5" /></button>}
                </div>
              ),
            },
          ]}
        />
      </Card>

      <Modal open={!!editing} onClose={() => setEditing(null)} title={editing?.id ? `Edit ${editing.code} v${editing.version}` : "New statutory rule"} wide footer={
        <>
          <button className="btn-secondary" onClick={() => setEditing(null)}>Cancel</button>
          <button className="btn-primary" disabled={save.isPending} onClick={() => save.mutate()}>{save.isPending && <Spinner className="h-4 w-4 text-white" />} Save</button>
        </>
      }>
        {formError && <div className="mb-3"><Alert>{formError}</Alert></div>}
        {editing?.is_used && <div className="mb-3"><Alert kind="warning">This version has been used in payroll, so its calculation fields are locked. Create a new version to change rates.</Alert></div>}
        {editing?.verification_notes && <div className="mb-3"><Alert kind="info"><strong>Verification notes:</strong> {editing.verification_notes}</Alert></div>}
        <FormFields fields={FIELDS.map((f) => ({ ...f, disabled: editing?.is_used && !["effective_to", "is_active", "source_name", "source_url", "source_reference", "source_retrieved_on", "description"].includes(f.name) }))}
          values={values} errors={errors} onChange={(n, v) => setValues((s) => ({ ...s, [n]: v }))} />
        {values.method === "PROGRESSIVE" && <BracketEditor brackets={brackets} onChange={setBrackets} disabled={editing?.is_used} />}
        {errors.brackets && <p className="mt-1 text-xs text-red-600">{errors.brackets}</p>}
      </Modal>

      <Modal open={!!verifying} onClose={() => setVerifying(null)} title={`Verify ${verifying?.code} v${verifying?.version}`} footer={
        <>
          <button className="btn-secondary" onClick={() => setVerifying(null)}>Cancel</button>
          <button className="btn-success" disabled={!notes || verify.isPending} onClick={() => verify.mutate()}>Mark verified</button>
        </>
      }>
        <p className="mb-2 text-sm text-slate-700">Confirm you have checked this rule's rates, bases and effective dates against the current official source.</p>
        {verifying?.source_url && <p className="mb-2 text-sm">Source: <a className="text-brand-600 underline" href={verifying.source_url} target="_blank" rel="noreferrer">{verifying.source_name || verifying.source_url}</a></p>}
        {verifying?.verification_notes && <Alert kind="warning">{verifying.verification_notes}</Alert>}
        <label className="label mt-3" htmlFor="vnotes">Verification notes (required)</label>
        <textarea id="vnotes" className="input" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="e.g. Checked against TRA PAYE table published ... on ..." />
      </Modal>

      <Modal open={!!versioning} onClose={() => setVersioning(null)} title={`New version of ${versioning?.code}`} footer={
        <>
          <button className="btn-secondary" onClick={() => setVersioning(null)}>Cancel</button>
          <button className="btn-primary" disabled={!newFrom || newVersion.isPending} onClick={() => newVersion.mutate()}>Create version</button>
        </>
      }>
        <p className="mb-3 text-sm text-slate-700">The current version is end-dated the day before. Historical payroll keeps using the version that was in force.</p>
        <label className="label" htmlFor="nvf">New version effective from</label>
        <input id="nvf" type="date" className="input" value={newFrom} onChange={(e) => setNewFrom(e.target.value)} />
      </Modal>

      <Modal open={!!preview} onClose={() => setPreview(null)} title={`Test ${preview?.rule.code}`}>
        {preview && (
          <div className="space-y-3">
            <div className="flex gap-2">
              <input className="input" type="number" aria-label="Base amount" value={preview.base} onChange={(e) => setPreview({ ...preview, base: e.target.value, result: undefined })} />
              <button className="btn-primary" onClick={() => runPreview.mutate()}>Calculate</button>
            </div>
            {preview.result && (
              <div className="rounded-md bg-slate-50 p-3 text-sm">
                <p className="font-semibold">Result: {money(preview.result.amount)}</p>
                {preview.result.detail.bands && (
                  <table className="mt-2 w-full text-xs">
                    <thead><tr><th className="text-left">Band</th><th className="text-right">Rate</th><th className="text-right">Portion</th><th className="text-right">Tax</th></tr></thead>
                    <tbody>{preview.result.detail.bands.map((b: any, i: number) => (
                      <tr key={i}><td>{money(b.lower, "")} – {b.upper ? money(b.upper, "") : "∞"}</td><td className="text-right">{b.rate}%</td><td className="text-right">{money(b.taxable_portion, "")}</td><td className="text-right">{money(b.tax, "")}</td></tr>
                    ))}</tbody>
                  </table>
                )}
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
