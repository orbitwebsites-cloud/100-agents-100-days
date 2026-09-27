"""Ad Copy Lab tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("ad-copy-lab")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


HEADS = ["Team Task Software", "Plan Projects in 4 Minutes", "Trusted by 12,000 Teams", "Free Forever Plan", "Team Task Software Tool!"]
DESCS = ["Get your team organized today. Start free, no credit card needed.", "x" * 95]


def test_validate_google_rsa_limits_pins_and_policy():
    out = call("validate_platform_copy", platform="google_rsa", headlines=HEADS, descriptions=DESCS, pins={"h1": [1]}, keyword="team task software")
    assert out["descriptions"][1]["fits"] is False
    assert out["descriptions"][1]["chars"] == 95
    flags = out["headlines"][4]["flags"]
    assert any("exclamation" in f for f in flags) and any("near-duplicate of #1" in f for f in flags)
    assert out["rsa_combinations_unpinned"] == 5 * 4 * 3 * 2  # P(5,3) × P(2,2)
    assert out["rsa_combinations"] == 1 * 4 * 3 * 2  # h1 fixed in slot 1
    assert out["headlines_with_keyword"] == [1, 5]
    assert out["ready"] is False


def test_validate_meta_fold_is_soft():
    out = call("validate_platform_copy", platform="meta", primary_texts=["y" * 140], headlines=["Short"])
    assert out["primary_texts"][0]["fits"] is True
    assert any("fold" in f for f in out["primary_texts"][0]["flags"])
    assert any("very short" in f for f in out["headlines"][0]["flags"])


def test_validate_rejects_bad_pins_and_no_assets():
    with pytest.raises(ToolError):
        call("validate_platform_copy", platform="google_rsa", headlines=HEADS, descriptions=DESCS, pins={"h1": [4]})
    with pytest.raises(ToolError):
        call("validate_platform_copy", platform="meta")


def test_angle_coverage_counts_and_gaps():
    out = call("angle_coverage", lines=["Trusted by 12,000 Teams", "Ends Friday: 20% off", "Stop Losing Tasks in Slack", "Built for Remote Teams", "Great software"], min_angles=5)
    assert out["angle_counts"]["social_proof"] == 1
    assert out["angle_counts"]["generic"] == 1
    assert out["angles_covered"] == 4
    assert out["meets_bar"] is False
    assert any("no angle" in f for f in out["fixes"])


def test_angle_coverage_rejects_empty():
    with pytest.raises(ToolError):
        call("angle_coverage", lines=[])


def test_score_ad_copy_rewards_specifics_and_penalises_policy():
    good = call("score_ad_copy", line="Plan Projects in 4 Minutes", keyword="projects")
    bad = call("score_ad_copy", line="BEST SOFTWARE EVER!!!")
    assert good["score"] >= 65 and good["grade"] == "ship"
    assert "contains a number" in good["reasons"] and "contains keyword" in good["reasons"]
    assert bad["score"] < 50 and bad["grade"] == "rewrite"
    assert any("ALL CAPS" in r for r in bad["reasons"])
    over = call("score_ad_copy", line="This headline is definitely far too long for a search ad", max_chars=30)
    assert over["chars"] > 30 and any("over limit" in r for r in over["reasons"])


def test_score_ad_copy_rejects_empty():
    with pytest.raises(ToolError):
        call("score_ad_copy", line="   ")


def test_ad_math_break_even():
    out = call("ad_math", daily_budget=150, cpc=2.4, cvr_pct=3, aov=85, margin_pct=60, ctr_pct=2)
    assert out["daily"]["clicks"] == 62.5
    assert out["daily"]["conversions"] == 1.88
    assert out["daily"]["impressions"] == 3125
    assert out["cpa"] == 80.0
    assert out["break_even_cpa"] == 51.0
    assert abs(out["break_even_roas"] - 1.67) < 0.01
    assert abs(out["break_even_cvr_pct"] - 4.71) < 0.01
    assert out["profitable"] is False
    good = call("ad_math", daily_budget=150, cpc=1.2, cvr_pct=5, aov=85, margin_pct=60)
    assert good["profitable"] is True and good["cpa"] == 24.0


def test_ad_math_rejects_zero_cpc():
    with pytest.raises(ToolError):
        call("ad_math", daily_budget=100, cpc=0, cvr_pct=3, aov=50, margin_pct=50)


def test_bad_arguments_raise_clean_error():
    with pytest.raises(ToolError):
        A.get_tool("ad_math").call({"daily_budget": "lots"})
