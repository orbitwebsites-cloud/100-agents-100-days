"""Interview Synthesizer tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("interview-synthesizer")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


NOTES = """Interview 1
I hate that exports lose all the formatting, so I just rebuild the report in Excel every week.
The onboarding was fine.
Interview 2
I would probably use a dashboard if you built one.
We pay $400 a month and honestly it's worth it.
Interview 3
If only the API had webhooks — I end up polling manually.
"""


def test_extract_signals_splits_interviews_and_ranks():
    out = call("extract_signals", notes=NOTES)
    assert out["interview_count"] == 3
    assert out["interviews_detected"] == ["P1", "P2", "P3"]
    top = out["quotes"][0]
    assert top["interview"] == "P1"
    assert {"pain", "workaround", "money_frequency"} <= set(top["signals"])
    hyp = [q for q in out["quotes"] if q["hypothetical"]]
    assert len(hyp) == 1 and "dashboard" in hyp[0]["quote"]
    assert out["hypothetical_count"] == 1
    assert "The onboarding was fine." not in [q["quote"] for q in out["quotes"]]


def test_extract_signals_rejects_bad_limit():
    with pytest.raises(ToolError):
        call("extract_signals", notes=NOTES, max_quotes=0)
    with pytest.raises(ToolError):
        call("extract_signals", notes="")


def test_cluster_observations_groups_similar():
    obs = [
        {"text": "exports lose formatting so I rebuild in Excel", "interview": "P1", "segment": "SMB"},
        {"text": "export formatting is lost, rebuild the report in excel weekly", "interview": "P4", "segment": "ENT"},
        {"text": "wants webhooks instead of polling the API", "interview": "P3", "segment": "SMB"},
    ]
    out = call("cluster_observations", observations=obs, threshold=0.25)
    assert out["cluster_count"] == 2
    big = out["clusters"][0]
    assert big["size"] == 2 and big["interview_count"] == 2
    assert big["segments"] == {"SMB": 1, "ENT": 1}
    assert "export" in big["keywords"]
    assert out["singletons"] == 1


def test_cluster_observations_rejects_bad_threshold():
    with pytest.raises(ToolError):
        call("cluster_observations", observations=[{"text": "a b c", "interview": "P1"}], threshold=0.95)


def test_tag_frequency_counts_interviews_not_mentions():
    tagged = [
        {"interview": "P1", "tags": ["exports", "exports", "pricing"], "segment": "SMB"},
        {"interview": "P2", "tags": ["exports"], "segment": "ENT"},
        {"interview": "P3", "tags": ["pricing"], "segment": "SMB"},
        {"interview": "P4", "tags": ["exports", "pricing"], "segment": "ENT"},
    ]
    out = call("tag_frequency", tagged=tagged)
    assert out["interview_count"] == 4
    top = out["tags"][0]
    assert top["tag"] == "exports" and top["interviews"] == 3 and top["mentions"] == 4
    assert top["interview_pct"] == 75.0
    assert top["by_segment"] == {"SMB": "1/2", "ENT": "2/2"}
    assert top["strength"] == "strong"
    assert out["co_occurrence"][0] == {"tags": ["exports", "pricing"], "interviews": 2}


def test_tag_frequency_rejects_missing_interview():
    with pytest.raises(ToolError):
        call("tag_frequency", tagged=[{"tags": ["x"]}])


def test_saturation_check_detects_plateau():
    out = call("saturation_check", tags_per_interview=[["a", "b"], ["a", "c"], ["b"], ["a"], ["c"]])
    assert out["total_themes"] == 3
    assert [c["new_themes"] for c in out["curve"]] == [2, 1, 0, 0, 0]
    assert out["saturated"] is True
    assert out["recommended_additional_interviews"] == 0


def test_saturation_check_not_saturated():
    out = call("saturation_check", tags_per_interview=[["a"], ["b"], ["c"], ["d"]])
    assert out["saturated"] is False
    assert out["recommended_additional_interviews"] >= 3


def test_saturation_check_rejects_bad_window():
    with pytest.raises(ToolError):
        call("saturation_check", tags_per_interview=[["a"]], window=1)


def test_extract_signals_catches_plain_spoken_pain_and_weekday_frequency():
    notes = "Interview 1\nOur biggest problem is approvals. Every Friday I spend three hours on the report.\n\nInterview 2\nApprovals are scattered and we lose track constantly. If there was a smarter search I might pay more."
    out = call("extract_signals", notes=notes)
    got = {q["quote"]: q["signals"] for q in out["quotes"]}
    assert "pain" in got["Our biggest problem is approvals."]
    assert "money_frequency" in got["Every Friday I spend three hours on the report."]
    assert "pain" in got["Approvals are scattered and we lose track constantly."]
    assert out["hypothetical_count"] == 1


def test_cluster_observations_links_inflected_short_notes():
    obs = [{"text": "Clients approve designs over email", "interview": "P2"},
           {"text": "Legal approvals happen in email threads", "interview": "P3"},
           {"text": "Approvals scattered across Slack and email threads", "interview": "P6"},
           {"text": "Rebuilds the weekly report in Excel", "interview": "P1"},
           {"text": "Rebuilds the weekly steering report by hand", "interview": "P4"}]
    out = call("cluster_observations", observations=obs)
    sizes = sorted((c["size"], tuple(c["interviews"])) for c in out["clusters"])
    assert sizes == [(2, ("P1", "P4")), (3, ("P2", "P3", "P6"))]
