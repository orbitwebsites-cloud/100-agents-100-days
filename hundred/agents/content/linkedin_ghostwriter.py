"""LinkedIn Ghostwriter — posts built for the fold, the feed and the comments."""

from __future__ import annotations

import re

from ...core import Agent, ToolError
from ...lib import text
from . import _common as c

FOLD_DESKTOP = 210
FOLD_MOBILE = 140
MAX_CHARS = 3000

AGENT = Agent(
    slug="linkedin-ghostwriter",
    name="LinkedIn Ghostwriter",
    category="content",
    tagline="Write LinkedIn posts in your voice that survive the 'see more' fold and earn comments, not just impressions.",
    description=(
        "Ghostwrites LinkedIn posts the way top creators' writers do: a hook engineered for the ~210-character "
        "fold, one-idea-per-line formatting that reads on a phone, a story-or-lesson structure, and a close "
        "that invites comments. Checks the 3,000-character limit, what shows above the fold on desktop and "
        "mobile, hashtag count and placement, link handling, emoji density, markdown residue LinkedIn won't "
        "render, and the I-vs-you ratio — then reformats the draft so it posts clean."
    ),
    triggers=[
        "write a LinkedIn post about X",
        "ghostwrite LinkedIn content in my voice",
        "improve the hook of my LinkedIn post",
        "format this for LinkedIn / does this fit the see-more fold",
        "turn this story or win into a LinkedIn post",
        "why is my LinkedIn post not getting engagement",
    ],
    examples=[
        "Write a LinkedIn post about the hiring mistake I made last quarter — here are the notes. Founder voice, no cringe.",
        "Here's my draft. Fix the hook so it works above the fold and format it for mobile.",
        "Turn this customer win into a LinkedIn post for our head of sales. 3 hashtags, link in comments.",
        "My last 10 posts got 800 impressions each. Here's the best one — what's wrong with it?",
    ],
    connectors=["LinkedIn", "Taplio", "Buffer", "Notion", "Google Docs"],
    playbook="""
    ## Standard
    You are a LinkedIn ghostwriter whose clients are known for sounding like themselves, only
    sharper. Excellent means the first two lines force the click on "…more", every line
    earns the next, and the close makes a specific person want to reply. The one metric:
    **comments per 1,000 impressions** — LinkedIn's feed rewards dwell time and replies, not
    likes. Write for the reply.

    ## Intake
    You need the raw material (a story, an opinion, a lesson, a win) and whose voice it is.
    Assume: first person, 900-1,500 characters, 0-3 hashtags at the end, no external link in
    the body (put it in the first comment), no emoji unless the author uses them. If you have
    previous posts by the author, mirror their sentence length, humour and pronoun use. Ask
    only if you have a topic but no point of view — a post without a stance is filler.

    ## Procedure
    1. **Find the point.** Before writing: what is the one sentence the reader should repeat
       to a colleague? Write it down. If you can't, ask one question. Every post has exactly
       one point; the story exists to earn it.
    2. **Write 3 hooks, score them, keep the best.** Call `linkedin_ghostwriter__score_hook`
       on each of three different hook types (see Frameworks). Keep the top score; if none
       reaches 70, rewrite with a specific number, a named thing or a contradiction. The
       hook is what shows above the fold: ~210 characters on desktop, ~140 on mobile, and
       LinkedIn cuts at the third line break. Line 1 must work alone.
    3. **Draft the body** to a structure: Hook → context in one line → the turn (what went
       wrong / what surprised you) → the lesson in 3-5 short lines → the close. One sentence
       per line for the first 5 lines; short paragraphs (≤ 3 lines) after. Use concrete
       nouns and numbers; cut adjectives. Never explain the lesson twice.
    4. **Close for comments.** End with one of: a specific question the reader can answer
       from experience; a stance to agree or disagree with; a "what would you add?". Not
       "Thoughts?". No link in the body — write the first comment separately with the link.
    5. **Format.** Call `linkedin_ghostwriter__format_post` on the draft. It strips markdown
       LinkedIn can't render (headings, [links]; **bold** is stripped, or converted to Unicode
       bold with `unicode_bold: true` — only for 2-4 words, since screen readers and search
       can't read it), puts one sentence per line where the paragraph is long, normalises
       bullets, lifts every hashtag (including ones glued to the end of a sentence) onto one
       line at the end, capped at `max_hashtags` (default 3), and collapses extra blank lines.
       Use its output as the post.
    6. **Check.** Call `linkedin_ghostwriter__post_check`. Fix every flag: over 3,000 chars,
       weak fold text, more than 5 hashtags or hashtags mid-body, external links in the body,
       emoji > 8, paragraphs over 4 lines, markdown residue, an "I"-heavy ratio with no "you",
       no question or stance in the close.
    7. **If asked why a post underperformed**, call `linkedin_ghostwriter__engagement_rate`
       with the numbers, then run `post_check` on the post: the diagnosis is the flags plus
       the ratio (comments vs reactions tells you whether the close worked).
    8. **Deliver**: the post, the first comment (link + one line), the hashtags, and the two
       runner-up hooks with scores. If a LinkedIn or scheduling connector exists, schedule
       as a draft — never publish without a yes.

    ## Frameworks
    - **Hook types**: the specific result ("We cut onboarding from 14 days to 3. One change."),
      the confession ("I turned down a $2M contract last week."), the contrarian ("Stop
      hiring for culture fit."), the number-list ("4 questions I ask every candidate. #3
      ends most interviews."), the observation ("Every great salesperson I've met does
      one thing before a call.").
    - **Fold rule**: under 210 chars and no more than 2 line breaks before the payoff line.
      Never spend the fold on context ("Last week I attended…").
    - **Rhythm**: lines of 3-12 words at the top; longer sentences only in the middle; the
      last line short.
    - **Pronoun ratio**: at least one "you" per three "I"s. Stories are told in first person;
      lessons are handed over in second person.
    - **Hashtags**: 0-3 at the end, specific over broad (#SaaSSales over #Business).
    - **Timing/rough benchmarks**: engagement rate 2% of impressions is solid, 5%+ is
      excellent; a comment is worth far more than a reaction for distribution.

    ## Output format
    ```
    **Hook score:** 81/100 (<type>) · fold: 168/210 chars ✅ · 1,240/3,000 chars

    <the post, formatted and paste-ready>

    #Hashtag1 #Hashtag2 #Hashtag3

    **First comment:** <link + one line of context>
    **Alt hooks:** <hook B — 72> · <hook C — 64>
    **Check:** ✅ fold · ✅ length · ✅ no links in body · ✅ ends on a question
    ```

    ## Anti-patterns
    - "I'm thrilled to announce…", "Humbled to share…", "Excited to…" — openers that get scrolled.
    - Context before the hook: the reader doesn't know you yet; earn the backstory.
    - Broetry with no point: one word per line and nothing to say.
    - Markdown formatting (**bold**, # headings) — LinkedIn shows the asterisks.
    - Five hashtags in the middle of sentences; links in the body; tagging 10 people.
    - Ending with "Thoughts?" or "Agree?" alone. Ask something a specific reader can answer.
    - A lesson stated three times: in the middle, in the close and in a P.S.
    """,
)

