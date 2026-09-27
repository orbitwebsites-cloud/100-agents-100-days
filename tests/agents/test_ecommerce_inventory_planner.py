"""Inventory Planner tools — textbook inventory math must be exactly right."""

import math

import pytest

from hundred.agents.ecommerce.inventory_planner import AGENT as A
from hundred.core import ToolError


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_reorder_point_combined_variability_formula():
    # SS = z·√(LT·σd² + d²·σLT²) = 1.8808·√(21·144 + 1600·16) = 1.8808·√28624 = 318.2
    out = call("reorder_point", daily_demand_mean=40, daily_demand_std=12, lead_time_days=21, lead_time_std_days=4, service_level=97)
    assert abs(out["z"] - 1.881) < 0.002
    assert out["safety_stock"] == math.ceil(1.8808 * math.sqrt(28624))
    assert out["expected_demand_over_lead_time"] == 840.0
    assert out["reorder_point"] == 840 + out["safety_stock"]
    assert out["variance_split"]["dominant"] == "lead-time variability"


def test_reorder_point_z_values_and_order_now():
    out95 = call("reorder_point", daily_demand_mean=10, daily_demand_std=3, lead_time_days=16, service_level=0.95, on_hand=150, on_order=40)
    assert abs(out95["z"] - 1.645) < 0.002
    # SS = 1.645 · 3 · √16 = 19.7 → 20 ; ROP = 160 + 19.7 → 180 ; position 190 > 180
    assert out95["safety_stock"] == 20
    assert out95["reorder_point"] == 180
    assert out95["order_now"] is False
    out99 = call("reorder_point", daily_demand_mean=10, daily_demand_std=3, lead_time_days=16, service_level=99, review_period_days=9, on_hand=100)
    assert abs(out99["z"] - 2.326) < 0.002
    # horizon 25 days: SS = 2.326·3·5 = 34.9 → 35; order-up-to = 250 + 35
    assert out99["safety_stock"] == 35
    assert out99["order_up_to_level"] == 285
    assert out99["order_now"] is True


def test_reorder_point_rejects_bad_service_level():
    with pytest.raises(ToolError):
        call("reorder_point", daily_demand_mean=10, daily_demand_std=3, lead_time_days=16, service_level=40)
    with pytest.raises(ToolError):
        call("reorder_point", daily_demand_mean=10, daily_demand_std=3, lead_time_days=0)


def test_eoq_textbook_and_moq_penalty():
    # EOQ = √(2·12000·85/(0.25·6.4)) = √(2040000/1.6) = 1129.2
    out = call("economic_order_quantity", annual_demand=12000, order_cost=85, unit_cost=6.4, holding_cost_pct=25)
    assert out["eoq_unconstrained"] == 1129.2
    assert out["recommended_order_qty"] == 1129.2
    assert abs(out["annual_cost_breakdown"]["ordering"] - out["annual_cost_breakdown"]["holding"]) < 1  # equal at optimum
    assert out["orders_per_year"] == round(12000 / 1129.2, 2)
    moq = call("economic_order_quantity", annual_demand=12000, order_cost=85, unit_cost=6.4, holding_cost_pct=25, moq=1500)
    assert moq["recommended_order_qty"] == 1500
    assert moq["constraint_cost_per_year_vs_eoq"] > 0
    assert moq["orders_per_year"] == 8.0


def test_eoq_all_units_price_break_wins_when_cheaper():
    out = call(
        "economic_order_quantity",
        annual_demand=12000, order_cost=85, unit_cost=6.4, holding_cost_pct=25,
        price_breaks=[{"min_qty": 2000, "unit_cost": 6.0}],
    )
    assert out["recommended_order_qty"] == 2000
    assert out["recommended_unit_cost"] == 6.0
    # total at 2000 @ 6.00: 72000 + 12000·85/2000 + 2000·1.5/2 = 72000 + 510 + 1500
    assert out["annual_cost_breakdown"]["total"] == 74010.0
    assert out["saving_per_year_vs_base_eoq"] > 4000


