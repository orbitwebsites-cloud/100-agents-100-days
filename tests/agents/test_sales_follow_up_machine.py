"""Follow-Up Machine tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("follow-up-machine")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_cadence_dates_business_days_and_channels():
    out = call("cadence_dates", last_contact="2026-09-18", stage="proposal", today="2026-09-18")  # Friday
    dates_ = [t["date"] for t in out["touches"]]
    assert dates_[:4] == ["2026-09-22", "2026-09-28", "2026-10-07", "2026-10-23"]
    assert [t["business_days_after_previous"] for t in out["touches"]] == [2, 4, 7, 12, 12]
    assert out["touches"][-1]["channel"] == "breakup email"
    assert all(t["weekday"] not in ("Sat", "Sun") for t in out["touches"])
    promised = call("cadence_dates", last_contact="2026-09-18", stage="proposal", promised_date="2026-10-14", today="2026-09-18")
    assert promised["touches"][0]["date"] == "2026-10-15"
    hol = call("cadence_dates", last_contact="2026-11-24", stage="negotiation", touches=1, holidays=["2026-11-25"], today="2026-11-24")
    assert hol["touches"][0]["date"] == "2026-11-26"


def test_cadence_dates_bad_input():
    with pytest.raises(ToolError):
        call("cadence_dates", last_contact="yesterday")
    with pytest.raises(ToolError):
        call("cadence_dates", last_contact="2026-09-18", touches=9)
    with pytest.raises(ToolError):
        call("cadence_dates", last_contact="2026-09-18", promised_date="2026-09-01", today="2026-09-18")
    with pytest.raises(ToolError):
        call("cadence_dates", last_contact="2026-09-18", today="2026-09-10")  # last contact after today


def test_next_touch_decision_branches():
    now = call("next_touch_decision", stage="proposal", last_contact="2026-09-18", touches_since_reply=1, today="2026-09-27")
    assert now["decision"] == "follow_up_now" and now["business_days_since_last_touch"] == 5
    wait = call("next_touch_decision", stage="proposal", last_contact="2026-09-25", touches_since_reply=1, today="2026-09-27")
    assert wait["decision"] == "wait" and wait["wait_until"] == "2026-10-01"
    breakup = call("next_touch_decision", stage="proposal", last_contact="2026-09-25", last_reply="2026-09-01", touches_since_reply=4, today="2026-09-27")
    assert breakup["decision"] == "breakup" and breakup["silent_days"] == 26
    promised = call("next_touch_decision", stage="demo", last_contact="2026-09-20", promised_date="2026-10-14", today="2026-09-27")
    assert promised["decision"] == "wait" and promised["wait_until"] == "2026-10-15"
    close = call("next_touch_decision", stage="discovery", last_contact="2026-09-20", last_reply="2026-08-01", touches_since_reply=6, today="2026-09-27")
    assert close["decision"] == "close_and_nurture"


def test_next_touch_decision_bad_input():
    with pytest.raises(ToolError):
        call("next_touch_decision", stage="proposal", last_contact="2026-12-01", today="2026-09-27")
    with pytest.raises(ToolError):
        call("next_touch_decision", stage="proposal", last_contact="2026-09-01", touches_since_reply=99)


def test_score_follow_up_bad_and_good():
    bad = call("score_follow_up", email="Hi Tom, just checking in to see if you had a chance to look at the proposal. I haven't heard back. Let me know!")
    assert bad["score"] < 40 and bad["grade"] == "rewrite"
    assert "just checking" in bad["cliches"] and "haven't heard back" in bad["guilt_phrases"]
    assert any("no new value" in f for f in bad["fixes"])
    good = call("score_follow_up", email="Hi Tom, you asked on the call how long onboarding takes — Northwind went live in 11 days. Is a 2-week pilot still worth exploring?")
    assert good["score"] == 100 and good["words"] == 24 and good["questions"] == 1  # "2-week" is one word
    breakup = call("score_follow_up", email="Tom — I'll close the file on this for now. Door's open whenever the timing changes. Anything I should pass along to whoever picks this up?", kind="breakup")
    assert breakup["score"] >= 80
    no_out = call("score_follow_up", email="Tom, is this still a priority?", kind="breakup")
    assert any("easy out" in f for f in no_out["fixes"])


def test_score_follow_up_bad_input():
    with pytest.raises(ToolError):
        call("score_follow_up", email="")
    with pytest.raises(ToolError):
        call("score_follow_up", email="hi", kind="nudge")


def test_stale_deals_thresholds_and_priority():
    out = call(
        "stale_deals",
        deals=[
            {"name": "Acme", "stage": "Proposal Sent", "amount": 50000, "last_activity": "2026-09-10"},
            {"name": "Beta", "stage": "discovery", "amount": 8000, "last_activity": "2026-09-25"},
            {"name": "Gamma", "stage": "negotiation", "amount": 20000, "last_activity": "2026-09-11", "touches_since_reply": 5, "close_date": "2026-09-20"},
        ],
        today="2026-09-27",
    )
    rows = {r["name"]: r for r in out["deals"]}
    assert rows["Acme"]["quiet_business_days"] == 11 and rows["Acme"]["threshold_business_days"] == 5 and rows["Acme"]["status"] == "at_risk"
    assert rows["Beta"]["status"] == "fresh" and rows["Beta"]["action"] == "none"
    assert rows["Gamma"]["status"] == "at_risk" and rows["Gamma"]["action"] == "breakup email" and "close date passed" in rows["Gamma"]["flags"]
    assert [r["name"] for r in out["chase_today"]] == ["Acme", "Gamma"]
    assert out["stale_amount"] == 70000.0 and out["counts"]["at_risk"] == 2
    override = call("stale_deals", deals=[{"name": "B", "stage": "discovery", "amount": 1, "last_activity": "2026-09-24"}], today="2026-09-27", thresholds={"discovery": 1})
    assert override["deals"][0]["status"] == "stale"


def test_stale_deals_bad_input():
    with pytest.raises(ToolError):
        call("stale_deals", deals=[{"name": "A", "stage": "demo", "amount": 1}])
    with pytest.raises(ToolError):
        call("stale_deals", deals=[{"name": "A", "stage": "demo", "amount": 1, "last_activity": "2027-01-01"}], today="2026-09-27")


def test_cadence_continues_from_touches_done_and_never_dates_the_past():
    out = call("cadence_dates", last_contact="2026-09-21", stage="proposal", touches=3, promised_date="2026-09-24", today="2026-09-28", touches_done=1)
    t = out["touches"]
    assert [x["touch"] for x in t] == [2, 3, 4]
    assert [x["date"] for x in t] == ["2026-09-28", "2026-10-07", "2026-10-23"]
    assert [x["channel"] for x in t] == ["phone", "linkedin", "breakup email"]
    assert out["overdue"] and "2026-09-25" in out["overdue"]


def test_score_follow_up_counts_every_ask_not_just_question_marks():
    out = call("score_follow_up", email="Tom, here's the 19-day rollout plan you asked for. Let me know if you have any questions. Happy to hop on a call. Does Tuesday work?")
    assert out["asks"] == 3 and out["questions"] == 1
    assert any("3 asks" in f for f in out["fixes"])
