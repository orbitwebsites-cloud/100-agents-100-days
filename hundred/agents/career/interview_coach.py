"""Interview Coach — builds a STAR story bank, drills role-specific questions, and schedules prep to the interview date."""

from __future__ import annotations

import math
import re
from datetime import date, timedelta
from typing import Literal

from ...core import Agent, ToolError
from ...lib import dates, text
from ._common import pct, require_text

AGENT = Agent(
    slug="interview-coach",
    name="Interview Coach",
    category="career",
    tagline="Turn your experience into 6-8 tight STAR stories, drill the questions this role actually asks, and prep on a dated plan.",
    description=(
        "Coaches you like a top interview coach: builds a story bank that covers every competency the "
        "role tests, checks each STAR story for structure, ownership ('I' vs 'we'), a quantified result and "
        "spoken length, drills a question bank organised by competency and role family with what a strong "
        "answer must contain, lints spoken answers for fillers and hedges, and lays out a day-by-day prep "
        "schedule anchored to your interview date. Behavioral, hiring-manager and panel rounds covered."
    ),
    triggers=[
        "help me prepare for an interview",
        "practice / mock interview questions for this role",
        "is my STAR story good enough",
        "what questions will they ask a product manager / engineer / sales rep",
        "make a prep plan for my interview next week",
        "how do I answer 'tell me about a time you failed'",
    ],
    examples=[
        "I have a final-round PM interview at Notion on Thursday. Here's the JD and my resume — get me ready.",
        "Here's my answer to 'tell me about a conflict with a coworker' — critique it.",
        "Give me 10 behavioral questions for an engineering manager role with what a great answer includes.",
    ],
    connectors=["Google Calendar", "Notion", "Google Docs"],
    playbook="""
    ## Standard
    You are an interview coach whose clients convert final rounds at well above the norm. The
    standard: the candidate walks in with 6-8 rehearsed stories that cover every competency
    the loop will test, each 90-120 seconds spoken, each ending in a number, each told in the
    first person singular. The metric that matters: no question in the loop lands without a
    prepared story behind it.

    ## Intake
    Ask at most three things, only if missing: (1) the role/JD and company, (2) interview date
    and format (phone screen, hiring manager, panel, case/technical), (3) 3-5 raw experiences
    they're proud of. If the user pastes a JD and a resume, you have enough — infer the
    competencies from the JD and start. State what you assumed.

    ## Procedure
    1. **Map the competencies.** From the JD, list the 5-7 competencies the loop will probe
       (e.g. ownership, ambiguity, influence without authority, conflict, failure/learning,
       execution, customer focus, plus 1-2 role-specific). Call
       `interview_coach__question_bank` with the role family, level and those competencies to
       get the question set and the "strong answer contains" criteria for each. Show the user
       the questions grouped by competency.
    2. **Build the story bank.** Take the user's raw experiences and draft 6-8 STAR stories,
       each tagged to 2+ competencies (one story should answer several questions). Every story
       needs: a one-line Situation, a Task with a stake, Actions in "I" voice with the decision
       points, and a Result with a number plus one sentence of reflection.
    3. **Check every story.** Call `interview_coach__check_star_story` on each. Fix anything
       it flags: missing component, Result under 15% of the words, Action under 40%, "we"
       outnumbering "I", no number, spoken length outside 75-150 seconds. A story that fails
       twice is the wrong story — pick another experience.
    4. **Drill delivery.** When the user pastes a spoken/typed answer, call
       `interview_coach__lint_answer`. Fillers, hedges ("I think", "kind of"), run-on
       sentences and answers over 2 minutes are what interviewers remember. Give the
       corrected version, not just the flags.
    5. **Schedule the prep.** Call `interview_coach__plan_prep_schedule` with the interview
       date and hours available. Deliver the day-by-day plan. Rule: the day before is light
       review + logistics only, never new material.
    6. **Prep the reverse questions.** Give 3 questions to ask the interviewer that only
       someone who read about this company could ask (team's biggest bet this half, what the
       last person in the role struggled with, how success is measured at 6 months).
    7. **Self-check:** each competency has ≥ 1 story; no story is used for more than 3
       questions; every Result has a number; total prep hours fit the schedule.

    ## Frameworks
    - **STAR-R:** Situation (10-15% of words), Task (10-15%), Action (45-55%), Result (15-20%)
      + Reflection (one sentence: what you'd do differently or what you now do by default).
    - **Ownership test:** count "I" vs "we" in the Action. "I" should win; "we" is fine for
      Situation and Result. Interviewers are grading you, not your team.
    - **The 90-second rule:** at ~150 words per minute, 225-300 words. Under 60 seconds feels
      thin; over 2:30 loses the panel. Deliver the headline result first when asked a
      follow-up ("Result was X; here's how").
    - **Failure questions:** real failure, your fault, concrete cost, concrete change since.
      "My weakness is perfectionism" is an automatic downgrade.
    - **Amazon-style Leadership Principle loops and Google's "Googleyness" rounds** both score
      on structured evidence; the bank's "strong answer contains" criteria mirror those rubrics.
    - **Salary questions in the loop:** deflect to range, do not anchor — "I'm focused on fit;
      what's the band for the role?" (Hand off to a negotiation playbook after the offer.)

    ## Output format
    ```
    ## Competency map
    | Competency | Likely questions | Story |
    |---|---|---|

    ## Story bank
    ### Story 1 — <title> (covers: ownership, ambiguity) · ~NN sec · score NN
    **S:** … **T:** … **A:** I … **R:** … (<number>) **Reflection:** …

    ## Delivery notes
    - <fix from lint_answer>

    ## Prep schedule
    | Date | Focus | Hours | Done when |
    |---|---|---|---|

    ## Questions to ask them
    1. …
    ```

    ## Anti-patterns
    - Stories without a number in the Result. "It went well" is not a result.
    - "We" stories: the interviewer cannot tell what you did.
    - Memorised scripts: rehearse the beats, not the sentences. Coach bullet cues, not paragraphs.
    - One mega-story for every question. Six to eight distinct stories, mapped.
    - Spending the day before learning new material. Sleep beats cramming.
    - Answering the question you wished they asked. Restate the question in one clause, then STAR.
    """,
)

