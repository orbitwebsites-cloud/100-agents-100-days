"""Pipeline Forecaster tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("pipeline-forecaster")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


DEALS = [
    {"name": "Acme", "stage": "negotiation", "amount": 50000, "close_date": "2026-10-15", "last_activity": "2026-09-20", "next_step": "legal review"},
    {"name": "Beta", "stage": "proposal", "amount": 30000, "close_date": "2026-11-10", "last_activity": "2026-08-01"},
    {"name": "Gamma", "stage": "discovery", "amount": 10000, "close_date": "2026-09-01"},
    {"name": "Delta", "stage": "closed won", "amount": 99},
]


def test_weighted_pipeline_categories_and_flags():
    out = call("weighted_pipeline", deals=DEALS, today="2026-09-27", period_end="2026-12-31")
    assert out["open_pipeline"] == 90000.0
    assert out["weighted_pipeline"] == 52000.0  # 50k*.7 + 30k*.5 + 10k*.2
    assert out["commit"] == 50000.0 and out["best_case"] == 30000.0 and out["forecast"] == 65000.0
    assert out["forecast_range"] == {"low": 50000.0, "high": 80000.0}
    assert out["category_counts"] == {"commit": 1, "best_case": 1, "pipeline": 0, "slipped": 1}
    assert any("slipped" in r for r in out["risks"]) and any("stale" in r for r in out["risks"]) and any("concentration" in r for r in out["risks"])
    assert out["by_stage"]["negotiation"]["weighted"] == 35000.0
    assert out["by_close_month"]["2026-10"]["amount"] == 50000.0
    default_q = call("weighted_pipeline", deals=DEALS[:1], today="2026-11-15")
    assert default_q["period_end"] == "2026-12-31"


def test_weighted_pipeline_custom_probabilities_and_bad_input():
    out = call("weighted_pipeline", deals=DEALS[:1], stage_probabilities={"negotiation": 80}, today="2026-09-27")
    assert out["weighted_pipeline"] == 40000.0
    with pytest.raises(ToolError):
        call("weighted_pipeline", deals=[])
    with pytest.raises(ToolError):
        call("weighted_pipeline", deals=[{"name": "x", "amount": 5}])
    with pytest.raises(ToolError):
        call("weighted_pipeline", deals=[{"name": "x", "stage": "demo", "amount": "lots"}])


def test_stage_conversion_rates_and_cycle():
    closed = [
        {"outcome": "won", "amount": 10000, "created": "2026-01-01", "closed": "2026-03-01"},
        {"outcome": "lost", "amount": 5000, "furthest_stage": "proposal", "created": "2026-01-01", "closed": "2026-02-01"},
        {"outcome": "lost", "amount": 5000, "furthest_stage": "discovery"},
    ]
    out = call("stage_conversion", closed_deals=closed)
    assert out["win_rate_pct"] == 33.3 and out["won"] == 1
    conv = {(x["from"], x["to"]): x["conversion_pct"] for x in out["stage_conversion"]}
    assert conv[("discovery", "demo")] == 66.7 and conv[("proposal", "negotiation")] == 50.0
    assert out["cycle_days"]["won_median"] == 59 and out["cycle_days"]["all_avg"] == 45.0
    assert out["measured_probabilities"]["proposal"] == 0.5
    assert out["biggest_leak"]["from"] == "proposal"


def test_stage_conversion_bad_input():
    with pytest.raises(ToolError):
        call("stage_conversion", closed_deals=[{"outcome": "won", "amount": 1}])
    with pytest.raises(ToolError):
        call("stage_conversion", closed_deals=[{"outcome": "maybe", "amount": 1}, {"outcome": "won", "amount": 1}])


def test_coverage_ratio_math_and_status():
    out = call("coverage_ratio", quota=1200000, closed_to_date=400000, open_pipeline=2100000, weighted_pipeline=700000, days_left=35, days_in_period=65, avg_deal_size=40000, win_rate_pct=25, median_cycle_days=60)
    assert out["attainment_pct"] == 33.3 and out["gap"] == 800000.0
    assert out["coverage_x"] == 2.62 and out["target_coverage_x"] == 2.0
    assert out["required_win_rate_pct"] == 38.1
    assert out["deals_needed_at_avg_size"] == 20
    assert out["pipeline_needed_at_win_rate"] == 3200000.0
    assert out["new_pipeline_can_land"] is False
    assert out["status"] == "at risk"
    met = call("coverage_ratio", quota=100, closed_to_date=120, open_pipeline=0)
    assert met["status"] == "quota met"


def test_coverage_ratio_bad_input():
    with pytest.raises(ToolError):
        call("coverage_ratio", quota=0, closed_to_date=0, open_pipeline=0)


def test_sales_velocity_and_sensitivity():
    out = call("sales_velocity", opportunities=40, avg_deal_size=20000, win_rate_pct=25, cycle_days=60)
    assert out["velocity_per_day"] == 3333.33
    assert out["projected_revenue_for_period"] == 300000.0
    assert out["sensitivity"]["cycle -10%"]["delta_pct"] == 11.1
    assert out["highest_leverage"] == "cycle -10%"
    with pytest.raises(ToolError):
        call("sales_velocity", opportunities=1, avg_deal_size=1, win_rate_pct=10, cycle_days=0)


def test_forecast_accuracy_mape_and_bias():
    out = call("forecast_accuracy", forecasts=[{"period": "Q1", "forecast": 110, "actual": 100}, {"period": "Q2", "forecast": 120, "actual": 100}, {"period": "Q3", "forecast": 95, "actual": 100}])
    assert out["mape_pct"] == 11.7 and out["bias_pct"] == 8.3
    assert out["direction"] == "over-forecasting"
    assert out["hit_rate_within_10pct"] == 66.7
    assert out["calibration_multiplier"] == 0.923
    with pytest.raises(ToolError):
        call("forecast_accuracy", forecasts=[{"forecast": 1, "actual": 0}, {"forecast": 1, "actual": 1}])
