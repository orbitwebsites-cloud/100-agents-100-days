"""Onboarding Planner — a dated 30-60-90 plan, a pre-boarding checklist that lands on time, and a first-month calendar that doesn't overload."""

from __future__ import annotations

from datetime import date, timedelta

from ...core import Agent, ToolError
from ...lib import dates
from ._common import pct, require_list, require_text

AGENT = Agent(
    slug="onboarding-planner",
    name="Onboarding Planner",
    category="career",
    tagline="A 30-60-90 plan with real dates, a pre-boarding checklist that ships equipment on time, and a first-month calendar that lands a first win.",
    description=(
        "Plans a new hire's first 90 days the way the best people-ops teams do: computes every milestone "
        "and check-in date (business-day aware, holiday aware), builds the pre-boarding checklist backwards "
        "from day one with due dates for equipment, accounts and buddy, schedules intro meetings without "
        "overloading week one, and lints any 30-60-90 plan for missing owners, dates, feedback checkpoints "
        "and a first deliverable. Works for managers onboarding a report and for new hires planning their own ramp."
    ),
    triggers=[
        "create a 30-60-90 day plan",
        "onboarding plan / checklist for a new hire",
        "what should my first 90 days look like",
        "pre-boarding checklist before the start date",
        "schedule intro meetings for my new hire",
        "review this onboarding plan",
    ],
    examples=[
        "New Senior PM starts Monday Oct 12. Build the 30-60-90 plan and the pre-boarding checklist.",
        "I start as an engineering manager on Nov 2 — draft my own 90-day plan with dates.",
        "Here's the onboarding doc HR gave me for my new report; check what's missing.",
    ],
    connectors=["Google Calendar", "Notion", "Asana", "Linear", "Slack", "Google Docs", "BambooHR", "Rippling"],
    playbook="""
    ## Standard
    You are a head of people who has onboarded hundreds of hires and knows the numbers: most
    regretted attrition in year one traces to the first 90 days — no clear first win, no
    feedback loop, a manager who was "too busy in week one". Excellence: the hire has working
    access on day one, meets the right ten people in the first two weeks, ships a visible first
    win by day 30, owns a real outcome by day 60, and hears exactly where they stand by day 90.
    The metric: a written 90-day review with no surprises on either side.

    ## Intake
    You need: start date, role (title + the 2-3 outcomes the role owns), manager, and whether
    it's remote/hybrid/onsite. Ask only for the start date and the role's outcomes if missing.
    Assume a 90-day probation/review period and a weekly 1:1 unless told otherwise; say so.

    ## Procedure
    1. **Anchor the dates.** Call `onboarding_planner__build_30_60_90` with the start date, role
       and any company holidays. It returns day 1, end of week 1, day 5 (the 5th working day —
       differs from end of week 1 in a holiday week; read `warnings`), day 30/60/90 (moved off
       weekends/holidays), the probation end, every weekly 1:1 date and the three phase windows.
       Use those dates verbatim; never estimate "about a month in".
    2. **Build the pre-boarding list.** Call `onboarding_planner__preboarding_checklist` with
       the start date and remote flag. Deliver it as a checklist with owners (manager, IT,
       HR, buddy) and the computed due dates; flag anything already overdue relative to today.
    3. **Write the plan** in the template: for each phase (Learn 1-30, Contribute 31-60, Own
       61-90) write 4-6 items, each with an owner, a due date inside the phase, a category
       (access / people / learning / deliverable / feedback) and a "done when". The first
       visible deliverable lands between day 14 and day 30 — small, real, and shown to the team.
       Day 60 owns a metric or a project. Day 90 has a written review conversation.
    4. **Schedule the people.** List the 8-15 stakeholders the hire must meet (manager's peers,
       key partners, the people whose work depends on this role, one skip-level, the buddy)
       with priority 1-3. Call `onboarding_planner__intro_meeting_schedule`. Deliver the dated
       list; priority 1 in week 1, never more than 3 intros a day, none on day 1 morning.
    5. **Lint the plan.** Call `onboarding_planner__check_plan` with the items and the start
       date. Fix every flag: missing owner/date, week-1 overload, no feedback checkpoint by day
       30, deliverable too early (before day 10) or absent, phase mismatches.
    6. **Act if connected:** create calendar holds for 1:1s and 30/60/90 reviews; create tasks
       for the pre-boarding list; post the day-1 agenda to the team channel. Otherwise deliver
       ready to paste and name the connector that would automate it.
    7. **Self-check:** every date is a business day; each phase has a feedback checkpoint;
       the manager's own tasks are on the list (they forget theirs first).

    ## Frameworks
    - **Learn / Contribute / Own (30-60-90):** first 30 days = context, relationships, tools,
      one small visible win; 31-60 = owning a workstream with support, first real decision;
      61-90 = independent ownership of an outcome, a proposal for what to change, written
      two-way review.
    - **Week-one rule:** access working before 10am day 1; manager blocks 60 min on day 1 and
      day 5; no more than 3 intro meetings a day; a buddy who is not the manager.
    - **Feedback cadence:** weekly 1:1 from week 1; explicit "how's it going / where do you
      stand" at days 30, 60, 90; the 90-day is written.
    - **Pre-boarding lead times (business days before start):** offer signed −15, background
      check started −14, equipment ordered −10 (−12 remote, shipping), accounts requested −5,
      buddy assigned −5, first-week calendar −3, welcome note from manager −3, day-1 agenda −1.
    - **First win menu:** fix a small known bug or doc gap; write the "how X works" doc nobody
      has; run one customer/user call and share notes; ship one dashboard tile; own one meeting.
    - Scope note: probation rules and required paperwork vary by country; confirm with HR.

    ## Output format
    ```
    # Onboarding — <Name>, <Role> — starts <YYYY-MM-DD (Day)>
    Manager: … · Buddy: … · 1:1: every <weekday> · Reviews: day 30 <date> · day 60 <date> · day 90 <date>

    ## Pre-boarding (owner → due)
    - [ ] <task> — <owner> — <date> (<status>)

    ## Days 1-30 — Learn (ends <date>)
    | Item | Category | Owner | Due | Done when |
    |---|---|---|---|---|

    ## Days 31-60 — Contribute (ends <date>)
    …
    ## Days 61-90 — Own (ends <date>)
    …

    ## Intro meetings
    | Week | Date | Who | Why |
    |---|---|---|---|

    ## Plan check
    Score NN/100 · flags: …
    ```

    ## Anti-patterns
    - Plans with no dates or with "week 1, week 2" only. Real dates, business-day aware.
    - 12 intro meetings in the first two days. The hire remembers none of them.
    - No deliverable until day 60. Confidence and credibility are built by day 30.
    - The manager's tasks missing from the checklist (calendar, welcome note, day-1 agenda).
    - Feedback only at day 90. By then a struggling hire has been struggling for 11 weeks.
    - Generic corporate onboarding with nothing about this role's actual outcomes.
    """,
)


