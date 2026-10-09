import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { CrudPage } from "../../components/CrudPage";
import { Alert } from "../../components/ui";

export default function BankFormats() {
  const fields = useQuery({ queryKey: ["bank-fields"], queryFn: async () => (await api.get("/bank-export-formats/available-fields/")).data as Record<string, string> });
  return (
    <CrudPage<any>
      title="Bank payment file formats"
      entityName="format"
      endpoint="/bank-export-formats/"
      managePermission="payments.export"
      searchable={false}
      deletable
      defaults={{ delimiter: ",", include_header: true, date_format: "%Y-%m-%d", amount_decimals: 2, narration_template: "Salary {period_name}", payment_method: "BANK", is_active: true,
        columns: JSON.stringify([{ header: "Account Number", field: "bank_account_number" }, { header: "Amount", field: "amount" }], null, 2) }}
      before={<div className="mb-4"><Alert kind="info">
        No bank's file layout is assumed. Define columns as JSON: <code>{`[{"header": "...", "field": "<field>"}]`}</code> or a constant <code>{`{"header": "...", "value": "TZS"}`}</code>.
        {fields.data && <> Available fields: {Object.keys(fields.data).map((f) => <code key={f} className="mx-0.5 rounded bg-white px-1">{f}</code>)}</>}
      </Alert></div>}
      columns={[
        { key: "name", header: "Name", className: "font-medium" },
        { key: "delimiter", header: "Delimiter" },
        { key: "payment_method", header: "Method" },
        { key: "cols", header: "Columns", render: (r) => r.columns.map((c: any) => c.header).join(", ") },
        { key: "is_active", header: "Active", render: (r) => (r.is_active ? "Yes" : "No") },
      ]}
      fields={[
        { name: "name", label: "Name", required: true },
        { name: "payment_method", label: "Payment method", type: "select", options: [{ value: "BANK", label: "Bank" }, { value: "MOBILE", label: "Mobile money" }] },
        { name: "delimiter", label: "Delimiter", type: "select", options: [{ value: ",", label: "Comma" }, { value: ";", label: "Semicolon" }, { value: "|", label: "Pipe" }, { value: "\\t", label: "Tab" }] },
        { name: "date_format", label: "Date format (strftime)" },
        { name: "amount_decimals", label: "Amount decimals", type: "number", min: "0" },
        { name: "narration_template", label: "Narration template" },
        { name: "columns", label: "Columns (JSON)", type: "json", required: true, colSpan: 2 },
        { name: "include_header", label: "Include header row", type: "checkbox" },
        { name: "is_active", label: "Active", type: "checkbox" },
        { name: "description", label: "Description", type: "textarea", colSpan: 2 },
      ]}
    />
  );
}
