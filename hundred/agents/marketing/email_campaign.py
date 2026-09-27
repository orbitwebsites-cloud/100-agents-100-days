"""Email Campaign Writer — subject/preheader testing, deliverability scan, send schedule and campaign math."""

from __future__ import annotations

import re
from datetime import date, timedelta

from ...core import Agent, ToolError
from ...lib import dates, text
from ._common import caps_ratio, count_emoji, pct, require_text, spam_hits, visible_len

AGENT = Agent(
    slug="email-campaign",
    name="Email Campaign Writer",
    category="marketing",
    tagline="Write campaigns that land in the inbox and get clicked: tested subject lines, clean bodies, a real send plan.",
    description=(
        "Plans and writes marketing email campaigns end to end: sequence structure, subject lines "
        "scored for mobile truncation and spam triggers, preheaders that extend (not repeat) the "
        "subject, bodies scanned for deliverability risks, link count and one-CTA discipline, "
        "merge-token safety, a business-day send schedule with recommended windows, and a "
        "benchmark-graded readout of the numbers after the send."
    ),
    triggers=[
        "write a marketing email / newsletter / launch email",
        "email subject line ideas or testing",
        "plan an email sequence or drip campaign",
        "check this email for spam triggers",
        "when should I send this campaign",
        "analyze my email campaign results",
    ],
    examples=[
        "Write a 3-email launch sequence for our new analytics feature to 8,000 SaaS customers.",
        "Test these 5 subject lines and pick the two to A/B: …",
        "Sent 20,000, 19,650 delivered, 4,900 opens, 610 clicks, 42 unsubscribes. Good or bad?",
    ],
    connectors=["Mailchimp", "HubSpot", "Klaviyo", "Gmail", "Google Sheets", "Notion"],
    playbook="""
    ## Standard
    You are a lifecycle-email lead who has sent hundreds of millions of messages. Excellent
    means: one goal per email, a subject that survives a 41-character phone screen, a
    preheader that adds a second hook, a body a subscriber can act on in 30 seconds, no
    deliverability landmines, and a schedule that respects the reader's week. The metric
    that matters is click-to-open rate on the primary CTA (opens are unreliable since
    mail privacy protection); unsubscribes are the guardrail.

    ## Intake
    Need: the goal (one action), the audience (who, how they joined, how warm), the offer,
    and the sender/brand. If the goal is missing, ask. If audience size and warmth are
    missing, assume an opted-in list that hears from the brand monthly, state it, continue.
    Ask at most 3 questions.

    ## Procedure
    1. **Structure the campaign** before writing: number of emails, the job of each, the
       gap between them. Use the cadence patterns in Frameworks. One email = one CTA.
    2. **Write 5 subject line candidates** per email across angles (benefit, curiosity,
       number, question, personal). Run every candidate through
       `email_campaign__test_subject_line` with its preheader. Keep candidates scoring ≥ 70
       with no spam hits; pick the top 2 for an A/B split on 20 % of the list.
    3. **Write the body** to the pattern: hook line (≤ 20 words, continues the subject) →
       one idea → proof → single CTA button + the same link in text → P.S. (second-highest
       read spot). Then call `email_campaign__scan_email_body` with the body and the merge
       fields that actually exist. Fix every hit: spam phrases, > 3 links, missing
       unsubscribe, ALL-CAPS, undefined tokens, no plain-text CTA.
    4. **Schedule the sends** with `email_campaign__send_schedule` from the first send date
       and the cadence; it avoids weekends and returns the window per day. Present dates in
       the reader's timezone; say which one.
    5. **If results are in**, run `email_campaign__campaign_metrics` and grade against
       benchmarks; recommend the one change for the next send.
    6. **Deliver** in the output format. Include the plain-text version note and the test
       plan (subject A/B, then CTA copy, never both at once).

    ## Frameworks
    - **Subject lines:** ≤ 41 chars keeps the whole line visible on an iPhone; ≤ 60 on
      desktop. Sentence case, no more than one punctuation mark, ≤ 1 emoji, never "Re:"/
      "Fwd:" tricks. Specific numbers beat adjectives. Personalisation token only when the
      data is clean.
    - **Preheader:** 40-90 chars; must add information the subject didn't (the offer,
      the deadline, the proof). Never "View this email in your browser".
    - **Cadence patterns:** launch = day 0 (announce), day 2 (proof/story), day 5
      (objections/FAQ), day 7 (last call); welcome = day 0, 1, 3, 7; nurture = weekly;
      re-engagement = 3 emails over 14 days then suppress non-openers.
    - **Send windows (local time):** B2B Tue-Thu 09:00-11:00; B2C Tue-Thu 10:00 or
      19:00-21:00; avoid Monday mornings and Friday afternoons; never public holidays.
    - **Benchmarks (broad, all-industry):** delivery ≥ 98 %, open 20-40 % (inflated by MPP),
      CTR 2-5 %, CTOR 10-20 %, unsubscribe < 0.5 %, spam complaints < 0.1 %, bounce < 2 %.
    - **Body:** 50-200 words for promotional, up to 500 for newsletters; one primary
      CTA, ≤ 3 links total (excluding footer); text-to-image ratio favouring text; a
      physical address and unsubscribe link are legally required (CAN-SPAM/GDPR — not
      legal advice; check local rules for consent).

    ## Output format
    ```
    # Campaign — <name> · <n> emails · list: <size / segment>
    **Goal:** <one action> · **Primary metric:** CTOR on <CTA> · **Guardrail:** unsub < 0.5 %

    ## Schedule
    | # | Send (local) | Job of the email | Subject A | Subject B |
    |---|---|---|---|---|

    ## Email 1 — <job>
    Subject A: <≤41 chars> (score n)   Subject B: <…> (score n)
    Preheader: <40-90 chars>
    ---
    <body, ≤ 200 words, one CTA as [Button label]>
    P.S. <one line>
    ---
    Scan: <clean / fixed: …>

    ## Test plan & next send
    - A/B subject on 20 % → winner to remaining 80 % after 2 h
    - Next: <the one change>
    ```

    ## Anti-patterns
    - Subjects that describe the email ("Our October newsletter") instead of the payoff.
    - Preheaders that repeat the subject, or default footer text leaking into it.
    - Three CTAs "to give options". Options lower clicks.
    - Sending to the whole list with an untested subject.
    - "FREE!!!", ALL CAPS, red text, image-only emails, URL shorteners.
    - Judging by opens after 2021.
    - Sending Monday 08:00 because that's when the team is at their desks.
    """,
)

