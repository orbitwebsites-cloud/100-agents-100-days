"""Study Coach tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("study-coach")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_sm2_review_exact_algorithm():
    out = call(
        "sm2_review",
        review_date="2026-10-01",
        cards=[
            {"id": "new-5", "quality": 5},  # new card, perfect → rep 1, interval 1, ease 2.6
            {"id": "second-4", "quality": 4, "repetitions": 1, "interval_days": 1, "ease": 2.5},  # → rep 2, interval 6, ease 2.5
            {"id": "third-3", "quality": 3, "repetitions": 2, "interval_days": 6, "ease": 2.5},  # → rep 3, interval round(6*2.36)=14, ease 2.36
            {"id": "lapse-1", "quality": 1, "repetitions": 4, "interval_days": 30, "ease": 2.5},  # → reset, interval 1, ease 1.96
            {"id": "floor", "quality": 0, "repetitions": 1, "interval_days": 1, "ease": 1.3},  # ease floor 1.3
        ],
    )
    by = {c["id"]: c for c in out["cards"]}
    assert by["new-5"]["interval_days"] == 1 and by["new-5"]["ease"] == 2.6 and by["new-5"]["due"] == "2026-10-02"
    assert by["second-4"]["interval_days"] == 6 and by["second-4"]["ease"] == 2.5 and by["second-4"]["due"] == "2026-10-07"
    assert by["third-3"]["interval_days"] == 14 and by["third-3"]["ease"] == 2.36 and by["third-3"]["status"] == "review"
    assert by["lapse-1"]["repetitions"] == 0 and by["lapse-1"]["interval_days"] == 1 and by["lapse-1"]["ease"] == 1.96
    assert by["floor"]["ease"] == 1.3
    assert out["lapses"] == 2 and out["next_review_date"] == "2026-10-02"


def test_sm2_review_bad_quality():
    with pytest.raises(ToolError):
        call("sm2_review", cards=[{"id": "x", "quality": 7}])
    with pytest.raises(ToolError):
        call("sm2_review", cards=[{"id": "x", "quality": 4, "ease": 1.0}])


def test_review_calendar_intervals_and_exam_clip():
    out = call(
        "review_calendar",
        topics=[{"topic": "Krebs", "learned_on": "2026-10-01"}, {"topic": "Glycolysis", "learned_on": "2026-10-03"}],
        exam_date="2026-10-20",
        max_reviews_per_day=1,
    )
    krebs = next(t for t in out["topics"] if t["topic"] == "Krebs")
    assert krebs["reviews"] == ["2026-10-02", "2026-10-04", "2026-10-08", "2026-10-15", "2026-10-18"]
    gly = next(t for t in out["topics"] if t["topic"] == "Glycolysis")
    assert gly["reviews"] == ["2026-10-04", "2026-10-06", "2026-10-10", "2026-10-17", "2026-10-18"]
    day = next(c for c in out["calendar"] if c["date"] == "2026-10-04")
    assert day["load"] == 2 and any("2026-10-04 has 2" in f for f in out["flags"])
    assert out["total_reviews"] == 10


def test_review_calendar_bad_input():
    with pytest.raises(ToolError):
        call("review_calendar", topics=[{"topic": "x", "learned_on": "2026-10-25"}], exam_date="2026-10-20")
    with pytest.raises(ToolError):
        call("review_calendar", topics=[{"topic": "x", "learned_on": "2026-10-01"}], intervals=[3, 1])


def test_anki_export_lints_and_escapes():
    out = call(
        "anki_export",
        cards=[
            {"front": "Which enzyme catalyses the first step of the Krebs cycle?", "back": "Citrate synthase", "tags": ["biochem", "krebs cycle"]},
            {"front": "Is ATP produced in glycolysis?", "back": "Yes", "tags": []},
            {"front": "Name the products of one turn of the Krebs cycle", "back": "3 NADH, 1 FADH2, 1 GTP, 2 CO2, and 1 CoA regenerated for the next turn", "tags": []},
            {"front": "Which enzyme catalyses the first step of the Krebs cycle?", "back": "Citrate synthase"},
            {"front": "", "back": "x"},
            {"front": "What does \"anaplerotic\"\tmean?", "back": "Replenishes cycle\nintermediates"},
        ],
        deck="Biochem",
    )
    assert out["cards_exported"] == 5 and out["cards_clean"] == 2
    kinds = {i["card"]: i["detail"] for i in out["issues"]}
    assert "yes/no" in kinds[2] and "cloze" in kinds[3] and "duplicate of card #1" in kinds[4] and "required" in kinds[5]
    lines = out["file_content"].splitlines()
    assert lines[0] == "#separator:tab" and "#deck:Biochem" in lines
    assert lines[4].split("\t")[2] == "biochem krebs_cycle"
    assert '"What does ""anaplerotic""\tmean?"' in out["file_content"] and "Replenishes cycle<br>intermediates" in out["file_content"]


def test_anki_export_bad_input():
    with pytest.raises(ToolError):
        call("anki_export", cards=[])
    with pytest.raises(ToolError):
        call("anki_export", cards=[{"front": "a?", "back": "b"}], separator="pipe")


def test_pomodoro_plan_clock_times_and_interleave():
    out = call(
        "pomodoro_plan",
        start_time="09:00",
        available_minutes=120,
        tasks=[{"name": "Krebs cards", "minutes": 50, "priority": 1}, {"name": "Practice problems", "minutes": 75, "priority": 2}],
        work_minutes=25,
        short_break=5,
        long_break=15,
        blocks_per_cycle=4,
    )
    work = [s for s in out["schedule"] if s["type"] == "work"]
    assert [w["task"] for w in work] == ["Krebs cards", "Practice problems", "Krebs cards", "Practice problems"]
    assert work[0]["start"] == "09:00" and work[0]["end"] == "09:25" and work[1]["start"] == "09:30"
    assert out["work_blocks"] == 4 and out["focused_minutes"] == 100 and out["end"] == "10:55"
    assert out["unfinished"] == [{"name": "Practice problems", "blocks_left": 1, "minutes_left": 25}]
    assert out["unused_minutes"] == 5


def test_pomodoro_plan_bad_input():
    with pytest.raises(ToolError):
        call("pomodoro_plan", start_time="9am", available_minutes=60, tasks=[{"name": "x"}])
    with pytest.raises(ToolError):
        call("pomodoro_plan", start_time="09:00", available_minutes=5, tasks=[{"name": "x"}])


def test_study_load_hours_and_fit():
    out = call(
        "study_load",
        exam_date="2026-12-12",
        today="2026-11-14",
        topics=[{"topic": "Thermo", "weight": 50, "hours_needed": 20}, {"topic": "Optics", "weight": 30, "hours_needed": 10}, {"topic": "Waves", "weight": 20, "hours_needed": 8}],
        hours_per_week=10,
        buffer_days=2,
    )
    assert out["days_left"] == 28 and out["study_days"] == 24
    assert out["hours_available"] == round(24 * 10 / 7, 1)
    assert out["hours_needed"] == 38 and out["fits"] is False
    assert any("Short by" in f for f in out["flags"])
    assert out["topics"][0]["hours_allocated"] == round(24 * 10 / 7 * 0.5, 1)
    assert len(out["weekly_plan"]) == 4 and out["weekly_plan"][-1]["focus"].startswith("retrieval")
    assert out["final_48h"].startswith("2026-12-10")


def test_study_load_bad_dates():
    with pytest.raises(ToolError):
        call("study_load", exam_date="2026-11-01", today="2026-11-14", topics=[{"topic": "x"}], hours_per_week=5)
