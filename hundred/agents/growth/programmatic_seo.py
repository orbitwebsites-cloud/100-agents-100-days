"""Programmatic SEO — plan, generate and quality-gate templated page sets without shipping thin duplicates."""

from __future__ import annotations

import itertools
import math
import re
from collections import Counter

from ...core import Agent, ToolError
from ...lib import text as _text
from . import _common as c

AGENT = Agent(
    slug="programmatic-seo",
    name="Programmatic SEO",
    category="growth",
    tagline="Plan and QA templated page sets — page counts, clean slugs, duplicate detection and a crawlable link architecture.",
    description=(
        "Does the engineering-adjacent work of programmatic SEO: computes how many pages a set of dimensions "
        "produces and previews their titles and URLs, generates collision-free slugs, measures near-duplicate "
        "and boilerplate ratios across generated pages before Google does, and designs the hub/spoke internal "
        "linking and sitemap structure that gets thousands of pages crawled and indexed — plus the go/no-go "
        "rules that separate pSEO that ranks from pSEO that gets flagged as spam."
    ),
    triggers=[
        "plan a programmatic SEO project / templated pages",
        "how many pages would these dimensions create",
        "generate URL slugs for these pages",
        "are these generated pages too similar / duplicate content check",
        "internal linking and sitemap structure for thousands of pages",
    ],
    examples=[
        "We want '[tool] for [industry] in [city]' pages: 12 tools, 20 industries, 50 cities. Is that sane? Show me sample titles and URLs.",
        "Here are 30 generated city pages — check whether they're too similar to each other.",
        "Slugify these 200 product names and flag any collisions or ugly ones.",
    ],
    connectors=["Google Search Console", "Google Sheets", "Airtable", "Webflow", "WordPress", "GitHub"],
    playbook="""
    ## Standard
    You are the programmatic SEO lead who has shipped page sets from 500 to 500,000 URLs and
    has also cleaned up the ones that got hit by helpful-content and scaled-content policies.
    The one metric: indexed pages that earn impressions per page shipped. Excellent output is
    a plan where every page has a real reason to exist (a distinct query with demand and
    distinct data on the page), the URL and title patterns are fixed before generation, and
    the duplicate/boilerplate ratio is measured, not assumed.

    ## Intake
    Need: the dimensions (lists of values), the template idea (title/URL), and what unique
    data each page will show. Nice to have: search demand per dimension value, the site's
    authority, and sample generated pages for QA. Ask at most 2 questions — the critical one
    is "what on the page is different between two sibling URLs besides the swapped words?"
    If the answer is nothing, say the project should not ship as designed.

    ## Procedure
    1. **Size the set.** Call `programmatic_seo__plan_combinations` with the dimensions and
       the title/URL templates. It returns the page count, per-dimension multipliers, sample
       titles/slugs, duplicate values, template placeholder errors, and tier warnings
       (≥ 10k pages: sitemap chunking and crawl budget; ≥ 100k: phased rollout mandatory).
       Prune dimension values with no demand before anything else — a 50-city list is
       usually 15 cities of demand.
    2. **Fix the URL pattern.** Call `programmatic_seo__slugify_batch` on the value lists or
       final page names. It produces ASCII, hyphenated, length-capped slugs and reports
       collisions (two names → one slug), stopword-only slugs and over-long ones. Never
       ship two pages on one slug; add a disambiguator from another dimension.
    3. **Quality-gate the content.** With a sample of generated pages (≥ 10), call
       `programmatic_seo__near_duplicates`. It computes shingle similarity between pages,
       the boilerplate ratio (text shared by most pages), each page's unique-content share,
       and clusters of near-duplicates. Gate: median unique share ≥ 40% and no pair ≥ 0.8
       similarity; otherwise add per-page data (tables, stats, local specifics, reviews) or
       cut pages.
    4. **Design crawlability.** Call `programmatic_seo__linking_architecture` with the page
       count. It returns the hub depth needed at a given fan-out, the number of sitemaps,
       and a rollout schedule (batches per week). Every page must be ≤ 3 clicks from the
       homepage and have ≥ 3 inbound internal links from related pages (siblings + hub).
    5. **Write the spec:** dimensions kept/cut with reasons, URL and title patterns, the
       unique-data block list per page, hub pages, sitemap plan, rollout phases with
       success gates (index rate ≥ 60% and impressions on ≥ 30% of the batch before the
       next batch), and the kill criteria.
    6. **Self-check:** no pair of pages targets the same query; every page has ≥ 2 unique
       data elements; slugs collision-free; rollout phased; a noindex rule for pages with
       no data.

    ## Frameworks
    - **Demand × data test:** a dimension value earns a page only if (a) people search for
      that combination and (b) you have data specific to it. One of the two → fold it into a
      parent page or a filter.
    - **Unique-content share** = words not in the boilerplate ÷ total words. ≥ 50% strong,
      40-50% acceptable with rich structured data, < 30% is thin at scale.
    - **Title pattern:** `<Dimension A> <Head term> in <Dimension B> (<Year>)` — keep the
      query-shaped part first; 50-60 chars.
    - **Rollout:** phase 1 = 5-10% of pages with the best demand; measure index rate at 2
      and 4 weeks in Search Console; expand only if ≥ 60% indexed and impressions arrive.
    - **Sitemaps:** ≤ 50,000 URLs and ≤ 50MB uncompressed each, a sitemap index above them,
      `lastmod` accurate. Hub pages: fan-out 50-150 links per hub page.
    - **Kill criteria:** pages with zero impressions after 90 days → consolidate or noindex;
      index rate < 30% after phase 1 → stop and add data.

    ## Output format
    ```
    # Programmatic SEO plan — <project>
    **Pages:** N (from dims A × B × C) → **recommended:** M after pruning · **rollout:** k phases

    ## Dimensions
    | Dimension | Values (kept/total) | Why cut |
    |---|---|---|

    ## Patterns
    URL: /<pattern>/ · Title: <pattern> · H1: <pattern> · Description: <pattern>
    Sample: <3 title + URL pairs>

    ## Unique data per page (the anti-thin block)
    - <data element> — source: … · present on 100% / N% of pages

    ## QA gates (from tools)
    Boilerplate ratio …% · median unique share …% · near-duplicate pairs … · slug collisions …

    ## Architecture
    Hubs: … · depth … · sitemaps … · inbound links per page ≥ 3 (siblings + hub)

    ## Rollout & kill criteria
    Phase 1 (N pages, week …) → gate … → Phase 2 …
    ```

    ## Anti-patterns
    - Multiplying every dimension because you can. 12 × 20 × 50 = 12,000 pages of nothing.
    - Spinning the intro paragraph with synonyms and calling it unique content.
    - Publishing 50k URLs in one day on a site with 300 pages of history — crawl budget and
      trust do not scale that way.
    - Titles that are the template with words swapped and no query-shaped phrase.
    - No noindex rule for combinations with empty data ("Plumbers in Nome, AK: 0 results").
    - Skipping the sample QA because "the template is fine". Measure similarity on real output.
    """,
)

