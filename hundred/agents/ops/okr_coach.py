"""OKR Coach — writes OKRs that survive scrutiny, grades progress against time, and forecasts where a KR will land."""

from __future__ import annotations

import re
from datetime import date, timedelta

from ...core import Agent, ToolError
from ...lib import dates, text
from ._common import as_float, as_str, as_str_list, clamp, md_table, require_list

AGENT = Agent(
    slug="okr-coach",
    name="OKR Coach",
    category="ops",
    tagline="Write OKRs that measure outcomes, grade them honestly against the calendar, and forecast where each KR lands.",
    description=(
        "Coaches OKRs the way Google-trained operators do: lints every objective and key result for the "
        "classic failures (tasks disguised as KRs, no baseline, no number, five objectives per team), grades "
        "progress against time elapsed with on-track/at-risk/off-track thresholds and 0.0-1.0 scores, projects "
        "each KR's end-of-quarter value from its trend, and lays out the check-in, mid-cycle review and scoring "
        "calendar. Turns 'we're doing OKRs' into OKRs that actually steer the quarter."
    ),
    triggers=[
        "write / review / improve our OKRs",
        "are these good key results",
        "grade our OKR progress / score the quarter",
        "are we on track to hit this KR",
        "set up our OKR cadence for the quarter",
        "turn these goals into objectives and key results",
    ],
    examples=[
        "Here are our Q4 OKRs — tell me what's wrong with them before I present to the exec team.",
        "We're 6 weeks into the quarter; here's start/target/current for each KR. Are we on track?",
        "Weekly numbers for our activation KR are 31, 33, 34, 36, 37. Target is 45 by Dec 31 — will we make it?",
        "Set up the OKR check-in and review calendar for Q1 starting Jan 5.",
    ],
    connectors=["Notion", "Google Sheets", "Google Docs", "Linear", "Asana", "Slack", "Google Calendar"],
    playbook="""
    ## Standard
    You are an OKR coach who has run the process at companies where it actually worked. An
    excellent OKR set has 1-3 objectives per team, 2-5 key results each, every KR a measured
    outcome with a baseline and a target, and a cadence that makes people look at the numbers
    weekly. The one metric that matters: **at quarter end, can every KR be scored from data
    without argument?** If a KR needs a debate to score, it was never a KR.

    ## Intake
    Need: the draft OKRs (or the goals behind them), the period (quarter dates), and for
    grading: start, target and current value per KR plus today's date. Ask at most 2
    questions and only if the period or the numbers are missing. If baselines are unknown,
    say "baseline unknown — measure it in week 1" rather than inventing one.

    ## Procedure
    1. **Lint before anything else.** Call `okr_coach__lint_okrs` with the objectives and
       their key results. It flags: metrics inside objectives, objectives longer than ~12
       words, KRs without a number, KRs without a baseline ("from X to Y"), task-shaped KRs
       (launch/ship/implement…), binary KRs, two metrics in one KR, more than 5 KRs or fewer
       than 2. For every flag, rewrite the line and show before → after. Target ≥ 80/100.
    2. **Rewrite pattern.** Objective: qualitative, inspiring, ≤ 12 words, no numbers
       ("Make onboarding effortless for self-serve teams"). KR: `<verb> <metric> from
       <baseline> to <target> [by <date>]` — "Increase week-1 activation from 31% to 45%".
       If a KR looks like a task, ask "what number moves if this succeeds?" and use that.
       Keep a separate "initiatives" list for the tasks; they are not KRs.
    3. **Balance the set.** Pair a quantity KR with a quality guardrail (more signups AND
       activation stays ≥ X). Mix leading (input, moves weekly) and lagging (outcome) KRs.
       Check the cascade: each team objective should support one company KR; name which.
    4. **Grade progress.** With start/target/current per KR and the period, call
       `okr_coach__grade_progress`. It computes progress %, time elapsed %, pace, status
       (on track / at risk / off track / done), the 0.0-1.0 score, and the run-rate needed
       for the rest of the period. Present the table; for every at-risk or off-track KR
       state one concrete recovery action or a proposal to descope, never "keep pushing".
    5. **Forecast.** When you have ≥ 3 historical data points for a KR, call
       `okr_coach__forecast_key_result`. Report the projected end value, whether the trend
       reaches target, and the slope required vs the current slope (e.g. "need 2.1/week,
       running at 1.3/week"). Trust a forecast only when R² ≥ 0.6; below that, say the
       data is too noisy and look at the last 3 points.
    6. **Set the cadence.** Call `okr_coach__okr_calendar` with the period. Output the
       check-in dates (weekly, 15 min: score confidence 1-10 per KR, one blocker each),
       the mid-cycle review (re-plan, don't re-write), next-cycle drafting window, scoring
       date, and retro. Put them in the calendar via connector if available.
    7. **Score at the end** on 0.0-1.0: 0.7 on a stretch KR is success; 1.0 every time
       means sandbagging; < 0.4 means the KR was wrong or the work was. Write a one-line
       learning per KR — the score is less important than the learning.

    ## Frameworks
    - **Doerr's formula**: "I will [Objective] as measured by [Key Results]."
    - **Committed vs aspirational**: committed KRs are expected at 1.0 (missing one needs an
      explanation); aspirational KRs average 0.7. Label each one.
    - **Google scoring bands**: 0.7-1.0 delivered; 0.4-0.6 progress but fell short;
      0.0-0.3 failed to make real progress.
    - **Progress thresholds** (linear expectation): on track if progress ≥ elapsed − 10 pts;
      at risk if ≥ elapsed − 25; otherwise off track. Lagging metrics that back-load
      (revenue closes at quarter end) get judged on pipeline KRs instead.
    - **Limits**: ≤ 3 objectives per team, 2-5 KRs each, ≤ 7 OKRs a person can hold.
    - **Cadence**: weekly check-in (Monday, 15 min), mid-quarter review (week 6-7),
      draft next quarter 3 weeks before end, score in the first week after.

    ## Output format
    ```
    # OKRs — <team>, <period>            Lint score: NN/100

    ## O1: <objective>                    (supports company KR: <…>)
    | KR | Type | Baseline → Target | Current | Progress | Status | Score |
    |---|---|---|---|---|---|---|
    | KR1.1 <verb metric from X to Y> | committed | 31% → 45% | 37% | 43% (time 50%) | at risk | 0.4 |

    **Rewrites**
    - ~~<original>~~ → **<rewritten>** — <why>

    ## Recovery actions
    - KR1.1: <one concrete action, owner, by when> or "propose descope to Y"

    ## Initiatives (not KRs)
    - <task that used to be a KR> → feeds KR1.1

    ## Cadence
    Check-ins: <dates> · Mid-cycle review: <date> · Draft next: <date> · Score: <date>
    ```

    ## Anti-patterns
    - KRs that are tasks ("Launch the new dashboard"). Launching is an initiative; the KR
      is what the dashboard changes.
    - No baseline. "Increase NPS to 50" hides whether that is +2 or +30.
    - Five objectives with five KRs each — 25 numbers nobody looks at. Cut to what matters.
    - Grading by feel ("we're basically on track"). Progress vs time elapsed, from the tool.
    - Scoring 1.0 across the board and calling it a great quarter. It was a sandbag.
    - Rewriting KRs mid-quarter to make them hit. Re-plan the work, not the target.
    - Confusing KPIs (health metrics you watch) with KRs (things you are trying to change).
    """,
)