TOKEN_RE = re.compile(r"\{\{\s*([\w.]+)\s*\}\}|\{([\w.]+)\}|\*\|([A-Z_]+)\|\*|%%([\w.]+)%%")
LINK_RE = re.compile(r"https?://\S+|\[[^\]]+\]\([^)]+\)|<a\s", re.I)
CTA_RE = re.compile(r"\[([^\]]{2,60})\]")
SHORTENER_RE = re.compile(r"\b(bit\.ly|tinyurl\.com|t\.co|goo\.gl|ow\.ly|rebrand\.ly|cutt\.ly)\b", re.I)


def _subject_score(subject: str, preheader: str) -> dict:
    s = subject.strip()
    L = visible_len(s)
    ws = text.words(s)
    score = 60
    flags, fixes = [], []
    if L == 0:
        raise ToolError("subject is empty.")
    if L <= 41:
        score += 12
    elif L <= 60:
        score += 2
        flags.append(f"{L} chars — clipped on phones after ~41")
        fixes.append("Front-load the payoff so the first 41 chars stand alone.")
    else:
        score -= 15
        flags.append(f"{L} chars — clipped everywhere")
        fixes.append("Cut to ≤ 41 chars (60 absolute max).")
    if len(ws) <= 2 and L < 12:
        score -= 10
        flags.append("too short to carry a hook")
    hits = spam_hits(s)
    if hits:
        score -= min(30, 12 * len(hits))
        flags.append(f"spam triggers: {', '.join(hits)}")
        fixes.append("Replace spam-trigger words with specific, plain wording.")
    cr = caps_ratio(s)
    if cr > 0.5 and len(ws) > 1:
        score -= 20
        flags.append("ALL CAPS")
        fixes.append("Use sentence case.")
    excl = s.count("!")
    if excl >= 2:
        score -= 15
        flags.append(f"{excl} exclamation marks")
    elif excl == 1:
        score -= 5
    if re.search(r"[!?.]{2,}", s):
        score -= 10
        flags.append("repeated punctuation")
    em = count_emoji(s)
    if em > 1:
        score -= 8
        flags.append(f"{em} emoji")
    if re.match(r"^\s*(re|fw|fwd)\s*:", s, re.I):
        score -= 25
        flags.append("fake reply/forward prefix — deceptive, hurts trust and deliverability")
    if re.search(r"\d", s):
        score += 8
    if "?" in s:
        score += 4
    if re.search(r"\b(you|your)\b", s, re.I):
        score += 5
    tokens = [t for grp in TOKEN_RE.findall(s) for t in grp if t]
    if tokens:
        score += 3
        flags.append(f"merge tokens: {', '.join(tokens)} — verify fallback values")
    if re.search(r"\b(newsletter|update|edition|issue|vol\.?)\b", s, re.I) and not re.search(r"\d", s):
        score -= 8
        flags.append("describes the email, not the payoff")
        fixes.append("Lead with what the reader gets, not what the email is.")
    if s.isupper() is False and s[:1].isupper() and sum(1 for w in ws if w[:1].isupper()) >= max(3, len(ws) - 1) and len(ws) >= 3:
        score -= 4
        flags.append("Title Case reads like an ad; sentence case reads like a person")
    out = {"subject": s, "chars": L, "words": len(ws), "mobile_visible": s[:41], "score": max(0, min(100, score)), "flags": flags, "fixes": fixes}
    if preheader:
        p = preheader.strip()
        pl = visible_len(p)
        pflags = []
        if pl < 40:
            pflags.append(f"{pl} chars — too short; 40-90 fills the preview")
        elif pl > 90:
            pflags.append(f"{pl} chars — clipped after ~90")
        if p.lower() in s.lower() or s.lower() in p.lower():
            pflags.append("repeats the subject — add new information instead")
        sw = set(w.lower() for w in text.words(s))
        pw = set(w.lower() for w in text.words(p))
        if sw and len(sw & pw) / len(sw) > 0.6:
            pflags.append("mostly the same words as the subject")
        if re.search(r"view (this|in) (email|browser)|having trouble|unsubscribe", p, re.I):
            pflags.append("footer/utility text as preheader — wasted hook")
        if spam_hits(p):
            pflags.append(f"spam triggers: {', '.join(spam_hits(p))}")
        out["preheader"] = {"text": p, "chars": pl, "flags": pflags, "ok": not pflags}
        out["score"] = max(0, out["score"] - 6 * len(pflags))
    return out


