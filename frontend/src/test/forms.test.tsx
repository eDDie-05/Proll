import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { FormFields, type FieldDef } from "../components/Form";

const fields: FieldDef[] = [
  { name: "payment_method", label: "Payment method", type: "select", options: [{ value: "BANK", label: "Bank" }, { value: "MOBILE", label: "Mobile" }] },
  { name: "bank_account_number", label: "Account number", showIf: (v) => v.payment_method === "BANK" },
  { name: "mobile_money_number", label: "Mobile number", showIf: (v) => v.payment_method === "MOBILE" },
];

function Harness() {
  const [values, setValues] = useState<Record<string, any>>({ payment_method: "BANK" });
  return <FormFields fields={fields} values={values} errors={{ bank_account_number: "Required for bank payments." }}
    onChange={(n, v) => setValues((s) => ({ ...s, [n]: v }))} />;
}

describe("FormFields", () => {
  it("shows conditional fields and inline errors", async () => {
    render(<Harness />);
    expect(screen.getByLabelText(/account number/i)).toBeInTheDocument();
    expect(screen.getByText("Required for bank payments.")).toBeInTheDocument();
    expect(screen.queryByLabelText(/mobile number/i)).not.toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText(/payment method/i), "MOBILE");
    expect(screen.getByLabelText(/mobile number/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/account number/i)).not.toBeInTheDocument();
  });
});
