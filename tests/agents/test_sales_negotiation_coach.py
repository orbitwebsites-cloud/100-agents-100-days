"""Negotiation Coach tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("negotiation-coach")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_zopa_batna_seller_zone_and_anchor():
    out = call("zopa_batna", our_walkaway=96000, our_target=110000, their_walkaway_estimate=115000, our_batna_value=50000, their_batna_value=80000)
    assert out["zopa_exists"] is True
    assert (out["zopa_low"], out["zopa_high"], out["zopa_width"]) == (96000.0, 115000.0, 19000.0)
    assert out["midpoint"] == 105500.0
    assert out["target_in_zopa"] is True and out["target_position_in_zopa"] == 0.74
    assert 110000 <= out["recommended_anchor"] <= 115000 * 1.10
    assert out["power"] == "theirs"


def test_zopa_batna_no_zone_and_buyer_side():
    none = call("zopa_batna", our_walkaway=96000, our_target=110000, their_walkaway_estimate=90000)
    assert none["zopa_exists"] is False and none["recommended_anchor"] is None and "gap $6,000" in none["verdict"]
    buyer = call("zopa_batna", our_walkaway=100000, our_target=85000, their_walkaway_estimate=80000, we_are_seller=False)
    assert (buyer["zopa_low"], buyer["zopa_high"]) == (80000.0, 100000.0)
    assert buyer["recommended_anchor"] <= 85000


def test_zopa_batna_bad_input():
    with pytest.raises(ToolError):
        call("zopa_batna", our_walkaway=100, our_target=90, their_walkaway_estimate=120)
    with pytest.raises(ToolError):
        call("zopa_batna", our_walkaway=0, our_target=90, their_walkaway_estimate=120)


def test_concession_ladder_shrinks_and_stays_above_floor():
    out = call("concession_ladder", opening_price=120000, floor_price=96000, steps=3)
    assert out["room"] == 24000.0
    moves = [s["move"] for s in out["ladder"]]
    assert moves == sorted(moves, reverse=True)
    assert all(s["price"] > 96000 for s in out["ladder"])
    assert [s["move_pct_of_room"] for s in out["ladder"]] == [47.5, 28.5, 19.0]
    assert out["ladder"][0]["price"] == 108603.0
    assert abs(sum(moves) - (120000 - out["ladder"][-1]["price"])) < 0.01
    assert out["held_in_reserve"] > 0
    assert out["ladder"][1]["only_if"].startswith("multi-year")
    one = call("concession_ladder", opening_price=1000, floor_price=800, steps=1, gets=["sign today"])
    assert one["ladder"][0]["only_if"] == "sign today" and one["ladder"][0]["price"] == 800.0


def test_concession_ladder_bad_input():
    with pytest.raises(ToolError):
        call("concession_ladder", opening_price=100, floor_price=100)
    with pytest.raises(ToolError):
        call("concession_ladder", opening_price=100, floor_price=50, steps=7)


def test_compare_packages_tcv_pv_and_ranking():
    out = call(
        "compare_packages",
        packages=[
            {"name": "1yr 10%", "annual_price": 100000, "term_years": 1, "discount_pct": 10},
            {"name": "3yr 18% upfront", "annual_price": 100000, "term_years": 3, "discount_pct": 18, "payment": "annual_upfront"},
            {"name": "3yr 18% monthly", "annual_price": 100000, "term_years": 3, "discount_pct": 18, "payment": "monthly"},
        ],
        cost_of_capital_pct=12,
    )
    by = {p["name"]: p for p in out["packages"]}
    assert by["1yr 10%"]["tcv"] == 90000.0 and by["1yr 10%"]["present_value"] == 90000.0
    assert by["3yr 18% upfront"]["tcv"] == 246000.0 and by["3yr 18% upfront"]["present_value"] == 220584.18
    assert by["3yr 18% monthly"]["present_value"] < by["3yr 18% upfront"]["present_value"]
    assert out["highest_pv"] == "3yr 18% upfront" and out["highest_pv_per_year"] == "1yr 10%"
    assert any("cash-timing benefit" in n for n in out["notes"])
    esc = call("compare_packages", packages=[{"name": "esc", "annual_price": 100, "term_years": 2, "escalator_pct": 10, "discount_pct": 0}], cost_of_capital_pct=0)
    assert esc["packages"][0]["tcv"] == 210.0 and esc["packages"][0]["effective_discount_pct"] == 0.0


def test_compare_packages_bad_input():
    with pytest.raises(ToolError):
        call("compare_packages", packages=[])
    with pytest.raises(ToolError):
        call("compare_packages", packages=[{"name": "x", "annual_price": 100, "payment": "bitcoin"}])


def test_trade_ranker_classes_and_pairs():
    out = call(
        "trade_ranker",
        trades=[
            {"item": "net-60", "side": "give", "cost_to_us": 2, "value_to_them": 4},
            {"item": "price lock 3yr", "side": "give", "cost_to_us": 4, "value_to_them": 3},
            {"item": "annual prepay", "side": "get", "value_to_us": 4, "cost_to_them": 2},
            {"item": "case study", "side": "get", "value_to_us": 3, "cost_to_them": 2},
        ],
    )
    assert out["cheap_gives"] == ["net-60"] and out["protect"] == ["price lock 3yr"]
    assert out["gives_ranked"][0]["leverage"] == 2.0
    assert out["pairs"][0]["if_they_want"] == "net-60" and out["pairs"][0]["we_ask_for"] == "annual prepay" and out["pairs"][0]["net_to_us"] == 2
    assert len(out["meso_packages"]) == 2


def test_trade_ranker_bad_input():
    with pytest.raises(ToolError):
        call("trade_ranker", trades=[{"item": "x", "side": "give"}])
    with pytest.raises(ToolError):
        call("trade_ranker", trades=[{"item": "x", "side": "give", "cost_to_us": 9}, {"item": "y", "side": "get"}])
