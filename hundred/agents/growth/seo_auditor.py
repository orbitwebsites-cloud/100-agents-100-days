"""SEO Auditor — a technical + on-page audit of any HTML page, scored and prioritised like an agency deliverable."""

from __future__ import annotations

import re
from collections import Counter
from urllib.parse import urlparse

from ...core import Agent, ToolError
from ...lib import text as _text
from . import _common as c

AGENT = Agent(
    slug="seo-auditor",
    name="SEO Auditor",
    category="growth",
    tagline="Paste a page's HTML; get a scored on-page audit with the exact fixes, ordered by ranking impact.",
    description=(
        "Runs a senior-SEO on-page and technical audit from the page source: title and meta length in "
        "real SERP pixels, heading outline, keyword placement, thin-content check, image alt coverage, "
        "canonical and robots directives, internal/external link hygiene and anchor text. Every finding "
        "is scored by impact and effort and comes with the literal replacement to ship — not generic advice."
    ),
    triggers=[
        "audit this page for SEO",
        "why isn't this page ranking / on-page SEO review",
        "check title, meta description, headings and alt text on this HTML",
        "technical SEO check of a landing page or blog post",
        "find SEO issues in this page source",
    ],
    examples=[
        "Here's the HTML of our pricing page — audit it for SEO. Target keyword: 'project management software'.",
        "Our blog post on 'how to brew cold brew' dropped from #4 to #11. Here's the source. What's wrong?",
        "Run an on-page SEO check on this landing page and give me the fixes in priority order.",
    ],
    connectors=["Google Search Console", "WordPress", "Webflow", "Shopify", "HubSpot", "Notion"],
    playbook="""
    ## Standard
    You are a senior technical SEO who has audited thousands of pages. The one metric that
    matters: does the page give Google an unambiguous answer to "what query is this the best
    result for, and is it trustworthy?" Excellent output is a prioritised fix list where every
    item states the *current* value, the *replacement* value, and the *reason* — a developer
    can ship it without asking a question. Never say "improve your title"; give the new title.

    ## Intake
    You need the raw HTML (view-source, a fetched document, or a CMS export). Nice to have:
    the target keyword, the page URL, and Search Console data (impressions, average position,
    CTR). If the keyword is missing, infer it from title/H1 and state the inference. Ask at
    most one question — and only if there is no HTML at all. Never fetch pages yourself; the
    user or a connector supplies the HTML.

    ## Procedure
    1. **Parse and score.** Call `seo_auditor__audit_page` with the HTML, the URL and the
       target keyword. It returns the element inventory (title, description, canonical, robots,
       H1s, word count, image alt coverage, links) and a 0-100 score built from weighted checks.
       Read the `issues` list: each has `severity` (critical/high/medium/low), the `element`,
       the `problem`, the `current` value and a concrete `fix`. Do not re-derive counts yourself.
    2. **Check the outline.** Call `seo_auditor__heading_outline` to lint the H1-H6 tree:
       missing/multiple H1s, skipped levels, empty or duplicate headings, headings that are
       styled questions vs. statements. Section depth tells you whether the page answers the
       query or merely mentions it.
    3. **Check keyword and content signals.** Call `seo_auditor__content_signals` with the
       HTML, the keyword and the URL. It reports placement (title, H1, first 100 words, URL, alt,
       description), density, readability, thin-content risk, and semantic coverage of the
       keyword's tokens. Under 300 words with commercial intent is thin; a keyword density
       above ~2.5% reads as stuffing; the keyword absent from the first 100 words is a fix.
    4. **Audit links.** Call `seo_auditor__link_audit` with the HTML and base URL. Look for:
       generic anchors ("click here", "read more"), external links without `rel` review,
       broken-looking hrefs (`#`, `javascript:`), too few internal links (< 3 on a content
       page), and the same URL linked with conflicting anchors.
    5. **Directives sanity.** From the audit output: `noindex` on a page that should rank is
       critical; a canonical pointing off-page means this URL is not meant to rank — say so
       before anything else; missing canonical on parameterised URLs is high, and the canonical
       you prescribe is the clean URL without the query string. URL hygiene (uppercase,
       underscores, parameters, > 115 chars) is low: only change a live URL with a 301.
    6. **Prioritise.** Order by severity, then by (impact ÷ effort). Cap the shipped list at
       the 10 highest-value fixes; put the rest in "Also noticed". Write the replacement
       title/description yourself using the keyword-first rule and pixel limits reported.
    7. **Self-check.** Every fix names current → replacement. No fix contradicts another
       (e.g. "add keyword to H1" while also "reduce keyword density"). Score quoted verbatim.

    ## Frameworks
    - **Title:** keyword in the first 60% of the string, ≤ 600px desktop (≈ 55-60 chars),
      brand suffix only if room, no keyword repeated, no ALL CAPS.
    - **Description:** 120-155 chars, keyword once, a reason to click, ≤ 920px desktop.
    - **One H1**, matching (not identical to) the title; H2s answer sub-questions of the query.
    - **Thin content thresholds:** < 300 words = thin for commercial/informational pages;
      product pages ≥ 150 words of unique copy; a "pillar" guide ≥ 1,500.
    - **E-E-A-T signals** to look for in the HTML: author byline, dated updates, outbound
      citations to primary sources, about/contact links in nav.
    - **Severity rubric:** critical = blocks indexing/ranking (noindex, wrong canonical, no
      title); high = primary relevance signal missing (no H1, keyword absent from title,
      thin content); medium = quality signals (alt text, description, outline); low = polish.

    ## Output format
    ```
    # SEO audit — <URL or page name> · Score <N>/100
    **Target keyword:** <kw> (<given|inferred>) · **Words:** N · **Indexable:** yes/no

    ## Blockers (fix today)
    1. <Issue> — current: `<value>` → ship: `<replacement>` — why: <one line>

    ## High-impact fixes
    | # | Element | Current | Replacement | Impact | Effort |
    |---|---|---|---|---|---|

    ## Also noticed
    - <medium/low items, one line each>

    ## New title + description (ready to paste)
    Title: <…> (<px>px / <chars> chars)
    Description: <…> (<chars> chars)

    ## Next
    <One sentence: the single most important thing, and what to re-check in 2-4 weeks.>
    ```

    ## Anti-patterns
    - Listing 40 issues of equal weight. A page has 3-5 things that matter; lead with them.
    - "Add more content." Say which sub-question the page fails to answer and the H2 to add.
    - Recommending keyword insertion into every element — that is stuffing, and it reads as such.
    - Treating a canonicalised or noindexed page as a ranking problem. It is a configuration decision; surface it first.
    - Quoting character counts for titles. Google truncates by pixel width; use the reported px.
    - Auditing rendered-JS content you cannot see. If the body text is near-empty but scripts are heavy, say the page may be client-rendered and that the audit covers the raw HTML only.
    """,
)

