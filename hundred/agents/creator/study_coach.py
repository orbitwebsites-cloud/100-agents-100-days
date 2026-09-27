"""Study Coach — spaced repetition (real SM-2), review calendars, Anki-ready cards and focused study sessions."""

from __future__ import annotations

import csv
import io
import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from ...core import Agent, ToolError
from ...lib import dates, text
from ._common import parse_hhmm

AGENT = Agent(
    slug="study-coach",
    name="Study Coach",
    category="creator",
    tagline="Learn it once and keep it: SM-2 spaced repetition, review calendars, Anki-ready cards and focused sessions.",
    description=(
        "Applies learning science instead of cramming folklore: schedules reviews with a faithful SM-2 "
        "algorithm (the one Anki descends from), builds a review calendar that expands intervals and "
        "front-loads before an exam, converts notes into Anki-importable cards that pass the minimum-"
        "information rule, packs a study day into Pomodoro blocks with real clock times, and turns an "
        "exam date and topic list into a weekly hour plan with a buffer. Retrieval practice first, always."
    ),
    triggers=[
        "help me study for an exam",
        "make a spaced repetition schedule",
        "turn these notes into flashcards / Anki cards",
        "plan my study week / pomodoro session",
        "when should I review this again",
        "how many hours a week do I need to pass",
    ],
    examples=[
        "Exam on Dec 12, 6 topics, I can study 10 hours a week. Build the plan.",
        "Here are my lecture notes on the Krebs cycle — make Anki cards I can import.",
        "I reviewed 20 cards today and rated them; schedule the next reviews with SM-2.",
    ],
    connectors=["Notion", "Google Calendar", "Google Docs", "Todoist", "Anki", "Google Sheets"],
    playbook="""
    ## Standard
    You are a learning scientist who coaches students and professionals to retain what they
    learn. Excellent means the learner can retrieve the material weeks later without
    re-reading it. The metric that matters is **retention at test time**, which is driven by
    retrieval practice + spacing + interleaving — not by hours spent or highlighter used.
    Re-reading and summarising feel productive and are the weakest methods in the literature;
    you never prescribe them as the main activity.

    ## Intake
    You need: what is being learned, the deadline (if any), hours available per week, and the
    material (notes, syllabus, or topic list). Ask at most 3 questions; if there is no
    deadline, assume a 6-week horizon and say so. If the learner pastes notes, start from them.

    ## Procedure
    1. **Size the job.** With a deadline, call `study_coach__study_load` with the exam date,
       topics (weighted by exam share or difficulty) and weekly hours. It returns hours per
       topic, a week-by-week allocation, the buffer, and whether the hours are sufficient. If
       insufficient, say what to drop or triage by weight — do not pretend it fits.
    2. **Convert material into retrieval.** Turn notes into question-and-answer cards
       (one fact per card, answer ≤ 15 words, questions that force recall, not recognition).
       Then call `study_coach__anki_export`; it lints every card (too long, yes/no
       questions, duplicates, list answers that should be cloze) and returns a tab-separated
       file ready for Anki's importer. Fix the flagged cards before delivering.
    3. **Schedule first reviews.** For new topics call `study_coach__review_calendar` with
       the dates each topic is first learned and the exam date. It expands intervals
       (1, 3, 7, 14, 30 days), clips to the exam, adds a final pass 1-2 days before, and
       flags days that overload. Move first-learn dates if any day exceeds the cap.
    4. **After each review session,** when the learner reports card grades (0-5), call
       `study_coach__sm2_review`. It updates ease factor, interval and repetitions with the
       exact SM-2 rules and returns the next due date per card. Never approximate this: an
       LLM guessing "review in about a week" defeats the algorithm.
    5. **Build the session.** For a study day, call `study_coach__pomodoro_plan` with the
       start time, available minutes and the tasks. It packs work/break blocks with clock
       times, alternates topics for interleaving, and reports what did not fit. Each block
       starts with 5 min of retrieval on yesterday's material.
    6. **Deliver** in the output format. Push review dates to Google Calendar/Todoist and the
       card file to Anki (via file) if connected.

    ## Frameworks
    - **SM-2:** grade 0-5; < 3 resets repetitions and interval to 1 day; interval sequence
      1 → 6 → previous × ease; ease' = ease + 0.1 − (5 − q)(0.08 + (5 − q) × 0.02), floor 1.3.
    - **Spacing schedule for new material:** 1, 3, 7, 14, 30 days, then monthly. Reviews are
      retrieval attempts, not re-reads: cover the answer, produce it, check.
    - **Interleaving:** alternate 2-3 topics within a session rather than blocking one; it
      feels harder and tests better.
    - **Card rules (Wozniak's 20 rules, the ones that matter):** minimum information; one
      answer per card; cloze for lists and definitions; add "why" cards, not just "what";
      no yes/no questions; 8-second answers.
    - **Session design:** 25/5 Pomodoros for most people, 50/10 for deep problem sets; a
      long break every 4 blocks; hard topic first when fresh; end each session by writing
      three questions to answer tomorrow.
    - **Exam week:** no new material in the last 48 h; full-length practice under time;
      sleep is part of the schedule (consolidation happens during it).

    ## Output format
    ```
    # Study plan — <subject> · exam <date> (<N> days) · <hours>/wk
    **Verdict:** <fits / short by N h> · **Buffer:** <days> · **Method:** retrieval + spacing + interleaving

    ## Weekly allocation
    | Week | Dates | Topics (hours) | Milestone |

    ## Review calendar
    | Date | Topic reviews (retrieval) | Load |

    ## Cards (<N>, Anki import attached)
    <3 example cards> … lint: <issues fixed>

    ## Today's session (<start>-<end>)
    | Block | Time | Task | Type |

    ## Rules
    - Cover, recall, check. No re-reading as study.
    - Miss a review → do it the next day, don't double up.
    - Last 48 h: practice tests and sleep only.
    ```

    ## Anti-patterns
    - "Read chapters 1-4 on Monday." Reading is intake, not study; pair every chapter with cards or practice questions.
    - Cards that are paragraphs. If the answer is over 15 words, split the card.
    - Blocking one topic per week. Interleave; the plan tool alternates for a reason.
    - Scheduling reviews by feel. SM-2 is deterministic; use the tool.
    - Cramming to 2 am before the exam. Sleep is when the memory consolidates.
    - A plan with zero buffer. Life happens; the load tool holds days back for it.
    """,
)


