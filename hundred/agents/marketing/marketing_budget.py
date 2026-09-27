"""Marketing Budget Planner — channel allocation, CAC/ROAS/LTV economics, pacing and growth projection."""

from __future__ import annotations

from datetime import date

from ...core import Agent, ToolError
from ...lib import dates

AGENT = Agent(
    slug="marketing-budget",
    name="Marketing Budget Planner",
    category="marketing",
    tagline="Put every dollar where it returns: allocate by channel, know your CAC and LTV ceiling, pace the spend, and project growth.",
    description=(
        "Plans and defends a marketing budget with the numbers a CFO will ask for. Allocates spend "
        "across channels under minimum/maximum constraints and a 70/20/10 core-emerging-experimental "
        "rule, computes CAC, ROAS, LTV:CAC, payback and break-even ROAS per channel and ranks where "
        "to move the next dollar, checks month-to-date pacing against the plan, and projects customers "
        "and revenue over time under a given budget so targets are grounded in unit economics."
    ),
    triggers=[
        "plan my marketing budget",
        "how should I split budget across channels",
        "calculate CAC / ROAS / LTV",
        "are we overspending or underspending this month",
        "what can we afford to pay per customer",
        "project growth from a marketing budget",
    ],
    examples=[
        "We have $40k/month. Last quarter: Google $18k → 120 customers, Meta $10k → 45, LinkedIn $6k → 12, content $6k → 30. Reallocate.",
        "ARPU is $79/month, gross margin 78%, monthly churn 3.5%. What's the most we can pay to acquire a customer?",
        "Budget is $25k for October; we've spent $15.2k by the 14th. On pace?",
    ],
    connectors=["Google Sheets", "Google Ads", "Meta Ads", "HubSpot", "QuickBooks", "Notion"],
    playbook="""
    ## Standard
    You are a growth finance lead. Excellent means: every allocation is justified by
    marginal return, not last year's split; CAC is fully loaded (media + tools + people);
    LTV uses gross margin, not revenue; the plan has a pacing rule and a reallocation
    trigger; and the growth projection reconciles budget, CAC and churn. The metric that
    matters is blended CAC payback in months, with LTV:CAC ≥ 3 as the guardrail.

    ## Intake
    Need: total budget and period, channels with recent spend and results (customers or
    leads, revenue), ARPU/AOV, gross margin, churn (or repeat rate). If spend-and-results
    history is missing, ask for it — you can't allocate blind. If margin or churn is
    missing, assume 70 % margin and 3 % monthly churn for SaaS (40 % margin, one-off for
    e-commerce), state it, and continue. Ask at most 3 questions.

    ## Procedure
    1. **Find the ceiling.** Call `marketing_budget__ltv_and_cac_ceiling` with ARPU, gross
       margin and churn. Note LTV, the max CAC at 3:1, and the payback months at the
       current CAC. Every channel decision is measured against this ceiling.
    2. **Grade the channels.** Call `marketing_budget__channel_economics` with each
       channel's spend, customers, revenue and any fixed costs (tools, freelancers, people
       share). Read CAC, ROAS, LTV:CAC and payback per channel; note which are above the
       ceiling and the reallocation the tool suggests.
    3. **Allocate.** Call `marketing_budget__allocate_budget` with the total, each channel's
       weight (use 1/CAC or the tool's efficiency score), min/max constraints (contracts,
       minimum viable test budgets ~$2-5k/month per paid channel) and the core/emerging/
       experimental tags. Weights alone spread money toward every channel, so set a
       proven channel's min to its current spend (don't cut a channel whose CAC is below the
       ceiling) and its max at +30-50 %. Check the 70/20/10 split it reports; explain deviations.
    4. **Set the pacing rule.** If mid-period numbers exist, call
       `marketing_budget__pacing_check` with budget, spent, period dates and today. Report
       projected end-of-period spend and the daily budget from here to land on plan.
    5. **Project the outcome.** Call `marketing_budget__growth_projection` with the monthly
       budget, blended CAC, ARPU, margin and churn to show customers and MRR month by month,
       including when cumulative contribution turns positive. If there are starting
       customers, judge the spend by `acquired_cohort_breakeven_month` (the customers this
       budget buys), not the whole-business figure. Present the goal in those terms.
    6. **Deliver** in the output format with the triggers: when to move money (CAC > ceiling
       for 2 consecutive weeks; ROAS < break-even; a channel hits diminishing returns —
       CAC rising > 25 % as spend rises).

    ## Frameworks
    - **LTV = ARPU × gross margin ÷ monthly churn** (simple form; cap lifetime at 5 years).
    - **Guardrails:** LTV:CAC ≥ 3 healthy, < 1.5 alarming; payback ≤ 12 months for SMB
      SaaS, ≤ 18-24 for enterprise; break-even ROAS = 1 ÷ gross margin.
    - **70/20/10:** 70 % to proven channels (CAC below ceiling for 2+ periods), 20 % to
      scaling channels with early signal, 10 % to experiments with a kill date.
    - **Marginal, not average:** the last dollar in a channel returns less than the
      average; cap increases at +30-50 % per period and re-measure.
    - **Fully-loaded CAC** includes media, tools, agency/freelancers and the share of
      salaries; report paid-only CAC separately when comparing platforms.
    - **Pacing:** spend tracks days elapsed ±10 %; front-load only for known seasonality.
    - **Attribution humility:** treat platform-reported ROAS as an upper bound; prefer
      blended CAC and incrementality tests for big reallocations.

    ## Output format
    ```
    # Marketing budget — <period> · total <$>
    **Ceiling:** LTV <$> · max CAC (3:1) <$> · payback target ≤ <n> mo · break-even ROAS <x>

    ## Channel economics (last period)
    | Channel | Spend | Customers | CAC | ROAS | LTV:CAC | Payback | Verdict |
    |---|---|---|---|---|---|---|---|

    ## Allocation (next period)
    | Channel | Tag | Last | Next | Δ | Why |
    |---|---|---|---|---|---|
    Core/emerging/experimental split: 70/20/10 → <actual>

    ## Pacing & triggers
    - Pace: <on / over / under> — <daily budget from here>
    - Move money when: <triggers>

    ## Projection (<n> months)
    | Month | Spend | New customers | Total customers | MRR | Cumulative contribution |
    ```

    ## Anti-patterns
    - Allocating by last year's percentages.
    - LTV from revenue instead of gross margin (inflates the ceiling ~30-60 %).
    - Killing a channel after two weeks of noise, or funding one for a year on "brand".
    - Comparing platform ROAS across channels as if they measured the same thing.
    - Spending 100 % on proven channels (no pipeline of next channels).
    - Ignoring people/tool costs in CAC and then wondering why margins don't add up.
    """,
)


