"""Content Repurposer — one piece of source content into a platform-native set, scheduled."""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Literal

from ...core import Agent, ToolError
from ...lib import dates, text
from . import _common as c

AGENT = Agent(
    slug="content-repurposer",
    name="Content Repurposer",
    category="content",
    tagline="Turn one article, talk or podcast into a month of platform-native posts, each cut to its real limits and scheduled.",
    description=(
        "Repurposes long-form content the way a content ops lead does: atomises the source into its quotable "
        "claims, stats, lists and contrasts; maps each to the right format per platform; checks every piece "
        "against real limits (X's weighted 280, LinkedIn's fold, Instagram's 125-char preview, Threads 500, "
        "YouTube title 100…) and trims at sentence boundaries to fit; then lays out a dated schedule that "
        "staggers platforms so nothing collides. Delivers the pieces, the limits table and the calendar."
    ),
    triggers=[
        "repurpose this blog post / podcast / talk into social posts",
        "what can I make from this article",
        "turn this into LinkedIn, X, Instagram versions",
        "what are the character limits for each platform",
        "does this fit on Threads / Instagram / X",
        "build a distribution plan for this content",
    ],
    examples=[
        "Here's a 2,000-word article on pricing. Turn it into an X thread, 3 LinkedIn posts, an Instagram carousel outline and a newsletter section, scheduled over two weeks starting Monday.",
        "I have a 45-minute podcast transcript. Pull out the best 10 atomic ideas and tell me which platform each belongs on.",
        "Does this caption fit Instagram's preview and Threads? Trim it if not.",
    ],
    connectors=["Buffer", "Hootsuite", "Notion", "Airtable", "LinkedIn", "X", "Google Sheets"],
    playbook="""
    ## Standard
    You are a content operations lead who makes one good piece do the work of twenty. Excellent
    means every derivative is *native* — it reads like it was written for that platform, not
    pasted — every piece fits the platform's real limits, and the schedule spreads reach
    without repeating the same idea on the same day. The one metric: **derivative pieces
    published per source piece, at native quality** — quantity is worthless if each post
    looks like a cut-down.

    ## Intake
    You need the source (text, transcript or notes) and the target platforms. Assume: a
    two-week plan, weekdays only, LinkedIn + X as defaults, the author's voice, and links
    back to the source where the platform allows. Ask only if the source has no clear
    claims to extract or the goal (reach vs traffic vs signups) changes the CTAs.

    ## Procedure
    1. **Atomise the source.** Call `content_repurposer__atomize` with the full text. It
       extracts stats, quotable lines, contrasts, questions, lists and headings, ranks them,
       and suggests a format for each (stat → single post/graphic; list → carousel or
       thread; contrast → LinkedIn hook; question → poll or reply-bait). Pick the 6-12
       strongest atoms; each derivative piece is built around exactly one.
    2. **Know the limits before writing.** Call `content_repurposer__platform_limits` with
       the target platforms. Write to the sweet spot, not the maximum, and note how each
       platform treats links and hashtags.
    3. **Write natively.** For each atom, write the piece in the platform's grammar:
       - X: one claim, ≤ 200 chars, no link in the hook; a thread only for lists ≥ 5 items.
       - LinkedIn: hook above the ~210-char fold, one-idea lines, story or lesson, question close.
       - Instagram: first 125 chars carry the message; carousel outline of 6-10 slides,
         one idea per slide, CTA on the last; 3-5 hashtags.
       - Threads/Bluesky: conversational, ≤ 300 chars, ask something.
       - Newsletter section: 120-200 words with the "why it matters" line and a link.
       - Short-video script: hook line in the first 2 seconds, ≤ 150 words for 60 seconds.
       Do not paste the source paragraph anywhere. Rewrite from the atom.
    4. **Fit-check every piece.** Call `content_repurposer__fit_check` with each piece and
       its platform. It counts the way the platform does (weighted for X, fold for LinkedIn
       and Instagram) and, if over, returns a sentence-boundary trim that fits. Use the trim
       or rewrite shorter — never let the platform truncate mid-sentence.
    5. **Schedule.** Call `content_repurposer__repurpose_plan` with the source type, word
       count, platforms and start date. It sizes the set (how many pieces per platform the
       source can honestly support) and lays them out on weekdays with no platform posting
       twice in a day and 2+ days between posts on the same platform. Map your pieces to
       its slots; the strongest atom goes first on each platform.
    6. **Deliver** the calendar table plus every piece, paste-ready and labelled with its
       slot. If a scheduler connector exists (Buffer/Hootsuite), queue as drafts.

    ## Frameworks
    - **Atom types → formats**: stat → single post + graphic; how-to list → carousel /
      thread / short video; contrast or contrarian claim → LinkedIn hook / X post; story
      → LinkedIn post / newsletter lead; question → poll / Threads; definition → Instagram
      slide 1 / X post; quote → graphic + caption.
    - **Sizing rule of thumb** (used by the plan tool): per 1,000 source words ≈ 1 thread,
      3-4 single posts, 1-2 LinkedIn posts, 1 carousel, 1 short-video script, 1 newsletter
      section. A 45-minute talk transcript (~6,000 words) supports a month.
    - **Spacing**: same platform ≥ 2 days apart; same atom on two platforms ≥ 1 day apart;
      the thread/carousel (biggest pieces) on Tuesday-Thursday.
    - **Link discipline**: X — link in the last post or a reply; LinkedIn — first comment;
      Instagram/TikTok — not clickable, say "link in bio"; Threads/Bluesky — inline is fine.

    ## Output format
    ```
    **Source:** <title/type, N words> · **Atoms used:** N of M · **Pieces:** N across <platforms>

    ## Calendar
    | Date | Platform | Piece | Atom | Fit |
    |---|---|---|---|---|
    | Mon 2026-10-05 | LinkedIn | Post 1 — "<hook>" | stat #2 | 1,180/3,000 ✅ |

    ## Pieces
    ### LinkedIn — Post 1 (Mon 2026-10-05)
    <paste-ready text>
    First comment: <link>
    ### X — Thread (Tue 2026-10-06)
    1/ …
    …

    **Limits used:** <one line per platform> · **Unused atoms:** <list for next round>
    ```

    ## Anti-patterns
    - Pasting the same paragraph on five platforms with a different hashtag.
    - Ignoring the fold: the point buried after "…more".
    - Threads that are the article's headings in order — build each post from an atom.
    - Links in X hooks and LinkedIn bodies (reach); "link in bio" missing on Instagram.
    - Posting the whole set in one day; or the same platform twice in a day.
    - Guessing limits ("X is 280 characters" — not with two links and three emoji).
    """,
)