def _holidays(values: list[str] | None) -> set[date]:
    out = set()
    for v in values or []:
        out.add(dates.parse_date(str(v)))
    return out


def _next_business_day(d: date, hol: set[date]) -> date:
    while d.weekday() >= 5 or d in hol:
        d += timedelta(days=1)
    return d


@AGENT.tool
def build_30_60_90(start_date: str, role: str, manager: str = "", holidays: list[str] | None = None, probation_days: int = 90, one_on_one_weeks: int = 13) -> dict:
    """Compute every onboarding date: day 1, end of week 1 (and the 5th working day), day 30/60/90 moved off weekends and holidays, probation end, weekly 1:1 dates and the three phase windows.

    Args:
        start_date: First day of work, YYYY-MM-DD.
        role: Role title (used to label the plan).
        manager: Manager's name (optional).
        holidays: Company holidays as YYYY-MM-DD strings (optional).
        probation_days: Probation/review period length in calendar days (default 90).
        one_on_one_weeks: How many weekly 1:1 dates to generate (default 13).
    """
    require_text(role, "role", max_chars=200)
    start = dates.parse_date(start_date)
    hol = _holidays(holidays)
    if not 30 <= probation_days <= 365:
        raise ToolError("probation_days must be 30-365.")
    if not 1 <= one_on_one_weeks <= 52:
        raise ToolError("one_on_one_weeks must be 1-52.")
    warnings = []
    if start.weekday() >= 5 or start in hol:
        warnings.append(f"start date {start} is a {'weekend' if start.weekday() >= 5 else 'holiday'} — next business day is {_next_business_day(start, hol)}")
    day1 = start
    # End of the first CALENDAR week (last working day on or before the Sunday of day 1's week),
    # and the fifth working day (the "day 5" manager check-in) — these differ in a holiday week.
    week1_last = day1 + timedelta(days=6 - day1.weekday())
    while week1_last > day1 and (week1_last.weekday() >= 5 or week1_last in hol):
        week1_last -= timedelta(days=1)
    week1_end = week1_last
    day5 = dates.add_business_days(day1, 4, hol)
    week1_bdays = dates.business_days_between(day1, week1_last, hol) + 1
    if week1_bdays < 5 and day1.weekday() == 0:
        hol_in_week = sorted(h.isoformat() for h in hol if day1 <= h <= day1 + timedelta(days=6))
        warnings.append(
            f"week 1 has only {week1_bdays} working day(s) (holidays {', '.join(hol_in_week) or 'none'}) — keep day 1-{week1_bdays} to access, manager and buddy; "
            f"the day-5 check-in lands on {day5} ({day5.strftime('%a')})"
        )

    def milestone(n: int) -> dict:
        raw = day1 + timedelta(days=n - 1)
        adj = _next_business_day(raw, hol)
        return {"day": n, "date": adj.isoformat(), "weekday": adj.strftime("%a"), "moved": adj != raw, "business_days_from_start": dates.business_days_between(day1, adj, hol)}

    d30, d60, d90 = milestone(30), milestone(60), milestone(90)
    probation = milestone(probation_days)
    one_on_ones = []
    for w in range(1, one_on_one_weeks + 1):
        raw = day1 + timedelta(days=7 * (w - 1))
        if w == 1:
            raw = day1 + timedelta(days=1)  # first 1:1 on day 2 — day 1 is the agenda, not the 1:1
        adj = _next_business_day(raw, hol)
        one_on_ones.append({"week": w, "date": adj.isoformat(), "weekday": adj.strftime("%a")})
    phases = [
        {"phase": "Learn", "days": "1-30", "start": day1.isoformat(), "end": d30["date"], "business_days": dates.business_days_between(day1, dates.parse_date(d30["date"]), hol) + 1,
         "goals": [f"Understand how the {role} role creates value here: the 2-3 outcomes it owns and how they're measured", "Working access to every tool by day 1; systems map written by day 10", "Meet the 8-15 people whose work touches this role (priority 1 in week 1)", "Ship one small visible win between day 14 and day 30", "Day-30 conversation: what's clear, what's confusing, what to change"]},
        {"phase": "Contribute", "days": "31-60", "start": (dates.parse_date(d30["date"]) + timedelta(days=1)).isoformat(), "end": d60["date"], "business_days": dates.business_days_between(dates.parse_date(d30["date"]), dates.parse_date(d60["date"]), hol),
         "goals": ["Own one workstream end to end with manager support", "Make and document one real decision with a trade-off", "Present something to the wider team (demo, findings, proposal)", "Day-60 conversation: performance against the level's expectations, in writing"]},
        {"phase": "Own", "days": "61-90", "start": (dates.parse_date(d60["date"]) + timedelta(days=1)).isoformat(), "end": d90["date"], "business_days": dates.business_days_between(dates.parse_date(d60["date"]), dates.parse_date(d90["date"]), hol),
         "goals": ["Independently own an outcome or metric", "Propose one thing to change, with evidence, and get a decision on it", "Draft next-quarter goals with the manager", "Day-90 written review: two-way, no surprises"]},
    ]
    return {
        "role": role,
        "manager": manager or None,
        "day_1": {"date": day1.isoformat(), "weekday": day1.strftime("%A")},
        "week_1_end": {"date": week1_end.isoformat(), "weekday": week1_end.strftime("%a"), "working_days": week1_bdays},
        "day_5": {"date": day5.isoformat(), "weekday": day5.strftime("%a"), "note": "fifth working day — manager's end-of-first-week check-in"},
        "day_30": d30,
        "day_60": d60,
        "day_90": d90,
        "probation_end": probation,
        "one_on_ones": one_on_ones,
        "one_on_one_weekday": one_on_ones[1]["weekday"] if len(one_on_ones) > 1 else one_on_ones[0]["weekday"],
        "phases": phases,
        "holidays_in_period": sorted(h.isoformat() for h in hol if day1 <= h <= dates.parse_date(d90["date"])),
        "warnings": warnings,
        "verdict": f"Day 1 {day1} ({day1.strftime('%a')}); reviews on {d30['date']}, {d60['date']}, {d90['date']}; weekly 1:1 on {one_on_ones[1]['weekday'] if len(one_on_ones) > 1 else one_on_ones[0]['weekday']}s."
        + (f" {len(warnings)} warning(s)." if warnings else ""),
    }


