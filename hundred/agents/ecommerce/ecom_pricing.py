"""E-com Pricing — unit economics, target-margin pricing, break-even ROAS and discount math that survive the CFO."""

from __future__ import annotations

import math

from ...core import Agent, ToolError
from ._common import as_fraction, median, money, pct, percentile, require_positive

AGENT = Agent(
    slug="ecom-pricing",
    name="E-com Pricing",
    category="ecommerce",
    tagline="Price products from true unit economics: contribution margin, break-even ROAS, and what a discount really costs.",
    description=(
        "Builds the full per-order P&L (COGS, shipping, packaging, payment and marketplace fees, returns) "
        "and turns it into decisions: the price that hits a target margin after percentage fees, the "
        "break-even ROAS and max CPA for ads, how many extra units a discount must sell to pay for "
        "itself, arc elasticity from a price test, and where you sit against competitors. Every figure "
        "is computed, with formulas shown, so pricing arguments end with numbers not opinions."
    ),
    triggers=[
        "what should I price this product at",
        "calculate my margin / markup / unit economics",
        "what's my break-even ROAS or max CPA",
        "should I run a 20% off sale — is it worth it",
        "how much can I discount and still make money",
        "analyze my price test / price elasticity",
        "am I priced too high vs competitors",
    ],
    examples=[
        "COGS $12.40, ship $6.10, box $0.80, Shopify Payments 2.9% + 30c, 8% return rate. I sell at $39.99 — what's my contribution margin and break-even ROAS?",
        "I want 60% gross margin on a product that costs me $18 landed and sells on Amazon (15% referral + $4.75 FBA). What price?",
        "We ran 20% off last week: 1,450 units vs 900 the week before at full price. Was it profitable? Cost $14, price $35.",
    ],
    connectors=["Shopify", "Google Sheets", "Stripe", "Amazon Seller Central"],
    playbook="""
    ## Standard
    You are the pricing lead of a profitable DTC brand — the person who killed the sitewide
    sale and grew profit anyway. The one metric that matters is **contribution margin per
    order after all variable costs and returns** (CM2). Revenue is vanity; a price change
    that raises revenue and lowers CM2 is a loss. Never estimate fees or margins mentally:
    percentage fees compound on price, and that is exactly where humans and LLMs get it wrong.

    ## Intake
    You need: landed unit cost (COGS incl. inbound freight and duties), outbound shipping
    and packaging cost, payment processing (rate + fixed), marketplace/referral and
    fulfilment fees if applicable, return rate and what a return costs, and the current or
    candidate price. Ask at most 3 questions, only if you cannot proceed. Otherwise assume
    and state: payment 2.9% + $0.30; return rate 8% (apparel 20%); return cost = outbound +
    return shipping + 15% restock loss; Amazon referral 15% (verify the category).

    ## Procedure
    1. **Build the order P&L.** Call `ecom_pricing__unit_economics` with every cost line.
       It returns gross margin, contribution margin after fees and returns, markup, break-even
       ROAS and max CPA. Quote the CM2 % and the break-even ROAS in your first sentence.
    2. **Price to target.** If the user has a target margin or is launching, call
       `ecom_pricing__price_for_target_margin`. It solves the fee-inclusive equation
       (price = fixed costs ÷ (1 − target − fee%)), then shows the charm-price options
       ($X.99, $X.95, $X.00, $X9) with the margin each actually delivers. Recommend one.
    3. **Interrogate discounts.** Any promo, coupon, bundle discount or sale goes through
       `ecom_pricing__discount_impact` first. It computes the break-even unit lift
       (discount ÷ (margin − discount)) and profit at realistic lifts. If the break-even
       lift exceeds ~40% and the product is not a traffic driver, say the promo is a losing
       trade and offer a non-price alternative (gift with purchase, free shipping threshold,
       bundle).
    4. **Read price tests** with `ecom_pricing__price_elasticity` (before/after or A/B).
       It computes arc (midpoint) elasticity, revenue and profit deltas, and says which way
       to move. |E| < 1 means demand is inelastic: raise the price. Warn about confounds
       (seasonality, ad spend changes, stockouts) before trusting a single test.
    5. **Position against the market** with `ecom_pricing__competitor_position` when
       competitor prices are known: percentile, index to median, and the premium the brand
       can justify. A premium above the 75th percentile needs a stated reason (reviews,
       warranty, bundle) or it becomes a conversion problem.
    6. **Recommend one price** and a guardrail: the floor price below which CM2 goes under
       the brand's minimum (state the floor), and the promo depth cap.
    7. **Self-check**: fees applied to price not cost; return cost included; ROAS uses
       revenue not profit; margins reported as % of price (margin) not % of cost (markup).

    ## Frameworks
    - **Contribution margin (CM2)** = price − COGS − shipping − packaging − payment fees −
      marketplace fees − expected return cost. Healthy DTC: CM2 ≥ 40% of price before ads.
    - **Break-even ROAS** = price ÷ CM2 (per order). A 40% CM2 means break-even ROAS 2.5×.
      Target ROAS for profit = break-even ÷ (1 − target ad-profit share).
    - **Max CPA** = CM2 per order (first-order break-even); with 60-day repeat contribution,
      max CPA = CM2 × (1 + repeat rate × repeat margin share).
    - **Discount break-even lift** = d ÷ (m − d), d = discount %, m = CM2 % before discount.
      20% off at 45% margin needs +80% units just to stand still.
    - **Markup vs margin**: markup = (price − cost) ÷ cost; margin = (price − cost) ÷ price.
      2× markup = 50% margin. Never mix them in one table.
    - **Charm pricing**: .99 endings lift conversion on value positioning; round numbers
      ($120) signal premium. Left-digit effect: $39.99 vs $40.00 is meaningful, $38.99 vs
      $39.99 is not.
    - **Good-better-best**: anchor tier ≈ 1.6-2.2× base; most buyers land on the middle.
    - Scope note: fees and tax rules change — verify marketplace fee tables for the category
      and treat sales tax/VAT as pass-through unless the price is tax-inclusive.

    ## Output format
    ```
    # Pricing — <product> · recommended price $X
    ## Unit economics at $X (per order)
    | Line | $ | % of price |
    | Price | | 100% |
    | COGS / shipping / packaging / fees / returns | | |
    | Contribution margin (CM2) | | |
    Break-even ROAS: N.N× · Max CPA: $Y · Floor price (min CM2 Z%): $F
    ## Recommendation
    <price, ending, why — 3 lines>
    ## Promo guardrails
    Max discount depth: N% (break-even lift M%) · preferred non-price lever: <…>
    ## Assumptions & formulas
    ```

    ## Anti-patterns
    - Applying percentage fees to cost instead of price (understates fees by the margin).
    - Forgetting returns: an 8% return rate on a $40 item with $12 handling cost is $1+/order.
    - Judging a sale on revenue lift. Show units needed to keep profit flat.
    - Calling a 2× markup "100% margin".
    - Recommending a price with no floor or promo cap — the next sale erases the work.
    - Trusting one week of price-test data with changed ad spend.
    """,
)