_TASK_VERBS = re.compile(r"^(launch|ship|build|implement|create|hire|write|publish|deliver|complete|release|migrate|roll ?out|set ?up|define|design|develop|deploy|finish|start|kick ?off|run|hold|conduct|organi[sz]e|document|research|explore|investigate|plan)\b", re.I)
_VAGUE = re.compile(r"\b(improve|better|more|some|several|various|enhance|optimi[sz]e|significantly|substantially|good|great|strong|robust)\b", re.I)
_NUMBER = re.compile(r"(\d+(?:[.,]\d+)?\s*(%|percent|k|m|x|×|pts?|points?|days?|hours?|min|users?|customers?|\$|€|£)?|\$\s?\d|\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|hundred|thousand|million)\b)", re.I)
_BASELINE = re.compile(r"\bfrom\s+[^\s]+.*?\bto\s+[^\s]+|\d[^\n]{0,12}(→|->|to)\s*\d", re.I)
_BINARY = re.compile(r"\b(launched|shipped|live|done|completed|signed|hired|published|delivered|yes/no|is live|in place|exists)\b", re.I)
_TIME = re.compile(r"\b(by|before|within|until|end of|eoq|q[1-4]|h[12]|january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b", re.I)


def _lint_objective(obj: str) -> list[str]:
    issues = []
    n = len(text.words(obj))
    if re.search(r"\d", obj):
        issues.append("contains a number — objectives are qualitative; move the metric into a KR")
    if n > 15:
        issues.append(f"{n} words — cut to ≤ 12; it should fit on a slide title")
    if n < 3:
        issues.append("too short to mean anything — say what changes for whom")
    if _TASK_VERBS.match(obj.strip()):
        issues.append("reads like a project (launch/build/…) — state the outcome the project creates")
    if re.search(r"\b and \b", obj) and n > 8:
        issues.append("two objectives joined by 'and' — split or pick one")
    return issues


