"""Persona Builder tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("persona-builder")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


ROWS = [
    {"role": "Ops", "tools": "Slack;Asana", "team_size": 12, "pain": "tracking"},
    {"role": "Ops", "tools": ["Slack"], "team_size": 8, "pain": "tracking"},
    {"role": "Eng", "tools": "Jira", "team_size": 30, "pain": "speed"},
    {"role": "Eng", "tools": "Jira;Slack", "team_size": 25, "pain": "speed"},
    {"role": "Ops", "tools": "Asana", "team_size": "5", "pain": "tracking", "nps": ""},
]


def test_tally_survey_counts_numbers_and_multiselect():
    out = call("tally_survey", responses=ROWS)
    assert out["responses"] == 5
    role = out["fields"]["role"]
    assert role["type"] == "single_choice" and role["top"][0] == {"answer": "Ops", "count": 3, "pct": 60.0}
    tools = out["fields"]["tools"]
    assert tools["type"] == "multi_select"
    assert tools["top"][0] == {"answer": "Slack", "count": 3, "pct": 60.0}
    ts = out["fields"]["team_size"]
    assert ts["type"] == "numeric" and ts["mean"] == 16.0 and ts["median"] == 12.0 and ts["min"] == 5.0
    assert out["fields"]["nps"]["type"] == "empty"
    assert "role: Ops (60.0%)" in out["dominant_answers"]
    assert any("Only 5 responses" in w for w in out["warnings"])


def test_tally_survey_rejects_non_objects():
    with pytest.raises(ToolError):
        call("tally_survey", responses=[{"a": 1}, "not a row"])


def test_cross_tab_chi_square():
    out = call("cross_tab", responses=ROWS * 8, row_field="role", col_field="pain")
    assert out["n"] == 40 and out["df"] == 1
    assert out["chi_square"] == 40.0 and out["cramers_v"] == 1.0
    assert out["significant_at_05"] is True
    ops = next(r for r in out["table"] if r["row"] == "Ops")
    assert ops["row_pct"]["tracking"] == 100.0 and ops["n"] == 24
    independent = call("cross_tab", responses=[{"a": "x", "b": "p"}, {"a": "x", "b": "q"}, {"a": "y", "b": "p"}, {"a": "y", "b": "q"}] * 10, row_field="a", col_field="b")
    assert independent["chi_square"] == 0.0 and independent["p_value"] == 1.0
    assert independent["significant_at_05"] is False


def test_cross_tab_rejects_too_few_pairs():
    with pytest.raises(ToolError):
        call("cross_tab", responses=[{"a": 1, "b": 2}], row_field="a", col_field="b")


def test_format_jtbd_formats_and_lints():
    out = call("format_jtbd", situation="When a patient cancels the morning of", motivation="I want to use Slotly to fill the slot", outcome="so I can keep the day fully booked", persona="Priya", product_names=["Slotly"])
    assert out["jtbd_statement"] == "When a patient cancels the morning of, I want to use Slotly to fill the slot, so I can keep the day fully booked."
    assert out["job_story"].startswith("When a patient cancels the morning of, Priya wants to")
    assert any("Product name 'Slotly'" in l for l in out["lint"])
    clean = call("format_jtbd", situation="a patient cancels the morning of", motivation="refill the slot from the waitlist", outcome="keep the day fully booked without calling anyone")
    assert clean["ready"] is True and clean["lint"] == []
    weak = call("format_jtbd", situation="sometimes", motivation="tracking things in the dashboard", outcome="track things")
    assert any("solution words" in l for l in weak["lint"])
    assert any("base verb" in l for l in weak["lint"])
    assert any("restates" in l for l in weak["lint"])


def test_format_jtbd_rejects_empty():
    with pytest.raises(ToolError):
        call("format_jtbd", situation="", motivation="x", outcome="y")


FULL = {
    "name": "Priya", "role": "Clinic manager", "segment": "3-10 providers",
    "jtbd": "When a patient cancels, I want to fill the slot, so I can keep revenue",
    "trigger_event": "cancellation", "current_alternative": "phone list", "pains": ["a", "b", "c"],
    "success_metric": "utilisation", "objections": ["cost", "EHR"], "buying_role": "economic buyer",
    "channels": ["MGMA", "Facebook groups"], "quote": "I spend my mornings calling the waitlist by hand",
    "anti_persona": "solo practices", "interviews": 7, "survey_n": 40,
}


def test_persona_scorecard_complete_vs_provisional():
    out = call("persona_scorecard", persona=FULL)
    assert out["score"] == 100 and out["status"] == "complete" and out["provisional"] is False
    thin = call("persona_scorecard", persona={**FULL, "pains": ["a"], "interviews": 2, "survey_n": 0, "quote": "too short"})
    assert thin["provisional"] is True
    assert thin["score"] < 85
    assert any(w.startswith("pains: only 1") for w in thin["weak"])
    assert any(w.startswith("quote") for w in thin["weak"])
    stock = call("persona_scorecard", persona={"name": "Bob", "demographics": "35, male", "interviews": 2})
    assert stock["status"] == "draft" and "jtbd" in stock["missing"]


def test_persona_scorecard_rejects_bad_counts():
    with pytest.raises(ToolError):
        call("persona_scorecard", persona={"name": "x", "interviews": "seven"})


def test_bad_arguments_raise_clean_error():
    with pytest.raises(ToolError):
        A.get_tool("tally_survey").call({"responses": "csv text"})
