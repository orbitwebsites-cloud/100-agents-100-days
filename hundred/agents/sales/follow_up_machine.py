"""Follow-Up Machine — the right follow-up, on the right date, with a reason to reply; and a stale-deal radar so nothing goes quiet."""

from __future__ import annotations

import re
from datetime import timedelta

from ...core import Agent, ToolError
from ...lib import dates, text
from . import _common as c

AGENT = Agent(
    slug="follow-up-machine",
    name="Follow-Up Machine",
    category="sales",
    tagline="Never lose a deal to silence: dated follow-up cadences, value-add follow-ups scored before sending, and a stale-deal radar.",
    description=(
        "Runs the follow-up discipline most reps abandon after touch two. Computes cadence dates on business "
        "days from the last contact, decides for each deal whether to follow up now, wait, send a breakup or "
        "close it, scores every follow-up email against the 'just checking in' failure modes (length, new "
        "value, single ask), and scans a pipeline for deals gone quiet by stage-specific thresholds so the "
        "rep's day starts with the right list."
    ),
    triggers=[
        "write a follow-up email to a prospect who went quiet",
        "when should I follow up / follow-up cadence",
        "which of my deals are stale or need a touch today",
        "write a breakup email",
        "review my follow-up email before I send it",
        "build a follow-up schedule after a demo / proposal",
    ],
    examples=[
        "Sent the proposal on Sept 18, no reply. Draft the follow-up and tell me when the next three touches go out.",
        "Here's my open-deal list with last-activity dates. Who do I chase today?",
        "Is this follow-up any good? 'Hi Tom, just checking in to see if you had a chance to look at the proposal…'",
        "Prospect ghosted after a great demo 3 weeks ago. Breakup email or one more try?",
    ],
    connectors=["Gmail", "Outlook", "HubSpot", "Salesforce", "Pipedrive", "Google Calendar", "Slack"],
    playbook="""
    ## Standard
    You are the rep whose follow-ups get answered because each one gives the prospect a
    reason to reply that they didn't have yesterday. Excellent follow-up is timed, short,
    adds something (a number, an answer to a question they asked, a relevant change),
    makes one ask, and stops gracefully at the right moment. The one metric: **reply
    rate on follow-ups** — and its silent twin, deals that go quiet without anyone
    noticing. Most replies in a sequence come from touches 2-5; most reps stop at 2.

    ## Intake
    You need: what the last touch was and when (date), the deal stage, what the
    prospect last said or asked, and any date they mentioned ("back to you after the
    board meeting on the 14th"). If the last-contact date is missing, ask for it — one
    question — because every cadence date depends on it. Otherwise proceed.

    ## Procedure
    1. **Decide the move.** Call `follow_up_machine__next_touch_decision` with the
       stage, last contact/reply dates, touches since the last reply, and any promised
       date. It returns one of: follow up now / wait until <date> / send breakup / close
       and nurture, with the reasoning. Never send a breakup before 4 unanswered touches
       and never chase a prospect before a date they themselves gave you.
    2. **Schedule the cadence.** Call `follow_up_machine__cadence_dates` with the last
       contact date, stage, `today`, and `touches_done` (= touches already sent since
       their last reply — the same number you gave the decision tool), so the plan
       continues the sequence instead of restarting it and never dates a touch in the past. It returns the dated touch plan (business days, weekends
       and holidays skipped, gaps widening: 2-3-5-7-14 days) with the channel for each
       touch (email → call → LinkedIn → email → breakup). Put the dates on the calendar
       or in the CRM if a connector exists.
    3. **Write the follow-up** with the structure: context (one line tying to the last
       exchange) → new value (the reason to reply today) → one ask with an easy
       yes/no or a date. Under 75 words for a follow-up; under 50 for a breakup.
    4. **Score it.** Call `follow_up_machine__score_follow_up` on the draft. It fails
       "just checking in / touching base / circling back", flags missing new value,
       multiple asks, length, guilt language ("I haven't heard back"), and
       unresolved tokens. Rewrite until it scores ≥ 80.
    5. **Radar the pipeline** when the user gives a deal list: call
       `follow_up_machine__stale_deals` with the deals and today's date. It applies
       stage-specific silence thresholds (e.g. proposal 5 business days, negotiation 3,
       discovery 10), ranks by amount × staleness, and returns today's chase list with
       the recommended touch per deal.
    6. **Deliver** in the output format: the decision, the email(s) with word counts,
       the dated cadence, and (for lists) the chase list ordered by priority.

    ## Frameworks
    - **The value-add ladder** (pick one per touch): answer to their question ·
      relevant number/benchmark · short case example · a change on their side (hire,
      news) · a resource tied to what they said · a simpler next step (shorter meeting,
      pilot) · the breakup.
    - **Cadence by stage:** after discovery: 2 → 5 → 10 business days; after demo:
      1 → 3 → 6 → 10; after proposal: 2 → 4 → 7 → 12; in negotiation: 1 → 2 → 4.
      Widen, never tighten. Alternate channels: email, phone, LinkedIn, video note.
    - **Breakup rules:** send after ≥ 4 unanswered touches and ≥ 14 days of silence.
      Tone: assume they're busy, not rude; give an easy out; leave one door open. Breakup
      emails often out-reply every other touch — because they're easy to answer.
    - **Promised dates:** if the prospect said "after the 14th", touch on the 15th (next
      business day), referencing their words. Chasing early signals you didn't listen.
    - **Stale thresholds (business days without any activity):** negotiation 3, proposal
      5, demo/evaluation 7, discovery 10, qualification 14. Beyond 2× the threshold, the
      deal is at risk and should be re-forecast.
    - **Subject lines for follow-ups:** reply in the same thread ("Re: …") for touches
      1-3; a fresh, specific subject for the breakup.

    ## Output format
    ```
    ## Decision
    <follow up now | wait until <date> | breakup | close & nurture> — <reason>

    ## Follow-up (<n> words) — send <date> via <channel>
    Subject: <Re: … | specific>
    <body>
    _score <n>/100 · value-add: <type> · one ask_

    ## Cadence
    | Touch | Date | Channel | Angle |
    |---|---|---|---|

    ## Chase list (if a pipeline was given)
    | Priority | Deal | Stage | Amount | Days quiet | Threshold | Action |
    ```

    ## Anti-patterns
    - "Just checking in", "touching base", "circling back", "bumping this" — zero value, zero reply.
    - Guilt: "I haven't heard back from you", "I've tried several times". It reads as blame.
    - Follow-ups longer than the original email.
    - Same channel five times. Switch.
    - Chasing before the date the prospect gave you.
    - Breaking up at touch 2 — or never breaking up and rotting the pipeline.
    - Following up with "any update?" — ask a question they can answer in one line.
    """,
)