@AGENT.tool
def ltv_and_cac_ceiling(arpu_monthly: float, gross_margin_pct: float, monthly_churn_pct: float, current_cac: float = 0.0, target_ltv_cac: float = 3.0, max_lifetime_months: int = 60) -> dict:
    """Compute LTV (margin-based), expected lifetime, the max CAC at a target LTV:CAC ratio, and payback months at the current CAC.

    Call first; every channel decision is measured against this ceiling.

    Args:
        arpu_monthly: Average revenue per customer per month (for one-off purchases: AOV × purchases per month).
        gross_margin_pct: Gross margin in percent.
        monthly_churn_pct: Monthly customer churn in percent (for one-off businesses use 100 / expected months of repeat buying).
        current_cac: Current blended CAC; 0 to skip payback.
        target_ltv_cac: Target LTV:CAC ratio (default 3).
        max_lifetime_months: Cap on lifetime used for LTV (default 60 months).
    """
    if arpu_monthly <= 0 or not 0 < gross_margin_pct <= 100 or not 0 < monthly_churn_pct <= 100:
        raise ToolError("arpu_monthly > 0; gross_margin_pct and monthly_churn_pct in (0, 100].")
    if target_ltv_cac <= 0 or current_cac < 0 or not 1 <= max_lifetime_months <= 240:
        raise ToolError("target_ltv_cac > 0, current_cac ≥ 0, max_lifetime_months 1-240.")
    margin = gross_margin_pct / 100
    churn = monthly_churn_pct / 100
    lifetime = min(1 / churn, max_lifetime_months)
    monthly_contribution = arpu_monthly * margin
    ltv = monthly_contribution * lifetime
    max_cac = ltv / target_ltv_cac
    out = {
        "monthly_contribution_per_customer": round(monthly_contribution, 2),
        "expected_lifetime_months": round(lifetime, 1),
        "lifetime_capped": (1 / churn) > max_lifetime_months,
        "ltv": round(ltv, 2),
        "max_cac_at_target_ratio": round(max_cac, 2),
        "target_ltv_cac": target_ltv_cac,
        "break_even_roas": round(1 / margin, 2),
    }
    if current_cac:
        ratio = ltv / current_cac
        payback = current_cac / monthly_contribution
        out.update({"current_cac": current_cac, "ltv_to_cac": round(ratio, 2), "payback_months": round(payback, 1), "cac_headroom": round(max_cac - current_cac, 2)})
        health = "healthy" if ratio >= 3 else "thin" if ratio >= 1.5 else "unprofitable"
        out["verdict"] = f"LTV {ltv:,.0f} vs CAC {current_cac:,.0f} = {ratio:.1f}:1 ({health}); payback {payback:.1f} months. Max CAC at {target_ltv_cac}:1 is {max_cac:,.0f}."
    else:
        out["verdict"] = f"LTV {ltv:,.0f} ({lifetime:.0f}-month lifetime × {monthly_contribution:,.0f}/mo contribution). Don't pay more than {max_cac:,.0f} per customer at {target_ltv_cac}:1."
    return out


