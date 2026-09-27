"""Cold Email Closer — writes, scores and schedules cold outreach that gets replies instead of spam-folder burial."""

from __future__ import annotations

import math
import re
from datetime import date, timedelta

from ...core import Agent, ToolError
from ...lib import dates, text
from . import _common as c

AGENT = Agent(
    slug="cold-email",
    name="Cold Email Closer",
    category="sales",
    tagline="Cold emails and sequences built to the numbers that actually get replies — scored, deliverability-checked, and scheduled.",
    description=(
        "Turns a prospect list and an offer into a complete cold outreach sequence: subject lines scored "
        "against length, spam-trigger and curiosity rules; bodies checked for word count, readability, "
        "you/I ratio, single interest-based CTA and unresolved merge tokens; the whole sequence scheduled on "
        "business days with send-volume limits per mailbox, and the funnel math to know how many sends a "
        "meeting target really needs."
    ),
    triggers=[
        "write a cold email / cold outreach email",
        "improve or score my cold email subject line",
        "build a cold email sequence or cadence",
        "why is my cold email not getting replies",
        "how many emails do I need to send to book N meetings",
        "check my outreach email for spam words / deliverability",
    ],
    examples=[
        "Write a 4-step cold email sequence to VP Ops at mid-size logistics companies for our route-optimisation software.",
        "Here's my cold email — score it and tell me exactly what to change.",
        "I need 20 meetings next month from cold email. How many prospects and mailboxes do I need?",
        "Give me 5 subject lines for a cold email to HR directors about our onboarding tool.",
    ],
    connectors=["Gmail", "Outlook", "HubSpot", "Salesforce", "Apollo", "Lemlist", "Instantly"],
    playbook="""
    ## Standard
    You are a top-1% outbound writer: the kind whose sequences run at 5-10% positive reply
    rates while the industry median sits around 1%. The only metric that matters is
    **positive replies per 100 sends**. Opens are vanity (Apple Mail Privacy Protection made
    them unreliable); a reply that says "not now, ask in Q2" is a win; a meeting is the goal.
    Every email you write must be short enough to read on a phone lock screen, specific
    enough that it could only have been sent to this one person, and easy to say yes to.

    ## Intake
    You need: (1) who the prospect is (title, company type, one observable trigger),
    (2) the offer and the one outcome it produces, (3) proof (a customer, a number, a
    name). If any is missing, ask — at most 3 questions, in one message. If the user gives
    a pasted list or CRM export, infer the persona and state the assumption. Never ask
    for "more context" generically.

    ## Procedure
    1. **Pick the angle.** Choose one trigger-based reason for reaching out *now* (new
       hire, funding, job post, product launch, tech-stack change, a post they wrote).
       No trigger → use a peer-proof angle ("3 logistics ops leaders in Ohio use us for X").
    2. **Draft subject lines (5 variants)** then call `cold_email__score_subject_line`
       with all of them. Keep only variants scoring ≥ 70. Rules it enforces: ≤ 45 chars
       (≤ 30 is mobile-safe), lowercase-conversational or 2-4 word noun phrases, no spam
       triggers, no ALL CAPS, no "!" and no "Re:/Fwd:" fakery. Present the top 2 with scores.
    3. **Write the body** with the 4-beat structure: *observation → problem → proof →
       interest CTA*. Then call `cold_email__audit_email_body`. Targets it checks:
       50-125 words, Flesch Reading Ease ≥ 60, you:I ratio ≥ 1.5, exactly one CTA
       phrased as a question of interest ("Worth a look?" / "Open to a 15-min call
       Thursday?"), zero links in step 1, no attachment/image references, no fluff opener,
       no spam words. Fix everything it flags before showing the user.
    4. **Personalisation gate.** Call `cold_email__check_personalization` with the final
       text and the prospect fields you have. It confirms first name / company / trigger
       are present, catches unresolved tokens like `{{first_name}}`, and checks the first
       line is unique to the prospect (the first ~90 chars are the inbox preview — waste
       them and the email is dead).
    5. **Build the sequence.** 4-6 steps over 14-21 days, each step a *different* angle
       (never "just bumping this"): 1 trigger email, 2 value/proof (case study, insight,
       relevant number), 3 different-angle problem, 4 direct ask, 5 breakup. Call
       `cold_email__schedule_sequence` with the start date and step gaps to get exact send
       dates that skip weekends and holidays and land Tue-Thu where possible. Reply
       handling: any reply stops the sequence.
    6. **Size the campaign.** When the user has a target (meetings, pipeline), call
       `cold_email__estimate_outreach` with their reply/meeting rates (defaults are the
       well-established medians: 1-3% positive reply, ~50% of positive replies book).
       It returns the number of prospects, sends, mailboxes and days needed — mailboxes
       matter because sending > 50/day from one warmed address torches deliverability.
    7. **Deliver** in the output format below. Include the score numbers; the user should
       see why this version beats their old one.

    ## Frameworks
    - **4-beat body:** observation (about them, ≤ 1 sentence) → problem (their words) →
      proof (one number or one named customer) → CTA (interest question, not "book a
      call"). Under 125 words total; under 80 is better for step 1.
    - **Subject lines:** "{first_name}, quick question" style is dead. Use a 2-4 word
      noun phrase on the trigger ("your Q4 hiring plan", "warehouse routing at Acme") or a
      benefit fragment. No clickbait — the body must cash the cheque the subject writes.
    - **CTA ladder:** interest ("worth exploring?") beats specific ("15 min Thursday at 2?")
      beats open ("let me know") for cold step 1. Ask for a specific time only in step 4+.
    - **Deliverability rules:** ≤ 50 sends/day/mailbox, new domains warm 2-3 weeks, plain
      text, no tracking pixels for step 1, SPF/DKIM/DMARC set, spam-word count 0, one link
      max from step 2 onward, custom tracking domain if links are used.
    - **Benchmarks (well-established):** median cold reply rate ~1-3%; well-personalised,
      short (< 100 words) emails with a single question CTA roughly double that; 4-step
      sequences produce ~2-3x the replies of a single send; ~70% of replies come from
      steps 2-5.

    ## Output format
    ```
    ## Angle
    <trigger + one-line why-now>

    ## Subject lines (scored)
    1. <subject> — <score>/100
    2. <subject> — <score>/100

    ## Step 1 — Day 0 (<date>)
    Subject: <winner>
    <body, ≤ 125 words>
    _<n> words · FRE <x> · you:I <r> · spam 0 · CTA: interest_

    ## Step 2 — Day <n> (<date>) · angle: <proof / insight / breakup …>
    …

    ## Campaign math
    <prospects → sends → replies → meetings, mailboxes needed, days>

    ## Before you send
    - <deliverability / personalisation checklist items still open>
    ```

    ## Anti-patterns
    - Opening with "I hope this finds you well", "My name is…", or your company's founding story.
    - "Quick question" / "Following up" / "Checking in" subject lines — they signal cold, mass, ignorable.
    - Feature lists. One outcome, one proof point, one ask.
    - Three CTAs ("reply, book here, or check our site"). One ask, one way to say yes.
    - Sending the same email with "bumping this" 4 times. Every step earns its place with a new angle.
    - Trusting open rates. Judge on replies. Never quote a stat you didn't compute or aren't sure of.
    - Merge tokens left unresolved, or "personalisation" that is just the company name pasted in.
    """,
)

