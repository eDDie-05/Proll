import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState, type ReactNode } from "react";
import { api, errorMessage, fieldErrors } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useList } from "../lib/hooks";
import { DataTable, Pagination, SearchBox, type Column } from "./DataTable";
import { hasFile, toFormData, toPayload, FormFields, type FieldDef } from "./Form";
import { useToast } from "./Toast";
import { Alert, Card, ConfirmDialog, Modal, PageHeader, Spinner } from "./ui";

export interface CrudConfig<T> {
  title: string;
  subtitle?: ReactNode;
  endpoint: string;
  columns: Column<T>[];
  fields: FieldDef[];
  managePermission: string | string[];
  defaults?: Record<string, any>;
  toForm?: (row: T) => Record<string, any>;
  searchable?: boolean;
  deletable?: boolean;
  editable?: (row: T) => boolean;
  filters?: ReactNode;
  params?: Record<string, any>;
  rowActions?: (row: T) => ReactNode;
  headerActions?: ReactNode;
  entityName?: string;
  onRowClick?: (row: T) => void;
  before?: ReactNode;
}

export function CrudPage<T extends { id: number }>(cfg: CrudConfig<T>) {
  const { can } = useAuth();
  const notify = useToast();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<T | null>(null);
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<Record<string, any>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState("");
  const [deleting, setDeleting] = useState<T | null>(null);
  const perms = Array.isArray(cfg.managePermission) ? cfg.managePermission : [cfg.managePermission];
  const canManage = can(...perms);
  const entity = cfg.entityName || "record";

  const list = useList<T>(cfg.endpoint, { page, search, ...(cfg.params || {}) });

  const startCreate = () => {
    setEditing(null);
    setValues({ ...(cfg.defaults || {}) });
    setErrors({});
    setFormError("");
    setOpen(true);
  };
  const startEdit = (row: T) => {
    setEditing(row);
    const v = cfg.toForm ? cfg.toForm(row) : { ...(row as any) };
    for (const f of cfg.fields) if (f.type === "json" && typeof v[f.name] !== "string") v[f.name] = JSON.stringify(v[f.name] ?? null, null, 2);
    setValues(v);
    setErrors({});
    setFormError("");
    setOpen(true);
  };

  const save = useMutation({
    mutationFn: async () => {
      const payload = toPayload(cfg.fields, values);
      const body = hasFile(payload) ? toFormData(payload) : payload;
      return editing ? api.patch(`${cfg.endpoint}${editing.id}/`, body) : api.post(cfg.endpoint, body);
    },
    onSuccess: () => {
      notify(`${entity[0].toUpperCase() + entity.slice(1)} ${editing ? "updated" : "created"}.`);
      setOpen(false);
      qc.invalidateQueries({ queryKey: [cfg.endpoint] });
    },
    onError: (e) => {
      setErrors(fieldErrors(e));
      setFormError(e instanceof Error && !("response" in e) ? e.message : errorMessage(e));
    },
  });

  const del = useMutation({
    mutationFn: (row: T) => api.delete(`${cfg.endpoint}${row.id}/`),
    onSuccess: () => {
      notify(`${entity} deleted.`);
      setDeleting(null);
      qc.invalidateQueries({ queryKey: [cfg.endpoint] });
    },
    onError: (e) => {
      notify(errorMessage(e), "error");
      setDeleting(null);
    },
  });

  const columns: Column<T>[] = [...cfg.columns];
  if (canManage || cfg.rowActions) {
    columns.push({
      key: "_actions",
      header: "",
      align: "right",
      render: (row) => (
        <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
          {cfg.rowActions?.(row)}
          {canManage && (!cfg.editable || cfg.editable(row)) && (
            <button className="btn-secondary btn-sm" onClick={() => startEdit(row)} aria-label="Edit">
              <Pencil className="h-3.5 w-3.5" />
            </button>
          )}
          {canManage && cfg.deletable && (
            <button className="btn-secondary btn-sm text-red-600" onClick={() => setDeleting(row)} aria-label="Delete">
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      ),
    });
  }

  return (
    <div>
      <PageHeader
        title={cfg.title}
        subtitle={cfg.subtitle}
        actions={
          <>
            {cfg.headerActions}
            {canManage && (
              <button className="btn-primary" onClick={startCreate}>
                <Plus className="h-4 w-4" /> New {entity}
              </button>
            )}
          </>
        }
      />
      {cfg.before}
      <Card>
        {(cfg.searchable !== false || cfg.filters) && (
          <div className="no-print mb-3 flex flex-col gap-2 sm:flex-row sm:items-center">
            {cfg.searchable !== false && <SearchBox value={search} onChange={(v) => { setSearch(v); setPage(1); }} />}
            {cfg.filters}
          </div>
        )}
        {list.isError && <Alert>{errorMessage(list.error)}</Alert>}
        <DataTable columns={columns} rows={list.data?.results} loading={list.isLoading} onRowClick={cfg.onRowClick} />
        {list.data && <Pagination page={page} count={list.data.count} onPage={setPage} />}
      </Card>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={`${editing ? "Edit" : "New"} ${entity}`}
        wide={cfg.fields.length > 8}
        footer={
          <>
            <button className="btn-secondary" onClick={() => setOpen(false)}>Cancel</button>
            <button className="btn-primary" onClick={() => save.mutate()} disabled={save.isPending}>
              {save.isPending && <Spinner className="h-4 w-4 text-white" />} Save
            </button>
          </>
        }
      >
        {formError && <div className="mb-3"><Alert>{formError}</Alert></div>}
        <FormFields fields={cfg.fields} values={values} errors={errors} onChange={(n, v) => setValues((s) => ({ ...s, [n]: v }))} />
      </Modal>

      <ConfirmDialog
        open={!!deleting}
        title={`Delete ${entity}`}
        message={`Are you sure you want to delete this ${entity}? This action is recorded in the audit log.`}
        danger
        confirmLabel="Delete"
        busy={del.isPending}
        onConfirm={() => deleting && del.mutate(deleting)}
        onCancel={() => setDeleting(null)}
      />
    </div>
  );
}
