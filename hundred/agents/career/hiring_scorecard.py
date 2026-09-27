"""Hiring Scorecard — structured interviews: a weighted rubric, a loop that covers it, evidence-based scoring and a clean debrief."""

from __future__ import annotations

import re
import statistics
from collections import defaultdict

from ...core import Agent, ToolError
from ...lib import text
from ._common import pct, require_list, require_text, scan_lexicon

AGENT = Agent(
    slug="hiring-scorecard",
    name="Hiring Scorecard",
    category="career",
    tagline="Build a weighted, behaviorally-anchored scorecard, assign the loop, and score candidates on evidence — not gut feel.",
    description=(
        "Runs structured hiring the way the best people teams do: defines 5-7 job-related competencies with "
        "weights and 1-4 behavioral anchors, rejects rubric items that proxy for protected characteristics "
        "('culture fit', 'energy'), assigns each competency to at least two interviewers with matching "
        "questions, computes weighted candidate scores with must-have bars, inter-rater disagreement and "
        "interviewer leniency, and audits written feedback for bias and evidence quality before the debrief. "
        "Fair, consistent, defensible decisions."
    ),
    triggers=[
        "create an interview scorecard / rubric for this role",
        "design a structured interview loop",
        "score these candidates / who should we hire",
        "review this interview feedback for bias",
        "how do we run a hiring debrief",
        "build an interview kit for my panel",
    ],
    examples=[
        "Build a scorecard and interview kit for a Senior Data Analyst; panel is me, Priya and Tom.",
        "Here are the four interviewers' ratings for three candidates. Who's the hire, and where do we disagree?",
        "Check this interview feedback before I post it in Greenhouse: 'Great energy, not sure about culture fit…'",
    ],
    connectors=["Greenhouse", "Lever", "Ashby", "Workable", "Notion", "Google Sheets", "Slack"],
    playbook="""
    ## Standard
    You are a head of talent who has built hiring processes at companies that are audited on
    them. The standard: every candidate is asked the same job-related questions, rated on the
    same behavioral anchors by interviewers who write evidence before they write opinions, and
    the decision follows the numbers unless someone can name the evidence that overrides them.
    Structured interviews roughly double the predictive validity of unstructured ones; that is
    the whole product. The metric: decisions traceable to rubric evidence, no interviewer
    rating on anything outside the rubric.

    ## Intake
    You need: the role (JD or a description of year-one outcomes), the interviewer panel, and
    — for scoring — each interviewer's ratings. Ask at most: "What are the 3 outcomes this hire
    must deliver in year one?" if the JD is thin. Never ask for, record or consider anything
    about a candidate's age, gender, race, religion, disability, family plans, national
    origin, or any proxy for these; if a user supplies it, say you will not use it and proceed
    on job-related evidence only.

    ## Procedure
    1. **Define the rubric.** Derive 5-7 competencies from the year-one outcomes (mix: 3-4
       role skills, 1-2 ways-of-working like ownership or collaboration, 1 judgment/ambiguity).
       Mark 1-3 as must-haves. Weight them to 100. Call `hiring_scorecard__build_scorecard`
       with the competencies and the interviewer names. It validates weights, blocks items that
       proxy for protected characteristics, writes the 1-4 anchors and questions, and assigns
       every competency to ≥ 2 interviewers. Deliver the kit per interviewer.
    2. **Brief the panel.** Each interviewer gets: their 2-3 competencies, the questions to ask
       every candidate identically, the anchors, and the rule "evidence first: write what the
       candidate said/did, then rate". Ratings are submitted before the debrief and before
       seeing anyone else's.
    3. **Score.** After the loop, call `hiring_scorecard__score_candidates` with all ratings.
       Read: weighted score, must-have bar failures, competencies where raters disagree by
       > 1.5 points, and interviewer leniency. Disagreement is not averaged away — it is the
       debrief agenda.
    4. **Audit the feedback.** Before the debrief, call `hiring_scorecard__check_feedback_bias`
       on each written feedback. Anything flagged non-job-related is struck from the record;
       opinion-heavy feedback goes back to the interviewer with the tool's rewrite prompt.
    5. **Run the debrief** in this order: (a) must-have bar check — anyone below the bar on a
       must-have is a no-hire unless the panel names contrary evidence; (b) disagreements
       competency by competency, evidence only; (c) final ratings updated; (d) decision by the
       hiring manager against the tool's thresholds. Most junior speaks first.
    6. **Self-check:** every competency was rated by ≥ 2 people; no rating lacks written
       evidence; the decision names the deciding competencies; feedback contains nothing the
       candidate couldn't see.

    ## Frameworks
    - **4-point anchored scale:** 1 = clear gap (evidence contradicts the bar); 2 = partial
      (some evidence, notable gaps); 3 = meets (consistent evidence at the level);
      4 = exceeds (evidence beyond the level, could teach it). No midpoints, no "5 = unicorn".
    - **Decision thresholds (weighted 0-100):** ≥ 80 strong hire; 65-79 hire (if no must-have
      below 3); 50-64 no hire unless a must-have is a 4 and the gap is coachable; < 50 no hire.
      Any must-have averaging < 2.5 = no hire regardless of total.
    - **Coverage rule:** each competency by ≥ 2 interviewers; each interviewer ≤ 3
      competencies; a 45-minute interview covers 2 competencies well, 3 at most.
    - **Evidence ratio:** ≥ 60% of feedback sentences should be observations or quotes.
    - **Bias controls:** same questions for everyone; ratings before discussion; "culture fit"
      replaced by named behaviours ("gives direct feedback in the moment"); work samples over
      brainteasers; a diverse panel; decisions logged with reasons.
    - Scope note: employment law varies by jurisdiction; this is process guidance, not legal
      advice. Loop in counsel for disability accommodations and protected-class questions.

    ## Output format
    ```
    ## Scorecard — <Role>
    | # | Competency | Weight | Must-have | Anchor 1 / 2 / 3 / 4 |
    |---|---|---|---|---|

    ## Interview kit
    ### <Interviewer> — <45 min> — competencies: A, B
    Q1 (A): … · follow-ups: … · listen for: …
    Q2 (B): …

    ## Candidate scores (after loop)
    | Candidate | Weighted | Must-haves | Disagreements | Decision |
    |---|---|---|---|---|

    ## Debrief agenda
    1. Must-have bar: <who/what>
    2. Disagreements: <competency — rater A said … (2), rater B said … (4)>
    3. Decision + reasons

    ## Feedback audit
    <interviewer>: evidence NN% · flags: … · rewrite: …
    ```

    ## Anti-patterns
    - "Culture fit", "energy", "polish", "gut feel" as criteria. Name the behaviour or drop it.
    - Discussing candidates before ratings are submitted — anchoring makes the panel one voice.
    - Averaging away a 1 and a 4. That spread is the most important thing in the debrief.
    - Asking different questions of different candidates, then comparing answers.
    - Rating "communication" from a candidate's accent or nerves. Rate the content.
    - Writing feedback the candidate couldn't legally see. If it wouldn't survive discovery,
      it doesn't belong in the ATS.
    """,
)

