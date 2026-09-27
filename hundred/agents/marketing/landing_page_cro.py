"""Landing Page CRO — audits a landing page against a weighted conversion rubric and sizes the fix."""

from __future__ import annotations

import math
import re

from ...core import Agent, ToolError
from ...lib import text
from ._common import CTA_VERBS, norm_ppf, require_text

AGENT = Agent(
    slug="landing-page-cro",
    name="Landing Page CRO",
    category="marketing",
    tagline="Audit a landing page like a conversion specialist: scored rubric, ranked fixes, and the test plan to prove them.",
    description=(
        "Runs a full conversion-rate-optimisation review of a landing page. Scores the copy and "
        "structure against a weighted LIFT-style rubric (value proposition, clarity, relevance, "
        "anxiety, distraction, urgency), 5-second-tests the headline, finds the biggest leak in the "
        "funnel, computes the revenue a lift is worth, and sizes the A/B test needed to prove it — "
        "so recommendations arrive ranked by expected impact, not by taste."
    ),
    triggers=[
        "audit / review my landing page",
        "why isn't my landing page converting",
        "improve conversion rate on this page",
        "rewrite my landing page headline",
        "how big a sample do I need to test this page",
        "landing page CRO checklist",
    ],
    examples=[
        "Here's the copy of our pricing landing page (2.1% CVR on 18k visitors/month). What should we fix first?",
        "Five-second-test our hero: 'Reimagining the future of work for modern teams' + 'Get started'.",
        "Funnel is 40,000 visits → 6,200 pricing views → 900 signups → 210 paid. Where's the leak and what's it worth?",
    ],
    connectors=["Google Analytics", "Hotjar", "Webflow", "HubSpot", "Google Sheets", "Notion"],
    playbook="""
    ## Standard
    You are a conversion specialist who has run hundreds of page tests. Excellent means: a
    ranked list of changes with an expected-impact rationale, each tied to a rubric
    dimension, the biggest leak identified from data (not vibes), the revenue at stake
    quantified, and a test plan with the sample it needs. The metric that matters is primary
    conversion rate per visitor — never "engagement".

    ## Intake
    Need: the page copy (paste or URL text), the single primary conversion, and ideally
    traffic + conversion numbers. If you have the copy, proceed. If traffic numbers are
    missing, assume 10,000 visitors/month and the category-typical baseline (SaaS trial 2-5 %,
    lead-gen form 5-10 %, e-commerce product page 2-3 %), state the assumption and continue.
    Ask at most 3 questions.

    ## Procedure
    1. **Score the page.** Call `landing_page_cro__audit_page` with the page copy and whatever
       structural facts you know (form fields, CTA count, load time, social proof present,
       nav links). Read the dimension scores; the two lowest are where the money is.
    2. **Five-second-test the hero.** Call `landing_page_cro__headline_clarity` with the
       headline, subheadline and CTA label. A visitor must be able to answer "what is it,
       who is it for, why should I care" in 5 seconds. If the tool grade is below B, rewrite
       the hero before anything else — nothing below the fold matters if the hero fails.
    3. **Find the leak.** If you have funnel numbers, call `landing_page_cro__funnel_leaks`
       with the ordered step counts. Fix the step with the largest absolute loss × ease.
    4. **Quantify the prize.** Call `landing_page_cro__lift_value` with monthly visitors,
       current CVR, the CVR you expect after the fix (use the ranges in Frameworks; be
       conservative) and value per conversion. Lead with this number in the report.
    5. **Size the test.** Call `landing_page_cro__test_sample_size` with the baseline CVR and
       the relative lift you're claiming. If the runtime exceeds 6 weeks, recommend shipping
       the fix without a test (or testing a bolder change) — say which.
    6. **Write the report** in the output format: top 5 fixes ranked by (expected lift ×
       confidence ÷ effort), each with a rewritten example, not just "improve the CTA".

    ## Frameworks
    - **LIFT model dimensions:** value proposition (the anchor), relevance to the traffic
      source, clarity (copy + design), anxiety (risk, privacy, "what happens next"),
      distraction (nav, competing CTAs), urgency (real, not fake).
    - **Hero formula:** headline = outcome + who + how (≤ 10 words); subheadline = the
      mechanism and proof (≤ 25 words); CTA = verb + what they get ("Start my free trial"),
      never "Submit"; one primary CTA above the fold, repeated after each section.
    - **Message match:** the headline must repeat the promise of the ad/email that sent the
      visitor; mismatch is the #1 cause of high bounce on paid traffic.
    - **Forms:** each field above 4 costs conversions; ask only what sales needs on day one.
    - **Proof stack, in order of strength:** named customer result with a number → logos →
      review score with count → testimonials → "trusted by X".
    - **Typical lift ranges (use as ceilings, not promises):** hero rewrite 10-30 %; removing
      nav on paid pages 5-15 %; form-field reduction 5-20 %; adding specific proof 5-15 %.
    - **Speed:** every extra second of load past 2 s measurably lowers CVR; flag > 3 s.

    ## Output format
    ```
    # CRO audit — <page> · score <n>/100
    **Primary conversion:** <x> · **Now:** <cvr %> on <visitors>/mo · **Prize:** +<n> conv/mo ≈ <$> / yr at <target cvr %>

    | Dimension | Score | Biggest issue |
    |---|---|---|

    ## Hero (5-second test: <grade>)
    - Now: "<headline>" / "<sub>" / [<CTA>]
    - Rewrite: "<headline>" / "<sub>" / [<CTA>]

    ## Ranked fixes
    1. **<fix>** — <dimension> · expected <x-y %> · effort <S/M/L> · <why + example>
    …

    ## Funnel leak
    <step> loses <n> (<pct>) — <cause hypothesis> — <fix>

    ## Test plan
    Hypothesis · variant · primary metric · <n> per arm · ~<weeks> weeks · ship if lift CI > 0
    ```

    ## Anti-patterns
    - Recommending "add more testimonials" without saying which proof type and where.
    - Clever headlines ("Work, reimagined") that fail the 5-second test.
    - Multiple competing CTAs above the fold ("Book demo", "Start trial", "Watch video").
    - Fake urgency countdowns; visitors notice when the timer resets.
    - Reporting a 3-day test as a win.
    - Auditing design taste ("more whitespace") instead of message, proof and friction.
    """,
)