def _lint_kr(kr: str) -> list[str]:
    issues = []
    n = len(text.words(kr))
    if not _NUMBER.search(kr):
        issues.append("no number — not measurable; add metric, baseline and target")
    elif not _BASELINE.search(kr):
        issues.append("no baseline — use 'from X to Y' so the ambition is visible")
    if _TASK_VERBS.match(kr.strip()):
        issues.append("task, not outcome — what number moves if this succeeds? Move the task to initiatives")
    if _BINARY.search(kr) and not _BASELINE.search(kr):
        issues.append("binary (done/not done) — replace with a measurable effect, or label it a milestone")
    if _VAGUE.search(kr) and not _NUMBER.search(kr):
        issues.append("vague qualifier without a number")
    if n > 25:
        issues.append(f"{n} words — a KR should be one line (≤ 20 words)")
    if len(re.findall(r"\b\d+(?:\.\d+)?\s*%", kr)) >= 3 or re.search(r"\band\b.*\d.*\band\b.*\d", kr):
        issues.append("looks like two KRs in one — split")
    if not _TIME.search(kr):
        issues.append("(minor) no date — fine if the period is the quarter; otherwise add 'by <date>'")
    return issues


@AGENT.tool
def lint_okrs(objectives: list[dict]) -> dict:
    """Lint an OKR set: metrics-in-objectives, missing numbers/baselines, task-shaped or binary KRs, KR counts. Scores 0-100.

    Args:
        objectives: List of {"objective": str, "key_results": [str, ...]}.
    """
    objectives = require_list(objectives, "objectives", 20)
    out, total_deduct, total_krs = [], 0, 0
    for i, o in enumerate(objectives, 1):
        if isinstance(o, str):
            o = {"objective": o, "key_results": []}
        if not isinstance(o, dict):
            raise ToolError(f"objectives[{i}] must be {{'objective': str, 'key_results': [str]}}.")
        obj = as_str(o.get("objective"), f"objectives[{i}].objective", max_len=500)
        krs = as_str_list(o.get("key_results", []), f"objectives[{i}].key_results", 20)
        obj_issues = _lint_objective(obj)
        kr_rows = []
        deduct = 4 * len(obj_issues)
        if len(krs) < 2:
            obj_issues.append(f"only {len(krs)} key result(s) — need 2-5 to triangulate the objective")
            deduct += 10
        elif len(krs) > 5:
            obj_issues.append(f"{len(krs)} key results — cut to ≤ 5; the rest are initiatives or KPIs")
            deduct += 6
        for k, kr in enumerate(krs, 1):
            iss = _lint_kr(kr)
            major = [x for x in iss if not x.startswith("(minor)")]
            deduct += 6 * len(major)
            kr_rows.append({"n": f"KR{i}.{k}", "text": kr, "issues": iss, "ok": not major})
        total_krs += len(krs)
        score = int(clamp(100 - deduct, 0, 100))
        total_deduct += deduct
        out.append({"n": f"O{i}", "objective": obj, "issues": obj_issues, "key_results": kr_rows, "score": score})
    if len(objectives) > 3:
        global_issues = [f"{len(objectives)} objectives — more than 3 per team dilutes focus"]
        total_deduct += 8
    else:
        global_issues = []
    score = int(clamp(100 - total_deduct / max(1, len(objectives)) - (8 if global_issues else 0), 0, 100))
    n_flags = sum(len(o["issues"]) for o in out) + sum(len([x for x in k["issues"] if not x.startswith("(minor)")]) for o in out for k in o["key_results"])
    grade = "ready" if score >= 80 else "needs rewrites" if score >= 55 else "start over with the outcome question"
    return {
        "score": score,
        "grade": grade,
        "objectives": out,
        "set_issues": global_issues,
        "counts": {"objectives": len(objectives), "key_results": total_krs, "flags": n_flags},
        "rewrite_pattern": "KR = <verb> <metric> from <baseline> to <target> [by <date>]; Objective = qualitative, ≤ 12 words, no numbers.",
        "verdict": f"Lint score {score}/100 ({grade}): {n_flags} flag(s) across {len(objectives)} objective(s) and {total_krs} KRs."
        + (" " + global_issues[0] + "." if global_issues else ""),
    }


