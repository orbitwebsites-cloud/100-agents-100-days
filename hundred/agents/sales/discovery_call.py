"""Discovery Call Coach — prepares, scores and debriefs discovery calls against MEDDPICC and top-rep talk metrics."""

from __future__ import annotations

import re
from collections import Counter

from ...core import Agent, ToolError
from ...lib import text
from . import _common as c

AGENT = Agent(
    slug="discovery-call",
    name="Discovery Call Coach",
    category="sales",
    tagline="Run discovery like a top rep: a question plan before the call, a MEDDPICC scorecard and talk-ratio audit after it.",
    description=(
        "Coaches every discovery call end-to-end. Before: a time-boxed agenda and a graded question plan "
        "(open vs closed vs leading). After: analyses the transcript for talk ratio, question count and "
        "quality, monologues and topic coverage, then scores the opportunity on MEDDPICC with evidence and "
        "tells you which gaps block the next stage and exactly what to ask to close them."
    ),
    triggers=[
        "prepare me for a discovery call",
        "what questions should I ask on this sales call",
        "score this deal on MEDDPICC / MEDDIC",
        "analyze my discovery call transcript",
        "did I talk too much on this call",
        "what should I ask to qualify this opportunity",
    ],
    examples=[
        "I have a 30-min discovery call tomorrow with the Head of Finance at a 200-person SaaS company. Build my plan.",
        "Here's the transcript from my discovery call. How did I do, and what did I miss?",
        "Score this opportunity on MEDDPICC — notes attached — and tell me if it's real.",
        "Rewrite these questions so they're open-ended and not leading.",
    ],
    connectors=["Gong", "Chorus", "Salesforce", "HubSpot", "Google Calendar", "Notion"],
    playbook="""
    ## Standard
    You are a discovery coach in the mould of the best enterprise sales trainers: the call
    is a diagnosis, not a pitch. Excellent discovery leaves the prospect having said, in
    their own words, what the problem costs them, who decides, and what happens if they
    do nothing. The one metric: **MEDDPICC coverage after the call** (how many of the 8
    elements are confirmed with prospect evidence, not rep assumption). Secondary: the
    prospect talked more than the rep, and the rep asked ≥ 10 questions, mostly open.

    ## Intake
    Determine the mode from the request: **prep** (call is upcoming), **debrief** (a
    transcript or notes exist), or **score** (they want the MEDDPICC verdict). For prep
    you need persona + company + what's already known; for debrief you need the transcript
    and which speaker is the rep. Ask at most 3 questions and only if truly blocked;
    otherwise assume (e.g. rep = first speaker) and say so.

    ## Procedure
    **Prep mode**
    1. Call `discovery_call__plan_call_agenda` with the duration and call type. It
       returns minute-by-minute time boxes (agenda-set, situation, problem, impact,
       decision, next step) — discovery calls that skip the upfront agenda and the
       explicit next-step block lose 5-10 minutes to small talk and end without a
       commitment.
    2. Draft 12-15 questions covering the SPIN ladder (situation → problem →
       implication → need-payoff) mapped to MEDDPICC gaps. Call
       `discovery_call__grade_questions` with them. Keep ≥ 70% open, zero leading, zero
       double-barrelled. Rewrite anything it flags and re-grade.
    3. Prepare 2-3 "peer stories" (how a similar customer described the problem) to use
       when the prospect goes quiet — never a feature pitch.

    **Debrief mode**
    4. Call `discovery_call__analyze_transcript` with the transcript and the rep's name.
       Read: talk ratio (target rep ≤ 45%), questions asked (target ≥ 10 in 30 min,
       ≥ 60% open), longest rep monologue (target ≤ 60 seconds ≈ 150 words), topic
       coverage (pain, impact, timeline, budget, decision process, competition, current
       solution), and fillers.
    5. Extract evidence for each MEDDPICC letter — a quote or a paraphrase of what the
       prospect said. Rate each 0-3 (0 unknown, 1 rep assumption, 2 prospect said it,
       3 prospect said it and it's verified/quantified). Call
       `discovery_call__meddpicc_scorecard` with those ratings and the current stage. It
       computes the weighted score, the stage gate, and the next question per gap.
    6. Write the debrief: what went well (specific), the 3 biggest misses, the exact
       questions for the next call, and the stage recommendation. Never inflate the
       score to be kind.

    ## Frameworks
    - **MEDDPICC:** Metrics · Economic buyer · Decision criteria · Decision process ·
      Paper process · Identify pain · Champion · Competition. Weights: Pain, Champion,
      Economic buyer and Metrics are the heavy four (they predict the win); Paper process
      matters late. Gate rules: no stage 3 (proposal) without Pain ≥ 2 and Champion ≥ 2;
      no commit without Economic buyer ≥ 2, Decision process ≥ 2 and Paper process ≥ 1.
    - **SPIN:** Situation (limit to 2-3 — they bore buyers), Problem, Implication
      (the cost of the problem — this is where value is created), Need-payoff (let them
      say why solving it matters).
    - **Talk metrics from call-recording research (Gong, Chorus):** top-performing reps
      talk ~43-46% of a discovery call; 11-14 questions per call correlates with the best
      win rates; the longest customer story should be ≥ 2 minutes uninterrupted.
    - **Question quality:** open ("How are you handling X today?") > closed ("Do you
      have X?") > leading ("You'd agree X is a problem, right?"). Never stack two
      questions in one breath — the prospect answers the easier one.

    ## Output format
    ```
    # Discovery <prep | debrief> — <company> · <date>

    ## Snapshot
    Talk ratio rep/prospect: <x/y>% · Questions: <n> (<open%> open) · Longest rep monologue: <n> words
    Topics covered: <list> · Missed: <list>

    ## MEDDPICC scorecard (<score>/24 · <pct>%)
    | Element | Score | Evidence (quote/paraphrase) | Gap → next question |
    |---|---|---|---|

    ## Stage recommendation
    <stay in discovery | advance to <stage> | disqualify> — because <gate rule>

    ## Top 3 fixes for next call
    1. …

    ## Question plan for next call
    - <open question mapped to element>
    ```

    ## Anti-patterns
    - Pitching in discovery. If the rep's longest monologue is a demo, say so bluntly.
    - Scoring MEDDPICC on what the rep *believes* rather than what the prospect *said*.
    - Situation questions that a 5-minute LinkedIn read would answer ("how many employees?").
    - "Does that make sense?" / "Sound good?" as the only questions — they are not discovery.
    - Ending without a written next step with a date and the prospect's name on it.
    - Cheerleading debriefs. The rep pays for honest coaching, not a participation medal.
    """,
)