WE_RE = re.compile(r"\b(we|our|us|ourselves)\b", re.I)
YOU_RE = re.compile(r"\b(you|your|yours)\b", re.I)
PROOF_RE = re.compile(r"\b(\d[\d,.]*\s*(k|m|\+|%)?\s*(customers|users|teams|companies|reviews|countries|brands|stars|rating)|rated|trusted by|case study|testimonial|G2|Capterra|as seen in|award)\b", re.I)
JARGON = frozenset(
    """synergy leverage seamless robust cutting-edge best-in-class next-generation innovative
    revolutionary world-class holistic paradigm scalable turnkey disruptive empower reimagine
    reimagining transform transformative ecosystem frictionless unlock elevate streamline
    end-to-end solution solutions platform-agnostic state-of-the-art game-changing""".split()
)
ANXIETY_RE = re.compile(r"\b(no credit card|cancel anytime|money-back|money back|guarantee|free trial|gdpr|soc ?2|secure|encrypted|privacy|refund|unsubscribe any ?time|no commitment|no contract)\b", re.I)
URGENCY_RE = re.compile(r"\b(today|now|limited|ends|only \d+ (left|spots|seats)|this week|until|deadline|closes)\b", re.I)
CTA_RE = re.compile(r"\[([^\]]{2,40})\]|\b(get started|start (your |my )?free|book a demo|request a demo|sign up|try (it )?free|start (free )?trial|buy now|add to cart|download|subscribe|contact sales|schedule a call|learn more|see pricing|join (now|free)|create (an )?account)\b", re.I)
WEAK_CTA = {"submit", "learn more", "click here", "continue", "go", "send", "next", "enter"}


