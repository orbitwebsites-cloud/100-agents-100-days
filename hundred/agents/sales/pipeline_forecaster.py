"""Pipeline Forecaster — weighted pipeline, stage conversion and velocity, coverage, and a forecast you can defend to the board."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta

from ...core import Agent, ToolError
from ...lib import dates
from . import _common as c

AGENT = Agent(
    slug="pipeline-forecaster",
    name="Pipeline Forecaster",
    category="sales",
    tagline="A forecast you can defend: weighted pipeline by stage and month, conversion and velocity, coverage vs quota, and the gap plan.",
    description=(
        "Turns a CRM export into a board-ready forecast. Computes weighted and category pipeline "
        "(commit / best case / pipeline), flags slipped and stale deals, derives stage-to-stage conversion, "
        "win rate and cycle time from history, checks coverage against quota with the time left in the "
        "period, runs the sales-velocity equation with lever sensitivity, and measures past forecast "
        "accuracy so the number you present is calibrated, not hopeful."
    ),
    triggers=[
        "forecast my pipeline / what will we close this quarter",
        "calculate weighted pipeline",
        "do we have enough pipeline coverage to hit quota",
        "stage conversion rates and sales cycle length",
        "sales velocity analysis",
        "how accurate have our forecasts been",
    ],
    examples=[
        "Here's our open-deal export (name, stage, amount, close date, last activity). Forecast Q4 and flag what's at risk.",
        "Quota is $1.2M, we've closed $400k, 35 business days left, $2.1M open pipeline. Are we covered?",
        "From these 120 closed deals with stage history, what are our conversion rates and average cycle?",
        "Our forecasts vs actuals for the last 6 quarters — how biased are we?",
    ],
    connectors=["Salesforce", "HubSpot", "Pipedrive", "Google Sheets", "Slack"],
    playbook="""
    ## Standard
    You are a VP Sales / RevOps lead presenting to a CFO who remembers last quarter's
    miss. Excellent means every number is computed from the data, every deal in
    "commit" has a next step and a date inside the period, the gap to quota is stated
    with a plan, and the forecast comes with its own error bars. The one metric:
    **forecast accuracy** (within ±10% of actual at the start of the last month of the
    quarter). A confident wrong number is worse than a cautious right one.

    ## Intake
    You need the open deals (name, stage, amount, close date; ideally last activity and
    next step), the stage probabilities (or you use defaults and say so), the quota and
    the period. For conversion/velocity you need closed deals with dates. Ask at most 3
    questions and only if the amount or stage fields are missing; otherwise assume and
    label every assumption.

    ## Procedure
    1. **Weighted pipeline.** Call `pipeline_forecaster__weighted_pipeline` with the open
       deals, the stage → probability map, and the period end date. It returns weighted
       total, totals by stage and by close month, forecast categories (commit = late
       stage with a date inside the period; best case; pipeline), and flags: deals with
       close dates in the past (slipped), deals with no activity for 14+ days (stale),
       deals with amounts ≥ 3× the median (concentration risk).
    2. **Historical rates.** If closed deals are available, call
       `pipeline_forecaster__stage_conversion`. It computes win rate, stage-to-stage
       conversion, average and median cycle length and days per stage, and shows where
       deals die. Replace default stage probabilities with the measured ones and re-run
       step 1 — the biggest forecast errors come from optimistic stage weights.
    3. **Coverage.** Call `pipeline_forecaster__coverage_ratio` with quota, closed-to-date,
       open and weighted pipeline, and the time left. It returns coverage (open ÷ gap),
       the required win rate on remaining pipeline, deals needed at the average size, and
       whether the period is recoverable given cycle length (if median cycle > days left,
       new pipeline can't save this period — say so).
    4. **Velocity.** Call `pipeline_forecaster__sales_velocity` with opportunity count,
       average deal size, win rate and cycle days. It gives revenue per day and the
       sensitivity of each lever (+10%), so the recommendation is "raise win rate 5 pts"
       not "sell more".
    5. **Calibrate.** If past forecasts and actuals exist, call
       `pipeline_forecaster__forecast_accuracy`. It computes MAPE, bias (systematic
       over/under), and a calibration multiplier to apply to this quarter's number.
    6. **Write the forecast** in the output format: the number, the range, what's in
       commit (deal by deal), the risks, and the gap plan with owners.

    ## Frameworks
    - **Stage probability defaults** (replace with measured): qualification 10%,
      discovery 20%, demo/evaluation 35%, proposal 50%, negotiation 70%, verbal/contract
      85%, closed won 100%.
    - **Forecast categories:** Commit = negotiation+ with close date in period and
      activity in the last 14 days; Best case = proposal+ with date in period; Pipeline =
      everything else open. The forecast number = commit + ~50% of best case, checked
      against weighted.
    - **Coverage rule of thumb:** 3× open-pipeline coverage of the remaining gap at the
      start of a quarter; 2× mid-quarter; late in the quarter coverage matters less than
      commit quality because new deals cannot close in time.
    - **Sales velocity** = (opportunities × win rate × avg deal) ÷ cycle days.
    - **Slippage:** any deal whose close date has already passed is pushed to next
      period in the forecast unless it has a signed order form; deals that slipped twice
      get 50% of their stage probability.
    - **Accuracy:** report the forecast as a range (commit … commit + best case), not a
      point; apply the historical calibration multiplier if bias > 10%.

    ## Output format
    ```
    # Forecast — <period> (as of <date>)

    **Forecast:** $<commit + 50% best case>  (range $<commit> – $<commit + best case>) · Weighted: $<x>
    **Quota:** $<q> · Closed: $<c> (<pct>%) · Gap: $<g> · Coverage: <n>× · Days left: <n>

    ## Commit (deal by deal)
    | Deal | Amount | Stage | Close | Next step | Risk |

    ## Best case
    | Deal | Amount | Stage | Close | What has to happen |

    ## Risks
    - Slipped: <n deals, $x> · Stale: <n, $x> · Concentration: <deal = y% of forecast>

    ## Gap plan
    1. <lever, expected $, owner, by date>

    ## Calibration
    Historical bias <+x%> → adjusted forecast $<y>
    ```

    ## Anti-patterns
    - Forecasting the weighted number as the forecast. Weighted is a sanity check, not a commit.
    - Letting reps' stage names carry probabilities they haven't earned.
    - Ignoring close dates in the past — a slipped deal is a signal, not a rounding error.
    - Adding new pipeline to this quarter's forecast when the cycle is longer than the days left.
    - One big deal = the quarter. Call out concentration > 30% every time.
    - A point forecast with no range and no accuracy history.
    """,
)

DEFAULT_PROBS = {
    "qualification": 0.10, "qualified": 0.10, "discovery": 0.20, "demo": 0.35, "evaluation": 0.35,
    "proposal": 0.50, "proposal sent": 0.50, "negotiation": 0.70, "contract": 0.85, "verbal": 0.85,
    "closed won": 1.0, "won": 1.0, "closed lost": 0.0, "lost": 0.0,
}
STAGE_ORDER = ["qualification", "discovery", "demo", "evaluation", "proposal", "negotiation", "contract", "verbal", "closed won"]
LATE_STAGES = {"negotiation", "contract", "verbal"}
MID_STAGES = {"proposal", "proposal sent"}


def _amount(v, i: int) -> float:
    try:
        f = float(str(v).replace(",", "").replace("$", "")) if v not in (None, "") else 0.0
    except ValueError:
        raise ToolError(f"Deal {i}: amount {v!r} is not a number.") from None
    if f < 0:
        raise ToolError(f"Deal {i}: amount cannot be negative.")
    return f


@AGENT.tool
def weighted_pipeline(deals: list[dict], stage_probabilities: dict | None = None, period_end: str = "", today: str = "", stale_days: int = 14) -> dict:
    """Compute weighted pipeline by stage and close month, forecast categories, and flag slipped/stale/concentrated deals.

    Call first with the open-deal export. Deal fields: name, stage, amount, close_date (YYYY-MM-DD),
    last_activity (YYYY-MM-DD, optional), next_step (optional), slips (int, optional).

    Args:
        deals: 1-2000 open deals.
        stage_probabilities: {"stage name": 0-1 or 0-100}; unknown stages fall back to defaults and are reported.
        period_end: Last day of the forecast period, YYYY-MM-DD (default: end of the current quarter).
        today: As-of date YYYY-MM-DD (default: today).
        stale_days: Days without activity after which a deal is stale (default 14).
    """
    if not deals or len(deals) > 2000:
        raise ToolError("Give 1-2000 deals.")
    asof = c.to_date(today)
    if period_end:
        pend = dates.parse_date(period_end)
    else:
        q_end_month = ((asof.month - 1) // 3 + 1) * 3
        first_of_end_month = date(asof.year, q_end_month, 1)
        pend = (first_of_end_month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    probs = dict(DEFAULT_PROBS)
    for k, v in (stage_probabilities or {}).items():
        try:
            p = float(v)
        except (TypeError, ValueError):
            raise ToolError(f"stage probability for {k!r} must be a number.") from None
        if p > 1:
            p /= 100
        if not 0 <= p <= 1:
            raise ToolError(f"stage probability for {k!r} must be 0-1 or 0-100.")
        probs[str(k).strip().lower()] = p
    rows, unknown_stages = [], set()
    by_stage: dict[str, dict] = defaultdict(lambda: {"count": 0, "amount": 0.0, "weighted": 0.0})
    by_month: dict[str, dict] = defaultdict(lambda: {"count": 0, "amount": 0.0, "weighted": 0.0})
    cats = {"commit": [], "best_case": [], "pipeline": [], "slipped": []}
    amounts = []
    for i, d in enumerate(deals, 1):
        if not isinstance(d, dict):
            raise ToolError(f"Deal {i} is not a dict.")
        name = str(d.get("name", f"Deal {i}"))
        stage = str(d.get("stage", "")).strip().lower()
        if not stage:
            raise ToolError(f"Deal {i} ({name}) has no stage.")
        amt = _amount(d.get("amount"), i)
        p = probs.get(stage)
        if p is None:
            unknown_stages.add(stage)
            p = 0.2
        if p >= 1.0 or p <= 0.0:
            continue  # closed deals don't belong in open pipeline
        close = c.to_date(str(d.get("close_date", ""))) if d.get("close_date") else None
        last_act = dates.parse_date(str(d["last_activity"])) if d.get("last_activity") else None
        slips = int(d.get("slips", 0) or 0)
        eff_p = p * (0.5 if slips >= 2 else 1.0)
        flags = []
        if close and close < asof:
            flags.append(f"close date {close.isoformat()} has passed — slipped")
        if last_act and (asof - last_act).days > stale_days:
            flags.append(f"no activity for {(asof - last_act).days} days — stale")
        if not close:
            flags.append("no close date")
        if not str(d.get("next_step", "")).strip():
            flags.append("no next step")
        if slips >= 2:
            flags.append(f"slipped {slips}× — probability halved")
        in_period = bool(close and asof <= close <= pend)
        stale = any("stale" in f for f in flags)
        if close and close < asof:
            cat = "slipped"
        elif stage in LATE_STAGES and in_period and not stale:
            cat = "commit"
        elif (stage in LATE_STAGES or stage in MID_STAGES) and in_period:
            cat = "best_case"
        else:
            cat = "pipeline"
        w = amt * eff_p
        row = {"name": name, "stage": stage, "amount": c.money(amt), "probability": round(eff_p, 2), "weighted": c.money(w), "close_date": close.isoformat() if close else None, "in_period": in_period, "category": cat, "flags": flags}
        rows.append(row)
        amounts.append(amt)
        cats[cat].append(row)
        by_stage[stage]["count"] += 1
        by_stage[stage]["amount"] += amt
        by_stage[stage]["weighted"] += w
        mkey = close.strftime("%Y-%m") if close else "no date"
        by_month[mkey]["count"] += 1
        by_month[mkey]["amount"] += amt
        by_month[mkey]["weighted"] += w
    if not rows:
        raise ToolError("No open deals after excluding closed won/lost.")
    total = sum(r["amount"] for r in rows)
    weighted = sum(r["weighted"] for r in rows)
    commit = sum(r["amount"] for r in cats["commit"])
    best = sum(r["amount"] for r in cats["best_case"])
    forecast = commit + 0.5 * best
    srt = sorted(amounts)
    median = srt[len(srt) // 2] if len(srt) % 2 else (srt[len(srt) // 2 - 1] + srt[len(srt) // 2]) / 2
    biggest = max(rows, key=lambda r: r["amount"])
    conc = c.pct(biggest["amount"], forecast) if forecast else 0.0
    risks = []
    if cats["slipped"]:
        risks.append(f"{len(cats['slipped'])} slipped deal(s) worth ${sum(r['amount'] for r in cats['slipped']):,.0f} — re-date or move out of the forecast")
    stale_rows = [r for r in rows if any("stale" in f for f in r["flags"])]
    if stale_rows:
        risks.append(f"{len(stale_rows)} stale deal(s) worth ${sum(r['amount'] for r in stale_rows):,.0f}")
    if forecast and conc > 30:
        risks.append(f"'{biggest['name']}' is {conc}% of the forecast — concentration risk")
    big = [r["name"] for r in rows if median and r["amount"] >= 3 * median]
    if big:
        risks.append(f"{len(big)} deal(s) ≥ 3× median size: {', '.join(big[:3])}")
    no_step = [r for r in cats["commit"] if "no next step" in r["flags"]]
    if no_step:
        risks.append(f"{len(no_step)} commit deal(s) have no next step — they aren't commit")
    return {
        "as_of": asof.isoformat(),
        "period_end": pend.isoformat(),
        "deals": rows,
        "open_pipeline": c.money(total),
        "weighted_pipeline": c.money(weighted),
        "commit": c.money(commit),
        "best_case": c.money(best),
        "forecast": c.money(forecast),
        "forecast_range": {"low": c.money(commit), "high": c.money(commit + best)},
        "by_stage": {k: {"count": v["count"], "amount": c.money(v["amount"]), "weighted": c.money(v["weighted"])} for k, v in sorted(by_stage.items(), key=lambda kv: STAGE_ORDER.index(kv[0]) if kv[0] in STAGE_ORDER else 99)},
        "by_close_month": {k: {"count": v["count"], "amount": c.money(v["amount"]), "weighted": c.money(v["weighted"])} for k, v in sorted(by_month.items())},
        "category_counts": {k: len(v) for k, v in cats.items()},
        "median_deal": c.money(median),
        "unknown_stages": sorted(unknown_stages),
        "risks": risks,
        "verdict": f"Forecast ${forecast:,.0f} (range ${commit:,.0f}–${commit + best:,.0f}); weighted ${weighted:,.0f} on ${total:,.0f} open." + (" " + risks[0] if risks else ""),
    }


@AGENT.tool
def stage_conversion(closed_deals: list[dict], stages: list[str] | None = None) -> dict:
    """Derive win rate, stage-to-stage conversion, cycle length and days-per-stage from closed deals.

    Call when history exists. Each deal: {"outcome": "won"|"lost", "amount": number, "created": "YYYY-MM-DD",
    "closed": "YYYY-MM-DD", "furthest_stage": str, "days_in_stage": {"stage": days} (optional)}.

    Args:
        closed_deals: 2-5000 closed deals.
        stages: Ordered pipeline stage names (default: qualification, discovery, demo, proposal, negotiation, closed won).
    """
    if not closed_deals or len(closed_deals) < 2 or len(closed_deals) > 5000:
        raise ToolError("Give 2-5000 closed deals.")
    order = [s.strip().lower() for s in (stages or ["qualification", "discovery", "demo", "proposal", "negotiation", "closed won"])]
    if len(order) < 2:
        raise ToolError("Need at least 2 stages.")
    reached = Counter()
    won, lost, won_amt, lost_amt = 0, 0, 0.0, 0.0
    cycles_won, cycles_all = [], []
    stage_days: dict[str, list[float]] = defaultdict(list)
    lost_at = Counter()
    for i, d in enumerate(closed_deals, 1):
        if not isinstance(d, dict):
            raise ToolError(f"Deal {i} is not a dict.")
        outcome = str(d.get("outcome", "")).strip().lower()
        if outcome not in ("won", "lost"):
            raise ToolError(f"Deal {i}: outcome must be won or lost.")
        amt = _amount(d.get("amount"), i)
        fs = str(d.get("furthest_stage", order[-1] if outcome == "won" else "")).strip().lower()
        if outcome == "won":
            fs = order[-1]
        if fs and fs not in order:
            raise ToolError(f"Deal {i}: furthest_stage {fs!r} not in stages {order}.")
        idx = order.index(fs) if fs else 0
        for s in order[: idx + 1]:
            reached[s] += 1
        if outcome == "won":
            won += 1
            won_amt += amt
        else:
            lost += 1
            lost_amt += amt
            lost_at[fs or order[0]] += 1
        if d.get("created") and d.get("closed"):
            days = (dates.parse_date(str(d["closed"])) - dates.parse_date(str(d["created"]))).days
            if days < 0:
                raise ToolError(f"Deal {i}: closed before created.")
            cycles_all.append(days)
            if outcome == "won":
                cycles_won.append(days)
        for s, v in (d.get("days_in_stage") or {}).items():
            try:
                stage_days[str(s).strip().lower()].append(float(v))
            except (TypeError, ValueError):
                raise ToolError(f"Deal {i}: days_in_stage values must be numbers.") from None
    n = won + lost
    conv = []
    for a, b in zip(order, order[1:]):
        ra, rb = reached[a], reached[b]
        conv.append({"from": a, "to": b, "entered": ra, "advanced": rb, "conversion_pct": c.pct(rb, ra) if ra else None})
    cum = []
    for s in order:
        cum.append({"stage": s, "reached": reached[s], "win_rate_from_here_pct": c.pct(won, reached[s]) if reached[s] else None})

    def _med(xs):
        if not xs:
            return None
        xs = sorted(xs)
        m = len(xs) // 2
        return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2

    worst = min((x for x in conv if x["conversion_pct"] is not None), key=lambda x: x["conversion_pct"], default=None)
    return {
        "deals": n,
        "won": won,
        "lost": lost,
        "win_rate_pct": c.pct(won, n),
        "win_rate_by_amount_pct": c.pct(won_amt, won_amt + lost_amt) if (won_amt + lost_amt) else None,
        "avg_won_deal": c.money(won_amt / won) if won else None,
        "stage_conversion": conv,
        "win_rate_from_stage": cum,
        "measured_probabilities": {s["stage"]: round((s["win_rate_from_here_pct"] or 0) / 100, 2) for s in cum},
        "lost_at_stage": dict(lost_at.most_common()),
        "cycle_days": {"won_avg": round(sum(cycles_won) / len(cycles_won), 1) if cycles_won else None, "won_median": _med(cycles_won), "all_avg": round(sum(cycles_all) / len(cycles_all), 1) if cycles_all else None, "all_median": _med(cycles_all)},
        "avg_days_in_stage": {s: round(sum(v) / len(v), 1) for s, v in stage_days.items()},
        "biggest_leak": worst,
        "verdict": f"Win rate {c.pct(won, n)}% on {n} deals" + (f"; median won cycle {_med(cycles_won)} days" if cycles_won else "") + (f". Biggest leak: {worst['from']} → {worst['to']} at {worst['conversion_pct']}%." if worst else "."),
    }


@AGENT.tool
def coverage_ratio(quota: float, closed_to_date: float, open_pipeline: float, weighted_pipeline: float = 0.0, days_left: int = 0, days_in_period: int = 0, avg_deal_size: float = 0.0, win_rate_pct: float = 0.0, median_cycle_days: int = 0) -> dict:
    """Coverage of the remaining gap, required win rate, deals needed, and whether the period is still recoverable.

    Call after weighted_pipeline. Coverage = open pipeline ÷ gap; rule of thumb 3× early, 2× mid-period.

    Args:
        quota: Period quota/target.
        closed_to_date: Closed-won so far this period.
        open_pipeline: Total open pipeline that can close in the period.
        weighted_pipeline: Weighted pipeline for the period (optional).
        days_left: Business days left in the period.
        days_in_period: Business days in the whole period (for the mid/late rule).
        avg_deal_size: Average won deal size (for deals-needed maths).
        win_rate_pct: Historical win rate (for pipeline-needed maths).
        median_cycle_days: Median sales cycle in calendar days (to judge if new pipeline can still land).
    """
    if quota <= 0:
        raise ToolError("quota must be > 0.")
    for name, v in (("closed_to_date", closed_to_date), ("open_pipeline", open_pipeline), ("weighted_pipeline", weighted_pipeline), ("avg_deal_size", avg_deal_size)):
        if v < 0:
            raise ToolError(f"{name} cannot be negative.")
    if not 0 <= win_rate_pct <= 100 or days_left < 0 or days_in_period < 0 or median_cycle_days < 0:
        raise ToolError("win_rate_pct 0-100; day counts ≥ 0.")
    gap = max(0.0, quota - closed_to_date)
    attainment = c.pct(closed_to_date, quota)
    coverage = round(open_pipeline / gap, 2) if gap else None
    weighted_cov = round(weighted_pipeline / gap, 2) if gap and weighted_pipeline else None
    required_win = c.pct(gap, open_pipeline) if open_pipeline else None
    progress = c.pct(days_in_period - days_left, days_in_period) if days_in_period else None
    target_cov = 3.0 if progress is None or progress < 33 else 2.0 if progress < 66 else 1.5
    deals_needed = None
    pipeline_needed = None
    if avg_deal_size:
        deals_needed = int(-(-gap // avg_deal_size)) if gap else 0
    if win_rate_pct:
        pipeline_needed = c.money(gap / (win_rate_pct / 100))
    verdicts, status = [], "on track"
    if gap == 0:
        status = "quota met"
        verdicts.append("Quota already met.")
    else:
        if coverage is not None and coverage < target_cov:
            status = "under-covered"
            verdicts.append(f"Coverage {coverage}× vs {target_cov}× needed at this point — short by ${max(0, target_cov * gap - open_pipeline):,.0f} of pipeline.")
        elif coverage is not None:
            verdicts.append(f"Coverage {coverage}× meets the {target_cov}× bar.")
        if required_win is not None and win_rate_pct and required_win > win_rate_pct * 1.25:
            status = "at risk"
            verdicts.append(f"Needs a {required_win}% win rate on open pipeline vs historical {win_rate_pct}%.")
        if weighted_cov is not None and weighted_cov < 1:
            status = "at risk" if status == "on track" else status
            verdicts.append(f"Weighted pipeline covers only {round(100 * weighted_cov)}% of the gap.")
        if median_cycle_days and days_left and median_cycle_days > days_left * 7 / 5:
            verdicts.append(f"Median cycle ({median_cycle_days} days) exceeds the time left — new pipeline can't close this period; focus on existing late-stage deals.")
    return {
        "quota": c.money(quota),
        "closed_to_date": c.money(closed_to_date),
        "attainment_pct": attainment,
        "gap": c.money(gap),
        "open_pipeline": c.money(open_pipeline),
        "coverage_x": coverage,
        "weighted_coverage_x": weighted_cov,
        "target_coverage_x": target_cov,
        "period_progress_pct": progress,
        "required_win_rate_pct": required_win,
        "deals_needed_at_avg_size": deals_needed,
        "pipeline_needed_at_win_rate": pipeline_needed,
        "new_pipeline_can_land": (median_cycle_days <= days_left * 7 / 5) if (median_cycle_days and days_left) else None,
        "status": status,
        "verdict": f"{attainment}% attained, gap ${gap:,.0f}. " + " ".join(verdicts),
    }


@AGENT.tool
def sales_velocity(opportunities: int, avg_deal_size: float, win_rate_pct: float, cycle_days: float, period_days: int = 90) -> dict:
    """Sales velocity (revenue per day) with +10% lever sensitivity and the revenue it implies for the period.

    Call to turn a diagnosis into a lever. Velocity = opportunities × win rate × avg deal ÷ cycle days.

    Args:
        opportunities: Number of open qualified opportunities.
        avg_deal_size: Average won deal size.
        win_rate_pct: Win rate, percent.
        cycle_days: Average sales cycle in days.
        period_days: Days in the period to project (default 90).
    """
    if opportunities < 0 or avg_deal_size < 0 or not 0 <= win_rate_pct <= 100 or cycle_days <= 0 or period_days <= 0:
        raise ToolError("opportunities/avg_deal_size ≥ 0, win_rate_pct 0-100, cycle_days > 0, period_days > 0.")
    wr = win_rate_pct / 100
    v = opportunities * wr * avg_deal_size / cycle_days
    levers = {
        "opportunities +10%": (opportunities * 1.1) * wr * avg_deal_size / cycle_days,
        "win rate +10% (relative)": opportunities * (wr * 1.1) * avg_deal_size / cycle_days,
        "avg deal +10%": opportunities * wr * (avg_deal_size * 1.1) / cycle_days,
        "cycle -10%": opportunities * wr * avg_deal_size / (cycle_days * 0.9),
    }
    sens = {k: {"velocity_per_day": c.money(x), "delta_per_day": c.money(x - v), "delta_pct": round(100 * (x - v) / v, 1) if v else None} for k, x in levers.items()}
    best = max(sens.items(), key=lambda kv: kv[1]["delta_per_day"])[0] if v else None
    return {
        "velocity_per_day": c.money(v),
        "projected_revenue_for_period": c.money(v * period_days),
        "expected_wins_in_period": round(opportunities * wr * period_days / cycle_days, 1),
        "sensitivity": sens,
        "highest_leverage": best,
        "note": "Cycle time is the only lever with a compounding effect: -10% cycle = +11.1% velocity.",
        "verdict": f"${v:,.0f}/day → ${v * period_days:,.0f} over {period_days} days." + (f" Best lever: {best}." if best else ""),
    }


@AGENT.tool
def forecast_accuracy(forecasts: list[dict]) -> dict:
    """Score past forecasts vs actuals: MAPE, bias direction, hit rate within ±10%, and a calibration multiplier.

    Call when the user has forecast history. Each row: {"period": str, "forecast": number, "actual": number}.

    Args:
        forecasts: 2-60 periods of forecast vs actual.
    """
    if not forecasts or len(forecasts) < 2 or len(forecasts) > 60:
        raise ToolError("Give 2-60 periods.")
    rows, apes, errs, hits = [], [], [], 0
    for i, r in enumerate(forecasts, 1):
        if not isinstance(r, dict):
            raise ToolError(f"Row {i} is not a dict.")
        f, a = _amount(r.get("forecast"), i), _amount(r.get("actual"), i)
        if a == 0:
            raise ToolError(f"Row {i}: actual is 0 — cannot compute percentage error.")
        err = (f - a) / a
        errs.append(err)
        apes.append(abs(err))
        hit = abs(err) <= 0.10
        hits += hit
        rows.append({"period": str(r.get("period", i)), "forecast": c.money(f), "actual": c.money(a), "error_pct": round(100 * err, 1), "within_10pct": hit})
    n = len(rows)
    mape = round(100 * sum(apes) / n, 1)
    bias = round(100 * sum(errs) / n, 1)
    over = sum(1 for e in errs if e > 0)
    ratio = sum(r["actual"] for r in rows) / sum(r["forecast"] for r in rows)
    direction = "over-forecasting" if bias > 5 else "under-forecasting (sandbagging)" if bias < -5 else "unbiased"
    grade = "excellent" if mape <= 5 else "good" if mape <= 10 else "fair" if mape <= 20 else "poor"
    return {
        "periods": rows,
        "mape_pct": mape,
        "bias_pct": bias,
        "direction": direction,
        "over_forecast_periods": over,
        "under_forecast_periods": n - over,
        "hit_rate_within_10pct": c.pct(hits, n),
        "calibration_multiplier": round(ratio, 3),
        "grade": grade,
        "verdict": f"MAPE {mape}% ({grade}), bias {bias:+}% — {direction}. Multiply this period's forecast by {round(ratio, 3)} to calibrate.",
    }
