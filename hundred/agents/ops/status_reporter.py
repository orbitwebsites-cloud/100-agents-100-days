"""Status Reporter — RAG status from numbers, week-over-week deltas, milestone health, and a report linter."""

from __future__ import annotations

import re
from datetime import date

from ...core import Agent, ToolError
from ...lib import dates, text
from ._common import as_float, as_str, as_str_list, md_table, pct_change, require_list

AGENT = Agent(
    slug="status-reporter",
    name="Status Reporter",
    category="ops",
    tagline="Write the weekly status update execs actually read: computed RAG, real deltas vs last week, and asks up front.",
    description=(
        "Produces the status report of a top program manager. Computes RAG from metric targets with explicit "
        "thresholds (no vibes), diffs this week's task list against last week's to surface what shipped, what "
        "slipped and by how many days, grades milestone health from baseline vs forecast dates, and lints the "
        "draft for length, structure, vagueness and missing asks before it goes out."
    ),
    triggers=[
        "write my weekly status update / report",
        "what's our RAG status",
        "what changed since last week",
        "summarize project progress for leadership",
        "is this milestone red or amber",
        "review my status report before I send it",
    ],
    examples=[
        "Here are this week's metrics vs targets and last week's numbers — give me the RAG and the update.",
        "Last week's task list vs this week's: what got done, what slipped?",
        "Draft the Friday exec update for the migration project from these notes.",
        "Here's my status update draft — tighten it and tell me what a VP would ask.",
    ],
    connectors=["Slack", "Notion", "Google Docs", "Gmail", "Linear", "Jira", "Asana", "Google Sheets"],
    playbook="""
    ## Standard
    You are the program manager whose Friday update executives read first. Excellent means: the
    reader knows the status, the delta and what you need from them in the first 5 lines, every
    colour is backed by a number and a threshold, and nothing is softened. The one metric that
    matters: **decisions made from the report without a follow-up meeting.**

    ## Intake
    Need: this week's facts (metrics with targets, milestones with dates, task list), last
    week's equivalents if available, and the audience (exec, team, customer). Ask at most one
    question, only if the audience is unclear. Missing last-week data → report absolute
    status and say "no baseline yet — deltas start next week".

    ## Procedure
    1. **Compute the colours.** Call `status_reporter__compute_rag` with each metric's
       target, current, previous value and direction. Thresholds default to green ≥ 95% of
       target, amber ≥ 85%, red below; use the project's own thresholds if it has them.
       The overall RAG is the worst metric's colour unless you have a documented reason —
       and then you say the reason.
    2. **Diff the work.** With last week's and this week's item lists, call
       `status_reporter__week_over_week`. It returns completed, added, removed, slipped
       (with days), pulled-in and stale items. "Shipped" means done, not "almost".
    3. **Check the dates.** For milestones call `status_reporter__milestone_health` with
       baseline vs forecast (and actual when done) and the team's holidays, so slip is in
       real working days. Slip 0 = green, 1-5 working days =
       amber, > 5 or overdue = red. Report slip in working days and the new date.
    4. **Write the update** in the Output format. Order: status line → TL;DR (3 bullets max)
       → asks/decisions needed → progress → risks with mitigation and owner → next week.
       Asks come BEFORE progress: the reader is busiest at the top.
    5. **Lint it.** Call `status_reporter__lint_report` on the draft. Fix everything it
       flags: length (150-400 words for an exec update), missing sections, vague phrases
       ("making progress", "on track" with no number), passive voice, sentences > 30 words.
       Re-lint until the score is ≥ 80.
    6. **Send / file** via Slack, Gmail or Notion if connected (post, don't DM the whole
       list). Otherwise output ready to paste. Keep a running "changes since last week" log
       so next week's delta is trivial.

    ## Frameworks
    - **RAG definitions** (write them at the bottom of every report once): Green = on plan,
      no help needed. Amber = at risk, recovery plan in place, may need a decision. Red = off
      plan, needs escalation now. Amber is not "slightly red" — it means there is a plan.
    - **Delta discipline**: every number gets "(vs X last week)". A number without a delta
      is a fact; a number with a delta is a story.
    - **Risk vs issue**: a risk hasn't happened yet (probability × impact, owner,
      mitigation). An issue has (impact, owner, resolution date). Don't mix them.
    - **SCQA for the TL;DR** when status changed: Situation, Complication, Question,
      Answer — in two sentences.
    - **Length**: exec update 150-400 words; team update up to 600; anything longer is a
      document, link it.
    - **Watermelon check**: green outside, red inside. If the metric is amber and the
      milestone slipped, the project is not green because "the team feels good".

    ## Output format
    ```
    **<Project> — week of <date> — 🟢/🟡/🔴 <GREEN/AMBER/RED>** (last week: <colour>)

    **TL;DR**
    - <what changed this week, with numbers and deltas>
    - <biggest risk and its mitigation>
    - <what you need>

    **Asks / decisions needed**
    - <decision> — by <date> — from <person>

    **Progress**
    | Metric | Target | This week | Last week | Δ | RAG |
    | Milestone | Baseline | Forecast | Slip | RAG |
    - Shipped: …  · Slipped: … (+N days, why) · Added: …

    **Risks & issues**
    - 🔴/🟡 <risk> — impact — mitigation — owner — date

    **Next week**
    - <3 concrete deliverables>

    _RAG: Green = on plan · Amber = at risk, plan in place · Red = off plan, escalation needed_
    ```

    ## Anti-patterns
    - "We're making good progress." On what, measured how, versus what?
    - Burying the ask in paragraph four. Asks go above progress.
    - Green because nobody objected. Green is a computed result of numbers and dates.
    - Listing every task done this week. Report outcomes; link the task list.
    - Changing the metrics' definitions week to week so the delta looks good.
    - Reporting risks without owners and mitigations — that's a worry list, not a risk register.
    - Passive voice hiding accountability ("a delay was experienced"). Say who and why.
    """,
)


