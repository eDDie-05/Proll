import { FileDown, Printer } from "lucide-react";
import { useParams } from "react-router-dom";
import { download, errorMessage, openPdf } from "../../api/client";
import { useToast } from "../../components/Toast";
import { Card, PageHeader } from "../../components/ui";
import { useList } from "../../lib/hooks";
import { ItemBreakdown } from "../payroll/ItemBreakdown";

export default function PayslipPreview() {
  const { itemId } = useParams();
  const notify = useToast();
  const slip = useList<any>("/payslips/", { item: itemId });
  const s = slip.data?.results[0];
  return (
    <div>
      <PageHeader
        title="Payslip preview"
        subtitle={s ? s.payslip_number : "Payslip not generated yet — generate it from the payroll period."}
        actions={s && (
          <>
            <button className="btn-secondary" onClick={() => openPdf(`/payslips/${s.id}/pdf/`)}><Printer className="h-4 w-4" /> Print</button>
            <button className="btn-primary" onClick={() => download(`/payslips/${s.id}/pdf/`, `${s.payslip_number}.pdf`).catch((e) => notify(errorMessage(e), "error"))}>
              <FileDown className="h-4 w-4" /> Download PDF
            </button>
          </>
        )}
      />
      <Card><ItemBreakdown itemId={Number(itemId)} /></Card>
    </div>
  );
}
