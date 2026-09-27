"""Incident Commander — run the incident, then the blameless postmortem, like an SRE lead.

Tools build the timeline with TTD/TTA/TTM/TTR, compute SLO error budgets and
burn rates, grade severity with explicit rules, and audit a postmortem draft
for completeness and blame language.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, timedelta

from ...core import Agent, ToolError
from ...lib import dates
from ._common import bound_list, require_text

AGENT = Agent(
    slug="incident-commander",
    name="Incident Commander",
    category="engineering",
    tagline="Run outages calmly: severity in 60 seconds, a timeline with real MTTR numbers, error-budget math, and a blameless postmortem that gets read.",
    description=(
        "Acts as the incident commander and postmortem author for on-call engineers and SRE leads. Grades "
        "severity with explicit rules, drives the response cadence (roles, comms, mitigation-before-root-"
        "cause), builds the timeline with time-to-detect/acknowledge/mitigate/resolve computed from the "
        "raw log of events, converts SLOs into error-budget and burn-rate numbers, and audits the "
        "postmortem for missing sections, unowned action items and blame language."
    ),
    triggers=[
        "we have an outage / incident, what do we do",
        "what severity is this incident",
        "build the incident timeline / calculate MTTR",
        "write the postmortem / post-incident review",
        "how much error budget do we have left / burn rate",
        "draft the status page update / customer comms for the incident",
    ],
    examples=[
        "Checkout is failing for ~30% of users since 14:02, we think it's the pricing service. Run this.",
        "Here are the Slack timestamps from the incident channel — build the timeline and MTTR.",
        "Our SLO is 99.9% over 30 days and we've had 38 minutes of downtime so far this month. Where are we?",
    ],
    connectors=["PagerDuty", "Opsgenie", "Slack", "Statuspage", "Jira", "Linear", "Datadog", "Notion", "Google Docs"],
    playbook="""
    ## Standard
    You are the incident commander: calm, explicit, and allergic to guessing. Excellent during
    the incident means the fastest *safe* mitigation with clear roles and a comms cadence
    nobody has to ask about. Excellent afterwards means a blameless postmortem whose action
    items would have prevented or shortened this incident and which actually get done. The one
    metric during: **time to mitigate**. The one metric after: **action items closed within
    30 days**.

    ## Intake
    During an incident, do not ask questions the responder can't answer yet. Work from: what
    is broken (symptom), since when, who is affected (rough %), what changed recently. For a
    postmortem: the timeline events with timestamps, the root cause as understood, and the
    SLO. Ask at most 3 questions, only if severity cannot be graded without them; otherwise
    grade provisionally and say what would change it.

    ## Procedure
    1. **Grade severity first.** Call `incident_commander__grade_severity` with impact
       (users %, core functionality down/degraded, data loss, security, workaround, revenue/h,
       customer-facing). Announce the SEV level, and the response expectations it returns
       (ack time, update cadence, status page, postmortem). Re-grade whenever impact changes.
    2. **Assign roles** (one person each, named): Incident Commander (decides, doesn't debug),
       Ops/Tech Lead (hands on keyboard), Comms Lead (status page, stakeholders, customers),
       Scribe (timeline in the channel). Under SEV3 the IC can also be the scribe.
    3. **Mitigate before you diagnose.** Order of options: rollback the last change → feature
       flag off → failover / scale out → shed load / rate limit → restart → hotfix. Rollback is
       the default when a deploy is within the impact window. Root cause is for the
       postmortem, not the incident. Say explicitly: "mitigation X, expected effect Y, we'll
       know by HH:MM".
    4. **Communicate on a cadence.** SEV1 every 30 min, SEV2 hourly, even if nothing changed
       ("still investigating, next update at HH:MM"). Every update: what's affected, what
       we're doing, when the next update comes. No speculation on cause, no blame, no jargon.
    5. **Keep the timeline as you go**: every event as `HH:MM <what happened>` in the channel.
       When it's over (or at the retro), call `incident_commander__build_timeline` with the
       lines. It sorts, computes gaps, tags detect/ack/identify/mitigate/resolve milestones,
       and returns TTD, TTA, TTM, TTR and any >30-minute comms gaps.
    6. **Quantify against the SLO.** Call `incident_commander__error_budget` with the SLO,
       window, and this incident's downtime (or bad/total requests). Report budget consumed by
       this incident, remaining for the window, and the burn rate. That number, not adjectives,
       decides whether the team pauses feature work.
    7. **Write the postmortem** with the output format. Then call
       `incident_commander__check_postmortem` on the draft: fix missing sections, unowned or
       undated action items, unquantified impact, and any blame language it flags. A
       postmortem with fewer than 2 action items or one that names "human error" as the root
       cause is not done.

    ## Frameworks
    - **Severity rules** (defaults; teams can tune the thresholds): SEV1 = data loss, security
      breach, or core customer-facing functionality down for ≥25% of users, or major revenue
      loss; SEV2 = core functionality degraded/down for ≥5% or no workaround; SEV3 = minor
      impact with workaround; SEV4 = cosmetic/internal.
    - **Incident metrics**: TTD (impact start → detected), TTA (detected → acknowledged),
      TTM (impact start → mitigated), TTR (impact start → resolved). Detection by customer
      report instead of monitoring is itself an action item.
    - **Error budget**: budget = (1 − SLO) × window. 99.9%/30d = 43.2 min; 99.95% = 21.6 min;
      99.99% = 4.3 min. Burn rate = fraction consumed ÷ fraction of window elapsed. Google's
      multi-window alerts: 14.4× over 1h (2% of budget), 6× over 6h (5%), 1× over 3d (10%).
    - **Blameless postmortem** (Google SRE / Etsy): describe what people knew and did and why
      it made sense at the time; systems and incentives are the root causes, never "X should
      have". Five Whys until you reach a systemic cause; contributing factors, not a single cause.
    - **Action item quality**: each has an owner, a due date, a priority, and a type
      (prevent / detect faster / mitigate faster / process). Prefer "make the mistake
      impossible" over "add a checklist item".

    ## Output format
    During the incident (each update):
    ```
    **[SEV<n>] <title> — update <HH:MM UTC>**
    Impact: <who/what, % users, since HH:MM> · Status: investigating | identified | mitigating | monitoring | resolved
    Current action: <mitigation>, expected effect by <HH:MM>
    Next update: <HH:MM> · IC: @name · Ops: @name · Comms: @name
    ```
    Postmortem:
    ```
    # Postmortem: <title> — <YYYY-MM-DD> — SEV<n>
    **Authors/owner:** · **Status:** draft | reviewed · **Duration:** HH:MM–HH:MM (<n> min)

    ## Summary (3 sentences)
    ## Impact (numbers: users %, requests failed, revenue, SLO budget consumed)
    ## Timeline (UTC) — table from build_timeline, milestones marked
    ## Detection — how we found out, and how we should have
    ## Root cause(s) and contributing factors — systemic, blameless
    ## What went well / What went poorly / Where we got lucky
    ## Action items — | # | Action | Type | Owner | Due | Priority |
    ## Lessons learned
    ```

    ## Anti-patterns
    - Debugging root cause while customers are down instead of rolling back.
    - "We'll update when we know more." Update on a clock, not on news.
    - Severity by gut feel or by who is shouting. Use the rules and re-grade on new facts.
    - Postmortems that say "engineer X deployed without testing". Ask why the system let a
      deploy without tests reach production.
    - Action items like "be more careful" / "add monitoring" with no owner, date or metric.
    - Reporting MTTR without stating whether it's from impact start or from detection.
    - Declaring resolved when the mitigation is in place but the fix isn't verified; use
      "monitoring" until the metric has been clean for a defined period.
    """,
)

# ── timeline ─────────────────────────────────────────────────────────────────

EVENT_RE = re.compile(
    r"^\s*\[?(?:(?P<date>\d{4}-\d{2}-\d{2})[T ])?(?P<h>\d{1,2}):(?P<m>\d{2})(?::(?P<s>\d{2}))?\s*(?P<ampm>[apAP][mM])?\s*(?:Z|UTC|GMT|[+-]\d{2}:?\d{2})?\]?\s*[-–—:|]?\s*(?P<text>.+?)\s*$"
)
MILESTONES = [
    ("impact_start", re.compile(r"\b(impact (started|began)|started (failing|erroring|returning)|began|deploy(ed|ment)?\b|released?|rollout|rolled out|first (error|failure)|latency spike|errors? spike|outage began|went down)\b", re.I)),
    ("detected", re.compile(r"\b(alert(ed|s)?|alarm|page[ds]?|paged|detect(ed|ion)|noticed|monitor(ing)? fired|customer(s)? report(ed|s)?|support ticket|reported)\b", re.I)),
    ("acknowledged", re.compile(r"\b(ack(ed|nowledged)?|joined|incident (declared|opened|created)|declared|on[- ]call (responding|engaged)|war ?room|bridge (opened|started)|IC assigned|took (command|IC))\b", re.I)),
    ("identified", re.compile(r"\b(root cause|identified|traced (it )?to|narrowed (it )?down|culprit|found (the|that)|cause (is|was)|correlated|confirmed .*cause)\b", re.I)),
    ("mitigated", re.compile(r"\b(mitigat(ed|ion)|roll(ed)? ?back|revert(ed)?|fail(ed)? ?over|disabled|feature flag|flag(ged)? off|scaled (up|out)|restart(ed)?|hotfix(ed)?|drained|error rate (dropping|recovering|falling)|recovering)\b", re.I)),
    ("resolved", re.compile(r"\b(resolved|recovered|all[- ]clear|closed|back to normal|fully restored|incident (closed|resolved|over)|monitoring (stable|clean)|stable for)\b", re.I)),
    ("comms", re.compile(r"\b(status ?page|customer comms|posted (an )?update|announced|notified|emailed customers|tweeted|stakeholders? (updated|informed)|comms sent)\b", re.I)),
]


def _fmt_min(m: float | None) -> str | None:
    if m is None:
        return None
    m = round(m)
    h, r = divmod(int(m), 60)
    return f"{h}h {r:02d}m" if h else f"{r}m"


@AGENT.tool
def build_timeline(events: list[str], incident_date: str = "") -> dict:
    """Sort raw incident events ("14:02 first alerts fired", ISO timestamps, or [HH:MM] lines), tag milestones (impact start, detected, acknowledged, identified, mitigated, resolved, comms), and compute TTD, TTA, TTI, TTM, TTR plus comms gaps over 30 minutes.

    Call after the incident with the channel log, or during the retro. Times are treated as
    UTC and midnight roll-over is handled.

    Args:
        events: Lines each starting with a time (HH:MM, HH:MM:SS, 2026-09-27T14:02Z) followed by what happened.
        incident_date: The date the incident started (YYYY-MM-DD) for absolute timestamps; optional.
    """
    events = bound_list(events, "events", 500)
    base_date = dates.parse_date(incident_date) if incident_date else None
    parsed, unparsed = [], []
    first_date: date | None = None
    for i, raw in enumerate(events, 1):
        if not isinstance(raw, str) or not raw.strip():
            continue
        m = EVENT_RE.match(raw)
        if not m or not m.group("text"):
            unparsed.append(raw.strip()[:120])
            continue
        h, mi, s = int(m.group("h")), int(m.group("m")), int(m.group("s") or 0)
        if m.group("ampm"):
            ap = m.group("ampm").lower()
            if ap == "pm" and h < 12:
                h += 12
            if ap == "am" and h == 12:
                h = 0
        if h > 23 or mi > 59 or s > 59:
            unparsed.append(raw.strip()[:120])
            continue
        d = dates.parse_date(m.group("date")) if m.group("date") else None
        if d and first_date is None:
            first_date = d
        day_offset = (d - first_date).days if d and first_date else None
        parsed.append({"n": i, "text": m.group("text").strip(), "hms": h * 3600 + mi * 60 + s, "day_offset": day_offset, "date": d})
    if not parsed:
        raise ToolError("No events with a leading time found. Format each as 'HH:MM what happened'.")
    # assign day offsets for date-less lines: assume input order, roll over midnight when time goes backwards
    day = 0
    prev = None
    for e in parsed:
        if e["day_offset"] is None:
            if prev is not None and e["hms"] < prev - 6 * 3600:
                day += 1
            e["day_offset"] = day
        else:
            day = e["day_offset"]
        prev = e["hms"]
        e["t"] = e["day_offset"] * 86400 + e["hms"]
    parsed.sort(key=lambda e: (e["t"], e["n"]))
    t0 = parsed[0]["t"]
    rows, milestones = [], {}
    prev_t = None
    gaps = []
    start_d = base_date or first_date
    for e in parsed:
        tags = [name for name, rx in MILESTONES if rx.search(e["text"])]
        if "impact_start" in tags and "mitigated" in tags and re.search(r"roll(ed)? ?back|revert", e["text"], re.I):
            tags.remove("impact_start")
        for tag in tags:
            if tag not in milestones or tag in ("resolved", "mitigated") and tag == "resolved":
                milestones.setdefault(tag, e["t"])
        if "resolved" in tags:
            milestones["resolved"] = e["t"]
        elapsed = e["t"] - t0
        delta = (e["t"] - prev_t) if prev_t is not None else 0
        if prev_t is not None and delta > 1800 and ("resolved" not in milestones or milestones["resolved"] > prev_t):
            gaps.append({"after": _clock(prev_t, start_d), "before": _clock(e["t"], start_d), "gap": _fmt_min(delta / 60)})
        rows.append({"time": _clock(e["t"], start_d), "elapsed": _fmt_min(elapsed / 60), "delta": _fmt_min(delta / 60), "event": e["text"], "milestones": tags})
        prev_t = e["t"]
    impact = milestones.get("impact_start", t0)
    det, ack, ident, mit, res = (milestones.get(k) for k in ("detected", "acknowledged", "identified", "mitigated", "resolved"))
    mins = lambda a, b: round((b - a) / 60, 1) if a is not None and b is not None and b >= a else None  # noqa: E731
    metrics = {
        "time_to_detect_min": mins(impact, det),
        "time_to_acknowledge_min": mins(det, ack),
        "time_to_identify_min": mins(det, ident),
        "time_to_mitigate_min": mins(impact, mit),
        "time_to_resolve_min": mins(impact, res),
        "total_span_min": round((parsed[-1]["t"] - t0) / 60, 1),
    }
    notes = []
    if "impact_start" not in milestones:
        notes.append("No explicit impact-start event; first event used as impact start — add a line like '14:02 errors began' if known.")
    if det is None:
        notes.append("No detection event tagged (alert/paged/reported) — TTD unknown.")
    if mit is None:
        notes.append("No mitigation event tagged (rollback/flag/failover/…).")
    if res is None:
        notes.append("No resolution event tagged — still open, or add 'resolved'/'all clear'.")
    if det is not None and re.search(r"customer|support ticket|reported", next((r["event"] for r in rows if "detected" in r["milestones"]), ""), re.I):
        notes.append("Detected via customer report, not monitoring — action item: alert on the failing signal.")
    for g in gaps:
        notes.append(f"{g['gap']} without an event between {g['after']} and {g['before']} — comms/cadence gap.")
    return {
        "events": rows,
        "milestones": {k: _clock(v, start_d) for k, v in milestones.items()},
        "metrics": metrics,
        "metrics_readable": {k.replace("_min", ""): _fmt_min(v) for k, v in metrics.items()},
        "comms_gaps": gaps,
        "unparsed": unparsed,
        "notes": notes,
        "summary": " · ".join(f"{k.replace('time_to_', 'TT').replace('_min', '').upper() if k != 'total_span_min' else 'span'}: {_fmt_min(v)}" for k, v in metrics.items() if v is not None),
    }


def _clock(t: int, start: date | None) -> str:
    day, rem = divmod(int(t), 86400)
    hh, rem = divmod(rem, 3600)
    mm = rem // 60
    if start:
        return f"{(start + timedelta(days=day)).isoformat()} {hh:02d}:{mm:02d}"
    return f"{hh:02d}:{mm:02d}" + (f" (+{day}d)" if day else "")


# ── error budget ─────────────────────────────────────────────────────────────

NINES = [99.0, 99.5, 99.9, 99.95, 99.99, 99.999]


@AGENT.tool
def error_budget(slo_pct: float, window_days: int = 30, downtime_minutes: float = 0, bad_events: int = 0, total_events: int = 0, elapsed_days: float = 0) -> dict:
    """Compute an SLO's error budget for the window, how much a given downtime or bad/total event count consumed, the burn rate versus time elapsed, projected exhaustion, and the multi-window burn-rate alert thresholds.

    Call whenever an incident or a month needs quantifying against the SLO.

    Args:
        slo_pct: The SLO target as a percentage, e.g. 99.9.
        window_days: SLO window length in days (28 or 30 are common).
        downtime_minutes: Minutes of full outage consumed so far in the window (time-based SLO).
        bad_events: Failed requests/events in the window (event-based SLO); use with total_events.
        total_events: Total requests/events in the window.
        elapsed_days: Days of the window elapsed so far, for burn-rate and projection (0 = unknown).
    """
    if not 50 <= slo_pct < 100:
        raise ToolError("slo_pct must be between 50 and 99.999… (e.g. 99.9).")
    if window_days <= 0 or window_days > 366:
        raise ToolError("window_days must be 1-366.")
    if downtime_minutes < 0 or bad_events < 0 or total_events < 0 or elapsed_days < 0:
        raise ToolError("Inputs cannot be negative.")
    if elapsed_days > window_days:
        raise ToolError("elapsed_days cannot exceed window_days.")
    if bad_events and not total_events:
        raise ToolError("total_events is required with bad_events.")
    if bad_events > total_events:
        raise ToolError("bad_events cannot exceed total_events.")
    err_frac = 1 - slo_pct / 100
    budget_min = window_days * 1440 * err_frac
    consumed = None
    basis = None
    if total_events:
        allowed_bad = total_events * err_frac
        consumed = bad_events / allowed_bad if allowed_bad else 0.0
        basis = f"events: {bad_events:,} bad of {total_events:,} (allowed {allowed_bad:,.0f})"
    if downtime_minutes:
        time_consumed = downtime_minutes / budget_min
        if consumed is None:
            consumed, basis = time_consumed, f"time: {downtime_minutes:g} min of {budget_min:.1f} min"
        else:
            basis += f"; time basis would say {round(100 * time_consumed, 1)}%"
    if consumed is None:
        consumed, basis = 0.0, "no consumption given"
    remaining = 1 - consumed
    remaining_min = max(0.0, budget_min * remaining)
    burn = None
    exhaust_day = None
    status = "healthy"
    if elapsed_days > 0:
        elapsed_frac = elapsed_days / window_days
        burn = consumed / elapsed_frac if elapsed_frac else None
        if burn and burn > 0:
            exhaust_day = window_days / burn
        if remaining <= 0:
            status = "exhausted"
        elif burn and burn >= 2:
            status = "critical"
        elif burn and burn > 1:
            status = "burning fast"
    elif remaining <= 0:
        status = "exhausted"
    elif consumed >= 0.5:
        status = "half spent"
    alerts = []
    for burn_rate, long_w, short_w, pct in ((14.4, "1h", "5m", 2), (6.0, "6h", "30m", 5), (1.0, "3d", "6h", 10)):
        alerts.append({"burn_rate": burn_rate, "long_window": long_w, "short_window": short_w, "budget_consumed_pct": pct, "error_rate_threshold_pct": round(100 * burn_rate * err_frac, 4)})
    table = [{"slo_pct": n, "budget_min_per_window": round(window_days * 1440 * (1 - n / 100), 1), "per_year_hours": round(365 * 24 * (1 - n / 100), 2)} for n in NINES]
    policy = {
        "healthy": "Ship normally.",
        "half spent": "Budget half spent — review risky launches; no policy action yet.",
        "burning fast": "Burn rate > 1× — freeze risky changes, prioritise reliability work this sprint.",
        "critical": "Burn rate ≥ 2× — feature freeze until burn is back under 1×; incident review required.",
        "exhausted": "Budget exhausted — feature freeze for the rest of the window; reliability work only.",
    }[status]
    return {
        "slo_pct": slo_pct,
        "window_days": window_days,
        "budget_minutes": round(budget_min, 2),
        "budget_readable": _fmt_min(budget_min),
        "consumed_pct": round(100 * consumed, 1),
        "remaining_pct": round(100 * remaining, 1),
        "remaining_minutes": round(remaining_min, 1),
        "basis": basis,
        "burn_rate": round(burn, 2) if burn is not None else None,
        "projected_exhaustion_day": round(exhaust_day, 1) if exhaust_day and exhaust_day <= window_days else None,
        "status": status,
        "policy": policy,
        "burn_rate_alerts": alerts,
        "reference_table": table,
        "verdict": (f"{slo_pct}% over {window_days}d = {_fmt_min(budget_min)} budget; {round(100 * consumed, 1)}% consumed ({basis}); "
                    f"{_fmt_min(remaining_min)} left" + (f"; burn rate {burn:.2f}×" if burn is not None else "")
                    + (f", exhausts on day {exhaust_day:.0f} of {window_days}" if exhaust_day and exhaust_day <= window_days else "") + f" — {status}."),
    }


# ── severity ─────────────────────────────────────────────────────────────────

RESPONSE = {
    1: {"ack_minutes": 5, "update_cadence": "every 30 minutes", "page": "primary on-call + incident commander + engineering leadership", "status_page": "yes, within 15 minutes", "postmortem": "required, draft within 3 business days, review within 5"},
    2: {"ack_minutes": 15, "update_cadence": "hourly", "page": "primary on-call + incident commander", "status_page": "yes if customer-facing", "postmortem": "required, within 5 business days"},
    3: {"ack_minutes": 60, "update_cadence": "twice a day", "page": "no page — ticket to the owning team, business hours", "status_page": "no (known-issues note if visible)", "postmortem": "lightweight, optional unless repeated"},
    4: {"ack_minutes": 1440, "update_cadence": "on change", "page": "no", "status_page": "no", "postmortem": "no"},
}


@AGENT.tool
def grade_severity(
    users_affected_pct: float,
    core_functionality_down: bool = False,
    degraded: bool = False,
    data_loss: bool = False,
    security_breach: bool = False,
    workaround_available: bool = True,
    revenue_impact_per_hour: float = 0,
    customer_facing: bool = True,
    sev1_users_pct: float = 25,
    sev2_users_pct: float = 5,
    sev1_revenue_per_hour: float = 10000,
) -> dict:
    """Grade an incident SEV1-SEV4 with explicit, auditable rules from impact facts, and return the response expectations (ack time, update cadence, who is paged, status page, postmortem) plus what would escalate or de-escalate it.

    Call at the start of every incident and again when impact changes.

    Args:
        users_affected_pct: Share of users (or traffic) affected, 0-100.
        core_functionality_down: A core user journey (login, checkout, core API) is unavailable.
        degraded: Functionality works but slowly/partially/with elevated errors.
        data_loss: Data was lost or corrupted (even for one customer).
        security_breach: Confirmed or strongly suspected unauthorised access/exposure.
        workaround_available: Users can still achieve the outcome another way.
        revenue_impact_per_hour: Estimated revenue lost per hour (same currency as the threshold).
        customer_facing: Whether external customers see the impact (vs internal tooling only).
        sev1_users_pct: Threshold of users affected that makes core-down a SEV1 (default 25).
        sev2_users_pct: Threshold of users affected that makes degradation a SEV2 (default 5).
        sev1_revenue_per_hour: Revenue-per-hour loss that alone makes it SEV1 (default 10,000).
    """
    if not 0 <= users_affected_pct <= 100:
        raise ToolError("users_affected_pct must be 0-100.")
    if revenue_impact_per_hour < 0:
        raise ToolError("revenue_impact_per_hour cannot be negative.")
    reasons = []
    sev = 4
    if security_breach:
        sev, reasons = 1, ["security breach — always SEV1 (legal/notification clocks may be running)"]
    elif data_loss:
        sev, reasons = 1, ["data loss/corruption — always SEV1 until scope is bounded"]
    elif customer_facing and core_functionality_down and users_affected_pct >= sev1_users_pct:
        sev, reasons = 1, [f"core functionality down for {users_affected_pct:g}% of users (≥ {sev1_users_pct:g}%)"]
    elif revenue_impact_per_hour >= sev1_revenue_per_hour > 0:
        sev, reasons = 1, [f"revenue impact {revenue_impact_per_hour:,.0f}/h ≥ {sev1_revenue_per_hour:,.0f}/h"]
    elif customer_facing and core_functionality_down:
        sev, reasons = 2, [f"core functionality down for {users_affected_pct:g}% of users (below the {sev1_users_pct:g}% SEV1 line)"]
    elif customer_facing and degraded and users_affected_pct >= sev2_users_pct:
        sev, reasons = 2, [f"degraded for {users_affected_pct:g}% of users (≥ {sev2_users_pct:g}%)"]
    elif customer_facing and not workaround_available and users_affected_pct > 0:
        sev, reasons = 2, ["no workaround for affected customers"]
    elif revenue_impact_per_hour >= sev1_revenue_per_hour / 10 > 0:
        sev, reasons = 2, [f"revenue impact {revenue_impact_per_hour:,.0f}/h"]
    elif core_functionality_down and not customer_facing:
        sev, reasons = 3, ["internal core tooling down — no customer impact"]
    elif degraded or users_affected_pct > 0:
        sev, reasons = 3, ["minor/partial impact with a workaround"]
    else:
        reasons = ["no measurable user impact"]
    if sev > 1 and not workaround_available and users_affected_pct >= sev1_users_pct and customer_facing:
        sev = min(sev, 2)
        reasons.append("no workaround for a large share of users")
    escalate = []
    if sev > 1:
        escalate.append(f"users affected reaches {sev1_users_pct:g}% with core functionality down, any data loss, any security angle, or revenue ≥ {sev1_revenue_per_hour:,.0f}/h → SEV1")
    if sev > 2:
        escalate.append(f"degradation spreads to ≥ {sev2_users_pct:g}% of users, or the workaround stops working → SEV2")
    deescalate = []
    if sev <= 2:
        deescalate.append("mitigation confirmed and users affected < 1% → SEV3 'monitoring'")
    r = RESPONSE[sev]
    return {
        "severity": f"SEV{sev}",
        "level": sev,
        "reasons": reasons,
        "response": r,
        "escalate_if": escalate,
        "deescalate_if": deescalate,
        "first_three_actions": [
            "Name the IC, Ops lead, Comms lead, Scribe in the channel.",
            "If a deploy/config change is inside the impact window: roll it back now, diagnose later.",
            f"Post the first update ({r['update_cadence']} thereafter): impact, action, next update time.",
        ] if sev <= 2 else ["Open a ticket with impact and workaround.", "Assign to the owning team; fix in normal priority.", "Note it in the weekly ops review."],
        "verdict": f"SEV{sev}: {'; '.join(reasons)}. Ack within {r['ack_minutes']} min, updates {r['update_cadence']}, status page: {r['status_page']}.",
    }


# ── postmortem check ─────────────────────────────────────────────────────────

SECTIONS = {
    "summary": r"\b(summary|overview|tl;?dr)\b",
    "impact": r"\bimpact\b",
    "timeline": r"\btimeline\b",
    "detection": r"\b(detection|how (we|it was) (detected|found|noticed))\b",
    "root cause": r"\b(root cause|causes?|why (it|this) happened)\b",
    "contributing factors": r"\b(contributing factors?|trigger|what made (it|this) worse)\b",
    "response/mitigation": r"\b(response|mitigation|recovery|what we did|remediation)\b",
    "action items": r"\b(action items?|follow[- ]?ups?|remediation items|next steps|corrective actions?)\b",
    "lessons learned": r"\b(lessons? learned|what went well|what went (poorly|badly|wrong)|where we got lucky|takeaways)\b",
}
BLAME_RE = re.compile(
    r"\b(should have|shouldn't have|should not have|failed to|forgot to|neglected|carelessly|negligen\w+|mistakenly|incompetent|didn't bother|didn't (pay attention|check|test)|human error|operator error|"
    r"(his|her|their) (fault|mistake)|blame|fault of|to blame|at fault|sloppy|lazy)\b", re.I)
NAME_BLAME_RE = re.compile(r"\b([A-Z][a-z]+|@\w+)\s+(should have|shouldn't have|failed to|forgot to|mistakenly|didn't (test|check|notice)|caused the|broke)\b")
ACTION_LINE_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)]|\|)\s*(?:\[[ xX]\]\s*)?(.+)$")
OWNER_RE = re.compile(r"(@\w+|\bowner\s*[:=]\s*\S+|\b[A-Z][a-z]+ [A-Z][a-z]+\b|\b(?:[A-Z][a-z]+)\s*\(owner\))")
DUE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2}|due\s*[:=]?\s*\S+|by (end of|eo[wmq]|next|q[1-4]|[A-Z][a-z]+ \d{1,2})|\d{1,2}/\d{1,2}(/\d{2,4})?)\b", re.I)
QUANT_RE = re.compile(r"\b\d[\d,.]*\s*(%|percent|users?|customers?|requests?|minutes?|mins?|hours?|hrs?|errors?|orders?|\$|€|£|k\b|m\b|rps|qps)|\$\s?\d", re.I)


@AGENT.tool
def check_postmortem(text: str) -> dict:
    """Audit a postmortem draft: required sections present, impact quantified, action items with owner and due date, root-cause depth, and blame language (names + 'should have', 'human error') that violates blamelessness.

    Call on the draft before review; fix everything it flags.

    Args:
        text: The postmortem document (Markdown or plain text).
    """
    text = require_text(text, "text", 300_000)
    low = text.lower()
    present, missing = [], []
    for name, rx in SECTIONS.items():
        (present if re.search(rx, low) else missing).append(name)
    # action items
    ai_section = re.split(r"(?im)^#{0,6}\s*(?:action items?|follow[- ]?ups?|next steps|corrective actions?)\b.*$", text, maxsplit=1)
    ai_text = ai_section[1] if len(ai_section) > 1 else ""
    ai_text = re.split(r"(?m)^#{1,6}\s", ai_text, maxsplit=1)[0] if ai_text else ""
    items = []
    for line in ai_text.splitlines():
        m = ACTION_LINE_RE.match(line)
        if not m or len(m.group(1).strip()) < 8 or re.match(r"^\|?\s*-{3,}", line) or re.search(r"\|\s*(action|owner|due|#)\s*\|", line, re.I):
            continue
        body = m.group(1)
        items.append({"text": body.strip()[:140], "has_owner": bool(OWNER_RE.search(body)), "has_due": bool(DUE_RE.search(body)),
                      "vague": bool(re.search(r"\b(be more careful|pay more attention|add (more )?monitoring$|improve (testing|communication)$|better (testing|process)$|investigate$|look into)\b", body, re.I))})
    blame = []
    for m in NAME_BLAME_RE.finditer(text):
        blame.append({"phrase": m.group(0), "why": "names a person with a should-have/failed-to construction"})
    for m in BLAME_RE.finditer(text):
        ctx = text[max(0, m.start() - 40):m.end() + 40].replace("\n", " ")
        blame.append({"phrase": m.group(0), "context": ctx.strip(), "why": "blame language — describe the system condition that made the action reasonable"})
    seen = set()
    blame = [b for b in blame if not (b["phrase"].lower() in seen or seen.add(b["phrase"].lower()))][:20]
    quantified = len(QUANT_RE.findall(text))
    whys = len(re.findall(r"\bbecause\b|\bwhy\b|\bwhich (meant|caused|led to)\b|\bdue to\b", low))
    single_cause = bool(re.search(r"\b(the|a) single root cause\b|\broot cause was (that )?(a|an|the) (engineer|developer|person|human)\b", low))
    score = 100
    score -= 8 * len(missing)
    score -= 15 if not items else 0
    score -= 5 * sum(1 for i in items if not i["has_owner"]) + 5 * sum(1 for i in items if not i["has_due"]) + 5 * sum(1 for i in items if i["vague"])
    score -= 10 if quantified < 3 else 0
    score -= 10 * min(3, len(blame))
    score -= 5 if whys < 3 else 0
    score -= 10 if single_cause else 0
    score = max(0, score)
    findings = []
    for s in missing:
        findings.append(f"missing section: {s}")
    if not items:
        findings.append("no action items found (need ≥ 2, each with owner, due date, type)")
    elif len(items) < 2:
        findings.append("only one action item — an incident usually needs prevent + detect-faster items")
    for i in items:
        if not i["has_owner"]:
            findings.append(f"action item without owner: \"{i['text'][:60]}\"")
        if not i["has_due"]:
            findings.append(f"action item without due date: \"{i['text'][:60]}\"")
        if i["vague"]:
            findings.append(f"vague action item: \"{i['text'][:60]}\" — make it verifiable")
    if quantified < 3:
        findings.append(f"impact barely quantified ({quantified} numeric statements) — add users %, failed requests, duration, budget consumed")
    if whys < 3:
        findings.append("causal chain is shallow — apply Five Whys until a systemic cause (process, tooling, design) appears")
    if single_cause:
        findings.append("a person is named as the root cause — the root cause is the system that allowed it")
    for b in blame:
        findings.append(f"blame language: \"{b['phrase']}\"")
    verdict = ("Ready for review." if score >= 85 and not blame and items else "Needs work before review." if score >= 60 else "Not ready — structural gaps.") + f" Score {score}/100."
    return {
        "score": score,
        "sections_present": present,
        "sections_missing": missing,
        "action_items": items,
        "action_items_complete": sum(1 for i in items if i["has_owner"] and i["has_due"] and not i["vague"]),
        "quantified_statements": quantified,
        "causal_depth_signals": whys,
        "blame_flags": blame,
        "findings": findings,
        "verdict": verdict,
    }
