"""E-commerce category scenario evals (evals/ecommerce.md) — replayable end-to-end checks.

Each test replays one realistic customer scenario through the agent's tools, exactly as the
customer's AI would call them, and asserts on values that were verified independently:
planted defects (recall), untouched correct elements (precision), and numbers recomputed here
with textbook formulas written without importing any hundred code (classical decomposition,
EOQ, combined-variability safety stock, per-order P&L, two-proportion z-test, business hours).
"""

import datetime as dt
import math
import random
from statistics import NormalDist

from hundred import registry


def run(slug, tool, **kwargs):
    return registry.get(slug).get_tool(tool).call(kwargs)


# ── 1. Inventory Planner ─────────────────────────────────────────────────────
# THERMO-32, Oct 2024 → Sep 2026 monthly units: Q4 peak, ~+10% YoY growth. Today 2026-10-01,
# lead time 45 ± 10 days, 1,600 on hand, nothing on order, A-item at 98% service level.
HISTORY = [505, 910, 1120, 455, 385, 470, 470, 565, 590, 660, 545, 510, 600, 955, 1300, 450, 460, 480, 555, 585, 700, 680, 640, 540]


def classical_decomposition(h):
    """Hyndman & Athanasopoulos FPP3 §3.4: 2×12 MA, seasonal ratios, trend on deseasonalised data."""
    n = len(h)
    ratios = {}
    for i in range(6, n - 6):
        cma = (0.5 * h[i - 6] + sum(h[i - 5 : i + 6]) + 0.5 * h[i + 6]) / 12
        ratios.setdefault(i % 12, []).append(h[i] / cma)
    raw = [sum(ratios[m]) / len(ratios[m]) for m in range(12)]
    s = [r * 12 / sum(raw) for r in raw]
    ds = [h[i] / s[i % 12] for i in range(n)]
    xm, ym = (n - 1) / 2, sum(ds) / n
    b = sum((i - xm) * (ds[i] - ym) for i in range(n)) / sum((i - xm) ** 2 for i in range(n))
    a = ym - b * xm
    return [(a + b * (n + k)) * s[(n + k) % 12] for k in range(12)]


def test_inventory_seasonal_sku_orders_now_with_price_break():
    ref = classical_decomposition(HISTORY)
    # sanity: the reference agrees with "same month last year × YoY growth" to within 1%
    yoy = sum(HISTORY[12:]) / sum(HISTORY[:12])
    for k in range(3):
        assert abs(ref[k] / (HISTORY[12 + k] * yoy) - 1) < 0.01

    fc = run("inventory-planner", "forecast_demand", history=HISTORY, period="monthly", horizon_periods=12, lead_time_days=45)
    for got, want in zip(fc["forecast"], ref):
        assert abs(got - want) < 0.1
    # the old raw-trend fit forecast Oct/Nov/Dec 2026 at 533/906/1172 — below last year despite +10% growth
    assert fc["forecast"][0] > HISTORY[12] and fc["forecast"][2] > HISTORY[14]
    days = 365 / 12
    ltd = ref[0] + ref[1] * (45 - days) / days
    assert abs(fc["lead_time_demand_forecast"] - ltd) < 0.1  # 1,170.5
    assert fc["lead_time_demand_at_historical_average"] == round(sum(HISTORY) / 24 / days * 45, 1)  # 932.7 — 20% short
    assert fc["use_for_reorder_point"].startswith("forecast_daily_demand_over_lead_time")

    # safety stock (combined variability, e.g. Silver-Pyke-Peterson; en.wikipedia.org/wiki/Safety_stock):
    # SS = z·√(LT·σd² + d²·σLT²)
    d, sd = fc["forecast_daily_demand_over_lead_time"], fc["daily_demand_std"]
    z = NormalDist().inv_cdf(0.98)
    ss = z * math.sqrt(45 * sd**2 + d**2 * 10**2)
    rop = run("inventory-planner", "reorder_point", daily_demand_mean=d, daily_demand_std=sd, lead_time_days=45, lead_time_std_days=10, service_level=98, on_hand=1600)
    assert rop["safety_stock"] == math.ceil(ss) == 557
    assert rop["reorder_point"] == math.ceil(d * 45 + ss) == 1728
    assert rop["order_now"] is True
    # the trap: the flat 24-month average says "not yet, ~10 days" for the same SKU
    flat = run("inventory-planner", "reorder_point", daily_demand_mean=fc["daily_demand_mean"], daily_demand_std=sd, lead_time_days=45, lead_time_std_days=10, service_level=98, on_hand=1600)
    assert flat["order_now"] is False

    # EOQ with MOQ 500, case pack 24 and all-units price breaks; annual demand = 12-month forecast
    D, S, i = 8730, 150, 0.25

    def tc(q, c):
        return D * c + D * S / q + q * i * c / 2

    eoq = run("inventory-planner", "economic_order_quantity", annual_demand=D, order_cost=S, unit_cost=6.80, holding_cost_pct=25, moq=500, pack_size=24,
              price_breaks=[{"min_qty": 1000, "unit_cost": 6.50}, {"min_qty": 2500, "unit_cost": 6.10}])
    assert eoq["eoq_unconstrained"] == round(math.sqrt(2 * D * S / (i * 6.80)), 1)  # 1241.2
    assert eoq["recommended_order_qty"] == 2520  # 2,500 break rounded up to the 24-pack
    assert eoq["annual_cost_breakdown"]["total"] == round(tc(2520, 6.10), 2)
    by_tier = {c["tier_min_qty"]: c for c in eoq["candidates"]}
    assert by_tier[1000.0]["order_qty"] == 1272 and by_tier[1000.0]["total"] == round(tc(1272, 6.50), 2)
    assert by_tier[0]["order_qty"] == 984  # best in-tier qty below the 1,000 break, not the MOQ

    # stockout date with the forecast burn (21.8/day in Oct, 34.8/day in Nov)
    cover = run("inventory-planner", "stock_cover", on_hand=1600, lead_time_days=45, safety_stock=557, today="2026-10-01",
                forecast_per_period=[round(x, 1) for x in ref[:6]], period="monthly")
    stock, t0, hit = 1600.0, dt.date(2026, 10, 1), None
    for day in range(400):
        if hit is None and stock <= 557:
            hit = day
        if stock <= 0:
            zero = day
            break
        stock -= round(ref[min(int(day / days), 5)], 1) / days
    assert cover["stockout_date"] == (t0 + dt.timedelta(zero)).isoformat() == "2026-11-28"
    assert cover["date_hits_safety_stock"] == (t0 + dt.timedelta(hit)).isoformat() == "2026-11-12"
    assert cover["last_order_date_to_protect_safety_stock"] == "2026-09-28" and cover["status"] == "order now"
    flat_cover = run("inventory-planner", "stock_cover", on_hand=1600, daily_demand=fc["daily_demand_mean"], lead_time_days=45, today="2026-10-01")
    assert flat_cover["stockout_date"] == "2026-12-18"  # three weeks too optimistic