@AGENT.tool
def audit_page(
    page_text: str,
    form_fields: int = 0,
    nav_links: int = 0,
    load_time_seconds: float = 0.0,
    distinct_ctas: int = 0,
    primary_cta_above_fold: bool = True,
    has_video: bool = False,
    traffic_source: str = "",
) -> dict:
    """Score a landing page 0-100 across six CRO dimensions from its copy plus structural facts, with ranked fixes.

    Call first with the full page copy. CTAs can be marked in the text as [Button label].

    Args:
        page_text: All visible copy of the page, top to bottom. Mark buttons as [Label] if you can.
        form_fields: Number of fields in the primary form (0 if no form).
        nav_links: Number of navigation / header links that leave the page.
        load_time_seconds: Measured or estimated load time; 0 if unknown.
        distinct_ctas: Number of different calls to action on the page; 0 to infer from text.
        primary_cta_above_fold: Whether the primary CTA is visible without scrolling.
        has_video: Whether the page includes an explainer or product video.
        traffic_source: Where visitors come from (e.g. "google ads: team task software") to judge message match.
    """
    body = require_text(page_text, "page_text")
    if form_fields < 0 or nav_links < 0 or load_time_seconds < 0 or distinct_ctas < 0:
        raise ToolError("Counts and load time cannot be negative.")
    ws = text.words(body)
    n_words = len(ws)
    low = body.lower()
    rd = text.readability(body)
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    headline = lines[0] if lines else ""
    we, you = len(WE_RE.findall(body)), len(YOU_RE.findall(body))
    proof = len(PROOF_RE.findall(body))
    numbers = len(re.findall(r"\d[\d,.]*%?", body))
    jargon_hits = sorted({w.lower() for w in ws if w.lower() in JARGON})
    anxiety_relievers = sorted({m.group(0).lower() for m in ANXIETY_RE.finditer(body)})
    urgency_hits = URGENCY_RE.findall(body)
    cta_matches = [m.group(1) or m.group(2) for m in CTA_RE.finditer(body)]
    cta_labels = sorted({c.strip().lower() for c in cta_matches})
    ctas = distinct_ctas or len(cta_labels)
    weak_ctas = [c for c in cta_labels if c in WEAK_CTA]
    src_words = set(w.lower() for w in text.words(traffic_source) if w.lower() not in text.STOPWORDS)
    head_words = set(w.lower() for w in text.words(" ".join(lines[:3])))
    match_ratio = round(len(src_words & head_words) / len(src_words), 2) if src_words else None

    dims: dict[str, dict] = {}

    def dim(name: str, weight: int, score: float, issue: str, fix: str) -> None:
        dims[name] = {"weight": weight, "score": max(0, min(100, round(score))), "issue": issue, "fix": fix}

    # Value proposition (25)
    vp = 40
    h_words = len(text.words(headline))
    if 0 < h_words <= 12:
        vp += 20
    if re.search(r"\d", headline):
        vp += 10
    if proof:
        vp += min(20, 10 * proof)
    if any(w in headline.lower() for w in JARGON):
        vp -= 20
    if you >= we:
        vp += 10
    dim("value_proposition", 25, vp, "headline is vague / no proof" if vp < 60 else "proof could be more specific", "Headline = outcome + who + how; add one named customer result with a number in the hero.")
    # Clarity (20)
    cl = 90
    if rd["fk_grade"] is not None and rd["fk_grade"] > 9:
        cl -= 20
    if rd["fk_grade"] is not None and rd["fk_grade"] > 12:
        cl -= 15
    cl -= min(30, 8 * len(jargon_hits))
    if n_words > 900:
        cl -= 10
    if n_words < 80:
        cl -= 15
    dim("clarity", 20, cl, f"grade {rd['fk_grade']}, jargon: {', '.join(jargon_hits[:4]) or 'none'}", "Target grade ≤ 8; swap each jargon word for the plain thing it means.")
    # Relevance (15)
    rl = 70
    if match_ratio is not None:
        rl = 40 + 60 * match_ratio
    if we > you:
        rl -= 15
    dim("relevance", 15, rl, f"message match {match_ratio if match_ratio is not None else 'unknown'}; we:you = {we}:{you}", "Repeat the ad/email promise in the headline; rewrite 'we' sentences to 'you'.")
    # Anxiety (15)
    ax = 50 + 12 * len(anxiety_relievers)
    if form_fields > 4:
        ax -= 8 * (form_fields - 4)
    if form_fields > 0 and not anxiety_relievers:
        ax -= 15
    dim("anxiety", 15, ax, f"{form_fields} form fields; relievers: {', '.join(anxiety_relievers) or 'none'}", "Cut the form to ≤ 4 fields; put 'no credit card / cancel anytime / what happens next' beside the CTA.")
    # Distraction (15)
    ds = 90 - 6 * nav_links - 12 * max(0, ctas - 1)
    if not primary_cta_above_fold:
        ds -= 25
    if weak_ctas:
        ds -= 10
    if has_video and n_words > 600:
        ds -= 5
    dim("distraction", 15, ds, f"{nav_links} nav links, {ctas} distinct CTAs{' incl. weak: ' + ', '.join(weak_ctas) if weak_ctas else ''}", "One primary CTA repeated; remove nav on paid-traffic pages; verb + benefit button labels.")
    # Urgency (10)
    ur = 50 + min(30, 15 * len(urgency_hits))
    if load_time_seconds > 3:
        ur -= 20
    dim("urgency", 10, ur, "no reason to act now" if not urgency_hits else "urgency present — make sure it's real", "Add a real reason to act now (cohort start date, price change, limited onboarding slots).")

    total = round(sum(d["score"] * d["weight"] for d in dims.values()) / sum(d["weight"] for d in dims.values()))
    ranked = sorted(dims.items(), key=lambda kv: (kv[1]["score"], -kv[1]["weight"]))
    fixes = [f"{name}: {d['fix']}" for name, d in ranked[:3]]
    if load_time_seconds > 3:
        fixes.insert(0, f"Speed: {load_time_seconds}s load — get under 2.5s before testing copy.")
    return {
        "score": total,
        "grade": "A" if total >= 85 else "B" if total >= 70 else "C" if total >= 55 else "D",
        "dimensions": dims,
        "stats": {
            "words": n_words,
            "fk_grade": rd["fk_grade"],
            "we_count": we,
            "you_count": you,
            "proof_mentions": proof,
            "numbers": numbers,
            "jargon": jargon_hits,
            "ctas_detected": cta_labels,
            "anxiety_relievers": anxiety_relievers,
            "message_match_ratio": match_ratio,
        },
        "fixes": fixes,
        "summary": f"{total}/100. Weakest: {ranked[0][0]} ({ranked[0][1]['score']}), then {ranked[1][0]} ({ranked[1][1]['score']}).",
    }


