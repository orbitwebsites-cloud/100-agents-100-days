"""A/B Test Analyst — correct significance, sample size, peeking and SRM math for experiments."""

from __future__ import annotations

import math

from ...core import Agent, ToolError
from ._common import chi2_sf, norm_cdf, norm_ppf

AGENT = Agent(
    slug="ab-test-analyst",
    name="A/B Test Analyst",
    category="marketing",
    tagline="Call your experiments correctly: real z-tests, sample sizes, peeking penalties and SRM checks.",
    description=(
        "Turns raw experiment numbers into a defensible decision. Runs a proper two-proportion "
        "z-test with confidence intervals on absolute and relative lift, Welch's t-test for revenue "
        "metrics, sample-size and duration planning at chosen power, sample-ratio-mismatch detection, "
        "and alpha corrections for peeking and multiple variants — then writes the readout the way a "
        "senior experimentation lead would, including what NOT to conclude."
    ),
    triggers=[
        "is my A/B test statistically significant",
        "how many visitors do I need for this test",
        "analyze these experiment results",
        "how long should I run this A/B test",
        "can I stop the test early / peeking",
        "write the experiment readout",
    ],
    examples=[
        "Control: 12,400 visitors, 310 conversions. Variant: 12,550 visitors, 362 conversions. Did we win?",
        "Baseline checkout conversion is 3.2%. I want to detect a 10% relative lift — how big a sample and how many weeks at 4k visitors/day?",
        "We looked at the dashboard every day for two weeks and it hit p=0.04 on day 9. Can we ship?",
    ],
    connectors=["Google Analytics", "Google Sheets", "Notion", "Slack"],
    playbook="""
    ## Standard
    You are the experimentation lead a growth team trusts to say "no" to a fake win. The one
    metric that matters: decisions that replicate. A readout is excellent when the primary
    metric, the hypothesis, the sample, the p-value and the confidence interval are all
    stated, and the recommendation follows from them — not from the team's hopes. Never do
    the arithmetic yourself; every number comes from a tool.

    ## Intake
    You need: (a) visitors and conversions per arm (or mean/SD/n for revenue metrics),
    (b) the primary metric and the hypothesis written before the test, (c) how long it ran
    and how often results were checked. If (a) is missing, ask for it — you cannot proceed.
    If (b)/(c) are missing, assume a single pre-planned look at α = 0.05 two-sided, 80 %
    power, state the assumption, and continue. Ask at most 3 questions.

    ## Procedure
    1. **Check the split first.** Call `ab_test_analyst__srm_check` with the expected
       allocation and observed visitor counts. If SRM is flagged (p < 0.001) the test is
       invalid — stop, report the mismatch, and list the usual causes (redirect latency,
       bot filtering, logging on one arm only). Do not analyse conversions.
    2. **Run the primary test.** Conversion metric → `ab_test_analyst__significance_test`.
       Revenue / AOV / time-on-page → `ab_test_analyst__continuous_metric_test` (Welch).
       Read the p-value, the CI on the relative lift, and the probability the variant beats
       control. A CI that spans zero means "not distinguishable", never "no effect".
    3. **Was the sample adequate?** Call `ab_test_analyst__sample_size` with the control
       rate and the MDE the team cared about. If the achieved sample is below the required
       one, the test is underpowered — the readout must say the effect was "too small to
       detect at this sample", not "no effect".
    4. **Correct for how the test was actually run.** If the team looked more than once or
       ran > 1 variant, call `ab_test_analyst__alpha_correction` with the number of looks
       and arms. Compare the observed p-value against the corrected per-look α, not 0.05.
       A p = 0.04 found on the 9th daily peek is not a win.
    5. **Decide with the rules below** and write the readout in the output format.
       Recommend one of: SHIP, ITERATE, KEEP RUNNING (with the date it reaches sample), or
       ABANDON.

    ## Frameworks
    - **Decision rules.** Ship when p < corrected α AND the lower bound of the relative-lift
      CI is above the cost-to-ship threshold (usually 0 %; higher if the change adds
      complexity). Keep running only if the pre-planned sample isn't reached. Never extend a
      test that reached its sample just because it "almost" won.
    - **Minimum runtime.** ≥ 1 full business cycle (7 days) and ideally 2, regardless of
      sample size, to average out weekday/weekend mix. Stop on the pre-planned date.
    - **Power.** 80 % power means 1 in 5 real effects of MDE size will be missed. Report it.
    - **Peeking.** Checking daily with a naïve p < 0.05 rule inflates false positives to
      ~20 % over 10 looks. Use the Pocock or Bonferroni boundary the tool returns, or a
      sequential method, if the team insists on interim looks.
    - **Novelty & primacy effects.** If the lift is shrinking day over day, flag it and
      suggest a holdout re-test after 2 weeks.
    - **Segments.** Post-hoc segment "wins" are hypotheses, not results — say so explicitly.
    - **Twyman's law.** Any lift > 25 % relative on a mature funnel is probably a bug.
      Check instrumentation before celebrating.

    ## Output format
    ```
    # Experiment readout — <test name>
    **Hypothesis:** <as written before the test>
    **Primary metric:** <metric> · **Runtime:** <days> · **Looks:** <n> · **α (corrected):** <x>

    | Arm | Visitors | Conversions | Rate |
    |---|---|---|---|

    **Result:** relative lift <x %> (95 % CI <lo %> to <hi %>), p = <p>, P(variant > control) = <y %>
    **Sample check:** needed <n>/arm for <MDE>; have <m>/arm → <adequate / underpowered>
    **SRM:** <pass / FAIL>

    ## Recommendation: <SHIP / ITERATE / KEEP RUNNING until <date> / ABANDON>
    <2-3 sentences: why, and the risk of being wrong.>

    ## What this does NOT tell us
    - <segment / secondary metric / novelty caveats>

    ## Next test
    <one concrete follow-up hypothesis>
    ```

    ## Anti-patterns
    - Reporting "95 % confidence" from a 1-sided test the team didn't pre-register.
    - Calling a test a loss when the CI includes the MDE — that's "inconclusive".
    - Averaging conversion rates across days instead of pooling counts.
    - Ending early on a win but extending on a loss (asymmetric stopping).
    - Quoting p-values to 4 decimals while ignoring that the split was 60/40.
    - Ignoring guardrail metrics (refunds, support tickets, page speed) in the readout.
    """,
)


