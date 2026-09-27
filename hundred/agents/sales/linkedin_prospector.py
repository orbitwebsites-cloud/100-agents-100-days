"""LinkedIn Prospector — hooks pulled from the profile, notes that fit the limits, and a multi-touch plan that respects LinkedIn's caps."""

from __future__ import annotations

import math
import re
from datetime import timedelta

from ...core import Agent, ToolError
from ...lib import text
from . import _common as c

AGENT = Agent(
    slug="linkedin-prospector",
    name="LinkedIn Prospector",
    category="sales",
    tagline="LinkedIn outreach that gets accepted and answered: profile-mined hooks, limit-checked notes, and a touch plan inside the weekly caps.",
    description=(
        "Runs social selling like a top SDR: extracts real conversation hooks from a pasted profile "
        "(job changes, tenure, posts, mutuals, headline claims), checks every connection note, InMail and "
        "message against LinkedIn's character limits and reply-killing patterns, plans a multi-touch "
        "sequence (view → engage → connect → message → email) on real dates within the ~100-invites-a-week cap, "
        "and computes how many invites a meeting target actually needs."
    ),
    triggers=[
        "write a LinkedIn connection request / note",
        "LinkedIn outreach sequence or cadence",
        "find a hook from this LinkedIn profile",
        "write an InMail or LinkedIn message to a prospect",
        "how many LinkedIn connection requests can I send",
        "LinkedIn prospecting plan for my SDR",
    ],
    examples=[
        "Here's the prospect's LinkedIn profile text. Write a connection note and the first message.",
        "Build a 3-week LinkedIn + email touch plan for 40 VP Marketing prospects starting Monday.",
        "Is this InMail too long? 'Hi Sarah, I noticed …' (pasted).",
        "I need 12 meetings a month from LinkedIn. How many invites is that and can one profile do it?",
    ],
    connectors=["LinkedIn Sales Navigator", "HubSpot", "Salesforce", "Apollo", "Lemlist", "Gmail"],
    playbook="""
    ## Standard
    You are the SDR whose connection requests get accepted at 40%+ and whose messages
    get answered because they never read as a pitch. Excellent means: the note could
    only have been written to this one person, nothing is sold before the connection is
    accepted, and every touch respects LinkedIn's limits so the account never gets
    restricted. The one metric: **conversations started per 100 invites**. Acceptance
    is a means; a reply is the outcome.

    ## Intake
    You need: the prospect's profile (pasted text, or the fields you have: headline,
    current role, start date, recent posts, mutuals), what you sell and to whom, and the
    campaign shape (how many prospects, start date). If there is no profile at all, ask
    for it (1 question) — a hook-less note is a mass note. Otherwise proceed and state
    assumptions.

    ## Procedure
    1. **Mine the profile.** Call `linkedin_prospector__extract_hooks` with the profile
       text. It finds and ranks hooks: new role (< 90 days = the best trigger), promotion,
       tenure milestone, headline claims, recent post topics, shared connections,
       school/city, and company signals. Use the top hook; never use two.
    2. **Write the connection note** (optional but use it when you have a hook): ≤ 300
       chars, no pitch, no link, one specific reference, no ask beyond connecting. Call
       `linkedin_prospector__check_message` with `kind="connection_note"` and `premium`
       (false if the sender has a free LinkedIn account). It enforces the note limit —
       300 chars on Premium/Sales Navigator, 200 on a free account (LinkedIn's help page;
       free accounts also get only a few noted invites a month) — warns above 200 either
       way, and catches pitch words, links, "I/my company" openers and template phrases.
       Rewrite until it passes. Ask whether the account is free or Premium if you don't know.
    3. **Write the first message** for after acceptance (24-48 h later): a thank-you that
       continues the hook + one open question about their world. Zero pitch. Check with
       `check_message` (`kind="message"`, target ≤ 500 chars). InMails (`kind="inmail"`)
       get a subject ≤ 200 chars and body ≤ 1,900 chars; the tool checks both and warns
       past 500 chars because reply rates fall with length.
    4. **Plan the touches.** Call `linkedin_prospector__plan_sequence` with the start date
       and prospect count. It returns a dated plan (profile view → post engagement →
       connect → message 1 → message 2 → email bridge → breakup) on business days and
       checks the daily/weekly invite load against the caps (≈100 invites/week; keep
       ≤ 20/day; withdraw pending invites older than 3 weeks). Reply = stop the sequence.
    5. **Size the campaign** with `linkedin_prospector__capacity_plan` when the user has a
       meeting target: it converts acceptance → reply → meeting rates into invites needed
       and weeks required, and says whether one account can carry it or the list must be
       split across reps or moved partly to email.
    6. **Deliver** in the output format. Include char counts on every message — the user
       will paste them and cannot count.

    ## Frameworks
    - **Hook hierarchy:** new role (< 90 days) > their own post (quote a line) > mutual
      connection (named) > company trigger (funding, hiring, launch) > shared background
      (school, city, former employer) > headline claim. Never "I see we're both in SaaS".
    - **No-pitch rule:** the connection note and message 1 contain zero product language.
      The pitch arrives in message 2 or the email bridge, and only as a question.
    - **Limits (LinkedIn, as commonly enforced):** connection note 300 chars on
      Premium/Sales Navigator, 200 on free accounts (which also get only ~3-5 noted
      invites a month — see linkedin.com/help/linkedin/answer/a563153); ~100
      invites/week for most accounts (Sales Navigator adds InMail credits, not invites);
      InMail subject 200 / body 1,900 chars; pending invites count against you — withdraw
      after ~3 weeks. Acceptance rates: notes with a specific hook ≈ 30-50%; blank
      requests to warm-ish profiles often accept at similar rates — the note's job is to
      set up the conversation, not to win acceptance.
    - **Touch cadence:** Day 0 view + engage → Day 1 connect → accept + 1 day message 1
      → +3 days message 2 (a question with a light value pointer) → +4 days email bridge
      → +7 days breakup. 5-7 touches over 2-3 weeks across 2 channels.
    - **Engagement first:** a thoughtful comment on their post 24 h before the invite
      lifts acceptance more than any wording in the note.

    ## Output format
    ```
    ## Hook
    <the one hook, with the profile evidence>

    ## Connection note (<n>/300 chars)
    <note>

    ## Message 1 — after acceptance (<n> chars)
    <message>

    ## Message 2 — Day +3 (<n> chars)
    <message with one question>

    ## Email bridge — Day +7
    Subject: <…>
    <≤ 80 words>

    ## Touch plan
    | Day | Date | Channel | Action |
    |---|---|---|---|

    ## Capacity
    <invites/day, weeks, accounts needed — from the tools>
    ```

    ## Anti-patterns
    - Pitching in the connection note. Acceptance drops and the profile is marked as a seller.
    - "I'd love to add you to my professional network." — the default text; it says nothing.
    - Notes that start with "I". Start with them.
    - Sending 100 invites on Monday. Spread ≤ 20/day; the algorithm notices bursts.
    - Automation tools that scrape or auto-send from the account — restriction risk.
    - Two hooks in one note. One is specific; two is a mail merge.
    - Ignoring pending invites. Withdraw at 3 weeks and try a different channel.
    """,
)

