"""Store CRO tools — funnel maths, real statistics, AOV modelling."""

import math

import pytest

from hundred.agents.ecommerce.store_cro import AGENT as A
from hundred.core import ToolError


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_funnel_analysis_rates_and_leak_ranking():
    out = call("funnel_analysis", sessions=84000, product_views=41000, add_to_carts=4300, checkouts=2100, orders=1150, revenue=92000)
    assert out["overall_conversion_pct"] == round(100 * 1150 / 84000, 2)
    assert out["aov"] == 80.0
    assert out["cart_abandonment_pct"] == round(100 * (1 - 1150 / 4300), 1)
    steps = {s["step"]: s for s in out["steps"]}
    assert steps["sessions → add to cart"]["rate_pct"] == 5.12
    # bringing ATC to 6% adds (5040 − 4300) carts × (1150/4300) orders/cart = 198 orders
    assert steps["sessions → add to cart"]["orders_gained_at_benchmark"] == 198
    assert out["leaks_ranked"][0]["step"] == "sessions → add to cart"
    assert steps["checkout → order"]["orders_gained_at_benchmark"] == round(0.58 * 2100 - 1150)


def test_funnel_analysis_rejects_non_narrowing_funnel():
    with pytest.raises(ToolError):
        call("funnel_analysis", sessions=1000, product_views=500, add_to_carts=600, checkouts=100, orders=50)


def test_ab_test_two_proportion_z():
    out = call("ab_test", control_visitors=19650, control_conversions=371, variant_visitors=19800, variant_conversions=412)
    p1, p2 = 371 / 19650, 412 / 19800
    pooled = 783 / 39450
    z = (p2 - p1) / math.sqrt(pooled * (1 - pooled) * (1 / 19650 + 1 / 19800))
    assert out["z"] == round(z, 3)
    assert out["p_value"] == 0.1699
    assert out["significant"] is False
    assert out["relative_lift_pct"] == round(100 * (p2 - p1) / p1, 2)
    assert out["ci_diff_pct_points"][0] < 0 < out["ci_diff_pct_points"][1]
    win = call("ab_test", control_visitors=50000, control_conversions=1000, variant_visitors=50000, variant_conversions=1150)
    assert win["significant"] is True and win["p_value"] < 0.01 and "WIN" in win["verdict"]


def test_ab_test_sample_size_planning():
    out = call("ab_test", baseline_rate_pct=2.0, min_detectable_effect_pct=10, daily_visitors=3000)
    # textbook: n ≈ 80.7k per arm for 2% → 2.2%, α 0.05 two-sided, power 0.8
    assert 80_000 <= out["sample_size_per_arm"] <= 81_500
    assert out["days_required"] == math.ceil(2 * out["sample_size_per_arm"] / 3000)
    assert out["run_for_full_weeks"] == 8


def test_ab_test_rejects_bad_input():
    with pytest.raises(ToolError):
        call("ab_test", control_visitors=100, control_conversions=150, variant_visitors=100, variant_conversions=5)
    with pytest.raises(ToolError):
        call("ab_test")


def test_free_shipping_threshold_distribution_maths():
    vals = [40] * 30 + [60] * 30 + [75] * 20 + [95] * 10 + [130] * 10  # AOV = 6750/100 = 67.5
    out = call("free_shipping_threshold", shipping_cost=7.4, gross_margin_pct=45, order_values=vals, candidate_thresholds=[80], conversion_lift_pct=0, nudge_uptake_pct=20)
    c = out["candidates"][0]
    assert out["aov"] == 67.5
    assert c["orders_already_above_pct"] == 20.0  # 95s and 130s
    assert c["orders_in_nudge_band_pct"] == 50.0  # 60s and 75s (band 60-80)
    assert c["expected_upgrades_per_100_orders"] == 10.0
    # extra revenue per order = ((30·20 + 20·5)/100)·0.2·1.05 = 7·0.2·1.05 = 1.47 → per 100 orders 147
    assert c["extra_revenue_per_100_orders"] == 147.0
    assert c["shipping_subsidy_change_per_100_orders"] == round(100 * 7.4 * 0.30, 2)
    assert c["breakeven_conversion_lift_pct"] > 0
    free_now = call("free_shipping_threshold", shipping_cost=7.4, gross_margin_pct=45, order_values=vals, candidate_thresholds=[80], currently_free=True)
    assert free_now["candidates"][0]["shipping_subsidy_change_per_100_orders"] < 0


def test_free_shipping_threshold_synthetic_from_aov_and_bad_input():
    out = call("free_shipping_threshold", shipping_cost=7, gross_margin_pct=50, aov=68)
    assert out["synthetic_distribution"] is True and len(out["candidates"]) >= 4
    with pytest.raises(ToolError):
        call("free_shipping_threshold", shipping_cost=7, gross_margin_pct=50)


def test_aov_levers_contribution_maths():
    out = call(
        "aov_levers", aov=68, monthly_orders=1150, gross_margin_pct=45,
        levers=[
            {"name": "post-purchase upsell", "take_rate_pct": 8, "avg_added_value": 22},
            {"name": "pre-checkout upsell", "take_rate_pct": 5, "avg_added_value": 18, "cvr_risk_pct": 3},
        ],
    )
    by = {r["lever"]: r for r in out["levers"]}
    assert by["post-purchase upsell"]["new_aov"] == round(68 + 0.08 * 22, 2)
    assert by["post-purchase upsell"]["incremental_contribution_per_month"] == round(1150 * 0.08 * 22 * 0.45, 2)
    assert by["pre-checkout upsell"]["incremental_contribution_per_month"] < 0  # CVR risk outweighs take
    assert out["levers"][0]["lever"] == "post-purchase upsell"


def test_aov_levers_rejects_bad_lever():
    with pytest.raises(ToolError):
        call("aov_levers", aov=68, monthly_orders=100, gross_margin_pct=45, levers=[{"name": "x", "take_rate_pct": 150, "avg_added_value": 5}])


def test_prioritize_tests_ice():
    out = call(
        "prioritize_tests",
        ideas=[
            {"name": "Add Shop Pay", "impact": 7, "confidence": 8, "ease": 9, "expected_lift_pct": 6},
            {"name": "Redesign PDP", "impact": 9, "confidence": 3, "ease": 2},
            {"name": "Fix size chart", "impact": 3, "confidence": 9, "ease": 9},
        ],
        monthly_orders=1150, aov=80,
    )
    assert out["ranked"][0]["idea"] == "Add Shop Pay" and out["ranked"][0]["ice"] == 504
    assert out["ranked"][0]["expected_orders_per_month"] == round(1150 * 0.06 * 0.8, 1)
    assert "Redesign PDP" in out["research_first"]
    assert "Fix size chart" in out["ship_without_test"]


def test_prioritize_tests_rejects_out_of_range():
    with pytest.raises(ToolError):
        call("prioritize_tests", ideas=[{"name": "x", "impact": 11, "confidence": 5, "ease": 5}])