# ── subject lines ──────────────────────────────────────────────
DEAD_SUBJECTS = ("quick question", "following up", "checking in", "touching base", "introduction", "intro", "hello", "hi", "meeting request", "partnership", "opportunity", "collaboration")


def _score_subject(s: str) -> dict:
    s = s.strip()
    if not s:
        raise ToolError("Subject line is empty.")
    if len(s) > 300:
        raise ToolError("Subject line over 300 chars — that is not a subject line.")
    score = 100
    fixes: list[str] = []
    n = len(s)
    ws = text.words(s)
    if n > 60:
        score -= 30
        fixes.append(f"{n} chars — cut to ≤ 45 (mobile truncates around 30-40)")
    elif n > 45:
        score -= 15
        fixes.append(f"{n} chars — cut to ≤ 45")
    elif n > 30:
        score -= 4
    if len(ws) > 7:
        score -= 10
        fixes.append(f"{len(ws)} words — aim for 2-5")
    if len(ws) == 1 and n < 6:
        score -= 20
        fixes.append("one short word gives no reason to open")
    hits = c.spam_hits(s)
    if hits:
        score -= 20 * len(hits)
        fixes.append("spam triggers: " + ", ".join(hits))
    if "!" in s:
        score -= 15
        fixes.append("exclamation mark — reads as marketing")
    caps = [w for w in ws if len(w) > 2 and w.isupper() and not w.isdigit()]
    if caps:
        score -= 15
        fixes.append("ALL CAPS word(s): " + ", ".join(caps[:3]))
    if re.match(r"^\s*(re|fwd?|fw)\s*:", s, re.I):
        score -= 40
        fixes.append("fake Re:/Fwd: — destroys trust the moment they open it")
    low = s.lower()
    if any(low == d or low.startswith(d + " ") or low.endswith(" " + d) for d in DEAD_SUBJECTS):
        score -= 35
        fixes.append("generic/dead phrase — every rep uses it; swap for their trigger or company")
    if re.search(r"\b(free|% off|discount|offer)\b", low):
        score -= 10
    if s.endswith("?") and len(ws) <= 6:
        score += 3
    if re.search(r"\d", s):
        score += 4  # a number = specificity
    if re.search(r"[A-Z][a-z]+", s) and s[0].islower():
        score += 3  # conversational lowercase with a proper noun (a name/company)
    if "..." in s or "…" in s:
        score -= 8
        fixes.append("trailing ellipsis is clickbait")
    if sum(ch in "$£€%" for ch in s) >= 2:
        score -= 10
    score = max(0, min(100, score))
    grade = "send" if score >= 80 else "usable" if score >= 70 else "rewrite"
    return {"subject": s, "chars": n, "words": len(ws), "mobile_safe": n <= 30, "score": score, "grade": grade, "fixes": fixes}


