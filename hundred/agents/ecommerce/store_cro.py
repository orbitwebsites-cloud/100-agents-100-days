"""Store CRO — finds the biggest funnel leak, sizes the fix in orders, and proves tests with real statistics."""

from __future__ import annotations

import math

from ...core import Agent, ToolError
from ._common import mean, median, money, norm_cdf, norm_ppf, pct, percentile, require_positive

AGENT = Agent(
    slug="store-cro",
    name="Store CRO",
    category="ecommerce",
    tagline="Find the funnel step that is costing you the most orders, size the fix, and run A/B tests that actually prove it.",
    description=(
        "Runs a conversion-rate-optimisation audit the way a senior CRO consultant does: reconstructs the "
        "session → product → cart → checkout → order funnel, benchmarks every step, ranks leaks by orders "
        "lost, models AOV levers (free-shipping threshold, bundles, upsells) in contribution dollars, "
        "prioritises the test backlog with ICE, and evaluates A/B tests with a proper two-proportion "
        "z-test, confidence intervals and sample-size planning — so you stop shipping 'wins' that are noise."
    ),
    triggers=[
        "why is my store conversion rate low",
        "analyze my ecommerce funnel / where are we losing customers",
        "how do I increase average order value",
        "what free shipping threshold should I set",
        "is my A/B test result significant / how long should I run the test",
        "prioritize my CRO test ideas",
        "audit my product page / checkout for conversion",
    ],
    examples=[
        "Last month: 84,000 sessions, 41,000 product views, 4,300 add to carts, 2,100 checkouts, 1,150 orders, $92k revenue. Where's the leak?",
        "Our AOV is $68 and shipping costs us $7.40. What free-shipping threshold should we set? Here are 500 order values.",
        "Variant B: 412 orders from 19,800 visitors vs control 371 from 19,650. Is it a win?",
    ],
    connectors=["Shopify", "Google Analytics", "Google Sheets", "Klaviyo", "Hotjar"],
    playbook="""
    ## Standard
    You are a senior CRO lead who has run hundreds of tests on stores from $1M to $100M. The
    one metric that matters is **contribution per session** (revenue per session × margin),
    not conversion rate alone — a "win" that lifts CVR by cutting AOV is not a win. Excellent
    work names one primary leak, sizes it in orders and dollars, proposes a specific fix with
    a hypothesis, and specifies how the test will be judged before it runs.

    ## Intake
    You need the funnel counts for one period (sessions, product views, add-to-carts,
    checkouts started, orders, revenue), ideally split by device. For AOV work, order values
    or at least AOV + margin + shipping cost. Ask at most 3 questions and only if the numbers
    are missing entirely; otherwise assume and state (e.g. "assuming 60% mobile, 45% gross
    margin").

    ## Procedure
    1. **Reconstruct the funnel.** Call `store_cro__funnel_analysis` with the counts. It
       returns each step's conversion rate, the gap to benchmark, the orders you would gain
       if that single step reached benchmark, and ranks the leaks. Lead with the #1 leak.
       If you have mobile vs desktop, run it twice — the leak is usually device-specific.
    2. **Diagnose the leak** with the matching checklist (Frameworks below). Pick the 2-3
       causes most likely for this store and turn each into a hypothesis: "Because [data],
       we believe [change] for [segment] will [metric] by [x%]."
    3. **Model AOV levers** when the leak is small or AOV < category norm. Call
       `store_cro__free_shipping_threshold` with order values (or AOV) and shipping cost —
       it finds the threshold that maximises net contribution, not just "AOV × 1.2". Call
       `store_cro__aov_levers` to compare bundles, upsells, gift-with-purchase and threshold
       in contribution dollars per month.
    4. **Prioritise the backlog** with `store_cro__prioritize_tests` (ICE with expected
       order gain). Ship no-brainers (broken things, trust signals) without a test; test
       everything that touches price, layout or copy on the money pages.
    5. **Plan the test** with `store_cro__ab_test` in planning mode (baseline rate, minimum
       detectable effect, daily traffic) to get sample size and duration. Run for whole
       weeks (min 2, max 4) and never stop early on a peek.
    6. **Read the result** with `store_cro__ab_test` in analysis mode, always passing the
       planned `min_detectable_effect_pct`, `daily_visitors` and `days_run` so it can check
       the pre-planned sample. Follow its `decision` field: declare a win only at p < 0.05
       with the confidence interval excluding zero, the planned sample reached and full
       weeks completed; report relative lift with its interval, not a point estimate.
    7. **Self-check**: the recommendation moves contribution per session, not just CVR; each
       hypothesis names a segment and a metric; sample size is stated before any test.

    ## Frameworks
    - **Typical step benchmarks (DTC, blended device; override with your vertical):** sessions
      → product view 40-60%; sessions → add-to-cart 4-8%; cart → checkout 45-60%; checkout
      → order 50-65%; overall CVR 1.5-3% (mobile ~half of desktop). Cart + checkout
      abandonment ~70% (Baymard, long-run average).
    - **Leak playbooks.** Low product-view rate: collection page merchandising, search, PLP
      images, load time > 3s. Low ATC: price anchoring, missing size/fit info, review count
      < 20, no urgency, weak hero image, unclear variant selection. Low cart→checkout: shipping
      cost surprise (the #1 abandonment reason), no express pay, cart drawer without totals.
      Low checkout completion: forced account creation, > 7 form fields, missing wallets
      (Shop Pay/Apple Pay), unexpected fees, no trust badges near CTA, error handling.
    - **AOV levers by typical lift:** free-shipping threshold set at AOV × 1.15-1.30 (+5-10%
      AOV), bundles (+10-20% on bundled SKUs), post-purchase upsell (5-15% take, no CVR
      risk), in-cart cross-sell (3-8% take), tiered gifts.
    - **ICE:** Impact × Confidence × Ease, each 1-10; anything with confidence ≤ 3 goes to
      research (session recordings, polls) before testing.
    - **Statistics:** two-proportion z-test, two-sided α = 0.05, power 0.8; MDE for most
      stores is 5-10% relative; below 3% relative is usually untestable in a month.

    ## Output format
    ```
    # CRO audit — <store> · <period> · CVR X.X% (benchmark Y-Z%)
    ## Funnel
    | Step | Rate | Benchmark | Orders lost/month | Rank |
    ## #1 leak: <step> — ~N orders/month ($X)
    Likely causes (ranked): 1… 2… 3…
    Hypothesis: Because…, we believe…, will…
    Fix now (no test): …
    Test: <variant> · primary metric · MDE · sample size/duration
    ## AOV plan
    Threshold $T (net +$/month) · bundle/upsell picks
    ## Backlog (ICE)
    | Idea | I | C | E | Score | Expected orders |
    ```

    ## Anti-patterns
    - Reporting conversion rate without segmenting by device or new vs returning.
    - Calling a test at 90% confidence or after 4 days because it "looks done".
    - Setting a free-shipping threshold far above AOV so nobody reaches it, or at AOV so it
      only subsidises orders that already qualified.
    - Recommending 15 changes at once. One leak, one fix, one test.
    - Generic advice ("improve your images"). Name the page, the element and the change.
    - Optimising CVR while AOV falls — always report contribution per session.
    """,
)