def test_inventory_catalogue_health_and_abc():
    health = run("inventory-planner", "inventory_health", period_days=90, lead_time_days=45, skus=[
        {"sku": "THERMO-32", "on_hand": 1600, "units_sold": 1860, "unit_cost": 6.80, "forecast_units_next_period": 3158},
        {"sku": "THERMO-20", "on_hand": 2100, "units_sold": 1230, "unit_cost": 5.20},
        {"sku": "LID-STRAW", "on_hand": 900, "units_sold": 1650, "unit_cost": 1.10},
        {"sku": "KIDS-12", "on_hand": 380, "units_sold": 310, "unit_cost": 4.60},
        {"sku": "CARRY-SLING", "on_hand": 70, "units_sold": 390, "unit_cost": 3.10},
        {"sku": "GLASS-18", "on_hand": 1450, "units_sold": 120, "unit_cost": 7.90},
        {"sku": "NEON-LTD", "on_hand": 260, "units_sold": 0, "unit_cost": 6.20},
    ])
    by = {r["sku"]: r for r in health["skus"]}
    assert "dead" in by["NEON-LTD"]["flags"][0] and health["totals"]["dead_value"] == 260 * 6.20
    assert "overstock" in by["GLASS-18"]["flags"][0]
    # excess over 26 weeks of supply: 1450 − 26·(120/90·7) = 1207.3 units × 7.90
    assert health["totals"]["overstock_value"] == round((1450 - 26 * 120 / 90 * 7) * 7.90, 2)
    assert "stockout risk" in by["CARRY-SLING"]["flags"][0] and by["CARRY-SLING"]["weeks_of_supply"] == round(70 / (390 / 90 * 7), 1)
    assert by["THERMO-32"]["velocity_basis"] == "forecast" and by["THERMO-32"]["weeks_of_supply"] == round(1600 / (3158 / 90 * 7), 1)

    abc = run("inventory-planner", "abc_xyz_classify", skus=[
        {"sku": "THERMO-32", "revenue": 254240, "demand_history": HISTORY[12:]},
        {"sku": "THERMO-20", "revenue": 118000, "demand_history": [390, 420, 410, 380, 400, 395, 415, 405, 420, 410, 400, 420]},
        {"sku": "LID-STRAW", "revenue": 41000},
        {"sku": "KIDS-12", "revenue": 26500, "demand_history": [40, 300, 420, 20, 15, 30, 60, 210, 30, 120, 100, 90]},
        {"sku": "CARRY-SLING", "revenue": 14300},
        {"sku": "GLASS-18", "revenue": 9800},
        {"sku": "NEON-LTD", "revenue": 1200},
    ])
    cls = {r["sku"]: r["class"] for r in abc["skus"]}
    assert cls["THERMO-32"] == "AX" and cls["KIDS-12"] == "BZ" and abc["a_items"] == 1