LIMITS = {
    "connection_note": {"body": 300, "warn": 200},
    "message": {"body": 8000, "warn": 500},
    "inmail": {"subject": 200, "body": 1900, "warn": 500},
    "headline": {"body": 220, "warn": 220},
}
PITCH_RE = re.compile(r"\b(our (?:platform|product|solution|software|tool|service|company)|we help|we provide|we offer|we are a|we're a|demo|free trial|pricing|schedule a call|book a (?:call|meeting|time)|15 minutes|quick call|discount|leading provider|award-winning|synergy|partnership opportunity)\b", re.I)
TEMPLATE_RE = re.compile(r"\b(add you to my (?:professional )?network|expand my network|grow my network|like-minded|fellow (?:professional|leader)|came across your profile|i see (?:we're|we are) both|i noticed (?:we're|we are) both|would love to connect|let'?s connect|i'?d love to connect|great to connect)\b", re.I)
LINK_RE = re.compile(r"(https?://\S+|www\.\S+|calendly|hubspot\.com/meetings|lnkd\.in)", re.I)


@AGENT.tool
def check_message(message: str, kind: str = "connection_note", subject: str = "", premium: bool = True) -> dict:
    """Check a LinkedIn connection note, message or InMail against character limits and reply-killing patterns.

    Call on every draft. kind: connection_note (300 chars on Premium/Sales Navigator; LinkedIn's
    help page states 200 for free accounts), message (post-accept DM), inmail (subject 200 /
    body 1,900), or headline (220). Returns counts, violations and a 0-100 score.

    Args:
        message: The note/message body.
        kind: connection_note, message, inmail or headline.
        subject: InMail subject line (only for kind="inmail").
        premium: True if the sender has Premium or Sales Navigator (300-char notes); False for a free account, where the note box stops at 200 chars and only a few noted invites are allowed per month.
    """
    k = kind.strip().lower()
    if k not in LIMITS:
        raise ToolError("kind must be connection_note, message, inmail or headline.")
    if not message or not message.strip():
        raise ToolError("message is empty.")
    if len(message) > 20_000:
        raise ToolError("message over 20k chars.")
    lim = dict(LIMITS[k])
    if k == "connection_note" and not premium:
        lim["body"] = 200
    n = len(message)
    ws = text.words(message)
    fixes, score = [], 100
    if n > lim["body"]:
        score -= 40
        fixes.append(f"{n} chars — LinkedIn limit is {lim['body']}; cut {n - lim['body']} chars or it won't send")
    elif n > lim["warn"] and k != "headline" and lim["warn"] < lim["body"]:
        score -= 10
        fixes.append(f"{n} chars — over the {lim['warn']}-char sweet spot; shorter gets more replies")
    if k == "inmail":
        if not subject.strip():
            score -= 15
            fixes.append("InMail needs a subject (≤ 200 chars, specific, no pitch)")
        elif len(subject) > lim["subject"]:
            score -= 20
            fixes.append(f"subject {len(subject)} chars — limit {lim['subject']}")
        elif len(subject) > 60:
            score -= 5
            fixes.append(f"subject {len(subject)} chars — keep ≤ 60 so it isn't truncated")
    pitch = [m.group(0) for m in PITCH_RE.finditer(message)]
    if pitch and k in ("connection_note",):
        score -= 30
        fixes.append("pitch language in a connection note: " + ", ".join(sorted(set(p.lower() for p in pitch))[:4]))
    elif pitch and k == "message":
        score -= 15
        fixes.append("pitch language in message 1 — save it for message 2 and phrase it as a question: " + ", ".join(sorted(set(p.lower() for p in pitch))[:3]))
    tmpl = [m.group(0) for m in TEMPLATE_RE.finditer(message)]
    if tmpl:
        score -= 20
        fixes.append("template phrases: " + ", ".join(sorted(set(t.lower() for t in tmpl))[:3]))
    links = LINK_RE.findall(message)
    if links and k == "connection_note":
        score -= 25
        fixes.append("link in a connection note — remove; LinkedIn and the prospect both read it as spam")
    elif len(links) > 1:
        score -= 10
        fixes.append(f"{len(links)} links — max one")
    stripped = re.sub(r"^\s*(hi|hello|hey|dear)\b[^,\n]*[,\n!]\s*", "", message, flags=re.I).strip()
    if re.match(r"^(i|my|we|our)\b", stripped, re.I):
        score -= 10
        fixes.append("opens with I/my/we — open with something about them")
    if "?" not in message and k in ("message", "inmail"):
        score -= 10
        fixes.append("no question — give them an easy reply hook")
    if message.count("?") > 2:
        score -= 5
        fixes.append(f"{message.count('?')} questions — ask one")
    if "!" in message:
        score -= 5
        fixes.append("exclamation marks read as salesy — remove")
    tokens = c.unresolved_tokens(message)
    if tokens:
        score -= 30
        fixes.append("unresolved merge tokens: " + ", ".join(tokens))
    ratio = c.you_i_ratio(message)
    if ratio["i_we_words"] >= 3 and ratio["you_to_i_ratio"] < 1:
        score -= 10
        fixes.append(f"you:I ratio {ratio['you_to_i_ratio']} — more about them")
    if k == "connection_note" and n < 40:
        score -= 10
        fixes.append("under 40 chars — too thin to carry a specific hook (or send with no note at all)")
    score = max(0, min(100, score))
    return {
        "kind": k,
        "chars": n,
        "limit": lim["body"],
        "account": ("premium" if premium else "free") if k == "connection_note" else None,
        "fits": n <= lim["body"],
        "over_by": max(0, n - lim["body"]),
        "words": len(ws),
        "subject_chars": len(subject) if k == "inmail" else None,
        "pitch_phrases": sorted(set(p.lower() for p in pitch)),
        "template_phrases": sorted(set(t.lower() for t in tmpl)),
        "links": len(links),
        "questions": message.count("?"),
        "you_to_i_ratio": ratio["you_to_i_ratio"],
        "score": score,
        "grade": "send" if score >= 80 else "fix" if score >= 60 else "rewrite",
        "fixes": fixes,
        "verdict": f"{n}/{lim['body']} chars, score {score}/100 — " + (fixes[0] if fixes else "clean."),
    }


MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
_MONTH_NUM = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
DATE_RANGE_RE = re.compile(rf"\b((?:{MONTHS})[a-z]*\.?\s+(\d{{4}}))\s*[-–—]\s*(present|current|now|(?:{MONTHS})[a-z]*\.?\s+\d{{4}})", re.I)
TENURE_RE = re.compile(r"\b(\d+)\s*(?:yrs?|years?)(?:\s*(\d+)\s*(?:mos?|months?))?\b|\b(\d+)\s*(?:mos?|months?)\b", re.I)
POST_RE = re.compile(r"^\s*(?:post|posted|activity|shared|wrote|published|commented)\s*[:\-–]\s*(.+)$", re.I | re.M)
MUTUAL_RE = re.compile(r"\b(\d+)\s+mutual connections?\b|\bmutual(?:s| connections?)?\s*[:\-–]\s*([^\n]+)", re.I)
SCHOOL_RE = re.compile(r"\b(university|college|school of|institute|mba|b\.?s\.?c?|b\.?a\.?)\b[^\n]{0,60}", re.I)
COMPANY_SIGNAL_RE = re.compile(r"\b(series [a-d]|raised|funding|acquired|acquisition|ipo|hiring|we'?re hiring|launched|launch|expanding|opened|new office|rebrand|partnership)\b", re.I)
PROMO_RE = re.compile(r"\b(promoted|promotion|now (?:leading|heading)|stepping into|new role|excited to (?:share|announce|join)|joined|starting a new position)\b", re.I)
HEADLINE_CLAIM_RE = re.compile(r"\b(helping|i help|building|scaling|driving|obsessed|passionate about|on a mission|transforming)\b[^\n|.]{0,80}", re.I)