DEFAULT_BENCHMARKS = {  # midpoint of the typical ranges above; caller may override
    "product_view_rate": 0.50,
    "add_to_cart_rate": 0.06,
    "cart_to_checkout_rate": 0.52,
    "checkout_completion_rate": 0.58,
    "overall_conversion_rate": 0.022,
}


@AGENT.tool
def funnel_analysis(sessions: int, product_views: int, add_to_carts: int, checkouts: int, orders: int, revenue: float = 0.0, gross_margin_pct: float = 45.0, benchmarks: dict | None = None) -> dict:
    """Compute every funnel step rate, compare to benchmarks, and rank leaks by orders (and dollars) lost per period.

    Args:
        sessions: Sessions (visits) in the period.
        product_views: Sessions that viewed at least one product page.
        add_to_carts: Sessions that added to cart.
        checkouts: Sessions that started checkout.
        orders: Orders placed.
        revenue: Revenue in the period (optional; enables AOV, revenue per session and $ upside).
        gross_margin_pct: Gross margin percent to convert lost orders into contribution.
        benchmarks: Optional overrides as fractions: {"product_view_rate", "add_to_cart_rate", "cart_to_checkout_rate", "checkout_completion_rate", "overall_conversion_rate"}.
    """
    counts = [("sessions", sessions), ("product_views", product_views), ("add_to_carts", add_to_carts), ("checkouts", checkouts), ("orders", orders)]
    for name, v in counts:
        if v is None or v < 0:
            raise ToolError(f"{name} must be >= 0.")
    if sessions <= 0:
        raise ToolError("sessions must be > 0.")
    for (a, va), (b, vb) in zip(counts, counts[1:]):
        if vb > va:
            raise ToolError(f"{b} ({vb}) cannot exceed {a} ({va}) — the funnel must narrow.")
    bm = dict(DEFAULT_BENCHMARKS)
    for k, v in (benchmarks or {}).items():
        if k in bm:
            bm[k] = v / 100 if v > 1 else v
    steps = [
        ("product_view_rate", "sessions → product view", sessions, product_views),
        ("add_to_cart_rate", "sessions → add to cart", sessions, add_to_carts),
        ("cart_to_checkout_rate", "cart → checkout", add_to_carts, checkouts),
        ("checkout_completion_rate", "checkout → order", checkouts, orders),
    ]
    aov = revenue / orders if orders and revenue else None
    margin = gross_margin_pct / 100 if gross_margin_pct > 1 else gross_margin_pct
    rows = []
    for key, label, denom, num in steps:
        rate = num / denom if denom else 0.0
        target = bm[key]
        # orders gained if this step alone reached benchmark, downstream rates unchanged
        if key == "product_view_rate":
            downstream = (orders / product_views) if product_views else 0
            gained = max(0.0, target * sessions - product_views) * downstream
        elif key == "add_to_cart_rate":
            downstream = (orders / add_to_carts) if add_to_carts else 0
            gained = max(0.0, target * sessions - add_to_carts) * downstream
        elif key == "cart_to_checkout_rate":
            downstream = (orders / checkouts) if checkouts else 0
            gained = max(0.0, target * add_to_carts - checkouts) * downstream
        else:
            gained = max(0.0, target * checkouts - orders)
        rows.append(
            {
                "step": label,
                "rate_pct": pct(rate, 2),
                "benchmark_pct": pct(target, 2),
                "gap_pct_points": round(100 * (rate - target), 2),
                "index_vs_benchmark": round(100 * rate / target, 0) if target else None,
                "orders_gained_at_benchmark": round(gained),
                "revenue_gained_at_benchmark": money(gained * aov) if aov else None,
                "contribution_gained_at_benchmark": money(gained * aov * margin) if aov else None,
            }
        )
    ranked = sorted(rows, key=lambda r: -r["orders_gained_at_benchmark"])
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
    cvr = orders / sessions
    abandonment = 1 - (orders / add_to_carts) if add_to_carts else None
    top = ranked[0]
    return {
        "overall_conversion_pct": pct(cvr, 2),
        "overall_benchmark_pct": pct(bm["overall_conversion_rate"], 2),
        "cart_abandonment_pct": pct(abandonment) if abandonment is not None else None,
        "aov": money(aov) if aov else None,
        "revenue_per_session": money(revenue / sessions) if revenue else None,
        "contribution_per_session": money(revenue / sessions * margin) if revenue else None,
        "steps": rows,
        "leaks_ranked": [{"rank": r["rank"], "step": r["step"], "orders_gained_at_benchmark": r["orders_gained_at_benchmark"]} for r in ranked],
        "verdict": (
            f"CVR {100 * cvr:.2f}% vs benchmark {100 * bm['overall_conversion_rate']:.1f}%. #1 leak: {top['step']} at {top['rate_pct']}% "
            f"(benchmark {top['benchmark_pct']}%) — worth ~{top['orders_gained_at_benchmark']} orders"
            + (f" / {top['revenue_gained_at_benchmark']:,.0f} revenue" if top["revenue_gained_at_benchmark"] else "")
            + " per period if brought to benchmark."
            if top["orders_gained_at_benchmark"] > 0
            else f"CVR {100 * cvr:.2f}% vs benchmark {100 * bm['overall_conversion_rate']:.1f}%. Every step is at or above benchmark — no leak to fix here; "
            "compare segments (device, new vs returning, traffic source) or work on AOV."
        ),
    }