S_CUES = re.compile(r"\b(situation|context|background|at the time|when i was|while (?:i was )?at|in my (?:previous|last|role))\b", re.I)
T_CUES = re.compile(r"\b(task|(?:my|our) (?:job|role|goal|responsibility) was|(?:i|we) (?:was asked|were asked|needed|had) to|the (?:goal|challenge|problem|objective) was|responsible for)\b", re.I)
# Action cues accept "I", "we" and "the team" as the actor: a "we" Action is still the Action —
# it is exactly what the ownership check below needs to see and flag.
_ACTION_VERBS = (
    r"decided|built|rebuilt|led|wrote|rewrote|proposed|ran|set up|created|organi[sz]ed|negotiated|convinced|designed|redesigned|"
    r"implemented|analy[sz]ed|prioriti[sz]ed|reached out|took|started|drafted|pushed|owned|chose|mapped|called|scheduled|cut|"
    r"changed|introduced|pulled|looked|found|tested|launched|interviewed|reviewed|shipped|removed|pitched|presented|met|asked|"
    r"dug|identified|sized|modell?ed|hired|coached|simplified|aligned|escalated|documented|measured|dropped|split|moved|replaced"
)
A_CUES = re.compile(r"\b((?:i|we|the team) (?:then |also |quickly |first )?(?:" + _ACTION_VERBS + r")|so (?:i|we)|first,? (?:i|we)|then (?:i|we)|next,? (?:i|we)|my approach)\b", re.I)
R_CUES = re.compile(r"\b(result|as a result|outcome|in the end|ultimately|which (?:led|resulted)|this (?:led|resulted|meant)|we (?:shipped|hit|reached|delivered|launched|grew|cut|saved)|increased|decreased|reduced|improved|grew|saved|delivered|launched|hit)\b", re.I)
REFLECT_CUES = re.compile(r"\b(i learned|lesson|looking back|in hindsight|what i(?:'d| would) do differently|since then|now i (?:always|never)|takeaway)\b", re.I)
NUM_RE = re.compile(r"(\d+(?:\.\d+)?\s?(?:%|percent|x\b|k\b|m\b|million|thousand|hours?|days?|weeks?|months?|people|engineers|customers|users|accounts|deals|tickets)|[$€£]\s?\d|\b\d{2,}\b|\b(?:doubled|tripled|halved)\b)", re.I)
FILLERS = {"um": "delete", "uh": "delete", "like": "delete when not a comparison", "you know": "delete", "basically": "delete", "actually": "delete", "literally": "delete", "so yeah": "delete", "kind of": "delete or commit", "sort of": "delete or commit", "i guess": "delete — state it", "i think": "delete — state it", "i feel like": "delete — state it", "honestly": "delete", "to be honest": "delete", "obviously": "delete", "just": "delete", "really": "delete", "very": "delete", "stuff": "name it", "things": "name them", "etc": "name the last item instead", "whatever": "delete"}
WE_RE = re.compile(r"\b(we|our|us|the team)\b", re.I)
I_RE = re.compile(r"\b(I|I'd|I've|I'm|my|me)\b")
WPM = 150


