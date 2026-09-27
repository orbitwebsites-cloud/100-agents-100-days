"""X Thread Builder — threads that get read to the end: scored hooks, exact 280-char splits, lint."""

from __future__ import annotations

import re
from typing import Literal

from ...core import Agent, ToolError
from ...lib import text
from . import _common as c

AGENT = Agent(
    slug="x-thread-builder",
    name="X Thread Builder",
    category="content",
    tagline="Turn an idea or article into an X thread with a scored hook, exact 280-character posts and a CTA that converts.",
    description=(
        "Builds X (Twitter) threads the way top accounts do: a hook scored against what actually stops the "
        "scroll, one idea per post, every post counted with X's real weighted length (URLs = 23, emoji = 2), "
        "numbering that never drifts, no links until the last post, and a lint pass that catches posts "
        "that don't stand alone. Also splits long text into a thread at sentence boundaries, so nothing "
        "is cut mid-thought."
    ),
    triggers=[
        "write an X / Twitter thread about X",
        "turn this article or notes into a thread",
        "split this text into tweets",
        "score or improve my hook tweet",
        "check my thread for character limits",
        "make this thread better",
    ],
    examples=[
        "Turn this blog post into a 10-tweet thread. Keep my voice, end with a CTA to the newsletter.",
        "Here's my hook: 'I grew my SaaS to $10k MRR in 6 months. Here's what worked:' — score it and give me 3 stronger versions.",
        "Split this 900-word essay into a thread without cutting sentences in half.",
    ],
    connectors=["X", "Typefully", "Buffer", "Hypefury", "Notion"],
    playbook="""
    ## Standard
    You are the ghostwriter behind accounts whose threads get bookmarked, not just liked. Excellent
    means: the hook alone would get the click, every post can be screenshotted on its own, and
    the reader reaches the last post feeling they got more than they expected. The one metric
    is **read-through to the last post** — hooks earn the open, structure earns the finish.

    ## Intake
    You need the idea (or source text) and the goal of the thread (followers, newsletter signups,
    product, authority). Assume a 6-12 post thread, a first-person practitioner voice, and no
    hashtags unless told otherwise. If a source article is given, extract 5-9 claims with a
    number or a concrete example each — those become the posts. Ask only if you have neither
    an idea nor a source.

    ## Procedure
    1. **Write three hooks, score them, keep the best.** Draft three different hook types
       (see Frameworks). Call `x_thread_builder__score_hook` on each. Keep the one scoring
       highest; if none reaches 70, rewrite — add a specific number, a contrast, or a
       promise with a timeframe. The hook never contains a link or a hashtag.
    2. **Draft the body posts.** One idea per post. Lead each with the point, then the
       proof (number, example, screenshot suggestion). Write posts 2-N so each is a
       complete thought that makes sense out of context — quote-tweets and screenshots
       travel alone. Put the biggest payoff in post 2 (readers decide there whether to
       continue) and the second biggest just before the CTA.
    3. **Count every post.** Call `x_thread_builder__count_post` on any post that might be
       long, or run `x_thread_builder__lint_thread` on the whole list — it counts with
       X's weighted rules (URLs are 23 chars regardless of length; emoji and CJK count 2).
       Anything over 280 gets cut, not squeezed: remove an adjective, then a clause, then
       split into two posts.
    4. **If splitting a long text**, call `x_thread_builder__split_thread` with the source.
       It breaks at paragraph and sentence boundaries, never mid-sentence, and adds
       numbering. Then rewrite each resulting post so it opens with its own point (a split
       is a draft, not a thread).
    5. **Close.** The last post: one-line recap of the promise, then one CTA — follow,
       subscribe or the link. Ask for a repost of the hook ("RT the first post if useful")
       *once*. Put the link here, never in the hook.
    6. **Lint before delivery.** Call `x_thread_builder__lint_thread` with the final list.
       Fix every flag: over-limit posts, numbering gaps, links before the last post, posts
       starting with a dangling conjunction, more than 2 hashtags in the thread, duplicate
       posts, empty posts. Deliver only a thread that lints clean.

    ## Frameworks
    - **Hook types that work** (pick by content): the specific result ("I went from 0 to
      12,400 subscribers in 90 days. The 7 emails that did it:"); the contrarian ("Stop
      writing daily. It's killing your reach."); the curiosity gap with a number ("3 pricing
      mistakes I see in 90% of SaaS decks:"); the story open ("In 2021 I got fired. Last
      month I sold the company that fired me."); the how-to promise ("How to write a cold
      email that gets a 40% reply rate (steps + template):").
    - **Hook rules**: 70-200 weighted chars; a number or a named thing; second person or
      first-person proof; end on a colon, an open loop, or a short punch — not an ellipsis;
      no "🧵", "thread", "a thread 👇" as the *only* signal; no hashtags; no links.
    - **Post rhythm**: ≤ 3 lines per post; line breaks between ideas; numbers as digits;
      one emoji max per post, or none; avoid "Also," and "And," openers.
    - **Length**: 5-12 posts for most topics. Beyond 15 read-through collapses; split into
      two threads.
    - **CTA math**: one ask. Two asks halve the response to each.

    ## Output format
    ```
    **Hook score:** 82/100 (<type>) — <one-line why>

    1/ <hook>

    2/ <post>

    …

    N/ <recap + single CTA + link>

    ---
    **Lint:** ✅ all posts ≤ 280 · no links before N · numbering OK
    **Alt hooks (scored):** <hook B — 74> · <hook C — 61>
    **Posting notes:** <best post 2 as a quote-tweet; screenshot to attach; reply to add link if reach drops>
    ```

    ## Anti-patterns
    - Hooks that announce a thread instead of delivering a promise ("A thread on marketing 🧵").
    - Posts that only make sense after the previous one ("And that's why…", "Which means…").
    - Cramming to 279 chars. Air is engagement; the best posts are 100-200 chars.
    - Links, hashtags or @mentions in the hook.
    - Numbering by hand — it drifts. Use the tools.
    - A closing post that says "That's it!" with no recap or CTA.
    - Generic advice ("be consistent") where the source had a specific number.
    """,
)

