"""Meta Writer — title tags and meta descriptions that fit the SERP in pixels and earn the click."""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from ...core import Agent, ToolError
from ...lib import text as _text
from . import _common as c

AGENT = Agent(
    slug="meta-writer",
    name="Meta Writer",
    category="growth",
    tagline="Write title tags and meta descriptions that fit Google's pixel limits and lift click-through rate.",
    description=(
        "Writes and validates title tags and meta descriptions the way a CTR-obsessed SEO does: measures "
        "them in real SERP pixels (Arial 20px / 14px, desktop and mobile), previews the truncation, scores "
        "keyword position, brand placement, specificity and click triggers, and audits whole site exports "
        "for duplicates, missing tags and cannibalising titles — then hands back paste-ready copy."
    ),
    triggers=[
        "write a title tag and meta description for this page",
        "is this title too long for Google / will it get truncated",
        "check these page titles and descriptions for length and duplicates",
        "improve the CTR of our search snippets",
        "SERP preview of a title and description",
    ],
    examples=[
        "Write 3 title tag options and a meta description for our page on 'standing desk for small spaces'. Brand: DeskLab.",
        "Here's a CSV of 200 URLs with titles and descriptions from Screaming Frog — find duplicates and anything over the limit.",
        "Will this title get cut off? 'The Complete, Definitive and Ultimate Guide to Sourdough Starter Maintenance | BakeHouse'",
    ],
    connectors=["Google Search Console", "Google Sheets", "WordPress", "Shopify", "Webflow"],
    playbook="""
    ## Standard
    You are the SEO who owns click-through rate. Rankings get impressions; the snippet gets
    the click. The one metric: CTR at a given position vs. the position's benchmark (roughly
    #1 ≈ 25-30%, #3 ≈ 10%, #5 ≈ 6%, #10 ≈ 2-3% on desktop for non-brand queries — treat as
    orders of magnitude, not targets). Excellent output: every title and description fits in
    pixels, leads with the query's words, promises something specific, and no two pages on
    the site share one.

    ## Intake
    Need: the page's topic or URL and its target keyword. Nice to have: brand name, what the
    page uniquely offers (price, number of items, year, free, speed), current CTR/position
    from Search Console, and the competing titles on the SERP. If the brand is unknown, omit
    the suffix and say so. Ask at most one question, and only when you cannot tell what the
    page is for.

    ## Procedure
    1. **Draft 3-5 title variants** using the formulas below. Then call
       `meta_writer__serp_preview` for each title + description pair. It returns pixel width
       at Google's desktop (600px title / 920px description) and mobile widths, the exact
       truncation point, and the visible preview. Never estimate by character count.
    2. **Score the title.** Call `meta_writer__score_title` with the title, keyword and
       brand. It checks keyword position, brand placement, separators, repetition, all-caps,
       power/number/year triggers, and truncation, returning a 0-100 score with fixes.
       Iterate until the best variant scores ≥ 80 and fits.
    3. **Score the description.** Call `meta_writer__score_description`. It checks length in
       px and chars, keyword presence, a call to action or value promise, active voice,
       first-person plural creep, and whether it duplicates the title.
    4. **Site-wide work:** when given an export, call `meta_writer__audit_snippets` with the
       rows. It finds duplicate titles/descriptions, missing tags, over/under length, titles
       that are just the brand, and near-duplicate titles that suggest cannibalisation.
       Fix the duplicates first — they are the highest-leverage bulk change.
    5. **Choose and present.** Lead with the recommended title + description; show the two
       runner-ups with a one-line reason each. Quote px widths from the tool.
    6. **Self-check.** Keyword in the first half of the title; brand at the end or absent;
       description ≤ 920px and ≥ 70 chars; no claim the page cannot keep.

    ## Frameworks
    - **Title formulas:** `<Keyword>: <Specific promise> | <Brand>` ·
      `<Number> <Keyword> <Qualifier> (<Year>)` · `<Keyword> — <Differentiator>` ·
      `How to <Outcome> <Qualifier>`. Keyword within the first 60% of the string.
    - **Pixel limits:** desktop title 600px @ Arial 20px (≈ 55-60 chars), mobile title
      wraps at two lines (~920px total); description 920px @ Arial 14px on desktop
      (≈ 155-160 chars), ~680px on mobile (≈ 120 chars). Google rewrites titles it finds
      too long, keyword-stuffed or boilerplate — fitting is a rewrite defence.
    - **Click triggers that test well:** specific numbers, current year for evergreen guides,
      brackets "[Free Template]", parenthetical qualifiers, price/"free", speed ("in 5 min").
    - **Description = answer + reason:** sentence 1 states what the page delivers with the
      keyword; sentence 2 gives the reason to click (proof, scope, benefit); optional CTA.
    - **Separator:** `|` or `–`; use one type per site. Do not use two separators in one title.

    ## Output format
    ```
    # Snippet — <page> · keyword: <kw>

    ## Recommended
    **Title:** <…>
    <N>px desktop (fits/cut at "…") · <chars> chars · score <N>/100
    **Description:** <…>
    <N>px · <chars> chars · score <N>/100

    ## Alternatives
    1. <title> — <px>px · <why it might win: e.g. tests a number>
    2. <title> — <px>px · <why>

    ## SERP preview (desktop)
    <Title as it will display>
    <domain › path>
    <Description as it will display>

    ## Notes
    - <assumption about brand / page purpose; what to A/B in Search Console after 4 weeks>
    ```
    For site-wide audits, output the duplicate groups and the over-limit list first, each with
    the replacement.

    ## Anti-patterns
    - Character counting. A title of 58 W's is 3× wider than 58 i's; use pixels.
    - Brand first ("Acme | Best Standing Desks") unless it is a brand query.
    - Stuffing two keywords with a pipe: "Standing Desk | Standing Desks for Small Spaces".
    - Descriptions that describe the company instead of the page ("We are a leading provider…").
    - Promising what the page does not contain (numbers, "free", "2026 updated") — CTR up, pogo-sticking up, rankings down.
    - Writing one title and calling it done. Draft variants; the tool picks the fit, you pick the promise.
    """,
)