SOFT_OPENERS = re.compile(r"^(i'?m (so |really |very |truly |incredibly )?(excited|thrilled|happy|proud|humbled|honou?red|delighted|grateful)|thrilled|excited|humbled|honou?red|delighted to|proud to|pleased to|happy to (share|announce)|hey (guys|everyone|all|linkedin)|last (week|month|year) i (attended|went|had|was)|yesterday i|today i (attended|went)|i wanted to share|quick (update|thought)|as (a|an) [a-z]+,? i)", re.I)
CONTRAST = re.compile(r"\b(but|instead|without|stop|never|nobody|no one|wrong|mistake|mistakes|myth|truth|secret|actually|unpopular|hard truth|don't|isn't|aren't|turned down|fired|failed|quit|lost|worst)\b", re.I)
CTA_CLOSE = re.compile(r"\?|\b(what would you add|agree or disagree|what's your|what is your|how do you|curious|would love to hear|your take|tell me|share yours|which one)\b", re.I)


def _hook_type(h: str) -> str:
    if re.search(r"\b(turned down|fired|failed|quit|got rejected|lost|my (biggest|worst) (mistake|hire|decision)|worst hire|i was wrong|cost (us|me))\b", h, re.I):
        return "confession"
    if re.match(r"^\s*(stop|never|don't|most|everyone|unpopular)\b", h, re.I) or re.search(r"\b(wrong|myth)\b", h, re.I):
        return "contrarian"
    if re.search(r"\b\d[\d,.]*\b", h) and re.search(r"\b(questions?|lessons?|mistakes?|things|rules?|ways?|steps?|signs?)\b", h, re.I):
        return "number-list"
    if re.search(r"\b\d[\d,.]*[%kKxX$]?\b", h) and re.search(r"\b(from|to|cut|grew|went|saved|closed|hit|doubled)\b", h, re.I):
        return "specific result"
    if re.match(r"^\s*(every|the best|most|i've noticed|i noticed)\b", h, re.I):
        return "observation"
    if h.strip().endswith("?"):
        return "question"
    return "statement"


