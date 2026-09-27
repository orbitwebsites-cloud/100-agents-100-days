"""Investor Update Writer — the monthly update investors actually read: deltas computed, KPI table formatted, asks explicit."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from ...core import Agent, ToolError
from ...lib import text
from ._common import D, ZERO, add_months, bound_rows, cagr, money, month_label, parse_iso, pct, ratio_to_pct, require_nonneg, require_positive

AGENT = Agent(
    slug="investor-update",
    name="Investor Update Writer",
    category="finance",
    tagline="Write the monthly investor update that gets replies: exact MoM/YoY deltas, a clean KPI table, honest lowlights and specific asks.",
    description=(
        "Turns raw numbers into the investor update format top founders use: computes every "
        "month-over-month and year-over-year delta exactly (with direction and 'needs explanation' "
        "flags), derives CMGR and trend from the metric history, states runway from cash and burn, "
        "builds the KPI table as ready-to-paste markdown, and lints the draft for the sections investors "
        "expect (TL;DR, metrics, highlights, lowlights, asks, runway) and the vague words that make "
        "updates unreadable. Sends as a Gmail draft or Notion page when connected."
    ),
    triggers=[
        "write our monthly / quarterly investor update",
        "calculate month over month and year over year changes for our metrics",
        "format a KPI table for investors",
        "how much runway do we have to report",
        "review / improve my investor update draft",
        "what growth rate should I report",
    ],
    examples=[
        "MRR $84k (was $78k last month, $41k a year ago), 312 customers (298 / 160), churn 2.4% (2.1%), cash $1.9M, burn $110k. Write the September update.",
        "Here's our MRR by month for the last 12 months — what CMGR and trend should I report?",
        "Here's my draft update — tell me what's missing before I send it.",
    ],
    connectors=["Gmail", "Notion", "Google Docs", "Stripe", "QuickBooks", "Slack"],
    playbook="""
    ## Standard
    You are the chief of staff to a founder who sends the update investors forward to their partners.
    Excellent means: readable in 3 minutes, every number has a delta and a cause, lowlights are as
    specific as highlights, and each ask names a person or a type of intro. The one metric is
    **replies with help**: an update that generates intros, hires and advice did its job. Never
    invent, round up, or hide a bad number; investors remember the ones that surprised them later.

    ## Intake
    Needed: this month's core metrics with last month's and (ideally) last year's values; cash and
    net burn for the last 1-3 months; 2-4 highlights, 2-3 lowlights, and asks. Ask at most 3
    questions only if there are no metrics or no cash figure. If prior-year values are missing,
    report MoM only and say YoY is unavailable.

    ## Procedure
    1. **Compute every delta.** Call `investor_update__metric_deltas` with the metrics list (name,
       current, prior month, prior year, unit, whether higher is better). It returns MoM and YoY in
       absolute and percent, direction, the formatted strings, and flags any move over 10% as "needs
       one line of explanation". Never compute a percentage yourself.
    2. **Derive the growth story.** With a metric history (6-24 months), call
       `investor_update__growth_series`. It returns CMGR, the last-3-month average growth, whether
       growth is accelerating or decelerating, annualised run-rate and months to double. Report CMGR,
       not the best single month.
    3. **State runway.** Call `investor_update__runway_line` with cash and the last 1-3 months of net
       burn (and revenue if it is growing). It returns average burn, months of runway, the cash-out
       month, and the standard sentence. Under 9 months of runway: the ask section must include
       fundraising and the update must say so plainly.
    4. **Draft in the format below.** TL;DR is 3 lines max: the one number, the one win, the one
       problem. Highlights and lowlights are each 2-4 bullets with a number in every bullet. Asks are
       specific: "intro to a Head of Sales at a Series B SaaS company" beats "hiring help".
    5. **Lint before sending.** Call `investor_update__update_lint` on the draft. Fix every missing
       section, every vague phrase it lists, and get length into the 350-700 word band. Numbers per
       100 words should be at least 3; it is a metrics document.
    6. **Send.** With Gmail: create a draft to the investor list, subject "<Company> — <Month YYYY>
       update". With Notion/Docs: file it under Investor Updates with the KPI table. Otherwise output
       ready to paste.

    ## Frameworks
    - **Structure (Y Combinator / Sequoia style)**: TL;DR → KPIs → Highlights → Lowlights → Asks →
      Runway/Team → Thanks (name the investors who helped last month).
    - **Delta rules**: MoM for operating metrics, YoY for seasonal ones, both when available.
      Every change > 10% gets one line of cause.
    - **CMGR** = (last ÷ first)^(1/months) − 1; compare to stage benchmarks (seed 10-15% MoM strong,
      Series A 5-8% strong; widely cited).
    - **Runway** = cash ÷ average net burn of the last 3 months; report the cash-out month.
    - **Cadence**: monthly for seed/A, quarterly later; the same day each month, no skipping bad months.

    ## Output format
    ```
    Subject: <Company> — <Month YYYY> update

    **TL;DR:** <one number> · <one win> · <one problem>

    ## KPIs
    | Metric | <Month> | MoM | YoY | Note |
    |---|---|---|---|---|

    ## Highlights
    - <win with number>

    ## Lowlights
    - <miss with number and what we are doing>

    ## Asks
    - <specific intro/hire/advice — who can help>

    ## Runway & team
    Cash $X, net burn $Y/mo → N months (cash-out <Month YYYY>). Team: N (+hires). <fundraising plan if < 12 months>

    Thanks to <names> for <specific help>.
    ```

    ## Anti-patterns
    - "Great month!" with no number in the first line.
    - Percent changes computed in prose (they are wrong more often than you think).
    - Lowlights section that says "nothing major" — investors read that as hiding.
    - Asks like "any help appreciated". Name the role, the company type, the intro.
    - 1,500-word updates. Nobody forwards those.
    - Skipping the month the numbers were bad.
    """,
)


def _fmt(v: Decimal, unit: str) -> str:
    if unit in ("$", "usd", "dollars"):
        return f"${money(v):,.0f}" if abs(v) >= 1000 else f"${money(v):,.2f}"
    if unit in ("%", "pct", "percent"):
        return f"{pct(v, 1)}%"
    if unit in ("x", "ratio"):
        return f"{pct(v, 2)}x"
    return f"{float(v):,.0f}" if v == v.to_integral_value() else f"{float(v):,.2f}"


def _delta(cur: Decimal, prior: Decimal | None, unit: str, higher_is_better: bool) -> dict | None:
    if prior is None:
        return None
    absolute = cur - prior
    is_pct_unit = unit in ("%", "pct", "percent")
    rel = (absolute / abs(prior)) if prior != 0 else None
    good = absolute > 0 if higher_is_better else absolute < 0
    direction = "flat" if absolute == 0 else ("up" if absolute > 0 else "down")
    if is_pct_unit:
        s = f"{'+' if absolute > 0 else ''}{pct(absolute, 1)} pts"
    else:
        s = (f"{'+' if absolute > 0 else ''}{ratio_to_pct(rel)}%" if rel is not None else "n/a") + f" ({'+' if absolute > 0 else ''}{_fmt(absolute, unit)})"
    return {"absolute": float(pct(absolute, 2)), "pct": ratio_to_pct(rel) if rel is not None else None, "direction": direction, "favourable": good if absolute != 0 else None, "display": s}


@AGENT.tool
def metric_deltas(metrics: list[dict], period_label: str = "", flag_threshold_pct: float = 10) -> dict:
    """Compute exact MoM and YoY deltas for every metric, flag big moves, and return a ready-to-paste markdown KPI table.

    Args:
        metrics: List of {"name": str, "current": n, "prior_month": n (optional), "prior_year": n (optional), "unit": "$"|"%"|"x"|"count", "higher_is_better": bool (default true)}.
        period_label: Column header for the current period, e.g. "Sep 2026".
        flag_threshold_pct: Percent move (or points for % metrics) above which a metric needs an explanation line.
    """
    rows = bound_rows(metrics, "metrics", limit=60)
    thr = D(flag_threshold_pct, "flag_threshold_pct")
    out, flags = [], []
    for i, m in enumerate(rows, 1):
        if not isinstance(m, dict) or "name" not in m or "current" not in m:
            raise ToolError(f"metrics[{i}] needs 'name' and 'current'")
        unit = str(m.get("unit", "count")).lower()
        hib = bool(m.get("higher_is_better", True))
        cur = D(m["current"], f"metrics[{i}].current")
        pm = D(m["prior_month"], f"metrics[{i}].prior_month") if m.get("prior_month") not in (None, "") else None
        py = D(m["prior_year"], f"metrics[{i}].prior_year") if m.get("prior_year") not in (None, "") else None
        mom, yoy = _delta(cur, pm, unit, hib), _delta(cur, py, unit, hib)
        needs = []
        if mom:
            mag = abs(Decimal(str(mom["pct"]))) if mom["pct"] is not None else abs(Decimal(str(mom["absolute"])))
            if mag >= thr:
                needs.append("MoM")
        row = {"name": str(m["name"]), "unit": unit, "current": float(cur), "current_display": _fmt(cur, unit), "mom": mom, "yoy": yoy, "needs_explanation": needs}
        out.append(row)
        if needs:
            flags.append({"name": row["name"], "move": mom["display"], "favourable": mom["favourable"]})
    hdr = period_label or "Current"
    lines = [f"| Metric | {hdr} | MoM | YoY | Note |", "|---|---|---|---|---|"]
    for r in out:
        arrow = lambda d: ("" if not d or d["favourable"] is None else ("▲ " if d["favourable"] else "▼ "))  # noqa: E731
        lines.append(f"| {r['name']} | {r['current_display']} | {arrow(r['mom']) + r['mom']['display'] if r['mom'] else '—'} | {arrow(r['yoy']) + r['yoy']['display'] if r['yoy'] else '—'} | {'explain' if r['needs_explanation'] else ''} |")
    good = sum(1 for r in out if r["mom"] and r["mom"]["favourable"])
    bad = sum(1 for r in out if r["mom"] and r["mom"]["favourable"] is False)
    return {
        "metrics": out,
        "flags": flags,
        "markdown_table": "\n".join(lines),
        "summary": {"favourable_mom": good, "unfavourable_mom": bad, "no_prior": sum(1 for r in out if not r["mom"])},
        "verdict": f"{good} metric(s) moved favourably MoM, {bad} unfavourably; {len(flags)} need a one-line explanation: {', '.join(f['name'] for f in flags) or 'none'}.",
    }


@AGENT.tool
def growth_series(values: list[float], labels: list[str] | None = None, name: str = "MRR") -> dict:
    """CMGR, last-3-month average growth, acceleration/deceleration, run-rate and months-to-double from a metric history.

    Args:
        values: Metric values oldest first, at least 3 months (e.g. MRR by month).
        labels: Optional month labels matching values, e.g. ["2026-01", ...].
        name: Metric name for the verdict.
    """
    if not isinstance(values, list) or len(values) < 3:
        raise ToolError("values needs at least 3 monthly data points, oldest first")
    if len(values) > 120:
        raise ToolError("values: at most 120 points")
    vals = [D(v, f"values[{i}]") for i, v in enumerate(values)]
    if any(v < 0 for v in vals):
        raise ToolError("values cannot be negative")
    if labels and len(labels) != len(vals):
        raise ToolError("labels must match values in length")
    n = len(vals)
    mom = []
    for i in range(1, n):
        prev, cur = vals[i - 1], vals[i]
        g = ((cur - prev) / prev) if prev > 0 else None
        mom.append({"period": labels[i] if labels else i, "value": money(cur), "mom_pct": ratio_to_pct(g) if g is not None else None})
    growth_pcts = [Decimal(str(m["mom_pct"])) for m in mom if m["mom_pct"] is not None]
    cm = cagr(vals[0], vals[-1], Decimal(n - 1))
    last3 = growth_pcts[-3:]
    prev3 = growth_pcts[-6:-3]
    avg3 = sum(last3) / len(last3) if last3 else None
    avg_prev3 = sum(prev3) / len(prev3) if prev3 else None
    if avg3 is not None and avg_prev3 is not None:
        trend = "accelerating" if avg3 > avg_prev3 + Decimal("0.5") else "decelerating" if avg3 < avg_prev3 - Decimal("0.5") else "steady"
    else:
        trend = "too short to judge trend (need 6+ months)"
    best = max(growth_pcts) if growth_pcts else None
    worst = min(growth_pcts) if growth_pcts else None
    months_to_double = None
    if cm is not None and cm > 0:
        import math

        months_to_double = round(math.log(2) / math.log(1 + float(cm)), 1)
    total_growth = ((vals[-1] - vals[0]) / vals[0]) if vals[0] > 0 else None
    return {
        "name": name,
        "points": n,
        "start": money(vals[0]),
        "end": money(vals[-1]),
        "total_growth_pct": ratio_to_pct(total_growth) if total_growth is not None else None,
        "cmgr_pct": ratio_to_pct(cm) if cm is not None else None,
        "annualised_growth_pct": ratio_to_pct((1 + cm) ** 12 - 1) if cm is not None else None,
        "last_3_avg_mom_pct": pct(avg3, 1) if avg3 is not None else None,
        "prior_3_avg_mom_pct": pct(avg_prev3, 1) if avg_prev3 is not None else None,
        "trend": trend,
        "best_month_pct": pct(best, 1) if best is not None else None,
        "worst_month_pct": pct(worst, 1) if worst is not None else None,
        "months_to_double_at_cmgr": months_to_double,
        "run_rate_annual": money(vals[-1] * 12),
        "monthly": mom,
        "verdict": (
            f"{name} grew {ratio_to_pct(total_growth) if total_growth is not None else 'n/a'}% over {n - 1} months (CMGR {ratio_to_pct(cm) if cm is not None else 'n/a'}%, last 3 months avg {pct(avg3, 1) if avg3 is not None else 'n/a'}%, {trend})."
            + (f" Doubles every {months_to_double} months at this rate." if months_to_double else "")
            + " Report the CMGR, not the best month."
        ),
    }


@AGENT.tool
def runway_line(cash: float, net_burn_months: list[float], as_of: str = "", hires_planned_monthly_cost: float = 0) -> dict:
    """Runway from cash and the last 1-3 months of net burn, with the cash-out month and the standard sentence.

    Args:
        cash: Cash and equivalents at month end.
        net_burn_months: Net burn for the last 1-3 months, most recent last (positive = burning; negative = cash-flow positive).
        as_of: Month-end date YYYY-MM-DD; defaults to today.
        hires_planned_monthly_cost: Extra monthly burn from planned hires, to show runway after hiring.
    """
    c = require_nonneg(D(cash, "cash"), "cash")
    if not net_burn_months or len(net_burn_months) > 3:
        raise ToolError("net_burn_months needs 1-3 values")
    burns = [D(b, "net_burn_months") for b in net_burn_months]
    avg = sum(burns) / len(burns)
    today = parse_iso(as_of, "as_of") if as_of else date.today()
    extra = require_nonneg(D(hires_planned_monthly_cost, "hires_planned_monthly_cost"), "hires_planned_monthly_cost")
    if avg <= 0:
        return {"cash": money(c), "avg_net_burn": money(avg), "runway_months": None, "cash_out_month": None, "cash_flow_positive": True, "sentence": f"Cash ${money(c):,.0f}; cash-flow positive (avg ${money(-avg):,.0f}/mo generated) — runway not applicable.", "verdict": "Cash-flow positive."}
    months = c / avg
    out_month = month_label(add_months(today, int(months)))
    sentence = f"Cash ${money(c):,.0f}, net burn ${money(avg):,.0f}/mo (avg of last {len(burns)}) → {pct(months, 1)} months of runway (cash-out ~{out_month})."
    res = {"cash": money(c), "avg_net_burn": money(avg), "burn_trend": ("rising" if len(burns) > 1 and burns[-1] > burns[0] else "falling" if len(burns) > 1 and burns[-1] < burns[0] else "flat"), "runway_months": pct(months, 1), "cash_out_month": out_month, "cash_flow_positive": False, "sentence": sentence}
    if extra > 0:
        m2 = c / (avg + extra)
        res["with_planned_hires"] = {"net_burn": money(avg + extra), "runway_months": pct(m2, 1), "cash_out_month": month_label(add_months(today, int(m2)))}
        sentence += f" After planned hires: {pct(m2, 1)} months."
        res["sentence"] = sentence
    res["fundraise_flag"] = months < 12
    res["verdict"] = sentence + (" Under 12 months — the update must state the fundraising plan." if months < 12 else "")
    return res


SECTIONS = {
    "tl;dr": r"\b(tl;?dr|summary|in short|headline)\b",
    "kpis": r"\b(kpis?|metrics|numbers|mrr|arr|revenue)\b",
    "highlights": r"\b(highlights?|wins?|what went well|good)\b",
    "lowlights": r"\b(lowlights?|misses|challenges|what didn'?t|problems|bad|concerns)\b",
    "asks": r"\b(asks?|how you can help|help (?:needed|wanted)|intros?)\b",
    "runway": r"\b(runway|cash|burn|months? (?:of|left))\b",
}
VAGUE = re.compile(r"\b(great month|exciting|significant(?:ly)?|a lot of|lots of|some|several|many|huge|massive|tons?|good progress|going well|working hard|on track|any help|nothing major|solid|strong momentum)\b", re.I)
NUMBER = re.compile(r"(\$\s?\d[\d,.]*[kKmM]?|\d[\d,.]*\s?%|\b\d[\d,.]*[kKmM]?\b)")
ASK_SPECIFIC = re.compile(r"\b(intro(?:duction)?s? to|looking for a|hiring an?|recommend(?:ation)?s? for|who knows|anyone who|connect (?:me|us) with)\b", re.I)


@AGENT.tool
def update_lint(draft: str) -> dict:
    """Score an investor-update draft 0-100: required sections, length band, number density, vague phrases and ask specificity.

    Args:
        draft: The full update text (markdown or plain).
    """
    if not draft or not draft.strip():
        raise ToolError("draft is empty")
    if len(draft) > 60_000:
        raise ToolError("draft too long (60k chars max)")
    words = len(text.words(draft))
    issues, score = [], 100
    missing = [name for name, pat in SECTIONS.items() if not re.search(pat, draft, re.I)]
    for m in missing:
        issues.append(f"missing section: {m}")
        score -= 12
    if words < 350:
        issues.append(f"{words} words — too thin; target 350-700")
        score -= 10
    elif words > 700:
        issues.append(f"{words} words — too long; target 350-700 (investors forward short updates)")
        score -= 10 if words <= 1000 else 20
    numbers = len(NUMBER.findall(draft))
    density = round(numbers / max(words, 1) * 100, 1)
    if density < 3:
        issues.append(f"only {numbers} numbers in {words} words ({density}/100); a metrics doc needs ≥3 per 100 words")
        score -= 10
    vague = sorted({m.group(0).lower() for m in VAGUE.finditer(draft)})
    if vague:
        issues.append("vague phrases to replace with numbers: " + ", ".join(vague[:8]))
        score -= min(15, 3 * len(vague))
    asks_section = re.search(r"(?is)(?:#+\s*)?(asks?|how you can help)\b.*?(?=\n#|\Z)", draft)
    if asks_section and not ASK_SPECIFIC.search(asks_section.group(0)):
        issues.append("asks are not specific — name the role, company type or intro")
        score -= 10
    first_line = next((ln for ln in draft.splitlines() if ln.strip() and not ln.strip().lower().startswith("subject")), "")
    if first_line and not NUMBER.search(first_line) and not re.search(r"tl;?dr", first_line, re.I):
        issues.append("first line has no number — lead with the headline metric")
        score -= 5
    if re.search(r"\b(thanks? to|thank you to)\b", draft, re.I) is None:
        issues.append("no thanks line — name the investors who helped last month")
        score -= 3
    score = max(score, 0)
    return {
        "score": score,
        "words": words,
        "numbers": numbers,
        "numbers_per_100_words": density,
        "missing_sections": missing,
        "vague_phrases": vague,
        "issues": issues,
        "ready_to_send": score >= 85 and not missing and words >= 250,
        "verdict": "Ready to send." if score >= 85 and not missing and words >= 250 else f"Fix {len(issues)} issue(s); start with: {issues[0]}." if issues else "Ready to send.",
    }