TITLE_PX = 20
DESC_PX = 14
LIMITS = {"desktop": {"title": 600, "description": 920}, "mobile": {"title": 920, "description": 680}}
POWER_WORDS = frozenset("free best guide ultimate complete easy fast quick proven new simple checklist template step-by-step tips ideas examples top".split())
CTA_WORDS = re.compile(r"\b(learn|discover|find|get|see|compare|start|try|download|shop|explore|read|book|watch|browse)\b", re.I)
SPAMMY = re.compile(r"(!{2,}|\bclick here\b|\b#1\b|\bguaranteed\b|100%)", re.I)
MAX_ROWS = 5000


def _preview_one(s: str, px: float, limit: float) -> dict:
    width = c.text_width(s, px)
    fits = width <= limit
    visible = s if fits else c.fit_prefix(s, px, limit - c.char_width("…", px))
    return {"px": width, "limit_px": limit, "fits": fits, "over_by_px": round(max(0.0, width - limit), 1), "visible": visible + ("" if fits else " …"), "cut_chars": 0 if fits else len(s) - len(visible)}


@AGENT.tool
def serp_preview(title: str, description: str = "", url: str = "") -> dict:
    """Measure a title and description in SERP pixels (desktop and mobile) and show exactly where Google truncates them.

    Uses Arial advance widths at 20px (title) and 14px (description) against Google's ~600px desktop
    title and ~920px description limits (mobile: 920px / 680px). Returns widths, fit, cut point and
    the visible snippet.

    Args:
        title: The proposed title tag text.
        description: The proposed meta description text (optional).
        url: The page URL, rendered as the breadcrumb line of the preview (optional).
    """
    t = " ".join(title.split())
    if not t:
        raise ToolError("title is empty.")
    if len(t) > 500 or len(description) > 2000:
        raise ToolError("title max 500 chars, description max 2000 chars.")
    d = " ".join(description.split())
    out = {
        "title": {"text": t, "chars": len(t), "desktop": _preview_one(t, TITLE_PX, LIMITS["desktop"]["title"]), "mobile": _preview_one(t, TITLE_PX, LIMITS["mobile"]["title"])},
    }
    if d:
        out["description"] = {"text": d, "chars": len(d), "desktop": _preview_one(d, DESC_PX, LIMITS["desktop"]["description"]), "mobile": _preview_one(d, DESC_PX, LIMITS["mobile"]["description"])}
    crumb = ""
    if url:
        from urllib.parse import urlparse

        p = urlparse(url if "://" in url else "https://" + url)
        parts = [x for x in p.path.split("/") if x]
        crumb = (p.hostname or "") + (" › " + " › ".join(parts) if parts else "")
    out["breadcrumb"] = crumb
    out["preview_desktop"] = "\n".join(x for x in [out["title"]["desktop"]["visible"], crumb, out.get("description", {}).get("desktop", {}).get("visible", "")] if x)
    td = out["title"]["desktop"]
    dd = out.get("description", {}).get("desktop")
    verdict = []
    verdict.append(f"Title {td['px']:.0f}px: " + ("fits desktop." if td["fits"] else f"cut on desktop by {td['over_by_px']}px (drop ~{td['cut_chars']} chars)."))
    if dd:
        verdict.append(f"Description {dd['px']:.0f}px: " + ("fits desktop." if dd["fits"] else f"cut by {dd['over_by_px']}px."))
        if len(d) < 70:
            verdict.append("Description is short (< 70 chars) — Google may replace it.")
    out["verdict"] = " ".join(verdict)
    return out


