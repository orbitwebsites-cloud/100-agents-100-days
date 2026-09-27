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