def _wilson(x: int, n: int, z: float) -> tuple[float, float]:
    """Wilson score interval for a single proportion (well-behaved at small counts and near 0 %/100 %)."""
    centre = (x + z * z / 2) / (n + z * z)
    half = z / (n + z * z) * math.sqrt(x * (n - x) / n + z * z / 4)
    return max(0.0, centre - half), min(1.0, centre + half)


def _check_arm(n: int, x: int, label: str) -> None:
    if n <= 0:
        raise ToolError(f"{label}: visitors must be > 0.")
    if x < 0 or x > n:
        raise ToolError(f"{label}: conversions must be between 0 and visitors ({n}).")


@AGENT.tool
def significance_test(
    control_visitors: int,
    control_conversions: int,
    variant_visitors: int,
    variant_conversions: int,
    alpha: float = 0.05,
    two_sided: bool = True,
) -> dict:
    """Two-proportion z-test for a conversion-rate A/B test with CIs on absolute and relative lift.

    Call for any binary metric (conversion, click, signup). Returns z, p-value, confidence
    intervals, the probability the variant beats control, and a plain-English verdict.

    Args:
        control_visitors: Visitors (or users) in the control arm.
        control_conversions: Conversions in the control arm.
        variant_visitors: Visitors in the variant arm.
        variant_conversions: Conversions in the variant arm.
        alpha: Significance level (default 0.05).
        two_sided: True for a two-sided test (default); False for one-sided "variant > control".
    """
    _check_arm(control_visitors, control_conversions, "control")
    _check_arm(variant_visitors, variant_conversions, "variant")
    if not 0 < alpha < 0.5:
        raise ToolError("alpha must be between 0 and 0.5 (e.g. 0.05).")
    n1, x1, n2, x2 = control_visitors, control_conversions, variant_visitors, variant_conversions
    p1, p2 = x1 / n1, x2 / n2
    pooled = (x1 + x2) / (n1 + n2)
    se_pooled = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    se_unpooled = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    diff = p2 - p1
    if se_pooled == 0:
        raise ToolError("Both arms have identical all-or-nothing outcomes; no variance to test.")
    z = diff / se_pooled
    p_value = 2 * (1 - norm_cdf(abs(z))) if two_sided else 1 - norm_cdf(z)
    zcrit = norm_ppf(1 - alpha / 2) if two_sided else norm_ppf(1 - alpha)
    ci_abs = (diff - zcrit * se_unpooled, diff + zcrit * se_unpooled)
    rel = diff / p1 if p1 else None
    # CI on relative lift via log-ratio (delta method); needs both rates > 0.
    if p1 > 0 and p2 > 0:
        se_log = math.sqrt((1 - p1) / (n1 * p1) + (1 - p2) / (n2 * p2))
        lr = math.log(p2 / p1)
        ci_rel = (math.exp(lr - zcrit * se_log) - 1, math.exp(lr + zcrit * se_log) - 1)
    else:
        ci_rel = (None, None)
    prob_beats = norm_cdf(diff / se_unpooled) if se_unpooled else None
    significant = p_value < alpha
    min_needed = min(x1, x2, n1 - x1, n2 - x2)
    small_sample_warning = min_needed < 10
    if significant and diff > 0:
        verdict = f"Variant wins: +{100 * rel:.1f}% relative lift, p = {p_value:.4f} (< {alpha})."
    elif significant:
        verdict = f"Variant loses: {100 * rel:.1f}% relative, p = {p_value:.4f} (< {alpha})."
    else:
        verdict = f"Not significant (p = {p_value:.3f}). Inconclusive, not 'no effect' — see the CI."
    if rel is not None and abs(rel) > 0.25:
        verdict += " Lift > 25% relative — Twyman's law: verify instrumentation before trusting it."
    z_arm = norm_ppf(1 - alpha / 2)
    w1, w2 = _wilson(x1, n1, z_arm), _wilson(x2, n2, z_arm)
    return {
        "control": {"visitors": n1, "conversions": x1, "rate_pct": round(100 * p1, 3), "rate_ci_pct": [round(100 * w1[0], 3), round(100 * w1[1], 3)]},
        "variant": {"visitors": n2, "conversions": x2, "rate_pct": round(100 * p2, 3), "rate_ci_pct": [round(100 * w2[0], 3), round(100 * w2[1], 3)]},
        "rate_ci_method": f"Wilson score, {round(100 * (1 - alpha))}% two-sided, per arm",
        "absolute_lift_pp": round(100 * diff, 3),
        "absolute_lift_ci_pp": [round(100 * ci_abs[0], 3), round(100 * ci_abs[1], 3)],
        "relative_lift_pct": round(100 * rel, 2) if rel is not None else None,
        "relative_lift_ci_pct": [round(100 * v, 2) if v is not None else None for v in ci_rel],
        "z": round(z, 4),
        "p_value": round(p_value, 6),
        "alpha": alpha,
        "two_sided": two_sided,
        "significant": significant,
        "prob_variant_beats_control_pct": round(100 * prob_beats, 1) if prob_beats is not None else None,
        "small_sample_warning": small_sample_warning,
        "verdict": verdict,
        "next_step": (
            "Compare p against the corrected alpha from alpha_correction if there were multiple looks or variants."
            if significant
            else "Run sample_size with the MDE you cared about to see whether this test was powered to find it."
        ),
    }