# ── 2. Product Listing Writer ────────────────────────────────────────────────
BAD = {
    "title": "Hydra Insulated Water Bottle 32 oz - BEST Stainless Steel Water Bottle with Straw Lid, Leak Proof Water Bottle for Gym, Sports & Travel! Double Wall Vacuum Insulated Bottle Keeps Drinks Cold 24 Hrs, Free Shipping, BPA-Free {Black}",
    "bullets": [
        "Made of 18/8 food-grade stainless steel.",
        "KEEPS DRINKS COLD 24 HOURS: Double-wall vacuum insulation keeps water ice cold for 24 hours and coffee hot for 12, so your drink tastes the same at 4pm as it did at 8am on the commute, in the gym bag or on a hot trail in July.",
        "LEAK PROOF STRAW LID: <b>Tested</b> upside down in a gym bag — the locking straw lid will not spill, so you can toss it in with your laptop and never think twice about it. 100% money-back guarantee if it ever leaks.",
        "FITS YOUR CUP HOLDER: The 3.1 inch base fits most car cup holders and bike cages, and the powder coat grip will not slip or sweat.",
        "WHAT'S IN THE BOX: 1 x 32 oz bottle, 1 x straw lid, 1 x chug lid, 1 x cleaning brush. Ships in 24 hours from our US warehouse.",
        "BUILT TO LAST: Powder-coated finish resists chips and scratches, FDA approved materials, and the dent-resistant body survives drops on concrete, making it the perfect bottle for kids, hikers and anyone who is hard on their gear.",
    ],
    "description": "<p>The Hydra 32 oz insulated water bottle is the best water bottle you will ever own. Our insulated water bottle keeps water cold for 24 hours. This insulated water bottle is BPA-free and FDA approved. Buy the insulated water bottle today.</p>",
    "backend_keywords": "water bottle, insulated, stainless steel, hydro flask, yeti rambler, B08XYZ1234, best gym bottle, new, tumbler, flask, thermos, hiking, camping, kids, straw",
}
GOOD = {
    "title": "Hydra Insulated Water Bottle 32 oz with Straw Lid, Leak Proof Stainless Steel Bottle, Keeps Drinks Cold 24 Hours, for Gym, Hiking and Kids, Black",
    "bullets": [
        "KEEPS DRINKS COLD 24 HOURS: Double-wall vacuum insulation keeps water ice cold for 24 hours and coffee hot for 12, so your 4pm sip tastes like your 8am one",
        "LEAK PROOF STRAW LID: The locking straw lid is tested upside down in a gym bag for 8 hours, so you can pack it next to your laptop without a second thought",
        "FITS YOUR CUP HOLDER: The 3.1 inch base fits most car cup holders and bike cages, and the powder-coat grip stays dry in your hand on hot days",
        "EVERYTHING YOU NEED: 1 x 32 oz bottle, 1 x straw lid, 1 x chug lid and 1 x cleaning brush, so you can switch from sipping to gulping in 5 seconds",
        "BUILT FOR ROUGH DAYS: 18/8 stainless steel body and a chip-resistant powder coat that survives 1 m drops on concrete, so it keeps up with hikers and kids",
    ],
    "description": "Meet the Hydra 32 oz insulated water bottle. It keeps water cold for 24 hours. It keeps coffee hot for 12.<br><br>Why you will reach for it every day:<br>- A straw lid for easy sips at your desk or on the trail<br>- A chug lid for fast refills at the gym<br>- A 3.1 inch base that fits car cup holders<br><br>Care: hand wash the lids. Put the body in the top rack of the dishwasher.",
    "backend_keywords": "tumbler flask canteen hydration jug sports travel camping school office cycling men women teen large 1 liter 946ml metal thermal",
}
KEYWORDS = ["insulated water bottle", "32 oz water bottle", "stainless steel water bottle", "water bottle with straw", "leak proof water bottle", "gym water bottle", "kids water bottle", "hiking water bottle"]


def test_listing_bad_amazon_listing_every_planted_violation():
    out = run("product-listing", "check_marketplace_limits", marketplace="amazon", brand="Hydra", **BAD)
    fails = " | ".join(out["fails"])
    assert len(BAD["title"]) == 230 and "title 230 chars > 200" in fails  # Amazon 2025 title policy: 200 max
    assert "free shipping" in fails and "best" in fails  # promo words
    assert "! { }" in fails  # banned special characters
    assert "water×3" in fails and "bottle×4" in fails  # same word more than twice
    assert "6 bullets > 5" in fails
    assert "money-back" in fails and "HTML not allowed" in fails and "shipping/price info" in fails
    assert "description contains HTML" in fails and "description promo" in fails
    assert "ASIN-like" in fails
    assert "subjective/temporary terms" in fails and "best, new" in fails  # search-terms policy
    assert out["fields"]["third_party_brands"]["backend_keywords"] == ["yeti", "hydro flask", "thermos"]
    assert out["claims_to_verify"] == ["bpa-free", "fda approved"]
    assert not out["passes"]
    kw = run("product-listing", "keyword_coverage", keywords=KEYWORDS, **BAD)
    assert any("insulated water bottle" in w and "4×" in w for w in kw["warnings"])  # description stuffing
    assert run("product-listing", "score_title", title=BAD["title"], marketplace="amazon", primary_keyword="insulated water bottle", brand="Hydra",
               attributes=["32 oz", "stainless steel", "leak proof", "straw lid"])["score"] < 40


def test_listing_rewrite_passes_and_is_fully_indexed():
    out = run("product-listing", "check_marketplace_limits", marketplace="amazon", brand="Hydra", **GOOD)
    assert out["passes"] and out["fails"] == [] and out["warnings"] == []
    assert out["fields"]["title"]["chars"] == len(GOOD["title"]) == 145
    assert out["fields"]["backend_keywords"]["bytes"] == len(GOOD["backend_keywords"].encode()) < 250
    assert all(len(b) <= 255 for b in GOOD["bullets"])
    title = run("product-listing", "score_title", title=GOOD["title"], marketplace="amazon", primary_keyword="insulated water bottle", brand="Hydra",
                attributes=["32 oz", "stainless steel", "leak proof", "straw lid"])
    assert title["score"] >= 85 and title["checks"]["brand_first"]
    lint = run("product-listing", "bullet_lint", bullets=GOOD["bullets"], description=GOOD["description"])
    assert lint["bullets_score"] == 100 and lint["description"]["score"] == 100  # <br> layout is not "one long paragraph"
    kw = run("product-listing", "keyword_coverage", keywords=KEYWORDS, **GOOD)
    # every word of every target keyword is indexed; only the primary needs the exact phrase
    assert kw["coverage_pct"] == 100.0 and kw["missing"] == [] and kw["keywords"][0]["status"] == "exact"
    assert kw["warnings"] == []