PROTECTED_PROXIES = {
    "culture fit": "replace with named behaviours (e.g. 'gives direct feedback', 'ships without being chased')",
    "cultural fit": "replace with named behaviours",
    "energy": "proxy for age/personality — replace with 'drives work forward without prompting'",
    "energetic": "proxy for age — replace with an observable behaviour",
    "young": "age — remove",
    "youthful": "age — remove",
    "mature": "age — remove",
    "digital native": "age — remove",
    "recent grad": "age — remove",
    "polish": "appearance/class proxy — replace with 'structures answers clearly'",
    "polished": "appearance/class proxy — replace with 'structures answers clearly'",
    "presentable": "appearance — remove",
    "attractive": "appearance — remove",
    "gut": "not a criterion — rate on evidence",
    "gut feel": "not a criterion — rate on evidence",
    "vibe": "not a criterion — rate on evidence",
    "likeable": "affinity bias — remove",
    "likable": "affinity bias — remove",
    "beer test": "affinity bias — remove",
    "family": "family status — remove",
    "kids": "family status — remove",
    "children": "family status — remove",
    "pregnan": "protected — remove",
    "married": "marital status — remove",
    "accent": "national origin — remove; rate content, not delivery",
    "native speaker": "national origin — use 'communicates clearly in English'",
    "religion": "protected — remove",
    "church": "protected — remove",
    "disability": "protected — remove; discuss accommodations with HR only",
    "health": "protected — remove",
    "nationality": "protected — remove",
    "race": "protected — remove",
    "ethnic": "protected — remove",
    "gender": "protected — remove",
    "pedigree": "class proxy — rate the skill, not the school",
    "ivy league": "class proxy — rate the skill, not the school",
    "hungry": "vague — replace with 'sets own stretch goals'",
    "aggressive": "gendered evaluation term — describe the behaviour",
    "abrasive": "gendered evaluation term — describe the behaviour and its impact",
    "bossy": "gendered evaluation term — describe the behaviour",
    "emotional": "gendered evaluation term — describe the behaviour",
    "bubbly": "gendered evaluation term — remove",
    "nice": "vague/affinity — remove",
    "nervous": "rate content, not nerves",
    "confident": "delivery, not competence — rate the content",
}
COMPETENCY_BANK = {
    "ownership": ["Tell me about a project you drove end to end. What did you personally decide?", "Describe something that broke that wasn't your fault. What did you do?"],
    "collaboration": ["Tell me about working with someone whose approach differed from yours. What happened?", "Describe a time you changed your plan because of a teammate's input."],
    "communication": ["Walk me through how you explained a complex decision to someone outside your field.", "Tell me about delivering unwelcome news to a stakeholder."],
    "problem solving": ["Describe the hardest problem you solved recently. How did you narrow it down?", "Tell me about a time the obvious solution was wrong."],
    "ambiguity": ["Tell me about a decision you made without enough information.", "Describe a project whose goal kept changing."],
    "leadership": ["Tell me about developing someone on your team — what changed for them?", "Describe managing an underperformer."],
    "customer focus": ["Tell me about advocating for a customer against internal pressure.", "How did you find out what customers actually needed?"],
    "execution": ["Describe the most complex project you delivered. What slipped and how did you recover?", "Tell me about a time you had too much to do. How did you choose?"],
    "technical": ["Walk me through a technical decision with a real trade-off.", "Describe the hardest bug or analysis you've owned."],
    "learning": ["What have you deliberately learned in the last year, and how?", "Tell me about being the least experienced person in the room."],
    "judgment": ["Tell me about a call you made that others disagreed with. What happened?", "Describe a decision you'd make differently today."],
}


