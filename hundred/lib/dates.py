"""Calendar math agents keep getting wrong in their heads."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from ..core import ToolError


def parse_date(value: str) -> date:
    """Parse YYYY-MM-DD (or an ISO datetime) into a date, with a clean error."""
    try:
        return datetime.fromisoformat(value.strip()).date()
    except (ValueError, AttributeError):
        raise ToolError(f"Expected a date like 2026-10-05, got {value!r}") from None


def add_business_days(start: date, days: int, holidays: set[date] | None = None) -> date:
    holidays = holidays or set()
    step = 1 if days >= 0 else -1
    current, remaining = start, abs(days)
    while remaining:
        current += timedelta(days=step)
        if current.weekday() < 5 and current not in holidays:
            remaining -= 1
    return current


def business_days_between(start: date, end: date, holidays: set[date] | None = None) -> int:
    holidays = holidays or set()
    if end < start:
        return -business_days_between(end, start, holidays)
    n, d = 0, start
    while d < end:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in holidays:
            n += 1
    return n


def fmt(d: date) -> str:
    return f"{d.isoformat()} ({d.strftime('%a')})"
