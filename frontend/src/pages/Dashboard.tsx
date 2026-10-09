import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, errorMessage } from "../api/client";
import { DataTable } from "../components/DataTable";
import { Alert, Card, Disclaimer, PageHeader, PageLoader, Stat, StatusBadge } from "../components/ui";
import { compact, money } from "../lib/format";

// Validated categorical palette (scripts/validate_palette.js): blue, amber, teal — fixed order.
const C1 = "#3B6AA8";
const C2 = "#C98A00";
const C3 = "#0F8A7A";
const GRID = "#E2E8F0";
const AXIS = { fontSize: 11, fill: "#64748B" };

interface DashboardData {
  total_employees: number;
  pending_approvals: number;
  current_period: { id: number; name: string; status: string; summary: Record<string, string> | null } | null;
  payroll_by_month: { period: string; gross: string; net: string; deductions: string; employer: string; cost: string; employees: number }[];
  payroll_by_department: { department: string; gross: string; net: string; employees: number }[];
  employees_by_department: { department: string; count: number }[];
  salary_distribution: { band: string; count: number }[];
  recent_periods: { id: number; name: string; status: string; start_date: string; net: string | null }[];
}

const toNum = <T extends Record<string, any>>(rows: T[], keys: string[]) =>
  rows.map((r) => ({ ...r, ...Object.fromEntries(keys.map((k) => [k, Number(r[k])])) }));

const moneyTip = (v: any) => money(v);

export default function Dashboard() {
  const q = useQuery({ queryKey: ["dashboard"], queryFn: async () => (await api.get<DashboardData>("/dashboard/")).data });
  if (q.isLoading) return <PageLoader />;
  if (q.isError) return <Alert>{errorMessage(q.error)}</Alert>;
  const d = q.data!;
  const s = d.current_period?.summary;
  const monthly = toNum(d.payroll_by_month, ["gross", "net", "deductions", "employer", "cost"]);
  const byDept = toNum(d.payroll_by_department, ["gross", "net"]);

  return (
    <div className="space-y-5">
      <PageHeader title="Dashboard" subtitle="Payroll overview for Bravado Company Ltd" />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Active employees" value={d.total_employees} />
        <Stat
          label="Current payroll"
          value={d.current_period ? d.current_period.name : "—"}
          hint={d.current_period ? <StatusBadge status={d.current_period.status} /> : "No periods yet"}
        />
        <Stat label="Pending approvals" value={d.pending_approvals} accent={d.pending_approvals > 0} />
        <Stat label="Employer contributions" value={s ? money(s.employer) : "—"} />
        <Stat label="Gross payroll" value={s ? money(s.gross) : "—"} />
        <Stat label="Total deductions" value={s ? money(s.deductions) : "—"} />
        <Stat label="Net payroll" value={s ? money(s.net) : "—"} accent />
        <Stat label="Total employer cost" value={s ? money(s.cost) : "—"} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Payroll by month">
          {monthly.length ? (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={monthly} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis dataKey="period" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} />
                <YAxis tick={AXIS} tickFormatter={compact} tickLine={false} axisLine={false} width={48} />
                <Tooltip formatter={moneyTip} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="gross" name="Gross" stroke={C1} strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} />
                <Line type="monotone" dataKey="net" name="Net" stroke={C2} strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} />
                <Line type="monotone" dataKey="deductions" name="Deductions" stroke={C3} strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          ) : <p className="py-10 text-center text-sm text-slate-400">No calculated payroll yet.</p>}
        </Card>

        <Card title={`Payroll by department${d.current_period ? ` — ${d.current_period.name}` : ""}`}>
          {byDept.length ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={byDept} margin={{ top: 8, right: 12, left: 0, bottom: 0 }} barGap={2}>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis dataKey="department" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} interval={0} angle={-15} textAnchor="end" height={50} />
                <YAxis tick={AXIS} tickFormatter={compact} tickLine={false} axisLine={false} width={48} />
                <Tooltip formatter={moneyTip} cursor={{ fill: "#F1F5F9" }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="gross" name="Gross" fill={C1} radius={[4, 4, 0, 0]} maxBarSize={28} />
                <Bar dataKey="net" name="Net" fill={C2} radius={[4, 4, 0, 0]} maxBarSize={28} />
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="py-10 text-center text-sm text-slate-400">No data for the current period.</p>}
        </Card>

        <Card title="Payroll cost trend (employer cost)">
          {monthly.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={monthly} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={GRID} vertical={false} />
                <XAxis dataKey="period" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} />
                <YAxis tick={AXIS} tickFormatter={compact} tickLine={false} axisLine={false} width={48} />
                <Tooltip formatter={moneyTip} />
                <Area type="monotone" dataKey="cost" name="Employer cost" stroke={C1} strokeWidth={2} fill={C1} fillOpacity={0.15} />
              </AreaChart>
            </ResponsiveContainer>
          ) : <p className="py-10 text-center text-sm text-slate-400">No trend data yet.</p>}
        </Card>

        <div className="grid gap-4 sm:grid-cols-2">
          <Card title="Employees by department">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={d.employees_by_department} layout="vertical" margin={{ left: 8, right: 16 }}>
                <XAxis type="number" allowDecimals={false} tick={AXIS} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="department" tick={AXIS} width={90} axisLine={false} tickLine={false} />
                <Tooltip cursor={{ fill: "#F1F5F9" }} />
                <Bar dataKey="count" name="Employees" fill={C1} radius={[0, 4, 4, 0]} maxBarSize={18} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
          <Card title="Salary distribution (basic)">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={d.salary_distribution} margin={{ right: 8 }}>
                <XAxis dataKey="band" tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} />
                <YAxis allowDecimals={false} tick={AXIS} axisLine={false} tickLine={false} width={28} />
                <Tooltip cursor={{ fill: "#F1F5F9" }} />
                <Bar dataKey="count" name="Employees" fill={C3} radius={[4, 4, 0, 0]} maxBarSize={32} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </div>
      </div>

      <Card title="Recent payroll periods" actions={<Link to="/payroll" className="btn-secondary btn-sm">View all</Link>}>
        <DataTable
          rows={d.recent_periods}
          columns={[
            { key: "name", header: "Period", render: (r) => <Link className="font-medium text-brand-700 hover:underline" to={`/payroll/${r.id}`}>{r.name}</Link> },
            { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
            { key: "net", header: "Net payroll", align: "right", render: (r) => money(r.net) },
          ]}
          empty="No payroll periods yet."
        />
      </Card>
      <Disclaimer />
    </div>
  );
}