@AGENT.tool
def extract_hooks(profile_text: str, today: str = "", my_school: str = "", my_city: str = "", my_former_companies: list[str] | None = None) -> dict:
    """Mine a pasted LinkedIn profile for ranked conversation hooks: new role, promotion, tenure, posts, mutuals, shared background.

    Call first. Paste the profile as text (headline, about, experience with dates like
    "Jan 2026 - Present", activity/posts, education, mutual connections).

    Args:
        profile_text: The profile text as copied from LinkedIn (max 60k chars).
        today: Today's date YYYY-MM-DD for tenure maths (default: today).
        my_school: Your school, to detect a shared alma mater (optional).
        my_city: Your city, to detect a shared location (optional).
        my_former_companies: Companies you've worked at, to detect shared employers (optional).
    """
    if not profile_text or not profile_text.strip():
        raise ToolError("profile_text is empty.")
    if len(profile_text) > 60_000:
        raise ToolError("profile_text over 60k chars — paste the profile, not the whole feed.")
    base = c.to_date(today)
    hooks = []
    low = profile_text.lower()
    # current role start → months in role
    months_in_role = None
    for m in DATE_RANGE_RE.finditer(profile_text):
        if m.group(3).lower() in ("present", "current", "now"):
            mon = m.group(1).split()[0][:3].lower()
            yr = int(m.group(2))
            if mon in _MONTH_NUM:
                mi = (base.year - yr) * 12 + (base.month - _MONTH_NUM[mon])
                months_in_role = mi if months_in_role is None else min(months_in_role, mi)
    if months_in_role is None:
        for m in TENURE_RE.finditer(profile_text):
            if m.group(3):
                months_in_role = int(m.group(3))
            elif m.group(1):
                months_in_role = int(m.group(1)) * 12 + int(m.group(2) or 0)
            break
    if months_in_role is not None:
        if months_in_role <= 3:
            hooks.append({"type": "new_role", "priority": 1, "evidence": f"{months_in_role} month(s) in current role", "angle": "Congratulate on the new role; ask what they're prioritising in the first 90 days — new leaders buy."})
        elif months_in_role <= 12:
            hooks.append({"type": "first_year", "priority": 3, "evidence": f"{months_in_role} months in role", "angle": "First-year leaders are still setting up their stack — ask what they've changed so far."})
        elif months_in_role % 12 == 0 and months_in_role >= 24:
            hooks.append({"type": "tenure_anniversary", "priority": 6, "evidence": f"{months_in_role // 12}-year anniversary in role", "angle": "Light anniversary mention; ask what's changed most since they started."})
    for m in PROMO_RE.finditer(profile_text):
        hooks.append({"type": "promotion_or_move", "priority": 2, "evidence": profile_text[max(0, m.start() - 40): m.end() + 60].strip().replace("\n", " "), "angle": "Reference the move specifically; no pitch."})
        break
    posts = [p.strip() for p in POST_RE.findall(profile_text)][:5]
    for p in posts[:2]:
        hooks.append({"type": "recent_post", "priority": 2, "evidence": p[:160], "angle": "Quote or paraphrase one line and add a genuine reaction or question. Comment on the post 24h before connecting."})
    mm = MUTUAL_RE.search(profile_text)
    if mm:
        count = mm.group(1)
        names = mm.group(2)
        hooks.append({"type": "mutual_connection", "priority": 3 if names else 5, "evidence": (names or f"{count} mutual connections").strip()[:160], "angle": "Name the mutual (only if you actually know them); mention how you know them."})
    for m in COMPANY_SIGNAL_RE.finditer(profile_text):
        hooks.append({"type": "company_signal", "priority": 4, "evidence": profile_text[max(0, m.start() - 50): m.end() + 50].strip().replace("\n", " "), "angle": "Tie the signal to a question about the resulting workload/priorities."})
        break
    if my_school and my_school.strip().lower() in low:
        hooks.append({"type": "shared_school", "priority": 5, "evidence": my_school, "angle": "Shared alma mater — mention it once; do not make it the whole note."})
    if my_city and my_city.strip().lower() in low:
        hooks.append({"type": "shared_city", "priority": 6, "evidence": my_city, "angle": "Shared city — good for an in-person coffee ask later."})
    for comp in (my_former_companies or [])[:20]:
        if comp.strip() and comp.strip().lower() in low:
            hooks.append({"type": "shared_former_employer", "priority": 4, "evidence": comp, "angle": "Alumni of the same company — a strong trust signal; ask about their time there."})
            break
    # a pasted profile usually starts with the name, then the headline — look at the first 3 non-empty lines
    head_lines = [ln for ln in profile_text.splitlines() if ln.strip()][:3]
    hm = next((m for m in (HEADLINE_CLAIM_RE.search(ln) for ln in head_lines) if m), None)
    if hm:
        hooks.append({"type": "headline_claim", "priority": 7, "evidence": hm.group(0).strip()[:120], "angle": "Ask how they're doing that — genuinely curious, not challenging."})
    hooks.sort(key=lambda h: h["priority"])
    schools = [s.group(0).strip() for s in SCHOOL_RE.finditer(profile_text)][:2]
    return {
        "months_in_current_role": months_in_role,
        "hooks": hooks,
        "best_hook": hooks[0] if hooks else None,
        "recent_posts_found": len(posts),
        "education_found": schools,
        "verdict": (f"Best hook: {hooks[0]['type']} — {hooks[0]['evidence'][:80]}" if hooks else "No specific hook found — get their recent activity or a mutual before sending; a hook-less note is a mass note."),
    }