def _rag_from_attainment(att: float, green: float, amber: float) -> str:
    return "GREEN" if att >= green else "AMBER" if att >= amber else "RED"


@AGENT.tool
def compute_rag(metrics: list[dict], green_pct: float = 95, amber_pct: float = 85) -> dict:
    """Compute RAG per metric from target/current with explicit thresholds, plus delta vs last week and overall status.

    Args:
        metrics: List of {"name": str, "target": number, "current": number, "previous": number or null, "direction": "higher"|"lower", "unit": str}.
        green_pct: Attainment (% of target) at or above which a metric is GREEN (default 95).
        amber_pct: Attainment at or above which a metric is AMBER (default 85); below is RED.
    """
    metrics = require_list(metrics, "metrics", 100)
    g, a = as_float(green_pct, "green_pct", lo=0, hi=200), as_float(amber_pct, "amber_pct", lo=0, hi=200)
    if a >= g:
        raise ToolError("amber_pct must be lower than green_pct.")
    rows = []
    for i, m in enumerate(metrics, 1):
        if not isinstance(m, dict):
            raise ToolError(f"metrics[{i}] must be {{'name','target','current','previous','direction'}}.")
        name = as_str(m.get("name"), f"metrics[{i}].name", max_len=100)
        target = as_float(m.get("target"), f"{name}.target")
        current = as_float(m.get("current"), f"{name}.current")
        prev_raw = m.get("previous")
        previous = as_float(prev_raw, f"{name}.previous") if prev_raw not in (None, "") else None
        direction = str(m.get("direction", "higher")).lower()
        if direction not in ("higher", "lower"):
            raise ToolError(f"{name}.direction must be 'higher' or 'lower'.")
        if direction == "higher":
            att = 100 * current / target if target else (100.0 if current >= 0 else 0.0)
        else:
            att = 100 * target / current if current > 0 else (200.0 if current <= target else 0.0)
            if current <= target:
                att = max(att, 100.0)
        att = round(att, 1)
        rag = _rag_from_attainment(att, g, a)
        delta = None
        if previous is not None:
            change = current - previous
            better = change > 0 if direction == "higher" else change < 0
            prev_att = 100 * previous / target if direction == "higher" and target else (100 * target / previous if previous > 0 else None)
            prev_rag = _rag_from_attainment(round(prev_att, 1), g, a) if prev_att is not None else None
            delta = {
                "abs": round(change, 4),
                "pct": pct_change(current, previous),
                "trend": "improving" if better else "worsening" if change else "flat",
                "arrow": "↑" if change > 0 else "↓" if change < 0 else "→",
                "previous_rag": prev_rag,
                "rag_changed": prev_rag != rag if prev_rag else None,
            }
        rows.append({"name": name, "unit": m.get("unit", ""), "target": target, "current": current, "previous": previous, "direction": direction, "attainment_pct": att, "gap_to_target": round(target - current if direction == "higher" else current - target, 4), "rag": rag, "delta": delta})
    order = {"RED": 0, "AMBER": 1, "GREEN": 2}
    overall = min((r["rag"] for r in rows), key=lambda x: order[x])
    counts = {k: sum(1 for r in rows if r["rag"] == k) for k in ("GREEN", "AMBER", "RED")}
    worst = min(rows, key=lambda r: r["attainment_pct"])
    movers = [r for r in rows if r["delta"] and r["delta"]["pct"] is not None]
    biggest = max(movers, key=lambda r: abs(r["delta"]["pct"])) if movers else None
    changed = [f"{r['name']} {r['delta']['previous_rag']}→{r['rag']}" for r in rows if r["delta"] and r["delta"].get("rag_changed")]
    table = md_table(
        ["Metric", "Target", "This week", "Last week", "Δ", "Attain.", "RAG"],
        [[r["name"], f"{r['target']:g}{r['unit']}", f"{r['current']:g}{r['unit']}", f"{r['previous']:g}{r['unit']}" if r["previous"] is not None else "—", f"{r['delta']['arrow']} {r['delta']['abs']:+g} ({r['delta']['pct']:+g}%)" if r["delta"] and r["delta"]["pct"] is not None else (f"{r['delta']['arrow']} {r['delta']['abs']:+g}" if r["delta"] else "—"), f"{r['attainment_pct']}%", r["rag"]] for r in rows],
    )
    return {
        "overall": overall,
        "counts": counts,
        "metrics": rows,
        "worst_metric": {"name": worst["name"], "attainment_pct": worst["attainment_pct"], "rag": worst["rag"]},
        "biggest_mover": {"name": biggest["name"], "pct": biggest["delta"]["pct"], "trend": biggest["delta"]["trend"]} if biggest else None,
        "rag_changes": changed,
        "thresholds": {"green_pct": g, "amber_pct": a},
        "markdown_table": table,
        "verdict": f"Overall {overall}: {counts['GREEN']} green, {counts['AMBER']} amber, {counts['RED']} red. Worst: {worst['name']} at {worst['attainment_pct']}% of target."
        + (f" Biggest move: {biggest['name']} {biggest['delta']['pct']:+g}% ({biggest['delta']['trend']})." if biggest else "")
        + (f" RAG changes: {', '.join(changed)}." if changed else ""),
    }