def test_eoq_rejects_bad_input():
    with pytest.raises(ToolError):
        call("economic_order_quantity", annual_demand=0, order_cost=85, unit_cost=6.4)


def test_forecast_demand_trend_and_daily_conversion():
    out = call("forecast_demand", history=[100, 110, 120, 130, 140, 150], period="monthly", horizon_periods=2)
    assert out["trend_units_per_period"] == 10.0
    assert out["forecast"] == [160.0, 170.0]
    assert out["daily_demand_mean"] == round(125 / (365 / 12), 3)
    assert out["std_floor_applied"] is True  # perfectly linear series → residual σ is 0 → floored


def test_forecast_demand_seasonality_needs_24_months():
    hist = [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 300] * 2
    out = call("forecast_demand", history=hist, period="monthly", horizon_periods=12)
    assert out["seasonal_indices"] is not None
    assert out["seasonal_indices"][11] > 2.0
    assert out["forecast"][11] > out["forecast"][0] * 2


def test_forecast_demand_rejects_short_history():
    with pytest.raises(ToolError):
        call("forecast_demand", history=[5], period="weekly")
    with pytest.raises(ToolError):
        call("forecast_demand", history=[5, 6], period="fortnightly")


def test_stock_cover_counts_incoming_on_arrival_and_backs_out_order_date():
    out = call(
        "stock_cover", on_hand=500, daily_demand=20, lead_time_days=14, safety_stock=100,
        incoming=[{"qty": 300, "arrives": "2026-10-10"}], today="2026-09-27", daily_demand_std=5,
    )
    assert out["days_of_cover_incl_incoming"] == 40.0
    assert out["stockout_date"] == "2026-11-06"
    assert out["date_hits_safety_stock"] == "2026-11-01"
    assert out["last_order_date_to_protect_safety_stock"] == "2026-10-18"
    assert out["stockout_date_pessimistic"] < out["stockout_date"]
    assert out["status"] == "ok"
    urgent = call("stock_cover", on_hand=50, daily_demand=20, lead_time_days=14, today="2026-09-27")
    assert urgent["status"] == "order overdue"


def test_stock_cover_rejects_bad_shipment():
    with pytest.raises(ToolError):
        call("stock_cover", on_hand=50, daily_demand=20, lead_time_days=14, incoming=[{"qty": 10, "arrives": "next week"}])


def test_abc_xyz_classification():
    out = call(
        "abc_xyz_classify",
        skus=[
            {"sku": "a", "revenue": 800, "demand_history": [10, 11, 9, 10]},
            {"sku": "b", "revenue": 150, "demand_history": [1, 10, 0, 5]},
            {"sku": "c", "revenue": 50},
        ],
    )
    by = {r["sku"]: r for r in out["skus"]}
    assert by["a"]["class"] == "AX" and by["a"]["cumulative_share_pct"] == 80.0
    assert by["b"]["abc"] == "B" and by["b"]["xyz"] == "Z"
    assert by["c"]["abc"] == "C" and by["c"]["xyz"] == "?"
    assert out["a_items"] == 1


def test_abc_rejects_zero_revenue():
    with pytest.raises(ToolError):
        call("abc_xyz_classify", skus=[{"sku": "a", "revenue": 0}])


def test_inventory_health_flags_dead_overstock_and_risk():
    out = call(
        "inventory_health",
        skus=[
            {"sku": "fast", "on_hand": 100, "units_sold": 900, "unit_cost": 5},
            {"sku": "slow", "on_hand": 2000, "units_sold": 30, "unit_cost": 2},
            {"sku": "dead", "on_hand": 40, "units_sold": 0, "unit_cost": 10},
        ],
        period_days=90, lead_time_days=30,
    )
    by = {r["sku"]: r for r in out["skus"]}
    assert by["fast"]["weeks_of_supply"] == 1.4 and "stockout risk" in by["fast"]["flags"][0]
    assert by["fast"]["sell_through_pct"] == 90.0
    assert "overstock" in by["slow"]["flags"][0]
    assert "dead" in by["dead"]["flags"][0]
    assert out["totals"]["dead_value"] == 400.0
    assert out["totals"]["stock_value"] == 4900.0