MEDDPICC = {
    "metrics": {"label": "Metrics", "weight": 1.5, "question": "What number would need to move for this to be a clear win — and by how much?"},
    "economic_buyer": {"label": "Economic buyer", "weight": 1.5, "question": "Who signs off on spend of this size, and have they seen the problem quantified?"},
    "decision_criteria": {"label": "Decision criteria", "weight": 1.0, "question": "When you compare options, what are the 3 things you'll judge them on?"},
    "decision_process": {"label": "Decision process", "weight": 1.0, "question": "Walk me through the steps from 'we like this' to 'it's live' — who's involved at each?"},
    "paper_process": {"label": "Paper process", "weight": 0.75, "question": "What does legal/procurement need, and how long did the last vendor take to get through it?"},
    "identify_pain": {"label": "Identify pain", "weight": 1.5, "question": "What's the cost of leaving this as it is for another two quarters?"},
    "champion": {"label": "Champion", "weight": 1.5, "question": "Who internally loses the most if this doesn't happen — would they present this to their boss?"},
    "competition": {"label": "Competition", "weight": 0.75, "question": "What else are you considering, including doing nothing or building it in-house?"},
}
STAGE_GATES = {
    "discovery": {},
    "evaluation": {"identify_pain": 2, "champion": 1},
    "proposal": {"identify_pain": 2, "champion": 2, "metrics": 2},
    "negotiation": {"identify_pain": 2, "champion": 2, "economic_buyer": 2, "decision_process": 2},
    "commit": {"identify_pain": 2, "champion": 2, "economic_buyer": 2, "decision_process": 2, "paper_process": 1, "metrics": 2},
}


