"""Decision Matrix tools — weighted scoring, sensitivity, expected value, AHP weights."""

import pytest

from hundred.agents.ops import decision_matrix
from hundred.core import ToolError

A = decision_matrix.AGENT

CRITERIA = [
    {"name": "Growth", "weight": 50},
    {"name": "Comp", "weight": 30},
    {"name": "Commute", "weight": 20, "direction": "lower"},
]
OPTIONS = [
    {"name": "Startup", "scores": {"Growth": 5, "Comp": 3, "Commute": 4}},
    {"name": "BigCo", "scores": {"Growth": 3, "Comp": 5, "Commute": 1}},
]


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_weighted_score_totals_and_direction():
    out = call("weighted_score", options=OPTIONS, criteria=CRITERIA)
    # Startup: 0.5*5 + 0.3*3 + 0.2*(5-4)=1 -> 3.6/5 = 72 ; BigCo: 0.5*3 + 0.3*5 + 0.2*(5-1)=4 -> 3.8/5 = 76
    by = {r["option"]: r for r in out["ranking"]}
    assert by["Startup"]["total"] == 72.0 and by["BigCo"]["total"] == 76.0
    assert out["winner"] == "BigCo" and out["margin_points"] == 4.0 and out["closeness"] == "CLOSE CALL"
    assert by["BigCo"]["normalised_scores"]["Commute"] == 4.0
    assert out["per_criterion"][0]["best"] == ["Startup"]


def test_weighted_score_normalises_raw_numbers_and_finds_dominated():
    out = call(
        "weighted_score",
        options=[
            {"name": "A", "scores": {"Quality": 4, "Cost": 100}},
            {"name": "B", "scores": {"Quality": 4, "Cost": 300}},
            {"name": "C", "scores": {"Quality": 5, "Cost": 200}},
        ],
        criteria=[{"name": "Quality", "weight": 1}, {"name": "Cost", "weight": 1, "direction": "lower", "normalise": True}],
    )
    by = {r["option"]: r for r in out["ranking"]}
    assert by["A"]["normalised_scores"]["Cost"] == 5.0 and by["B"]["normalised_scores"]["Cost"] == 0.0 and by["C"]["normalised_scores"]["Cost"] == 2.5
    assert {"option": "B", "dominated_by": "A"} in out["dominated_options"]
    with pytest.raises(ToolError, match="no score"):
        call("weighted_score", options=[{"name": "A", "scores": {"Quality": 4}}, {"name": "B", "scores": {"Quality": 3}}], criteria=[{"name": "Quality"}, {"name": "Cost"}])


def test_sensitivity_check_finds_weight_and_score_flips():
    out = call("sensitivity_check", options=OPTIONS, criteria=CRITERIA)
    assert out["winner"] == "BigCo"
    growth = next(f for f in out["weight_flips"] if f["criterion"] == "Growth")
    assert growth["new_winner"] == "Startup" and growth["flip_at_weight_pct"] == 55  # break-even at 54.5%
    assert "Growth" in out["fragile_criteria"]
    assert out["robustness"] in ("FRAGILE", "MODERATE")
    assert out["smallest_score_flip"]["change"] < 1.0
    assert out["equal_weights_winner"] == "BigCo" and out["equal_weights_agrees"] is True


def test_expected_value_and_regret():
    out = call(
        "expected_value",
        options=[
            {"name": "Build", "outcomes": [{"name": "ships on time", "probability": 0.6, "value": 500}, {"name": "slips", "probability": 0.4, "value": -300}]},
            {"name": "Buy", "outcomes": [{"name": "ships on time", "probability": 0.6, "value": 200}, {"name": "slips", "probability": 0.4, "value": 100}]},
        ],
    )
    build, buy = out["ranking"]
    assert build["option"] == "Build" and build["expected_value"] == 180.0 and buy["expected_value"] == 160.0
    assert build["probability_of_loss"] == 0.4 and build["expected_loss"] == -120.0
    assert build["std_dev"] == 391.92
    assert out["regret"]["by_option"]["Buy"]["max_regret"] == 300 and out["regret"]["by_option"]["Build"]["max_regret"] == 400
    assert out["regret"]["minimax_choice"] == "Buy"
    with pytest.raises(ToolError, match="sum to"):
        call("expected_value", options=[{"name": "X", "outcomes": [{"name": "a", "probability": 0.5, "value": 1}, {"name": "b", "probability": 0.3, "value": 2}]}])


def test_pairwise_weights_ahp_consistency():
    out = call(
        "pairwise_weights",
        criteria=["Growth", "Comp", "Commute"],
        comparisons=[{"a": "Growth", "b": "Comp", "ratio": 3}, {"a": "Growth", "b": "Commute", "ratio": 9}, {"a": "Comp", "b": "Commute", "ratio": 3}],
    )
    assert out["consistent"] is True and out["consistency_ratio"] == 0.0
    assert out["ranking"] == ["Growth", "Comp", "Commute"]
    assert abs(out["weights"]["Growth"] - 0.6923) < 0.001 and abs(out["weights"]["Commute"] - 0.0769) < 0.001
    bad = call(
        "pairwise_weights",
        criteria=["A", "B", "C"],
        comparisons=[{"a": "A", "b": "B", "ratio": 9}, {"a": "B", "b": "C", "ratio": 9}, {"a": "C", "b": "A", "ratio": 9}],
    )
    assert bad["consistent"] is False and bad["consistency_ratio"] > 1
    assert bad["most_inconsistent_triad"] is not None
    with pytest.raises(ToolError, match="unknown criterion"):
        call("pairwise_weights", criteria=["A", "B"], comparisons=[{"a": "A", "b": "Z", "ratio": 2}])


def test_bad_arguments_raise_clean_error():
    with pytest.raises(ToolError):
        A.get_tool("weighted_score").call({"options": "a,b", "criteria": []})