STAGE_CADENCE = {
    "qualification": [3, 5, 10, 14],
    "discovery": [2, 5, 10, 14],
    "demo": [1, 3, 6, 10],
    "evaluation": [2, 4, 7, 12],
    "proposal": [2, 4, 7, 12],
    "negotiation": [1, 2, 4, 7],
    "post_meeting": [1, 3, 6, 10],
    "cold": [3, 4, 5, 7],
}
CHANNELS = ["email", "phone", "linkedin", "email", "breakup email"]
ANGLES = ["answer/recap + one question", "call: 'quick one — is X still the priority?'", "LinkedIn: comment/DM tied to their post or news", "new value: number, example or simpler next step", "breakup: easy out, one door open"]
STALE_THRESHOLDS = {"negotiation": 3, "proposal": 5, "evaluation": 7, "demo": 7, "discovery": 10, "qualification": 14}


def _stage(s: str) -> str:
    s = (s or "").strip().lower()
    for key in STAGE_CADENCE:
        if key in s:
            return key
    if "meeting" in s or "call" in s:
        return "post_meeting"
    if "contract" in s or "legal" in s or "verbal" in s:
        return "negotiation"
    return "discovery"


@AGENT.tool
def cadence_dates(last_contact: str, stage: str = "proposal", touches: int = 5, holidays: list[str] | None = None, promised_date: str = "", today: str = "", touches_done: int = 0) -> dict:
    """Compute dated follow-up touches on business days from the last contact, with widening gaps and channel rotation.

    Call after deciding to follow up. Gaps depend on stage (proposal: 2, 4, 7, 12 business days;
    negotiation tighter; discovery looser). If the prospect promised a date, the first touch is the next
    business day after it.

    Args:
        last_contact: Date of your last touch, YYYY-MM-DD.
        stage: Deal stage: qualification, discovery, demo, evaluation, proposal, negotiation, post_meeting or cold.
        touches: Number of touches to schedule, 1-6 (default 5, the last being the breakup).
        holidays: Dates to skip, YYYY-MM-DD.
        promised_date: A date the prospect said they'd respond by (YYYY-MM-DD), if any.
        today: As-of date YYYY-MM-DD (default today). A touch that would fall before it is moved to today (it is overdue).
        touches_done: Unanswered touches already sent since their last reply (0-5); the plan continues the gap and channel sequence from there instead of restarting at touch 1.
    """
    last = dates.parse_date(last_contact)
    if not 1 <= touches <= 6:
        raise ToolError("touches must be 1-6.")
    if not 0 <= touches_done <= 5:
        raise ToolError("touches_done must be 0-5.")
    asof = c.to_date(today)
    if last > asof:
        raise ToolError("last_contact is after today.")
    hols = c.parse_holidays(holidays or [])
    st = _stage(stage)
    gaps = STAGE_CADENCE[st]
    plan = []
    cursor = last
    promised_first = False
    if promised_date:
        pd = dates.parse_date(promised_date)
        if pd < last:
            raise ToolError("promised_date is before last_contact.")
        cursor = pd  # first touch = next business day after the promised date
        promised_first = True
    overdue_note = None
    for i in range(touches):
        n = touches_done + i  # 0-based position in the whole cadence
        gap = gaps[n] if n < len(gaps) else gaps[-1]
        if i == 0 and promised_first:
            gap = 1
        d = dates.add_business_days(cursor, gap, hols)
        if i == 0 and d < asof:
            overdue_note = f"touch {n + 1} was due {d.isoformat()} — overdue, send it today"
            d = asof
            while d.weekday() >= 5 or d in hols:
                d = dates.add_business_days(d, 1, hols)
        idx = min(n, len(CHANNELS) - 1)
        is_last = i == touches - 1 and touches_done + touches >= 4
        plan.append({
            "touch": n + 1,
            "date": d.isoformat(),
            "weekday": d.strftime("%a"),
            "business_days_after_previous": dates.business_days_between(cursor, d, hols),
            "calendar_days_after_last_contact": (d - last).days,
            "channel": "breakup email" if is_last else CHANNELS[idx],
            "angle": ANGLES[-1] if is_last else ANGLES[idx],
        })
        cursor = d
    return {
        "stage": st,
        "last_contact": last.isoformat(),
        "promised_date": promised_date or None,
        "touches": plan,
        "span_calendar_days": plan[-1]["calendar_days_after_last_contact"],
        "overdue": overdue_note,
        "stop_rule": "Any reply resets the cadence; a meeting booked ends it.",
        "verdict": (overdue_note + ". " if overdue_note else "") + f"{touches} touches from {plan[0]['date']} to {plan[-1]['date']} ({plan[-1]['calendar_days_after_last_contact']} days), gaps {', '.join(str(p['business_days_after_previous']) for p in plan)} business days.",
    }