@AGENT.tool
def meddpicc_scorecard(ratings: dict, target_stage: str = "proposal") -> dict:
    """Compute the weighted MEDDPICC score, the stage-gate verdict and the next question per gap.

    Call after extracting prospect evidence for each element. Ratings are 0-3 per element:
    0 unknown, 1 rep assumption only, 2 prospect stated it, 3 stated and verified/quantified.

    Args:
        ratings: Dict keyed by element (metrics, economic_buyer, decision_criteria, decision_process, paper_process, identify_pain, champion, competition), each either an int 0-3 or {"score": int, "evidence": str}.
        target_stage: Stage you want to move to: discovery, evaluation, proposal, negotiation or commit.
    """
    if not isinstance(ratings, dict) or not ratings:
        raise ToolError("ratings must be a non-empty dict keyed by MEDDPICC element.")
    stage = target_stage.strip().lower()
    if stage not in STAGE_GATES:
        raise ToolError(f"target_stage must be one of {', '.join(STAGE_GATES)}.")
    aliases = {"m": "metrics", "e": "economic_buyer", "dc": "decision_criteria", "dp": "decision_process", "p": "paper_process", "i": "identify_pain", "pain": "identify_pain", "c": "champion", "comp": "competition", "eb": "economic_buyer"}
    norm: dict[str, dict] = {}
    for k, v in ratings.items():
        key = aliases.get(str(k).strip().lower(), str(k).strip().lower().replace(" ", "_"))
        if key not in MEDDPICC:
            raise ToolError(f"Unknown element {k!r}. Use: {', '.join(MEDDPICC)}.")
        if isinstance(v, dict):
            score, evidence = v.get("score", 0), str(v.get("evidence", "")).strip()
        else:
            score, evidence = v, ""
        try:
            score = int(score)
        except (TypeError, ValueError):
            raise ToolError(f"{key}: score must be an integer 0-3.") from None
        if not 0 <= score <= 3:
            raise ToolError(f"{key}: score must be 0-3, got {score}.")
        if score >= 2 and not evidence:
            evidence = "(no evidence given — downgrade to 1 unless you can quote the prospect)"
        norm[key] = {"score": score, "evidence": evidence}
    rows, total, max_total, gaps, blockers = [], 0.0, 0.0, [], []
    for key, meta in MEDDPICC.items():
        r = norm.get(key, {"score": 0, "evidence": ""})
        total += r["score"] * meta["weight"]
        max_total += 3 * meta["weight"]
        required = STAGE_GATES[stage].get(key)
        blocked = required is not None and r["score"] < required
        if blocked:
            blockers.append(f"{meta['label']} is {r['score']}, needs ≥ {required} for {stage}")
        if r["score"] < 2:
            gaps.append({"element": meta["label"], "score": r["score"], "next_question": meta["question"]})
        rows.append({"element": meta["label"], "key": key, "score": r["score"], "weight": meta["weight"], "evidence": r["evidence"], "gate_required": required, "blocks_stage": blocked})
    pct_score = round(100 * total / max_total, 1)
    raw = sum(r["score"] for r in rows)
    health = "strong" if pct_score >= 75 else "developing" if pct_score >= 50 else "weak" if pct_score >= 25 else "unqualified"
    heavy = ["identify_pain", "champion", "economic_buyer", "metrics"]
    heavy_known = sum(1 for k in heavy if norm.get(k, {}).get("score", 0) >= 2)
    return {
        "elements": rows,
        "raw_score": raw,
        "raw_max": 24,
        "weighted_pct": pct_score,
        "health": health,
        "heavy_four_confirmed": f"{heavy_known}/4",
        "target_stage": stage,
        "gate_passed": not blockers,
        "blockers": blockers,
        "gaps": gaps,
        "verdict": (f"{raw}/24 raw, {pct_score}% weighted — {health}. " + ("Gate to " + stage + " passed." if not blockers else f"Do NOT advance to {stage}: " + "; ".join(blockers) + ".")),
    }


TOPICS = {
    "pain": r"\b(problem|pain|struggl|frustrat|broken|manual|slow|error|bottleneck|headache|challenge|issue|waste|churn|miss(?:ed|ing))\w*",
    "impact": r"\b(cost(?:s|ing)?|lose|losing|lost|hours|per (?:week|month)|revenue|margin|penalt|risk|delay|impact|\$\s?\d|\d+\s?%)\w*",
    "timeline": r"\b(deadline|by (?:q[1-4]|end of|january|february|march|april|may|june|july|august|september|october|november|december)|this quarter|next quarter|timeline|when do you|go[- ]live|renewal|urgen)\w*",
    "budget": r"\b(budget|spend|price|pricing|cost of|invest|approve[ds]?|funding|allocated|per seat|per user)\w*",
    "decision_process": r"\b(sign[- ]?off|decision|approv|procurement|legal|security review|stakeholder|committee|who else|evaluat|criteria)\w*",
    "competition": r"\b(alternative|competitor|other vendor|compar|in[- ]house|build it|also looking|evaluating|incumbent|currently use|switch)\w*",
    "current_solution": r"\b(today|currently|right now|spreadsheet|excel|manual|existing|current (?:tool|process|system|vendor)|we use)\w*",
    "next_step": r"\b(next step|follow[- ]up|send (?:you|over)|schedule|calendar|invite|proposal|pilot|trial|demo)\w*",
}
_TOPIC_RES = {k: re.compile(v, re.I) for k, v in TOPICS.items()}


