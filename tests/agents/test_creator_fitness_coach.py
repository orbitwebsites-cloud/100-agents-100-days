"""Fitness Coach tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("fitness-coach")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_one_rep_max_formulas():
    out = call("one_rep_max", weight=80, reps=6, unit="kg")
    assert out["formulas"]["epley"] == 96.0
    assert out["formulas"]["brzycki"] == round(80 * 36 / 31, 1)
    assert out["estimated_1rm"] == round((96 + 80 * 36 / 31) / 2, 1)
    assert out["estimated_1rm_rounded"] == 95.0
    assert out["percent_table"]["85%"] == 80.0
    assert out["reliability"].startswith("fair")
    poor = call("one_rep_max", weight=100, reps=15, unit="lb")
    assert poor["reliability"].startswith("poor")
    single = call("one_rep_max", weight=100, reps=1)
    assert single["estimated_1rm"] == 100


def test_one_rep_max_bad_reps():
    with pytest.raises(ToolError):
        call("one_rep_max", weight=80, reps=0)
    with pytest.raises(ToolError):
        call("one_rep_max", weight=-5, reps=5)


def test_progression_plan_531_cycle():
    out = call("progression_plan", exercise="Back squat", one_rm=140, weeks=8, model="531", unit="kg")
    w1 = out["weeks"][0]
    assert w1["training_max"] == 125.0  # 0.9 × 140 = 126 → 125 on 2.5 kg plates
    assert [s["load"] for s in w1["sets"]] == [82.5, 95.0, 107.5]  # 81.25 / 93.75 / 106.25 rounded half-up to 2.5
    assert out["weeks"][3]["type"] == "deload"
    assert out["weeks"][4]["training_max"] == 130.0  # +5 kg for a lower-body lift
    assert out["weeks"][6]["sets"][-1]["reps"] == "1+"


def test_progression_plan_linear_and_double():
    lin = call("progression_plan", exercise="Bench press", one_rm=100, weeks=5, model="linear", unit="kg")
    assert [w["load"] for w in lin["weeks"]] == [80.0, 82.5, 85.0, 52.5, 87.5]
    assert lin["weeks"][3]["type"] == "deload"
    dbl = call("progression_plan", exercise="Dumbbell curl", one_rm=20, weeks=6, model="double_progression", unit="kg", increment=2.5, start_pct=70)
    assert [w["sets_reps"] for w in dbl["weeks"]] == ["3 × 8", "3 × 9", "3 × 10", "3 × 11", "3 × 12", "3 × 8"]
    assert dbl["weeks"][5]["load"] == 17.5


def test_progression_plan_bad_input():
    with pytest.raises(ToolError):
        call("progression_plan", exercise="Squat", one_rm=100, weeks=30)
    with pytest.raises(ToolError):
        call("progression_plan", exercise="Squat", one_rm=100, increment=500)


def test_tdee_and_macros_mifflin_and_floors():
    out = call("tdee_and_macros", sex="male", age=34, height_cm=180, weight_kg=82, activity="moderate", goal="lose")
    bmr = 10 * 82 + 6.25 * 180 - 5 * 34 + 5
    assert out["bmr_kcal"] == round(bmr)
    assert out["tdee_kcal"] == round(bmr * 1.55)
    assert out["target_kcal"] == round(bmr * 1.55 - 0.5 * 7700 / 7)
    assert out["macros_g"]["protein"] == 164
    assert out["flags"] == []
    crash = call("tdee_and_macros", sex="female", age=30, height_cm=160, weight_kg=55, activity="sedentary", goal="lose", weekly_change_kg=1.0)
    assert crash["target_kcal"] == 1200
    assert any("floor" in f for f in crash["flags"]) and any("1% of bodyweight" in f for f in crash["flags"])
    assert "not medical advice" in crash["scope_note"]


def test_tdee_rejects_minors_and_bad_values():
    with pytest.raises(ToolError):
        call("tdee_and_macros", sex="male", age=15, height_cm=170, weight_kg=60)
    with pytest.raises(ToolError):
        call("tdee_and_macros", sex="male", age=30, height_cm=170, weight_kg=60, weekly_change_kg=5)


def test_weekly_volume_audit_counts_and_flags():
    sessions = [
        {"day": "Mon", "exercises": [{"name": "Bench press", "sets": 5}, {"name": "Incline DB press", "sets": 4}, {"name": "Cable fly", "sets": 4}, {"name": "Tricep pushdown", "sets": 3}]},
        {"day": "Thu", "exercises": [{"name": "Bench press", "sets": 5}, {"name": "Barbell row", "sets": 3}, {"name": "Back squat", "sets": 4}, {"name": "Bench warm-up", "sets": 2, "rpe": 3}]},
    ]
    out = call("weekly_volume_audit", sessions=sessions)
    per = {r["muscle"]: r for r in out["per_muscle"]}
    assert per["chest"]["direct_sets"] == 18 and per["chest"]["status"] == "ok"
    assert per["triceps"]["effective_sets"] == 3 + 0.5 * 18
    assert per["back"]["direct_sets"] == 3 and per["back"]["status"] == "under"
    assert per["quads"]["frequency_days"] == 1
    assert any("Push:pull" in f for f in out["flags"]) and any("back:" in f for f in out["flags"])
    assert out["total_hard_sets"] == 28


def test_weekly_volume_audit_bad_input():
    with pytest.raises(ToolError):
        call("weekly_volume_audit", sessions=[{"day": "Mon"}])


def test_plate_loading_greedy_and_nearest():
    out = call("plate_loading", target=102.5, bar=20, unit="kg")
    assert out["plates_per_side"] == [25.0, 15.0, 1.25] and out["exact"] is True
    lb = call("plate_loading", target=137.5, bar=45, unit="lb")
    assert lb["plates_per_side"] == [45.0] and lb["loaded_total"] == 135.0 and lb["exact"] is False
    odd = call("plate_loading", target=101, bar=20, unit="kg")
    assert odd["exact"] is False and odd["loaded_total"] == 100.0 and odd["next_step_up"] == 102.5


def test_plate_loading_lighter_than_bar():
    with pytest.raises(ToolError):
        call("plate_loading", target=15, bar=20)


def test_heart_rate_zones_karvonen():
    out = call("heart_rate_zones", age=40, resting_hr=60)
    assert out["max_hr"] == 180
    assert out["heart_rate_reserve"] == 120
    assert out["zone2_bpm"] == [132, 144]
    with pytest.raises(ToolError):
        call("heart_rate_zones", age=40, resting_hr=200)
