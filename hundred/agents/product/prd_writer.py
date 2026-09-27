"""PRD Writer — turns a fuzzy feature idea into a PRD engineers can estimate and QA can test."""

from __future__ import annotations

import re

from ...core import Agent, ToolError
from ...lib import text
from ._common import ambiguous_terms, check_rows, check_text, stem

AGENT = Agent(
    slug="prd-writer",
    name="PRD Writer",
    category="product",
    tagline="Turn a feature idea into a PRD with numbered, testable requirements and real success metrics.",
    description=(
        "Writes and audits product requirement documents the way a senior PM at a top product company "
        "does: problem-first, with a scored completeness check across the 12 sections that matter, "
        "auto-numbered requirement IDs with MUST/SHOULD/COULD priority, an ambiguity linter that catches "
        "untestable words like 'fast' and 'easy', user-story and acceptance-criteria linting, and a "
        "success-metric check that refuses metrics without a baseline, target and deadline."
    ),
    triggers=[
        "write a PRD / product requirements document",
        "review or score my PRD",
        "turn this feature idea into requirements",
        "write user stories and acceptance criteria",
        "define success metrics for a feature",
        "number and prioritise these requirements",
    ],
    examples=[
        "Write a PRD for adding SSO (SAML + Google) to our B2B SaaS app.",
        "Here's my PRD draft — score it and tell me what's missing before I send it to engineering.",
        "Turn these Slack notes about the new export feature into numbered requirements with acceptance criteria.",
    ],
    connectors=["Notion", "Google Docs", "Confluence", "Linear", "Jira"],
    playbook="""
    ## Standard
    You are a senior product manager whose PRDs are famous for one thing: engineering estimates
    them in one sitting and QA can write test cases from them without asking a question. The one
    metric that matters is **zero clarifying questions after handoff**. Every requirement is
    numbered, prioritised, and testable; every success metric has a baseline, a target and a date;
    the problem is stated before any solution. A PRD is a decision document, not a spec dump.

    ## Intake
    Proceed with whatever you were given. Only ask (max 3 questions) if you cannot infer:
    (1) who the user is and what they are trying to do today, (2) what business outcome triggered
    this, (3) what is explicitly out of scope. If the user gave you a draft, audit it first. If they
    gave you an idea, assume a sensible target user and constraints, list your assumptions under an
    **Assumptions** heading, and continue.

    ## Procedure
    1. **Audit the draft (if any).** Call `prd_writer__check_completeness` with the full text. It
       scores 12 weighted sections (problem, users, goals/non-goals, metrics, requirements, UX,
       edge cases, dependencies, risks, rollout, open questions, appendix) and returns the missing
       ones with what each should contain. Below 70/100 means "not ready for engineering". Fix the
       missing sections before polishing prose.
    2. **Frame the problem** in the format *"[User] needs to [job] because [motivation], but today
       [obstacle], which costs [quantified pain]."* If you cannot fill "costs", say the pain is
       unquantified and mark it as the first open question.
    3. **Write goals and non-goals.** 2-4 goals, each mapped to a metric. Non-goals are as important
       as goals: at least 3, each one a thing a reasonable engineer might otherwise build.
    4. **Draft requirements as single testable sentences**, then call `prd_writer__number_requirements`
       with the list. It assigns IDs (FR-001, NFR-001...), infers MUST/SHOULD/COULD from the modal
       verb (RFC 2119), flags ambiguous words ("fast", "easy", "etc"), compound requirements joined by
       "and/or", and requirements with no observable behaviour. Rewrite every flagged line — an
       ambiguous requirement is a future bug.
    5. **Write user stories for the top flows** ("As a <role>, I want <capability>, so that
       <outcome>") with Given/When/Then acceptance criteria, then call `prd_writer__lint_user_stories`.
       It checks the three-part structure, that every story has ≥ 1 acceptance criterion, that
       criteria are Given/When/Then or checkbox form, and that no story's "so that" merely restates
       the "I want". Fix before shipping.
    6. **Define success metrics** and call `prd_writer__check_success_metrics` on them. Each metric
       needs a name, a baseline, a target, a timeframe and a measurement source. The tool computes the
       implied relative lift and flags anything unmeasurable, targets with no baseline, and lifts
       above 50% without a stated reason (usually wishful). One primary metric, ≤ 3 guardrails.
    7. **Assemble** in the output format below. Then re-run `prd_writer__check_completeness` on your
       own draft and report the score at the top. Do not ship below 80.
    8. **Act if you can.** If Notion/Confluence/Google Docs is connected, file the PRD. If
       Linear/Jira is connected, create one ticket per MUST requirement titled with its ID.

    ## Frameworks
    - **RFC 2119 priorities:** MUST = launch-blocking; SHOULD = expected unless there's a good reason;
      COULD = nice-to-have, first to cut. Aim for ≤ 40% MUST — a PRD where everything is a MUST has
      not been prioritised.
    - **Amazon working-backwards:** if you cannot write the one-paragraph launch announcement, the
      problem is not understood yet.
    - **Testability test:** a requirement is testable when two engineers would independently write
      the same test for it. "The page loads fast" fails; "P95 page load ≤ 1.5 s on 4G" passes.
    - **Metric hierarchy:** one North Star input metric (moves within weeks), 1-3 guardrails
      (must not degrade: error rate, support tickets, churn), and a leading indicator you can read
      in the first 7 days.

    ## Output format
    ```
    # PRD: <Feature name>            Completeness: <score>/100 · Status: Draft · Owner: <name>
    ## 1. Problem                     <User needs… but today… costs…>
    ## 2. Users & jobs                <primary persona, secondary, explicitly NOT for>
    ## 3. Goals / Non-goals           <bullets; each goal → metric>
    ## 4. Success metrics             | Metric | Baseline | Target | By | Source |
    ## 5. Requirements                | ID | Priority | Requirement | Acceptance test |
    ## 6. User stories                As a… I want… so that… + Given/When/Then
    ## 7. UX & flows                  <entry points, states: empty/loading/error/success>
    ## 8. Edge cases & errors         <numbered>
    ## 9. Dependencies & constraints  <systems, teams, legal/privacy, platforms>
    ## 10. Risks & mitigations        | Risk | Likelihood | Impact | Mitigation |
    ## 11. Rollout                    <flag %, cohorts, kill switch, comms>
    ## 12. Open questions             | # | Question | Owner | Needed by |
    ## Assumptions                    <everything you guessed>
    ```

    ## Anti-patterns
    - Solution before problem ("Build a dashboard that…"). Lead with the user's job and pain.
    - Requirements with "should be easy/fast/intuitive". Replace with numbers or observable behaviour.
    - A metric like "increase engagement". No baseline, no target, no date = not a metric.
    - Everything is a MUST. Prioritise or engineering will do it for you, badly.
    - No non-goals. Scope creep starts in the PRD.
    - Hiding open questions in prose. They belong in the table with an owner and a date.
    """,
)