@AGENT.tool
def channel_economics(channels: list[dict], ltv: float = 0.0, gross_margin_pct: float = 100.0, arpu_monthly: float = 0.0) -> dict:
    """Per-channel CAC, ROAS, LTV:CAC, payback and break-even ROAS, ranked, with a reallocation suggestion from worst to best.

    Call with last period's spend and results per channel. Fixed costs (tools, people) are added to fully-loaded CAC.

    Args:
        channels: List of {"channel": str, "spend": float, "customers": int, "revenue": float (optional), "fixed_costs": float (optional), "tag": "core"|"emerging"|"experimental" (optional)}.
        ltv: Customer LTV (margin-based) from ltv_and_cac_ceiling; 0 to skip LTV:CAC.
        gross_margin_pct: Gross margin in percent, for break-even ROAS (default 100 = revenue basis).
        arpu_monthly: Monthly revenue per customer, for payback months; 0 to skip.
    """
    if not channels or len(channels) > 50:
        raise ToolError("Provide 1-50 channels.")
    if not 0 < gross_margin_pct <= 100 or ltv < 0 or arpu_monthly < 0:
        raise ToolError("gross_margin_pct in (0, 100]; ltv and arpu_monthly ≥ 0.")
    margin = gross_margin_pct / 100
    be_roas = 1 / margin
    rows = []
    tot_spend = tot_cust = tot_rev = tot_fixed = 0.0
    for raw in channels:
        try:
            name = str(raw.get("channel", "channel"))
            spend = float(raw.get("spend", 0))
            cust = float(raw.get("customers", 0))
            rev = float(raw.get("revenue", 0) or 0)
            fixed = float(raw.get("fixed_costs", 0) or 0)
        except (AttributeError, TypeError, ValueError):
            raise ToolError("Each channel needs channel, spend, customers (numbers).") from None
        if spend < 0 or cust < 0 or rev < 0 or fixed < 0:
            raise ToolError(f"{name}: negative values are not allowed.")
        total_cost = spend + fixed
        cac = total_cost / cust if cust else None
        paid_cac = spend / cust if cust else None
        roas = rev / spend if spend and rev else None
        ltv_cac = ltv / cac if (ltv and cac) else None
        payback = cac / (arpu_monthly * margin) if (cac and arpu_monthly) else None
        if cust == 0 and total_cost > 0:
            verdict = "no customers — kill or fix tracking"
        elif ltv_cac is not None:
            verdict = "scale" if ltv_cac >= 3 else "hold" if ltv_cac >= 1.5 else "cut"
        elif roas is not None:
            verdict = "scale" if roas >= 1.5 * be_roas else "hold" if roas >= be_roas else "cut"
        else:
            verdict = "insufficient data"
        rows.append({"channel": name, "tag": str(raw.get("tag", "") or ""), "spend": spend, "fixed_costs": fixed, "customers": int(cust), "revenue": rev, "cac_fully_loaded": round(cac, 2) if cac else None, "cac_paid_only": round(paid_cac, 2) if paid_cac else None, "roas": round(roas, 2) if roas else None, "ltv_to_cac": round(ltv_cac, 2) if ltv_cac else None, "payback_months": round(payback, 1) if payback else None, "verdict": verdict})
        tot_spend += spend
        tot_fixed += fixed
        tot_cust += cust
        tot_rev += rev
    blended_cac = (tot_spend + tot_fixed) / tot_cust if tot_cust else None
    ranked = sorted([r for r in rows if r["cac_fully_loaded"]], key=lambda r: r["cac_fully_loaded"])
    suggestion = None
    if len(ranked) >= 2:
        best, worst = ranked[0], ranked[-1]
        if worst["cac_fully_loaded"] > 1.5 * best["cac_fully_loaded"]:
            move = round(0.3 * worst["spend"], 2)
            extra = move / best["cac_fully_loaded"] - move / worst["cac_fully_loaded"]
            suggestion = {"from": worst["channel"], "to": best["channel"], "amount": move, "expected_extra_customers": round(extra, 1), "note": "Move ≤ 30% per period and re-measure — marginal CAC rises as a channel scales."}
    share = [{"channel": r["channel"], "spend_share_pct": round(100 * r["spend"] / tot_spend, 1) if tot_spend else 0} for r in rows]
    summary = f"Blended CAC {blended_cac:,.0f}" if blended_cac else "No customers recorded"
    if ranked:
        summary += f"; best {ranked[0]['channel']} ({ranked[0]['cac_fully_loaded']:,.0f}), worst {ranked[-1]['channel']} ({ranked[-1]['cac_fully_loaded']:,.0f})."
        if suggestion:
            summary += f" Move {suggestion['amount']:,.0f} from {suggestion['from']} to {suggestion['to']} (≈ +{suggestion['expected_extra_customers']:.0f} customers)."
    else:
        summary += "."
    return {
        "channels": rows,
        "ranked_by_cac": [r["channel"] for r in ranked],
        "totals": {"spend": tot_spend, "fixed_costs": tot_fixed, "customers": int(tot_cust), "revenue": tot_rev, "blended_cac": round(blended_cac, 2) if blended_cac else None, "blended_roas": round(tot_rev / tot_spend, 2) if tot_spend and tot_rev else None},
        "break_even_roas": round(be_roas, 2),
        "spend_share": share,
        "reallocation": suggestion,
        "summary": summary,
    }


