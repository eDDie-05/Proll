"""
Seed reference data (departments, employment types, allowance/deduction/leave types, a generic bank format).
With --demo, also create sample employees and one user per role (password from DEMO_PASSWORD env var).

Allowance tax treatment below is a neutral starting point and MUST be reviewed by the payroll team.
"""
import datetime
import os
from decimal import Decimal as D

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Role, User
from apps.accounts.services import sync_permissions_and_roles
from apps.compensation.models import AllowanceType, DeductionType, EmployeeAllowance
from apps.employees.models import Department, Employee, EmploymentType, Position, SalaryRecord
from apps.leave.models import LeaveType
from apps.payroll.models import BankExportFormat

DEPARTMENTS = [("ADM", "Administration"), ("FIN", "Finance"), ("HR", "Human Resources"), ("OPS", "Operations"),
               ("SAL", "Sales & Marketing"), ("ICT", "ICT")]
EMPLOYMENT_TYPES = [("PERM", "Permanent"), ("CONT", "Contract"), ("TEMP", "Temporary"), ("PART", "Part-time")]
ALLOWANCES = [
    # code, name, category, calc, taxable, ss_base, recurring
    ("HOUSING", "Housing allowance", "ALLOWANCE", "FIXED", True, True, True),
    ("TRANSPORT", "Transport allowance", "ALLOWANCE", "FIXED", True, True, True),
    ("COMMUNICATION", "Communication allowance", "ALLOWANCE", "FIXED", True, True, True),
    ("MEAL", "Meal allowance", "ALLOWANCE", "FIXED", True, True, True),
    ("RESPONSIBILITY", "Responsibility allowance", "ALLOWANCE", "PERCENT_OF_BASIC", True, True, True),
    ("OVERTIME", "Overtime", "OVERTIME", "HOURS_X_RATE", True, True, False),
    ("BONUS", "Bonus", "BONUS", "FIXED", True, True, False),
    ("COMMISSION", "Commission", "COMMISSION", "FIXED", True, True, False),
    ("OTHER", "Other allowance", "OTHER", "FIXED", True, True, False),
]
DEDUCTIONS = [
    ("INSURANCE", "Medical insurance", "INSURANCE", False),
    ("ADVANCE", "Salary advance recovery", "ADVANCE", False),
    ("UNION", "Trade union dues", "UNION", False),
    ("OTHER_DED", "Other approved deduction", "OTHER", False),
]
LEAVE = [("ANNUAL", "Annual leave", "NONE", 28), ("SICK", "Sick leave", "NONE", None),
         ("MATERNITY", "Maternity leave", "NONE", None), ("PATERNITY", "Paternity leave", "NONE", None),
         ("UNPAID", "Unpaid leave", "DEDUCT_BASIC_PRORATA", None)]