SECTIONS: list[tuple[str, int, str, str]] = [
    # key, weight, regex of heading/keywords, what it should contain
    ("problem", 14, r"problem|pain|why (?:now|this)|background|context|opportunity", "who hurts, how, and what it costs today"),
    ("users", 10, r"users?\b|persona|customer|audience|who is this for|jobs?[- ]to[- ]be[- ]done", "primary/secondary persona and who it is NOT for"),
    ("goals", 10, r"goals?|objectives?|non[- ]goals?|out of scope|not in scope", "2-4 goals and ≥ 3 explicit non-goals"),
    ("metrics", 12, r"success metrics?|kpis?|measure|north star|guardrail|how we(?:'ll| will) know", "baseline, target, date, source per metric"),
    ("requirements", 14, r"requirements?|functional|must|shall|user stories|acceptance criteria", "numbered, prioritised, testable statements"),
    ("ux", 8, r"ux|user experience|flows?|wireframes?|design|mockups?|screens?|states?", "entry points, empty/loading/error/success states"),
    ("edge_cases", 7, r"edge cases?|error (?:handling|states?)|failure|what if|corner cases?", "numbered edge cases with expected behaviour"),
    ("dependencies", 6, r"dependenc|constraints?|assumptions?|platforms?|integrations?|privacy|security|legal", "systems, teams, legal/privacy constraints"),
    ("risks", 6, r"risks?|mitigations?|unknowns", "risk, likelihood, impact, mitigation"),
    ("rollout", 6, r"rollout|launch plan|release|phases?|milestones?|timeline|feature flag|go[- ]to[- ]market|gtm", "flag %, cohorts, kill switch, comms"),
    ("open_questions", 5, r"open questions?|unresolved|tbd|to be decided|decisions? needed", "table with owner and needed-by date"),
    ("appendix", 2, r"appendix|references?|research|links?|competitive|prior art", "research, competitive notes, links"),
]
_HEADING_RE = re.compile(r"^\s*(?:#{1,6}\s+|\d+(?:\.\d+)*[.)]\s+|[A-Z][A-Za-z &/-]{2,40}:\s*$)(.*)$", re.M)