@AGENT.tool
def headline_clarity(headline: str, subheadline: str = "", cta_label: str = "") -> dict:
    """Five-second-test a hero: does the headline + subheadline + CTA say what, for whom, and why, in plain words?

    Call on the current hero and again on your rewrite; ship only grade A/B.

    Args:
        headline: The H1.
        subheadline: The supporting line under the H1 (optional).
        cta_label: The primary button label (optional).
    """
    h = require_text(headline, "headline", 1000).strip()
    hw = text.words(h)
    sw = text.words(subheadline)
    checks: dict[str, bool] = {}
    fixes = []
    checks["headline_len_ok"] = 3 <= len(hw) <= 10
    if not checks["headline_len_ok"]:
        fixes.append("Headline should be 3-10 words." if len(hw) > 10 else "Headline too short to state an outcome.")
    combined = f"{h} {subheadline}"
    lowc = combined.lower()
    checks["states_outcome"] = bool(re.search(r"\b(get|save|grow|cut|reduce|faster|more|less|without|in \d+|double|stop|never|increase|close|ship|launch|hire|sell|find|book|track|manage|automate|turn|make)\b", lowc)) or bool(re.search(r"\d", combined))
    if not checks["states_outcome"]:
        fixes.append("Name the outcome (what changes for the reader) — a verb or a number.")
    checks["names_audience"] = bool(re.search(r"\b(for|teams?|founders|marketers|agencies|developers|managers|ops|sales|hr|freelancers|creators|parents|small business|smbs?|enterprises?|students|clinics|restaurants|shops)\b", lowc))
    if not checks["names_audience"]:
        fixes.append("Say who it's for, in the headline or subheadline.")
    checks["says_what_it_is"] = bool(re.search(r"\b(app|software|platform|tool|service|course|template|plugin|api|crm|marketplace|agency|book|kit|system|dashboard|extension|plan|program|coach)\b", lowc)) or bool(re.search(r"\b(is|helps|lets|turns)\b", lowc))
    if not checks["says_what_it_is"]:
        fixes.append("A first-time visitor can't tell what the product is — name the category in the subheadline.")
    jargon = sorted({w.lower() for w in hw + sw if w.lower() in JARGON})
    checks["no_jargon"] = not jargon
    if jargon:
        fixes.append(f"Remove jargon: {', '.join(jargon)}.")
    checks["reader_focused"] = len(YOU_RE.findall(combined)) >= len(WE_RE.findall(combined))
    if not checks["reader_focused"]:
        fixes.append("More 'we/our' than 'you' — flip the sentence to the reader.")
    checks["has_proof"] = bool(PROOF_RE.search(combined)) or bool(re.search(r"\d", subheadline))
    if not checks["has_proof"]:
        fixes.append("Put one proof point in the subheadline (number, customer, rating).")
    checks["sub_len_ok"] = not subheadline or len(sw) <= 25
    if not checks["sub_len_ok"]:
        fixes.append("Subheadline over 25 words — cut to the mechanism + one proof.")
    cta_ok = True
    if cta_label:
        c = cta_label.strip().lower()
        cta_ok = c not in WEAK_CTA and (text.words(c)[0] in CTA_VERBS if text.words(c) else False) and len(text.words(c)) <= 5
        if not cta_ok:
            fixes.append("CTA should be verb-first + what they get ('Start my free trial'), ≤ 5 words, never 'Submit'/'Learn more'.")
    checks["cta_ok"] = cta_ok
    rd = text.readability(combined)
    checks["readable"] = (rd["fk_grade"] or 0) <= 9
    if not checks["readable"]:
        fixes.append(f"Reading grade {rd['fk_grade']} — use shorter words.")
    passed = sum(checks.values())
    total = len(checks)
    pct_score = round(100 * passed / total)
    grade = "A" if pct_score >= 90 else "B" if pct_score >= 75 else "C" if pct_score >= 55 else "F"
    return {
        "headline_words": len(hw),
        "subheadline_words": len(sw),
        "fk_grade": rd["fk_grade"],
        "checks": checks,
        "passed": f"{passed}/{total}",
        "score": pct_score,
        "grade": grade,
        "fixes": fixes,
        "verdict": f"Grade {grade} ({passed}/{total}). " + ("Ship it." if grade in "AB" else "Rewrite the hero before touching anything else."),
    }


