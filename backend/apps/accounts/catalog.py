"""Canonical permission codes and default role definitions."""

PERMISSIONS = {
    "users.manage": "Manage user accounts",
    "roles.manage": "Manage roles and permissions",
    "company.manage": "Configure company settings",
    "statutory.view": "View statutory rules",
    "statutory.manage": "Configure statutory rules",
    "statutory.verify": "Mark statutory rules as verified",
    "audit.view": "View audit logs",
    "employees.view": "View employee directory",
    "employees.view_sensitive": "View sensitive employee data (bank, TIN, social security)",
    "employees.manage": "Create and edit employees",
    "contracts.manage": "Manage employment contracts",
    "salary.view": "View salary records",
    "salary.manage": "Manage salary records",
    "allowances.manage": "Manage allowances",
    "deductions.manage": "Manage deductions",
    "loans.view": "View loans and advances",
    "loans.manage": "Manage loans and advances",
    "leave.view": "View leave records",
    "leave.manage": "Manage leave records",
    "payroll.view": "View payroll (all states)",
    "payroll.view_approved": "View approved payroll summaries",
    "payroll.prepare": "Create, calculate and submit payroll",
    "payroll.approve": "Approve or reject payroll",
    "payroll.close": "Close payroll periods",
    "payroll.adjust": "Create payroll adjustments",
    "payslips.generate": "Generate payslips",
    "payments.view": "View payment information",
    "payments.manage": "Record salary payments",
    "payments.export": "Export bank payment files",
    "reports.view": "View all payroll reports",
    "reports.view_department": "View department reports",
    "reports.export": "Export reports",
    "self.view": "View own profile and payslips",
}

ROLES = {
    "SUPER_ADMIN": {
        "name": "Super Administrator",
        "permissions": list(PERMISSIONS),
    },
    "HR_MANAGER": {
        "name": "HR Manager",
        "permissions": [
            "employees.view", "employees.view_sensitive", "employees.manage", "contracts.manage",
            "salary.view", "salary.manage", "allowances.manage", "deductions.manage",
            "loans.view", "loans.manage", "leave.view", "leave.manage", "payroll.view",
            "statutory.view", "self.view",
        ],
    },
    "PAYROLL_OFFICER": {
        "name": "Payroll Officer",
        "permissions": [
            "employees.view", "employees.view_sensitive", "salary.view", "loans.view", "leave.view",
            "payroll.view", "payroll.prepare", "payroll.adjust", "payroll.close", "payslips.generate",
            "payments.view", "payments.manage", "payments.export", "reports.view", "reports.export",
            "statutory.view", "self.view",
        ],
    },
    "FINANCE_OFFICER": {
        "name": "Finance Officer",
        "permissions": [
            "employees.view", "payroll.view", "payments.view", "payments.manage", "payments.export",
            "reports.view", "reports.export", "loans.view", "statutory.view", "self.view",
        ],
    },
    "MANAGER": {
        "name": "Manager",
        "permissions": [
            "employees.view", "payroll.view_approved", "payroll.approve", "reports.view_department",
            "self.view",
        ],
    },
    "EMPLOYEE": {
        "name": "Employee",
        "permissions": ["self.view"],
    },
}