SOFT_OPENERS = re.compile(r"^(i'?m (so |really |very )?(excited|thrilled|happy|proud)|thrilled|excited|hey (guys|everyone|all)|so,|today i|just (wanted|a quick)|a thread|thread:|🧵\s*$)", re.I)
CONTRAST = re.compile(r"\b(but|instead|without|stop|never|nobody|no one|wrong|mistake|myth|truth|secret|actually|unpopular|hard truth|don't|isn't|aren't)\b", re.I)
PROMISE = re.compile(r"\b(how to|here's|here is|the \d+|steps?|framework|playbook|template|lessons?|mistakes?|rules?|ways?|things|what i learned|exactly)\b", re.I)
CTA_RE = re.compile(r"\b(follow|subscribe|newsletter|repost|retweet|rt\b|bookmark|share|like this|sign up|join|link|dm me|reply)\b", re.I)
DANGLING = re.compile(r"^(and|but|so|which|also|because|or|then|plus|that's why|meaning)\b[,\s]", re.I)
NUMBERING_RE = re.compile(r"^\s*(\d{1,3})\s*/\s*(\d{0,3})\s*|^\s*\(?(\d{1,3})\s*/\s*(\d{1,3})\)?\s*$|\(?\b(\d{1,3})\s*/\s*(\d{1,3})\)?\s*$")


def _hook_type(h: str) -> str:
    if re.match(r"^\s*(how to|how i)\b", h, re.I):
        return "how-to promise"
    if re.match(r"^\s*(stop|never|don't|most|everyone|unpopular)\b", h, re.I) or re.search(r"\b(wrong|myth|lie)\b", h, re.I):
        return "contrarian"
    if re.search(r"\b(in|last|ago|when i|i got|i was|years?)\b", h, re.I) and re.search(r"\b(19|20)\d{2}\b|\bago\b|\bi was\b|\bi got\b", h, re.I):
        return "story"
    if re.search(r"\b\d[\d,.]*[%kKxX$]?\b", h) and re.search(r"\b(mistakes?|lessons?|ways?|rules?|things|steps?|tools?|tips?)\b", h, re.I):
        return "numbered list"
    if re.search(r"\b\d[\d,.]*\b", h) and re.search(r"\b(from|to|grew|went|made|earned|saved|cut|lost)\b", h, re.I):
        return "specific result"
    if h.strip().endswith("?"):
        return "question"
    return "statement"