@AGENT.tool
def funnel_leaks(steps: list[dict], value_per_final_conversion: float = 0.0) -> dict:
    """Compute step-to-step conversion, cumulative conversion and the biggest absolute and relative leak in a funnel.

    Call with ordered steps from landing to final conversion; the largest leak is where to work.

    Args:
        steps: Ordered list of {"name": str, "count": int}, e.g. [{"name": "visits", "count": 40000}, ...].
        value_per_final_conversion: Optional revenue per final-step conversion to price each leak.
    """
    if len(steps) < 2 or len(steps) > 30:
        raise ToolError("Provide 2-30 ordered funnel steps.")
    parsed = []
    for i, s in enumerate(steps):
        try:
            name = str(s.get("name") or f"step {i + 1}")
            count = float(s.get("count"))
        except (AttributeError, TypeError, ValueError):
            raise ToolError('Each step needs {"name": str, "count": number}.') from None
        if count < 0:
            raise ToolError(f"Step {name!r} has a negative count.")
        parsed.append((name, count))
    if parsed[0][1] <= 0:
        raise ToolError("The first step must have a count > 0.")
    for i in range(1, len(parsed)):
        if parsed[i][1] > parsed[i - 1][1]:
            raise ToolError(f"Step {parsed[i][0]!r} ({parsed[i][1]:.0f}) exceeds the previous step ({parsed[i - 1][1]:.0f}); funnels only shrink.")
    top = parsed[0][1]
    final = parsed[-1][1]
    overall_cvr = final / top
    rows, leaks = [], []
    for i, (name, count) in enumerate(parsed):
        row = {"step": name, "count": int(count), "cumulative_pct": round(100 * count / top, 2)}
        if i > 0:
            prev = parsed[i - 1][1]
            step_rate = count / prev if prev else 0
            lost = prev - count
            row.update({"step_conversion_pct": round(100 * step_rate, 2), "lost": int(lost), "lost_pct_of_prev": round(100 * (1 - step_rate), 2)})
            # Value of the lost users if they had converted downstream at the current downstream rate.
            downstream_rate = (final / count) if count else 0
            row["final_conversions_lost"] = round(lost * downstream_rate, 1)
            if value_per_final_conversion:
                row["value_lost"] = round(lost * downstream_rate * value_per_final_conversion, 2)
            leaks.append((name, lost, 1 - step_rate, lost * downstream_rate))
        rows.append(row)
    worst_abs = max(leaks, key=lambda t: t[3])
    worst_rel = max(leaks, key=lambda t: t[2])
    # What a 10% relative improvement at the worst step is worth.
    idx = [r["step"] for r in rows].index(worst_abs[0])
    prev_count = rows[idx - 1]["count"]
    cur = rows[idx]["count"]
    improved = min(prev_count, cur * 1.10)
    extra_final = (improved - cur) * (final / cur if cur else 0)
    return {
        "steps": rows,
        "overall_conversion_pct": round(100 * overall_cvr, 3),
        "biggest_leak_by_lost_conversions": {"step": worst_abs[0], "lost_users": int(worst_abs[1]), "final_conversions_lost": round(worst_abs[3], 1)},
        "biggest_leak_by_rate": {"step": worst_rel[0], "drop_pct": round(100 * worst_rel[2], 2)},
        "value_of_10pct_fix_at_biggest_leak": {
            "extra_final_conversions": round(extra_final, 1),
            "extra_value": round(extra_final * value_per_final_conversion, 2) if value_per_final_conversion else None,
        },
        "summary": f"Overall {100 * overall_cvr:.2f}%. Biggest leak: '{worst_abs[0]}' loses {int(worst_abs[1]):,} users (≈{worst_abs[3]:.0f} final conversions). A 10% step improvement there ≈ +{extra_final:.0f} final conversions.",
    }


