"""Product Listing Writer — marketplace-legal titles, bullets and descriptions that rank and convert."""

from __future__ import annotations

import re
from collections import Counter

from ...core import Agent, ToolError
from ...lib import text
from ._common import pct

AGENT = Agent(
    slug="product-listing",
    name="Product Listing Writer",
    category="ecommerce",
    tagline="Write listings that pass Amazon, Etsy, Shopify, eBay and Walmart rules, cover every keyword, and sell the benefit.",
    description=(
        "Writes and audits product listings for the major marketplaces. Validates every field against the "
        "platform's limits and content rules (title length, banned promo phrases, special characters, "
        "backend-keyword bytes, Etsy tag counts), measures keyword coverage across title, bullets, description "
        "and backend fields so nothing is wasted or stuffed, scores the title formula for search and mobile "
        "truncation, and lints bullets and description for benefit-first, scannable copy. The result is a "
        "listing you can paste in without a rejection or a missed search term."
    ),
    triggers=[
        "write an Amazon product listing / title / bullet points",
        "write an Etsy listing with tags",
        "optimize my product description for Shopify SEO",
        "check my listing against Amazon rules / character limits",
        "which keywords is my listing missing",
        "improve my product title for search",
        "write an eBay or Walmart product listing",
    ],
    examples=[
        "Write an Amazon listing for a 32oz insulated stainless steel water bottle, brand Hydra, keywords: insulated water bottle, 32 oz, leak proof, gym, stainless steel.",
        "Here's my Etsy title, description and tags for a personalised leather journal — check limits and tell me what keywords I'm missing.",
        "Rewrite these five bullets so they lead with benefits and pass Amazon's style rules.",
    ],
    connectors=["Shopify", "Amazon Seller Central", "Etsy", "Google Sheets", "Notion"],
    playbook="""
    ## Standard
    You are a top-1% marketplace listing copywriter: your listings index for every relevant
    search, survive the platform's automated checks, and convert because they answer the
    buyer's questions in the order they ask them. The one metric that matters is
    **conversion rate on the listing page** (unit session %), with search impressions as the
    input you control through keyword coverage. Compliance is the floor, not the goal.

    ## Intake
    You need: the marketplace, the product's facts (brand, what it is, key specs: size,
    material, quantity, compatibility, colour), the target keywords (or the competitor
    listing to mine), the primary use case and buyer, and any claims you must not make
    (medical, "best", certifications you lack). Ask at most 3 questions only if you cannot
    proceed; otherwise assume from the product facts and say what you assumed.

    ## Procedure
    1. **Build the keyword set** (≤ 15): primary keyword (highest volume, exact product
       type), 3-5 secondary (attributes + use cases), long-tail (problem/occasion/gift
       phrasing). Pull from the user's list, competitor titles and the product facts.
    2. **Write the title** with the marketplace formula (Frameworks) and score it with
       `product_listing__score_title` (brand, primary keyword, attributes, mobile
       truncation, banned words). Iterate until ≥ 85.
    3. **Write bullets and description** in the buyer's order: the #1 benefit, the
       proof/spec behind it, fit/compatibility, what's in the box, care/guarantee. Run
       `product_listing__bullet_lint` on the bullets (and description) — it flags feature-
       only bullets, missing lead-ins, duplicates, length and reading grade.
    4. **Validate against the platform** with `product_listing__check_marketplace_limits`
       on every field (title, bullets, description, backend keywords, tags, SEO title/meta).
       It knows the character limits and content rules per marketplace and reports each
       violation with the fix; pass overrides if your category has different limits.
    5. **Check keyword coverage** with `product_listing__keyword_coverage`: which keywords
       appear where, which are missing, what is duplicated in backend fields (wasted bytes),
       and whether the description is stuffed. Move missing keywords into the field with
       room, highest-value field first (title → bullets → description → backend/tags).
    6. **Deliver the final listing** in the output format, every field within limits, plus
       the compliance notes (claims to verify, certifications) and the A/B suggestion for
       the title's first 60 characters.
    7. **Self-check**: no promo/subjective words in the title; primary keyword in the first
       60 characters; each bullet starts with a benefit lead-in; no keyword appears > 3× in
       the description; nothing claims what the product does not do.

    ## Frameworks
    - **Amazon title formula:** Brand + Product type + Key attribute(s) + Size/Quantity +
      Use case/compatibility. ≤ 200 chars max, aim 80-150; no "best seller", "free
      shipping", "#1", no ! $ ? _ { } ^ ¬ ¦, no word more than twice (title policy
      updated 2025 — verify current). Mobile shows ~70-80 chars: front-load.
    - **Amazon bullets:** 5 bullets, ≤ 255 chars each recommended, "LEAD-IN BENEFIT: proof
      and spec" pattern, no promo/pricing, no shipping info, no HTML. Description 2000 chars
      max (A+ replaces it when present). Backend search terms ≤ 250 bytes, no commas needed,
      no repeats of title/bullet words, no brand names, no ASINs.
    - **Etsy:** title ≤ 140 chars, keyword phrase first, readable (Etsy penalises keyword
      lists in titles for buyer experience); 13 tags × ≤ 20 chars, multi-word tags,
      no repeats of each other; use all 13. First ~160 chars of description = meta
      description. 10 photos + video.
    - **Shopify:** product title ≤ 255, SEO title ≤ 70 (Google shows ~60), meta description
      ≤ 320 (Google truncates ~155-160), URL handle short and keyworded; description in
      H2 sections with specs table.
    - **eBay:** title ≤ 80 chars, every word a search term (no "L@@K", no "wow"), item
      specifics filled completely — they drive Cassini ranking more than the description.
    - **Walmart:** product name 50-75 chars recommended, key features 3-10 bullets, description
      ≥ 150 words; conversational, no all-caps; verify current spec sheet.
    - **Google Shopping feed:** title ≤ 150, description ≤ 5000 — front-load the first 70.
    - **Copy rules:** benefit before feature; numbers over adjectives ("keeps ice 24h" beats
      "long-lasting cold"); reading grade ≤ 8; one idea per bullet; answer the top 3
      questions from reviews/Q&A.
    - Scope note: claims like "BPA-free", "FDA approved", "medical grade", "organic" need
      documentation; flag them rather than write them.

    ## Output format
    ```
    # <Marketplace> listing — <product>
    **Title (N/limit chars):** …
    **Bullets:**
    1. LEAD-IN: …
    …
    **Description (N chars):**
    …
    **Backend keywords (N bytes) / Tags (13):** …
    **SEO title / meta (Shopify):** …
    ## Compliance & coverage
    limits: pass/fail per field · keywords: covered X/Y, missing: … · claims to verify: …
    ## Title A/B
    A: <first 60 chars> · B: <first 60 chars>
    ```

    ## Anti-patterns
    - Titles that are keyword lists ("Bottle Water Bottle Insulated Bottle Steel") — banned
      on Amazon (word repeats) and demoted on Etsy.
    - Bullets that are features without a benefit ("Made of 18/8 stainless steel.").
    - Promo language anywhere in title/bullets ("Sale", "Free shipping", "Best", "Guaranteed").
    - Putting keywords in backend search terms that are already in the title — wasted bytes.
    - Description paragraphs of 120 words; shoppers skim on phones.
    - Claims you cannot document; superlatives with no number.
    """,
)

