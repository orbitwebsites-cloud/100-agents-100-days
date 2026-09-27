"""Pricing Strategist tools — Van Westendorp intersections, tier ladder, elasticity, break-even volume."""

import pytest

from hundred.agents.finance.pricing_strategist import AGENT as A
from hundred.core import ToolError


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def _survey():
    # 10 respondents with overlapping curves; intersections are checkable by hand (see test).
    rows = []
    for k in range(10):
        rows.append({"too_cheap": 10 + 2 * k, "bargain": 15 + 2 * k, "expensive": 20 + 2 * k, "too_expensive": 30 + 2 * k})
    rows.append({"too_cheap": 50, "bargain": 10, "expensive": 20, "too_expensive": 30})  # inconsistent → dropped
    return rows


def test_van_westendorp_points_and_drops_inconsistent():
    out = call("van_westendorp", responses=_survey())
    assert out["n_valid"] == 10 and out["n_dropped_inconsistent"] == 1
    p = out["points"]
    # by hand: at $22 too_cheap(>=22)=40% and not_cheap(1-bargain>=22)=40% → PMC 22;
    # at $26 bargain(>=26)=40% and expensive(<=26)=40% → IPP 26;
    # not_expensive vs too_expensive cross between 33 (30%/20%) and 34 (20%/30%) → PME 33.5
    assert p["pmc"] == 22.0
    assert p["ipp"] == 26.0
    assert p["pme"] == 33.5
    assert p["pmc"] < p["ipp"] < p["pme"]
    assert out["acceptable_range"] == {"low": 22.0, "high": 33.5}
    assert out["confidence"] == "low"


def test_van_westendorp_needs_enough_rows():
    with pytest.raises(ToolError):
        call("van_westendorp", responses=[{"too_cheap": 1, "bargain": 2, "expensive": 3, "too_expensive": 4}])
    with pytest.raises(ToolError):
        call("van_westendorp", responses=[{"too_cheap": 1}] * 6)


def test_tier_builder_default_ladder():
    out = call("tier_builder", anchor_price=49)
    t = out["tiers"]
    assert [x["monthly"] for x in t] == [19.0, 49.0, 109.0]
    assert t[1]["annual_per_month"] == 40.0
    assert t[1]["effective_annual_discount_pct"] == 18.4
    assert t[0]["annual_total"] == 180.0
    assert out["target_tier"] == "Pro"
    assert out["flags"] == []


def test_tier_builder_flags_and_validation():
    out = call("tier_builder", anchor_price=100, ratios=[1, 1.2, 6], charm=False)
    assert any("1.5x" in f for f in out["flags"]) and any("4x" in f for f in out["flags"])
    with pytest.raises(ToolError):
        call("tier_builder", anchor_price=100, tiers=7)
    with pytest.raises(ToolError):
        call("tier_builder", anchor_price=100, ratios=[3, 2, 1])


def test_elasticity_arc_and_best_points():
    out = call("elasticity", observations=[{"price": 10, "quantity": 1000}, {"price": 12, "quantity": 900}, {"price": 15, "quantity": 600}], unit_cost=4)
    assert out["segments"][0]["arc_elasticity"] == -0.58
    assert out["segments"][0]["classification"] == "inelastic"
    assert out["segments"][1]["arc_elasticity"] == -1.8
    assert out["revenue_max"]["price"] == 12.0
    assert out["profit_max"]["gross_profit"] == 7200.0
    with pytest.raises(ToolError):
        call("elasticity", observations=[{"price": 10, "quantity": 5}, {"price": 10, "quantity": 6}])


def test_price_change_breakeven_raise_and_discount():
    up = call("price_change_breakeven", current_price=100, price_change_pct=10, gross_margin_pct=70, current_units=1000)
    assert up["breakeven_volume_change_pct"] == -12.5
    assert up["units_can_lose"] == 125.0
    assert up["new_gross_margin_pct"] == 72.7
    assert up["markup_pct"] == 233.3
    down = call("price_change_breakeven", current_price=100, price_change_pct=-20, unit_cost=30)
    assert down["breakeven_volume_change_pct"] == 40.0
    wipe = call("price_change_breakeven", current_price=100, price_change_pct=-70, gross_margin_pct=70)
    assert wipe["breakeven_volume_change_pct"] is None
    with pytest.raises(ToolError):
        call("price_change_breakeven", current_price=100, price_change_pct=10)