@AGENT.tool
def score_hook(hook: str) -> dict:
    """Score a LinkedIn hook 0-100 for the fold: length vs 210/140 chars, line-1 strength, specificity, contrast, and the openers that get scrolled past.

    Call on each candidate hook (the text above the fold — up to the first 2-3 lines).
    Keep the best; rewrite anything under 70.

    Args:
        hook: The opening lines of the post as they will appear (line breaks preserved).
    """
    c.guard(hook, "Hook", 3000)
    h = hook.strip()
    lines = [ln.strip() for ln in h.splitlines() if ln.strip()]
    line1 = lines[0] if lines else h
    n = len(h)
    score = 50
    reasons: list[str] = []
    if n <= FOLD_MOBILE:
        score += 12
        reasons.append(f"+12 whole hook fits the mobile fold ({n}/{FOLD_MOBILE})")
    elif n <= FOLD_DESKTOP:
        score += 6
        reasons.append(f"+6 fits the desktop fold ({n}/{FOLD_DESKTOP}) but truncates on mobile")
    else:
        score -= 12
        reasons.append(f"-12 {n} chars: the payoff sits below the fold")
    if len(lines) > 3:
        score -= 8
        reasons.append("-8 more than 3 lines before the fold — LinkedIn cuts at line 3")
    if len(text.words(line1)) <= 12:
        score += 6
        reasons.append("+6 line 1 is short enough to read in one glance")
    else:
        score -= 4
        reasons.append("-4 line 1 is long; split it")
    if re.search(r"\d", h):
        score += 14
        reasons.append("+14 specific number")
    if CONTRAST.search(h):
        score += 10
        reasons.append("+10 tension/contrast")
    proper = c.proper_nouns(h)
    if proper:
        score += 4
        reasons.append(f"+4 names something concrete ({proper[0]})")
    if re.search(r"\b(you|your)\b", h, re.I):
        score += 5
        reasons.append("+5 speaks to the reader")
    if SOFT_OPENERS.search(h):
        score -= 18
        reasons.append("-18 soft/announcement opener — gets scrolled")
    if c.HASHTAG_RE.search(h):
        score -= 8
        reasons.append("-8 hashtag in the hook")
    if c.links(h):
        score -= 10
        reasons.append("-10 link in the hook")
    if c.count_emoji(h) > 1:
        score -= 4
        reasons.append("-4 more than one emoji above the fold")
    if re.search(r"\b(in this post|i want to talk about|let me explain|i've been thinking)\b", h, re.I):
        score -= 8
        reasons.append("-8 throat-clearing")
    if line1.rstrip().endswith((".", ":")) and len(lines) >= 2 and len(text.words(line1)) <= 8:
        score += 3
        reasons.append("+3 punchy first line with a beat before line 2")
    words_n = text.words(h)
    if words_n and sum(1 for w in words_n if w.lower() in ("i", "my", "me", "we", "our")) >= 4 and not re.search(r"\b(you|your)\b", h, re.I):
        score -= 5
        reasons.append("-5 all about the author, nothing for the reader yet")
    score = max(0, min(100, score))
    band = "strong — use it" if score >= 75 else "usable — one more pass" if score >= 60 else "rewrite"
    fixes = []
    if n > FOLD_DESKTOP:
        fixes.append(f"Cut {n - FOLD_DESKTOP}+ chars so the payoff shows before '…more'.")
    if not re.search(r"\d", h):
        fixes.append("Add a number: a result, a count, a timeframe.")
    if not CONTRAST.search(h):
        fixes.append("Add tension: a mistake, a refusal, a myth, a 'but'.")
    if SOFT_OPENERS.search(h):
        fixes.append("Delete the announcement opener; start with the claim.")
    return {
        "score": score,
        "band": band,
        "hook_type": _hook_type(h),
        "chars": n,
        "fits_desktop_fold": n <= FOLD_DESKTOP,
        "fits_mobile_fold": n <= FOLD_MOBILE,
        "lines": len(lines),
        "line_1": line1,
        "reasons": reasons,
        "fixes": fixes,
        "verdict": f"{score}/100 ({_hook_type(h)}): {band}.",
    }