def _fees(price: float, payment_fee_pct: float, payment_fee_fixed: float, marketplace_fee_pct: float) -> tuple[float, float]:
    return price * payment_fee_pct + payment_fee_fixed, price * marketplace_fee_pct


@AGENT.tool
def unit_economics(
    price: float,
    cogs: float,
    shipping_cost: float = 0.0,
    packaging_cost: float = 0.0,
    payment_fee_pct: float = 2.9,
    payment_fee_fixed: float = 0.30,
    marketplace_fee_pct: float = 0.0,
    fulfillment_fee: float = 0.0,
    return_rate_pct: float = 0.0,
    return_cost: float = 0.0,
    shipping_charged: float = 0.0,
    min_margin_pct: float = 30.0,
) -> dict:
    """Build the per-order P&L: gross margin, contribution margin after fees and returns, markup, break-even ROAS, max CPA and floor price.

    Args:
        price: Selling price per order/unit (ex tax).
        cogs: Landed cost of goods per unit (incl. inbound freight, duties).
        shipping_cost: Outbound shipping cost you pay per order.
        packaging_cost: Box, filler, inserts per order.
        payment_fee_pct: Payment processor percentage (2.9 for 2.9%).
        payment_fee_fixed: Payment processor fixed fee per transaction (0.30).
        marketplace_fee_pct: Marketplace referral/commission percent of price (Amazon ~15; 0 for own store).
        fulfillment_fee: Per-unit fulfilment fee (FBA pick/pack/ship) if the marketplace ships it.
        return_rate_pct: Percent of orders returned (8 typical, apparel 20-30).
        return_cost: Cost per returned order: return shipping + handling + value lost. Refunded price is handled automatically.
        shipping_charged: Shipping revenue collected from the customer per order (0 if free shipping).
        min_margin_pct: The contribution margin (% of price) below which you refuse to sell; used to compute the floor price.
    """
    p = require_positive("price", price)
    c = require_positive("cogs", cogs, allow_zero=True)
    for name, v in (("shipping_cost", shipping_cost), ("packaging_cost", packaging_cost), ("fulfillment_fee", fulfillment_fee), ("return_cost", return_cost), ("shipping_charged", shipping_charged), ("payment_fee_fixed", payment_fee_fixed)):
        require_positive(name, v, allow_zero=True)
    pf = as_fraction(payment_fee_pct, "payment_fee_pct")
    mf = as_fraction(marketplace_fee_pct, "marketplace_fee_pct")
    rr = as_fraction(return_rate_pct, "return_rate_pct")
    mm = as_fraction(min_margin_pct, "min_margin_pct")
    revenue = p + shipping_charged
    pay_fee, mkt_fee = _fees(revenue, pf, payment_fee_fixed, mf)
    gross_profit = p - c
    variable = shipping_cost + packaging_cost + fulfillment_fee + pay_fee + mkt_fee
    cm1 = revenue - c - variable
    # a returned order loses the contribution it would have earned plus the handling cost;
    # expected cost = return rate × (cm1 + return_cost) (fees are usually not refunded → conservative)
    expected_return_cost = rr * (cm1 + return_cost) if cm1 > 0 else rr * return_cost
    cm2 = cm1 - expected_return_cost
    pct_fees = pf + mf
    fixed_costs = c + shipping_cost + packaging_cost + fulfillment_fee + payment_fee_fixed
    # floor price: (1 - rr) * (P(1 - pct) - fixed) - rr * return_cost = mm * P  (ignoring shipping_charged)
    denom = (1 - rr) * (1 - pct_fees) - mm
    floor = ((1 - rr) * fixed_costs + rr * return_cost) / denom if denom > 0 else None
    breakeven_roas = revenue / cm2 if cm2 > 0 else None
    lines = {
        "price": money(p),
        "shipping_charged": money(shipping_charged),
        "cogs": money(c),
        "shipping_cost": money(shipping_cost),
        "packaging_cost": money(packaging_cost),
        "fulfillment_fee": money(fulfillment_fee),
        "payment_fees": money(pay_fee),
        "marketplace_fees": money(mkt_fee),
        "expected_return_cost": money(expected_return_cost),
    }
    return {
        "lines": lines,
        "gross_profit": money(gross_profit),
        "gross_margin_pct": pct(gross_profit / p),
        "markup_pct": pct(gross_profit / c) if c else None,
        "contribution_before_returns": money(cm1),
        "contribution_margin": money(cm2),
        "contribution_margin_pct": pct(cm2 / p),
        "breakeven_roas": round(breakeven_roas, 2) if breakeven_roas else None,
        "max_cpa_first_order": money(cm2) if cm2 > 0 else 0.0,
        "target_roas_for_20pct_ad_profit": round(breakeven_roas / 0.8, 2) if breakeven_roas else None,
        "floor_price_at_min_margin": money(floor) if floor else None,
        "pct_of_price": {k: pct(v / p) for k, v in lines.items() if k not in ("price", "shipping_charged")},
        "formulas": "CM2 = revenue − COGS − ship − pack − fees − rr·(CM1 + return_cost); ROAS_be = revenue ÷ CM2; markup = GP ÷ COGS",
        "verdict": (
            f"CM2 {cm2:.2f} ({100 * cm2 / p:.1f}% of price), gross margin {100 * gross_profit / p:.0f}%, "
            + (f"break-even ROAS {breakeven_roas:.2f}×, max CPA {cm2:.2f}." if breakeven_roas else "NEGATIVE contribution — this price loses money on every order.")
            + (f" Floor price for {min_margin_pct:.0f}% CM2: {floor:.2f}." if floor else "")
        ),
    }


