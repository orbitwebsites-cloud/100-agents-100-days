"""Growth Experiment Lab tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("growth-experiments")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_score_experiments_ice_ranks_and_flags():
    out = call("score_experiments", experiments=[{"name": "a", "impact": 8, "confidence": 9, "ease": 8}, {"name": "b", "impact": 5, "confidence": 5, "ease": 5, "evidence": "past test"}, {"name": "c", "impact": 5, "confidence": 5, "ease": 5}])
    assert out["ranked"][0] == {**out["ranked"][0], "name": "a", "score": 576.0, "rank": 1}
    assert any("confidence 9/10 with no evidence" in f for f in out["flags"])
    assert any("Tied scores: 125" in f for f in out["flags"])
    assert out["top_3"] == ["a", "b", "c"]


def test_score_experiments_rice():
    out = call("score_experiments", method="RICE", experiments=[{"name": "a", "reach": 1000, "impact": 2, "confidence": 80, "effort": 4}, {"name": "b", "reach": 500, "impact": 3, "confidence": 0.5, "effort": 1}])
    assert [(r["name"], r["score"]) for r in out["ranked"]] == [("b", 750.0), ("a", 400.0)]
    with pytest.raises(ToolError):
        call("score_experiments", experiments=[{"name": "a", "impact": 11, "confidence": 5, "ease": 5}])
    with pytest.raises(ToolError):
        call("score_experiments", experiments=[], method="ICE")


def test_sample_size_matches_standard_calculator():
    out = call("sample_size", baseline_rate=0.032, mde_relative=0.10, weekly_traffic=8000)
    assert 49_000 <= out["visitors_per_arm"] <= 50_500  # standard two-proportion z-test result ≈ 49.8k
    assert out["weeks_needed"] == 13
    assert "Not feasible" in out["verdict"]
    assert 11 < out["mde_detectable_in_8_weeks_pct"] < 14
    pct = call("sample_size", baseline_rate=3.2, mde_relative=20, weekly_traffic=8000)
    assert 12_800 <= pct["visitors_per_arm"] <= 13_300
    assert pct["weeks_needed"] == 4
    three = call("sample_size", baseline_rate=0.05, mde_relative=0.2, variants=3)
    assert three["alpha_per_comparison"] == 0.025
    assert three["visitors_total"] == three["visitors_per_arm"] * 3


def test_sample_size_bad_input():
    with pytest.raises(ToolError):
        call("sample_size", baseline_rate=0, mde_relative=0.1)
    with pytest.raises(ToolError):
        call("sample_size", baseline_rate=0.1, mde_relative=-1)


def test_evaluate_result_decisions():
    inc = call("evaluate_result", control_visitors=10412, control_conversions=331, variant_visitors=10388, variant_conversions=372)
    assert inc["decision"] == "inconclusive"
    assert 0.10 < inc["p_value"] < 0.12
    assert 12 < inc["relative_lift_pct"] < 13.5
    assert inc["ci_95_relative_pct"][0] < 0 < inc["ci_95_relative_pct"][1]
    win = call("evaluate_result", control_visitors=20000, control_conversions=600, variant_visitors=20000, variant_conversions=700)
    assert win["decision"] == "ship" and win["significant"] and win["p_value"] < 0.01
    srm = call("evaluate_result", control_visitors=52000, control_conversions=1000, variant_visitors=48000, variant_conversions=1000)
    assert srm["decision"] == "invalid" and srm["srm"]["failed"] is True
    peek = call("evaluate_result", control_visitors=1000, control_conversions=30, variant_visitors=1000, variant_conversions=55, planned_visitors_per_arm=5000)
    assert peek["decision"] == "inconclusive" and "peeking" in peek["verdict"]
    lose = call("evaluate_result", control_visitors=20000, control_conversions=700, variant_visitors=20000, variant_conversions=600)
    assert lose["decision"] == "kill"
    with pytest.raises(ToolError):
        call("evaluate_result", control_visitors=10, control_conversions=11, variant_visitors=10, variant_conversions=1)


def test_lint_hypothesis():
    good = call("lint_hypothesis", hypothesis="If we add social proof to the pricing page for new visitors, signup conversion will increase by 10% because interviews showed trust concerns")
    assert good["completeness_pct"] == 100 and good["testable"] and good["gaps"] == []
    bad = call("lint_hypothesis", hypothesis="Make the onboarding better and more engaging")
    assert bad["completeness_pct"] == 0 and bad["testable"] is False
    assert any("Vague" in g for g in bad["gaps"])
    assert "[CHANGE]" in bad["rewrite_template"]
    with pytest.raises(ToolError):
        call("lint_hypothesis", hypothesis="short")


def test_plan_sprint_packs_by_score_and_surface():
    out = call("plan_sprint", experiments=[{"name": "a", "score": 500, "weeks": 3, "surface": "pricing"}, {"name": "b", "score": 400, "weeks": 2, "surface": "pricing"}, {"name": "c", "score": 300, "weeks": 4, "surface": "onboarding"}, {"name": "d", "score": 100, "weeks": 10}], parallel_slots=2, horizon_weeks=8)
    sched = {s["name"]: s for s in out["schedule"]}
    assert sched["a"]["start_week"] == 1 and sched["a"]["end_week"] == 3
    assert sched["b"]["start_week"] == 4  # same surface as a → waits
    assert sched["c"]["start_week"] == 1 and sched["c"]["slot"] != sched["a"]["slot"]
    assert out["unscheduled"][0]["name"] == "d"
    assert out["utilisation_pct"] == 56.2
    assert out["gantt"][0] == "slot 1: █████···"
    with pytest.raises(ToolError):
        call("plan_sprint", experiments=[{"name": "a", "weeks": 2}], parallel_slots=0)