PREBOARD = [
    ("Offer signed and countersigned", "HR", 15, 15, "signed copy filed"),
    ("Background / right-to-work check started", "HR", 14, 14, "check initiated; results due before day 1"),
    ("Equipment ordered (laptop, monitor, peripherals)", "IT", 10, 12, "order confirmation; tracking number for remote"),
    ("Payroll and benefits enrolment sent", "HR", 8, 8, "forms sent; deadline before day 1"),
    ("Buddy assigned and briefed", "Manager", 5, 5, "buddy has accepted and knows the week-1 plan"),
    ("Accounts requested (email, SSO, Slack, repos/CRM/tools)", "IT", 5, 5, "tickets filed with role-based access list"),
    ("Manager writes the 30-60-90 plan draft", "Manager", 5, 5, "plan doc shared with the hire's future skip-level"),
    ("Welcome note from manager sent (what to expect, day-1 logistics)", "Manager", 3, 3, "email sent; reply received"),
    ("First-week calendar built (1:1s, intros ≤ 3/day, team rituals)", "Manager", 3, 3, "invites sent from the hire's new calendar"),
    ("Team told who's joining and why (channel post)", "Manager", 2, 2, "post published"),
    ("Accounts verified working; equipment delivered/at desk", "IT", 1, 2, "test login done"),
    ("Day-1 agenda sent (times, links/location, who they'll meet)", "Manager", 1, 1, "agenda in the hire's inbox"),
]


