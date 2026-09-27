"""Pricing Strategist — price like a monetisation lead: Van Westendorp, tiers, elasticity, break-even volume."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from ...core import Agent, ToolError
from ._common import D, ZERO, as_rate, bound_rows, money, pct, ratio_to_pct, require_nonneg, require_positive

AGENT = Agent(
    slug="pricing-strategist",
    name="Pricing Strategist",
    category="finance",
    tagline="Set and change prices with evidence: Van Westendorp price bands, a tiered ladder, elasticity and break-even volume math.",
    description=(
        "Runs the pricing process a SaaS monetisation lead follows: analyses willingness-to-pay survey "
        "data with the Van Westendorp Price Sensitivity Meter (exact curve intersections, not eyeballed), "
        "builds a Good/Better/Best tier ladder with anchoring ratios, charm prices and annual discounts, "
        "estimates price elasticity from real price/volume observations, and computes how much volume a "
        "price change must gain or can afford to lose to break even on gross profit. Ends with a packaging "
        "and price recommendation plus the test to run before rollout."
    ),
    triggers=[
        "what should I charge / how to price my product",
        "analyse Van Westendorp / pricing survey results",
        "build pricing tiers / good better best packaging",
        "should I raise prices and by how much",
        "how price sensitive are my customers (elasticity)",
        "will a discount pay for itself",
    ],
    examples=[
        "Here are 120 Van Westendorp responses (too cheap / bargain / expensive / too expensive). What price range should we launch in?",
        "We charge $49/month flat. Design a 3-tier ladder with an annual plan.",
        "Our gross margin is 70%. If we raise prices 15%, how many customers can we lose and still come out ahead?",
    ],
    connectors=["Stripe", "HubSpot", "Google Sheets", "Notion", "Typeform"],
    playbook="""
    ## Standard
    You are the head of monetisation at a company that treats pricing as its highest-leverage lever
    (a 1% price improvement is worth ~11% in operating profit for a typical firm, per McKinsey's
    classic analysis — far more than a 1% volume gain). Excellent means a recommendation with a
    number, the evidence behind it, the risk (volume loss you can absorb) and the experiment that
    validates it before full rollout. The one metric: **gross profit per customer × retained
    customers**, not revenue and never "conversion rate" alone.

    ## Intake
    Needed: current price(s) and packaging, gross margin or unit cost, who the buyer is and what value
    metric scales with their use (seats, usage, revenue), and any evidence: survey data, past price
    changes with volume before/after, win/loss notes. Ask at most 3 questions, only if margin or
    current price is missing. Otherwise assume a 75% gross margin for software, 40% for services,
    and say so.

    ## Procedure
    1. **Find the acceptable band.** With survey data, call `pricing_strategist__van_westendorp`
       with the four responses per respondent. It returns PMC (point of marginal cheapness), PME
       (point of marginal expensiveness), OPP (optimal price point) and IPP (indifference price point)
       from exact curve intersections, and drops inconsistent respondents. The launch price sits
       between IPP and PME for a differentiated product; near OPP for a volume play. Below 30 valid
       responses, present the band as directional only.
    2. **Learn from history.** With any past price/volume observations, call
       `pricing_strategist__elasticity`. It returns arc elasticity between points, the
       revenue-maximising and profit-maximising observed prices, and whether demand is elastic
       (|E| > 1: price cuts grow revenue) or inelastic (|E| < 1: price rises grow revenue).
    3. **Quantify the bet.** For any proposed change, call `pricing_strategist__price_change_breakeven`
       with the current price, margin and proposed change. It gives the exact volume change that keeps
       gross profit flat. A 10% rise at 70% margin breaks even at a 12.5% volume loss; if you believe
       you would lose less, raise. Also use it for discounts: the lift a discount needs is usually far
       larger than sales expects.
    4. **Design the ladder.** Call `pricing_strategist__tier_builder` with the anchor (mid) price and
       target tier count. It returns Good/Better/Best prices on the ~1 : 2-2.5 : 5+ ratio, charm-rounded,
       with the annual price at the discount you choose (default two months free) and a decoy check.
       Assign features so each tier maps to a buyer segment, not a feature count.
    5. **Recommend and de-risk.** State the price, packaging, value metric, expected volume impact,
       and the rollout: new customers first, then existing customers with 30-60 days' notice and
       grandfathering for 6-12 months if churn risk is high. Propose the A/B or cohort test with the
       decision rule (e.g. "ship if conversion drops < 12.5%").

    ## Frameworks
    - **Van Westendorp PSM**: PMC = "too cheap" × "not cheap"; PME = "too expensive" × "not
      expensive"; OPP = "too cheap" × "too expensive"; IPP = "cheap" × "expensive".
    - **Break-even volume change** = −Δp / (margin + Δp) for a price change Δp at gross margin m.
    - **Good/Better/Best** (Mohammed): 3 tiers, middle tier is the target, top tier anchors.
      Most revenue should come from the middle; if > 70% buy the cheapest, the middle is mispriced.
    - **Value metric**: charge on the unit that grows with the customer's success (seats, volume,
      revenue) — not on features the buyer cannot predict needing.
    - **Charm pricing** ($49, $99, $199) for self-serve; round numbers ($50k) for enterprise.
    - **Annual discount**: 15-20% (two months free) is the norm; more than 25% signals weak retention.

    ## Output format
    ```
    # Pricing recommendation — <product>
    **Recommended:** $X/<metric>/month · **Acceptable band:** $PMC–$PME (OPP $Y, IPP $Z) · **Confidence:** high|medium|low (n=…)

    ## Ladder
    | Tier | Monthly | Annual (per month) | For whom | Includes |

    ## The bet
    Change: +/−N% · Break-even volume change: ±M% · Expected: … · Gross profit impact: $…

    ## Rollout & test
    - New customers: <date> · Existing: <date, notice, grandfathering>
    - Test: <design>, decision rule: <ship if …>

    ## Risks
    - <one line each>
    ```

    ## Anti-patterns
    - Cost-plus pricing. Costs set the floor, not the price; value and willingness to pay set the price.
    - Reading Van Westendorp intersections by eye or from a chart. Compute them.
    - Ten tiers, or three tiers that differ only by usage caps nobody understands.
    - Discounting to close without computing the volume the discount must generate.
    - Raising prices on existing customers overnight with no notice, or never raising them at all.
    - Optimising revenue when margin differs by tier. Optimise gross profit.
    """,
)


def _curve(values: list[Decimal], grid: list[Decimal], ascending: bool) -> list[Decimal]:
    """Cumulative share of respondents at each grid price (ascending: share with value <= p; else >= p)."""
    n = Decimal(len(values))
    out = []
    for p in grid:
        k = sum(1 for v in values if (v <= p if ascending else v >= p))
        out.append(Decimal(k) / n)
    return out


def _cross(grid: list[Decimal], a: list[Decimal], b: list[Decimal]) -> Decimal | None:
    """First price where curve a crosses curve b (a starts above b), with linear interpolation."""
    for i in range(1, len(grid)):
        d0, d1 = a[i - 1] - b[i - 1], a[i] - b[i]
        if d0 == 0:
            return grid[i - 1]
        if (d0 > 0) != (d1 > 0):
            if d0 == d1:
                return grid[i]
            t = d0 / (d0 - d1)
            return grid[i - 1] + (grid[i] - grid[i - 1]) * t
    return None


@AGENT.tool
def van_westendorp(responses: list[dict]) -> dict:
    """Compute Van Westendorp price points (PMC, OPP, IPP, PME) from survey responses via exact curve intersections.

    Each respondent gives four prices: too_cheap (quality doubt), bargain (great value), expensive
    (pricey but consider), too_expensive (would not buy). Inconsistent respondents (not
    too_cheap <= bargain <= expensive <= too_expensive) are excluded and reported.

    Args:
        responses: List of {"too_cheap": n, "bargain": n, "expensive": n, "too_expensive": n}, one per respondent.
    """
    rows = bound_rows(responses, "responses", limit=5000)
    valid, dropped = [], 0
    keys = ("too_cheap", "bargain", "expensive", "too_expensive")
    for i, r in enumerate(rows, 1):
        if not isinstance(r, dict):
            raise ToolError(f"responses[{i}] must be an object with {keys}")
        try:
            vals = [D(r[k], f"responses[{i}].{k}") for k in keys]
        except KeyError as e:
            raise ToolError(f"responses[{i}] is missing {e.args[0]!r}") from None
        if any(v < 0 for v in vals):
            raise ToolError(f"responses[{i}]: prices cannot be negative")
        if vals[0] <= vals[1] <= vals[2] <= vals[3]:
            valid.append(vals)
        else:
            dropped += 1
    if len(valid) < 5:
        raise ToolError(f"Need at least 5 consistent responses; got {len(valid)} (dropped {dropped})")
    too_cheap = [v[0] for v in valid]
    bargain = [v[1] for v in valid]
    expensive = [v[2] for v in valid]
    too_exp = [v[3] for v in valid]
    grid = sorted(set(too_cheap + bargain + expensive + too_exp))
    c_too_cheap = _curve(too_cheap, grid, ascending=False)
    c_bargain = _curve(bargain, grid, ascending=False)
    c_expensive = _curve(expensive, grid, ascending=True)
    c_too_exp = _curve(too_exp, grid, ascending=True)
    not_cheap = [1 - x for x in c_bargain]
    not_expensive = [1 - x for x in c_expensive]
    pmc = _cross(grid, c_too_cheap, not_cheap)
    pme = _cross(grid, not_expensive, c_too_exp)
    opp = _cross(grid, c_too_cheap, c_too_exp)
    ipp = _cross(grid, c_bargain, c_expensive)
    n = len(valid)
    conf = "high" if n >= 100 else "medium" if n >= 30 else "low"
    pts = {"pmc": pmc, "opp": opp, "ipp": ipp, "pme": pme}
    fmt = {k: (money(v) if v is not None else None) for k, v in pts.items()}
    median_bargain = sorted(bargain)[n // 2]
    median_expensive = sorted(expensive)[n // 2]
    return {
        "n_valid": n,
        "n_dropped_inconsistent": dropped,
        "confidence": conf,
        "points": fmt,
        "acceptable_range": {"low": fmt["pmc"], "high": fmt["pme"]},
        "medians": {"too_cheap": money(sorted(too_cheap)[n // 2]), "bargain": money(median_bargain), "expensive": money(median_expensive), "too_expensive": money(sorted(too_exp)[n // 2])},
        "definitions": {
            "pmc": "point of marginal cheapness: too_cheap x not_cheap — below this, quality doubts outweigh bargain appeal",
            "opp": "optimal price point: too_cheap x too_expensive — fewest people reject",
            "ipp": "indifference price point: bargain x expensive — perceived 'normal' price",
            "pme": "point of marginal expensiveness: not_expensive x too_expensive — above this, resistance dominates",
        },
        "verdict": (
            f"Acceptable range ${fmt['pmc']:,.2f}–${fmt['pme']:,.2f}; OPP ${fmt['opp']:,.2f}, IPP ${fmt['ipp']:,.2f} (n={n}, {conf} confidence). "
            "Launch between IPP and PME for a differentiated product; near OPP for a volume play."
            if all(v is not None for v in pts.values())
            else f"Some curves never cross (n={n}); widen the survey's price range or collect more responses."
        ),
    }


def _charm(price: Decimal) -> Decimal:
    """Round to a charm price: <$10 -> x.99, <$100 -> ends in 9, <$1000 -> ends in 9 or 99, else nearest 50 minus 1."""
    if price < 10:
        return (price.quantize(Decimal("1"), rounding=ROUND_HALF_UP) - Decimal("0.01")).max(Decimal("0.99"))
    if price < 100:
        base = (price / 10).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * 10
        return max(base - 1, Decimal("9"))
    if price < 1000:
        base = (price / 10).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * 10
        return base - 1
    base = (price / 50).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * 50
    return base - 1


@AGENT.tool
def tier_builder(
    anchor_price: float,
    tiers: int = 3,
    ratios: list[float] | None = None,
    annual_discount_pct: float = 16.7,
    charm: bool = True,
    per_seat: bool = False,
    seats_by_tier: list[int] | None = None,
) -> dict:
    """Build a Good/Better/Best price ladder from an anchor (middle-tier) price with annual prices.

    Default ratios follow the 1 : 2.2 : 5 pattern relative to the lowest tier (middle = anchor).
    Returns monthly and annual prices, the effective annual discount, decoy diagnostics and the
    revenue mix at which the ladder is healthy.

    Args:
        anchor_price: The intended middle-tier monthly price (or the single-tier price today).
        tiers: Number of tiers, 2-5.
        ratios: Optional price multipliers relative to the lowest tier, e.g. [1, 2.2, 5]. Length must equal tiers.
        annual_discount_pct: Discount for annual prepay, e.g. 16.7 = two months free.
        charm: Round to charm prices ($49, $99, $199).
        per_seat: If true, prices are per seat and seats_by_tier gives included seats.
        seats_by_tier: Included seats per tier when per_seat is true, e.g. [1, 5, 20].
    """
    anchor = require_positive(D(anchor_price, "anchor_price"), "anchor_price")
    if not 2 <= tiers <= 5:
        raise ToolError("tiers must be 2-5")
    disc = as_rate(annual_discount_pct, "annual_discount_pct")
    if not 0 <= disc < Decimal("0.6"):
        raise ToolError("annual_discount_pct must be between 0 and 60")
    default_ratios = {2: [1, 2.5], 3: [1, 2.2, 5], 4: [1, 2, 4, 8], 5: [1, 2, 4, 8, 16]}
    rs = [D(x, "ratios") for x in (ratios or default_ratios[tiers])]
    if len(rs) != tiers or any(r <= 0 for r in rs) or rs != sorted(rs):
        raise ToolError("ratios must have one positive, ascending value per tier")
    mid_idx = tiers // 2 if tiers > 2 else 0
    base = anchor / rs[mid_idx]
    names = {2: ["Starter", "Pro"], 3: ["Starter", "Pro", "Business"], 4: ["Starter", "Pro", "Business", "Enterprise"], 5: ["Free-ish", "Starter", "Pro", "Business", "Enterprise"]}[tiers]
    out = []
    for i, r in enumerate(rs):
        raw = base * r
        monthly = _charm(raw) if charm else raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        annual_month = monthly * (1 - disc)
        # annual price: whole dollars (floor) so the discount reads as at least the promised %
        annual_month = annual_month.quantize(Decimal("1"), rounding="ROUND_FLOOR") if charm and annual_month >= 10 else annual_month.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        row = {
            "tier": names[i],
            "monthly": money(monthly),
            "annual_per_month": money(annual_month),
            "annual_total": money(annual_month * 12),
            "effective_annual_discount_pct": ratio_to_pct(1 - annual_month / monthly) if monthly else 0.0,
            "ratio_to_lowest": pct(monthly / (base * rs[0]) if not charm else monthly / _charm(base * rs[0]), 2),
        }
        if per_seat:
            seats = (seats_by_tier or [1] * tiers)[i] if seats_by_tier and len(seats_by_tier) == tiers else 1
            row["included_seats"] = seats
            row["monthly_per_seat"] = money(monthly / seats) if seats else None
        out.append(row)
    steps = [pct(out[i + 1]["monthly"] / out[i]["monthly"], 2) for i in range(tiers - 1)]
    flags = []
    if steps and min(steps) < 1.5:
        flags.append("adjacent tiers less than 1.5x apart — buyers cannot tell them apart; widen the gap or merge")
    if steps and max(steps) > 4:
        flags.append("a jump over 4x between adjacent tiers — the upper tier needs a clearly different buyer (e.g. enterprise) or a middle step")
    return {
        "tiers": out,
        "step_multiples": steps,
        "target_tier": names[mid_idx],
        "healthy_mix": "aim for 50-70% of new revenue on the target tier; if >70% choose the lowest tier, the lowest tier is too generous",
        "flags": flags,
        "verdict": f"{tiers}-tier ladder anchored on {names[mid_idx]} at ${out[mid_idx]['monthly']:,.2f}/mo; annual at ${out[mid_idx]['annual_per_month']:,.2f}/mo ({out[mid_idx]['effective_annual_discount_pct']}% off)." + (" " + "; ".join(flags) if flags else ""),
    }


@AGENT.tool
def elasticity(observations: list[dict], unit_cost: float = 0) -> dict:
    """Estimate price elasticity from observed price/quantity pairs and find the revenue- and profit-best price.

    Uses the arc (midpoint) elasticity between consecutive observations sorted by price. Needs at
    least two distinct prices. Unit cost turns revenue into gross profit for the profit-max point.

    Args:
        observations: List of {"price": n, "quantity": n, "label": str (optional)} — one per period or test cell.
        unit_cost: Variable cost per unit (0 if pure software with negligible marginal cost).
    """
    rows = bound_rows(observations, "observations")
    cost = require_nonneg(D(unit_cost, "unit_cost"), "unit_cost")
    pts = []
    for i, r in enumerate(rows, 1):
        if not isinstance(r, dict):
            raise ToolError(f"observations[{i}] must be an object")
        p = require_positive(D(r.get("price"), f"observations[{i}].price"), f"observations[{i}].price")
        q = require_nonneg(D(r.get("quantity"), f"observations[{i}].quantity"), f"observations[{i}].quantity")
        pts.append({"label": str(r.get("label") or f"obs {i}"), "price": p, "quantity": q})
    pts.sort(key=lambda x: x["price"])
    if len({x["price"] for x in pts}) < 2:
        raise ToolError("Need at least two distinct prices to estimate elasticity")
    segs = []
    for a, b in zip(pts, pts[1:]):
        if a["price"] == b["price"]:
            continue
        dq = (b["quantity"] - a["quantity"]) / ((a["quantity"] + b["quantity"]) / 2) if (a["quantity"] + b["quantity"]) else ZERO
        dp = (b["price"] - a["price"]) / ((a["price"] + b["price"]) / 2)
        e = dq / dp
        segs.append({"from": money(a["price"]), "to": money(b["price"]), "arc_elasticity": pct(e, 2), "classification": "elastic" if abs(e) > 1 else "unit elastic" if abs(e) == 1 else "inelastic"})
    table = []
    for x in pts:
        rev = x["price"] * x["quantity"]
        gp = (x["price"] - cost) * x["quantity"]
        table.append({"label": x["label"], "price": money(x["price"]), "quantity": float(x["quantity"]), "revenue": money(rev), "gross_profit": money(gp)})
    best_rev = max(table, key=lambda t: t["revenue"])
    best_gp = max(table, key=lambda t: t["gross_profit"])
    avg_e = sum(Decimal(str(s["arc_elasticity"])) for s in segs) / len(segs) if segs else None
    overall = "elastic" if avg_e is not None and abs(avg_e) > 1 else "inelastic"
    return {
        "segments": segs,
        "average_elasticity": pct(avg_e, 2) if avg_e is not None else None,
        "overall": overall,
        "table": table,
        "revenue_max": best_rev,
        "profit_max": best_gp,
        "verdict": (
            f"Demand is {overall} (avg arc elasticity {pct(avg_e, 2)}). "
            + ("Price cuts grow revenue here; " if overall == "elastic" else "Price rises grow revenue here; ")
            + f"observed profit-max price ${best_gp['price']:,.2f} ({best_gp['label']}), revenue-max ${best_rev['price']:,.2f}."
            if avg_e is not None
            else "Not enough distinct prices."
        ),
        "caveat": "Observational elasticity conflates price with time/mix effects; confirm with a controlled test before a large change.",
    }


@AGENT.tool
def price_change_breakeven(current_price: float, price_change_pct: float, gross_margin_pct: float = 0, unit_cost: float = 0, current_units: float = 0) -> dict:
    """Volume change needed to keep gross profit flat after a price change, plus margin/markup math.

    Give either gross_margin_pct or unit_cost. Formula: break-even volume change = -dp / (m + dp).
    With current_units it also reports the unit and dollar thresholds.

    Args:
        current_price: Price today.
        price_change_pct: Proposed change, e.g. 10 for +10% or -20 for a 20% discount.
        gross_margin_pct: Gross margin at today's price, e.g. 70. Leave 0 if giving unit_cost.
        unit_cost: Variable cost per unit (alternative to gross_margin_pct).
        current_units: Units sold per period today (optional, for absolute thresholds).
    """
    p = require_positive(D(current_price, "current_price"), "current_price")
    dp = as_rate(price_change_pct, "price_change_pct")
    if dp <= -1 or dp > 5:
        raise ToolError("price_change_pct must be between -99 and 500")
    if gross_margin_pct:
        m = as_rate(gross_margin_pct, "gross_margin_pct")
        if not 0 < m <= 1:
            raise ToolError("gross_margin_pct must be between 0 and 100")
        cost = p * (1 - m)
    elif unit_cost:
        cost = require_nonneg(D(unit_cost, "unit_cost"), "unit_cost")
        if cost >= p:
            raise ToolError("unit_cost must be below current_price")
        m = (p - cost) / p
    else:
        raise ToolError("Give gross_margin_pct or unit_cost")
    new_price = p * (1 + dp)
    new_margin = (new_price - cost) / new_price
    if m + dp <= 0:
        return {
            "new_price": money(new_price),
            "new_gross_margin_pct": ratio_to_pct(new_margin),
            "breakeven_volume_change_pct": None,
            "verdict": f"A {pct(dp * 100)}% cut wipes out the entire {ratio_to_pct(m)}% margin — no volume gain can break even.",
        }
    be = -dp / (m + dp)
    out = {
        "current_price": money(p),
        "new_price": money(new_price),
        "unit_cost": money(cost),
        "gross_margin_pct": ratio_to_pct(m),
        "new_gross_margin_pct": ratio_to_pct(new_margin),
        "markup_pct": ratio_to_pct((p - cost) / cost) if cost else None,
        "breakeven_volume_change_pct": ratio_to_pct(be),
        "unit_profit_before": money(p - cost),
        "unit_profit_after": money(new_price - cost),
    }
    if current_units and D(current_units) > 0:
        u = D(current_units)
        out["current_units"] = float(u)
        out["breakeven_units"] = float((u * (1 + be)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
        out["units_can_lose" if dp > 0 else "units_must_gain"] = float((u * abs(be)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
        out["gross_profit_now"] = money(u * (p - cost))
    if dp > 0:
        out["verdict"] = f"Raising {pct(dp * 100)}% (${money(p):,.2f} → ${money(new_price):,.2f}) at {ratio_to_pct(m)}% margin breaks even if you lose no more than {ratio_to_pct(-be)}% of volume; anything less is pure profit."
    else:
        out["verdict"] = f"Discounting {pct(-dp * 100)}% (${money(p):,.2f} → ${money(new_price):,.2f}) at {ratio_to_pct(m)}% margin needs {ratio_to_pct(be)}% MORE volume just to break even on gross profit."
    return out
