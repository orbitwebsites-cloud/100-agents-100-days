"""Unit Economics — LTV, CAC, payback, NRR, cohorts and efficiency ratios, computed the way a board expects."""

from __future__ import annotations

from decimal import Decimal

from ...core import Agent, ToolError
from ._common import D, as_pct, ZERO, as_rate, bound_rows, money, pct, ratio_to_pct, require_nonneg, require_positive

AGENT = Agent(
    slug="unit-economics",
    name="Unit Economics",
    category="finance",
    tagline="LTV, CAC, payback, NRR, cohort retention and burn multiple — computed correctly and benchmarked, not hand-waved.",
    description=(
        "Computes the unit economics an investor or CFO will actually check: gross-margin-adjusted LTV "
        "and LTV/CAC, CAC payback in months, gross and net revenue retention, logo churn and quick ratio, "
        "cohort retention curves with a leaky-bucket test, contribution margin and break-even units, and "
        "the efficiency ratios (magic number, burn multiple, Rule of 40). Every metric comes with the "
        "formula used, the benchmark it is judged against, and the lever that moves it."
    ),
    triggers=[
        "calculate LTV / CAC / payback period",
        "what is our net revenue retention / NRR / GRR",
        "analyse cohort retention",
        "are our unit economics good",
        "burn multiple / magic number / rule of 40",
        "contribution margin and break-even",
    ],
    examples=[
        "ARPA is $220/month, gross margin 78%, monthly churn 2.1%, CAC $2,900. Are we in good shape?",
        "Start of year ARR $2.4M, churned $180k, contraction $60k, expansion $410k, new $900k. What are GRR and NRR?",
        "Here are 8 monthly cohorts with customer counts by month since signup — is retention flattening?",
    ],
    connectors=["Stripe", "ChartMogul", "HubSpot", "Google Sheets", "QuickBooks"],
    playbook="""
    ## Standard
    You are a SaaS CFO preparing the metrics page of a board deck. Excellent means: every number is
    defined the way a Series A/B investor defines it, the formula is stated, the benchmark is named,
    and the diagnosis says which lever to pull. The one metric that matters is **LTV/CAC on a
    gross-margin basis with a payback under 18 months** — any business that clears that can scale;
    one that does not is buying revenue. Never present revenue LTV as LTV.

    ## Intake
    Needed: ARPA (average revenue per account per month), gross margin %, monthly logo or revenue
    churn, blended CAC (all sales + marketing spend ÷ new customers), and for retention: starting
    ARR, churned, contraction, expansion, new. Ask at most 3 questions only if CAC or churn is
    missing. Otherwise assume software gross margin 75% and say so. Distinguish monthly from annual
    churn explicitly; mixing them is the most common error.

    ## Procedure
    1. **Core ratios.** Call `unit_economics__ltv_cac` with ARPA, gross margin, monthly churn, CAC and
       any net expansion. It returns customer lifetime, gross-margin LTV, LTV/CAC, CAC payback months,
       and the verdict against benchmarks (LTV/CAC ≥ 3, payback ≤ 12 months SMB / ≤ 18 mid-market /
       ≤ 24 enterprise). Report both the simple LTV and the discounted one if provided.
    2. **Retention.** Call `unit_economics__retention_metrics` with the period's starting ARR (or
       MRR), churned, contraction, expansion and new. It returns GRR, NRR, revenue churn and the SaaS
       quick ratio. GRR is the truth-teller; NRR above 100% with GRR below 80% is a leaky bucket
       masked by upsell.
    3. **Cohorts.** With cohort tables, call `unit_economics__cohort_analysis`. It normalises each
       cohort to 100% at month 0, gives the average curve, month-3/6/12 retention, and tests whether
       the curve flattens (slope of the last three periods). A curve that keeps falling means the
       product has not found retention; growth spend is premature.
    4. **Contribution.** Call `unit_economics__contribution_margin` with price and every variable
       cost (COGS, hosting, payment fees, support, commissions). It returns unit contribution,
       contribution margin % and break-even units against fixed costs. If contribution margin is
       under 50% for software, the pricing or cost structure is the problem, not marketing.
    5. **Efficiency.** Call `unit_economics__efficiency_metrics` with net new ARR, S&M spend, net
       burn, growth rate and margin. It returns magic number (> 0.75 = step on the gas), burn
       multiple (< 1 great, 1-2 good, > 2 stop), and Rule of 40.
    6. **Diagnose and prescribe.** For each metric below benchmark name one lever: churn →
       onboarding/activation; CAC → channel mix or sales cycle; payback → annual prepay, price;
       NRR → expansion packaging; contribution → hosting/payment costs.

    ## Frameworks
    - **LTV (gross margin)** = ARPA × GM% ÷ monthly churn (adjust churn for net expansion when given).
    - **CAC payback** = CAC ÷ (ARPA × GM%) in months.
    - **GRR** = (start − churn − contraction) ÷ start; **NRR** = (start − churn − contraction + expansion) ÷ start.
    - **Quick ratio** = (new + expansion) ÷ (churn + contraction); > 4 is excellent.
    - **Magic number** = net new ARR (quarter) × 4 ÷ prior-quarter S&M; **burn multiple** = net burn ÷ net new ARR.
    - **Rule of 40**: revenue growth % + profit margin % ≥ 40.
    - Benchmarks (public and PE SaaS data, widely cited): NRR 100-110% median, 120%+ top quartile;
      GRR ≥ 90% enterprise, ≥ 80% SMB; monthly logo churn < 1% enterprise, 3-5% SMB.

    ## Output format
    ```
    # Unit economics — <company / segment> — <period>
    | Metric | Value | Formula | Benchmark | Status |
    |---|---|---|---|---|
    | LTV (GM) | $… | ARPA×GM÷churn | — | |
    | LTV/CAC | …x | | ≥3x | ✓/✗ |
    | CAC payback | … mo | CAC÷(ARPA×GM) | ≤18 | |
    | GRR / NRR | …% / …% | | ≥85% / ≥110% | |
    | Burn multiple | …x | burn÷net new ARR | <2 | |

    ## Diagnosis
    <3 sentences: the constraint, the evidence, the lever>

    ## Levers (ranked by impact on LTV/CAC)
    1. <lever> — moves <metric> from X to Y

    ## Assumptions
    - <each one stated>
    ```

    ## Anti-patterns
    - Revenue LTV. Always gross-margin LTV, and say so.
    - Annual churn plugged into a monthly formula (or the reverse).
    - Quoting NRR without GRR.
    - LTV from a 2% churn assumption when cohorts show 6%. Cohorts beat assumptions.
    - "Payback" computed on revenue rather than gross profit.
    - Presenting a ratio with no benchmark or no lever.
    """,
)

