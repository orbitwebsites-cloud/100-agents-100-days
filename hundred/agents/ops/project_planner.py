"""Project Planner — turns a task list into a critical-path schedule with real dates, float, and a Gantt."""

from __future__ import annotations

import math
from collections import defaultdict, deque
from datetime import date, timedelta

from ...core import Agent, ToolError
from ...lib import dates
from ._common import as_float, as_str, as_str_list, md_table, require_list

AGENT = Agent(
    slug="project-planner",
    name="Project Planner",
    category="ops",
    tagline="Turn a task list into a critical-path plan with real dates, float, risk buffers and a Gantt.",
    description=(
        "Builds the plan a senior PM would: dependency graph, Critical Path Method (forward/backward "
        "pass, total and free float, cycle detection), business-day calendar scheduling around holidays, "
        "PERT three-point estimates with P80/P90 confidence dates, a text Gantt, and a slip report when "
        "reality diverges. Every date is computed, never guessed."
    ),
    triggers=[
        "plan this project / build a project plan",
        "what's the critical path",
        "when will this be done if we start on X",
        "make a gantt chart or timeline from these tasks",
        "how much buffer do we need / P80 date",
        "which tasks are slipping and what does it do to the end date",
    ],
    examples=[
        "Here are 12 tasks with durations and dependencies — build the plan starting Oct 5 and tell me the end date.",
        "Which of these tasks are on the critical path, and how much slack do the others have?",
        "Give me optimistic/likely/pessimistic estimates rolled up into a P80 launch date.",
        "We're 3 weeks in. Here's baseline vs actual for each milestone — how bad is the slip?",
    ],
    connectors=["Linear", "Asana", "Jira", "Notion", "Google Sheets", "Google Calendar", "Slack"],
    playbook="""
    ## Standard
    You are a senior technical program manager. A plan is excellent when it answers, without
    hand-waving: what is the end date, which tasks decide that date, how much confidence do we
    have, and what happens if X slips. The one metric that matters: **the plan survives contact
    with reality** — the critical path is explicit, float is visible, and buffers are sized
    from estimate uncertainty rather than gut feel. Never compute a date or a float in your head.

    ## Intake
    You need: (1) a task list with durations in working days and dependencies, (2) a start
    date, (3) team calendar (holidays, 4-day weeks). If the user gives only a goal, decompose
    it yourself into 8-25 tasks (deliverable-shaped, 1-10 days each — anything longer than
    10 days is two tasks) and state that the durations are your estimates. Ask at most one
    question, and only if the start date is missing AND matters to them. Otherwise assume
    next Monday and say so.

    ## Procedure
    1. **Normalise the task list.** Give every task a short id (T1, T2… or the user's keys),
       a duration in working days (milestones = 0), and a `depends_on` list. Finish-to-start
       only; if the user describes an overlap ("design can start when spec is half done")
       split the predecessor into two tasks. Fixed-date constraints become milestone tasks.
    2. **Run `project_planner__critical_path`** with the task list. It returns ES/EF/LS/LF,
       total float, free float, the critical path(s), near-critical tasks (float ≤ 2 days or
       ≤ 10% of project length), and it rejects cycles and unknown dependencies with the
       offending ids — fix those and re-run rather than guessing.
    3. **Put it on the calendar with `project_planner__schedule_calendar`** (same task list +
       start date + holidays + working days per week). It converts working-day offsets to
       real dates, flags tasks that straddle holidays, and renders a text Gantt. Use those
       dates verbatim in the output.
    4. **Size the buffer.** For tasks on or near the critical path, get optimistic / most
       likely / pessimistic estimates (from the user, or your own: pessimistic ≈ 2× likely for
       novel work, 1.3× for routine) and call `project_planner__pert_estimate`. Report the
       P50 and P80 end dates; commit externally to P80, plan internally to P50. The buffer
       is the gap between them — put it at the END of the chain (Critical Chain style), not
       padded into each task.
    5. **Stress-test.** Identify the three tasks whose slip hurts most: highest (duration ×
       number of dependent successors) with zero float. Name the mitigation for each
       (start earlier, add a person, descope, parallelise by splitting).
    6. **If the project is already running,** call `project_planner__slip_report` with
       baseline vs forecast/actual per milestone. Report slip in working days, the trend,
       and the new forecast end date. Never soften: "3 days late" not "slightly behind".
    7. **Act if connectors exist:** create tasks with dates in Linear/Asana/Jira, milestones
       in Google Calendar. Otherwise output the table ready to paste.

    ## Frameworks
    - **CPM**: total float = LS − ES; float 0 = critical. Free float = earliest successor ES −
      EF (how much this task can slip without touching anyone else).
    - **PERT**: E = (O + 4M + P)/6, σ = (P − O)/6. Chain σ = √Σσ². P80 = E + 0.84σ; P90 = E + 1.28σ.
    - **Critical Chain**: aggressive (50%) task estimates + a project buffer of ~50% of the
      chain length; consume buffer, don't pad tasks. Buffer burn > % chain complete = red.
    - **Sizing rules**: tasks 1-10 working days; ≥ 8 tasks; every task has exactly one owner;
      milestones are zero-duration and verb-free ("Beta live", not "Launch beta").
    - **Parkinson & student syndrome**: publish the P50 dates to the team, keep the buffer
      at project level, and review buffer consumption weekly.

    ## Output format
    ```
    # <Project> — plan (start <YYYY-MM-DD>)
    **End date (P50):** <date> · **Commit date (P80):** <date> · **Working days:** N · **Critical path:** T1 → T4 → T7

    ## Schedule
    | ID | Task | Owner | Days | Start | End | Float | Critical |
    |---|---|---|---|---|---|---|---|

    ## Gantt
    <text gantt from the tool, verbatim>

    ## Risks on the critical path
    1. <Task> — why it's fragile — mitigation
    2. …

    ## Buffer
    Chain P50 = N days, σ = X → P80 adds Y days. Buffer placed after <last task>.

    ## Assumptions
    - <working week, holidays, estimates that are yours>
    ```
    If the project is in flight, add a **## Slip report** section from the slip tool before Risks.

    ## Anti-patterns
    - Computing dates by counting on your fingers. Always use the tools; weekends and
      holidays are where hand-made plans die.
    - Padding every task "to be safe". That hides the real duration and guarantees Parkinson.
      One buffer, at the end, sized by σ.
    - A plan with no float column. If the user can't see which tasks can slip, they'll
      firefight the wrong ones.
    - Tasks like "Backend work — 15 days". Split into deliverables; nobody can report
      progress on a blob.
    - Reporting only the P50 date to stakeholders. Give P50 and P80 and say which is which.
    - Ignoring cycles or unknown dependencies the tool flagged and "fixing" them by deleting
      the dependency. Ask or reason about which direction is real.
    """,
)