@AGENT.tool
def check_completeness(prd_text: str) -> dict:
    """Score a PRD draft 0-100 against the 12 sections engineering needs, listing what is missing.

    Call before editing a draft and again on your final version. Heading-aware: a section counts as
    present when a heading (or strong keyword cluster) for it exists and it has ≥ 25 words of body.

    Args:
        prd_text: The full PRD draft (markdown or plain text).
    """
    body = check_text(prd_text, "prd_text")
    lower = body.lower()
    headings = [h.strip().lower() for h in _HEADING_RE.findall(body)]
    total_words = len(text.words(body))
    found, missing, thin = [], [], []
    score = 0
    for key, weight, pattern, should in SECTIONS:
        rx = re.compile(pattern, re.I)
        in_heading = any(rx.search(h) for h in headings)
        keyword_hits = len(rx.findall(lower))
        present = in_heading or keyword_hits >= 3
        if not present:
            missing.append({"section": key, "weight": weight, "should_contain": should})
            continue
        # crude body-size check: words in the paragraph after the matched heading
        body_words = _section_words(body, rx)
        min_words = 8 if key in ("open_questions", "appendix") else 25
        if body_words is not None and body_words < min_words:
            thin.append({"section": key, "words": body_words, "should_contain": should})
            score += weight // 2
        else:
            score += weight
        found.append(key)
    metric_rows = len(re.findall(r"\b(?:baseline|target)\b", lower))
    numbered_reqs = len(re.findall(r"\b(?:FR|NFR|REQ|R)-?\d{1,4}\b", body))
    must_count = len(re.findall(r"\b(?:must|shall)\b", lower))
    bonus_notes = []
    if numbered_reqs == 0 and "requirements" in found:
        bonus_notes.append("Requirements are not numbered — run prd_writer__number_requirements.")
    if metric_rows < 2 and "metrics" in found:
        bonus_notes.append("Metrics section mentions no baseline/target — run prd_writer__check_success_metrics.")
    if not re.search(r"non[- ]goals?|out of scope|not in scope", lower):
        bonus_notes.append("No explicit non-goals — add at least 3.")
    score = max(0, min(100, score))
    verdict = (
        "Ready for engineering review" if score >= 80 else
        "Needs work before handoff" if score >= 70 else
        "Not ready — fill the missing sections first"
    )
    return {
        "score": score,
        "verdict": verdict,
        "total_words": total_words,
        "present": found,
        "missing": missing,
        "thin": thin,
        "numbered_requirements": numbered_reqs,
        "must_statements": must_count,
        "notes": bonus_notes,
        "next_step": (f"Add: {', '.join(m['section'] for m in missing)}" if missing else "Polish thin sections, then number requirements."),
    }


