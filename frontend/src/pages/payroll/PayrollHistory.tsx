import { ReportView } from "../reports/Reports";

export default function PayrollHistory() {
  return <ReportView reportKey="history" title="Payroll history" needsPeriod={false} />;
}