def _segment(story: str) -> dict[str, list[str]]:
    """Assign each sentence to S/T/A/R by cues; unlabelled sentences inherit the previous label."""
    sents = text.sentences(story)
    labels: list[str] = []
    order = ["S", "T", "A", "R"]
    current = "S"
    for i, s in enumerate(sents):
        found = []
        if R_CUES.search(s) and (NUM_RE.search(s) or re.search(r"\b(result|outcome|as a result|in the end|ultimately)\b", s, re.I)):
            found.append("R")
        if A_CUES.search(s):
            found.append("A")
        if T_CUES.search(s):
            found.append("T")
        if S_CUES.search(s) or i == 0:
            found.append("S")
        if found:
            # Only move forward through S→T→A→R; a later cue keeps the story monotone.
            candidates = [f for f in found if order.index(f) >= order.index(current)]
            nxt = min(candidates, key=order.index) if candidates else current
            # An R cue late in the story wins even if an A cue co-occurs.
            if "R" in found and i >= len(sents) * 0.6:
                nxt = "R"
            current = nxt
        labels.append(current)
    out: dict[str, list[str]] = {"S": [], "T": [], "A": [], "R": []}
    for s, lab in zip(sents, labels):
        out[lab].append(s)
    return out


@AGENT.tool
def check_star_story(story: str, target_seconds: int = 100) -> dict:
    """Check a STAR story for structure balance, ownership ('I' vs 'we'), a quantified result, reflection and spoken length.

    Splits the story into Situation/Task/Action/Result by cue phrases, reports each part's word
    share against the ideal (S 10-15%, T 10-15%, A 45-55%, R 15-20%), and scores it 0-100.

    Args:
        story: The full story as the candidate would say it.
        target_seconds: Intended spoken length in seconds (default 100; 90-120 is the sweet spot).
    """
    require_text(story, "story", max_chars=20_000)
    if not 30 <= target_seconds <= 300:
        raise ToolError("target_seconds must be between 30 and 300.")
    parts = _segment(story)
    total = len(text.words(story)) or 1
    shares = {k: pct(len(text.words(" ".join(v))), total) for k, v in parts.items()}
    ideal = {"S": (8, 20), "T": (5, 20), "A": (40, 60), "R": (12, 35)}
    seconds = round(total / WPM * 60)
    action_text = " ".join(parts["A"])
    i_count, we_count = len(I_RE.findall(action_text)), len(WE_RE.findall(action_text))
    result_text = " ".join(parts["R"])
    quantified = bool(NUM_RE.search(result_text))
    reflection = bool(REFLECT_CUES.search(story))
    issues, fixes = [], []
    score = 100
    for k, (lo, hi) in ideal.items():
        name = {"S": "Situation", "T": "Task", "A": "Action", "R": "Result"}[k]
        if not parts[k]:
            issues.append(f"no {name} detected")
            fixes.append({"S": "open with one sentence of context: where, when, stakes", "T": "state what YOU were asked to do and why it mattered", "A": "narrate 3-5 decisions in 'I' voice", "R": "end with the outcome and a number"}[k])
            score -= 20
        elif shares[k] < lo:
            issues.append(f"{name} is thin ({shares[k]}% of words; aim {lo}-{hi}%)")
            score -= 8
        elif shares[k] > hi:
            issues.append(f"{name} is bloated ({shares[k]}% of words; aim {lo}-{hi}%)")
            score -= 8
    i_total, we_total = len(I_RE.findall(story)), len(WE_RE.findall(story))
    if parts["A"] and we_count > i_count:
        issues.append(f"Action uses 'we' {we_count}× vs 'I' {i_count}× — the interviewer can't see your part")
        fixes.append("rewrite the Action in first person singular: 'I decided…', 'I convinced…'")
        score -= 15
    elif we_total > i_total and we_total >= 3:
        issues.append(f"story uses 'we/our/the team' {we_total}× vs 'I/my' {i_total}× — the interviewer can't see your part")
        fixes.append("rewrite the Action in first person singular: 'I decided…', 'I convinced…'")
        score -= 15
    if not quantified:
        issues.append("Result has no number")
        fixes.append("add %, $, time, volume, or a before/after comparison to the Result")
        score -= 15
    if not reflection:
        issues.append("no reflection line")
        fixes.append("close with one sentence: what you learned or now do by default")
        score -= 5
    if seconds < 60:
        issues.append(f"~{seconds}s spoken — under a minute feels thin")
        score -= 8
    elif seconds > 150:
        issues.append(f"~{seconds}s spoken — over 2.5 minutes loses the panel")
        fixes.append(f"cut ~{total - int(target_seconds * WPM / 60)} words, mostly from Situation")
        score -= 10
    score = max(0, score)
    return {
        "score": score,
        "words": total,
        "spoken_seconds": seconds,
        "target_seconds": target_seconds,
        "word_share_pct": shares,
        "ideal_share_pct": {k: f"{lo}-{hi}" for k, (lo, hi) in ideal.items()},
        "segments": {k: " ".join(v)[:600] for k, v in parts.items()},
        "ownership": {"i_in_action": i_count, "we_in_action": we_count, "i_total": i_total, "we_total": we_total},
        "result_quantified": quantified,
        "reflection_present": reflection,
        "issues": issues,
        "fixes": fixes,
        "verdict": ("Interview-ready." if score >= 80 else f"Score {score}/100 — fix {len(issues)} issue(s); re-check."),
    }


