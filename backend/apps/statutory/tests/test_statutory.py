import datetime
from decimal import Decimal as D

import pytest
from django.core.management import call_command

from apps.core.models import AuditLog
from apps.payroll import engine
from apps.payroll.models import PayrollPeriod
from apps.statutory import calculator
from apps.statutory.models import StatutoryRule, TaxBracket
from conftest import make_rule

pytestmark = pytest.mark.django_db

PAYE = {
    "code": "PAYE_X", "name": "PAYE test", "category": "TAX", "party": "EMPLOYEE", "method": "PROGRESSIVE",
    "base": "TAXABLE_INCOME", "effective_from": "2026-07-01", "source_name": "Test",
    "brackets": [{"lower_bound": "0", "upper_bound": "100000", "rate": "0"},
                 {"lower_bound": "100000", "upper_bound": None, "rate": "10"}],
}


def test_progressive_tax_math():
    B = type("B", (), {})
    def b(lo, hi, r):
        x = B(); x.lower_bound, x.upper_bound, x.rate = D(lo), (None if hi is None else D(hi)), D(r); return x
    brackets = [b(0, 100, 0), b(100, 500, 10), b(500, None, 20)]
    assert calculator.progressive_tax(D("50"), brackets)[0] == D("0.00")
    assert calculator.progressive_tax(D("500"), brackets)[0] == D("40.00")
    assert calculator.progressive_tax(D("900"), brackets)[0] == D("120.00")
    assert calculator.progressive_tax(D("-5"), brackets)[0] == D("0.00")


def test_flat_rule_caps():
    rule = make_rule(code="R", name="R", rate=D("10"), base_ceiling=D("1000"), min_amount=D("5"), max_amount=D("80"))
    assert calculator.calculate(rule, D("500"))[0] == D("50.00")
    assert calculator.calculate(rule, D("5000"))[0] == D("80.00")
    assert calculator.calculate(rule, D("10"))[0] == D("5.00")
    assert calculator.calculate(rule, D("0"))[0] == D("0.00")


def test_create_rule_via_api_and_validation(admin_user, client_for):
    c = client_for(admin_user)
    r = c.post("/api/statutory-rules/", PAYE, format="json")
    assert r.status_code == 201, r.data
    assert r.data["version"] == 1 and r.data["verification_status"] == "UNVERIFIED"
    gap = {**PAYE, "effective_from": "2030-01-01",
           "brackets": [{"lower_bound": "0", "upper_bound": "100", "rate": "0"},
                        {"lower_bound": "200", "upper_bound": None, "rate": "10"}]}
    assert c.post("/api/statutory-rules/", gap, format="json").status_code == 400
    overlap = {**PAYE, "effective_from": "2026-08-01"}
    assert c.post("/api/statutory-rules/", overlap, format="json").status_code == 400
    flat_no_rate = {**PAYE, "code": "Z", "method": "FLAT_RATE", "brackets": []}
    assert c.post("/api/statutory-rules/", flat_no_rate, format="json").status_code == 400


def test_rule_permissions(make_user, client_for):
    hr = client_for(make_user("HR_MANAGER", "hr"))
    assert hr.get("/api/statutory-rules/").status_code == 200
    assert hr.post("/api/statutory-rules/", PAYE, format="json").status_code == 403
    officer = client_for(make_user("PAYROLL_OFFICER", "po"))
    rule = make_rule(code="Q", name="Q", rate=D("1"), verification_status="UNVERIFIED")
    assert officer.post(f"/api/statutory-rules/{rule.id}/verify/", {"verification_notes": "x"}).status_code == 403


def test_verify_and_edit_resets_verification(admin_user, client_for):
    c = client_for(admin_user)
    rid = c.post("/api/statutory-rules/", PAYE, format="json").data["id"]
    assert c.post(f"/api/statutory-rules/{rid}/verify/", {}, format="json").status_code == 400  # notes required
    r = c.post(f"/api/statutory-rules/{rid}/verify/", {"verification_notes": "Checked TRA site"}, format="json")
    assert r.data["verification_status"] == "VERIFIED" and r.data["verified_by_name"] == "admin"
    r = c.patch(f"/api/statutory-rules/{rid}/", {"brackets": [{"lower_bound": "0", "upper_bound": None, "rate": "5"}]},
                format="json")
    assert r.status_code == 200 and r.data["verification_status"] == "UNVERIFIED"
    assert AuditLog.objects.filter(model="statutory.StatutoryRule", object_id=str(rid), action="UPDATE").count() >= 2


def test_used_rule_is_locked_and_new_version(admin_user, client_for, make_employee, test_rules):
    make_employee(1_000_000)
    p = PayrollPeriod.objects.create(name="Sep", start_date=datetime.date(2026, 9, 1), end_date=datetime.date(2026, 9, 30))
    engine.calculate_period(p, admin_user)
    c = client_for(admin_user)
    rule = test_rules["ss_ee"]
    r = c.patch(f"/api/statutory-rules/{rule.id}/", {"rate": "12"}, format="json")
    assert r.status_code == 400 and "locked" in str(r.data)
    assert c.patch(f"/api/statutory-rules/{rule.id}/", {"description": "note"}, format="json").status_code == 200
    r = c.post(f"/api/statutory-rules/{rule.id}/new-version/", {"effective_from": "2027-01-01"}, format="json")
    assert r.status_code == 201, r.data
    assert r.data["version"] == 2 and r.data["verification_status"] == "UNVERIFIED"
    rule.refresh_from_db()
    assert rule.effective_to == datetime.date(2026, 12, 31)
    new_id = r.data["id"]
    assert c.patch(f"/api/statutory-rules/{new_id}/", {"rate": "12"}, format="json").status_code == 200
    in_force = c.get("/api/statutory-rules/in-force/?date=2027-02-01").data
    assert {x["code"]: x["rate"] for x in in_force}["SS_EE"] == "12.0000"


def test_seed_command_creates_unverified_rules(db):
    call_command("seed_tz_statutory")
    rules = StatutoryRule.objects.all()
    assert rules.count() >= 5
    assert not rules.filter(verification_status="VERIFIED").exists()
    assert all(r.source_url and r.source_reference for r in rules)
    paye = rules.get(code="PAYE_RESIDENT")
    paye.validate_brackets()
    call_command("seed_tz_statutory")  # idempotent
    assert StatutoryRule.objects.count() == rules.count()