def _charm_options(raw: float) -> list[dict]:
    opts = []
    seen = set()
    base = math.floor(raw)
    for label, cand in (
        ("x.99", base + 0.99 if raw <= base + 0.99 else base + 1.99),
        ("x.95", base + 0.95 if raw <= base + 0.95 else base + 1.95),
        ("round", float(math.ceil(raw))),
        ("x9 (nine-ending tens)", float((math.ceil(raw / 10) * 10) - 1) if (math.ceil(raw / 10) * 10 - 1) >= raw else float(math.ceil(raw / 10) * 10 + 9)),
    ):
        cand = round(cand, 2)
        if cand in seen:
            continue
        seen.add(cand)
        opts.append({"ending": label, "price": cand})
    return opts


@AGENT.tool
def price_for_target_margin(
    cogs: float,
    target_margin_pct: float,
    shipping_cost: float = 0.0,
    packaging_cost: float = 0.0,
    payment_fee_pct: float = 2.9,
    payment_fee_fixed: float = 0.30,
    marketplace_fee_pct: float = 0.0,
    fulfillment_fee: float = 0.0,
    return_rate_pct: float = 0.0,
    return_cost: float = 0.0,
    margin_basis: str = "contribution",
) -> dict:
    """Solve for the price that delivers a target margin after percentage fees and returns, then show charm-price options with their real margins.

    Args:
        cogs: Landed unit cost.
        target_margin_pct: Desired margin as percent of price (60 for 60%).
        shipping_cost: Outbound shipping cost per order you absorb.
        packaging_cost: Packaging per order.
        payment_fee_pct: Payment processor percent (2.9).
        payment_fee_fixed: Payment fixed fee per order (0.30).
        marketplace_fee_pct: Marketplace referral percent of price (Amazon ~15).
        fulfillment_fee: Per-unit fulfilment fee if applicable.
        return_rate_pct: Percent of orders returned.
        return_cost: Cost per returned order beyond the refund.
        margin_basis: "contribution" (target applies to margin after all variable costs and returns) or "gross" (target applies to price − COGS only).
    """
    c = require_positive("cogs", cogs)
    t = as_fraction(target_margin_pct, "target_margin_pct")
    if margin_basis not in ("contribution", "gross"):
        raise ToolError("margin_basis must be 'contribution' or 'gross'.")
    pf = as_fraction(payment_fee_pct, "payment_fee_pct")
    mf = as_fraction(marketplace_fee_pct, "marketplace_fee_pct")
    rr = as_fraction(return_rate_pct, "return_rate_pct")
    if margin_basis == "gross":
        raw = c / (1 - t)
    else:
        fixed = c + shipping_cost + packaging_cost + fulfillment_fee + payment_fee_fixed
        denom = (1 - rr) * (1 - pf - mf) - t
        if denom <= 0:
            raise ToolError(f"Target margin {target_margin_pct}% is impossible: fees + returns already consume {100 * (1 - (1 - rr) * (1 - pf - mf)):.1f}% of price.")
        raw = ((1 - rr) * fixed + rr * return_cost) / denom
    options = []
    for opt in _charm_options(raw):
        ue = unit_economics(
            price=opt["price"], cogs=c, shipping_cost=shipping_cost, packaging_cost=packaging_cost, payment_fee_pct=payment_fee_pct,
            payment_fee_fixed=payment_fee_fixed, marketplace_fee_pct=marketplace_fee_pct, fulfillment_fee=fulfillment_fee,
            return_rate_pct=return_rate_pct, return_cost=return_cost,
        )
        options.append({**opt, "contribution_margin_pct": ue["contribution_margin_pct"], "gross_margin_pct": ue["gross_margin_pct"], "breakeven_roas": ue["breakeven_roas"]})
    best = min(options, key=lambda o: o["price"])
    return {
        "exact_price": money(raw),
        "target_margin_pct": round(t * 100, 2),
        "margin_basis": margin_basis,
        "charm_options": options,
        "recommended": best,
        "formula": "P = ((1−rr)·fixed + rr·return_cost) ÷ ((1−rr)(1 − fee%) − target)" if margin_basis == "contribution" else "P = COGS ÷ (1 − target)",
        "verdict": f"Exact price {raw:.2f}; lowest charm price that still clears the target: {best['price']:.2f} ({best['ending']}) at {best['contribution_margin_pct']}% CM2.",
    }