@AGENT.tool
def grade_progress(key_results: list[dict], period_start: str, period_end: str, as_of: str = "") -> dict:
    """Grade each KR against time elapsed: progress %, pace, on/at-risk/off-track status, 0.0-1.0 score, run-rate needed.

    Args:
        key_results: List of {"name": str, "start": number, "target": number, "current": number, "type": "committed"|"aspirational"}.
        period_start: First day of the OKR period (YYYY-MM-DD).
        period_end: Last day of the period (YYYY-MM-DD).
        as_of: Grading date (YYYY-MM-DD); defaults to today.
    """
    krs = require_list(key_results, "key_results", 50)
    p0, p1 = dates.parse_date(period_start), dates.parse_date(period_end)
    if p1 <= p0:
        raise ToolError("period_end must be after period_start.")
    today = dates.parse_date(as_of) if as_of else date.today()
    total_days = (p1 - p0).days
    elapsed_days = int(clamp((today - p0).days, 0, total_days))
    elapsed_pct = round(100 * elapsed_days / total_days, 1)
    weeks_left = max(0.0, (p1 - max(today, p0)).days / 7)
    weeks_gone = max(elapsed_days / 7, 1e-9)
    rows = []
    for i, kr in enumerate(krs, 1):
        if not isinstance(kr, dict):
            raise ToolError(f"key_results[{i}] must be {{'name','start','target','current'}}.")
        name = as_str(kr.get("name"), f"key_results[{i}].name", max_len=200)
        s = as_float(kr.get("start"), f"{name}.start")
        t = as_float(kr.get("target"), f"{name}.target")
        c = as_float(kr.get("current"), f"{name}.current")
        if t == s:
            raise ToolError(f"{name}: target equals start — nothing to measure.")
        ktype = str(kr.get("type", "aspirational")).lower()
        progress = 100 * (c - s) / (t - s)
        direction = "up" if t > s else "down"
        if progress >= 100:
            status = "done"
        elif progress >= elapsed_pct - 10:
            status = "on track"
        elif progress >= elapsed_pct - 25:
            status = "at risk"
        else:
            status = "off track"
        score = round(clamp(progress / 100, 0, 1), 1)
        band = "delivered" if score >= 0.7 else "fell short" if score >= 0.4 else "no real progress"
        remaining = t - c if direction == "up" else c - t
        needed_rate = (remaining / weeks_left) if weeks_left > 0 and remaining > 0 else 0.0
        achieved_rate = (c - s if direction == "up" else s - c) / weeks_gone
        rows.append(
            {
                "name": name,
                "type": ktype,
                "start": s,
                "target": t,
                "current": c,
                "direction": direction,
                "progress_pct": round(progress, 1),
                "time_elapsed_pct": elapsed_pct,
                "pace": round(progress / elapsed_pct, 2) if elapsed_pct else None,
                "status": status,
                "score": score,
                "band": band,
                "remaining": round(max(0.0, remaining), 2),
                "needed_per_week": round(needed_rate, 2),
                "achieved_per_week": round(achieved_rate, 2),
                "rate_multiplier_needed": round(needed_rate / achieved_rate, 1) if achieved_rate > 0 and needed_rate > 0 else None,
            }
        )
    counts = {k: sum(1 for r in rows if r["status"] == k) for k in ("done", "on track", "at risk", "off track")}
    avg_score = round(sum(r["score"] for r in rows) / len(rows), 2)
    committed_missing = [r["name"] for r in rows if r["type"] == "committed" and r["status"] in ("at risk", "off track")]
    worst = min(rows, key=lambda r: r["progress_pct"] - r["time_elapsed_pct"])
    return {
        "as_of": today.isoformat(),
        "period": {"start": p0.isoformat(), "end": p1.isoformat(), "days": total_days, "elapsed_pct": elapsed_pct, "weeks_left": round(weeks_left, 1)},
        "key_results": rows,
        "counts": counts,
        "average_score": avg_score,
        "committed_at_risk": committed_missing,
        "worst": {"name": worst["name"], "gap_vs_time_pts": round(worst["progress_pct"] - worst["time_elapsed_pct"], 1)},
        "markdown_table": md_table(
            ["KR", "Baseline → Target", "Current", "Progress", "Time", "Status", "Score", "Need/wk vs actual/wk"],
            [[r["name"], f"{r['start']:g} → {r['target']:g}", f"{r['current']:g}", f"{r['progress_pct']}%", f"{r['time_elapsed_pct']}%", r["status"], r["score"], f"{r['needed_per_week']:g} vs {r['achieved_per_week']:g}"] for r in rows],
        ),
        "verdict": f"{elapsed_pct}% of the period gone: {counts['done']} done, {counts['on track']} on track, {counts['at risk']} at risk, {counts['off track']} off track (avg score {avg_score}). "
        + (f"Committed KRs in trouble: {', '.join(committed_missing)}. " if committed_missing else "")
        + f"Worst gap: {worst['name']} ({round(worst['progress_pct'] - worst['time_elapsed_pct'], 1):+} pts vs time).",
    }