# ── 3. E-com Pricing ─────────────────────────────────────────────────────────
def order_pnl(price, cogs=13.50, ship=7.20, pack=1.10, pf=0.029, pff=0.30, rr=0.12, ret=10.53):
    """Per-order contribution: a return refunds the price and restocks the unit; outbound ship,
    packaging and the processing fee are sunk (Shopify Payments keeps the fee on refunds)."""
    fee = price * pf + pff
    kept = price - cogs - ship - pack - fee
    returned = -(ship + pack + fee) - ret
    return (1 - rr) * kept + rr * returned


def test_pricing_pnl_and_20pct_sale_is_a_losing_trade():
    args = dict(cogs=13.50, shipping_cost=7.20, packaging_cost=1.10, payment_fee_pct=2.9, payment_fee_fixed=0.30, return_rate_pct=12, return_cost=10.53, min_margin_pct=30)
    full = run("ecom-pricing", "unit_economics", price=48, **args)
    sale = run("ecom-pricing", "unit_economics", price=38.40, **args)
    assert full["contribution_margin"] == round(order_pnl(48), 2) == 19.1
    assert sale["contribution_margin"] == round(order_pnl(38.40), 2) == 10.93
    assert full["gross_margin_pct"] == round(100 * 34.5 / 48, 1) and full["markup_pct"] == round(100 * 34.5 / 13.5, 1)  # 71.9% margin vs 255.6% markup
    assert full["breakeven_roas"] == round(48 / order_pnl(48), 2) == 2.51
    assert abs(order_pnl(full["floor_price_at_min_margin"]) / full["floor_price_at_min_margin"] - 0.30) < 0.001
    promo = run("ecom-pricing", "discount_impact", price=48, unit_variable_cost=0, discount_pct=20, baseline_units=260, expected_lift_pct=45, promo_fixed_cost=1500,
                contribution_at_full_price=full["contribution_margin"], contribution_at_discount_price=sale["contribution_margin"])
    be_units = (260 * 19.10 + 1500) / 10.93
    assert promo["breakeven_units"] == math.ceil(be_units) == 592 and promo["breakeven_lift_pct"] == round(100 * (be_units / 260 - 1), 1)
    assert promo["expected_scenario"]["profit_vs_baseline"] < -2000 and promo["recommendation"].startswith("Losing trade")
    # the trap: a COGS-only "variable cost" makes the same sale look profitable
    naive = run("ecom-pricing", "discount_impact", price=48, unit_variable_cost=13.50, discount_pct=20, baseline_units=260, expected_lift_pct=45)
    assert naive["breakeven_lift_pct"] == round(100 * 0.2 / (34.5 / 48 - 0.2), 1) == 38.6
    assert naive["expected_scenario"]["profit_vs_baseline"] > 0


def test_pricing_target_price_elasticity_and_market_position():
    target = run("ecom-pricing", "price_for_target_margin", cogs=13.50, target_margin_pct=40, shipping_cost=7.20, packaging_cost=1.10, return_rate_pct=12, return_cost=10.53)
    assert abs(order_pnl(target["exact_price"]) / target["exact_price"] - 0.40) < 0.001  # 48.21
    assert target["recommended"]["price"] == 48.95
    el = run("ecom-pricing", "price_elasticity", price_a=44, units_a=310, price_b=48, units_b=285, unit_variable_cost=28.9)
    assert el["arc_elasticity"] == round(((285 - 310) / 297.5) / ((48 - 44) / 46), 2) == -0.97
    comp = run("ecom-pricing", "competitor_position", my_price=48, competitor_prices=[36, 39, 42, 45, 49, 55, 58, 64], my_rating=4.7, market_rating=4.4)
    assert comp["median_competitor_price"] == 47.0 and comp["your_percentile"] == 50.0 and comp["band"] == "mid-market"


# ── 4. Store CRO ─────────────────────────────────────────────────────────────
def two_prop(n1, x1, n2, x2):
    p1, p2 = x1 / n1, x2 / n2
    pp = (x1 + x2) / (n1 + n2)
    z = (p2 - p1) / math.sqrt(pp * (1 - pp) * (1 / n1 + 1 / n2))
    return z, 2 * (1 - NormalDist().cdf(abs(z)))


