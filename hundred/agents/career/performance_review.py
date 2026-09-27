"""Performance Review Writer — reviews built from SBI evidence and goal math, checked for bias and recency before they're filed."""

from __future__ import annotations

import re
import statistics
from collections import defaultdict
from datetime import date

from ...core import Agent, ToolError
from ...lib import dates, text
from ._common import pct, require_list, require_number, require_text, scan_lexicon

AGENT = Agent(
    slug="performance-review",
    name="Performance Review Writer",
    category="career",
    tagline="Write reviews that are specific, fair and defensible: SBI evidence, goal attainment math, and a bias check before you file.",
    description=(
        "Turns a manager's notes into a performance review a head of people would sign off: every claim in "
        "Situation-Behavior-Impact form, goal attainment computed from targets and actuals with weights, a "
        "rating that follows the evidence, and a language audit that catches personality-over-performance "
        "wording, gendered descriptors, absolutes and recency bias (all examples from the last month). "
        "Also calibrates ratings across a team so managers' leniency doesn't decide who gets promoted."
    ),
    triggers=[
        "write a performance review for my report",
        "turn my notes into review feedback",
        "is this review fair / biased",
        "help me write a self-review",
        "calibrate ratings across my team",
        "calculate goal attainment for the review cycle",
    ],
    examples=[
        "Here are my notes on Sam for H1 — write the review. Goals: ship v2 (done, 2 weeks late), NPS 40→50 (hit 47).",
        "Draft my self-review; here's what I shipped this half and my OKRs.",
        "Check this review before I submit it: 'Priya is a pleasure to work with and always helpful…'",
    ],
    connectors=["Lattice", "Workday", "Culture Amp", "Notion", "Google Docs"],
    playbook="""
    ## Standard
    You are a head of people who has run calibration for a thousand reviews. A great review is
    one the employee recognises as accurate, a skip-level could defend in a promotion committee,
    and a lawyer would be relaxed about. Every judgement is anchored to observed behaviour and a
    measured outcome; the rating follows the evidence, not the other way round. The metric:
    zero unsupported claims — every strength and every gap has a Situation, a Behavior and an
    Impact.

    ## Intake
    You need: the review period, the goals (with targets and actuals if any), and the manager's
    raw notes or examples. Ask at most: "What were the 2-3 goals and how did they land?" and
    "Give me one concrete example for each strength and each gap." If notes are thin, write the
    review with explicit [EXAMPLE NEEDED] placeholders rather than inventing specifics.

    ## Procedure
    1. **Compute goal attainment.** Call `performance_review__goal_attainment` with each goal's
       target, actual, weight and direction. Use its weighted attainment and rating band as the
       starting rating. Never eyeball percentages.
    2. **Convert every example to SBI.** For each strength and gap, call
       `performance_review__format_sbi` with the situation, behavior and impact. Fix what it
       flags: trait words instead of behaviours ("lazy", "brilliant"), no time/place, no
       impact, "always/never". Use its rewritten sentences verbatim in the review.
    3. **Draft** in the template below. Lead with impact, then strengths (2-3, each SBI), then
       growth areas (1-3, each SBI + the expectation for next period), then the rating and one
       paragraph on why. Growth areas are written as behaviours to start/stop, with a date to
       revisit. For a self-review, same structure, first person, numbers first.
    4. **Audit the language.** Call `performance_review__check_review_language` with the draft
       and the cycle dates. Fix every flag: personality words (helpful, abrasive, pleasant),
       vague praise, absolutes, comparisons to peers, and a recency flag if most dated examples
       fall in the last quarter of the cycle — go back to the notes for earlier examples.
    5. **Calibrate if you have the team.** With ratings for several people, call
       `performance_review__calibrate_ratings`. Flag managers whose average sits > 0.5 above or
       below the group and ratings that need a written justification (top and bottom bands).
    6. **Self-check:** every claim traces to an SBI; the rating matches the attainment band or
       the deviation is explained in writing; nothing in the review would surprise the employee
       (if it would, it belongs in a 1:1 first); no protected characteristics or proxies.

    ## Frameworks
    - **SBI (Center for Creative Leadership):** "In <situation: when/where>, you <behavior:
      observable>, which <impact: on whom/what, measured>." Behaviours, not traits.
    - **Attainment bands (weighted %):** < 70 below expectations; 70-89 partially meets;
      90-109 meets; 110-129 exceeds; ≥ 130 far exceeds. Lower-is-better goals invert.
      Qualitative goals need a rubric or they're not goals.
    - **Bias patterns to catch:** personality feedback given more to women ("abrasive",
      "helpful", "pleasant"), vaguer praise for under-represented groups, "potential" language
      for majority-group employees, recency bias, halo/horns from one big event, and idiosyncratic
      rater effect (the rating says more about the manager than the employee — calibrate).
    - **Language ratio:** outcome/behaviour words should outnumber personality words at least
      3:1. Every paragraph needs a number, a date or a named artefact.
    - **Growth areas:** one behaviour, one expectation, one date. "Improve communication" is
      not a growth area; "Send the weekly status by Friday noon without a reminder, starting
      next sprint" is.
    - Scope note: for terminations, PIPs or legally sensitive situations, involve HR/legal;
      this is a writing and analysis aid, not legal advice.

    ## Output format
    ```
    # Performance review — <Name> — <period>
    **Overall rating:** <band> (weighted goal attainment NN%)

    ## Impact this period
    <2-3 sentences with the headline numbers and artefacts>

    ## Goals
    | Goal | Target | Actual | Attainment | Weight |
    |---|---|---|---|---|

    ## Strengths
    - **<Strength>** — In <situation>, you <behavior>, which <impact>.

    ## Growth areas
    - **<Area>** — In <situation>, you <behavior>, which <impact>. Expectation: <behaviour> by <date>.

    ## Rating rationale
    <one paragraph tying the band to the evidence>

    ---
    Language audit: personality:outcome ratio 1:N · recency: ok/flagged · absolutes: 0 · bias terms: 0
    ```

    ## Anti-patterns
    - Traits instead of behaviours ("she's a natural leader", "he lacks attention to detail").
    - Feedback sandwiches that bury the growth area in praise so it never lands.
    - A rating that ignores the goal math because "the vibe was good/bad this half".
    - Every example from the last four weeks.
    - Comparing to peers by name. Compare to the expectations for the level.
    - Surprises. A review is a summary of conversations that already happened.
    """,
)