_DONE = re.compile(r"^(done|complete|completed|shipped|closed|released|finished|merged|live)$", re.I)


def _norm_items(items: list, label: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i, it in enumerate(require_list(items, label, 500, min_len=0), 1):
        if isinstance(it, str):
            it = {"item": it}
        if not isinstance(it, dict):
            raise ToolError(f"{label}[{i}] must be {{'item','status','due','owner'}}.")
        name = as_str(it.get("item") or it.get("name") or it.get("title"), f"{label}[{i}].item", max_len=200)
        key = re.sub(r"\s+", " ", name.lower().strip())
        due = as_str(it.get("due", ""), "due", required=False)
        out[key] = {"item": name, "status": as_str(it.get("status", ""), "status", required=False, max_len=40), "due": dates.parse_date(due) if due else None, "owner": as_str(it.get("owner", ""), "owner", required=False, max_len=60)}
    return out


@AGENT.tool
def week_over_week(previous: list[dict], current: list[dict], holidays: list[str] = []) -> dict:
    """Diff last week's item list against this week's: completed, added, removed, slipped (days), pulled in, stale.

    Args:
        previous: Last week's items: {"item": str, "status": str, "due": "YYYY-MM-DD", "owner": str}.
        current: This week's items in the same shape.
        holidays: Non-working dates (YYYY-MM-DD) excluded from working-day slip counts.
    """
    prev, cur = _norm_items(previous, "previous"), _norm_items(current, "current")
    hol = {dates.parse_date(h) for h in as_str_list(holidays, "holidays", 400)}
    if not prev and not cur:
        raise ToolError("Both lists are empty.")
    completed, added, removed, slipped, pulled_in, stale, regressed, status_changes = [], [], [], [], [], [], [], []
    for key, c in cur.items():
        p = prev.get(key)
        c_done = bool(_DONE.match(c["status"]))
        if p is None:
            added.append({"item": c["item"], "owner": c["owner"], "due": c["due"].isoformat() if c["due"] else None})
            continue
        p_done = bool(_DONE.match(p["status"]))
        if c_done and not p_done:
            completed.append({"item": c["item"], "owner": c["owner"]})
        elif p_done and not c_done:
            regressed.append({"item": c["item"], "from": p["status"], "to": c["status"]})
        elif c["status"].lower() != p["status"].lower():
            status_changes.append({"item": c["item"], "from": p["status"], "to": c["status"]})
        elif not c_done and c["due"] == p["due"]:
            stale.append({"item": c["item"], "status": c["status"], "owner": c["owner"]})
        if p["due"] and c["due"] and c["due"] != p["due"]:
            days = dates.business_days_between(p["due"], c["due"], hol)
            rec = {"item": c["item"], "from": p["due"].isoformat(), "to": c["due"].isoformat(), "working_days": days, "owner": c["owner"]}
            (slipped if days > 0 else pulled_in).append(rec)
    for key, p in prev.items():
        if key not in cur:
            removed.append({"item": p["item"], "last_status": p["status"]})
    open_prev = sum(1 for p in prev.values() if not _DONE.match(p["status"]))
    throughput = round(100 * len(completed) / open_prev, 1) if open_prev else None
    total_slip = sum(s["working_days"] for s in slipped)
    return {
        "completed": completed,
        "added": added,
        "removed": removed,
        "slipped": sorted(slipped, key=lambda s: -s["working_days"]),
        "pulled_in": pulled_in,
        "status_changes": status_changes,
        "regressed": regressed,
        "stale": stale,
        "counts": {"completed": len(completed), "added": len(added), "removed": len(removed), "slipped": len(slipped), "stale": len(stale), "open_now": sum(1 for c in cur.values() if not _DONE.match(c["status"]))},
        "throughput_pct_of_open": throughput,
        "total_slip_working_days": total_slip,
        "verdict": f"Shipped {len(completed)}, added {len(added)}, removed {len(removed)}, slipped {len(slipped)} ({total_slip} working days total), {len(stale)} stale (unchanged and not done)."
        + (f" Regressed: {', '.join(r['item'] for r in regressed)}." if regressed else "")
        + (f" Throughput: {throughput}% of last week's open items closed." if throughput is not None else ""),
    }


@AGENT.tool
def milestone_health(milestones: list[dict], as_of: str = "", amber_max_days: int = 5, holidays: list[str] = []) -> dict:
    """RAG per milestone from baseline vs forecast/actual dates: slip in working days, overdue, days to go, overall colour.

    Args:
        milestones: List of {"name": str, "baseline": "YYYY-MM-DD", "forecast": "YYYY-MM-DD", "actual": "YYYY-MM-DD" or "", "percent_complete": 0-100 optional}.
        as_of: Today's date (YYYY-MM-DD); defaults to today.
        amber_max_days: Slip in working days up to which a milestone is AMBER rather than RED (default 5).
        holidays: Non-working dates (YYYY-MM-DD) excluded from working-day slip counts (use the project's calendar).
    """
    hol = {dates.parse_date(h) for h in as_str_list(holidays, "holidays", 400)}
    milestones = require_list(milestones, "milestones", 200)
    today = dates.parse_date(as_of) if as_of else date.today()
    if not (1 <= amber_max_days <= 30):
        raise ToolError("amber_max_days must be 1-30.")
    rows = []
    for i, m in enumerate(milestones, 1):
        if not isinstance(m, dict):
            raise ToolError(f"milestones[{i}] must be {{'name','baseline','forecast','actual'}}.")
        name = as_str(m.get("name"), f"milestones[{i}].name", max_len=120)
        base = dates.parse_date(as_str(m.get("baseline"), f"{name}.baseline"))
        actual_s = as_str(m.get("actual", ""), "actual", required=False)
        actual = dates.parse_date(actual_s) if actual_s else None
        fc_s = as_str(m.get("forecast", ""), "forecast", required=False)
        forecast = dates.parse_date(fc_s) if fc_s else (actual or base)
        pct = m.get("percent_complete")
        pct = as_float(pct, f"{name}.percent_complete", lo=0, hi=100) if pct not in (None, "") else None
        eff = actual or forecast
        slip = dates.business_days_between(base, eff, hol)
        days_to_go = (eff - today).days
        reasons = []
        if actual:
            rag = "GREEN" if slip <= 0 else "AMBER" if slip <= amber_max_days else "RED"
            state = "done"
            reasons.append(f"completed {slip:+d} wd vs baseline")
        elif eff < today:
            rag, state = "RED", "OVERDUE"
            reasons.append(f"forecast date passed {(today - eff).days} days ago with no completion")
        else:
            state = "open"
            rag = "GREEN" if slip <= 0 else "AMBER" if slip <= amber_max_days else "RED"
            if slip > 0:
                reasons.append(f"slipped {slip} wd vs baseline")
            if pct is not None and days_to_go <= 7 and pct < 80:
                rag = "RED" if rag == "AMBER" else "AMBER" if rag == "GREEN" else rag
                reasons.append(f"only {pct:g}% complete with {days_to_go} days to go")
            if not reasons:
                reasons.append("on baseline")
        rows.append({"name": name, "state": state, "baseline": base.isoformat(), "forecast": forecast.isoformat(), "actual": actual.isoformat() if actual else None, "slip_working_days": slip, "days_to_go": days_to_go if not actual else None, "percent_complete": pct, "rag": rag, "reason": "; ".join(reasons)})
    order = {"RED": 0, "AMBER": 1, "GREEN": 2}
    open_rows = [r for r in rows if r["state"] != "done"]
    overall = min((r["rag"] for r in (open_rows or rows)), key=lambda x: order[x])
    counts = {k: sum(1 for r in rows if r["rag"] == k) for k in ("GREEN", "AMBER", "RED")}
    next_up = min(open_rows, key=lambda r: r["forecast"]) if open_rows else None
    return {
        "as_of": today.isoformat(),
        "overall": overall,
        "counts": counts,
        "milestones": rows,
        "next_milestone": {"name": next_up["name"], "forecast": next_up["forecast"], "days_to_go": next_up["days_to_go"], "rag": next_up["rag"]} if next_up else None,
        "overdue": [r["name"] for r in rows if r["state"] == "OVERDUE"],
        "markdown_table": md_table(["Milestone", "Baseline", "Forecast", "Slip (wd)", "RAG", "Why"], [[r["name"], r["baseline"], r["actual"] or r["forecast"], r["slip_working_days"], r["rag"], r["reason"]] for r in rows]),
        "verdict": f"Milestones {overall}: {counts['GREEN']} green, {counts['AMBER']} amber, {counts['RED']} red."
        + (f" Overdue: {', '.join(r['name'] for r in rows if r['state'] == 'OVERDUE')}." if any(r["state"] == "OVERDUE" for r in rows) else "")
        + (f" Next: {next_up['name']} in {next_up['days_to_go']} days ({next_up['rag']})." if next_up else ""),
    }


_VAGUE_PHRASES = [
    "making progress", "good progress", "going well", "on track", "on schedule", "as planned", "moving forward", "ramping up",
    "soon", "asap", "shortly", "in the near future", "various", "several", "a lot of", "lots of", "some issues", "a few",
    "working on it", "looking into", "no major", "should be", "hopefully", "basically", "pretty much", "significant",
]
_SECTIONS = {
    "status_line": re.compile(r"\b(green|amber|yellow|red)\b|🟢|🟡|🔴|\bstatus\s*:", re.I),
    "tldr": re.compile(r"\b(tl;?dr|summary|headline|bottom line|in short)\b", re.I),
    "asks": re.compile(r"\b(asks?|decisions? needed|need(s|ed)? from|help needed|requests?|escalat)\w*", re.I),
    "progress": re.compile(r"\b(progress|shipped|completed|done|delivered|highlights?|accomplish)\w*", re.I),
    "risks": re.compile(r"\b(risks?|issues?|blockers?|concerns?)\b", re.I),
    "next": re.compile(r"\b(next (week|steps?|up)|upcoming|plan for)\b", re.I),
}


@AGENT.tool
def lint_report(report: str, audience: str = "exec") -> dict:
    """Lint a status-report draft: length, section coverage, vague phrases, numbers-per-claim, passive voice, long sentences. Score 0-100.

    Args:
        report: The draft status update text (markdown or plain).
        audience: "exec" (150-400 words) or "team" (up to 600 words).
    """
    if not report.strip():
        raise ToolError("Report is empty.")
    if len(report) > 100_000:
        raise ToolError("Report too long to lint (100k chars max).")
    if audience not in ("exec", "team"):
        raise ToolError("audience must be 'exec' or 'team'.")
    lo, hi = (150, 400) if audience == "exec" else (100, 600)
    ws = text.words(report)
    n_words = len(ws)
    sents = text.sentences(report)
    first_lines = "\n".join(report.strip().splitlines()[:2])
    sections = {k: bool(rx.search(report)) for k, rx in _SECTIONS.items()}
    sections["status_line"] = bool(_SECTIONS["status_line"].search(first_lines))
    missing = [k for k, v in sections.items() if not v]
    low = report.lower()
    vague = []
    for ph in _VAGUE_PHRASES:
        for m in re.finditer(r"\b" + re.escape(ph) + r"\b", low):
            window = low[max(0, m.start() - 60): m.end() + 60]
            if not re.search(r"\d", window):  # a number nearby makes the phrase acceptable
                vague.append(ph)
    vague_counts = {p: vague.count(p) for p in dict.fromkeys(vague)}
    prose = "\n".join(ln for ln in report.splitlines() if not ln.lstrip().startswith("|"))  # tables are not sentences
    passive = text.passive_sentences(prose)
    long_sents = [s for s in text.sentences(prose) if len(text.words(s)) > 30]
    numbers = len(re.findall(r"\d+(?:[.,]\d+)?%?", report))
    deltas = len(re.findall(r"\(\s*(vs|from|was|last week)[^)]*\d[^)]*\)|[+-]\d+(?:\.\d+)?%?|↑|↓", report))
    asks_before_progress = True
    if sections["asks"] and sections["progress"]:
        # compare section HEADINGS when the draft has them ("**Asks**", "## Progress", "Asks:"), else first mentions
        heads = [(m.start(), m.group(0)) for m in re.finditer(r"(?m)^[ \t]*(?:#{1,6}[ \t]+|\*\*|__)?[^\n|]{1,50}?(?:\*\*|__)?[ \t]*:?[ \t]*$", report)
                 if len(text.words(m.group(0))) <= 6]
        a_head = next((pos for pos, h in heads if _SECTIONS["asks"].search(h)), None)
        p_head = next((pos for pos, h in heads if _SECTIONS["progress"].search(h)), None)
        a_pos = a_head if a_head is not None else _SECTIONS["asks"].search(report).start()
        p_pos = p_head if p_head is not None else _SECTIONS["progress"].search(report).start()
        asks_before_progress = a_pos < p_pos
    score = 100
    fixes = []
    if n_words < lo:
        score -= 10
        fixes.append(f"{n_words} words — too thin for a {audience} update; add deltas, risks and asks (target {lo}-{hi}).")
    elif n_words > hi:
        score -= min(25, 5 * ((n_words - hi) // 50 + 1))
        fixes.append(f"{n_words} words — over the {hi}-word limit; move detail to a linked doc.")
    for k in missing:
        score -= {"status_line": 15, "asks": 15, "risks": 10, "tldr": 8, "progress": 8, "next": 6}[k]
        fixes.append({"status_line": "No status colour in the first 2 lines — open with '🟢/🟡/🔴 GREEN/AMBER/RED'.", "asks": "No asks/decisions section — if you need nothing, say 'No asks this week'.", "risks": "No risks/issues section.", "tldr": "No TL;DR — three bullets at the top.", "progress": "No progress/shipped section.", "next": "No 'next week' section."}[k])
    if vague_counts:
        score -= min(20, 4 * sum(vague_counts.values()))
        fixes.append("Vague phrases without a number nearby: " + ", ".join(f"'{p}'×{c}" for p, c in vague_counts.items()) + " — replace each with a metric or a date.")
    if passive:
        score -= min(10, 3 * len(passive))
        fixes.append(f"{len(passive)} passive sentence(s) — name who did/decided: e.g. \"{passive[0][:80]}\"")
    if long_sents:
        score -= min(10, 3 * len(long_sents))
        fixes.append(f"{len(long_sents)} sentence(s) over 30 words — split them.")
    if numbers < max(3, n_words // 60):
        score -= 10
        fixes.append(f"Only {numbers} numbers in {n_words} words — status without numbers is opinion.")
    if numbers and deltas == 0:
        score -= 6
        fixes.append("No deltas — every metric needs '(vs X last week)'.")
    if not asks_before_progress:
        score -= 5
        fixes.append("Asks appear after progress — move them above; readers stop early.")
    score = int(max(0, score))
    return {
        "score": score,
        "grade": "send it" if score >= 80 else "fix the flags" if score >= 60 else "rewrite",
        "words": n_words,
        "sentences": len(sents),
        "reading_time_min": text.reading_time_minutes(report),
        "sections_found": sections,
        "missing_sections": missing,
        "vague_phrases": vague_counts,
        "passive_sentences": passive[:10],
        "long_sentences": [s[:120] for s in long_sents[:5]],
        "numbers": numbers,
        "deltas": deltas,
        "asks_before_progress": asks_before_progress,
        "fixes": fixes,
        "verdict": f"Lint {score}/100: {n_words} words, {len(missing)} missing section(s), {sum(vague_counts.values())} vague phrase(s), {len(passive)} passive, {numbers} numbers/{deltas} deltas.",
    }
