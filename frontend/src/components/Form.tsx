import clsx from "clsx";
import type { ReactNode } from "react";

export type FieldType = "text" | "number" | "date" | "email" | "select" | "textarea" | "checkbox" | "password" | "tel" | "file" | "json";

export interface FieldDef {
  name: string;
  label: string;
  type?: FieldType;
  required?: boolean;
  options?: { value: string | number; label: string }[];
  help?: string;
  placeholder?: string;
  step?: string;
  min?: string;
  colSpan?: 1 | 2;
  disabled?: boolean;
  showIf?: (values: Record<string, any>) => boolean;
}

export function Field({ label, error, help, required, children, className, htmlFor }: {
  label: string; error?: string; help?: string; required?: boolean; children: ReactNode; className?: string; htmlFor?: string;
}) {
  return (
    <div className={className}>
      <label className="label" htmlFor={htmlFor}>
        {label} {required && <span className="text-red-600">*</span>}
      </label>
      {children}
      {help && !error && <p className="mt-1 text-xs text-slate-500">{help}</p>}
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  );
}

/** Renders a grid of inputs from a declarative field list. Values are strings/booleans keyed by name. */
export function FormFields({ fields, values, onChange, errors = {} }: {
  fields: FieldDef[];
  values: Record<string, any>;
  onChange: (name: string, value: any) => void;
  errors?: Record<string, string>;
}) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {fields
        .filter((f) => !f.showIf || f.showIf(values))
        .map((f) => {
          const id = `f-${f.name}`;
          const type = f.type || "text";
          const common = { id, name: f.name, disabled: f.disabled, required: f.required, "aria-invalid": !!errors[f.name] };
          let input: ReactNode;
          if (type === "select") {
            input = (
              <select {...common} className="input" value={values[f.name] ?? ""} onChange={(e) => onChange(f.name, e.target.value)}>
                <option value="">— Select —</option>
                {f.options?.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            );
          } else if (type === "textarea" || type === "json") {
            input = (
              <textarea {...common} className={clsx("input min-h-[80px]", type === "json" && "font-mono text-xs")} value={values[f.name] ?? ""}
                placeholder={f.placeholder} onChange={(e) => onChange(f.name, e.target.value)} />
            );
          } else if (type === "checkbox") {
            return (
              <label key={f.name} className={clsx("flex items-start gap-2 text-sm", f.colSpan === 2 && "sm:col-span-2")}>
                <input type="checkbox" id={id} className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-700" checked={!!values[f.name]}
                  disabled={f.disabled} onChange={(e) => onChange(f.name, e.target.checked)} />
                <span>
                  <span className="font-medium text-slate-700">{f.label}</span>
                  {f.help && <span className="block text-xs text-slate-500">{f.help}</span>}
                  {errors[f.name] && <span className="block text-xs text-red-600">{errors[f.name]}</span>}
                </span>
              </label>
            );
          } else if (type === "file") {
            input = (
              <input {...common} type="file" className="input" accept=".pdf,.png,.jpg,.jpeg" onChange={(e) => onChange(f.name, e.target.files?.[0] ?? null)} />
            );
          } else {
            input = (
              <input {...common} type={type} className="input" value={values[f.name] ?? ""} placeholder={f.placeholder} step={f.step} min={f.min}
                onChange={(e) => onChange(f.name, e.target.value)} />
            );
          }
          return (
            <Field key={f.name} htmlFor={id} label={f.label} required={f.required} help={f.help} error={errors[f.name]}
              className={clsx(f.colSpan === 2 && "sm:col-span-2")}>
              {input}
            </Field>
          );
        })}
    </div>
  );
}

/** Convert form state into an API payload: "" -> null for optional non-text fields; JSON fields parsed. */
export function toPayload(fields: FieldDef[], values: Record<string, any>) {
  const out: Record<string, any> = {};
  for (const f of fields) {
    if (f.showIf && !f.showIf(values)) continue;
    let v = values[f.name];
    if (f.type === "file") {
      if (v instanceof File) out[f.name] = v;
      continue;
    }
    if (f.type === "json") {
      try {
        v = typeof v === "string" ? JSON.parse(v || "null") : v;
      } catch {
        throw new Error(`${f.label}: invalid JSON`);
      }
    }
    const type = f.type || "text";
    if (v === "" && !["text", "textarea", "email", "tel"].includes(type)) v = null;
    if (f.type === "checkbox") v = !!v;
    out[f.name] = v;
  }
  return out;
}

export function hasFile(payload: Record<string, any>) {
  return Object.values(payload).some((v) => v instanceof File);
}

export function toFormData(payload: Record<string, any>) {
  const fd = new FormData();
  for (const [k, v] of Object.entries(payload)) {
    if (v === null || v === undefined) continue;
    fd.append(k, v instanceof File ? v : typeof v === "object" ? JSON.stringify(v) : String(v));
  }
  return fd;
}