@AGENT.tool
def test_subject_line(subject: str, preheader: str = "", alternatives: list[str] = []) -> dict:
    """Score a subject line (and preheader) for mobile truncation, spam triggers, caps, punctuation and hook signals; ranks alternatives.

    Call on every candidate; keep ≥ 70 with no spam hits.

    Args:
        subject: The subject line to score.
        preheader: The preheader / preview text (optional but recommended).
        alternatives: Other subject candidates to score and rank against the first.
    """
    if len(alternatives) > 50:
        raise ToolError("Max 50 alternatives.")
    if len(subject or "") > 500 or len(preheader or "") > 500:
        raise ToolError("Subject and preheader must be under 500 chars.")
    main = _subject_score(subject, preheader)
    ranked = [main] + [_subject_score(str(a), "") for a in alternatives if str(a).strip()]
    ranked.sort(key=lambda r: -r["score"])
    best = ranked[0]
    return {
        "primary": main,
        "ranked": [{"subject": r["subject"], "score": r["score"], "chars": r["chars"], "flags": r["flags"]} for r in ranked],
        "recommended_ab_pair": [r["subject"] for r in ranked[:2]],
        "verdict": f"'{best['subject']}' scores {best['score']}/100" + (f"; primary scored {main['score']}." if best is not main else ".") + (" Fix: " + main["fixes"][0] if main["fixes"] else ""),
    }