GENERIC_ANCHORS = frozenset(
    {"click here", "here", "read more", "learn more", "more", "link", "this", "this page", "website", "continue", "go", "view", "see more", "more info", "details"}
)
TITLE_PX_LIMIT = 600
DESC_PX_LIMIT = 920


def _severity_weight(sev: str) -> int:
    return {"critical": 25, "high": 12, "medium": 6, "low": 2}[sev]


@AGENT.tool
def audit_page(html: str, url: str = "", keyword: str = "") -> dict:
    """Run the full on-page SEO audit of an HTML document and score it 0-100 with prioritised fixes.

    Parses title, meta description, robots, canonical, hreflang, headings, images, links, word
    count and Open Graph tags; evaluates each against senior-SEO thresholds (pixel widths, keyword
    placement, thin content, alt coverage) and returns weighted issues with concrete fixes.

    Args:
        html: The raw HTML source of the page (up to 400k characters).
        url: The page's URL, used for canonical comparison and internal-link classification.
        keyword: The primary target keyword or phrase; if empty, placement checks are skipped.
    """
    page = c.parse_html(html)
    kw = keyword.strip().lower()
    issues: list[dict] = []

    def add(sev, element, problem, fix, current=""):
        issues.append({"severity": sev, "element": element, "problem": problem, "current": current, "fix": fix})

    # ── title
    title = page.title
    title_px = c.text_width(title, 20)
    if not title:
        add("critical", "title", "No <title> tag", "Add a keyword-first title, 50-60 chars / ≤ 600px.")
    else:
        if page.title_count > 1:
            add("high", "title", f"{page.title_count} <title> tags — Google may pick either", "Keep exactly one <title>.", title)
        if title_px > TITLE_PX_LIMIT:
            add("medium", "title", f"Title is {title_px:.0f}px; Google truncates at ~{TITLE_PX_LIMIT}px", f"Shorten so it ends by: '{c.fit_prefix(title, 20, TITLE_PX_LIMIT)}…'", title)
        elif len(title) < 30:
            add("low", "title", f"Title is short ({len(title)} chars) — leaving relevance on the table", "Extend to 50-60 chars with the keyword and a differentiator.", title)
        if kw and kw not in title.lower():
            add("high", "title", "Target keyword absent from title", f"Rewrite as '<{keyword}> — <benefit> | <Brand>'.", title)
        elif kw and title.lower().find(kw) > len(title) * 0.6:
            add("low", "title", "Keyword appears late in the title", "Move the keyword into the first half.", title)
        if title.isupper() and len(title) > 10:
            add("low", "title", "Title is ALL CAPS", "Use sentence or title case.", title)
        if kw and title.lower().count(kw) > 1:
            add("medium", "title", "Keyword repeated in title (stuffing signal)", "Use the keyword once.", title)

    # ── description
    desc = page.description
    if not desc:
        add("medium", "meta description", "No meta description — Google will write its own snippet", "Add 120-155 chars with the keyword once and a reason to click.")
    else:
        dpx = c.text_width(desc, 14)
        if len(desc) > 160 or dpx > DESC_PX_LIMIT:
            add("low", "meta description", f"Description is {len(desc)} chars / {dpx:.0f}px; truncates at ~{DESC_PX_LIMIT}px", f"Trim to end by: '{c.fit_prefix(desc, 14, DESC_PX_LIMIT)}…'", desc)
        elif len(desc) < 70:
            add("low", "meta description", f"Description is only {len(desc)} chars", "Expand to 120-155 chars.", desc)
        if kw and kw not in desc.lower():
            add("low", "meta description", "Keyword absent from description (no bolding in snippet)", "Include the keyword once, naturally.", desc)
    if "description#dup" in page.metas:
        add("medium", "meta description", "Multiple meta descriptions", "Keep one.")

    # ── robots / canonical
    robots = page.robots.lower()
    indexable = "noindex" not in robots
    if not indexable:
        add("critical", "robots", "Page is set to noindex — it cannot rank", "Remove `noindex` if this page should rank; otherwise stop the audit here.", page.robots)
    if "nofollow" in robots:
        add("high", "robots", "Page-level nofollow — passes no internal link equity", "Remove `nofollow` from the robots meta.", page.robots)
    canon = page.canonical
    canonical_status = "missing"
    if len(canon) > 1:
        add("critical", "canonical", f"{len(canon)} canonical tags — Google ignores all of them", "Keep exactly one canonical.", " | ".join(canon))
        canonical_status = "conflicting"
    elif canon:
        canonical_status = "self" if not url or _same_url(canon[0], url) else "points elsewhere"
        if canonical_status == "points elsewhere":
            add("critical", "canonical", f"Canonical points to another URL: {canon[0]}", "If this page should rank, make the canonical self-referencing.", canon[0])
        if not canon[0].startswith("http"):
            add("medium", "canonical", "Canonical is relative", "Use an absolute https URL.", canon[0])
    else:
        clean = _clean_url(url) if url else ""
        has_params = bool(url and urlparse(url).query)
        add(
            "high" if has_params else "medium",
            "canonical",
            "No canonical tag" + (" on a parameterised URL — every ?variant/?ref copy competes as a duplicate" if has_params else ""),
            f"Add <link rel=\"canonical\" href=\"{clean or 'https://…'}\">" + (" (the clean URL, without the query string)." if has_params else "."),
        )

    # ── headings
    h1s = page.h1s
    if not h1s:
        add("high", "h1", "No H1", f"Add one H1 containing '{keyword or 'the target keyword'}'.")
    elif len(h1s) > 1:
        add("medium", "h1", f"{len(h1s)} H1s dilute the topic signal", "Keep one H1; demote the rest to H2.", " | ".join(h1s)[:200])
    if h1s and kw and not any(kw in h.lower() for h in h1s):
        add("high", "h1", "Keyword absent from H1", f"Rewrite the H1 to include '{keyword}'.", h1s[0])
    if h1s and title and h1s[0].strip().lower() == title.strip().lower():
        add("low", "h1", "H1 identical to title", "Vary the H1 so title and H1 cover two phrasings.", h1s[0])
    if len(page.headings) < 2 and len(_text.words(page.text)) > 400:
        add("medium", "headings", "Long page with no subheadings", "Add H2s for each sub-question the page answers.")

    # ── content
    ws = _text.words(page.text)
    n_words = len(ws)
    if n_words < 300:
        sev = "high" if n_words < 150 else "medium"
        add(sev, "content", f"Thin content: {n_words} words in the HTML body", "Target ≥ 300 words of unique copy (≥ 150 for product pages); if the page is JS-rendered, confirm the rendered DOM.")
    if kw:
        first100 = " ".join(ws[:100]).lower()
        if kw not in first100:
            add("medium", "content", "Keyword not in the first 100 words", "Open with a sentence that states the keyword and the page's answer.")
        dens = _text.keyword_density(page.text, keyword)["density_pct"]
        if dens > 2.5:
            add("medium", "content", f"Keyword density {dens}% — reads as stuffing", "Reduce to 0.5-1.5%; use synonyms and entities.")

    # ── images
    imgs = page.images
    missing_alt = [i for i in imgs if i["alt"] is None]
    empty_alt = [i for i in imgs if i["alt"] == ""]
    if missing_alt:
        add("medium" if len(missing_alt) < 5 else "high", "images", f"{len(missing_alt)}/{len(imgs)} images have no alt attribute", "Add descriptive alt (or alt=\"\" for decorative).", ", ".join(i["src"][-40:] for i in missing_alt[:5]))
    if url.lower().startswith("https://"):
        insecure = [i["src"] for i in imgs if i["src"].lower().startswith("http://")]
        if insecure:
            add("medium", "security", f"Mixed content: {len(insecure)} image(s) loaded over http on an https page", "Serve the images over https (browsers block or warn on mixed content).", ", ".join(x[-50:] for x in insecure[:3]))
    long_alt = [i for i in imgs if i["alt"] and len(i["alt"]) > 100]
    if long_alt:
        add("low", "images", f"{len(long_alt)} alt text(s) over 100 characters", "Describe the image in ≤ 100 characters; alt is not a place for keyword lists.", long_alt[0]["alt"][:120])
    no_dims = [i for i in imgs if not i["width"] or not i["height"]]
    if no_dims:
        add("low", "images", f"{len(no_dims)} image(s) lack width/height (layout shift / CLS)", "Set width and height attributes.", ", ".join(i["src"][-40:] for i in no_dims[:3]))
    if imgs and not any(i["loading"] == "lazy" for i in imgs) and len(imgs) > 6:
        add("low", "images", f"{len(imgs)} images, none lazy-loaded", "Add loading=\"lazy\" to below-the-fold images.")

    # ── links
    base_host = c.host_of(url)
    internal = external = nav_none = 0
    generic = []
    for link in page.links:
        kind = c.is_internal(link["href"], base_host)
        if kind is None:
            nav_none += 1
        elif kind:
            internal += 1
        else:
            external += 1
        if link["text"].lower().strip(" .!") in GENERIC_ANCHORS:
            generic.append(link["text"])
    if internal < 3 and n_words > 300:
        add("medium", "links", f"Only {internal} internal links", "Link to 3-8 related pages with descriptive anchors.")
    if generic:
        add("low", "links", f"{len(generic)} generic anchors ({', '.join(sorted(set(generic))[:4])})", "Replace with anchors that describe the destination.")

    # ── technical
    if not page.has_viewport:
        add("high", "mobile", "No viewport meta — fails mobile-friendly", "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">.")
    if not page.lang:
        add("low", "html", "No lang attribute on <html>", "Add lang=\"en\" (or the page language).")
    if not page.charset and "content-type" not in page.metas:
        add("low", "html", "No charset declared", "Add <meta charset=\"utf-8\"> as the first element in <head>.")
    og_missing = [t for t in ("og:title", "og:description", "og:image") if t not in page.metas]
    if og_missing:
        add("low", "social", f"Missing Open Graph tags: {', '.join(og_missing)}", "Add them so shares render a card.")
    if not page.jsonld:
        add("low", "structured data", "No JSON-LD structured data", "Add Article/Product/FAQ schema as appropriate (see Schema Markup Builder).")
    if page.external_scripts + page.inline_scripts > 10 and n_words < 200:
        add("medium", "rendering", "Heavy scripts and little HTML text — page may be client-rendered", "Verify Google sees the rendered content (URL Inspection → View crawled page).")
    if url and urlparse(url).scheme == "http":
        add("high", "security", "Page served over http", "Serve over https and 301 http → https.")
    url_issues = _url_issues(url) if url else []
    if url_issues:
        add("low", "url", "URL hygiene: " + "; ".join(url_issues), f"Prefer a lowercase, hyphenated, parameter-free path, e.g. {_suggest_path(url)} (301 the old URL if you change it).", url)

    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    issues.sort(key=lambda i: order[i["severity"]])
    penalty = sum(_severity_weight(i["severity"]) for i in issues)
    score = max(0, 100 - penalty)
    counts = Counter(i["severity"] for i in issues)
    verdict = (
        "Not indexable — fix directives before anything else." if not indexable or canonical_status in ("points elsewhere", "conflicting")
        else "Strong page; polish only." if score >= 85
        else "Solid base with clear gaps." if score >= 65
        else "Major on-page work needed." if score >= 40
        else "Rebuild the on-page fundamentals."
    )
    return {
        "score": score,
        "verdict": verdict,
        "indexable": indexable,
        "canonical_status": canonical_status,
        "inventory": {
            "title": title,
            "title_chars": len(title),
            "title_px": title_px,
            "description": desc,
            "description_chars": len(desc),
            "robots": page.robots or None,
            "canonical": canon[0] if canon else None,
            "hreflang_count": len(page.hreflang),
            "lang": page.lang or None,
            "h1": h1s,
            "heading_count": len(page.headings),
            "word_count": n_words,
            "images": len(imgs),
            "images_missing_alt": len(missing_alt),
            "images_empty_alt": len(empty_alt),
            "links_internal": internal,
            "links_external": external,
            "links_non_navigational": nav_none,
            "jsonld_blocks": len(page.jsonld),
            "og_tags": {k: v for k, v in page.metas.items() if k.startswith("og:")},
            "viewport": page.has_viewport,
        },
        "issue_counts": dict(counts),
        "issues": issues,
        "top_fixes": [f"[{i['severity']}] {i['element']}: {i['fix']}" for i in issues[:5]],
    }


def _clean_url(u: str) -> str:
    """The URL without query string or fragment — the usual canonical target for a parameterised URL."""
    p = urlparse(u.strip())
    return p._replace(query="", fragment="").geturl()


def _url_issues(u: str) -> list[str]:
    p = urlparse(u.strip())
    path = p.path or "/"
    out = []
    if any(ch.isupper() for ch in path):
        out.append("uppercase characters in path")
    if "_" in path:
        out.append("underscores in path (Google treats '_' as a word joiner; use hyphens)")
    if p.query:
        out.append(f"query parameters ({p.query[:40]})")
    if " " in u or "%20" in u:
        out.append("contains a space")
    if "//" in path:
        out.append("multiple slashes")
    if re.search(r"[^\x00-\x7f]", u):
        out.append("non-ASCII characters")
    if len(u) > 115:
        out.append(f"{len(u)} characters (over 115)")
    return out


def _suggest_path(u: str) -> str:
    p = urlparse(u.strip())
    segs = [c.slugify(s.replace("_", "-"), 80) for s in (p.path or "/").split("/") if s]
    return "/" + "/".join(s for s in segs if s) + ("/" if (p.path or "").endswith("/") else "")


def _same_url(a: str, b: str) -> bool:
    def norm(u: str) -> str:
        p = urlparse(u.strip())
        host = (p.hostname or "").lower().removeprefix("www.")
        path = (p.path or "/").rstrip("/") or "/"
        return f"{host}{path}"

    return norm(a) == norm(b)


@AGENT.tool
def heading_outline(html: str) -> dict:
    """Lint the H1-H6 heading tree: missing/multiple H1s, skipped levels, empty or duplicate headings.

    Returns the indented outline plus each defect with the heading it concerns, so you can judge
    whether the page's structure answers the query's sub-questions.

    Args:
        html: The raw HTML source of the page.
    """
    page = c.parse_html(html)
    hs = page.headings
    problems = []
    outline = []
    prev = 0
    seen: Counter[str] = Counter()
    for h in hs:
        lvl, t = h["level"], h["text"]
        outline.append(("  " * (lvl - 1)) + f"H{lvl}: {t or '(empty)'}")
        if not t:
            problems.append({"heading": f"H{lvl}", "problem": "empty heading", "fix": "Remove it or give it text."})
        if prev and lvl > prev + 1:
            problems.append({"heading": f"H{lvl}: {t[:60]}", "problem": f"skips from H{prev} to H{lvl}", "fix": f"Use H{prev + 1}."})
        if len(_text.words(t)) > 14:
            problems.append({"heading": f"H{lvl}: {t[:60]}", "problem": f"{len(_text.words(t))}-word heading", "fix": "Cut to ≤ 10 words; move detail into the paragraph."})
        key = t.lower().strip()
        if key:
            seen[key] += 1
        prev = lvl
    for k, n in seen.items():
        if n > 1:
            problems.append({"heading": k[:60], "problem": f"appears {n} times", "fix": "Make each heading unique."})
    n_h1 = len(page.h1s)
    if n_h1 == 0:
        problems.insert(0, {"heading": "H1", "problem": "no H1", "fix": "Add exactly one H1 with the target keyword."})
    elif n_h1 > 1:
        problems.insert(0, {"heading": "H1", "problem": f"{n_h1} H1s", "fix": "Keep one; demote others to H2."})
    if hs and hs[0]["level"] != 1:
        problems.append({"heading": f"H{hs[0]['level']}: {hs[0]['text'][:60]}", "problem": "first heading is not the H1", "fix": "Put the H1 before any H2-H6."})
    levels = Counter(h["level"] for h in hs)
    questions = sum(1 for h in hs if h["text"].rstrip().endswith("?") or re.match(r"^(how|what|why|when|where|which|can|does|is|should)\b", h["text"], re.I))
    return {
        "outline": outline,
        "counts": {f"h{i}": levels.get(i, 0) for i in range(1, 7)},
        "question_headings": questions,
        "problems": problems,
        "verdict": "Outline is clean." if not problems else f"{len(problems)} outline defect(s); fix H1 issues first.",
    }


@AGENT.tool
def content_signals(html: str, keyword: str, url: str = "") -> dict:
    """Measure keyword placement, density, readability and thin-content risk for a target keyword.

    Reports whether the keyword (and each of its tokens) appears in the title, H1, first 100 words,
    meta description, image alts, headings and (when a URL is given) the URL slug, plus word count,
    Flesch readability and a stuffing/thinness verdict.

    Args:
        html: The raw HTML source of the page.
        keyword: The primary target keyword or phrase (2-80 characters).
        url: The page URL (optional); enables the keyword-in-slug check.
    """
    kw = keyword.strip()
    if not 2 <= len(kw) <= 80:
        raise ToolError("keyword must be 2-80 characters.")
    page = c.parse_html(html)
    kwl = kw.lower()
    ws = _text.words(page.text)
    body = page.text.lower()
    first100 = " ".join(ws[:100]).lower()
    alts = " ".join((i["alt"] or "") for i in page.images).lower()
    subheads = " ".join(h["text"] for h in page.headings if h["level"] >= 2).lower()
    placement = {
        "title": kwl in page.title.lower(),
        "h1": any(kwl in h.lower() for h in page.h1s),
        "first_100_words": kwl in first100,
        "meta_description": kwl in page.description.lower(),
        "subheadings": kwl in subheads,
        "image_alt": kwl in alts,
        "body": kwl in body,
    }
    if url:
        slug_tokens = set(c.tokens(re.sub(r"[-_/.]+", " ", urlparse(url).path)))
        kw_toks = set(c.tokens(kw))
        placement["url"] = bool(kw_toks) and kw_toks <= slug_tokens
    dens = _text.keyword_density(page.text, kw)
    kw_tokens = [t for t in c.tokens(kw) if t]
    body_tokens = set(c.tokens(page.text))
    token_coverage = {t: (t in body_tokens) for t in kw_tokens}
    read = _text.readability(page.text) if ws else {}
    n = len(ws)
    thin = n < 300
    stuffed = dens["density_pct"] > 2.5
    placed = sum(placement.values())
    fixes = []
    if not placement["title"]:
        fixes.append("Put the keyword in the title.")
    if not placement["h1"]:
        fixes.append("Put the keyword in the H1.")
    if not placement["first_100_words"]:
        fixes.append("State the keyword in the opening sentence.")
    if url and not placement["url"]:
        fixes.append(f"URL slug lacks the keyword ({', '.join(sorted(set(c.tokens(kw)) - set(c.tokens(re.sub(r'[-_/.]+', ' ', urlparse(url).path)))))} missing) — only change it on a new page or with a 301.")
    if not placement["subheadings"] and len(page.headings) > 2:
        fixes.append("Use the keyword (or a close variant) in one H2.")
    if thin:
        fixes.append(f"Only {n} words — expand to ≥ 300 with sub-questions answered.")
    if stuffed:
        fixes.append(f"Density {dens['density_pct']}% — cut repetitions to ≤ 1.5%.")
    missing_tokens = [t for t, ok in token_coverage.items() if not ok]
    if missing_tokens:
        fixes.append(f"Body never uses: {', '.join(missing_tokens)}.")
    return {
        "keyword": kw,
        "word_count": n,
        "placement": placement,
        "placement_score": f"{placed}/{len(placement)}",
        "occurrences": dens["occurrences"],
        "density_pct": dens["density_pct"],
        "token_coverage": token_coverage,
        "readability": read,
        "paragraphs": len(page.paragraphs),
        "avg_paragraph_words": round(sum(len(_text.words(p)) for p in page.paragraphs) / max(1, len(page.paragraphs)), 1),
        "thin_content": thin,
        "stuffing_risk": stuffed,
        "top_terms": [t for t, _ in _text.top_terms(page.text, 10)],
        "fixes": fixes,
        "verdict": ("Keyword well placed." if placed >= len(placement) - 2 and not thin and not stuffed else "Relevance signals incomplete — apply the fixes."),
    }


@AGENT.tool
def link_audit(html: str, base_url: str = "") -> dict:
    """Classify every link on the page (internal/external/non-navigational) and lint anchor text and rel attributes.

    Finds generic anchors, empty anchors, javascript:/# hrefs, duplicate targets with conflicting
    anchors, external links missing rel=noopener on target=_blank, and http links on an https page.

    Args:
        html: The raw HTML source of the page.
        base_url: The page URL; needed to tell internal from external absolute links.
    """
    page = c.parse_html(html)
    host = c.host_of(base_url)
    internal, external, other = [], [], []
    problems = []
    by_target: dict[str, set[str]] = {}
    for link in page.links:
        href, anchor = link["href"], link["text"]
        kind = c.is_internal(href, host)
        entry = {"href": href, "anchor": anchor, "rel": link["rel"] or None}
        if kind is None:
            other.append(entry)
            if href.strip() in ("", "#") or href.lower().startswith("javascript:"):
                problems.append({"href": href or "(empty)", "anchor": anchor, "problem": "non-crawlable href", "fix": "Use a real URL or a <button>."})
            continue
        (internal if kind else external).append(entry)
        low = anchor.lower().strip(" .!")
        if not anchor:
            problems.append({"href": href, "anchor": "", "problem": "empty anchor (no text or alt)", "fix": "Add link text or an alt on the linked image."})
        elif low in GENERIC_ANCHORS:
            problems.append({"href": href, "anchor": anchor, "problem": "generic anchor", "fix": "Describe the destination page in the anchor."})
        elif len(_text.words(anchor)) > 12:
            problems.append({"href": href, "anchor": anchor[:60], "problem": "anchor is a whole sentence", "fix": "Shorten to 2-6 descriptive words."})
        if low.startswith("http"):
            problems.append({"href": href, "anchor": anchor[:60], "problem": "naked URL as anchor", "fix": "Use descriptive text."})
        if not kind and link["target"] == "_blank" and "noopener" not in link["rel"]:
            problems.append({"href": href, "anchor": anchor[:60], "problem": "target=_blank without rel=noopener", "fix": "Add rel=\"noopener\"."})
        if base_url.startswith("https") and href.lower().startswith("http://"):
            problems.append({"href": href, "anchor": anchor[:60], "problem": "http link on https page", "fix": "Update to https."})
        norm = href.split("#")[0].rstrip("/").lower()
        if norm and anchor:
            by_target.setdefault(norm, set()).add(low)
    for target, anchors in by_target.items():
        if len(anchors) > 2:
            problems.append({"href": target, "anchor": " / ".join(sorted(anchors)[:3]), "problem": f"same URL linked with {len(anchors)} different anchors", "fix": "Standardise on one descriptive anchor."})
    nofollow_ext = sum(1 for e in external if e["rel"] and "nofollow" in e["rel"])
    dup_internal = Counter(e["href"] for e in internal)
    return {
        "counts": {"internal": len(internal), "external": len(external), "non_navigational": len(other), "external_nofollow": nofollow_ext, "duplicate_internal_targets": sum(1 for v in dup_internal.values() if v > 1)},
        "internal": internal[:100],
        "external": external[:100],
        "problems": problems,
        "verdict": ("Link hygiene is good." if not problems and len(internal) >= 3 else f"{len(problems)} link problem(s)" + ("; add internal links (fewer than 3)." if len(internal) < 3 else ".")),
    }
