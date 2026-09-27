"""Launch Planner tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("launch-planner")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_countdown_timeline_business_days():
    out = call("countdown_timeline", launch_date="2026-11-12", size="medium", today="2026-09-27")
    assert out["runway_business_days"] == 34 and out["compressed"] is False
    assert out["launch_weekday"] == "Thursday"
    by_name = {m["milestone"]: m for m in out["milestones"]}
    assert by_name["LAUNCH"]["date"] == "2026-11-12"
    assert by_name["Positioning, message hierarchy and launch tier locked"]["date"] == "2026-10-01"  # 30 business days before
    assert by_name["Final QA of every link, UTM and form; emails scheduled"]["date"] == "2026-11-10"
    assert all(m["weekday"] not in ("Sat", "Sun") for m in out["milestones"])
    assert out["overdue"] == []


def test_countdown_timeline_compresses_and_warns():
    out = call("countdown_timeline", launch_date="2026-10-10", size="large", today="2026-09-27")
    assert out["compressed"] is True
    assert any("Saturday" in w for w in out["warnings"])
    assert any("compressed" in w for w in out["warnings"])
    assert max(m["t_minus_business_days"] for m in out["milestones"]) <= 10
    overdue = call("countdown_timeline", launch_date="2026-11-12", size="small", today="2026-11-05")
    assert "Positioning and message locked" in overdue["overdue"]  # T-10 business days = Oct 29


def test_countdown_timeline_rejects_past_launch():
    with pytest.raises(ToolError):
        call("countdown_timeline", launch_date="2026-09-01", today="2026-09-27")


def test_channel_checklist_deadlines_and_aliases():
    out = call("channel_checklist", channels=["blog", "email", "Product Hunt", "press", "tiktok"], launch_date="2026-11-12")
    assert out["unknown_channels"] == ["tiktok"]
    by = {c["channel"]: c for c in out["channels"]}
    assert by["press"]["final_by"] == "2026-10-22"  # 15 business days before
    assert by["email"]["final_by"] == "2026-11-09"
    assert by["product_hunt"]["lead_business_days"] == 7
    assert out["first_deadline"]["channel"] == "press"
    assert out["total_assets"] == 16


def test_channel_checklist_rejects_all_unknown():
    with pytest.raises(ToolError):
        call("channel_checklist", channels=["carrier pigeon"], launch_date="2026-11-12")


def test_readiness_score_blocks_on_p0():
    out = call("readiness_score", items=[{"item": "Billing tested on prod", "status": "in progress"}, {"item": "Blog post", "priority": "P1", "status": "done", "owner": "Ana"}, {"item": "Swag", "priority": "P2", "status": "not_started"}])
    assert out["decision"] == "NO-GO"
    assert out["p0_blockers"][0]["item"] == "Billing tested on prod"
    assert out["score"] == round(100 * (5 * 0.5 + 3) / 9)
    assert out["unowned_open_items"] == ["Billing tested on prod", "Swag"]
    go = call("readiness_score", items=[{"item": "Billing tested on prod", "status": "done"}, {"item": "Blog", "status": "done"}])
    assert go["decision"] == "GO" and go["score"] == 100


def test_readiness_score_rejects_unknown_status():
    with pytest.raises(ToolError):
        call("readiness_score", items=[{"item": "x", "status": "maybe"}])


def test_launch_targets_projection_and_gap():
    out = call("launch_targets", goal=1500, channels=[{"channel": "email", "reach": 20000, "engagement_pct": 4, "conversion_pct": 20}, {"channel": "linkedin", "reach": 8000, "engagement_pct": 2, "conversion_pct": 10}, {"channel": "paid", "reach": 100000, "engagement_pct": 1, "conversion_pct": 5, "cost": 3000}])
    assert out["projected_signups"] == 226.0
    assert out["gap"] == 1274.0 and out["on_track"] is False
    assert out["channels"][0]["channel"] == "email" and out["channels"][0]["signups"] == 160.0
    paid = next(c for c in out["channels"] if c["channel"] == "paid")
    assert paid["cost_per_signup"] == 60.0
    assert out["concentration_warning"].startswith("email delivers 71%")


def test_launch_targets_rejects_bad_pct():
    with pytest.raises(ToolError):
        call("launch_targets", goal=10, channels=[{"channel": "x", "reach": 10, "engagement_pct": 500, "conversion_pct": 1}])


def test_launch_day_schedule_timezones_and_product_hunt():
    out = call("launch_day_schedule", launch_datetime="2026-11-12T09:00:00-05:00", audience_utc_offsets=[-8, 0, 5.5], product_hunt=True)
    first = out["steps"][0]
    assert first["action"].startswith("Product Hunt goes live")
    assert first["offset_minutes"] == -359  # 12:01 AM PST = 03:01 EST
    assert first["audience_times"] == {"UTC-8": "00:01", "UTC+0": "08:01", "UTC+5.5": "13:31"}
    go = next(s for s in out["steps"] if s["offset_minutes"] == 0)
    assert go["audience_times"]["UTC+0"] == "14:00"
    assert len(out["warnings"]) == 2


def test_launch_day_schedule_rejects_naive_datetime():
    with pytest.raises(ToolError):
        call("launch_day_schedule", launch_datetime="2026-11-12T09:00:00")


def test_bad_arguments_raise_clean_error():
    with pytest.raises(ToolError):
        A.get_tool("readiness_score").call({"items": "all done"})