@AGENT.tool
def discount_impact(price: float, unit_variable_cost: float, discount_pct: float, baseline_units: float, expected_lift_pct: float = 0.0, promo_fixed_cost: float = 0.0) -> dict:
    """Compute the unit lift a discount needs to break even on profit, and profit at expected/realistic lifts.

    Args:
        price: Regular selling price.
        unit_variable_cost: All variable cost per unit (COGS + shipping + packaging + fixed fees). Percentage fees on price are handled via price change if you include them here as at-full-price amounts.
        discount_pct: Discount depth as percent of price (20 for 20% off).
        baseline_units: Units you would sell at full price over the promo period.
        expected_lift_pct: Your expected unit lift from the promo (percent), 0 to just see break-even.
        promo_fixed_cost: Fixed promo cost (ads, creative, email) to recover.
    """
    p = require_positive("price", price)
    v = require_positive("unit_variable_cost", unit_variable_cost, allow_zero=True)
    d = as_fraction(discount_pct, "discount_pct")
    b = require_positive("baseline_units", baseline_units)
    if d >= 1:
        raise ToolError("discount_pct must be below 100.")
    margin = (p - v) / p
    new_price = p * (1 - d)
    new_unit_profit = new_price - v
    baseline_profit = b * (p - v) - 0
    if new_unit_profit <= 0:
        be_lift = None
    else:
        be_units = (baseline_profit + promo_fixed_cost) / new_unit_profit
        be_lift = be_units / b - 1
    scenarios = []
    for lift in sorted({0.0, 0.25, 0.5, 1.0, 1.5, as_fraction(expected_lift_pct, "expected_lift_pct") if expected_lift_pct else 0.0}):
        units = b * (1 + lift)
        profit = units * new_unit_profit - promo_fixed_cost
        scenarios.append({"lift_pct": round(lift * 100), "units": round(units), "revenue": money(units * new_price), "profit": money(profit), "profit_vs_baseline": money(profit - baseline_profit)})
    expected = next((s for s in scenarios if s["lift_pct"] == round(as_fraction(expected_lift_pct, "x") * 100)), None) if expected_lift_pct else None
    verdict = (
        f"{discount_pct:.0f}% off cuts unit profit from {p - v:.2f} to {new_unit_profit:.2f} ({100 * margin:.0f}% → {100 * new_unit_profit / new_price:.0f}% margin). "
        + (f"Break-even lift: +{100 * be_lift:.0f}% units ({math.ceil(b * (1 + be_lift)):,} vs {b:,.0f})." if be_lift is not None else "Unit profit is ≤ 0 at this depth — every extra unit loses money.")
        + (f" At your expected +{expected_lift_pct:.0f}%: {expected['profit_vs_baseline']:+,.0f} vs baseline." if expected else "")
    )
    return {
        "margin_pct_before": pct(margin),
        "margin_pct_after": pct(new_unit_profit / new_price) if new_price else None,
        "unit_profit_before": money(p - v),
        "unit_profit_after": money(new_unit_profit),
        "breakeven_lift_pct": round(100 * be_lift, 1) if be_lift is not None else None,
        "breakeven_units": math.ceil(b * (1 + be_lift)) if be_lift is not None else None,
        "baseline_profit": money(baseline_profit),
        "scenarios": scenarios,
        "expected_scenario": expected,
        "rule_of_thumb": "break-even lift ≈ d ÷ (m − d) with m = margin % and d = discount %",
        "recommendation": (
            "Losing trade unless it drives new customers with strong repeat — prefer bundle / GWP / threshold."
            if be_lift is None or be_lift > 0.6
            else ("Viable only with a proven lift driver (email + ads); cap depth." if be_lift > 0.3 else "Acceptable depth; likely profitable if the promo is promoted.")
        ),
        "verdict": verdict,
    }


