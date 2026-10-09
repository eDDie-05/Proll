import { money, humanize, compact } from "../lib/format";
import { toPayload } from "../components/Form";

describe("format helpers", () => {
  it("formats TZS money with negatives in brackets", () => {
    expect(money("1500000")).toBe("TZS 1,500,000.00");
    expect(money(-100000)).toBe("TZS (100,000.00)");
    expect(money(null)).toBe("-");
    expect(money("250.5", "")).toBe("250.50");
  });
  it("humanizes codes and compacts numbers", () => {
    expect(humanize("PAYROLL_APPROVE")).toBe("Payroll approve");
    expect(compact(2_500_000)).toBe("2.5M");
  });
});

describe("toPayload", () => {
  const fields = [
    { name: "name", label: "Name" },
    { name: "amount", label: "Amount", type: "number" as const },
    { name: "active", label: "Active", type: "checkbox" as const },
    { name: "cols", label: "Cols", type: "json" as const },
    { name: "hidden", label: "Hidden", showIf: () => false },
  ];
  it("normalises empty optional numbers to null and parses JSON", () => {
    expect(toPayload(fields, { name: "", amount: "", active: undefined, cols: '["NSSF"]', hidden: "x" })).toEqual({
      name: "", amount: null, active: false, cols: ["NSSF"],
    });
  });
  it("rejects invalid JSON", () => {
    expect(() => toPayload(fields, { cols: "{bad" })).toThrow(/invalid JSON/);
  });
});
