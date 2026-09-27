"""Startup Financial Model — MRR projection, hiring-plan burn, runway and round sizing with real compounding."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from ...core import Agent, ToolError
from ._common import D, as_pct, ZERO, add_months, as_rate, bound_rows, cagr, money, month_label, parse_iso, pct, ratio_to_pct, require_nonneg, require_positive

AGENT = Agent(
    slug="startup-model",
    name="Startup Financial Model",
    category="finance",
    tagline="A driver-based startup model: MRR projection, hiring-plan burn, runway and how much to raise — with the compounding done right.",
    description=(
        "Builds the three tables every seed-to-Series-B model needs and investors actually read: a "
        "monthly MRR projection driven by new, expansion and churn (with CMGR and months-to-target), a "
        "hiring plan that turns roles and start months into fully loaded monthly burn, a runway model that "
        "combines the two with cash to find the zero-cash month, and round sizing that turns a milestone "
        "plan into a raise amount and dilution. Outputs a founder-readable summary and the sensitivity that "
        "matters most."
    ),
    triggers=[
        "build a financial model / projections for my startup",
        "project MRR / ARR for the next 24 months",
        "how much does my hiring plan cost / burn",
        "how much should we raise and what dilution",
        "when do we run out of money with this plan",
        "what growth rate do we need to hit $1M ARR",
    ],
    examples=[
        "MRR is $42k, we add $6k new MRR a month growing 5%, churn 2.5%, expansion 1%. Project 24 months and tell me when we hit $100k MRR.",
        "We plan to hire 2 engineers in Jan at $160k, a sales lead in March at $140k plus commission, a designer in June at $120k. What's the burn?",
        "We have $1.2M, burning $95k/month, want 24 months of runway after the raise. How much should we raise at a $12M pre?",
    ],
    connectors=["Google Sheets", "Notion", "QuickBooks", "Stripe", "Carta"],
    playbook="""
    ## Standard
    You are a startup CFO who has built the model for several venture-backed companies. Excellent
    means: a driver-based model (new, expansion, churn, headcount) where every number is traceable to
    an assumption a founder can defend, not a top-down "we'll get 1% of the market". The one metric
    that matters is **months of runway to the next fundable milestone with 6 months of buffer**.
    Projections are estimates; label them as such, never as forecasts of fact.

    ## Intake
    Needed: current MRR, new MRR per month (or new customers × ARPA), monthly churn %, expansion %,
    cash on hand, current monthly costs, and the hiring plan (role, start month, salary). Ask at most
    3 questions only if MRR, cash or costs are missing. Otherwise assume: churn 3% monthly for SMB /
    1% for enterprise, salary load factor 1.3, and say so.

    ## Procedure
    1. **Project revenue.** Call `startup_model__mrr_projection` with starting MRR, new MRR, its
       monthly growth, churn and expansion, and the horizon (24-36 months). It returns the monthly
       table, ending MRR/ARR, CMGR and the month you cross any target you pass. Check the implied
       growth against benchmarks: T2D3 (triple, triple, double, double, double) from $1M ARR is
       top-decile; 10-15% MoM at seed stage is strong; 5% is fundable.
    2. **Cost the team.** Call `startup_model__hiring_plan_burn` with every planned hire and start
       month, the load factor for benefits/taxes/equipment, and existing non-payroll costs. It returns
       monthly headcount and total burn, and flags any month where payroll jumps by more than 25%.
    3. **Combine into runway.** Call `startup_model__runway_projection` with cash, the monthly
       revenue series from step 1 and the cost series from step 2 (both as lists). It returns net burn
       per month, cash balance, the zero-cash month, the minimum cash month, and whether the plan
       reaches break-even before cash runs out. If zero-cash arrives before the milestone month plus
       6 months, the plan fails; cut hires or raise.
    4. **Size the round.** Call `startup_model__fundraise_sizing` with the burn (peak or average from
       step 3), target runway months (18-24 is standard), buffer, and valuation terms. It returns the
       raise amount, post-money, dilution and founder ownership after the round and option pool.
       Sanity check dilution: 15-25% per priced round is typical; more than 30% is a red flag.
    5. **Sensitivity.** Rerun step 1 with churn +2 points and new MRR −25%. Report ending ARR and
       zero-cash month under each. The founder should see the plan's fragility in one table.
    6. **Write the summary** in the output format with every assumption listed.

    ## Frameworks
    - **MRR bridge**: ending = starting + new + expansion − churn − contraction. Report each.
    - **CMGR** = (end ÷ start)^(1/months) − 1.
    - **Load factor**: salary × 1.25-1.4 covers payroll tax, benefits, equipment, software.
    - **Runway target after raise**: 18-24 months, milestone + 6 months buffer.
    - **Dilution** = raise ÷ post-money; option pool top-ups usually come out of the pre-money.
    - **Benchmarks**: seed → A needs ~$1M+ ARR growing 3x; A → B needs $3-5M ARR growing 2-3x
      (widely cited ranges; they move with the market).

    ## Output format
    ```
    # Model summary — <company> — <horizon>
    **Today:** MRR $X · burn $Y/mo · cash $Z · runway N mo
    **Plan:** MRR $X → $A in M months (CMGR c%) · peak burn $B · zero-cash <YYYY-MM> · break-even <YYYY-MM|not in horizon>

    ## MRR projection (quarterly view)
    | Month | New | Expansion | Churn | Ending MRR | ARR |

    ## Hiring plan & burn
    | Month | Headcount | Payroll | Other | Total burn |

    ## Raise
    Raise $R for M months of runway → post-money $P, dilution d%, founders own f% after pool

    ## Sensitivity
    | Case | Ending ARR | Zero-cash | Break-even |

    ## Assumptions
    - <every driver, one per line>
    ```

    ## Anti-patterns
    - Top-down market-share revenue. Drivers or nothing.
    - Churn applied to new MRR in the same month it is added, or ignored entirely.
    - Hiring costs at salary only; the load factor is real cash.
    - A hockey stick with no change in the drivers that would cause it.
    - Raising for exactly the runway needed. Fundraising takes 3-6 months; buffer is mandatory.
    - Doing the compounding by hand. Every table comes from a tool call.
    """,
)


@AGENT.tool
def mrr_projection(
    starting_mrr: float,
    months: int,
    new_mrr_monthly: float,
    new_mrr_growth_pct: float = 0,
    churn_pct: float = 3,
    expansion_pct: float = 0,
    target_mrr: float = 0,
    start_month: str = "",
) -> dict:
    """Project MRR month by month from new, expansion and churn drivers; report CMGR and the month a target is reached.

    Each month: churn and expansion apply to the opening MRR; new MRR is added after (so it is not
    churned in its first month); new MRR itself compounds at new_mrr_growth_pct.

    Args:
        starting_mrr: MRR today.
        months: Horizon in months (1-60).
        new_mrr_monthly: New MRR added from new customers in month 1.
        new_mrr_growth_pct: Monthly growth in the new-MRR figure, e.g. 5 for 5% MoM.
        churn_pct: Monthly gross revenue churn (incl. contraction), e.g. 3 for 3%.
        expansion_pct: Monthly expansion as a percent of opening MRR, e.g. 1.
        target_mrr: Optional target; the tool reports the first month at or above it.
        start_month: YYYY-MM-DD in the first projected month (month 1 is labelled with this month); defaults to today.
    """
    mrr = require_nonneg(D(starting_mrr, "starting_mrr"), "starting_mrr")
    if not 1 <= months <= 60:
        raise ToolError("months must be 1-60")
    new = require_nonneg(D(new_mrr_monthly, "new_mrr_monthly"), "new_mrr_monthly")
    g = as_pct(new_mrr_growth_pct, "new_mrr_growth_pct")
    churn = as_pct(churn_pct, "churn_pct")
    exp = as_pct(expansion_pct, "expansion_pct")
    if not 0 <= churn <= 1 or not 0 <= exp <= 1 or g < Decimal("-0.9") or g > 1:
        raise ToolError("churn_pct and expansion_pct must be 0-100; new_mrr_growth_pct between -90 and 100")
    tgt = D(target_mrr, "target_mrr") if target_mrr else ZERO
    start = parse_iso(start_month, "start_month") if start_month else date.today()
    rows, target_month = [], None
    cur, cur_new = mrr, new
    tot_new = tot_exp = tot_churn = ZERO
    for m in range(1, months + 1):
        churned = cur * churn
        expanded = cur * exp
        ending = cur - churned + expanded + cur_new
        tot_new += cur_new
        tot_exp += expanded
        tot_churn += churned
        rows.append({"month": m, "label": month_label(add_months(start, m - 1)), "opening": money(cur), "new": money(cur_new), "expansion": money(expanded), "churn": money(-churned), "ending_mrr": money(ending), "arr": money(ending * 12), "mom_growth_pct": ratio_to_pct((ending - cur) / cur) if cur else None})
        if tgt and target_month is None and ending >= tgt:
            target_month = m
        cur = ending
        cur_new = cur_new * (1 + g)
    cm = cagr(mrr, cur, Decimal(months)) if mrr > 0 else None
    steady_state = (cur_new / (churn - exp)) if exp < churn else None  # MRR converges to N / (churn - expansion) if new MRR stops growing
    return {
        "starting_mrr": money(mrr),
        "ending_mrr": money(cur),
        "ending_arr": money(cur * 12),
        "months": months,
        "cmgr_pct": ratio_to_pct(cm) if cm is not None else None,
        "totals": {"new": money(tot_new), "expansion": money(tot_exp), "churn": money(tot_churn)},
        "net_new_mrr_avg": money((cur - mrr) / months),
        "target_mrr": money(tgt) if tgt else None,
        "target_reached_month": target_month,
        "target_reached_label": rows[target_month - 1]["label"] if target_month else None,
        "steady_state_mrr_if_new_flat": money(steady_state) if steady_state is not None else None,
        "monthly": rows,
        "verdict": (
            f"MRR ${money(mrr):,.0f} → ${money(cur):,.0f} in {months} months (CMGR {ratio_to_pct(cm) if cm is not None else 'n/a'}%, ARR ${money(cur * 12):,.0f})."
            + (f" Target ${money(tgt):,.0f} reached in month {target_month} ({rows[target_month - 1]['label']})." if target_month else f" Target ${money(tgt):,.0f} not reached in horizon." if tgt else "")
            + (f" Churn caps MRR near ${money(steady_state):,.0f} unless new MRR keeps growing." if steady_state is not None and steady_state < cur * 2 else "")
        ),
    }


@AGENT.tool
def hiring_plan_burn(hires: list[dict], months: int, load_factor: float = 1.3, existing_monthly_costs: float = 0, existing_headcount: int = 0, existing_payroll_monthly: float = 0, start_month: str = "") -> dict:
    """Turn a hiring plan into monthly headcount and fully loaded burn, flagging payroll step-ups.

    Loaded monthly cost per hire = annual_salary × load_factor ÷ 12 (+ monthly extras such as commission or contractor fees).

    Args:
        hires: List of {"role": str, "start_month": int (1 = first month of horizon), "annual_salary": n, "count": int (default 1), "monthly_extra": n (optional, e.g. commission)}.
        months: Horizon in months (1-60).
        load_factor: Multiplier on salary for taxes, benefits, equipment (1.25-1.4 typical).
        existing_monthly_costs: Current non-payroll monthly costs (rent, software, hosting, marketing).
        existing_headcount: People already on payroll.
        existing_payroll_monthly: Current fully loaded monthly payroll for existing staff.
        start_month: YYYY-MM-DD in month 1 of the horizon (labels month 1 with this month); defaults to today.
    """
    rows = bound_rows(hires, "hires", limit=200)
    if not 1 <= months <= 60:
        raise ToolError("months must be 1-60")
    lf = D(load_factor, "load_factor")
    if not 1 <= lf <= 2:
        raise ToolError("load_factor must be between 1.0 and 2.0")
    other = require_nonneg(D(existing_monthly_costs, "existing_monthly_costs"), "existing_monthly_costs")
    base_payroll = require_nonneg(D(existing_payroll_monthly, "existing_payroll_monthly"), "existing_payroll_monthly")
    if existing_headcount < 0:
        raise ToolError("existing_headcount cannot be negative")
    start = parse_iso(start_month, "start_month") if start_month else date.today()
    plan = []
    for i, h in enumerate(rows, 1):
        if not isinstance(h, dict):
            raise ToolError(f"hires[{i}] must be an object")
        sm = int(h.get("start_month", 1))
        if not 1 <= sm <= months:
            raise ToolError(f"hires[{i}] ({h.get('role', '?')}): start_month must be 1-{months}")
        sal = require_nonneg(D(h.get("annual_salary", 0), f"hires[{i}].annual_salary"), f"hires[{i}].annual_salary")
        count = int(h.get("count", 1))
        if count < 1 or count > 100:
            raise ToolError(f"hires[{i}]: count must be 1-100")
        extra = require_nonneg(D(h.get("monthly_extra", 0), f"hires[{i}].monthly_extra"), f"hires[{i}].monthly_extra")
        monthly = (sal * lf / 12 + extra) * count
        plan.append({"role": str(h.get("role") or f"hire {i}"), "start_month": sm, "count": count, "loaded_monthly_cost": money(monthly), "_m": monthly})
    table, flags = [], []
    prev_payroll = base_payroll
    cum = ZERO
    for m in range(1, months + 1):
        active = [p for p in plan if p["start_month"] <= m]
        payroll = base_payroll + sum(p["_m"] for p in active)
        hc = existing_headcount + sum(p["count"] for p in active)
        total = payroll + other
        cum += total
        if prev_payroll > 0 and payroll > prev_payroll * Decimal("1.25"):
            flags.append(f"month {m}: payroll steps up {ratio_to_pct(payroll / prev_payroll - 1)}% — stagger starts if cash is tight")
        table.append({"month": m, "label": month_label(add_months(start, m - 1)), "headcount": hc, "payroll": money(payroll), "other_costs": money(other), "total_burn": money(total), "starts": [p["role"] for p in plan if p["start_month"] == m]})
        prev_payroll = payroll
    for p in plan:
        p.pop("_m")
    peak = max(table, key=lambda r: r["total_burn"])
    return {
        "hires": plan,
        "months": months,
        "monthly": table,
        "burn_series": [r["total_burn"] for r in table],
        "starting_burn": table[0]["total_burn"],
        "ending_burn": table[-1]["total_burn"],
        "peak_burn": {"month": peak["month"], "amount": peak["total_burn"]},
        "ending_headcount": table[-1]["headcount"],
        "cumulative_burn": money(cum),
        "flags": flags,
        "verdict": f"Burn grows from ${table[0]['total_burn']:,.0f} to ${table[-1]['total_burn']:,.0f}/month over {months} months (headcount {table[0]['headcount']} → {table[-1]['headcount']}); cumulative ${money(cum):,.0f}." + (" " + "; ".join(flags[:3]) if flags else ""),
    }


@AGENT.tool
def runway_projection(cash: float, monthly_revenue: list[float], monthly_costs: list[float], gross_margin_pct: float = 100, milestone_month: int = 0, start_month: str = "") -> dict:
    """Combine cash, a revenue series and a cost series into a monthly cash balance, zero-cash month and break-even check.

    Series are month 1 first; the shorter one is extended with its last value. Revenue is scaled by
    gross margin if costs exclude COGS.

    Args:
        cash: Cash on hand at the start of month 1.
        monthly_revenue: Revenue collected per month (e.g. ending_mrr per month from mrr_projection).
        monthly_costs: Total cash costs per month (e.g. burn_series from hiring_plan_burn).
        gross_margin_pct: If monthly_costs exclude cost of revenue, pass the gross margin so revenue is net of COGS. Default 100 (costs already include COGS).
        milestone_month: The month you need to reach (next raise or break-even) — the tool checks for milestone + 6 months buffer.
        start_month: YYYY-MM-DD in month 1 (use the same start_month as mrr_projection and hiring_plan_burn); defaults to today.
    """
    c = D(cash, "cash")
    if not monthly_revenue and not monthly_costs:
        raise ToolError("Give monthly_revenue and/or monthly_costs series")
    n = max(len(monthly_revenue), len(monthly_costs))
    if n > 120:
        raise ToolError("series must be at most 120 months")
    gm = as_rate(gross_margin_pct, "gross_margin_pct")
    if not 0 < gm <= 1:
        raise ToolError("gross_margin_pct must be between 0 and 100")
    rev = [require_nonneg(D(x, "monthly_revenue"), "monthly_revenue") for x in monthly_revenue] or [ZERO]
    cost = [require_nonneg(D(x, "monthly_costs"), "monthly_costs") for x in monthly_costs] or [ZERO]
    rev += [rev[-1]] * (n - len(rev))
    cost += [cost[-1]] * (n - len(cost))
    start = parse_iso(start_month, "start_month") if start_month else date.today()
    bal, rows = c, []
    zero_m = be_m = None
    low = (1, c)
    for m in range(1, n + 1):
        net = rev[m - 1] * gm - cost[m - 1]
        bal += net
        if bal < low[1]:
            low = (m, bal)
        if zero_m is None and bal < 0:
            zero_m = m
        if be_m is None and net >= 0 and m > 1:
            be_m = m
        rows.append({"month": m, "label": month_label(add_months(start, m - 1)), "revenue": money(rev[m - 1]), "costs": money(cost[m - 1]), "net_burn": money(-net), "cash": money(bal)})
    needed = money(-low[1]) if low[1] < 0 else 0.0
    ok_milestone = None
    if milestone_month:
        if milestone_month < 1:
            raise ToolError("milestone_month must be >= 1")
        need_until = milestone_month + 6
        ok_milestone = zero_m is None or zero_m > need_until
    verdict = (
        (f"Cash runs out in month {zero_m} ({rows[zero_m - 1]['label']})" if zero_m else f"Cash stays positive through month {n}")
        + (f"; break-even in month {be_m} ({rows[be_m - 1]['label']})" if be_m else "; no break-even in horizon")
        + (f". Lowest cash ${money(low[1]):,.0f} in month {low[0]} — plan needs ${needed:,.0f} more." if low[1] < 0 else f". Lowest cash ${money(low[1]):,.0f} in month {low[0]}.")
        + ("" if ok_milestone is None else (" Covers the milestone plus 6 months buffer." if ok_milestone else f" Does NOT cover milestone month {milestone_month} + 6 months — cut costs or raise before month {zero_m}."))
    )
    return {
        "months": n,
        "zero_cash_month": zero_m,
        "zero_cash_label": rows[zero_m - 1]["label"] if zero_m else None,
        "breakeven_month": be_m,
        "lowest_cash": {"month": low[0], "amount": money(low[1])},
        "additional_cash_needed": needed,
        "ending_cash": money(bal),
        "runway_months": (zero_m - 1) if zero_m else n,
        "milestone_covered_with_buffer": ok_milestone,
        "monthly": rows,
        "verdict": verdict,
    }


@AGENT.tool
def fundraise_sizing(
    monthly_burn: float,
    runway_months_target: int = 24,
    buffer_months: int = 6,
    pre_money_valuation: float = 0,
    option_pool_pct: float = 0,
    founder_ownership_pct: float = 100,
    burn_growth_pct_monthly: float = 0,
) -> dict:
    """Size a round from burn and target runway, then compute post-money, dilution and founder ownership.

    Raise = cumulative burn over (runway + buffer) months, with burn compounding if it grows.
    A post-money option pool is carved from the pre-money (the standard investor ask), so
    founders bear it.

    Args:
        monthly_burn: Net burn per month at the start of the runway period.
        runway_months_target: Months of runway the raise must fund (18-24 typical).
        buffer_months: Extra months for the next raise process (3-6 typical).
        pre_money_valuation: Agreed or expected pre-money (0 to skip dilution math).
        option_pool_pct: NEW post-money option pool investors require, e.g. 10 (treated as entirely new shares from the pre-money; subtract any existing unallocated pool first).
        founder_ownership_pct: Founders' combined ownership before the round, e.g. 80.
        burn_growth_pct_monthly: If burn grows each month (hiring), e.g. 3 for 3% MoM.
    """
    burn = require_positive(D(monthly_burn, "monthly_burn"), "monthly_burn")
    if not 1 <= runway_months_target <= 60 or not 0 <= buffer_months <= 24:
        raise ToolError("runway_months_target must be 1-60 and buffer_months 0-24")
    g = as_pct(burn_growth_pct_monthly, "burn_growth_pct_monthly")
    if not -Decimal("0.5") <= g <= Decimal("0.5"):
        raise ToolError("burn_growth_pct_monthly must be between -50 and 50")
    total_months = runway_months_target + buffer_months
    cum, b = ZERO, burn
    for _ in range(total_months):
        cum += b
        b *= 1 + g
    raise_amt = cum.quantize(Decimal("1E3"), rounding="ROUND_CEILING")
    out = {
        "months_funded": total_months,
        "cumulative_burn": money(cum),
        "raise_amount": money(raise_amt),
        "ending_monthly_burn": money(b / (1 + g)) if g else money(burn),
        "verdict": f"Raise ${money(raise_amt):,.0f} to fund {runway_months_target} months plus a {buffer_months}-month buffer" + (f" (burn grows to ${money(b / (1 + g)):,.0f}/mo)." if g else "."),
    }
    if pre_money_valuation:
        pre = require_positive(D(pre_money_valuation, "pre_money_valuation"), "pre_money_valuation")
        pool = as_rate(option_pool_pct, "option_pool_pct")
        founders = as_rate(founder_ownership_pct, "founder_ownership_pct")
        if not 0 <= pool < Decimal("0.5") or not 0 < founders <= 1:
            raise ToolError("option_pool_pct must be 0-49 and founder_ownership_pct 1-100")
        post = pre + raise_amt
        investor_pct = raise_amt / post
        # pool sized as % of post-money but created before the round: it comes entirely out of existing holders
        if investor_pct + pool >= 1:
            raise ToolError("raise plus option pool would exceed 100% of the company — check pre_money_valuation")
        existing_after = 1 - investor_pct - pool
        founders_after = founders * existing_after
        effective_pre = pre - pool * post  # what the pre-money is really worth to existing holders
        out.update(
            {
                "pre_money": money(pre),
                "post_money": money(post),
                "investor_ownership_pct": ratio_to_pct(investor_pct),
                "option_pool_pct": ratio_to_pct(pool),
                "effective_pre_money_after_pool": money(effective_pre),
                "founders_before_pct": ratio_to_pct(founders),
                "founders_after_pct": ratio_to_pct(founders_after),
                "founder_dilution_pct": ratio_to_pct(1 - founders_after / founders),
                "price_per_1pct": money(post / 100),
            }
        )
        flag = " Dilution over 30% in one round is a red flag — negotiate valuation or raise less." if investor_pct + (pool if pool else 0) > Decimal("0.30") else ""
        out["verdict"] += f" At ${money(pre):,.0f} pre → ${money(post):,.0f} post; investors get {ratio_to_pct(investor_pct)}%, founders go {ratio_to_pct(founders)}% → {ratio_to_pct(founders_after)}%" + (f" (pool {ratio_to_pct(pool)}% carved from pre-money)." if pool else ".") + flag
    return out