@AGENT.tool
def price_elasticity(price_a: float, units_a: float, price_b: float, units_b: float, unit_variable_cost: float, periods_equal: bool = True) -> dict:
    """Arc (midpoint) price elasticity from a before/after or A/B price test, with revenue and profit deltas and the direction to move.

    Args:
        price_a: Price in the control / before period.
        units_a: Units sold at price_a.
        price_b: Price in the test / after period.
        units_b: Units sold at price_b (same length period, or per-visitor normalised).
        unit_variable_cost: Variable cost per unit (to compute profit, not just revenue).
        periods_equal: False if the two periods differ in length or traffic — results then need normalising first.
    """
    pa, pb = require_positive("price_a", price_a), require_positive("price_b", price_b)
    ua, ub = require_positive("units_a", units_a, allow_zero=True), require_positive("units_b", units_b, allow_zero=True)
    v = require_positive("unit_variable_cost", unit_variable_cost, allow_zero=True)
    if pa == pb:
        raise ToolError("Prices are identical — no price change to measure.")
    if ua + ub == 0:
        raise ToolError("No units sold in either period.")
    dq = (ub - ua) / ((ua + ub) / 2)
    dp = (pb - pa) / ((pa + pb) / 2)
    e = dq / dp
    rev_a, rev_b = pa * ua, pb * ub
    prof_a, prof_b = (pa - v) * ua, (pb - v) * ub
    # optimal markup rule (Lerner): (P − MC)/P = −1/E  →  P* = MC · E / (1 + E) for E < −1
    p_opt = v * e / (1 + e) if e < -1 and v > 0 else None
    if abs(e) < 1:
        direction = "inelastic — demand barely moves with price: raise price (test +5-10%)."
    elif abs(e) < 1.5:
        direction = "moderately elastic — near the revenue-max point; optimise on profit, not revenue."
    else:
        direction = "elastic — volume is price-sensitive: lowering price may grow revenue, check profit."
    return {
        "arc_elasticity": round(e, 2),
        "pct_change_price": round(100 * (pb - pa) / pa, 1),
        "pct_change_units": round(100 * (ub - ua) / ua, 1) if ua else None,
        "revenue_a": money(rev_a),
        "revenue_b": money(rev_b),
        "revenue_change_pct": pct((rev_b - rev_a) / rev_a) if rev_a else None,
        "profit_a": money(prof_a),
        "profit_b": money(prof_b),
        "profit_change": money(prof_b - prof_a),
        "profit_change_pct": pct((prof_b - prof_a) / prof_a) if prof_a else None,
        "lerner_optimal_price": money(p_opt) if p_opt else None,
        "direction": direction,
        "caveats": [
            "one test ≠ elasticity curve: confounds include seasonality, ad spend, stockouts, promo overlap",
        ] + ([] if periods_equal else ["periods not equal — normalise units per visitor or per day before trusting this"]),
        "verdict": f"E = {e:.2f} ({direction}) Price {pa:.2f}→{pb:.2f}: revenue {100 * (rev_b - rev_a) / rev_a:+.1f}%, profit {prof_b - prof_a:+,.0f} ({100 * (prof_b - prof_a) / prof_a:+.1f}%)." if rev_a and prof_a else f"E = {e:.2f}.",
    }