@AGENT.tool
def next_touch_decision(stage: str, last_contact: str, last_reply: str = "", touches_since_reply: int = 1, today: str = "", promised_date: str = "", deal_amount: float = 0.0) -> dict:
    """Decide the next move for one deal: follow up now, wait until a date, send the breakup, or close and nurture.

    Call before writing anything. Uses the stage cadence, the silence length, the touch count and any promised date.

    Args:
        stage: Deal stage (qualification, discovery, demo, evaluation, proposal, negotiation, post_meeting, cold).
        last_contact: Date of your last outbound touch, YYYY-MM-DD.
        last_reply: Date of the prospect's last reply, YYYY-MM-DD (blank if never).
        touches_since_reply: Unanswered touches sent since their last reply (0-20).
        today: As-of date YYYY-MM-DD (default today).
        promised_date: Date the prospect said they'd get back to you, if any.
        deal_amount: Deal value (used for the effort recommendation).
    """
    st = _stage(stage)
    last = dates.parse_date(last_contact)
    asof = c.to_date(today)
    if last > asof:
        raise ToolError("last_contact is in the future.")
    if not 0 <= touches_since_reply <= 20:
        raise ToolError("touches_since_reply must be 0-20.")
    if deal_amount < 0:
        raise ToolError("deal_amount cannot be negative.")
    reply = dates.parse_date(last_reply) if last_reply else None
    silent_days = (asof - (reply or last)).days
    since_touch_bd = dates.business_days_between(last, asof)
    gaps = STAGE_CADENCE[st]
    due_gap = gaps[min(touches_since_reply, len(gaps) - 1)]
    reasons = []
    if promised_date:
        pd = dates.parse_date(promised_date)
        if asof <= pd:
            nxt = dates.add_business_days(pd, 1)
            return {"decision": "wait", "wait_until": nxt.isoformat(), "silent_days": silent_days, "touches_since_reply": touches_since_reply, "reason": f"They said they'd respond by {pd.isoformat()}; touch on {nxt.isoformat()} referencing their words.", "verdict": f"Wait until {nxt.isoformat()} — chasing before a promised date signals you didn't listen."}
        reasons.append(f"promised date {pd.isoformat()} has passed")
    if touches_since_reply >= 5 and silent_days >= 21:
        decision, reason = "close_and_nurture", f"{touches_since_reply} unanswered touches over {silent_days} days — the breakup went unanswered; move to nurture, re-engage on a trigger"
    elif touches_since_reply >= 4 and silent_days >= 14:
        decision, reason = "breakup", f"{touches_since_reply} unanswered touches and {silent_days} days of silence — send the breakup (≤ 50 words, easy out, one door open)"
    elif since_touch_bd >= due_gap:
        decision, reason = "follow_up_now", f"{since_touch_bd} business days since your last touch ≥ the {due_gap}-day gap for touch {touches_since_reply + 1} in {st}"
    else:
        nxt = dates.add_business_days(last, due_gap)
        decision, reason = "wait", f"only {since_touch_bd} business days since the last touch; touch {touches_since_reply + 1} is due {nxt.isoformat()}"
    out = {
        "decision": decision,
        "stage": st,
        "silent_days": silent_days,
        "business_days_since_last_touch": since_touch_bd,
        "touches_since_reply": touches_since_reply,
        "next_gap_business_days": due_gap,
        "reason": "; ".join(reasons + [reason]),
        "channel": ("breakup email" if decision == "breakup" else CHANNELS[min(touches_since_reply, len(CHANNELS) - 2)]),
        "value_add_hint": ANGLES[min(touches_since_reply, len(ANGLES) - 1)],
    }
    if decision == "wait":
        out["wait_until"] = dates.add_business_days(last, due_gap).isoformat()
    if deal_amount >= 25_000 and decision in ("follow_up_now", "breakup"):
        out["effort"] = "high-value deal: use phone or a 60-second video note before an email"
    out["verdict"] = {"follow_up_now": "Follow up today", "wait": f"Wait until {out.get('wait_until')}", "breakup": "Send the breakup", "close_and_nurture": "Close-lost / nurture"}[decision] + f" — {reason}."
    return out


