"""Helpers shared by the Creators & Personal agents (skipped by the registry)."""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ...core import ToolError

# ── time strings ────────────────────────────────────────────────


def parse_timestamp(value: str | int | float) -> int:
    """'1:02:03', '62:03', '3723', 3723 → seconds. Raises ToolError on junk."""
    if isinstance(value, bool):
        raise ToolError(f"Bad timestamp {value!r}")
    if isinstance(value, (int, float)):
        if value < 0:
            raise ToolError(f"Timestamp cannot be negative: {value!r}")
        return int(round(value))
    s = str(value).strip()
    if not s:
        raise ToolError("Empty timestamp")
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return int(round(float(s)))
    m = re.fullmatch(r"(?:(\d{1,3}):)?(\d{1,3}):(\d{2})(?:\.\d+)?", s)
    if not m:
        raise ToolError(f"Bad timestamp {value!r}: use mm:ss, h:mm:ss or plain seconds")
    h = int(m.group(1) or 0)
    mnt, sec = int(m.group(2)), int(m.group(3))
    if sec >= 60 or (m.group(1) and mnt >= 60):
        raise ToolError(f"Bad timestamp {value!r}: minutes/seconds must be < 60")
    return h * 3600 + mnt * 60 + sec


def fmt_timestamp(seconds: int | float, force_hours: bool = False) -> str:
    """3723 → '1:02:03'; 62 → '1:02'. YouTube-chapter friendly (no leading zero on the top unit)."""
    s = int(round(max(0, seconds)))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h or force_hours:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


def fmt_minutes(seconds: int | float) -> str:
    s = int(round(seconds))
    if s < 60:
        return f"{s}s"
    m, sec = divmod(s, 60)
    return f"{m}m {sec:02d}s" if sec else f"{m} min"


def parse_hhmm(value: str) -> tuple[int, int]:
    """'09:30' or '9:30' or '21:05' → (hour, minute)."""
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", str(value or ""))
    if not m:
        raise ToolError(f"Expected a time like 09:30, got {value!r}")
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        raise ToolError(f"Time out of range: {value!r}")
    return h, mi


# ── timezones ───────────────────────────────────────────────────


def tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(str(name).strip())
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        raise ToolError(f"Unknown timezone {name!r}. Use an IANA name like Europe/Paris or America/New_York.") from None


def local_dt(day: date, hhmm: str, zone: str) -> datetime:
    h, m = parse_hhmm(hhmm)
    return datetime(day.year, day.month, day.day, h, m, tzinfo=tz(zone))


def parse_local_datetime(value: str, zone: str) -> datetime:
    """'2026-10-05 14:30' or ISO 'T' form, in the given IANA zone."""
    s = str(value or "").strip().replace("T", " ")
    try:
        naive = datetime.strptime(s, "%Y-%m-%d %H:%M")
    except ValueError:
        raise ToolError(f"Expected a datetime like 2026-10-05 14:30, got {value!r}") from None
    return naive.replace(tzinfo=tz(zone))


# ── numbers ─────────────────────────────────────────────────────


def positive(value: float, label: str, maximum: float | None = None) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ToolError(f"{label} must be a number") from None
    if v != v or v <= 0:
        raise ToolError(f"{label} must be > 0")
    if maximum is not None and v > maximum:
        raise ToolError(f"{label} is implausibly large (> {maximum:g})")
    return v


def round_to(value: float, step: float) -> float:
    """Round to the nearest multiple of step, ties rounding up (not banker's rounding)."""
    if step <= 0:
        return value
    return round(math.floor(value / step + 0.5) * step, 3)


def pct(part: float, whole: float) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def money(value: float) -> float:
    return round(float(value) + 1e-9, 2)


# ── speech ──────────────────────────────────────────────────────

FILLER_RE = re.compile(
    r"\b(um+|uh+|erm|ah+|like|you know|basically|literally|actually|honestly|kind of|sort of|"
    r"i mean|right\?|okay so|so yeah)\b",
    re.I,
)
