"""Pure calculation of a single statutory rule against a base amount. No database writes."""
from decimal import Decimal

from apps.core.utils import ZERO, money

from .models import StatutoryRule

HUNDRED = Decimal("100")


def progressive_tax(income, brackets):
    """Marginal-rate tax. `brackets`: iterable of objects with lower_bound, upper_bound (None=open), rate (%)."""
    income = max(income, ZERO)
    total = ZERO
    detail = []
    for b in sorted(brackets, key=lambda x: x.lower_bound):
        if income <= b.lower_bound:
            break
        top = income if b.upper_bound is None else min(income, b.upper_bound)
        portion = top - b.lower_bound
        tax = portion * b.rate / HUNDRED
        total += tax
        detail.append({
            "lower": str(b.lower_bound), "upper": None if b.upper_bound is None else str(b.upper_bound),
            "rate": str(b.rate), "taxable_portion": str(money(portion)), "tax": str(money(tax)),
        })
    return money(total), detail


def calculate(rule: StatutoryRule, base_amount):
    """Return (amount, detail_dict) for `rule` applied to `base_amount`."""
    base_amount = max(base_amount, ZERO)
    applied_base = base_amount
    if rule.base_ceiling is not None and applied_base > rule.base_ceiling:
        applied_base = rule.base_ceiling
    detail = {
        "rule": rule.code, "version": rule.version, "method": rule.method, "base_type": rule.base,
        "base_amount": str(money(base_amount)), "applied_base": str(money(applied_base)),
        "effective_from": rule.effective_from.isoformat(),
        "verification_status": rule.verification_status,
    }
    if rule.method == StatutoryRule.Method.PROGRESSIVE:
        amount, bands = progressive_tax(applied_base, rule.brackets.all())
        detail["bands"] = bands
    elif rule.method == StatutoryRule.Method.FLAT_RATE:
        amount = money(applied_base * rule.rate / HUNDRED)
        detail["rate"] = str(rule.rate)
    else:
        amount = money(rule.fixed_amount)
    if rule.min_amount is not None and amount < rule.min_amount and base_amount > 0:
        amount = money(rule.min_amount)
        detail["min_applied"] = True
    if rule.max_amount is not None and amount > rule.max_amount:
        amount = money(rule.max_amount)
        detail["max_applied"] = True
    detail["amount"] = str(amount)
    return amount, detail