CHECKIN_RE = re.compile(r"\b(just (?:checking|following up|touching base|circling|wanted to|reaching out)|checking in|touching base|circling back|bumping this|bump this|following up on my|any update|per my last|as per my previous|gentle reminder|friendly reminder)\b", re.I)
GUILT_RE = re.compile(r"\b(haven'?t heard (?:back|from you)|didn'?t hear back|no response|tried (?:to reach|reaching|several|a few|multiple) times|not sure if you (?:saw|got|received)|you may have missed|i know you'?re busy)\b", re.I)
VALUE_RE = re.compile(r"(\d[\d,.]*\s?(%|percent|hours?|days?|weeks?|x\b|k\b|m\b)|[$£€]\s?\d|\b(case study|benchmark|example|customers? like|similar (?:team|company)|here'?s (?:the|an?|what)|attached (?:is|the)|answer(?:ed|ing)? your|you asked|you mentioned|since we spoke|saw (?:that|your|you)|noticed (?:that|your)|congrats|new (?:hire|role|funding|office|launch))\b)", re.I)
OFFER_RE = re.compile(r"\b(happy to (?:hop on|jump on|chat|walk you|set up|send)|feel free to (?:reach out|call|book|grab)|grab (?:a|some) time|book (?:a|some) time|here'?s my calendar|my calendar link)\b", re.I)
ASK_RE = re.compile(r"\?|\b(let me know|reply with|would (?:tuesday|wednesday|thursday|monday|friday)|does (?:this|that) work|worth|should i|shall i|can i|could i|open to|still (?:a priority|relevant|on your radar))\b", re.I)