@AGENT.tool
def preboarding_checklist(start_date: str, remote: bool = False, holidays: list[str] | None = None, today: str = "") -> dict:
    """Build the pre-boarding checklist with due dates counted back in business days from day 1 (longer equipment lead time for remote), flagging anything overdue.

    Args:
        start_date: First day of work, YYYY-MM-DD.
        remote: True if the hire is remote (equipment needs shipping lead time).
        holidays: Company holidays as YYYY-MM-DD strings (optional).
        today: Today's date as YYYY-MM-DD, for overdue flags. Defaults to today.
    """
    start = dates.parse_date(start_date)
    hol = _holidays(holidays)
    now = dates.parse_date(today) if today else date.today()
    items = []
    overdue = []
    for task, owner, lead_onsite, lead_remote, done in PREBOARD:
        lead = lead_remote if remote else lead_onsite
        due = dates.add_business_days(start, -lead, hol)
        status = "overdue" if due < now else "due today" if due == now else "upcoming"
        if status == "overdue":
            overdue.append(task)
        items.append({"task": task, "owner": owner, "lead_business_days": lead, "due": due.isoformat(), "weekday": due.strftime("%a"), "status": status, "done_when": done})
    items.sort(key=lambda i: i["due"])
    by_owner: dict[str, int] = {}
    for i in items:
        by_owner[i["owner"]] = by_owner.get(i["owner"], 0) + 1
    bd_left = dates.business_days_between(now, start, hol) if now <= start else 0
    return {
        "start_date": start.isoformat(),
        "today": now.isoformat(),
        "business_days_until_start": bd_left,
        "remote": remote,
        "items": items,
        "by_owner": by_owner,
        "overdue": overdue,
        "verdict": f"{len(items)} tasks; {bd_left} business days until start; {len(overdue)} overdue."
        + (" Start with: " + overdue[0] + "." if overdue else ""),
    }


CATEGORIES = ("access", "people", "learning", "deliverable", "feedback")
CATEGORY_CUES = {
    "access": ("access", "account", "laptop", "login", "sso", "permissions", "tool", "setup", "set up", "vpn"),
    "people": ("meet", "intro", "1:1", "coffee", "buddy", "stakeholder", "shadow"),
    "learning": ("read", "learn", "understand", "review docs", "onboarding doc", "training", "course", "watch", "study", "map"),
    "deliverable": ("ship", "deliver", "build", "write", "present", "publish", "fix", "launch", "own", "propose", "draft", "dashboard", "demo"),
    "feedback": ("feedback", "check-in", "check in", "review", "retro", "how's it going", "30-day", "60-day", "90-day"),
}


