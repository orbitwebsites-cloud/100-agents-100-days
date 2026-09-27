"""Podcast Producer tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("podcast-producer")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


TRANSCRIPT = """[00:00] Host: Welcome to the show. So, um, tell me about growth loops?
[00:20] Guest: Sure. Growth loops are basically closed systems where output feeds input. """ + "That matters because retention compounds. " * 80 + """
[05:00] Host: Why do teams get that wrong?
[05:10] Guest: Um, like, they, um, measure the, um, wrong thing, you know, like, honestly the top of funnel.
"""


def test_analyze_transcript_talk_share_questions_and_flags():
    out = call("analyze_transcript", transcript=TRANSCRIPT, host="Host")
    assert out["speakers"][0] == "Guest"
    assert out["questions_by_speaker"]["Host"] == 2
    assert out["talk_share_pct"]["Guest"] > 90
    assert out["duration_source"] == "timestamps"
    assert out["estimated_minutes"] == round(310 / 60, 1)
    assert out["long_monologues"][0]["speaker"] == "Guest" and out["long_monologues"][0]["words"] >= 400
    assert out["filler_dense_passages"][0]["line"] == 4
    assert out["fillers_by_speaker"]["Guest"] >= 6


def test_analyze_transcript_needs_labels():
    with pytest.raises(ToolError):
        call("analyze_transcript", transcript="just some words without any speakers at all")


def test_format_chapters_validates_youtube_rules():
    out = call(
        "format_chapters",
        chapters=[{"start": "0:00", "title": "Cold open"}, {"start": "1:30", "title": "Why growth loops beat funnels"}, {"start": "1:35", "title": "Intro"}, {"start": "3723", "title": "The retention mistake"}],
        total_duration="1:10:00",
    )
    assert out["chapters"][1]["length_s"] == 5
    assert out["chapters"][3]["start"] == "1:02:03" and out["chapters"][3]["length_s"] == 477
    assert out["youtube_valid"] is False
    assert any("≥ 10 s" in i for i in out["issues"])
    assert any("says where, not what" in i for i in out["issues"])
    assert out["youtube_block"].splitlines()[0] == "0:00 Cold open"
    good = call("format_chapters", chapters=[{"start": 0, "title": "Cold open"}, {"start": "2:00", "title": "The claim"}, {"start": "10:00", "title": "Proof"}])
    assert good["youtube_valid"] is True and good["chapters"][-1]["length"] == "to end"


def test_format_chapters_bad_input():
    with pytest.raises(ToolError):
        call("format_chapters", chapters=[{"start": "1:99", "title": "x"}])
    with pytest.raises(ToolError):
        call("format_chapters", chapters=[])


def test_plan_ad_breaks_positions_and_revenue():
    out = call("plan_ad_breaks", duration="58:20", ad_load="standard", downloads_per_episode=12000, cpm=25)
    types = [b["type"] for b in out["breaks"]]
    assert types == ["pre-roll", "mid-roll 1", "mid-roll 2", "post-roll"]
    mids = [b["at_s"] for b in out["breaks"] if b["type"].startswith("mid")]
    assert all(480 <= s <= 0.9 * 3500 for s in mids) and mids[0] < mids[1]
    assert out["estimated_revenue"] == 12000 / 1000 * 25 * 4
    assert out["ad_load_pct"] == round(100 * 180 / 3500, 1)
    light = call("plan_ad_breaks", duration="20:00", ad_load="light")
    assert [b["type"] for b in light["breaks"]] == ["pre-roll", "mid-roll 1"]
    assert light["estimated_revenue"] is None


def test_plan_ad_breaks_rejects_short_episode():
    with pytest.raises(ToolError):
        call("plan_ad_breaks", duration="1:00")


def test_check_metadata_flags_number_showname_and_preview():
    out = call(
        "check_metadata",
        title="Ep 42 - The Growth Show: A conversation with Andrew",
        description="In this episode we talk about growth. " * 6,
        show_name="The Growth Show",
        guest="Andrew Chen",
    )
    joined = " ".join(out["fixes"])
    assert "episode number" in joined and "Show name" in joined and "In this episode" in joined and "Guest name" in joined
    assert out["score"] < 70
    ok = call("check_metadata", title="Andrew Chen on why growth teams measure the wrong thing", description="Andrew Chen explains why 90% of growth teams optimise top of funnel. " * 4 + "Timestamps: 1:30 loops, 12:00 retention. https://example.com", guest="Andrew Chen")
    assert ok["fixes"] == [] and ok["description"]["timestamps"] == 2


def test_check_metadata_empty_title():
    with pytest.raises(ToolError):
        call("check_metadata", title=" ", description="x")


def test_plan_release_calendar_weekly_and_twice_weekly():
    out = call("plan_release_calendar", first_publish="2026-10-06", count=3, cadence="weekly", publish_time="05:00", timezone="America/New_York", record_lead_days=7, edit_lead_days=3)
    assert [r["publish"] for r in out["schedule"]] == ["2026-10-06", "2026-10-13", "2026-10-20"]
    assert out["schedule"][0]["record_by"] == "2026-09-29" and out["schedule"][0]["edit_locked_by"] == "2026-10-03"
    assert out["schedule"][0]["publish_utc"] == "2026-10-06 09:00 UTC"
    assert out["show_day"] == "Tuesday"
    tw = call("plan_release_calendar", first_publish="2026-10-06", count=4, cadence="twice_weekly", second_weekday="Thu")
    assert [r["weekday"] for r in tw["schedule"]] == ["Tue", "Thu", "Tue", "Thu"]
    assert tw["schedule"][1]["publish"] == "2026-10-08"
    daily = call("plan_release_calendar", first_publish="2026-10-09", count=3, cadence="daily_weekdays")
    assert [r["publish"] for r in daily["schedule"]] == ["2026-10-09", "2026-10-12", "2026-10-13"]
    monthly = call("plan_release_calendar", first_publish="2026-01-31", count=3, cadence="monthly")
    assert [r["publish"] for r in monthly["schedule"]] == ["2026-01-31", "2026-02-28", "2026-03-31"]


def test_plan_release_calendar_bad_input():
    with pytest.raises(ToolError):
        call("plan_release_calendar", first_publish="2026-10-06", count=3, record_lead_days=2, edit_lead_days=5)
    with pytest.raises(ToolError):
        call("plan_release_calendar", first_publish="2026-10-06", count=3, timezone="Mars/Olympus")
