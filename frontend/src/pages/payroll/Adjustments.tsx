import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, errorMessage } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { CrudPage } from "../../components/CrudPage";
import { useToast } from "../../components/Toast";
import { Alert, StatusBadge } from "../../components/ui";
import { money } from "../../lib/format";
import { employeeLabel, useOptions } from "../../lib/hooks";

export default function Adjustments() {
  const { can } = useAuth();
  const notify = useToast();
  const qc = useQueryClient();
  const employees = useOptions("/employees/", employeeLabel);
  const openPeriods = useOptions("/payroll-periods/", (p) => `${p.name} (${p.status})`, true, { status: "" });
  const decide = useMutation({
    mutationFn: ({ id, action }: { id: number; action: string }) => api.post(`/payroll-adjustments/${id}/${action}/`),
    onSuccess: () => { notify("Adjustment updated."); qc.invalidateQueries({ queryKey: ["/payroll-adjustments/"] }); },
    onError: (e) => notify(errorMessage(e), "error"),
  });
  return (
    <CrudPage<any>
      title="Payroll adjustments"
      subtitle="Corrections to closed or approved payroll are applied through approved adjustments in an open period — history is never silently changed."
      entityName="adjustment"
      endpoint="/payroll-adjustments/"
      managePermission="payroll.adjust"
      editable={(r) => r.status === "PENDING"}
      deletable
      defaults={{ category: "EARNING", is_taxable: true, is_social_security_base: true, is_cash_emolument: true }}
      before={<div className="mb-4"><Alert kind="info">Adjustments can only target a DRAFT or CALCULATED period, and must be approved by someone other than the creator. Recalculate the target period after approval.</Alert></div>}
      columns={[
        { key: "employee_name", header: "Employee" },
        { key: "name", header: "Description" },
        { key: "category", header: "Type", render: (r) => (r.category === "EARNING" ? "Earning" : "Deduction") },
        { key: "amount", header: "Amount", align: "right", render: (r) => money(r.amount) },
        { key: "target_period_name", header: "Applied in" },
        { key: "original_period_name", header: "Corrects", hideOnMobile: true, render: (r) => r.original_period_name || "-" },
        { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
      ]}
      rowActions={(r) => r.status === "PENDING" && can("payroll.approve") ? (
        <>
          <button className="btn-success btn-sm" onClick={() => decide.mutate({ id: r.id, action: "approve" })}>Approve</button>
          <button className="btn-secondary btn-sm" onClick={() => decide.mutate({ id: r.id, action: "reject" })}>Reject</button>
        </>
      ) : null}
      fields={[
        { name: "employee", label: "Employee", type: "select", required: true, options: employees, colSpan: 2 },
        { name: "target_period", label: "Apply in period", type: "select", required: true, options: openPeriods },
        { name: "original_period", label: "Corrects period (optional)", type: "select", options: openPeriods },
        { name: "category", label: "Type", type: "select", required: true, options: [{ value: "EARNING", label: "Additional earning / arrears" }, { value: "DEDUCTION", label: "Recovery / deduction" }] },
        { name: "amount", label: "Amount (TZS)", type: "number", required: true, min: "0" },
        { name: "name", label: "Description (shown on payslip)", required: true, colSpan: 2 },
        { name: "is_taxable", label: "Taxable", type: "checkbox", showIf: (v) => v.category === "EARNING" },
        { name: "is_social_security_base", label: "Counts for social security", type: "checkbox", showIf: (v) => v.category === "EARNING" },
        { name: "is_cash_emolument", label: "Cash emolument (employer levies)", type: "checkbox", showIf: (v) => v.category === "EARNING" },
        { name: "reason", label: "Reason / justification", type: "textarea", required: true, colSpan: 2 },
      ]}
    />
  );
}