class Command(BaseCommand):
    help = "Seed reference data; --demo adds sample employees and users."

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true")

    @transaction.atomic
    def handle(self, *args, **opts):
        sync_permissions_and_roles()
        depts = {c: Department.objects.get_or_create(code=c, defaults={"name": n})[0] for c, n in DEPARTMENTS}
        types = {c: EmploymentType.objects.get_or_create(code=c, defaults={"name": n})[0] for c, n in EMPLOYMENT_TYPES}
        for code, name, cat, calc, taxable, ss, rec in ALLOWANCES:
            AllowanceType.objects.get_or_create(code=code, defaults=dict(
                name=name, category=cat, calculation_type=calc, is_taxable=taxable, is_social_security_base=ss,
                is_recurring=rec, treatment_reference="REVIEW REQUIRED: confirm tax/contribution treatment with TRA/NSSF"))
        for code, name, cat, pre in DEDUCTIONS:
            DeductionType.objects.get_or_create(code=code, defaults=dict(name=name, category=cat, reduces_taxable_income=pre))
        for code, name, effect, days in LEAVE:
            LeaveType.objects.get_or_create(code=code, defaults=dict(name=name, payroll_effect=effect,
                                                                     annual_entitlement_days=days))
        BankExportFormat.objects.get_or_create(name="Generic CSV (bank transfer)", defaults=dict(
            description="Neutral template. Replace with your bank's required layout.",
            columns=[{"header": "Account Number", "field": "bank_account_number"},
                     {"header": "Account Name", "field": "bank_account_name"},
                     {"header": "Bank", "field": "bank_name"}, {"header": "Branch", "field": "bank_branch"},
                     {"header": "Amount", "field": "amount"}, {"header": "Currency", "field": "currency"},
                     {"header": "Reference", "field": "reference"}, {"header": "Narration", "field": "narration"}]))
        call_command("seed_tz_statutory", stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS("Reference data seeded."))
        if opts["demo"]:
            self._demo(depts, types)

    def _demo(self, depts, types):
        password = os.environ.get("DEMO_PASSWORD")
        if not password:
            raise CommandError("Set DEMO_PASSWORD to create demo users.")
        roles = {r.code: r for r in Role.objects.all()}
        users = {}
        for code, uname in [("SUPER_ADMIN", "admin"), ("HR_MANAGER", "hr"), ("PAYROLL_OFFICER", "payroll"),
                            ("FINANCE_OFFICER", "finance"), ("MANAGER", "manager"), ("EMPLOYEE", "employee")]:
            u, created = User.objects.get_or_create(username=uname, defaults=dict(
                email=f"{uname}@bravado.example", role=roles[code], is_staff=code == "SUPER_ADMIN",
                is_superuser=code == "SUPER_ADMIN", first_name=uname.title()))
            if created:
                u.set_password(password)
                u.save()
            users[uname] = u
        people = [
            ("BRV0001", "John", "Doe", "FIN", "Accountant", 1_500_000, "manager"),
            ("BRV0002", "Asha", "Mushi", "HR", "HR Officer", 1_200_000, "employee"),
            ("BRV0003", "Baraka", "Mwakyusa", "OPS", "Operations Supervisor", 1_800_000, None),
            ("BRV0004", "Neema", "Kimaro", "SAL", "Sales Executive", 950_000, None),
            ("BRV0005", "Juma", "Hassan", "ICT", "Systems Administrator", 2_200_000, None),
            ("BRV0006", "Rehema", "Said", "ADM", "Office Administrator", 750_000, None),
            ("BRV0007", "Emmanuel", "Mollel", "OPS", "Driver", 600_000, None),
            ("BRV0008", "Grace", "Lyimo", "FIN", "Finance Manager", 3_500_000, None),
        ]
        housing = AllowanceType.objects.get(code="HOUSING")
        transport = AllowanceType.objects.get(code="TRANSPORT")
        start = datetime.date(2026, 1, 1)
        for i, (num, first, last, dept, title, basic, uname) in enumerate(people):
            pos, _ = Position.objects.get_or_create(title=title, department=depts[dept])
            emp, created = Employee.objects.get_or_create(employee_number=num, defaults=dict(
                first_name=first, last_name=last, department=depts[dept], position=pos, employment_type=types["PERM"],
                employment_start_date=start, bank_name="Demo Bank", bank_account_name=f"{first} {last}",
                bank_account_number=f"01500{i:07d}", email=f"{first.lower()}@bravado.example",
                user=users.get(uname) if uname else None, social_security_number=f"DEMO-SS-{i:04d}"))
            if created:
                SalaryRecord.create_new(emp, D(basic), start, reason="Demo data")
                EmployeeAllowance.objects.create(employee=emp, allowance_type=housing, amount=D(basic) * D("0.15"),
                                                 effective_from=start)
                EmployeeAllowance.objects.create(employee=emp, allowance_type=transport, amount=D("100000"),
                                                 effective_from=start)
        self.stdout.write(self.style.SUCCESS(
            "Demo users: admin, hr, payroll, finance, manager, employee (password from DEMO_PASSWORD)."))