@AGENT.tool
def scan_email_body(body: str, available_fields: list[str] = [], email_type: str = "promotional") -> dict:
    """Deliverability and structure scan of an email body: spam phrases, links, CTAs, tokens, caps, length, legal footer.

    Call after drafting; fix every hit before scheduling.

    Args:
        body: The email body (plain text, markdown with [Button] CTAs, or HTML).
        available_fields: Merge fields that exist in the list (e.g. ["first_name", "company"]); undefined tokens are flagged.
        email_type: "promotional" (50-200 words ideal) or "newsletter" (up to ~500).
    """
    raw = require_text(body, "body")
    plain = re.sub(r"<[^>]+>", " ", raw)
    ws = text.words(plain)
    n = len(ws)
    hits = spam_hits(plain)
    links = LINK_RE.findall(raw)
    ctas = [m.group(1) for m in CTA_RE.finditer(raw)]
    tokens = sorted({t for grp in TOKEN_RE.findall(raw) for t in grp if t})
    fields = {f.lower() for f in available_fields}
    undefined = [t for t in tokens if fields and t.lower().split("|")[0] not in fields]
    has_unsub = bool(re.search(r"unsubscribe|opt[- ]out|manage (your )?preferences", plain, re.I))
    has_address = bool(re.search(r"\b\d{1,5}\s+\w+(\s\w+)*\s+(st|street|ave|avenue|rd|road|blvd|suite|ste|way|lane|ln|dr|drive)\b", plain, re.I))
    excl = plain.count("!")
    caps_words = [w for w in ws if len(w) >= 4 and w.isupper() and w.isalpha()]
    shorteners = SHORTENER_RE.findall(raw)
    img_tags = len(re.findall(r"<img\b", raw, re.I))
    rd = text.readability(plain)
    issues, fixes = [], []
    if hits:
        issues.append(f"spam phrases: {', '.join(hits[:6])}")
        fixes.append("Reword spam-trigger phrases; specific beats hype.")
    footer_links = sum(1 for lk in links if re.search(r"unsub|preferences|opt-?out", lk, re.I))
    content_links = max(0, len(links) - footer_links)
    if content_links > 3:
        issues.append(f"{content_links} links — more than 3 dilutes clicks and looks spammy")
        fixes.append("Keep ≤ 3 links; point them all at the one CTA.")
    if len(ctas) == 0 and not links:
        issues.append("no CTA found — mark the button as [Label]")
        fixes.append("Add one clear CTA button + a plain-text link.")
    if len(set(c.lower() for c in ctas)) > 1:
        issues.append(f"{len(set(c.lower() for c in ctas))} different CTAs: {', '.join(sorted(set(ctas)))}")
        fixes.append("One email, one action — repeat the same CTA instead of adding another.")
    if undefined:
        issues.append(f"merge tokens not in list fields: {', '.join(undefined)}")
        fixes.append("Remove undefined tokens or add a fallback (e.g. {{first_name|there}}).")
    if not has_unsub:
        issues.append("no unsubscribe link/text")
        fixes.append("Add an unsubscribe link in the footer (legally required).")
    if not has_address:
        issues.append("no postal address detected in footer")
    if excl > 2:
        issues.append(f"{excl} exclamation marks")
    if caps_words:
        issues.append(f"ALL-CAPS words: {', '.join(caps_words[:5])}")
    if shorteners:
        issues.append(f"URL shortener(s): {', '.join(set(shorteners))} — blocked by many filters")
        fixes.append("Use full branded links instead of shorteners.")
    if img_tags and n < 40:
        issues.append("image-heavy with little text — filters and image-blocking clients will hurt")
    ideal = (50, 200) if email_type != "newsletter" else (150, 600)
    if n < ideal[0]:
        issues.append(f"{n} words — under the {ideal[0]}-word floor for {email_type}")
    elif n > ideal[1]:
        issues.append(f"{n} words — over the {ideal[1]}-word ceiling for {email_type}")
        fixes.append("Cut to one idea; move the rest to a landing page.")
    if rd["fk_grade"] is not None and rd["fk_grade"] > 9:
        issues.append(f"reading grade {rd['fk_grade']} — aim ≤ 8")
    risk = "high" if len(hits) >= 3 or shorteners or (caps_words and excl > 2) else "medium" if hits or content_links > 3 or not has_unsub else "low"
    return {
        "words": n,
        "reading_time_seconds": round(n / 238 * 60),
        "fk_grade": rd["fk_grade"],
        "spam_hits": hits,
        "links": len(links),
        "content_links": content_links,
        "ctas": ctas,
        "merge_tokens": tokens,
        "undefined_tokens": undefined,
        "has_unsubscribe": has_unsub,
        "has_postal_address": has_address,
        "exclamations": excl,
        "caps_words": caps_words,
        "deliverability_risk": risk,
        "issues": issues,
        "fixes": fixes,
        "summary": f"Deliverability risk {risk}; {len(issues)} issue(s). " + ("Clean." if not issues else issues[0]),
    }