@AGENT.tool
def score_title(title: str, keyword: str, brand: str = "") -> dict:
    """Score a title tag 0-100 for SEO and click-through: keyword position, brand placement, separators, triggers, pixel fit.

    Args:
        title: The title tag text.
        keyword: The primary keyword the page targets.
        brand: The brand name expected as a suffix (optional).
    """
    t = " ".join(title.split())
    kw = keyword.strip().lower()
    if not t or not kw:
        raise ToolError("title and keyword are required.")
    if len(t) > 500:
        raise ToolError("title max 500 chars.")
    low = t.lower()
    score, fixes, notes = 100, [], []
    width = c.text_width(t, TITLE_PX)
    if width > LIMITS["desktop"]["title"]:
        score -= 20
        fixes.append(f"{width:.0f}px > 600px: Google will cut it at '{c.fit_prefix(t, TITLE_PX, 600 - 10)}…' — shorten.")
    elif width < 300:
        score -= 8
        fixes.append(f"Only {width:.0f}px — room for a qualifier or promise.")
    pos = low.find(kw)
    if pos < 0:
        kw_tokens = set(c.tokens(kw))
        covered = kw_tokens & set(c.tokens(t))
        if kw_tokens and len(covered) == len(kw_tokens):
            score -= 8
            notes.append("Keyword words present but not as a phrase — acceptable, exact phrase is stronger.")
        else:
            score -= 30
            fixes.append(f"Keyword '{keyword}' is missing — put it in the first half.")
    elif pos > len(t) * 0.5:
        score -= 10
        fixes.append("Keyword starts after the midpoint — move it earlier.")
    if low.count(kw) > 1:
        score -= 15
        fixes.append("Keyword repeated — once is enough.")
    b = brand.strip().lower()
    if b:
        bpos = low.find(b)
        if bpos == 0 and pos != 0:
            score -= 12
            fixes.append("Brand first — move brand to the end as ' | Brand'.")
        elif bpos < 0:
            notes.append("No brand suffix; fine if pixels are tight.")
    seps = len(re.findall(r"\s[|–—-]\s", t)) + t.count(" : ")
    if seps > 1:
        score -= 8
        fixes.append("More than one separator — keep one.")
    if t.isupper() and len(t) > 8:
        score -= 15
        fixes.append("ALL CAPS reads as spam — use title case.")
    caps_words = [w for w in t.split() if len(w) > 3 and w.isupper() and not w.isdigit()]
    if len(caps_words) >= 2 and not t.isupper():
        score -= 5
        fixes.append(f"Shouty words: {' '.join(caps_words[:3])}.")
    if SPAMMY.search(t):
        score -= 10
        fixes.append("Spammy pattern (!!, click here, guaranteed, 100%) — remove.")
    words = [w.lower() for w in _text.words(t)]
    dup = [w for w, n in Counter(words).items() if n > 1 and w not in _text.STOPWORDS and len(w) > 3]
    if dup:
        score -= 5
        fixes.append(f"Repeated word(s): {', '.join(dup)}.")
    triggers = []
    if re.search(r"\b\d+\b", t):
        triggers.append("number")
    if re.search(r"\b20\d\d\b", t):
        triggers.append("year")
    if re.search(r"[\[\(].+[\]\)]", t):
        triggers.append("bracket qualifier")
    pw = [w for w in words if w in POWER_WORDS]
    if pw:
        triggers.append(f"power word ({pw[0]})")
    if not triggers:
        score -= 6
        fixes.append("No click trigger — add a number, year, bracketed qualifier or specific promise.")
    generic = low.strip() in ("home", "homepage", b, "welcome", "untitled")
    if generic:
        score = min(score, 20)
        fixes.insert(0, "Title is generic/brand-only — describe the page.")
    score = max(0, min(100, score))
    return {
        "title": t,
        "score": score,
        "px": width,
        "chars": len(t),
        "fits_desktop": width <= LIMITS["desktop"]["title"],
        "keyword_position": pos if pos >= 0 else None,
        "keyword_in_first_half": 0 <= pos <= len(t) * 0.5,
        "click_triggers": triggers,
        "fixes": fixes,
        "notes": notes,
        "verdict": "Ship it." if score >= 80 and not fixes else ("Close — apply the fixes." if score >= 60 else "Rewrite."),
    }