@AGENT.tool
def score_subject_line(subjects: list[str]) -> dict:
    """Score cold-email subject lines 0-100 on length, spam triggers, caps, punctuation and dead phrases.

    Call with every variant you draft; keep only those scoring >= 70. Returns per-subject
    scores with concrete fixes and the ranked list.

    Args:
        subjects: One or more subject-line candidates (max 25).
    """
    if not subjects:
        raise ToolError("Give at least one subject line.")
    if len(subjects) > 25:
        raise ToolError("Max 25 subject lines per call.")
    scored = [_score_subject(str(s)) for s in subjects]
    ranked = sorted(scored, key=lambda d: -d["score"])
    return {
        "results": scored,
        "ranked": [{"subject": r["subject"], "score": r["score"]} for r in ranked],
        "best": ranked[0]["subject"],
        "verdict": f"Best: '{ranked[0]['subject']}' ({ranked[0]['score']}/100). "
        + (f"{sum(1 for r in scored if r['score'] < 70)} variant(s) need a rewrite." if any(r["score"] < 70 for r in scored) else "All variants are usable."),
    }


# ── body audit ─────────────────────────────────────────────────
CTA_RE = re.compile(
    r"(worth (a look|exploring|a chat|a conversation|15 minutes|a call))|open to|interested in|"
    r"would it make sense|mind if|can i send|should i send|does (this|that) (resonate|sound)|"
    r"(book|grab|schedule|find) (a|some) time|are you the right person|who (would be|is) the (right|best) person|"
    r"let me know|thoughts\?|make sense to|free (for|to)|(this|next) (week|thursday|tuesday|wednesday|monday|friday)",
    re.I,
)
INTEREST_CTA_RE = re.compile(r"(worth (a look|exploring|a chat|a conversation)|open to|interested in|would it make sense|mind if|can i send|should i send|does (this|that) (resonate|sound)|are you the right person|who (would be|is) the (right|best) person|make sense to)\b", re.I)
LINK_RE = re.compile(r"(https?://\S+|www\.\S+)", re.I)
ATTACH_RE = re.compile(r"\b(attached|attachment|see the deck|pdf attached|screenshot below|image below)\b", re.I)