@AGENT.tool
def score_follow_up(email: str, kind: str = "follow_up") -> dict:
    """Score a follow-up or breakup email: check-in clichés, guilt language, new value, single ask, length, tokens.

    Call on every draft before sending; rewrite until >= 80. Follow-ups target <= 75 words, breakups <= 50.

    Args:
        email: The email body (subject optional on the first line as "Subject: ...").
        kind: follow_up (default) or breakup.
    """
    if not email or not email.strip():
        raise ToolError("email is empty.")
    if len(email) > 20_000:
        raise ToolError("email over 20k chars.")
    k = kind.strip().lower()
    if k not in ("follow_up", "breakup"):
        raise ToolError("kind must be follow_up or breakup.")
    body = re.sub(r"^\s*subject\s*:.*$", "", email, flags=re.I | re.M).strip()
    n_words = c.word_count(body)
    limit = 50 if k == "breakup" else 75
    score, fixes = 100, []
    cliches = sorted(set(m.group(0).lower() for m in CHECKIN_RE.finditer(body)))
    if cliches:
        score -= 30
        fixes.append("check-in clichés: " + ", ".join(cliches))
    guilt = sorted(set(m.group(0).lower() for m in GUILT_RE.finditer(body)))
    if guilt:
        score -= 20
        fixes.append("guilt language: " + ", ".join(guilt))
    value = sorted(set(m.group(0).lower() for m in VALUE_RE.finditer(body)))
    if not value and k == "follow_up":
        score -= 25
        fixes.append("no new value — add a number, an answer to something they asked, a relevant change, or a simpler next step")
    # an "ask" is any sentence that requests something: a question, "let me know…", "happy to hop on a call"
    ask_sentences = [s_ for s_ in text.sentences(body) if ASK_RE.search(s_) or OFFER_RE.search(s_)]
    n_asks = len(ask_sentences)
    n_questions = body.count("?")
    if n_asks == 0:
        score -= 20
        fixes.append("no ask — end with one question they can answer in a line")
    elif n_asks > 1:
        score -= 10 * min(n_asks - 1, 3)
        fixes.append(f"{n_asks} asks — keep one: " + " | ".join(a[:50] for a in ask_sentences[:3]))
    if n_words > limit * 1.5:
        score -= 20
        fixes.append(f"{n_words} words — cut to ≤ {limit}")
    elif n_words > limit:
        score -= 10
        fixes.append(f"{n_words} words — aim for ≤ {limit}")
    tokens = c.unresolved_tokens(body)
    if tokens:
        score -= 30
        fixes.append("unresolved tokens: " + ", ".join(tokens))
    if k == "breakup":
        if not re.search(r"\b(close (?:the|this|your) file|close the loop|stop (?:reaching out|emailing|following up)|last (?:note|email|time)|won'?t (?:reach out|follow up|bother)|assume (?:this|it)'?s not|if (?:this|it)'?s not a priority|door'?s open|door is open|feel free to reach out|when(?:ever)? the time is right)\b", body, re.I):
            score -= 15
            fixes.append("breakup needs the easy out + open door ('I'll close the file — door's open whenever timing changes')")
    if re.search(r"^\s*(hi|hello|hey)\b[^\n]*\n+\s*(i|we)\b", body, re.I) or re.match(r"^\s*(i|we)\b", body, re.I):
        score -= 5
        fixes.append("opens with I/we — open with their context")
    if "!" in body:
        score -= 5
        fixes.append("exclamation marks — remove")
    score = max(0, min(100, score))
    return {
        "kind": k,
        "score": score,
        "grade": "send" if score >= 80 else "fix" if score >= 60 else "rewrite",
        "words": n_words,
        "word_limit": limit,
        "cliches": cliches,
        "guilt_phrases": guilt,
        "value_signals": value[:5],
        "questions": n_questions,
        "asks": n_asks,
        "unresolved_tokens": tokens,
        "fixes": fixes,
        "verdict": f"{score}/100, {n_words} words — " + (fixes[0] if fixes else "gives them a reason to reply."),
    }


