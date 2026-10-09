import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, errorMessage } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { CrudPage } from "../../components/CrudPage";
import { DataTable } from "../../components/DataTable";
import { useToast } from "../../components/Toast";
import { Modal, StatusBadge } from "../../components/ui";
import { date, humanize, money } from "../../lib/format";
import { employeeLabel, useOptions } from "../../lib/hooks";

export default function Loans() {
  const { can } = useAuth();
  const notify = useToast();
  const qc = useQueryClient();
  const [viewing, setViewing] = useState<any>(null);
  const employees = useOptions("/employees/", employeeLabel, true, { status: "ACTIVE" });
  const act = useMutation({
    mutationFn: ({ id, action }: { id: number; action: string }) => api.post(`/loans/${id}/${action}/`),
    onSuccess: () => { notify("Loan updated."); qc.invalidateQueries({ queryKey: ["/loans/"] }); },
    onError: (e) => notify(errorMessage(e), "error"),
  });
  return (
    <>
      <CrudPage<any>
        title="Loans & salary advances"
        subtitle="Approved loans are deducted automatically each payroll until the balance is cleared."
        entityName="loan"
        endpoint="/loans/"
        managePermission="loans.manage"
        editable={(r) => r.status === "PENDING"}
        defaults={{ loan_type: "LOAN", interest_rate: "0" }}
        onRowClick={setViewing}
        columns={[
          { key: "reference", header: "Reference", className: "font-medium" },
          { key: "employee_name", header: "Employee" },
          { key: "loan_type", header: "Type", hideOnMobile: true, render: (r) => humanize(r.loan_type) },
          { key: "total_repayable", header: "Total", align: "right", render: (r) => money(r.total_repayable) },
          { key: "installment_amount", header: "Installment", align: "right", hideOnMobile: true, render: (r) => money(r.installment_amount) },
          { key: "remaining_balance", header: "Balance", align: "right", render: (r) => money(r.remaining_balance) },
          { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
        ]}
        rowActions={(r) => can("loans.manage") && (r.status === "PENDING" || r.status === "ACTIVE") ? (
          <>
            {r.status === "PENDING" && <button className="btn-success btn-sm" onClick={() => act.mutate({ id: r.id, action: "approve" })}>Approve</button>}
            <button className="btn-secondary btn-sm" onClick={() => act.mutate({ id: r.id, action: "cancel" })}>Cancel</button>
          </>
        ) : null}
        fields={[
          { name: "employee", label: "Employee", type: "select", required: true, options: employees },
          { name: "reference", label: "Reference", required: true },
          { name: "loan_type", label: "Type", type: "select", required: true, options: [{ value: "LOAN", label: "Loan" }, { value: "ADVANCE", label: "Salary advance" }] },
          { name: "principal", label: "Principal (TZS)", type: "number", required: true, min: "0" },
          { name: "interest_rate", label: "Flat interest (%)", type: "number", min: "0", step: "0.01" },
          { name: "installment_amount", label: "Installment per period (TZS)", type: "number", required: true, min: "0" },
          { name: "number_of_installments", label: "Number of installments", type: "number", required: true, min: "1" },
          { name: "start_date", label: "First deduction date", type: "date", required: true },
          { name: "end_date", label: "Expected end date", type: "date" },
          { name: "notes", label: "Notes", type: "textarea", colSpan: 2 },
        ]}
      />
      <Modal open={!!viewing} onClose={() => setViewing(null)} title={`Loan ${viewing?.reference ?? ""} — repayment history`}>
        {viewing && (
          <>
            <p className="mb-3 text-sm text-slate-600">
              {viewing.employee_name} · Total {money(viewing.total_repayable)} · Repaid {money(viewing.amount_repaid)} · Balance {money(viewing.remaining_balance)}
            </p>
            <DataTable rows={viewing.repayments} empty="No repayments yet." columns={[
              { key: "date", header: "Date", render: (r: any) => date(r.date) },
              { key: "source", header: "Source", render: (r: any) => humanize(r.source) },
              { key: "period_name", header: "Period", render: (r: any) => r.period_name || "-" },
              { key: "amount", header: "Amount", align: "right", render: (r: any) => money(r.amount) },
            ]} />
          </>
        )}
      </Modal>
    </>
  );
}