TRAIT_WORDS = {
    "lazy": "describe the missed commitment (what, when, how often)",
    "unmotivated": "describe the observed behaviour",
    "brilliant": "describe what they produced and its effect",
    "genius": "describe what they produced and its effect",
    "natural leader": "describe a specific act of leadership and its result",
    "rockstar": "describe the outcome",
    "attitude": "describe the words/actions and their effect",
    "unprofessional": "describe the specific behaviour",
    "difficult": "describe the specific behaviour and its impact",
    "not a team player": "describe the specific interaction",
    "team player": "describe a collaboration outcome",
    "hard-working": "describe output and outcomes",
    "hard working": "describe output and outcomes",
    "smart": "describe the decision or analysis",
    "sloppy": "name the defects and their cost",
    "careless": "name the defects and their cost",
    "passionate": "describe what they did",
    "immature": "describe the specific behaviour",
    "abrasive": "describe the words used and their effect on whom",
    "aggressive": "describe the words/actions and their effect",
    "bossy": "describe the behaviour and its effect",
    "emotional": "describe the behaviour and its effect",
    "helpful": "describe what they did and its measured effect",
    "pleasant": "outcome, not personality",
    "nice": "outcome, not personality",
    "bubbly": "remove",
    "friendly": "outcome, not personality",
}
ABSOLUTE_RE = re.compile(r"\b(always|never|constantly|every time|all the time|nobody|everyone|everybody)\b", re.I)
TIME_RE = re.compile(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s*\d{0,4}\b|\b(?:q[1-4]|h[12])\b|\b\d{4}-\d{2}(?:-\d{2})?\b|\b(?:during|in|at|on|last|this)\s+(?:the\s+)?(?:\w+\s+){0,2}(?:sprint|launch|review|meeting|offsite|incident|release|quarter|week|month|project|migration|demo|retro|planning|standup|deadline|outage|onboarding)\b|\b(?:week|sprint)\s+\d+\b", re.I)
IMPACT_RE = re.compile(r"\b(which|so that|resulting in|as a result|led to|meant|caused|saved|cost|reduced|increased|improved|delayed|unblocked|blocked|enabled|lost|won|cut|grew|freed|shipped|avoided|prevented|agreed|adopted|approved|escalated|churned|renewed|complained|thanked|missed|slipped|landed)\b|%|\$|\d", re.I)
IMPACT_VERB_START = re.compile(r"^(?:meant|led|caused|saved|cost|reduced|increased|improved|delayed|unblocked|blocked|enabled|lost|won|cut|grew|freed|avoided|prevented|resulted|left|gave|made|kept|put|forced|let|helped|allowed|took|slipped|landed)\b", re.I)
BEHAVIOR_VERB_RE = re.compile(r"\b(said|wrote|sent|shipped|built|led|ran|asked|told|missed|skipped|delivered|presented|reviewed|fixed|proposed|pushed|interrupted|escalated|documented|paired|mentored|refactored|tested|closed|opened|deployed|drafted|scheduled|flagged|declined|ignored|responded|replied|committed|merged|filed|raised|paused|stopped|started|cancelled|owned|took|handed|coached|planned|chose|decided|prioriti[sz]ed)\b", re.I)


@AGENT.tool
def format_sbi(items: list[dict]) -> dict:
    """Validate and rewrite feedback items into Situation-Behavior-Impact sentences; flags traits instead of behaviours, missing time/place, missing impact and absolutes.

    Args:
        items: [{"situation": str, "behavior": str, "impact": str, "kind": "strength"|"growth" (optional)}] — up to 40 items.
    """
    require_list(items, "items", max_items=40)
    rows = []
    for i, it in enumerate(items, 1):
        if not isinstance(it, dict):
            raise ToolError(f"item #{i} must be an object with situation/behavior/impact.")
        s = str(it.get("situation", "")).strip()
        b = str(it.get("behavior", "")).strip()
        im = str(it.get("impact", "")).strip()
        kind = str(it.get("kind", "")).strip().lower() or None
        if not (s or b or im):
            raise ToolError(f"item #{i} is empty.")
        issues, fixes = [], []
        if not s:
            issues.append("no situation")
            fixes.append("add when/where: 'In the March release retro…'")
        elif not TIME_RE.search(s):
            issues.append("situation has no time or place marker")
            fixes.append("anchor it: a date, sprint, meeting, project or incident name")
        if not b:
            issues.append("no behavior")
        else:
            traits = scan_lexicon(b, TRAIT_WORDS)
            if traits:
                issues.append("trait instead of behaviour: " + ", ".join(f"'{t['term']}'" for t in traits))
                fixes.extend(f"'{t['term']}' → {t['suggestion']}" for t in traits[:3])
            elif not BEHAVIOR_VERB_RE.search(b):
                issues.append("behaviour isn't observable (no action verb)")
                fixes.append("say what they did or said: 'sent the status doc two days late', 'interrupted the client twice'")
            if ABSOLUTE_RE.search(b):
                issues.append("absolute ('always/never')")
                fixes.append("replace with a frequency: 'in 3 of the last 4 sprints'")
        if not im:
            issues.append("no impact")
            fixes.append("add the effect on a person, team, customer or metric — with a number if possible")
        elif not IMPACT_RE.search(im):
            issues.append("impact isn't concrete")
            fixes.append("name who/what was affected and by how much")
        quantified = bool(re.search(r"\d", im))
        score = max(0, 100 - 20 * len([x for x in issues if x.startswith("no ")]) - 12 * len([x for x in issues if not x.startswith("no ")]))
        # Rewrite.
        sit = s.rstrip(".") if s else "[when/where?]"
        if sit and not sit.startswith("[") and not re.match(r"^(?:in|during|at|on|when|while|after|before|last|this|throughout|over)\b", sit, re.I):
            sit = "in " + sit
        sit = sit[0].lower() + sit[1:] if not sit.startswith("[") else sit
        beh = b.rstrip(".") if b else "[what did they do?]"
        if not beh.startswith("["):
            beh = re.sub(r"^(?:he|she|they|you)\s+(?:is|was|are|were|has been|have been)?\s*", "", beh, flags=re.I)
            beh = re.sub(r"^(?:is|was|are|were)\s+", "", beh, flags=re.I)
            beh = beh[0].lower() + beh[1:] if beh else beh
        impact = im.rstrip(".") if im else "[effect on whom/what?]"
        impact = re.sub(r"^(?:which|this|that|it|and|so|as a result,?)\s+", "", impact, flags=re.I)
        joiner = "which" if IMPACT_VERB_START.match(impact) or impact.startswith("[") else "which meant"
        sentence = f"{sit[0].upper() + sit[1:]}, you {beh}, {joiner} {impact}."
        rows.append({"n": i, "kind": kind, "situation": s, "behavior": b, "impact": im, "issues": issues, "fixes": fixes, "quantified_impact": quantified, "score": score, "sbi": sentence})
    ready = [r["n"] for r in rows if not r["issues"]]
    return {
        "items": rows,
        "ready": ready,
        "needs_work": [r["n"] for r in rows if r["issues"]],
        "quantified_pct": pct(sum(1 for r in rows if r["quantified_impact"]), len(rows)),
        "verdict": f"{len(ready)}/{len(rows)} items are clean SBI; {pct(sum(1 for r in rows if r['quantified_impact']), len(rows))}% have a number in the impact.",
    }


PERSONALITY = {**{k: v for k, v in TRAIT_WORDS.items()}, "personality": "describe behaviour", "energy": "describe behaviour", "likeable": "remove", "charming": "remove", "warm": "remove", "supportive": "what did they do, with what effect?", "kind": "remove", "loud": "describe the behaviour", "quiet": "describe the behaviour and impact", "shy": "describe the behaviour and impact", "confident": "describe the behaviour", "mature": "remove (age-coded)", "young": "remove (age-coded)", "family": "remove (family status)", "pregnan": "remove (protected)", "kids": "remove (family status)", "maternity": "remove (protected)", "accent": "remove (national origin)", "health": "remove (protected)", "religio": "remove (protected)"}
OUTCOME_RE = re.compile(r"\b(shipped|delivered|launched|reduced|increased|cut|grew|saved|closed|hit|missed|exceeded|achieved|migrated|fixed|resolved|built|wrote|presented|led|onboarded|mentored|automated|improved|retained|won|lost|completed|%|\$|revenue|latency|uptime|churn|nps|velocity|bugs?|incidents?|tickets?|customers?|users?|deals?|\d+)\b", re.I)
VAGUE_PRAISE = {"great job": "which job, what result?", "did well": "what and how measured?", "good work": "which work?", "solid contributor": "contributed what?", "valuable member": "what value, measured how?", "went above and beyond": "what specifically?", "excellent": "at what, evidenced by?", "outstanding": "at what, evidenced by?", "strong performer": "which goals, what attainment?", "has potential": "potential for what, based on what evidence?", "high potential": "based on what evidence?", "needs to improve": "what behaviour, to what standard, by when?", "could be better": "what behaviour, to what standard, by when?", "communication skills": "which communication behaviour?", "step up": "what specifically?"}
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
DATE_MENTION_RE = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?(?:\s+\d{1,2})?(?:,?\s+(\d{4}))?\b|\b(\d{4})-(\d{2})(?:-\d{2})?\b|\b(q[1-4])\b", re.I)


@AGENT.tool
def check_review_language(review: str, cycle_start: str = "", cycle_end: str = "") -> dict:
    """Audit a review for personality-over-performance wording, gendered/protected terms, vague praise, absolutes, peer comparisons and recency bias.

    Recency bias is measured from dated mentions in the text: if most fall in the last quarter
    of the cycle, the review is flagged. Returns a personality:outcome ratio and rewrite prompts.

    Args:
        review: The review draft.
        cycle_start: Review period start, YYYY-MM-DD (optional, needed for the recency check).
        cycle_end: Review period end, YYYY-MM-DD (optional, needed for the recency check).
    """
    require_text(review, "review")
    personality = scan_lexicon(review, PERSONALITY)
    vague = scan_lexicon(review, VAGUE_PRAISE)
    absolutes = ABSOLUTE_RE.findall(review)
    outcome_hits = len(OUTCOME_RE.findall(review))
    pers_n = sum(h["count"] for h in personality)
    comparisons = re.findall(r"\b(unlike|compared to|better than|worse than|not as \w+ as|the rest of the team|other (?:engineers|team members|people|reports))\b", review, re.I)
    protected = [h for h in personality if "protected" in h["suggestion"] or "age-coded" in h["suggestion"] or "family" in h["suggestion"] or "national origin" in h["suggestion"]]
    sents = text.sentences(review)
    evidenced = sum(1 for s in sents if re.search(r"\d|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b|\bq[1-4]\b", s, re.I))
    recency = None
    if cycle_start and cycle_end:
        cs, ce = dates.parse_date(cycle_start), dates.parse_date(cycle_end)
        if ce <= cs:
            raise ToolError("cycle_end must be after cycle_start.")
        span = (ce - cs).days
        cutoff = ce.toordinal() - span * 0.25
        dated: list[date] = []
        for m in DATE_MENTION_RE.finditer(review):
            mon, yr, y2, m2, q = m.groups()
            try:
                if mon:
                    y = int(yr) if yr else (ce.year if MONTHS[mon.lower()[:3]] <= ce.month else cs.year)
                    dated.append(date(y, MONTHS[mon.lower()[:3]], 15))
                elif y2:
                    dated.append(date(int(y2), int(m2), 15))
                elif q:
                    qn = int(q[1])
                    dated.append(date(ce.year if qn * 3 <= ce.month or ce.year == cs.year else cs.year, qn * 3 - 1, 15))
            except ValueError:
                continue
        in_cycle = [d for d in dated if cs <= d <= ce]
        late = [d for d in in_cycle if d.toordinal() >= cutoff]
        recency = {"dated_mentions": len(in_cycle), "in_last_quarter_of_cycle": len(late), "pct_late": pct(len(late), len(in_cycle)), "flag": len(in_cycle) >= 2 and len(late) / len(in_cycle) >= 0.7, "months_covered": sorted({d.strftime("%Y-%m") for d in in_cycle})}
    issues, fixes = [], []
    score = 100
    if protected:
        issues.append("protected/proxy terms: " + ", ".join(f"'{h['term']}'" for h in protected))
        score -= 25 * len(protected)
    if pers_n and (outcome_hits < 3 * pers_n):
        issues.append(f"personality:outcome ratio 1:{round(outcome_hits / pers_n, 1) if pers_n else 0} (aim ≥ 1:3)")
        fixes.extend(f"'{h['term']}' → {h['suggestion']}" for h in personality[:5])
        score -= 15
    elif pers_n:
        fixes.extend(f"'{h['term']}' → {h['suggestion']}" for h in personality[:3])
        score -= 3 * min(pers_n, 3)
    if vague:
        issues.append("vague praise/criticism: " + ", ".join(f"'{h['term']}'" for h in vague[:6]))
        fixes.extend(f"'{h['term']}' → {h['suggestion']}" for h in vague[:4])
        score -= min(20, 5 * len(vague))
    if absolutes:
        issues.append(f"absolutes: {', '.join(sorted(set(a.lower() for a in absolutes)))}")
        fixes.append("replace with frequencies ('in 3 of 4 sprints')")
        score -= 5 * len(absolutes)
    if comparisons:
        issues.append(f"peer comparison(s): {len(comparisons)}")
        fixes.append("compare to the level's expectations, not to named peers")
        score -= 10
    if sents and pct(evidenced, len(sents)) < 40:
        issues.append(f"only {pct(evidenced, len(sents))}% of sentences carry a number, date or artefact")
        fixes.append("every paragraph needs a number, a date or a named deliverable")
        score -= 15
    if recency and recency["flag"]:
        issues.append(f"recency bias: {recency['in_last_quarter_of_cycle']}/{recency['dated_mentions']} dated examples fall in the last quarter of the cycle")
        fixes.append("pull examples from the first half of the period (1:1 notes, shipped work, earlier feedback)")
        score -= 15
    score = max(0, score)
    return {
        "score": score,
        "personality_terms": personality,
        "personality_count": pers_n,
        "outcome_mentions": outcome_hits,
        "vague_terms": vague,
        "absolutes": sorted(set(a.lower() for a in absolutes)),
        "peer_comparisons": len(comparisons),
        "evidenced_sentence_pct": pct(evidenced, len(sents)),
        "recency": recency,
        "issues": issues,
        "fixes": fixes,
        "verdict": ("Language is clean and evidence-based." if score >= 85 else f"Score {score}/100 — {len(issues)} issue(s) to fix before filing."),
    }


@AGENT.tool
def goal_attainment(goals: list[dict], cap_pct: float = 150) -> dict:
    """Compute attainment % per goal (higher- or lower-is-better), weighted overall attainment and the rating band.

    Args:
        goals: [{"name": str, "target": number, "actual": number, "weight": number (default 1), "direction": "higher"|"lower" (default higher), "baseline": number (optional, for lower-is-better or improvement goals)}].
        cap_pct: Cap on a single goal's attainment so one blow-out doesn't hide misses (default 150).
    """
    require_list(goals, "goals", max_items=50)
    cap = require_number(cap_pct, "cap_pct", 100, 1000)
    rows = []
    for i, g in enumerate(goals, 1):
        if not isinstance(g, dict):
            raise ToolError(f"goal #{i} must be an object.")
        name = str(g.get("name") or f"Goal {i}")
        try:
            target = float(g["target"])
            actual = float(g["actual"])
        except (KeyError, TypeError, ValueError):
            raise ToolError(f"goal '{name}': target and actual must be numbers (qualitative goals need a rubric score, e.g. target 3, actual 2).") from None
        weight = require_number(g.get("weight", 1), f"goal '{name}' weight", 0)
        direction = str(g.get("direction", "higher")).lower()
        baseline = g.get("baseline")
        if direction not in ("higher", "lower"):
            raise ToolError(f"goal '{name}': direction must be 'higher' or 'lower'.")
        if baseline is not None:
            base = float(baseline)
            span = target - base
            if span == 0:
                raise ToolError(f"goal '{name}': target equals baseline — no improvement to measure.")
            att = 100 * (actual - base) / span
        elif direction == "higher":
            if target == 0:
                raise ToolError(f"goal '{name}': target is 0 — give a baseline or a non-zero target.")
            att = 100 * actual / target
        else:
            if actual == 0:
                att = cap
            else:
                att = 100 * target / actual
        att = max(0.0, min(cap, att))
        band = "far exceeds" if att >= 130 else "exceeds" if att >= 110 else "meets" if att >= 90 else "partially meets" if att >= 70 else "below"
        rows.append({"name": name, "target": target, "actual": actual, "direction": direction, "baseline": baseline, "weight": weight, "attainment_pct": round(att, 1), "band": band})
    tot_w = sum(r["weight"] for r in rows)
    if tot_w <= 0:
        raise ToolError("weights must sum to more than 0.")
    weighted = sum(r["attainment_pct"] * r["weight"] for r in rows) / tot_w
    overall_band = "far exceeds" if weighted >= 130 else "exceeds" if weighted >= 110 else "meets" if weighted >= 90 else "partially meets" if weighted >= 70 else "below"
    misses = [r["name"] for r in rows if r["attainment_pct"] < 90]
    return {
        "goals": rows,
        "weighted_attainment_pct": round(weighted, 1),
        "rating_band": overall_band,
        "bands": {"below": "< 70", "partially meets": "70-89", "meets": "90-109", "exceeds": "110-129", "far exceeds": "≥ 130"},
        "missed_goals": misses,
        "verdict": f"Weighted attainment {weighted:.1f}% → {overall_band}." + (f" Missed: {', '.join(misses)}." if misses else " All goals at or above 90%."),
    }


@AGENT.tool
def calibrate_ratings(ratings: list[dict], scale_max: int = 5, expected_distribution: dict | None = None) -> dict:
    """Compare ratings across managers: distribution vs an expected curve, per-manager leniency, and who needs written justification.

    Args:
        ratings: [{"employee": str, "manager": str, "rating": number (1..scale_max), "level": str (optional)}].
        scale_max: Top of the scale (3, 4 or 5).
        expected_distribution: Optional {"<rating>": pct} expected share per rating; default is a gentle curve (5-scale: 1:5, 2:10, 3:55, 4:22, 5:8).
    """
    require_list(ratings, "ratings", max_items=500, min_items=2)
    if scale_max not in (3, 4, 5):
        raise ToolError("scale_max must be 3, 4 or 5.")
    defaults = {5: {1: 5, 2: 10, 3: 55, 4: 22, 5: 8}, 4: {1: 8, 2: 30, 3: 50, 4: 12}, 3: {1: 10, 2: 75, 3: 15}}
    expected = {int(k): float(v) for k, v in (expected_distribution or defaults[scale_max]).items()}
    if abs(sum(expected.values()) - 100) > 1:
        raise ToolError("expected_distribution must sum to 100.")
    by_mgr: dict[str, list[float]] = defaultdict(list)
    rows = []
    for i, r in enumerate(ratings, 1):
        if not isinstance(r, dict):
            raise ToolError(f"rating #{i} must be an object.")
        try:
            val = float(r["rating"])
        except (KeyError, TypeError, ValueError):
            raise ToolError(f"rating #{i}: 'rating' must be a number.") from None
        if not 1 <= val <= scale_max:
            raise ToolError(f"rating #{i}: {val} outside 1-{scale_max}.")
        mgr = str(r.get("manager") or "unknown")
        by_mgr[mgr].append(val)
        rows.append({"employee": str(r.get("employee") or f"Employee {i}"), "manager": mgr, "rating": val, "level": r.get("level")})
    all_vals = [r["rating"] for r in rows]
    mean = statistics.mean(all_vals)
    sd = statistics.pstdev(all_vals)
    dist = {k: pct(sum(1 for v in all_vals if round(v) == k), len(all_vals)) for k in range(1, scale_max + 1)}
    dist_gap = {k: round(dist[k] - expected.get(k, 0), 1) for k in dist}
    managers = {}
    for m, vals in by_mgr.items():
        mm = statistics.mean(vals)
        managers[m] = {"n": len(vals), "mean": round(mm, 2), "delta_vs_org": round(mm - mean, 2), "top_band_pct": pct(sum(1 for v in vals if v >= scale_max), len(vals)), "flag": ("lenient" if mm - mean >= 0.5 else "harsh" if mm - mean <= -0.5 else None) if len(vals) >= 3 else "too few to judge"}
    for r in rows:
        r["z_score"] = round((r["rating"] - mean) / sd, 2) if sd else 0.0
        r["needs_justification"] = r["rating"] >= scale_max or r["rating"] <= 1
    top_share = dist.get(scale_max, 0)
    flags = []
    if top_share > expected.get(scale_max, 0) + 10:
        flags.append(f"{top_share}% at the top rating vs ~{expected.get(scale_max, 0)}% expected — top ratings need written evidence of exceeding the level")
    if dist.get(1, 0) + dist.get(2, 0) < 3 and len(all_vals) >= 10:
        flags.append("almost no low ratings — either the team is exceptional or gaps aren't being named")
    for m, v in managers.items():
        if v["flag"] in ("lenient", "harsh"):
            flags.append(f"{m} is {v['flag']}: mean {v['mean']} vs org {round(mean, 2)} — review their top/bottom cases first")
    return {
        "n": len(rows),
        "org_mean": round(mean, 2),
        "org_sd": round(sd, 2),
        "distribution_pct": dist,
        "expected_pct": expected,
        "distribution_gap_pct": dist_gap,
        "managers": managers,
        "employees": rows,
        "needs_justification": [r["employee"] for r in rows if r["needs_justification"]],
        "flags": flags,
        "verdict": f"{len(rows)} ratings, mean {mean:.2f}; {len(flags)} calibration flag(s)." + (" Discuss: " + flags[0] if flags else ""),
    }