@AGENT.tool
def score_hook(hook: str) -> dict:
    """Score a hook (first post) 0-100 against what stops the scroll: specificity, contrast, promise, length, and the killers (links, hashtags, soft openers).

    Call on every candidate hook; keep the best, rewrite anything under 70. Returns the
    hook type it detects and concrete reasons so you can fix, not guess.

    Args:
        hook: The first post of the thread, exactly as it will be posted.
    """
    c.guard(hook, "Hook", 2000)
    h = hook.strip()
    n = c.x_length(h)
    score = 50
    reasons: list[str] = []
    if 70 <= n <= 200:
        score += 10
        reasons.append(f"+10 length {n} in the 70-200 sweet spot")
    elif n < 40:
        score -= 10
        reasons.append(f"-10 too short ({n}) to carry a promise")
    elif n > 240:
        score -= 12
        reasons.append(f"-12 long hook ({n}); the preview gets cut")
    if n > 280:
        score -= 30
        reasons.append("-30 over 280 chars — it can't be posted")
    if re.search(r"\d", h):
        score += 15
        reasons.append("+15 contains a specific number")
    proper = c.proper_nouns(h)
    if proper:
        score += 5
        reasons.append(f"+5 names something concrete ({proper[0]})")
    if re.search(r"\b(you|your|you're)\b", h, re.I):
        score += 8
        reasons.append("+8 addresses the reader")
    if CONTRAST.search(h):
        score += 8
        reasons.append("+8 contrast/tension word")
    if PROMISE.search(h):
        score += 8
        reasons.append("+8 promise of a payoff")
    if h.rstrip().endswith(":") or h.rstrip().endswith("👇") or re.search(r"\b(here's (how|what|why)|thread|🧵)", h, re.I):
        score += 4
        reasons.append("+4 opens the loop into post 2")
    if h.rstrip().endswith("..."):
        score -= 4
        reasons.append("-4 trailing ellipsis (overused)")
    if SOFT_OPENERS.search(h):
        score -= 15
        reasons.append("-15 soft opener (excited/thrilled/hey/a thread)")
    tags = c.HASHTAG_RE.findall(h)
    if tags:
        score -= 10 * min(3, len(tags))
        reasons.append(f"-{10 * min(3, len(tags))} hashtag(s) in the hook")
    if c.URL_RE.search(h):
        score -= 15
        reasons.append("-15 link in the hook (kills reach; move to last post)")
    if c.MENTION_RE.search(h):
        score -= 5
        reasons.append("-5 @mention in the hook")
    caps = [w for w in text.words(h) if len(w) > 2 and w.isupper() and not w.isdigit()]
    if len(caps) > 2:
        score -= 6
        reasons.append("-6 shouting (3+ ALL-CAPS words)")
    if c.count_emoji(h) > 2:
        score -= 5
        reasons.append("-5 more than 2 emoji")
    lines = [ln for ln in h.splitlines() if ln.strip()]
    if len(lines) > 4:
        score -= 5
        reasons.append("-5 more than 4 lines; the preview truncates")
    words_n = len(text.words(h))
    if words_n and sum(1 for w in text.words(h) if w.lower() in c.HEDGES) >= 2:
        score -= 6
        reasons.append("-6 hedging words weaken the claim")
    if re.search(r"\b(a thread|thread)\b\s*[:👇🧵]*\s*$", h, re.I) and not re.search(r"\d", h):
        score -= 8
        reasons.append("-8 ends by announcing a thread with nothing specific")
    score = max(0, min(100, score))
    band = "strong — post it" if score >= 75 else "usable — one more pass" if score >= 60 else "rewrite"
    fixes = []
    if not re.search(r"\d", h):
        fixes.append("Add a specific number (result, timeframe, count).")
    if not CONTRAST.search(h) and not PROMISE.search(h):
        fixes.append("Add tension (a mistake, a myth) or a promise (what they'll get).")
    if n > 200:
        fixes.append("Cut to under 200 chars — remove the setup, keep the claim.")
    if tags or c.URL_RE.search(h):
        fixes.append("Remove hashtags/links from the hook.")
    return {
        "score": score,
        "band": band,
        "hook_type": _hook_type(h),
        "weighted_chars": n,
        "fits_280": n <= 280,
        "reasons": reasons,
        "fixes": fixes,
        "verdict": f"{score}/100 ({_hook_type(h)}): {band}.",
    }