@AGENT.tool
def forecast_key_result(history: list[dict], target: float, period_end: str) -> dict:
    """Project a KR's end-of-period value from its trend (least squares), with R², required vs current slope and hit date.

    Args:
        history: At least 3 points of {"date": "YYYY-MM-DD", "value": number}, in any order.
        target: The KR target value.
        period_end: Last day of the period (YYYY-MM-DD).
    """
    history = require_list(history, "history", 500, min_len=3)
    end = dates.parse_date(period_end)
    tgt = as_float(target, "target")
    pts = []
    for i, h in enumerate(history, 1):
        if not isinstance(h, dict):
            raise ToolError(f"history[{i}] must be {{'date','value'}}.")
        pts.append((dates.parse_date(as_str(h.get("date"), f"history[{i}].date")), as_float(h.get("value"), f"history[{i}].value")))
    pts.sort()
    d0 = pts[0][0]
    xs = [(d - d0).days for d, _ in pts]
    ys = [v for _, v in pts]
    if len(set(xs)) < 2:
        raise ToolError("history needs at least two distinct dates.")
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = my - slope * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1 - ss_res / ss_tot if ss_tot else 1.0
    last_d, last_v = pts[-1]
    days_left = (end - last_d).days
    if days_left < 0:
        raise ToolError(f"period_end {end.isoformat()} is before the last data point {last_d.isoformat()}.")
    projected = intercept + slope * (end - d0).days
    direction = "up" if tgt >= ys[0] else "down"
    needed_slope = (tgt - last_v) / days_left if days_left else 0.0
    reaches = (projected >= tgt) if direction == "up" else (projected <= tgt)
    hit_date = None
    if slope != 0:
        days_to = (tgt - intercept) / slope
        if days_to >= xs[-1] and ((direction == "up" and slope > 0) or (direction == "down" and slope < 0)):
            hit_date = (d0 + timedelta(days=int(round(days_to)))).isoformat()
    recent = ys[-3:]
    recent_slope = (recent[-1] - recent[0]) / max(1, xs[-1] - xs[-3])
    confidence = "high" if r2 >= 0.8 and n >= 5 else "medium" if r2 >= 0.6 else "low (noisy — use judgement)"
    return {
        "points": n,
        "first": {"date": d0.isoformat(), "value": ys[0]},
        "last": {"date": last_d.isoformat(), "value": last_v},
        "slope_per_day": round(slope, 4),
        "slope_per_week": round(slope * 7, 3),
        "recent_slope_per_week": round(recent_slope * 7, 3),
        "r_squared": round(r2, 3),
        "confidence": confidence,
        "projected_end_value": round(projected, 2),
        "target": tgt,
        "reaches_target_on_trend": reaches,
        "projected_hit_date": hit_date,
        "hit_after_period_end": bool(hit_date and hit_date > end.isoformat()),
        "needed_slope_per_week": round(needed_slope * 7, 3),
        "slope_multiplier_needed": round(needed_slope / slope, 2) if slope and (needed_slope / slope) > 0 else None,
        "days_left": days_left,
        "verdict": f"Trend projects {projected:.1f} by {end.isoformat()} vs target {tgt:g} → "
        + ("reaches target" if reaches else "MISSES target")
        + f" (R² {r2:.2f}, {confidence}). Running at {slope * 7:.2f}/week; need {needed_slope * 7:.2f}/week"
        + (f" — {needed_slope / slope:.1f}× current pace." if slope and needed_slope / slope > 1 else ".")
        + (f" On trend, target is hit around {hit_date}." if hit_date else ""),
    }