CONTRAST_RE = re.compile(r"\b(but|instead|not \w+ but|rather than|unlike|versus|vs\.?|wrong|myth|actually|the truth|stop|never|nobody|most people|everyone thinks|contrary)\b", re.I)


@AGENT.tool
def atomize(source: str, max_atoms: int = 25) -> dict:
    """Extract and rank the atomic, reusable units from long-form content: stats, quotable lines, contrasts, questions, lists and headings — each with a suggested platform/format.

    Call first with the full source. Build each derivative piece around one atom.

    Args:
        source: The article, transcript or notes (markdown or plain text).
        max_atoms: Maximum atoms to return (5-60).
    """
    c.guard(source, "Source")
    if not 5 <= max_atoms <= 60:
        raise ToolError("max_atoms must be 5-60.")
    secs = c.sections(source)
    headings = [s["title"] for s in secs if s["level"] > 0]
    plain = c.strip_markdown(source)
    words_n = len(text.words(plain))
    if words_n < 80:
        raise ToolError("Source has fewer than 80 words — too short to atomise; write the piece directly.")
    sents = text.sentences(plain)
    atoms: list[dict] = []
    seen: set[str] = set()

    def add(kind: str, txt: str, score: float, fmt: str):
        key = re.sub(r"\W+", " ", txt.lower()).strip()[:120]
        if key in seen or len(text.words(txt)) < 4:
            return
        seen.add(key)
        atoms.append({"type": kind, "text": txt.strip()[:400], "words": len(text.words(txt)), "score": round(score, 1), "suggested_format": fmt})

    for s in sents:
        n = len(text.words(s))
        if n > 60:
            continue
        has_num = bool(re.search(r"\d", s))
        if has_num and re.search(r"\d+(?:\.\d+)?\s?(%|percent|x\b|k\b|m\b|million|billion|\$|€|£|hours?|days?|weeks?|months?|years?|times)|[$€£]\s?\d", s, re.I):
            add("stat", s, 8 + (3 if n <= 25 else 0), "single post + graphic (X / LinkedIn / Instagram slide)")
        elif has_num and n <= 30:
            add("number", s, 6, "single post (X / Threads)")
        if CONTRAST_RE.search(s) and n <= 30:
            add("contrast", s, 7 + (2 if n <= 18 else 0), "hook (LinkedIn / X)")
        if s.rstrip().endswith("?") and n <= 25:
            add("question", s, 5, "poll / Threads / reply-bait")
        if n <= 14 and re.search(r"\b(is|are|isn't|aren't|means|equals|beats|wins|matters|works|fails)\b", s, re.I) and not s.rstrip().endswith("?"):
            add("aphorism", s, 6.5, "quote graphic / X post / carousel slide 1")
        m = re.search(r"[\"“]([^\"”]{25,240})[\"”]", s)
        if m:
            add("quote", m.group(1), 6, "quote graphic + caption")
    list_blocks = re.findall(r"(?:^\s*(?:[-*+•]|\d{1,3}[.)])\s+.+\n?){3,}", source, re.M)
    for lb in list_blocks[:10]:
        items = [re.sub(r"^\s*(?:[-*+•]|\d{1,3}[.)])\s+", "", ln).strip() for ln in lb.strip().splitlines() if ln.strip()]
        add("list", " / ".join(i[:80] for i in items[:10]), 7 + min(3, len(items) * 0.4), f"carousel ({len(items)} slides) / thread ({len(items)} posts) / short video")
    for h in headings:
        if len(text.words(h)) >= 3:
            add("heading", h, 4, "thread outline post / section-level LinkedIn post")
    atoms.sort(key=lambda a: -a["score"])
    atoms = atoms[:max_atoms]
    counts: dict[str, int] = {}
    for a in atoms:
        counts[a["type"]] = counts.get(a["type"], 0) + 1
    return {
        "source_words": words_n,
        "source_sentences": len(sents),
        "headings": headings[:30],
        "atoms": atoms,
        "count": len(atoms),
        "by_type": counts,
        "supports": {
            "single_posts": max(1, min(12, counts.get("stat", 0) + counts.get("contrast", 0) + counts.get("aphorism", 0) + counts.get("number", 0))),
            "threads_or_carousels": max(0, min(4, counts.get("list", 0) + (1 if len(headings) >= 4 else 0))),
            "polls": counts.get("question", 0),
        },
        "summary": f"{len(atoms)} atoms from {words_n} words: " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])) + ".",
    }