@AGENT.tool
def check_plan(items: list[dict], start_date: str, holidays: list[str] | None = None) -> dict:
    """Lint a 30-60-90 plan: missing owners/dates, phase mismatches, week-1 overload, first deliverable timing, feedback checkpoints and category coverage.

    Args:
        items: [{"task": str, "owner": str, "due": "YYYY-MM-DD", "phase": 30|60|90 (optional), "category": access|people|learning|deliverable|feedback (optional; inferred)}].
        start_date: Day 1, YYYY-MM-DD.
        holidays: Company holidays as YYYY-MM-DD strings (optional).
    """
    require_list(items, "items", max_items=200)
    start = dates.parse_date(start_date)
    hol = _holidays(holidays)
    rows, flags = [], []
    week_load: dict[int, int] = {}
    cats_present: set[str] = set()
    first_deliverable_day = None
    feedback_days: list[int] = []
    for i, it in enumerate(items, 1):
        if not isinstance(it, dict) or not str(it.get("task", "")).strip():
            raise ToolError(f"item #{i} needs a 'task'.")
        task = str(it["task"]).strip()
        owner = str(it.get("owner", "")).strip()
        due_s = str(it.get("due", "")).strip()
        issues = []
        day_n = None
        if not owner:
            issues.append("no owner")
        if not due_s:
            issues.append("no due date")
        else:
            due = dates.parse_date(due_s)
            day_n = (due - start).days + 1
            if day_n < 1:
                issues.append("due before day 1 — belongs in pre-boarding")
            elif day_n > 90:
                issues.append(f"due on day {day_n} — outside the 90-day window")
            if due.weekday() >= 5 or due in hol:
                issues.append(f"due on a {'weekend' if due.weekday() >= 5 else 'holiday'} — move to {_next_business_day(due, hol)}")
            phase = it.get("phase")
            if phase is not None and day_n is not None:
                try:
                    p = int(phase)
                except (TypeError, ValueError):
                    raise ToolError(f"item #{i}: phase must be 30, 60 or 90.") from None
                if p not in (30, 60, 90):
                    raise ToolError(f"item #{i}: phase must be 30, 60 or 90.")
                lo = {30: 1, 60: 31, 90: 61}[p]
                if not lo <= day_n <= p:
                    issues.append(f"tagged phase {p} but due on day {day_n}")
            if 1 <= day_n <= 90:
                wk = (day_n - 1) // 7 + 1
                week_load[wk] = week_load.get(wk, 0) + 1
        low = task.lower()
        cat = str(it.get("category", "")).strip().lower() or next((c for c, cues in CATEGORY_CUES.items() if any(k in low for k in cues)), "other")
        if cat not in CATEGORIES and cat != "other":
            issues.append(f"unknown category '{cat}'")
            cat = "other"
        cats_present.add(cat)
        if cat == "deliverable" and day_n and (first_deliverable_day is None or day_n < first_deliverable_day):
            first_deliverable_day = day_n
        if cat == "feedback" and day_n:
            feedback_days.append(day_n)
        rows.append({"n": i, "task": task, "owner": owner or None, "due": due_s or None, "day": day_n, "category": cat, "issues": issues})
    score = 100
    if any("no owner" in r["issues"] for r in rows):
        n = sum(1 for r in rows if "no owner" in r["issues"])
        flags.append(f"{n} item(s) without an owner")
        score -= min(20, 5 * n)
    if any("no due date" in r["issues"] for r in rows):
        n = sum(1 for r in rows if "no due date" in r["issues"])
        flags.append(f"{n} item(s) without a due date")
        score -= min(20, 5 * n)
    mism = sum(1 for r in rows if any("tagged phase" in x for x in r["issues"]))
    if mism:
        flags.append(f"{mism} item(s) due outside their tagged phase")
        score -= 5 * mism
    if week_load.get(1, 0) > 6:
        flags.append(f"week 1 has {week_load[1]} items — overload; move learning items to week 2")
        score -= 10
    if first_deliverable_day is None:
        flags.append("no deliverable in the plan — add a visible first win due between day 14 and day 30")
        score -= 15
    elif first_deliverable_day < 10:
        flags.append(f"first deliverable on day {first_deliverable_day} — too early to be real; aim for day 14-30")
        score -= 5
    elif first_deliverable_day > 30:
        flags.append(f"first deliverable on day {first_deliverable_day} — credibility is built by day 30")
        score -= 10
    if not any(d <= 30 for d in feedback_days):
        flags.append("no feedback checkpoint by day 30")
        score -= 15
    if not any(61 <= d <= 90 for d in feedback_days):
        flags.append("no day-90 review in the plan")
        score -= 10
    missing = [c for c in CATEGORIES if c not in cats_present]
    if missing:
        flags.append("categories missing: " + ", ".join(missing))
        score -= 5 * len(missing)
    off = sum(1 for r in rows if any("weekend" in x or "holiday" in x for x in r["issues"]))
    if off:
        flags.append(f"{off} item(s) due on a weekend/holiday")
        score -= 3 * off
    score = max(0, score)
    return {
        "score": score,
        "items": rows,
        "week_load": dict(sorted(week_load.items())),
        "categories_present": sorted(cats_present),
        "categories_missing": missing,
        "first_deliverable_day": first_deliverable_day,
        "feedback_checkpoint_days": sorted(feedback_days),
        "flags": flags,
        "verdict": ("Plan is complete." if score >= 85 and not flags else f"Score {score}/100 — {len(flags)} flag(s).") + f" {len(rows)} items, first deliverable day {first_deliverable_day or '—'}.",
    }