@AGENT.tool
def analyze_transcript(transcript: str, rep_name: str = "", call_minutes: int = 0) -> dict:
    """Measure a discovery call: talk ratio, question count and quality, longest monologue, topic coverage, fillers.

    Call first in debrief mode. Transcript lines look like "Name: text" (timestamps OK).
    If rep_name is blank the first speaker is assumed to be the rep.

    Args:
        transcript: Raw call transcript text.
        rep_name: The seller's name as it appears in the transcript (optional).
        call_minutes: Actual call length in minutes if known; otherwise estimated at 150 words/min.
    """
    turns = c.parse_transcript(transcript)
    speakers = [s for s, _ in turns if s]
    if not speakers:
        raise ToolError("No 'Name: text' lines found — label each line with the speaker.")
    order = list(dict.fromkeys(speakers))
    rep = c.match_speaker(rep_name, order) if rep_name else None
    if rep_name and rep is None:
        raise ToolError(f"rep_name {rep_name!r} not found among speakers {order}.")
    rep = rep or order[0]
    words_by: Counter[str] = Counter()
    rep_questions: list[str] = []
    prospect_questions = 0
    longest_rep = ("", 0)
    longest_prospect = ("", 0)
    rep_fillers: Counter[str] = Counter()
    prospect_text_parts: list[str] = []
    rep_text_parts: list[str] = []
    for spk, said in turns:
        if not spk:
            continue
        n = len(text.words(said))
        words_by[spk] += n
        qs = c.questions_in(said)
        if spk == rep:
            rep_questions.extend(qs)
            rep_fillers.update(c.count_fillers(said))
            rep_text_parts.append(said)
            if n > longest_rep[1]:
                longest_rep = (said[:160], n)
        else:
            prospect_questions += len(qs)
            prospect_text_parts.append(said)
            if n > longest_prospect[1]:
                longest_prospect = (said[:160], n)
    total = sum(words_by.values()) or 1
    minutes = call_minutes if call_minutes > 0 else max(1, round(total / 150))
    q_types = Counter(c.classify_question(q) for q in rep_questions)
    n_q = len(rep_questions)
    open_pct = c.pct(q_types["open"], n_q) if n_q else 0.0
    prospect_text = " ".join(prospect_text_parts)
    rep_text = " ".join(rep_text_parts)
    coverage = {}
    for topic, rx in _TOPIC_RES.items():
        p_hits = len(rx.findall(prospect_text))
        r_hits = len(rx.findall(rep_text))
        # next-step counts when either side raises it; every other topic must come from the prospect's mouth
        coverage[topic] = {"prospect_mentions": p_hits, "rep_mentions": r_hits, "covered": p_hits > 0 or (topic == "next_step" and r_hits > 0)}
    covered = [t for t, v in coverage.items() if v["covered"]]
    missed = [t for t in TOPICS if t not in covered]
    rep_share = c.pct(words_by[rep], total)
    flags = []
    if rep_share > 55:
        flags.append(f"rep talked {rep_share}% — target ≤ 45%; you pitched, they didn't discover")
    elif rep_share > 45:
        flags.append(f"rep talked {rep_share}% — slightly high; target ≤ 45%")
    q_per_30 = round(n_q * 30 / minutes, 1)
    if q_per_30 < 10:
        flags.append(f"{n_q} questions in ~{minutes} min ({q_per_30}/30 min) — target 11-14 per 30 min")
    if n_q and open_pct < 60:
        flags.append(f"only {open_pct}% open questions — target ≥ 60%")
    if q_types["leading"]:
        flags.append(f"{q_types['leading']} leading question(s) — they produce polite agreement, not truth")
    if q_types["multi"]:
        flags.append(f"{q_types['multi']} double-barrelled question(s) — ask one at a time")
    if longest_rep[1] > 150:
        flags.append(f"longest rep monologue {longest_rep[1]} words (~{round(longest_rep[1] / 150 * 60)}s) — cap at ~60s")
    if longest_prospect[1] < 80:
        flags.append(f"prospect's longest answer was only {longest_prospect[1]} words — you never got them telling the story")
    filler_total = sum(rep_fillers.values())
    fillers_per_min = round(filler_total / minutes, 1)
    if fillers_per_min > 3:
        flags.append(f"{fillers_per_min} filler words/min — rehearse the transitions")
    if "next_step" not in covered and coverage["next_step"]["rep_mentions"] == 0:
        flags.append("no next step discussed — the call ended without a commitment")
    if "impact" not in covered:
        flags.append("impact/cost never quantified by the prospect — no value was established")
    return {
        "rep": rep,
        "speakers": order,
        "talk_share_pct": {s: c.pct(w, total) for s, w in words_by.most_common()},
        "rep_talk_pct": rep_share,
        "estimated_minutes": minutes,
        "total_words": total,
        "rep_questions": n_q,
        "rep_questions_per_30min": q_per_30,
        "question_types": dict(q_types),
        "open_question_pct": open_pct,
        "prospect_questions": prospect_questions,
        "longest_rep_monologue": {"words": longest_rep[1], "starts": longest_rep[0]},
        "longest_prospect_answer": {"words": longest_prospect[1], "starts": longest_prospect[0]},
        "rep_fillers": dict(rep_fillers.most_common(5)),
        "fillers_per_minute": fillers_per_min,
        "topic_coverage": coverage,
        "topics_covered": covered,
        "topics_missed": missed,
        "flags": flags,
        "verdict": f"Rep {rep_share}% talk, {n_q} questions ({open_pct}% open), {len(covered)}/{len(TOPICS)} topics covered. " + (flags[0] if flags else "Solid discovery mechanics."),
    }


