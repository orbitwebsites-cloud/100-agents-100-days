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


def test_rice_score_groups_fragile_ranks_into_tiers():
    out = call("rice_score", items=[
        {"name": "A", "reach": 7000, "impact": 0.5, "confidence": 100, "effort": 1, "evidence": "tickets"},
        {"name": "B", "reach": 6000, "impact": 1, "confidence": 80, "effort": 2},
        {"name": "C", "reach": 5000, "impact": 2, "confidence": 80, "effort": 4},
        {"name": "D", "reach": 400, "impact": 2, "confidence": 80, "effort": 3},
    ])
    assert out["tiers"] == [["A"], ["B", "C"], ["D"]]


def test_wsjf_and_ice_scores():
    w = call("framework_score", items=[{"name": "SSO", "business_value": 13, "time_criticality": 13, "risk_reduction": 5, "job_size": 8},
                                      {"name": "Audit log", "business_value": 5, "time_criticality": 8, "risk_reduction": 8, "job_size": 3}])
    assert [r["name"] for r in w["ranked"]] == ["Audit log", "SSO"] and w["ranked"][1]["score"] == 3.88
    i = call("framework_score", method="ice", items=[{"name": "x", "impact": 8, "confidence": 5, "ease": 6}])
    assert i["ranked"][0]["score"] == 240.0
    with pytest.raises(ToolError):
        call("framework_score", method="rice", items=[{"name": "x"}])


def test_kano_worse_is_never_negative_zero():
    out = call("kano_classify", features=[{"name": "f", "responses": [{"functional": "like", "dysfunctional": "neutral"}]}])
    assert str(out["features"][0]["worse"]) == "0.0"


def test_capacity_check_overflowing_coulds_are_the_contingency():
    out = call("capacity_check", capacity_weeks=10, items=[{"name": "a", "moscow": "must", "effort": 5}, {"name": "b", "moscow": "should", "effort": 3}, {"name": "c", "moscow": "could", "effort": 2}])
    assert out["problems"] == [] and out["below_the_line"] == ["c"] and "contingency" in out["notes"][0]


def test_framework_score_value_effort_and_weighted_drivers():
    ve = call("framework_score", method="value_effort", items=[{"name": "a", "value": 8, "effort": 2}, {"name": "b", "value": 9, "effort": 3}])
    assert [(r["name"], r["score"]) for r in ve["ranked"]] == [("a", 4.0), ("b", 3.0)]
    wt = call("framework_score", method="weighted", weights={"retention": 3, "expansion": 1},
              items=[{"name": "SSO", "scores": {"retention": 2, "expansion": 5}}, {"name": "Exports", "scores": {"retention": 4}}])
    # SSO: (3·2 + 1·5)/4 = 2.75 ; Exports: (3·4 + 0)/4 = 3.0 (missing driver counted as 0 and noted)
    assert [(r["name"], r["score"]) for r in wt["ranked"]] == [("Exports", 3.0), ("SSO", 2.75)]
    assert "no score for expansion" in wt["ranked"][0]["notes"][0]
    with pytest.raises(ToolError):
        call("framework_score", method="weighted", items=[{"name": "x", "scores": {}}])