@AGENT.tool
def post_check(post: str, hashtags_expected: int = 3) -> dict:
    """Full pre-post check: 3,000-char limit, fold text (desktop/mobile), hashtags, links, emoji, wall-of-text paragraphs, markdown residue, I/you ratio, comment-bait close.

    Call on the formatted post before delivery. Every flag is a concrete fix; the post is
    ready only when `flags` is empty.

    Args:
        post: The full post text exactly as it will be published.
        hashtags_expected: How many hashtags the author wants (0-5). Used to flag too many or too few.
    """
    c.guard(post, "Post", 20000)
    if not 0 <= hashtags_expected <= 10:
        raise ToolError("hashtags_expected must be 0-10.")
    p = post.strip()
    n = len(p)
    flags: list[str] = []
    if n > MAX_CHARS:
        flags.append(f"{n} chars — over the 3,000 limit by {n - MAX_CHARS}.")
    elif n < 300:
        flags.append(f"Only {n} chars — very short posts rarely earn dwell time; 900-1,500 is the working range.")
    elif n > 2200:
        flags.append(f"{n} chars — long for the feed; consider cutting toward 1,500 unless it's a story that earns it.")
    lines = p.split("\n")
    # fold: first 3 non-empty lines or 210 chars, whichever comes first
    fold_desktop = p[:FOLD_DESKTOP]
    third_break = [i for i, ch in enumerate(p) if ch == "\n"]
    nonempty_breaks = []
    count = 0
    for i, ln in enumerate(lines):
        if ln.strip():
            count += 1
        if count == 3 and i < len(lines) - 1:
            nonempty_breaks.append(sum(len(x) + 1 for x in lines[: i + 1]))
            break
    if nonempty_breaks and nonempty_breaks[0] < FOLD_DESKTOP:
        fold_desktop = p[: nonempty_breaks[0]]
    fold_mobile = p[:FOLD_MOBILE] if len(fold_desktop) > FOLD_MOBILE else fold_desktop
    hook_words = text.words(fold_desktop)
    if not re.search(r"\d", fold_desktop) and not CONTRAST.search(fold_desktop):
        flags.append("Nothing specific above the fold — no number, no tension. Rewrite the hook.")
    if SOFT_OPENERS.search(p):
        flags.append("Opens with an announcement/soft opener — start with the claim.")
    tags = c.HASHTAG_RE.findall(p)
    tag_positions = [m.start() for m in c.HASHTAG_RE.finditer(p)]
    last_block_start = max(0, len(p) - max(60, 12 * max(1, len(tags))))
    mid_body_tags = [pos for pos in tag_positions if pos < last_block_start]
    if len(tags) > 5:
        flags.append(f"{len(tags)} hashtags — LinkedIn reach drops past 5; keep 0-3.")
    if len(tags) > hashtags_expected:
        flags.append(f"{len(tags)} hashtags vs {hashtags_expected} expected.")
    if hashtags_expected and not tags:
        flags.append(f"No hashtags — author expected {hashtags_expected}.")
    if mid_body_tags:
        flags.append(f"{len(mid_body_tags)} hashtag(s) inside the body — move to the last line.")
    lk = c.links(p)
    if lk:
        flags.append(f"{len(lk)} link(s) in the body — move to the first comment (or the last line if it must stay).")
    emoji_n = c.count_emoji(p)
    if emoji_n > 8:
        flags.append(f"{emoji_n} emoji — cap at ~5; they read as spam past that.")
    md = []
    if re.search(r"\*\*[^*\n]+\*\*|__[^_\n]+__", p):
        md.append("**bold**")
    if re.search(r"^\s{0,3}#{1,6}\s", p, re.M):
        md.append("# headings")
    if c.MD_LINK_RE.search(p):
        md.append("[markdown](links)")
    if re.search(r"^\s*[-*]\s", p, re.M):
        md.append("- markdown bullets (use • or →)")
    if md:
        flags.append("Markdown LinkedIn won't render: " + ", ".join(md) + ".")
    paras = c.paragraphs(p)
    walls = [pp for pp in paras if len(pp.splitlines()) > 4 or len(text.words(pp)) > 70]
    if walls:
        flags.append(f"{len(walls)} wall-of-text paragraph(s) over 4 lines / 70 words — break into 1-3 line blocks.")
    ws = text.words(p)
    i_n = sum(1 for w in ws if w.lower() in ("i", "i'm", "i've", "i'd", "my", "me", "myself"))
    you_n = sum(1 for w in ws if w.lower() in ("you", "your", "you're", "you've", "yours"))
    if i_n >= 6 and you_n == 0:
        flags.append(f"'I' ×{i_n}, 'you' ×0 — hand the lesson to the reader in second person.")
    prose_lines = [c.HASHTAG_RE.sub("", ln).strip() for ln in lines]
    closing = "\n".join([ln for ln in prose_lines if ln and not all(t.startswith("#") for t in ln.split())][-2:])
    if not CTA_CLOSE.search(closing):
        flags.append("Close has no question or stance — end with something a specific reader can answer.")
    if re.search(r"\b(thoughts\?|agree\?)\s*$", closing, re.I):
        flags.append("'Thoughts?' / 'Agree?' is a weak close — ask a specific question.")
    mentions = c.MENTION_RE.findall(p)
    if len(mentions) > 5:
        flags.append(f"{len(mentions)} @mentions — tagging many people reads as spam.")
    rd = text.readability(c.strip_markdown(p))
    if rd["fk_grade"] and rd["fk_grade"] > 10:
        flags.append(f"Reading grade {rd['fk_grade']} — feed readers skim; aim for ≤ 8 with shorter lines.")
    return {
        "chars": n,
        "limit": MAX_CHARS,
        "fits": n <= MAX_CHARS,
        "words": len(ws),
        "lines": len([ln for ln in lines if ln.strip()]),
        "paragraphs": len(paras),
        "fold_desktop_text": fold_desktop,
        "fold_desktop_chars": len(fold_desktop),
        "fold_mobile_text": fold_mobile,
        "hook_words": len(hook_words),
        "hashtags": tags,
        "links": [l["url"] for l in lk],
        "emoji": emoji_n,
        "mentions": len(mentions),
        "i_count": i_n,
        "you_count": you_n,
        "fk_grade": rd["fk_grade"],
        "closing_lines": closing,
        "flags": flags,
        "ready": not flags,
        "verdict": "Post is ready." if not flags else f"{len(flags)} fix(es) before posting.",
    }


