"""Discovery Call Coach tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("discovery-call")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


TRANSCRIPT = """Sam (rep): Thanks for making time. How are you handling dispatch today?
Dana: Honestly it is a spreadsheet and it breaks every week. We lose about 30 hours a week fixing routes and it costs us maybe 20k a month in overtime. Really painful.
Sam: Got it. Do you have budget for this?
Dana: We have some allocated for Q4.
Sam: Great. So our product does routing, scheduling, dispatch, analytics, and reporting and integrates with everything, um, and it is used by 500 companies and um we were founded in 2015 and basically we are the leader.
Dana: Ok.
Sam: Who signs off on something like this? And when do you need it live?
Dana: My VP, by end of Q4.
Sam: Should we schedule a demo next Tuesday?"""


def test_meddpicc_scorecard_weights_gates_and_gaps():
    out = call(
        "meddpicc_scorecard",
        ratings={"identify_pain": {"score": 3, "evidence": "loses 30h/wk"}, "champion": 1, "metrics": 2, "economic_buyer": 0},
        target_stage="proposal",
    )
    assert out["raw_score"] == 6
    assert out["weighted_pct"] == 31.6
    assert out["gate_passed"] is False
    assert any("Champion" in b for b in out["blockers"])
    assert {g["element"] for g in out["gaps"]} >= {"Champion", "Economic buyer", "Competition"}
    strong = call("meddpicc_scorecard", ratings={k: {"score": 3, "evidence": "q"} for k in ["metrics", "economic_buyer", "decision_criteria", "decision_process", "paper_process", "identify_pain", "champion", "competition"]}, target_stage="commit")
    assert strong["weighted_pct"] == 100.0 and strong["gate_passed"] is True and strong["health"] == "strong"


def test_meddpicc_scorecard_bad_input():
    with pytest.raises(ToolError):
        call("meddpicc_scorecard", ratings={"metrics": 5})
    with pytest.raises(ToolError):
        call("meddpicc_scorecard", ratings={"bogus": 2})
    with pytest.raises(ToolError):
        call("meddpicc_scorecard", ratings={"metrics": 2}, target_stage="moon")


def test_analyze_transcript_metrics():
    out = call("analyze_transcript", transcript=TRANSCRIPT, rep_name="Sam")
    assert out["rep"] == "Sam"
    assert out["rep_talk_pct"] == 63.0
    assert out["rep_questions"] == 5
    assert out["question_types"]["open"] == 3 and out["question_types"]["closed"] == 2
    assert "pain" in out["topics_covered"] and "impact" in out["topics_covered"] and "next_step" in out["topics_covered"]
    assert "competition" in out["topics_missed"]
    assert any("talked 63.0%" in f for f in out["flags"])
    assert out["rep_fillers"].get("um") == 2


def test_analyze_transcript_bad_input():
    with pytest.raises(ToolError):
        call("analyze_transcript", transcript="   ")
    with pytest.raises(ToolError):
        call("analyze_transcript", transcript=TRANSCRIPT, rep_name="Nobody")


def test_plan_call_agenda_sums_to_duration():
    out = call("plan_call_agenda", duration_minutes=30)
    assert sum(b["minutes"] for b in out["agenda"]) == 30
    assert out["agenda"][-1]["end_min"] == 30
    assert out["agenda"][0]["block"].startswith("Open")
    assert out["target_questions"] == 12
    demo = call("plan_call_agenda", duration_minutes=45, call_type="demo_discovery", attendee_count=4)
    assert any("demo" in b["block"].lower() for b in demo["agenda"])
    assert sum(b["minutes"] for b in demo["agenda"]) == 45


def test_plan_call_agenda_bad_input():
    with pytest.raises(ToolError):
        call("plan_call_agenda", duration_minutes=5)
    with pytest.raises(ToolError):
        call("plan_call_agenda", duration_minutes=30, call_type="pitch")


def test_grade_questions_classifies_and_rewrites():
    out = call(
        "grade_questions",
        questions=[
            "Do you have a CRM?",
            "How are you handling onboarding today?",
            "You would agree that is a problem, right?",
            "What is the timeline? And who decides?",
        ],
    )
    types = [q["type"] for q in out["questions"]]
    assert types == ["closed", "open", "leading", "multi"]
    assert out["questions"][0]["rewrite"].startswith("How are you handling")
    assert out["counts"]["leading"] == 1 and out["counts"]["multi"] == 1
    assert out["meets_bar"] is False and out["open_pct"] == 25.0


def test_grade_questions_bad_input():
    with pytest.raises(ToolError):
        call("grade_questions", questions=[])
    with pytest.raises(ToolError):
        call("grade_questions", questions=["   "])


def test_topics_catch_everyday_wording_and_ignore_time_spend():
    t = ("Rep: How are reminders handled?\n"
         "Buyer: Honestly it's a mess, reminders drop when we're short-staffed and the managers spend hours on the phone. "
         "We want it live before the January reset. We had a demo from Weave in the spring.\n")
    out = call("analyze_transcript", transcript=t, rep_name="Rep")
    assert {"pain", "timeline", "competition"} <= set(out["topics_covered"])
    assert "budget" in out["topics_missed"]  # "spend hours" is not a budget conversation


def test_double_barrelled_joined_by_comma_and():
    out = call("grade_questions", questions=["Who else is involved, and what's your timeline?", "What's driving the timeline?"])
    assert [q["type"] for q in out["questions"]] == ["multi", "open"]


def test_minutes_from_timestamps_and_partial_transcript_warning():
    t = "[00:00] Rep: Hi, what prompted the call?\n[04:30] Buyer: We keep missing renewals and it costs us."
    out = call("analyze_transcript", transcript=t, rep_name="Rep")
    assert out["estimated_minutes"] == 4.5 and out["minutes_source"] == "timestamps"
    partial = call("analyze_transcript", transcript=t, rep_name="Rep", call_minutes=30)
    assert any("partial transcript" in f for f in partial["flags"])
    fill = call("analyze_transcript", transcript="Rep: I think you'll like the dashboard. It was, like, huge.\nBuyer: ok", rep_name="Rep")
    assert fill["rep_fillers"] == {"like": 1}


def test_compare_calls_averages_per_rep():
    a = "Sam: Is budget approved?\nDana: Not yet, we lose 10 hours a week on this.\nSam: Do you use Excel?\nDana: Yes."
    b = "Sam: How are you handling renewals today?\nLee: Manually in a spreadsheet, and it is slow and we missed two last quarter.\nSam: Right."
    c_ = "Ana: What prompted the call?\nBo: Our renewals process broke and it cost us a customer, so we want it live by Q1."
    out = call("compare_calls", calls=[{"transcript": a, "rep_name": "Sam"}, {"transcript": b, "rep_name": "Sam"}, {"transcript": c_, "rep_name": "Ana"}])
    one = call("analyze_transcript", transcript=a, rep_name="Sam")
    two = call("analyze_transcript", transcript=b, rep_name="Sam")
    sam = out["by_rep"]["Sam"]
    assert sam["calls"] == 2 and sam["avg_rep_talk_pct"] == round((one["rep_talk_pct"] + two["rep_talk_pct"]) / 2, 1)
    assert sam["avg_open_question_pct"] == round((one["open_question_pct"] + two["open_question_pct"]) / 2, 1)
    assert out["by_rep"]["Ana"]["calls"] == 1
    with pytest.raises(ToolError):
        call("compare_calls", calls=[{"transcript": a, "rep_name": "Sam"}])
