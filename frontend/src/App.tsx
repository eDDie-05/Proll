import { lazy, type ReactElement } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { firstAllowedPath, Layout } from "./components/Layout";
import { PageLoader } from "./components/ui";
const AuditLogs = lazy(() => import("./pages/admin/AuditLogs"));
const BankFormats = lazy(() => import("./pages/admin/BankFormats"));
const CompanySettingsPage = lazy(() => import("./pages/admin/CompanySettings"));
const Organisation = lazy(() => import("./pages/admin/Organisation"));
const Roles = lazy(() => import("./pages/admin/Roles"));
const StatutoryRules = lazy(() => import("./pages/admin/StatutoryRules"));
const Users = lazy(() => import("./pages/admin/Users"));
import ForgotPassword from "./pages/auth/ForgotPassword";
import Login from "./pages/auth/Login";
import ResetPassword from "./pages/auth/ResetPassword";
const AllowanceTypes = lazy(() => import("./pages/compensation/Compensation").then((m) => ({ default: m.AllowanceTypes })));
const DeductionTypes = lazy(() => import("./pages/compensation/Compensation").then((m) => ({ default: m.DeductionTypes })));
const EmployeeAllowances = lazy(() => import("./pages/compensation/Compensation").then((m) => ({ default: m.EmployeeAllowances })));
const EmployeeDeductions = lazy(() => import("./pages/compensation/Compensation").then((m) => ({ default: m.EmployeeDeductions })));
const Leave = lazy(() => import("./pages/compensation/Leave"));
const Loans = lazy(() => import("./pages/compensation/Loans"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Contracts = lazy(() => import("./pages/employees/Contracts"));
const EmployeeForm = lazy(() => import("./pages/employees/EmployeeForm"));
const EmployeeList = lazy(() => import("./pages/employees/EmployeeList"));
const EmployeeProfile = lazy(() => import("./pages/employees/EmployeeProfile"));
const Salaries = lazy(() => import("./pages/employees/Salaries"));
const Adjustments = lazy(() => import("./pages/payroll/Adjustments"));
const Payments = lazy(() => import("./pages/payroll/Payments"));
const PayrollHistory = lazy(() => import("./pages/payroll/PayrollHistory"));
const PeriodDetail = lazy(() => import("./pages/payroll/PeriodDetail"));
const Periods = lazy(() => import("./pages/payroll/Periods"));
const PayslipList = lazy(() => import("./pages/payslips/PayslipList"));
const PayslipPreview = lazy(() => import("./pages/payslips/PayslipPreview"));
const Reports = lazy(() => import("./pages/reports/Reports"));
const MyDeductions = lazy(() => import("./pages/self/SelfService").then((m) => ({ default: m.MyDeductions })));
const MyPayslips = lazy(() => import("./pages/self/SelfService").then((m) => ({ default: m.MyPayslips })));
const MyProfile = lazy(() => import("./pages/self/SelfService").then((m) => ({ default: m.MyProfile })));

function Guard({ perms, children }: { perms: string[]; children: ReactElement }) {
  const { can } = useAuth();
  if (!can(...perms)) {
    return (
      <div className="card p-8 text-center">
        <h1 className="text-lg font-semibold text-brand-800">Access denied</h1>
        <p className="mt-1 text-sm text-slate-500">Your role does not have permission to view this page.</p>
      </div>
    );
  }
  return children;
}

const P = {
  payroll: ["payroll.view", "payroll.view_approved", "payroll.approve", "payroll.prepare"],
  reports: ["reports.view", "reports.view_department"],
};

export default function App() {
  const { user, loading, can } = useAuth();
  if (loading) return <PageLoader />;
  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }
  const g = (perms: string[], el: ReactElement) => <Guard perms={perms}>{el}</Guard>;
  return (
    <Routes>
      <Route path="/login" element={<Navigate to="/" replace />} />
      <Route element={<Layout />}>
        <Route index element={<Navigate to={firstAllowedPath(can)} replace />} />
        <Route path="dashboard" element={g([...P.reports, "payroll.view", "payroll.prepare"], <Dashboard />)} />
        <Route path="employees" element={g(["employees.view"], <EmployeeList />)} />
        <Route path="employees/new" element={g(["employees.manage"], <EmployeeForm />)} />
        <Route path="employees/:id" element={g(["employees.view"], <EmployeeProfile />)} />
        <Route path="employees/:id/edit" element={g(["employees.manage"], <EmployeeForm />)} />
        <Route path="contracts" element={g(["contracts.manage"], <Contracts />)} />
        <Route path="salaries" element={g(["salary.view"], <Salaries />)} />
        <Route path="leave" element={g(["leave.view"], <Leave />)} />
        <Route path="payroll" element={g(P.payroll, <Periods />)} />
        <Route path="payroll/history" element={g(P.reports, <PayrollHistory />)} />
        <Route path="payroll/:id" element={g(P.payroll, <PeriodDetail />)} />
        <Route path="adjustments" element={g(["payroll.adjust", "payroll.view"], <Adjustments />)} />
        <Route path="payments" element={g(["payments.view"], <Payments />)} />
        <Route path="payslips" element={g(["payslips.generate", "payroll.view"], <PayslipList />)} />
        <Route path="payslips/:itemId" element={g([...P.payroll, "self.view"], <PayslipPreview />)} />
        <Route path="allowance-types" element={g(["allowances.manage"], <AllowanceTypes />)} />
        <Route path="employee-allowances" element={g(["allowances.manage"], <EmployeeAllowances />)} />
        <Route path="deduction-types" element={g(["deductions.manage"], <DeductionTypes />)} />
        <Route path="employee-deductions" element={g(["deductions.manage"], <EmployeeDeductions />)} />
        <Route path="loans" element={g(["loans.view"], <Loans />)} />
        <Route path="reports" element={g(P.reports, <Reports />)} />
        <Route path="admin/users" element={g(["users.manage"], <Users />)} />
        <Route path="admin/roles" element={g(["roles.manage"], <Roles />)} />
        <Route path="admin/statutory-rules" element={g(["statutory.view"], <StatutoryRules />)} />
        <Route path="admin/organisation" element={g(["employees.manage", "leave.manage"], <Organisation />)} />
        <Route path="admin/bank-formats" element={g(["payments.export"], <BankFormats />)} />
        <Route path="admin/company" element={g(["company.manage"], <CompanySettingsPage />)} />
        <Route path="admin/audit-logs" element={g(["audit.view"], <AuditLogs />)} />
        <Route path="me" element={g(["self.view"], <MyProfile />)} />
        <Route path="me/payslips" element={g(["self.view"], <MyPayslips />)} />
        <Route path="me/deductions" element={g(["self.view"], <MyDeductions />)} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