def _section_words(body: str, rx: re.Pattern) -> int | None:
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if _HEADING_RE.match(line) and rx.search(line):
            n = 0
            for nxt in lines[i + 1 :]:
                if _HEADING_RE.match(nxt) and len(nxt.strip()) < 80:
                    break
                n += len(text.words(nxt))
            return n
    return None


_PRIORITY_RE = re.compile(r"\b(must|shall|required|must not|shall not)\b|\b(should|recommended)\b|\b(could|may|optional|nice[- ]to[- ]have)\b", re.I)
_NFR_RE = re.compile(r"\b(latency|p9[059]|ms\b|seconds?|throughput|uptime|availability|sla|scal|secur|encrypt|gdpr|accessib|wcag|performance|load|concurren|localis|localiz|i18n|audit log|retention|backup|compliance)", re.I)
_OBSERVABLE_RE = re.compile(r"\b(display|show|return|send|sent|receive|create|delete|update|allow|prevent|block|redirect|log|store|validate|reject|accept|approve|request|notify|remind|export|import|render|respond|complete|configure|assign|invite|share|upload|download|view|see|open|edit|save|search|filter|sort|generate|within|≤|<=|>=|at least|at most|no more than|\d)", re.I)
# a second clause joined by and/or ("gets an email and can approve") = two behaviours in one requirement
_COMPOUND_RE = re.compile(r"\b(?:and|or)\s+(?:then\s+)?(?:can|must|should|shall|will|may|could|is|are|gets?|sends?|receives?|shows?|creates?|updates?|deletes?|allows?|notif(?:y|ies))\b", re.I)


@AGENT.tool
def number_requirements(requirements: list[str], prefix: str = "FR", start: int = 1) -> dict:
    """Assign IDs and RFC-2119 priorities to requirements, flagging untestable or compound ones.

    Returns each requirement with an ID (FR-001 / NFR-001), inferred priority (MUST/SHOULD/COULD),
    ambiguity words, compound flags ("and/or", multiple "and" clauses), and the MUST ratio.

    Args:
        requirements: One requirement per string, as full sentences.
        prefix: ID prefix for functional requirements (default "FR"); non-functional ones get "N"+prefix.
        start: First number to use (default 1).
    """
    reqs = check_rows(requirements, "requirements")
    if not isinstance(start, int) or start < 1:
        raise ToolError("start must be a positive integer.")
    prefix = re.sub(r"[^A-Z]", "", str(prefix).upper()) or "FR"
    out, counters = [], {"F": start, "N": start}
    by_priority = {"MUST": 0, "SHOULD": 0, "COULD": 0}
    for raw in reqs:
        s = str(raw).strip()
        if not s:
            raise ToolError("requirements contains an empty string.")
        m = _PRIORITY_RE.search(s)
        if m and m.group(1):
            pri, explicit = "MUST", True
        elif m and m.group(2):
            pri, explicit = "SHOULD", True
        elif m and m.group(3):
            pri, explicit = "COULD", True
        else:
            pri, explicit = "MUST", False
        kind = "N" if _NFR_RE.search(s) else "F"
        rid = f"{'N' if kind == 'N' else ''}{prefix}-{counters[kind]:03d}"
        counters[kind] += 1
        issues = []
        amb = ambiguous_terms(s)
        if amb:
            issues.append(f"ambiguous: {', '.join(amb)} — replace with a number or observable behaviour")
        if re.search(r"\band/or\b", s, re.I) or len(re.findall(r"\band\b", s, re.I)) >= 2 or _COMPOUND_RE.search(s):
            issues.append("compound — split into one requirement per behaviour")
        if not _OBSERVABLE_RE.search(s):
            issues.append("no observable behaviour — what would a tester see?")
        if not explicit:
            issues.append("no modal verb — defaulted to MUST; state MUST/SHOULD/COULD explicitly")
        if len(text.words(s)) > 40:
            issues.append("over 40 words — shorten or split")
        by_priority[pri] += 1
        out.append({"id": rid, "priority": pri, "type": "non-functional" if kind == "N" else "functional", "requirement": s, "issues": issues})
    n = len(out)
    must_pct = round(100 * by_priority["MUST"] / n, 1)
    flagged = sum(1 for r in out if r["issues"])
    notes = []
    if must_pct > 60:
        notes.append(f"{must_pct}% are MUST — prioritise; aim for ≤ 40% MUST.")
    if flagged:
        notes.append(f"{flagged}/{n} requirements need rewriting before handoff.")
    return {
        "requirements": out,
        "count": n,
        "by_priority": by_priority,
        "must_pct": must_pct,
        "flagged": flagged,
        "verdict": "Clean — ready to paste" if not flagged and must_pct <= 60 else "Rewrite flagged items",
        "notes": notes,
    }


