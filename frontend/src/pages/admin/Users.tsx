import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, errorMessage } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { CrudPage } from "../../components/CrudPage";
import { useToast } from "../../components/Toast";
import { StatusBadge } from "../../components/ui";
import { dateTime } from "../../lib/format";
import { useList } from "../../lib/hooks";

export default function Users() {
  const { user } = useAuth();
  const notify = useToast();
  const qc = useQueryClient();
  const roles = useList<any>("/roles/");
  const roleOptions = (roles.data?.results || []).map((r: any) => ({ value: r.code, label: r.name }));
  const toggle = useMutation({
    mutationFn: (u: any) => api.post(`/users/${u.id}/${u.is_active ? "deactivate" : "activate"}/`),
    onSuccess: () => { notify("Account status updated."); qc.invalidateQueries({ queryKey: ["/users/"] }); },
    onError: (e) => notify(errorMessage(e), "error"),
  });
  return (
    <CrudPage<any>
      title="Users"
      subtitle="Accounts are deactivated, never deleted, to preserve the audit trail."
      entityName="user"
      endpoint="/users/"
      managePermission="users.manage"
      defaults={{ is_active: true, role: "EMPLOYEE", must_change_password: true }}
      toForm={(r) => ({ ...r, password: "" })}
      columns={[
        { key: "username", header: "Username", className: "font-medium" },
        { key: "name", header: "Name", hideOnMobile: true, render: (r) => `${r.first_name} ${r.last_name}`.trim() || "-" },
        { key: "email", header: "Email", hideOnMobile: true },
        { key: "role_name", header: "Role", render: (r) => r.role_name || "-" },
        { key: "last_login", header: "Last login", hideOnMobile: true, render: (r) => dateTime(r.last_login) },
        { key: "is_active", header: "Status", render: (r) => <StatusBadge status={r.is_active ? "ACTIVE" : "CANCELLED"} /> },
      ]}
      rowActions={(r) => r.id !== user?.id ? (
        <button className="btn-secondary btn-sm" onClick={() => toggle.mutate(r)}>{r.is_active ? "Deactivate" : "Activate"}</button>
      ) : null}
      fields={[
        { name: "username", label: "Username", required: true },
        { name: "email", label: "Email", type: "email", required: true },
        { name: "first_name", label: "First name" },
        { name: "last_name", label: "Last name" },
        { name: "phone", label: "Phone", type: "tel" },
        { name: "role", label: "Role", type: "select", required: true, options: roleOptions },
        { name: "password", label: "Password (leave blank to keep)", type: "password", help: "Min. 10 characters; not common or purely numeric." },
        { name: "must_change_password", label: "Require password change", type: "checkbox" },
        { name: "is_active", label: "Active", type: "checkbox" },
      ]}
    />
  );
}
