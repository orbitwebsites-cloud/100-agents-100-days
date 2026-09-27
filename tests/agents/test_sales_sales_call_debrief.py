"""Call Debrief tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("sales-call-debrief")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


TRANSCRIPT = """Sam: Thanks for joining. How is dispatch handled today?
Dana: It is a spreadsheet, honestly. We lose about 30 hours a week on it and it costs us maybe 20k a month in overtime. When we roll this out we would need it live before Q4 and my CFO wants to see the numbers, so I'll loop in our CFO.
Sam: Makes sense. I'll send the proposal by Thursday and let's schedule the CFO review for next Tuesday.
Dana: Sounds good, that works.
Sam: Um, great, and, um, pricing is per seat, uh, how many seats?
Dana: About 40. What does onboarding look like?"""


def test_call_metrics_talk_share_and_fillers():
    out = call("call_metrics", transcript=TRANSCRIPT, rep_name="Sam")
    assert out["rep"] == "Sam"
    assert out["talk_share_pct"]["Dana"] == 62.2 and out["rep_talk_pct"] == 37.8
    assert out["rep_questions"] == 2
    assert out["rep_top_fillers"] == {"um": 2, "uh": 1}
    assert out["turns"] == {"Sam": 3, "Dana": 3}
    assert out["benchmark_rep_talk_pct"] == "43-46"
    demo = call("call_metrics", transcript=TRANSCRIPT, rep_name="Sam", call_type="demo")
    assert demo["benchmark_rep_talk_pct"] == "60-65"


def test_call_metrics_bad_input():
    with pytest.raises(ToolError):
        call("call_metrics", transcript="no speaker labels here")
    with pytest.raises(ToolError):
        call("call_metrics", transcript=TRANSCRIPT, call_type="karaoke")


def test_detect_next_steps_resolves_dates_and_agreement():
    out = call("detect_next_steps", transcript=TRANSCRIPT, call_date="2026-09-23", rep_name="Sam")  # Wednesday
    assert out["next_step_agreed"] is True
    first = out["agreed_next_steps"][0]
    assert first["speaker"] == "Sam" and first["resolved_date"] == "2026-09-24"
    assert "2026-10-06" in first["all_resolved_dates"]  # next Tuesday (same convention as meeting-ops)
    assert first["prospect_agreed"] is True
    none = call("detect_next_steps", transcript="Sam: Great chat.\nDana: Yes, thanks.", call_date="2026-09-23")
    assert none["next_step_agreed"] is False and "No next step agreed" in none["verdict"]
    intention = call("detect_next_steps", transcript="Sam: I'll send over the proposal sometime.\nDana: Hmm.", call_date="2026-09-23")
    assert intention["next_step_agreed"] is False and intention["intentions"] == [] and intention["candidates"][0]["quality"] == "mention"


def test_detect_next_steps_bad_input():
    with pytest.raises(ToolError):
        call("detect_next_steps", transcript="  ")
    with pytest.raises(ToolError):
        call("detect_next_steps", transcript=TRANSCRIPT, call_date="Wednesday")


def test_buying_signals_temperature():
    hot = call("buying_signals", transcript=TRANSCRIPT, rep_name="Sam")
    assert hot["temperature"] == "hot"
    assert {"timeline stated", "stakeholders introduced", "pain quantified", "implementation questions", "future-state language"} <= set(hot["positive_types"])
    assert hot["negative_signals"] == []
    cold = call("buying_signals", transcript="Sam: Thoughts?\nDana: Honestly we're just exploring and there's no budget this year.", rep_name="Sam")
    assert cold["temperature"] == "cold" and "no budget (strong)" in cold["strong_negatives"]
    assert all(s["speaker"] == "Dana" for s in cold["negative_signals"])
    with pytest.raises(ToolError):
        call("buying_signals", transcript="")


def test_map_crm_fields_hubspot_and_salesforce():
    out = call(
        "map_crm_fields",
        fields={"name": "Acme - Routing", "stage": "proposal", "amount": "48,000", "close_date": "2026-12-15", "next_step": "Send proposal", "next_step_date": "2026-09-25", "competitors": ["Onfleet", "spreadsheet"]},
        crm="hubspot",
        call_date="2026-09-23",
    )
    assert out["payload"]["dealstage"] == "decisionmakerboughtin"
    assert out["payload"]["amount"] == 48000.0 and out["payload"]["closedate"] == "2026-12-15"
    assert out["payload"]["competitors"] == "Onfleet; spreadsheet"
    assert out["ready"] is True and out["missing_required"] == []
    sf = call("map_crm_fields", fields={"stage": "negotiation", "close_date": "2026-01-01", "next_step": "follow up"}, crm="salesforce", call_date="2026-09-23")
    assert sf["payload"]["StageName"] == "Negotiation/Review"
    assert any("before the call date" in i for i in sf["issues"])
    assert "Name" in sf["missing_required"] and sf["ready"] is False
    assert any("no date" in i for i in sf["issues"])


def test_map_crm_fields_bad_input():
    with pytest.raises(ToolError):
        call("map_crm_fields", fields={"stage": "demo"}, crm="zoho")
    with pytest.raises(ToolError):
        call("map_crm_fields", fields={}, crm="hubspot")
