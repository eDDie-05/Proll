import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { api, errorMessage } from "../../api/client";
import { Alert, PageLoader } from "../../components/ui";
import { money } from "../../lib/format";
import type { PayrollItemDetail, PayrollLine } from "../../lib/types";

function Row({ label, value, bold, hint }: { label: ReactNode; value: string; bold?: boolean; hint?: ReactNode }) {
  return (
    <div className={`flex items-start justify-between gap-4 py-1.5 text-sm ${bold ? "border-t border-slate-300 font-semibold" : ""}`}>
      <div>
        <span>{label}</span>
        {hint && <div className="text-xs text-slate-500">{hint}</div>}
      </div>
      <span className="whitespace-nowrap tabular-nums">{money(value)}</span>
    </div>
  );
}

function lineHint(l: PayrollLine): ReactNode {
  const d = l.detail || {};
  if (l.source_type === "STATUTORY") {
    const parts = [`${d.method === "PROGRESSIVE" ? "Brackets" : d.rate ? d.rate + "%" : "Fixed"} on ${d.base_type?.toLowerCase().replace(/_/g, " ")} ${money(d.applied_base, "")}`];
    parts.push(`rule v${l.statutory_rule_version}`);
    if (d.verification_status !== "VERIFIED") parts.push("⚠ unverified rule");
    return parts.join(" · ");
  }
  if (l.code === "BASIC" && d.segments?.length) {
    return d.segments.map((s: any) => `${money(s.monthly_basic, "")} × ${s.days}d`).join(" + ") + (d.proration_factor !== "1.000000" ? ` · factor ${Number(d.proration_factor).toFixed(4)}` : "");
  }
  if (l.source_type === "LEAVE") return `${d.days} day(s) × ${money(d.daily_rate, "")}`;
  if (l.source_type === "LOAN") return `Balance before: ${money(d.balance_before, "")}`;
  if (l.source_type === "ADJUSTMENT") return d.reason;
  const flags = [l.is_taxable ? "taxable" : l.category === "EARNING" ? "non-taxable" : "", l.reduces_taxable_income ? "pre-tax" : ""].filter(Boolean);
  return flags.join(" · ");
}

/** Full, auditable calculation breakdown of one employee's pay. */
export function ItemBreakdown({ itemId, url }: { itemId: number; url?: string }) {
  const q = useQuery({
    queryKey: ["payroll-item", itemId, url],
    queryFn: async () => (await api.get<PayrollItemDetail>(url || `/payroll-items/${itemId}/`)).data,
  });
  if (q.isLoading) return <PageLoader />;
  if (q.isError) return <Alert>{errorMessage(q.error)}</Alert>;
  const it = q.data!;
  const earnings = it.lines.filter((l) => l.category === "EARNING");
  const deductions = it.lines.filter((l) => l.category === "DEDUCTION");
  const employer = it.lines.filter((l) => l.category === "EMPLOYER");
  const tax = deductions.filter((l) => l.sub_category === "TAX");
  const statutory = deductions.filter((l) => l.is_statutory && l.sub_category !== "TAX");
  const other = deductions.filter((l) => !l.is_statutory);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
        <div><span className="text-slate-500">Employee</span><div className="font-medium">{it.employee_name}</div></div>
        <div><span className="text-slate-500">ID</span><div className="font-medium">{it.employee_number}</div></div>
        <div><span className="text-slate-500">Department</span><div className="font-medium">{it.department_name}</div></div>
        <div><span className="text-slate-500">Days employed</span><div className="font-medium">{Number(it.days_employed)} / {Number(it.days_in_period)}</div></div>
      </div>
      {it.warnings?.length > 0 && <Alert kind="warning">{it.warnings.join(" ")}</Alert>}
      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-brand-700">Earnings</h3>
          {earnings.map((l) => <Row key={l.id} label={l.name} value={l.amount} hint={lineHint(l)} />)}
          <Row label="Gross earnings" value={it.gross_earnings} bold />
          <div className="mt-3 rounded bg-slate-50 p-2 text-xs text-slate-600">
            Taxable income: <strong>{money(it.taxable_income)}</strong> · Social-security base: <strong>{money(it.social_security_base)}</strong>
          </div>
        </div>
        <div>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-brand-700">Employee deductions</h3>
          {[...tax, ...statutory, ...other].map((l) => <Row key={l.id} label={l.name} value={l.amount} hint={lineHint(l)} />)}
          <Row label="Total deductions" value={it.total_deductions} bold />
        </div>
      </div>
      <div className="flex items-center justify-between rounded-lg bg-brand-700 px-4 py-3 text-white">
        <span className="font-semibold">NET SALARY</span>
        <span className="text-lg font-bold tabular-nums">{money(it.net_salary)}</span>
      </div>
      <div>
        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-brand-700">Employer contributions (not deducted from pay)</h3>
        {employer.map((l) => <Row key={l.id} label={l.name} value={l.amount} hint={lineHint(l)} />)}
        <Row label="Employer total cost (gross + contributions)" value={it.employer_total_cost} bold />
      </div>
    </div>
  );
}
