import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { me } from "./utils";

let permissions: string[] = [];
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: me(permissions), can: (...c: string[]) => c.some((x) => permissions.includes(x)) }),
}));

const period = (status: string) => ({
  id: 7, name: "September 2026", start_date: "2026-09-01", end_date: "2026-09-30", pay_date: "2026-09-28", status, notes: "",
  current_run: status === "DRAFT" ? null : {
    id: 1, run_number: 1, calculated_by_name: "payroll", calculated_at: "2026-09-26T10:00:00Z", employee_count: 2,
    total_gross: "3000000", total_employee_deductions: "600000", total_paye: "300000", total_net: "2400000",
    total_employer_contributions: "330000", total_employer_cost: "3330000", warnings: ["Statutory rule PAYE v1 is UNVERIFIED."], rules_used: [],
  },
  calculated_by_name: "payroll", calculated_at: null, submitted_by_name: null, submitted_at: null, approved_by_name: null, approved_at: null,
  paid_by_name: null, paid_at: null, closed_by_name: null, closed_at: null,
});

const get = vi.fn();
const post = vi.fn();
vi.mock("../api/client", async () => {
  const actual: any = await vi.importActual("../api/client");
  return { ...actual, api: { get: (...a: any[]) => get(...a), post: (...a: any[]) => post(...a) } };
});

import PeriodDetail from "../pages/payroll/PeriodDetail";
import { renderWithProviders } from "./utils";

function mockPeriod(status: string, check = { can_approve: true, blockers: [] as string[] }) {
  get.mockImplementation(async (url: string) => {
    if (url.endsWith("/approval-check/")) return { data: check };
    if (url.endsWith("/items/")) return { data: { count: 1, results: [{ id: 11, employee: 1, employee_number: "BRV0001", employee_name: "John Doe", department_name: "Finance", job_title: "", days_employed: "30", days_in_period: "30", monthly_basic_salary: "1000000", basic_earned: "1000000", gross_earnings: "1000000", taxable_income: "900000", paye: "120000", total_statutory_deductions: "220000", total_other_deductions: "0", total_deductions: "220000", net_salary: "780000", total_employer_contributions: "110000", employer_total_cost: "1110000", warnings: [], payment_status: null, has_payslip: false }] } };
    return { data: period(status) };
  });
}

const render = () => renderWithProviders(<PeriodDetail />, { route: "/payroll/7", path: "/payroll/:id" });

describe("Payroll workflow page", () => {
  beforeEach(() => { get.mockReset(); post.mockReset(); });

  it("lets a payroll officer calculate a draft and confirms first", async () => {
    permissions = ["payroll.prepare", "payroll.view"];
    mockPeriod("DRAFT");
    post.mockResolvedValue({ data: {} });
    render();
    await userEvent.click(await screen.findByRole("button", { name: /calculate payroll/i }));
    expect(screen.getByRole("dialog")).toHaveTextContent(/statutory rules in force/i);
    expect(post).not.toHaveBeenCalled();
    await userEvent.click(screen.getAllByRole("button", { name: /calculate payroll/i }).at(-1)!);
    await waitFor(() => expect(post).toHaveBeenCalledWith("/payroll-periods/7/calculate/", { comment: "" }));
    expect(screen.queryByRole("button", { name: /approve payroll/i })).not.toBeInTheDocument();
  });

  it("shows items, warnings and a submit action once calculated", async () => {
    permissions = ["payroll.prepare", "payroll.view"];
    mockPeriod("CALCULATED");
    render();
    expect(await screen.findByText("John Doe")).toBeInTheDocument();
    expect(screen.getByText(/1 calculation warning/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /submit for review/i })).toBeInTheDocument();
  });

  it("disables approval and lists blockers for approvers", async () => {
    permissions = ["payroll.approve", "payroll.view_approved"];
    mockPeriod("REVIEW", { can_approve: false, blockers: ["Statutory rule PAYE v1 is not verified."] });
    render();
    expect(await screen.findByText(/approval blocked/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: /approve payroll/i })).toBeDisabled());
    expect(screen.getByRole("button", { name: /reject payroll/i })).toBeEnabled();
    expect(screen.queryByRole("button", { name: /calculate payroll/i })).not.toBeInTheDocument();
  });

  it("requires a comment to reject", async () => {
    permissions = ["payroll.approve"];
    mockPeriod("REVIEW");
    render();
    await userEvent.click(await screen.findByRole("button", { name: /reject payroll/i }));
    expect(screen.getByLabelText(/comment/i)).toBeInTheDocument();
  });
});
