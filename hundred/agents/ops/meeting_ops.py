"""Meeting Ops — turns a finished meeting into filed notes, owned tasks, and a sent-ready follow-up.

The reference agent: every other agent in the library follows this shape.
Free forever — it's the lead magnet that gets people to install the MCP link.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date

from ...core import Agent, ToolError
from ...lib import dates, text
from ._common import resolve_relative_date

AGENT = Agent(
    slug="meeting-ops",
    name="Meeting Ops",
    category="ops",
    free=True,
    tagline="Paste a transcript; get filed notes, owned tasks with real due dates, and a follow-up email.",
    description=(
        "Runs the whole post-meeting workflow. Reads the transcript, extracts decisions and "
        "commitments with owners and due dates, files the notes (Notion/Docs), creates one task per "
        "action item (Linear/Asana/Jira), and drafts the follow-up email (Gmail) — grounded strictly "
        "in what was said, with every commitment traceable to a quote."
    ),
    triggers=[
        "summarize this meeting / call / transcript",
        "turn meeting notes into action items or tasks",
        "draft a follow-up email after a call",
        "what did we decide in this meeting",
        "file meeting notes to Notion / create Linear tickets from a call",
    ],
    examples=[
        "Here's the transcript from our product sync — file the notes and create the tasks.",
        "Summarize this sales call and draft the follow-up to the prospect.",
        "Pull every action item out of this standup with owners and due dates.",
    ],
    connectors=["Notion", "Google Docs", "Linear", "Asana", "Jira", "Gmail", "Slack", "Google Calendar"],
    playbook="""
    ## Standard
    You are a chief-of-staff-grade meeting operator. Your output is judged on one thing:
    could every attendee act on it without re-watching the recording? Nothing invented,
    nothing important dropped, every task has an owner and a date.

    ## Procedure
    1. **Profile the transcript.** Call `meeting_ops__transcript_stats` with the raw
       transcript (plain "Name: text", Otter/Fireflies exports with "Name  0:42" lines, or
       Zoom .vtt all work). It returns speakers, talk share, duration estimate, the meeting
       date if the header states one, every line with commitment language ("I'll", "by
       Friday", "can you", "someone should"), every line with decision language ("let's go
       with", "we're killing"), and retractions ("scratch that"). Candidates are your
       checklist: read each one in context, together with the lines that follow it — a
       commitment can be reassigned ("Aisha, can you take it instead?") or withdrawn two
       lines later, and the later state wins.
    2. **Resolve dates.** For every deadline phrase ("Friday", "EOD Thursday", "next
       Tuesday", "Oct 15th", "end of next week", "in two weeks") call
       `meeting_ops__resolve_due_dates` with the phrases exactly as spoken and the meeting
       date (use `detected_meeting_date`; if it is null, ask once, or assume today and say
       so). Never compute dates yourself. If a result has `confirm: true`, keep the date but
       mark it "(confirm)"; a phrase with no date ("once it's merged") stays undated — a
       condition is not a due date.
    3. **Classify every candidate** as exactly one of:
       - **Decision** — something the group agreed is now true ("we're going with Stripe").
       - **Action item** — a specific person committed to a specific deliverable.
       - **Open question** — raised, not resolved, needs an owner.
       - **Noise** — brainstorming, hypotheticals, "we should maybe someday".
       An action item needs an owner. If the owner is ambiguous ("someone should"),
       it becomes an open question with a suggested owner — never silently assign.
    4. **Build the task list** and run `meeting_ops__format_action_items` on it. It
       normalises titles to imperative verbs, flags tasks with no owner/date, detects
       duplicates, and groups by owner for the email.
    5. **Act, if you can.** If the user's AI has Notion/Docs, file the notes. If it has
       Linear/Asana/Jira, create one issue per action item (title, owner, due date,
       one-line context + the source quote). If it has Gmail, create a *draft* (never
       send without the user saying so). If a connector is missing, output the content
       ready to paste and say which connector would automate it.
    6. **Self-check before replying** (silently): every action item has owner + due date
       or is explicitly flagged; every decision is phrased as a fact; no item appears
       twice; nothing in the output is not supported by the transcript.

    ## Output format
    ```
    # <Meeting title> — <YYYY-MM-DD>
    **Attendees:** … · **Length:** ~N min · **Talk share:** A 40%, B 35%, …

    ## TL;DR
    <2-3 sentences: why we met, what changed.>

    ## Decisions
    - <Decision stated as fact> — _"<short supporting quote>"_

    ## Action items
    | # | Task (imperative) | Owner | Due | Source |
    |---|---|---|---|---|

    ## Open questions
    - <Question> → suggested owner: <name>

    ## Follow-up email (draft)
    Subject: <specific>
    <One-line recap. Owner → task (due) list. Warm one-line close.>
    ```
    Then one line listing what you filed/created, or which connectors would automate it.

    ## Anti-patterns
    - Summarising the conversation chronologically ("First, Sam talked about…"). Report outcomes.
    - Tasks like "Look into X" with no deliverable — rewrite to what "done" looks like.
    - Inventing due dates. No date stated → "no date — confirm" flag, not a guess.
    - Keeping the first owner of a task that was reassigned later in the meeting, or a
      commitment the speaker withdrew ("scratch that"). The last word in the transcript wins.
    - Turning "someone should…" into a task for whoever said it. No named owner = open question.
    - Padding the TL;DR. If it was a status meeting with no decisions, say so.
    """,
)

SPEAKER_RE = re.compile(r"^\s*(?:\[?[\d:.]{4,12}\]?\s*)?([A-Z][\w .'-]{0,40}?)\s*(?:\([^)]*\))?\s*:\s+(.+)$")
# Otter/Fireflies-style exports put the speaker and a timestamp on their own line, text below.
SPEAKER_HEADER_RE = re.compile(r"^\s*([A-Z][\w.'-]*(?: [A-Z0-9][\w.'-]*){0,3})\s*(?:\([^)]*\))?(?:\s{2,}|\s*[-–—|]\s*|\s+(?=[\[(]))\[?\(?(\d{1,2}:\d{2}(?::\d{2})?)\)?\]?\s*$")
VTT_NOISE_RE = re.compile(r"^\s*(WEBVTT|NOTE\b|\d+\s*$|[\d:.]+\s*-->\s*[\d:.]+)")
# "Attendees: …", "Date: …" are header fields, not speakers.
HEADER_LABELS = {
    "attendees", "attendee", "participants", "present", "date", "time", "agenda", "location", "subject", "title",
    "meeting", "notes", "note", "action items", "action item", "summary", "recording", "duration", "absent", "cc",
    "re", "topic", "transcript", "host", "organizer", "next meeting", "decisions",
}
COMMIT_RE = re.compile(
    r"\b(I'?ll|I will|I can|I'm going to|I'm on it|I owe|I need to|I have to|let me|will do|we'?ll|we will|let'?s|"
    r"can you|could you|will you|would you mind|you'?ll|action item|todo|to-do|follow up|"
    r"by (?:mon|tues?|wed(?:nes)?|thurs?|fri|satur|sun)(?:day)?|"
    r"by (?:eod|eow|cob|end of|tomorrow|next|the \d)|owner|assign|take (?:that|this|it) on|I'?ll take|on it|"
    r"someone (?:should|needs to|has to)|who(?:'s| is) (?:going to|taking|owning))\b",
    re.I,
)
DECISION_RE = re.compile(
    r"\b(we(?:'ve| have)? decided|decision is|let'?s go with|we'?re going with|going with|agreed|we agree|"
    r"final (?:answer|call)|locked in|that'?s settled|we'?ll stick with|let'?s keep|let'?s kill|we'?re killing|"
    r"let'?s (?:not|drop|cut|move|push|ship)|approved|sign(?:ed)? off)\b",
    re.I,
)
RETRACT_RE = re.compile(r"\b(scratch that|never ?mind|actually,? no|forget (?:that|it)|not needed anymore|no longer needed|cancel that)\b", re.I)
_DATE_IN_HEADER = [
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
    re.compile(r"\b((?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})\b", re.I),
    re.compile(r"\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?,?\s+\d{4})\b", re.I),
]


def _detect_meeting_date(transcript: str) -> str | None:
    head = "\n".join(transcript.splitlines()[:8])
    for rx in _DATE_IN_HEADER:
        m = rx.search(head)
        if m:
            d, _rule = resolve_relative_date(m.group(1), date(2000, 1, 1))
            if d:
                return d.isoformat()
    return None


@AGENT.tool
def transcript_stats(transcript: str) -> dict:
    """Profile a meeting transcript: speakers, talk share, length, commitment and decision candidate lines, meeting date.

    Call first. Works with "Name: text" lines (optionally timestamped), Otter/Fireflies exports
    ("Name  0:42" on its own line, text below) and Zoom .vtt captions. Header fields such as
    "Attendees:" are not counted as speakers. Returns every line with commitment language
    (so no action item is missed), lines with decision language, retractions ("scratch that"),
    and the meeting date if the header states one.

    Args:
        transcript: The raw meeting transcript text.
    """
    if not transcript.strip():
        raise ToolError("Transcript is empty.")
    if len(transcript) > 400_000:
        raise ToolError("Transcript too long (400k chars max). Split it into parts.")
    words_by_speaker: Counter[str] = Counter()
    candidates, decisions, retractions = [], [], []
    unattributed = 0
    current: str | None = None
    for n, line in enumerate(transcript.splitlines(), 1):
        if not line.strip() or VTT_NOISE_RE.match(line):
            continue
        hdr = SPEAKER_HEADER_RE.match(line)
        if hdr and hdr.group(1).strip().lower() not in HEADER_LABELS:
            current = hdr.group(1).strip()
            continue
        m = SPEAKER_RE.match(line)
        if m and m.group(1).strip().lower() in HEADER_LABELS:
            continue  # "Attendees: …", "Date: …"
        if m:
            speaker, said = m.group(1).strip(), m.group(2)
            current = speaker
        elif current and not line.lstrip().startswith(("[", "(")) or (current and len(line) > 60):
            speaker, said = current, line
        else:
            speaker, said = None, line
        if speaker:
            words_by_speaker[speaker] += len(text.words(said))
        else:
            unattributed += 1
        item = {"line": n, "speaker": speaker, "text": said.strip()[:400]}
        if COMMIT_RE.search(said):
            candidates.append(item)
        if DECISION_RE.search(said):
            decisions.append(item)
        if RETRACT_RE.search(said):
            retractions.append(item)
    total = sum(words_by_speaker.values()) or len(text.words(transcript))
    share = {s: round(100 * w / total, 1) for s, w in words_by_speaker.most_common()}
    detected = _detect_meeting_date(transcript)
    return {
        "speakers": list(share),
        "talk_share_pct": share,
        "total_words": total,
        "estimated_minutes": round(len(text.words(transcript)) / 150),
        "detected_meeting_date": detected,
        "commitment_candidates": candidates,
        "decision_candidates": decisions,
        "retractions": retractions,
        "unattributed_lines": unattributed,
        "note": "Each candidate still needs judgement: confirm owner + deliverable in context, drop anything retracted "
        "or reassigned later in the meeting, and pass detected_meeting_date to resolve_due_dates"
        + ("" if detected else " (no date in the header — ask, or assume today and say so)")
        + ".",
    }


@AGENT.tool
def resolve_due_dates(phrases: list[str], meeting_date: str = "") -> dict:
    """Turn relative deadlines ("by Friday", "EOD Thursday", "next Tuesday", "Oct 15th", "in 2 weeks") into calendar dates.

    A named weekday beats a same-day word ("EOD Thursday" is Thursday, not today). "next <day>"
    means that day in the next calendar week; when a speaker could have meant the nearer one, the
    rule says "confirm". Phrases with no date ("once it's merged") return null — never guess.

    Args:
        phrases: Deadline phrases exactly as spoken in the meeting.
        meeting_date: The meeting date as YYYY-MM-DD (use transcript_stats' detected_meeting_date). Defaults to today.
    """
    base = dates.parse_date(meeting_date) if meeting_date else date.today()
    out = []
    for phrase in phrases[:100]:
        d, rule = resolve_relative_date(str(phrase), base)
        if d is None:
            rule = "unrecognised — confirm with owner"
        out.append({"phrase": phrase, "due": d.isoformat() if d else None, "weekday": d.strftime("%a") if d else None, "rule": rule, "confirm": d is None or "confirm" in rule})
    return {"meeting_date": base.isoformat(), "meeting_weekday": base.strftime("%A"), "assumed_today": not meeting_date, "resolved": out}


VAGUE_VERBS = re.compile(r"^(look into|think about|consider|check on|explore|touch base|circle back|discuss)\b", re.I)
IMPERATIVE_FIX = {"will ": "", "i'll ": "", "we'll ": "", "going to ": "", "to ": ""}


@AGENT.tool
def format_action_items(items: list[dict]) -> dict:
    """Normalise, validate, dedupe and group action items before filing them.

    Flags items missing an owner or due date, vague tasks with no deliverable, and
    near-duplicates. Returns the cleaned list plus an owner-grouped view for the email.

    Args:
        items: List of {"task": str, "owner": str, "due": "YYYY-MM-DD" or "", "quote": str}.
    """
    cleaned, flags = [], []
    seen: dict[frozenset[str], int] = {}
    by_owner: dict[str, list[str]] = defaultdict(list)
    for i, raw in enumerate(items[:200], 1):
        task = str(raw.get("task", "")).strip().rstrip(".")
        low = task.lower()
        for prefix, repl in IMPERATIVE_FIX.items():
            if low.startswith(prefix):
                task = repl + task[len(prefix):]
                low = task.lower()
        task = task[:1].upper() + task[1:]
        owner = str(raw.get("owner", "")).strip()
        due = str(raw.get("due", "")).strip()
        issues = []
        if not task:
            issues.append("empty task")
        if not owner:
            issues.append("no owner — move to open questions or confirm")
        if not due:
            issues.append("no due date — confirm")
        elif due:
            try:
                dates.parse_date(due)
            except ToolError:
                issues.append(f"bad date {due!r}")
        if VAGUE_VERBS.match(task):
            issues.append("vague — rewrite as a deliverable (what does done look like?)")
        key = frozenset(w for w in text.words(low) if w not in text.STOPWORDS)
        dup_of = next((idx for k, idx in seen.items() if key and len(key & k) / max(1, len(key | k)) >= 0.7), None)
        if dup_of:
            issues.append(f"likely duplicate of #{dup_of}")
        else:
            seen[key] = i
        item = {"n": i, "task": task, "owner": owner or None, "due": due or None, "quote": raw.get("quote", ""), "issues": issues}
        cleaned.append(item)
        if issues:
            flags.append({"n": i, "issues": issues})
        by_owner[owner or "UNASSIGNED"].append(f"{task}" + (f" (due {due})" if due else ""))
    return {
        "items": cleaned,
        "flags": flags,
        "by_owner": dict(by_owner),
        "ready_to_file": not any("empty task" in f["issues"] or any("duplicate" in x for x in f["issues"]) for f in flags),
    }