@AGENT.tool
def platform_limits(platforms: list[str] | None = None) -> dict:
    """The limits matrix for the target platforms: max characters, how they count, the sweet spot, hashtag and link rules, media specs.

    Call before writing derivatives. Leave platforms empty for the whole table.

    Args:
        platforms: Platform keys or common names (x, twitter, linkedin, instagram, threads, bluesky, mastodon, facebook, tiktok, youtube_title, youtube_description, pinterest, reddit, email_subject, newsletter, blog, short_video_script, podcast_notes).
    """
    keys = [c.platform_key(p) for p in (platforms or [])] or list(c.PLATFORMS)
    rows = [{"platform": k, **c.PLATFORMS[k]} for k in keys]
    return {
        "platforms": rows,
        "count": len(rows),
        "notes": [
            "Write to the sweet spot, not the max.",
            "X counts URLs as 23 chars and emoji/CJK as 2; Bluesky counts graphemes.",
            "LinkedIn and Instagram show only the first ~210 / ~125 chars before 'more' — the hook lives there.",
        ],
        "summary": "; ".join(f"{r['name']}: {r['max_chars'] or 'no hard limit'} ({r['sweet_spot']})" for r in rows[:8]) + ("; …" if len(rows) > 8 else ""),
    }


def _trim_to(txt: str, limit: int, counter) -> str:
    sents = text.sentences(txt)
    keep = list(sents)
    while keep and counter(" ".join(keep)) > limit:
        keep.pop()
    return " ".join(keep)


