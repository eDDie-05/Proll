import clsx from "clsx";
import {
  BadgeDollarSign, BarChart3, Building2, CalendarDays, ClipboardList, FileText, HandCoins, History, Landmark,
  LayoutDashboard, LogOut, Menu, MinusCircle, PlusCircle, Receipt, Scale, Settings, ShieldCheck, User, Users, Wallet, X,
} from "lucide-react";
import { Suspense, useState, type ComponentType } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { PageLoader } from "./ui";

interface NavItem { to: string; label: string; icon: ComponentType<{ className?: string }>; perms: string[] }
interface NavGroup { title: string; items: NavItem[] }

const PAYROLL_VIEW = ["payroll.view", "payroll.view_approved", "payroll.approve", "payroll.prepare"];

export const NAV: NavGroup[] = [
  {
    title: "Overview",
    items: [{ to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, perms: ["reports.view", "reports.view_department", "payroll.view", "payroll.prepare"] }],
  },
  {
    title: "People",
    items: [
      { to: "/employees", label: "Employees", icon: Users, perms: ["employees.view"] },
      { to: "/contracts", label: "Contracts", icon: FileText, perms: ["contracts.manage"] },
      { to: "/salaries", label: "Salary history", icon: BadgeDollarSign, perms: ["salary.view"] },
      { to: "/leave", label: "Leave", icon: CalendarDays, perms: ["leave.view"] },
    ],
  },
  {
    title: "Payroll",
    items: [
      { to: "/payroll", label: "Payroll periods", icon: Wallet, perms: PAYROLL_VIEW },
      { to: "/payroll/history", label: "Payroll history", icon: History, perms: ["reports.view", "reports.view_department"] },
      { to: "/adjustments", label: "Adjustments", icon: Scale, perms: ["payroll.adjust", "payroll.view"] },
      { to: "/payments", label: "Payments", icon: Landmark, perms: ["payments.view"] },
      { to: "/payslips", label: "Payslips", icon: Receipt, perms: ["payslips.generate", "payroll.view"] },
    ],
  },
  {
    title: "Compensation",
    items: [
      { to: "/allowance-types", label: "Allowance types", icon: PlusCircle, perms: ["allowances.manage"] },
      { to: "/employee-allowances", label: "Employee allowances", icon: PlusCircle, perms: ["allowances.manage"] },
      { to: "/deduction-types", label: "Deduction types", icon: MinusCircle, perms: ["deductions.manage"] },
      { to: "/employee-deductions", label: "Employee deductions", icon: MinusCircle, perms: ["deductions.manage"] },
      { to: "/loans", label: "Loans & advances", icon: HandCoins, perms: ["loans.view"] },
    ],
  },
  {
    title: "Reports",
    items: [{ to: "/reports", label: "Reports", icon: BarChart3, perms: ["reports.view", "reports.view_department"] }],
  },
  {
    title: "Administration",
    items: [
      { to: "/admin/users", label: "Users", icon: Users, perms: ["users.manage"] },
      { to: "/admin/roles", label: "Roles", icon: ShieldCheck, perms: ["roles.manage"] },
      { to: "/admin/statutory-rules", label: "Statutory rules", icon: Scale, perms: ["statutory.view"] },
      { to: "/admin/organisation", label: "Organisation setup", icon: Building2, perms: ["employees.manage", "leave.manage"] },
      { to: "/admin/bank-formats", label: "Bank file formats", icon: Landmark, perms: ["payments.export"] },
      { to: "/admin/company", label: "Company settings", icon: Settings, perms: ["company.manage"] },
      { to: "/admin/audit-logs", label: "Audit logs", icon: ClipboardList, perms: ["audit.view"] },
    ],
  },
  {
    title: "My space",
    items: [
      { to: "/me", label: "My profile", icon: User, perms: ["self.view"] },
      { to: "/me/payslips", label: "My payslips", icon: Receipt, perms: ["self.view"] },
      { to: "/me/deductions", label: "My deductions", icon: MinusCircle, perms: ["self.view"] },
    ],
  },
];

export function firstAllowedPath(can: (...c: string[]) => boolean) {
  for (const g of NAV) for (const i of g.items) if (can(...i.perms)) return i.to;
  return "/me";
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { can } = useAuth();
  return (
    <nav className="flex h-full flex-col overflow-y-auto bg-brand-800 px-3 py-4 text-brand-100" aria-label="Main navigation">
      <div className="mb-6 flex items-center gap-2 px-2">
        <img src="/logo.svg" alt="Bravado Company Ltd logo" width={48} height={48} className="object-contain"/>
        <div className="leading-tight">
          <p className="text-sm font-bold text-white">Bravado Company Ltd</p>
          <p className="text-xs text-brand-200">Payroll Management</p>
        </div>
      </div>
      {NAV.map((g) => {
        const items = g.items.filter((i) => can(...i.perms));
        if (!items.length) return null;
        return (
          <div key={g.title} className="mb-4">
            <p className="mb-1 px-2 text-[11px] font-semibold uppercase tracking-wider text-brand-300">{g.title}</p>
            {items.map((i) => (
              <NavLink
                key={i.to}
                to={i.to}
                end={i.to === "/payroll" || i.to === "/me"}
                onClick={onNavigate}
                className={({ isActive }) =>
                  clsx(
                    "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition",
                    isActive ? "bg-brand-600 font-semibold text-white" : "hover:bg-brand-700 hover:text-white",
                  )
                }
              >
                <i.icon className="h-4 w-4 shrink-0" />
                {i.label}
              </NavLink>
            ))}
          </div>
        );
      })}
    </nav>
  );
}

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const doLogout = async () => {
    await logout();
    navigate("/login");
  };
  return (
    <div className="flex min-h-screen">
      <aside className="no-print fixed inset-y-0 left-0 hidden w-64 lg:block">
        <Sidebar />
      </aside>
      {open && (
        <div className="no-print fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-72">
            <button className="absolute right-2 top-3 z-10 rounded p-1 text-white" onClick={() => setOpen(false)} aria-label="Close menu">
              <X className="h-5 w-5" />
            </button>
            <Sidebar onNavigate={() => setOpen(false)} />
          </div>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col lg:pl-64">
        <header className="no-print sticky top-0 z-30 flex h-14 items-center justify-between border-b border-slate-200 bg-white px-4">
          <button className="rounded p-1 text-slate-600 lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu">
            <Menu className="h-6 w-6" />
          </button>
          <div className="hidden text-sm text-slate-500 lg:block">Bravado Company Ltd · Payroll</div>
          <div className="flex items-center gap-3">
            <div className="text-right leading-tight">
              <p className="text-sm font-medium text-slate-800">{user?.first_name || user?.username}</p>
              <p className="text-xs text-slate-500">{user?.role_name}</p>
            </div>
            <button className="btn-secondary btn-sm" onClick={doLogout} aria-label="Log out">
              <LogOut className="h-4 w-4" /> <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 p-4 sm:p-6">
          <Suspense fallback={<PageLoader />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
