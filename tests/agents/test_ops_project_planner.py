"""Project Planner tools — CPM, calendar scheduling, PERT, slip report."""

import pytest

from hundred.agents.ops import project_planner
from hundred.core import ToolError

A = project_planner.AGENT

TASKS = [
    {"id": "A", "name": "Spec", "duration": 3, "depends_on": []},
    {"id": "B", "name": "Design", "duration": 4, "depends_on": ["A"]},
    {"id": "C", "name": "Backend", "duration": 8, "depends_on": ["A"]},
    {"id": "D", "name": "Frontend", "duration": 3, "depends_on": ["B"]},
    {"id": "E", "name": "QA", "duration": 2, "depends_on": ["C", "D"]},
    {"id": "M", "name": "Launch", "duration": 0, "depends_on": ["E"]},
]


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_critical_path_forward_backward_pass_and_float():
    out = call("critical_path", tasks=TASKS)
    assert out["project_duration_days"] == 13
    assert out["critical_path"] == ["A", "C", "E", "M"]
    by = {t["id"]: t for t in out["tasks"]}
    assert (by["B"]["es"], by["B"]["ef"], by["B"]["ls"], by["B"]["lf"]) == (3, 7, 4, 8)
    assert by["B"]["total_float"] == 1 and by["B"]["free_float"] == 0
    assert by["D"]["total_float"] == 1 and by["D"]["free_float"] == 1
    assert by["C"]["critical"] is True and by["D"]["critical"] is False
    assert out["near_critical_task_ids"] == ["B", "D"]
    assert out["highest_risk_tasks"][0]["id"] == "C"


def test_critical_path_two_parallel_paths():
    out = call("critical_path", tasks=[
        {"id": "A", "duration": 2}, {"id": "B", "duration": 2}, {"id": "C", "duration": 1, "depends_on": ["A", "B"]},
    ])
    assert len(out["all_critical_paths"]) == 2
    assert "fragile" in out["verdict"]


def test_critical_path_detects_cycle_and_unknown_dep():
    with pytest.raises(ToolError, match="cycle"):
        call("critical_path", tasks=[{"id": "A", "duration": 1, "depends_on": ["B"]}, {"id": "B", "duration": 1, "depends_on": ["A"]}])
    with pytest.raises(ToolError, match="unknown"):
        call("critical_path", tasks=[{"id": "A", "duration": 1, "depends_on": ["Z"]}])
    with pytest.raises(ToolError):
        call("critical_path", tasks=[{"id": "A", "duration": -1}])


def test_schedule_calendar_skips_weekends_and_holidays():
    # Mon 2026-10-05 start. A = 3 days: Oct 5-7. C = 8 days from Oct 8 skipping the Oct 12 holiday -> ends Oct 20.
    out = call("schedule_calendar", tasks=TASKS, start_date="2026-10-05", holidays=["2026-10-12"])
    by = {t["id"]: t for t in out["tasks"]}
    assert (by["A"]["start"], by["A"]["end"]) == ("2026-10-05", "2026-10-07")
    assert (by["C"]["start"], by["C"]["end"]) == ("2026-10-08", "2026-10-20")
    assert by["C"]["holidays_inside"] == ["2026-10-12"]
    assert by["M"]["milestone"] is True and by["M"]["start"] == by["E"]["end"]
    assert out["end_date"] == "2026-10-22" and by["E"]["end"] == "2026-10-22"
    assert "◆" in out["gantt"] and "Backend*" in out["gantt"]


def test_schedule_calendar_start_on_weekend_rolls_forward():
    out = call("schedule_calendar", tasks=[{"id": "A", "duration": 1}], start_date="2026-10-03")  # Saturday
    assert out["start_date"] == "2026-10-05" and out["end_date"] == "2026-10-05"
    with pytest.raises(ToolError):
        call("schedule_calendar", tasks=[{"id": "A", "duration": 1}], start_date="next monday")


def test_pert_estimate_chain_math():
    out = call("pert_estimate", tasks=[
        {"name": "a", "optimistic": 2, "most_likely": 4, "pessimistic": 12},
        {"name": "b", "optimistic": 3, "most_likely": 3, "pessimistic": 3},
    ])
    assert out["tasks"][0]["expected"] == 5.0 and out["tasks"][0]["sigma"] == 1.67
    assert out["tasks"][0]["flag"]
    assert out["chain"]["expected_p50"] == 8.0
    assert out["chain"]["sigma"] == 1.67
    assert out["chain"]["p80"] == 9.4
    with pytest.raises(ToolError):
        call("pert_estimate", tasks=[{"name": "x", "optimistic": 5, "most_likely": 3, "pessimistic": 8}])


def test_slip_report_working_day_slip_and_rag():
    out = call("slip_report", milestones=[
        {"name": "Spec done", "baseline": "2026-09-04", "actual": "2026-09-04"},
        {"name": "Beta", "baseline": "2026-09-18", "forecast": "2026-09-25"},
        {"name": "GA", "baseline": "2026-10-02", "forecast": "2026-10-16"},
    ], as_of="2026-09-21")
    by = {m["name"]: m for m in out["milestones"]}
    assert by["Beta"]["slip_working_days"] == 5 and by["Beta"]["status"] == "slipping"
    assert by["GA"]["slip_working_days"] == 10
    assert by["Spec done"]["status"] == "done on time"
    assert out["rag"] == "AMBER" and out["project_end_forecast"] == "2026-10-16"
    with pytest.raises(ToolError):
        call("slip_report", milestones=[{"name": "x", "baseline": "soon"}])


def test_bad_arguments_raise_clean_error():
    with pytest.raises(ToolError):
        A.get_tool("critical_path").call({"tasks": "A, B, C"})
