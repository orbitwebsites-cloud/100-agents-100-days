"""Meeting Ops — turns a finished meeting into filed notes, owned tasks, and a sent-ready follow-up.

The reference agent: every other agent in the library follows this shape.
Free forever — it's the lead magnet that gets people to install the MCP link.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date, timedelta

from ...core import Agent, ToolError
from ...lib import dates, text

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
       transcript. It returns speakers, talk share, duration estimate and every line that
       contains commitment language ("I'll", "by Friday", "let's", "can you"). Those lines
       are your candidate action items — read each one in context.
    2. **Resolve dates.** For every relative deadline ("Friday", "end of next week",
       "EOD tomorrow", "in two weeks") call `meeting_ops__resolve_due_dates` with the
       phrases and the meeting date (ask for it only if it isn't in the transcript;
       otherwise assume today and say so). Never compute dates yourself.
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
    - Padding the TL;DR. If it was a status meeting with no decisions, say so.
    """,
)

SPEAKER_RE = re.compile(r"^\s*(?:\[?[\d:]{4,8}\]?\s*)?([A-Z][\w .'-]{0,40}?)\s*(?:\([^)]*\))?\s*:\s+(.+)$")
COMMIT_RE = re.compile(
    r"\b(I'?ll|I will|I can|I'm going to|we'?ll|we will|let'?s|can you|could you|will you|"
    r"you'?ll|action item|todo|to-do|follow up|by (?:mon|tues|wednes|thurs|fri|satur|sun)day|"
    r"by (?:eod|eow|end of|tomorrow|next)|owner|assign|take (?:that|this) on|on it)\b",
    re.I,
)
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


@AGENT.tool
def transcript_stats(transcript: str) -> dict:
    """Profile a meeting transcript: speakers, talk share, length, and candidate commitment lines.

    Call first. Works with "Name: text" lines (optionally timestamped). Returns the lines
    containing commitment language so no action item is missed.

    Args:
        transcript: The raw meeting transcript text.
    """
    if not transcript.strip():
        raise ToolError("Transcript is empty.")
    if len(transcript) > 400_000:
        raise ToolError("Transcript too long (400k chars max). Split it into parts.")
    words_by_speaker: Counter[str] = Counter()
    candidates = []
    unattributed = 0
    for n, line in enumerate(transcript.splitlines(), 1):
        if not line.strip():
            continue
        m = SPEAKER_RE.match(line)
        speaker, said = (m.group(1).strip(), m.group(2)) if m else (None, line)
        if speaker:
            words_by_speaker[speaker] += len(text.words(said))
        else:
            unattributed += 1
        if COMMIT_RE.search(said):
            candidates.append({"line": n, "speaker": speaker, "text": said.strip()[:400]})
    total = sum(words_by_speaker.values()) or len(text.words(transcript))
    share = {s: round(100 * w / total, 1) for s, w in words_by_speaker.most_common()}
    return {
        "speakers": list(share),
        "talk_share_pct": share,
        "total_words": total,
        "estimated_minutes": round(len(text.words(transcript)) / 150),
        "commitment_candidates": candidates,
        "unattributed_lines": unattributed,
        "note": "Each candidate still needs judgement: confirm owner + deliverable in context.",
    }


def _resolve(phrase: str, base: date) -> tuple[date | None, str]:
    p = phrase.lower().strip()
    if re.search(r"\b(today|eod|end of (the )?day)\b", p) and "tomorrow" not in p:
        return base, "same day"
    if "tomorrow" in p:
        return base + timedelta(days=1), "next day"
    m = re.search(r"\bin (\d+|a|one|two|three|four) (day|week|month)s?\b", p)
    if m:
        n = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4}.get(m.group(1)) or int(m.group(1))
        unit = m.group(2)
        days = n * {"day": 1, "week": 7, "month": 30}[unit]
        return base + timedelta(days=days), f"+{n} {unit}(s)"
    m = re.search(r"\bin (\d+) business days?\b", p)
    if m:
        return dates.add_business_days(base, int(m.group(1))), "business days"
    if re.search(r"\b(eow|end of (?:the |next )?week)\b", p):
        d = base + timedelta(days=(4 - base.weekday()) % 7)
        return (d + timedelta(days=7) if "next" in p else d), "Friday"
    if re.search(r"\bend of (the )?month|eom\b", p):
        nxt = (base.replace(day=28) + timedelta(days=4)).replace(day=1)
        return nxt - timedelta(days=1), "last day of month"
    if re.search(r"\bnext week\b", p):
        return base + timedelta(days=7 - base.weekday()), "Monday next week"
    for i, day in enumerate(WEEKDAYS):
        if re.search(rf"\b{day[:3]}(?:{day[3:]})?\b", p):
            ahead = (i - base.weekday()) % 7 or 7
            if "next" in p and ahead < 7:
                ahead += 7
            return base + timedelta(days=ahead), day.title()
    m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", p)
    if m:
        return dates.parse_date(m.group(1)), "explicit"
    return None, "unrecognised — confirm with owner"


@AGENT.tool
def resolve_due_dates(phrases: list[str], meeting_date: str = "") -> dict:
    """Turn relative deadlines ("by Friday", "end of next week", "in 2 weeks") into calendar dates.

    Args:
        phrases: Deadline phrases exactly as spoken in the meeting.
        meeting_date: The meeting date as YYYY-MM-DD. Defaults to today.
    """
    base = dates.parse_date(meeting_date) if meeting_date else date.today()
    out = []
    for phrase in phrases[:100]:
        d, rule = _resolve(phrase, base)
        out.append({"phrase": phrase, "due": d.isoformat() if d else None, "weekday": d.strftime("%a") if d else None, "rule": rule})
    return {"meeting_date": base.isoformat(), "resolved": out}


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