@AGENT.tool
def fit_check(piece: str, platform: str) -> dict:
    """Check a piece against one platform's real limit and fold (X weighted count, LinkedIn 210-char fold, Instagram 125-char preview, Threads 500…); returns a sentence-boundary trim if it's over.

    Call on every derivative before scheduling. Use `trimmed` or rewrite shorter — never
    let the platform cut mid-sentence.

    Args:
        piece: The post/caption text exactly as it will be published.
        platform: Platform key or common name (x, linkedin, instagram, threads, bluesky, facebook, tiktok, youtube_title, email_subject…).
    """
    c.guard(piece, "Piece", 50000)
    key = c.platform_key(platform)
    spec = c.PLATFORMS[key]
    counter = c.x_length if key in ("x", "x_premium") else len
    n = counter(piece)
    limit = spec["max_chars"]
    fold = {"linkedin": 210, "instagram": 125, "facebook": 480, "x_premium": 280, "youtube_description": 150, "tiktok": 150}.get(key)
    fold_text = piece[:fold] if fold else None
    flags: list[str] = []
    fits = True
    if limit and n > limit:
        fits = False
        flags.append(f"Over {spec['name']} limit by {n - limit} ({n}/{limit}).")
    if fold and len(piece) > fold:
        first = piece[:fold]
        if not re.search(r"\d", first) and not CONTRAST_RE.search(first):
            flags.append(f"The first {fold} chars (shown before 'more') carry no number or tension — move the hook up.")
    tags = c.HASHTAG_RE.findall(piece)
    tag_rule = spec["hashtags"]
    m = re.search(r"(\d+)\s*-\s*(\d+)|≤\s*(\d+)|max (\d+)", tag_rule)
    if m:
        hi = int(next(g for g in (m.group(2), m.group(3), m.group(4)) if g))
        if len(tags) > hi:
            flags.append(f"{len(tags)} hashtags — {spec['name']} guidance is {tag_rule}.")
    elif tag_rule in ("none", "n/a") and tags:
        flags.append(f"Hashtags don't belong on {spec['name']}.")
    links = c.links(piece)
    if key in ("x", "x_premium"):
        links = [{"url": u} for _, _, u in c.x_urls(piece)]
    if links and key in ("instagram", "tiktok"):
        flags.append("Links aren't clickable here — say 'link in bio' instead.")
    if links and key == "x" and not piece.rstrip().endswith(links[-1]["url"]):
        flags.append("Link mid-post on X — move to the end or a reply.")
    if key == "linkedin" and links:
        flags.append("Link in the LinkedIn body — move to the first comment.")
    sweet = spec["sweet_spot"]
    trimmed = ""
    if not fits and limit:
        trimmed = _trim_to(piece, limit, counter)
        if not trimmed:
            trimmed = ""
            flags.append("No sentence-level cut fits — rewrite shorter or split into a thread/carousel.")
    words_n = len(text.words(piece))
    if key == "short_video_script":
        secs = round(words_n / 2.5)
        flags.append(f"~{secs}s at 150 wpm" + (" — over 60s" if secs > 60 else ""))
        fits = secs <= 60
    return {
        "platform": key,
        "platform_name": spec["name"],
        "chars": n,
        "count_method": spec["count"],
        "limit": limit or None,
        "fits": fits and not any(f.startswith("Over") for f in flags),
        "over_by": max(0, n - limit) if limit else 0,
        "fold_chars": fold,
        "fold_text": fold_text,
        "hashtags": len(tags),
        "links": len(links),
        "words": words_n,
        "sweet_spot": sweet,
        "trimmed": trimmed,
        "trimmed_chars": counter(trimmed) if trimmed else None,
        "flags": flags,
        "verdict": ("Fits." if fits and not flags else f"{len(flags)} issue(s).") + f" {n}/{limit or '∞'} on {spec['name']}.",
    }


SIZING = {  # pieces per 1,000 source words by platform
    "x": 3.5, "linkedin": 1.5, "instagram": 1.0, "threads": 2.0, "bluesky": 2.0, "mastodon": 1.5, "facebook": 1.0,
    "tiktok": 0.7, "youtube_community": 1.0, "pinterest": 1.0, "reddit": 0.3, "newsletter": 0.6, "short_video_script": 0.8,
    "youtube_title": 0.3, "youtube_description": 0.3, "email_subject": 0.6, "blog": 0.3, "podcast_notes": 0.3, "x_premium": 0.5, "linkedin_article": 0.3,
}
BIG_PIECES = {"x": "thread", "instagram": "carousel", "linkedin": "long post", "short_video_script": "script"}