@AGENT.tool
def score_description(description: str, keyword: str, title: str = "") -> dict:
    """Score a meta description 0-100: pixel fit, keyword, value promise or CTA, voice, and overlap with the title.

    Args:
        description: The meta description text.
        keyword: The primary keyword the page targets.
        title: The page's title tag, to detect a description that merely repeats it (optional).
    """
    d = " ".join(description.split())
    kw = keyword.strip().lower()
    if not d or not kw:
        raise ToolError("description and keyword are required.")
    if len(d) > 2000:
        raise ToolError("description max 2000 chars.")
    low = d.lower()
    score, fixes = 100, []
    width = c.text_width(d, DESC_PX)
    if width > LIMITS["desktop"]["description"]:
        score -= 15
        fixes.append(f"{width:.0f}px > 920px: truncates after '{c.fit_prefix(d, DESC_PX, 910)}…'.")
    if len(d) < 70:
        score -= 20
        fixes.append(f"{len(d)} chars is too short; Google will likely substitute page text. Aim 120-155.")
    elif len(d) < 110:
        score -= 6
        fixes.append("Under 110 chars — add the reason to click.")
    if kw not in low:
        score -= 20
        fixes.append("Keyword missing — include it once (Google bolds query words).")
    elif low.count(kw) > 1:
        score -= 8
        fixes.append("Keyword repeated.")
    has_cta = bool(CTA_WORDS.search(d))
    has_number = bool(re.search(r"\d", d))
    if not has_cta and not has_number:
        score -= 10
        fixes.append("No CTA verb or concrete number — give a reason to click.")
    if re.search(r"\b(we are|we're|our company|leading provider|world[- ]class)\b", low):
        score -= 12
        fixes.append("Company-speak ('we are a leading…') — describe what the reader gets.")
    passive = len(_text.passive_sentences(d))
    if passive:
        score -= 5
        fixes.append(f"{passive} passive sentence(s) — make it active.")
    if SPAMMY.search(d):
        score -= 10
        fixes.append("Spammy pattern — remove.")
    if d.endswith((",", ";", "-", "and", "the")):
        score -= 5
        fixes.append("Ends mid-thought.")
    overlap = None
    if title:
        tt = set(c.tokens(title))
        dt = set(c.tokens(d))
        overlap = round(len(tt & dt) / max(1, len(tt)), 2)
        if overlap >= 0.8 and len(tt) >= 3:
            score -= 10
            fixes.append("Description just restates the title — add new information.")
    sents = _text.sentences(d)
    score = max(0, min(100, score))
    return {
        "description": d,
        "score": score,
        "px": width,
        "chars": len(d),
        "fits_desktop": width <= LIMITS["desktop"]["description"],
        "sentences": len(sents),
        "has_keyword": kw in low,
        "has_cta": has_cta,
        "has_number": has_number,
        "title_overlap": overlap,
        "fixes": fixes,
        "verdict": "Ship it." if score >= 80 and not fixes else ("Close — apply the fixes." if score >= 60 else "Rewrite."),
    }


