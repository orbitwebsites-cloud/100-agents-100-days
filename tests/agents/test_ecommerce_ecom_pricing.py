"""E-com Pricing tools — margin, fee-inclusive pricing, discount and elasticity math."""

import pytest

from hundred.agents.ecommerce.ecom_pricing import AGENT as A
from hundred.core import ToolError


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_unit_economics_full_pnl():
    out = call("unit_economics", price=39.99, cogs=12.40, shipping_cost=6.10, packaging_cost=0.80, return_rate_pct=8, return_cost=9)
    assert out["gross_profit"] == 27.59
    assert out["gross_margin_pct"] == 69.0
    assert out["markup_pct"] == 222.5
    assert out["lines"]["payment_fees"] == round(39.99 * 0.029 + 0.30, 2)  # 1.46
    # CM1 = 39.99 − 12.40 − 6.10 − 0.80 − 1.46 = 19.23 ; returns = 0.08 × (19.23 + 9) = 2.26
    assert out["contribution_before_returns"] == 19.23
    assert out["contribution_margin"] == 16.97
    assert out["breakeven_roas"] == round(39.99 / 16.97, 2)
    assert out["max_cpa_first_order"] == 16.97
    assert 31 < out["floor_price_at_min_margin"] < 32


def test_unit_economics_marketplace_fees_apply_to_price_and_negative_margin():
    out = call("unit_economics", price=20, cogs=18, marketplace_fee_pct=15, fulfillment_fee=4.75, payment_fee_pct=0, payment_fee_fixed=0)
    assert out["lines"]["marketplace_fees"] == 3.0
    assert out["contribution_margin"] == 20 - 18 - 3 - 4.75
    assert out["breakeven_roas"] is None
    assert "NEGATIVE" in out["verdict"]


def test_unit_economics_rejects_bad_input():
    with pytest.raises(ToolError):
        call("unit_economics", price=0, cogs=5)
    with pytest.raises(ToolError):
        call("unit_economics", price=10, cogs=5, payment_fee_pct=150)


def test_price_for_target_margin_gross_and_contribution():
    g = call("price_for_target_margin", cogs=18, target_margin_pct=60, margin_basis="gross")
    assert g["exact_price"] == 45.0
    # contribution basis, Amazon-style: fixed = 18 + 4.75 ; denom = (1 − 0.15) − 0.30 = 0.55 → 41.36
    c = call("price_for_target_margin", cogs=18, target_margin_pct=30, marketplace_fee_pct=15, fulfillment_fee=4.75, payment_fee_pct=0, payment_fee_fixed=0)
    assert c["exact_price"] == round(22.75 / 0.55, 2)
    assert all(o["contribution_margin_pct"] >= 30 for o in c["charm_options"])
    assert c["recommended"]["price"] >= c["exact_price"]


def test_price_for_target_margin_impossible_target():
    with pytest.raises(ToolError):
        call("price_for_target_margin", cogs=18, target_margin_pct=90, marketplace_fee_pct=15)


def test_discount_impact_breakeven_lift_rule():
    # margin 60%, discount 20% → break-even lift = 0.2 / (0.6 − 0.2) = 50%
    out = call("discount_impact", price=35, unit_variable_cost=14, discount_pct=20, baseline_units=900, expected_lift_pct=61)
    assert out["breakeven_lift_pct"] == 50.0
    assert out["breakeven_units"] == 1350
    assert out["unit_profit_after"] == 14.0
    assert out["expected_scenario"]["profit_vs_baseline"] == 1386.0
    deep = call("discount_impact", price=35, unit_variable_cost=14, discount_pct=60, baseline_units=900)
    assert deep["breakeven_lift_pct"] is None  # unit profit ≤ 0
    assert "Losing" in deep["recommendation"]


def test_discount_impact_rejects_full_discount():
    with pytest.raises(ToolError):
        call("discount_impact", price=35, unit_variable_cost=14, discount_pct=100, baseline_units=900)


def test_price_elasticity_arc_formula():
    # dq = 550/1175 = 0.468 ; dp = −7/31.5 = −0.222 → E = −2.106
    out = call("price_elasticity", price_a=35, units_a=900, price_b=28, units_b=1450, unit_variable_cost=14)
    assert out["arc_elasticity"] == -2.11
    assert out["revenue_change_pct"] == 28.9
    assert out["profit_change"] == 1400.0
    assert out["lerner_optimal_price"] == round(14 * -2.1064 / (1 - 2.1064), 2)
    inel = call("price_elasticity", price_a=30, units_a=1000, price_b=33, units_b=960, unit_variable_cost=10)
    assert abs(inel["arc_elasticity"]) < 1 and "raise price" in inel["direction"]


def test_price_elasticity_rejects_same_price():
    with pytest.raises(ToolError):
        call("price_elasticity", price_a=30, units_a=1000, price_b=30, units_b=960, unit_variable_cost=10)


def test_competitor_position_percentiles():
    out = call("competitor_position", my_price=45, competitor_prices=[29, 35, 39, 42, 49, 55], unit_variable_cost=15, my_rating=4.7, market_rating=4.3)
    assert out["median_competitor_price"] == 40.5
    assert out["your_percentile"] == 66.7
    assert out["index_to_median"] == 111.1
    assert out["nearest_below"] == 42.0 and out["nearest_above"] == 49.0
    assert out["band"] == "mid-market"
    assert out["justified_premium_pct_from_ratings"] == 10.0
    assert out["margin_pct_if_priced_at_median"] == 63.0
    high = call("competitor_position", my_price=60, competitor_prices=[29, 35, 39, 42, 49, 55], my_rating=4.0, market_rating=4.3)
    assert high["band"] == "premium" and "warning" in high


def test_competitor_position_rejects_too_few():
    with pytest.raises(ToolError):
        call("competitor_position", my_price=45, competitor_prices=[40])
    with pytest.raises(ToolError):
        A.get_tool("competitor_position").call({"my_price": "cheap", "competitor_prices": [1, 2]})