@AGENT.tool
def audit_email_body(body: str, step: int = 1) -> dict:
    """Audit a cold-email body: word count, readability, you:I ratio, CTA count/type, links, spam and fluff.

    Call after drafting each step. Returns a 0-100 score with the exact rules failed and
    what to change. Step 1 is held to stricter rules (no links, <= 125 words).

    Args:
        body: The email body text (no subject line).
        step: Position in the sequence, 1 = first touch. Later steps may include one link.
    """
    if not body or not body.strip():
        raise ToolError("Email body is empty.")
    if len(body) > 20_000:
        raise ToolError("Body over 20k chars — a cold email is under 1,000.")
    if step < 1 or step > 12:
        raise ToolError("step must be between 1 and 12.")
    ws = text.words(body)
    n_words = len(ws)
    read = text.readability(body)
    ratio = c.you_i_ratio(body)
    ctas = CTA_RE.findall(body)
    n_cta = len(ctas)
    interest_cta = bool(INTEREST_CTA_RE.search(body))
    links = LINK_RE.findall(body)
    spam = c.spam_hits(body)
    fluff = c.fluff_hits(body)
    tokens = c.unresolved_tokens(body)
    exclam = body.count("!")
    questions = body.count("?")
    paragraphs = [p for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]
    longest_para = max((len(text.words(p)) for p in paragraphs), default=n_words)
    first_line = paragraphs[0].strip().splitlines()[0] if paragraphs else ""
    score = 100
    fixes: list[str] = []
    if n_words > 150:
        score -= 25
        fixes.append(f"{n_words} words — cut to ≤ 125 (≤ 80 for step 1 is better)")
    elif n_words > 125:
        score -= 12
        fixes.append(f"{n_words} words — trim to ≤ 125")
    elif n_words < 30:
        score -= 10
        fixes.append(f"{n_words} words — too thin to carry observation + problem + proof + ask")
    fre = read.get("flesch_reading_ease") or 0
    if fre < 50:
        score -= 15
        fixes.append(f"Flesch Reading Ease {fre} — shorten sentences, drop jargon (target ≥ 60)")
    elif fre < 60:
        score -= 6
        fixes.append(f"Flesch Reading Ease {fre} — target ≥ 60")
    if ratio["i_we_words"] and ratio["you_to_i_ratio"] < 1.0:
        score -= 15
        fixes.append(f"you:I ratio {ratio['you_to_i_ratio']} — it's about them; rewrite 'we/I' sentences around 'you'")
    elif ratio["i_we_words"] and ratio["you_to_i_ratio"] < 1.5:
        score -= 6
        fixes.append(f"you:I ratio {ratio['you_to_i_ratio']} — aim ≥ 1.5")
    if n_cta == 0:
        score -= 25
        fixes.append("no CTA — end with one interest question ('Worth a look?')")
    elif n_cta > 2:
        score -= 15
        fixes.append(f"{n_cta} asks — keep exactly one")
    elif not interest_cta and step <= 2:
        score -= 6
        fixes.append("CTA asks for time/commitment — for step 1-2 use an interest CTA instead")
    if links and step == 1:
        score -= 15
        fixes.append("link in step 1 — remove (hurts deliverability, screams mass mail)")
    elif len(links) > 1:
        score -= 10
        fixes.append(f"{len(links)} links — max one")
    if spam:
        score -= min(30, 10 * len(spam))
        fixes.append("spam words: " + ", ".join(spam))
    if fluff:
        score -= min(30, 12 * len(fluff))
        fixes.append("fluff phrases: " + "; ".join(f"'{f}'" for f in fluff))
    if tokens:
        score -= 30
        fixes.append("unresolved merge tokens: " + ", ".join(tokens))
    if exclam:
        score -= 5 * min(exclam, 3)
        fixes.append(f"{exclam} exclamation mark(s) — remove")
    if ATTACH_RE.search(body):
        score -= 10
        fixes.append("attachment/image reference — cold step attachments get filtered; describe, don't attach")
    if longest_para > 60:
        score -= 8
        fixes.append(f"a {longest_para}-word paragraph — break into ≤ 3-line blocks")
    if re.match(r"^\s*(hi|hello|hey|dear)\b[^\n]{0,40}$", first_line, re.I):
        # greeting on its own line — check the *next* line instead
        first_line = paragraphs[1].strip().splitlines()[0] if len(paragraphs) > 1 else ""
    if re.match(r"^\s*(i|we|my|our)\b", first_line, re.I):
        score -= 10
        fixes.append("first line starts with I/we — open with an observation about them")
    if not re.search(r"\d", body):
        score -= 5
        fixes.append("no number anywhere — add one concrete proof point (%, $, weeks, customers)")
    score = max(0, min(100, score))
    return {
        "score": score,
        "grade": "send" if score >= 80 else "fix then send" if score >= 60 else "rewrite",
        "words": n_words,
        "flesch_reading_ease": fre,
        "fk_grade": read.get("fk_grade"),
        "you_to_i_ratio": ratio["you_to_i_ratio"],
        "cta_count": n_cta,
        "cta_type": "interest" if interest_cta else ("time/commitment" if n_cta else "none"),
        "links": len(links),
        "questions": questions,
        "spam_words": spam,
        "fluff_phrases": fluff,
        "unresolved_tokens": tokens,
        "paragraphs": len(paragraphs),
        "longest_paragraph_words": longest_para,
        "fixes": fixes,
        "verdict": f"{score}/100 — " + (fixes[0] if fixes else "clean: short, readable, one interest CTA."),
    }


