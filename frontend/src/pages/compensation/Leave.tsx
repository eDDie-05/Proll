import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, errorMessage } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { CrudPage } from "../../components/CrudPage";
import { useToast } from "../../components/Toast";
import { StatusBadge } from "../../components/ui";
import { date } from "../../lib/format";
import { employeeLabel, useOptions } from "../../lib/hooks";

export default function Leave() {
  const { can } = useAuth();
  const notify = useToast();
  const qc = useQueryClient();
  const employees = useOptions("/employees/", employeeLabel);
  const types = useOptions("/leave-types/", (t) => `${t.name}${t.payroll_effect !== "NONE" ? " (unpaid)" : ""}`);
  const act = useMutation({
    mutationFn: ({ id, action }: { id: number; action: string }) => api.post(`/leave-records/${id}/${action}/`),
    onSuccess: () => { notify("Leave updated."); qc.invalidateQueries({ queryKey: ["/leave-records/"] }); },
    onError: (e) => notify(errorMessage(e), "error"),
  });
  return (
    <CrudPage<any>
      title="Leave & absence"
      subtitle="Approved leave of a type configured as unpaid reduces basic salary pro-rata in open payroll periods."
      entityName="leave record"
      endpoint="/leave-records/"
      managePermission="leave.manage"
      editable={(r) => r.status === "PENDING"}
      columns={[
        { key: "employee_name", header: "Employee" },
        { key: "leave_type_name", header: "Type" },
        { key: "start_date", header: "From", render: (r) => date(r.start_date) },
        { key: "end_date", header: "To", render: (r) => date(r.end_date) },
        { key: "days", header: "Days", align: "right" },
        { key: "payroll_effect", header: "Payroll", hideOnMobile: true, render: (r) => (r.payroll_effect === "NONE" ? "Paid" : "Unpaid") },
        { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
      ]}
      rowActions={(r) => can("leave.manage") && r.status === "PENDING" ? (
        <>
          <button className="btn-success btn-sm" onClick={() => act.mutate({ id: r.id, action: "approve" })}>Approve</button>
          <button className="btn-secondary btn-sm" onClick={() => act.mutate({ id: r.id, action: "reject" })}>Reject</button>
        </>
      ) : can("leave.manage") && r.status === "APPROVED" ? (
        <button className="btn-secondary btn-sm" onClick={() => act.mutate({ id: r.id, action: "cancel" })}>Cancel</button>
      ) : null}
      fields={[
        { name: "employee", label: "Employee", type: "select", required: true, options: employees },
        { name: "leave_type", label: "Leave type", type: "select", required: true, options: types },
        { name: "start_date", label: "Start date", type: "date", required: true },
        { name: "end_date", label: "End date", type: "date", required: true },
        { name: "days", label: "Days (blank = calendar days)", type: "number", min: "0.5", step: "0.5" },
        { name: "reason", label: "Reason", type: "textarea", colSpan: 2 },
      ]}
    />
  );
}
