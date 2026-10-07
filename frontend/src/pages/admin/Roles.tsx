import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { api, errorMessage } from "../../api/client";
import { useToast } from "../../components/Toast";
import { Alert, Card, Modal, PageHeader, PageLoader, Spinner } from "../../components/ui";
import { useList } from "../../lib/hooks";

export default function Roles() {
  const notify = useToast();
  const qc = useQueryClient();
  const roles = useList<any>("/roles/");
  const perms = useList<any>("/permissions/");
  const [editing, setEditing] = useState<any | null>(null);
  const [error, setError] = useState("");
  const save = useMutation({
    mutationFn: (r: any) => (r.id ? api.patch(`/roles/${r.id}/`, r) : api.post("/roles/", r)),
    onSuccess: () => { notify("Role saved. Permission change recorded in the audit log."); setEditing(null); qc.invalidateQueries({ queryKey: ["/roles/"] }); },
    onError: (e) => setError(errorMessage(e)),
  });
  if (roles.isLoading || perms.isLoading) return <PageLoader />;
  const groups: Record<string, any[]> = {};
  for (const p of perms.data?.results || []) (groups[p.code.split(".")[0]] ||= []).push(p);
  const toggle = (code: string) =>
    setEditing((e: any) => ({ ...e, permissions: e.permissions.includes(code) ? e.permissions.filter((c: string) => c !== code) : [...e.permissions, code] }));

  return (
    <div>
      <PageHeader title="Roles & permissions" actions={
        <button className="btn-primary" onClick={() => { setError(""); setEditing({ code: "", name: "", description: "", permissions: [] }); }}>
          <Plus className="h-4 w-4" /> New role
        </button>
      } />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {roles.data?.results.map((r: any) => (
          <Card key={r.id} title={r.name} actions={<button className="btn-secondary btn-sm" onClick={() => { setError(""); setEditing({ ...r }); }}>Edit</button>}>
            <p className="text-xs text-slate-500">{r.code} · {r.user_count} user(s){r.is_system && " · system role"}</p>
            <p className="mt-2 text-sm text-slate-700">{r.permissions.length} permission(s)</p>
          </Card>
        ))}
      </div>
      <Modal open={!!editing} onClose={() => setEditing(null)} title={editing?.id ? `Edit ${editing.name}` : "New role"} wide footer={
        <>
          <button className="btn-secondary" onClick={() => setEditing(null)}>Cancel</button>
          <button className="btn-primary" disabled={save.isPending} onClick={() => save.mutate(editing)}>{save.isPending && <Spinner className="h-4 w-4 text-white" />} Save</button>
        </>
      }>
        {editing && (
          <div className="space-y-4">
            {error && <Alert>{error}</Alert>}
            <div className="grid gap-3 sm:grid-cols-2">
              <div><label className="label" htmlFor="rc">Code</label><input id="rc" className="input" disabled={editing.is_system} value={editing.code} onChange={(e) => setEditing({ ...editing, code: e.target.value })} /></div>
              <div><label className="label" htmlFor="rn">Name</label><input id="rn" className="input" value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} /></div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {Object.entries(groups).map(([g, list]) => (
                <fieldset key={g} className="rounded-md border border-slate-200 p-3">
                  <legend className="px-1 text-xs font-semibold uppercase text-brand-700">{g}</legend>
                  {list.map((p) => (
                    <label key={p.code} className="flex items-start gap-2 py-0.5 text-sm">
                      <input type="checkbox" className="mt-0.5" checked={editing.permissions.includes(p.code)} onChange={() => toggle(p.code)} />
                      <span>{p.description} <span className="text-xs text-slate-400">({p.code})</span></span>
                    </label>
                  ))}
                </fieldset>
              ))}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