MAX_PAGES_PREVIEW = 40
PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


@AGENT.tool
def plan_combinations(dimensions: dict[str, list[str]], title_template: str = "", url_template: str = "", sample: int = 12) -> dict:
    """Count the pages a set of dimensions produces, validate the title/URL templates, and preview sample titles and slugs.

    Templates use {dimension_name} placeholders. Reports the multiplier per dimension, duplicate or empty
    values, placeholder mismatches, and scale-tier warnings for sitemaps, crawl budget and rollout.

    Args:
        dimensions: {"city": ["Austin", "Boston"], "service": ["plumber", "electrician"]} — 1-6 dimensions, up to 5000 values each.
        title_template: e.g. "Best {service} in {city} (2026)" — optional.
        url_template: e.g. "/{service}/{city}/" — optional; slugified per value.
        sample: How many sample pages to preview (1-40), spread evenly across the set.
    """
    if not dimensions:
        raise ToolError("dimensions is empty.")
    if len(dimensions) > 6:
        raise ToolError("Max 6 dimensions — more than that never has demand for every combination.")
    n_sample = int(sample)
    if not 1 <= n_sample <= MAX_PAGES_PREVIEW:
        raise ToolError(f"sample must be 1-{MAX_PAGES_PREVIEW}.")
    dims: dict[str, list[str]] = {}
    warnings: list[str] = []
    for name, vals in dimensions.items():
        if not isinstance(vals, list) or not vals:
            raise ToolError(f"Dimension {name!r} must be a non-empty list of values.")
        if len(vals) > 5000:
            raise ToolError(f"Dimension {name!r} has {len(vals)} values (max 5000).")
        cleaned = [str(v).strip() for v in vals]
        empties = sum(1 for v in cleaned if not v)
        if empties:
            warnings.append(f"{name}: {empties} empty value(s) removed.")
        cleaned = [v for v in cleaned if v]
        dupes = [v for v, n in Counter(x.lower() for x in cleaned).items() if n > 1]
        if dupes:
            warnings.append(f"{name}: duplicate values {dupes[:5]} — deduplicated.")
        seen = set()
        uniq = []
        for v in cleaned:
            if v.lower() not in seen:
                seen.add(v.lower())
                uniq.append(v)
        if not uniq:
            raise ToolError(f"Dimension {name!r} has no usable values.")
        dims[name] = uniq
    total = math.prod(len(v) for v in dims.values())
    per_dim = {k: len(v) for k, v in dims.items()}
    # template checks
    tpl_issues = []
    for label, tpl in (("title_template", title_template), ("url_template", url_template)):
        if not tpl:
            continue
        used = set(PLACEHOLDER.findall(tpl))
        unknown = used - set(dims)
        unused = set(dims) - used
        if unknown:
            tpl_issues.append(f"{label}: unknown placeholder(s) {sorted(unknown)} — dimensions are {sorted(dims)}.")
        if unused:
            tpl_issues.append(f"{label}: dimension(s) {sorted(unused)} not used — pages differing only in {sorted(unused)} will share the same {label.split('_')[0]}.")
    # samples spread across the space
    combos = list(itertools.product(*[[(k, v) for v in vals] for k, vals in dims.items()])) if total <= 200_000 else None
    samples = []
    if combos is not None:
        step = max(1, len(combos) // n_sample)
        picked = combos[::step][:n_sample]
    else:
        picked = [tuple((k, dims[k][(i * 7919) % len(dims[k])]) for k in dims) for i in range(n_sample)]
    slug_seen: dict[str, int] = {}
    for combo in picked:
        d = dict(combo)
        title = PLACEHOLDER.sub(lambda m: d.get(m.group(1), m.group(0)), title_template) if title_template else " ".join(d.values())
        if url_template:
            url = PLACEHOLDER.sub(lambda m: c.slugify(d.get(m.group(1), m.group(0))), url_template)
        else:
            url = "/" + "/".join(c.slugify(v) for v in d.values()) + "/"
        slug_seen[url] = slug_seen.get(url, 0) + 1
        samples.append({"values": d, "title": title, "title_px": c.text_width(title, 20), "url": url})
    title_over = sum(1 for s in samples if s["title_px"] > 600)
    if title_over:
        warnings.append(f"{title_over}/{len(samples)} sample titles exceed 600px — shorten the template.")
    if any(n > 1 for n in slug_seen.values()):
        warnings.append("URL template produces the same URL for different pages — include every dimension in the URL.")
    # scale tiers
    if total >= 100_000:
        tier = "very large"
        warnings.append(f"{total:,} pages: phased rollout is mandatory (start with ≤ 5%), {math.ceil(total / 50000)} sitemaps, expect index rate well under 50% without strong authority.")
    elif total >= 10_000:
        tier = "large"
        warnings.append(f"{total:,} pages: chunk sitemaps ({math.ceil(total / 50000)}), build hub pages, roll out in ≥ 3 phases.")
    elif total >= 1_000:
        tier = "medium"
    else:
        tier = "small"
    biggest = max(per_dim, key=per_dim.get)
    return {
        "total_pages": total,
        "per_dimension": per_dim,
        "tier": tier,
        "biggest_multiplier": biggest,
        "pages_if_halving": {k: total // 2 for k in [biggest]},
        "template_issues": tpl_issues,
        "warnings": warnings,
        "samples": samples,
        "sitemaps_needed": math.ceil(total / 50000),
        "verdict": (
            f"{total:,} pages ({' × '.join(f'{k} {n}' for k, n in per_dim.items())}). "
            + ("Template errors to fix first. " if tpl_issues else "")
            + f"Prune '{biggest}' to values with demand first — it is the biggest multiplier."
        ),
    }


@AGENT.tool
def slugify_batch(items: list[str], max_length: int = 60, drop_stopwords: bool = False) -> dict:
    """Turn page names into clean URL slugs (ASCII, lowercase, hyphenated, length-capped) and report collisions and problems.

    Args:
        items: Page names or dimension values to slugify (1-5000).
        max_length: Maximum slug length in characters (20-120); cut at a word boundary.
        drop_stopwords: Remove a/an/the/of/and/… from slugs (shorter URLs, slightly less readable).
    """
    if not items:
        raise ToolError("items is empty.")
    if len(items) > 5000:
        raise ToolError("Max 5000 items per call.")
    ml = int(max_length)
    if not 20 <= ml <= 120:
        raise ToolError("max_length must be 20-120.")
    rows = []
    by_slug: dict[str, list[str]] = {}
    problems = []
    for raw in items:
        name = str(raw).strip()
        slug = c.slugify(name, ml, drop_stopwords)
        issues = []
        if not slug:
            issues.append("empty slug (no alphanumerics)")
        else:
            if len(c.slugify(name, 1000, drop_stopwords)) > ml:
                issues.append(f"truncated to {len(slug)} chars")
            if re.fullmatch(r"\d+", slug):
                issues.append("digits only — add a word")
            if len(slug) < 3:
                issues.append("very short")
            if slug.count("-") >= 8:
                issues.append("9+ words — consider shortening")
            if re.search(r"[^\x00-\x7f]", name):
                issues.append("transliterated non-ASCII")
        rows.append({"input": name, "slug": slug, "issues": issues})
        by_slug.setdefault(slug, []).append(name)
        if issues:
            problems.append({"input": name, "slug": slug, "issues": issues})
    collisions = [{"slug": s, "inputs": names} for s, names in by_slug.items() if len(names) > 1 and s]
    for col in collisions:
        for r in rows:
            if r["slug"] == col["slug"]:
                r["issues"].append(f"collides with {len(col['inputs']) - 1} other(s)")
    return {
        "slugs": rows,
        "collisions": collisions,
        "problems": problems,
        "counts": {"items": len(rows), "unique_slugs": len([s for s in by_slug if s]), "collisions": len(collisions), "with_issues": len(problems)},
        "verdict": ("All slugs unique and clean." if not collisions and not problems else f"{len(collisions)} collision group(s), {len(problems)} slug(s) with issues — resolve collisions with a disambiguating dimension."),
    }


@AGENT.tool
def near_duplicates(pages: list[dict], similarity_threshold: float = 0.8, shingle_size: int = 3) -> dict:
    """Measure how similar generated pages are: pairwise shingle similarity, boilerplate ratio, per-page unique-content share and duplicate clusters.

    Boilerplate = word shingles present on ≥ 50% of pages. Unique share = a page's shingles not in the
    boilerplate ÷ its shingles. Gate: median unique share ≥ 40% and no pair ≥ threshold.

    Args:
        pages: List of {"id": str, "text": str} — 2-300 pages of visible body text (strip nav/footer if you can).
        similarity_threshold: Jaccard similarity at which two pages count as near-duplicates (0.5-0.95).
        shingle_size: Words per shingle (2-5; 3 is standard).
    """
    if not pages or len(pages) < 2:
        raise ToolError("Give at least 2 pages.")
    if len(pages) > 300:
        raise ToolError("Max 300 pages per call — sample them.")
    thr = float(similarity_threshold)
    if not 0.5 <= thr <= 0.95:
        raise ToolError("similarity_threshold must be 0.5-0.95.")
    n = int(shingle_size)
    if not 2 <= n <= 5:
        raise ToolError("shingle_size must be 2-5.")
    docs = []
    for i, p in enumerate(pages):
        pid = str(p.get("id") or f"page {i + 1}")
        txt = str(p.get("text") or "")
        if len(txt) > 200_000:
            raise ToolError(f"{pid}: text over 200k chars.")
        sh = c.shingles(txt, n)
        if not sh:
            raise ToolError(f"{pid}: no text.")
        docs.append((pid, sh, len(_text.words(txt))))
    freq: Counter = Counter()
    for _, sh, _ in docs:
        freq.update(sh)
    half = max(2, len(docs) / 2)
    boiler = {s for s, k in freq.items() if k >= half}
    total_shingles = sum(len(sh) for _, sh, _ in docs)
    boiler_hits = sum(1 for _, sh, _ in docs for s in sh if s in boiler)
    per_page = []
    for pid, sh, wc in docs:
        uniq = len(sh - boiler) / len(sh)
        per_page.append({"id": pid, "words": wc, "unique_share": round(uniq, 3), "thin": wc < 300 or uniq < 0.3})
    shares = sorted(p["unique_share"] for p in per_page)
    median = shares[len(shares) // 2] if len(shares) % 2 else (shares[len(shares) // 2 - 1] + shares[len(shares) // 2]) / 2
    pairs = []
    parent = list(range(len(docs)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    sims = []
    for a in range(len(docs)):
        for b in range(a + 1, len(docs)):
            s = c.jaccard(docs[a][1], docs[b][1])
            sims.append(s)
            if s >= thr:
                pairs.append({"a": docs[a][0], "b": docs[b][0], "similarity": round(s, 3)})
                parent[find(a)] = find(b)
    clusters: dict[int, list[str]] = {}
    for i in range(len(docs)):
        clusters.setdefault(find(i), []).append(docs[i][0])
    dup_clusters = [v for v in clusters.values() if len(v) > 1]
    pairs.sort(key=lambda p: -p["similarity"])
    avg_sim = round(sum(sims) / len(sims), 3) if sims else 0.0
    boiler_ratio = round(boiler_hits / total_shingles, 3) if total_shingles else 0.0
    passes = median >= 0.4 and not pairs
    return {
        "pages": len(docs),
        "boilerplate_ratio": boiler_ratio,
        "median_unique_share": round(median, 3),
        "avg_pairwise_similarity": avg_sim,
        "near_duplicate_pairs": pairs[:200],
        "duplicate_clusters": dup_clusters,
        "per_page": per_page,
        "thin_pages": [p["id"] for p in per_page if p["thin"]],
        "passes_gate": passes,
        "verdict": (
            ("PASS: " if passes else "FAIL: ")
            + f"boilerplate {boiler_ratio:.0%}, median unique share {median:.0%}, {len(pairs)} pair(s) ≥ {thr} similarity in {len(dup_clusters)} cluster(s), {sum(1 for p in per_page if p['thin'])} thin page(s). "
            + ("Ship the sample pattern." if passes else "Add page-specific data (tables, local stats, reviews) or cut pages before publishing.")
        ),
    }


@AGENT.tool
def linking_architecture(page_count: int, links_per_hub: int = 100, existing_authority_pages: int = 1, rollout_weeks: int = 8, first_phase_pct: float = 10) -> dict:
    """Design the hub/spoke structure, sitemap plan and phased rollout for a page set: hub pages per level, click depth, sitemap count, batch sizes.

    Args:
        page_count: Number of programmatic pages to publish (1-5,000,000).
        links_per_hub: Links each hub page carries to child pages/hubs (20-300; 50-150 is the sweet spot).
        existing_authority_pages: Strong existing pages (homepage, category pages) that can link to top-level hubs.
        rollout_weeks: Weeks over which to publish after phase 1 (1-52).
        first_phase_pct: Share of pages in phase 1 (1-50), chosen from the highest-demand values.
    """
    n = int(page_count)
    if not 1 <= n <= 5_000_000:
        raise ToolError("page_count must be 1-5,000,000.")
    fan = int(links_per_hub)
    if not 20 <= fan <= 300:
        raise ToolError("links_per_hub must be 20-300.")
    auth = max(1, int(existing_authority_pages))
    weeks = int(rollout_weeks)
    if not 1 <= weeks <= 52:
        raise ToolError("rollout_weeks must be 1-52.")
    p1 = float(first_phase_pct)
    if not 1 <= p1 <= 50:
        raise ToolError("first_phase_pct must be 1-50.")
    # hub levels: leaf hubs each link `fan` pages; hubs of hubs until <= auth*fan top hubs
    levels = []
    remaining = n
    depth = 1  # leaf pages are 1 click below their hub
    while remaining > auth * fan:
        hubs = math.ceil(remaining / fan)
        levels.append(hubs)
        remaining = hubs
        depth += 1
    click_depth_from_home = depth + (1 if levels else 1)  # home → hub(s) → … → page
    total_hubs = sum(levels)
    sitemaps = math.ceil(n / 50000)
    phase1 = math.ceil(n * p1 / 100)
    rest = n - phase1
    per_week = math.ceil(rest / weeks) if rest else 0
    inbound_min = 3
    sibling_links = max(0, inbound_min - 1)
    return {
        "page_count": n,
        "links_per_hub": fan,
        "hub_levels": levels,
        "total_hub_pages": total_hubs,
        "click_depth_from_home": click_depth_from_home,
        "depth_ok": click_depth_from_home <= 4,
        "sitemaps": sitemaps,
        "sitemap_index_needed": sitemaps > 1,
        "inbound_links_per_page_target": inbound_min,
        "per_page_links": {"from_hub": 1, "from_siblings": sibling_links, "to_parent_hub": 1, "to_siblings": sibling_links + 1},
        "rollout": {"phase_1_pages": phase1, "phase_1_gate": "≥ 60% indexed and impressions on ≥ 30% of pages at 4 weeks", "remaining_pages": rest, "weeks": weeks, "pages_per_week": per_week},
        "verdict": (
            f"{n:,} pages need {total_hubs} hub page(s) in {len(levels)} level(s) at {fan} links per hub; pages sit {click_depth_from_home} clicks from home"
            + (" (fine)" if click_depth_from_home <= 4 else " — too deep: raise links_per_hub or add authority entry points")
            + f". {sitemaps} sitemap(s). Phase 1: {phase1:,} pages, then {per_week:,}/week for {weeks} weeks if the gate passes."
        ),
    }
