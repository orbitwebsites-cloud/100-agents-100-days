"""Objection Crusher tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("objection-handler")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_classify_objection_price_with_competitor_secondary():
    out = call("classify_objection", objection="Love it but the price is double what we pay HubSpot now.", stage="proposal")
    assert out["primary"] == "price"
    assert out["secondary"] == "competitor"
    assert out["smokescreen"] is False
    assert "Isolate" in out["framework"]


def test_classify_objection_smokescreen_and_stage_prior():
    out = call("classify_objection", objection="Send me some information and I'll get back to you.")
    assert out["smokescreen"] is True
    early = call("classify_objection", objection="We don't really have budget for this right now.", stage="discovery")
    assert early["primary"] in ("need", "price") and early["signal_counts"].get("need", 0) >= 1


def test_classify_objection_bad_input():
    with pytest.raises(ToolError):
        call("classify_objection", objection="  ")


def test_roi_rebuttal_math():
    out = call("roi_rebuttal", annual_price=24000, hours_saved_per_week=5, people_affected=6, hourly_cost=60)
    assert out["hours_saved_per_year"] == 1440
    assert out["annual_value"] == 86400.0
    assert out["roi_pct_steady_state"] == 260.0
    assert out["payback_months"] == 3.3
    assert out["cost_of_delay"]["per_month"] == 7200.0
    assert out["breakeven_hours_saved_per_person_per_week"] == 1.39
    weak = call("roi_rebuttal", annual_price=50000, hours_saved_per_week=1, people_affected=2, hourly_cost=30, implementation_cost=10000)
    assert weak["roi_pct_steady_state"] < 0 and "Negative ROI" in weak["verdict"]


def test_roi_rebuttal_bad_input():
    with pytest.raises(ToolError):
        call("roi_rebuttal", annual_price=0)
    with pytest.raises(ToolError):
        call("roi_rebuttal", annual_price=1000, hours_saved_per_week=-1)


def test_reframe_price_per_unit_and_delta():
    out = call("reframe_price", annual_price=24000, users=6, fte_annual_cost=120000, alternative_annual_cost=12000, working_days=250)
    assert out["per_user_per_month"] == 333.33
    assert out["per_user_per_day"] == 16.0
    assert out["per_user_per_working_hour"] == 2.0
    assert out["share_of_one_fte"] == 0.2
    assert out["delta_vs_alternative"] == 12000.0 and out["delta_pct_vs_alternative"] == 100.0
    assert out["recommended_framing"].startswith("$16.00 per user per working day")


def test_reframe_price_bad_input():
    with pytest.raises(ToolError):
        call("reframe_price", annual_price=1000, users=0)


def test_objection_log_stats_counts_and_insights():
    rows = [{"category": "price", "stage": "proposal", "outcome": "lost"}] * 4 + [
        {"category": "timing", "stage": "discovery", "outcome": "won"},
        {"text": "we already use Salesforce", "stage": "discovery", "outcome": "lost"},
    ]
    out = call("objection_log_stats", objections=rows)
    assert out["total"] == 6
    top = out["by_category"][0]
    assert top["category"] == "price" and top["count"] == 4 and top["share_pct"] == 66.7
    assert top["win_rate_when_raised_pct"] == 0.0
    assert any("cluster late" in i for i in out["insights"])
    assert out["by_stage"]["proposal"] == 4


def test_objection_log_stats_bad_input():
    with pytest.raises(ToolError):
        call("objection_log_stats", objections=[])
    with pytest.raises(ToolError):
        call("objection_log_stats", objections=[{"category": "price", "outcome": "maybe"}])
    with pytest.raises(ToolError):
        call("objection_log_stats", objections=[{"stage": "x"}])


def test_price_subtypes_detected():
    out = call("classify_objection", objection="Honestly the price is almost double what we pay for Tipalti today, and I can't justify $38k a year to our CFO.", stage="proposal")
    assert out["primary"] == "price"
    assert out["price_subtypes"] == ["competitor_cheaper", "value_gap"]
    assert "total cost of ownership" in out["price_responses"]["competitor_cheaper"]
    assert call("classify_objection", objection="We just don't have budget until next fiscal year.", stage="proposal")["price_subtypes"] == ["budget"]