@AGENT.tool
def competitor_position(my_price: float, competitor_prices: list[float], unit_variable_cost: float = 0.0, my_rating: float = 0.0, market_rating: float = 0.0) -> dict:
    """Place your price in the competitive set: percentile, index to median, gap to nearest rivals, and the justified premium band.

    Args:
        my_price: Your current or candidate price.
        competitor_prices: Prices of comparable competitor products (3+ recommended).
        unit_variable_cost: Your variable cost per unit — enables margin at the competitor median.
        my_rating: Your average review rating (0-5), optional; premium justification input.
        market_rating: Average rating of the competitive set (0-5), optional.
    """
    p = require_positive("my_price", my_price)
    comps = [float(x) for x in competitor_prices if x is not None]
    if len(comps) < 2:
        raise ToolError("Need at least 2 competitor prices.")
    if len(comps) > 500:
        raise ToolError("Too many competitor prices (500 max).")
    if any(x <= 0 for x in comps):
        raise ToolError("Competitor prices must be > 0.")
    med = median(comps)
    p25, p75 = percentile(comps, 25), percentile(comps, 75)
    below = sum(1 for x in comps if x < p)
    percentile_rank = 100 * below / len(comps)
    index = p / med * 100
    nearest_below = max((x for x in comps if x <= p), default=None)
    nearest_above = min((x for x in comps if x >= p), default=None)
    band = "premium" if p > p75 else ("value" if p < p25 else "mid-market")
    rating_gap = (my_rating - market_rating) if my_rating and market_rating else None
    justified_premium_pct = None
    if rating_gap is not None:
        # heuristic: each +0.1 star above market supports ~2-3% premium; cap ±15%
        justified_premium_pct = max(-15.0, min(15.0, round(rating_gap * 25, 1)))
    out = {
        "median_competitor_price": money(med),
        "p25": money(p25),
        "p75": money(p75),
        "min": money(min(comps)),
        "max": money(max(comps)),
        "your_percentile": round(percentile_rank, 1),
        "index_to_median": round(index, 1),
        "premium_vs_median_pct": round(index - 100, 1),
        "nearest_below": money(nearest_below) if nearest_below is not None else None,
        "nearest_above": money(nearest_above) if nearest_above is not None else None,
        "band": band,
        "justified_premium_pct_from_ratings": justified_premium_pct,
        "margin_pct_if_priced_at_median": pct((med - unit_variable_cost) / med) if unit_variable_cost else None,
        "verdict": f"{p:.2f} is at the {percentile_rank:.0f}th percentile ({band}), {index - 100:+.0f}% vs median {med:.2f}; P25-P75 band {p25:.2f}-{p75:.2f}.",
    }
    if justified_premium_pct is not None and index - 100 > justified_premium_pct + 5:
        out["warning"] = f"Premium ({index - 100:+.0f}%) exceeds what your rating gap supports (~{justified_premium_pct:+.0f}%) — expect conversion drag unless differentiated."
    return out