@AGENT.tool
def lift_value(monthly_visitors: int, current_cvr_pct: float, target_cvr_pct: float, value_per_conversion: float, months: int = 12) -> dict:
    """Translate a conversion-rate lift into extra conversions and revenue per month and over a horizon.

    Call to lead the report with the size of the prize before listing fixes.

    Args:
        monthly_visitors: Visitors per month to the page.
        current_cvr_pct: Current conversion rate in percent.
        target_cvr_pct: Expected conversion rate after the fix, in percent.
        value_per_conversion: Revenue (or pipeline value) per conversion.
        months: Horizon for the cumulative figure (default 12).
    """
    if monthly_visitors <= 0 or value_per_conversion < 0 or months < 1 or months > 120:
        raise ToolError("monthly_visitors > 0, value_per_conversion ≥ 0, months 1-120.")
    if not 0 <= current_cvr_pct <= 100 or not 0 <= target_cvr_pct <= 100:
        raise ToolError("Conversion rates must be between 0 and 100 percent.")
    cur = monthly_visitors * current_cvr_pct / 100
    tgt = monthly_visitors * target_cvr_pct / 100
    extra = tgt - cur
    rel = (target_cvr_pct - current_cvr_pct) / current_cvr_pct if current_cvr_pct else None
    return {
        "current_conversions_per_month": round(cur, 1),
        "target_conversions_per_month": round(tgt, 1),
        "extra_conversions_per_month": round(extra, 1),
        "relative_lift_pct": round(100 * rel, 1) if rel is not None else None,
        "extra_revenue_per_month": round(extra * value_per_conversion, 2),
        "extra_revenue_over_horizon": round(extra * value_per_conversion * months, 2),
        "months": months,
        "summary": f"{current_cvr_pct}% → {target_cvr_pct}% = +{extra:.0f} conversions/mo ≈ {extra * value_per_conversion:,.0f}/mo, {extra * value_per_conversion * months:,.0f} over {months} months."
        + (f" That is a {100 * rel:.0f}% relative lift — " + ("plausible for a hero rewrite." if rel <= 0.3 else "aggressive; be ready to justify it.") if rel is not None else ""),
    }