@AGENT.tool
def sample_size(
    baseline_rate_pct: float,
    mde_relative_pct: float = 0.0,
    alpha: float = 0.05,
    power: float = 0.8,
    variants: int = 2,
    daily_visitors: int = 0,
    two_sided: bool = True,
    mde_absolute_pp: float = 0.0,
    start_date: str = "",
) -> dict:
    """Visitors per arm and test duration needed to detect a lift at given alpha and power, with the stop date.

    Call before a test starts, and after one ends to judge whether it was adequately powered.
    Give the MDE as a relative lift (mde_relative_pct) or in percentage points (mde_absolute_pp).

    Args:
        baseline_rate_pct: Control conversion rate in percent (e.g. 3.2 for 3.2%).
        mde_relative_pct: Minimum detectable effect as a relative percent lift (e.g. 10 for +10%).
        alpha: Significance level (default 0.05).
        power: Statistical power, 0-1 (default 0.8).
        variants: Total arms including control (default 2). More arms split traffic.
        daily_visitors: Total eligible visitors per day across all arms; 0 to skip duration.
        two_sided: Two-sided test (default True).
        mde_absolute_pp: Alternative to mde_relative_pct: the MDE in percentage points (e.g. 0.5 for 3.2% → 3.7%).
        start_date: Date the test started / starts, YYYY-MM-DD; with daily_visitors, returns the date it reaches sample.
    """
    if not 0 < baseline_rate_pct < 100:
        raise ToolError("baseline_rate_pct must be between 0 and 100 (exclusive).")
    if mde_absolute_pp and mde_relative_pct:
        raise ToolError("Give the MDE once: mde_relative_pct or mde_absolute_pp, not both.")
    if mde_absolute_pp:
        if mde_absolute_pp <= 0:
            raise ToolError("mde_absolute_pp must be > 0.")
        mde_relative_pct = 100 * mde_absolute_pp / baseline_rate_pct
    if mde_relative_pct <= 0:
        raise ToolError("mde_relative_pct (or mde_absolute_pp) must be > 0.")
    if not 0 < alpha < 0.5 or not 0.5 <= power < 1:
        raise ToolError("alpha must be in (0, 0.5) and power in [0.5, 1).")
    if variants < 2 or variants > 10:
        raise ToolError("variants must be between 2 and 10 (including control).")
    p1 = baseline_rate_pct / 100
    p2 = p1 * (1 + mde_relative_pct / 100)
    if p2 >= 1:
        raise ToolError("baseline × (1 + MDE) exceeds 100% — lower the MDE.")
    za = norm_ppf(1 - alpha / 2) if two_sided else norm_ppf(1 - alpha)
    zb = norm_ppf(power)
    pbar = (p1 + p2) / 2
    n = ((za * math.sqrt(2 * pbar * (1 - pbar)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2) / ((p2 - p1) ** 2)
    per_arm = math.ceil(n)
    total = per_arm * variants
    out = {
        "baseline_rate_pct": baseline_rate_pct,
        "target_rate_pct": round(100 * p2, 3),
        "mde_relative_pct": mde_relative_pct,
        "mde_absolute_pp": round(100 * (p2 - p1), 3),
        "alpha": alpha,
        "power": power,
        "variants": variants,
        "visitors_per_arm": per_arm,
        "visitors_total": total,
    }
    if daily_visitors > 0:
        days = math.ceil(total / daily_visitors)
        weeks = max(1, math.ceil(days / 7))
        out.update(
            {
                "daily_visitors": daily_visitors,
                "days_needed": days,
                "recommended_runtime_days": max(7, weeks * 7),
                "runtime_note": "Rounded up to full weeks; never stop mid-week. Minimum 7 days even if the sample fills sooner.",
            }
        )
        if days > 56:
            out["warning"] = f"{days} days is too long — raise the MDE, pick a higher-traffic metric, or test fewer arms."
        if start_date:
            from datetime import timedelta

            from ...lib import dates

            s0 = dates.parse_date(start_date)
            out["start_date"] = s0.isoformat()
            out["sample_reached_date"] = (s0 + timedelta(days=days - 1)).isoformat()
            out["stop_date"] = (s0 + timedelta(days=out["recommended_runtime_days"] - 1)).isoformat()
            out["stop_date_note"] = "Last day of the test (inclusive), after rounding up to whole weeks."
    out["method"] = (
        "Two-proportion z-test, pooled variance under H0 (Fleiss, no continuity correction) — the same test "
        "significance_test runs. Evan Miller's calculator uses the baseline variance under H0 and returns ~5-8% fewer "
        "visitors (e.g. 1,030 vs 1,094 per arm at 20% baseline, +5 pp)."
    )
    out["summary"] = f"Need {per_arm:,} visitors per arm ({total:,} total) to detect +{round(mde_relative_pct, 2)}% relative (+{round(100 * (p2 - p1), 3)} pp) at {int(power * 100)}% power, α={alpha}."
    return out


@AGENT.tool
def alpha_correction(looks: int = 1, variants: int = 2, alpha: float = 0.05) -> dict:
    """Corrected per-look and per-comparison alpha for peeking and multiple variants, with false-positive inflation.

    Call whenever results were checked more than once or the test had more than one variant.

    Args:
        looks: Number of times the results were (or will be) examined, including the final.
        variants: Total arms including control; comparisons = variants - 1.
        alpha: Nominal significance level (default 0.05).
    """
    if looks < 1 or looks > 1000:
        raise ToolError("looks must be between 1 and 1000.")
    if variants < 2 or variants > 20:
        raise ToolError("variants must be between 2 and 20.")
    if not 0 < alpha < 0.5:
        raise ToolError("alpha must be in (0, 0.5).")
    comparisons = variants - 1
    tests = looks * comparisons
    bonferroni = alpha / tests
    sidak = 1 - (1 - alpha) ** (1 / tests)
    # Pocock constant boundaries for α=0.05 two-sided (Pocock 1977); scaled for other alphas via ratio.
    pocock_05 = {1: 0.05, 2: 0.0294, 3: 0.0221, 4: 0.0182, 5: 0.0158, 6: 0.0142, 7: 0.0130, 8: 0.0120, 9: 0.0112, 10: 0.0106}
    pocock = pocock_05.get(looks)
    if pocock is not None and alpha != 0.05:
        pocock = round(pocock * alpha / 0.05, 5)
    # Approximate family-wise error if you peek `looks` times with a naïve alpha rule
    # (Armitage, McPherson & Rowe 1969 for α=0.05; independent-look upper bound otherwise).
    armitage = {1: 0.05, 2: 0.083, 3: 0.107, 4: 0.126, 5: 0.142, 10: 0.193, 20: 0.246, 50: 0.320}
    if alpha == 0.05 and looks in armitage:
        naive_fwer_peeking = armitage[looks]
    else:
        keys = sorted(armitage)
        lo = max(k for k in keys if k <= looks)
        hi = min((k for k in keys if k >= looks), default=None)
        if hi is None:
            naive_fwer_peeking = min(0.6, armitage[50] + 0.02 * math.log(looks / 50 + 1))
        elif lo == hi:
            naive_fwer_peeking = armitage[lo]
        else:
            naive_fwer_peeking = armitage[lo] + (armitage[hi] - armitage[lo]) * (looks - lo) / (hi - lo)
        if alpha != 0.05:
            naive_fwer_peeking = min(1.0, naive_fwer_peeking * alpha / 0.05)
    naive_fwer_total = 1 - (1 - naive_fwer_peeking) ** comparisons
    return {
        "looks": looks,
        "variants": variants,
        "comparisons": comparisons,
        "nominal_alpha": alpha,
        "naive_false_positive_rate_pct": round(100 * naive_fwer_total, 1),
        "bonferroni_alpha_per_test": round(bonferroni, 5),
        "sidak_alpha_per_test": round(sidak, 5),
        "pocock_alpha_per_look": pocock,
        "recommended_alpha": round(pocock / comparisons if pocock else bonferroni, 5),
        "verdict": (
            f"With {looks} look(s) and {comparisons} comparison(s), a naïve p<{alpha} rule yields ~{100 * naive_fwer_total:.0f}% false positives. "
            f"Require p < {round(pocock / comparisons if pocock else bonferroni, 4)} instead."
        ),
        "note": "Pocock boundaries are tabulated up to 10 looks; beyond that Bonferroni is used (conservative).",
    }


@AGENT.tool
def srm_check(expected_split_pct: list[float], observed_visitors: list[int]) -> dict:
    """Sample-ratio-mismatch check: chi-square goodness of fit of observed arm sizes vs planned split.

    Call before analysing any result. An SRM (p < 0.001) invalidates the test.

    Args:
        expected_split_pct: Planned traffic share per arm in percent, e.g. [50, 50] or [34, 33, 33].
        observed_visitors: Observed visitor counts per arm in the same order.
    """
    if len(expected_split_pct) != len(observed_visitors) or len(observed_visitors) < 2:
        raise ToolError("Provide the same number (≥ 2) of expected shares and observed counts.")
    if any(v < 0 for v in observed_visitors) or sum(observed_visitors) == 0:
        raise ToolError("Observed visitor counts must be non-negative and not all zero.")
    if any(s <= 0 for s in expected_split_pct):
        raise ToolError("Expected shares must be > 0.")
    tot_share = sum(expected_split_pct)
    total = sum(observed_visitors)
    expected = [total * s / tot_share for s in expected_split_pct]
    chi2 = sum((o - e) ** 2 / e for o, e in zip(observed_visitors, expected))
    df = len(observed_visitors) - 1
    p = chi2_sf(chi2, df)
    srm = p < 0.001
    return {
        "observed": observed_visitors,
        "expected": [round(e, 1) for e in expected],
        "observed_split_pct": [round(100 * o / total, 2) for o in observed_visitors],
        "chi_square": round(chi2, 3),
        "df": df,
        "p_value": round(p, 6),
        "srm_detected": srm,
        "verdict": (
            "SAMPLE RATIO MISMATCH — the assignment is broken; results are invalid until the cause is found."
            if srm
            else ("Split looks slightly off (p < 0.05) — investigate but not disqualifying." if p < 0.05 else "Split is consistent with the plan.")
        ),
        "usual_causes": ["redirect latency dropping slow users from one arm", "bot filtering applied unevenly", "logging failure on one arm", "targeting rule interacting with assignment"] if srm else [],
    }


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (Numerical Recipes)."""
    maxit, eps, fpmin = 300, 3e-14, 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > fpmin else fpmin)
    h = d
    for m in range(1, maxit + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > fpmin else fpmin)
        c = 1 + aa / (c if abs(c) > fpmin else fpmin)
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > fpmin else fpmin)
        c = 1 + aa / (c if abs(c) > fpmin else fpmin)
        de = d * c
        h *= de
        if abs(de - 1) < eps:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return bt * _betacf(a, b, x) / a
    return 1 - bt * _betacf(b, a, 1 - x) / b


def t_sf(t: float, df: float) -> float:
    """One-sided survival function P(T > t) of Student's t."""
    x = df / (df + t * t)
    p_two = _betainc(df / 2, 0.5, x)
    return p_two / 2 if t >= 0 else 1 - p_two / 2


def t_ppf(p: float, df: float) -> float:
    """Student t quantile by bisection on t_sf (df ≥ 1)."""
    lo, hi = -200.0, 200.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if 1 - t_sf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


@AGENT.tool
def continuous_metric_test(
    control_mean: float,
    control_sd: float,
    control_n: int,
    variant_mean: float,
    variant_sd: float,
    variant_n: int,
    alpha: float = 0.05,
    alternative: str = "two-sided",
) -> dict:
    """Welch's t-test for revenue-per-visitor, AOV, time-on-page or any continuous metric.

    Call when the metric is a mean, not a rate. Handles unequal variances and reports
    the CI on the difference and on the relative lift.

    Args:
        control_mean: Mean of the metric in control.
        control_sd: Standard deviation in control (sample SD).
        control_n: Number of observations in control.
        variant_mean: Mean in variant.
        variant_sd: Standard deviation in variant.
        variant_n: Number of observations in variant.
        alpha: Significance level (default 0.05).
        alternative: "two-sided" (default), "greater" (variant mean > control) or "less" (variant mean < control); one-sided only if pre-registered.
    """
    if alternative not in ("two-sided", "greater", "less"):
        raise ToolError('alternative must be "two-sided", "greater" or "less".')
    if control_n < 2 or variant_n < 2:
        raise ToolError("Each arm needs at least 2 observations.")
    if control_sd < 0 or variant_sd < 0:
        raise ToolError("Standard deviations cannot be negative.")
    if not 0 < alpha < 0.5:
        raise ToolError("alpha must be in (0, 0.5).")
    v1, v2 = control_sd**2 / control_n, variant_sd**2 / variant_n
    se = math.sqrt(v1 + v2)
    if se == 0:
        raise ToolError("Zero variance in both arms; nothing to test.")
    diff = variant_mean - control_mean
    t = diff / se
    df = (v1 + v2) ** 2 / (v1**2 / (control_n - 1) + v2**2 / (variant_n - 1))
    if alternative == "two-sided":
        p = 2 * t_sf(abs(t), df)
    elif alternative == "greater":
        p = t_sf(t, df)
    else:
        p = 1 - t_sf(t, df)
    tcrit = t_ppf(1 - alpha / 2, df)
    ci = (diff - tcrit * se, diff + tcrit * se)
    arm_ci = {}
    for label, mean, sd, n in (("control", control_mean, control_sd, control_n), ("variant", variant_mean, variant_sd, variant_n)):
        half = t_ppf(1 - alpha / 2, n - 1) * sd / math.sqrt(n)
        arm_ci[label] = {"mean": mean, "ci": [round(mean - half, 4), round(mean + half, 4)]}
    rel = diff / control_mean if control_mean else None
    significant = p < alpha
    skew_note = ""
    if control_sd > 2 * abs(control_mean) or variant_sd > 2 * abs(variant_mean):
        skew_note = " SD > 2× mean suggests a heavy-tailed metric (revenue); consider winsorising outliers or a bootstrap."
    return {
        "arms": arm_ci,
        "alternative": alternative,
        "difference": round(diff, 4),
        "difference_ci": [round(ci[0], 4), round(ci[1], 4)],
        "relative_lift_pct": round(100 * rel, 2) if rel is not None else None,
        "t": round(t, 4),
        "df": round(df, 1),
        "p_value": round(p, 6),
        "significant": significant,
        "verdict": (f"{'Significant' if significant else 'Not significant'} (p = {p:.4f}); difference {diff:+.3f} (95% CI {ci[0]:.3f} to {ci[1]:.3f})." + skew_note),
    }