EPS = 1e-9


def _normalise_tasks(tasks: list) -> list[dict]:
    tasks = require_list(tasks, "tasks", 500)
    out, ids = [], set()
    for i, raw in enumerate(tasks, 1):
        if not isinstance(raw, dict):
            raise ToolError(f"tasks[{i}] must be an object like {{'id': 'T1', 'duration': 3, 'depends_on': []}}.")
        tid = as_str(raw.get("id") or raw.get("name") or f"T{i}", f"tasks[{i}].id", max_len=60)
        if tid in ids:
            raise ToolError(f"Duplicate task id {tid!r}.")
        ids.add(tid)
        dur = as_float(raw.get("duration", raw.get("days")), f"tasks[{i}].duration", lo=0, hi=3650)
        deps = as_str_list(raw.get("depends_on", raw.get("deps", [])), f"tasks[{i}].depends_on")
        out.append(
            {
                "id": tid,
                "name": as_str(raw.get("name") or tid, "name", max_len=120),
                "duration": dur,
                "depends_on": deps,
                "owner": as_str(raw.get("owner", ""), "owner", required=False, max_len=60),
            }
        )
    by_id = {t["id"]: t for t in out}
    for t in out:
        for d in t["depends_on"]:
            if d not in by_id:
                raise ToolError(f"Task {t['id']!r} depends on unknown task {d!r}. Known ids: {', '.join(sorted(by_id))[:300]}.")
            if d == t["id"]:
                raise ToolError(f"Task {t['id']!r} depends on itself.")
    return out