@AGENT.tool
def plan_call_agenda(duration_minutes: int = 30, call_type: str = "discovery", attendee_count: int = 2) -> dict:
    """Build a minute-by-minute time-boxed agenda for a discovery, demo-discovery or qualification call.

    Call in prep mode. Blocks scale with duration; multi-stakeholder calls get more
    time for role/decision-process questions.

    Args:
        duration_minutes: Scheduled call length, 15-90 minutes.
        call_type: discovery (default), demo_discovery (discovery then short demo), or qualification (first call, 15-20 min).
        attendee_count: Number of people on the prospect side (1-10).
    """
    if not 15 <= duration_minutes <= 90:
        raise ToolError("duration_minutes must be 15-90.")
    ct = call_type.strip().lower()
    if ct not in ("discovery", "demo_discovery", "qualification"):
        raise ToolError("call_type must be discovery, demo_discovery or qualification.")
    if not 1 <= attendee_count <= 10:
        raise ToolError("attendee_count must be 1-10.")
    # weights of each block; demo_discovery inserts a demo block; multi-stakeholder adds decision time
    blocks = [
        ("Open + agenda-set (PPP: purpose, plan, permission)", 0.10, "Confirm time, state the plan, ask what they want out of it."),
        ("Situation (2-3 questions max)", 0.12, "Current tool/process, team, what triggered the call."),
        ("Problem", 0.20, "Where it breaks, how often, who feels it."),
        ("Implication / impact", 0.20, "Cost in hours, money, risk. Get a number."),
        ("Decision & process", 0.13 + (0.05 if attendee_count >= 3 else 0), "Who decides, criteria, timeline, paper process."),
        ("Need-payoff + fit summary", 0.10, "Let them say why solving it matters; summarise back in their words."),
        ("Next step (with date, named owner)", 0.15 - (0.05 if attendee_count >= 3 else 0), "Propose the specific next meeting; confirm attendees."),
    ]
    if ct == "demo_discovery":
        blocks.insert(5, ("Targeted demo (only what maps to stated pain)", 0.25, "Show 2-3 things tied to their words; no tour."))
    if ct == "qualification":
        blocks = [
            ("Open + agenda-set", 0.15, "State purpose: see if it's worth both our time."),
            ("Trigger + problem", 0.35, "Why now, what's broken."),
            ("Impact + timeline", 0.25, "Cost, deadline."),
            ("Fit check + next step", 0.25, "Decide: discovery call with the right people, or not."),
        ]
    total_w = sum(w for _, w, _ in blocks)
    agenda, t = [], 0
    remaining = duration_minutes
    for i, (name, w, note) in enumerate(blocks):
        mins = max(2, round(duration_minutes * w / total_w)) if i < len(blocks) - 1 else remaining
        mins = min(mins, remaining)
        agenda.append({"block": name, "start_min": t, "minutes": mins, "end_min": t + mins, "coach_note": note})
        t += mins
        remaining -= mins
    rep_talk_budget = round(duration_minutes * 0.43)
    return {
        "call_type": ct,
        "duration_minutes": duration_minutes,
        "agenda": agenda,
        "target_questions": max(6, round(duration_minutes / 30 * 12)),
        "rep_talk_budget_minutes": rep_talk_budget,
        "hard_stop_rule": f"At minute {duration_minutes - agenda[-1]['minutes']} stop discovering and lock the next step, even mid-topic.",
        "verdict": f"{len(agenda)} blocks; aim for ~{max(6, round(duration_minutes / 30 * 12))} questions and ≤ {rep_talk_budget} min of rep talk time.",
    }


