"""Shared money math for the finance agents. Underscore module: skipped by the registry.

Everything here is exact Decimal arithmetic rounded once at the edge (ROUND_HALF_UP,
the way accountants and banks round), so tools never drift by a cent over a 360-month
schedule. Return values are plain floats/ints/strings so they serialise to JSON.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from ...core import ToolError

CENT = Decimal("0.01")
ZERO = Decimal("0")
MAX_ROWS = 500
MAX_MONTHS = 600  # 50 years — anything longer is "never" for practical purposes

_NUM_RE = re.compile(r"^[-+]?\(?\$?\s*[-+]?[\d,]*\.?\d+\s*%?\)?$")


def D(value, name: str = "value") -> Decimal:
    """Coerce a number-ish input (int, float, '1,234.50', '$99', '(50)', '12%') to Decimal."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise ToolError(f"{name}: expected a number, got a boolean")
    if isinstance(value, (int, float)):
        if value != value or value in (float("inf"), float("-inf")):
            raise ToolError(f"{name}: must be a finite number")
        return Decimal(str(value))
    if value is None:
        raise ToolError(f"{name}: missing")
    s = str(value).strip()
    if not s or not _NUM_RE.match(s):
        raise ToolError(f"{name}: expected a number, got {value!r}")
    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace("$", "").replace(",", "").replace("%", "").strip()
    try:
        d = Decimal(s)
    except InvalidOperation:
        raise ToolError(f"{name}: expected a number, got {value!r}") from None
    return -d if negative else d


def money(value) -> float:
    """Round to cents (half-up) and return a float for JSON."""
    return float(Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP))


def pct(value, places: int = 1) -> float:
    """Round a ratio already expressed in percent (e.g. 12.345 -> 12.3)."""
    q = Decimal(1).scaleb(-places)
    return float(Decimal(value).quantize(q, rounding=ROUND_HALF_UP))


def ratio_to_pct(ratio, places: int = 1) -> float:
    return pct(Decimal(ratio) * 100, places)


def as_rate(value, name: str = "rate") -> Decimal:
    """Accept 7, 7.0, '7%' or 0.07 and return the decimal rate 0.07.

    Anything with magnitude >= 1 is treated as a percent. 0.5 is a rate (50%), not 0.5%.
    Only for shares where a sub-1% value is implausible (gross margin, business-use %, ownership);
    use `as_pct` for churn, growth, APR, APY and fee rates.
    """
    d = D(value, name)
    if isinstance(value, str) and "%" in value:
        return d / 100
    return d / 100 if abs(d) >= 1 else d


def as_pct(value, name: str = "percent") -> Decimal:
    """A value that is always a percent: 7 -> 0.07, 0.6 -> 0.006, '0.6%' -> 0.006.

    Use for rates where sub-1% values are realistic (monthly churn/expansion/growth, APRs on promo
    loans, savings APYs, fees). `as_rate`'s "below 1 means a fraction" heuristic silently turns
    0.6% monthly expansion into 60% — never use it for those.
    """
    return D(value, name) / 100


def require_positive(value: Decimal, name: str) -> Decimal:
    if value <= 0:
        raise ToolError(f"{name} must be greater than zero (got {value})")
    return value


def require_nonneg(value: Decimal, name: str) -> Decimal:
    if value < 0:
        raise ToolError(f"{name} cannot be negative (got {value})")
    return value


def bound_rows(rows: list, name: str = "rows", limit: int = MAX_ROWS) -> list:
    if not isinstance(rows, list):
        raise ToolError(f"{name} must be a list")
    if not rows:
        raise ToolError(f"{name} is empty — nothing to compute")
    if len(rows) > limit:
        raise ToolError(f"{name}: too many items ({len(rows)}); limit is {limit}")
    return rows


def add_months(d: date, n: int) -> date:
    """Calendar month arithmetic that clamps to month end (Jan 31 + 1 month = Feb 28)."""
    y, m = divmod(d.month - 1 + n, 12)
    year, month = d.year + y, m + 1
    last = [31, 29 if _leap(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return d.replace(year=year, month=month, day=min(d.day, last))


def _leap(y: int) -> bool:
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def month_label(d: date) -> str:
    return d.strftime("%Y-%m")


def monthly_payment(principal: Decimal, annual_rate: Decimal, months: int) -> Decimal:
    """Standard amortised payment with monthly compounding. annual_rate as a decimal (0.07)."""
    if months <= 0:
        raise ToolError("term must be at least 1 month")
    r = annual_rate / 12
    if r == 0:
        return principal / months
    factor = (1 + r) ** months
    return principal * r * factor / (factor - 1)


def amortize(principal: Decimal, annual_rate: Decimal, payment: Decimal, max_months: int = MAX_MONTHS) -> dict:
    """Run a payment against a balance month by month.

    Returns months, total_interest, and whether the balance ever reaches zero. If the
    payment does not cover the first month's interest, the loan never pays off and
    `pays_off` is False with the minimum payment that would make progress.
    """
    r = annual_rate / 12
    first_interest = (principal * r).quantize(CENT, rounding=ROUND_HALF_UP)
    if payment <= first_interest:
        return {
            "pays_off": False,
            "months": None,
            "total_interest": None,
            "min_payment_to_progress": money(first_interest + CENT),
        }
    balance, total_interest, n = principal, ZERO, 0
    while balance > 0 and n < max_months:
        interest = (balance * r).quantize(CENT, rounding=ROUND_HALF_UP)
        pay = min(payment, balance + interest)
        balance = balance + interest - pay
        total_interest += interest
        n += 1
    if balance > 0:
        return {"pays_off": False, "months": None, "total_interest": None, "min_payment_to_progress": money(first_interest + CENT)}
    return {"pays_off": True, "months": n, "total_interest": money(total_interest), "min_payment_to_progress": None}


def cagr(start: Decimal, end: Decimal, periods: Decimal) -> Decimal | None:
    """Compound growth per period; None when undefined (non-positive start or zero periods)."""
    if start <= 0 or periods <= 0 or end < 0:
        return None
    return Decimal(str((float(end) / float(start)) ** (1.0 / float(periods)))) - 1


def parse_iso(value: str, name: str = "date") -> date:
    from ...lib.dates import parse_date

    try:
        return parse_date(str(value))
    except ToolError:
        raise ToolError(f"{name}: expected YYYY-MM-DD, got {value!r}") from None
