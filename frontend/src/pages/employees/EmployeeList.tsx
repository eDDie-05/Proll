import { Plus } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { DataTable, Pagination, SearchBox } from "../../components/DataTable";
import { Alert, Card, PageHeader, StatusBadge } from "../../components/ui";
import { date } from "../../lib/format";
import { useList, useOptions } from "../../lib/hooks";
import type { Employee } from "../../lib/types";

export const EMPLOYEE_STATUSES = ["ACTIVE", "ON_LEAVE", "SUSPENDED", "TERMINATED", "RESIGNED", "RETIRED"];

export default function EmployeeList() {
  const { can } = useAuth();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [department, setDepartment] = useState("");
  const [status, setStatus] = useState("");
  const depts = useOptions("/departments/", (d) => d.name);
  const list = useList<Employee>("/employees/", { page, search, department, status });

  return (
    <div>
      <PageHeader
        title="Employees"
        subtitle="Employee directory"
        actions={can("employees.manage") && (
          <Link to="/employees/new" className="btn-primary"><Plus className="h-4 w-4" /> Add employee</Link>
        )}
      />
      <Card>
        <div className="mb-3 flex flex-col gap-2 sm:flex-row">
          <SearchBox value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Name, ID, email..." />
          <select className="input sm:w-48" value={department} onChange={(e) => { setDepartment(e.target.value); setPage(1); }} aria-label="Department">
            <option value="">All departments</option>
            {depts.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
          </select>
          <select className="input sm:w-40" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} aria-label="Status">
            <option value="">All statuses</option>
            {EMPLOYEE_STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
          </select>
        </div>
        {list.isError && <Alert>{errorMessage(list.error)}</Alert>}
        <DataTable
          loading={list.isLoading}
          rows={list.data?.results}
          onRowClick={(e) => navigate(`/employees/${e.id}`)}
          columns={[
            { key: "employee_number", header: "Emp. ID", className: "font-medium text-brand-700" },
            { key: "full_name", header: "Name" },
            { key: "department_name", header: "Department" },
            { key: "position_title", header: "Job title", hideOnMobile: true, render: (e) => e.position_title || "-" },
            { key: "employment_type_name", header: "Type", hideOnMobile: true },
            { key: "employment_start_date", header: "Start date", hideOnMobile: true, render: (e) => date(e.employment_start_date) },
            { key: "status", header: "Status", render: (e) => <StatusBadge status={e.status} /> },
          ]}
        />
        {list.data && <Pagination page={page} count={list.data.count} onPage={setPage} />}
      </Card>
    </div>
  );
}