# Marketplace limits. VERIFY against current platform documentation before relying on these;
# callers can override any value via `overrides` (e.g. category-specific bullet limits).
LIMITS: dict[str, dict] = {
    "amazon": {
        "title_max": 200, "title_recommended": 150, "title_mobile": 80, "bullets_max": 5, "bullet_chars_max": 255, "description_max": 2000,
        "backend_bytes_max": 250, "images_max": 9, "title_special_chars": "!$?_{}^¬¦", "title_word_repeat_max": 2, "html_allowed": False,
    },
    "etsy": {"title_max": 140, "title_recommended": 140, "title_mobile": 60, "tags_max": 13, "tag_chars_max": 20, "materials_max": 13, "images_max": 10, "meta_description_chars": 160, "html_allowed": False},
    "shopify": {"title_max": 255, "title_recommended": 70, "title_mobile": 60, "seo_title_max": 70, "seo_title_recommended": 60, "meta_description_max": 320, "meta_description_recommended": 155, "html_allowed": True},
    "ebay": {"title_max": 80, "title_recommended": 80, "title_mobile": 60, "subtitle_max": 55, "images_max": 24, "html_allowed": True},
    "walmart": {"title_max": 200, "title_recommended": 75, "title_mobile": 60, "bullets_min": 3, "bullets_max": 10, "description_max": 4000, "description_min_words": 150, "html_allowed": False},
    "google_shopping": {"title_max": 150, "title_recommended": 70, "title_mobile": 70, "description_max": 5000, "html_allowed": False},
}
PROMO_RE = re.compile(
    r"\b(free shipping|free delivery|best ?seller|best selling|#\s?1|number one|top rated|hot (item|sale)|on sale|sale|discount|cheap(est)?|"
    r"guarantee[d]?|100% (satisfaction|money back)|money[- ]back|limited time|buy now|new arrival|great deal|lowest price|premium quality|"
    r"high quality|best|amazing|perfect|must[- ]have)\b",
    re.I,
)
CLAIM_RE = re.compile(r"\b(fda[- ]?(approved|cleared|registered)|medical grade|clinically (proven|tested)|cures?|treats?|bpa[- ]free|organic|non[- ]?toxic|eco[- ]?friendly|biodegradable|antibacterial|hypoallergenic|certified|patented)\b", re.I)
HTML_RE = re.compile(r"<[^>]{1,50}>")
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")