PATTERNS = {
    "launch": [0, 2, 5, 7],
    "welcome": [0, 1, 3, 7],
    "nurture": [0, 7, 14, 21, 28],
    "reengagement": [0, 5, 14],
    "webinar": [-14, -7, -1, 0, 1],
}


@AGENT.tool
def send_schedule(
    first_send_date: str,
    pattern: str = "launch",
    email_count: int = 0,
    custom_offsets_days: list[int] = [],
    audience: str = "b2b",
    avoid_dates: list[str] = [],
) -> dict:
    """Build the send calendar for a sequence: dates shifted off weekends and blocked days, with the best window per send.

    Call once the sequence structure is set. Offsets are days from the first send.

    Args:
        first_send_date: First send date as YYYY-MM-DD.
        pattern: launch (0,2,5,7), welcome (0,1,3,7), nurture (weekly ×5), reengagement (0,5,14), webinar (-14,-7,-1,0,+1) or "custom".
        email_count: Trim or extend the pattern to this many emails (0 = pattern length; extension repeats the last gap).
        custom_offsets_days: Day offsets when pattern is "custom", e.g. [0, 3, 7, 10].
        audience: "b2b" or "b2c" — picks the send window.
        avoid_dates: Dates to skip (holidays, other campaigns) as YYYY-MM-DD.
    """
    start = dates.parse_date(first_send_date)
    if pattern == "custom":
        offsets = list(custom_offsets_days)
        if not offsets:
            raise ToolError("custom pattern needs custom_offsets_days.")
    elif pattern in PATTERNS:
        offsets = list(PATTERNS[pattern])
    else:
        raise ToolError(f"Unknown pattern {pattern!r}; use {', '.join(PATTERNS)} or custom.")
    if len(offsets) > 60:
        raise ToolError("Max 60 sends.")
    if email_count:
        if email_count < 1 or email_count > 60:
            raise ToolError("email_count must be 1-60.")
        if email_count < len(offsets):
            offsets = offsets[:email_count]
        else:
            gap = (offsets[-1] - offsets[-2]) if len(offsets) >= 2 else 3
            while len(offsets) < email_count:
                offsets.append(offsets[-1] + max(1, gap))
    blocked = {dates.parse_date(d) for d in avoid_dates}
    window = "09:00-11:00 local (Tue-Thu best)" if audience.lower() == "b2b" else "10:00 or 19:00-21:00 local"
    sends, used = [], set()
    for i, off in enumerate(offsets, 1):
        planned = start + timedelta(days=off)
        d = planned
        shifted = []
        while d.weekday() >= 5 or d in blocked or d in used:
            reason = "weekend" if d.weekday() >= 5 else "blocked" if d in blocked else "collision"
            shifted.append(reason)
            d += timedelta(days=1)
        used.add(d)
        warn = []
        if d.weekday() == 0:
            warn.append("Monday — inbox is crowded; send after 10:00 or move to Tuesday")
        if d.weekday() == 4:
            warn.append("Friday — engagement drops after noon; send early")
        sends.append({"n": i, "planned": planned.isoformat(), "send": d.isoformat(), "weekday": d.strftime("%A"), "window": window, "shifted_because": shifted, "warnings": warn, "days_since_previous": (d - sends[-1]["_d"]).days if sends else 0, "_d": d})
    for s in sends:
        s.pop("_d")
    tight = [s["n"] for s in sends[1:] if s["days_since_previous"] < 1]
    return {
        "pattern": pattern,
        "sends": sends,
        "span_days": (date.fromisoformat(sends[-1]["send"]) - date.fromisoformat(sends[0]["send"])).days,
        "same_day_collisions": tight,
        "summary": f"{len(sends)} sends from {sends[0]['send']} to {sends[-1]['send']} ({sends[-1]['weekday']}); window {window}.",
    }


