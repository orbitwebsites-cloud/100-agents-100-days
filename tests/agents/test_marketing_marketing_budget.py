"""Marketing Budget Planner tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("marketing-budget")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_ltv_and_cac_ceiling():
    out = call("ltv_and_cac_ceiling", arpu_monthly=79, gross_margin_pct=78, monthly_churn_pct=3.5, current_cac=600)
    assert out["monthly_contribution_per_customer"] == 61.62
    assert out["expected_lifetime_months"] == 28.6
    assert abs(out["ltv"] - 1760.57) < 0.01
    assert abs(out["max_cac_at_target_ratio"] - 586.86) < 0.01
    assert out["ltv_to_cac"] == 2.93 and out["payback_months"] == 9.7
    assert abs(out["break_even_roas"] - 1.28) < 0.01
    capped = call("ltv_and_cac_ceiling", arpu_monthly=100, gross_margin_pct=80, monthly_churn_pct=0.5)
    assert capped["lifetime_capped"] is True and capped["expected_lifetime_months"] == 60.0


def test_ltv_rejects_zero_churn():
    with pytest.raises(ToolError):
        call("ltv_and_cac_ceiling", arpu_monthly=79, gross_margin_pct=78, monthly_churn_pct=0)


CHANNELS = [
    {"channel": "Google", "spend": 18000, "customers": 120, "tag": "core"},
    {"channel": "Meta", "spend": 10000, "customers": 45},
    {"channel": "LinkedIn", "spend": 6000, "customers": 12},
    {"channel": "Content", "spend": 6000, "customers": 30, "fixed_costs": 4000},
]


def test_channel_economics_cac_and_reallocation():
    out = call("channel_economics", channels=CHANNELS, ltv=1760, gross_margin_pct=78, arpu_monthly=79)
    by = {c["channel"]: c for c in out["channels"]}
    assert by["Google"]["cac_fully_loaded"] == 150.0 and by["Google"]["verdict"] == "scale"
    assert by["Content"]["cac_fully_loaded"] == 333.33 and by["Content"]["cac_paid_only"] == 200.0
    assert by["LinkedIn"]["cac_fully_loaded"] == 500.0
    assert out["ranked_by_cac"] == ["Google", "Meta", "Content", "LinkedIn"]
    assert out["totals"]["blended_cac"] == round(44000 / 207, 2)
    assert out["reallocation"]["from"] == "LinkedIn" and out["reallocation"]["to"] == "Google" and out["reallocation"]["amount"] == 1800.0
    assert out["reallocation"]["expected_extra_customers"] == round(1800 / 150 - 1800 / 500, 1)
    dead = call("channel_economics", channels=[{"channel": "Radio", "spend": 5000, "customers": 0}])
    assert dead["channels"][0]["verdict"].startswith("no customers")


def test_channel_economics_rejects_negative():
    with pytest.raises(ToolError):
        call("channel_economics", channels=[{"channel": "x", "spend": -5, "customers": 1}])


def test_allocate_budget_respects_bounds_and_split():
    out = call("allocate_budget", total=40000, channels=[
        {"channel": "Google", "weight": 1 / 150, "tag": "core", "max": 22000},
        {"channel": "Meta", "weight": 1 / 222, "tag": "core"},
        {"channel": "LinkedIn", "weight": 1 / 500, "tag": "emerging", "min": 3000},
        {"channel": "Podcast", "weight": 0, "tag": "experimental", "min": 4000},
    ])
    amounts = {a["channel"]: a["amount"] for a in out["allocation"]}
    assert abs(sum(amounts.values()) - 40000) < 0.05
    assert amounts["Podcast"] == 4000.0
    assert amounts["Google"] > amounts["Meta"] > amounts["LinkedIn"] >= 3000
    assert out["split_by_tag_pct"]["experimental"] == 10.0
    assert out["unallocated"] == 0.0
    capped = call("allocate_budget", total=10000, channels=[{"channel": "A", "weight": 1, "max": 3000, "tag": "core"}, {"channel": "B", "weight": 1, "max": 3000, "tag": "core"}])
    assert capped["unallocated"] == 4000.0 and any("could not be allocated" in w for w in capped["warnings"])


def test_allocate_budget_rejects_minimums_over_total():
    with pytest.raises(ToolError):
        call("allocate_budget", total=1000, channels=[{"channel": "A", "weight": 1, "min": 800}, {"channel": "B", "weight": 1, "min": 800}])


def test_pacing_check_over_pace():
    out = call("pacing_check", budget=25000, spent_to_date=15200, period_start="2026-10-01", period_end="2026-10-31", as_of="2026-10-14")
    assert out["period"]["days_elapsed"] == 14 and out["period"]["days_remaining"] == 17
    assert out["expected_spend_to_date"] == round(25000 * 14 / 31, 2)
    assert out["status"] == "over pace" and abs(out["pace_ratio"] - 1.346) < 0.001
    assert out["projected_end_spend"] == round(15200 / 14 * 31, 2)
    assert out["daily_budget_to_land_on_plan"] == round(9800 / 17, 2)
    under = call("pacing_check", budget=25000, spent_to_date=5000, period_start="2026-10-01", period_end="2026-10-31", as_of="2026-10-14")
    assert under["status"] == "under pace"


def test_pacing_check_rejects_backwards_period():
    with pytest.raises(ToolError):
        call("pacing_check", budget=100, spent_to_date=10, period_start="2026-10-31", period_end="2026-10-01")


def test_growth_projection_compounds_and_breaks_even():
    out = call("growth_projection", monthly_budget=40000, cac=190, arpu_monthly=79, gross_margin_pct=78, monthly_churn_pct=3.5, months=12)
    m1 = out["projection"][0]
    assert m1["new_customers"] == round(40000 / 190, 1) and m1["customers"] == m1["new_customers"]
    assert abs(m1["mrr"] - 40000 / 190 * 79) < 0.01
    assert out["projection"][-1]["customers"] > m1["customers"] * 8
    assert out["breakeven_month"] == 6
    assert out["steady_state_customers"] == round(40000 / 190 / 0.035)
    inflated = call("growth_projection", monthly_budget=40000, cac=190, arpu_monthly=79, gross_margin_pct=78, monthly_churn_pct=3.5, months=12, cac_inflation_pct_per_month=5)
    assert inflated["end_customers"] < out["end_customers"]
    assert inflated["projection"][-1]["cac"] == round(190 * 1.05**11, 2)


def test_growth_projection_rejects_zero_cac():
    with pytest.raises(ToolError):
        call("growth_projection", monthly_budget=1000, cac=0, arpu_monthly=10, gross_margin_pct=50, monthly_churn_pct=2)


def test_bad_arguments_raise_clean_error():
    with pytest.raises(ToolError):
        A.get_tool("pacing_check").call({"budget": "big", "spent_to_date": 1, "period_start": "2026-10-01", "period_end": "2026-10-31"})
