"""Feedback Analyzer tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("feedback-analyzer")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_score_survey_nps_math_and_segments():
    scores = [10, 9, 9, 8, 7, 6, 5, 10, 9, 3]  # 5 promoters, 2 passives, 3 detractors
    out = call("score_survey", scores=scores, survey="nps", segments=["a"] * 10, previous_score=10)
    assert out["score"] == 20.0
    assert out["promoters_pct"] == 50.0 and out["detractors_pct"] == 30.0
    assert out["moe"] == 54.0  # 1.96*sqrt((.25+.21+.3)/10)*100
    assert out["by_segment"]["a"]["reportable"] is False
    assert out["delta"] == {"previous": 10.0, "change": 10.0, "beats_noise": False}


def test_score_survey_csat():
    out = call("score_survey", scores=[5, 4, 4, 3, 2, 5, 1, 4], survey="csat")
    assert out["score"] == 62.5 and out["mean"] == 3.5


def test_score_survey_rejects_out_of_range():
    with pytest.raises(ToolError):
        call("score_survey", scores=[11, 3], survey="nps")
    with pytest.raises(ToolError):
        call("score_survey", scores=[5, 5], survey="nps", segments=["a"])


def test_count_themes_counts_responses_and_sentiment():
    out = call(
        "count_themes",
        responses=[
            {"text": "The app is slow and crashes constantly. Slow slow slow.", "score": 3, "segment": "SMB"},
            {"text": "Love it, so easy to use", "score": 10, "segment": "ENT"},
            {"text": "Too expensive for what it does", "score": 5, "segment": "SMB"},
            {"text": "Wonderful support team", "score": 9},
            {"text": "meh", "score": 7},
        ],
    )
    themes = {t["theme"]: t for t in out["themes"]}
    assert themes["performance"]["responses"] == 1 and themes["performance"]["share_pct"] == 20.0
    assert themes["performance"]["sentiment"] == -1.0
    assert themes["performance"]["by_band"] == {"detractor": 1}
    assert themes["support"]["sentiment"] > 0
    assert out["untagged"] == 1 and out["untagged_pct"] == 20.0


def test_count_themes_rejects_bad_taxonomy():
    with pytest.raises(ToolError):
        call("count_themes", responses=[{"text": "hi"}], taxonomy={"x": []})


def test_driver_analysis_gap_and_detractor_share():
    rows = [{"themes": ["bugs"], "score": 3}] * 5 + [{"themes": [], "score": 9}] * 5 + [{"themes": ["bugs"], "score": 8}] * 5
    out = call("driver_analysis", tagged_rows=rows, min_n=5)
    d = out["drivers"][0]
    assert d["theme"] == "bugs" and d["n"] == 10
    assert d["mean_with"] == 5.5 and d["mean_without"] == 9.0 and d["gap"] == -3.5
    assert d["detractor_rate_pct"] == 50.0 and d["detractor_share_pct"] == 100.0
    assert out["negative_drivers"] == ["bugs"]


def test_driver_analysis_rejects_missing_score():
    with pytest.raises(ToolError):
        call("driver_analysis", tagged_rows=[{"themes": ["a"]}, {"themes": ["b"], "score": 5}])


def test_prioritize_fixes_ranks_by_share_severity_reach():
    out = call(
        "prioritize_fixes",
        fixes=[
            {"fix": "Fix export crash", "responses": 40, "severity": 3, "reach": 3, "effort": 2},
            {"fix": "Dark mode", "responses": 60, "severity": 1, "reach": 3, "effort": 1},
        ],
        total_responses=200,
    )
    assert out["ranked"][0]["fix"] == "Fix export crash" and out["ranked"][0]["priority"] == 20.0
    assert out["ranked"][1]["priority"] == 10.0
    assert out["top_3_cover_pct"] == 50.0


def test_prioritize_fixes_rejects_bad_total():
    with pytest.raises(ToolError):
        call("prioritize_fixes", fixes=[{"fix": "x", "responses": 1, "severity": 1, "reach": 1}], total_responses=0)


def test_count_themes_matches_plurals_and_keeps_export_out_of_integrations():
    out = call("count_themes", responses=[
        {"text": "Costs more than Trello", "score": 7},
        {"text": "Export to CSV crashes every time", "score": 2},
        {"text": "Takes 10 seconds to load a project", "score": 5},
        {"text": "No Salesforce integration", "score": 4},
    ])
    tagged = {r["i"]: set(r["themes"]) for r in out["tagged_rows"]}
    assert "pricing" in tagged[0]
    assert "integrations" not in tagged[1] and "bugs" in tagged[1]
    assert "performance" in tagged[2]
    assert "integrations" in tagged[3]
    assert [r["score"] for r in out["tagged_rows"]] == [7.0, 2.0, 5.0, 4.0]


def test_driver_analysis_accepts_count_themes_rows_and_skips_unscored():
    rows = [{"themes": ["bugs"], "score": 2}, {"themes": ["bugs"], "score": 3}, {"themes": [], "score": 9}, {"themes": [], "score": 10}, {"themes": ["bugs"], "score": None}]
    out = call("driver_analysis", tagged_rows=rows, min_n=2)
    assert out["skipped_unscored"] == 1 and out["drivers"][0]["gap"] == -7.0
