"""Small validation + formatting helpers shared by the ops agents (not an agent itself)."""

from __future__ import annotations

import math
import re
from datetime import date, datetime, time, timedelta
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
_NUM_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5,
    "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_MONTH_RX = "|".join(sorted(_MONTHS, key=len, reverse=True))
_MONTH_DAY = re.compile(rf"\b({_MONTH_RX})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(\d{{4}}))?")
_DAY_MONTH = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTH_RX})\b\.?(?:,?\s+(\d{{4}}))?")
_WEEKDAY_RX = [re.compile(rf"\b{d[:3]}(?:{d[3:]}|{d[3:4]})?\b") for d in _WEEKDAYS]  # "tue"/"tues"/"tuesday"
_WEEKDAY_RX[1] = re.compile(r"\btue(?:s|sday)?\b")
_WEEKDAY_RX[3] = re.compile(r"\bthu(?:r|rs|rsday)?\b")
_WEEKDAY_RX[2] = re.compile(r"\bwed(?:nesday)?\b")


def _month_date(p: str, base: date) -> tuple[date | None, str] | None:
    for rx, mi, di in ((_MONTH_DAY, 1, 2), (_DAY_MONTH, 2, 1)):
        m = rx.search(p)
        if not m:
            continue
        mo, da, yr = _MONTHS[m.group(mi)], int(m.group(di)), m.group(3)
        if m.group(mi) == "may" and mi == 1 and not re.search(r"\bmay\s+\d", p):
            continue
        try:
            d = date(int(yr) if yr else base.year, mo, da)
        except ValueError:
            return None, "bad explicit date"
        if not yr and d < base - timedelta(days=31):  # "Jan 10" said in December means next year
            d = date(base.year + 1, mo, da)
        return d, "explicit (month name)"
    return None


def resolve_relative_date(phrase: str, base: date) -> tuple[date | None, str]:
    """Deadline phrase -> (date, rule), anchored on `base` (the day it was said/sent).

    Handles ISO and m/d dates, month names ("Oct 15th", "15 October"), "tomorrow", "in/within N
    (business) days/weeks", weekdays ("Friday", "EOD Thursday", "next Tuesday", "Tuesday next
    week"), end of week/month/quarter, "next week", and same-day words (today/EOD/COB/ASAP).
    A named weekday always wins over a same-day word, so "EOD Thursday" is Thursday.
    "next <weekday>" = that weekday in the NEXT calendar week (Mon-Sun); when that differs from
    the nearest upcoming one the rule says so, so the caller can confirm.
    """
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
    md = _month_date(p, base)
    if md is not None:
        return md
    if "day after tomorrow" in p:
        return base + timedelta(days=2), "+2 days"
    if "tomorrow" in p:
        return base + timedelta(days=1), "next day"
    m = re.search(r"\b(?:in|within|give me|takes?|another) (\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten) (business |working )?(day|week|month|hour)s?\b", p)
    if m:
        n = _NUM_WORDS.get(m.group(1)) or int(m.group(1))
        unit = m.group(3)
        if unit == "hour":
            return base + timedelta(days=1 if n >= 12 else 0), f"+{n} hours"
        if m.group(2):
            from ...lib import dates as _dates

            return _dates.add_business_days(base, n), f"+{n} business days"
        return base + timedelta(days=n * {"day": 1, "week": 7, "month": 30}[unit]), f"+{n} {unit}(s)"
    for i, rx in enumerate(_WEEKDAY_RX):
        if not rx.search(p):
            continue
        day = _WEEKDAYS[i].title()
        nearest = base + timedelta(days=(i - base.weekday()) % 7 or 7)
        next_cal_week = base + timedelta(days=7 - base.weekday() + i)
        if re.search(rf"\b(?:the\s+)?{_WEEKDAYS[i][:3]}\w*\s+after\s+next\b", p):
            return next_cal_week + timedelta(days=7), f"{day} after next"
        if re.search(r"\bnext week\b", p) or re.search(rf"\bnext\s+{_WEEKDAYS[i][:3]}", p):
            if next_cal_week != nearest:
                return next_cal_week, f"{day} of next week (said on a {base.strftime('%A')}; 'next {day}' could also mean {nearest.isoformat()} — confirm)"
            return next_cal_week, f"{day} of next week"
        if re.search(rf"\bthis\s+{_WEEKDAYS[i][:3]}", p) and i == base.weekday():
            return base, f"{day} (today)"
        return nearest, day
    if re.search(r"\b(eow|end of (?:the |this |next )?week|this week)\b", p):
        d = base + timedelta(days=(4 - base.weekday()) % 7)
        return (d + timedelta(days=7) if "next" in p else d), "Friday" + (" of next week" if "next" in p else "")
    if re.search(r"\b(eom|end of (the |this |next )?month)\b", p):
        anchor = base if "next" not in p else (base.replace(day=28) + timedelta(days=4)).replace(day=1)
        nxt = (anchor.replace(day=28) + timedelta(days=4)).replace(day=1)
        return nxt - timedelta(days=1), "last day of month"
    if re.search(r"\b(eoq|end of (the |this )?quarter)\b", p):
        q_end_month = ((base.month - 1) // 3 + 1) * 3
        nxt = (date(base.year, q_end_month, 28) + timedelta(days=4)).replace(day=1)
        return nxt - timedelta(days=1), "last day of quarter"
    if re.search(r"\bnext week\b", p):
        return base + timedelta(days=7 - base.weekday()), "Monday next week"
    if re.search(r"\b(today|eod|cob|eob|close of (?:business|play)|end of (the )?day|tonight|asap|now|immediately|urgent(ly)?)\b", p):
        return base, "same day"
    return None, "unrecognised"