_STORY_RE = re.compile(r"as\s+an?\s+(.+?),?\s+i\s+(?:want|need|can|would like)\s+(?:to\s+)?(.+?)(?:,?\s+so\s+that\s+(.+))?$", re.I | re.S)
_GWT_RE = re.compile(r"\bgiven\b.*\bwhen\b.*\bthen\b", re.I | re.S)


@AGENT.tool
def lint_user_stories(stories: list[dict]) -> dict:
    """Validate user stories and acceptance criteria: structure, testability, and circular "so that".

    Args:
        stories: List of {"story": "As a X, I want Y, so that Z", "criteria": ["Given… When… Then…", ...]}.
    """
    rows = check_rows(stories, "stories")
    results, ok = [], 0
    for i, raw in enumerate(rows, 1):
        if not isinstance(raw, dict):
            raise ToolError(f"stories[{i - 1}] must be an object with 'story' and 'criteria'.")
        story = str(raw.get("story", "")).strip()
        criteria = raw.get("criteria") or []
        if not isinstance(criteria, list):
            raise ToolError(f"stories[{i - 1}].criteria must be a list of strings.")
        issues = []
        m = _STORY_RE.match(story)
        role = want = outcome = None
        if not m:
            issues.append("not in 'As a <role>, I want <capability>, so that <outcome>' form")
        else:
            role, want, outcome = m.group(1).strip(), m.group(2).strip(), (m.group(3) or "").strip()
            if role.lower() in {"user", "users", "customer", "person", "someone"}:
                issues.append("role is generic ('user') — name the persona")
            if not outcome:
                issues.append("missing 'so that' — why does the user want this?")
            else:
                wset = {stem(w) for w in text.words(want.lower()) if w not in text.STOPWORDS}
                oset = {stem(w) for w in text.words(outcome.lower()) if w not in text.STOPWORDS}
                if wset and oset and len(wset & oset) / len(oset) >= 0.6:
                    issues.append("'so that' restates 'I want' — state the real outcome/benefit")
            amb = ambiguous_terms(want)
            if amb:
                issues.append(f"ambiguous: {', '.join(amb)}")
        if not criteria:
            issues.append("no acceptance criteria — add ≥ 1 Given/When/Then")
        bad_crit = [c for c in criteria if not (_GWT_RE.search(str(c)) or re.match(r"^\s*(?:-|\*|\[[ x]\]|\d+[.)])", str(c)))]
        if bad_crit:
            issues.append(f"{len(bad_crit)} criteria not Given/When/Then or checklist form")
        amb_crit = sorted({w for c in criteria for w in ambiguous_terms(str(c))})
        if amb_crit:
            issues.append(f"criteria contain ambiguous words: {', '.join(amb_crit)}")
        if not issues:
            ok += 1
        results.append({"n": i, "role": role, "capability": want, "outcome": outcome or None, "criteria_count": len(criteria), "issues": issues})
    return {
        "stories": results,
        "count": len(results),
        "passing": ok,
        "verdict": f"{ok}/{len(results)} stories ready" + ("" if ok == len(results) else " — fix flagged ones"),
    }