DEFAULT_TOUCHES = [
    (0, "linkedin", "View profile + like/comment on a recent post (thoughtful, 1-2 sentences)"),
    (1, "linkedin", "Send connection request (note ≤ 300 chars, hook only)"),
    (3, "linkedin", "Message 1 after acceptance: thanks + continue hook + one open question (if not accepted, wait)"),
    (6, "linkedin", "Message 2: one question tied to their priorities + light value pointer (no link)"),
    (10, "email", "Email bridge: ≤ 80 words, reference the LinkedIn thread, one interest CTA"),
    (14, "linkedin", "Engage on another post or share a relevant resource in a DM (no ask)"),
    (18, "email", "Breakup: close the loop politely, leave the door open"),
    (21, "linkedin", "Withdraw the invite if still pending; move to a nurture list"),
]


@AGENT.tool
def plan_sequence(start_date: str, prospects: int = 1, invites_per_day_cap: int = 20, weekly_invite_cap: int = 100, holidays: list[str] | None = None) -> dict:
    """Date a LinkedIn + email touch plan on business days and check the invite load against LinkedIn's caps.

    Call once the messages are written. Returns each touch with a calendar date, the invite
    ramp (prospects per day), and warnings if the list can't be worked inside the caps.

    Args:
        start_date: Day 0 of the sequence, YYYY-MM-DD.
        prospects: How many prospects enter the sequence (1-5000).
        invites_per_day_cap: Max invites you'll send per day (default 20 — safe pace).
        weekly_invite_cap: LinkedIn's weekly invite ceiling for the account (default 100).
        holidays: Dates (YYYY-MM-DD) to skip.
    """
    start = c.to_date(start_date)
    if not 1 <= prospects <= 5000:
        raise ToolError("prospects must be 1-5000.")
    if invites_per_day_cap < 1 or weekly_invite_cap < 1:
        raise ToolError("caps must be ≥ 1.")
    hols = c.parse_holidays(holidays or [])
    while start.weekday() >= 5 or start in hols:
        start += timedelta(days=1)
    plan = []
    for offset, channel, action in DEFAULT_TOUCHES:
        d = start + timedelta(days=offset)
        while d.weekday() >= 5 or d in hols:
            d += timedelta(days=1)
        plan.append({"day": offset, "date": d.isoformat(), "weekday": d.strftime("%a"), "channel": channel, "action": action})
    per_day = min(invites_per_day_cap, math.ceil(weekly_invite_cap / 5))
    days_to_enrol = math.ceil(prospects / per_day)
    cohorts = []
    d, remaining, i = start, prospects, 1
    while remaining > 0 and i <= 400:
        while d.weekday() >= 5 or d in hols:
            d += timedelta(days=1)
        batch = min(per_day, remaining)
        cohorts.append({"cohort": i, "enrol_date": d.isoformat(), "prospects": batch})
        remaining -= batch
        d += timedelta(days=1)
        i += 1
    warnings = []
    if prospects > weekly_invite_cap:
        warnings.append(f"{prospects} prospects exceed the weekly cap ({weekly_invite_cap}) — enrolment spreads over {days_to_enrol} business days; consider splitting across reps or leading with email for part of the list")
    if invites_per_day_cap > 25:
        warnings.append("more than ~25 invites/day looks automated to LinkedIn — restriction risk")
    last_touch = plan[-1]["date"]
    finish = cohorts[-1]["enrol_date"] if cohorts else start.isoformat()
    return {
        "start": start.isoformat(),
        "touches": plan,
        "sequence_length_days": DEFAULT_TOUCHES[-1][0],
        "invites_per_day": per_day,
        "business_days_to_enrol_all": days_to_enrol,
        "enrolment_cohorts": cohorts[:60],
        "last_cohort_enrols": finish,
        "first_cohort_finishes": last_touch,
        "stop_rules": ["Any reply stops the sequence.", "Withdraw pending invites at day 21.", "If the invite is accepted late, restart from Message 1 within 24h."],
        "warnings": warnings,
        "verdict": f"{len(plan)} touches over {DEFAULT_TOUCHES[-1][0]} days; {prospects} prospects at {per_day}/day = {days_to_enrol} business day(s) to enrol." + (" " + warnings[0] if warnings else ""),
    }