BENCH = {"ltv_cac_min": Decimal(3), "payback_smb": 12, "payback_mid": 18, "payback_ent": 24}


@AGENT.tool
def ltv_cac(
    arpa_monthly: float,
    gross_margin_pct: float,
    monthly_churn_pct: float,
    cac: float,
    monthly_expansion_pct: float = 0,
    annual_discount_rate_pct: float = 0,
    segment: str = "mid-market",
) -> dict:
    """Gross-margin LTV, LTV/CAC and CAC payback months with benchmark verdicts.

    LTV = ARPA × GM ÷ (churn − expansion) using monthly rates; if expansion ≥ churn, lifetime is
    capped at 10 years and flagged. Optional discount rate gives a discounted LTV (perpetuity).

    Args:
        arpa_monthly: Average revenue per account per month.
        gross_margin_pct: Gross margin, e.g. 78 for 78%.
        monthly_churn_pct: Monthly revenue (or logo) churn, e.g. 2.1. Convert annual first: monthly = 1 − (1 − annual)^(1/12).
        cac: Fully loaded customer acquisition cost (all S&M ÷ new customers in the period).
        monthly_expansion_pct: Net monthly expansion from existing accounts, e.g. 0.5.
        annual_discount_rate_pct: Discount rate for a discounted LTV, e.g. 10. 0 = undiscounted.
        segment: "smb", "mid-market" or "enterprise" — sets the payback benchmark (12 / 18 / 24 months).
    """
    arpa = require_positive(D(arpa_monthly, "arpa_monthly"), "arpa_monthly")
    gm = as_rate(gross_margin_pct, "gross_margin_pct")
    if not 0 < gm <= 1:
        raise ToolError("gross_margin_pct must be between 0 and 100")
    churn = as_pct(monthly_churn_pct, "monthly_churn_pct")
    if not 0 <= churn <= 1:
        raise ToolError("monthly_churn_pct must be between 0 and 100")
    exp = as_pct(monthly_expansion_pct, "monthly_expansion_pct")
    cac_d = require_positive(D(cac, "cac"), "cac")
    seg = segment.lower().strip()
    payback_bench = {"smb": 12, "enterprise": 24}.get(seg, 18)
    net_churn = churn - exp
    gp_month = arpa * gm
    capped = False
    if net_churn <= 0:
        lifetime = Decimal(120)
        capped = True
    else:
        lifetime = min(1 / net_churn, Decimal(120))
        capped = lifetime == 120
    ltv = gp_month * lifetime
    ltv_revenue = arpa * lifetime
    ratio = ltv / cac_d
    payback = cac_d / gp_month if gp_month else None
    out = {
        "gross_profit_per_month": money(gp_month),
        "customer_lifetime_months": pct(lifetime, 1),
        "lifetime_capped_at_120_months": capped,
        "ltv_gross_margin": money(ltv),
        "ltv_revenue_basis_do_not_use": money(ltv_revenue),
        "ltv_to_cac": pct(ratio, 2),
        "cac_payback_months": pct(payback, 1),
        "benchmarks": {"ltv_to_cac_min": 3, "payback_max_months": payback_bench, "segment": seg},
        "formulas": {"ltv": "ARPA x GM% / (monthly churn - monthly expansion)", "payback": "CAC / (ARPA x GM%)"},
    }
    if annual_discount_rate_pct:
        r = as_pct(annual_discount_rate_pct, "annual_discount_rate_pct") / 12
        disc_ltv = gp_month / (net_churn + r) if (net_churn + r) > 0 else ltv
        out["ltv_discounted"] = money(disc_ltv)
        out["ltv_to_cac_discounted"] = pct(disc_ltv / cac_d, 2)
    status = []
    status.append("LTV/CAC " + ("✓" if ratio >= 3 else "✗") + f" ({pct(ratio, 2)}x vs ≥3x)")
    status.append("payback " + ("✓" if payback <= payback_bench else "✗") + f" ({pct(payback, 1)} mo vs ≤{payback_bench})")
    if ratio >= 3 and payback <= payback_bench:
        verdict = "Healthy: " + "; ".join(status) + ". Scale acquisition; watch that blended CAC holds as channels saturate."
    elif ratio >= 3:
        verdict = "Profitable but slow: " + "; ".join(status) + ". Push annual prepay or raise price to pull payback in."
    elif payback <= payback_bench:
        verdict = "Fast payback, short lifetime: " + "; ".join(status) + ". Churn is the constraint — fix activation before spending more."
    else:
        verdict = "Buying revenue: " + "; ".join(status) + ". Do not scale spend until churn or CAC moves."
    if capped:
        verdict += " Lifetime capped at 120 months (expansion ≥ churn) — treat LTV as an upper bound."
    out["verdict"] = verdict
    return out


