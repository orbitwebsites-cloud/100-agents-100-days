"""Onboarding Planner tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("onboarding-planner")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_build_30_60_90_dates_move_off_weekends_and_holidays():
    out = call("build_30_60_90", start_date="2026-10-12", role="Senior PM", manager="Dana", holidays=["2026-11-26", "2026-11-27", "2026-12-25"])
    assert out["day_1"] == {"date": "2026-10-12", "weekday": "Monday"}
    assert out["week_1_end"]["date"] == "2026-10-16"
    assert out["day_30"]["date"] == "2026-11-10" and out["day_30"]["moved"] is False
    assert out["day_60"]["date"] == "2026-12-10"
    assert out["day_90"] == {"day": 90, "date": "2027-01-11", "weekday": "Mon", "moved": True, "business_days_from_start": 62}
    assert out["one_on_ones"][0]["date"] == "2026-10-13" and out["one_on_ones"][1]["date"] == "2026-10-19"
    assert out["one_on_one_weekday"] == "Mon"
    assert out["holidays_in_period"] == ["2026-11-26", "2026-11-27", "2026-12-25"]
    assert [p["end"] for p in out["phases"]] == ["2026-11-10", "2026-12-10", "2027-01-11"]
    weekend = call("build_30_60_90", start_date="2026-10-10", role="Analyst")
    assert weekend["warnings"] and "weekend" in weekend["warnings"][0]


def test_build_30_60_90_rejects_bad_probation():
    with pytest.raises(ToolError):
        call("build_30_60_90", start_date="2026-10-12", role="PM", probation_days=5)


def test_preboarding_checklist_business_day_lead_times_and_overdue():
    out = call("preboarding_checklist", start_date="2026-10-12", remote=True, today="2026-09-27")
    by_task = {i["task"]: i for i in out["items"]}
    assert by_task["Offer signed and countersigned"]["due"] == "2026-09-21"
    assert by_task["Equipment ordered (laptop, monitor, peripherals)"]["lead_business_days"] == 12
    assert by_task["Equipment ordered (laptop, monitor, peripherals)"]["due"] == "2026-09-24"
    assert by_task["Day-1 agenda sent (times, links/location, who they'll meet)"]["due"] == "2026-10-09"
    assert out["business_days_until_start"] == 11
    assert len(out["overdue"]) == 3
    onsite = call("preboarding_checklist", start_date="2026-10-12", remote=False, today="2026-09-01")
    assert {i["task"]: i for i in onsite["items"]}["Equipment ordered (laptop, monitor, peripherals)"]["lead_business_days"] == 10
    assert onsite["overdue"] == []


def test_preboarding_checklist_rejects_bad_date():
    with pytest.raises(ToolError):
        call("preboarding_checklist", start_date="next monday")


PLAN = [
    {"task": "Get laptop and SSO access", "owner": "IT", "due": "2026-10-12"},
    {"task": "Meet the design lead", "owner": "Dana", "due": "2026-10-13", "phase": 30},
    {"task": "Read the roadmap docs", "owner": "Sam", "due": "2026-10-14"},
    {"task": "Ship first dashboard tile", "owner": "Sam", "due": "2026-10-30", "phase": 30},
    {"task": "30-day check-in", "owner": "Dana", "due": "2026-11-10", "phase": 30},
    {"task": "Own the pricing experiment", "owner": "Sam", "due": "2026-12-10", "phase": 60},
    {"task": "90-day review", "owner": "Dana", "due": "2027-01-09", "phase": 90},
    {"task": "Something", "due": "2026-10-17"},
]


def test_check_plan_flags_and_categories():
    out = call("check_plan", items=PLAN, start_date="2026-10-12")
    assert out["categories_present"] == ["access", "deliverable", "feedback", "learning", "other", "people"]
    assert out["first_deliverable_day"] == 19
    assert out["feedback_checkpoint_days"] == [30, 90]
    assert out["week_load"][1] == 4
    assert out["items"][6]["issues"] == ["due on a weekend — move to 2027-01-11"]
    assert "no owner" in out["items"][7]["issues"]
    assert out["score"] == 89
    thin = call("check_plan", items=[{"task": "Read docs", "owner": "Sam", "due": "2026-10-13"}], start_date="2026-10-12")
    assert any("no deliverable" in f for f in thin["flags"]) and any("no feedback checkpoint" in f for f in thin["flags"])
    mism = call("check_plan", items=[{"task": "Ship thing", "owner": "S", "due": "2026-12-01", "phase": 30}], start_date="2026-10-12")
    assert any("tagged phase 30 but due on day 51" in i for i in mism["items"][0]["issues"])


def test_check_plan_rejects_bad_phase():
    with pytest.raises(ToolError):
        call("check_plan", items=[{"task": "x", "owner": "y", "due": "2026-10-13", "phase": 45}], start_date="2026-10-12")


def test_intro_meeting_schedule_respects_windows_and_daily_cap():
    stakeholders = [{"name": f"P{i}", "priority": 1} for i in range(8)] + [{"name": f"Q{i}", "priority": 2} for i in range(4)] + [{"name": "Z", "priority": 3, "minutes": 15}]
    out = call("intro_meeting_schedule", start_date="2026-10-12", stakeholders=stakeholders, max_per_day=2)
    assert out["by_week"] == {1: 8, 2: 4, 3: 1}
    assert out["meetings"][0]["date"] == "2026-10-13"  # never day 1
    assert all(m["week"] == 1 for m in out["meetings"] if m["name"].startswith("P"))
    from collections import Counter

    per_day = Counter(m["date"] for m in out["meetings"])
    assert max(per_day.values()) == 2
    assert out["total_minutes"] == 12 * 30 + 15
    assert out["unscheduled"] == []
    overflow = call("intro_meeting_schedule", start_date="2026-10-12", stakeholders=[{"name": f"P{i}", "priority": 1} for i in range(12)], max_per_day=2)
    assert overflow["by_week"] == {1: 8, 2: 4}  # spill to week 2, not dropped


def test_intro_meeting_schedule_rejects_bad_priority():
    with pytest.raises(ToolError):
        call("intro_meeting_schedule", start_date="2026-10-12", stakeholders=[{"name": "A", "priority": 9}])
