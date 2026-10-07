import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, errorMessage, fieldErrors } from "../../api/client";
import { FormFields, toPayload, type FieldDef } from "../../components/Form";
import { useToast } from "../../components/Toast";
import { Alert, Card, PageHeader, PageLoader, Spinner } from "../../components/ui";
import { useOptions } from "../../lib/hooks";
import { EMPLOYEE_STATUSES } from "./EmployeeList";

export default function EmployeeForm() {
  const { id } = useParams();
  const editing = !!id;
  const navigate = useNavigate();
  const notify = useToast();
  const qc = useQueryClient();
  const [values, setValues] = useState<Record<string, any>>({
    status: "ACTIVE", payment_method: "BANK", social_security_scheme: "NSSF", is_tax_resident: true,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);

  const existing = useQuery({
    queryKey: ["/employees/", id],
    enabled: editing,
    queryFn: async () => (await api.get(`/employees/${id}/`)).data,
  });
  useEffect(() => {
    if (existing.data) setValues(existing.data);
  }, [existing.data]);

  const depts = useOptions("/departments/", (d) => d.name);
  const positions = useOptions("/positions/", (p) => p.title + (p.department_name ? ` (${p.department_name})` : ""));
  const types = useOptions("/employment-types/", (t) => t.name);

  const sections: { title: string; fields: FieldDef[] }[] = [
    {
      title: "Personal details",
      fields: [
        { name: "employee_number", label: "Employee ID", required: true, placeholder: "BRV0001" },
        { name: "first_name", label: "First name", required: true },
        { name: "middle_name", label: "Middle name" },
        { name: "last_name", label: "Last name", required: true },
        { name: "gender", label: "Gender", type: "select", options: [
          { value: "MALE", label: "Male" }, { value: "FEMALE", label: "Female" }, { value: "UNSPECIFIED", label: "Prefer not to say" }] },
        { name: "date_of_birth", label: "Date of birth", type: "date" },
        { name: "phone", label: "Phone", type: "tel", placeholder: "+255 7xx xxx xxx" },
        { name: "email", label: "Email", type: "email" },
        { name: "national_id", label: "NIDA number" },
        { name: "address", label: "Address", type: "textarea", colSpan: 2 },
      ],
    },
    {
      title: "Employment",
      fields: [
        { name: "department", label: "Department", type: "select", required: true, options: depts },
        { name: "position", label: "Job title / position", type: "select", options: positions },
        { name: "employment_type", label: "Employment type", type: "select", required: true, options: types },
        { name: "status", label: "Employment status", type: "select", required: true,
          options: EMPLOYEE_STATUSES.map((s) => ({ value: s, label: s.replace("_", " ") })) },
        { name: "employment_start_date", label: "Start date", type: "date", required: true },
        { name: "employment_end_date", label: "End date", type: "date" },
      ],
    },
    {
      title: "Payment details",
      fields: [
        { name: "payment_method", label: "Payment method", type: "select", required: true,
          options: [{ value: "BANK", label: "Bank transfer" }, { value: "MOBILE", label: "Mobile money" }, { value: "CASH", label: "Cash / cheque" }] },
        { name: "bank_name", label: "Bank", showIf: (v) => v.payment_method === "BANK" },
        { name: "bank_branch", label: "Branch", showIf: (v) => v.payment_method === "BANK" },
        { name: "bank_account_name", label: "Account name", showIf: (v) => v.payment_method === "BANK" },
        { name: "bank_account_number", label: "Account number", showIf: (v) => v.payment_method === "BANK" },
        { name: "bank_swift_code", label: "SWIFT code", showIf: (v) => v.payment_method === "BANK" },
        { name: "mobile_money_number", label: "Mobile money number", type: "tel", showIf: (v) => v.payment_method === "MOBILE" },
      ],
    },
    {
      title: "Tax & statutory",
      fields: [
        { name: "tin", label: "TIN" },
        { name: "is_tax_resident", label: "Tax resident", type: "checkbox", help: "Determines which PAYE rule applies." },
        { name: "social_security_scheme", label: "Social security scheme", type: "select",
          options: [{ value: "NSSF", label: "NSSF" }, { value: "PSSSF", label: "PSSSF" }, { value: "NONE", label: "Not a member" }, { value: "OTHER", label: "Other" }] },
        { name: "social_security_number", label: "Social security number" },
        { name: "wcf_number", label: "WCF number" },
      ],
    },
    {
      title: "Emergency contact",
      fields: [
        { name: "emergency_contact_name", label: "Name" },
        { name: "emergency_contact_phone", label: "Phone", type: "tel" },
        { name: "emergency_contact_relationship", label: "Relationship" },
      ],
    },
  ];
  const allFields = sections.flatMap((s) => s.fields);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErrors({});
    setFormError("");
    try {
      const payload = toPayload(allFields, values);
      const r = editing ? await api.patch(`/employees/${id}/`, payload) : await api.post("/employees/", payload);
      qc.invalidateQueries({ queryKey: ["/employees/"] });
      notify(editing ? "Employee updated." : "Employee created.");
      navigate(`/employees/${r.data.id}`);
    } catch (err) {
      setErrors(fieldErrors(err));
      setFormError(errorMessage(err));
      window.scrollTo({ top: 0, behavior: "smooth" });
    } finally {
      setBusy(false);
    }
  };

  if (editing && existing.isLoading) return <PageLoader />;
  return (
    <form onSubmit={submit} noValidate>
      <PageHeader
        title={editing ? `Edit ${values.first_name ?? ""} ${values.last_name ?? ""}` : "Add employee"}
        actions={
          <>
            <button type="button" className="btn-secondary" onClick={() => navigate(-1)}>Cancel</button>
            <button className="btn-primary" disabled={busy}>{busy && <Spinner className="h-4 w-4 text-white" />} Save</button>
          </>
        }
      />
      {formError && <div className="mb-4"><Alert>{formError}</Alert></div>}
      {!editing && (
        <div className="mb-4"><Alert kind="info">After saving, add a salary record from the employee profile (Salary tab) so the employee can be paid.</Alert></div>
      )}
      <div className="space-y-4">
        {sections.map((s) => (
          <Card key={s.title} title={s.title}>
            <FormFields fields={s.fields} values={values} errors={errors} onChange={(n, v) => setValues((st) => ({ ...st, [n]: v }))} />
          </Card>
        ))}
      </div>
    </form>
  );
}