def _caps_words(s: str) -> list[str]:
    return [w for w in text.words(s) if len(w) >= 4 and w.isupper() and not w.isdigit()]


@AGENT.tool
def check_marketplace_limits(
    marketplace: str,
    title: str,
    bullets: list[str] | None = None,
    description: str = "",
    backend_keywords: str = "",
    tags: list[str] | None = None,
    seo_title: str = "",
    meta_description: str = "",
    overrides: dict | None = None,
) -> dict:
    """Validate every listing field against the marketplace's character limits and content rules (promo words, special characters, word repeats, HTML, backend bytes, tag counts) and list each violation with its fix.

    Args:
        marketplace: amazon, etsy, shopify, ebay, walmart or google_shopping.
        title: Product title.
        bullets: Bullet points / key features (Amazon, Walmart).
        description: Product description (plain text or HTML).
        backend_keywords: Amazon backend search terms (space-separated).
        tags: Etsy tags (up to 13).
        seo_title: Shopify SEO/page title.
        meta_description: Shopify meta description.
        overrides: Optional limit overrides, e.g. {"bullet_chars_max": 500, "title_max": 150} for categories with different rules.
    """
    mp = marketplace.lower().strip()
    if mp not in LIMITS:
        raise ToolError(f"marketplace must be one of {', '.join(LIMITS)}.")
    if not title.strip():
        raise ToolError("title is empty.")
    for name, val in (("title", title), ("description", description), ("backend_keywords", backend_keywords), ("seo_title", seo_title), ("meta_description", meta_description)):
        if len(val) > 200_000:
            raise ToolError(f"{name} is absurdly long (200k chars max).")
    lim = dict(LIMITS[mp])
    for k, v in (overrides or {}).items():
        lim[k] = v
    bullets = [b for b in (bullets or []) if b is not None]
    tags = [t for t in (tags or []) if t is not None]
    fails, warns, fields = [], [], {}

    # ── title ──
    n = len(title)
    fields["title"] = {"chars": n, "max": lim["title_max"], "recommended": lim.get("title_recommended"), "mobile_visible": title[: lim.get("title_mobile", 70)]}
    if n > lim["title_max"]:
        fails.append(f"title {n} chars > {lim['title_max']} max — cut {n - lim['title_max']}")
    elif lim.get("title_recommended") and n > lim["title_recommended"]:
        warns.append(f"title {n} chars > {lim['title_recommended']} recommended")
    if n < 20:
        warns.append("title under 20 chars — add product type and key attributes")
    promo = PROMO_RE.findall(title)
    if promo:
        fails.append(f"title promo/subjective words: {', '.join(sorted({(p if isinstance(p, str) else p[0]).lower() for p in promo}))}")
    caps = _caps_words(title)
    if caps:
        (fails if mp in ("amazon", "walmart") else warns).append(f"title ALL CAPS words: {', '.join(caps[:4])}")
    if lim.get("title_special_chars"):
        bad = sorted({c for c in title if c in lim["title_special_chars"]})
        if bad:
            fails.append(f"title special characters not allowed: {' '.join(bad)}")
    if EMOJI_RE.search(title):
        fails.append("title contains emoji")
    if lim.get("title_word_repeat_max"):
        counts = Counter(w.lower() for w in text.words(title) if len(w) > 2 and w.lower() not in text.STOPWORDS)
        rep = [f"{w}×{c}" for w, c in counts.items() if c > lim["title_word_repeat_max"]]
        if rep:
            fails.append(f"title repeats a word more than {lim['title_word_repeat_max']}×: {', '.join(rep)}")
    if mp == "ebay" and re.search(r"l@@k|wow|look!", title, re.I):
        fails.append("eBay title filler ('L@@K', 'WOW') — every word must be a search term")

    # ── bullets ──
    if bullets or lim.get("bullets_max"):
        fields["bullets"] = {"count": len(bullets), "max": lim.get("bullets_max"), "chars": [len(b) for b in bullets]}
        if lim.get("bullets_max") and len(bullets) > lim["bullets_max"]:
            fails.append(f"{len(bullets)} bullets > {lim['bullets_max']} max")
        if lim.get("bullets_min") and 0 < len(bullets) < lim["bullets_min"]:
            warns.append(f"{len(bullets)} bullets < {lim['bullets_min']} recommended minimum")
        if mp == "amazon" and 0 < len(bullets) < 5:
            warns.append(f"only {len(bullets)} bullets — use all 5")
        for i, b in enumerate(bullets, 1):
            if lim.get("bullet_chars_max") and len(b) > lim["bullet_chars_max"]:
                fails.append(f"bullet {i}: {len(b)} chars > {lim['bullet_chars_max']}")
            if not b.strip():
                fails.append(f"bullet {i} is empty")
            if PROMO_RE.search(b):
                fails.append(f"bullet {i}: promo language “{PROMO_RE.search(b).group(0)}”")
            if HTML_RE.search(b):
                fails.append(f"bullet {i}: HTML not allowed")
            if re.search(r"\b(free shipping|ship(ping|s)? (in|within)|price|\$\d)", b, re.I) and mp == "amazon":
                fails.append(f"bullet {i}: shipping/price info not allowed")

    # ── description ──
    if description:
        d_chars = len(description)
        fields["description"] = {"chars": d_chars, "max": lim.get("description_max"), "words": len(text.words(description))}
        if lim.get("description_max") and d_chars > lim["description_max"]:
            fails.append(f"description {d_chars} chars > {lim['description_max']}")
        if lim.get("description_min_words") and len(text.words(description)) < lim["description_min_words"]:
            warns.append(f"description {len(text.words(description))} words < {lim['description_min_words']} recommended")
        if HTML_RE.search(description) and not lim.get("html_allowed", False):
            tags_found = sorted({m.lower() for m in re.findall(r"<\s*/?\s*([a-zA-Z0-9]+)", description)})
            allowed = {"br"} if mp == "amazon" else set()
            if set(tags_found) - allowed:
                fails.append(f"description contains HTML ({', '.join(tags_found[:6])}) — not allowed on {mp}" + (" except <br>" if mp == "amazon" else ""))
        if mp == "etsy":
            fields["description"]["meta_preview"] = description[: lim["meta_description_chars"]]
            if not re.search(r"[a-z]", description[:160].lower()):
                warns.append("first 160 chars of the description are the meta description — start with the keyword phrase")

    # ── backend keywords (Amazon) ──
    if backend_keywords:
        b = backend_keywords.strip()
        nbytes = len(b.encode("utf-8"))
        words = [w.lower() for w in text.words(b)]
        front = {w.lower() for w in text.words(title + " " + " ".join(bullets))}
        dup_front = sorted({w for w in words if w in front and len(w) > 2})
        dup_self = sorted({w for w, c in Counter(words).items() if c > 1})
        fields["backend_keywords"] = {"bytes": nbytes, "max": lim.get("backend_bytes_max"), "words": len(words), "duplicated_from_title_bullets": dup_front, "repeated_within": dup_self}
        if lim.get("backend_bytes_max") and nbytes > lim["backend_bytes_max"]:
            fails.append(f"backend keywords {nbytes} bytes > {lim['backend_bytes_max']}")
        if "," in b:
            warns.append("backend keywords: commas waste bytes — separate with spaces")
        if dup_front:
            warns.append(f"backend keywords repeat title/bullet words (wasted bytes): {', '.join(dup_front[:8])}")
        if dup_self:
            warns.append(f"backend keywords repeated within field: {', '.join(dup_self[:6])}")
        if re.search(r"\b[A-Z0-9]{10}\b", b):
            fails.append("backend keywords contain an ASIN-like token — not allowed")

    # ── tags (Etsy) ──
    if tags or lim.get("tags_max"):
        clean = [str(t).strip() for t in tags]
        fields["tags"] = {"count": len(clean), "max": lim.get("tags_max"), "over_length": [t for t in clean if lim.get("tag_chars_max") and len(t) > lim["tag_chars_max"]]}
        if lim.get("tags_max"):
            if len(clean) > lim["tags_max"]:
                fails.append(f"{len(clean)} tags > {lim['tags_max']} max")
            elif len(clean) < lim["tags_max"]:
                warns.append(f"only {len(clean)} of {lim['tags_max']} tags used — every empty tag is lost search traffic")
        for t in fields["tags"]["over_length"]:
            fails.append(f"tag “{t}” is {len(t)} chars > {lim['tag_chars_max']}")
        dups = [t for t, c in Counter(t.lower() for t in clean).items() if c > 1]
        if dups:
            fails.append(f"duplicate tags: {', '.join(dups)}")
        single = [t for t in clean if len(text.words(t)) == 1]
        if len(single) > len(clean) / 2 and clean:
            warns.append("most tags are single words — multi-word phrases match how buyers search")

    # ── Shopify SEO fields ──
    if seo_title:
        fields["seo_title"] = {"chars": len(seo_title), "max": lim.get("seo_title_max", 70), "recommended": lim.get("seo_title_recommended", 60)}
        if len(seo_title) > fields["seo_title"]["max"]:
            fails.append(f"SEO title {len(seo_title)} chars > {fields['seo_title']['max']}")
        elif len(seo_title) > fields["seo_title"]["recommended"]:
            warns.append(f"SEO title {len(seo_title)} chars — Google shows ~{fields['seo_title']['recommended']}")
    if meta_description:
        fields["meta_description"] = {"chars": len(meta_description), "max": lim.get("meta_description_max", 320), "recommended": lim.get("meta_description_recommended", 155)}
        if len(meta_description) > fields["meta_description"]["max"]:
            fails.append(f"meta description {len(meta_description)} chars > {fields['meta_description']['max']}")
        elif len(meta_description) > fields["meta_description"]["recommended"]:
            warns.append(f"meta description {len(meta_description)} chars — Google truncates ~{fields['meta_description']['recommended']}")

    claims = sorted({c.lower() for c in CLAIM_RE.findall(" ".join([title, description] + bullets)) if isinstance(c, str)} | {m.group(0).lower() for m in CLAIM_RE.finditer(" ".join([title, description] + bullets))})
    return {
        "marketplace": mp,
        "limits_used": lim,
        "fields": fields,
        "fails": fails,
        "warnings": warns,
        "claims_to_verify": claims,
        "passes": not fails,
        "verdict": ("PASS" if not fails else f"FAIL — {len(fails)} violation(s)") + f", {len(warns)} warning(s)" + (f"; verify claims: {', '.join(claims)}" if claims else "") + ". Limits are a snapshot — verify against current platform docs.",
    }