@AGENT.tool
def retention_metrics(starting_revenue: float, churned: float, contraction: float = 0, expansion: float = 0, new: float = 0, starting_logos: int = 0, churned_logos: int = 0) -> dict:
    """GRR, NRR, revenue churn, logo churn and SaaS quick ratio for a period, with benchmarks.

    Use ARR or MRR consistently for all inputs. Period is whatever the inputs cover (month, quarter, year).

    Args:
        starting_revenue: ARR/MRR at the start of the period from existing customers.
        churned: Revenue lost from customers who cancelled in the period.
        contraction: Revenue lost from downgrades.
        expansion: Revenue gained from upsell/cross-sell of existing customers.
        new: Revenue from brand-new customers in the period (for quick ratio and ending revenue).
        starting_logos: Customer count at start (optional, for logo churn).
        churned_logos: Customers lost in the period (optional).
    """
    start = require_positive(D(starting_revenue, "starting_revenue"), "starting_revenue")
    ch = require_nonneg(D(churned, "churned"), "churned")
    con = require_nonneg(D(contraction, "contraction"), "contraction")
    ex = require_nonneg(D(expansion, "expansion"), "expansion")
    nw = require_nonneg(D(new, "new"), "new")
    if ch + con > start:
        raise ToolError("churned + contraction cannot exceed starting_revenue")
    grr = (start - ch - con) / start
    nrr = (start - ch - con + ex) / start
    lost = ch + con
    quick = (nw + ex) / lost if lost > 0 else None
    ending = start - ch - con + ex + nw
    out = {
        "grr_pct": ratio_to_pct(grr),
        "nrr_pct": ratio_to_pct(nrr),
        "gross_revenue_churn_pct": ratio_to_pct(lost / start),
        "net_revenue_churn_pct": ratio_to_pct((lost - ex) / start),
        "quick_ratio": pct(quick, 2) if quick is not None else None,
        "ending_revenue": money(ending),
        "growth_pct": ratio_to_pct((ending - start) / start),
        "benchmarks": {"grr_smb": 80, "grr_enterprise": 90, "nrr_median": 100, "nrr_top_quartile": 120, "quick_ratio_good": 4},
    }
    if starting_logos:
        if churned_logos > starting_logos or churned_logos < 0:
            raise ToolError("churned_logos must be between 0 and starting_logos")
        out["logo_churn_pct"] = ratio_to_pct(Decimal(churned_logos) / Decimal(starting_logos))
    flags = []
    if grr < Decimal("0.8"):
        flags.append(f"GRR {out['grr_pct']}% is below the 80% floor — a leaky bucket regardless of NRR")
    if nrr >= Decimal("1.2"):
        flags.append("NRR in the top quartile (≥120%) — expansion is a growth engine; invest in account management")
    elif nrr < 1:
        flags.append("NRR under 100% — the existing base shrinks every period without new logos")
    if quick is not None and quick < 1:
        flags.append("quick ratio under 1 — losing more than you add; growth spend is filling a hole")
    out["flags"] = flags
    out["verdict"] = f"GRR {out['grr_pct']}%, NRR {out['nrr_pct']}%, quick ratio {out['quick_ratio']}" + (". " + "; ".join(flags) if flags else ". Retention is healthy; the base compounds on its own.")
    return out


