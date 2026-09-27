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
        ("next Tuesday", "2026-10-06"),
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