REWRITES = [
    (re.compile(r"^(do|does|did) (you|your team|your company) (have|use|run|struggle with|face)\s+(.*)\?$", re.I), r"How are you handling \4 today?"),
    (re.compile(r"^(is|are) (.*) (a problem|an issue|a priority|important)( for you)?\?$", re.I), r"Where does \2 sit on your priority list this quarter, and why?"),
    (re.compile(r"^(would|wouldn't|don't|doesn't) (.*)\?$", re.I), r"What would have to be true for \2?"),
    (re.compile(r"^(can|could) (you|we) (.*)\?$", re.I), r"What would it take to \3?"),
    (re.compile(r"^(have you) (.*)\?$", re.I), r"What has your experience been with \2?"),
]


@AGENT.tool
def grade_questions(questions: list[str]) -> dict:
    """Grade discovery questions: open / closed / leading / double-barrelled, with rewrites for weak ones.

    Call on your drafted question plan (or questions pulled from a transcript). Returns
    per-question type, an overall quality score, and open-ended rewrites.

    Args:
        questions: The list of questions to grade (max 60).
    """
    if not questions:
        raise ToolError("Give at least one question.")
    if len(questions) > 60:
        raise ToolError("Max 60 questions per call.")
    graded, counts = [], Counter()
    for q in questions:
        q = str(q).strip()
        if not q:
            continue
        if len(q) > 500:
            raise ToolError("A question over 500 chars is a speech, not a question.")
        qq = q if q.endswith("?") else q + "?"
        kind = c.classify_question(qq)
        counts[kind] += 1
        issue, rewrite = None, None
        if kind == "closed":
            issue = "closed — invites yes/no"
            for rx, rep in REWRITES:
                if rx.match(qq):
                    rewrite = rx.sub(rep, qq)
                    break
            rewrite = rewrite or "How … / What … / Walk me through …"
        elif kind == "leading":
            issue = "leading — you supplied the answer"
            rewrite = "Strip the 'right?/wouldn't you agree' and ask what they actually think."
        elif kind == "multi":
            issue = "double-barrelled — they'll answer the easier half"
            rewrite = "Split into two questions; ask the harder one first."
        n_words = len(text.words(qq))
        if n_words > 25:
            issue = (issue + "; " if issue else "") + f"{n_words} words — trim to ≤ 20"
        situational = bool(re.search(r"\b(how many (employees|people|users)|what (tools?|crm|software) do you use|where are you (based|located))\b", qq, re.I))
        if situational:
            issue = (issue + "; " if issue else "") + "situation question you could research — spend the airtime on problem/impact"
        graded.append({"question": q, "type": kind, "words": n_words, "issue": issue, "rewrite": rewrite})
    n = len(graded)
    if not n:
        raise ToolError("All questions were blank.")
    open_pct = c.pct(counts["open"], n)
    score = round(max(0, min(100, 100 * counts["open"] / n - 15 * counts["leading"] - 10 * counts["multi"] - 5 * sum(1 for g in graded if "situation" in (g["issue"] or "")))))
    return {
        "questions": graded,
        "counts": dict(counts),
        "open_pct": open_pct,
        "score": score,
        "meets_bar": open_pct >= 70 and counts["leading"] == 0 and counts["multi"] == 0,
        "verdict": f"{n} questions, {open_pct}% open, {counts['leading']} leading, {counts['multi']} double-barrelled — score {score}/100.",
    }
