"""Keyword Strategist tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("keyword-strategist")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


@pytest.mark.parametrize(
    "kw,intent",
    [
        ("best crm software", "commercial"),
        ("buy running shoes", "transactional"),
        ("how to make cold brew", "informational"),
        ("hubspot login", "navigational"),
        ("plumber near me", "local"),
        ("crm software", "transactional"),
        ("free crm", "transactional"),
        ("crm vs erp", "commercial"),
    ],
)
def test_classify_intent(kw, intent):
    out = call("classify_intent", keywords=[kw], brands=["hubspot"])
    assert out["rows"][0]["intent"] == intent


def test_classify_intent_confidence_and_counts():
    out = call("classify_intent", keywords=["crm", "best crm software", "buy crm"])
    assert out["rows"][0]["confidence"] < 0.6
    assert out["low_confidence"] == ["crm"]
    assert out["counts"] == {"informational": 1, "commercial": 1, "transactional": 1}
    with pytest.raises(ToolError):
        call("classify_intent", keywords=[])


def test_cluster_keywords_groups_and_splits_by_intent():
    kws = ["cold brew coffee", "how to make cold brew coffee", "cold brew coffee recipe", "buy cold brew coffee", "best espresso machine", "espresso machine reviews"]
    vols = [5000, 3000, 2000, 400, 9000, 1200]
    out = call("cluster_keywords", keywords=kws, volumes=vols)
    heads = {c["head"]: c for c in out["clusters"]}
    assert out["cluster_count"] == 3
    assert set(heads["cold brew coffee"]["members"]) == {"cold brew coffee", "how to make cold brew coffee", "cold brew coffee recipe"}
    assert heads["buy cold brew coffee"]["intent"] == "transactional"
    assert heads["buy cold brew coffee"]["split_from"] == "cold brew coffee"
    assert heads["best espresso machine"]["total_volume"] == 10200
    assert out["clusters"][0]["head"] == "best espresso machine"  # ordered by volume


def test_cluster_keywords_validation():
    with pytest.raises(ToolError):
        call("cluster_keywords", keywords=["only one"])
    with pytest.raises(ToolError):
        call("cluster_keywords", keywords=["a b", "a c"], volumes=[1])
    with pytest.raises(ToolError):
        call("cluster_keywords", keywords=["a b", "a c"], min_similarity=0.05)


def test_score_opportunities_ranks_and_flags():
    rows = [
        {"keyword": "best crm", "volume": 50000, "difficulty": 90, "cpc": 12, "cluster": "crm"},
        {"keyword": "crm for realtors", "volume": 800, "difficulty": 22, "cpc": 5, "cluster": "crm"},
        {"keyword": "what is crm", "volume": 10000, "difficulty": 45},
    ]
    out = call("score_opportunities", rows=rows, site_stage="new", current_positions={"what is crm": 12})
    assert out["ranked"][0]["keyword"] == "crm for realtors"
    assert out["ranked"][-1]["keyword"] == "best crm"
    assert out["quick_wins"] == ["crm for realtors"]
    assert out["striking_distance"] == ["what is crm"]
    assert out["long_term"] == ["best crm"]
    assert out["clusters"][0]["cluster"] == "crm" and out["clusters"][0]["keywords"] == 2
    # established sites are punished less by difficulty
    est = call("score_opportunities", rows=rows, site_stage="established")
    best_new = next(r for r in out["ranked"] if r["keyword"] == "best crm")["score"]
    best_est = next(r for r in est["ranked"] if r["keyword"] == "best crm")["score"]
    assert best_est > best_new


def test_score_opportunities_bad_input():
    with pytest.raises(ToolError):
        call("score_opportunities", rows=[{"keyword": "x", "difficulty": 140}])
    with pytest.raises(ToolError):
        call("score_opportunities", rows=[{"keyword": "x"}], site_stage="huge")
    with pytest.raises(ToolError):
        call("score_opportunities", rows=[{"volume": 10}])


def test_keyword_gap_normalises_and_counts_competitors():
    out = call("keyword_gap", ours=["crm software", "crm for realtors"], competitors={"a": ["CRM softwares", "crm pricing", "free crm"], "b": ["free crm", "crm pricing"]})
    assert out["gap_count"] == 2
    assert out["high_confidence_gap"] == ["crm pricing", "free crm"]
    assert out["gap"][0]["competitor_count"] == 2
    assert out["unique_to_us"] == ["crm for realtors"]
    assert out["overlap"]["a"]["shared"] == 1
    with pytest.raises(ToolError):
        call("keyword_gap", ours=["a"], competitors={})