@AGENT.tool
def cohort_analysis(cohorts: list[dict], flatten_threshold_pct: float = 1.0) -> dict:
    """Normalise cohort tables to retention curves, average them, and test whether retention flattens.

    Each cohort lists the active customers (or revenue) by month since acquisition, month 0 first.
    Returns per-cohort retention %, the average curve, month-1/3/6/12 retention, the slope over the
    last three observed periods, and a leaky-bucket verdict.

    Args:
        cohorts: List of {"cohort": "2026-01", "values": [120, 96, 84, 79, ...]} with month 0 first. Ragged lengths are fine.
        flatten_threshold_pct: Average monthly drop (percentage points) below which the curve counts as flat. Default 1.0.
    """
    rows = bound_rows(cohorts, "cohorts", limit=120)
    curves = []
    for i, c in enumerate(rows, 1):
        if not isinstance(c, dict) or not isinstance(c.get("values"), list) or not c["values"]:
            raise ToolError(f"cohorts[{i}] needs a non-empty 'values' list")
        vals = [D(v, f"cohorts[{i}].values") for v in c["values"][:60]]
        if vals[0] <= 0:
            raise ToolError(f"cohorts[{i}]: month-0 value must be positive")
        ret = [ratio_to_pct(v / vals[0]) for v in vals]
        if any(r > 100 for r in ret[1:]):
            note = "values exceed month 0 (net expansion) — revenue cohort"
        else:
            note = None
        curves.append({"cohort": str(c.get("cohort") or f"cohort {i}"), "size": float(vals[0]), "retention_pct": ret, "note": note})
    max_len = max(len(c["retention_pct"]) for c in curves)
    avg = []
    for m in range(max_len):
        obs = [c["retention_pct"][m] for c in curves if len(c["retention_pct"]) > m]
        avg.append({"month": m, "avg_retention_pct": pct(sum(Decimal(str(o)) for o in obs) / len(obs), 1), "cohorts_observed": len(obs)})
    def at(m):
        return avg[m]["avg_retention_pct"] if m < len(avg) else None
    slope = None
    if len(avg) >= 4:
        last = [Decimal(str(a["avg_retention_pct"])) for a in avg[-4:] if a["cohorts_observed"] >= 1]
        if len(last) >= 2:
            slope = (last[-1] - last[0]) / (len(last) - 1)
    thr = D(flatten_threshold_pct, "flatten_threshold_pct")
    if slope is None:
        shape = "too short to judge (need ≥4 months)"
    elif slope >= -thr:
        shape = "flattening — a retained core exists"
    else:
        shape = "still falling — leaky bucket; retention not yet found"
    return {
        "cohorts": curves,
        "average_curve": avg,
        "retention_at": {"m1": at(1), "m3": at(3), "m6": at(6), "m12": at(12)},
        "late_slope_pts_per_month": pct(slope, 2) if slope is not None else None,
        "shape": shape,
        "verdict": f"Average retention m1 {at(1) if at(1) is not None else 'n/a'}%, m3 {at(3) if at(3) is not None else 'n/a'}%, m6 {at(6) if at(6) is not None else 'n/a'}%; late-period slope {pct(slope, 2) if slope is not None else 'n/a'} pts/month → {shape}.",
    }


