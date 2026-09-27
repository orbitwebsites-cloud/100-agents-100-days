"""Newsletter Editor — issues that get opened, read to the end, and clicked."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ...core import Agent, ToolError
from ...lib import text
from . import _common as c

AGENT = Agent(
    slug="newsletter-editor",
    name="Newsletter Editor",
    category="content",
    tagline="Edit every issue like a paid subscription depends on it: subject lines tested, sections balanced, links tagged, reading time exact.",
    description=(
        "The editor-in-chief pass a newsletter needs before it goes out: subject line and preheader scored "
        "for length, spam triggers and mobile truncation; the issue audited for reading time against your "
        "target, section balance (one bloated section kills read-through), link density and dead-weight "
        "sections; every link checked for generic anchors, duplicates and missing UTM tags — and tagged "
        "correctly without breaking existing query strings. Ends with a send-ready issue and a checklist."
    ),
    triggers=[
        "edit / review my newsletter issue before sending",
        "write a subject line and preheader for this issue",
        "is this newsletter too long / how long is the read",
        "check the links in my newsletter and add UTM tags",
        "structure this week's newsletter from these notes",
        "why is my newsletter open or click rate low",
    ],
    examples=[
        "Here's Thursday's issue in markdown. Edit it, give me 5 subject lines, and make sure it's a 5-minute read.",
        "Tag every link in this issue with utm_source=newsletter, utm_medium=email, utm_campaign=issue-42.",
        "Turn these six bullet points into a newsletter issue with a clear lead story and a short close.",
    ],
    connectors=["Mailchimp", "beehiiv", "Substack", "ConvertKit", "Klaviyo", "HubSpot", "Gmail", "Google Docs"],
    playbook="""
    ## Standard
    You are the editor of a newsletter people pay for — and you run the send like a
    publication: one lead story, a clear spine, no filler, and nothing that makes a reader
    regret opening. Excellent means the subject line gets the open, the first screen justifies
    it, the reader reaches the sign-off, and the links get clicked. The one metric is
    **click-to-open rate** — opens prove the subject line; clicks prove the issue.

    ## Intake
    You need the draft (or the raw material) and the audience. Assume: a 3-5 minute read
    (700-1,200 words), one lead story + 2-4 short sections + a close, subject line ≤ 50
    characters, a preheader that adds information rather than repeating the subject, and
    links tagged for the sender's analytics. Ask only if the issue has no obvious lead
    story or the audience is unclear.

    ## Procedure
    1. **Find the lead.** The single most valuable item goes first — the one a subscriber
       would forward. If the draft buries it, move it. Write a one-line "why this matters"
       under the lead's headline. Everything else is ranked by reader value, not by when it
       happened.
    2. **Audit the issue.** Call `newsletter_editor__issue_audit` with the full markdown
       and the target reading time. Fix what it flags: over/under length, an intro over
       120 words, a section over 45% of the issue, stub sections under 40 words (merge or
       cut), sections with no link (why is it there?), more than ~3 links per 100 words
       (link-dump), missing sign-off.
    3. **Tighten the prose.** One idea per section; the first sentence of each section is
       the takeaway; paragraphs ≤ 3 sentences; bold only the phrase a skimmer needs; no
       "In this issue…" table of contents unless the issue has 6+ sections.
    4. **Write the subject line and preheader — 5 options.** Draft five different types
       (see Frameworks). Call `newsletter_editor__subject_line_check` on each pair. Keep
       the two highest scorers, recommend one, and state the A/B split if the platform
       supports it (send to 20% split, winner to the rest after 2-4 hours).
    5. **Audit and tag links.** Call `newsletter_editor__link_audit` on the issue. Rewrite
       generic anchors ("click here", "this") into descriptive text; remove duplicates and
       naked URLs; flag http:// links. Then call `newsletter_editor__tag_links` with all
       destination URLs and the campaign values — it appends utm_* parameters without
       clobbering existing query strings or fragments, and skips mailto/anchors. Use the
       returned URLs verbatim.
    6. **Pre-send checklist** (silently verify, then report): personalisation tokens have
       fallbacks; the plain-text version reads fine; images have alt text; the unsubscribe
       link exists; the "from" name is a person or the publication, not "noreply"; no
       spam-trigger words in the subject; the preheader is not "View in browser".
    7. **Deliver** in the output format. If the ESP connector is available, create the
       campaign as a *draft* with the subject, preheader and body — never send.

    ## Frameworks
    - **Subject line types**: the specific (“The 3-email sequence that got 41% replies”),
      the curiosity gap (“We were wrong about onboarding”), the direct benefit (“Cut your
      churn analysis to 20 minutes”), the news (“Stripe changed its fees. Here's the math”),
      the personal (“What I'd do with $5k of ad spend”). Avoid: "Newsletter #42", "Weekly
      update", anything with "!!!" or ALL CAPS.
    - **Length rules**: subject 30-50 chars (mobile shows ~35-40); preheader 40-90 chars
      that continues the subject's thought; issue 700-1,200 words for a weekly.
    - **Section balance**: lead 35-50% of words; no other section over 25%; 3-6 sections.
    - **Link rules**: 5-15 links per issue; descriptive anchors of 2-6 words; the most
      important link appears twice (in the lead and in the close); every link tagged.
    - **Rough benchmarks** (vary widely by niche): open rate 35-45% is healthy for an
      engaged list, click-to-open 8-15%, unsubscribe under 0.3% per send.

    ## Output format
    ```
    **Subject (recommended):** <≤ 50 chars> — score N/100
    **Preheader:** <40-90 chars>
    **A/B alternative:** <subject> — score N/100
    **Read time:** N min (N words) · **Sections:** N · **Links:** N (all tagged)

    ---
    <the edited issue, paste-ready, with tagged links>
    ---

    **Other subject lines tried:** <3 more with scores>
    **Pre-send checklist:** ✅ alt text · ✅ unsubscribe · ✅ plain-text · ⚠️ <anything failing>
    **Changes made:** <lead moved, sections merged/cut, anchors rewritten>
    ```

    ## Anti-patterns
    - Opening with "Hope you're doing well!" or a paragraph about the weather/the week.
    - A subject line that describes the issue ("This week: three articles") instead of selling one thing.
    - A preheader that repeats the subject, or "View in browser".
    - Link dumps: ten bare URLs with no reason to click each.
    - One 900-word section and four one-liners. Balance or cut.
    - Untagged links — you will never know what worked.
    - Sending a draft you haven't read on a phone (line length, image width, fold).
    """,
)

SIGNOFF_RE = re.compile(r"\b(until next (week|time)|see you (next|on)|thanks for reading|that'?s (all|it) for (this week|today|now)|cheers|talk soon|— ?[A-Z][a-z]+\s*$|reply to this email|hit reply)\b", re.I | re.M)


@AGENT.tool
def issue_audit(markdown: str, target_minutes: float = 5.0) -> dict:
    """Audit a newsletter issue: reading time vs target, section balance (share of words per section), link density per section, intro length, stubs, sign-off.

    Call first with the full draft (markdown headings mark sections; '---' rules also split).
    Returns a per-section table and prioritised fixes.

    Args:
        markdown: The full issue in markdown or plain text.
        target_minutes: The reading time you're aiming for (default 5; at 238 wpm that's ~1,200 words).
    """
    c.guard(markdown, "Issue")
    if not 0.5 <= target_minutes <= 60:
        raise ToolError("target_minutes must be between 0.5 and 60.")
    secs = c.sections(markdown)
    if len([s for s in secs if s["level"] > 0]) == 0 and "\n---" in markdown:
        parts = re.split(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$", markdown, flags=re.M)
        secs = []
        for i, p in enumerate(parts):
            if p.strip():
                first = p.strip().splitlines()[0][:60]
                secs.append({"level": 2 if i else 0, "title": first if i else "(intro)", "line": 0, "body": p, "words": len(text.words(c.strip_markdown(p)))})
    plain = c.strip_markdown(markdown)
    total = len(text.words(plain))
    if total < 30:
        raise ToolError("Issue has fewer than 30 words — nothing to audit.")
    minutes = round(total / 238, 1)
    target_words = int(target_minutes * 238)
    rows = []
    flags: list[str] = []
    for s in secs:
        lk = c.links(s["body"])
        rows.append({
            "section": s["title"][:60], "level": s["level"], "words": s["words"],
            "share_pct": c.pct(s["words"], total), "links": len(lk),
            "minutes": round(s["words"] / 238, 1),
        })
    content_rows = [r for r in rows if r["level"] > 0]
    intro = next((r for r in rows if r["level"] == 0), None)
    if intro and intro["words"] > 120:
        flags.append(f"Intro is {intro['words']} words — cut to ≤ 120; the lead story must start on screen one.")
    if minutes > target_minutes * 1.25:
        flags.append(f"{minutes} min read vs {target_minutes} target — cut ~{total - target_words} words.")
    elif minutes < target_minutes * 0.6:
        flags.append(f"{minutes} min read vs {target_minutes} target — thin; add depth to the lead or a section.")
    if content_rows:
        biggest = max(content_rows, key=lambda r: r["words"])
        if biggest["share_pct"] > 50:
            flags.append(f"'{biggest['section']}' is {biggest['share_pct']}% of the issue — split it or cut it to ≤ 45%.")
        stubs = [r for r in content_rows if r["words"] < 40]
        if stubs:
            flags.append(f"{len(stubs)} stub section(s) under 40 words: {', '.join(r['section'][:25] for r in stubs[:4])} — merge or cut.")
        linkless = [r for r in content_rows if r["links"] == 0 and r["words"] >= 60]
        if linkless:
            flags.append(f"{len(linkless)} section(s) with no link: {', '.join(r['section'][:25] for r in linkless[:4])} — what should the reader do with it?")
        if len(content_rows) > 7:
            flags.append(f"{len(content_rows)} sections — more than 7 reads as a digest nobody finishes; cut to 3-6.")
        elif len(content_rows) < 2 and total > 500:
            flags.append("Only one section for 500+ words — add structure (lead + shorts + close) so skimmers can navigate.")
    else:
        flags.append("No sections detected — add headings (## Lead story, ## Quick hits, ## Close).")
    all_links = c.links(markdown)
    per100 = round(100.0 * len(all_links) / total, 1)
    if per100 > 3:
        flags.append(f"{len(all_links)} links ({per100} per 100 words) — link-dump; give each a reason to click or cut.")
    if len(all_links) == 0:
        flags.append("No links at all — the issue can't be measured and gives the reader nowhere to go.")
    if not SIGNOFF_RE.search(markdown[-600:]):
        flags.append("No sign-off detected — end with a one-line close and a reply prompt.")
    images = c.MD_IMAGE_RE.findall(markdown)
    no_alt = sum(1 for alt, _ in images if not alt.strip())
    if no_alt:
        flags.append(f"{no_alt} image(s) without alt text — many clients block images by default.")
    rd = text.readability(plain)
    if rd["fk_grade"] and rd["fk_grade"] > 10:
        flags.append(f"Reading grade {rd['fk_grade']} — email is read on phones; aim ≤ 8.")
    lead = content_rows[0] if content_rows else None
    return {
        "words": total,
        "reading_minutes": minutes,
        "target_minutes": target_minutes,
        "target_words": target_words,
        "words_to_cut": max(0, total - target_words),
        "sections": rows,
        "section_count": len(content_rows),
        "lead_share_pct": lead["share_pct"] if lead else None,
        "links": len(all_links),
        "links_per_100_words": per100,
        "images": len(images),
        "fk_grade": rd["fk_grade"],
        "flags": flags,
        "verdict": "Issue structure passes." if not flags else f"{len(flags)} fix(es) before send.",
    }


@AGENT.tool
def subject_line_check(subject: str, preheader: str = "") -> dict:
    """Score a subject line (and preheader) 0-100: length vs mobile truncation, spam triggers, caps/punctuation, specificity, and whether the preheader adds new information.

    Call on every candidate. Keep the top two for an A/B test.

    Args:
        subject: The subject line exactly as it would send.
        preheader: The preview text (optional). Checked for 40-90 chars and for repeating the subject.
    """
    c.guard(subject, "Subject", 500)
    s = subject.strip()
    n = len(s)
    score = 60
    reasons: list[str] = []
    if 30 <= n <= 50:
        score += 12
        reasons.append(f"+12 {n} chars: fits mobile")
    elif n < 20:
        score -= 6
        reasons.append(f"-6 {n} chars: too short to carry a reason to open")
    elif n <= 60:
        score += 2
        reasons.append(f"+2 {n} chars: fine on desktop, may clip on mobile (~40)")
    else:
        score -= 12
        reasons.append(f"-12 {n} chars: truncates on most phones")
    spam = c.find_phrases(s, c.SPAM_WORDS)
    if spam:
        pen = min(30, 10 * len(spam))
        score -= pen
        reasons.append(f"-{pen} spam trigger(s): {', '.join(h['phrase'] for h in spam[:4])}")
    if re.search(r"\d", s):
        score += 10
        reasons.append("+10 contains a number")
    caps = [w for w in text.words(s) if len(w) > 2 and w.isupper()]
    if caps:
        score -= 8
        reasons.append("-8 ALL-CAPS word(s)")
    excl = s.count("!")
    if excl:
        score -= 5 * min(3, excl)
        reasons.append(f"-{5 * min(3, excl)} exclamation mark(s)")
    if c.count_emoji(s) > 1:
        score -= 5
        reasons.append("-5 more than one emoji")
    if re.match(r"^\s*(newsletter|issue|weekly|monthly|update|vol\.?|edition|#\d+|\[)", s, re.I):
        score -= 12
        reasons.append("-12 starts like a label (Newsletter/Issue #/Weekly), not a reason to open")
    if re.search(r"\b(you|your)\b", s, re.I):
        score += 4
        reasons.append("+4 addresses the reader")
    if re.search(r"\b(how|why|what|the \w+ (that|behind)|mistake|wrong|secret|nobody|never|stop)\b", s, re.I):
        score += 6
        reasons.append("+6 curiosity or contrast")
    if re.search(r"\{\{|\{%|\*\|", s):
        score += 2
        reasons.append("+2 personalisation token (check its fallback)")
    if s.endswith("...") or s.endswith("…"):
        score -= 3
        reasons.append("-3 trailing ellipsis")
    if re.search(r"\bre:|\bfwd:", s, re.I):
        score -= 15
        reasons.append("-15 fake reply/forward prefix — erodes trust")
    words_n = len(text.words(s))
    if words_n > 12:
        score -= 5
        reasons.append("-5 more than 12 words")
    pre = (preheader or "").strip()
    pre_report = None
    if pre:
        pn = len(pre)
        pre_flags = []
        if pn < 40:
            pre_flags.append(f"{pn} chars — short; 40-90 fills the preview space")
        elif pn > 90:
            pre_flags.append(f"{pn} chars — clips after ~90")
        if re.search(r"view (this|in) (email|browser)|having trouble viewing|can't see this", pre, re.I):
            pre_flags.append("'View in browser' text as preheader — wasted preview space")
            score -= 10
        sw, pw = set(w.lower() for w in text.words(s)), set(w.lower() for w in text.words(pre))
        overlap = len(sw & pw) / max(1, len(sw))
        if overlap >= 0.6:
            pre_flags.append(f"repeats the subject ({int(overlap * 100)}% word overlap) — continue the thought instead")
            score -= 6
        elif pn >= 40:
            score += 5
            reasons.append("+5 preheader adds new information")
        if c.find_phrases(pre, c.SPAM_WORDS):
            pre_flags.append("spam trigger word in preheader")
        pre_report = {"chars": pn, "in_range": 40 <= pn <= 90, "flags": pre_flags}
    score = max(0, min(100, score))
    band = "send it" if score >= 75 else "usable — try one more variant" if score >= 60 else "rewrite"
    return {
        "subject": s,
        "chars": n,
        "words": words_n,
        "mobile_preview": s[:40] + ("…" if n > 40 else ""),
        "fits_mobile": n <= 40,
        "fits_desktop": n <= 60,
        "score": score,
        "band": band,
        "reasons": reasons,
        "spam_triggers": [h["phrase"] for h in spam],
        "preheader": pre_report,
        "verdict": f"{score}/100 — {band}.",
    }


@AGENT.tool
def link_audit(markdown: str) -> dict:
    """List every link with its anchor and domain; flag generic anchors, naked URLs, duplicates, http, missing UTM tags, and link density.

    Call before tagging. Returns the list you pass to tag_links plus the anchors to rewrite.

    Args:
        markdown: The issue in markdown or plain text.
    """
    c.guard(markdown, "Issue")
    lk = c.links(markdown)
    words_n = len(text.words(c.strip_markdown(markdown)))
    rows = []
    seen: dict[str, int] = {}
    flags: list[str] = []
    generic = naked = untagged = insecure = dupes = 0
    for i, l in enumerate(lk, 1):
        url, anchor = l["url"], l["anchor"]
        issues = []
        if url.lower().startswith(("mailto:", "tel:", "#")):
            rows.append({"n": i, "anchor": anchor, "url": url, "domain": "", "issues": ["not a web link — skipped"]})
            continue
        if l["naked"]:
            naked += 1
            issues.append("naked URL — give it anchor text")
        elif anchor.strip().lower().rstrip(".!") in c.GENERIC_ANCHORS or len(text.words(anchor)) == 0:
            generic += 1
            issues.append("generic anchor — say what the reader gets")
        elif len(text.words(anchor)) > 8:
            issues.append("long anchor (> 8 words) — trim to the key phrase")
        if url.lower().startswith("http://"):
            insecure += 1
            issues.append("http:// — use https")
        if "utm_" not in url.lower():
            untagged += 1
            issues.append("no UTM tags")
        key = url.split("#")[0].rstrip("/").lower()
        if key in seen:
            dupes += 1
            issues.append(f"same destination as link {seen[key]}")
        else:
            seen[key] = i
        rows.append({"n": i, "anchor": anchor, "url": url, "domain": c.domain_of(url), "issues": issues})
    if generic:
        flags.append(f"{generic} generic anchor(s) ('here', 'this', 'read more') — rewrite as 2-6 descriptive words.")
    if naked:
        flags.append(f"{naked} naked URL(s) — wrap in anchor text.")
    if insecure:
        flags.append(f"{insecure} http:// link(s).")
    if dupes:
        flags.append(f"{dupes} duplicate destination(s) — fine for the lead link (twice), otherwise cut.")
    if untagged:
        flags.append(f"{untagged} link(s) without UTM tags — run tag_links.")
    per100 = round(100.0 * len(rows) / max(1, words_n), 1)
    if per100 > 3:
        flags.append(f"{per100} links per 100 words — link-heavy.")
    domains = {}
    for r in rows:
        if r["domain"]:
            domains[r["domain"]] = domains.get(r["domain"], 0) + 1
    return {
        "links": rows,
        "count": len(rows),
        "unique_destinations": len(seen),
        "links_per_100_words": per100,
        "by_domain": dict(sorted(domains.items(), key=lambda kv: -kv[1])),
        "urls_to_tag": [r["url"] for r in rows if r["domain"] and "utm_" not in r["url"].lower()],
        "flags": flags,
        "verdict": "Links are clean." if not flags else f"{len(flags)} link issue(s).",
    }


@AGENT.tool
def tag_links(urls: list[str], source: str = "newsletter", medium: str = "email", campaign: str = "", content: str = "", overwrite: bool = False) -> dict:
    """Append utm_source/medium/campaign(/content) to each URL correctly — preserving existing query strings and fragments, skipping mailto/anchors, and never double-tagging unless told to.

    Call after link_audit with `urls_to_tag`. Use the returned `tagged` URLs verbatim.

    Args:
        urls: Destination URLs to tag (max 200).
        source: utm_source value (default "newsletter").
        medium: utm_medium value (default "email").
        campaign: utm_campaign value, e.g. "issue-42" or "2026-09-25". Required.
        content: Optional utm_content value to distinguish placements (e.g. "lead-cta").
        overwrite: Replace existing utm_* parameters instead of leaving tagged URLs alone.
    """
    if not isinstance(urls, list) or not urls:
        raise ToolError("urls must be a non-empty list.")
    if len(urls) > 200:
        raise ToolError("Max 200 URLs per call.")
    if not campaign or not campaign.strip():
        raise ToolError("campaign is required (e.g. 'issue-42').")

    def clean(v: str) -> str:
        v = v.strip().lower()
        v = re.sub(r"\s+", "-", v)
        return re.sub(r"[^a-z0-9._-]", "", v)

    params = {"utm_source": clean(source), "utm_medium": clean(medium), "utm_campaign": clean(campaign)}
    if content:
        params["utm_content"] = clean(content)
    results = []
    tagged_n = skipped_n = 0
    for u in urls:
        u = str(u or "").strip()
        if not u:
            results.append({"original": u, "tagged": u, "status": "skipped: empty"})
            skipped_n += 1
            continue
        if u.lower().startswith(("mailto:", "tel:", "#", "sms:")):
            results.append({"original": u, "tagged": u, "status": "skipped: not a web link"})
            skipped_n += 1
            continue
        target = u if re.match(r"^https?://", u, re.I) else "https://" + u
        parts = urlsplit(target)
        if not parts.netloc:
            results.append({"original": u, "tagged": u, "status": "skipped: could not parse"})
            skipped_n += 1
            continue
        existing = parse_qsl(parts.query, keep_blank_values=True)
        has_utm = any(k.lower().startswith("utm_") for k, _ in existing)
        if has_utm and not overwrite:
            results.append({"original": u, "tagged": u, "status": "already tagged — left alone"})
            skipped_n += 1
            continue
        kept = [(k, v) for k, v in existing if not k.lower().startswith("utm_")]
        query = urlencode(kept + list(params.items()))
        new = urlunsplit((parts.scheme, parts.netloc, parts.path or "/", query, parts.fragment))
        results.append({"original": u, "tagged": new, "status": "tagged" if not has_utm else "re-tagged"})
        tagged_n += 1
    return {
        "params": params,
        "results": results,
        "tagged": [r["tagged"] for r in results],
        "tagged_count": tagged_n,
        "skipped_count": skipped_n,
        "summary": f"Tagged {tagged_n} URL(s) with {params['utm_campaign']}; {skipped_n} skipped.",
    }
