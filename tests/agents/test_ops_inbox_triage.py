"""Inbox Triage tools — priority scoring, ask extraction, template filling, session planning."""

import pytest

from hundred.agents.ops import inbox_triage
from hundred.core import ToolError

A = inbox_triage.AGENT

EMAILS = [
    {"id": "1", "from": "Priya Shah <priya@acme.com>", "to": "me@acme.com", "subject": "Board deck numbers", "body": "Can you send me the Q3 numbers by EOD tomorrow? Also, is the churn figure final?", "received": "2026-09-27"},
    {"id": "2", "from": "newsletter@saasweekly.io", "to": "me@acme.com", "subject": "This week in SaaS", "body": "Top stories... Unsubscribe | View in browser", "received": "2026-09-27"},
    {"id": "3", "from": "dan@vendor.com", "to": "sam@acme.com", "cc": "me@acme.com", "subject": "FYI: updated timeline", "body": "Sharing the revised plan for visibility.", "received": "2026-09-26"},
    {"id": "4", "from": "notifications@github.com", "to": "me@acme.com", "subject": "[repo] New sign-in from a new device", "body": "A new sign-in was detected.", "received": "2026-09-27"},
    {"id": "5", "from": "lee@customer.io", "to": "me@acme.com", "subject": "Renewal pricing", "body": "We need the renewal quote before our budget meeting on Friday. Could you confirm the pricing?", "received": "2026-09-23"},
]


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_score_priority_orders_and_classifies():
    out = call("score_priority", emails=EMAILS, me="me@acme.com", vips=["priya@acme.com"], as_of="2026-09-28")
    by = {r["id"]: r for r in out["emails"]}
    assert out["emails"][0]["id"] in ("1", "5") and by["1"]["action"] == "Reply now" and "VIP sender" in by["1"]["reasons"]
    assert by["1"]["deadline"] == "2026-09-28" and by["1"]["quadrant"].startswith("Q1")
    assert by["2"]["action"] == "Unsubscribe or digest" and by["2"]["score"] < 25
    assert by["3"]["score"] < by["5"]["score"] and "you are only CC'd" in by["3"]["reasons"]
    assert by["4"]["action"] == "Archive"
    assert by["5"]["deadline"] == "2026-09-25" and "money/contract topic" in by["5"]["reasons"] and by["5"]["action"] == "Reply now"
    assert by["5"]["age_days"] == 5
    assert out["total_estimated_minutes"] == sum(r["estimated_minutes"] for r in out["emails"])
    with pytest.raises(ToolError):
        call("score_priority", emails=[{"id": "x", "received": "yesterday"}])


def test_extract_asks_questions_requests_deadlines():
    body = """Hi Sam,

Could you send the signed SOW by Friday? What's the earliest kickoff date you can do?
Also please confirm whether the SLA is 99.9%. We need your approval on the budget before EOD.

Thanks,
Lee

On Mon, Sep 21, 2026 Sam wrote:
> Can you resend the old contract?
"""
    out = call("extract_asks", body=body, as_of="2026-09-23", received="2026-09-23")
    assert out["counts"]["questions"] == 2 and out["counts"]["requests"] == 2
    assert out["quoted_history_dropped"] is True
    assert all("old contract" not in a["text"] for a in out["asks"])
    dl = [a["deadline"]["date"] for a in out["asks"] if a["deadline"]]
    assert "2026-09-25" in dl and "2026-09-23" in dl
    assert out["earliest_deadline"]["date"] == "2026-09-23"
    assert out["counts"]["decisions_needed"] == 1 and out["reply_order"][0] == 4
    fyi = call("extract_asks", body="Sharing the deck for visibility. No action needed.")
    assert fyi["asks"] == [] and "FYI" in fyi["verdict"]
    with pytest.raises(ToolError):
        call("extract_asks", body="   ")


def test_fill_reply_template_placeholders_and_checks():
    out = call(
        "fill_reply_template",
        template="Hi {{name}}, thanks for the note. I can't make [date], but I'm free {alt_date}. Does that work? Best, <sender>",
        fields={"name": "Priya", "alt-date": "Thursday 2pm", "unused": "x"},
    )
    assert out["reply"].startswith("Hi Priya, thanks") and "Thursday 2pm" in out["reply"]
    assert out["unfilled_placeholders"] == ["date", "sender"] and out["unused_fields"] == ["unused"]
    assert out["ready_to_send"] is False and out["sentences"] == 4
    ok = call("fill_reply_template", template="Hi {name}, yes — I'll send it by {day}. Thanks!", fields={"name": "Lee", "day": "Friday"})
    assert ok["ready_to_send"] is True and ok["fixes"] == []
    with pytest.raises(ToolError):
        call("fill_reply_template", template="Hi {name}", fields="name=Lee")


def test_plan_session_two_minute_rule_and_deferral():
    out = call(
        "plan_session",
        items=[
            {"id": "a", "action": "Reply now", "minutes": 15, "score": 90},
            {"id": "b", "action": "Reply today", "minutes": 2, "score": 50},
            {"id": "c", "action": "Reply now", "minutes": 15, "score": 80, "deadline": "2026-09-29"},
            {"id": "d", "action": "Schedule", "minutes": 10, "score": 40},
            {"id": "e", "action": "Archive", "minutes": 0, "score": 5},
        ],
        minutes_available=30,
        as_of="2026-09-28",  # Monday
    )
    # 2-min item first; within "Reply now" the deadline-bound item beats the higher score; d fits in what's left
    assert [p["id"] for p in out["plan"]] == ["b", "c", "d"]
    assert out["archive_first"]["ids"] == ["e"] and out["minutes_planned"] == 27
    deferred = {d["id"]: d for d in out["deferred"]}
    assert set(deferred) == {"a"} and "reply-now" in deferred["a"]["risk"]
    assert "a" in out["deferred_at_risk"] and out["inbox_zero_eta"] == "2026-09-29"
    with pytest.raises(ToolError):
        call("plan_session", items=[{"id": "a", "action": "Ignore", "minutes": 5}], minutes_available=30)


def test_bad_arguments_raise_clean_error():
    with pytest.raises(ToolError):
        A.get_tool("plan_session").call({"items": [], "minutes_available": 30})