def _anchors(name: str, desc: str) -> dict[str, str]:
    what = desc.strip().rstrip(".") if desc.strip() else name
    return {
        "1": f"Clear gap: evidence contradicts the bar for {what}; couldn't give a concrete example or the example showed the opposite.",
        "2": f"Partial: one thin or assisted example of {what}; gaps in ownership, outcome or reflection.",
        "3": f"Meets: two or more concrete, first-person examples of {what} at this level, with outcomes.",
        "4": f"Exceeds: examples of {what} beyond this level, with measured outcomes and evidence of teaching or scaling it.",
    }


@AGENT.tool
def build_scorecard(role: str, competencies: list[dict], interviewers: list[str], minutes_per_interview: int = 45) -> dict:
    """Validate a competency rubric (weights, must-haves, fairness), write 1-4 behavioral anchors and questions, and assign the interview loop.

    Rejects competencies that proxy for protected characteristics ('culture fit', 'energy').
    Normalises weights to 100, assigns every competency to at least two interviewers with at
    most three competencies each, and returns a per-interviewer kit.

    Args:
        role: The role title, e.g. "Senior Data Analyst".
        competencies: 3-8 items: {"name": str, "weight": number, "must_have": bool, "description": str (what good looks like)}.
        interviewers: Names of the panel (2-8).
        minutes_per_interview: Length of each interview in minutes (30-90).
    """
    require_text(role, "role", max_chars=200)
    require_list(competencies, "competencies", max_items=8, min_items=3)
    require_list(interviewers, "interviewers", max_items=8, min_items=2)
    if not 30 <= minutes_per_interview <= 90:
        raise ToolError("minutes_per_interview must be 30-90.")
    names = [str(i).strip() for i in interviewers if str(i).strip()]
    if len(set(names)) != len(names) or len(names) < 2:
        raise ToolError("interviewers must be 2+ distinct non-empty names.")
    rejected, comps = [], []
    for i, c in enumerate(competencies, 1):
        if not isinstance(c, dict) or not str(c.get("name", "")).strip():
            raise ToolError(f"competency #{i} needs a 'name'.")
        name = str(c["name"]).strip()
        desc = str(c.get("description", "")).strip()
        hits = scan_lexicon(f"{name} {desc}", PROTECTED_PROXIES)
        if hits:
            rejected.append({"name": name, "reason": f"'{hits[0]['term']}': {hits[0]['suggestion']}"})
            continue
        try:
            w = float(c.get("weight", 0))
        except (TypeError, ValueError):
            raise ToolError(f"competency '{name}': weight must be a number.") from None
        if w < 0:
            raise ToolError(f"competency '{name}': weight can't be negative.")
        comps.append({"name": name, "weight": w, "must_have": bool(c.get("must_have", False)), "description": desc})
    if len(comps) < 3:
        raise ToolError("Fewer than 3 usable competencies after removing non-job-related items: " + "; ".join(r["reason"] for r in rejected))
    total_w = sum(c["weight"] for c in comps)
    if total_w <= 0:
        for c in comps:
            c["weight"] = 1.0
        total_w = float(len(comps))
    for c in comps:
        c["weight_pct"] = round(100 * c["weight"] / total_w, 1)
    # Questions and anchors.
    for c in comps:
        key = next((k for k in COMPETENCY_BANK if k in c["name"].lower() or k.split()[0] in c["name"].lower()), None)
        qs = COMPETENCY_BANK.get(key, [f"Tell me about a specific time you demonstrated {c['name'].lower()}. What did you personally do, and what was the result?", f"Describe a time {c['name'].lower()} was hard for you. What would you do differently?"])
        c["questions"] = qs
        c["follow_ups"] = ["What was your specific part?", "What was the measurable outcome?", "What would you do differently?"]
        c["anchors"] = _anchors(c["name"], c["description"])
    # Loop assignment: each competency to 2 interviewers (3 if panel ≥ 6), round-robin, balanced load.
    per_comp = 3 if len(names) >= 6 else 2
    max_per_interviewer = 3 if minutes_per_interview >= 45 else 2
    load: dict[str, list[str]] = {n: [] for n in names}
    order = sorted(comps, key=lambda c: (not c["must_have"], -c["weight"]))
    coverage: dict[str, list[str]] = {}
    idx = 0
    for c in order:
        assigned: list[str] = []
        tries = 0
        while len(assigned) < per_comp and tries < len(names) * 2:
            n = names[idx % len(names)]
            idx += 1
            tries += 1
            if n in assigned or len(load[n]) >= max_per_interviewer:
                continue
            load[n].append(c["name"])
            assigned.append(n)
        coverage[c["name"]] = assigned
    under = [k for k, v in coverage.items() if len(v) < 2]
    warnings = []
    if under:
        warnings.append(f"competencies with < 2 interviewers: {', '.join(under)} — add an interviewer or a second round")
    if rejected:
        warnings.append(f"removed {len(rejected)} non-job-related item(s): " + "; ".join(f"{r['name']} ({r['reason']})" for r in rejected))
    must = [c["name"] for c in comps if c["must_have"]]
    if not must:
        warnings.append("no must-haves marked — mark 1-3 so the bar check can run")
    kit = [{"interviewer": n, "minutes": minutes_per_interview, "competencies": load[n], "questions": [{"competency": cn, "ask": next(c for c in comps if c["name"] == cn)["questions"][0]} for cn in load[n]]} for n in names]
    return {
        "role": role,
        "competencies": comps,
        "must_haves": must,
        "weights_sum_to": round(sum(c["weight_pct"] for c in comps), 1),
        "rejected": rejected,
        "coverage": coverage,
        "kit": kit,
        "scale": {"1": "clear gap", "2": "partial", "3": "meets", "4": "exceeds"},
        "decision_thresholds": {"strong_hire": 80, "hire": 65, "must_have_bar": 2.5},
        "warnings": warnings,
        "verdict": f"{len(comps)} competencies ({len(must)} must-have) across {len(names)} interviewers; every competency covered by {per_comp} raters"
        + (" except: " + ", ".join(under) if under else "") + ".",
    }