def _find_cycle(tasks: list[dict]) -> list[str]:
    succ = defaultdict(list)
    for t in tasks:
        for d in t["depends_on"]:
            succ[d].append(t["id"])
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {t["id"]: WHITE for t in tasks}
    stack: list[str] = []

    def dfs(u: str) -> list[str] | None:
        colour[u] = GREY
        stack.append(u)
        for v in succ[u]:
            if colour[v] == GREY:
                return stack[stack.index(v):] + [v]
            if colour[v] == WHITE:
                found = dfs(v)
                if found:
                    return found
        stack.pop()
        colour[u] = BLACK
        return None

    for t in tasks:
        if colour[t["id"]] == WHITE:
            c = dfs(t["id"])
            if c:
                return c
    return []


def _cpm(tasks: list[dict]) -> dict:
    by_id = {t["id"]: t for t in tasks}
    succ: dict[str, list[str]] = defaultdict(list)
    indeg = {t["id"]: len(t["depends_on"]) for t in tasks}
    for t in tasks:
        for d in t["depends_on"]:
            succ[d].append(t["id"])
    order, q = [], deque(t["id"] for t in tasks if indeg[t["id"]] == 0)
    while q:
        u = q.popleft()
        order.append(u)
        for v in succ[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    if len(order) != len(tasks):
        cycle = _find_cycle(tasks)
        raise ToolError("Dependency cycle detected: " + " -> ".join(cycle) + ". Break the loop and re-run.")
    es, ef = {}, {}
    for u in order:
        es[u] = max((ef[d] for d in by_id[u]["depends_on"]), default=0.0)
        ef[u] = es[u] + by_id[u]["duration"]
    project = max(ef.values(), default=0.0)
    ls, lf = {}, {}
    for u in reversed(order):
        lf[u] = min((ls[v] for v in succ[u]), default=project)
        ls[u] = lf[u] - by_id[u]["duration"]
    rows = []
    for u in order:
        tf = ls[u] - es[u]
        ff = min((es[v] for v in succ[u]), default=project) - ef[u]
        rows.append(
            {
                "id": u,
                "name": by_id[u]["name"],
                "owner": by_id[u]["owner"] or None,
                "duration": by_id[u]["duration"],
                "depends_on": by_id[u]["depends_on"],
                "es": es[u],
                "ef": ef[u],
                "ls": ls[u],
                "lf": lf[u],
                "total_float": round(tf, 3),
                "free_float": round(max(0.0, ff), 3),
                "critical": abs(tf) < EPS,
                "successors": succ[u],
            }
        )
    # enumerate critical paths (bounded)
    crit = {r["id"] for r in rows if r["critical"]}
    paths: list[list[str]] = []

    def walk(u: str, path: list[str]) -> None:
        if len(paths) >= 10:
            return
        nxt = [v for v in succ[u] if v in crit and abs(es[v] - ef[u]) < EPS]
        if not nxt:
            paths.append(path)
            return
        for v in nxt:
            walk(v, path + [v])

    for r in rows:
        if r["critical"] and not any(d in crit and abs(ef[d] - es[r["id"]]) < EPS for d in r["depends_on"]):
            walk(r["id"], [r["id"]])
    rows.sort(key=lambda r: (r["es"], -r["duration"], r["id"]))
    return {"rows": rows, "project_duration": project, "critical_paths": paths, "order": order}


@AGENT.tool
def critical_path(tasks: list[dict]) -> dict:
    """Run the Critical Path Method on a task list: early/late dates, float, critical path(s), cycle detection.

    Durations are in working days (milestones = 0). Dependencies are finish-to-start.
    Rejects cycles, self-references and unknown dependency ids with the offending task names.

    Args:
        tasks: List of {"id": str, "name": str, "duration": working days, "depends_on": [ids], "owner": str}.
    """
    norm = _normalise_tasks(tasks)
    res = _cpm(norm)
    rows, project = res["rows"], res["project_duration"]
    near_thresh = max(2.0, 0.10 * project)
    near = [r["id"] for r in rows if not r["critical"] and 0 < r["total_float"] <= near_thresh]
    critical_ids = [r["id"] for r in rows if r["critical"]]
    # risk = duration x downstream reach, for zero-float tasks
    succ = {r["id"]: r["successors"] for r in rows}

    def reach(u: str) -> int:
        seen, stack = set(), list(succ[u])
        while stack:
            v = stack.pop()
            if v not in seen:
                seen.add(v)
                stack.extend(succ[v])
        return len(seen)

    risk = sorted(
        ({"id": r["id"], "name": r["name"], "duration": r["duration"], "dependents": reach(r["id"]), "risk_score": round(r["duration"] * (1 + reach(r["id"])), 1)} for r in rows if r["critical"] and r["duration"] > 0),
        key=lambda x: -x["risk_score"],
    )[:5]
    parallel_peak = 0
    for t in range(int(math.ceil(project)) + 1):
        active = sum(1 for r in rows if r["duration"] > 0 and r["es"] <= t < r["ef"])
        parallel_peak = max(parallel_peak, active)
    table = md_table(
        ["ID", "Task", "Days", "ES", "EF", "LS", "LF", "Float", "Critical"],
        [[r["id"], r["name"], r["duration"], r["es"], r["ef"], r["ls"], r["lf"], r["total_float"], "YES" if r["critical"] else ""] for r in rows],
    )
    return {
        "project_duration_days": project,
        "critical_path": res["critical_paths"][0] if res["critical_paths"] else [],
        "all_critical_paths": res["critical_paths"],
        "critical_task_ids": critical_ids,
        "near_critical_task_ids": near,
        "near_critical_threshold_days": round(near_thresh, 1),
        "tasks": [{k: v for k, v in r.items() if k != "successors"} for r in rows],
        "highest_risk_tasks": risk,
        "peak_parallel_tasks": parallel_peak,
        "markdown_table": table,
        "verdict": (
            f"{len(rows)} tasks, {project:g} working days end-to-end. Critical path: "
            + (" -> ".join(res["critical_paths"][0]) if res["critical_paths"] else "none")
            + f" ({len(critical_ids)} of {len(rows)} tasks have zero float"
            + (f"; {len(res['critical_paths'])} parallel critical paths — fragile" if len(res["critical_paths"]) > 1 else "")
            + f"). {len(near)} near-critical."
        ),
    }


def _working_day_index(start: date, holidays: set[date], workdays: set[int], n: int) -> date:
    """Return the calendar date of working day number n (0 = first working day on/after start)."""
    d = start
    while d.weekday() not in workdays or d in holidays:
        d += timedelta(days=1)
    remaining = n
    while remaining > 0:
        d += timedelta(days=1)
        if d.weekday() in workdays and d not in holidays:
            remaining -= 1
    return d


def _parse_workdays(spec: str) -> set[int]:
    spec = (spec or "").strip().lower()
    names = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
    if not spec or spec in ("mon-fri", "weekdays", "5"):
        return {0, 1, 2, 3, 4}
    if spec in ("mon-thu", "4"):
        return {0, 1, 2, 3}
    days = {names[p[:3]] for p in spec.replace(",", " ").split() if p[:3] in names}
    if not days:
        raise ToolError(f"workdays: expected like 'mon-fri' or 'mon tue wed thu', got {spec!r}.")
    return days


@AGENT.tool
def schedule_calendar(tasks: list[dict], start_date: str, holidays: list[str] = [], workdays: str = "mon-fri", gantt_unit: str = "auto") -> dict:
    """Place a CPM plan on the real calendar: start/end dates per task, project end date and a text Gantt.

    Skips weekends (configurable) and holidays, flags tasks that straddle a holiday, and marks
    critical tasks in the Gantt. Call after critical_path (or instead — it runs CPM itself).

    Args:
        tasks: Same list as critical_path: {"id", "name", "duration" (working days), "depends_on", "owner"}.
        start_date: Project start as YYYY-MM-DD. If it falls on a non-working day, the first working day after is used.
        holidays: Non-working dates as YYYY-MM-DD strings.
        workdays: Working week, e.g. "mon-fri" (default) or "mon-thu" or "mon tue wed thu fri sat".
        gantt_unit: "day", "week" or "auto" (day when the project is ≤ 30 working days, otherwise week).
    """
    norm = _normalise_tasks(tasks)
    start = dates.parse_date(start_date)
    hol = {dates.parse_date(h) for h in as_str_list(holidays, "holidays", 400)}
    wd = _parse_workdays(workdays)
    res = _cpm(norm)
    rows, project = res["rows"], res["project_duration"]
    if project > 3650:
        raise ToolError("Project longer than 10 years of working days — check the durations.")
    cache: dict[int, date] = {}

    def wday(n: float) -> date:
        k = int(math.ceil(n - EPS))
        if k not in cache:
            cache[k] = _working_day_index(start, hol, wd, k)
        return cache[k]

    real_start = wday(0)
    sched = []
    for r in rows:
        if r["duration"] == 0:  # milestone: reached at the end of its last predecessor's day
            s = e = wday(max(r["es"] - 1, 0))
        else:
            s = wday(r["es"])
            e = wday(r["ef"] - 1)
        straddled = sorted(h.isoformat() for h in hol if s <= h <= e)
        sched.append(
            {
                "id": r["id"],
                "name": r["name"],
                "owner": r["owner"],
                "duration": r["duration"],
                "start": s.isoformat(),
                "end": e.isoformat(),
                "total_float": r["total_float"],
                "critical": r["critical"],
                "milestone": r["duration"] == 0,
                "holidays_inside": straddled,
            }
        )
    end = wday(max(project - 1, 0)) if project >= 1 else real_start
    unit = gantt_unit if gantt_unit in ("day", "week") else ("day" if project <= 30 else "week")
    span = 1 if unit == "day" else 7
    total_cal_days = (end - real_start).days + 1
    cols = int(math.ceil(total_cal_days / span))
    cols = max(1, min(cols, 120))
    header_label = "".join(("D" if unit == "day" else "W") + str(i + 1) if (i + 1) % 5 == 1 or unit == "week" else "" for i in range(cols))
    gantt_lines = [f"{'Task':<22} {'Start':<10} {'End':<10} " + (f"{unit}s from {real_start.isoformat()} (each column = 1 {unit}; █ = work, ◆ = milestone, * = critical)")]
    for item in sched:
        s, e = date.fromisoformat(item["start"]), date.fromisoformat(item["end"])
        c0 = (s - real_start).days // span
        c1 = (e - real_start).days // span
        bar = ""
        for c in range(cols):
            if item["milestone"] and c == c0:
                bar += "◆"
            elif c0 <= c <= c1 and not item["milestone"]:
                bar += "█"
            else:
                bar += "·"
        label = (item["name"][:19] + ("*" if item["critical"] else " ")).ljust(22)
        gantt_lines.append(f"{label} {item['start']} {item['end']} {bar}")
    gantt = "\n".join(gantt_lines)
    if cols == 120 and total_cal_days / span > 120:
        gantt += "\n(Gantt truncated at 120 columns.)"
    table = md_table(
        ["ID", "Task", "Owner", "Days", "Start", "End", "Float", "Critical"],
        [[i["id"], i["name"], i["owner"] or "", i["duration"], i["start"], i["end"], i["total_float"], "YES" if i["critical"] else ""] for i in sched],
    )
    return {
        "start_date": real_start.isoformat(),
        "end_date": end.isoformat(),
        "working_days": project,
        "calendar_days": total_cal_days,
        "holidays_applied": sorted(h.isoformat() for h in hol),
        "workdays": sorted(wd),
        "critical_path": res["critical_paths"][0] if res["critical_paths"] else [],
        "tasks": sched,
        "markdown_table": table,
        "gantt": gantt,
        "verdict": f"Starts {dates.fmt(real_start)}, ends {dates.fmt(end)}: {project:g} working days over {total_cal_days} calendar days"
        + (f", {len(hol)} holiday(s) skipped" if hol else "")
        + ".",
    }


@AGENT.tool
def pert_estimate(tasks: list[dict], unit: str = "days") -> dict:
    """PERT three-point estimate per task and for the whole chain: expected, sigma, P50/P80/P90.

    Pass the tasks on the critical path (or any sequential chain). Chain sigma is the root of
    summed variances, so it does not over-count uncertainty like naive summing does.

    Args:
        tasks: List of {"id"/"name": str, "optimistic": n, "most_likely": n, "pessimistic": n}.
        unit: Label for the numbers ("days" default, or "hours", "weeks").
    """
    tasks = require_list(tasks, "tasks", 500)
    rows, total_e, total_var = [], 0.0, 0.0
    for i, raw in enumerate(tasks, 1):
        if not isinstance(raw, dict):
            raise ToolError(f"tasks[{i}] must be an object with optimistic/most_likely/pessimistic.")
        name = as_str(raw.get("id") or raw.get("name") or f"T{i}", "name", max_len=80)
        o = as_float(raw.get("optimistic", raw.get("o")), f"{name}.optimistic", lo=0)
        m = as_float(raw.get("most_likely", raw.get("m", raw.get("likely"))), f"{name}.most_likely", lo=0)
        p = as_float(raw.get("pessimistic", raw.get("p")), f"{name}.pessimistic", lo=0)
        if not (o <= m <= p):
            raise ToolError(f"{name}: need optimistic <= most_likely <= pessimistic (got {o}, {m}, {p}).")
        e = (o + 4 * m + p) / 6
        sd = (p - o) / 6
        total_e += e
        total_var += sd * sd
        rows.append(
            {
                "task": name,
                "optimistic": o,
                "most_likely": m,
                "pessimistic": p,
                "expected": round(e, 2),
                "sigma": round(sd, 2),
                "p80": round(e + 0.8416 * sd, 2),
                "uncertainty_ratio": round(p / o, 2) if o else None,
                "flag": "wide range — decompose or spike" if o and p / o >= 3 else "",
            }
        )
    sigma = math.sqrt(total_var)
    p50, p80, p90 = total_e, total_e + 0.8416 * sigma, total_e + 1.2816 * sigma
    naive = sum(r["pessimistic"] for r in rows)
    return {
        "unit": unit,
        "tasks": rows,
        "chain": {
            "expected_p50": round(p50, 2),
            "sigma": round(sigma, 2),
            "p80": round(p80, 2),
            "p90": round(p90, 2),
            "buffer_for_p80": round(p80 - p50, 2),
            "buffer_for_p80_pct": round(100 * (p80 - p50) / p50, 1) if p50 else None,
            "sum_of_pessimistic": naive,
            "sum_of_most_likely": round(sum(r["most_likely"] for r in rows), 2),
        },
        "verdict": (
            f"Chain P50 = {p50:.1f} {unit}, P80 = {p80:.1f}, P90 = {p90:.1f} (σ {sigma:.1f}). "
            f"Commit to P80 and hold a {p80 - p50:.1f}-{unit} buffer at the end. "
            f"Summing pessimistic estimates would give {naive:g} — that's padding, not planning."
        ),
    }


@AGENT.tool
def slip_report(milestones: list[dict], as_of: str = "", holidays: list[str] = []) -> dict:
    """Compare baseline vs forecast/actual dates per milestone: slip in working days, overdue items, trend.

    Args:
        milestones: List of {"name": str, "baseline": "YYYY-MM-DD", "forecast": "YYYY-MM-DD" (current plan), "actual": "YYYY-MM-DD" or "" (when done)}.
        as_of: Today's date as YYYY-MM-DD. Defaults to today.
        holidays: Non-working dates (YYYY-MM-DD) to exclude from working-day slip counts.
    """
    milestones = require_list(milestones, "milestones", 300)
    today = dates.parse_date(as_of) if as_of else date.today()
    hol = {dates.parse_date(h) for h in as_str_list(holidays, "holidays", 400)}
    rows, slips, overdue, done_on_time, done_late = [], [], [], 0, 0
    for i, raw in enumerate(milestones, 1):
        if not isinstance(raw, dict):
            raise ToolError(f"milestones[{i}] must be an object with name/baseline/forecast.")
        name = as_str(raw.get("name") or f"M{i}", "name", max_len=100)
        base = dates.parse_date(as_str(raw.get("baseline"), f"{name}.baseline"))
        actual_s = as_str(raw.get("actual", ""), "actual", required=False)
        actual = dates.parse_date(actual_s) if actual_s else None
        fc_s = as_str(raw.get("forecast", ""), "forecast", required=False)
        forecast = dates.parse_date(fc_s) if fc_s else (actual or base)
        effective = actual or forecast
        slip = dates.business_days_between(base, effective, hol)
        if actual:
            status = "done on time" if slip <= 0 else "done late"
            done_on_time += slip <= 0
            done_late += slip > 0
        elif effective < today:
            status = "OVERDUE"
            overdue.append(name)
        elif slip > 0:
            status = "slipping"
        elif slip < 0:
            status = "ahead"
        else:
            status = "on plan"
        slips.append(slip)
        rows.append(
            {
                "name": name,
                "baseline": base.isoformat(),
                "forecast": forecast.isoformat(),
                "actual": actual.isoformat() if actual else None,
                "slip_working_days": slip,
                "status": status,
                "days_from_today": (effective - today).days,
            }
        )
    final = max(rows, key=lambda r: r["forecast"]) if rows else None
    open_rows = [r for r in rows if r["actual"] is None]
    worst = max(rows, key=lambda r: r["slip_working_days"]) if rows else None
    avg_slip = round(sum(slips) / len(slips), 1) if slips else 0
    if any(r["status"] == "OVERDUE" for r in rows) or (final and final["slip_working_days"] > 10):
        rag = "RED"
    elif final and final["slip_working_days"] > 0 or avg_slip > 2:
        rag = "AMBER"
    else:
        rag = "GREEN"
    return {
        "as_of": today.isoformat(),
        "rag": rag,
        "milestones": rows,
        "project_end_baseline": max(r["baseline"] for r in rows),
        "project_end_forecast": final["forecast"] if final else None,
        "project_end_slip_working_days": final["slip_working_days"] if final else 0,
        "average_slip_working_days": avg_slip,
        "worst_slip": {"name": worst["name"], "days": worst["slip_working_days"]} if worst else None,
        "overdue": overdue,
        "completed": {"on_time": done_on_time, "late": done_late},
        "open_milestones": len(open_rows),
        "markdown_table": md_table(
            ["Milestone", "Baseline", "Forecast", "Actual", "Slip (wd)", "Status"],
            [[r["name"], r["baseline"], r["forecast"], r["actual"] or "", r["slip_working_days"], r["status"]] for r in rows],
        ),
        "verdict": (
            f"{rag}: project end {final['forecast'] if final else 'n/a'} vs baseline {max(r['baseline'] for r in rows)} "
            f"({final['slip_working_days'] if final else 0:+d} working days). "
            f"{len(overdue)} overdue, {done_late} of {done_on_time + done_late} completed milestones were late."
        ),
    }