# ── personalisation ────────────────────────────────────────────
@AGENT.tool
def check_personalization(email: str, prospect: dict, preview_chars: int = 90) -> dict:
    """Verify an email is actually personalised: name/company/trigger present, tokens resolved, preview line specific.

    Call on the final text of each step before sending. Prospect fields you can pass:
    first_name, last_name, company, title, trigger (the observed event), city, mutual.

    Args:
        email: Full email text (subject + body is fine).
        prospect: Dict of known prospect fields, e.g. {"first_name": "Dana", "company": "Acme", "trigger": "Series B"}.
        preview_chars: How many leading body characters count as the inbox preview (default 90).
    """
    if not email or not email.strip():
        raise ToolError("Email text is empty.")
    if len(email) > 20_000:
        raise ToolError("Email over 20k chars.")
    if not isinstance(prospect, dict):
        raise ToolError("prospect must be a dict of fields.")
    low = email.lower()
    fields = {k: str(v).strip() for k, v in prospect.items() if v is not None and str(v).strip()}
    present, missing = [], []
    for key in ("first_name", "company", "trigger", "title", "city", "mutual"):
        val = fields.get(key)
        if not val:
            continue
        # a trigger counts as present if ≥ 60% of its content words appear
        vw = [w.lower() for w in text.words(val) if w.lower() not in text.STOPWORDS]
        hit = (val.lower() in low) or (vw and sum(1 for w in vw if w in low) / len(vw) >= 0.6)
        (present if hit else missing).append(key)
    tokens = c.unresolved_tokens(email)
    body = re.sub(r"^\s*subject\s*:.*$", "", email, flags=re.I | re.M).strip()
    body_wo_greeting = re.sub(r"^\s*(hi|hello|hey|dear)\b[^\n]*\n", "", body, flags=re.I).strip()
    preview = body_wo_greeting[:preview_chars]
    plow = preview.lower()
    preview_specific = any(
        fields.get(k, "").lower() and fields[k].lower() in plow for k in ("company", "trigger", "city", "mutual")
    ) or bool(re.search(r"\d", preview))
    generic_preview = bool(c.fluff_hits(preview)) or re.match(r"^\s*(i|we|my|our)\b", preview, re.I) is not None
    company_only = present == ["company"] and "first_name" not in present and not fields.get("first_name")
    level = "deep" if ("trigger" in present or "mutual" in present) and preview_specific else "surface" if present else "none"
    fixes = []
    if tokens:
        fixes.append("resolve merge tokens before sending: " + ", ".join(tokens))
    if "first_name" in missing:
        fixes.append("use their first name in the greeting")
    if "trigger" in missing:
        fixes.append("the trigger you know isn't referenced — put it in sentence one")
    if not preview_specific or generic_preview:
        fixes.append(f"first {preview_chars} chars are generic — the inbox preview must show something only true of them")
    if company_only or level == "surface":
        fixes.append("only name/company merged — that's mail-merge, not personalisation; add a trigger, a post, or a peer")
    return {
        "personalization_level": level,
        "fields_present": present,
        "fields_missing": missing,
        "unresolved_tokens": tokens,
        "preview_text": preview,
        "preview_is_specific": preview_specific and not generic_preview,
        "fixes": fixes,
        "ready": not tokens and level == "deep" and not generic_preview,
        "verdict": {"deep": "Personalised on a real trigger.", "surface": "Mail-merge level only.", "none": "Nothing prospect-specific found."}[level],
    }