@AGENT.tool
def audit_snippets(rows: list[dict]) -> dict:
    """Audit a site export of URLs with titles and descriptions: duplicates, missing, over/under limit, brand-only titles, near-duplicate titles.

    Args:
        rows: List of {"url": str, "title": str, "description": str} (up to 5000 rows; description optional).
    """
    if not rows:
        raise ToolError("rows is empty.")
    if len(rows) > MAX_ROWS:
        raise ToolError(f"Too many rows ({len(rows)}); max {MAX_ROWS}.")
    titles: dict[str, list[str]] = defaultdict(list)
    descs: dict[str, list[str]] = defaultdict(list)
    problems: list[dict] = []
    token_sets: list[tuple[str, str, frozenset]] = []
    counts = Counter()
    for i, r in enumerate(rows):
        url = str(r.get("url") or f"row {i + 1}")
        t = " ".join(str(r.get("title") or "").split())
        d = " ".join(str(r.get("description") or "").split())
        if not t:
            problems.append({"url": url, "issue": "missing title", "severity": "high"})
            counts["missing_title"] += 1
        else:
            titles[t.lower()].append(url)
            w = c.text_width(t, TITLE_PX)
            if w > LIMITS["desktop"]["title"]:
                problems.append({"url": url, "issue": f"title {w:.0f}px > 600px", "severity": "medium", "value": t})
                counts["title_too_long"] += 1
            elif w < 200:
                problems.append({"url": url, "issue": f"title only {w:.0f}px", "severity": "low", "value": t})
                counts["title_too_short"] += 1
            if len(_text.words(t)) <= 2:
                problems.append({"url": url, "issue": "title is 1-2 words (brand/generic)", "severity": "medium", "value": t})
                counts["title_generic"] += 1
            token_sets.append((url, t, frozenset(c.tokens(t))))
        if not d:
            problems.append({"url": url, "issue": "missing description", "severity": "medium"})
            counts["missing_description"] += 1
        else:
            descs[d.lower()].append(url)
            w = c.text_width(d, DESC_PX)
            if w > LIMITS["desktop"]["description"]:
                problems.append({"url": url, "issue": f"description {w:.0f}px > 920px", "severity": "low", "value": d[:80]})
                counts["description_too_long"] += 1
            elif len(d) < 70:
                problems.append({"url": url, "issue": f"description {len(d)} chars (< 70)", "severity": "low", "value": d})
                counts["description_too_short"] += 1
    dup_titles = [{"title": k, "urls": v} for k, v in titles.items() if len(v) > 1]
    dup_descs = [{"description": k[:100], "urls": v} for k, v in descs.items() if len(v) > 1]
    near = []
    if len(token_sets) <= 1500:
        for a in range(len(token_sets)):
            ua, ta, sa = token_sets[a]
            if len(sa) < 2:
                continue
            for b in range(a + 1, len(token_sets)):
                ub, tb, sb = token_sets[b]
                if ta.lower() == tb.lower() or len(sb) < 2:
                    continue
                if c.jaccard(set(sa), set(sb)) >= 0.75:
                    near.append({"a": {"url": ua, "title": ta}, "b": {"url": ub, "title": tb}})
                    if len(near) >= 200:
                        break
            if len(near) >= 200:
                break
    sev_order = {"high": 0, "medium": 1, "low": 2}
    problems.sort(key=lambda p: sev_order[p["severity"]])
    return {
        "rows": len(rows),
        "counts": dict(counts) | {"duplicate_title_groups": len(dup_titles), "duplicate_description_groups": len(dup_descs), "near_duplicate_title_pairs": len(near)},
        "duplicate_titles": dup_titles[:100],
        "duplicate_descriptions": dup_descs[:100],
        "near_duplicate_titles": near[:100],
        "problems": problems[:500],
        "summary": (
            f"{len(rows)} pages: {len(dup_titles)} duplicate-title groups, {len(near)} near-duplicate pairs (cannibalisation risk), "
            f"{counts['missing_title']} missing titles, {counts['title_too_long']} titles over 600px, {counts['missing_description']} missing descriptions. Fix duplicates first."
        ),
    }