@AGENT.tool
def test_sample_size(baseline_cvr_pct: float, expected_relative_lift_pct: float, monthly_visitors: int = 0, power: float = 0.8, alpha: float = 0.05) -> dict:
    """Visitors per variant and weeks needed to prove a landing-page change at 80% power (two-sided).

    Call after choosing the fix, to decide between "A/B test it" and "just ship it".

    Args:
        baseline_cvr_pct: Current conversion rate in percent.
        expected_relative_lift_pct: The relative lift you expect (e.g. 15 for +15%).
        monthly_visitors: Monthly page visitors, to convert the sample into weeks; 0 to skip.
        power: Statistical power (default 0.8).
        alpha: Two-sided significance level (default 0.05).
    """
    if not 0 < baseline_cvr_pct < 100 or expected_relative_lift_pct <= 0:
        raise ToolError("baseline_cvr_pct in (0, 100); expected_relative_lift_pct > 0.")
    if not 0.5 <= power < 1 or not 0 < alpha < 0.5:
        raise ToolError("power in [0.5, 1); alpha in (0, 0.5).")
    p1 = baseline_cvr_pct / 100
    p2 = p1 * (1 + expected_relative_lift_pct / 100)
    if p2 >= 1:
        raise ToolError("Target rate exceeds 100%; lower the lift.")
    za, zb = norm_ppf(1 - alpha / 2), norm_ppf(power)
    pbar = (p1 + p2) / 2
    n = ((za * math.sqrt(2 * pbar * (1 - pbar)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2) / ((p2 - p1) ** 2)
    per_arm = math.ceil(n)
    out = {"visitors_per_variant": per_arm, "visitors_total": 2 * per_arm, "baseline_cvr_pct": baseline_cvr_pct, "target_cvr_pct": round(100 * p2, 3), "power": power, "alpha": alpha}
    if monthly_visitors > 0:
        weeks = 2 * per_arm / (monthly_visitors / 4.345)
        weeks_rounded = max(1, math.ceil(weeks))
        out["weeks_needed"] = weeks_rounded
        if weeks_rounded > 6:
            out["recommendation"] = f"{weeks_rounded} weeks is too long. Ship the change (measure pre/post with a holdout) or test a bolder variant (≥ {math.ceil(expected_relative_lift_pct * math.sqrt(weeks / 6))}% lift)."
        else:
            out["recommendation"] = f"Test it: ~{weeks_rounded} week(s) at {monthly_visitors:,} visitors/month. Run at least 1 full week regardless."
    out["summary"] = f"{per_arm:,} visitors per variant to detect +{expected_relative_lift_pct}% relative on a {baseline_cvr_pct}% baseline."
    return out