@AGENT.tool
def keyword_coverage(keywords: list[str], title: str, bullets: list[str] | None = None, description: str = "", backend_keywords: str = "", tags: list[str] | None = None) -> dict:
    """Map each target keyword to where it appears (title, bullets, description, backend, tags), find missing and partially covered ones, wasted backend duplicates and stuffing.

    Args:
        keywords: Target search terms/phrases, primary first (≤ 40).
        title: Product title.
        bullets: Bullet points.
        description: Description text.
        backend_keywords: Amazon backend search terms.
        tags: Etsy tags.
    """
    kws = [str(k).strip() for k in keywords if str(k).strip()]
    if not kws:
        raise ToolError("keywords is empty.")
    if len(kws) > 40:
        raise ToolError("Max 40 keywords per call.")
    if not title.strip():
        raise ToolError("title is empty.")
    fields = {"title": title, "bullets": " \n ".join(bullets or []), "description": description, "backend": backend_keywords, "tags": " \n ".join(tags or [])}
    if any(len(v) > 200_000 for v in fields.values()):
        raise ToolError("A field is absurdly long (200k chars max).")
    lows = {k: v.lower() for k, v in fields.items()}
    words_by_field = {k: {w.lower() for w in text.words(v)} for k, v in fields.items()}
    weights = {"title": 3, "bullets": 2, "description": 1, "backend": 1, "tags": 2}
    rows, score, max_score = [], 0.0, 0.0
    for i, kw in enumerate(kws):
        kl = kw.lower()
        kwords = [w.lower() for w in text.words(kw)]
        exact = [f for f, v in lows.items() if v and re.search(r"(?<!\w)" + re.escape(kl) + r"(?!\w)", v)]
        partial = [f for f, ws in words_by_field.items() if f not in exact and kwords and all(w in ws for w in kwords)]
        weight = 3 if i == 0 else (2 if i <= 4 else 1)
        max_score += weight
        if exact:
            score += weight
        elif partial:
            score += weight * 0.5
        title_pos = lows["title"].find(kl) if "title" in exact else None
        status = "exact" if exact else ("partial (all words present, not the phrase)" if partial else "MISSING")
        suggestion = None
        if not exact:
            if "title" not in exact and i == 0:
                suggestion = "put the exact phrase in the title, within the first 60 chars"
            elif not description:
                suggestion = "add to description"
            elif backend_keywords == "" and tags is None:
                suggestion = "add to a bullet as a natural phrase"
            else:
                suggestion = "add to backend keywords / tags (words not already in the title)"
        rows.append(
            {
                "keyword": kw,
                "priority": "primary" if i == 0 else ("secondary" if i <= 4 else "long-tail"),
                "exact_in": exact,
                "partial_in": partial,
                "title_char_position": title_pos,
                "status": status,
                "suggestion": suggestion,
                "occurrences_in_description": text.keyword_density(description, kw)["occurrences"] if description else 0,
            }
        )
    coverage = score / max_score if max_score else 0.0
    primary = rows[0]
    stuffing = []
    if description:
        for r in rows:
            d = text.keyword_density(description, r["keyword"])
            if d["density_pct"] > 3.0 and d["occurrences"] >= 3:
                stuffing.append(f"“{r['keyword']}” {d['occurrences']}× = {d['density_pct']}% of description (> 3%)")
    backend_waste = sorted({w for w in words_by_field["backend"] if len(w) > 2 and (w in words_by_field["title"] or w in words_by_field["bullets"])})
    missing = [r["keyword"] for r in rows if r["status"] == "MISSING"]
    warnings = list(stuffing)
    if primary["status"] != "exact" or "title" not in primary["exact_in"]:
        warnings.append("primary keyword is not an exact phrase in the title")
    elif primary["title_char_position"] is not None and primary["title_char_position"] > 60:
        warnings.append(f"primary keyword starts at char {primary['title_char_position']} — after the mobile cut (~60-80)")
    if backend_waste:
        warnings.append(f"backend words already in title/bullets (wasted bytes): {', '.join(backend_waste[:10])}")
    return {
        "coverage_pct": pct(coverage),
        "keywords": rows,
        "missing": missing,
        "partial": [r["keyword"] for r in rows if r["status"].startswith("partial")],
        "backend_wasted_words": backend_waste,
        "warnings": warnings,
        "verdict": f"Coverage {100 * coverage:.0f}% (weighted). {len(missing)} missing, {len([r for r in rows if r['status'].startswith('partial')])} partial. " + ("Primary keyword in title at char " + str(primary["title_char_position"]) + "." if primary["title_char_position"] is not None else "Primary keyword NOT in the title as a phrase."),
    }