@AGENT.tool
def ab_test(
    control_visitors: int = 0,
    control_conversions: int = 0,
    variant_visitors: int = 0,
    variant_conversions: int = 0,
    baseline_rate_pct: float = 0.0,
    min_detectable_effect_pct: float = 10.0,
    daily_visitors: int = 0,
    confidence_pct: float = 95.0,
    power_pct: float = 80.0,
    days_run: int = 0,
) -> dict:
    """Two-proportion z-test for a finished A/B test (p-value, CI, lift) or sample-size and duration planning for a new one.

    Analysis mode: pass the four visitor/conversion counts. Planning mode: pass baseline_rate_pct,
    min_detectable_effect_pct (relative) and daily_visitors. Both if you want the required sample
    alongside the current read.

    Args:
        control_visitors: Visitors (or sessions) in the control.
        control_conversions: Conversions in the control.
        variant_visitors: Visitors in the variant.
        variant_conversions: Conversions in the variant.
        baseline_rate_pct: Planning: current conversion rate in percent (2.1 for 2.1%). Defaults to control rate if counts given.
        min_detectable_effect_pct: Planning: smallest relative lift worth detecting, in percent (10 = +10% relative).
        daily_visitors: Planning: total daily visitors that will be split across the two arms.
        confidence_pct: Confidence level (95 → α = 0.05, two-sided).
        power_pct: Statistical power (80 typical).
        days_run: Days the test has been running (analysis). With the planning inputs it checks the pre-planned sample and full weeks before a win can be called.
    """
    if not 50 < confidence_pct < 100 or not 50 <= power_pct < 100:
        raise ToolError("confidence_pct must be in (50, 100) and power_pct in [50, 100).")
    alpha = 1 - confidence_pct / 100
    z_alpha = norm_ppf(1 - alpha / 2)
    z_beta = norm_ppf(power_pct / 100)
    out: dict = {"mode": []}
    has_counts = control_visitors > 0 and variant_visitors > 0
    if has_counts:
        if control_conversions > control_visitors or variant_conversions > variant_visitors or min(control_conversions, variant_conversions) < 0:
            raise ToolError("Conversions must be between 0 and visitors for each arm.")
        p1 = control_conversions / control_visitors
        p2 = variant_conversions / variant_visitors
        pooled = (control_conversions + variant_conversions) / (control_visitors + variant_visitors)
        se_pooled = math.sqrt(pooled * (1 - pooled) * (1 / control_visitors + 1 / variant_visitors)) if 0 < pooled < 1 else 0.0
        z = (p2 - p1) / se_pooled if se_pooled else 0.0
        p_value = 2 * (1 - norm_cdf(abs(z)))
        se_diff = math.sqrt(p1 * (1 - p1) / control_visitors + p2 * (1 - p2) / variant_visitors)
        ci_lo, ci_hi = (p2 - p1) - z_alpha * se_diff, (p2 - p1) + z_alpha * se_diff
        lift = (p2 - p1) / p1 if p1 else None
        significant = p_value < alpha
        small = min(control_conversions, variant_conversions) < 100
        out["mode"].append("analysis")
        out.update(
            {
                "control_rate_pct": pct(p1, 3),
                "variant_rate_pct": pct(p2, 3),
                "relative_lift_pct": round(100 * lift, 2) if lift is not None else None,
                "absolute_diff_pct_points": round(100 * (p2 - p1), 3),
                "z": round(z, 3),
                "p_value": round(p_value, 4),
                "ci_diff_pct_points": [round(100 * ci_lo, 3), round(100 * ci_hi, 3)],
                "ci_relative_lift_pct": [round(100 * ci_lo / p1, 1), round(100 * ci_hi / p1, 1)] if p1 else None,
                "significant": significant,
                "conversions_per_arm_ok": not small,
                "verdict": (
                    (f"{'WIN' if p2 > p1 else 'LOSS'}: {100 * lift:+.1f}% relative (CI {100 * ci_lo / p1:+.1f}% to {100 * ci_hi / p1:+.1f}%), p = {p_value:.4f}."
                     if significant and p1 else f"Not significant: p = {p_value:.3f}, lift {100 * (lift or 0):+.1f}% (CI {100 * ci_lo / (p1 or 1):+.1f}% to {100 * ci_hi / (p1 or 1):+.1f}%). Keep running or accept no difference.")
                    + (" Fewer than 100 conversions per arm — treat as directional only." if small else "")
                ),
            }
        )
        if not baseline_rate_pct:
            baseline_rate_pct = 100 * p1
    if baseline_rate_pct > 0 and min_detectable_effect_pct > 0:
        p1 = baseline_rate_pct / 100
        if not 0 < p1 < 1:
            raise ToolError("baseline_rate_pct must be between 0 and 100.")
        p2 = p1 * (1 + min_detectable_effect_pct / 100)
        if p2 >= 1:
            raise ToolError("MDE pushes the rate above 100% — check inputs.")
        pbar = (p1 + p2) / 2
        n = ((z_alpha * math.sqrt(2 * pbar * (1 - pbar)) + z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2) / ((p2 - p1) ** 2)
        n = math.ceil(n)
        out["mode"].append("planning")
        out.update({"sample_size_per_arm": n, "sample_size_total": 2 * n, "mde_relative_pct": min_detectable_effect_pct, "baseline_rate_pct": round(baseline_rate_pct, 3)})
        if daily_visitors > 0:
            days = math.ceil(2 * n / daily_visitors)
            weeks = max(1, math.ceil(days / 7))
            out["days_required"] = days
            out["run_for_full_weeks"] = min(weeks, 8) if days <= 56 else None
            out["planning_verdict"] = (
                f"Need {n:,} visitors per arm ({2 * n:,} total) to detect +{min_detectable_effect_pct:g}% relative at {confidence_pct:g}% confidence / {power_pct:g}% power: ~{days} days"
                + (f" → run {weeks} full week(s)." if days <= 56 else " — too long; raise the MDE or test a bigger change.")
            )
        else:
            out["planning_verdict"] = f"Need {n:,} visitors per arm ({2 * n:,} total) for +{min_detectable_effect_pct:g}% relative MDE."
        if has_counts:
            out["progress_pct_of_required_sample"] = round(100 * min(control_visitors, variant_visitors) / n, 1)
    if has_counts:
        # a p-value is only valid at the pre-planned sample size; an early "win" is a peek, not a result
        blockers = []
        prog = out.get("progress_pct_of_required_sample")
        if prog is not None and prog < 100:
            blockers.append(f"only {prog:g}% of the planned {out['sample_size_per_arm']:,} visitors per arm")
        if days_run and days_run < 14:
            blockers.append(f"{days_run} days run (< 2 full weeks)")
        elif days_run and days_run % 7:
            blockers.append(f"{days_run} days is not whole weeks (day-of-week mix is unbalanced)")
        if out["significant"] and not blockers:
            out["decision"] = "call it: " + ("ship the variant" if out["variant_rate_pct"] > out["control_rate_pct"] else "keep control")
        elif out["significant"]:
            out["decision"] = "NOT YET — significant at this peek but " + "; ".join(blockers) + ". Keep running to the planned sample; stopping on a peek inflates false positives."
            out["verdict"] = "PROVISIONAL (do not call): " + out["verdict"]
        elif blockers:
            out["decision"] = "keep running — " + "; ".join(blockers)
        else:
            out["decision"] = "no detectable difference at the planned sample — keep control or test a bolder change"
    if not out["mode"]:
        raise ToolError("Pass either the four test counts (analysis) or baseline_rate_pct + min_detectable_effect_pct (planning).")
    out["peeking_warning"] = "Decide the sample size before starting; checking daily and stopping at the first p < 0.05 inflates false positives several-fold."
    return out


@AGENT.tool
def free_shipping_threshold(
    shipping_cost: float,
    gross_margin_pct: float,
    order_values: list[float] | None = None,
    aov: float = 0.0,
    currently_free: bool = False,
    nudge_uptake_pct: float = 25.0,
    conversion_lift_pct: float = 10.0,
    candidate_thresholds: list[float] | None = None,
) -> dict:
    """Find the free-shipping threshold that maximises net contribution using your actual order-value distribution.

    For each candidate threshold it estimates: orders already above it (subsidy cost), orders in the
    nudge band (threshold − 25% to threshold) that could be pushed up, extra contribution from those
    upgrades, extra orders from the conversion lift free shipping buys on qualifying baskets, the net
    effect per 100 orders, and the break-even conversion lift if you distrust the assumption.

    Args:
        shipping_cost: Your average cost to ship an order.
        gross_margin_pct: Gross margin percent on merchandise (to value the extra items added).
        order_values: List of recent order values (200+ recommended). If omitted, aov is used with a lognormal-ish spread.
        aov: Average order value, used only when order_values is not supplied.
        currently_free: True if you already offer free shipping on all orders (threshold then removes subsidy on small orders).
        nudge_uptake_pct: Percent of orders in the nudge band assumed to add items to reach the threshold (20-30 typical; test to confirm).
        conversion_lift_pct: Assumed relative lift in orders among baskets that qualify for free shipping (unexpected shipping cost is the #1 abandonment reason; 5-15 typical, 0 to see pure subsidy maths).
        candidate_thresholds: Optional thresholds to evaluate; defaults to AOV × 1.0-1.5 rounded to 5.
    """
    sc = require_positive("shipping_cost", shipping_cost, allow_zero=True)
    margin = gross_margin_pct / 100 if gross_margin_pct > 1 else gross_margin_pct
    if not 0 < margin < 1:
        raise ToolError("gross_margin_pct must be between 0 and 100.")
    uptake = nudge_uptake_pct / 100 if nudge_uptake_pct > 1 else nudge_uptake_pct
    lift = conversion_lift_pct / 100 if conversion_lift_pct > 1 else conversion_lift_pct
    if lift < 0 or lift > 1:
        raise ToolError("conversion_lift_pct must be between 0 and 100.")
    vals = [float(v) for v in (order_values or []) if v is not None and v > 0]
    if len(vals) > 20000:
        raise ToolError("Too many order values (20,000 max).")
    synthetic = False
    if len(vals) < 20:
        if aov <= 0:
            raise ToolError("Provide at least 20 order_values or a positive aov.")
        # synthetic right-skewed distribution around AOV (deciles of a lognormal with CV≈0.6)
        synthetic = True
        sigma = 0.55
        mu = math.log(aov) - sigma**2 / 2
        vals = [math.exp(mu + sigma * norm_ppf((i + 0.5) / 200)) for i in range(200)]
    n = len(vals)
    avg = mean(vals)
    med = median(vals)
    if candidate_thresholds:
        cands = sorted({float(t) for t in candidate_thresholds if t > 0})[:20]
    else:
        cands = sorted({float(round(avg * m / 5) * 5) for m in (1.0, 1.1, 1.2, 1.3, 1.4, 1.5)})
    rows = []
    for t in cands:
        above = [v for v in vals if v >= t]
        band = [v for v in vals if 0.75 * t <= v < t]
        share_above = len(above) / n
        share_band = len(band) / n
        upgrades = share_band * uptake
        extra_rev = sum(t - v for v in band) / n * uptake if band else 0.0  # per order, averaged across all orders
        # top-ups are usually a bit above the line; assume 5% overshoot
        extra_rev *= 1.05
        extra_contrib = extra_rev * margin
        # subsidy: orders that become free that were not free before (above threshold + upgrades)
        qualifying = share_above + upgrades
        if currently_free:
            subsidy_change = -sc * (1 - qualifying)  # negative = saving: small orders now pay shipping
            lift_orders = 0.0  # already free: no new conversion lift
        else:
            subsidy_change = sc * qualifying
            lift_orders = qualifying * lift  # extra orders per existing order
        avg_above = mean(above) if above else t
        contrib_per_lift_order = avg_above * margin - sc
        lift_contrib = lift_orders * contrib_per_lift_order
        net = extra_contrib + lift_contrib - subsidy_change
        be_lift = (subsidy_change - extra_contrib) / (qualifying * contrib_per_lift_order) if (not currently_free and qualifying and contrib_per_lift_order > 0) else None
        rows.append(
            {
                "threshold": t,
                "threshold_vs_aov": round(t / avg, 2),
                "orders_already_above_pct": pct(share_above),
                "orders_in_nudge_band_pct": pct(share_band),
                "expected_upgrades_per_100_orders": round(100 * upgrades, 1),
                "extra_revenue_per_100_orders": money(100 * extra_rev),
                "extra_contribution_per_100_orders": money(100 * extra_contrib),
                "shipping_subsidy_change_per_100_orders": money(100 * subsidy_change),
                "extra_orders_from_conversion_lift_per_100": round(100 * lift_orders, 1),
                "contribution_from_lift_per_100_orders": money(100 * lift_contrib),
                "net_contribution_per_100_orders": money(100 * net),
                "breakeven_conversion_lift_pct": round(100 * max(0.0, be_lift), 1) if be_lift is not None else None,
            }
        )
    best = max(rows, key=lambda r: r["net_contribution_per_100_orders"])
    warnings = []
    if len(rows) > 1 and best is rows[-1]:
        warnings.append(f"Best candidate is the highest one tested ({best['threshold']:.0f}) — the optimum may lie beyond the range; the model rewards shrinking the subsidy, so sanity-check reach.")
    if best["orders_already_above_pct"] + best["expected_upgrades_per_100_orders"] < 25:
        warnings.append(f"Only ~{best['orders_already_above_pct'] + best['expected_upgrades_per_100_orders']:.0f}% of orders would qualify at {best['threshold']:.0f} — a threshold few customers reach barely moves conversion; the lift assumption is least reliable here.")
    spread = max(r["net_contribution_per_100_orders"] for r in rows) - min(r["net_contribution_per_100_orders"] for r in rows)
    if abs(best["net_contribution_per_100_orders"]) < 0.5 * sc * 100 * 0.1 and spread < sc * 100 * 0.2:
        warnings.append("Net effect is within noise of break-even across candidates — pick by reach (AOV × 1.15-1.30) and test; do not treat the argmax as a finding.")
    return {
        "warnings": warnings,
        "orders_analysed": n,
        "synthetic_distribution": synthetic,
        "aov": money(avg),
        "median_order_value": money(med),
        "p75_order_value": money(percentile(vals, 75)),
        "candidates": rows,
        "recommended_threshold": best["threshold"],
        "verdict": (
            f"Set free shipping at {best['threshold']:.0f} ({best['threshold_vs_aov']:.2f}× AOV {avg:.0f}): {best['orders_in_nudge_band_pct']}% of orders sit in the nudge band, "
            f"net {best['net_contribution_per_100_orders']:+,.0f} contribution per 100 orders at {nudge_uptake_pct:g}% uptake and {conversion_lift_pct:g}% conversion lift"
            + (f" (break-even lift {best['breakeven_conversion_lift_pct']}%)." if best["breakeven_conversion_lift_pct"] is not None else ".")
            + (" All candidates are net negative at these assumptions: free shipping is a conversion bet here, not self-funding — test it or fund it from the price." if best["net_contribution_per_100_orders"] < 0 else "")
            + (" (Distribution synthesised from AOV — pass real order values for a firmer answer.)" if synthetic else "")
        ),
        "assumptions": {"nudge_band": "75-100% of threshold", "uptake_pct": nudge_uptake_pct, "conversion_lift_pct_on_qualifying": conversion_lift_pct, "overshoot": "5% above threshold"},
    }


@AGENT.tool
def aov_levers(aov: float, monthly_orders: int, gross_margin_pct: float, levers: list[dict]) -> dict:
    """Compare AOV levers (bundles, upsells, cross-sells, gifts, thresholds) in incremental contribution per month, not just AOV.

    Args:
        aov: Current average order value.
        monthly_orders: Orders per month.
        gross_margin_pct: Gross margin percent on merchandise.
        levers: List of {"name": str, "take_rate_pct": % of orders that accept, "avg_added_value": extra revenue per accepting order, "cost_per_accept": incremental cost per accepting order (e.g. gift COGS, discount), "cvr_risk_pct": optional % drop in conversion caused by the lever (pre-purchase upsells)}.
    """
    a = require_positive("aov", aov)
    if monthly_orders <= 0:
        raise ToolError("monthly_orders must be > 0.")
    margin = gross_margin_pct / 100 if gross_margin_pct > 1 else gross_margin_pct
    if not 0 < margin < 1:
        raise ToolError("gross_margin_pct must be between 0 and 100.")
    if not levers:
        raise ToolError("levers is empty.")
    if len(levers) > 50:
        raise ToolError("Too many levers (50 max).")
    base_contrib = a * margin * monthly_orders
    rows = []
    for lv in levers:
        name = str(lv.get("name", "lever"))
        take = float(lv.get("take_rate_pct", 0))
        take = take / 100 if take > 1 else take
        added = float(lv.get("avg_added_value", 0))
        cost = float(lv.get("cost_per_accept", 0))
        risk = float(lv.get("cvr_risk_pct", 0))
        risk = risk / 100 if risk > 1 else risk
        if not 0 <= take <= 1 or added < 0 or cost < 0 or not 0 <= risk < 1:
            raise ToolError(f"lever {name!r}: take_rate 0-100, avg_added_value/cost >= 0, cvr_risk 0-99.")
        orders = monthly_orders * (1 - risk)
        new_aov = a + take * added
        rev = orders * new_aov
        contrib = orders * (a * margin + take * (added * margin - cost))
        rows.append(
            {
                "lever": name,
                "new_aov": money(new_aov),
                "aov_lift_pct": pct(take * added / a),
                "monthly_orders_after_risk": round(orders),
                "incremental_revenue_per_month": money(rev - a * monthly_orders),
                "incremental_contribution_per_month": money(contrib - base_contrib),
                "contribution_per_accepting_order": money(added * margin - cost),
            }
        )
    rows.sort(key=lambda r: -r["incremental_contribution_per_month"])
    best = rows[0]
    return {
        "baseline": {"aov": money(a), "monthly_revenue": money(a * monthly_orders), "monthly_contribution": money(base_contrib)},
        "levers": rows,
        "verdict": f"Best lever: {best['lever']} → AOV {best['new_aov']:.2f} ({best['aov_lift_pct']:+.1f}%), {best['incremental_contribution_per_month']:+,.0f} contribution/month."
        + ("" if best["incremental_contribution_per_month"] > 0 else " No lever is net positive at these assumptions."),
    }


@AGENT.tool
def prioritize_tests(ideas: list[dict], monthly_orders: int = 0, aov: float = 0.0) -> dict:
    """Score a CRO backlog with ICE (Impact × Confidence × Ease, 1-10 each), flag research-first items, and estimate expected orders where a lift is given.

    Args:
        ideas: List of {"name": str, "impact": 1-10, "confidence": 1-10, "ease": 1-10, "expected_lift_pct": optional relative CVR lift, "page": optional page/step it targets}.
        monthly_orders: Current monthly orders (for expected-order maths).
        aov: Average order value (for expected revenue).
    """
    if not ideas:
        raise ToolError("ideas is empty.")
    if len(ideas) > 200:
        raise ToolError("Too many ideas (200 max).")
    rows = []
    for idea in ideas:
        name = str(idea.get("name", "")).strip()
        if not name:
            raise ToolError("Every idea needs a name.")
        try:
            i, c, e = float(idea.get("impact", 0)), float(idea.get("confidence", 0)), float(idea.get("ease", 0))
        except (TypeError, ValueError):
            raise ToolError(f"{name}: impact, confidence and ease must be numbers 1-10.") from None
        if not all(1 <= x <= 10 for x in (i, c, e)):
            raise ToolError(f"{name}: impact, confidence and ease must each be 1-10.")
        score = i * c * e
        lift = float(idea.get("expected_lift_pct", 0) or 0)
        # discount expected orders by confidence (probability-ish the lift is real)
        exp_orders = monthly_orders * lift / 100 * (c / 10) if monthly_orders and lift else None
        if c <= 3:
            action = "research first (recordings, polls, support tickets) — confidence too low to test"
        elif e >= 8 and i <= 4:
            action = "just ship it (low risk, no test needed)"
        elif score >= 300:
            action = "test now"
        else:
            action = "backlog"
        rows.append(
            {
                "idea": name,
                "page": idea.get("page"),
                "impact": i,
                "confidence": c,
                "ease": e,
                "ice": round(score),
                "expected_orders_per_month": round(exp_orders, 1) if exp_orders is not None else None,
                "expected_revenue_per_month": money(exp_orders * aov) if exp_orders is not None and aov else None,
                "action": action,
            }
        )
    rows.sort(key=lambda r: (-r["ice"], -(r["expected_orders_per_month"] or 0)))
    for k, r in enumerate(rows, 1):
        r["rank"] = k
    return {
        "ranked": rows,
        "test_now": [r["idea"] for r in rows if r["action"] == "test now"],
        "ship_without_test": [r["idea"] for r in rows if r["action"].startswith("just ship")],
        "research_first": [r["idea"] for r in rows if r["action"].startswith("research")],
        "verdict": f"Top: {rows[0]['idea']} (ICE {rows[0]['ice']}). {len([r for r in rows if r['action'] == 'test now'])} ready to test, {len([r for r in rows if r['action'].startswith('research')])} need research first.",
    }
