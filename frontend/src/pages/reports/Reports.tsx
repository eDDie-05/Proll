import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { FileDown, FileSpreadsheet, Printer } from "lucide-react";
import { useState } from "react";
import { api, download, errorMessage } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { useToast } from "../../components/Toast";
import { Alert, Card, Disclaimer, EmptyState, PageHeader, PageLoader } from "../../components/ui";
import { date, money, num } from "../../lib/format";
import { employeeLabel, useOptions } from "../../lib/hooks";
import type { ReportData } from "../../lib/types";

interface ReportDef { key: string; title: string; needsPeriod: boolean; perm: string[]; employeeFilter?: boolean }

const REPORTS: ReportDef[] = [
  { key: "payroll-summary", title: "Payroll summary", needsPeriod: true, perm: ["reports.view", "reports.view_department"] },
  { key: "department", title: "Department report", needsPeriod: true, perm: ["reports.view", "reports.view_department"] },
  { key: "register", title: "Payroll register", needsPeriod: true, perm: ["reports.view"] },
  { key: "tax", title: "PAYE tax report", needsPeriod: true, perm: ["reports.view"] },
  { key: "contributions", title: "Statutory contributions", needsPeriod: true, perm: ["reports.view"] },
  { key: "deductions", title: "Deductions report", needsPeriod: true, perm: ["reports.view"] },
  { key: "payments", title: "Payment report", needsPeriod: true, perm: ["reports.view"] },
  { key: "history", title: "Payroll history", needsPeriod: false, perm: ["reports.view", "reports.view_department"] },
  { key: "employee-salary", title: "Employee salary report", needsPeriod: false, perm: ["reports.view"], employeeFilter: true },
];

function cell(v: any, type: string) {
  if (v === null || v === undefined || v === "") return "-";
  if (type === "money") return money(v, "");
  if (type === "int") return num(v);
  if (type === "date") return date(v);
  return String(v);
}