@AGENT.tool
def score_title(title: str, marketplace: str, primary_keyword: str, brand: str = "", attributes: list[str] | None = None) -> dict:
    """Score a product title 0-100 for the marketplace formula: brand placement, primary keyword position vs mobile truncation, attribute coverage, length, banned words, repeats and case.

    Args:
        title: The title to score.
        marketplace: amazon, etsy, shopify, ebay, walmart or google_shopping.
        primary_keyword: The main search phrase the title must contain.
        brand: Brand name ("" if unbranded/generic).
        attributes: Key attributes the buyer searches by (e.g. ["32 oz", "stainless steel", "leak proof"]).
    """
    mp = marketplace.lower().strip()
    if mp not in LIMITS:
        raise ToolError(f"marketplace must be one of {', '.join(LIMITS)}.")
    if not title.strip():
        raise ToolError("title is empty.")
    if not primary_keyword.strip():
        raise ToolError("primary_keyword is empty.")
    if len(title) > 5000:
        raise ToolError("title too long to be a title.")
    lim = LIMITS[mp]
    low = title.lower()
    score, checks, fixes = 100, {}, []
    n = len(title)
    mobile = lim.get("title_mobile", 70)
    # primary keyword
    pos = low.find(primary_keyword.lower().strip())
    checks["primary_keyword_present"] = pos >= 0
    checks["primary_keyword_char_position"] = pos if pos >= 0 else None
    if pos < 0:
        score -= 30
        fixes.append(f"add the exact phrase “{primary_keyword}”")
    elif pos + len(primary_keyword) > mobile:
        score -= 12
        fixes.append(f"move “{primary_keyword}” into the first {mobile} chars (mobile cut)")
    # brand
    if brand.strip():
        bpos = low.find(brand.lower().strip())
        checks["brand_present"] = bpos >= 0
        checks["brand_first"] = bpos == 0
        if bpos < 0:
            score -= 10
            fixes.append("include the brand" + (" first" if mp in ("amazon", "walmart") else ""))
        elif mp in ("amazon", "walmart") and bpos != 0:
            score -= 5
            fixes.append("Amazon/Walmart convention: brand first")
    # attributes
    attrs = [a for a in (attributes or []) if str(a).strip()]
    hit = [a for a in attrs if str(a).lower() in low]
    checks["attributes_covered"] = f"{len(hit)}/{len(attrs)}"
    if attrs:
        miss = [a for a in attrs if a not in hit]
        pen = round(20 * len(miss) / len(attrs))
        score -= pen
        if miss:
            fixes.append(f"add attributes: {', '.join(str(m) for m in miss[:5])}")
    # length
    checks["chars"] = n
    if n > lim["title_max"]:
        score -= 25
        fixes.append(f"over {lim['title_max']} chars — will be rejected/truncated")
    elif lim.get("title_recommended") and n > lim["title_recommended"]:
        score -= 8
        fixes.append(f"over the {lim['title_recommended']}-char recommendation")
    elif n < 40 and mp != "ebay":
        score -= 8
        fixes.append("under 40 chars — add attributes/use case")
    # banned / style
    promo = sorted({m.group(0).lower() for m in PROMO_RE.finditer(title)})
    if promo:
        score -= 10 * min(len(promo), 3)
        fixes.append(f"remove promo/subjective words: {', '.join(promo)}")
    caps = _caps_words(title)
    if caps:
        score -= 8
        fixes.append(f"no ALL CAPS ({', '.join(caps[:3])}) — Title Case")
    special = sorted({c for c in title if c in lim.get("title_special_chars", "")})
    if special:
        score -= 10
        fixes.append(f"remove characters {' '.join(special)}")
    counts = Counter(w.lower() for w in text.words(title) if len(w) > 2 and w.lower() not in text.STOPWORDS)
    reps = [w for w, c in counts.items() if c > lim.get("title_word_repeat_max", 3)]
    if reps:
        score -= 12
        fixes.append(f"word repeated too often: {', '.join(reps)}")
    if re.search(r"\b(\w+)\s+\1\b", low):
        score -= 5
        fixes.append("adjacent duplicate word")
    if len(text.words(title)) >= 4 and sum(1 for w in text.words(title) if w[:1].isupper() or w[:1].isdigit()) / len(text.words(title)) < 0.5:
        score -= 4
        fixes.append("use Title Case (capitalise main words)")
    # keyword-list smell: many separators and no connecting words
    if len(re.findall(r"[|,/•]", title)) >= 4 or (len(text.words(title)) >= 8 and not any(w.lower() in ("for", "with", "and") for w in text.words(title))):
        score -= 6
        fixes.append("reads like a keyword list — add 'for', 'with' to make a phrase")
    score = max(0, min(100, score))
    return {
        "score": score,
        "chars": n,
        "mobile_visible": title[:mobile],
        "checks": checks,
        "fixes": fixes,
        "formula": {"amazon": "Brand + Product type + Key attributes + Size/Qty + Use case", "walmart": "Brand + Product + Attributes + Size", "etsy": "Keyword phrase first + material/occasion, readable", "ebay": "Every word a search term, 80 chars, brand + item + specifics", "shopify": "Product + key attribute, ≤ 70 for SEO", "google_shopping": "Brand + Product + Attributes, front-load 70"}[mp],
        "verdict": f"{score}/100" + (" — ship it." if score >= 85 else f" — {len(fixes)} fix(es): " + "; ".join(fixes[:3])),
    }


