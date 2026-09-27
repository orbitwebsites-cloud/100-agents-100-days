"""Roadmap Prioritizer tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("roadmap-prioritizer")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_rice_score_ranks_and_flags():
    out = call(
        "rice_score",
        items=[
            {"name": "SSO", "reach": 500, "impact": "high", "confidence": 80, "effort": 4},
            {"name": "Dark mode", "reach": 2000, "impact": 0.5, "confidence": 1.0, "effort": 2},
            {"name": "AI summaries", "reach": 3000, "impact": 3, "confidence": 0.3, "effort": 6},
        ],
    )
    ranked = out["ranked"]
    assert ranked[0]["name"] == "Dark mode" and ranked[0]["rice"] == 500.0
    assert ranked[1]["name"] == "AI summaries" and ranked[1]["rice"] == 450.0
    assert ranked[2]["name"] == "SSO" and ranked[2]["rice"] == 200.0
    assert "Dark mode" in out["fragile_ranks"] and "AI summaries" in out["fragile_ranks"]
    assert any("confidence < 50%" in f for f in ranked[1]["flags"])
    assert out["total_effort_weeks"] == 12.0


def test_rice_score_rejects_zero_effort():
    with pytest.raises(ToolError):
        call("rice_score", items=[{"name": "x", "reach": 1, "impact": 1, "confidence": 1, "effort": 0}])


def test_kano_classify_uses_evaluation_table():
    out = call(
        "kano_classify",
        features=[
            {"name": "Offline mode", "responses": [{"functional": "like", "dysfunctional": "dislike"}] * 6 + [{"functional": "like", "dysfunctional": "neutral"}] * 2},
            {"name": "Login", "responses": [{"functional": "must-be", "dysfunctional": "dislike"}] * 5 + [{"functional": "neutral", "dysfunctional": "dislike"}] * 3},
            {"name": "Confetti", "responses": [{"functional": "neutral", "dysfunctional": "neutral"}] * 7 + [{"functional": "like", "dysfunctional": "live-with"}]},
        ],
    )
    by = {f["name"]: f for f in out["features"]}
    assert by["Login"]["code"] == "M" and by["Login"]["counts"]["Must-be"] == 8
    assert by["Offline mode"]["code"] == "O" and by["Offline mode"]["better"] == 1.0 and by["Offline mode"]["worse"] == -0.75
    assert by["Confetti"]["code"] == "I"
    assert out["build_order"] == ["Login", "Offline mode"]
    assert out["cut_candidates"] == ["Confetti"]


def test_kano_classify_rejects_bad_answer():
    with pytest.raises(ToolError):
        call("kano_classify", features=[{"name": "x", "responses": [{"functional": "meh", "dysfunctional": "like"}]}])


def test_opportunity_score_formula_and_bands():
    out = call("opportunity_score", outcomes=[{"outcome": "find past invoices", "importance": 9, "satisfaction": 3}, {"outcome": "change theme", "importance": 4, "satisfaction": 8}])
    assert out["ranked"][0]["opportunity"] == 15.0 and "worth pursuing" in out["ranked"][0]["band"]
    assert out["ranked"][1]["opportunity"] == 4.0 and "over-served" in out["ranked"][1]["band"]


def test_opportunity_score_rejects_out_of_range():
    with pytest.raises(ToolError):
        call("opportunity_score", outcomes=[{"outcome": "x", "importance": 11, "satisfaction": 3}])


def test_capacity_check_applies_moscow_rules():
    out = call(
        "capacity_check",
        items=[
            {"name": "A", "moscow": "must", "effort": 10},
            {"name": "B", "moscow": "must", "effort": 5},
            {"name": "C", "moscow": "should", "effort": 4},
            {"name": "D", "moscow": "could", "effort": 3},
            {"name": "E", "moscow": "won't", "effort": 9},
        ],
        capacity_weeks=20,
    )
    assert out["plannable_weeks"] == 16.0
    assert out["must_pct_of_capacity"] == 75.0
    assert out["effort_by_category"] == {"must": 15.0, "should": 4.0, "could": 3.0}
    assert out["below_the_line"] == ["C", "D"]
    assert any("Must = 75.0%" in p for p in out["problems"])
    assert out["items"][4]["fits"] is False and out["items"][4]["cumulative"] is None


def test_capacity_check_rejects_bad_category():
    with pytest.raises(ToolError):
        call("capacity_check", items=[{"name": "A", "moscow": "maybe", "effort": 1}], capacity_weeks=10)