@AGENT.tool
def capacity_plan(target_meetings: int, acceptance_rate_pct: float = 35.0, reply_rate_pct: float = 25.0, meeting_rate_pct: float = 30.0, weekly_invite_cap: int = 100, accounts: int = 1) -> dict:
    """Work back from a meeting target to invites needed, weeks required and whether the invite cap allows it.

    Call when the user states a goal. Defaults are conservative mid-range figures for
    personalised outreach: 35% accept, 25% of accepted reply, 30% of replies book.

    Args:
        target_meetings: Meetings the LinkedIn channel must produce.
        acceptance_rate_pct: Share of invites accepted (0-100).
        reply_rate_pct: Share of accepted connections that reply to message 1/2 (0-100).
        meeting_rate_pct: Share of repliers who book a meeting (0-100).
        weekly_invite_cap: Invites per account per week (default 100).
        accounts: Number of rep accounts working the campaign.
    """
    if target_meetings < 1 or target_meetings > 5000:
        raise ToolError("target_meetings must be 1-5000.")
    for name, v in (("acceptance_rate_pct", acceptance_rate_pct), ("reply_rate_pct", reply_rate_pct), ("meeting_rate_pct", meeting_rate_pct)):
        if not 0 < v <= 100:
            raise ToolError(f"{name} must be > 0 and ≤ 100.")
    if weekly_invite_cap < 1 or accounts < 1:
        raise ToolError("weekly_invite_cap and accounts must be ≥ 1.")
    p = (acceptance_rate_pct / 100) * (reply_rate_pct / 100) * (meeting_rate_pct / 100)
    invites = math.ceil(target_meetings / p)
    accepted = round(invites * acceptance_rate_pct / 100)
    replies = round(accepted * reply_rate_pct / 100)
    weekly_capacity = weekly_invite_cap * accounts
    weeks = math.ceil(invites / weekly_capacity)
    meetings_per_week_max = round(weekly_capacity * p, 1)
    warnings = []
    if weeks > 4:
        warnings.append(f"{weeks} weeks at the cap with {accounts} account(s) — add accounts or move part of the list to email to hit the target in a month")
    if acceptance_rate_pct > 60 or reply_rate_pct > 50:
        warnings.append("rates above typical — plan on the defaults and treat the upside as bonus")
    return {
        "target_meetings": target_meetings,
        "invite_to_meeting_rate_pct": round(100 * p, 2),
        "invites_needed": invites,
        "expected_accepted": accepted,
        "expected_replies": replies,
        "weekly_invite_capacity": weekly_capacity,
        "weeks_needed": weeks,
        "max_meetings_per_week_at_cap": meetings_per_week_max,
        "accounts_for_one_month": math.ceil(invites / (weekly_invite_cap * 4)),
        "warnings": warnings,
        "verdict": f"{target_meetings} meetings ≈ {invites} invites ({round(100 * p, 2)}% invite→meeting) → {weeks} week(s) with {accounts} account(s); one account maxes at ~{meetings_per_week_max} meetings/week.",
    }
