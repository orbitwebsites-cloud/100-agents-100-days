"""Sponsorship Pricer tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("sponsorship-pricer")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_rate_card_cpm_math_and_uplifts():
    base = call("rate_card", platform="youtube", median_views=40000, deliverable="integration")
    assert base["base_low_mid_high"] == [800.0, 1200.0, 1600.0]
    assert base["quote_mid"] == 1200.0 and base["effective_cpm_mid"] == 30.0
    loaded = call("rate_card", platform="youtube", median_views=40000, deliverable="integration", engagement_rate_pct=6, niche="finance", usage_days=90, exclusivity_months=2, rush=True)
    # mult = 1.5 × 1.2 = 1.8; adders = 1 + 0.5 + 0.3 + 0.25 = 2.05 → 1200 × 1.8 × 2.05
    assert loaded["audience_multiplier"] == 1.8 and loaded["term_adders_pct"] == 105
    assert loaded["quote_mid"] == round(1200 * 1.8 * 2.05, 2)
    assert any("usage rights 90 days +50%" in r for r in loaded["reasoning"])
    floor = call("rate_card", platform="x", median_views=2000, deliverable="post", production_hours=3, hourly_floor=100)
    assert floor["floor_applied"] is True and floor["quote_low"] == 300.0
    override = call("rate_card", platform="tiktok", median_views=100000, deliverable="video", cpm_override=20)
    assert override["quote_mid"] == 2000.0 and override["cpm_source"] == "creator override"
    # table restored after override
    assert call("rate_card", platform="tiktok", median_views=100000, deliverable="video")["quote_mid"] == 1800.0


def test_rate_card_bad_input():
    with pytest.raises(ToolError):
        call("rate_card", platform="myspace", median_views=1000)
    with pytest.raises(ToolError):
        call("rate_card", platform="youtube", median_views=0)
    with pytest.raises(ToolError):
        call("rate_card", platform="youtube", median_views=1000, deliverable="story")


def test_media_kit_numbers_median_vs_mean():
    views = [10000, 12000, 9000, 11000, 250000, 10500, 9800, 10200, 11500, 9900]
    out = call("media_kit_numbers", views=views, followers=50000, likes=20000, comments=1500, shares=500, previous_followers=45000, period_days=30)
    assert out["median_views"] == 10350 and out["mean_views"] == 34390
    assert out["engagement_rate_by_views_pct"] == round(100 * 22000 / sum(views), 1)
    assert out["engagement_rate_by_followers_pct"] == round(100 * 2200 / 50000, 1)
    assert out["views_per_follower"] == 0.21
    assert out["follower_growth_pct"] == 11.1
    assert any("outliers inflate" in n for n in out["notes"])
    assert out["coefficient_of_variation"] > 0.8


def test_media_kit_numbers_bad_input():
    with pytest.raises(ToolError):
        call("media_kit_numbers", views=[])
    with pytest.raises(ToolError):
        call("media_kit_numbers", views=[100, -5])


def test_evaluate_offer_gap_flags_and_counter():
    out = call(
        "evaluate_offer",
        offer_amount=800,
        platform="tiktok",
        median_views=60000,
        deliverable="dedicated",
        production_hours=10,
        hourly_floor=100,
        perpetual_usage=True,
        exclusivity_months=6,
        payment_terms_days=60,
        revision_rounds=3,
        kill_fee=False,
    )
    assert out["implied_cpm"] == round(800 / 60, 2)
    assert out["effective_hourly"] == 80.0
    assert out["rate_card_mid"] > out["offer"] and out["gap_vs_mid_pct"] < 0
    joined = " ".join(out["red_flags"])
    assert "Perpetual" in joined and "exclusivity" in joined and "Net-60" in joined and "revision" in joined and "floor" in joined
    assert any("kill fee" in a for a in out["amber_flags"])
    assert out["counter"] >= out["rate_card_mid"] and out["counter"] % 25 == 0
    assert out["verdict"].startswith("Underpriced")
    fair = call("evaluate_offer", offer_amount=5000, platform="youtube", median_views=40000, deliverable="integration", deposit_pct=50)
    assert fair["verdict"].startswith("At or above") and fair["counter"] == 5000.0


def test_evaluate_offer_bad_input():
    with pytest.raises(ToolError):
        call("evaluate_offer", offer_amount=500, platform="youtube", median_views=1000, deliverables=0)


def test_bundle_quote_caps_discount_and_schedules():
    out = call(
        "bundle_quote",
        items=[{"deliverable": "YouTube integration", "rate": 1800, "quantity": 2}, {"deliverable": "Reel", "rate": 500, "quantity": 2}],
        bundle_discount_pct=25,
        months=3,
        deposit_pct=50,
        net_days=30,
    )
    assert out["list_price"] == 4600.0 and out["bundle_discount_pct"] == 15.0
    assert out["package_price"] == 3910.0 and out["contract_total"] == 11730.0
    assert out["payment_schedule"][0]["amount"] == 1955.0 and len(out["payment_schedule"]) == 4
    assert any("capped" in f for f in out["flags"])
    one = call("bundle_quote", items=[{"deliverable": "Post", "rate": 400}], bundle_discount_pct=0)
    assert one["package_price"] == 400.0 and one["payment_schedule"][1]["amount"] == 200.0


def test_bundle_quote_bad_input():
    with pytest.raises(ToolError):
        call("bundle_quote", items=[{"deliverable": "x", "rate": -5}])