export function ReportView({ reportKey, title, needsPeriod, employeeFilter }: { reportKey: string; title: string; needsPeriod: boolean; employeeFilter?: boolean }) {
  const { can } = useAuth();
  const notify = useToast();
  const [period, setPeriod] = useState("");
  const [department, setDepartment] = useState("");
  const [employee, setEmployee] = useState("");
  const [year, setYear] = useState("");
  const allDepts = can("reports.view");
  const periods = useOptions("/payroll-periods/", (p) => `${p.name} (${p.status})`, needsPeriod);
  const depts = useOptions("/departments/", (d) => d.name, allDepts);
  const employees = useOptions("/employees/", employeeLabel, !!employeeFilter);
  const params: Record<string, string> = {};
  if (period) params.period = period;
  if (department) params.department = department;
  if (employee) params.employee = employee;
  if (year) params.year = year;
  const ready = !needsPeriod || !!period;
  const q = useQuery({
    queryKey: ["report", reportKey, params],
    enabled: ready,
    queryFn: async () => (await api.get<ReportData>(`/reports/${reportKey}/`, { params })).data,
  });
  const exportAs = (fmt: string) => {
    const qs = new URLSearchParams({ ...params, export: fmt }).toString();
    download(`/reports/${reportKey}/?${qs}`, `${reportKey}.${fmt}`).catch((e) => notify(errorMessage(e), "error"));
  };
  const r = q.data;
  const canExport = can("reports.export", "reports.view_department");

  return (
    <div className="space-y-4">
      <PageHeader
        title={title}
        subtitle={r?.subtitle}
        actions={r && (
          <>
            <button className="btn-secondary" onClick={() => window.print()}><Printer className="h-4 w-4" /> Print</button>
            {canExport && (
              <>
                <button className="btn-secondary" onClick={() => exportAs("csv")}><FileDown className="h-4 w-4" /> CSV</button>
                <button className="btn-secondary" onClick={() => exportAs("xlsx")}><FileSpreadsheet className="h-4 w-4" /> Excel</button>
                <button className="btn-primary" onClick={() => exportAs("pdf")}><FileDown className="h-4 w-4" /> PDF</button>
              </>
            )}
          </>
        )}
      />
      <div className="no-print flex flex-col gap-2 sm:flex-row">
        {needsPeriod && (
          <select className="input sm:w-64" value={period} onChange={(e) => setPeriod(e.target.value)} aria-label="Payroll period">
            <option value="">Select payroll period…</option>
            {periods.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
        )}
        {allDepts && reportKey !== "history" && (
          <select className="input sm:w-56" value={department} onChange={(e) => setDepartment(e.target.value)} aria-label="Department">
            <option value="">All departments</option>
            {depts.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
          </select>
        )}
        {employeeFilter && (
          <select className="input sm:w-72" value={employee} onChange={(e) => setEmployee(e.target.value)} aria-label="Employee">
            <option value="">All employees</option>
            {employees.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
          </select>
        )}
        {reportKey === "history" && (
          <input className="input sm:w-32" type="number" placeholder="Year" value={year} onChange={(e) => setYear(e.target.value)} aria-label="Year" />
        )}
      </div>
      {!ready && <Card><EmptyState message="Select a payroll period to view this report." /></Card>}
      {q.isLoading && ready && <PageLoader />}
      {q.isError && <Alert>{errorMessage(q.error)}</Alert>}
      {r && (
        <>
          {r.summary && (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
              {r.summary.map((s) => (
                <div key={s.label} className="card p-3">
                  <p className="text-xs text-slate-500">{s.label}</p>
                  <p className="text-base font-bold text-brand-800">{typeof s.value === "number" ? num(s.value) : money(s.value)}</p>
                </div>
              ))}
            </div>
          )}
          <Card>
            {r.rows.length === 0 ? <EmptyState /> : (
              <div className="-mx-4 overflow-x-auto sm:mx-0">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <thead className="bg-brand-700">
                    <tr>{r.columns.map((c) => (
                      <th key={c.key} className={clsx("th text-white", (c.type === "money" || c.type === "int") && "text-right")}>{c.label}</th>
                    ))}</tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {r.rows.map((row, i) => (
                      <tr key={i} className="odd:bg-white even:bg-slate-50">
                        {r.columns.map((c) => (
                          <td key={c.key} className={clsx("td", (c.type === "money" || c.type === "int") && "text-right tabular-nums")}>{cell(row[c.key], c.type)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                  {r.totals && (
                    <tfoot className="bg-amber-50 font-semibold">
                      <tr>{r.columns.map((c) => (
                        <td key={c.key} className={clsx("td", (c.type === "money" || c.type === "int") && "text-right tabular-nums")}>{r.totals![c.key] !== undefined ? cell(r.totals![c.key], c.type) : ""}</td>
                      ))}</tr>
                    </tfoot>
                  )}
                </table>
              </div>
            )}
          </Card>
          <Disclaimer />
        </>
      )}
    </div>
  );
}

export default function Reports() {
  const { can } = useAuth();
  const available = REPORTS.filter((r) => can(...r.perm));
  const [active, setActive] = useState(available[0]?.key);
  const def = available.find((r) => r.key === active);
  return (
    <div className="grid gap-4 lg:grid-cols-[220px_1fr]">
      <nav className="no-print card h-fit p-2" aria-label="Reports">
        {available.map((r) => (
          <button key={r.key} onClick={() => setActive(r.key)}
            className={clsx("block w-full rounded-md px-3 py-2 text-left text-sm", active === r.key ? "bg-brand-700 text-white" : "text-slate-700 hover:bg-slate-100")}>
            {r.title}
          </button>
        ))}
      </nav>
      <div className="min-w-0">{def && <ReportView key={def.key} reportKey={def.key} title={def.title} needsPeriod={def.needsPeriod} employeeFilter={def.employeeFilter} />}</div>
    </div>
  );
}
