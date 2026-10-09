import { screen } from "@testing-library/react";
import { vi } from "vitest";

vi.mock("recharts", async () => {
  const actual: any = await vi.importActual("recharts");
  return { ...actual, ResponsiveContainer: ({ children }: any) => <div style={{ width: 600, height: 300 }}>{children}</div> };
});
vi.mock("../api/client", async () => {
  const actual: any = await vi.importActual("../api/client");
  return {
    ...actual,
    api: {
      get: vi.fn(async () => ({
        data: {
          total_employees: 8, pending_approvals: 1,
          current_period: { id: 3, name: "September 2026", status: "REVIEW", summary: { gross: "15175000.00", net: "10912662.50", deductions: "4262337.50", employer: "1593375.00", cost: "16768375.00", employees: 8 } },
          payroll_by_month: [{ period: "September 2026", gross: "15175000", net: "10912662.5", deductions: "4262337.5", employer: "1593375", cost: "16768375", employees: 8 }],
          payroll_by_department: [{ department: "Finance", gross: "5000000", net: "3500000", employees: 2 }],
          employees_by_department: [{ department: "Finance", count: 2 }],
          salary_distribution: [{ band: "0M-0.5M", count: 0 }],
          recent_periods: [{ id: 3, name: "September 2026", status: "REVIEW", start_date: "2026-09-01", net: "10912662.50" }],
        },
      })),
    },
  };
});

import Dashboard from "../pages/Dashboard";
import { renderWithProviders } from "./utils";

describe("Dashboard", () => {
  it("renders headline figures and the recent periods table", async () => {
    renderWithProviders(<Dashboard />);
    expect(await screen.findByText("Active employees")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getAllByText("TZS 10,912,662.50").length).toBeGreaterThan(0);
    expect(screen.getByText("TZS 16,768,375.00")).toBeInTheDocument();
    expect(screen.getAllByText("September 2026").length).toBeGreaterThan(0);
    expect(screen.getByText(/statutory disclaimer/i)).toBeInTheDocument();
  });
});
