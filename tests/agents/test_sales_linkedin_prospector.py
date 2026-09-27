"""LinkedIn Prospector tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("linkedin-prospector")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_check_message_clean_note_and_limits():
    note = "Hi Sarah, your post on onboarding churn hit home — the 30-day cliff is exactly what we saw at Northwind. Curious how you're measuring it now."
    out = call("check_message", message=note, kind="connection_note")
    assert out["chars"] == len(note) and out["fits"] is True and out["score"] == 100
    long = call("check_message", message="x" * 320, kind="connection_note")
    assert long["fits"] is False and long["over_by"] == 20 and long["score"] < 70


def test_check_message_flags_pitch_template_link_and_inmail_subject():
    out = call("check_message", message="Hi! I would love to add you to my professional network. Our platform helps companies book a demo https://x.com", kind="connection_note")
    assert "our platform" in out["pitch_phrases"] and "demo" in out["pitch_phrases"]
    assert out["template_phrases"] == ["add you to my professional network"]
    assert out["links"] == 1 and out["grade"] == "rewrite"
    inmail = call("check_message", message="Saw your team is hiring three SDRs — how are you thinking about ramp time?", kind="inmail", subject="")
    assert any("subject" in f for f in inmail["fixes"])


def test_check_message_bad_input():
    with pytest.raises(ToolError):
        call("check_message", message="", kind="message")
    with pytest.raises(ToolError):
        call("check_message", message="hello", kind="tweet")


PROFILE = """Sarah Lee | Helping SaaS teams scale onboarding
VP Customer Success at Acme
Jan 2026 - Present · 9 mos
Director CS at Beta Corp
Mar 2021 - Dec 2025
Post: The 30-day onboarding cliff is real - here is what we changed
12 mutual connections
University of Michigan, MBA"""


def test_extract_hooks_ranks_and_computes_tenure():
    out = call("extract_hooks", profile_text=PROFILE, today="2026-09-27", my_school="University of Michigan")
    assert out["months_in_current_role"] == 8
    types = [h["type"] for h in out["hooks"]]
    assert types[0] == "recent_post"
    assert "first_year" in types and "mutual_connection" in types and "shared_school" in types and "headline_claim" in types
    new = call("extract_hooks", profile_text="Head of Ops at Zed\nAug 2026 - Present", today="2026-09-27")
    assert new["months_in_current_role"] == 1 and new["best_hook"]["type"] == "new_role"


def test_extract_hooks_bad_input():
    with pytest.raises(ToolError):
        call("extract_hooks", profile_text=" ")


def test_plan_sequence_dates_and_cap_warning():
    out = call("plan_sequence", start_date="2026-10-03", prospects=150)  # Saturday start → Monday
    assert out["start"] == "2026-10-05"
    assert out["touches"][0]["date"] == "2026-10-05" and out["touches"][1]["date"] == "2026-10-06"
    assert all(t["weekday"] not in ("Sat", "Sun") for t in out["touches"])
    assert out["invites_per_day"] == 20 and out["business_days_to_enrol_all"] == 8
    assert len(out["enrolment_cohorts"]) == 8 and out["enrolment_cohorts"][-1]["prospects"] == 10
    assert any("exceed the weekly cap" in w for w in out["warnings"])


def test_plan_sequence_bad_input():
    with pytest.raises(ToolError):
        call("plan_sequence", start_date="2026-10-05", prospects=0)
    with pytest.raises(ToolError):
        call("plan_sequence", start_date="soon")


def test_capacity_plan_math():
    out = call("capacity_plan", target_meetings=12)
    assert out["invite_to_meeting_rate_pct"] == 2.62
    assert out["invites_needed"] == 458
    assert out["weeks_needed"] == 5 and out["accounts_for_one_month"] == 2
    two = call("capacity_plan", target_meetings=12, accounts=2)
    assert two["weeks_needed"] == 3


def test_capacity_plan_bad_input():
    with pytest.raises(ToolError):
        call("capacity_plan", target_meetings=0)
    with pytest.raises(ToolError):
        call("capacity_plan", target_meetings=5, acceptance_rate_pct=0)


def test_connection_note_limit_depends_on_account_type():
    note = "Rachel, " + "x" * 206  # 214 chars
    prem = call("check_message", message=note, kind="connection_note")
    free = call("check_message", message=note, kind="connection_note", premium=False)
    assert prem["fits"] is True and prem["limit"] == 300
    assert free["fits"] is False and free["limit"] == 200 and free["over_by"] == 14


def test_headline_claim_found_below_the_name_line():
    out = call("extract_hooks", profile_text="Rachel Okonkwo\nHelping mid-market SaaS teams build pipeline | VP Marketing", today="2026-09-28")
    assert any(h["type"] == "headline_claim" for h in out["hooks"])