COMPETENCY_BANK: dict[str, list[dict]] = {
    "ownership": [
        {"q": "Tell me about a time you took on something outside your job description.", "strong": "a self-initiated scope, a concrete deliverable, and what changed after", "red_flags": "waiting for permission; no outcome"},
        {"q": "Describe a project you drove end to end. What was your specific contribution?", "strong": "clear 'I' decisions, trade-offs named, measurable result", "red_flags": "'we' throughout; can't name a decision they made"},
        {"q": "Tell me about a time something broke that wasn't your fault. What did you do?", "strong": "acted anyway, communicated early, fixed root cause", "red_flags": "blame; 'not my area'"},
    ],
    "ambiguity": [
        {"q": "Tell me about a time you had to make a decision without enough information.", "strong": "what they knew, what they assumed, how they de-risked, when they'd revisit", "red_flags": "waited for certainty; no reversibility thinking"},
        {"q": "Describe a project whose goal kept changing. How did you handle it?", "strong": "re-scoped explicitly, renegotiated with stakeholders, protected the team", "red_flags": "complaint narrative; no action"},
        {"q": "How did you figure out what to work on when nobody told you?", "strong": "a prioritisation method, evidence gathered, a choice defended", "red_flags": "picked the most interesting thing"},
    ],
    "influence": [
        {"q": "Tell me about a time you changed someone's mind who didn't report to you.", "strong": "understood their incentives, brought data, offered a concession, named the outcome", "red_flags": "escalated first; 'I kept pushing until they gave in'"},
        {"q": "Describe a time you disagreed with your manager. What happened?", "strong": "disagreed with evidence, committed once decided, result either way", "red_flags": "never disagreed; or went around the manager"},
        {"q": "Tell me about getting buy-in from a skeptical stakeholder.", "strong": "diagnosed the objection, pilot or proof, converted them into a sponsor", "red_flags": "one meeting, no follow-through"},
    ],
    "conflict": [
        {"q": "Tell me about a conflict with a coworker and how you resolved it.", "strong": "direct conversation, their perspective stated fairly, working agreement, relationship after", "red_flags": "avoided it; HR as first step; other person is the villain"},
        {"q": "Describe a time you received harsh feedback. What did you do with it?", "strong": "specific feedback, initial reaction owned, concrete change, evidence it stuck", "red_flags": "the feedback was wrong; vague change"},
        {"q": "Tell me about a time you had to deliver bad news.", "strong": "early, direct, with options, and what they did to soften impact", "red_flags": "delayed; sugar-coated; no options"},
    ],
    "failure": [
        {"q": "Tell me about a time you failed. What did you learn?", "strong": "a real failure they caused, cost quantified, specific practice changed since", "red_flags": "'perfectionism'; team failure; no cost; lesson is generic"},
        {"q": "Describe a decision you'd make differently today.", "strong": "the reasoning at the time, what new info changed, the rule they use now", "red_flags": "hindsight blame; no rule"},
        {"q": "Tell me about a goal you missed.", "strong": "the gap in numbers, root cause not excuses, what recovered", "red_flags": "external factors only"},
    ],
    "execution": [
        {"q": "Tell me about the most complex project you delivered. How did you keep it on track?", "strong": "milestones, risk register, what slipped and how they recovered, delivered outcome", "red_flags": "'we worked hard'; no mechanism"},
        {"q": "Describe a time you had too much to do. How did you prioritise?", "strong": "an explicit ranking method, what they dropped and told whom", "red_flags": "did it all by working nights"},
        {"q": "Tell me about a time you improved a process.", "strong": "baseline metric, change made, after metric, adoption", "red_flags": "no before/after"},
    ],
    "customer": [
        {"q": "Tell me about a time you advocated for a customer against internal pressure.", "strong": "customer evidence, the internal cost, the decision, the result for both", "red_flags": "always sides with the business; or ignores cost"},
        {"q": "Describe how you found out what customers actually needed.", "strong": "a research method, a surprise finding, a product/decision change", "red_flags": "assumed; only listened to loudest customer"},
        {"q": "Tell me about turning around an unhappy customer.", "strong": "root cause, ownership, resolution, retention or NPS result", "red_flags": "discount as the whole answer"},
    ],
    "leadership": [
        {"q": "Tell me about developing someone on your team.", "strong": "a specific person, a gap diagnosed, a plan, their growth evidenced (promotion, scope)", "red_flags": "'I give lots of feedback'"},
        {"q": "Describe a time you had to manage an underperformer.", "strong": "clear expectations, documented plan, honest conversations, resolution either way", "red_flags": "let it drag; fired without process"},
        {"q": "How have you set direction for a team when the strategy was unclear?", "strong": "a hypothesis, a bounded bet, communication cadence, adjustment", "red_flags": "waited for leadership"},
    ],
    "technical_judgment": [
        {"q": "Walk me through a technical decision with a trade-off you had to make.", "strong": "options considered, criteria, the choice, what they'd revisit and when", "red_flags": "only one option; no criteria"},
        {"q": "Tell me about a time you pushed back on a technical requirement.", "strong": "the cost quantified, an alternative proposed, outcome", "red_flags": "just complied"},
        {"q": "Describe the hardest bug or analysis you've owned.", "strong": "systematic narrowing, tools used, root cause, prevention", "red_flags": "'I tried things until it worked'"},
    ],
    "growth": [
        {"q": "What have you deliberately learned in the last year and how?", "strong": "a named skill, a method, evidence of application", "red_flags": "'I read a lot'"},
        {"q": "Tell me about a time you were the least experienced person in the room.", "strong": "how they added value anyway, what they asked, what they absorbed", "red_flags": "stayed silent"},
    ],
}
ROLE_QUESTIONS: dict[str, list[dict]] = {
    "engineering": [
        {"q": "Tell me about a system you designed that had to scale. What broke first?", "strong": "load numbers, bottleneck found, fix, and what they'd design differently", "red_flags": "no numbers"},
        {"q": "Describe a time you reduced technical debt while still shipping features.", "strong": "how they sized the debt, sequenced it, and measured velocity or incident change", "red_flags": "'we did a rewrite'"},
        {"q": "Tell me about an incident you were on call for.", "strong": "timeline, communication, mitigation vs fix, post-mortem action items", "red_flags": "blame; no post-mortem"},
    ],
    "product": [
        {"q": "Tell me about a product decision you made with data that surprised you.", "strong": "hypothesis, metric, the surprise, the decision changed", "red_flags": "data confirmed what they wanted"},
        {"q": "Describe how you said no to a feature a senior stakeholder wanted.", "strong": "the cost/opportunity framing, alternative offered, relationship intact", "red_flags": "built it anyway"},
        {"q": "Walk me through a launch: what was the goal metric and did you hit it?", "strong": "target set before launch, actual vs target, what they learned", "red_flags": "no pre-set target"},
    ],
    "sales": [
        {"q": "Tell me about a deal you lost. Why, and what changed after?", "strong": "honest loss reason, discovery gap, process change, later win", "red_flags": "price as the only reason"},
        {"q": "Walk me through your best deal from first touch to close.", "strong": "multi-threading, champion built, objections handled, cycle length, ACV", "red_flags": "inbound lay-up with no method"},
        {"q": "How do you build pipeline when inbound is dry?", "strong": "a targeted list, a message that got replies, conversion numbers", "red_flags": "'I network'"},
    ],
    "marketing": [
        {"q": "Tell me about a campaign that underperformed and what you did.", "strong": "target vs actual, diagnosis, iteration, lift after", "red_flags": "blamed the creative/agency"},
        {"q": "Describe how you decided where to put budget last quarter.", "strong": "CAC/payback by channel, a reallocation, its result", "red_flags": "even split"},
        {"q": "Tell me about a piece of messaging you changed and how you knew it worked.", "strong": "research input, before/after conversion or reply rate", "red_flags": "'it felt stronger'"},
    ],
    "design": [
        {"q": "Walk me through a design where research changed your direction.", "strong": "method, finding, the pivot, usability or business metric after", "red_flags": "research as validation only"},
        {"q": "Tell me about shipping a compromised version of your design.", "strong": "what they protected, what they gave up, how they documented the follow-up", "red_flags": "refused to compromise; or gave up everything"},
    ],
    "data": [
        {"q": "Tell me about an analysis that changed a business decision.", "strong": "the question, the method, the finding in one sentence, the decision and its result", "red_flags": "the dashboard was the deliverable"},
        {"q": "Describe a time your analysis was wrong. How did you find out?", "strong": "the error, how it surfaced, the fix, the check they added since", "red_flags": "never wrong"},
    ],
    "operations": [
        {"q": "Tell me about a process you redesigned. What were the before/after numbers?", "strong": "cycle time, error rate or cost before and after, adoption method", "red_flags": "no baseline"},
        {"q": "Describe a time a vendor or partner failed you.", "strong": "early detection, contingency, renegotiation, outcome", "red_flags": "waited it out"},
    ],
    "management": [
        {"q": "How do you decide what to delegate and to whom?", "strong": "a framework (skill × will, stretch assignments), an example, a growth result", "red_flags": "delegates what they dislike"},
        {"q": "Tell me about hiring someone who didn't work out.", "strong": "what the process missed, what they changed in the loop since", "red_flags": "'bad luck'"},
    ],
    "general": [],
}
ROLE_ALIASES = {"software": "engineering", "engineer": "engineering", "developer": "engineering", "swe": "engineering", "pm": "product", "product manager": "product", "account executive": "sales", "ae": "sales", "sdr": "sales", "bdr": "sales", "growth": "marketing", "ux": "design", "analyst": "data", "analytics": "data", "data science": "data", "ops": "operations", "program": "operations", "project": "operations", "manager": "management", "director": "management", "head of": "management", "vp": "management"}
LEVEL_NOTES = {
    "entry": "Interviewers expect coachability and ownership over scope; stories from school, internships or side projects are fine if they end in a number.",
    "mid": "Interviewers expect independent execution and cross-team influence; at least half the stories should show you driving, not assisting.",
    "senior": "Interviewers expect judgment under ambiguity and influence without authority; every story needs a trade-off you decided and its consequence.",
    "lead": "Interviewers expect multiplying others, setting direction and making calls with incomplete data; include developing people and killing a project.",
    "executive": "Interviewers expect strategy, org design, capital allocation and board/exec communication; stories should span quarters and name numbers in $M.",
}


