"""Pitch Deck Coach tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("pitch-deck-coach")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_check_deck_structure_finds_missing_and_order():
    out = call("check_deck_structure", slide_titles=["Acme", "Our solution", "The problem", "Market size", "Team", "The ask"], stage="seed")
    assert out["canonical_score"] == "6/12"
    missing = {m["slide"] for m in out["missing"]}
    assert {"traction", "competition", "business_model", "why_now", "product", "use_of_funds"} == missing
    assert "solution appears before problem" in out["critical_order_problems"]
    assert any("6 slides" in p for p in out["problems"])
    assert out["proposed_order"][1] == "problem" and out["proposed_order"][2] == "solution"


def test_check_deck_structure_rejects_bad_stage():
    with pytest.raises(ToolError):
        call("check_deck_structure", slide_titles=["Acme"], stage="ipo")


def test_market_size_bottom_up_math_and_flags():
    out = call("market_size", target_customers=200_000, annual_revenue_per_customer=4800, serviceable_pct=60, capture_pct=3, top_down_tam=5_000_000_000)
    assert out["tam"] == 960_000_000 and out["sam"] == 576_000_000 and out["som"] == 17_280_000
    assert out["som_customers"] == 3600 and out["customers_to_win_per_year"] == 720.0
    assert any("under $1B" in f for f in out["flags"])
    assert any("top-down" in f for f in out["flags"])


def test_market_size_rejects_zero_customers():
    with pytest.raises(ToolError):
        call("market_size", target_customers=0, annual_revenue_per_customer=100)


def test_raise_math_dilution_pool_and_runway():
    out = call("raise_math", amount=2_500_000, valuation=12_000_000, option_pool_pct=10, monthly_burn=100_000, start_date="2026-10-01")
    assert out["pre_money"] == 9_500_000 and out["investor_pct"] == 20.83
    assert out["founders_and_existing_pct"] == 69.17
    assert out["effective_pre_money"] == 8_300_000
    assert out["runway"]["months"] == 25.0
    assert out["runway"]["end_date"] == "2028-11-01"
    assert not any("runway" in f for f in out["flags"])


def test_raise_math_pre_money_and_short_runway():
    out = call("raise_math", amount=1_000_000, valuation=4_000_000, valuation_is_post=False, monthly_burn=90_000)
    assert out["post_money"] == 5_000_000 and out["investor_pct"] == 20.0
    assert out["runway"]["months"] < 18 and any("runway" in f for f in out["flags"])


def test_raise_math_rejects_amount_over_post():
    with pytest.raises(ToolError):
        call("raise_math", amount=5_000_000, valuation=4_000_000)


def test_slide_density_flags_walls_and_labels():
    out = call(
        "slide_density",
        slides=[
            {"title": "Acme", "body": "We make invoicing painless"},
            {"title": "Traction", "body": " ".join(["word"] * 60) + "\n- a\n- b\n- c\n- d\n- e\n- f\n- g"},
            {"title": "Churn fell to 1.2% after the onboarding redesign", "body": "- 1.2% monthly churn\n- 41% MoM growth"},
        ],
    )
    s2 = " ".join(out["slides"][1]["issues"])
    assert "words" in s2 and "bullets" in s2 and "label" in s2
    assert out["slides"][2]["issues"] == []
    assert out["clean"] == 2 and out["count"] == 3


def test_slide_density_rejects_non_object():
    with pytest.raises(ToolError):
        call("slide_density", slides=["Title"])


def test_check_deck_structure_claim_titles_need_slide_types():
    titles = ["Acme", "Front desks lose 11 hours a week to phone scheduling", "Our AI books appointments 24/7", "Why now: voice AI got 90% cheaper", "Use of funds: 18 months"]
    fallback = call("check_deck_structure", slide_titles=titles)
    m = {x["slide"]: x["canonical"] for x in fallback["mapping"]}
    assert m[2] == "problem" and m[4] == "why_now" and m[5] == "use_of_funds"
    given = call("check_deck_structure", slide_titles=titles, slide_types=["title", "problem", "solution", "why_now", "use_of_funds"])
    assert "solution" not in {x["slide"] for x in given["missing"]}
    with pytest.raises(ToolError):
        call("check_deck_structure", slide_titles=titles, slide_types=["title"])


def test_raise_math_counts_existing_cash_and_growth():
    out = call("raise_math", amount=2_500_000, valuation=12_000_000, option_pool_pct=10, monthly_burn=140_000, burn_growth_pct_per_month=3, start_date="2026-11-01", existing_cash=300_000)
    assert out["runway"]["months"] == 15.9 and out["runway"]["end_date"] == "2028-02-01"
    assert any("$3,278,021" in f for f in out["flags"])


def test_slide_density_flags_one_percent_of_market_claim():
    out = call("slide_density", slides=[{"title": "Acme", "body": "x"}, {"title": "A $12B market", "body": "We only need 1% of it."}])
    assert any("1% of the market" in i for i in out["slides"][1]["issues"])