@AGENT.tool
def count_post(post: str) -> dict:
    """Count a single post the way X does: URLs = 23 chars, emoji/CJK = 2, everything else 1. Returns fit, overage and what to trim.

    Call on any post that might be near the limit — the model's own count is usually off
    when links or emoji are present.

    Args:
        post: The post text exactly as it will be published.
    """
    c.guard(post, "Post", 10000)
    n = c.x_length(post)
    urls = c.URL_RE.findall(post)
    emoji_n = c.count_emoji(post)
    sents = text.sentences(post)
    trim_hint = ""
    if n > 280 and sents:
        # drop sentences from the end until it fits
        keep = list(sents)
        while keep and c.x_length(" ".join(keep)) > 280:
            keep.pop()
        trim_hint = " ".join(keep) if keep else "(no sentence-level cut fits — split into two posts)"
    return {
        "weighted_chars": n,
        "raw_chars": len(post),
        "limit": 280,
        "fits": n <= 280,
        "over_by": max(0, n - 280),
        "remaining": max(0, 280 - n),
        "urls": len(urls),
        "url_chars_counted": 23 * len(urls),
        "emoji": emoji_n,
        "lines": len([ln for ln in post.splitlines() if ln.strip()]),
        "words": len(text.words(post)),
        "trim_to_fit": trim_hint,
        "verdict": ("fits" if n <= 280 else f"over by {n - 280} — cut an adjective, then a clause, then split") + f" ({n}/280 weighted).",
    }


def _pack(units: list[str], limit: int) -> list[str]:
    """Greedy-pack text units into chunks ≤ limit weighted chars; over-long units split on words."""
    chunks: list[str] = []
    cur = ""
    for u in units:
        u = u.strip()
        if not u:
            continue
        if c.x_length(u) > limit:
            if cur:
                chunks.append(cur)
                cur = ""
            piece = ""
            for w in u.split():
                cand = (piece + " " + w).strip()
                if c.x_length(cand) > limit and piece:
                    chunks.append(piece)
                    piece = w
                else:
                    piece = cand
            if piece:
                cur = piece
            continue
        cand = (cur + " " + u).strip() if cur else u
        if c.x_length(cand) <= limit:
            cur = cand
        else:
            chunks.append(cur)
            cur = u
    if cur:
        chunks.append(cur)
    return chunks


@AGENT.tool
def split_thread(source: str, numbering: Literal["1/", "1/N", "(1/N)", "none"] = "1/", paragraph_mode: Literal["hard", "pack"] = "hard", max_chars: int = 280) -> dict:
    """Split long text into a thread at paragraph and sentence boundaries (never mid-sentence), numbered, every post ≤ the limit by X's weighted count.

    Use to draft a thread from an article or essay. "hard" paragraph mode starts a new
    post at every paragraph break (write one paragraph per intended post); "pack" fills
    each post as fully as sentences allow.

    Args:
        source: The long text to split (plain text or markdown).
        numbering: "1/" prefix, "1/N" prefix with total, "(1/N)" suffix, or "none".
        paragraph_mode: "hard" = paragraph breaks always start a new post; "pack" = pack sentences across paragraphs.
        max_chars: Weighted character limit per post (default 280; use 500 for Threads, 300 for Bluesky).
    """
    c.guard(source, "Source")
    if not 100 <= max_chars <= 25000:
        raise ToolError("max_chars must be between 100 and 25000.")
    plain = c.strip_markdown(source)
    paras = c.paragraphs(plain)
    if not paras:
        raise ToolError("No text to split.")
    reserve = {"1/": 4, "1/N": 7, "(1/N)": 9, "none": 0}[numbering]
    limit = max_chars - reserve
    if paragraph_mode == "hard":
        bodies: list[str] = []
        for p in paras:
            bodies.extend(_pack(text.sentences(p), limit))
    else:
        units = [s for p in paras for s in text.sentences(p)]
        bodies = _pack(units, limit)
    if len(bodies) > 100:
        raise ToolError(f"That would be {len(bodies)} posts — split the source into parts (max 100 posts).")
    total = len(bodies)
    posts = []
    for i, b in enumerate(bodies, 1):
        if numbering == "1/":
            t = f"{i}/ {b}"
        elif numbering == "1/N":
            t = f"{i}/{total} {b}"
        elif numbering == "(1/N)":
            t = f"{b} ({i}/{total})"
        else:
            t = b
        posts.append({"n": i, "text": t, "weighted_chars": c.x_length(t), "fits": c.x_length(t) <= max_chars})
    longest = max(p["weighted_chars"] for p in posts)
    notes = []
    if total > 15:
        notes.append(f"{total} posts is long for read-through — consider two threads or cutting.")
    if total == 1:
        notes.append("Fits in a single post — no thread needed.")
    return {
        "posts": posts,
        "count": total,
        "longest_post_chars": longest,
        "all_fit": all(p["fits"] for p in posts),
        "source_words": len(text.words(plain)),
        "notes": notes,
        "summary": f"{total} posts, longest {longest}/{max_chars}. Now rewrite each so it opens with its own point — a split is a draft, not a thread.",
    }