@AGENT.tool
def contribution_margin(price: float, variable_costs: list[dict], fixed_costs_monthly: float = 0, payment_fee_pct: float = 0, units_per_month: float = 0) -> dict:
    """Unit contribution margin after every variable cost, and break-even units against fixed costs.

    Args:
        price: Price per unit (per customer per month, per order, etc.).
        variable_costs: List of {"name": str, "amount": n} per-unit costs, or {"name": str, "pct": n} as percent of price (e.g. commissions).
        fixed_costs_monthly: Monthly fixed costs to cover (salaries, rent) for the break-even calculation.
        payment_fee_pct: Card/processor fee as percent of price, e.g. 2.9 (added on top of variable_costs).
        units_per_month: Current monthly units (optional) to report margin of safety.
    """
    p = require_positive(D(price, "price"), "price")
    costs = bound_rows(variable_costs, "variable_costs", limit=100) if variable_costs else []
    total_var = ZERO
    lines = []
    for i, c in enumerate(costs, 1):
        if not isinstance(c, dict):
            raise ToolError(f"variable_costs[{i}] must be an object")
        if "pct" in c:
            amt = p * as_pct(c["pct"], f"variable_costs[{i}].pct")
        else:
            amt = D(c.get("amount", 0), f"variable_costs[{i}].amount")
        amt = require_nonneg(amt, f"variable_costs[{i}]")
        total_var += amt
        lines.append({"name": str(c.get("name") or f"cost {i}"), "per_unit": money(amt), "pct_of_price": ratio_to_pct(amt / p)})
    if payment_fee_pct:
        fee = p * as_pct(payment_fee_pct, "payment_fee_pct")
        total_var += fee
        lines.append({"name": "payment processing", "per_unit": money(fee), "pct_of_price": ratio_to_pct(fee / p)})
    contrib = p - total_var
    cm = contrib / p
    fixed = require_nonneg(D(fixed_costs_monthly, "fixed_costs_monthly"), "fixed_costs_monthly")
    be_units = (fixed / contrib).quantize(Decimal("1"), rounding="ROUND_CEILING") if contrib > 0 and fixed > 0 else None
    out = {
        "price": money(p),
        "variable_cost_per_unit": money(total_var),
        "contribution_per_unit": money(contrib),
        "contribution_margin_pct": ratio_to_pct(cm),
        "cost_lines": lines,
        "breakeven_units_monthly": float(be_units) if be_units is not None else None,
        "breakeven_revenue_monthly": money(be_units * p) if be_units is not None else None,
    }
    if units_per_month and D(units_per_month) > 0:
        u = D(units_per_month)
        out["current_contribution_monthly"] = money(u * contrib)
        out["operating_profit_monthly"] = money(u * contrib - fixed)
        if be_units is not None:
            out["margin_of_safety_pct"] = ratio_to_pct((u - be_units) / u)
    if contrib <= 0:
        out["verdict"] = f"Negative contribution: every unit loses ${money(-contrib):,.2f}. Volume makes it worse — fix price or variable cost first."
    else:
        out["verdict"] = f"Contribution ${money(contrib):,.2f}/unit ({out['contribution_margin_pct']}%)" + (f"; break-even at {out['breakeven_units_monthly']:,.0f} units/month (${out['breakeven_revenue_monthly']:,.2f})." if be_units is not None else ".") + (" Below the 50% software norm — cost structure, not marketing, is the constraint." if cm < Decimal("0.5") else "")
    return out


