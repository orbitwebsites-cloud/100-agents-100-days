"""Meeting Ops tools — the reference test file every agent's tests follow."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("meeting-ops")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_transcript_stats_finds_speakers_and_commitments():
    out = call("transcript_stats", transcript="Sam: I'll ship the fix by Friday.\nAna: Sounds good.\nSam: Also lunch was great.")
    assert out["speakers"][0] == "Sam"
    assert [c["line"] for c in out["commitment_candidates"]] == [1]


def test_transcript_stats_rejects_empty():
    with pytest.raises(ToolError):
        call("transcript_stats", transcript="   ")


@pytest.mark.parametrize(
    "phrase,due",
    [
        ("by Friday", "2026-09-25"),  # meeting on Wed 2026-09-23
        ("end of next week", "2026-10-02"),
        ("tomorrow", "2026-09-24"),
        ("in 2 weeks", "2026-10-07"),
        ("next Tuesday", "2026-09-29"),  # Tuesday of next calendar week, not 13 days out
        ("EOD Thursday", "2026-09-24"),  # a named weekday beats "EOD"
        ("by end of day Thursday", "2026-09-24"),
        ("Tuesday next week", "2026-09-29"),
        ("by October 15th", "2026-10-15"),
        ("this week", "2026-09-25"),
        ("once it is merged", None),
        ("EOD", "2026-09-23"),
        ("sometime", None),
    ],
)
def test_resolve_due_dates(phrase, due):
    out = call("resolve_due_dates", phrases=[phrase], meeting_date="2026-09-23")
    assert out["resolved"][0]["due"] == due


def test_format_action_items_flags_dupes_vague_and_missing():
    out = call(
        "format_action_items",
        items=[
            {"task": "will ship the checkout fix", "owner": "Sam", "due": "2026-09-25"},
            {"task": "ship checkout fix", "owner": "Sam"},
            {"task": "look into pricing"},
        ],
    )
    assert out["items"][0]["task"] == "Ship the checkout fix"
    assert any("duplicate" in i for i in out["items"][1]["issues"])
    assert any("vague" in i for i in out["items"][2]["issues"])
    assert out["ready_to_file"] is False


def test_bad_arguments_raise_clean_error():
    with pytest.raises(ToolError):
        A.get_tool("resolve_due_dates").call({"phrases": 5})


def test_transcript_stats_skips_header_labels_and_reads_otter_export():
    otter = "Sync - Oct 7, 2026\nAttendees: Ana, Bo\n\nAna Diaz  0:00\nI'll send the deck by Friday.\n\nBo Kim  0:12\nLet's go with Okta. Actually no, scratch that.\n"
    out = call("transcript_stats", transcript=otter)
    assert sorted(out["speakers"]) == ["Ana Diaz", "Bo Kim"]
    assert "Attendees" not in out["talk_share_pct"]
    assert out["detected_meeting_date"] == "2026-10-07"
    assert [c["speaker"] for c in out["commitment_candidates"]][0] == "Ana Diaz"
    assert out["decision_candidates"] and out["retractions"]


def test_next_weekday_flags_ambiguity_when_nearer_day_exists():
    out = call("resolve_due_dates", phrases=["next Thursday"], meeting_date="2026-09-28")  # a Monday
    r = out["resolved"][0]
    assert r["due"] == "2026-10-08" and r["confirm"] is True
