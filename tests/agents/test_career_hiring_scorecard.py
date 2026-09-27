"""Hiring Scorecard tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("hiring-scorecard")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


COMPS = [
    {"name": "SQL & data modeling", "weight": 30, "must_have": True, "description": "writes correct, efficient SQL"},
    {"name": "Problem solving", "weight": 25, "must_have": True},
    {"name": "Communication", "weight": 20},
    {"name": "Ownership", "weight": 15},
    {"name": "Culture fit", "weight": 10},
]


def test_build_scorecard_normalises_weights_rejects_proxies_and_assigns_loop():
    out = call("build_scorecard", role="Senior Data Analyst", competencies=COMPS, interviewers=["Me", "Priya", "Tom"])
    assert out["rejected"][0]["name"] == "Culture fit"
    assert [c["weight_pct"] for c in out["competencies"]] == [33.3, 27.8, 22.2, 16.7]
    assert out["must_haves"] == ["SQL & data modeling", "Problem solving"]
    assert all(len(v) == 2 for v in out["coverage"].values())
    assert all(len(k["competencies"]) <= 3 for k in out["kit"])
    assert out["competencies"][1]["questions"][0].startswith("Describe the hardest problem")
    assert set(out["competencies"][0]["anchors"]) == {"1", "2", "3", "4"}
    assert out["warnings"] and "Culture fit" in out["warnings"][0]


def test_build_scorecard_rejects_when_too_few_job_related_items():
    with pytest.raises(ToolError):
        call("build_scorecard", role="X", competencies=[{"name": "Culture fit", "weight": 1}, {"name": "Energy", "weight": 1}, {"name": "SQL", "weight": 1}], interviewers=["A", "B"])
    with pytest.raises(ToolError):
        call("build_scorecard", role="X", competencies=COMPS, interviewers=["A"])


def test_score_candidates_weighted_bar_and_disagreement():
    out = call(
        "score_candidates",
        candidates=[
            {"name": "Ana", "ratings": {"Me": {"SQL": 4, "Problem solving": 3}, "Priya": {"SQL": 4, "Communication": 3}, "Tom": {"Problem solving": 4, "Communication": 2}}},
            {"name": "Ben", "ratings": {"Me": {"SQL": 2, "Problem solving": 3}, "Priya": {"SQL": 2, "Communication": 4}, "Tom": {"Problem solving": 1, "Communication": 4}}},
        ],
        weights={"SQL": 40, "Problem solving": 35, "Communication": 25},
        must_haves=["SQL"],
    )
    ana, ben = out["candidates"]
    assert ana["weighted_score"] == 86.2 and ana["decision"] == "strong hire" and ana["disagreements"] == []
    assert ben["weighted_score"] == 62.5 and ben["decision"].startswith("no hire (must-have")
    assert ben["must_have_failures"][0] == {"competency": "SQL", "mean": 2.0, "bar": 2.5}
    assert ben["disagreements"][0]["spread"] == 2.0
    assert out["ranking"] == ["Ana", "Ben"]
    assert out["interviewer_leniency"]["Priya"]["delta_vs_panel"] == 0.25
    assert len(out["debrief_agenda"]) == 2


def test_score_candidates_rejects_rating_outside_rubric():
    with pytest.raises(ToolError):
        call("score_candidates", candidates=[{"name": "A", "ratings": {"Me": {"Vibe": 4}}}], weights={"SQL": 1})
    with pytest.raises(ToolError):
        call("score_candidates", candidates=[{"name": "A", "ratings": {"Me": {"SQL": 7}}}], weights={"SQL": 1})


def test_check_feedback_bias_flags_proxies_and_rewards_evidence():
    bad = call("check_feedback_bias", feedback="Great energy, really likeable. I think she's smart but not sure about culture fit. Seems a bit young for the role. 3/4.")
    assert {h["term"] for h in bad["protected_or_proxy_terms"]} == {"culture fit", "energy", "likeable", "young"}
    assert bad["strike_before_filing"] is True and bad["score"] == 0
    assert bad["evidence_ratio_pct"] < 40
    good = call(
        "check_feedback_bias",
        feedback=(
            "When asked about the churn analysis, she described building a cohort model in SQL that cut the query from 40s to 2s "
            "and walked me through the join logic. She quantified the impact: 12% fewer false churn flags. On communication, she "
            "explained the trade-off to the marketing lead using one chart. I rate SQL 4 and communication 3 because the example was a single stakeholder."
        ),
        interviewer="Priya",
    )
    assert good["score"] == 100 and good["evidence_ratio_pct"] == 100.0 and good["interviewer"] == "Priya"


def test_check_feedback_bias_rejects_empty():
    with pytest.raises(ToolError):
        call("check_feedback_bias", feedback="")