@AGENT.tool
def allocate_budget(total: float, channels: list[dict], core_pct: float = 70.0, emerging_pct: float = 20.0, experimental_pct: float = 10.0) -> dict:
    """Allocate a budget across channels by weight under min/max constraints, and compare the core/emerging/experimental split to the 70/20/10 rule.

    Call after grading channels; use 1/CAC (or the efficiency you trust) as the weight.

    Args:
        total: Total budget for the period.
        channels: List of {"channel": str, "weight": float, "min": float (optional), "max": float (optional), "tag": "core"|"emerging"|"experimental"}.
        core_pct: Target share for proven channels (default 70).
        emerging_pct: Target share for scaling channels (default 20).
        experimental_pct: Target share for experiments (default 10).
    """
    if total <= 0:
        raise ToolError("total must be > 0.")
    if not channels or len(channels) > 50:
        raise ToolError("Provide 1-50 channels.")
    if abs(core_pct + emerging_pct + experimental_pct - 100) > 0.01:
        raise ToolError("core_pct + emerging_pct + experimental_pct must equal 100.")
    items = []
    for raw in channels:
        try:
            name = str(raw.get("channel", "channel"))
            w = float(raw.get("weight", 1))
            lo = float(raw.get("min", 0) or 0)
            hi = raw.get("max")
            hi = float(hi) if hi is not None else None
        except (AttributeError, TypeError, ValueError):
            raise ToolError("Each channel needs channel and weight (numbers); min/max optional.") from None
        if w < 0 or lo < 0 or (hi is not None and hi < lo):
            raise ToolError(f"{name}: weight ≥ 0, min ≥ 0, max ≥ min.")
        items.append({"channel": name, "weight": w, "min": lo, "max": hi, "tag": str(raw.get("tag", "") or "").lower()})
    if sum(i["min"] for i in items) > total + 1e-9:
        raise ToolError(f"Minimums sum to {sum(i['min'] for i in items):,.0f}, more than the {total:,.0f} budget.")
    # Proportional-to-weight with bounds ("water-filling"): amount_i = clamp(λ·w_i, min_i, max_i), with λ
    # chosen so the amounts sum to the total. A minimum is a floor, not an extra on top of the weight share.
    def filled(lam: float) -> dict[str, float]:
        out = {}
        for i in items:
            v = max(i["min"], lam * i["weight"])
            out[i["channel"]] = min(v, i["max"]) if i["max"] is not None else v
        return out

    uncapped = any(i["max"] is None and i["weight"] > 0 for i in items)
    ceiling = float("inf") if uncapped else sum(filled(1e18).values())
    if ceiling <= total:
        alloc = filled(1e18)  # every weighted channel at its max; the rest can't be placed
    else:
        lo, hi = 0.0, 1.0
        while sum(filled(hi).values()) < total:
            hi *= 2
        for _ in range(200):
            mid = (lo + hi) / 2
            if sum(filled(mid).values()) < total:
                lo = mid
            else:
                hi = mid
        alloc = filled(hi)
        # Trim the sub-cent bisection overshoot from the largest channel that stays above its floor.
        over = sum(alloc.values()) - total
        floors = {i["channel"]: i["min"] for i in items}
        movable = [c for c in alloc if alloc[c] - over >= floors[c]]
        if over > 0 and movable:
            alloc[max(movable, key=lambda c: alloc[c])] -= over
    remaining = total - sum(alloc.values())
    unallocated = round(remaining, 2) if remaining > 0.005 else 0.0
    rows = [{"channel": i["channel"], "tag": i["tag"] or "untagged", "amount": round(alloc[i["channel"]], 2), "share_pct": round(100 * alloc[i["channel"]] / total, 1), "at_min": abs(alloc[i["channel"]] - i["min"]) < 0.01 and i["min"] > 0, "at_max": i["max"] is not None and abs(alloc[i["channel"]] - i["max"]) < 0.01} for i in items]
    rows.sort(key=lambda r: -r["amount"])
    by_tag = {"core": 0.0, "emerging": 0.0, "experimental": 0.0, "untagged": 0.0}
    for r in rows:
        by_tag[r["tag"] if r["tag"] in by_tag else "untagged"] += r["amount"]
    split = {k: round(100 * v / total, 1) for k, v in by_tag.items()}
    targets = {"core": core_pct, "emerging": emerging_pct, "experimental": experimental_pct}
    deviations = [f"{k}: {split[k]}% vs target {targets[k]}%" for k in targets if abs(split[k] - targets[k]) > 10]
    warnings = []
    if unallocated:
        warnings.append(f"{unallocated:,.2f} could not be allocated — every channel hit its max. Raise a cap or add a channel.")
    if split["untagged"] > 0:
        warnings.append(f"{split['untagged']}% of budget is untagged — tag each channel core/emerging/experimental.")
    small_paid = [r["channel"] for r in rows if 0 < r["amount"] < 1000 and r["tag"] != "experimental"]
    if small_paid:
        warnings.append(f"Under 1,000 for {', '.join(small_paid)} — below a meaningful test budget; consolidate or drop.")
    return {
        "total": total,
        "allocation": rows,
        "split_by_tag_pct": split,
        "target_split_pct": targets,
        "split_deviations": deviations,
        "unallocated": unallocated,
        "warnings": warnings,
        "summary": f"Allocated {total - unallocated:,.0f} of {total:,.0f} across {len(rows)} channels; core/emerging/experimental = {split['core']}/{split['emerging']}/{split['experimental']}%" + (f" ({len(deviations)} deviation(s) from 70/20/10)." if deviations else " — on rule."),
    }


