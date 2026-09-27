"""OKR Coach tools — linter, progress grader, forecast, cadence calendar."""

import pytest

from hundred.agents.ops import okr_coach
from hundred.core import ToolError

A = okr_coach.AGENT


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_lint_okrs_flags_classic_mistakes():
    out = call(
        "lint_okrs",
        objectives=[
            {
                "objective": "Increase revenue by 20%",
                "key_results": ["Launch the new dashboard", "Improve customer satisfaction", "Increase week-1 activation from 31% to 45%"],
            }
        ],
    )
    o = out["objectives"][0]
    assert any("contains a number" in i for i in o["issues"])
    kr1, kr2, kr3 = o["key_results"]
    assert any("task" in i for i in kr1["issues"]) and any("no number" in i for i in kr1["issues"])
    assert any("no number" in i for i in kr2["issues"])
    assert kr3["ok"] is True
    assert out["score"] < 80 and out["grade"] != "ready"
    good = call("lint_okrs", objectives=[{"objective": "Make onboarding effortless for self-serve teams", "key_results": ["Increase week-1 activation from 31% to 45%", "Reduce median time-to-first-value from 3 days to 1 day", "Cut onboarding support tickets from 120 to 60 per month"]}])
    assert good["score"] >= 80 and good["grade"] == "ready"
    with pytest.raises(ToolError):
        call("lint_okrs", objectives=[{"objective": "", "key_results": []}])


def test_grade_progress_status_and_run_rate():
    out = call(
        "grade_progress",
        key_results=[
            {"name": "Activation", "start": 30, "target": 50, "current": 38, "type": "committed"},
            {"name": "Churn", "start": 8, "target": 4, "current": 7.5},
            {"name": "NPS", "start": 20, "target": 40, "current": 41},
        ],
        period_start="2026-10-01", period_end="2026-12-31", as_of="2026-11-15",
    )
    assert out["period"]["elapsed_pct"] == 48.9  # 45 of Q4's 92 days are behind us on Nov 15
    act, churn, nps = out["key_results"]
    assert act["progress_pct"] == 40.0 and act["status"] == "on track" and act["score"] == 0.4
    assert act["needed_per_week"] == round(12 / (47 / 7), 2)  # Nov 15..Dec 31 inclusive = 47 days
    assert churn["direction"] == "down" and churn["progress_pct"] == 12.5 and churn["status"] == "off track"
    assert nps["status"] == "done" and nps["score"] == 1.0
    assert out["committed_at_risk"] == [] and out["worst"]["name"] == "Churn"
    with pytest.raises(ToolError, match="target equals start"):
        call("grade_progress", key_results=[{"name": "x", "start": 5, "target": 5, "current": 5}], period_start="2026-10-01", period_end="2026-12-31")


def test_forecast_key_result_linear_trend():
    out = call(
        "forecast_key_result",
        history=[{"date": "2026-10-05", "value": 31}, {"date": "2026-10-12", "value": 33}, {"date": "2026-10-19", "value": 35}, {"date": "2026-10-26", "value": 37}],
        target=45, period_end="2026-12-31",
    )
    assert out["slope_per_week"] == 2.0 and out["r_squared"] == 1.0
    assert out["projected_end_value"] == 55.86
    assert out["reaches_target_on_trend"] is True and out["projected_hit_date"] == "2026-11-23"
    miss = call("forecast_key_result", history=[{"date": "2026-10-05", "value": 31}, {"date": "2026-10-12", "value": 31.5}, {"date": "2026-10-19", "value": 32}], target=45, period_end="2026-12-31")
    assert miss["reaches_target_on_trend"] is False and miss["slope_multiplier_needed"] > 1
    with pytest.raises(ToolError):
        call("forecast_key_result", history=[{"date": "2026-10-05", "value": 31}], target=45, period_end="2026-12-31")


def test_okr_calendar_dates():
    out = call("okr_calendar", period_start="2026-10-01", period_end="2026-12-31", checkin="weekly", checkin_weekday="monday", as_of="2026-09-27")
    assert out["checkins"][0] == "2026-10-05" and out["checkins"][-1] == "2026-12-28"
    assert len(out["checkins"]) == 13
    assert out["mid_cycle_review"] == "2026-11-16"
    assert out["scoring_day"] == "2027-01-01" and out["draft_next_cycle"]["start"] == "2026-12-10"
    assert out["events"][0]["event"].startswith("Kickoff") and out["events"][0]["date"] == "2026-10-01"
    with pytest.raises(ToolError):
        call("okr_calendar", period_start="2026-10-01", period_end="2026-09-01")


def test_bad_arguments_raise_clean_error():
    with pytest.raises(ToolError):
        A.get_tool("lint_okrs").call({"objectives": "Grow revenue"})


def test_grade_on_last_day_still_needs_a_rate():
    out = call("grade_progress", key_results=[{"name": "A", "start": 0, "target": 10, "current": 9}], period_start="2026-10-01", period_end="2026-12-31", as_of="2026-12-31")
    assert out["period"]["days"] == 92 and out["key_results"][0]["needed_per_week"] == 7.0  # 1 unit in the 1 day left