LEAD_IN_RE = re.compile(r"^\s*(?:[A-Z][A-Z0-9 &'\-]{3,40}[:\-–—]|[A-Z][\w'\-]+(?: [A-Z][\w'\-]+){0,4}\s*[:\-–—])\s+\S")
BENEFIT_RE = re.compile(r"\b(you|your|yours|keeps?|saves?|protects?|prevents?|fits?|lasts?|easy|easily|no more|never|without|so you|enjoy|stay|stays|feel|feels|makes|lets|helps?|ready|comfort\w*)\b", re.I)
SPEC_RE = re.compile(r"\d+(\.\d+)?\s?(oz|ml|l|lb|lbs|kg|g|mm|cm|in|inch|inches|ft|hours?|hrs|h|days?|x|%|w|v|mah|\"|”|°)|\b\d{2,}\b", re.I)


@AGENT.tool
def bullet_lint(bullets: list[str], description: str = "", marketplace: str = "amazon") -> dict:
    """Lint bullet points (and optionally the description) for benefit-first lead-ins, proof/specs, length, duplicates, promo words, reading grade and scannability.

    Args:
        bullets: The bullet points / key features.
        description: Optional description to check for paragraph length, sentence length, passive voice and reading grade.
        marketplace: amazon (default), walmart, shopify, etsy, ebay or google_shopping — sets length conventions.
    """
    if not bullets or not any(str(b).strip() for b in bullets):
        raise ToolError("bullets is empty.")
    if len(bullets) > 20:
        raise ToolError("Max 20 bullets.")
    mp = marketplace.lower().strip()
    if mp not in LIMITS:
        raise ToolError(f"marketplace must be one of {', '.join(LIMITS)}.")
    max_chars = LIMITS[mp].get("bullet_chars_max", 255)
    rows, keys = [], []
    total = 0
    for i, b in enumerate(bullets, 1):
        b = str(b).strip()
        if len(b) > 5000:
            raise ToolError(f"bullet {i} too long (5k chars).")
        issues, s = [], 100
        n = len(b)
        if n > max_chars:
            issues.append(f"{n} chars > {max_chars}")
            s -= 20
        elif n > 200:
            issues.append(f"{n} chars — long for a skim; aim 120-200")
            s -= 5
        elif n < 60 and n > 0:
            issues.append(f"{n} chars — too thin; add the proof/spec")
            s -= 10
        lead = bool(LEAD_IN_RE.match(b))
        if not lead:
            issues.append("no benefit lead-in (e.g. “KEEPS DRINKS COLD 24H: …”)")
            s -= 15
        if not BENEFIT_RE.search(b):
            issues.append("feature-only — say what it does for the buyer (“so you…”)")
            s -= 15
        if not SPEC_RE.search(b):
            issues.append("no number/spec as proof")
            s -= 10
        pm = PROMO_RE.search(b)
        if pm:
            issues.append(f"promo/subjective word “{pm.group(0)}”")
            s -= 10
        if len(_caps_words(b)) > 6:
            issues.append("too much ALL CAPS beyond the lead-in")
            s -= 5
        if HTML_RE.search(b):
            issues.append("HTML in bullet")
            s -= 10
        if mp == "amazon" and b.endswith((".", "!")):
            issues.append("style: Amazon bullets conventionally have no closing punctuation")
        sents = text.sentences(b)
        if len(sents) > 3:
            issues.append(f"{len(sents)} sentences — one idea per bullet")
            s -= 5
        key = frozenset(w.lower() for w in text.words(b) if w.lower() not in text.STOPWORDS and len(w) > 2)
        dup = next((j for j, k in keys if key and len(key & k) / max(1, len(key | k)) >= 0.5), None)
        if dup:
            issues.append(f"overlaps heavily with bullet {dup}")
            s -= 10
        keys.append((i, key))
        total += max(0, s)
        rows.append({"n": i, "chars": n, "has_lead_in": lead, "score": max(0, s), "issues": issues})
    out: dict = {"bullets": rows, "bullets_score": round(total / len(rows)), "order_note": "bullet 1 = #1 benefit, 2 = proof/spec, 3 = fit/compatibility, 4 = what's in the box/use, 5 = care/guarantee-free assurance"}
    if description.strip():
        if len(description) > 200_000:
            raise ToolError("description too long (200k chars max).")
        rd = text.readability(description)
        paras = [p for p in re.split(r"\n\s*\n|\n", description) if p.strip()]
        long_paras = [len(text.words(p)) for p in paras if len(text.words(p)) > 80]
        long_sents = [s for s in text.sentences(description) if len(text.words(s)) > 25]
        passive = text.passive_sentences(description)
        d_issues = []
        if rd["fk_grade"] and rd["fk_grade"] > 8:
            d_issues.append(f"reading grade {rd['fk_grade']} > 8 — shorter sentences, plainer words")
        if long_paras:
            d_issues.append(f"{len(long_paras)} paragraph(s) over 80 words — break into H2/H3 sections or bullets")
        if long_sents:
            d_issues.append(f"{len(long_sents)} sentence(s) over 25 words")
        if passive:
            d_issues.append(f"{len(passive)} passive sentence(s)")
        promo_d = sorted({m.group(0).lower() for m in PROMO_RE.finditer(description)})
        if promo_d:
            d_issues.append(f"promo/subjective words: {', '.join(promo_d[:5])}")
        if not SPEC_RE.search(description):
            d_issues.append("no numbers/specs in the description — add dimensions, capacity, materials, what's included")
        out["description"] = {"chars": len(description), "words": rd["words"], "fk_grade": rd["fk_grade"], "paragraphs": len(paras), "issues": d_issues, "score": max(0, 100 - 12 * len(d_issues))}
    out["verdict"] = f"Bullets {out['bullets_score']}/100" + (f"; description {out['description']['score']}/100" if "description" in out else "") + ". " + ("Ship it." if out["bullets_score"] >= 85 and out.get("description", {}).get("score", 100) >= 85 else "Fix the flagged bullets first.")
    return out