@AGENT.tool
def lint_thread(posts: list[str], max_chars: int = 280) -> dict:
    """Lint a finished thread: per-post weighted length, numbering sequence, links before the last post, hashtags, dangling openers, duplicates, empties, CTA in the close.

    Call with the final list before delivering. Fix everything in `flags`; the thread is
    done only when `clean` is true.

    Args:
        posts: The thread as a list of post strings, in order (hook first).
        max_chars: Weighted character limit per post (default 280).
    """
    if not isinstance(posts, list) or not posts:
        raise ToolError("posts must be a non-empty list of strings.")
    if len(posts) > 100:
        raise ToolError("Max 100 posts per lint.")
    if not 100 <= max_chars <= 25000:
        raise ToolError("max_chars must be between 100 and 25000.")
    report = []
    flags: list[str] = []
    seen: dict[str, int] = {}
    numbers: list[int | None] = []
    total_tags = 0
    for i, p in enumerate(posts, 1):
        p = str(p or "")
        n = c.x_length(p)
        issues = []
        if not p.strip():
            issues.append("empty post")
        if n > max_chars:
            issues.append(f"over limit by {n - max_chars}")
        m = NUMBERING_RE.search(p)
        num = None
        if m:
            g = [x for x in m.groups() if x]
            num = int(g[0]) if g else None
        numbers.append(num)
        urls = c.URL_RE.findall(p)
        if urls and i < len(posts):
            issues.append("link before the last post — move to the close or a reply")
        tags = c.HASHTAG_RE.findall(p)
        total_tags += len(tags)
        if i == 1 and tags:
            issues.append("hashtag in the hook")
        body = re.sub(r"^\s*\d{1,3}\s*/\s*\d{0,3}\s*", "", p)
        if DANGLING.match(body.strip()):
            issues.append("starts with a dangling conjunction — won't stand alone")
        key = re.sub(r"\W+", " ", body.lower()).strip()
        if key and key in seen:
            issues.append(f"duplicate of post {seen[key]}")
        elif key:
            seen[key] = i
        if len([ln for ln in p.splitlines() if ln.strip()]) > 6:
            issues.append("more than 6 lines — split or tighten")
        if c.count_emoji(p) > 3:
            issues.append("more than 3 emoji")
        report.append({"n": i, "weighted_chars": n, "fits": n <= max_chars, "numbered_as": num, "issues": issues})
        for iss in issues:
            flags.append(f"Post {i}: {iss}")
    present = [x for x in numbers if x is not None]
    if present and len(present) != len(posts):
        flags.append(f"Numbering on {len(present)}/{len(posts)} posts — number all or none.")
    elif present and present != list(range(1, len(posts) + 1)):
        flags.append(f"Numbering out of sequence: {present}.")
    if total_tags > 2:
        flags.append(f"{total_tags} hashtags across the thread — keep to ≤ 2 (ideally 0).")
    last = str(posts[-1] or "")
    if len(posts) > 1 and not CTA_RE.search(last):
        flags.append("Last post has no CTA (follow / subscribe / repost / link).")
    if len(posts) > 15:
        flags.append(f"{len(posts)} posts — read-through drops sharply past 15; split into two threads.")
    hook_n = report[0]["weighted_chars"]
    if hook_n > 240:
        flags.append(f"Hook is {hook_n} chars — trim under 200 so the whole promise shows in the preview.")
    return {
        "posts": report,
        "count": len(posts),
        "total_weighted_chars": sum(r["weighted_chars"] for r in report),
        "avg_chars": round(sum(r["weighted_chars"] for r in report) / len(report)),
        "flags": flags,
        "clean": not flags,
        "verdict": "Thread lints clean — ready to post." if not flags else f"{len(flags)} issue(s) to fix before posting.",
    }