@AGENT.tool
def pacing_check(budget: float, spent_to_date: float, period_start: str, period_end: str, as_of: str = "", tolerance_pct: float = 10.0) -> dict:
    """Month-to-date pacing: expected spend by today, pace ratio, projected end-of-period spend and the daily budget to land on plan.

    Call with mid-period actuals; act when pace is outside the tolerance band.

    Args:
        budget: Budget for the period.
        spent_to_date: Amount spent so far (through the end of yesterday, ideally).
        period_start: First day of the period, YYYY-MM-DD.
        period_end: Last day of the period (inclusive), YYYY-MM-DD.
        as_of: The date the spend figure is current to, YYYY-MM-DD (defaults to today).
        tolerance_pct: Acceptable deviation from linear pace in percent (default 10).
    """
    if budget <= 0 or spent_to_date < 0:
        raise ToolError("budget > 0 and spent_to_date ≥ 0.")
    start, end = dates.parse_date(period_start), dates.parse_date(period_end)
    today = dates.parse_date(as_of) if as_of else date.today()
    if end < start:
        raise ToolError("period_end is before period_start.")
    if today < start:
        raise ToolError("as_of is before the period starts.")
    total_days = (end - start).days + 1
    elapsed = min(total_days, (today - start).days + 1)
    remaining_days = total_days - elapsed
    expected = budget * elapsed / total_days
    pace = spent_to_date / expected if expected else 0
    projected = spent_to_date / elapsed * total_days if elapsed else 0
    remaining_budget = budget - spent_to_date
    daily_needed = remaining_budget / remaining_days if remaining_days > 0 else 0
    current_daily = spent_to_date / elapsed if elapsed else 0
    tol = tolerance_pct / 100
    status = "on pace" if abs(pace - 1) <= tol else "over pace" if pace > 1 else "under pace"
    action = "Hold daily budgets."
    if status == "over pace":
        action = f"Cut daily spend to {daily_needed:,.0f}/day (from {current_daily:,.0f}) or you'll finish at {projected:,.0f} ({100 * (projected / budget - 1):+.0f}%)."
        if remaining_budget <= 0:
            action = f"Budget exhausted with {remaining_days} day(s) left — pause or approve an overage of {projected - budget:,.0f}."
    elif status == "under pace":
        action = f"Raise daily spend to {daily_needed:,.0f}/day (from {current_daily:,.0f}) or accept underspend of {budget - projected:,.0f}. Don't dump it all in the last 3 days."
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(), "as_of": today.isoformat(), "days_total": total_days, "days_elapsed": elapsed, "days_remaining": remaining_days},
        "budget": budget,
        "spent_to_date": spent_to_date,
        "expected_spend_to_date": round(expected, 2),
        "pace_ratio": round(pace, 3),
        "status": status,
        "projected_end_spend": round(projected, 2),
        "projected_variance": round(projected - budget, 2),
        "remaining_budget": round(remaining_budget, 2),
        "current_daily_rate": round(current_daily, 2),
        "daily_budget_to_land_on_plan": round(daily_needed, 2),
        "action": action,
        "summary": f"{status} ({pace:.2f}× linear) on day {elapsed}/{total_days}: spent {spent_to_date:,.0f} vs expected {expected:,.0f}; projected {projected:,.0f} of {budget:,.0f}. {action}",
    }