@AGENT.tool
def repurpose_plan(source_type: Literal["article", "podcast", "talk", "webinar", "report", "newsletter", "video"], source_words: int, platforms: list[str], start_date: str = "", weeks: int = 2, max_per_platform: int = 8) -> dict:
    """Size the derivative set from the source length and lay it out on a dated weekday calendar: no platform twice in a day, ≥ 2 days between posts on the same platform, big pieces mid-week.

    Call after fit-checking. Map your pieces to the returned slots; strongest atom first
    per platform.

    Args:
        source_type: article, podcast, talk, webinar, report, newsletter or video.
        source_words: Word count of the source (or transcript). 100-100000.
        platforms: Target platforms (keys or common names).
        start_date: First posting day as YYYY-MM-DD (defaults to the next Monday).
        weeks: Length of the plan in weeks (1-8).
        max_per_platform: Cap on pieces per platform (1-30).
    """
    if not 100 <= source_words <= 100_000:
        raise ToolError("source_words must be 100-100000.")
    if not 1 <= weeks <= 8:
        raise ToolError("weeks must be 1-8.")
    if not 1 <= max_per_platform <= 30:
        raise ToolError("max_per_platform must be 1-30.")
    if not isinstance(platforms, list) or not platforms:
        raise ToolError("platforms must be a non-empty list.")
    keys = []
    for p in platforms:
        k = c.platform_key(p)
        if k not in keys:
            keys.append(k)
    if start_date:
        start = dates.parse_date(start_date)
    else:
        today = date.today()
        start = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
    if start.weekday() >= 5:
        start = dates.add_business_days(start, 1)
    per_k = source_words / 1000.0
    factor = {"article": 1.0, "podcast": 0.6, "talk": 0.7, "webinar": 0.6, "report": 1.2, "newsletter": 0.8, "video": 0.7}[source_type]
    counts = {}
    for k in keys:
        n = round(SIZING.get(k, 1.0) * per_k * factor)
        counts[k] = int(max(1, min(max_per_platform, n)))
    days = [d for d in (start + timedelta(days=i) for i in range(weeks * 7)) if d.weekday() < 5]
    # slots: platform round-robin, each platform at most once per day, ≥ 2 days apart per platform
    last_day: dict[str, date | None] = {k: None for k in keys}
    remaining = dict(counts)
    slots = []
    piece_idx = {k: 0 for k in keys}
    order = sorted(keys, key=lambda k: -counts[k])
    for d in days:
        used_today: set[str] = set()
        for k in order:
            if remaining[k] <= 0 or k in used_today:
                continue
            if last_day[k] is not None and (d - last_day[k]).days < 2:
                continue
            if len(used_today) >= 3:
                break
            piece_idx[k] += 1
            big = piece_idx[k] == 1 and k in BIG_PIECES
            if big and d.weekday() in (0, 4) and remaining[k] > 1 and len(days) > 5:
                # prefer Tue-Thu for the big piece: swap by deferring
                piece_idx[k] -= 1
                continue
            label = f"{BIG_PIECES[k]} (lead)" if big else f"post {piece_idx[k]}"
            slots.append({"date": d.isoformat(), "weekday": d.strftime("%a"), "platform": k, "piece": label, "atom_hint": "strongest atom" if piece_idx[k] == 1 else f"atom #{piece_idx[k]}"})
            used_today.add(k)
            last_day[k] = d
            remaining[k] -= 1
    unscheduled = {k: v for k, v in remaining.items() if v > 0}
    total = sum(counts.values())
    notes = []
    if unscheduled:
        notes.append(f"{sum(unscheduled.values())} piece(s) didn't fit in {weeks} week(s) with spacing rules: {unscheduled} — extend the plan or drop them.")
    if source_words < 600:
        notes.append("Short source — the set is small on purpose; don't pad it.")
    return {
        "source_type": source_type,
        "source_words": source_words,
        "start_date": start.isoformat(),
        "weeks": weeks,
        "pieces_per_platform": counts,
        "total_pieces": total,
        "scheduled": len(slots),
        "calendar": slots,
        "unscheduled": unscheduled,
        "notes": notes,
        "summary": f"{total} pieces across {len(keys)} platform(s) from {start.isoformat()}: " + ", ".join(f"{k} ×{v}" for k, v in counts.items()) + f"; {len(slots)} scheduled.",
    }
