"""Inbox Triage — scores every email by rule, extracts the asks, fills replies, and plans the processing session."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime

from ...core import Agent, ToolError
from ...lib import dates, text
from ._common import as_float, as_str, as_str_list, clamp, fmt_duration, md_table, require_dict, require_list, resolve_relative_date

AGENT = Agent(
    slug="inbox-triage",
    name="Inbox Triage",
    category="ops",
    tagline="Get to inbox zero in one pass: every email scored, sorted into do/reply/defer/archive, with replies half-written.",
    description=(
        "Runs the inbox like an executive assistant with a system: a transparent rule-based priority score "
        "for every message (VIP, direct ask, deadline, thread age, newsletter detection), extraction of the "
        "exact questions and requests with resolved deadlines, a reply-template filler that catches unfilled "
        "placeholders and over-long replies, and a session planner that fits the work into the minutes you have "
        "using the two-minute rule. Deterministic, explainable, and fast."
    ),
    triggers=[
        "triage my inbox / help me get to inbox zero",
        "which of these emails matter",
        "what is this person actually asking me",
        "draft replies to these emails",
        "I have 30 minutes — what should I answer first",
        "sort my email by priority",
    ],
    examples=[
        "Here are 25 emails from this morning (sender, subject, first lines). Tell me what to do with each.",
        "This thread is long — what exactly do they need from me and by when?",
        "Fill in my standard 'can't make it' reply for these three invites.",
        "I've got 40 minutes before my next meeting. Plan the inbox session.",
    ],
    connectors=["Gmail", "Outlook", "Slack", "Google Calendar", "Notion", "Todoist", "Linear"],
    playbook="""
    ## Standard
    You are the executive assistant who keeps a CEO's inbox at zero without anything important
    slipping. Excellent means: every message gets exactly one decision (do / reply / delegate /
    defer with a date / archive), the important ones are answered in the order of consequence,
    and nothing is answered twice. The one metric that matters: **important emails answered
    within 24 hours, and zero "sorry for the late reply".**

    ## Intake
    Need: the emails (sender, subject, body or first lines, date; To/CC if available), who the
    user is (their address/domain) and their VIP list (boss, key customers, family). Time
    available for the session. Ask at most one question — the VIP list — and only if the
    user hasn't mentioned who matters; otherwise infer VIPs from the same domain + people
    they have replied to, and say so.

    ## Procedure
    1. **Score everything first.** Call `inbox_triage__score_priority` with all emails, the
       user's address and VIP list. Do not read emails one by one before scoring — the score
       orders your reading. It returns a 0-100 score with named reasons, an Eisenhower
       quadrant, an action (Reply now / Reply today / Schedule / Delegate / Archive /
       Unsubscribe), an estimated reply time, and any detected deadline.
    2. **Read the top of the list** (score ≥ 45). For each, call `inbox_triage__extract_asks`
       on the body to get the exact questions, requests and deadlines (resolved to dates).
       Reply to the asks in the order they appear, one line each — people skim.
    3. **Decide once per email**, using the score as a default you can override with reason:
       - Score ≥ 70 → reply now; if the reply takes ≤ 2 minutes, send before moving on.
       - 45-69 → reply today, batched in one block.
       - 25-44 → schedule (create a task with a date) or delegate with a one-line brief.
       - < 25 → archive; newsletters → unsubscribe if unread 3 times in a row.
    4. **Draft replies** with `inbox_triage__fill_reply_template` when a template applies
       (decline, schedule, acknowledge, status) — it fills the fields and flags unfilled
       placeholders, replies over 5 sentences and missing next steps. Non-template replies:
       ≤ 5 sentences, answer first, context second, next step + date last.
    5. **Plan the session** with `inbox_triage__plan_session` (items with action + minutes +
       score, and minutes available). It applies the two-minute rule, packs by score, and
       returns what to defer and to when. Present it as an ordered checklist.
    6. **Act** via Gmail/Outlook if connected: create drafts (never send unasked), archive,
       label; create tasks for deferred items in the task tool. Otherwise output the
       decisions table and the drafts ready to paste.

    ## Frameworks
    - **4 D's**: Do (≤ 2 min), Delegate (someone else is better placed), Defer (task with a
      date, then archive the mail), Delete/archive. Every email gets one.
    - **Eisenhower**: important = VIP sender, direct ask, money, customers, commitments;
      urgent = deadline within 48 hours. Urgent-not-important is where delegation lives.
    - **Two-minute rule (Allen)**: if it takes < 2 minutes, do it now — the overhead of
      tracking it costs more than doing it.
    - **Batching**: process in 2-3 sessions a day (e.g. 08:30, 13:00, 16:30), 20-40 minutes
      each; notifications off in between. Reply-time expectations: internal same day,
      customers/VIPs < 4 h, everyone else 24-48 h.
    - **Reply anatomy**: answer → context (1 line) → next step with owner and date → close.
      Subject changes when the topic changes. One ask per email you send.
    - **Newsletter rule**: unread three issues in a row → unsubscribe. Digest the rest into
      one weekly read block.

    ## Output format
    ```
    # Inbox triage — <date>, N emails, ~X min of work
    **Reply now (≥70)**
    | # | From | Subject | Why | Ask | Deadline | Min |
    **Reply today (45-69)**
    | … |
    **Schedule / delegate (25-44)**
    - <subject> → task "<…>" due <date> / delegate to <who>: "<one-line brief>"
    **Archive (<25)**: N emails (M newsletters → unsubscribe: <list>)

    ## Drafts
    ### Re: <subject>  (to <name>)
    <≤ 5 sentences>

    ## Session plan (<minutes> min)
    1. [2 min] … 2. [5 min] … → deferred to <date>: …
    ```

    ## Anti-patterns
    - Reading everything in arrival order. Score first, read in score order.
    - Replies that restate the question. Answer in the first sentence.
    - "Let me get back to you" with no date. Defer means a date on a task.
    - Leaving mail in the inbox as a to-do list. The task tool is the to-do list; archive.
    - Sending from the assistant persona without the user's approval. Drafts only.
    - Treating CC'd threads as asks. If you're on CC and there is no question to you, archive.
    """,
)

_NEWSLETTER_SENDER = re.compile(r"(newsletter|digest|marketing|news@|updates?@|hello@|info@|team@|community@)", re.I)
_AUTO_SENDER = re.compile(r"(no-?reply|do-?not-?reply|notifications?@|alerts?@|mailer|billing@|system@|bot@|calendar-notification|jira@|github\.com|linear\.app|slack\.com)", re.I)
_NEWSLETTER_BODY = re.compile(r"\b(unsubscribe|view (this )?(email )?in (your )?browser|manage (your )?preferences|you are receiving this|email preferences|opt out)\b", re.I)
_AUTOMATED_SUBJ = re.compile(r"\b(receipt|invoice|your order|password|verify your|confirm your|weekly digest|daily digest|summary|report is ready|new sign-?in|security alert|automatic reply|out of office|delivery status)\b", re.I)
_ASK = re.compile(r"\b(can you|could you|would you|will you|please|need you to|need your|let me know|i need|we need|are you able|do you have|thoughts\?|your input|your approval|sign off|approve|confirm|review)\b", re.I)
_DEADLINE = re.compile(
    r"\b(?:(?:by|before|until|no later than|due|due by|due on|on|deadline(?: is|:)?)\s+(?:the |our |my |this |next |end of (?:the )?)?(?:\w+ )?"
    r"(?:eod|eow|eom|eoq|tomorrow|today|tonight|noon|day|week|month|quarter|mon|tue|tues|wed|thu|thurs|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday|meeting|call|launch|\d{1,2}(?:/\d{1,2})?|\d{4}-\d{2}-\d{2})"
    r"|asap|urgent(?:ly)?|time.sensitive|today|tomorrow|eod|eow|within \d+ (?:hours?|days?|business days?))\b",
    re.I,
)
_MONEY = re.compile(r"(\$|€|£)\s?\d|\b(invoice|payment|contract|renewal|refund|pricing|quote|proposal|offer|budget)\b", re.I)
_FYI = re.compile(r"^\s*(fyi|fwd?:|for your information|no action)\b", re.I)
_THANKS_ONLY = re.compile(r"^\s*(thanks|thank you|thx|ty|cheers|great|perfect|sounds good|got it|ok|okay|noted)[\s!.,]*(\w+[\s!.,]*){0,4}$", re.I)


def _addr(s: str) -> str:
    m = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", s or "")
    return m.group(0).lower() if m else (s or "").strip().lower()


def _domain(addr: str) -> str:
    return addr.split("@")[-1] if "@" in addr else ""


@AGENT.tool
def score_priority(emails: list[dict], me: str = "", vips: list[str] = [], as_of: str = "") -> dict:
    """Score every email 0-100 with named reasons; assign action (reply now/today, schedule, delegate, archive, unsubscribe), quadrant, minutes, deadline.

    Args:
        emails: List of {"id": str, "from": str, "subject": str, "body": str (first lines are enough), "to": str, "cc": str, "received": "YYYY-MM-DD" or ISO, "thread_length": int}.
        me: The user's email address (used for direct-To vs CC and same-domain detection).
        vips: Addresses, names or domains that always matter (boss, key customers).
        as_of: Today's date (YYYY-MM-DD) for age and deadline math; defaults to today.
    """
    emails = require_list(emails, "emails", 500)
    today = dates.parse_date(as_of) if as_of else date.today()
    me_addr = _addr(me)
    my_domain = _domain(me_addr)
    vip_list = [v.lower().strip() for v in as_str_list(vips, "vips", 200)]
    rows = []
    total_minutes = 0
    for i, e in enumerate(emails, 1):
        if not isinstance(e, dict):
            raise ToolError(f"emails[{i}] must be {{'id','from','subject','body','to','cc','received'}}.")
        eid = as_str(e.get("id") or str(i), "id", max_len=60)
        sender_raw = as_str(e.get("from", ""), "from", required=False, max_len=200)
        sender = _addr(sender_raw)
        subject = as_str(e.get("subject", ""), "subject", required=False, max_len=500)
        body = as_str(e.get("body", ""), "body", required=False, max_len=20000)
        to = as_str(e.get("to", ""), "to", required=False, max_len=2000).lower()
        cc = as_str(e.get("cc", ""), "cc", required=False, max_len=2000).lower()
        thread_len = int(as_float(e.get("thread_length", 1), "thread_length", lo=0, hi=1000, default=1.0))
        received = None
        if e.get("received"):
            try:
                received = datetime.fromisoformat(str(e["received"]).replace("Z", "+00:00")).date()
            except ValueError:
                raise ToolError(f"emails[{i}].received must be an ISO date/datetime.") from None
        score, reasons = 35.0, []
        text_all = f"{subject}\n{body}"
        sender_l = sender_raw.lower()
        is_vip = any(v and (v in sender_l or v == _domain(sender)) for v in vip_list)
        newsletter = bool(_NEWSLETTER_SENDER.search(sender) or _NEWSLETTER_BODY.search(body))
        automated = not newsletter and not is_vip and bool(_AUTO_SENDER.search(sender) or _AUTOMATED_SUBJ.search(subject))
        if is_vip:
            score += 30
            reasons.append("VIP sender")
        if me_addr and me_addr in to:
            score += 12
            reasons.append("addressed directly to you")
        elif me_addr and me_addr in cc:
            score -= 12
            reasons.append("you are only CC'd")
        elif to and "," in to and not me_addr:
            score -= 3
        if my_domain and _domain(sender) == my_domain and not is_vip:
            score += 6
            reasons.append("internal sender")
        asks = len(_ASK.findall(text_all))
        questions = text_all.count("?")
        if asks:
            score += min(15, 8 + 3 * asks)
            reasons.append(f"{asks} explicit request(s)")
        if questions:
            score += min(10, 5 + 2 * questions)
            reasons.append(f"{questions} question(s)")
        deadline_phrase, deadline_date, days_to = None, None, None
        m = _DEADLINE.search(text_all)
        if m:
            deadline_phrase = m.group(0)
            d, _rule = resolve_relative_date(text_all[m.start(): m.end() + 30], received or today)
            if d:
                deadline_date = d
                days_to = (d - today).days
                if days_to <= 0:
                    score += 20
                    reasons.append(f"deadline {d.isoformat()} is today or passed")
                elif days_to <= 2:
                    score += 15
                    reasons.append(f"deadline in {days_to} day(s)")
                else:
                    score += 6
                    reasons.append(f"deadline {d.isoformat()}")
            else:
                score += 8
                reasons.append(f"urgency language: '{deadline_phrase}'")
        if _MONEY.search(text_all):
            score += 8
            reasons.append("money/contract topic")
        if _FYI.match(subject):
            score -= 12
            reasons.append("FYI/forward")
        if newsletter:
            score -= 40
            reasons.append("newsletter / no-reply sender")
        elif automated:
            score -= 28
            reasons.append("automated notification")
        if _THANKS_ONLY.match(body) and not asks:
            score -= 25
            reasons.append("thanks-only, no ask")
        if thread_len >= 3:
            score += 4
            reasons.append(f"active thread ({thread_len} msgs)")
        age = (today - received).days if received else None
        if age is not None and age >= 3 and not newsletter and not automated:
            score += min(10, 2 * age)
            reasons.append(f"waiting {age} days")
        score = int(clamp(round(score), 0, 100))
        important = is_vip or (asks > 0 and (not me_addr or me_addr in to)) or bool(_MONEY.search(text_all))
        urgent = days_to is not None and days_to <= 2 or (deadline_phrase is not None and re.search(r"asap|urgent|today|eod|tomorrow", deadline_phrase, re.I) is not None)
        quadrant = "Q1 do first (important + urgent)" if important and urgent else "Q2 schedule (important)" if important else "Q3 delegate (urgent, not important)" if urgent else "Q4 archive"
        if newsletter:
            action = "Unsubscribe or digest"
        elif automated or score < 25:
            action = "Archive"
        elif score >= 70:
            action = "Reply now"
        elif score >= 45:
            action = "Reply today"
        elif quadrant.startswith("Q3"):
            action = "Delegate"
        else:
            action = "Schedule"
        words = len(text.words(body))
        minutes = 0 if action in ("Archive", "Unsubscribe or digest") else 2 if (asks + questions) <= 1 and words < 120 else 5 if (asks + questions) <= 3 and words < 400 else 15
        total_minutes += minutes
        rows.append({"id": eid, "from": sender_raw[:80], "subject": subject[:120], "score": score, "action": action, "quadrant": quadrant, "reasons": reasons, "deadline": deadline_date.isoformat() if deadline_date else None, "deadline_phrase": deadline_phrase, "days_to_deadline": days_to, "asks": asks, "questions": questions, "estimated_minutes": minutes, "age_days": age})
    rows.sort(key=lambda r: (-r["score"], r["days_to_deadline"] if r["days_to_deadline"] is not None else 999))
    counts = Counter(r["action"] for r in rows)
    return {
        "as_of": today.isoformat(),
        "emails": rows,
        "counts": dict(counts),
        "total_estimated_minutes": total_minutes,
        "reply_now_ids": [r["id"] for r in rows if r["action"] == "Reply now"],
        "unsubscribe_candidates": [r["from"] for r in rows if r["action"] == "Unsubscribe or digest"],
        "markdown_table": md_table(["#", "Score", "Action", "From", "Subject", "Why", "Deadline", "Min"], [[r["id"], r["score"], r["action"], r["from"][:30], r["subject"][:40], "; ".join(r["reasons"][:3]), r["deadline"] or "", r["estimated_minutes"]] for r in rows]),
        "verdict": f"{len(rows)} emails: {counts.get('Reply now', 0)} reply now, {counts.get('Reply today', 0)} today, {counts.get('Schedule', 0) + counts.get('Delegate', 0)} schedule/delegate, {counts.get('Archive', 0) + counts.get('Unsubscribe or digest', 0)} archive. ~{fmt_duration(total_minutes)} of replies.",
    }


_QUESTION_WORDS = re.compile(r"^(what|when|where|who|why|how|which|can|could|would|will|should|do|does|did|is|are|have|has|any)\b", re.I)


@AGENT.tool
def extract_asks(body: str, as_of: str = "", received: str = "") -> dict:
    """Pull the questions, requests and deadlines out of an email body, resolve deadlines to dates, and order them for the reply.

    Args:
        body: The email body (quoted history is ignored after lines starting with '>' or 'On … wrote:').
        as_of: Today's date (YYYY-MM-DD); defaults to today.
        received: Date the email was received (YYYY-MM-DD) — relative deadlines like "by Friday" resolve from this. Defaults to as_of.
    """
    if not body.strip():
        raise ToolError("Email body is empty.")
    if len(body) > 100_000:
        raise ToolError("Body too long (100k chars max).")
    today = dates.parse_date(as_of) if as_of else date.today()
    base = dates.parse_date(received) if received else today
    lines = []
    for ln in body.splitlines():
        if ln.strip().startswith(">") or re.match(r"^\s*On .{5,120} wrote:\s*$", ln) or re.match(r"^\s*(-{2,}|_{2,})\s*$", ln) or re.match(r"^\s*From:\s", ln):
            break
        lines.append(ln)
    own = "\n".join(lines).strip() or body
    asks = []
    for s in text.sentences(own):
        st = s.strip()
        low = st.lower()
        kind = None
        if st.endswith("?") or _QUESTION_WORDS.match(st) and "?" in st:
            kind = "question"
        elif _ASK.search(st):
            kind = "request"
        m = _DEADLINE.search(st)
        deadline = None
        if m:
            d, rule = resolve_relative_date(st[m.start(): m.end() + 30], base)
            deadline = {"phrase": m.group(0), "date": d.isoformat() if d else None, "days_from_today": (d - today).days if d else None, "rule": rule}
            if not kind:
                kind = "deadline"
        if kind:
            asks.append({"n": len(asks) + 1, "type": kind, "text": st[:300], "deadline": deadline, "needs_decision": bool(re.search(r"\b(approve|approval|sign off|decide|decision|go/no-go|ok to|permission)\b", low))})
    deadlines = [a["deadline"] for a in asks if a["deadline"] and a["deadline"]["date"]]
    earliest = min(deadlines, key=lambda d: d["date"]) if deadlines else None
    words = len(text.words(own))
    order = [a["n"] for a in sorted(asks, key=lambda a: (0 if a["needs_decision"] else 1, 0 if a["type"] == "question" else 1, a["n"]))]
    skeleton = []
    for a in asks:
        if a["type"] == "question":
            skeleton.append(f"Q{a['n']}: <one-line answer>")
        elif a["type"] == "request":
            skeleton.append(f"R{a['n']}: <yes/no + by when>" + (f" (they asked for {a['deadline']['date']})" if a["deadline"] and a["deadline"]["date"] else ""))
    return {
        "asks": asks,
        "counts": {"questions": sum(1 for a in asks if a["type"] == "question"), "requests": sum(1 for a in asks if a["type"] == "request"), "deadlines": len(deadlines), "decisions_needed": sum(1 for a in asks if a["needs_decision"])},
        "earliest_deadline": earliest,
        "own_text_words": words,
        "quoted_history_dropped": len(own) < len(body.strip()),
        "reply_order": order,
        "reply_skeleton": skeleton + ["Next step: <what you will do> by <date>."],
        "verdict": (f"{len(asks)} ask(s): {sum(1 for a in asks if a['type'] == 'question')} question(s), {sum(1 for a in asks if a['type'] == 'request')} request(s)" + (f"; earliest deadline {earliest['date']} ({earliest['days_from_today']:+d} days)" if earliest else "; no deadline stated") + ".") if asks else "No explicit ask found — this is FYI unless the context says otherwise; archive or one-line acknowledge.",
    }


_PLACEHOLDER = re.compile(r"\{\{\s*([\w .-]+?)\s*\}\}|\{([\w .-]+?)\}|\[([\w .-]+?)\]|<([\w .-]+?)>")


@AGENT.tool
def fill_reply_template(template: str, fields: dict, max_sentences: int = 5) -> dict:
    """Fill a reply template's placeholders ({{name}}, {name}, [name], <name>), then check for unfilled slots, length and a next step.

    Args:
        template: The reply template text with placeholders.
        fields: Mapping of placeholder name to value, e.g. {"name": "Priya", "date": "Oct 9"}.
        max_sentences: Maximum sentences a good reply should have (default 5).
    """
    if not template.strip():
        raise ToolError("Template is empty.")
    if len(template) > 20_000:
        raise ToolError("Template too long (20k chars max).")
    fields = require_dict(fields, "fields")
    if not (1 <= max_sentences <= 30):
        raise ToolError("max_sentences must be 1-30.")
    norm = {re.sub(r"[\s_-]+", "", str(k).lower()): ("" if v is None else str(v)) for k, v in fields.items()}
    unfilled, used = [], set()

    def sub(m: re.Match) -> str:
        key = next(g for g in m.groups() if g is not None)
        nk = re.sub(r"[\s_-]+", "", key.lower())
        if nk in norm and norm[nk] != "":
            used.add(nk)
            return norm[nk]
        unfilled.append(key)
        return m.group(0)

    filled = _PLACEHOLDER.sub(sub, template)
    unused = [k for k in fields if re.sub(r"[\s_-]+", "", str(k).lower()) not in used]
    sents = text.sentences(filled)
    words = len(text.words(filled))
    rd = text.readability(filled)
    fixes = []
    if unfilled:
        fixes.append("Unfilled placeholders: " + ", ".join(f"'{u}'" for u in dict.fromkeys(unfilled)) + " — supply values or remove them.")
    if len(sents) > max_sentences:
        fixes.append(f"{len(sents)} sentences — cut to ≤ {max_sentences}; answer first, context second, next step last.")
    if words > 150:
        fixes.append(f"{words} words — replies over ~150 words get skimmed; move detail to a doc or a call.")
    if not re.search(r"\b(by|on|before|next|will|i'll|we'll|let's|tomorrow|today|monday|tuesday|wednesday|thursday|friday|\d{1,2}(:\d{2})?\s?(am|pm))\b", filled, re.I):
        fixes.append("No next step or date — end with what happens next and when.")
    if not re.match(r"^\s*(hi|hello|hey|dear|good (morning|afternoon)|thanks|thank you)\b", filled, re.I):
        fixes.append("No greeting — a one-word greeting keeps a template from reading as automated.")
    if rd.get("fk_grade") and rd["fk_grade"] > 10:
        fixes.append(f"Reading grade {rd['fk_grade']} — simplify; aim ≤ 8.")
    ready = not unfilled and len(sents) <= max_sentences
    return {
        "reply": filled,
        "ready_to_send": ready,
        "unfilled_placeholders": list(dict.fromkeys(unfilled)),
        "unused_fields": unused,
        "sentences": len(sents),
        "words": words,
        "reading_grade": rd.get("fk_grade"),
        "fixes": fixes,
        "verdict": ("Ready" if ready else "Not ready") + f": {len(sents)} sentences, {words} words" + (f", {len(set(unfilled))} unfilled placeholder(s)" if unfilled else "") + ".",
    }


_ACTION_ORDER = {"reply now": 0, "do": 0, "reply today": 1, "reply": 1, "delegate": 2, "schedule": 3, "defer": 3, "archive": 4, "unsubscribe or digest": 4, "unsubscribe": 4}


@AGENT.tool
def plan_session(items: list[dict], minutes_available: int, two_minute_rule: bool = True, as_of: str = "") -> dict:
    """Pack triaged emails into the minutes available: two-minute items first, then by score; returns the ordered plan and what to defer to when.

    Args:
        items: List of {"id": str, "subject": str, "action": "Reply now"|"Reply today"|"Schedule"|"Delegate"|"Archive", "minutes": int, "score": 0-100, "deadline": "YYYY-MM-DD" optional}.
        minutes_available: Minutes the user has for this session (5-480).
        two_minute_rule: Do all ≤ 2-minute replies first regardless of score (default true).
        as_of: Today's date (YYYY-MM-DD) for deferral dates; defaults to today.
    """
    items = require_list(items, "items", 500)
    if not (5 <= minutes_available <= 480):
        raise ToolError("minutes_available must be 5-480.")
    today = dates.parse_date(as_of) if as_of else date.today()
    norm = []
    for i, it in enumerate(items, 1):
        if not isinstance(it, dict):
            raise ToolError(f"items[{i}] must be {{'id','action','minutes','score'}}.")
        action = as_str(it.get("action", "Reply today"), "action", max_len=40)
        if action.lower() not in _ACTION_ORDER:
            raise ToolError(f"items[{i}].action {action!r} must be one of Reply now, Reply today, Schedule, Delegate, Archive, Unsubscribe.")
        mins = int(as_float(it.get("minutes", 5), f"items[{i}].minutes", lo=0, hi=240, default=5.0))
        dl = as_str(it.get("deadline", ""), "deadline", required=False)
        norm.append({"id": as_str(it.get("id") or str(i), "id", max_len=60), "subject": as_str(it.get("subject", ""), "subject", required=False, max_len=120), "action": action, "minutes": mins, "score": as_float(it.get("score", 50), f"items[{i}].score", lo=0, hi=100, default=50.0), "deadline": dates.parse_date(dl) if dl else None})
    archive = [n for n in norm if _ACTION_ORDER[n["action"].lower()] == 4]
    work = [n for n in norm if _ACTION_ORDER[n["action"].lower()] < 4]
    quick = sorted([n for n in work if two_minute_rule and n["minutes"] <= 2], key=lambda n: -n["score"])
    rest = sorted([n for n in work if n not in quick], key=lambda n: (_ACTION_ORDER[n["action"].lower()], n["deadline"] or date.max, -n["score"]))
    budget = minutes_available - min(3, minutes_available // 10)  # 10% overhead for archiving/labeling
    plan, deferred, used = [], [], 0
    archive_minutes = min(3, minutes_available // 10) if archive else 0
    for n in quick + rest:
        if used + n["minutes"] <= budget:
            plan.append({**n, "deadline": n["deadline"].isoformat() if n["deadline"] else None, "start_minute": used})
            used += n["minutes"]
        else:
            deferred.append(n)
    next_session = dates.add_business_days(today, 1) if today.weekday() < 4 else dates.add_business_days(today, 1)
    deferred_out = []
    for n in deferred:
        late = n["deadline"] and n["deadline"] <= next_session
        hot = n["action"].lower() in ("reply now", "do")
        risk = "deadline before next session" if late else "reply-now item deferred — do it right after the session" if hot else None
        deferred_out.append({**n, "deadline": n["deadline"].isoformat() if n["deadline"] else None, "defer_to": (today.isoformat() + " (later today)") if (late or hot) else next_session.isoformat(), "risk": risk})
    at_risk = [d for d in deferred_out if d["risk"]]
    total_work = sum(n["minutes"] for n in work)
    sessions_needed = -(-total_work // max(1, budget))
    return {
        "minutes_available": minutes_available,
        "minutes_planned": used,
        "archive_first": {"count": len(archive), "minutes": archive_minutes, "ids": [a["id"] for a in archive]},
        "plan": plan,
        "deferred": deferred_out,
        "deferred_at_risk": [d["id"] for d in at_risk],
        "two_minute_items": len(quick),
        "total_work_minutes": total_work,
        "sessions_needed": sessions_needed,
        "inbox_zero_eta": today.isoformat() if not deferred else next_session.isoformat(),
        "verdict": f"{len(plan)} items in {used} of {minutes_available} min ({len(quick)} two-minute replies first), archive {len(archive)} in a batch, defer {len(deferred)} to {next_session.isoformat()}."
        + (f" WARNING: {len(at_risk)} deferred item(s) have a deadline before then — swap them in or do them after the meeting." if at_risk else "")
        + (f" Total backlog {fmt_duration(total_work)} ≈ {sessions_needed} session(s)." if sessions_needed > 1 else ""),
    }
