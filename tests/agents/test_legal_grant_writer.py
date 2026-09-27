"""Grant Writer tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("grant-writer")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_budget_table_mtdc_indirect_and_cost_share():
    out = call(
        "budget_table",
        line_items=[
            {"category": "personnel", "description": "Director", "salary": 70000, "fte": 1},
            {"category": "personnel", "description": "Coordinator", "salary": 60000, "fte": 0.5},
            {"category": "equipment", "description": "Laptops", "amount": 12000},
            {"category": "travel", "quantity": 4, "unit_cost": 2000},
            {"category": "subaward", "description": "Evaluator", "amount": 40000},
        ],
        fringe_rate_pct=28,
        indirect_rate_pct=10,
        indirect_base="mtdc",
        cost_share_required_pct=25,
        cost_share_provided=30000,
        uniform_guidance="pre-2024",  # award made before 2024-10-01: $5k equipment, first $25k of each subaward, 10% de minimis
    )
    assert out["salaries"] == 100000.0 and out["fringe"] == 28000.0
    assert out["total_direct"] == 188000.0
    assert out["mtdc"] == 161000.0  # excludes 12k equipment and 15k of the subaward above 25k
    assert out["indirect"] == 16100.0 and out["total_request"] == 204100.0
    assert out["cost_share"] == {"required": 51025.0, "provided": 30000.0, "gap": 21025.0}
    assert any("Cost share short" in f for f in out["flags"])


def test_budget_table_indirect_cap_and_request_cap():
    out = call("budget_table", line_items=[{"category": "supplies", "amount": 90000}], indirect_rate_pct=25, indirect_base="tdc", indirect_cap_pct_of_total=10, request_cap=95000)
    assert out["indirect"] == 10000.0 and out["total_request"] == 100000.0
    assert any("caps at 10%" in f for f in out["flags"]) and any("exceeds the $95,000 cap" in f for f in out["flags"])


def test_budget_table_rejects_unknown_category():
    with pytest.raises(ToolError):
        call("budget_table", line_items=[{"category": "snacks", "amount": 10}])


def test_check_section_limits_words_and_pages():
    out = call(
        "check_section_limits",
        sections=[
            {"name": "need", "text": "word " * 520, "limit": 500, "unit": "words"},
            {"name": "approach", "text": "word " * 1000, "limit": 3, "unit": "pages", "spacing": "double"},
            {"name": "eval", "text": "word " * 300, "limit": 500, "unit": "words"},
        ],
    )
    s = {r["name"]: r for r in out["sections"]}
    assert s["need"]["fits"] is False and s["need"]["cut_needed"] == "cut 20 words"
    assert s["approach"]["used"] == 4.0 and s["approach"]["fits"] is False
    assert s["eval"]["status"].startswith("thin")
    assert out["over_limit"] == ["need", "approach"] and out["all_fit"] is False


def test_check_section_limits_rejects_bad_unit():
    with pytest.raises(ToolError):
        call("check_section_limits", sections=[{"name": "x", "text": "hi", "limit": 10, "unit": "lines"}])


def test_criteria_coverage_weights_and_smart():
    out = call(
        "criteria_coverage",
        sections=[
            {"name": "need", "text": "The community need is severe. Youth lack access to coding and the data show a gap.", "criterion": "Need"},
            {"name": "approach", "text": "Our approach uses cohorts and mentors with a curriculum and evaluation plan built on evidence.", "criterion": "Approach"},
        ],
        criteria=[{"name": "Need", "weight": 30, "keywords": ["need", "community", "data"]}, {"name": "Approach", "weight": 70, "keywords": ["approach", "curriculum", "mentors", "cohorts"]}],
        objectives=["Empower young people.", "By 2027-06-30, 120 youth will complete 30 hours of instruction, as measured by attendance records."],
    )
    c = {r["criterion"]: r for r in out["criteria"]}
    assert c["Need"]["keyword_coverage_pct"] == 100.0 and c["Approach"]["keyword_coverage_pct"] == 100.0
    assert c["Approach"]["status"] == "under-covered vs weight"
    assert out["objectives"][0]["score"] == 0 and "add a number or %" in out["objectives"][0]["fixes"]
    assert out["objectives"][1]["score"] == 4
    assert out["objectives_passing"] == 1


def test_criteria_coverage_rejects_zero_weights():
    with pytest.raises(ToolError):
        call("criteria_coverage", sections=[{"name": "a", "text": "x y z"}], criteria=[{"name": "A", "weight": 0}])


def test_project_timeline_reports_and_milestones():
    out = call("project_timeline", start_date="2026-10-01", duration_months=12, milestones=[{"name": "Launch", "month": 2}, {"name": "Late", "month": 14}], reporting="quarterly", report_lag_days=30, final_report_lag_days=90)
    assert out["period_of_performance"]["end"] == "2027-09-30"
    assert [r["due"] for r in out["reports"]] == ["2027-01-30", "2027-04-30", "2027-07-30", "2027-12-29"]
    ms = {m["name"]: m for m in out["milestones"]}
    assert ms["Launch"]["date"] == "2026-11-30" and ms["Launch"]["within_period"] is True
    assert out["milestones_outside_period"] == ["Late"]


def test_project_timeline_rejects_bad_cadence():
    with pytest.raises(ToolError):
        call("project_timeline", start_date="2026-10-01", duration_months=12, reporting="weekly")