@AGENT.tool
def question_bank(
    role_family: str,
    level: Literal["entry", "mid", "senior", "lead", "executive"] = "mid",
    competencies: list[str] | None = None,
    count: int = 12,
) -> dict:
    """Return a deterministic, role-specific behavioral question set with what a strong answer must contain and red flags.

    Draws evenly across the requested competencies (default: the seven every loop tests) plus
    role-family questions. Same inputs always give the same set, so drills are repeatable.

    Args:
        role_family: One of engineering, product, sales, marketing, design, data, operations, management, general — or a title like "Senior PM" (aliases are mapped).
        level: Seniority: entry, mid, senior, lead, executive. Changes the guidance, not the questions.
        competencies: Subset of ownership, ambiguity, influence, conflict, failure, execution, customer, leadership, technical_judgment, growth. Defaults to the core seven.
        count: Number of questions to return (4-30).
    """
    rf = role_family.strip().lower()
    family = rf if rf in ROLE_QUESTIONS else next((v for k, v in ROLE_ALIASES.items() if k in rf), "general")
    if not 4 <= count <= 30:
        raise ToolError("count must be between 4 and 30.")
    default = ["ownership", "ambiguity", "influence", "conflict", "failure", "execution", "customer"]
    if level in ("lead", "executive"):
        default = ["leadership", "ownership", "ambiguity", "influence", "conflict", "failure", "execution"]
    if level == "entry":
        default = ["ownership", "growth", "conflict", "failure", "execution", "ambiguity"]
    comps = [c.strip().lower().replace(" ", "_") for c in (competencies or default) if str(c).strip()]
    bad = [c for c in comps if c not in COMPETENCY_BANK]
    if bad:
        raise ToolError(f"Unknown competencies: {', '.join(bad)}. Use: {', '.join(COMPETENCY_BANK)}.")
    if not comps:
        raise ToolError("competencies list is empty.")
    picked: list[dict] = []
    role_q = ROLE_QUESTIONS[family]
    role_share = min(len(role_q), max(1, count // 4)) if role_q else 0
    for q in role_q[:role_share]:
        picked.append({**q, "competency": f"role:{family}"})
    # Round-robin across competencies so coverage is even.
    idx = 0
    while len(picked) < count:
        progressed = False
        for c in comps:
            if len(picked) >= count:
                break
            bank = COMPETENCY_BANK[c]
            if idx < len(bank):
                picked.append({**bank[idx], "competency": c})
                progressed = True
        if not progressed:
            break
        idx += 1
    by_comp: dict[str, int] = {}
    for q in picked:
        by_comp[q["competency"]] = by_comp.get(q["competency"], 0) + 1
    stories_needed = max(6, min(8, len(comps) + 1))
    return {
        "role_family": family,
        "level": level,
        "level_guidance": LEVEL_NOTES[level],
        "questions": [{"n": i, **q} for i, q in enumerate(picked, 1)],
        "count": len(picked),
        "coverage": by_comp,
        "stories_needed": stories_needed,
        "verdict": f"{len(picked)} questions across {len(by_comp)} areas. Build {stories_needed} STAR stories; each must cover ≥ 2 competencies.",
    }


@AGENT.tool
def lint_answer(answer: str, question: str = "", max_seconds: int = 120) -> dict:
    """Lint a spoken or typed interview answer for fillers, hedges, run-on sentences, 'we'-heavy ownership and length.

    Use on any answer (not only STAR stories): "tell me about yourself", "why us", follow-ups.
    Returns the offending words with positions and a tightened word budget.

    Args:
        answer: The answer as spoken or typed.
        question: The question being answered (optional; checks the answer restates it briefly).
        max_seconds: Maximum spoken length in seconds (default 120; 60-90 for "tell me about yourself").
    """
    require_text(answer, "answer", max_chars=20_000)
    if not 20 <= max_seconds <= 600:
        raise ToolError("max_seconds must be between 20 and 600.")
    words = text.words(answer)
    n = len(words)
    seconds = round(n / WPM * 60)
    sents = text.sentences(answer)
    low = answer.lower()
    fillers = []
    for term, fix in FILLERS.items():
        if term == "like":
            # "like" is a filler only when it isn't the verb ("I really like growth") or part of
            # another counted hedge ("I feel like"): skip it after a subject/auxiliary/sense verb.
            cnt = sum(
                1
                for m in re.finditer(r"(?<![\w'])like(?![\w'])", low)
                if not re.search(r"(?:\b(?:i|you|we|they|he|she|would|really|just|to|also|don't|didn't|not|feel|feels|felt|look|looks|looked|sound|sounds|seem|seems|'d)\s*)$", low[: m.start()])
            )
        else:
            cnt = len(re.findall(r"(?<![\w'])" + re.escape(term) + r"(?![\w'])", low))
        if cnt:
            fillers.append({"term": term, "count": cnt, "fix": fix})
    fillers.sort(key=lambda f: -f["count"])
    filler_total = sum(f["count"] for f in fillers)
    long_sents = [s[:160] for s in sents if len(text.words(s)) > 30]
    i_n, we_n = len(I_RE.findall(answer)), len(WE_RE.findall(answer))
    number_present = bool(NUM_RE.search(answer))
    restates = None
    if question.strip():
        q_terms = {w.lower() for w in text.words(question) if w.lower() not in text.STOPWORDS and len(w) > 3}
        first = " ".join(sents[:1]).lower()
        restates = bool(q_terms) and any(t in first for t in q_terms)
    issues, fixes = [], []
    score = 100
    if seconds > max_seconds:
        issues.append(f"~{seconds}s spoken vs {max_seconds}s max")
        fixes.append(f"cut to ≤ {int(max_seconds * WPM / 60)} words — lead with the headline, drop the second example")
        score -= min(25, 5 * ((seconds - max_seconds) // 15 + 1))
    if filler_total:
        rate = pct(filler_total, n)
        issues.append(f"{filler_total} filler/hedge words ({rate}% of words)")
        fixes.extend(f"'{f['term']}' ×{f['count']}: {f['fix']}" for f in fillers[:5])
        score -= min(30, 3 * filler_total)
    if long_sents:
        issues.append(f"{len(long_sents)} run-on sentence(s) over 30 words")
        fixes.append("one idea per sentence — split at 'and', 'so', 'which'")
        score -= 5 * len(long_sents)
    if we_n > i_n:
        issues.append(f"'we' {we_n}× vs 'I' {i_n}× — ownership unclear")
        score -= 10
    if not number_present:
        issues.append("no number anywhere in the answer")
        score -= 10
    if restates is False:
        issues.append("opening doesn't acknowledge the question — restate it in one clause")
        score -= 5
    score = max(0, score)
    return {
        "score": score,
        "words": n,
        "spoken_seconds": seconds,
        "max_seconds": max_seconds,
        "word_budget": int(max_seconds * WPM / 60),
        "fillers": fillers,
        "filler_pct": pct(filler_total, n),
        "run_on_sentences": long_sents,
        "ownership": {"i": i_n, "we": we_n},
        "number_present": number_present,
        "restates_question": restates,
        "issues": issues,
        "fixes": fixes,
        "verdict": ("Clean delivery." if score >= 85 else f"Score {score}/100 — {len(issues)} delivery issue(s)."),
    }


PHASES = [
    ("Research", "company: product, last 2 launches, business model, 3 news items; role: re-read JD, list 5-7 competencies; interviewers: LinkedIn backgrounds", 2.0, "you can say in 60s why this company, this role, now"),
    ("Story bank", "draft 6-8 STAR stories mapped to competencies; run each through the checker; fix numbers", 3.0, "every competency has a story with a number"),
    ("Role drill", "role-specific questions (case, technical, portfolio, deal review); prepare 1-2 artefacts to reference", 2.5, "you can walk through your best work in 3 minutes with a number"),
    ("Mock interview", "full mock out loud (record it); lint two answers; tighten fillers and length", 2.0, "answers ≤ 2 min, fillers < 2%"),
    ("Second pass", "re-run weakest 3 stories out loud; prepare 3 reverse questions; prepare salary deflection line", 1.5, "weakest story scores ≥ 80"),
    ("Light review + logistics", "cue cards only (no new material); confirm time zone, link/location, outfit, ID; sleep", 1.0, "you could do it tomorrow with no notes"),
]


@AGENT.tool
def plan_prep_schedule(interview_date: str, start_date: str = "", hours_per_day: float = 2.0, interview_time: str = "") -> dict:
    """Build a dated, day-by-day prep schedule that ends with a light day before the interview.

    Allocates research → story bank → role drill → mock → second pass → light review across the
    days available, respecting hours_per_day. Compresses sensibly when there are only 1-3 days.

    Args:
        interview_date: Interview date as YYYY-MM-DD.
        start_date: First prep day as YYYY-MM-DD. Defaults to today.
        hours_per_day: Hours the candidate can prep per day (0.5-8).
        interview_time: Interview time like "14:00" (optional; used for the day-of note).
    """
    iv = dates.parse_date(interview_date)
    start = dates.parse_date(start_date) if start_date else date.today()
    if not 0.5 <= hours_per_day <= 8:
        raise ToolError("hours_per_day must be between 0.5 and 8.")
    if iv < start:
        raise ToolError(f"interview_date {iv} is before start_date {start}.")
    days_available = (iv - start).days  # prep days before the interview day
    plan = []
    if days_available == 0:
        plan.append({"date": iv.isoformat(), "weekday": iv.strftime("%a"), "focus": "Same-day essentials", "hours": min(hours_per_day, 1.5), "tasks": "60s 'why us / why now'; your 3 best stories out loud with numbers; 2 reverse questions; logistics", "done_when": "you can say your headline result for each story without notes"})
    else:
        # Total hours available for prep excluding the light day before.
        work_days = max(0, days_available - 1)
        budget = work_days * hours_per_day
        phases = PHASES[:-1]
        need = sum(p[2] for p in phases)
        scale = min(1.0, budget / need) if need else 1.0
        # Distribute phases over work days in order; several phases may share a day.
        day_slots: list[list[dict]] = [[] for _ in range(max(1, work_days))]
        # With slack, spread the work instead of front-loading it and idling for days before the
        # interview: cap each day at the smallest half-hour step that still fits everything.
        per_day = hours_per_day
        if scale >= 1.0 and work_days > 0:
            per_day = min(hours_per_day, max(0.5, math.ceil(need / work_days * 2) / 2))
        remaining = [per_day] * max(1, work_days)
        di = 0
        for name, tasks, hrs, done in phases:
            h = round(hrs * scale, 1)
            while h > 0 and di < len(day_slots):
                take = round(min(h, remaining[di]), 1)
                if take <= 0:
                    di += 1
                    continue
                day_slots[di].append({"focus": name, "hours": take, "tasks": tasks, "done_when": done})
                remaining[di] = round(remaining[di] - take, 1)
                h = round(h - take, 1)
                if remaining[di] <= 0:
                    di += 1
        for i, slots in enumerate(day_slots):
            d = start + timedelta(days=i)
            if not slots:
                plan.append({"date": d.isoformat(), "weekday": d.strftime("%a"), "focus": "Rest / buffer", "hours": 0, "tasks": "no prep — buffer day", "done_when": "—"})
                continue
            for s in slots:
                plan.append({"date": d.isoformat(), "weekday": d.strftime("%a"), **s})
        if work_days == 0:
            # One day before only: compress essentials into it.
            plan = [{"date": start.isoformat(), "weekday": start.strftime("%a"), "focus": "Essentials", "hours": hours_per_day, "tasks": "research (45 min); 4 STAR stories with numbers (60 min); one mock out loud; reverse questions; logistics", "done_when": "4 stories ≤ 2 min each with a number"}]
        else:
            light = iv - timedelta(days=1)
            name, tasks, hrs, done = PHASES[-1]
            plan.append({"date": light.isoformat(), "weekday": light.strftime("%a"), "focus": name, "hours": min(hrs, hours_per_day), "tasks": tasks, "done_when": done})
        plan.append({"date": iv.isoformat(), "weekday": iv.strftime("%a"), "focus": "Interview day", "hours": 0.5, "tasks": ("arrive/log in 10 min early" + (f" for {interview_time}" if interview_time else "")) + "; re-read cue cards once; no new material; eat; walk", "done_when": "calm"})
    total_hours = round(sum(p["hours"] for p in plan), 1)
    compressed = days_available < 4
    return {
        "interview_date": iv.isoformat(),
        "interview_weekday": iv.strftime("%A"),
        "start_date": start.isoformat(),
        "days_before_interview": days_available,
        "total_prep_hours": total_hours,
        "compressed": compressed,
        "schedule": plan,
        "verdict": f"{days_available} day(s) before the interview, {total_hours}h of prep scheduled"
        + (" — compressed plan: prioritise story bank and one mock." if compressed else " — full plan; the day before is light review only."),
    }
