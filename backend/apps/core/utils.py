from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0")


def to_decimal(value):
    if value is None:
        return ZERO
    return value if isinstance(value, Decimal) else Decimal(str(value))


def money(value, places=2):
    quant = Decimal(1).scaleb(-places)
    return to_decimal(value).quantize(quant, rounding=ROUND_HALF_UP)


def overlap_days(a_start, a_end, b_start, b_end):
    """Inclusive day overlap between [a_start, a_end] and [b_start, b_end]. None end = open."""
    start = max(a_start, b_start)
    ends = [d for d in (a_end, b_end) if d is not None]
    end = min(ends) if ends else None
    if end is None:
        return None
    return max((end - start).days + 1, 0)
