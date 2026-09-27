"""Positioning Strategist tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("positioning-strategist")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_canvas_check_finds_gaps_and_vague_claims():
    out = call("canvas_check", canvas={"competitive_alternatives": ["Calendly", "practice suites"], "unique_attributes": ["reads the EHR directly", "seamless booking"], "value": ["no double bookings"], "best_fit_customers": ["small clinics"], "market_category": "scheduling for clinics"})
    assert out["category_kind"] == "subsegment"
    assert any(g.startswith("unique_attributes: 2") for g in out["gaps"])
    assert any("spreadsheet" in g for g in out["gaps"])
    assert any("no proof" in g for g in out["gaps"])
    assert [v["item"] for v in out["vague_claims"]] == ["seamless booking"]
    assert out["ready"] is False and out["completeness_score"] < 60
    full = call("canvas_check", canvas={"competitive_alternatives": "Calendly\nthe front desk phone list\ndo nothing", "unique_attributes": ["reads the EHR directly", "fills cancellations by text in 2 hours", "no patient login"], "value": ["80% of cancelled slots refilled (Lakeside Clinic)", "front desk saves 3 hours a day"], "best_fit_customers": ["clinics with 3-10 providers who still call the waitlist by hand", "practices using Athena or eCW"], "market_category": "patient scheduling for small clinics"})
    assert full["ready"] is True and full["completeness_score"] == 100


def test_canvas_check_rejects_empty():
    with pytest.raises(ToolError):
        call("canvas_check", canvas={})


def test_differentiation_matrix_classes():
    out = call("differentiation_matrix", attributes=[
        {"attribute": "EHR sync", "us": 5, "competitors": {"Calendly": 1, "Suite": 3}, "importance": 5},
        {"attribute": "Calendar UI", "us": 4, "competitors": {"Calendly": 4, "Suite": 3}, "importance": 4},
        {"attribute": "Dark mode", "us": 5, "competitors": {"Calendly": 2, "Suite": 2}, "importance": 1},
        {"attribute": "Billing", "us": 1, "competitors": {"Calendly": 1, "Suite": 5}, "importance": 4},
    ], competitors=["Calendly", "Suite"])
    assert out["by_class"] == {"lead": ["EHR sync"], "fix or reframe": ["Billing"], "table stakes": ["Calendar UI"], "trivia": ["Dark mode"]}
    assert out["lead_with"] == ["EHR sync"]
    assert out["matrix"][0]["gap"] == 2.0 and out["matrix"][0]["best_competitor"] == "Suite"
    assert out["missing_ratings"] == []
    assert 0 < out["differentiation_index"] < 50
    assert any("Behind on important" in a for a in out["advice"])


def test_differentiation_matrix_rejects_out_of_range():
    with pytest.raises(ToolError):
        call("differentiation_matrix", attributes=[{"attribute": "x", "us": 7, "competitors": {}, "importance": 3}])


def test_positioning_statement_builds_and_lints():
    out = call("positioning_statement", target="clinic managers who still book by phone", need="need to fill cancelled slots fast", product="Slotly", category="patient scheduling tool", key_benefit="fills 80% of cancellations within 2 hours", primary_alternative="Calendly and the front desk", differentiator="read the EHR directly, so availability is never stale")
    assert out["moore_statement"].startswith("For clinic managers who still book by phone who need to fill cancelled slots fast, Slotly is a patient scheduling tool that fills 80%")
    assert out["x_for_y"] == "Slotly is patient scheduling tool for clinic managers who still book by phone."
    assert out["ready"] is True
    weak = call("positioning_statement", target="teams", need="want to work better", product="X", category="all-in-one platform", key_benefit="work seamlessly", primary_alternative="email", differentiator="a better way to work")
    assert any("Generic claim" in l for l in weak["lint"])
    assert any("No number" in l for l in weak["lint"])
    assert any("behavioural trait" in l for l in weak["lint"])


def test_positioning_statement_rejects_missing_field():
    with pytest.raises(ToolError):
        call("positioning_statement", target="t", need="n", product="", category="c", key_benefit="b", primary_alternative="a", differentiator="d")


def test_message_clarity_ranks_specific_over_generic():
    out = call("message_clarity", messages=["The all-in-one platform for modern teams", "Slotly fills 80% of cancelled clinic slots within 2 hours", "Reimagining healthcare"])
    assert out["best"] == "Slotly fills 80% of cancelled clinic slots within 2 hours"
    scores = {r["message"]: r for r in out["ranked"]}
    assert scores["The all-in-one platform for modern teams"]["competitor_could_say_it"] is True
    assert scores["Slotly fills 80% of cancelled clinic slots within 2 hours"]["competitor_could_say_it"] is False
    assert scores["The all-in-one platform for modern teams"]["score"] <= 40


def test_message_clarity_rejects_empty():
    with pytest.raises(ToolError):
        call("message_clarity", messages=[])


def test_bad_arguments_raise_clean_error():
    with pytest.raises(ToolError):
        A.get_tool("differentiation_matrix").call({"attributes": "EHR sync"})
