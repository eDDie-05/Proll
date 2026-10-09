import datetime
from decimal import Decimal as D

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.accounts.services import sync_permissions_and_roles
from apps.core.models import CompanySettings
from apps.employees.models import Department, Employee, EmploymentType, Position, SalaryRecord
from apps.statutory.models import StatutoryRule, TaxBracket

PASSWORD = "Str0ng-Test-Pass!"


@pytest.fixture(autouse=True)
def _settings(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}
    settings.SECURE_SSL_REDIRECT = False


@pytest.fixture
def roles(db):
    sync_permissions_and_roles()
    return {r.code: r for r in Role.objects.all()}


@pytest.fixture
def make_user(roles):
    def _make(role_code, username=None, **extra):
        username = username or role_code.lower()
        user = User(username=username, email=f"{username}@bravado.test", role=roles[role_code], **extra)
        user.set_password(PASSWORD)
        user.save()
        return user
    return _make


@pytest.fixture
def client_for():
    def _client(user):
        c = APIClient()
        c.force_authenticate(user)
        return c
    return _client


@pytest.fixture
def admin_user(make_user):
    return make_user("SUPER_ADMIN", "admin")


@pytest.fixture
def org(db):
    dept = Department.objects.create(code="FIN", name="Finance")
    ops = Department.objects.create(code="OPS", name="Operations")
    etype = EmploymentType.objects.create(code="PERM", name="Permanent")
    pos = Position.objects.create(title="Accountant", department=dept)
    return {"dept": dept, "ops": ops, "etype": etype, "pos": pos}


@pytest.fixture
def make_employee(org):
    counter = {"n": 0}

    def _make(basic=None, start=datetime.date(2026, 1, 1), salary_from=None, **extra):
        counter["n"] += 1
        defaults = dict(
            employee_number=f"BRV{counter['n']:04d}", first_name="John", last_name=f"Doe{counter['n']}",
            department=org["dept"], position=org["pos"], employment_type=org["etype"],
            employment_start_date=start, bank_name="CRDB", bank_account_number=f"0150{counter['n']:08d}",
        )
        defaults.update(extra)
        emp = Employee.objects.create(**defaults)
        if basic is not None:
            SalaryRecord.create_new(emp, D(basic), salary_from or start)
        return emp
    return _make


def make_rule(**kw):
    brackets = kw.pop("brackets", None)
    defaults = dict(category="OTHER", party="EMPLOYEE", method="FLAT_RATE", base="GROSS",
                    effective_from=datetime.date(2026, 1, 1), verification_status="VERIFIED")
    defaults.update(kw)
    rule = StatutoryRule.objects.create(**defaults)
    for lo, hi, rate in brackets or []:
        TaxBracket.objects.create(rule=rule, lower_bound=D(lo), upper_bound=None if hi is None else D(hi), rate=D(rate))
    return rule


@pytest.fixture
def test_rules(db):
    """Simple, obviously synthetic rates for deterministic tests (not real Tanzanian rates)."""
    return {
        "ss_ee": make_rule(code="SS_EE", name="Social security (employee)", category="SOCIAL_SECURITY", rate=D("10"),
                           base="SOCIAL_SECURITY_BASE", reduces_taxable_income=True, calculation_order=10),
        "ss_er": make_rule(code="SS_ER", name="Social security (employer)", category="SOCIAL_SECURITY", party="EMPLOYER",
                           rate=D("10"), base="SOCIAL_SECURITY_BASE", calculation_order=10),
        "levy": make_rule(code="LEVY", name="Employer levy", category="LEVY", party="EMPLOYER", rate=D("1"),
                          base="CASH_EMOLUMENTS", calculation_order=80),
        "paye": make_rule(code="PAYE", name="PAYE", category="TAX", method="PROGRESSIVE", base="TAXABLE_INCOME",
                          residency="RESIDENT", calculation_order=50,
                          brackets=[(0, 100000, 0), (100000, 500000, 10), (500000, None, 20)]),
    }


@pytest.fixture
def company(db):
    return CompanySettings.load()
