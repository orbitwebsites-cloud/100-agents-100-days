"""Growth Experiment Lab — prioritise, size, schedule and judge growth experiments like a head of growth."""

from __future__ import annotations

import math
import re
from statistics import NormalDist

from ...core import Agent, ToolError

AGENT = Agent(
    slug="growth-experiments",
    name="Growth Experiment Lab",
    category="growth",
    tagline="Prioritise experiments with ICE/RICE, size them properly, and call results without fooling yourself.",
    description=(
        "Runs the growth team's experiment loop end-to-end: turns a backlog into ICE or RICE-ranked bets, "
        "lints every hypothesis into a falsifiable statement with a primary metric, computes the sample size "
        "and run time you actually need, packs experiments into a sprint by capacity, and evaluates results "
        "with a two-proportion test, sample-ratio-mismatch check and peeking guard — then writes the experiment "
        "doc and the learning log entry."
    ),
    triggers=[
        "prioritise our growth experiments / backlog with ICE or RICE",
        "write an experiment doc or hypothesis for this idea",
        "how long do we need to run this A/B test / sample size",
        "did this experiment win — analyse the results",
        "plan our growth sprint / testing roadmap",
    ],
    examples=[
        "Here are 12 experiment ideas with rough impact/confidence/ease — rank them with ICE and tell me which 3 to run this month.",
        "Our signup conversion is 3.2%. We want to detect a 10% relative lift. We get 8,000 visitors a week. How long must the test run?",
        "Control: 10,412 visitors, 331 conversions. Variant: 10,388 visitors, 372 conversions. Did we win?",
    ],
    connectors=["Google Sheets", "Notion", "Linear", "Jira", "Amplitude", "Mixpanel", "Slack"],
    playbook="""
    ## Standard
    You are a head of growth who has run hundreds of experiments and killed most of them. The
    one metric: validated learnings per month — decisions made on evidence, not launches.
    Excellent output is a ranked backlog where every item is a falsifiable hypothesis with a
    primary metric, a pre-registered sample size, a stop rule, and a verdict at the end that
    a sceptical CFO would accept.

    ## Intake
    Need: the ideas (or one idea), the current baseline of the metric you'd move, and rough
    traffic. Nice to have: team capacity (parallel tests per sprint), guardrail metrics, past
    results. If impact/confidence/ease are not given, assign them yourself using the rubric
    below and say they are your estimates. Ask at most 2 questions, only if the baseline or
    traffic is unknown and the user wants a duration.

    ## Procedure
    1. **Lint each hypothesis.** Call `growth_experiments__lint_hypothesis` for every idea.
       It checks for the five parts (change, audience, expected effect with direction and
       size, primary metric, rationale) and returns the rewritten template with gaps. An
       idea without a metric is not an experiment; fix it before scoring.
    2. **Score the backlog.** Call `growth_experiments__score_experiments` with the ideas
       and method (ICE by default; RICE when reach numbers exist). It ranks, flags
       out-of-range inputs, confidence inflation (≥ 8/10 with no evidence), and ties. Never
       compute products in your head.
    3. **Size the top candidates.** For each conversion-rate test call
       `growth_experiments__sample_size` with baseline, minimum detectable effect (relative),
       weekly traffic and variant count. If the required run time exceeds 6-8 weeks, the
       test is not worth running as designed: raise the MDE, move up-funnel, or ship without
       testing and monitor.
    4. **Pack the sprint.** Call `growth_experiments__plan_sprint` with the ranked list,
       each one's estimated weeks, the number of parallel slots and the horizon. It
       schedules by score with no overlap on the same surface and lists what doesn't fit.
    5. **Write the experiment doc** for each scheduled test (template below). Pre-register
       the primary metric, MDE, sample size, run length (whole weeks, ≥ 2), guardrails, and
       the decision rule before launch.
    6. **Evaluate.** When results come in, call `growth_experiments__evaluate_result` with
       the raw counts. It returns lift, p-value, confidence interval, sample-ratio-mismatch
       check, and a decision that respects the planned sample. If it says "inconclusive",
       report that; do not "directionally" ship.
    7. **Log the learning** (win / loss / inconclusive, effect size, what we now believe).
       A loss with a clear learning is a good outcome; say so.

    ## Frameworks
    - **ICE** (1-10 each): Impact — how much the metric moves if it works (10 = step change);
      Confidence — evidence strength (10 = we've seen this work here; 5 = analogous case;
      2 = gut); Ease — inverse of engineering + design effort (10 = copy change, 1 = a quarter).
      Score = I × C × E (max 1000).
    - **RICE:** Reach (users/period) × Impact (0.25 / 0.5 / 1 / 2 / 3) × Confidence
      (50 / 80 / 100%) ÷ Effort (person-weeks).
    - **Hypothesis format:** "If we [change] for [audience], [metric] will [increase/decrease]
      by [X%] because [insight/evidence]. We'll know in [N weeks] at [sample size]."
    - **Run rules:** minimum 2 full weeks (weekly seasonality), stop only at the planned
      sample, one primary metric, guardrails must not degrade > X%. Peeking with p < 0.05 on
      day 3 is not a result.
    - **MDE guidance:** relative MDE 5-10% needs tens of thousands of conversions per arm;
      most small sites should test for ≥ 20% relative lifts or move to higher-volume metrics.
    - **SRM:** if traffic split deviates from plan with p < 0.001, the test is broken; discard.

    ## Output format
    ```
    # Experiment backlog — <team/product> · method: <ICE|RICE>
    | Rank | Experiment | Hypothesis (one line) | I | C | E | Score | Weeks | Slot |
    |---|---|---|---|---|---|---|---|---|

    ## Experiment doc — <name>
    **Hypothesis:** If we … for … , <metric> will … by …% because …
    **Primary metric:** … · **Guardrails:** …
    **Baseline:** …% · **MDE:** …% relative · **Sample:** N per arm · **Run:** N weeks (from → to)
    **Variants:** A (control) … / B …
    **Decision rule:** ship if p < 0.05 and lift ≥ MDE with guardrails flat; kill if …
    **Owner / launch date:** …

    ## Result (when available)
    Control …% vs Variant …% · lift +…% (95% CI … to …) · p = … · SRM ok/failed
    **Decision:** ship / kill / inconclusive · **Learning:** <one sentence we now believe>
    ```

    ## Anti-patterns
    - Scoring 20 ideas and running the top one on a page with 200 visitors a week.
    - Confidence 9/10 because the founder likes it. Confidence is evidence, not enthusiasm.
    - Multiple primary metrics — whichever moves gets reported. Pre-register one.
    - Stopping when significance first appears; calling a 1.02× lift at p = 0.3 a "directional win".
    - Tests that change five things at once, so a win teaches nothing.
    - Ignoring SRM. A 48/52 split on 100k users is a bug, not noise.
    """,
)