def test_inventory_health_rejects_bad_rows():
    with pytest.raises(ToolError):
        call("inventory_health", skus=[{"sku": "x", "on_hand": "lots", "units_sold": 1, "unit_cost": 1}])
    with pytest.raises(ToolError):
        A.get_tool("inventory_health").call({"skus": "not a list"})


def test_forecast_seasonal_trend_fitted_on_deseasonalised_series():
    # 2 years, Q1 peak (index 0-2) and +20% growth: a raw straight-line fit is dragged down by the early peaks
    y1 = [300, 280, 260, 100, 100, 100, 100, 100, 100, 100, 100, 100]
    hist = y1 + [round(v * 1.2) for v in y1]
    out = call("forecast_demand", history=hist, period="monthly", horizon_periods=3, lead_time_days=30)
    assert out["trend_units_per_period"] > 0
    assert out["forecast"][0] > hist[12]  # next Jan beats last Jan on a growing SKU
    assert out["lead_time_demand_forecast"] == round(out["forecast"][0] * 30 / (365 / 12), 1)
    assert out["use_for_reorder_point"].startswith("forecast_daily_demand_over_lead_time")


def test_forecast_lead_time_demand_spans_periods_and_stable_sku_note():
    out = call("forecast_demand", history=[100] * 12, period="monthly", horizon_periods=1, lead_time_days=45)
    assert out["lead_time_demand_forecast"] == round(100 * 45 / (365 / 12), 1)
    assert out["use_for_reorder_point"].startswith("daily_demand_mean")
    with pytest.raises(ToolError):
        call("forecast_demand", history=[1, 2, 3], lead_time_days=-1)


def test_stock_cover_follows_forecast_profile():
    # 30.42-day periods: 304.2 units in period 1 (10/day), then 20/day
    out = call("stock_cover", on_hand=500, lead_time_days=10, today="2026-10-01", forecast_per_period=[304.1667, 608.3333], period="monthly")
    assert out["demand_basis"] == "forecast profile"
    # days 0-30 burn 310 (31 days × 10), remaining 190 at 20/day → 9.5 days → zero on day 41
    assert out["stockout_date"] == "2026-11-11"
    with pytest.raises(ToolError):
        call("stock_cover", on_hand=10, lead_time_days=5, forecast_per_period=[-1])


def test_inventory_health_uses_forecast_velocity_when_given():
    out = call("inventory_health", skus=[{"sku": "s", "on_hand": 700, "units_sold": 90, "unit_cost": 2, "forecast_units_next_period": 900}], period_days=90, lead_time_days=30)
    row = out["skus"][0]
    assert row["velocity_basis"] == "forecast" and row["weeks_of_supply"] == 10.0 and row["trailing_weekly_velocity"] == 7.0
    assert row["flags"] == []  # trailing velocity alone would call this 100 weeks = overstock


def test_eoq_candidate_above_tier_uses_largest_in_tier_quantity():
    out = call("economic_order_quantity", annual_demand=8730, order_cost=150, unit_cost=6.8, moq=500, pack_size=24, price_breaks=[{"min_qty": 1000, "unit_cost": 6.5}])
    base = next(c for c in out["candidates"] if c["tier_min_qty"] == 0)
    assert base["order_qty"] == 984 and base["eoq_feasible_in_tier"] is False


def test_forecast_scales_up_stockout_periods():
    days = 365 / 12
    out = call("forecast_demand", history=[100, 100, 50, 100], period="monthly", stockout_days=[0, 0, days / 2, 0], horizon_periods=1)
    assert out["stockout_adjusted_periods"] == [2]
    assert out["baseline_per_period"] == 100.0  # 50 sold in half a month in stock = 100 demand
    with pytest.raises(ToolError):
        call("forecast_demand", history=[100, 100], stockout_days=[0])
