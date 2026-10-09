import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, errorMessage, fieldErrors } from "../../api/client";
import { FormFields, hasFile, toFormData, toPayload, type FieldDef } from "../../components/Form";
import { useToast } from "../../components/Toast";
import { Alert, Card, PageHeader, PageLoader, Spinner } from "../../components/ui";

const FIELDS: FieldDef[] = [
  { name: "name", label: "Company name", required: true },
  { name: "tin", label: "Company TIN" },
  { name: "phone", label: "Phone", type: "tel" },
  { name: "email", label: "Email", type: "email" },
  { name: "website", label: "Website" },
  { name: "currency", label: "Currency", required: true },
  { name: "nssf_employer_number", label: "NSSF employer number" },
  { name: "wcf_registration_number", label: "WCF registration number" },
  { name: "address", label: "Address", type: "textarea", colSpan: 2 },
  { name: "logo", label: "Logo (PNG/JPG, max 5 MB)", type: "file" },
  { name: "proration_basis", label: "Pro-ration basis", type: "select", options: [
    { value: "CALENDAR_DAYS", label: "Calendar days in period" }, { value: "FIXED_30_DAYS", label: "Fixed 30-day month" }],
    help: "How partial-month salaries are computed for joiners/leavers and unpaid leave." },
  { name: "rounding_decimals", label: "Rounding decimals", type: "number", min: "0" },
  { name: "require_verified_rules_for_approval", label: "Block approval when unverified statutory rules are used", type: "checkbox", colSpan: 2 },
  { name: "enforce_segregation_of_duties", label: "Preparer cannot approve the same payroll", type: "checkbox", colSpan: 2 },
  { name: "payslip_footer", label: "Payslip footer", type: "textarea", colSpan: 2 },
  { name: "statutory_disclaimer", label: "Statutory disclaimer (on reports)", type: "textarea", colSpan: 2 },
];

export default function CompanySettingsPage() {
  const notify = useToast();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["company"], queryFn: async () => (await api.get("/company-settings/")).data });
  const [values, setValues] = useState<Record<string, any>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  useEffect(() => { if (q.data) setValues({ ...q.data, logo: null }); }, [q.data]);
  const save = useMutation({
    mutationFn: () => {
      const p = toPayload(FIELDS, values);
      return api.patch("/company-settings/", hasFile(p) ? toFormData(p) : p);
    },
    onSuccess: () => { notify("Company settings saved."); setError(""); setErrors({}); qc.invalidateQueries({ queryKey: ["company"] }); },
    onError: (e) => { setErrors(fieldErrors(e)); setError(errorMessage(e)); },
  });
  if (q.isLoading) return <PageLoader />;
  return (
    <div>
      <PageHeader title="Company settings" actions={
        <button className="btn-primary" disabled={save.isPending} onClick={() => save.mutate()}>{save.isPending && <Spinner className="h-4 w-4 text-white" />} Save</button>
      } />
      {error && <div className="mb-4"><Alert>{error}</Alert></div>}
      <Card>
        {q.data?.logo && <img src={q.data.logo} alt="Company logo" className="mb-4 h-16 object-contain" />}
        <FormFields fields={FIELDS} values={values} errors={errors} onChange={(n, v) => setValues((s) => ({ ...s, [n]: v }))} />
      </Card>
    </div>
  );
}
