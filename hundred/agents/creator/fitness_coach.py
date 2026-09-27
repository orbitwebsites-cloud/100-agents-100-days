"""Fitness Coach — strength programming and nutrition targets built on the formulas coaches actually use."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Literal

from ...core import Agent, ToolError
from ._common import positive, round_to

AGENT = Agent(
    slug="fitness-coach",
    name="Fitness Coach",
    category="creator",
    tagline="Strength plans and calorie/macro targets computed with real formulas, progressed like a coach would.",
    description=(
        "Coaches like a certified strength coach with a dietitian on speed-dial: estimates 1RM from any "
        "rep set (Epley, Brzycki, Lombardi, O'Conner), writes progressive-overload blocks (linear, 5/3/1, "
        "double progression) rounded to real plates, computes BMR/TDEE with Mifflin-St Jeor and sets "
        "macros with hard safety floors, audits weekly training volume per muscle against evidence-based "
        "set ranges, loads the bar, and sets heart-rate zones. Not medical advice; it says so when it matters."
    ),
    triggers=[
        "build me a workout / training program",
        "what's my one rep max",
        "how many calories and protein should I eat to lose fat / build muscle",
        "progressive overload plan for squat / bench / deadlift",
        "is my training volume enough / too much",
        "what plates do I put on the bar for 102.5 kg",
        "heart rate zones for zone 2 training",
    ],
    examples=[
        "I'm 34M, 82 kg, 180 cm, lift 4x/week, want to lose fat without losing strength. Calories and macros?",
        "Bench 80 kg for 6 reps — what's my 1RM and give me a 12-week 5/3/1 plan.",
        "Here's my current week of training — am I under-training back and over-training chest?",
    ],
    connectors=["Google Sheets", "Notion", "Apple Health", "Strava", "MyFitnessPal", "Google Calendar"],
    playbook="""
    ## Standard
    You are a strength and conditioning coach (CSCS-level thinking) who also knows nutrition
    well enough to set targets and to know when to refer out. Excellence means the client
    progresses measurably over 8-12 weeks without injury or a crash diet: loads rise, body
    composition moves in the intended direction at a safe rate, adherence stays above 80%.
    The metric that matters is **adherence-adjusted progress**: the best plan is the one the
    client actually follows for 12 weeks.

    **Scope note (say this once, briefly):** general fitness guidance, not medical advice.
    Refer to a doctor or registered dietitian for pregnancy, under-18s, eating disorders or
    disordered eating history, diabetes, heart/kidney conditions, injuries, or any
    prescription that interacts with diet or exercise. Never provide a plan under
    1,200 kcal/day, and never coach weight loss for someone describing ED symptoms.

    ## Intake
    Minimum: goal, training age (months/years lifting), days per week available, sex, age,
    height, weight. Ask for at most 3 missing items; assume the rest (e.g. moderate activity,
    3 days/week, no injuries) and say so. If the person reports pain, an injury, pregnancy,
    or medical conditions, give the scope note and keep advice conservative.

    ## Procedure
    1. **Anchor the numbers.** For every lift they report ("80 kg × 6"), call
       `fitness_coach__one_rep_max`. Use the tool's estimate (Epley/Brzycki mean) as the
       working 1RM; never trust a 1RM extrapolated from > 10 reps for programming — take the
       tool's reliability flag seriously and prescribe a 3-5 rep test instead.
    2. **Set the nutrition targets** when the goal involves body composition: call
       `fitness_coach__tdee_and_macros` with sex, age, height, weight, activity and goal. It
       applies Mifflin-St Jeor, the activity multiplier, the calorie delta for the requested
       weekly change, protein/fat/carb splits and the safety floors. Present its flags
       verbatim: an aggressive deficit is a decision the client makes knowingly or not at all.
    3. **Choose the progression model** from training age: < 6 months → linear (add weight
       every session/week); 6-24 months → double progression for accessories and linear or
       5/3/1 for the main lifts; > 2 years → 5/3/1 or a block plan. Call
       `fitness_coach__progression_plan` per main lift; it rounds to real plate increments
       and builds deloads in. Do not hand-compute percentages.
    4. **Write the week** — exercises, sets × reps, RPE/%1RM, rest — then call
       `fitness_coach__weekly_volume_audit` on it. It maps every exercise to muscle groups and
       counts hard sets per muscle per week against the 10-20 set landmarks and 2×/week
       frequency. Fix under- and over-trained muscles before showing the plan.
    5. **Make the loads real.** For any awkward weight (e.g. 102.5 kg, 137.5 lb) call
       `fitness_coach__plate_loading` so the client knows what to put on each side.
    6. **Conditioning** (if in scope): call `fitness_coach__heart_rate_zones` with age and
       resting HR for Karvonen zones; prescribe Zone 2 in minutes/week, not "go for a run".
    7. **Self-check:** every session has a warm-up ramp; the plan states what to do when a
       rep target is missed (repeat the weight, then drop 10%); nothing violates the floors.

    ## Frameworks
    - **1RM:** Epley = w × (1 + r/30); Brzycki = w × 36 / (37 − r). Both are accurate to a few
      percent up to ~10 reps; error grows fast beyond.
    - **Volume landmarks (per muscle, per week):** ~10 hard sets is the floor for growth for
      most trained lifters, 10-20 is the productive range, 20+ needs deliberate recovery.
      Frequency ≥ 2×/week per muscle outperforms 1× at matched volume.
    - **Progressive overload order:** add reps within range → add load (2.5 kg upper, 5 kg
      lower) → add a set. Deload every 4th-6th week (−40 to −50% volume) or when two sessions
      in a row miss reps.
    - **5/3/1:** training max = 90% of 1RM; week 1 65/75/85% ×5, week 2 70/80/90% ×3, week 3
      75/85/95% ×5/3/1+, week 4 deload 40/50/60%; TM +2.5 kg upper / +5 kg lower per cycle.
    - **Nutrition:** Mifflin-St Jeor BMR; activity 1.2 (sedentary) → 1.9 (athlete); fat loss
      at 0.5-1% bodyweight/week; protein 1.6-2.2 g/kg; fat ≥ 0.6 g/kg and ~25% of calories;
      carbs fill the rest and go up on hard training days.
    - **HR zones:** HRmax ≈ 208 − 0.7 × age (Tanaka); Karvonen zones on heart-rate reserve.

    ## Output format
    ```
    # <Name> — <goal>, <weeks>-week block
    _General guidance, not medical advice. <scope line if relevant>_

    **Numbers:** 1RM est. — Squat NNN / Bench NNN / Deadlift NNN (from tool) · TDEE NNNN kcal
    **Targets:** NNNN kcal · P NNN g · F NN g · C NNN g · <rate>/week  <flags from tool>

    ## Week template (<N> days)
    | Day | Exercise | Sets × reps | Load / RPE | Rest |
    |---|---|---|---|---|

    ## Progression (per main lift)
    | Week | Squat | Bench | Deadlift | Notes |
    |---|---|---|---|---|
    (deload weeks marked)

    ## Volume check
    <muscle: N sets/wk, frequency ×/wk> … → <changes made>

    ## Rules
    - Missed reps twice → repeat load; three times → −10%, rebuild.
    - Warm-up ramp: bar ×10, 50% ×5, 70% ×3, 85% ×1, then work sets.
    - Re-test 1RM at week <N> with a 3-rep max, not a true single.
    ```

    ## Anti-patterns
    - Giving a 1,400 kcal target to an 85 kg man because "he wants fast results". Floors exist.
    - Programming from a 1RM estimated off a 15-rep set.
    - 30 sets of chest, 6 of back. The audit tool will catch it; look at it.
    - "Lift heavier each week" with no deload and no missed-rep rule.
    - Percentages like 87.3% of 1RM that no bar can be loaded to. Round to plates.
    - Diagnosing pain. Pain → refer out and program around it.
    """,
)

UNIT_STEP = {"kg": 2.5, "lb": 5.0}


def _unit(unit: str) -> str:
    u = unit.strip().lower()
    if u in ("kg", "kgs", "kilograms"):
        return "kg"
    if u in ("lb", "lbs", "pounds"):
        return "lb"
    raise ToolError("unit must be 'kg' or 'lb'")


@AGENT.tool
def one_rep_max(weight: float, reps: int, unit: Literal["kg", "lb"] = "kg") -> dict:
    """Estimate a one-rep max from a weight × reps set (Epley, Brzycki, Lombardi, O'Conner) with a %1RM table.

    Returns a working estimate (mean of Epley and Brzycki), all four formulas, a reliability flag
    for high-rep sets, and training loads at 50-95% rounded to real plate increments.

    Args:
        weight: Weight lifted for the set.
        reps: Reps completed with good form (1-30).
        unit: kg or lb (affects rounding: 2.5 kg / 5 lb).
    """
    w = positive(weight, "weight", 1000)
    if not isinstance(reps, int) or not 1 <= reps <= 30:
        raise ToolError("reps must be an integer between 1 and 30")
    u = _unit(unit)
    step = UNIT_STEP[u]
    if reps == 1:
        est = w
        formulas = {"actual_single": w}
        reliability = "actual single — no estimate needed"
    else:
        epley = w * (1 + reps / 30)
        brzycki = w * 36 / (37 - reps)
        lombardi = w * reps**0.1
        oconner = w * (1 + 0.025 * reps)
        formulas = {"epley": round(epley, 1), "brzycki": round(brzycki, 1), "lombardi": round(lombardi, 1), "oconner": round(oconner, 1)}
        est = (epley + brzycki) / 2
        reliability = "good (≤ 5 reps)" if reps <= 5 else "fair (6-10 reps, ±5%)" if reps <= 10 else "poor (> 10 reps — test a 3-5RM before programming)"
    table = {f"{p}%": round_to(est * p / 100, step) for p in (50, 60, 65, 70, 75, 80, 85, 90, 95)}
    return {
        "input": f"{w:g} {u} × {reps}",
        "estimated_1rm": round(est, 1),
        "estimated_1rm_rounded": round_to(est, step),
        "formulas": formulas,
        "reliability": reliability,
        "training_max_90pct": round_to(est * 0.9, step),
        "percent_table": table,
        "unit": u,
        "verdict": f"Estimated 1RM ≈ {round_to(est, step):g} {u} ({reliability}).",
    }


@AGENT.tool
def progression_plan(
    exercise: str,
    one_rm: float,
    weeks: int = 8,
    model: Literal["linear", "531", "double_progression"] = "linear",
    unit: Literal["kg", "lb"] = "kg",
    increment: float = 0,
    start_pct: float = 0,
) -> dict:
    """Build a week-by-week loading plan (linear, 5/3/1 or double progression) rounded to plates with deloads built in.

    Linear adds a fixed increment weekly with a deload every 4th week; 5/3/1 runs 4-week
    cycles off a 90% training max; double progression climbs reps 8→12 before adding load.

    Args:
        exercise: Lift name, e.g. "Back squat" (lower-body lifts get a larger default increment).
        one_rm: Current estimated 1RM (from one_rep_max).
        weeks: Plan length in weeks, 1-24 (default 8).
        model: linear (default), 531, or double_progression.
        unit: kg or lb.
        increment: Load added per progression step; 0 = default (2.5 kg / 5 lb upper, 5 kg / 10 lb lower).
        start_pct: Starting working weight as % of 1RM for linear/double progression; 0 = default (80% linear, 70% double).
    """
    orm = positive(one_rm, "one_rm", 1000)
    if not 1 <= weeks <= 24:
        raise ToolError("weeks must be 1-24")
    u = _unit(unit)
    step = UNIT_STEP[u]
    lower = bool(re.search(r"squat|deadlift|lunge|leg|hip|rdl|clean|thrust|press$", exercise.lower())) and not re.search(r"bench|overhead|shoulder|military", exercise.lower())
    inc = increment or (2 * step if lower else step)
    if inc <= 0 or inc > orm:
        raise ToolError("increment must be > 0 and below the 1RM")
    rows = []
    if model == "linear":
        pct = start_pct or 80
        if not 40 <= pct <= 95:
            raise ToolError("start_pct must be 40-95 for linear")
        work = orm * pct / 100
        added = 0.0
        for w in range(1, weeks + 1):
            if w % 4 == 0:
                rows.append({"week": w, "load": round_to((work + added) * 0.6, step), "sets_reps": "3 × 5", "type": "deload", "pct_1rm": round(100 * (work + added) * 0.6 / orm)})
                continue
            load = round_to(work + added, step)
            rows.append({"week": w, "load": load, "sets_reps": "3 × 5", "type": "work", "pct_1rm": round(100 * load / orm)})
            added += inc
            if (work + added) / orm > 0.95:
                rows[-1]["note"] = "Approaching 95% 1RM — re-test and reset to 85% next block."
    elif model == "531":
        tm = round_to(orm * 0.9, step)
        cycle = [
            ("5s week", [(65, "5"), (75, "5"), (85, "5+")]),
            ("3s week", [(70, "3"), (80, "3"), (90, "3+")]),
            ("5/3/1 week", [(75, "5"), (85, "3"), (95, "1+")]),
            ("deload", [(40, "5"), (50, "5"), (60, "5")]),
        ]
        for w in range(1, weeks + 1):
            label, sets = cycle[(w - 1) % 4]
            rows.append({
                "week": w,
                "training_max": tm,
                "type": label,
                "sets": [{"pct_tm": p, "load": round_to(tm * p / 100, step), "reps": r} for p, r in sets],
            })
            if w % 4 == 0 and w < weeks:
                tm = round_to(tm + inc, step)
    else:
        pct = start_pct or 70
        if not 40 <= pct <= 90:
            raise ToolError("start_pct must be 40-90 for double progression")
        load = round_to(orm * pct / 100, step)
        reps = 8
        for w in range(1, weeks + 1):
            rows.append({"week": w, "load": load, "sets_reps": f"3 × {reps}", "type": "work", "rule": "hit 3×12 with 1-2 reps in reserve → add load, reset to 8"})
            if reps >= 12:
                reps = 8
                load = round_to(load + inc, step)
            else:
                reps += 1
    last = rows[-1]
    end_load = last.get("load") or (last["sets"][-1]["load"] if "sets" in last else None)
    return {
        "exercise": exercise,
        "model": model,
        "unit": u,
        "one_rm": orm,
        "increment_per_step": inc,
        "weeks": rows,
        "end_top_load": end_load,
        "rules": [
            "Missed reps twice in a row → repeat the load; three times → drop 10% and rebuild.",
            "Warm-up ramp: empty bar ×10, 50% ×5, 70% ×3, 85% ×1, then work sets.",
            "Deload weeks are not optional; skip one and the next block stalls.",
        ],
        "summary": f"{model} plan for {exercise}: {weeks} weeks, {inc:g} {u} per step, top load ends at {end_load:g} {u}.",
    }


ACTIVITY = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "very": 1.725, "athlete": 1.9}


@AGENT.tool
def tdee_and_macros(
    sex: Literal["male", "female"],
    age: int,
    height_cm: float,
    weight_kg: float,
    activity: Literal["sedentary", "light", "moderate", "very", "athlete"] = "moderate",
    goal: Literal["maintain", "lose", "gain"] = "maintain",
    weekly_change_kg: float = 0,
) -> dict:
    """Compute BMR (Mifflin-St Jeor), TDEE, calorie target and protein/fat/carb grams with safety floors and flags.

    Applies the 7,700 kcal/kg rule for the requested weekly change, protein at 1.6-2.2 g/kg by goal,
    fat at ~25% of calories (≥ 0.6 g/kg), carbs as the remainder; never returns under 1,200 kcal.

    Args:
        sex: male or female (biological sex for the BMR equation).
        age: Age in years (18-90).
        height_cm: Height in centimetres.
        weight_kg: Current bodyweight in kilograms.
        activity: sedentary (desk, no exercise), light (1-3 sessions/wk), moderate (3-5), very (6-7), athlete (2×/day or physical job).
        goal: maintain, lose or gain.
        weekly_change_kg: Desired change per week in kg (positive number); 0 = default 0.5 for lose, 0.25 for gain.
    """
    if not isinstance(age, int) or not 18 <= age <= 90:
        raise ToolError("age must be 18-90 (under-18s: refer to a paediatric professional)")
    h = positive(height_cm, "height_cm", 250)
    w = positive(weight_kg, "weight_kg", 400)
    if h < 120:
        raise ToolError("height_cm looks wrong (< 120 cm)")
    if w < 30:
        raise ToolError("weight_kg looks wrong (< 30 kg) — this tool is not appropriate; refer to a professional")
    if weekly_change_kg < 0 or weekly_change_kg > 2:
        raise ToolError("weekly_change_kg must be between 0 and 2 (as a positive number)")
    bmr = 10 * w + 6.25 * h - 5 * age + (5 if sex == "male" else -161)
    tdee = bmr * ACTIVITY[activity]
    rate = weekly_change_kg or {"maintain": 0.0, "lose": 0.5, "gain": 0.25}[goal]
    delta_per_day = rate * 7700 / 7
    if goal == "lose":
        target = tdee - delta_per_day
    elif goal == "gain":
        target = tdee + delta_per_day
    else:
        target, rate = tdee, 0.0
    flags = []
    floor = 1200 if sex == "female" else 1500
    if target < floor:
        flags.append(f"Target ({target:.0f} kcal) is below the {floor} kcal floor — raised to {floor}. Slow the rate instead.")
        target = floor
    deficit_pct = (tdee - target) / tdee * 100 if tdee else 0
    if goal == "lose" and deficit_pct > 25:
        flags.append(f"Deficit is {deficit_pct:.0f}% of TDEE (> 25%): expect strength and muscle loss and poor adherence. 15-20% is the sweet spot.")
    if goal == "lose" and rate > 0.01 * w:
        flags.append(f"{rate:g} kg/week is over 1% of bodyweight per week; cap at {0.01 * w:.2f} kg/week unless supervised.")
    if goal == "gain" and delta_per_day > 500:
        flags.append("Surplus over 500 kcal/day mostly adds fat; 250-400 is the productive range.")
    protein_per_kg = {"lose": 2.0, "maintain": 1.6, "gain": 1.8}[goal]
    bmi = w / (h / 100) ** 2
    protein_basis = w
    if bmi >= 30:
        protein_basis = 22 * (h / 100) ** 2  # lean-mass proxy: scale protein to a BMI-22 reference weight
        flags.append("BMI ≥ 30: protein scaled to a reference bodyweight (BMI 22) rather than total weight.")
    protein_g = protein_per_kg * protein_basis
    fat_g = max(0.6 * w, 0.25 * target / 9)
    if protein_g * 4 + fat_g * 9 > target:
        fat_g = max(0.6 * w, (target - protein_g * 4) / 9)
        if protein_g * 4 + fat_g * 9 > target:
            flags.append("Calorie target too low to fit protein and minimum fat — rate is too aggressive.")
    carbs_g = max(0.0, (target - protein_g * 4 - fat_g * 9) / 4)
    return {
        "scope_note": "General guidance, not medical advice. See a doctor/dietitian for pregnancy, eating disorders, diabetes or other conditions.",
        "bmr_kcal": round(bmr),
        "tdee_kcal": round(tdee),
        "activity_multiplier": ACTIVITY[activity],
        "goal": goal,
        "weekly_change_kg": rate,
        "daily_delta_kcal": round(delta_per_day) if goal != "maintain" else 0,
        "target_kcal": round(target),
        "deficit_pct_of_tdee": round(deficit_pct, 1) if goal == "lose" else 0.0,
        "bmi": round(bmi, 1),
        "macros_g": {"protein": round(protein_g), "fat": round(fat_g), "carbs": round(carbs_g)},
        "macros_pct": {"protein": round(100 * protein_g * 4 / target), "fat": round(100 * fat_g * 9 / target), "carbs": round(100 * carbs_g * 4 / target)},
        "protein_g_per_kg": round(protein_g / w, 2),
        "weeks_to_lose_5kg": round(5 / rate, 1) if goal == "lose" and rate else None,
        "flags": flags,
        "verdict": f"TDEE ≈ {tdee:.0f} kcal; target {target:.0f} kcal/day for {goal}" + (f" at {rate:g} kg/week" if rate else "") + f" — P {protein_g:.0f} / F {fat_g:.0f} / C {carbs_g:.0f} g." + (" " + " ".join(flags) if flags else ""),
    }


# exercise keyword → (primary muscles, secondary muscles)
MUSCLE_MAP: list[tuple[re.Pattern, list[str], list[str]]] = [
    (re.compile(r"back squat|front squat|\bsquat|leg press|hack squat|lunge|split squat|step.?up|bulgarian"), ["quads", "glutes"], ["hamstrings"]),
    (re.compile(r"leg extension"), ["quads"], []),
    (re.compile(r"\bdeadlift|\brdl|romanian|good morning|hip hinge|back extension"), ["hamstrings", "glutes"], ["back"]),
    (re.compile(r"sumo"), ["glutes", "quads"], ["hamstrings", "back"]),
    (re.compile(r"leg curl|nordic"), ["hamstrings"], []),
    (re.compile(r"hip thrust|glute bridge|kickback"), ["glutes"], ["hamstrings"]),
    (re.compile(r"calf"), ["calves"], []),
    (re.compile(r"bench|push.?up|chest press|incline|decline|dip|fly|flye|pec"), ["chest"], ["triceps", "shoulders"]),
    (re.compile(r"overhead press|\bohp|shoulder press|military|push press|arnold"), ["shoulders"], ["triceps"]),
    (re.compile(r"lateral raise|side raise|upright row"), ["shoulders"], []),
    (re.compile(r"rear delt|face pull|reverse fly|reverse flye"), ["shoulders"], ["back"]),
    (re.compile(r"pull.?up|chin.?up|pulldown|lat pull"), ["back"], ["biceps"]),
    (re.compile(r"\brow\b|rows|seal row|pendlay|t-bar|cable row"), ["back"], ["biceps"]),
    (re.compile(r"shrug"), ["back"], []),
    (re.compile(r"curl(?!.*leg)"), ["biceps"], []),
    (re.compile(r"tricep|pushdown|skull|close.?grip|kickback"), ["triceps"], []),
    (re.compile(r"plank|crunch|ab |abs|leg raise|pallof|rollout|dead bug|hanging"), ["core"], []),
    (re.compile(r"clean|snatch|kettlebell swing|kb swing"), ["glutes", "hamstrings", "back"], ["quads", "shoulders"]),
]


@AGENT.tool
def weekly_volume_audit(sessions: list[dict], training_age: Literal["beginner", "intermediate", "advanced"] = "intermediate") -> dict:
    """Count hard sets per muscle group per week from a training plan and flag under/over-trained muscles and low frequency.

    Maps exercise names to primary (1 set) and secondary (0.5 set) muscles, then compares against
    the 10-20 sets/week landmark and 2×/week frequency.

    Args:
        sessions: One dict per training day: {"day": "Mon", "exercises": [{"name": "Back squat", "sets": 4, "reps": 5, "rpe": 8 (optional)}]}.
        training_age: beginner (landmarks 6-12 sets), intermediate (10-20, default) or advanced (12-22).
    """
    if not sessions:
        raise ToolError("sessions is empty")
    if len(sessions) > 14:
        raise ToolError("Give at most 14 sessions (one training week, two if double days)")
    landmarks = {"beginner": (6, 12), "intermediate": (10, 20), "advanced": (12, 22)}[training_age]
    direct: Counter[str] = Counter()
    effective: Counter[str] = Counter()
    days_per_muscle: dict[str, set] = defaultdict(set)
    unmapped = []
    total_sets = 0
    for si, s in enumerate(sessions, 1):
        if not isinstance(s, dict) or not isinstance(s.get("exercises"), list):
            raise ToolError(f"session #{si} needs an 'exercises' list")
        day = str(s.get("day", f"Day {si}"))
        for ex in s["exercises"]:
            if not isinstance(ex, dict) or not ex.get("name"):
                raise ToolError(f"session #{si}: each exercise needs a 'name'")
            name = str(ex["name"]).lower()
            sets = ex.get("sets", 0)
            if not isinstance(sets, (int, float)) or sets < 0 or sets > 30:
                raise ToolError(f"{ex['name']}: sets must be 0-30")
            rpe = ex.get("rpe")
            if rpe is not None and (not isinstance(rpe, (int, float)) or rpe < 5):
                continue  # warm-ups and easy sets do not count
            total_sets += sets
            hit = None
            for rx, prim, sec in MUSCLE_MAP:
                if rx.search(name):
                    hit = (prim, sec)
                    break
            if not hit:
                unmapped.append(ex["name"])
                continue
            for m in hit[0]:
                direct[m] += sets
                effective[m] += sets
                days_per_muscle[m].add(day)
            for m in hit[1]:
                effective[m] += 0.5 * sets
    muscles = ["chest", "back", "shoulders", "quads", "hamstrings", "glutes", "biceps", "triceps", "calves", "core"]
    lo, hi = landmarks
    table, flags = [], []
    for m in muscles:
        eff = effective.get(m, 0.0)
        freq = len(days_per_muscle.get(m, set()))
        status = "under" if eff < lo else "over" if eff > hi else "ok"
        if m in ("calves", "core") and eff == 0:
            status = "none"
        table.append({"muscle": m, "direct_sets": direct.get(m, 0), "effective_sets": round(eff, 1), "frequency_days": freq, "status": status})
        if status == "under" and m not in ("calves", "core"):
            flags.append(f"{m}: {eff:g} effective sets/week (< {lo}) — add {int(lo - eff + 0.5)}+ sets.")
        elif status == "over":
            flags.append(f"{m}: {eff:g} effective sets/week (> {hi}) — recovery risk; trim or split across more days.")
        if eff >= lo and freq < 2:
            flags.append(f"{m}: all volume on one day — split across 2+ days for the same sets.")
    push = effective.get("chest", 0) + effective.get("shoulders", 0) + effective.get("triceps", 0)
    pull = effective.get("back", 0) + effective.get("biceps", 0)
    if push and pull and push / pull > 1.5:
        flags.append(f"Push:pull ratio {push / pull:.1f}:1 — add rowing/pulling to protect the shoulders.")
    if unmapped:
        flags.append(f"Could not map: {', '.join(sorted(set(unmapped))[:8])} — tell me the muscles worked.")
    return {
        "training_age": training_age,
        "landmark_sets_per_week": list(landmarks),
        "sessions": len(sessions),
        "total_hard_sets": total_sets,
        "per_muscle": table,
        "push_pull_ratio": round(push / pull, 2) if pull else None,
        "unmapped_exercises": sorted(set(unmapped)),
        "flags": flags,
        "verdict": "Volume is balanced." if not flags else f"{len(flags)} change(s) recommended.",
    }


@AGENT.tool
def plate_loading(target: float, bar: float = 20, unit: Literal["kg", "lb"] = "kg", plates: list[float] | None = None) -> dict:
    """Work out which plates go on each side of the bar for a target load, and the nearest loadable weight.

    Args:
        target: Total weight wanted on the bar (including the bar).
        bar: Bar weight (default 20 kg; use 45 for a lb bar, 15 for a women's bar).
        unit: kg or lb.
        plates: Available plate sizes (per plate). Default kg: 25, 20, 15, 10, 5, 2.5, 1.25; lb: 45, 35, 25, 10, 5, 2.5.
    """
    t = positive(target, "target", 1000)
    b = positive(bar, "bar", 100)
    u = _unit(unit)
    avail = plates or ({"kg": [25, 20, 15, 10, 5, 2.5, 1.25], "lb": [45, 35, 25, 10, 5, 2.5]}[u])
    avail = sorted({float(p) for p in avail if isinstance(p, (int, float)) and p > 0}, reverse=True)
    if not avail:
        raise ToolError("plates must contain positive numbers")
    if t < b:
        raise ToolError(f"target ({t:g}) is lighter than the bar ({b:g})")
    per_side = (t - b) / 2
    remaining, chosen = per_side, []
    for p in avail:
        while remaining + 1e-9 >= p:
            chosen.append(p)
            remaining -= p
    loaded = b + 2 * sum(chosen)
    smallest = avail[-1]
    return {
        "target": t,
        "bar": b,
        "unit": u,
        "per_side_needed": round(per_side, 3),
        "plates_per_side": chosen,
        "loaded_total": round(loaded, 3),
        "exact": abs(loaded - t) < 1e-6,
        "short_by": round(t - loaded, 3),
        "next_step_up": round(loaded + 2 * smallest, 3),
        "verdict": (f"{t:g} {u}: " if abs(loaded - t) < 1e-6 else f"{t:g} {u} not loadable; nearest below is {loaded:g} {u}: ") + (" + ".join(f"{p:g}" for p in chosen) if chosen else "empty bar") + " per side.",
    }


@AGENT.tool
def heart_rate_zones(age: int, resting_hr: int = 60, max_hr: int = 0) -> dict:
    """Compute Karvonen heart-rate zones (1-5) from age and resting HR, using Tanaka's HRmax unless a measured max is given.

    Args:
        age: Age in years (10-100).
        resting_hr: Resting heart rate in bpm, measured on waking (default 60).
        max_hr: Measured maximum heart rate if known; 0 = estimate with 208 − 0.7 × age.
    """
    if not isinstance(age, int) or not 10 <= age <= 100:
        raise ToolError("age must be 10-100")
    if not 30 <= resting_hr <= 120:
        raise ToolError("resting_hr must be 30-120 bpm")
    hrmax = max_hr or round(208 - 0.7 * age)
    if not 100 <= hrmax <= 230 or hrmax <= resting_hr:
        raise ToolError("max_hr must be between 100 and 230 and above resting_hr")
    hrr = hrmax - resting_hr
    bands = [("Zone 1 — recovery", 50, 60), ("Zone 2 — aerobic base", 60, 70), ("Zone 3 — tempo", 70, 80), ("Zone 4 — threshold", 80, 90), ("Zone 5 — VO2max", 90, 100)]
    zones = [{"zone": name, "pct_hrr": [lo, hi], "bpm": [round(resting_hr + hrr * lo / 100), round(resting_hr + hrr * hi / 100)]} for name, lo, hi in bands]
    return {
        "max_hr": hrmax,
        "max_hr_source": "measured" if max_hr else "Tanaka (208 − 0.7 × age)",
        "resting_hr": resting_hr,
        "heart_rate_reserve": hrr,
        "zones": zones,
        "zone2_bpm": zones[1]["bpm"],
        "summary": f"HRmax {hrmax}, HRR {hrr}; Zone 2 = {zones[1]['bpm'][0]}-{zones[1]['bpm'][1]} bpm (conversational pace).",
    }
