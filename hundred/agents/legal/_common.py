"""Shared helpers for the Legal & Admin agents (stdlib only).

Every legal agent's output carries the scope note below: these agents are drafting and
review aids, not legal advice; jurisdiction changes the answer; high-stakes documents go
to a licensed lawyer.
"""

from __future__ import annotations

import re
from datetime import date

from ...core import ToolError
from ...lib import dates

MAX_TEXT = 300_000
MAX_ROWS = 500

SCOPE_NOTE = (
    "Drafting/review aid, not legal advice. Contract law varies by jurisdiction; have a licensed "
    "lawyer review anything high-value, cross-border, or involving IP, employment or personal data."
)

_NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "twenty": 20, "thirty": 30,
    "forty": 40, "forty-five": 45, "sixty": 60, "ninety": 90, "one hundred": 100, "one hundred twenty": 120,
    "one hundred eighty": 180, "a": 1, "an": 1,
}
NUMBER_RE = r"(?:\d{1,4}|(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|twenty|thirty|forty(?:-five)?|sixty|ninety|one hundred(?: twenty| eighty)?|a|an))(?:\s*\(\d{1,4}\))?"
DURATION_RE = re.compile(rf"\b({NUMBER_RE})\s+(business\s+|calendar\s+|working\s+)?(days?|weeks?|months?|years?)\b", re.I)


def check_text(value: str, label: str = "text", max_len: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolError(f"{label} is empty.")
    if len(value) > max_len:
        raise ToolError(f"{label} too long ({len(value):,} chars; max {max_len:,}). Split it.")
    return value


def check_rows(rows: list, label: str = "rows", max_rows: int = MAX_ROWS) -> list:
    if not isinstance(rows, list) or not rows:
        raise ToolError(f"{label} is empty — pass at least one item.")
    if len(rows) > max_rows:
        raise ToolError(f"Too many {label} ({len(rows)}; max {max_rows}).")
    return rows


def parse_number(token: str) -> int | None:
    """'thirty (30)' → 30, 'ninety' → 90, '45' → 45."""
    t = token.strip().lower()
    m = re.search(r"\((\d{1,4})\)", t)
    if m:
        return int(m.group(1))
    if t.isdigit():
        return int(t)
    return _NUM_WORDS.get(re.sub(r"\s+", " ", t))


def duration_days(n: int, unit: str, business: bool = False) -> int:
    u = unit.lower().rstrip("s")
    if u == "day":
        return n
    if u == "week":
        return n * 7
    if u == "month":
        return n * 30
    if u == "year":
        return n * 365
    return n


def add_months(d: date, months: int) -> date:
    y, m = d.year + (d.month - 1 + months) // 12, (d.month - 1 + months) % 12 + 1
    last = [31, 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return d.replace(year=y, month=m, day=min(d.day, last))


def excerpt(text: str, match: re.Match, width: int = 160) -> str:
    start = max(0, match.start() - width // 2)
    end = min(len(text), match.end() + width // 2)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def money(x: float, currency: str = "$") -> str:
    return f"{currency}{x:,.2f}" if abs(x) < 1000 else f"{currency}{x:,.0f}"


def to_float(value, label: str, lo: float | None = None, hi: float | None = None) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ToolError(f"{label} must be a number, got {value!r}.") from None
    if f != f or f in (float("inf"), float("-inf")):
        raise ToolError(f"{label} must be a finite number.")
    if lo is not None and f < lo:
        raise ToolError(f"{label} must be >= {lo}, got {f}.")
    if hi is not None and f > hi:
        raise ToolError(f"{label} must be <= {hi}, got {f}.")
    return f


def parse_date(value: str, label: str = "date") -> date:
    if not isinstance(value, str) or not value.strip():
        raise ToolError(f"{label} is required as YYYY-MM-DD.")
    return dates.parse_date(value)