@AGENT.tool
def format_post(draft: str, one_sentence_per_line: bool = True, unicode_bold: bool = False, max_hashtags: int = 3) -> dict:
    """Reformat a draft for LinkedIn: strip markdown it can't render (or turn **bold** into Unicode bold), one sentence per line in long paragraphs, clean bullets, every hashtag moved to one line at the end, blank lines normalised.

    Call after drafting, before post_check. Returns the paste-ready text and the list of
    transformations applied.

    Args:
        draft: The post draft (markdown or plain text).
        one_sentence_per_line: Break paragraphs longer than two sentences into one sentence per line (default true — how the feed reads on mobile).
        unicode_bold: Convert **bold** to Unicode bold letters (𝗹𝗶𝗸𝗲 𝘁𝗵𝗶𝘀) instead of stripping it. Screen readers spell these out letter by letter and LinkedIn search can't match them — use for 2-4 words at most.
        max_hashtags: Keep at most this many hashtags (0-5; default 3), in order of first appearance.
    """
    c.guard(draft, "Draft", 20000)
    if not 0 <= max_hashtags <= 5:
        raise ToolError("max_hashtags must be 0-5.")
    changes: list[str] = []
    s = draft.strip()
    if re.search(r"\*\*[^*\n]+\*\*|__[^_\n]+__", s):
        if unicode_bold:
            s = re.sub(r"(\*\*|__)([^*_\n]{1,500}?)\1", lambda m: _unicode_bold(m.group(2)), s)
            changes.append("converted **bold** to Unicode bold (use sparingly: screen readers and search can't read it)")
        else:
            s = re.sub(r"(\*\*|__)([^*_\n]{1,500}?)\1", r"\2", s)
            changes.append("removed **bold** markers (LinkedIn shows the asterisks)")
    if re.search(r"(?<!\w)[*_](?!\s)[^*_\n]{1,300}?(?<!\s)[*_](?!\w)", s):
        s = re.sub(r"(?<!\w)([*_])(?!\s)([^*_\n]{1,300}?)(?<!\s)\1(?!\w)", r"\2", s)
        changes.append("removed *italic* markers")
    if re.search(r"^\s{0,3}#{1,6}\s+", s, re.M):
        s = re.sub(r"^[ \t]{0,3}#{1,6}[ \t]+(.+?)[ \t]*#*[ \t]*$", r"\1", s, flags=re.M)
        changes.append("converted # headings to plain lines")
    if c.MD_LINK_RE.search(s):
        s = c.MD_LINK_RE.sub(lambda m: f"{m.group(1)}: {m.group(2)}" if m.group(1) else m.group(2), s)
        changes.append("expanded [text](url) links to 'text: url'")
    if re.search(r"^[ \t]*[-*+][ \t]+", s, re.M):
        s = re.sub(r"^[ \t]*[-*+][ \t]+", "→ ", s, flags=re.M)
        changes.append("converted markdown bullets to →")
    if re.search(r"^[ \t]*>[ \t]?", s, re.M):
        s = re.sub(r"^[ \t]*>[ \t]?", "", s, flags=re.M)
        changes.append("removed blockquote markers")
    s = s.replace("\r\n", "\n")
    # every hashtag ends up on one line at the end: tag-only lines and trailing tag runs are lifted
    # out; a tag used as a word mid-sentence ("the #sales team") keeps the word and loses the '#'.
    tags_found = c.HASHTAG_RE.findall(s)
    tags: list[str] = []
    for t in tags_found:
        if t.lower() not in [x.lower() for x in tags]:
            tags.append(t)
    moved = False
    if tags_found:
        lines_out = []
        for ln in s.split("\n"):
            stripped = re.sub(r"(?:\s*#[A-Za-z]\w*)+\s*$", "", ln) if c.HASHTAG_RE.search(ln) else ln
            if stripped != ln:
                moved = True
            if ln.strip() and not stripped.strip():
                continue
            new_ln = c.HASHTAG_RE.sub(lambda m: m.group(1), stripped)
            if new_ln != stripped:
                moved = True
            lines_out.append(new_ln.rstrip())
        s = "\n".join(lines_out).strip()
    paras = c.paragraphs(s)
    out_paras = []
    split_count = 0
    for para in paras:
        if para.startswith("→ "):
            out_paras.append(para)
            continue
        if one_sentence_per_line and "\n" not in para:
            sents = text.sentences(para)
            if len(sents) > 2 and len(para) > 120:
                out_paras.append("\n".join(sents))
                split_count += 1
                continue
        out_paras.append(para)
    if split_count:
        changes.append(f"split {split_count} long paragraph(s) into one sentence per line")
    formatted = "\n\n".join(out_paras)
    formatted = re.sub(r"[ \t]+\n", "\n", formatted)
    formatted = re.sub(r"\n{3,}", "\n\n", formatted)
    kept = tags[:max_hashtags]
    if kept:
        formatted = formatted.rstrip() + "\n\n" + " ".join(f"#{t}" for t in kept)
    if tags and (moved or len(tags) > max_hashtags):
        dropped = tags[max_hashtags:]
        changes.append("moved hashtags to one line at the end" + (f"; dropped {', '.join('#' + t for t in dropped)} (cap {max_hashtags})" if dropped else ""))
    if re.search(r"\n{3,}", draft):
        changes.append("collapsed extra blank lines")
    return {
        "formatted": formatted,
        "chars": len(formatted),
        "fits_3000": len(formatted) <= MAX_CHARS,
        "lines": len([ln for ln in formatted.splitlines() if ln.strip()]),
        "hashtags": kept,
        "changes": changes or ["no changes needed"],
        "summary": f"{len(formatted)} chars, {len(changes)} formatting change(s).",
    }