@AGENT.tool
def intro_meeting_schedule(start_date: str, stakeholders: list[dict], max_per_day: int = 3, holidays: list[str] | None = None, minutes_default: int = 30) -> dict:
    """Schedule intro meetings across the first four weeks: priority 1 in week 1 (from day 2), 2 in week 2, 3 in weeks 3-4, never more than max_per_day.

    Args:
        start_date: Day 1, YYYY-MM-DD.
        stakeholders: [{"name": str, "role": str, "priority": 1|2|3, "minutes": int (optional), "why": str (optional)}].
        max_per_day: Maximum intro meetings per day (1-5; default 3).
        holidays: Company holidays as YYYY-MM-DD strings (optional).
        minutes_default: Default meeting length when not given (15-60).
    """
    start = dates.parse_date(start_date)
    require_list(stakeholders, "stakeholders", max_items=60)
    if not 1 <= max_per_day <= 5:
        raise ToolError("max_per_day must be 1-5.")
    if not 15 <= minutes_default <= 60:
        raise ToolError("minutes_default must be 15-60.")
    hol = _holidays(holidays)
    people = []
    for i, s in enumerate(stakeholders, 1):
        if not isinstance(s, dict) or not str(s.get("name", "")).strip():
            raise ToolError(f"stakeholder #{i} needs a 'name'.")
        try:
            pr = int(s.get("priority", 2))
        except (TypeError, ValueError):
            raise ToolError(f"stakeholder #{i}: priority must be 1, 2 or 3.") from None
        if pr not in (1, 2, 3):
            raise ToolError(f"stakeholder #{i}: priority must be 1, 2 or 3.")
        people.append({"name": str(s["name"]).strip(), "role": str(s.get("role", "")).strip(), "priority": pr, "minutes": int(s.get("minutes") or minutes_default), "why": str(s.get("why", "")).strip(), "order": i})
    people.sort(key=lambda p: (p["priority"], p["order"]))
    # Business days of the first 4 calendar weeks, starting day 2 (day 1 is the manager + agenda).
    days: list[tuple[date, int]] = []
    d = start
    while True:
        d = _next_business_day(d + timedelta(days=1), hol)
        week = (d - start).days // 7 + 1
        if week > 4:
            break
        days.append((d, week))
    windows = {1: (1,), 2: (2,), 3: (3, 4)}
    load = {i: 0 for i in range(len(days))}
    scheduled, unscheduled = [], []
    for p in people:
        preferred = [i for i, (_, wk) in enumerate(days) if wk in windows[p["priority"]]]
        later = [i for i, (_, wk) in enumerate(days) if wk > max(windows[p["priority"]])]
        placed = False
        for idx in preferred + later:
            if load[idx] < max_per_day:
                load[idx] += 1
                dd, wk = days[idx]
                scheduled.append({**p, "date": dd.isoformat(), "weekday": dd.strftime("%a"), "day": (dd - start).days + 1, "week": wk, "slot": load[idx]})
                placed = True
                break
        if not placed:
            unscheduled.append(p["name"])
    scheduled.sort(key=lambda s: (s["date"], s["slot"]))
    by_week: dict[int, int] = {}
    for s in scheduled:
        by_week[s["week"]] = by_week.get(s["week"], 0) + 1
    total_min = sum(s["minutes"] for s in scheduled)
    return {
        "start_date": start.isoformat(),
        "meetings": scheduled,
        "by_week": dict(sorted(by_week.items())),
        "unscheduled": unscheduled,
        "total_minutes": total_min,
        "share_of_week1_pct": pct(sum(s["minutes"] for s in scheduled if s["week"] == 1), 5 * 8 * 60),
        "verdict": f"{len(scheduled)} intros over {len(by_week)} week(s), max {max_per_day}/day, {total_min} minutes total."
        + (f" {len(unscheduled)} couldn't fit in 4 weeks: {', '.join(unscheduled)}." if unscheduled else ""),
    }