@AGENT.tool
def score_candidates(candidates: list[dict], weights: dict, must_haves: list[str] | None = None, scale_max: int = 4) -> dict:
    """Compute weighted candidate scores (0-100), must-have bar failures, inter-rater disagreement and interviewer leniency, then rank and decide.

    Args:
        candidates: [{"name": str, "ratings": {"<interviewer>": {"<competency>": 1-4, ...}, ...}}].
        weights: {"<competency>": weight} (any positive numbers; normalised to 100).
        must_haves: Competency names where an average below 2.5 (on a 4-scale) is disqualifying.
        scale_max: Top of the rating scale (4 or 5).
    """
    require_list(candidates, "candidates", max_items=50)
    if not isinstance(weights, dict) or not weights:
        raise ToolError("weights must map competency → weight.")
    if scale_max not in (4, 5):
        raise ToolError("scale_max must be 4 or 5.")
    try:
        w = {str(k): float(v) for k, v in weights.items()}
    except (TypeError, ValueError):
        raise ToolError("weights must be numbers.") from None
    if any(v < 0 for v in w.values()) or sum(w.values()) <= 0:
        raise ToolError("weights must be non-negative and sum to more than 0.")
    tot_w = sum(w.values())
    bar = 2.5 * scale_max / 4
    musts = [str(m) for m in (must_haves or [])]
    unknown_must = [m for m in musts if m not in w]
    if unknown_must:
        raise ToolError(f"must_haves not in weights: {', '.join(unknown_must)}")
    rater_scores: dict[str, list[float]] = defaultdict(list)
    rows = []
    for i, c in enumerate(candidates, 1):
        if not isinstance(c, dict) or not isinstance(c.get("ratings"), dict) or not c["ratings"]:
            raise ToolError(f"candidate #{i} needs 'ratings' as {{interviewer: {{competency: score}}}}.")
        name = str(c.get("name") or f"Candidate {i}")
        per_comp: dict[str, list[float]] = defaultdict(list)
        for rater, scores in c["ratings"].items():
            if not isinstance(scores, dict):
                raise ToolError(f"{name}: ratings for {rater} must be {{competency: score}}.")
            for comp, s in scores.items():
                if comp not in w:
                    raise ToolError(f"{name}/{rater}: competency {comp!r} is not in weights — ratings outside the rubric are not allowed.")
                try:
                    sv = float(s)
                except (TypeError, ValueError):
                    raise ToolError(f"{name}/{rater}/{comp}: score must be a number.") from None
                if not 1 <= sv <= scale_max:
                    raise ToolError(f"{name}/{rater}/{comp}: score {s} outside 1-{scale_max}.")
                per_comp[comp].append(sv)
                rater_scores[str(rater)].append(sv)
        comp_rows, weighted, covered_w = {}, 0.0, 0.0
        disagreements, must_fail, uncovered = [], [], []
        for comp, wt in w.items():
            vals = per_comp.get(comp, [])
            if not vals:
                uncovered.append(comp)
                comp_rows[comp] = {"mean": None, "raters": 0, "spread": None}
                continue
            mean = statistics.mean(vals)
            spread = max(vals) - min(vals)
            comp_rows[comp] = {"mean": round(mean, 2), "raters": len(vals), "spread": spread, "scores": vals}
            weighted += wt * mean
            covered_w += wt
            if spread >= 1.5:
                disagreements.append({"competency": comp, "scores": vals, "spread": spread})
            if comp in musts and mean < bar:
                must_fail.append({"competency": comp, "mean": round(mean, 2), "bar": bar})
        score = round(100 * weighted / (covered_w * scale_max), 1) if covered_w else 0.0
        if must_fail:
            decision = "no hire (must-have below bar)"
        elif score >= 80:
            decision = "strong hire"
        elif score >= 65:
            decision = "hire"
        elif score >= 50:
            decision = "no hire unless a must-have is a 4 and the gap is coachable"
        else:
            decision = "no hire"
        single = [k for k, v in comp_rows.items() if v["raters"] == 1]
        rows.append({"name": name, "weighted_score": score, "decision": decision, "by_competency": comp_rows, "must_have_failures": must_fail, "disagreements": disagreements, "uncovered": uncovered, "single_rater": single, "coverage_pct": pct(covered_w, tot_w)})
    overall_mean = statistics.mean([s for v in rater_scores.values() for s in v]) if rater_scores else 0
    leniency = {r: {"mean": round(statistics.mean(v), 2), "delta_vs_panel": round(statistics.mean(v) - overall_mean, 2), "n": len(v)} for r, v in rater_scores.items()}
    lenient = [r for r, v in leniency.items() if abs(v["delta_vs_panel"]) >= 0.5 and v["n"] >= 3]
    ranked = sorted(rows, key=lambda r: (bool(r["must_have_failures"]), -r["weighted_score"]))
    agenda = []
    for r in rows:
        for f in r["must_have_failures"]:
            agenda.append(f"{r['name']}: must-have '{f['competency']}' averaged {f['mean']} (< {bar}) — no hire unless the panel names contrary evidence")
        for d in r["disagreements"]:
            agenda.append(f"{r['name']}: '{d['competency']}' rated {d['scores']} — each rater states the evidence, then re-rate")
    if lenient:
        agenda.append("rater calibration: " + ", ".join(f"{r} averages {leniency[r]['delta_vs_panel']:+.2f} vs panel" for r in lenient))
    top = ranked[0]
    return {
        "scale_max": scale_max,
        "must_have_bar": bar,
        "candidates": rows,
        "ranking": [r["name"] for r in ranked],
        "interviewer_leniency": leniency,
        "calibration_flags": lenient,
        "debrief_agenda": agenda,
        "verdict": f"{top['name']} leads at {top['weighted_score']}/100 → {top['decision']}. {len(agenda)} debrief item(s)."
        if not top["must_have_failures"] else f"No candidate clears the must-have bar; top weighted score is {top['name']} at {top['weighted_score']}. {len(agenda)} debrief item(s).",
    }