@AGENT.tool
def stale_deals(deals: list[dict], today: str = "", thresholds: dict | None = None, holidays: list[str] | None = None) -> dict:
    """Scan a pipeline for deals gone quiet by stage-specific business-day thresholds; returns today's prioritised chase list.

    Call with the open-deal export. Deal fields: name, stage, amount, last_activity (YYYY-MM-DD),
    close_date (optional), owner (optional), touches_since_reply (optional).

    Args:
        deals: 1-2000 open deals.
        today: As-of date YYYY-MM-DD (default today).
        thresholds: Override business-day thresholds per stage, e.g. {"proposal": 4}.
        holidays: Dates to exclude from business-day counts.
    """
    if not deals or len(deals) > 2000:
        raise ToolError("Give 1-2000 deals.")
    asof = c.to_date(today)
    hols = c.parse_holidays(holidays or [])
    th = dict(STALE_THRESHOLDS)
    for k, v in (thresholds or {}).items():
        try:
            th[str(k).strip().lower()] = int(v)
        except (TypeError, ValueError):
            raise ToolError(f"threshold for {k!r} must be an integer.") from None
    rows, total_stale_amt = [], 0.0
    for i, d in enumerate(deals, 1):
        if not isinstance(d, dict):
            raise ToolError(f"Deal {i} is not a dict.")
        name = str(d.get("name", f"Deal {i}"))
        stage_raw = str(d.get("stage", "")).strip().lower()
        st = next((k for k in th if k in stage_raw), None) or _stage(stage_raw)
        limit = th.get(st, 10)
        try:
            amt = float(str(d.get("amount", 0) or 0).replace(",", "").replace("$", ""))
        except ValueError:
            raise ToolError(f"Deal {i} ({name}): amount is not a number.") from None
        if not d.get("last_activity"):
            raise ToolError(f"Deal {i} ({name}) has no last_activity date.")
        la = dates.parse_date(str(d["last_activity"]))
        if la > asof:
            raise ToolError(f"Deal {i} ({name}): last_activity is in the future.")
        quiet_bd = dates.business_days_between(la, asof, hols)
        quiet_cal = (asof - la).days
        ratio = quiet_bd / limit if limit else 0
        status = "at_risk" if ratio >= 2 else "stale" if ratio >= 1 else "warm" if ratio >= 0.6 else "fresh"
        close = dates.parse_date(str(d["close_date"])) if d.get("close_date") else None
        flags = []
        if close and close < asof:
            flags.append("close date passed")
        touches = int(d.get("touches_since_reply", 0) or 0)
        if status in ("stale", "at_risk"):
            if touches >= 4 and quiet_cal >= 14:
                action = "breakup email"
            elif st == "negotiation":
                action = "call today — ask what's blocking signature"
            elif st in ("proposal", "evaluation"):
                action = "call + email: one question about the proposal ('is X still the priority?')"
            else:
                action = "email with new value tied to their stated problem"
        elif status == "warm":
            action = "prepare touch — due within 1-2 business days"
        else:
            action = "none"
        priority = round(amt * max(ratio, 0.1), 2) if amt else round(ratio, 2)
        if status in ("stale", "at_risk"):
            total_stale_amt += amt
        rows.append({"name": name, "stage": st, "amount": c.money(amt), "owner": d.get("owner"), "last_activity": la.isoformat(), "quiet_business_days": quiet_bd, "quiet_calendar_days": quiet_cal, "threshold_business_days": limit, "staleness_x": round(ratio, 2), "status": status, "flags": flags, "action": action, "priority_score": priority})
    chase = sorted([r for r in rows if r["status"] in ("stale", "at_risk")], key=lambda r: -r["priority_score"])
    warm = [r for r in rows if r["status"] == "warm"]
    n_stale = len(chase)
    return {
        "as_of": asof.isoformat(),
        "deals": rows,
        "chase_today": chase,
        "coming_due": warm,
        "counts": {"fresh": sum(1 for r in rows if r["status"] == "fresh"), "warm": len(warm), "stale": sum(1 for r in rows if r["status"] == "stale"), "at_risk": sum(1 for r in rows if r["status"] == "at_risk")},
        "stale_amount": c.money(total_stale_amt),
        "stale_share_pct": c.pct(total_stale_amt, sum(r["amount"] for r in rows)) if rows else 0.0,
        "verdict": f"{n_stale} of {len(rows)} deals need a touch today (${total_stale_amt:,.0f}, {c.pct(total_stale_amt, sum(r['amount'] for r in rows))}% of pipeline)." + (f" Start with {chase[0]['name']} ({chase[0]['quiet_business_days']} business days quiet in {chase[0]['stage']})." if chase else ""),
    }
