import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { me } from "./utils";

const perms = ["reports.view", "reports.export"];
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: me(perms), can: (...c: string[]) => c.some((x) => perms.includes(x)) }),
}));
const get = vi.fn(async (url: string, _cfg?: unknown) => {
  if (url === "/payroll-periods/") return { data: { count: 1, results: [{ id: 7, name: "September 2026", status: "APPROVED" }] } };
  if (url === "/departments/") return { data: [{ id: 1, name: "Finance" }] };
  return {
    data: {
      title: "PAYE Tax Report", subtitle: "September 2026",
      columns: [{ key: "employee_name", label: "Employee", type: "text" }, { key: "paye", label: "PAYE", type: "money" }],
      rows: [{ employee_name: "John Doe", paye: "120000.00" }], totals: { employee_name: "TOTAL", paye: "120000.00" }, summary: null,
    },
  };
});
vi.mock("../api/client", async () => {
  const actual: any = await vi.importActual("../api/client");
  return { ...actual, api: { get: (url: string, cfg: any) => get(url, cfg) } };
});

import { ReportView } from "../pages/reports/Reports";
import { renderWithProviders } from "./utils";

describe("Reports", () => {
  it("asks for a period, then renders the report with totals and export buttons", async () => {
    renderWithProviders(<ReportView reportKey="tax" title="PAYE tax report" needsPeriod />);
    expect(screen.getByText(/select a payroll period/i)).toBeInTheDocument();
    await screen.findByRole("option", { name: /september 2026/i });
    await userEvent.selectOptions(screen.getByLabelText(/payroll period/i), "7");
    expect(await screen.findByText("John Doe")).toBeInTheDocument();
    expect(screen.getByText("TOTAL")).toBeInTheDocument();
    expect(screen.getAllByText("120,000.00")).toHaveLength(2);
    for (const name of [/csv/i, /excel/i, /pdf/i, /print/i]) expect(screen.getByRole("button", { name })).toBeInTheDocument();
    expect(get).toHaveBeenCalledWith("/reports/tax/", { params: { period: "7" } });
  });
});