EVIDENCE_RE = re.compile(r"(\"|“|”|\bshe said|\bhe said|\bthey said|\bsaid\b|\bdescribed\b|\bexplained\b|\bwalked (?:me|us) through\b|\bexample\b|\bwhen (?:asked|I asked)\b|\bgave\b|\bmentioned\b|\btold\b|\bshowed\b|\bcited\b|\bquantified\b|\d)", re.I)
OPINION_RE = re.compile(r"\b(i (?:think|feel|believe|liked|loved|didn't like)|seems?|seemed|impress(?:ive|ed)|great|good|bad|smart|sharp|brilliant|weak|strong|solid|amazing|awesome|nice|fine|okay|meh|not sure|unsure|gut|vibe|fit)\b", re.I)
VAGUE = {"great": "what did they do that was great?", "good": "what specifically?", "smart": "what did they say that showed it?", "impressive": "which answer, and why?", "strong": "evidence at which anchor?", "weak": "which answer fell short, and how?", "solid": "evidence?", "seems": "observed or inferred?", "seemed": "observed or inferred?", "not sure": "what evidence would resolve it? (rate 2 with the gap named)", "i think": "state the observation", "i feel": "state the observation", "sharp": "which answer?", "amazing": "which answer?"}


@AGENT.tool
def check_feedback_bias(feedback: str, interviewer: str = "") -> dict:
    """Audit written interview feedback for non-job-related or protected-characteristic remarks, vague opinion vs evidence, and rating-without-example.

    Reports an evidence ratio (sentences with quotes, examples, numbers), flagged terms with
    the reason, and rewrite prompts so the interviewer can fix it before the debrief.

    Args:
        feedback: The interviewer's written feedback text.
        interviewer: Interviewer name (optional; echoed in the report).
    """
    require_text(feedback, "feedback")
    sents = text.sentences(feedback)
    n = len(sents) or 1
    evidence = [s for s in sents if EVIDENCE_RE.search(s)]
    opinion_only = [s for s in sents if OPINION_RE.search(s) and not EVIDENCE_RE.search(s)]
    protected = scan_lexicon(feedback, PROTECTED_PROXIES)
    vague = scan_lexicon(feedback, VAGUE)
    rating_mentions = re.findall(r"\b([1-5])\s*(?:/\s*[45]|out of [45])\b|\b(?:rating|score|rate)\D{0,10}([1-5])\b", feedback, re.I)
    ev_ratio = pct(len(evidence), n)
    issues, fixes = [], []
    score = 100
    if protected:
        issues.append("non-job-related / protected-proxy language: " + ", ".join(f"'{h['term']}'" for h in protected))
        fixes.extend(f"'{h['term']}' — {h['suggestion']}" for h in protected)
        score -= 25 * len(protected)
    if ev_ratio < 60:
        issues.append(f"evidence ratio {ev_ratio}% (aim ≥ 60%) — {len(opinion_only)} opinion-only sentence(s)")
        fixes.append("for each opinion sentence, add what the candidate said or did that produced it")
        score -= 20 if ev_ratio < 40 else 10
    if vague:
        issues.append("vague evaluators: " + ", ".join(f"'{h['term']}'" for h in vague[:6]))
        fixes.extend(f"'{h['term']}' → {h['suggestion']}" for h in vague[:4])
        score -= min(20, 4 * len(vague))
    if rating_mentions and ev_ratio < 40:
        issues.append("rating given with little evidence — a rating must cite the anchor it matched")
        score -= 10
    if len(text.words(feedback)) < 40:
        issues.append("under 40 words — too thin to defend in a debrief")
        score -= 10
    score = max(0, score)
    return {
        "interviewer": interviewer or None,
        "score": score,
        "sentences": len(sents),
        "evidence_sentences": len(evidence),
        "evidence_ratio_pct": ev_ratio,
        "opinion_only_sentences": [s[:200] for s in opinion_only[:6]],
        "protected_or_proxy_terms": protected,
        "vague_terms": vague,
        "issues": issues,
        "fixes": fixes,
        "strike_before_filing": bool(protected),
        "verdict": ("Usable as filed." if score >= 80 and not protected else f"Score {score}/100 — " + ("strike flagged terms; " if protected else "") + "return to interviewer for evidence."),
    }
