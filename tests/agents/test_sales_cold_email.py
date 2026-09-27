"""Cold Email Closer tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("cold-email")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_score_subject_line_ranks_specific_over_dead_and_spammy():
    out = call("score_subject_line", subjects=["warehouse routing at Acme", "quick question", "FREE DEMO!!!"])
    assert out["best"] == "warehouse routing at Acme"
    by = {r["subject"]: r for r in out["results"]}
    assert by["warehouse routing at Acme"]["score"] >= 90
    assert by["quick question"]["score"] < 70 and any("dead" in f for f in by["quick question"]["fixes"])
    assert by["FREE DEMO!!!"]["score"] < 50
    assert any("spam" in f for f in by["FREE DEMO!!!"]["fixes"]) and any("CAPS" in f for f in by["FREE DEMO!!!"]["fixes"])
    assert by["warehouse routing at Acme"]["chars"] == 25 and by["warehouse routing at Acme"]["mobile_safe"] is True


def test_score_subject_line_rejects_empty_and_too_many():
    with pytest.raises(ToolError):
        call("score_subject_line", subjects=[])
    with pytest.raises(ToolError):
        call("score_subject_line", subjects=["   "])


GOOD_BODY = (
    "Hi Dana,\n\nSaw Acme opened a third warehouse in Ohio last month. Most ops leads tell us the "
    "routing spreadsheet breaks around site three.\n\nBrightline cut Northwind's dispatch time by 22% in "
    "six weeks.\n\nWorth a look?"
)


def test_audit_email_body_scores_good_email_and_counts():
    out = call("audit_email_body", body=GOOD_BODY)
    assert out["score"] >= 80 and out["grade"] == "send"
    assert out["words"] == 37
    assert out["cta_count"] == 1 and out["cta_type"] == "interest"
    assert out["links"] == 0 and out["spam_words"] == [] and out["unresolved_tokens"] == []


def test_audit_email_body_flags_fluff_links_tokens_and_length():
    body = (
        "Hi {{first_name}}, I hope this email finds you well. My name is Bob and I am reaching out because "
        "our revolutionary platform is the leading provider of amazing solutions! Check https://x.com and "
        "https://y.com. " + "We help companies grow. " * 30
    )
    out = call("audit_email_body", body=body)
    assert out["score"] < 40
    assert "{{first_name}}" in out["unresolved_tokens"]
    assert out["links"] == 2
    assert "revolutionary" in out["spam_words"]
    assert any("fluff" in f for f in out["fixes"]) and any("words" in f for f in out["fixes"])


def test_audit_email_body_bad_input():
    with pytest.raises(ToolError):
        call("audit_email_body", body="")
    with pytest.raises(ToolError):
        call("audit_email_body", body="hi", step=0)


def test_check_personalization_levels():
    deep = call(
        "check_personalization",
        email="Hi Dana,\nSaw Acme opened a third warehouse in Ohio last month — congrats. Worth a look?",
        prospect={"first_name": "Dana", "company": "Acme", "trigger": "third warehouse in Ohio"},
    )
    assert deep["personalization_level"] == "deep" and deep["ready"] is True
    assert set(deep["fields_present"]) == {"first_name", "company", "trigger"}
    surface = call(
        "check_personalization",
        email="Hi {{first_name}},\nI wanted to reach out about Acme's growth. Worth a look?",
        prospect={"first_name": "Dana", "company": "Acme", "trigger": "Series B"},
    )
    assert surface["personalization_level"] == "surface"
    assert "{{first_name}}" in surface["unresolved_tokens"] and surface["ready"] is False
    assert "trigger" in surface["fields_missing"]


def test_check_personalization_bad_input():
    with pytest.raises(ToolError):
        call("check_personalization", email="", prospect={"first_name": "A"})


def test_schedule_sequence_skips_weekends_and_nudges_midweek():
    out = call("schedule_sequence", start_date="2026-10-02", gaps_days=[0, 3, 4, 5, 7])  # Friday start
    steps = out["steps"]
    assert len(steps) == 5
    assert all(s["weekday"] not in ("Sat", "Sun") for s in steps)
    assert steps[0]["date"] == "2026-10-01"  # Fri → nudged back to Thu
    assert steps[1]["date"] > steps[0]["date"] and steps[-1]["date"] == out["last_send"]
    holidays = call("schedule_sequence", start_date="2026-11-24", gaps_days=[0, 2], holidays=["2026-11-26"], prefer_midweek=False)
    assert holidays["steps"][1]["date"] == "2026-11-27"  # Thu holiday skipped → Fri


def test_schedule_sequence_bad_input():
    with pytest.raises(ToolError):
        call("schedule_sequence", start_date="next week")
    with pytest.raises(ToolError):
        call("schedule_sequence", start_date="2026-10-02", gaps_days=[0, 99])


def test_estimate_outreach_funnel_math():
    out = call("estimate_outreach", target_meetings=20, reply_rate_pct=2, positive_share_pct=50, meeting_rate_pct=60, steps=4, days_available=20)
    assert out["prospect_to_meeting_rate_pct"] == 0.6
    assert out["prospects_needed"] == 3334
    assert out["total_sends"] == 13336
    assert out["mailboxes_needed"] == 14
    assert out["list_size_incl_bounces"] > out["prospects_needed"]


def test_estimate_outreach_bad_input():
    with pytest.raises(ToolError):
        call("estimate_outreach", target_meetings=0)
    with pytest.raises(ToolError):
        call("estimate_outreach", target_meetings=5, reply_rate_pct=150)