@AGENT.tool
def campaign_metrics(sent: int, delivered: int, unique_opens: int = 0, unique_clicks: int = 0, unsubscribes: int = 0, spam_complaints: int = 0, conversions: int = 0, revenue: float = 0.0) -> dict:
    """Compute delivery, open, CTR, CTOR, unsubscribe, complaint and conversion rates and grade them against benchmarks.

    Call with post-send numbers to produce the readout and the one change for next time.

    Args:
        sent: Emails sent.
        delivered: Emails delivered (sent minus bounces).
        unique_opens: Unique opens (unreliable post-MPP; still reported).
        unique_clicks: Unique clicks on any link.
        unsubscribes: Unsubscribes from this send.
        spam_complaints: Spam/abuse complaints.
        conversions: Downstream conversions attributed to the send.
        revenue: Revenue attributed to the send.
    """
    if sent <= 0 or delivered < 0 or delivered > sent:
        raise ToolError("sent must be > 0 and delivered between 0 and sent.")
    for name, v in (("unique_opens", unique_opens), ("unique_clicks", unique_clicks), ("unsubscribes", unsubscribes), ("spam_complaints", spam_complaints), ("conversions", conversions)):
        if v < 0 or v > sent:
            raise ToolError(f"{name} must be between 0 and sent.")
    bounces = sent - delivered
    m = {
        "delivery_rate_pct": pct(delivered, sent),
        "bounce_rate_pct": pct(bounces, sent),
        "open_rate_pct": pct(unique_opens, delivered),
        "click_rate_pct": pct(unique_clicks, delivered),
        "click_to_open_rate_pct": pct(unique_clicks, unique_opens) if unique_opens else None,
        "unsubscribe_rate_pct": pct(unsubscribes, delivered, 3),
        "complaint_rate_pct": pct(spam_complaints, delivered, 3),
        "conversion_rate_pct": pct(conversions, delivered, 3),
        "click_to_conversion_pct": pct(conversions, unique_clicks) if unique_clicks else None,
        "revenue_per_email": round(revenue / delivered, 4) if delivered and revenue else None,
    }
    grades = {}
    grades["delivery"] = "good" if m["delivery_rate_pct"] >= 98 else "watch" if m["delivery_rate_pct"] >= 95 else "bad"
    grades["open"] = "n/a" if not unique_opens else "good" if m["open_rate_pct"] >= 25 else "ok" if m["open_rate_pct"] >= 15 else "bad"
    grades["click"] = "good" if m["click_rate_pct"] >= 3 else "ok" if m["click_rate_pct"] >= 1.5 else "bad"
    grades["ctor"] = "n/a" if m["click_to_open_rate_pct"] is None else "good" if m["click_to_open_rate_pct"] >= 12 else "ok" if m["click_to_open_rate_pct"] >= 7 else "bad"
    grades["unsubscribe"] = "good" if m["unsubscribe_rate_pct"] < 0.3 else "watch" if m["unsubscribe_rate_pct"] < 0.5 else "bad"
    grades["complaints"] = "good" if m["complaint_rate_pct"] < 0.05 else "watch" if m["complaint_rate_pct"] < 0.1 else "bad — sender reputation at risk"
    diagnosis = []
    if grades["delivery"] != "good":
        diagnosis.append("List hygiene: bounces are high — remove hard bounces, re-verify old addresses.")
    if grades["open"] == "bad":
        diagnosis.append("Subject/sender problem: test subject lines and check the from-name.")
    if grades["open"] in ("good", "ok") and grades["ctor"] == "bad":
        diagnosis.append("Body problem: people opened but didn't click — sharpen the single CTA and the offer.")
    if grades["click"] == "good" and conversions and (m["click_to_conversion_pct"] or 0) < 5:
        diagnosis.append("Landing page problem: clicks convert poorly — check message match.")
    if grades["unsubscribe"] != "good" or grades["complaints"] != "good":
        diagnosis.append("Audience mismatch or frequency: segment tighter and slow the cadence.")
    if not diagnosis:
        diagnosis.append("Healthy send. Next test: CTA copy or send time.")
    return {"counts": {"sent": sent, "delivered": delivered, "bounces": bounces, "opens": unique_opens, "clicks": unique_clicks, "unsubscribes": unsubscribes, "complaints": spam_complaints, "conversions": conversions}, "rates": m, "grades": grades, "diagnosis": diagnosis, "summary": f"CTR {m['click_rate_pct']}% ({grades['click']}), CTOR {m['click_to_open_rate_pct']}% ({grades['ctor']}), unsub {m['unsubscribe_rate_pct']}% ({grades['unsubscribe']}). {diagnosis[0]}"}