@AGENT.tool
def efficiency_metrics(
    net_new_arr: float,
    sales_marketing_spend: float,
    net_burn: float = 0,
    revenue_growth_pct: float = 0,
    profit_margin_pct: float = 0,
    period: str = "quarter",
) -> dict:
    """Magic number, burn multiple, CAC ratio and Rule of 40 with the standard benchmarks.

    Magic number annualises net new ARR for a quarter (×4) over the period's S&M spend; for a year
    it uses the raw ratio. Burn multiple = net burn ÷ net new ARR for the same period.

    Args:
        net_new_arr: Net new ARR added in the period (ending ARR − starting ARR).
        sales_marketing_spend: Total sales + marketing spend in the period (ideally the prior period for magic number).
        net_burn: Net cash burned in the period (0 if profitable).
        revenue_growth_pct: Year-over-year revenue growth, e.g. 65.
        profit_margin_pct: Operating or free-cash-flow margin, e.g. -20.
        period: "quarter" or "year" — the period the inputs cover.
    """
    nn = D(net_new_arr, "net_new_arr")
    sm = require_positive(D(sales_marketing_spend, "sales_marketing_spend"), "sales_marketing_spend")
    burn = D(net_burn, "net_burn")
    if period not in ("quarter", "year"):
        raise ToolError("period must be 'quarter' or 'year'")
    magic = (nn * (4 if period == "quarter" else 1)) / sm
    burn_multiple = (burn / nn) if nn > 0 and burn > 0 else None
    cac_ratio = sm / nn if nn > 0 else None
    r40 = D(revenue_growth_pct, "revenue_growth_pct") + D(profit_margin_pct, "profit_margin_pct")
    out = {
        "magic_number": pct(magic, 2),
        "burn_multiple": pct(burn_multiple, 2) if burn_multiple is not None else None,
        "cac_ratio_sm_per_dollar_arr": pct(cac_ratio, 2) if cac_ratio is not None else None,
        "rule_of_40": pct(r40, 1),
        "benchmarks": {"magic_number": "<0.5 fix funnel; 0.5-0.75 ok; >0.75 invest more", "burn_multiple": "<1 amazing; 1-1.5 great; 1.5-2 good; 2-3 suspect; >3 bad", "rule_of_40": ">=40 healthy"},
    }
    notes = []
    notes.append("magic number " + ("strong — step on the gas" if magic > Decimal("0.75") else "acceptable" if magic >= Decimal("0.5") else "weak — fix the funnel before adding spend"))
    if burn_multiple is not None:
        notes.append("burn multiple " + ("excellent" if burn_multiple < 1 else "great" if burn_multiple < Decimal("1.5") else "good" if burn_multiple < 2 else "suspect" if burn_multiple < 3 else "bad — every $1 of ARR costs $3+ of burn"))
    elif nn <= 0:
        notes.append("net new ARR ≤ 0 — burn multiple undefined; the business is shrinking")
    notes.append("Rule of 40 " + ("met" if r40 >= 40 else f"missed by {pct(40 - r40, 1)} pts"))
    out["verdict"] = "; ".join(notes) + "."
    return out
