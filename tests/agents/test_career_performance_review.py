"""Performance Review Writer tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("performance-review")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_format_sbi_rewrites_and_flags():
    out = call(
        "format_sbi",
        items=[
            {"situation": "In the March release retro", "behavior": "you presented the incident timeline with root causes before anyone asked", "impact": "the team agreed on two fixes in 20 minutes instead of the usual hour", "kind": "strength"},
            {"situation": "lately", "behavior": "She is always lazy", "impact": "bad"},
            {"situation": "Q2 planning", "behavior": "skipped the estimate review", "impact": "which meant the roadmap slipped two weeks"},
        ],
    )
    good, bad, ok = out["items"]
    assert good["score"] == 100 and good["issues"] == []
    assert good["sbi"] == "In the March release retro, you presented the incident timeline with root causes before anyone asked, which meant the team agreed on two fixes in 20 minutes instead of the usual hour."
    assert "situation has no time or place marker" in bad["issues"]
    assert any("'lazy'" in i for i in bad["issues"]) and any("absolute" in i for i in bad["issues"])
    assert ok["sbi"] == "In Q2 planning, you skipped the estimate review, which meant the roadmap slipped two weeks."
    assert out["ready"] == [1, 3] and out["needs_work"] == [2]


def test_format_sbi_rejects_empty_item():
    with pytest.raises(ToolError):
        call("format_sbi", items=[{"situation": "", "behavior": "", "impact": ""}])


def test_check_review_language_catches_personality_absolutes_comparison_and_recency():
    review = (
        "Priya is a pleasure to work with and always helpful. She did a great job this half. In June she shipped the billing "
        "migration, cutting invoice errors 40%. In June she also led the incident review. Unlike other engineers she is very confident."
    )
    out = call("check_review_language", review=review, cycle_start="2026-01-01", cycle_end="2026-06-30")
    assert {h["term"] for h in out["personality_terms"]} == {"helpful", "confident"}
    assert out["absolutes"] == ["always"]
    assert out["peer_comparisons"] == 2
    assert out["recency"]["flag"] is True and out["recency"]["pct_late"] == 100.0 and out["recency"]["months_covered"] == ["2026-06"]
    assert any("great job" in i for i in out["issues"])
    assert out["score"] <= 50
    clean = call(
        "check_review_language",
        review="In February you shipped the billing migration, cutting invoice errors 40%. In May you led the incident review and closed all 6 action items within 2 weeks.",
        cycle_start="2026-01-01",
        cycle_end="2026-06-30",
    )
    assert clean["score"] >= 85 and clean["recency"]["flag"] is False


def test_check_review_language_rejects_bad_cycle():
    with pytest.raises(ToolError):
        call("check_review_language", review="Shipped x in March.", cycle_start="2026-06-30", cycle_end="2026-01-01")


def test_goal_attainment_math_and_bands():
    out = call(
        "goal_attainment",
        goals=[
            {"name": "Ship v2", "target": 1, "actual": 1, "weight": 40},
            {"name": "NPS 40→50", "target": 50, "actual": 47, "baseline": 40, "weight": 40},
            {"name": "p95 latency", "target": 200, "actual": 250, "direction": "lower", "weight": 20},
            {"name": "Blowout", "target": 100, "actual": 400, "weight": 0},
        ],
    )
    g = {r["name"]: r for r in out["goals"]}
    assert g["Ship v2"]["attainment_pct"] == 100.0 and g["Ship v2"]["band"] == "meets"
    assert g["NPS 40→50"]["attainment_pct"] == 70.0 and g["NPS 40→50"]["band"] == "partially meets"
    assert g["p95 latency"]["attainment_pct"] == 80.0
    assert g["Blowout"]["attainment_pct"] == 150.0  # capped
    assert out["weighted_attainment_pct"] == 84.0 and out["rating_band"] == "partially meets"
    assert out["missed_goals"] == ["NPS 40→50", "p95 latency"]


def test_goal_attainment_rejects_non_numeric():
    with pytest.raises(ToolError):
        call("goal_attainment", goals=[{"name": "Vibes", "target": "good", "actual": "great"}])


def test_calibrate_ratings_flags_lenient_and_harsh_managers():
    out = call(
        "calibrate_ratings",
        ratings=[
            {"employee": "A", "manager": "M1", "rating": 5},
            {"employee": "B", "manager": "M1", "rating": 5},
            {"employee": "C", "manager": "M1", "rating": 4},
            {"employee": "D", "manager": "M2", "rating": 3},
            {"employee": "E", "manager": "M2", "rating": 3},
            {"employee": "F", "manager": "M2", "rating": 2},
        ],
    )
    assert out["org_mean"] == 3.67
    assert out["distribution_pct"][5] == 33.3
    assert out["managers"]["M1"]["flag"] == "lenient" and out["managers"]["M2"]["flag"] == "harsh"
    assert out["managers"]["M1"]["delta_vs_org"] == 1.0
    assert out["needs_justification"] == ["A", "B"]
    assert any("top rating" in f for f in out["flags"])


def test_calibrate_ratings_rejects_out_of_scale():
    with pytest.raises(ToolError):
        call("calibrate_ratings", ratings=[{"employee": "A", "manager": "M", "rating": 6}, {"employee": "B", "manager": "M", "rating": 3}])
