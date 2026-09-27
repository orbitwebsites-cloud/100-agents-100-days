"""Salary Negotiator tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("salary-negotiator")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_compare_offers_year_by_year_math():
    out = call(
        "compare_offers",
        offers=[
            {"name": "A", "base": 160000, "bonus_pct": 15, "equity_value": 200000, "signing_bonus": 20000},
            {"name": "B", "base": 175000, "shares": 20000, "share_price": 5, "strike_price": 2, "equity_type": "options", "schedule": "amazon", "match_pct": 4},
            {"name": "Stay", "base": 150000, "bonus_pct": 10},
        ],
        years=4,
    )
    a, b, stay = out["offers"]
    assert a["year_1_cash"] == 204000 and a["year_1_total"] == 254000 and a["average_annual"] == 239000
    assert b["equity_grant_value"] == 60000 and b["vest_pct_by_year"] == [5, 15, 40, 40]
    assert b["by_year"][0]["equity_vested"] == 3000 and b["by_year"][2]["equity_vested"] == 24000
    assert b["average_annual"] == 197000
    assert stay["average_annual"] == 165000
    assert out["ranking"] == ["A", "B", "Stay"]
    assert stay["gap_to_best_annual"] == 74000


def test_compare_offers_haircut_and_col():
    out = call(
        "compare_offers",
        offers=[{"name": "SF", "base": 200000, "equity_value": 400000, "col_index": 150}, {"name": "Austin", "base": 170000, "col_index": 100}],
        equity_haircut_pct=75,
    )
    sf = out["offers"][0]
    assert sf["by_year"][0]["equity_vested"] == 25000  # 100k/yr × 25% after haircut
    assert sf["average_annual"] == 225000 and sf["average_annual_col_adjusted"] == 150000
    assert out["best"] == "Austin"


def test_compare_offers_rejects_bad_schedule_length():
    with pytest.raises(ToolError):
        call("compare_offers", offers=[{"name": "X", "base": 100000, "equity_value": 10000, "schedule": "amazon", "vesting_years": 3}])
    with pytest.raises(ToolError):
        call("compare_offers", offers=[{"name": "X", "base": 0}])


def test_vesting_schedule_cliff_quarterly_and_leave_date():
    out = call("vesting_schedule", grant_value=200000, start_date="2026-11-02", cliff_months=12, frequency="quarterly", leave_date="2028-11-01")
    assert out["cliff"] == {"months": 12, "date": "2027-11-02", "amount": 50000.0}
    assert out["event_count"] == 13
    assert out["events"][1] == {"n": 2, "date": "2028-02-02", "month": 15, "amount": 12500.0, "cumulative": 62500.0, "cumulative_pct": 31.2, "cliff": False}
    assert out["events"][-1]["cumulative"] == 200000.0 and out["end_date"] == "2030-11-02"
    assert out["if_leave"] == {"leave_date": "2028-11-01", "vested": 87500.0, "vested_pct": 43.8, "forfeited": 112500.0, "next_vest": "2028-11-02"}


def test_vesting_schedule_backloaded_annual_and_month_end():
    out = call("vesting_schedule", grant_value=100000, start_date="2026-01-01", cliff_months=12, frequency="annual", schedule="amazon")
    assert [(e["date"], e["amount"]) for e in out["events"]] == [("2027-01-01", 5000.0), ("2028-01-01", 15000.0), ("2029-01-01", 40000.0), ("2030-01-01", 40000.0)]
    assert "sign-on" in out["verdict"]
    monthly = call("vesting_schedule", grant_value=100000, start_date="2026-01-31", cliff_months=0, frequency="monthly", vesting_years=1)
    assert monthly["event_count"] == 12 and monthly["events"][0]["date"] == "2026-02-28"


def test_vesting_schedule_rejects_custom_without_pcts():
    with pytest.raises(ToolError):
        call("vesting_schedule", grant_value=1000, start_date="2026-01-01", schedule="custom")
    with pytest.raises(ToolError):
        call("vesting_schedule", grant_value=1000, start_date="2026-01-01", schedule="custom", custom_vest_pct=[50, 30])


def test_plan_counter_anchors_on_strongest_justification():
    out = call("plan_counter", offer_base=120000, walk_away_base=118000, market_p50=135000, market_p75=145000, competing_offer_base=128000)
    assert out["ask_base"] == 145000 and out["justification"] == "market p75"
    assert out["ask_pct_above_offer"] == 20.8
    assert out["expected_landing"] == 132500
    assert out["credibility"] == "strong"
    assert out["levers_in_order"][0]["lever"] == "base" and out["levers_in_order"][1]["lever"] == "signing bonus"
    assert "128,000" in out["script_line"]
    assert any("below market median" in w for w in out["warnings"])
    weak = call("plan_counter", offer_base=120000, walk_away_base=110000)
    assert weak["ask_base"] == 134500 and weak["credibility"].startswith("weak")
    capped = call("plan_counter", offer_base=100000, walk_away_base=90000, target_base=200000)
    assert capped["ask_base"] == 125000  # 25% ceiling without a competing offer


def test_plan_counter_rejects_absurd_walk_away():
    with pytest.raises(ToolError):
        call("plan_counter", offer_base=100000, walk_away_base=200000)


def test_raise_value_compounds():
    out = call("raise_value", base_before=120000, base_after=132000, years=10, annual_raise_pct=3, bonus_pct=10)
    assert out["increase"] == 12000 and out["increase_pct"] == 10.0
    assert out["by_year"][0]["difference"] == 13200.0  # 12k × 1.10 bonus multiplier
    assert out["total_difference"] == 151323.21
    assert out["year_final_difference"] == 17223.01


def test_raise_value_rejects_bad_years():
    with pytest.raises(ToolError):
        call("raise_value", base_before=100000, base_after=110000, years=0)