def test_cro_funnel_by_device_and_ab_peek():
    mob = run("store-cro", "funnel_analysis", sessions=62000, product_views=29800, add_to_carts=2480, checkouts=1240, orders=520, revenue=41600, gross_margin_pct=55)
    steps = {s["step"]: s for s in mob["steps"]}
    assert steps["checkout → order"]["rate_pct"] == round(100 * 520 / 1240, 2) == 41.94
    assert steps["sessions → add to cart"]["orders_gained_at_benchmark"] == round((0.06 * 62000 - 2480) * 520 / 2480) == 260
    assert steps["checkout → order"]["orders_gained_at_benchmark"] == round(0.58 * 1240 - 520) == 199
    desk = run("store-cro", "funnel_analysis", sessions=22000, product_views=12300, add_to_carts=1650, checkouts=1020, orders=640, revenue=58900, gross_margin_pct=55)
    assert "no leak" in desk["verdict"]  # desktop beats every benchmark: the leak is mobile-only

    # published example (en.wikipedia.org/wiki/Two-proportion_Z-test): 80/200 vs 60/200 → z 2.0966, p 0.0360
    wiki = run("store-cro", "ab_test", control_visitors=200, control_conversions=60, variant_visitors=200, variant_conversions=80)
    assert wiki["z"] == 2.097 and wiki["p_value"] == 0.036
    z, p = two_prop(9850, 402, 9910, 468)
    ab = run("store-cro", "ab_test", control_visitors=9850, control_conversions=402, variant_visitors=9910, variant_conversions=468,
             min_detectable_effect_pct=10, daily_visitors=2067, days_run=10)
    assert ab["z"] == round(z, 3) and ab["p_value"] == round(p, 4) == 0.028 and ab["significant"]
    p1 = 402 / 9850
    p2 = p1 * 1.1
    pb = (p1 + p2) / 2
    n = (NormalDist().inv_cdf(0.975) * math.sqrt(2 * pb * (1 - pb)) + NormalDist().inv_cdf(0.8) * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2 / (p2 - p1) ** 2
    assert ab["sample_size_per_arm"] == math.ceil(n) == 38655
    # the trap: p < 0.05 at a day-10 peek with 25% of the planned sample is not a win
    assert ab["decision"].startswith("NOT YET") and ab["verdict"].startswith("PROVISIONAL")


def test_cro_free_shipping_threshold_flags_edge_optimum():
    rng = random.Random(42)
    mu = math.log(86) - 0.55**2 / 2
    orders = [round(rng.lognormvariate(mu, 0.55), 2) for _ in range(400)]
    out = run("store-cro", "free_shipping_threshold", shipping_cost=8.40, gross_margin_pct=55, order_values=orders, nudge_uptake_pct=25, conversion_lift_pct=8)
    row = next(c for c in out["candidates"] if c["threshold"] == 115.0)
    assert row["orders_already_above_pct"] == round(100 * sum(v >= 115 for v in orders) / 400, 1)
    assert row["orders_in_nudge_band_pct"] == round(100 * sum(86.25 <= v < 115 for v in orders) / 400, 1)
    assert out["recommended_threshold"] == 135.0 and len(out["warnings"]) == 3  # argmax at the edge, low reach, within noise


# ── 5. Review Responder ──────────────────────────────────────────────────────
REVIEWS = [
    ("R01", 5, "Love it! Keeps my water ice cold all day at the office. The straw lid is great."),
    ("R02", 1, "Took 3 weeks to arrive and the lid was cracked. Emailed support twice and no one answered. Very disappointed."),
    ("R03", 2, "The straw lid leaks in my bag every single time. Not leak proof at all. Soaked my laptop."),
    ("R04", 5, "Excellent bottle, sturdy and well made. Survived a drop on concrete with just a small dent."),
    ("R05", 4, "Great bottle, keeps drinks cold. Only complaint is it does not fit my car cup holder."),
    ("R06", 1, "The lid cracked and a sharp edge cut my son's lip. We had to go to urgent care. This is dangerous for kids."),
    ("R07", 3, "Works fine but smaller than expected for 32 oz, looks nothing like the photo size."),
    ("R08", 5, "Highly recommend. Ice still there after 24 hours in a hot car."),
    ("R09", 2, "The powder coat started peeling after two weeks. Cheaply made for the price."),
    ("R10", 1, "The FedEx driver left it at the wrong porch and it was stolen. Never got it."),
    ("R11", 5, "Perfect for the gym. Chug lid is a nice bonus."),
    ("R12", 4, "Good value for the price, keeps coffee hot for hours. Wish the handle was bigger."),
    ("R13", 1, "Received the wrong colour, ordered black and got pink. Call me at 555-201-3344 to fix this."),
    ("R14", 5, "Amazing. My kids love the straw lid and it survives the school bus."),
    ("R15", 2, "Arrived damaged, dented on the side and the box was crushed. Packaging was just a thin mailer."),
    ("R16", 5, "Best purchase this year. Works perfectly on long hikes."),
    ("R17", 3, "Keeps things cold but there is a metallic smell and taste for the first week."),
    ("R18", 5, "Sturdy, durable, and the colour is beautiful."),
    ("R19", 1, "Straw lid leaks all over my car. Returned it. Waste of money."),
    ("R20", 4, "Solid bottle. Shipping was slow but customer service was helpful when I asked."),
    ("R21", 5, "Exceeded my expectations. No sweating at all."),
    ("R22", 2, "Lid leaks when tipped over. Support told me to tighten it, which I did. Still leaks."),
    ("R23", 5, "Great gift for my dad, he takes it fishing every weekend."),
    ("R24", 4, "Love this bottle but it is heavy when full."),
    ("R25", 1, "Cheaper on Temu, buy it there instead. Same factory."),
    ("R26", 5, "Works great, easy to clean with the brush that comes in the box."),
    ("R27", 3, "Took two weeks to ship which was late for my trip. Bottle itself is fine."),
    ("R28", 5, "High quality and keeps ice for a whole day."),
    ("R29", 2, "The straw lid leaks and the straw fell apart after a month."),
    ("R30", 4, "Nice bottle. The straw is a little hard to clean."),
]


def test_reviews_tagging_finds_leak_safety_and_policy_cases():
    rows = [{"id": i, "rating": r, "text": t, "date": (dt.date(2026, 9, 30) - dt.timedelta(days=k)).isoformat()} for k, (i, r, t) in enumerate(REVIEWS)]
    out = run("review-responder", "tag_reviews", reviews=rows, today="2026-10-01")
    by = {r["id"]: r for r in out["reviews"]}
    assert out["average_rating"] == round(sum(r for _, r, _ in REVIEWS) / 30, 2) == 3.33
    # recall: the #1 product defect (leaking lid, 4 reviews) was untagged before the fix
    leaks = {r["id"] for r in out["reviews"] if "leaking" in r["issue_tags"]}
    assert leaks == {"R03", "R19", "R22", "R29"}
    assert next(i for i in out["issues"] if i["issue"] == "leaking")["share_pct"] == 13.3
    assert "leaking" in [i["issue"] for i in out["escalate_upstream"]]
    # the injury review jumps the queue and is escalated
    assert out["queue_order"][0] == "R06" and out["safety_escalations"] == ["R06"]
    assert "sizing_fit" in by["R05"]["issue_tags"] and "delivery_lost" in by["R10"]["issue_tags"]
    assert {c["id"]: c["flags"] for c in out["report_candidates"]} == {"R10": ["courier-only"], "R13": ["personal information"], "R25": ["competitor promotion"]}
    # precision: praise reviews stay clean
    assert by["R01"]["issue_tags"] == ["praise_quality"] and "leaking" not in by["R21"]["issue_tags"]


def test_reviews_replies_and_rating_math():
    unsafe = ("Jess, I'm so sorry about your son's lip and the trip to urgent care. I hope he is healing well. A cracked lid with a sharp edge should never reach a family, "
              "and I've asked our product team to pull and inspect lids from the same batch today. Please email me at care@hydrabottles.com or call our care line and ask for me. "
              "— Maya, Head of Customer Care")
    safe = ("Jess, I'm so sorry about your son's lip and the trip to urgent care. I hope he is healing well. I've shared what you described about the cracked lid and the sharp "
            "edge with our product safety team today, and I'd like to hear the details from you directly so we can look after you properly. Please email me at "
            "care@hydrabottles.com or call our care line and ask for me. — Maya, Head of Customer Care")
    review = REVIEWS[5][2]
    bad = run("review-responder", "lint_response", response=unsafe, review_text=review, rating=1, reviewer_name="Jess R.", platform="shopify")
    assert bad["ready_to_post"] is False and any("concedes cause" in i for i in bad["issues"])
    good = run("review-responder", "lint_response", response=safe, review_text=review, rating=1, reviewer_name="Jess R.", platform="shopify")
    assert good["ready_to_post"] and good["score"] == 100
    dana = ("Dana, three weeks for a bottle and then a cracked lid is not okay, and two unanswered emails made it worse. I'm sorry. I've found both of your messages: they went "
            "to an old inbox, and we fixed that routing this week. I've shipped a new lid to you today by express post. If anything else is off, email me at "
            "care@hydrabottles.com and I'll handle it myself. — Maya, Head of Customer Care")
    assert run("review-responder", "lint_response", response=dana, review_text=REVIEWS[1][2], rating=1, reviewer_name="Dana K.")["score"] == 100
    # k = n(T − A)/(5 − T): 180·(4.45 − 4.21)/(5 − 4.45) = 78.5 → 79 (4.45 displays as 4.5)
    rm = run("review-responder", "rating_math", current_average=4.21, review_count=180, target_average=4.45, monthly_reviews=22)
    assert rm["reviews_needed_if_all_new_rating"] == math.ceil(180 * 0.24 / 0.55) == 79
    assert rm["reviews_needed_realistic"] == math.ceil(180 * 0.24 / (0.85 * 5 + 0.15 * 2.5 - 4.45)) == 247
    assert rm["average_after_one_1_star"] == round((4.21 * 180 + 1) / 181, 3)


# ── 6. Support Desk ──────────────────────────────────────────────────────────
TICKETS = [
    ("T01", "Where is my order?", "Ordered last Monday, tracking hasn't updated in 4 days. Order #4411.", 42, "2026-10-02T09:12"),
    ("T02", "Lid snapped", "The straw lid snapped when I opened it and the plastic cut my daughter's finger. She needed 3 stitches at the ER last night. I have photos. This needs to be looked at.", 38, "2026-10-02T15:55"),
    ("T03", "Wrong colour", "I ordered black and received pink. Please send the right one, it's a gift for Saturday.", 38, "2026-10-02T10:05"),
    ("T04", "Cancel order", "Please cancel order #4520, I ordered the wrong size by mistake.", 29, "2026-10-02T16:10"),
    ("T05", "Tracking", "It wouldn't hurt to send tracking emails. I have no idea where my order is.", 55, "2026-10-02T11:40"),
    ("T06", "Chargeback", "I don't recognise this charge on my card and I've already opened a dispute with my bank.", 76, "2026-10-02T13:20"),
    ("T07", "Question", "Does the 32 oz fit a standard car cup holder? What are the base dimensions?", 0, "2026-10-02T14:02"),
    ("T08", "Arrived dented", "Bottle arrived dented and the box was crushed. Can you replace it?", 38, "2026-10-01T17:30"),
    ("T09", "Second time asking!!!", "This is the THIRD time I am writing. My refund still hasn't arrived. Unacceptable!!!", 64, "2026-10-01T09:30"),
    ("T10", "Return", "How do I return an unopened bottle? I changed my mind.", 38, "2026-10-02T08:15"),
    ("T11", "Discount code", "The code WELCOME10 didn't work at checkout.", 0, "2026-10-02T12:30"),
    ("T12", "Leaking lid", "The lid leaks all over my bag. Not leak proof as advertised.", 38, "2026-10-02T09:45"),
    ("T13", "Love it", "Just wanted to say thanks, the bottle is great and my team loves them.", 0, "2026-10-02T10:30"),
    ("T14", "Bulk order", "We want 300 bottles with our logo for a corporate event. What is your lead time and price?", 0, "2026-10-02T15:10"),
    ("T15", "Missing lid", "My order came without the chug lid that is supposed to be in the box.", 38, "2026-10-02T11:00"),
    ("T16", "Button stuck", "I pressed the button on the lid and now it won't open.", 38, "2026-10-02T13:50"),
    ("T17", "Address change", "Can I update my address? I just moved. Order #4533.", 45, "2026-10-02T16:20"),
    ("T18", "Late delivery", "Order still not delivered after 12 days, this is my 2nd message.", 230, "2026-10-01T14:00"),
    ("T19", "Metallic taste", "Water tastes metallic, is this normal? Is it safe to drink from?", 38, "2026-10-02T12:05"),
    ("T20", "Press inquiry", "I'm a journalist at Outdoor Weekly writing about insulated bottles and would like a comment on lid safety complaints.", 0, "2026-10-02T14:45"),
]


def business_hours(start, end, open_h=9, close_h=18):
    """Mon-Fri 9-18 hours between two datetimes, minute by minute (independent reference)."""
    t, mins = start, 0
    while t < end:
        if t.weekday() < 5 and open_h <= t.hour < close_h:
            mins += 1
        t += dt.timedelta(minutes=1)
    return mins / 60


def test_support_triage_safety_first_and_no_false_alarms():
    out = run("support-desk", "triage_tickets", now="2026-10-02T16:30", tickets=[
        {"id": i, "subject": s, "body": b, "order_value": v, "created_at": c} for i, s, b, v, c in TICKETS])
    q = out["queue"]
    by = {r["id"]: r for r in q}
    # the injury ticket (no "injury" keyword — "cut", "stitches", "ER") is first; it used to land last as P4 "other"
    assert q[0]["id"] == "T02" and by["T02"]["category"] == "safety" and by["T02"]["priority"] == "P1"
    assert [r["id"] for r in q[:3]] == ["T02", "T20", "T06"] and out["needs_human_now"] == ["T02", "T20", "T06"]
    # precision: "it wouldn't hurt to…" and "I pressed the button" are not safety/press escalations
    assert by["T05"]["category"] == "wismo" and by["T05"]["priority"] == "P3" and not by["T05"]["needs_human"]
    assert by["T16"]["category"] == "damaged_defective" and not by["T16"]["needs_human"]
    assert by["T04"]["category"] == "cancel_change" and by["T04"]["priority"] == "P2"
    assert by["T15"]["category"] == "wrong_or_missing_item" and by["T09"]["category"] == "return_refund" and by["T09"]["priority"] == "P2"
    assert by["T14"]["category"] == "wholesale_b2b" and any("safety question" in f for f in by["T19"]["flags"])
    # waiting time is measured on the business clock (Thu 17:30 → Fri 16:30 = 8.0 business h, not 23 h)
    now = dt.datetime(2026, 10, 2, 16, 30)
    for tid in ("T08", "T09", "T18"):
        created = dt.datetime.fromisoformat(next(c for i, *_, c in TICKETS if i == tid))
        assert by[tid]["waiting_sla_hours"] == round(business_hours(created, now), 1)


def test_support_sla_deadlines_across_weekend_and_replies():
    fri = dt.datetime(2026, 10, 2, 16, 20)
    p2 = run("support-desk", "sla_deadline", created_at="2026-10-02T16:20", priority="P2", now="2026-10-02T16:30")
    assert p2["due_at"].startswith("2026-10-05 11:20")  # 1h40 Friday + 2h20 Monday
    assert business_hours(fri, dt.datetime(2026, 10, 5, 11, 20)) == 4.0
    res = run("support-desk", "sla_deadline", created_at="2026-10-02T16:20", sla_hours=24, priority="P2", now="2026-10-02T16:30")
    assert res["due_at"].startswith("2026-10-07 13:20") and business_hours(fri, dt.datetime(2026, 10, 7, 13, 20)) == 24.0
    hol = run("support-desk", "sla_deadline", created_at="2026-10-02T16:20", priority="P2", holidays=["2026-10-05"], now="2026-10-02T16:30")
    assert hol["due_at"].startswith("2026-10-06 11:20")
    p1 = run("support-desk", "sla_deadline", created_at="2026-10-02T15:55", priority="P1", calendar_hours=True, now="2026-10-02T16:30")
    assert p1["due_at"].startswith("2026-10-02 16:55") and not p1["breached"]
    late = run("support-desk", "sla_deadline", created_at="2026-10-01T17:30", priority="P2", now="2026-10-02T16:30")
    assert late["breached"] and late["due_at"].startswith("2026-10-02 12:30") and late["business_hours_remaining"] == -4.0

    reply = ("Hi {{first_name}},\n\nI'm so sorry your daughter was hurt, and I hope her finger is healing well after the stitches. I've read your message and I'm handling "
             "this myself. I've passed your report and order {{order_number}} to our product safety lead today. Please reply with the photos when you can, and keep the lid "
             "if possible. I'll call you today at a time that suits you, and you'll have a written update from me by Monday.\n\nThank you,\nMaya")
    lint = run("support-desk", "lint_macro", template=reply, variables={"first_name": "Rosa", "order_number": "#4402"}, customer_message=TICKETS[1][2])
    assert lint["ready_to_send"] and lint["placeholders_missing"] == []
    assert run("support-desk", "tone_check", reply=lint["filled"], customer_message=TICKETS[1][2])["score"] >= 75


# ── 7. Email Flows ───────────────────────────────────────────────────────────
def customers():
    r = random.Random(11)
    out = []
    for i in range(120):
        d = dt.date(2026, 1, 5) + dt.timedelta(days=r.randint(0, 200))
        ds = [d]
        if r.random() < 0.45:
            for _ in range(r.randint(1, 4)):
                d = d + dt.timedelta(days=max(7, round(r.lognormvariate(3.64, 0.35))))
                ds.append(d)
        out.append({"customer": f"C{i:03d}", "order_dates": [x.isoformat() for x in ds]})
    return out


def test_email_purchase_cycle_drives_winback_schedule():
    cust = customers()
    gaps = sorted((b - a).days for c in cust for a, b in zip(map(dt.date.fromisoformat, c["order_dates"]), map(dt.date.fromisoformat, c["order_dates"][1:])))
    n = len(gaps)

    def pctl(p):
        k = (n - 1) * p / 100
        f = int(k)
        return gaps[f] + (gaps[min(f + 1, n - 1)] - gaps[f]) * (k - f)

    pc = run("email-flows", "purchase_cycle", customers=cust)
    assert pc["median_gap_days"] == pctl(50) == 37 and pc["p75_gap_days"] == pctl(75) == 49
    assert pc["repeat_rate_pct"] == round(100 * sum(len(c["order_dates"]) > 1 for c in cust) / 120, 1)
    wb = run("email-flows", "flow_schedule", flow="win_back", trigger_at="2026-08-20T14:05", **pc["flow_schedule_args"])
    last = dt.datetime(2026, 8, 20, 14, 5)
    assert wb["emails"][0]["send_at_local"].startswith((last + dt.timedelta(days=49)).strftime("%Y-%m-%d %H:%M"))  # p75, not 1.5 × median = 55.5
    assert wb["emails"][2]["send_at_local"].startswith((last + dt.timedelta(days=98)).strftime("%Y-%m-%d"))
    ac = run("email-flows", "flow_schedule", flow="abandoned_checkout", trigger_at="2026-10-03T22:15")
    assert [e["send_at_local"][:16] for e in ac["emails"]] == ["2026-10-03 23:15", "2026-10-05 10:00", "2026-10-07 10:00"]
    assert [e["incentive_allowed"] for e in ac["emails"]] == [False, False, True]


def test_email_diagnostics_subjects_and_revenue():
    diag = run("email-flows", "flow_diagnostics", flows=[
        {"name": "Abandoned checkout", "type": "abandoned_checkout", "sent": 4100, "delivered": 4060, "opens": 1650, "clicks": 210, "orders": 61, "revenue": 3782, "unsubscribes": 22, "spam_complaints": 3},
        {"name": "Welcome", "type": "welcome", "sent": 2300, "delivered": 2280, "opens": 1150, "clicks": 160, "orders": 30, "revenue": 1650, "unsubscribes": 9, "spam_complaints": 1},
        {"name": "Win-back", "type": "win_back", "sent": 5200, "delivered": 4900, "opens": 1300, "clicks": 70, "orders": 12, "revenue": 610, "unsubscribes": 60, "spam_complaints": 12},
    ])
    by = {f["flow"]: f for f in diag["flows"]}
    assert by["Abandoned checkout"]["placed_order_rate_pct"] == round(100 * 61 / 4060, 2) and by["Abandoned checkout"]["fix_first"] == "conversion"
    assert by["Win-back"]["fix_first"] == "deliverability" and by["Win-back"]["delivery_rate_pct"] == round(100 * 4900 / 5200, 2)
    assert by["Win-back"]["spam_rate_pct"] == round(100 * 12 / 4900, 3)
    assert by["Abandoned checkout"]["upside_if_at_benchmark_low"] == round((0.03 - 61 / 4060) * 4060 * 3782 / 61, 2)
    subj = run("email-flows", "subject_line_check", subjects=["You left something behind", "Your serum is still in your cart", "LAST CHANCE: FREE shipping ends tonight!!", "Re: your order"])
    s = {r["subject"]: r for r in subj["results"]}
    assert subj["best"] == "Your serum is still in your cart"
    assert s["Re: your order"]["score"] <= 50 and s["LAST CHANCE: FREE shipping ends tonight!!"]["score"] < 50
    rev = run("email-flows", "flow_revenue_model", flow="abandoned_checkout", monthly_triggers=4100, aov=62, current_placed_order_rate_pct=1.49, gross_margin_pct=70)
    assert rev["gap_to_benchmark_low"] == round(4100 * (0.03 - 0.0149) * 62, 2)