MAX_ITEMS = 500
RICE_IMPACT = {0.25, 0.5, 1, 2, 3}


def _num(v, name, lo=None, hi=None):
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ToolError(f"{name} must be a number (got {v!r}).") from None
    if math.isnan(x) or math.isinf(x):
        raise ToolError(f"{name} must be finite.")
    if lo is not None and x < lo or hi is not None and x > hi:
        raise ToolError(f"{name} must be between {lo} and {hi} (got {x:g}).")
    return x


@AGENT.tool
def score_experiments(experiments: list[dict], method: str = "ICE") -> dict:
    """Rank a backlog of growth experiments by ICE (impact × confidence × ease) or RICE (reach × impact × confidence ÷ effort).

    Validates ranges (ICE 1-10; RICE impact in {0.25,0.5,1,2,3}, confidence 0-100%, effort > 0),
    flags confidence inflation when no evidence is given, and reports ties and the score spread.

    Args:
        experiments: List of {"name": str, "impact": n, "confidence": n, "ease": n} for ICE, or {"name", "reach", "impact", "confidence", "effort"} for RICE; optional "evidence": str and "surface": str.
        method: "ICE" or "RICE".
    """
    m = (method or "ICE").upper()
    if m not in ("ICE", "RICE"):
        raise ToolError("method must be 'ICE' or 'RICE'.")
    if not experiments:
        raise ToolError("experiments is empty.")
    if len(experiments) > MAX_ITEMS:
        raise ToolError(f"Too many experiments (max {MAX_ITEMS}).")
    rows, flags = [], []
    for i, e in enumerate(experiments, 1):
        name = str(e.get("name") or f"experiment {i}").strip()
        evidence = str(e.get("evidence") or "").strip()
        if m == "ICE":
            imp = _num(e.get("impact"), f"{name}: impact", 1, 10)
            conf = _num(e.get("confidence"), f"{name}: confidence", 1, 10)
            ease = _num(e.get("ease"), f"{name}: ease", 1, 10)
            score = imp * conf * ease
            row = {"name": name, "impact": imp, "confidence": conf, "ease": ease, "score": round(score, 1), "score_max": 1000}
            if conf >= 8 and not evidence:
                flags.append(f"{name}: confidence {conf:g}/10 with no evidence given — justify or lower to ≤ 5.")
            if imp >= 8 and ease >= 8:
                flags.append(f"{name}: impact {imp:g} and ease {ease:g} — big and easy is rare; sanity-check both.")
        else:
            reach = _num(e.get("reach"), f"{name}: reach", 0)
            imp = _num(e.get("impact"), f"{name}: impact", 0.25, 3)
            if imp not in RICE_IMPACT:
                flags.append(f"{name}: RICE impact {imp:g} is not one of 0.25/0.5/1/2/3 — using as given.")
            conf = _num(e.get("confidence"), f"{name}: confidence", 0, 100)
            if conf <= 1:
                conf *= 100  # given as fraction
            effort = _num(e.get("effort"), f"{name}: effort", 0.01)
            score = reach * imp * (conf / 100) / effort
            row = {"name": name, "reach": reach, "impact": imp, "confidence_pct": conf, "effort": effort, "score": round(score, 1)}
            if conf > 80 and not evidence:
                flags.append(f"{name}: confidence {conf:g}% with no evidence — RICE confidence should be 50/80/100 backed by data.")
        row["surface"] = str(e.get("surface") or "")
        row["evidence"] = evidence
        rows.append(row)
    rows.sort(key=lambda r: -r["score"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    scores = [r["score"] for r in rows]
    ties = [s for s in set(scores) if scores.count(s) > 1]
    if ties:
        flags.append(f"Tied scores: {', '.join(f'{t:g}' for t in sorted(ties, reverse=True))} — break ties by lower effort/ease, then faster learning.")
    top = rows[0]
    spread = round(scores[0] / scores[-1], 1) if scores[-1] > 0 else None
    return {
        "method": m,
        "ranked": rows,
        "flags": flags,
        "top_3": [r["name"] for r in rows[:3]],
        "score_spread": spread,
        "summary": f"#1 '{top['name']}' scores {top['score']:g}" + (f"; top-to-bottom spread {spread}×" if spread else "") + f". {len(flags)} flag(s) to resolve before committing.",
    }


def _z(p: float) -> float:
    return NormalDist().inv_cdf(p)


@AGENT.tool
def sample_size(baseline_rate: float, mde_relative: float, weekly_traffic: int = 0, alpha: float = 0.05, power: float = 0.8, variants: int = 2) -> dict:
    """Compute the per-variant sample size and run time to detect a relative lift in a conversion rate at given alpha and power.

    Uses the two-proportion z-test formula with a Bonferroni-adjusted alpha when there are more than
    two variants. Returns visitors per arm, total, weeks needed (rounded up to whole weeks, minimum 2)
    and a feasibility verdict.

    Args:
        baseline_rate: Current conversion rate as a fraction (0.032 for 3.2%) or a percent (3.2).
        mde_relative: Minimum detectable effect as a relative lift (0.10 or 10 for a 10% relative lift).
        weekly_traffic: Total eligible visitors per week across all variants (0 = skip duration).
        alpha: Two-sided significance level (default 0.05).
        power: Statistical power (default 0.8).
        variants: Number of arms including control (2-10).
    """
    p1 = _num(baseline_rate, "baseline_rate", 0, 100)
    if p1 > 1:
        p1 /= 100
    if not 0 < p1 < 1:
        raise ToolError("baseline_rate must be between 0 and 1 (or 0-100 as a percent), exclusive.")
    mde = _num(mde_relative, "mde_relative", 0)
    if mde >= 1:
        mde /= 100
    if not 0 < mde < 5:
        raise ToolError("mde_relative must be a positive relative lift like 0.1 (10%).")
    a = _num(alpha, "alpha", 0.001, 0.5)
    pw = _num(power, "power", 0.5, 0.999)
    k = int(_num(variants, "variants", 2, 10))
    wt = int(_num(weekly_traffic, "weekly_traffic", 0))
    p2 = min(0.9999, p1 * (1 + mde))
    a_adj = a / (k - 1)  # Bonferroni across treatment arms
    z_a = _z(1 - a_adj / 2)
    z_b = _z(pw)
    pbar = (p1 + p2) / 2
    n = ((z_a * math.sqrt(2 * pbar * (1 - pbar)) + z_b * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2) / ((p2 - p1) ** 2)
    per_arm = math.ceil(n)
    total = per_arm * k
    out = {
        "baseline_rate": round(p1, 5),
        "target_rate": round(p2, 5),
        "absolute_lift": round(p2 - p1, 5),
        "mde_relative_pct": round(mde * 100, 2),
        "alpha": a,
        "alpha_per_comparison": round(a_adj, 4),
        "power": pw,
        "variants": k,
        "visitors_per_arm": per_arm,
        "visitors_total": total,
        "conversions_per_arm_expected": math.ceil(per_arm * p1),
    }
    if wt > 0:
        weeks_raw = total / wt
        weeks = max(2, math.ceil(weeks_raw))
        out.update({"weekly_traffic": wt, "weeks_needed": weeks, "weeks_raw": round(weeks_raw, 2)})
        if weeks > 8:
            # what MDE is detectable in 8 weeks?
            n8 = wt * 8 / k
            lo, hi = mde, 5.0
            for _ in range(60):
                mid = (lo + hi) / 2
                p2m = min(0.9999, p1 * (1 + mid))
                pb = (p1 + p2m) / 2
                nm = ((z_a * math.sqrt(2 * pb * (1 - pb)) + z_b * math.sqrt(p1 * (1 - p1) + p2m * (1 - p2m))) ** 2) / ((p2m - p1) ** 2)
                if nm > n8:
                    lo = mid
                else:
                    hi = mid
            out["mde_detectable_in_8_weeks_pct"] = round(hi * 100, 1)
            out["verdict"] = f"Not feasible as designed: {weeks} weeks. In 8 weeks you could only detect a ≥ {out['mde_detectable_in_8_weeks_pct']}% relative lift — raise the MDE, test a higher-volume metric, or ship and monitor."
        else:
            out["verdict"] = f"Run {weeks} full week(s) ({per_arm:,} visitors per arm, {total:,} total). Pre-register this and don't stop early."
    else:
        out["verdict"] = f"{per_arm:,} visitors per arm ({total:,} total). Give weekly traffic to get run time."
    return out


@AGENT.tool
def evaluate_result(control_visitors: int, control_conversions: int, variant_visitors: int, variant_conversions: int, alpha: float = 0.05, planned_visitors_per_arm: int = 0, expected_split: float = 0.5) -> dict:
    """Judge an A/B result: conversion rates, relative lift, two-proportion z-test p-value, 95% CI, sample-ratio mismatch and a ship/kill/inconclusive decision.

    Args:
        control_visitors: Visitors (or users) exposed to control.
        control_conversions: Conversions in control.
        variant_visitors: Visitors exposed to the variant.
        variant_conversions: Conversions in the variant.
        alpha: Two-sided significance level (default 0.05).
        planned_visitors_per_arm: Pre-registered sample per arm; if the test is below it, the verdict warns about peeking.
        expected_split: Planned share of traffic to the variant (0.5 for 50/50), used for the SRM check.
    """
    n1 = int(_num(control_visitors, "control_visitors", 1))
    x1 = int(_num(control_conversions, "control_conversions", 0))
    n2 = int(_num(variant_visitors, "variant_visitors", 1))
    x2 = int(_num(variant_conversions, "variant_conversions", 0))
    if x1 > n1 or x2 > n2:
        raise ToolError("Conversions cannot exceed visitors.")
    a = _num(alpha, "alpha", 0.001, 0.5)
    split = _num(expected_split, "expected_split", 0.01, 0.99)
    planned = int(_num(planned_visitors_per_arm, "planned_visitors_per_arm", 0))
    p1, p2 = x1 / n1, x2 / n2
    pooled = (x1 + x2) / (n1 + n2)
    se_pooled = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2)) if 0 < pooled < 1 else 0.0
    z = (p2 - p1) / se_pooled if se_pooled else 0.0
    nd = NormalDist()
    p_value = 2 * (1 - nd.cdf(abs(z))) if se_pooled else 1.0
    se_diff = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    zc = _z(1 - a / 2)
    diff = p2 - p1
    ci = (diff - zc * se_diff, diff + zc * se_diff)
    rel = diff / p1 if p1 else None
    rel_ci = ((ci[0] / p1), (ci[1] / p1)) if p1 else None
    # SRM: chi-square with 1 df against expected split
    total = n1 + n2
    exp_var = total * split
    exp_ctrl = total - exp_var
    chi = (n2 - exp_var) ** 2 / exp_var + (n1 - exp_ctrl) ** 2 / exp_ctrl
    srm_p = math.erfc(math.sqrt(chi / 2))  # chi-square(1) survival
    srm_failed = srm_p < 0.001
    under_sample = planned > 0 and min(n1, n2) < planned
    significant = p_value < a
    if srm_failed:
        decision = "invalid"
        why = f"Sample ratio mismatch: observed {n2 / total:.1%} variant vs planned {split:.0%} (p = {srm_p:.2e}). The assignment is broken; discard and fix."
    elif under_sample and significant:
        decision = "inconclusive"
        why = f"p = {p_value:.3f} but only {min(n1, n2):,} of {planned:,} planned visitors per arm — this is peeking. Keep running to the planned sample."
    elif under_sample:
        decision = "keep running"
        why = f"{min(n1, n2):,} of {planned:,} planned per arm; not yet significant (p = {p_value:.3f})."
    elif significant and diff > 0:
        decision = "ship"
        why = f"Variant wins: {rel:+.1%} relative (95% CI {rel_ci[0]:+.1%} to {rel_ci[1]:+.1%}), p = {p_value:.4f}."
    elif significant and diff < 0:
        decision = "kill"
        why = f"Variant loses: {rel:+.1%} relative (95% CI {rel_ci[0]:+.1%} to {rel_ci[1]:+.1%}), p = {p_value:.4f}."
    else:
        decision = "inconclusive"
        why = f"No significant difference (p = {p_value:.3f}); the CI spans {rel_ci[0]:+.1%} to {rel_ci[1]:+.1%}. Not a directional win — a null result."
    return {
        "control": {"visitors": n1, "conversions": x1, "rate": round(p1, 5)},
        "variant": {"visitors": n2, "conversions": x2, "rate": round(p2, 5)},
        "absolute_lift": round(diff, 5),
        "relative_lift_pct": round(rel * 100, 2) if rel is not None else None,
        "ci_95_absolute": [round(ci[0], 5), round(ci[1], 5)],
        "ci_95_relative_pct": [round(rel_ci[0] * 100, 2), round(rel_ci[1] * 100, 2)] if rel_ci else None,
        "z": round(z, 3),
        "p_value": round(p_value, 5),
        "significant": significant,
        "srm": {"chi_square": round(chi, 3), "p_value": srm_p, "failed": srm_failed, "observed_variant_share": round(n2 / total, 4)},
        "under_planned_sample": under_sample,
        "decision": decision,
        "verdict": why,
    }


PARTS = {
    "change": re.compile(r"\b(if we|when we|by (?:adding|removing|changing|showing|moving|replacing)|we (?:add|remove|change|show|move|replace|introduce|launch|test))\b", re.I),
    "audience": re.compile(r"\b(for|among|to) (?:new|returning|mobile|desktop|trial|free|paid|enterprise|smb|users|visitors|customers|signups|[a-z-]+ users|[a-z-]+ visitors)\b", re.I),
    "direction": re.compile(r"\b(increase|decrease|lift|raise|reduce|improve|grow|cut|drop|boost)\b", re.I),
    "magnitude": re.compile(r"(\d+(\.\d+)?\s?(%|percent|pp|x|×|points?)|from \d[\d.,]*%? to \d[\d.,]*%?)", re.I),
    "metric": re.compile(r"\b(conversion|conversion rate|signups?|sign-ups?|activation|retention|churn|revenue|arpu|ctr|click-?through|open rate|checkout|trial[- ]to[- ]paid|aov|average order|engagement|dau|wau|mau|nps|completion|bounce|time to value|referrals?)\b", re.I),
    "rationale": re.compile(r"\b(because|since|as (?:we|our|the) (?:saw|data|research|interviews|analytics|survey)|based on|we (?:observed|found|know|learned))\b", re.I),
}
VAGUE = re.compile(r"\b(better|improve the experience|optimi[sz]e|enhance|more engaging|delight|streamline)\b", re.I)


@AGENT.tool
def lint_hypothesis(hypothesis: str) -> dict:
    """Check a growth hypothesis for the five parts of a falsifiable statement (change, audience, directional effect with size, primary metric, rationale) and return the rewrite template with gaps.

    Args:
        hypothesis: The hypothesis or experiment idea as written (10-2000 characters).
    """
    h = " ".join((hypothesis or "").split())
    if len(h) < 10:
        raise ToolError("hypothesis is too short to lint (10+ characters).")
    if len(h) > 2000:
        raise ToolError("hypothesis max 2000 characters.")
    found = {}
    for part, rx in PARTS.items():
        m = rx.search(h)
        found[part] = m.group(0) if m else None
    present = sum(1 for v in found.values() if v)
    score = round(100 * present / len(PARTS))
    gaps = []
    if not found["change"]:
        gaps.append("State the change as an action: 'If we <add/remove/change X>…'.")
    if not found["audience"]:
        gaps.append("Name the audience: 'for <new mobile visitors / trial users>'.")
    if not found["direction"]:
        gaps.append("Give the direction: increase / decrease.")
    if not found["magnitude"]:
        gaps.append("Give the size: 'by 10% relative' or 'from 3.2% to 3.5%'. Without it you cannot size the test.")
    if not found["metric"]:
        gaps.append("Name ONE primary metric (e.g. signup conversion, trial-to-paid).")
    if not found["rationale"]:
        gaps.append("Add the evidence: 'because <user research / funnel data / prior test>'.")
    vague = VAGUE.findall(h)
    if vague:
        gaps.append(f"Vague words ({', '.join(sorted(set(v.lower() for v in vague)))}) — replace with an observable outcome.")
    multi = len(re.findall(r"\b(and|also|plus)\b", h))
    if multi >= 3:
        gaps.append("Reads like several changes at once — one change per experiment, or you learn nothing from a win.")
    template = (
        f"If we [{found['change'] or 'CHANGE'}] for [{found['audience'] or 'AUDIENCE'}], "
        f"[{found['metric'] or 'PRIMARY METRIC'}] will [{found['direction'] or 'increase/decrease'}] by [{found['magnitude'] or 'X% relative'}] "
        f"because [{found['rationale'] or 'EVIDENCE'}]. We'll know in [N weeks] at [N per arm]."
    )
    return {
        "parts_found": found,
        "completeness_pct": score,
        "gaps": gaps,
        "rewrite_template": template,
        "testable": present >= 4 and bool(found["metric"]),
        "verdict": "Testable — fill any bracketed gap and size it." if present >= 4 and found["metric"] else "Not yet testable — it is an idea, not a hypothesis. Fill the gaps.",
    }


@AGENT.tool
def plan_sprint(experiments: list[dict], parallel_slots: int = 2, horizon_weeks: int = 12, start_week: int = 1) -> dict:
    """Pack ranked experiments into a testing calendar by capacity, never overlapping two tests on the same surface.

    Greedy by score: each experiment takes the earliest slot where it fits within the horizon and no
    running test shares its surface. Returns the schedule, utilisation and what didn't fit.

    Args:
        experiments: List of {"name": str, "score": number, "weeks": number, "surface": str} — surface is the page/flow being tested (optional).
        parallel_slots: How many experiments can run at once (1-10).
        horizon_weeks: Planning horizon in weeks (2-52).
        start_week: Week number to start from (default 1).
    """
    if not experiments:
        raise ToolError("experiments is empty.")
    if len(experiments) > MAX_ITEMS:
        raise ToolError(f"Too many experiments (max {MAX_ITEMS}).")
    slots = int(_num(parallel_slots, "parallel_slots", 1, 10))
    horizon = int(_num(horizon_weeks, "horizon_weeks", 2, 52))
    start = int(_num(start_week, "start_week", 0, 520))
    items = []
    for i, e in enumerate(experiments, 1):
        name = str(e.get("name") or f"experiment {i}")
        weeks = math.ceil(_num(e.get("weeks", 2), f"{name}: weeks", 0.5, 52))
        items.append({"name": name, "score": _num(e.get("score", 0), f"{name}: score", 0), "weeks": weeks, "surface": str(e.get("surface") or "").strip().lower()})
    items.sort(key=lambda x: (-x["score"], x["weeks"]))
    end = start + horizon  # exclusive
    slot_free = [start] * slots  # week each slot becomes free
    surface_busy: dict[str, list[tuple[int, int]]] = {}
    scheduled, unscheduled = [], []
    for it in items:
        best = None
        for s in range(slots):
            t = slot_free[s]
            # push start past any surface conflict
            if it["surface"]:
                moved = True
                while moved:
                    moved = False
                    for a, b in surface_busy.get(it["surface"], []):
                        if t < b and t + it["weeks"] > a:
                            t = b
                            moved = True
            if t + it["weeks"] <= end and (best is None or t < best[1]):
                best = (s, t)
        if best is None:
            unscheduled.append({"name": it["name"], "weeks": it["weeks"], "reason": "no slot within horizon" + (" (surface conflicts)" if it["surface"] else "")})
            continue
        s, t = best
        slot_free[s] = t + it["weeks"]
        if it["surface"]:
            surface_busy.setdefault(it["surface"], []).append((t, t + it["weeks"]))
        scheduled.append({"name": it["name"], "slot": s + 1, "start_week": t, "end_week": t + it["weeks"] - 1, "weeks": it["weeks"], "surface": it["surface"] or None, "score": it["score"]})
    scheduled.sort(key=lambda x: (x["start_week"], x["slot"]))
    used = sum(x["weeks"] for x in scheduled)
    utilisation = round(100 * used / (slots * horizon), 1)
    lanes = []
    for s in range(slots):
        lane = ["·"] * horizon
        for x in scheduled:
            if x["slot"] == s + 1:
                for w in range(x["start_week"] - start, x["end_week"] - start + 1):
                    lane[w] = "█"
        lanes.append(f"slot {s + 1}: " + "".join(lane))
    return {
        "schedule": scheduled,
        "unscheduled": unscheduled,
        "slots": slots,
        "horizon_weeks": horizon,
        "utilisation_pct": utilisation,
        "gantt": lanes,
        "summary": f"{len(scheduled)} experiments scheduled over {horizon} weeks in {slots} slot(s) ({utilisation}% utilised); {len(unscheduled)} left over.",
    }
