"""
Load a DRAFT set of Tanzania statutory rules.

Every rule is created UNVERIFIED. Figures come from secondary sources consulted on 2026-09-26 and must
be checked by an authorised administrator against current official publications (TRA, NSSF, PSSSF, WCF)
before use. Payroll approval is blocked while unverified rules are in use (see Company Settings).
"""
import datetime
from decimal import Decimal as D

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.statutory.models import StatutoryRule, TaxBracket

RETRIEVED = datetime.date(2026, 9, 26)
EFFECTIVE = datetime.date(2026, 7, 1)

RULES = [
    {
        "code": "PAYE_RESIDENT", "name": "PAYE - resident individual (monthly)", "category": "TAX", "party": "EMPLOYEE",
        "method": "PROGRESSIVE", "base": "TAXABLE_INCOME", "residency": "RESIDENT", "calculation_order": 50,
        "source_name": "PwC Worldwide Tax Summaries - Tanzania (last reviewed 09 Sep 2026); official source: TRA",
        "source_url": "https://taxsummaries.pwc.com/tanzania/individual/taxes-on-personal-income",
        "source_reference": "Income Tax Act (Cap. 332), First Schedule - resident individual rates",
        "verification_notes": (
            "UNVERIFIED DRAFT. Conflicting secondary sources: PwC lists 8% on TZS 270,000-520,000 "
            "(tax at 520,000 = 20,000), while some calculators list 9% (22,500). Confirm the current "
            "band rates with TRA (https://www.tra.go.tz) and the latest Finance Act before verifying."
        ),
        "brackets": [(0, 270000, 0), (270000, 520000, 8), (520000, 760000, 20), (760000, 1000000, 25), (1000000, None, 30)],
    },
    {
        "code": "PAYE_NON_RESIDENT", "name": "PAYE - non-resident employee", "category": "TAX", "party": "EMPLOYEE",
        "method": "FLAT_RATE", "rate": D("15"), "base": "TAXABLE_INCOME", "residency": "NON_RESIDENT",
        "calculation_order": 50,
        "source_name": "PwC Worldwide Tax Summaries - Tanzania (last reviewed 09 Sep 2026); official source: TRA",
        "source_url": "https://taxsummaries.pwc.com/tanzania/individual/taxes-on-personal-income",
        "source_reference": "Income Tax Act (Cap. 332) - non-resident employment income",
        "verification_notes": "UNVERIFIED DRAFT. Confirm rate and base with TRA before verifying.",
    },
    {
        "code": "NSSF_EMPLOYEE", "name": "NSSF - employee share", "category": "SOCIAL_SECURITY", "party": "EMPLOYEE",
        "method": "FLAT_RATE", "rate": D("10"), "base": "SOCIAL_SECURITY_BASE", "applies_to_schemes": ["NSSF"],
        "reduces_taxable_income": True, "calculation_order": 10,
        "source_name": "National Social Security Fund (NSSF) - Rate of Contributions",
        "source_url": "https://www.nssf.go.tz/pages/rate-of-contributions",
        "source_reference": "NSSF: 20% of gross salary jointly; employee share not to exceed 10%",
        "verification_notes": (
            "UNVERIFIED DRAFT. NSSF states total 20% of gross salary with the employee share capped at 10%. "
            "Confirm the contribution base (which earnings count) and whether contributions are deductible "
            "for PAYE with NSSF/TRA before verifying."
        ),
    },
    {
        "code": "NSSF_EMPLOYER", "name": "NSSF - employer share", "category": "SOCIAL_SECURITY", "party": "EMPLOYER",
        "method": "FLAT_RATE", "rate": D("10"), "base": "SOCIAL_SECURITY_BASE", "applies_to_schemes": ["NSSF"],
        "calculation_order": 10,
        "source_name": "National Social Security Fund (NSSF) - Rate of Contributions",
        "source_url": "https://www.nssf.go.tz/pages/rate-of-contributions",
        "source_reference": "NSSF: 20% of gross salary jointly (employer remits total)",
        "verification_notes": "UNVERIFIED DRAFT. Confirm with NSSF before verifying.",
    },
    {
        "code": "WCF", "name": "Workers Compensation Fund contribution", "category": "LEVY", "party": "EMPLOYER",
        "method": "FLAT_RATE", "rate": D("0.5"), "base": "CASH_EMOLUMENTS", "calculation_order": 80,
        "source_name": "PwC Worldwide Tax Summaries - Tanzania, Other taxes (last reviewed 09 Sep 2026); official: WCF",
        "source_url": "https://taxsummaries.pwc.com/tanzania/individual/other-taxes",
        "source_reference": "Workers Compensation Act (Cap. 263) - employer contribution",
        "verification_notes": "UNVERIFIED DRAFT. Private-sector rate reported as 0.5%. Confirm with WCF (https://www.wcf.go.tz).",
    },
    {
        "code": "SDL", "name": "Skills and Development Levy", "category": "LEVY", "party": "EMPLOYER",
        "method": "FLAT_RATE", "rate": D("3.5"), "base": "CASH_EMOLUMENTS", "min_employee_count": 10,
        "calculation_order": 80,
        "source_name": "PwC Worldwide Tax Summaries - Tanzania, Other taxes (last reviewed 09 Sep 2026); official: TRA",
        "source_url": "https://taxsummaries.pwc.com/tanzania/individual/other-taxes",
        "source_reference": "Vocational Education and Training Act - SDL on gross emoluments",
        "verification_notes": (
            "UNVERIFIED DRAFT. Reported as 3.5% of gross cash emoluments for employers with 10+ employees; "
            "certain employers are exempt. Confirm with TRA before verifying."
        ),
    },
]


class Command(BaseCommand):
    help = "Seed UNVERIFIED draft Tanzania statutory rules (skips codes that already exist)."

    @transaction.atomic
    def handle(self, *args, **opts):
        created = 0
        for spec in RULES:
            spec = dict(spec)
            brackets = spec.pop("brackets", [])
            if StatutoryRule.objects.filter(code=spec["code"]).exists():
                self.stdout.write(f"skip {spec['code']} (exists)")
                continue
            rule = StatutoryRule.objects.create(
                effective_from=EFFECTIVE, source_retrieved_on=RETRIEVED,
                verification_status=StatutoryRule.Verification.UNVERIFIED, **spec,
            )
            TaxBracket.objects.bulk_create([
                TaxBracket(rule=rule, lower_bound=D(lo), upper_bound=None if hi is None else D(hi), rate=D(r))
                for lo, hi, r in brackets
            ])
            rule.validate_brackets()
            created += 1
        self.stdout.write(self.style.WARNING(
            f"Created {created} UNVERIFIED rules. Verify each against official sources before approving payroll."
        ))