_TIME_RE = re.compile(
    r"\b(\d+\s*(?:days?|weeks?|months?|quarters?|q[1-4]|sprints?)|by\s+\d{4}-\d{2}-\d{2}|\d{4}-\d{2}-\d{2}|end of\s+\w+|within\s+\d+"
    r"|(?:q[1-4]|h[12]|fy)\s*'?\d{2,4}"  # Q4 2026, H1 2027, FY26
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+(?:\d{1,2},?\s+)?\d{4})",  # Dec 2026, December 31, 2026
    re.I,
)
_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _num(v) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = _NUM_RE.search(str(v).replace(",", ""))
    return float(m.group(0)) if m else None


@AGENT.tool
def check_success_metrics(metrics: list[dict]) -> dict:
    """Validate success metrics (baseline, target, timeframe, source) and compute the implied lift.

    Flags metrics with no baseline, no target, no deadline, no measurement source, an undefined
    direction, or an implausible lift (> 50% relative without a stated reason).

    Args:
        metrics: List of {"name": str, "baseline": number|str, "target": number|str, "timeframe": str,
            "source": str, "type": "primary"|"guardrail"|"leading" (optional), "unit": str (optional)}.
    """
    rows = check_rows(metrics, "metrics")
    out, primaries, ready = [], 0, 0
    for i, raw in enumerate(rows, 1):
        if not isinstance(raw, dict):
            raise ToolError(f"metrics[{i - 1}] must be an object.")
        name = str(raw.get("name", "")).strip()
        base, target = _num(raw.get("baseline")), _num(raw.get("target"))
        tf, src = str(raw.get("timeframe", "")).strip(), str(raw.get("source", "")).strip()
        mtype = str(raw.get("type", "")).strip().lower() or "unspecified"
        issues = []
        if not name:
            issues.append("no name")
        if base is None:
            issues.append("no numeric baseline — measure current state first")
        if target is None:
            issues.append("no numeric target")
        if not tf or not _TIME_RE.search(tf):
            issues.append("no concrete timeframe (e.g. '90 days after launch', '2026-12-31')")
        if not src:
            issues.append("no measurement source (which dashboard/event/query?)")
        lift_abs = lift_rel = None
        if base is not None and target is not None:
            lift_abs = round(target - base, 4)
            if base != 0:
                lift_rel = round(100 * (target - base) / abs(base), 1)
                if abs(lift_rel) > 50 and not raw.get("reason"):
                    issues.append(f"{lift_rel:+.0f}% relative change — justify or make it a stretch target")
            if lift_abs == 0:
                issues.append("target equals baseline — no change expected?")
        if re.search(r"\b(engagement|satisfaction|awareness|experience|adoption)\b$", name.lower()) and raw.get("unit") is None:
            issues.append("vague metric name — say what exactly is counted (e.g. 'weekly active exporters')")
        if mtype == "primary":
            primaries += 1
        if not issues:
            ready += 1
        out.append({"n": i, "name": name, "type": mtype, "baseline": base, "target": target, "lift_abs": lift_abs, "lift_rel_pct": lift_rel, "issues": issues})
    notes = []
    if primaries == 0:
        notes.append("No metric is marked primary — pick exactly one North Star.")
    elif primaries > 1:
        notes.append(f"{primaries} primary metrics — pick one; demote the rest to guardrails.")
    guardrails = sum(1 for m in out if m["type"] == "guardrail")
    if guardrails == 0:
        notes.append("No guardrail metric — add at least one thing that must not get worse.")
    return {"metrics": out, "ready": ready, "count": len(out), "verdict": f"{ready}/{len(out)} metrics fully specified", "notes": notes}
