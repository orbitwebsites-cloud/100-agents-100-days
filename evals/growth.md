# Growth (SEO & Growth) — parity evals

**Date:** 2026-09-27 · **Scope:** all 8 agents in `hundred/agents/growth/` · **Regression suite:** `tests/scenarios/test_growth.py` (21 scenario tests) plus new unit tests in `tests/agents/test_growth_*.py`.

**How to read this.** We can't run the competitors, so each agent is compared with the **documented** checks of the paid tool whose job overlaps most (sources cited in each section). For each agent I wrote a realistic scenario with planted defects, ran it exactly as a customer's AI would (`hundred.admin brief` → follow the playbook → `hundred.admin run <slug> <tool>`), and verified the results independently:
- pixel widths against the Liberation Sans font tables (metrically identical to Arial), parsed with `struct`;
- statistics with textbook formulas, using an inverse-normal written from `math.erfc`;
- shingles and Jaccard similarity with my own set code;
- K-factor, LTV and review math by hand;
- schema against Google's documented required properties.

None of the verification code imports `hundred`. "Out of scope" means the check needs crawling, a keyword or backlink database, rank tracking, a citation network, or execution (sending or paying). These aren't counted as failures.

Prices come from `marketing/pricing_research/content_seo_creator.md` (seen 2026-09-27).

## Overview

Checklist columns: M = matches · P = partial · X = missing · OOS = out of scope.

| Agent | Comparable & price | Checklist (M / P / X / OOS) | Correctness / recall checks (after fixes) | Verdict on the overlapping job | Fixes shipped |
|---|---|---|---|---|---|
| seo-auditor | Screaming Frog SEO Spider, $279/yr (≈ $23/mo) | 9 / 1 / 0 / 5 | 12/12 planted defects found (was 11/12, and the canonical fix pointed at the parameterised URL). 0 false alarms. One real but unplanted defect found (logo has no size attributes). Title px within 0.01% of Arial metrics. | **AT PAR** (single-page audit) | Clean-URL canonical, `high` severity on parameterised URLs; URL hygiene check; mixed-content images; alt text over 100 chars; size attributes on any image; keyword-in-slug check; playbook field names |
| meta-writer | Yoast SEO Premium, $9.90/mo (+ Screaming Frog titles/descriptions tabs) | 6 / 1 / 0 / 1 | Site export: 8/8 planted issues, 0 false positives. Pixel widths within 0.08% of Arial metrics across 26 strings (accents, curly quotes, ™, W×36, i×45). | **AT PAR** | None needed |
| schema-markup | Rank Math PRO (≈ €7–9/mo) / Yoast; the reference is Google's Rich Results rules | 4 / 2 / 0 / 1 | 7/7 planted errors (was 5/7). False errors removed for Article and Organization, where Google lists no required properties. Rebuilt markup passes an independent re-statement of Google's product-snippet rules. | **AT PAR** on supported types; **BELOW** on type breadth | Required/recommended tables aligned with Google's docs; AggregateRating and Review requirements; `priceCurrency` downgraded to a warning for snippets; conflicting-duplicate-block detection; ambiguous-date warning |
| local-seo | BrightLocal Track, $29–39/mo per location [3P] | 3 / 2 / 0 / 3 | NAP: 3/3 real mismatches and 0 false alarms (was 1 false alarm: "Texas" vs "TX"). Review-reply lint: 6/6 planted problems (was 5/6) and 0 false issues on a good reply (was 1). Review math equals hand calculation (24 five-star reviews for a true 4.5; 19 for the displayed 4.5). | **AT PAR** on auditing the data you have | US state normalisation; keyword-stuffed name flag; duplicate-listing flag; target for the displayed (rounded) rating; defensive and ownership regex fixes |
| keyword-strategist | Semrush Keyword Strategy Builder (Semrush $139/mo) / Ahrefs Starter $29/mo | 4 / 3 / 0 / 1 | Intent: 21/21 hand labels (was 17/21). Clusters: no page mixes confident intents; "meal prep ideas" and "meal prep containers" are no longer one 12-keyword page; duplicates merged. Opportunity scores equal the published formula on all 27 rows. Gap: 7/7. | **AT PAR** with Semrush's topic grouping; **BELOW** Ahrefs' SERP-based Parent Topic | Gazetteer-based local intent; brandless navigational hints only; clustering compares against a fixed head; case/whitespace dedupe; volume lookup bug; product nouns flagged uncertain; navigational terms never quick wins; pillar step in playbook |
| growth-experiments | GrowthBook Pro, $40/seat/mo | 4 / 1 / 2 / 2 | Sample size equals the textbook formula (49,777 per arm; the classic 10%→12% value is 3,841). z, p and SRM χ² equal hand calculation. Relative CI now uses the delta method (−3.75% to +29.05%; was −2.8% to +28.1%, too narrow). | **AT PAR** on fixed-horizon 2-arm tests; **BELOW** on sequential/Bayesian | Delta-method relative CI; accurate reason when an experiment can't be scheduled |
| referral-program | ReferralCandy Basic, $39/mo + 10.5% | 1 / 4 / 0 / 2 | LTV, payback, K, amplification, 90-day projection and funnel upside all equal hand math. `compare_rewards` no longer recommends a signup-paid structure with a 7.4-month payback. | **AT PAR** on program design (the only overlap) | Guardrail-aware ranking; the "K ≈ 0.00" display bug; playbook wording |
| programmatic-seo | Research anchor: Surfer, $49/mo (little overlap). Overlapping checks: Screaming Frog, $279/yr, plus Google sitemap limits | 4 / 3 / 0 / 1 | Unique share and duplicate clusters equal an independent shingle computation. Collisions 2/2, template errors 3/3. Click depth was off by one and the threshold (4) contradicted the playbook (3). Both fixed. | **AT PAR** (sample QA and planning) | Depth formula and threshold; authority-page semantics documented |