# ── sequence scheduling ────────────────────────────────────────
PREFERRED_DAYS = {1, 2, 3}  # Tue, Wed, Thu


@AGENT.tool
def schedule_sequence(
    start_date: str,
    gaps_days: list[int] | None = None,
    holidays: list[str] | None = None,
    prefer_midweek: bool = True,
    send_hour_local: int = 8,
) -> dict:
    """Turn a start date and inter-step gaps into exact send dates that skip weekends/holidays and favour Tue-Thu.

    Call once the step count is decided. Default gaps [0, 3, 4, 5, 7] = 5 steps over ~19 days.

    Args:
        start_date: First send date, YYYY-MM-DD.
        gaps_days: Days after the previous step for each step; first entry is offset from start (usually 0). Max 12 steps.
        holidays: Dates (YYYY-MM-DD) to never send on.
        prefer_midweek: If a step lands on Monday or Friday, nudge it to the nearest Tue-Thu (never backwards past the previous step).
        send_hour_local: Recommended local send hour for the prospect (default 8 = 8am, before inbox triage).
    """
    start = c.to_date(start_date)
    gaps = gaps_days if gaps_days else [0, 3, 4, 5, 7]
    if len(gaps) > 12:
        raise ToolError("Max 12 steps in a sequence.")
    if any((not isinstance(g, int)) or g < 0 or g > 60 for g in gaps):
        raise ToolError("Each gap must be an integer 0-60 days.")
    if not 0 <= send_hour_local <= 23:
        raise ToolError("send_hour_local must be 0-23.")
    hols = c.parse_holidays(holidays or [])
    steps = []
    current = start
    prev: date | None = None
    for i, gap in enumerate(gaps, 1):
        d = (prev + timedelta(days=gap)) if prev is not None else start + timedelta(days=gap)
        while d.weekday() >= 5 or d in hols:
            d += timedelta(days=1)
        if prefer_midweek and d.weekday() not in PREFERRED_DAYS:
            # Monday → Tuesday; Friday → Thursday (only if that keeps ≥ 2 days after the previous step)
            nudged = d + timedelta(days=1) if d.weekday() == 0 else d - timedelta(days=1)
            if nudged not in hols and (prev is None or (nudged - prev).days >= 2):
                d = nudged
        if prev is not None and d <= prev:
            d = dates.add_business_days(prev, 1, hols)
        steps.append({"step": i, "date": d.isoformat(), "weekday": d.strftime("%a"), "day_offset": (d - start).days, "send_local_time": f"{send_hour_local:02d}:00"})
        prev = d
        current = d
    span = (current - start).days
    return {
        "start_date": start.isoformat(),
        "steps": steps,
        "total_span_days": span,
        "last_send": current.isoformat(),
        "stop_rule": "Any reply (including out-of-office) pauses the sequence for that contact.",
        "verdict": f"{len(steps)} steps over {span} days, all on business days"
        + (", nudged to Tue-Thu where possible." if prefer_midweek else "."),
    }