@AGENT.tool
def sm2_review(cards: list[dict], review_date: str = "") -> dict:
    """Apply the SM-2 spaced-repetition algorithm to graded cards and return each card's new ease, interval and due date.

    Grades: 5 perfect, 4 correct after hesitation, 3 correct with difficulty, 2 wrong but
    recognised, 1 wrong but familiar, 0 blackout. Below 3 resets the card to a 1-day interval.

    Args:
        cards: List of {"id": "card-1", "quality": 4, "repetitions": 2, "interval_days": 6, "ease": 2.5}; repetitions/interval_days/ease default to 0/0/2.5 for new cards.
        review_date: Date of the review as YYYY-MM-DD (default today).
    """
    if not cards or len(cards) > 5000:
        raise ToolError("Give 1-5000 cards")
    base = dates.parse_date(review_date) if review_date else date.today()
    out, due_counter = [], Counter()
    lapses = 0
    for i, c in enumerate(cards, 1):
        if not isinstance(c, dict) or "quality" not in c:
            raise ToolError(f"card #{i} needs a 'quality' grade 0-5")
        q = c["quality"]
        if not isinstance(q, int) or not 0 <= q <= 5:
            raise ToolError(f"card #{i}: quality must be an integer 0-5")
        reps = c.get("repetitions", 0)
        interval = c.get("interval_days", 0)
        ease = c.get("ease", 2.5)
        if not isinstance(reps, int) or reps < 0 or not isinstance(interval, (int, float)) or interval < 0 or not isinstance(ease, (int, float)) or ease < 1.3:
            raise ToolError(f"card #{i}: repetitions ≥ 0, interval_days ≥ 0, ease ≥ 1.3")
        ease_new = max(1.3, ease + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        if q < 3:
            reps_new, interval_new = 0, 1
            lapses += 1
        else:
            reps_new = reps + 1
            if reps_new == 1:
                interval_new = 1
            elif reps_new == 2:
                interval_new = 6
            else:
                interval_new = int(round(interval * ease_new))
        interval_new = max(1, interval_new)
        due = base + timedelta(days=interval_new)
        due_counter[due.isoformat()] += 1
        out.append({
            "id": c.get("id", f"card-{i}"),
            "quality": q,
            "repetitions": reps_new,
            "interval_days": interval_new,
            "ease": round(ease_new, 2),
            "due": due.isoformat(),
            "status": "relearn" if q < 3 else "learning" if reps_new < 3 else "review",
        })
    return {
        "review_date": base.isoformat(),
        "cards": out,
        "lapses": lapses,
        "lapse_rate_pct": round(100 * lapses / len(out), 1),
        "due_by_date": dict(sorted(due_counter.items())),
        "next_review_date": min(due_counter) if due_counter else None,
        "summary": f"{len(out)} cards graded, {lapses} lapse(s) ({100 * lapses / len(out):.0f}%); next review {min(due_counter)}." + (" Lapse rate over 20%: cards are too big or reviews too sparse." if lapses / len(out) > 0.2 else ""),
    }


@AGENT.tool
def review_calendar(topics: list[dict], exam_date: str = "", intervals: list[int] | None = None, max_reviews_per_day: int = 4) -> dict:
    """Build a dated review calendar for newly learned topics with expanding intervals, clipped to an exam with a final pass.

    Args:
        topics: List of {"topic": "Krebs cycle", "learned_on": "YYYY-MM-DD"}.
        exam_date: Optional exam date YYYY-MM-DD; reviews after it are dropped and a final pass is added 2 days before.
        intervals: Days after learning to review; default [1, 3, 7, 14, 30].
        max_reviews_per_day: Days with more topic reviews than this are flagged (default 4).
    """
    if not topics or len(topics) > 300:
        raise ToolError("Give 1-300 topics")
    ivs = intervals or [1, 3, 7, 14, 30]
    if not all(isinstance(x, int) and 1 <= x <= 365 for x in ivs) or ivs != sorted(ivs) or len(set(ivs)) != len(ivs):
        raise ToolError("intervals must be ascending, unique integers between 1 and 365")
    if max_reviews_per_day < 1:
        raise ToolError("max_reviews_per_day must be ≥ 1")
    exam = dates.parse_date(exam_date) if exam_date else None
    by_day: dict[str, list[str]] = defaultdict(list)
    per_topic = []
    for i, t in enumerate(topics, 1):
        if not isinstance(t, dict) or not t.get("topic") or not t.get("learned_on"):
            raise ToolError(f"topic #{i} needs 'topic' and 'learned_on'")
        learned = dates.parse_date(str(t["learned_on"]))
        if exam and learned >= exam:
            raise ToolError(f"{t['topic']}: learned_on is on/after the exam date")
        reviews = []
        for k, iv in enumerate(ivs, 1):
            d = learned + timedelta(days=iv)
            if exam and d >= exam - timedelta(days=1):
                break
            reviews.append(d)
            by_day[d.isoformat()].append(str(t["topic"]))
        if exam:
            final = exam - timedelta(days=2)
            if final > learned and (not reviews or reviews[-1] != final):
                reviews.append(final)
                by_day[final.isoformat()].append(f"{t['topic']} (final pass)")
        per_topic.append({"topic": str(t["topic"]), "learned_on": learned.isoformat(), "reviews": [d.isoformat() for d in reviews], "review_count": len(reviews)})
    calendar = [{"date": d, "weekday": dates.parse_date(d).strftime("%a"), "reviews": v, "load": len(v)} for d, v in sorted(by_day.items())]
    overloaded = [c for c in calendar if c["load"] > max_reviews_per_day]
    flags = [f"{c['date']} has {c['load']} reviews (> {max_reviews_per_day}). Stagger first-learn dates or split the session." for c in overloaded[:10]]
    if exam:
        late = [t for t in per_topic if (exam - dates.parse_date(t["learned_on"])).days < 7]
        if late:
            flags.append(f"{len(late)} topic(s) learned under 7 days before the exam get fewer than 3 spaced reviews — prioritise them in the final pass.")
    return {
        "exam_date": exam.isoformat() if exam else None,
        "intervals_days": ivs,
        "topics": per_topic,
        "calendar": calendar,
        "total_reviews": sum(c["load"] for c in calendar),
        "busiest_day": max(calendar, key=lambda c: c["load"])["date"] if calendar else None,
        "flags": flags,
        "summary": f"{sum(c['load'] for c in calendar)} reviews across {len(calendar)} days for {len(per_topic)} topics" + (f", final pass {(exam - timedelta(days=2)).isoformat()}." if exam else ".") + (" " + flags[0] if flags else ""),
    }


YES_NO_RE = re.compile(r"^\s*(is|are|does|do|did|can|could|was|were|will|would|should|has|have|had)\b", re.I)
LIST_RE = re.compile(r"(,\s*[^,]+){3,}|\b(and|&)\b.*\b(and|&)\b|;\s*\S+;|\b\d\)\s|\n\s*[-*•]")


@AGENT.tool
def anki_export(cards: list[dict], deck: str = "Study", separator: str = "tab") -> dict:
    """Lint flashcards against minimum-information rules and return an Anki-importable text file (front, back, tags).

    Flags long fronts/backs, yes/no questions, list answers that should be cloze cards,
    duplicates and empties; escapes quotes, separators and newlines so the import never breaks.

    Args:
        cards: List of {"front": "What enzyme…?", "back": "Citrate synthase", "tags": ["biochem"] (optional)}.
        deck: Deck name written into the file header (default "Study").
        separator: "tab" (default, safest) or "comma".
    """
    if not cards or len(cards) > 2000:
        raise ToolError("Give 1-2000 cards")
    if separator not in ("tab", "comma"):
        raise ToolError("separator must be 'tab' or 'comma'")
    delim = "\t" if separator == "tab" else ","
    buf = io.StringIO()
    buf.write("#separator:" + ("tab" if delim == "\t" else "comma") + "\n#html:false\n#tags column:3\n" + f"#deck:{deck}\n")
    writer = csv.writer(buf, delimiter=delim, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    issues, seen = [], {}
    clean = 0
    for i, c in enumerate(cards, 1):
        if not isinstance(c, dict):
            raise ToolError(f"card #{i} must be a dict with 'front' and 'back'")
        front = str(c.get("front", "")).strip()
        back = str(c.get("back", "")).strip()
        tags = c.get("tags", [])
        if isinstance(tags, str):
            tags = tags.split()
        if not front or not back:
            issues.append({"card": i, "type": "empty", "detail": "front and back are both required"})
            continue
        card_issues = []
        fw, bw = len(text.words(front)), len(text.words(back))
        if fw > 30:
            card_issues.append(f"front is {fw} words — over 30; strip context, ask one thing")
        if bw > 15:
            card_issues.append(f"back is {bw} words — over 15; split into several cards or use cloze")
        if YES_NO_RE.match(front) and "?" in front:
            card_issues.append("yes/no question — rewrite as 'what/why/how' so the answer must be produced")
        if LIST_RE.search(back) and bw >= 6:
            card_issues.append("answer is a list — make one cloze card per item ({{c1::…}}) instead")
        key = re.sub(r"\W+", " ", front.lower()).strip()
        if key in seen:
            card_issues.append(f"duplicate of card #{seen[key]}")
        else:
            seen[key] = i
        if not front.rstrip().endswith("?") and not re.search(r"\{\{c\d+::", front) and fw <= 3:
            card_issues.append("front is a bare term — 'What is X?' or a cloze sentence gives the recall a cue")
        writer.writerow([front.replace("\n", "<br>"), back.replace("\n", "<br>"), " ".join(str(t).replace(" ", "_") for t in tags)])
        if card_issues:
            issues.append({"card": i, "type": "quality", "detail": "; ".join(card_issues)})
        else:
            clean += 1
    exported = len(cards) - sum(1 for x in issues if x["type"] == "empty")
    return {
        "deck": deck,
        "cards_exported": exported,
        "cards_clean": clean,
        "issues": issues,
        "file_name": f"{re.sub(r'[^A-Za-z0-9_-]+', '_', deck)}.txt",
        "file_content": buf.getvalue(),
        "import_steps": "Anki → File → Import → choose the .txt; the header lines set separator, deck and the tags column automatically; field 1 = Front, field 2 = Back.",
        "verdict": f"{exported} cards exported, {clean} clean, {len(issues)} with issues." + (" Fix the flagged cards first — bad cards get reviewed forever." if issues else ""),
    }


@AGENT.tool
def pomodoro_plan(
    start_time: str,
    available_minutes: int,
    tasks: list[dict],
    work_minutes: int = 25,
    short_break: int = 5,
    long_break: int = 15,
    blocks_per_cycle: int = 4,
    interleave: bool = True,
) -> dict:
    """Pack tasks into timed Pomodoro blocks with clock times, alternating topics for interleaving, and report what doesn't fit.

    Args:
        start_time: Session start as HH:MM (24h).
        available_minutes: Total minutes available including breaks (15-720).
        tasks: List of {"name": "Krebs cycle cards", "minutes": 50, "priority": 1} — lower priority number = do first.
        work_minutes: Length of a work block (default 25; use 50 for problem sets).
        short_break: Minutes between blocks (default 5).
        long_break: Minutes after every blocks_per_cycle blocks (default 15).
        blocks_per_cycle: Blocks before a long break (default 4).
        interleave: Alternate between tasks block by block (default True) instead of finishing one task first.
    """
    h, m = parse_hhmm(start_time)
    if not 15 <= available_minutes <= 720:
        raise ToolError("available_minutes must be 15-720")
    if not (10 <= work_minutes <= 90 and 0 <= short_break <= 30 and 0 <= long_break <= 60 and 1 <= blocks_per_cycle <= 8):
        raise ToolError("work 10-90, short break 0-30, long break 0-60, blocks_per_cycle 1-8")
    if not tasks or len(tasks) > 40:
        raise ToolError("Give 1-40 tasks")
    queue = []
    for i, t in enumerate(tasks, 1):
        if not isinstance(t, dict) or not t.get("name"):
            raise ToolError(f"task #{i} needs a 'name'")
        mins = t.get("minutes", work_minutes)
        if not isinstance(mins, (int, float)) or mins <= 0:
            raise ToolError(f"{t['name']}: minutes must be > 0")
        blocks = max(1, math.ceil(mins / work_minutes))
        queue.append({"name": str(t["name"]), "priority": t.get("priority", i), "blocks_left": blocks, "blocks_done": 0, "minutes": mins})
    queue.sort(key=lambda t: (t["priority"], t["name"]))
    clock = datetime(2000, 1, 1, h, m)
    elapsed = 0
    schedule = []
    block_n = 0
    idx = 0
    while True:
        active = [t for t in queue if t["blocks_left"] > 0]
        if not active or elapsed + work_minutes > available_minutes:
            break
        task = active[idx % len(active)] if interleave else active[0]
        block_n += 1
        end = clock + timedelta(minutes=work_minutes)
        schedule.append({"block": block_n, "start": clock.strftime("%H:%M"), "end": end.strftime("%H:%M"), "type": "work", "task": task["name"], "note": "first 5 min: retrieval on the previous block/yesterday"})
        task["blocks_left"] -= 1
        task["blocks_done"] += 1
        clock, elapsed = end, elapsed + work_minutes
        idx += 1
        still = [t for t in queue if t["blocks_left"] > 0]
        if not still or elapsed + work_minutes > available_minutes:
            break
        br = long_break if block_n % blocks_per_cycle == 0 else short_break
        if br and elapsed + br + work_minutes <= available_minutes:
            end = clock + timedelta(minutes=br)
            schedule.append({"block": block_n, "start": clock.strftime("%H:%M"), "end": end.strftime("%H:%M"), "type": "long break" if br == long_break and block_n % blocks_per_cycle == 0 else "break", "task": "", "note": "away from the desk; no screens"})
            clock, elapsed = end, elapsed + br
    unfinished = [{"name": t["name"], "blocks_left": t["blocks_left"], "minutes_left": t["blocks_left"] * work_minutes} for t in queue if t["blocks_left"] > 0]
    work_total = sum(work_minutes for s in schedule if s["type"] == "work")
    return {
        "start": start_time,
        "end": clock.strftime("%H:%M"),
        "work_blocks": block_n,
        "focused_minutes": work_total,
        "break_minutes": elapsed - work_total,
        "unused_minutes": available_minutes - elapsed,
        "schedule": schedule,
        "unfinished": unfinished,
        "per_task": [{"name": t["name"], "blocks": t["blocks_done"], "minutes": t["blocks_done"] * work_minutes} for t in queue],
        "summary": f"{block_n} × {work_minutes}-min blocks ({work_total} focused min) from {start_time} to {clock.strftime('%H:%M')}" + (f"; {len(unfinished)} task(s) carry over ({sum(u['minutes_left'] for u in unfinished)} min)." if unfinished else "; everything fits."),
    }


@AGENT.tool
def study_load(exam_date: str, topics: list[dict], hours_per_week: float, today: str = "", buffer_days: int = 2, max_hours_per_day: float = 4) -> dict:
    """Turn an exam date, weighted topics and weekly hours into hours per topic, a week-by-week allocation and a fit verdict.

    Reserves buffer days and the final 2 days for practice tests, caps daily hours, and says
    plainly whether the available hours cover the estimated need.

    Args:
        exam_date: Exam date YYYY-MM-DD.
        topics: List of {"topic": "Thermodynamics", "weight": 30 (share of exam or difficulty), "hours_needed": 8 (optional estimate)}.
        hours_per_week: Study hours available per week.
        today: Start date YYYY-MM-DD (default today).
        buffer_days: Days held back for slippage (default 2).
        max_hours_per_day: Cap on study hours in a day (default 4).
    """
    exam = dates.parse_date(exam_date)
    start = dates.parse_date(today) if today else date.today()
    if exam <= start:
        raise ToolError("exam_date must be after today")
    if hours_per_week <= 0 or hours_per_week > 80:
        raise ToolError("hours_per_week must be between 0 and 80")
    if not topics or len(topics) > 60:
        raise ToolError("Give 1-60 topics")
    if buffer_days < 0 or max_hours_per_day <= 0:
        raise ToolError("buffer_days ≥ 0 and max_hours_per_day > 0")
    days_left = (exam - start).days
    practice_days = 2 if days_left > 7 else 1
    study_days = max(0, days_left - buffer_days - practice_days)
    available = min(study_days * hours_per_week / 7, study_days * max_hours_per_day)
    parsed, total_w, needed = [], 0.0, 0.0
    for i, t in enumerate(topics, 1):
        if not isinstance(t, dict) or not t.get("topic"):
            raise ToolError(f"topic #{i} needs a 'topic'")
        w = float(t.get("weight", 1) or 1)
        if w <= 0:
            raise ToolError(f"{t['topic']}: weight must be > 0")
        hn = t.get("hours_needed")
        if hn is not None and (not isinstance(hn, (int, float)) or hn < 0):
            raise ToolError(f"{t['topic']}: hours_needed must be ≥ 0")
        parsed.append({"topic": str(t["topic"]), "weight": w, "hours_needed": float(hn) if hn is not None else None})
        total_w += w
        if hn is not None:
            needed += float(hn)
    has_estimates = all(p["hours_needed"] is not None for p in parsed)
    for p in parsed:
        p["share_pct"] = round(100 * p["weight"] / total_w, 1)
        p["hours_allocated"] = round(available * p["weight"] / total_w, 1)
    weeks = max(1, math.ceil(study_days / 7))
    plan = []
    d = start
    for w in range(1, weeks + 1):
        wk_days = min(7, study_days - 7 * (w - 1))
        if wk_days <= 0:
            break
        wk_hours = min(wk_days * hours_per_week / 7, wk_days * max_hours_per_day)
        # early weeks: heavier on high-weight topics; final week: everything, lighter, retrieval-focused
        alloc = {p["topic"]: round(wk_hours * p["weight"] / total_w, 1) for p in parsed}
        plan.append({"week": w, "from": d.isoformat(), "to": (d + timedelta(days=wk_days - 1)).isoformat(), "hours": round(wk_hours, 1), "topics": alloc, "focus": "learn + cards" if w < weeks else "retrieval + mixed practice"})
        d += timedelta(days=wk_days)
    flags = []
    if has_estimates and needed > available:
        flags.append(f"Short by {needed - available:.1f} h: need {needed:.0f} h, have {available:.0f} h. Raise weekly hours to {needed * 7 / max(1, study_days):.1f} or triage the lowest-weight topics.")
    if hours_per_week / 7 > max_hours_per_day:
        flags.append(f"{hours_per_week:g} h/week exceeds the {max_hours_per_day:g} h/day cap — capped; add days rather than hours.")
    if days_left <= 3:
        flags.append("Under 3 days: no new material; practice tests, targeted review of weak topics, and sleep.")
    if study_days and available / study_days < 0.5:
        flags.append("Under 30 min/day average — fine for maintenance, not for learning new topics.")
    return {
        "today": start.isoformat(),
        "exam_date": exam.isoformat(),
        "days_left": days_left,
        "study_days": study_days,
        "buffer_days": buffer_days,
        "practice_test_days": practice_days,
        "hours_available": round(available, 1),
        "hours_needed": round(needed, 1) if has_estimates else None,
        "fits": (needed <= available) if has_estimates else None,
        "topics": parsed,
        "weekly_plan": plan,
        "final_48h": f"{(exam - timedelta(days=practice_days)).isoformat()} → {exam.isoformat()}: practice tests only, then sleep.",
        "flags": flags,
        "verdict": f"{days_left} days to the exam, {study_days} study days, {available:.0f} h available" + (f" vs {needed:.0f} h needed — {'fits' if needed <= available else 'DOES NOT fit'}." if has_estimates else ".") + (" " + " ".join(flags) if flags else ""),
    }
