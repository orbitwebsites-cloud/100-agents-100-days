"""Time Blocker — packs priorities into a real day, finds cross-timezone meeting slots, audits where the week goes."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from ...core import Agent, ToolError
from ...lib import dates
from ._common import as_float, as_str, fmt_duration, fmt_hhmm, md_table, parse_datetime, parse_hhmm, require_list

AGENT = Agent(
    slug="time-blocker",
    name="Time Blocker",
    category="ops",
    tagline="Pack your priorities into real calendar blocks, find meeting slots across time zones, and see where the week goes.",
    description=(
        "Runs a time-blocking practice the way an executive assistant to a CEO would: turns a task list "
        "into a packed day that protects deep work in your peak hours, finds meeting windows that respect "
        "every participant's working hours with correct DST handling (zoneinfo), converts times without "
        "off-by-one-day mistakes, and audits a calendar export for meeting load, fragmentation and maker time."
    ),
    triggers=[
        "plan my day / time-block my day",
        "find a meeting time that works across time zones",
        "what time is 3pm ET in Berlin / convert this time",
        "audit my calendar / how much of my week is meetings",
        "fit these tasks into my schedule",
        "schedule deep work around my meetings",
    ],
    examples=[
        "Here are my 7 tasks for today and my meetings — build my schedule; I'm sharpest 8-11am.",
        "Find a 45-minute slot next Tuesday for people in SF, London and Bangalore.",
        "Convert Thursday 14:00 Sydney to New York, London and Singapore.",
        "Here's my calendar export for last week — how fragmented is it and what should I change?",
    ],
    connectors=["Google Calendar", "Outlook Calendar", "Notion", "Todoist", "Linear", "Slack"],
    playbook="""
    ## Standard
    You are the time-management operator behind a top executive. Excellent means: every
    important task has a block on the calendar (not a list), deep work sits in the person's
    peak hours, meetings across time zones land inside everyone's working day, and no time
    is computed by hand. The one metric: **protected focus time per week** — a knowledge worker
    needs ≥ 2 blocks of 90+ minutes per day; below 10 h/week of focus time, output collapses.

    ## Intake
    Need: (a) the tasks with rough minutes and priority, (b) fixed meetings, (c) working
    hours and peak window (default 09:00-18:00, peak 09:00-12:00 — say so). For meetings:
    each participant's city or IANA zone and working hours (default 09:00-17:00 local,
    Mon-Fri). Ask at most one question, only if a time zone is genuinely ambiguous
    ("Portland" — Oregon or Maine?). Otherwise assume and state the assumption.

    ## Procedure
    1. **Plan a day.** Assign each task a priority (1 = must happen today … 4 = nice),
       a kind (deep / shallow / admin) and minutes (round up to 15; if unknown, 45 for
       deep, 20 for shallow). Call `time_blocker__pack_day` with the tasks, fixed events,
       working hours and peak window. It packs deep work into peak-hour gaps first, splits
       long tasks into ≤ 90-minute blocks, adds buffers after meetings, and returns what
       did not fit. Present the blocks as the schedule; for the leftovers, say explicitly
       which day they move to. Never silently drop a task.
    2. **Find a meeting time.** Call `time_blocker__find_meeting_slots` with participants
       (name, zone, working hours), duration and the date(s). Report only windows the tool
       marked `everyone_in_hours`; if none exist, present the tool's `best_compromise`
       windows and say who is outside hours and by how much. Rotate the pain across
       recurring meetings — don't make the same region take 7 am every time.
    3. **Convert a time.** Any time you state in a second zone, get it from
       `time_blocker__convert_time`. It handles DST and day rollover (e.g. Sydney Thursday
       14:00 is Wednesday 23:00 in New York). Always print the weekday with the time.
    4. **Audit a calendar.** Given an export (title, start, end), call
       `time_blocker__audit_calendar`. Report meeting load %, fragmentation (free gaps
       under 30 min, which are unusable), longest focus block per day, back-to-back
       chains, and category mix. Then prescribe: which meetings to cluster, which day to
       make meeting-free, which recurring meeting to shorten or kill.
    5. **Act.** With Google/Outlook Calendar connected, create the blocks as events (title
       "Focus: <task>", private, "busy"). With a task manager, add the due date. Otherwise
       output the schedule ready to paste.

    ## Frameworks
    - **Time blocking (Newport)**: every minute of the workday has a job; re-plan when the
      plan breaks — the value is in the re-planning, not in obedience.
    - **Peak / trough / recovery (Pink)**: analytical work in the morning peak for most
      people, admin in the early-afternoon trough, creative work in late-afternoon recovery.
      Ask "when are you sharpest" and let the answer override the default.
    - **Eisenhower**: priority 1 = important + urgent (do first), 2 = important not urgent
      (schedule in peak), 3 = urgent not important (batch or delegate), 4 = neither (cut).
    - **Maker / manager schedule (Graham)**: a single 30-minute meeting at 10:30 destroys a
      morning for a maker. Cluster meetings into one or two afternoon bands.
    - **Meeting thresholds**: > 50% of work hours in meetings = red; 30-50% amber; < 30%
      green. More than 4 back-to-back meetings = add 10-minute buffers or shorten to 25/50.
    - **Time-zone etiquette**: 08:00-18:00 local is acceptable, 07:00-20:00 is tolerable
      once in a while, outside that is a favour to be repaid.

    ## Output format
    ```
    # <Day/Date> — plan (work 09:00-18:00, peak 09:00-12:00)
    | Time | Block | Kind | Notes |
    |---|---|---|---|
    | 09:00-10:30 | Focus: <task> | deep | P1 |
    …
    **Focus time:** Xh · **Meetings:** Yh (Z%) · **Unscheduled:** <task> → <which day>

    ## Meeting slot options            (only when asked)
    | Option | UTC | <Name> (<Zone>) | <Name> (<Zone>) | Everyone in hours? |
    |---|---|---|---|---|

    ## Calendar audit                  (only when asked)
    Meeting load: X% (RAG) · Fragments: N gaps < 30 min · Longest focus block: Xh (<day>)
    Top 3 changes: 1. … 2. … 3. …
    ```

    ## Anti-patterns
    - Converting time zones from memory ("Berlin is +6 from New York" — not during the two
      weeks when DST shifts differ). Use the tool, every time.
    - Scheduling deep work at 15:00 because that's where the gap was, while 09:00-10:00 is
      spent on email. Peak hours are for the hardest thing.
    - Back-to-back blocks with no buffer. Meetings run over; plan 5-10 minute gaps.
    - A "plan" that lists tasks without times. If it isn't on the calendar, it's a wish.
    - Splitting a deep task into 25-minute pieces across the day. Minimum useful deep block
      is 50 minutes; ideal is 90.
    - Proposing a meeting at a time that is 06:30 for someone and calling it "works for all".
    """,
)

MAX_PARTICIPANTS = 25
_CITY_ALIASES = {
    "new york": "America/New_York", "nyc": "America/New_York", "et": "America/New_York", "est": "America/New_York", "edt": "America/New_York",
    "boston": "America/New_York", "toronto": "America/Toronto", "miami": "America/New_York",
    "chicago": "America/Chicago", "ct": "America/Chicago", "cst": "America/Chicago", "austin": "America/Chicago", "dallas": "America/Chicago",
    "denver": "America/Denver", "mt": "America/Denver", "mst": "America/Denver",
    "san francisco": "America/Los_Angeles", "sf": "America/Los_Angeles", "la": "America/Los_Angeles", "los angeles": "America/Los_Angeles",
    "seattle": "America/Los_Angeles", "pt": "America/Los_Angeles", "pst": "America/Los_Angeles", "pdt": "America/Los_Angeles",
    "vancouver": "America/Vancouver", "mexico city": "America/Mexico_City", "sao paulo": "America/Sao_Paulo", "são paulo": "America/Sao_Paulo",
    "buenos aires": "America/Argentina/Buenos_Aires", "bogota": "America/Bogota",
    "london": "Europe/London", "uk": "Europe/London", "gmt": "Etc/GMT", "bst": "Europe/London", "dublin": "Europe/Dublin", "lisbon": "Europe/Lisbon",
    "paris": "Europe/Paris", "berlin": "Europe/Berlin", "cet": "Europe/Berlin", "cest": "Europe/Berlin", "madrid": "Europe/Madrid", "rome": "Europe/Rome",
    "amsterdam": "Europe/Amsterdam", "zurich": "Europe/Zurich", "stockholm": "Europe/Stockholm", "oslo": "Europe/Oslo", "copenhagen": "Europe/Copenhagen",
    "warsaw": "Europe/Warsaw", "prague": "Europe/Prague", "vienna": "Europe/Vienna", "athens": "Europe/Athens", "helsinki": "Europe/Helsinki",
    "kyiv": "Europe/Kyiv", "kiev": "Europe/Kyiv", "moscow": "Europe/Moscow", "istanbul": "Europe/Istanbul",
    "tel aviv": "Asia/Jerusalem", "jerusalem": "Asia/Jerusalem", "dubai": "Asia/Dubai", "riyadh": "Asia/Riyadh", "cairo": "Africa/Cairo",
    "lagos": "Africa/Lagos", "nairobi": "Africa/Nairobi", "johannesburg": "Africa/Johannesburg", "cape town": "Africa/Johannesburg",
    "mumbai": "Asia/Kolkata", "bangalore": "Asia/Kolkata", "bengaluru": "Asia/Kolkata", "delhi": "Asia/Kolkata", "india": "Asia/Kolkata", "ist": "Asia/Kolkata",
    "karachi": "Asia/Karachi", "dhaka": "Asia/Dhaka", "bangkok": "Asia/Bangkok", "jakarta": "Asia/Jakarta", "ho chi minh": "Asia/Ho_Chi_Minh",
    "singapore": "Asia/Singapore", "sgt": "Asia/Singapore", "kuala lumpur": "Asia/Kuala_Lumpur", "manila": "Asia/Manila",
    "hong kong": "Asia/Hong_Kong", "shanghai": "Asia/Shanghai", "beijing": "Asia/Shanghai", "china": "Asia/Shanghai", "taipei": "Asia/Taipei",
    "seoul": "Asia/Seoul", "tokyo": "Asia/Tokyo", "jst": "Asia/Tokyo", "japan": "Asia/Tokyo",
    "sydney": "Australia/Sydney", "aest": "Australia/Sydney", "melbourne": "Australia/Melbourne", "brisbane": "Australia/Brisbane",
    "perth": "Australia/Perth", "adelaide": "Australia/Adelaide", "auckland": "Pacific/Auckland", "wellington": "Pacific/Auckland",
    "utc": "UTC", "honolulu": "Pacific/Honolulu", "anchorage": "America/Anchorage",
}


def _zone(name: str, label: str = "timezone") -> ZoneInfo:
    raw = as_str(name, label, max_len=80)
    key = raw.strip()
    alias = _CITY_ALIASES.get(key.lower())
    if alias:
        key = alias
    try:
        return ZoneInfo(key)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        pass
    # case-insensitive match against the database
    low = key.lower().replace(" ", "_")
    for tz in available_timezones():
        if tz.lower() == low or tz.lower().endswith("/" + low):
            return ZoneInfo(tz)
    raise ToolError(f"{label}: unknown time zone {raw!r}. Use an IANA name like 'Europe/Berlin' or a major city like 'London'.")


def _offset_label(dt: datetime) -> str:
    off = dt.utcoffset() or timedelta()
    total = int(off.total_seconds() // 60)
    sign = "+" if total >= 0 else "-"
    h, m = divmod(abs(total), 60)
    return f"UTC{sign}{h:02d}:{m:02d}"


@AGENT.tool
def convert_time(when: str, from_zone: str, to_zones: list[str]) -> dict:
    """Convert a date-time from one zone to others with DST and day-rollover handled (zoneinfo).

    Args:
        when: Local date-time in the source zone, e.g. "2026-10-08 14:00" (a bare date means 09:00).
        from_zone: Source IANA zone ("America/New_York") or major city ("London", "Bangalore").
        to_zones: Target zones or cities to convert into.
    """
    src = _zone(from_zone, "from_zone")
    to_zones = require_list(to_zones, "to_zones", 50)
    naive = parse_datetime(when, "when")
    if naive.tzinfo is not None:
        base = naive.astimezone(src)
    else:
        base = naive.replace(tzinfo=src)
        # detect non-existent / ambiguous local times around DST transitions
        if base.astimezone(ZoneInfo("UTC")).astimezone(src).replace(tzinfo=None) != naive:
            raise ToolError(f"{when!r} does not exist in {src.key} (clocks skip forward at that DST change). Pick another time.")
    utc = base.astimezone(ZoneInfo("UTC"))
    out = []
    for z in to_zones:
        tz = _zone(z, "to_zones")
        local = utc.astimezone(tz)
        day_shift = (local.date() - base.date()).days
        out.append(
            {
                "zone": tz.key,
                "local": local.strftime("%Y-%m-%d %H:%M"),
                "weekday": local.strftime("%A"),
                "offset": _offset_label(local),
                "abbreviation": local.tzname(),
                "is_dst": bool(local.dst()),
                "day_shift": day_shift,
                "day_note": {0: "same day", 1: "next day", -1: "previous day"}.get(day_shift, f"{day_shift:+d} days"),
                "in_business_hours": 8 <= local.hour < 18 and local.weekday() < 5,
            }
        )
    return {
        "source": {"zone": src.key, "local": base.strftime("%Y-%m-%d %H:%M"), "weekday": base.strftime("%A"), "offset": _offset_label(base), "is_dst": bool(base.dst())},
        "utc": utc.strftime("%Y-%m-%d %H:%M"),
        "conversions": out,
        "summary": "; ".join(f"{c['zone']}: {c['weekday'][:3]} {c['local'][11:]} ({c['day_note']})" for c in out),
    }


def _participants(raw: list) -> list[dict]:
    raw = require_list(raw, "participants", MAX_PARTICIPANTS)
    out = []
    for i, p in enumerate(raw, 1):
        if isinstance(p, str):
            p = {"name": p, "zone": p}
        if not isinstance(p, dict):
            raise ToolError(f"participants[{i}] must be {{'name', 'zone', 'work_start', 'work_end'}}.")
        tz = _zone(p.get("zone") or p.get("tz") or p.get("timezone") or p.get("city"), f"participants[{i}].zone")
        ws = parse_hhmm(p.get("work_start", "09:00"), f"participants[{i}].work_start")
        we = parse_hhmm(p.get("work_end", "17:00"), f"participants[{i}].work_end")
        if we <= ws:
            raise ToolError(f"participants[{i}]: work_end must be after work_start.")
        out.append({"name": as_str(p.get("name") or tz.key, "name", max_len=60), "tz": tz, "ws": ws, "we": we, "weekends": bool(p.get("weekends", False))})
    return out


@AGENT.tool
def find_meeting_slots(participants: list[dict], duration_minutes: int = 30, date: str = "", days: int = 1, step_minutes: int = 15) -> dict:
    """Find meeting windows where every participant is inside their own working hours (DST-correct).

    Returns perfect windows first; if none exist, the least-painful compromises (who is outside
    hours and by how much), with the local time for each participant.

    Args:
        participants: List of {"name": str, "zone": IANA zone or city, "work_start": "09:00", "work_end": "17:00", "weekends": false}.
        duration_minutes: Meeting length in minutes (15-480).
        date: First date to search as YYYY-MM-DD (in the first participant's zone). Defaults to today.
        days: How many consecutive days to search (1-14).
        step_minutes: Search granularity (5, 10, 15 or 30).
    """
    people = _participants(participants)
    if not (15 <= duration_minutes <= 480):
        raise ToolError("duration_minutes must be between 15 and 480.")
    if not (1 <= days <= 14):
        raise ToolError("days must be 1-14.")
    if step_minutes not in (5, 10, 15, 30):
        raise ToolError("step_minutes must be 5, 10, 15 or 30.")
    d0 = dates.parse_date(date) if date else datetime.now(people[0]["tz"]).date()
    utc = ZoneInfo("UTC")
    start = datetime(d0.year, d0.month, d0.day, 0, 0, tzinfo=people[0]["tz"]).astimezone(utc)
    end = start + timedelta(days=days)
    step = timedelta(minutes=step_minutes)
    n_steps = int((end - start) / step)
    TOL_START, TOL_END = 7 * 60, 20 * 60

    def status(t: datetime) -> list[int]:
        # 0 = in working hours, 1 = tolerable (07:00-20:00 weekday), 2 = painful
        out = []
        for p in people:
            loc = t.astimezone(p["tz"])
            mins = loc.hour * 60 + loc.minute
            weekend = loc.weekday() >= 5 and not p["weekends"]
            if not weekend and p["ws"] <= mins and mins + duration_minutes <= p["we"]:
                out.append(0)
            elif not weekend and TOL_START <= mins and mins + duration_minutes <= TOL_END:
                out.append(1)
            else:
                out.append(2)
        return out

    grid = [start + i * step for i in range(n_steps)]
    stats = [status(t) for t in grid]

    def windows(pred) -> list[tuple[datetime, datetime]]:
        wins, i = [], 0
        while i < len(grid):
            if pred(stats[i]):
                j = i
                while j + 1 < len(grid) and pred(stats[j + 1]):
                    j += 1
                wins.append((grid[i], grid[j] + timedelta(minutes=duration_minutes)))
                i = j + 1
            else:
                i += 1
        return wins

    def describe(t0: datetime, t1: datetime, st: list[int]) -> dict:
        locals_ = {}
        for p, s in zip(people, st):
            a, b = t0.astimezone(p["tz"]), (t0 + timedelta(minutes=duration_minutes)).astimezone(p["tz"])
            locals_[p["name"]] = f"{a.strftime('%a %H:%M')}-{b.strftime('%H:%M')} {a.tzname()}" + ("" if s == 0 else " (outside hours)" if s == 1 else " (PAINFUL)")
        return {
            "start_utc": t0.strftime("%Y-%m-%d %H:%M"),
            "latest_start_utc": t1.strftime("%Y-%m-%d %H:%M") if t1 != t0 else None,
            "window_minutes": int((t1 - t0).total_seconds() // 60) + duration_minutes,
            "local": locals_,
            "outside_hours": [p["name"] for p, s in zip(people, st) if s > 0],
        }

    perfect_raw = windows(lambda s: all(v == 0 for v in s))
    perfect = [describe(a, b - timedelta(minutes=duration_minutes), status(a)) for a, b in perfect_raw][:12]
    compromise = []
    if not perfect:
        best_pain = min((sum(s) for s in stats if 2 not in s), default=None)
        if best_pain is not None:
            comp_raw = windows(lambda s: 2 not in s and sum(s) == best_pain)
            compromise = [describe(a, b - timedelta(minutes=duration_minutes), status(a)) for a, b in comp_raw][:8]
    offsets = [{"name": p["name"], "zone": p["tz"].key, "offset": _offset_label(start.astimezone(p["tz"])), "working_hours_local": f"{fmt_hhmm(p['ws'])}-{fmt_hhmm(p['we'])}"} for p in people]
    dst_flags = [p["name"] for p in people if (start.astimezone(p["tz"]).utcoffset() != end.astimezone(p["tz"]).utcoffset())]
    spread_hours = round((max(int((start.astimezone(p["tz"]).utcoffset() or timedelta()).total_seconds()) for p in people) - min(int((start.astimezone(p["tz"]).utcoffset() or timedelta()).total_seconds()) for p in people)) / 3600, 1)
    if perfect:
        verdict = f"{len(perfect)} window(s) where all {len(people)} are inside working hours. Best: {perfect[0]['start_utc']} UTC ({'; '.join(f'{k} {v}' for k, v in perfect[0]['local'].items())})."
    elif compromise:
        verdict = f"No slot fits everyone's working hours (offset spread {spread_hours} h). Least painful: {compromise[0]['start_utc']} UTC — outside hours for {', '.join(compromise[0]['outside_hours'])}."
    else:
        verdict = f"No workable overlap even allowing 07:00-20:00 (offset spread {spread_hours} h). Split into two meetings or go async."
    return {
        "date_range": f"{d0.isoformat()} +{days} day(s)",
        "duration_minutes": duration_minutes,
        "participants": offsets,
        "offset_spread_hours": spread_hours,
        "everyone_in_hours": perfect,
        "best_compromise": compromise,
        "dst_change_during_range": dst_flags,
        "verdict": verdict,
    }


_KIND_MIN = {"deep": 50, "shallow": 15, "admin": 15}


@AGENT.tool
def pack_day(
    tasks: list[dict],
    fixed_events: list[dict] = [],
    day_start: str = "09:00",
    day_end: str = "18:00",
    peak_start: str = "09:00",
    peak_end: str = "12:00",
    lunch_start: str = "12:30",
    lunch_minutes: int = 30,
    buffer_minutes: int = 10,
    max_block_minutes: int = 90,
) -> dict:
    """Pack tasks into concrete time blocks around fixed meetings: deep work in peak hours first, buffers, leftovers.

    Args:
        tasks: List of {"name": str, "minutes": int, "priority": 1-4 (1 = must today), "kind": "deep"|"shallow"|"admin"}.
        fixed_events: Meetings already on the calendar: {"title": str, "start": "10:00", "end": "10:30"}.
        day_start: Workday start (HH:MM).
        day_end: Workday end (HH:MM).
        peak_start: Start of the user's peak-energy window for deep work.
        peak_end: End of the peak window.
        lunch_start: Lunch start (HH:MM); set lunch_minutes to 0 to skip.
        lunch_minutes: Lunch length in minutes.
        buffer_minutes: Gap to leave after each fixed meeting (0-30).
        max_block_minutes: Longest single focus block; longer tasks are split (45-180).
    """
    tasks = require_list(tasks, "tasks", 100)
    ds, de = parse_hhmm(day_start, "day_start"), parse_hhmm(day_end, "day_end")
    ps, pe = parse_hhmm(peak_start, "peak_start"), parse_hhmm(peak_end, "peak_end")
    if de <= ds:
        raise ToolError("day_end must be after day_start.")
    if pe <= ps:
        raise ToolError("peak_end must be after peak_start.")
    if not (0 <= buffer_minutes <= 30):
        raise ToolError("buffer_minutes must be 0-30.")
    if not (45 <= max_block_minutes <= 180):
        raise ToolError("max_block_minutes must be 45-180.")
    busy: list[tuple[int, int, str, str]] = []
    for i, ev in enumerate(require_list(fixed_events, "fixed_events", 60, min_len=0), 1):
        if not isinstance(ev, dict):
            raise ToolError(f"fixed_events[{i}] must be {{'title','start','end'}}.")
        s, e = parse_hhmm(ev.get("start"), f"fixed_events[{i}].start"), parse_hhmm(ev.get("end"), f"fixed_events[{i}].end")
        if e <= s:
            raise ToolError(f"fixed_events[{i}]: end must be after start.")
        busy.append((s, e, as_str(ev.get("title") or "Meeting", "title", max_len=80), "meeting"))
    if lunch_minutes > 0:
        ls = parse_hhmm(lunch_start, "lunch_start")
        busy.append((ls, ls + int(lunch_minutes), "Lunch", "break"))
    busy.sort()
    norm = []
    for i, t in enumerate(tasks, 1):
        if not isinstance(t, dict):
            raise ToolError(f"tasks[{i}] must be {{'name','minutes','priority','kind'}}.")
        kind = str(t.get("kind", "deep")).lower().strip()
        if kind not in _KIND_MIN:
            raise ToolError(f"tasks[{i}].kind must be deep, shallow or admin.")
        mins = int(as_float(t.get("minutes", 45), f"tasks[{i}].minutes", lo=5, hi=600))
        mins = int(math.ceil(mins / 5.0) * 5)
        pr = int(as_float(t.get("priority", 2), f"tasks[{i}].priority", lo=1, hi=4))
        norm.append({"name": as_str(t.get("name"), f"tasks[{i}].name", max_len=80), "minutes": mins, "priority": pr, "kind": kind, "n": i})
    order = sorted(norm, key=lambda t: (t["priority"], 0 if t["kind"] == "deep" else 1, -t["minutes"], t["n"]))
    # free gaps
    gaps: list[list[int]] = []
    cursor = ds
    for s, e, _, k in busy:
        pad = buffer_minutes if k == "meeting" else 0
        if s > cursor:
            gaps.append([cursor, min(s, de)])
        cursor = max(cursor, e + pad)
    if cursor < de:
        gaps.append([cursor, de])
    gaps = [g for g in gaps if g[1] - g[0] >= 15]
    blocks: list[dict] = []
    unscheduled: list[dict] = []

    def peak_overlap(a: int, b: int) -> int:
        return max(0, min(b, pe) - max(a, ps))

    for t in order:
        remaining = t["minutes"]
        deep = t["kind"] == "deep"
        min_chunk = _KIND_MIN["deep"] if deep else min(t["minutes"], max_block_minutes)  # shallow/admin are not split
        placed_min = 0
        while remaining > 0:
            need = min(remaining, min_chunk)
            candidates = [g for g in gaps if g[1] - g[0] >= need]
            if not candidates:
                break

            def chunk_in(g: list[int]) -> int:
                c = min(remaining, max_block_minutes, g[1] - g[0])
                if deep and 0 < remaining - c < 15:  # avoid a useless orphan
                    c = remaining if g[1] - g[0] >= remaining else c
                return c

            if deep:
                g = max(candidates, key=lambda g: (round(peak_overlap(g[0], g[0] + chunk_in(g)) / chunk_in(g), 2), -g[0]))
            else:
                g = min(candidates, key=lambda g: (peak_overlap(g[0], g[0] + chunk_in(g)), g[0]))
            c = chunk_in(g)
            s = g[0]
            blocks.append({"start": fmt_hhmm(s), "end": fmt_hhmm(s + c), "minutes": c, "task": t["name"], "kind": t["kind"], "priority": t["priority"], "in_peak": peak_overlap(s, s + c) >= c * 0.5})
            placed_min += c
            remaining -= c
            g[0] = s + c + (5 if g[1] - (s + c) >= 20 else 0)
            if g[1] - g[0] < 15:
                gaps.remove(g)
        if remaining > 0:
            unscheduled.append({"task": t["name"], "priority": t["priority"], "minutes_left": remaining, "reason": "no gap large enough" if placed_min == 0 else f"only {placed_min} of {t['minutes']} min fitted"})
    for s, e, title, k in busy:
        blocks.append({"start": fmt_hhmm(s), "end": fmt_hhmm(e), "minutes": e - s, "task": title, "kind": k, "priority": None, "in_peak": None})
    blocks.sort(key=lambda b: b["start"])
    work_min = de - ds
    meeting_min = sum(b["minutes"] for b in blocks if b["kind"] == "meeting")
    deep_min = sum(b["minutes"] for b in blocks if b["kind"] == "deep")
    shallow_min = sum(b["minutes"] for b in blocks if b["kind"] in ("shallow", "admin"))
    free_min = sum(g[1] - g[0] for g in gaps)
    load = round(100 * meeting_min / work_min)
    warnings = []
    if load > 50:
        warnings.append(f"Meeting load {load}% — over the 50% red line; decline or shorten something.")
    if deep_min and not any(b["kind"] == "deep" and b["in_peak"] for b in blocks):
        warnings.append("No deep work landed in the peak window — meetings occupy it; move one meeting.")
    if unscheduled and any(u["priority"] == 1 for u in unscheduled):
        warnings.append("A priority-1 task did not fit. Cut a priority 3-4 task or a meeting before accepting that.")
    longest_deep = max((b["minutes"] for b in blocks if b["kind"] == "deep"), default=0)
    if deep_min and longest_deep < 50:
        warnings.append("Longest deep block is under 50 minutes — not enough for real focus.")
    return {
        "blocks": blocks,
        "unscheduled": unscheduled,
        "stats": {
            "workday_minutes": work_min,
            "meeting_minutes": meeting_min,
            "meeting_load_pct": load,
            "deep_work_minutes": deep_min,
            "shallow_admin_minutes": shallow_min,
            "free_minutes_left": free_min,
            "longest_deep_block": longest_deep,
            "tasks_scheduled": len(norm) - len(unscheduled),
            "tasks_unscheduled": len(unscheduled),
        },
        "warnings": warnings,
        "markdown_table": md_table(["Time", "Block", "Kind", "P"], [[f"{b['start']}-{b['end']}", b["task"], b["kind"], b["priority"] or ""] for b in blocks]),
        "verdict": f"{len(norm) - len(unscheduled)}/{len(norm)} tasks placed: {fmt_duration(deep_min)} deep work, {fmt_duration(meeting_min)} meetings ({load}%), {fmt_duration(free_min)} unallocated."
        + (f" Did not fit: {', '.join(u['task'] for u in unscheduled)}." if unscheduled else ""),
    }


_CATEGORY_RULES = [
    ("1:1", re.compile(r"\b(1:1|1-1|one[- ]on[- ]one|1on1)\b", re.I)),
    ("standup/sync", re.compile(r"\b(stand-?up|daily|sync|check-?in|huddle|scrum)\b", re.I)),
    ("interview/hiring", re.compile(r"\b(interview|hiring|candidate|debrief|screen)\b", re.I)),
    ("review/planning", re.compile(r"\b(review|planning|retro|sprint|roadmap|prioriti|grooming|refinement)\b", re.I)),
    ("external/customer", re.compile(r"\b(customer|client|prospect|demo|vendor|partner|sales|call with)\b", re.I)),
    ("focus", re.compile(r"\b(focus|deep work|heads[- ]down|writing|block|no meetings|DNS)\b", re.I)),
    ("all-hands/social", re.compile(r"\b(all[- ]hands|town ?hall|social|lunch|coffee|birthday|offsite)\b", re.I)),
]


def _categorise(title: str, given: str) -> str:
    if given:
        return given.strip().lower()[:40]
    for label, rx in _CATEGORY_RULES:
        if rx.search(title):
            return label
    return "other meeting"


@AGENT.tool
def audit_calendar(events: list[dict], work_start: str = "09:00", work_end: str = "18:00", focus_block_minutes: int = 90) -> dict:
    """Audit a calendar export: meeting load, fragmentation, back-to-back chains, longest focus block per day, category mix.

    Args:
        events: List of {"title": str, "start": "YYYY-MM-DD HH:MM", "end": "YYYY-MM-DD HH:MM", "category": optional}.
        work_start: Workday start (HH:MM) used to measure free time.
        work_end: Workday end (HH:MM).
        focus_block_minutes: Minimum uninterrupted free minutes that count as a focus block (default 90).
    """
    events = require_list(events, "events", 2000)
    ws, we = parse_hhmm(work_start, "work_start"), parse_hhmm(work_end, "work_end")
    if we <= ws:
        raise ToolError("work_end must be after work_start.")
    if not (30 <= focus_block_minutes <= 240):
        raise ToolError("focus_block_minutes must be 30-240.")
    by_day: dict[str, list[tuple[int, int, str, str]]] = defaultdict(list)
    for i, ev in enumerate(events, 1):
        if not isinstance(ev, dict):
            raise ToolError(f"events[{i}] must be {{'title','start','end'}}.")
        s = parse_datetime(ev.get("start"), f"events[{i}].start")
        e = parse_datetime(ev.get("end"), f"events[{i}].end")
        if e <= s:
            raise ToolError(f"events[{i}]: end must be after start.")
        if (e - s) > timedelta(hours=24):
            continue  # all-day / multi-day items are not meetings
        title = as_str(ev.get("title") or "Untitled", "title", required=False, max_len=120)
        cat = _categorise(title, str(ev.get("category") or ""))
        d = s.date()
        while d <= e.date():
            s_min = s.hour * 60 + s.minute if d == s.date() else 0
            e_min = e.hour * 60 + e.minute if d == e.date() else 24 * 60
            if e_min > s_min:
                by_day[d.isoformat()].append((s_min, e_min, title, cat))
            d += timedelta(days=1)
    days_out, cat_min = [], defaultdict(int)
    tot_meet = tot_frag = tot_b2b = tot_focus_blocks = 0
    for day in sorted(by_day):
        evs = sorted(by_day[day])
        merged: list[list[int]] = []
        for s, e, title, cat in evs:
            if cat != "focus":
                cat_min[cat] += e - s
            if merged and s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        meet = sum(min(e, we) - max(s, ws) for s, e in merged if min(e, we) > max(s, ws))
        b2b = sum(1 for a, b in zip(evs, evs[1:]) if 0 <= b[0] - a[1] < 5)
        gaps = []
        cursor = ws
        for s, e in merged:
            if s > cursor:
                gaps.append(min(s, we) - cursor if min(s, we) > cursor else 0)
            cursor = max(cursor, e)
        if cursor < we:
            gaps.append(we - cursor)
        gaps = [g for g in gaps if g > 0]
        frag = sum(1 for g in gaps if g < 30)
        focus_blocks = sum(1 for g in gaps if g >= focus_block_minutes)
        longest = max(gaps, default=0)
        dt = datetime.fromisoformat(day)
        days_out.append(
            {
                "date": day,
                "weekday": dt.strftime("%a"),
                "meetings": len(evs),
                "meeting_minutes": meet,
                "meeting_load_pct": round(100 * meet / (we - ws)),
                "back_to_back": b2b,
                "fragments_under_30": frag,
                "longest_free_block": longest,
                "focus_blocks": focus_blocks,
                "first_meeting": fmt_hhmm(evs[0][0]),
                "last_meeting_end": fmt_hhmm(max(e for _, e, _, _ in evs)),
            }
        )
        tot_meet += meet
        tot_frag += frag
        tot_b2b += b2b
        tot_focus_blocks += focus_blocks
    if not days_out:
        raise ToolError("No usable events found (all-day items are ignored).")
    n_days = len(days_out)
    capacity = n_days * (we - ws)
    load = round(100 * tot_meet / capacity)
    rag = "RED" if load > 50 else "AMBER" if load > 30 else "GREEN"
    worst = max(days_out, key=lambda d: d["meeting_minutes"])
    best = max(days_out, key=lambda d: d["longest_free_block"])
    cats = sorted(({"category": c, "minutes": m, "share_pct": round(100 * m / max(1, sum(cat_min.values())))} for c, m in cat_min.items()), key=lambda x: -x["minutes"])
    recs = []
    if load > 50:
        recs.append(f"Meeting load {load}% is above the 50% red line: cancel or delegate ~{fmt_duration(tot_meet - 0.4 * capacity)} of meetings per {n_days} days to get to 40%.")
    if tot_frag >= n_days:
        recs.append(f"{tot_frag} free gaps under 30 min — dead time. Cluster meetings into one band per day to reclaim it.")
    if tot_focus_blocks < 2 * n_days:
        recs.append(f"Only {tot_focus_blocks} focus blocks (≥ {focus_block_minutes} min) across {n_days} days; target is 2 per day. Block {best['weekday']} mornings first.")
    if tot_b2b >= 3:
        recs.append(f"{tot_b2b} back-to-back transitions: switch to 25/50-minute meetings to create buffers.")
    if cats and cats[0]["category"] in ("standup/sync", "other meeting") and cats[0]["share_pct"] >= 35:
        recs.append(f"'{cats[0]['category']}' is {cats[0]['share_pct']}% of meeting time — the first candidate to shorten or make async.")
    if not recs:
        recs.append("Calendar is healthy: keep the focus blocks and defend them.")
    return {
        "days_analysed": n_days,
        "meeting_load_pct": load,
        "rag": rag,
        "total_meeting_hours": round(tot_meet / 60, 1),
        "capacity_hours": round(capacity / 60, 1),
        "maker_time_hours": round((capacity - tot_meet) / 60, 1),
        "fragments_under_30": tot_frag,
        "back_to_back_transitions": tot_b2b,
        "focus_blocks": tot_focus_blocks,
        "worst_day": {"date": worst["date"], "weekday": worst["weekday"], "meeting_minutes": worst["meeting_minutes"]},
        "best_focus_day": {"date": best["date"], "weekday": best["weekday"], "longest_free_block": best["longest_free_block"]},
        "by_day": days_out,
        "by_category": cats,
        "recommendations": recs,
        "verdict": f"{rag}: {load}% of {n_days} workdays in meetings ({round(tot_meet / 60, 1)} h), {tot_focus_blocks} focus blocks, {tot_frag} fragments under 30 min, {tot_b2b} back-to-back transitions. Worst day {worst['weekday']} {worst['date']}.",
    }