_WD = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4}


@AGENT.tool
def okr_calendar(period_start: str, period_end: str, checkin: str = "weekly", checkin_weekday: str = "monday", as_of: str = "") -> dict:
    """Build the OKR cycle calendar: check-in dates, mid-cycle review, next-cycle drafting window, scoring day, retro.

    Args:
        period_start: First day of the period (YYYY-MM-DD).
        period_end: Last day of the period (YYYY-MM-DD).
        checkin: "weekly" or "biweekly".
        checkin_weekday: Weekday for check-ins (monday-friday).
        as_of: Today's date (YYYY-MM-DD) to compute days-until; defaults to today.
    """
    p0, p1 = dates.parse_date(period_start), dates.parse_date(period_end)
    if p1 <= p0:
        raise ToolError("period_end must be after period_start.")
    if (p1 - p0).days > 400:
        raise ToolError("Period longer than a year — OKR cycles are quarters or halves.")
    if checkin not in ("weekly", "biweekly"):
        raise ToolError("checkin must be 'weekly' or 'biweekly'.")
    wd = _WD.get(checkin_weekday.lower().strip())
    if wd is None:
        raise ToolError("checkin_weekday must be monday-friday.")
    today = dates.parse_date(as_of) if as_of else date.today()
    step = 7 if checkin == "weekly" else 14
    first = p0 + timedelta(days=(wd - p0.weekday()) % 7)
    if first == p0:
        first += timedelta(days=step)  # week 1 is for kickoff, not a check-in
    checkins = []
    d = first
    while d <= p1 - timedelta(days=3):
        checkins.append(d)
        d += timedelta(days=step)
    total = (p1 - p0).days
    mid_target = p0 + timedelta(days=total // 2)
    mid = min(checkins, key=lambda c: abs((c - mid_target).days)) if checkins else mid_target
    draft_start = dates.add_business_days(p1, -15)
    draft_final = dates.add_business_days(p1, -5)
    scoring = dates.add_business_days(p1, 1)
    retro = dates.add_business_days(p1, 4)
    kickoff = p0 if p0.weekday() < 5 else dates.add_business_days(p0, 1)
    events = [
        {"event": "Kickoff: publish OKRs, confirm baselines", "date": kickoff.isoformat()},
        *({"event": f"Check-in {i}", "date": c.isoformat()} for i, c in enumerate(checkins, 1)),
        {"event": "Mid-cycle review (re-plan work, keep targets)", "date": mid.isoformat()},
        {"event": "Start drafting next cycle's OKRs", "date": draft_start.isoformat()},
        {"event": "Next cycle's OKRs finalised", "date": draft_final.isoformat()},
        {"event": "Score this cycle (0.0-1.0) from data", "date": scoring.isoformat()},
        {"event": "Retro: one learning per KR", "date": retro.isoformat()},
    ]
    for e in events:
        e["weekday"] = date.fromisoformat(e["date"]).strftime("%a")
        e["days_from_today"] = (date.fromisoformat(e["date"]) - today).days
    events.sort(key=lambda e: e["date"])
    return {
        "period": {"start": p0.isoformat(), "end": p1.isoformat(), "weeks": round(total / 7, 1)},
        "checkin_cadence": f"{checkin} on {checkin_weekday.title()}s, 15 minutes: confidence 1-10 per KR + one blocker each",
        "checkins": [c.isoformat() for c in checkins],
        "mid_cycle_review": mid.isoformat(),
        "draft_next_cycle": {"start": draft_start.isoformat(), "finalise": draft_final.isoformat()},
        "scoring_day": scoring.isoformat(),
        "retro": retro.isoformat(),
        "events": events,
        "verdict": f"{len(checkins)} {checkin} check-ins from {first.isoformat()}, mid-cycle review {mid.isoformat()}, draft next cycle from {draft_start.isoformat()}, score on {scoring.isoformat()}.",
    }
