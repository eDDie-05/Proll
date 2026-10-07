export interface Me {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string | null;
  role_name: string | null;
  permissions: string[];
  employee_id: number | null;
  must_change_password: boolean;
}

export type PeriodStatus = "DRAFT" | "CALCULATED" | "REVIEW" | "APPROVED" | "PAID" | "CLOSED";

export interface PayrollRun {
  id: number;
  run_number: number;
  calculated_by_name: string;
  calculated_at: string;
  employee_count: number;
  total_gross: string;
  total_employee_deductions: string;
  total_paye: string;
  total_net: string;
  total_employer_contributions: string;
  total_employer_cost: string;
  warnings: string[];
  rules_used: { id: number; code: string; version: number; verification_status: string }[];
}

export interface PayrollPeriod {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  pay_date: string | null;
  status: PeriodStatus;
  notes: string;
  current_run: PayrollRun | null;
  calculated_by_name: string | null;
  calculated_at: string | null;
  submitted_by_name: string | null;
  submitted_at: string | null;
  approved_by_name: string | null;
  approved_at: string | null;
  paid_by_name: string | null;
  paid_at: string | null;
  closed_by_name: string | null;
  closed_at: string | null;
}

export interface PayrollItem {
  id: number;
  employee: number;
  employee_number: string;
  employee_name: string;
  department_name: string;
  job_title: string;
  days_employed: string;
  days_in_period: string;
  monthly_basic_salary: string;
  basic_earned: string;
  gross_earnings: string;
  taxable_income: string;
  paye: string;
  total_statutory_deductions: string;
  total_other_deductions: string;
  total_deductions: string;
  net_salary: string;
  total_employer_contributions: string;
  employer_total_cost: string;
  warnings: string[];
  payment_status: string | null;
  has_payslip: boolean;
}

export interface PayrollLine {
  id: number;
  category: "EARNING" | "DEDUCTION" | "EMPLOYER";
  sub_category: string;
  code: string;
  name: string;
  amount: string;
  is_taxable: boolean;
  is_statutory: boolean;
  reduces_taxable_income: boolean;
  statutory_rule: number | null;
  statutory_rule_version: number | null;
  source_type: string;
  detail: Record<string, any>;
}

export interface PayrollItemDetail extends PayrollItem {
  lines: PayrollLine[];
  period: { id: number; name: string; status: PeriodStatus; start_date: string; end_date: string; run_number: number };
  social_security_base: string;
  cash_emoluments: string;
  proration_factor: string;
  payment_method: string;
  bank_name: string;
}

export interface Employee {
  id: number;
  employee_number: string;
  first_name: string;
  middle_name: string;
  last_name: string;
  full_name: string;
  email: string;
  phone: string;
  department: number;
  department_name: string;
  position: number | null;
  position_title: string | null;
  employment_type: number;
  employment_type_name: string;
  employment_start_date: string;
  employment_end_date: string | null;
  status: string;
  current_basic_salary?: string | null;
  [key: string]: any;
}

export interface ReportData {
  title: string;
  subtitle: string;
  columns: { key: string; label: string; type: "text" | "money" | "int" | "date" }[];
  rows: Record<string, any>[];
  totals: Record<string, any> | null;
  summary: { label: string; value: any }[] | null;
}