# ── campaign math ──────────────────────────────────────────────
@AGENT.tool
def estimate_outreach(
    target_meetings: int,
    reply_rate_pct: float = 2.0,
    positive_share_pct: float = 50.0,
    meeting_rate_pct: float = 60.0,
    steps: int = 4,
    daily_limit_per_mailbox: int = 50,
    days_available: int = 20,
    bounce_rate_pct: float = 3.0,
) -> dict:
    """Work backwards from a meeting target to prospects, sends, mailboxes and days needed.

    Call whenever the user states a goal (meetings, demos, pipeline). Uses conservative
    defaults: 2% reply rate, half of replies positive, 60% of positives book.

    Args:
        target_meetings: Meetings the campaign must produce.
        reply_rate_pct: Total reply rate across the sequence, percent of prospects (default 2.0).
        positive_share_pct: Share of replies that are positive/interested (default 50).
        meeting_rate_pct: Share of positive replies that turn into a booked meeting (default 60).
        steps: Emails per prospect in the sequence (default 4).
        daily_limit_per_mailbox: Max sends per mailbox per day, 50 is the safe ceiling for a warmed domain.
        days_available: Business days the campaign can run (default 20 = one month).
        bounce_rate_pct: Expected bounce rate; lists with > 5% bounce damage sender reputation.
    """
    if target_meetings < 1 or target_meetings > 10_000:
        raise ToolError("target_meetings must be 1-10000.")
    for name, v, hi in (("reply_rate_pct", reply_rate_pct, 60), ("positive_share_pct", positive_share_pct, 100), ("meeting_rate_pct", meeting_rate_pct, 100), ("bounce_rate_pct", bounce_rate_pct, 50)):
        if v <= 0 and name != "bounce_rate_pct" or v < 0 or v > hi:
            raise ToolError(f"{name} must be between 0 and {hi}.")
    if steps < 1 or steps > 12 or daily_limit_per_mailbox < 1 or days_available < 1:
        raise ToolError("steps 1-12, daily_limit_per_mailbox ≥ 1, days_available ≥ 1.")
    p_meet = (reply_rate_pct / 100) * (positive_share_pct / 100) * (meeting_rate_pct / 100)
    prospects_needed = math.ceil(target_meetings / p_meet)
    list_size = math.ceil(prospects_needed / (1 - bounce_rate_pct / 100))
    replies = round(prospects_needed * reply_rate_pct / 100, 1)
    positives = round(replies * positive_share_pct / 100, 1)
    # ~70% of replies arrive from step 2+, so multi-step sends are worth it; conservatively all steps go out
    total_sends = prospects_needed * steps
    capacity_per_mailbox = daily_limit_per_mailbox * days_available
    mailboxes = math.ceil(total_sends / capacity_per_mailbox)
    daily_new_prospects = math.ceil(prospects_needed / days_available)
    warnings = []
    if bounce_rate_pct > 5:
        warnings.append("bounce rate > 5% — verify the list (email validation) before sending or the domain gets flagged")
    if reply_rate_pct > 10:
        warnings.append("reply rate > 10% is exceptional — plan on the median (2%) and treat this as upside")
    if mailboxes > 1:
        warnings.append(f"{mailboxes} mailboxes needed — use secondary domains (not the main company domain) and warm each 2-3 weeks first")
    return {
        "target_meetings": target_meetings,
        "prospect_to_meeting_rate_pct": round(100 * p_meet, 2),
        "prospects_needed": prospects_needed,
        "list_size_incl_bounces": list_size,
        "expected_replies": replies,
        "expected_positive_replies": positives,
        "total_sends": total_sends,
        "sends_per_day": math.ceil(total_sends / days_available),
        "new_prospects_per_day": daily_new_prospects,
        "mailboxes_needed": mailboxes,
        "days_available": days_available,
        "warnings": warnings,
        "verdict": f"{target_meetings} meetings needs ~{prospects_needed:,} prospects ({list_size:,} raw) → {total_sends:,} sends over {days_available} days = {mailboxes} mailbox(es) at ≤ {daily_limit_per_mailbox}/day.",
    }