**Test summary (final run):**
- `tests/agents -k growth` + `tests/scenarios/test_growth.py`: 96 passed
- `tests/test_library.py`: 303 passed

---

## 1. SEO Auditor — vs Screaming Frog SEO Spider

**Scenario.** A furniture e-commerce product page, "Ergo Pro Mesh" (3.9 kB HTML, 337 words). URL: `https://www.sitwell.com/products/ergo_pro_mesh_chair?variant=41872`. Keyword: "ergonomic office chair".

Twelve planted defects:
- no canonical on a `?variant=` URL
- two H1s
- 3 images with no `alt` attribute (a decorative `alt=""` and one good alt are correct)
- 117-character title
- 208-character description
- H2 → H4 skip
- "click here" and "Read more" anchors
- a `javascript:void(0)` link
- `target=_blank` without `noopener`
- an `http://` outbound link
- no `lang` attribute
- underscores and parameters in the URL

Correct elements included to test precision: viewport, charset, OG tags, JSON-LD, keyword in title/H1/intro, indexable, 9 internal links.

**Checklist** (sources: [SEO Spider features](https://www.screamingfrog.co.uk/seo-spider/), [issues library](https://www.screamingfrog.co.uk/seo-spider/issues/))

| # | Screaming Frog documented check | Status | Why |
|---|---|---|---|
| 1 | Page titles: missing, multiple, over px, below px, same as H1 | MATCHES | Uses 600px (Screaming Frog's default is 561px); widths match Arial |
| 2 | Meta description: missing, multiple, long, short | MATCHES | |
| 3 | H1 missing/multiple; H2 non-sequential | MATCHES | `heading_outline` |
| 4 | Images: missing alt attribute vs missing alt text; alt over 100 chars; missing size attributes | MATCHES (after fix) | Alt over 100 chars was missing; size attributes were only flagged at 3+ images |
| 5 | Canonicals: missing, multiple, relative, canonicalised | MATCHES (after fix) | The fix used to paste the `?variant=` URL itself as the canonical |
| 6 | Directives: noindex, nofollow | MATCHES | X-Robots-Tag header is OOS (needs HTTP) |
| 7 | URL: uppercase, underscores, parameters, over 115 chars, non-ASCII, multiple slashes, space | MATCHES (after fix) | Was MISSING |
| 8 | Links: non-descriptive anchors, no anchor text, uncrawlable outlinks | MATCHES | |
| 9 | Security: HTTP URLs, mixed content, unsafe cross-origin links | PARTIAL | Mixed content covers images only; security headers are OOS |
| 10 | Content: low content, readability | MATCHES | |
| — | Crawl, response codes, redirects, crawl depth, hreflang return tags, site-wide duplicates | OUT OF SCOPE | Needs a crawler |

**Correctness**

| Check | Result |
|---|---|
| Recall of planted defects | 12/12 across `audit_page` + `heading_outline` + `link_audit` (11/12 before the URL check) |
| Precision | 0 false alarms. The 9th `audit_page` issue (header `logo.svg` has no width/height) is real, just unplanted |
| Title width | Tool 1083.3px vs 1083.4px from the font tables |
| Description width | Tool 1296px vs 1296.4px from the font tables |
| Canonical fix | Before: `href="…ergo_pro_mesh_chair?variant=41872"` (wrong). After: the clean URL, severity `high` |

**Deliverable excerpt**
```
# SEO audit — /products/ergo_pro_mesh_chair · Score 60/100
**Target keyword:** ergonomic office chair (given) · **Words:** 337 · **Indexable:** yes
## Blockers (fix today)
None — no noindex, no off-page canonical.
## High-impact fixes
| # | Element | Current | Replacement | Impact | Effort |
| 1 | canonical | missing on ?variant= URL | <link rel="canonical" href="https://www.sitwell.com/products/ergo_pro_mesh_chair"> | high | low |
| 2 | title | 117 chars / 1083px | Ergo Pro Ergonomic Office Chair (12-Year Warranty) | SitWell | med | low |
| 3 | H1 | 2 H1s | keep "Ergo Pro Mesh Ergonomic Office Chair"; "Why Our Customers Love It" → H2 | med | low |
| 4 | images | front/side/lumbar have no alt | alt="Ergo Pro mesh chair, front view" (etc.) | med | low |
| 5 | outline | H2 Features → H4 Dimensions | Dimensions as H3 | low | low |
| 6 | links | javascript:void(0) "click here"; "Read more"→/contact | <button> for chat; "ask about sizing" | low | low |
| 7 | links | BIFMA target=_blank w/o rel; OSHA over http | rel="noopener"; https://www.osha.gov/… | low | low |
## Also noticed
- Description 208 chars / 1296px (cut at 920px) · no lang="en" · logo.svg lacks width/height
- URL has underscores + ?variant — only change with a 301 (→ /products/ergo-pro-mesh-chair)
## New title + description (ready to paste)
Title: Ergo Pro Ergonomic Office Chair (12-Year Warranty) | SitWell (546px / 60 chars, score 100)
Description: Ergo Pro Mesh ergonomic office chair: adjustable lumbar, 4D armrests and a 12-year warranty. Ships assembled, with a 100-night trial. (133 chars / 836px)
## Next
Ship the clean canonical first; in 2-4 weeks confirm in Search Console that ?variant URLs consolidate.
```

**Where a heuristic approach would slip (seen in this run):**
- The first "safe" rewrite I tried, *"Ergo Pro Mesh Ergonomic Office Chair – 4D Arms, Lumbar | SitWell"*, is only 64 characters but measures 603px, which is over the limit. Counting characters would pass it.
- The obvious canonical fix (self-referencing the current URL) is wrong on a parameterised URL.

**Honest gaps:**
- No crawler, so nothing site-wide (duplicates across pages, orphan pages, redirect chains).
- It audits the raw HTML only; JS-rendered content is flagged as a risk, not rendered.
- Mixed content covers `<img>` only, not scripts or CSS.

---

## 2. Meta Writer — vs Yoast SEO Premium (+ Screaming Frog bulk tabs)

**Scenario.**
- Part 1: write the snippet for DeskLab's guide "standing desk for small spaces" (brand: DeskLab).
- Part 2: audit a 12-row Screaming Frog-style export with 8 planted issues:
  - a duplicate-title pair, which also shares a duplicate description
  - a missing title
  - a missing description
  - a 972px title
  - a cannibalising near-duplicate pair
  - a brand-only title
  - a 9-character description

  Four rows are clean.

**Checklist** (sources: [Yoast assessment scoring spec](https://github.com/Yoast/wordpress-seo/blob/trunk/packages/yoastseo/src/scoring/assessments/SCORING%20SEO.md), [Yoast page titles](https://yoast.com/page-titles-seo/), [Yoast meta descriptions](https://yoast.com/meta-descriptions/), [Screaming Frog issues library](https://www.screamingfrog.co.uk/seo-spider/issues/))

| # | Documented check | Status | Why |
|---|---|---|---|
| 1 | SEO title width: red above 600px | MATCHES | Same 600px limit; widths match Arial to 0.08% |
| 2 | Keyphrase in SEO title, ideally at the beginning | MATCHES | `score_title`: position, first-half rule |
| 3 | Meta description length, green at 120–156 chars | MATCHES | Pixel-based (920px) with penalties under 70 and under 110; the recommended snippet is 149 chars |
| 4 | Keyphrase in meta description (1–2 matches is green) | PARTIAL | We penalise a 2nd occurrence that Yoast accepts |
| 5 | Google snippet preview, desktop/mobile | MATCHES | Text preview with the exact cut point; no visual render |
| 6 | AI-generated title/description suggestions (Premium) | MATCHES | The customer's AI drafts; tools score and iterate |
| 7 | Bulk missing/duplicate/long/short titles and descriptions (Screaming Frog) | MATCHES | Plus near-duplicate (cannibalising) titles, which Screaming Frog doesn't list |
| — | Editing inside the CMS / bulk editor | OUT OF SCOPE | |

**Correctness**

| Check | Result |
|---|---|
| Site audit recall | 8/8 |
| Site audit precision | 0 problems reported on the 4 clean rows |
| Pixel widths vs font metrics | Worst deviation 0.082% over 26 strings |
| Recommended title | 520.6px / 56 chars, keyword at position 0, score 100 |
| Recommended description | 909px / 149 chars, score 100; mobile cut at 680px reported |
| Variant with `(2026) \| DeskLab` | 606.5px, correctly rejected by 6.5px |

**Deliverable excerpt**
```
# Snippet — /guides/standing-desk-small-spaces · keyword: standing desk for small spaces
## Recommended
**Title:** Standing Desk for Small Spaces: 9 Picks Under 40" (2026)
521px desktop (fits) · 56 chars · score 100/100
**Description:** Find a standing desk for small spaces that fits: 9 compact sit-stand desks from 30" wide, tested for wobble at full height. Compare sizes and prices.
909px · 149 chars · score 100/100
## Alternatives
1. Standing Desk for Small Spaces: 9 Compact Picks (2026) | DeskLab — 606px · over by 6px; tests brand suffix
2. Small Space Standing Desk Guide | DeskLab — 402px · shorter promise; keyword not an exact phrase
## SERP preview (desktop)
Standing Desk for Small Spaces: 9 Picks Under 40" (2026)
desklab.com › guides › standing-desk-small-spaces
Find a standing desk for small spaces that fits: 9 compact sit-stand desks from 30" wide, tested for wobble at full height. Compare sizes and prices.
## Site export (12 URLs) — duplicates first
- "Standing Desks | DeskLab" + same 62-char description on /desks/corner-standing-desk and /desks/kids-standing-desk → write one per page
- Cannibalising: /guides/best-small-standing-desks vs /blog/best-small-standing-desk-apartment → consolidate (301 blog → guide)
- Missing title /desks/wall-mounted-desk · missing description /accessories/monitor-arm · 972px title /guides/standing-desk-height-calculator · brand-only title + 9-char description /about
## Notes
- Mobile cuts the description at "…tested for wobble …"; A/B year-in-title in GSC after 4 weeks.
```

**Where a heuristic approach would slip:** "Standing Desk for Small Spaces: 9 Compact Picks (2026) | DeskLab" is 64 characters, inside the common "50–60 chars, maybe 65" rule of thumb, but it is 606px and gets cut.

**Honest gaps:**
- No CMS write-back.
- The keyphrase-in-description rule is a little stricter than Yoast's.
- Mobile title limit is modelled as a 920px two-line wrap, not measured.

---

## 3. Schema Markup Builder — vs Rank Math PRO schema (reference: Google Rich Results rules)

**Scenario.** A trail-shoe product page carrying four JSON-LD blocks, as a plugin plus a hand-written copy would produce. Seven planted errors:
- `price: "$129.99"`
- `availability: "In Stock"`
- `priceValidUntil: "12/31/2026"`
- `aggregateRating` without a count
- a `review` with no author
- a second `Product` block with a conflicting name and price (139.99)
- a BreadcrumbList starting at position 0

Correct elements included to test precision: an authored review, a last breadcrumb without `item` (allowed), a valid Organization block, and a valid second Product block.

**Checklist** (sources: [Rank Math rich snippets KB](https://rankmath.com/kb/rich-snippets/); Google docs: [Product snippet](https://developers.google.com/search/docs/appearance/structured-data/product-snippet), [Article](https://developers.google.com/search/docs/appearance/structured-data/article), [Organization](https://developers.google.com/search/docs/appearance/structured-data/organization), [LocalBusiness](https://developers.google.com/search/docs/appearance/structured-data/local-business), [Event](https://developers.google.com/search/docs/appearance/structured-data/event), [Recipe](https://developers.google.com/search/docs/appearance/structured-data/recipe), [Breadcrumb](https://developers.google.com/search/docs/appearance/structured-data/breadcrumb), [Review snippet](https://developers.google.com/search/docs/appearance/structured-data/review-snippet))

| # | Documented capability | Status | Why |
|---|---|---|---|
| 1 | Schema generator for common types | PARTIAL | We build Article/BlogPosting/NewsArticle, Product, FAQ, HowTo, LocalBusiness + 17 subtypes, Organization, Event, Recipe, Breadcrumb. Rank Math lists ~37 types, including JobPosting, Course, Video, SoftwareApplication and Book |
| 2 | Code validation before publishing (Rank Math opens Google's Rich Results Test) | MATCHES | `validate_schema` reports errors and warnings itself, against Google's tables |
| 3 | Import from HTML or JSON-LD | MATCHES | `extract_schema` / `validate_schema`; fetching a live URL is OOS |
| 4 | Custom schema builder / advanced editor | PARTIAL | Unknown keys pass through and hand edits are re-validated; types outside the table get structural checks only |
| 5 | Breadcrumb schema | MATCHES | Positions, absolute URLs, final `item` optional |
| 6 | Required-property accuracy vs Google | MATCHES (after fix) | Was over-strict: Article without `image`/`datePublished`, or Organization without `url`, were reported as **errors**. Google says both types have *no* required properties. Was under-strict: AggregateRating count and Review author/rating weren't checked |
| — | Schema templates with display conditions across pages | OUT OF SCOPE | CMS feature |

**Correctness**

| Check | Result |
|---|---|
| Planted errors found | 7/7 (5/7 before; the rating count and review author were missed) |
| False errors | 0. Authored review, last crumb without `item`, Organization and second Product are all clean. Before the fix, a headline-only BlogPosting produced 2 false errors |
| Conflict report | `Product.name: 'Stride Trail 3' vs 'Stride Trail 3 Running Shoe'`, `Product.offers.price: '129.99' vs '139.99'`. The `$` sign and "In Stock" spelling are correctly *not* treated as conflicts |
| Rebuilt markup | 0 errors. Passes an independent re-statement of Google's product-snippet rules (price numeric, ISO date, schema.org enum, rating count) |
| Date parsing | `03/04/2026` is now reported as ambiguous (US reading 2026-03-04 vs EU reading 2026-04-03). It used to parse silently as day/month |

**Deliverable excerpt**
```
# Structured data — stride.com/trail-3 · type: Product
**Rich result:** blocked by 8 errors today → eligible for a product snippet (price, availability, rating) after the fix
## Validation (current page)
- Errors: price "$129.99" (currency symbol) · availability "In Stock" (not a schema.org URL) · priceValidUntil "12/31/2026" (not ISO) · aggregateRating lacks ratingCount/reviewCount · review[0] has no author · BreadcrumbList positions start at 0
- Conflict: two Product blocks disagree on name and price (129.99 vs 139.99) → delete the hand-written block
```html
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Stride Trail 3","image":["https://stride.com/img/trail3-side.jpg"],
 "brand":{"@type":"Brand","name":"Stride"},"sku":"TR3-M-10","url":"https://stride.com/trail-3",
 "offers":{"@type":"Offer","price":"129.99","priceCurrency":"USD","availability":"https://schema.org/InStock",
   "url":"https://stride.com/trail-3","priceValidUntil":"2026-12-31","itemCondition":"https://schema.org/NewCondition"},
 "aggregateRating":{"@type":"AggregateRating","ratingValue":"4.6","reviewCount":"212","bestRating":"5"}}
</script>
```
## Not included (and why)
- review[0] — no reviewer name on the page · description — no product description in the HTML
## Placement
<head>, replacing both Product blocks; breadcrumb positions 1-3. Rich Results Test now, GSC Product report in 1-2 weeks.
```

**Honest gaps:**
- Fewer types than Rank Math.
- Invalid values of *recommended* properties (e.g. `availability`) are reported as errors; Google's Rich Results Test may report them as non-critical.
- Merchant-listing rules (shipping, returns, GTIN) aren't modelled.

---

## 4. Local SEO — vs BrightLocal (Citation Tracker, GBP Audit, Reputation Manager)

**Scenario.** Rivera Family Plumbing, Austin, with eight listings: website, GBP, Yelp, Facebook, Bing, Apple, YellowPages, Angi.

Three real mismatches are planted:
- Facebook name keyword-stuffed ("Rivera Plumbing Austin - Best Plumber")
- Bing still shows the old address
- Apple shows a call-tracking phone number

Cosmetic-only variants that must *not* be flagged:
- Texas vs TX
- `#200` vs `Suite 200`
- ZIP+4
- `+1 512.555.0142`
- LLC / Inc.
- www / http website variants

Also in the scenario:
- 40 dated reviews (average 4.2, target 4.5)
- a 2-star review with a draft reply containing 6 planted problems: template phrase, "Actually," defensiveness, invoice number, discount-for-update incentive, no ownership, no offline contact
- a revised reply that should pass
- a partial GBP profile

**Checklist** (sources: [Citation Tracker](https://www.brightlocal.com/local-seo-tools/citation-tracker/), [What is Citation Tracker](https://help.brightlocal.com/hc/en-us/articles/360018761233-What-is-Citation-Tracker), [GBP Audit](https://help.brightlocal.com/hc/en-us/articles/360025649253-What-is-Google-Business-Profile-Audit), [Reputation Manager](https://help.brightlocal.com/hc/en-us/articles/360025090194-What-is-Reputation-Manager))

| # | BrightLocal documented feature | Status | Why |
|---|---|---|---|
| 1 | Find incorrect NAP data on listings | MATCHES (after fix) | Covers the listings supplied. Normalised name, address and phone; spelled-out state names now handled |
| 2 | Detect duplicate listings | PARTIAL | Flags duplicates among the supplied listings; *finding* them needs a crawl |
| 3 | Competitor citations / missing directories | OUT OF SCOPE | Citation network |
| 4 | GBP audit: business details, categories, NAP vs setup | PARTIAL | Weighted completeness plus exact fixes; no benchmark against the top-10 competitors (data) |
| 5 | Average rating and review count over time, review growth | MATCHES | Distribution, velocity, 90-day trend, five-star reviews needed |
| 6 | Reply to reviews / reply templates | MATCHES | Drafting plus a policy and tone lint; posting is OOS |
| 7 | Local rank tracking | OUT OF SCOPE | |
| 8 | Review-request email/SMS campaigns | OUT OF SCOPE | Sending; we compute the monthly ask target |

**Correctness**

| Check | Result |
|---|---|
| NAP mismatches | 3/3 found, 0 false (before the fix: 4 reported, including Facebook "Austin Texas 78756" vs "Austin, TX 78756") |
| Stuffed name | Flagged with note "extra: austin, best, plumber" |
| Consistency | 62% (5 of 8 sources clean) |
| Five-star reviews needed | 24 for a true 4.5 ((168+120)/64 = 4.5). 19 for Google to *display* 4.5 (263/59 = 4.458). The second is new |
| Velocity | 2.0/month last 90 days vs 3.0 prior → "slowing"; 1.68/month all-time; 22 reviews in the last 12 months; 12.0 months to target |
| Reply lint, bad draft | 6/6 problems found (before: "Actually," was missed because `\b` after a comma never matches) |
| Reply lint, good draft | 0 issues (before: a false "No ownership" because "…is on us" wasn't recognised) |
| GBP score | 56 = 15+8+6+5+4+8+4+6 (the weighted sum) |

**Deliverable excerpt**
```
# Local SEO plan — Rivera Family Plumbing, Austin
**Canonical NAP:** Rivera Family Plumbing · 4410 Burnet Rd Ste 200, Austin, TX 78756 · (512) 555-0142
**Primary category:** Plumber · **Secondary:** add Water heater installation service, Drainage service (only if offered)
## Fix now (highest impact)
1. Facebook name — current: "Rivera Plumbing Austin - Best Plumber" → set to: "Rivera Family Plumbing" (stuffed names violate the guideline)
2. Bing address — current: 3100 N Lamar Blvd, 78705 → set to: 4410 Burnet Rd Ste 200, Austin, TX 78756
3. Apple phone — current: (512) 555-0199 (tracking) → set to: (512) 555-0142
## NAP consistency  (5/8 sources clean · 62%)
| Source | Name | Address | Phone | Status |  … website/gbp/yelp/yellowpages/angi ok (formatting only)
## Profile completeness: 56/100 (C)
- photos 6 → upload ≥ 10 · services 3 → list ≥ 5 · description 43 chars → 250-750 · posts 45 days → post every 2 weeks · respond to reviews 55% → ≥ 90%
## Reviews
Rating 4.2 from 40 · velocity 2.0/month (last 90d vs 3.0 prior: slowing) · to reach a true 4.5: 24 five-star reviews (Google shows 4.5 after 19)
Monthly ask target: 8 · Ask moment: tech closes the job and the customer confirms the fix
## Review responses (drafted)
Mark (2★): "Mark, I'm sorry. Arriving three hours late without a call is on us, … Please call me directly at (512) 555-0142 …"
```

**Where a heuristic approach would slip:**
- "Austin Texas" vs "Austin, TX" is formatting, not a mismatch.
- The number of reviews needed for the rating to *display* 4.5 (19) differs from the number for a true 4.5 average (24).

**Honest gaps:**
- It doesn't discover listings, track rankings or benchmark competitors. That is BrightLocal's core, and it is out of scope here.
- Non-US address formats (provinces, postcodes) aren't normalised.
- The lint's keyword check can be satisfied by a word inside an email address.

---

## 5. Keyword Strategist — vs Semrush Keyword Strategy Builder / Ahrefs Keywords Explorer

**Scenario.** A messy 28-row export for a meal-prep container brand (PrepPal, new site), with volume, KD and CPC. It includes:
- a duplicate row differing only in case and a trailing space
- singular/plural variants
- traps: "meal prep in bulk", "…last in the fridge", "best meal prep app", "meal prep planner app"
- local, brand and competitor-brand queries

21 rows were hand-labelled for intent. Also included: two competitor keyword lists for the gap analysis and one Search Console position.

**Checklist** (sources: [Semrush KSB](https://www.semrush.com/kb/1058-keyword-strategy-builder), [Ahrefs Keywords Explorer](https://ahrefs.com/keywords-explorer))

| # | Documented capability | Status | Why |
|---|---|---|---|
| 1 | Intent labels: informational / navigational / commercial / transactional | PARTIAL | Modifier rules plus local; 21/21 on labelled rows. Bare product nouns get low confidence and are handed to the AI. Ahrefs uses SERP/AI intent, which needs data |
| 2 | Group keywords into topics/clusters (Semrush) / Parent Topic (Ahrefs) | PARTIAL | Lexical clustering against a fixed head term; no SERP overlap |
| 3 | Pillar pages + subpages | PARTIAL | Playbook step added; no tool output |
| 4 | Metrics per cluster: volume, KD, intent | MATCHES | From the export |
| 5 | Import up to 2,000 keywords | MATCHES | Same cap |
| 6 | Prioritise by volume and KD ("Best for Strategy") | MATCHES | Published formula plus quick wins and striking distance |
| 7 | Content/keyword gap vs competitors | MATCHES | Competitor lists supplied by the customer |
| — | Volume/KD/Traffic Potential database, SERP features | OUT OF SCOPE | |

**Correctness**

| Check | Before | After |
|---|---|---|
| Intent vs hand labels | 17/21 (in-bulk and in-the-fridge → local; both "app" rows → navigational) | 21/21 |
| Clustering | "meal prep ideas", "meal prep containers", "what is meal prep" and 9 more in **one** cluster. The common core shrank to {meal, prep}. The duplicate row was a separate member and its volume was dropped (lookup used unstripped keys) | 14 single-intent clusters. Ideas and containers kept apart. Duplicate merged, volume counted once |
| Opportunity scores | Equal to `25·log10(v+10)·w·(1−KD/100)²·(1+min(CPC,10)/10)` (×1.5 striking distance) on all 27 rows | same |
| Quick wins | Included "preppal login" (own-brand navigational) | Equal to the hand-computed set, without navigational terms |
| Gap analysis | 7 gaps; 2 shared by both competitors (glass containers, dishwasher-safe); overlap 1 and 0 | same |

**Deliverable excerpt**
```
# Keyword strategy — PrepPal (meal prep containers) · 27 keywords → 14 pages
**Assumptions:** new site (KD punished, k = 2), conversion = container order; bare product nouns judged transactional
## Ship first (quick wins)
| Rank | Page | Primary keyword | Intent | Format | Vol | KD | Score | Secondaries |
| 1 | Glass meal prep containers (collection) | glass meal prep containers | transactional | category page | 9,900 | 22 | 97.0 | meal prep container dishwasher safe |
| 2 | Bulk / cheap meal prep containers | cheap meal prep containers | transactional | category + price filter | 880 | 15 | 84.3 | buy meal prep containers bulk, set price |
| 3 | Best glass meal prep containers | best glass meal prep containers | commercial | roundup w/ verdict | 1,300 | 18 | 72.3 | containers vs tupperware |
## Build next (strategic)
| 4 | Meal prep containers (pillar collection) | meal prep containers | transactional | category | 40,500 | 38 | 69.4 | meal prep container |
| 5 | How to meal prep chicken (striking distance, pos 14) | how to meal prep chicken | informational | how-to | 6,600 | 35 | ×1.5 | meal prep chicken recipes |
## Skip / later
- meal prep ideas (KD 62, informational, new site) · meal prep delivery near me/austin (local, off-model) · preppal login (own brand)
## Gap vs competitors
- glass meal prep containers — prepnaturals + bentgo · 9,900 · transactional
- meal prep container dishwasher safe — prepnaturals + bentgo · 590 · transactional
## Notes
- Low-confidence calls I made: meal prep containers / glass… / dishwasher safe → transactional (product nouns); meal prep sunday → informational
```

**Honest gaps:**
- Clustering is lexical, so two keywords that share a SERP but no words won't merge. Ahrefs' Parent Topic would catch them. Not fixable without SERP data.
- Intent for bare nouns is left to the AI's judgement.
- The city list is a gazetteer of about 150 major cities: "plumber waco" is not detected as local.

---

## 6. Growth Experiment Lab — vs GrowthBook Pro

**Scenario.**
- Baseline 3.2% signup, MDE 10% relative, 8,000 visitors/week. Plus a 3-arm variant at 25% MDE.
- Six-idea ICE backlog with surfaces and durations, 2 parallel slots, 12-week horizon.
- Two hypotheses: one vague, one complete.
- Three results: the playbook's 10,412/331 vs 10,388/372; an SRM case (50,000 vs 48,200); a peeking case (p = 0.013 at 8% of plan).

**Checklist** (sources: [GrowthBook statistics overview](https://docs.growthbook.io/statistics/overview), [frequentist details](https://docs.growthbook.io/statistics/details), [power analysis](https://docs.growthbook.io/statistics/power), [experiment results / SRM](https://docs.growthbook.io/app/experiment-results))

| # | GrowthBook documented capability | Status | Why |
|---|---|---|---|
| 1 | Frequentist test and p-value | MATCHES | Two-proportion z-test. GrowthBook uses Welch t, which converges to the normal at these sample sizes |
| 2 | CI on relative uplift (delta method) | MATCHES (after fix) | Previously divided the absolute CI by p₁, which is too narrow |
| 3 | SRM chi-square, warn at p < 0.001 | MATCHES | Same test and threshold |
| 4 | Power analysis: users/weeks for 80% power, MDE, number of variations | MATCHES | Plus the MDE detectable in 8 weeks |
| 5 | Multiple-testing corrections | PARTIAL | Bonferroni in sizing; `evaluate_result` is 2-arm only |
| 6 | Sequential testing (safe peeking) | MISSING | Fixed horizon plus a peeking guard instead |
| 7 | Bayesian engine / chance to win (GrowthBook default) | MISSING | |
| 8 | CUPED variance reduction | OUT OF SCOPE | Needs pre-period unit-level data |
| — | Assignment, feature flags, warehouse metrics | OUT OF SCOPE | |

**Correctness** (independent `math.erfc` inverse-normal, textbook formulas)

| Check | Tool | Independent |
|---|---|---|
| n per arm, 3.2% → +10% | 49,777 | 49,777 |
| n per arm, 3 arms, +25% (Bonferroni α/2) | 10,307 | 10,307 |
| n per arm, 10% → 12% (classic table value) | 3,841 | 3,841 |
| Weeks at 8k/week | 13 (12.44 raw); MDE detectable in 8 weeks 12.5% | ⌈99,554/8,000⌉ = 13 |
| z / p (playbook example) | 1.604 / 0.10865 | 1.6043 / 0.10865 |
| Relative CI | −3.75% to +29.05% (was −2.8% to +28.1%) | −3.75% to +29.05% (delta method) |
| SRM χ² (50,000 vs 48,200) | 32.994, p = 9.2e-9 → invalid | 32.994 |
| ICE products and sprint | 378/288/270/240/175/128; the two signup tests don't overlap; exit-intent doesn't fit the horizon | hand-checked |

**Deliverable excerpt**
```
# Experiment backlog — signup funnel · method: ICE
| Rank | Experiment | Hypothesis (one line) | I | C | E | Score | Weeks | Slot |
| 1 | Social proof bar on signup | If we add logos + 4.8★ under the form for new desktop visitors, signup conversion +10% because 3/5 interviewees… | 6 | 7 | 9 | 378 | 4 | 1 (wk 1-4) |
| 2 | Remove card from trial | (needs evidence — confidence 8 with none given) | 9 | 8 | 4 | 288 | 6 | 1 (wk 5-10) |
| 3 | Annual plan default | … | 5 | 6 | 9 | 270 | 3 | 2 (wk 1-3) |
## Experiment doc — Social proof bar
**Baseline:** 3.2% · **MDE:** 10% relative · **Sample:** 49,777 per arm · **Run:** 13 weeks → not feasible;
detectable in 8 weeks: ≥ 12.5% → pre-register MDE 12.5% or test a higher-volume step
**Decision rule:** ship if p < 0.05 and lift ≥ MDE with guardrails flat
## Result (playbook example)
Control 3.18% vs Variant 3.58% · lift +12.6% (95% CI −3.8% to +29.1%) · p = 0.109 · SRM ok (p = 0.87)
**Decision:** inconclusive — a null result, not a directional win
```

**Where a heuristic approach would slip:** the naive relative CI (−2.8% to +28.1%) looks tighter than the data supports. The delta-method interval is about 1 percentage point wider on each side.

**Honest gaps:**
- No sequential or Bayesian analysis.
- Multi-arm results must be evaluated pairwise with manual correction.
- Continuous metrics (revenue per visitor) aren't supported.

---

## 7. Referral Program Designer — vs ReferralCandy

**Scenario.**
- $29/mo SaaS, 70% margin, 4% monthly churn, $180 paid CAC; proposed two-sided $50/$50.
- Viral inputs: 1.8 invites/user at 12%, 10-day cycle, 2,000 seed users, 90 days.
- Funnel: 8% share, 3.2 invites per sharer, 25% click, 15% signup, 40% qualified.
- Three reward structures to compare, including a signup-paid $30/$30 with a higher raw net.

**Checklist** (source: [ReferralCandy features](https://www.referralcandy.com/features))

| # | ReferralCandy documented feature | Status | Why |
|---|---|---|---|
| 1 | Reward types: cash, % or flat discount, store credit, gift card | PARTIAL | Economics are modelled for any cash-equivalent value; % discounts must be converted to currency by the AI |
| 2 | Different rewards for referrer and friend | MATCHES | `referee_reward`, `compare_rewards` |
| 3 | Tiers that climb with volume | PARTIAL | Playbook only; no tier-schedule model |
| 4 | Fraud detection | PARTIAL | Fraud rules plus a guardrail against signup-paid rewards; live detection is OOS |
| 5 | Revenue, conversion and ROI analytics | PARTIAL | ROI and funnel diagnostics from supplied numbers; live attribution is OOS |
| 6 | Post-purchase widget, landing pages, invite emails | OUT OF SCOPE | Copy is drafted; hosting and sending are not |
| 7 | Link/code attribution, payouts | OUT OF SCOPE | |

**Correctness (by hand)**

| Check | Result |
|---|---|
| LTV | 29 × 0.7 / 0.04 = **507.5** ✓ |
| Payback | 100 / 20.3 = **4.93 months** ✓ |
| Ceiling | min(LTV/3 = 169.17, CAC 180) = **169.17** ✓ |
| K | 1.8 × 0.12 = **0.216** ✓ |
| Amplification | 1/(1−K) = **1.28** ✓ |
| Users at day 90 | 2000·Σ₀⁹Kⁿ = **2,551** ✓ |
| Funnel | 2000·0.08·3.2·0.25·0.15·0.40 = **7.68 qualified** (K 0.00384) ✓ |
| Upside | Lifting click→signup to 35% adds 10.24 → **10** ✓ |
| `compare_rewards` | Before: recommended "$30/$30 at signup" (net $5,005/100 invites, but 7.4-month payback and signup-paid, both failing the playbook's own self-check). After: recommends "$50/$50 credit" ($4,890) and names why the other fails |

**Deliverable excerpt**
```
# Referral program — (SaaS, $29/mo)
**Economics:** LTV $507.50 · paid CAC $180 · reward ceiling $169 · proposed reward $50 (+$50 credit to friend)
→ cost per referred customer $100 · payback 4.9 months · fits (5.1× LTV)
## Mechanics
- Trigger: after the first successful project export · Reward timing: on the friend's first payment (never at signup)
- Referrer gets $50 account credit · Friend gets $50 off first invoice · Cap: 10 rewards/month · Hold: 30 days (refund window)
## Targets (per 1,000 active users / month)
| Step | Benchmark | Now | Target |
| click → signup | 15-35% | 15% | 25% (biggest lever: +10 customers per 2,000 users at 35%) |
Referred customers/month now: 3.8 per 1,000 · Implied K: 0.004 — a channel, not a growth engine
## Fraud & abuse rules
- one reward per card + email + device · no self-referral (same card/domain) · manual review above 5/month
## Copy
Ask: "Know a team drowning in spreadsheets? Give them $50 off." (≤ 15 words)
```

**Honest gaps:**
- It doesn't run the program: tracking, payouts, widgets and fraud scoring are ReferralCandy's actual product.
- No tiered-reward modelling.
- The viral projection is a deterministic generation model, not a cohort simulation with churn.

---

## 8. Programmatic SEO — vs Screaming Frog (duplicates, URL issues) + Google sitemap rules

Research anchor: Surfer Discovery ($49/mo). Surfer's content-editor job barely overlaps this agent; the checks that do overlap are Screaming Frog's.

**Scenario.** A "[service] cost in [city], TX" page set: 8 services (one duplicate) × 13 cities (one empty). The URL template forgets `{city}`. Slugs include "Winston-Salem"/"Winston Salem", "Kitchen & Bath"/"Kitchen and Bath", "Cañon City", "Coeur d'Alene" and a 100-character service name.

Ten sample pages:
- 6 city-swapped template pages (only the city and price change)
- 3 pages with real local data
- 1 exact copy

**Checklist** (sources: [Screaming Frog duplicate content](https://www.screamingfrog.co.uk/seo-spider/tutorials/how-to-check-for-duplicate-content/), [issues library](https://www.screamingfrog.co.uk/seo-spider/issues/), [Google sitemap limits](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap))

| # | Documented capability | Status | Why |
|---|---|---|---|
| 1 | Exact duplicates (MD5 hash) | MATCHES | Similarity 1.0 clusters |
| 2 | Near duplicates, adjustable threshold (minhash, 90% default) | MATCHES | Exact shingle Jaccard, threshold 0.5–0.95 |
| 3 | Exclude nav/footer from the comparison | PARTIAL | Takes text, so the caller strips boilerplate; the boilerplate ratio is measured instead |
| 4 | URL issues: non-ASCII, over-long, spaces | MATCHES | `slugify_batch`, plus collision detection |
| 5 | Low-content pages | MATCHES | Thin below 300 words |
| 6 | Crawl depth | PARTIAL | Planned from the hub design, not measured |
| 7 | XML sitemaps (≤ 50,000 URLs / 50 MB, index file) | PARTIAL | Counts sitemaps and index need; doesn't emit XML |
| — | Crawling the live site | OUT OF SCOPE | |

**Correctness**

| Check | Result |
|---|---|
| Page count | 7 × 12 = **84** ✓ (duplicate and empty value removed) |
| Template errors | Unused `{city}` in the URL template flagged ✓ |
| Titles over 600px | 3/6 sample titles, confirmed against the font metrics |
| Slug collisions | 2/2 (winston-salem, kitchen-and-bath-remodel); `canon-city`, `coeur-dalene` and the 60-character cap all correct |
| Unique share | 0.178 for the 6 template pages and 1.0 for the 3 data-rich pages, equal to an independent shingle computation |
| Median unique share | 0.178 → **FAIL** ✓ |
| Duplicate cluster | [austin, austin-copy] |
| Why the city-swap pages aren't pairs | Pairwise Jaccard austin/dallas ≈ 0.6, under the 0.8 threshold (Screaming Frog's 90% default would miss them too). The unique-share gate catches them |
| Click depth (before) | Off by one: 12,000 pages at 100 links per hub = home → 2 → 120 → page = **3 clicks**, reported as 4. The tool's "ok" threshold was 4 while the playbook says ≤ 3 |
| Click depth (after) | Both fixed; with more than one authority page, a category level (+1) is assumed and documented |

**Deliverable excerpt**
```
# Programmatic SEO plan — HomeQuote "[service] cost in [city], TX"
**Pages:** 84 (7 services × 12 cities) → **recommended:** 21 after pruning · **rollout:** 2 phases
## Dimensions
| Dimension | Values (kept/total) | Why cut |
| service | 7/8 | "Roof Replacement" listed twice |
| city | 3/12 for launch | only San Antonio, El Paso, Round Rock have local data today |
## Patterns
URL: /cost/{service}/{city}/  (template was missing {city} — every city collided on one URL)
Title: {service} Cost in {city}, TX (2026) — 3/6 samples ran past 600px with "Prices) | HomeQuote"
## QA gates (from tools)
Boilerplate 53% · median unique share 18% (gate 40%) · 1 exact duplicate (austin / austin-copy) · slug collisions 2
→ FAIL: the six city-swap pages share 82% of their text; add permit rules, local job counts, median price, lead time
## Architecture
84 pages: linked straight from the /cost/ hub (1 click from home), 1 sitemap; ≥ 3 inbound links per page (hub + 2 siblings)
## Rollout & kill criteria
Phase 1: 9 pages with local data → gate ≥ 60% indexed + impressions on ≥ 30% at 4 weeks → Phase 2
```

**Honest gaps:**
- Semantic duplicates ("St. Louis" vs "Saint Louis") need an alias list; lexical slugging treats them as two cities.
- No XML output.
- Depth is planned, not crawled.
- Surfer's core job (NLP term coverage against the SERP) isn't covered at all.

---

## Issues outside `hundred/agents/growth/` (described, not edited)
- None required by the growth fixes.
- During the run, `hundred/agents/legal/contract_reviewer.py` briefly failed to import (an f-string with a backslash, Python < 3.12), apparently from another workstream. `tests/test_library.py` passed on the final run.