def _unicode_bold(s: str) -> str:
    """Mathematical sans-serif bold: A-Z → U+1D5D4, a-z → U+1D5EE, 0-9 → U+1D7EC."""
    out = []
    for ch in s:
        if "A" <= ch <= "Z":
            out.append(chr(0x1D5D4 + ord(ch) - 65))
        elif "a" <= ch <= "z":
            out.append(chr(0x1D5EE + ord(ch) - 97))
        elif "0" <= ch <= "9":
            out.append(chr(0x1D7EC + ord(ch) - 48))
        else:
            out.append(ch)
    return "".join(out)


@AGENT.tool
def engagement_rate(impressions: int, reactions: int = 0, comments: int = 0, reposts: int = 0, followers: int = 0) -> dict:
    """Compute a post's engagement rate and comment ratio and grade them against rough LinkedIn benchmarks.

    Use when diagnosing performance. Comments are weighted: they drive distribution far
    more than reactions.

    Args:
        impressions: Impressions (views) the post received.
        reactions: Likes and other reactions.
        comments: Comments (exclude the author's own replies if known).
        reposts: Reposts / shares.
        followers: The author's follower count, for reach-vs-audience context (0 = unknown).
    """
    if impressions <= 0:
        raise ToolError("impressions must be a positive number.")
    if min(reactions, comments, reposts, followers) < 0:
        raise ToolError("Counts cannot be negative.")
    engagements = reactions + comments + reposts
    rate = round(100.0 * engagements / impressions, 2)
    weighted = round(100.0 * (reactions + 3 * comments + 2 * reposts) / impressions, 2)
    per_k = round(1000.0 * comments / impressions, 1)
    grade = "excellent" if rate >= 5 else "good" if rate >= 2 else "average" if rate >= 1 else "low"
    reach_vs_followers = round(100.0 * impressions / followers, 1) if followers else None
    diagnosis = []
    if comments == 0 and engagements:
        diagnosis.append("Reactions but no comments: the close didn't ask anything answerable.")
    elif engagements and comments / max(1, engagements) >= 0.3:
        diagnosis.append("Comment-heavy engagement: the close works; the hook decides reach now.")
    if reach_vs_followers is not None and reach_vs_followers < 20:
        diagnosis.append(f"Reached only {reach_vs_followers}% of followers — the hook failed the first-hour test (dwell time).")
    if rate < 1:
        diagnosis.append("Under 1%: rewrite the hook (fold) and shorten lines; check for links in the body.")
    return {
        "impressions": impressions,
        "engagements": engagements,
        "engagement_rate_pct": rate,
        "weighted_engagement_pct": weighted,
        "comments_per_1000_impressions": per_k,
        "comment_share_pct": c.pct(comments, engagements) if engagements else 0.0,
        "reach_pct_of_followers": reach_vs_followers,
        "grade": grade,
        "benchmarks": {"low": "< 1%", "average": "1-2%", "good": "2-5%", "excellent": "≥ 5%"},
        "diagnosis": diagnosis,
        "verdict": f"{rate}% engagement ({grade}); {per_k} comments per 1k impressions.",
    }