@AGENT.tool
def growth_projection(monthly_budget: float, cac: float, arpu_monthly: float, gross_margin_pct: float, monthly_churn_pct: float, months: int = 12, starting_customers: int = 0, cac_inflation_pct_per_month: float = 0.0) -> dict:
    """Project new and total customers, MRR, gross profit and cumulative contribution month by month under a marketing budget.

    Call to turn a budget into a target — and to find the month cumulative contribution turns positive.

    Args:
        monthly_budget: Marketing spend per month.
        cac: Blended customer acquisition cost.
        arpu_monthly: Revenue per customer per month.
        gross_margin_pct: Gross margin in percent.
        monthly_churn_pct: Monthly customer churn in percent.
        months: Horizon in months (1-60).
        starting_customers: Customers at month 0.
        cac_inflation_pct_per_month: How much CAC rises each month as channels saturate (e.g. 2 for +2%/month).
    """
    if monthly_budget < 0 or cac <= 0 or arpu_monthly <= 0 or not 0 < gross_margin_pct <= 100 or not 0 <= monthly_churn_pct <= 100:
        raise ToolError("Check inputs: budget ≥ 0, cac > 0, arpu > 0, margin in (0,100], churn in [0,100].")
    if not 1 <= months <= 60 or starting_customers < 0 or cac_inflation_pct_per_month < 0:
        raise ToolError("months 1-60, starting_customers ≥ 0, cac inflation ≥ 0.")
    margin = gross_margin_pct / 100
    churn = monthly_churn_pct / 100
    customers = float(starting_customers)
    cum = 0.0
    rows = []
    breakeven_month = None
    cohort, cohort_cum, cohort_breakeven = 0.0, 0.0, None
    cur_cac = cac
    for m in range(1, months + 1):
        new = monthly_budget / cur_cac
        churned = customers * churn
        customers = customers - churned + new
        mrr = customers * arpu_monthly
        gp = mrr * margin
        contribution = gp - monthly_budget
        cum += contribution
        if breakeven_month is None and cum >= 0:
            breakeven_month = m
        # The cohort bought by this budget alone (excludes starting customers), to judge the spend itself.
        cohort = cohort * (1 - churn) + new
        cohort_cum += cohort * arpu_monthly * margin - monthly_budget
        if cohort_breakeven is None and cohort_cum >= 0:
            cohort_breakeven = m
        rows.append({"month": m, "spend": round(monthly_budget, 2), "cac": round(cur_cac, 2), "new_customers": round(new, 1), "churned": round(churned, 1), "customers": round(customers, 1), "mrr": round(mrr, 2), "gross_profit": round(gp, 2), "contribution": round(contribution, 2), "cumulative_contribution": round(cum, 2), "acquired_cohort_customers": round(cohort, 1), "acquired_cohort_cumulative_contribution": round(cohort_cum, 2)})
        cur_cac *= 1 + cac_inflation_pct_per_month / 100
    end_cac = rows[-1]["cac"]
    steady = monthly_budget / end_cac / churn if churn else None  # at the final (inflated) CAC
    last = rows[-1]
    return {
        "months": months,
        "projection": rows,
        "end_customers": last["customers"],
        "end_mrr": last["mrr"],
        "total_spend": round(monthly_budget * months, 2),
        "total_new_customers": round(sum(r["new_customers"] for r in rows), 1),
        "cumulative_contribution": last["cumulative_contribution"],
        "breakeven_month": breakeven_month,
        "acquired_cohort_breakeven_month": cohort_breakeven,
        "acquired_cohort_cumulative_contribution": round(cohort_cum, 2),
        "steady_state_customers": round(steady, 0) if steady else None,
        "summary": f"After {months} months: {last['customers']:,.0f} customers, MRR {last['mrr']:,.0f}, cumulative contribution {last['cumulative_contribution']:,.0f}"
        + (f"; turns positive in month {breakeven_month}." if breakeven_month else "; not yet positive.")
        + (
            f" The spend's own cohort (excluding the {starting_customers:,} starting customers) "
            + (f"pays back in month {cohort_breakeven}." if cohort_breakeven else f"has not paid back yet ({cohort_cum:,.0f}).")
            if starting_customers
            else ""
        )
        + (f" Steady state at this budget/churn (CAC {end_cac:,.0f}) ≈ {steady:,.0f} customers." if steady else ""),
    }

