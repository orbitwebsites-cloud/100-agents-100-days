"""Time Blocker tools — zoneinfo conversions, meeting finder, day packer, calendar audit."""

import pytest

from hundred.agents.ops import time_blocker
from hundred.core import ToolError

A = time_blocker.AGENT


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_convert_time_handles_dst_and_day_rollover():
    # 2026-10-08: Sydney is on AEDT (UTC+11), New York on EDT (UTC-4) -> 15h apart.
    out = call("convert_time", when="2026-10-08 14:00", from_zone="Sydney", to_zones=["New York", "London", "Asia/Kolkata"])
    ny, ldn, ind = out["conversions"]
    assert ny["local"] == "2026-10-07 23:00" and ny["day_shift"] == -1 and ny["weekday"] == "Wednesday"
    assert ldn["local"] == "2026-10-08 04:00" and ldn["is_dst"] is True
    assert ind["local"] == "2026-10-08 08:30" and ind["offset"] == "UTC+05:30"
    assert out["utc"] == "2026-10-08 03:00"


def test_convert_time_after_dst_change_differs():
    # 2026-11-02: US already on standard time (Nov 1), UK back on GMT (Oct 25).
    out = call("convert_time", when="2026-11-02 09:00", from_zone="America/New_York", to_zones=["Europe/London"])
    assert out["conversions"][0]["local"] == "2026-11-02 14:00"
    out = call("convert_time", when="2026-10-28 09:00", from_zone="America/New_York", to_zones=["Europe/London"])
    assert out["conversions"][0]["local"] == "2026-10-28 13:00"


def test_convert_time_rejects_unknown_zone_and_nonexistent_time():
    with pytest.raises(ToolError, match="unknown time zone"):
        call("convert_time", when="2026-10-08 14:00", from_zone="Narnia/Lantern", to_zones=["UTC"])
    with pytest.raises(ToolError, match="does not exist"):
        call("convert_time", when="2026-03-08 02:30", from_zone="America/New_York", to_zones=["UTC"])


def test_find_meeting_slots_three_zones():
    out = call(
        "find_meeting_slots",
        participants=[
            {"name": "Ana", "zone": "America/Los_Angeles"},
            {"name": "Ben", "zone": "Europe/London"},
        ],
        duration_minutes=30,
        date="2026-10-06",  # Tuesday
    )
    # LA 09:00-17:00 PDT = 16:00-00:00 UTC; London 09:00-17:00 BST = 08:00-16:00 UTC -> no overlap at all
    assert out["everyone_in_hours"] == []
    assert out["best_compromise"], "should offer a tolerable compromise"
    assert out["offset_spread_hours"] == 8.0
    out2 = call(
        "find_meeting_slots",
        participants=[{"name": "Ana", "zone": "America/New_York"}, {"name": "Ben", "zone": "Europe/London"}],
        duration_minutes=60,
        date="2026-10-06",
    )
    first = out2["everyone_in_hours"][0]
    assert first["start_utc"] == "2026-10-06 13:00"  # 09:00 EDT / 14:00 BST
    assert first["window_minutes"] == 180  # until London's 17:00 (16:00 UTC)
    assert "Mon" not in first["local"]["Ana"] and "Tue 09:00-10:00" in first["local"]["Ana"]


def test_find_meeting_slots_skips_weekend_and_validates():
    out = call("find_meeting_slots", participants=[{"name": "A", "zone": "UTC"}], date="2026-10-10", days=1)  # Saturday
    assert out["everyone_in_hours"] == [] and out["best_compromise"] == []
    with pytest.raises(ToolError):
        call("find_meeting_slots", participants=[{"name": "A", "zone": "UTC"}], duration_minutes=5)


def test_pack_day_puts_deep_work_in_peak_and_reports_leftovers():
    out = call(
        "pack_day",
        tasks=[
            {"name": "Write strategy doc", "minutes": 120, "priority": 1, "kind": "deep"},
            {"name": "Expense report", "minutes": 30, "priority": 3, "kind": "admin"},
            {"name": "Review PRs", "minutes": 45, "priority": 2, "kind": "shallow"},
            {"name": "Model rewrite", "minutes": 240, "priority": 2, "kind": "deep"},
        ],
        fixed_events=[{"title": "Standup", "start": "10:00", "end": "10:15"}, {"title": "Design review", "start": "14:00", "end": "15:00"}],
        day_start="09:00", day_end="17:00",
    )
    deep = [b for b in out["blocks"] if b["task"] == "Write strategy doc"]
    assert deep[0]["start"] == "09:00" and deep[0]["in_peak"] is True
    assert out["stats"]["meeting_minutes"] == 75 and out["stats"]["meeting_load_pct"] == 16
    assert out["stats"]["tasks_unscheduled"] == 1 and out["unscheduled"][0]["task"] == "Model rewrite"
    starts = [b["start"] for b in out["blocks"]]
    assert starts == sorted(starts)
    # no two blocks overlap
    mins = [(time_blocker.parse_hhmm(b["start"]), time_blocker.parse_hhmm(b["end"])) for b in out["blocks"]]
    assert all(b[0] >= a[1] for a, b in zip(mins, mins[1:]))
    with pytest.raises(ToolError):
        call("pack_day", tasks=[{"name": "x", "minutes": 30, "kind": "nap"}])


def test_audit_calendar_load_fragments_and_focus():
    out = call(
        "audit_calendar",
        events=[
            {"title": "Standup", "start": "2026-10-05 09:00", "end": "2026-10-05 09:15"},
            {"title": "1:1 with Sam", "start": "2026-10-05 09:30", "end": "2026-10-05 10:00"},
            {"title": "Customer call", "start": "2026-10-05 10:00", "end": "2026-10-05 11:00"},
            {"title": "Standup", "start": "2026-10-06 09:00", "end": "2026-10-06 09:15"},
        ],
        work_start="09:00", work_end="17:00",
    )
    mon, tue = out["by_day"]
    assert mon["meeting_minutes"] == 105 and mon["back_to_back"] == 1 and mon["fragments_under_30"] == 1
    assert mon["longest_free_block"] == 360 and mon["focus_blocks"] == 1
    assert tue["focus_blocks"] == 1 and tue["longest_free_block"] == 465
    assert out["meeting_load_pct"] == 12 and out["rag"] == "GREEN"
    assert out["by_category"][0]["category"] == "external/customer"
    with pytest.raises(ToolError):
        call("audit_calendar", events=[{"title": "x", "start": "2026-10-05 10:00", "end": "2026-10-05 09:00"}])


def test_bad_arguments_raise_clean_error():
    with pytest.raises(ToolError):
        A.get_tool("convert_time").call({"when": "2026-10-08 14:00", "from_zone": "UTC", "to_zones": "London"})
