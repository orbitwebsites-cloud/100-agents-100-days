"""Small validation + formatting helpers shared by the ops agents (not an agent itself)."""

from __future__ import annotations

import math
import re
from datetime import date, datetime, time
from typing import Any

from ...core import ToolError

_HHMM = re.compile(r"^\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*$", re.I)


def require_list(value: Any, name: str, max_len: int, min_len: int = 1) -> list:
    if not isinstance(value, list):
        raise ToolError(f"{name} must be a list.")
    if len(value) < min_len:
        raise ToolError(f"{name} needs at least {min_len} item(s).")
    if len(value) > max_len:
        raise ToolError(f"{name} too large ({len(value)} items; max {max_len}).")
    return value


def require_dict(value: Any, name: str) -> dict:
    if not isinstance(value, dict):
        raise ToolError(f"{name} must be an object/dict, got {type(value).__name__}.")
    return value


def as_float(value: Any, name: str, lo: float | None = None, hi: float | None = None, default: float | None = None) -> float:
    if value is None or value == "":
        if default is not None:
            return default
        raise ToolError(f"{name} is required and must be a number.")
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("$", "").replace("%", "").strip()
        f = float(value)
    except (TypeError, ValueError):
        raise ToolError(f"{name} must be a number, got {value!r}.") from None
    if math.isnan(f) or math.isinf(f):
        raise ToolError(f"{name} must be a finite number.")
    if lo is not None and f < lo:
        raise ToolError(f"{name} must be >= {lo}, got {f}.")
    if hi is not None and f > hi:
        raise ToolError(f"{name} must be <= {hi}, got {f}.")
    return f


def as_str(value: Any, name: str, required: bool = True, max_len: int = 2000) -> str:
    s = "" if value is None else str(value).strip()
    if required and not s:
        raise ToolError(f"{name} is required.")
    return s[:max_len]


def as_str_list(value: Any, name: str, max_len: int = 200) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        value = [v for v in re.split(r"[,;\n]", value) if v.strip()]
    if not isinstance(value, list):
        raise ToolError(f"{name} must be a list of strings.")
    return [str(v).strip() for v in value[:max_len] if str(v).strip()]


def pct_change(new: float, old: float) -> float | None:
    if old == 0:
        return None
    return round(100.0 * (new - old) / abs(old), 1)


def parse_hhmm(value: Any, name: str = "time") -> int:
    """'09:30', '9:30', '9am', '17:00', '5pm' -> minutes since midnight."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        m = int(value)
        if 0 <= m <= 24 * 60:
            return m
        raise ToolError(f"{name}: {value} is not a valid minutes-of-day value.")
    m = _HHMM.match(str(value or ""))
    if not m:
        raise ToolError(f"{name}: expected a time like 09:30 or 5pm, got {value!r}.")
    h, mins, ampm = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
    if ampm == "pm" and h < 12:
        h += 12
    if ampm == "am" and h == 12:
        h = 0
    if not (0 <= h <= 24 and 0 <= mins < 60) or (h == 24 and mins != 0):
        raise ToolError(f"{name}: {value!r} is out of range.")
    return h * 60 + mins


def fmt_hhmm(minutes: int) -> str:
    minutes = int(round(minutes))
    return f"{(minutes // 60) % 24:02d}:{minutes % 60:02d}"


def fmt_duration(minutes: float) -> str:
    minutes = int(round(minutes))
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h}h {m:02d}m"
    if h:
        return f"{h}h"
    return f"{m}m"


def parse_datetime(value: Any, name: str = "datetime") -> datetime:
    """Parse ISO datetime ('2026-10-05 14:00' / '2026-10-05T14:00:00'); a bare date means 09:00."""
    s = str(value or "").strip()
    if not s:
        raise ToolError(f"{name} is required (e.g. 2026-10-05 14:00).")
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        raise ToolError(f"{name}: expected ISO datetime like 2026-10-05 14:00, got {value!r}.") from None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        dt = datetime.combine(dt.date(), time(9, 0))
    return dt


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    def cell(v: Any) -> str:
        if isinstance(v, float):
            return f"{v:g}"
        return str(v if v is not None else "")

    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(cell(v) for v in r) + " |" for r in rows]
    return "\n".join(lines)


def iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_NUM_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "ten": 10}


def resolve_relative_date(phrase: str, base: date) -> tuple[date | None, str]:
    """'by Friday', 'EOD', 'tomorrow', 'in 2 weeks', 'next Tuesday', 'end of month', '2026-10-05' -> (date, rule)."""
    from datetime import timedelta

    p = (phrase or "").lower().strip()
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", p)
    if m:
        try:
            return datetime.fromisoformat(m.group(1)).date(), "explicit"
        except ValueError:
            return None, "bad explicit date"
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", p)
    if m:
        mo, da, yr = int(m.group(1)), int(m.group(2)), m.group(3)
        year = base.year if not yr else (int(yr) + 2000 if len(yr) == 2 else int(yr))
        try:
            d = date(year, mo, da)
            if not yr and d < base:
                d = date(year + 1, mo, da)
            return d, "explicit (m/d)"
        except ValueError:
            return None, "bad explicit date"
    if "tomorrow" in p:
        return base + timedelta(days=1), "next day"
    if re.search(r"\b(today|eod|end of (the )?day|tonight|asap|now|immediately|urgent(ly)?)\b", p):
        return base, "same day"
    m = re.search(r"\b(?:in|within) (\d+|a|an|one|two|three|four|five|six|seven|ten) (business |working )?(day|week|month|hour)s?\b", p)
    if m:
        n = _NUM_WORDS.get(m.group(1)) or int(m.group(1))
        unit = m.group(3)
        if unit == "hour":
            return base + timedelta(days=1 if n >= 12 else 0), f"+{n} hours"
        if m.group(2):
            from ...lib import dates as _dates

            return _dates.add_business_days(base, n), f"+{n} business days"
        return base + timedelta(days=n * {"day": 1, "week": 7, "month": 30}[unit]), f"+{n} {unit}(s)"
    if re.search(r"\b(eow|end of (?:the |this |next )?week|this week)\b", p):
        d = base + timedelta(days=(4 - base.weekday()) % 7)
        return (d + timedelta(days=7) if "next" in p else d), "Friday"
    if re.search(r"\b(eom|end of (the |this )?month)\b", p):
        nxt = (base.replace(day=28) + timedelta(days=4)).replace(day=1)
        return nxt - timedelta(days=1), "last day of month"
    if re.search(r"\b(eoq|end of (the |this )?quarter)\b", p):
        q_end_month = ((base.month - 1) // 3 + 1) * 3
        nxt = (date(base.year, q_end_month, 28) + timedelta(days=4)).replace(day=1)
        return nxt - timedelta(days=1), "last day of quarter"
    if re.search(r"\bnext week\b", p):
        return base + timedelta(days=7 - base.weekday()), "Monday next week"
    for i, day in enumerate(_WEEKDAYS):
        if re.search(rf"\b{day[:3]}(?:{day[3:]})?\b", p):
            ahead = (i - base.weekday()) % 7 or 7
            if "next" in p and ahead < 7:
                ahead += 7
            return base + timedelta(days=ahead), day.title()
    return None, "unrecognised"
