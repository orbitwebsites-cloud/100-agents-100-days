# E-commerce category eval: parity against paid tools

**Date:** 2026-09-27 · **Evaluator:** Claude (agent evaluator) · **Scope:** `hundred/agents/ecommerce/` (7 agents)

## How to read this

We have no accounts with the competitors, so we could not run them. For each agent we:

1. listed what the most-overlapping paid tool **documents** it does on the shared job, with a link for each item;
2. wrote a realistic customer request with planted problems;
3. ran it the way a customer's AI would (`python -m hundred.admin brief …`, then each tool through `hundred.admin run`);
4. checked every number against formulas written separately (in the scratchpad and in `tests/scenarios/test_ecommerce.py`, with no `hundred` imports).

The following count as **OUT OF SCOPE**, not as failures:

- store or marketplace data sync;
- search-volume databases;
- sending email or SMS;
- a helpdesk inbox;
- scraping competitor prices;
- recordings and heatmaps.

The verdict covers only the overlapping job.

We did **not** run a plain LLM without the agent. The failures listed under "what went wrong" are what the **agent's own tools returned before our fixes**. A customer's AI would have passed those numbers straight to the customer.

Every scenario can be replayed with `tests/scenarios/test_ecommerce.py` (14 tests). The new unit tests are in `tests/agents/test_ecommerce_*.py`.

## Overview

| Agent | Comparable & price | Checklist | Correctness checks | Verdict | Fixes made |
|---|---|---|---|---|---|
| inventory-planner | Prediko $49/mo (<$100k GMV); Inventory Planner by Sage (quote only) | 6 MATCHES · 2 PARTIAL · 0 MISSING · 1 OOS | 9/9 after fix. Before the fix, the seasonal forecast was 14–19% low and ROP said "not yet" when the answer was **order now** | **AT PAR** (was BELOW) | Classical decomposition for the seasonal forecast; lead-time demand from the forecast; `stock_cover` follows the forecast profile; stockout-adjusted demand; forecast velocity in health; EOQ in-tier candidate |
| product-listing | Helium 10 Platinum $129/mo ($99 annual); Jungle Scout $29 | 5 MATCHES · 2 PARTIAL · 1 MISSING · 2 OOS | 15/15 planted violations caught after fix (3 were missed before) | **AT PAR** | Competitor brand names and subjective/temporary words in search terms; promo words in the description; indexed vs exact-phrase keyword coverage; `<br>`-aware description lint |
| ecom-pricing | TrueProfit $35/mo (profit per order); Prisync $99/mo (price rules) | 4 MATCHES · 1 PARTIAL · 0 MISSING · 2 OOS | 8/8 after fix. Before the fix, the return cost was understated by $1.20/order (2.5 margin points) | **AT PAR** | Correct return model (outbound shipping and fees are sunk); `discount_impact` takes CM2 at both prices; the playbook no longer tells the AI to double-count outbound shipping |
| store-cro | Lucky Orange Build $39/mo | 2 MATCHES · 1 PARTIAL · 0 MISSING · 2 OOS | 7/7 (z-test matches the published example exactly) | **AT PAR** (the overlap is small) | `ab_test` blocks "wins" called at a peek (planned sample and full weeks); honest verdict when no step leaks; warnings when the free-shipping argmax is misleading |
| review-responder | Judge.me Awesome $15/mo | 2 MATCHES · 1 PARTIAL · 0 MISSING · 2 OOS | 8/8 after fix. Before the fix, the #1 defect (leaking lid, 13% of reviews) was **untagged** and the injury review was not escalated | **AT PAR** (was BELOW) | Tags for leaking, safety_injury and delivery_lost (negation-aware); safety review goes to the top of the queue; per-review policy flags; lint blocks public admissions on injury reviews |
| support-desk | Gorgias Starter $10/mo + AI Agent $0.90–1/resolution | 4 MATCHES · 1 PARTIAL · 0 MISSING · 2 OOS | 10/10 after fix. Before the fix, the **injury ticket was triaged P4 and landed last**, and "it wouldn't hurt…" was a P1 | **AT PAR** (was BELOW) | Negation-aware injury detection; safety first within P1; cancel/refund-status/missing-item rules; waiting time on the business clock; stem-based mirroring and empathy phrases |
| email-flows | Klaviyo (~$20/mo entry, 3P source) | 3 MATCHES · 2 PARTIAL · 0 MISSING · 1 OOS | 8/8 | **AT PAR** | Win-back and sunset timing use the measured p75 from `purchase_cycle`; flow problems ranked by severity rather than a fixed order; fake "RE:" and cliché subject lines penalised |

Checklist counts are for items the comparable documents. OOS = out of scope.

**Test results (final run):**

- `python -m pytest -q tests/agents -k ecommerce tests/scenarios/test_ecommerce.py`: 108 passed
- `python -m pytest -q tests/test_library.py`: 303 passed

No problems were found in `hundred/core.py` or `hundred/lib/`. While we worked, `hundred/agents/legal/contract_reviewer.py` briefly failed to import (an f-string with a backslash). That is another category's work in progress; it was fine by the end, and we did not touch it.

---

## 1. Inventory Planner — vs Prediko / Inventory Planner by Sage

**Scenario.** A DTC bottle brand on 2026-10-01 asks: "What should I order this week?"

- **Hero SKU THERMO-32:** 24 months of monthly sales. Q4 peak (Dec ≈ 2× average), +10.6% year on year, realistic noise.
- **Supplier:** lead time 45 ± 10 days; MOQ 500; case pack 24; $150 per PO; unit cost $6.80, with breaks to $6.50 at 1,000 and $6.10 at 2,500; holding cost 25%.
- **Stock:** 1,600 on hand, nothing on order; A-class, so 98% service level.
- **Catalogue:** 6 other SKUs, including an overstock (GLASS-18), a dead SKU (NEON-LTD) and a fast mover about to run out (CARRY-SLING).

**Parity checklist**

| # | Documented capability | Source | Status | Why |
|---|---|---|---|---|
| 1 | Forecast = same period last year + growth trend + seasonality | [Prediko: how to forecast inventory](https://www.prediko.io/forecasting-demand-planning/how-to-forecast-inventory); [IP: Configuring the forecast — "Seasonal" method](https://help.inventory-planner.com/en/articles/638170-configuring-the-forecast) | MATCHES (was BELOW) | Classical multiplicative decomposition. It agrees with "last year × YoY growth" to within 1% |
| 2 | Adjust the forecast for past stockouts ("Use stockouts history") | [IP help](https://help.inventory-planner.com/en/articles/638170-configuring-the-forecast) | MATCHES (new) | `stockout_days` scales sales up by in-stock days |
| 3 | Reorder point = daily demand × lead time + safety stock; "Buy Now" when below it | [Prediko reorder point](https://www.prediko.io/blog/how-to-calculate-reorder-point) | MATCHES | Adds statistical safety stock with lead-time variability; returns `order_now` |
| 4 | Safety stock expressed in days of cover, seasonality-proof | [Prediko: What is the safety stock](https://help.prediko.io/en/articles/9717637-what-is-the-safety-stock) | MATCHES | Returns `safety_stock_days_of_cover`; demand now comes from the forecast |
| 5 | Stock health (overstock / at risk / stock-out likely), counting incoming POs, "at delivery" | [Prediko: Stock Health](https://help.prediko.io/en/articles/6541624-what-is-the-stock-health-and-how-is-it-determined) | PARTIAL | `stock_cover` counts incoming POs by arrival date. `inventory_health` screens weeks of supply but ignores on-order stock |
| 6 | PO recommendation from lead times, MOQs, velocity and safety stock | [Prediko AI inventory management](https://www.prediko.io/ai-inventory-management) | MATCHES | EOQ with MOQ, pack size and all-units price breaks, plus the $ trade-off |
| 7 | ABC analysis | [Prediko forecasting guide](https://www.prediko.io/forecasting-demand-planning/how-to-forecast-inventory) | MATCHES | ABC plus XYZ with a service-level policy per cell |
| 8 | Several suppliers per SKU, each with its own lead time | [Prediko (search summary of help/blog)](https://www.prediko.io/shopify-inventory-forecasting) | PARTIAL | One supplier per call; the AI compares by running each |
| 9 | Shopify sync, one-click PO creation | Prediko | OUT OF SCOPE | Data sync and actions |

**Correctness**

| Check | Independent value | Agent (after fix) | Before fix |
|---|---|---|---|
| Forecast Oct / Nov / Dec 2026 | 663.7 / 1,057.1 / 1,437.6 (FPP3 §3.4 classical decomposition; last-year × YoY gives 663 / 1,056 / 1,438) | 663.7 / 1,057.1 / 1,437.6 | **537.7 / 906.9 / 1,177.3** (trend fitted to raw seasonal data came out −1%/mo on a growing SKU) |
| 12-month forecast | 8,729.7 | 8,729.7 | 7,357.9 (−16%) |
| Lead-time demand (45 d) | 1,170.5 | 1,170.5 | 932.7 (the playbook used the 24-month average) |
| Safety stock, z(98%)·√(LT·σd² + d²·σLT²) ([Wikipedia: Safety stock](https://en.wikipedia.org/wiki/Safety_stock), APICS combined-variability form) | 557.0 | 557 | 454 |
| Reorder point / decision | 1,727.5 → **order now** (1,600 < 1,728) | 1,728, ORDER NOW | 1,387, "not yet, ~10 days" |
| EOQ √(2DS/H) | 1,241.2 | 1,241.2 | 1,241.2 |
| Best quantity with breaks, pack 24 | 2,520 @ $6.10, TC $55,694.14 (vs $58,807.98 at 1,272 @ $6.50) | same | same (base-tier row showed 504 instead of the in-tier best of 984) |
| Stockout date on the forecast burn | 2026-11-28; hits safety stock 11-12; last safe order date 09-28 | same | 2026-12-18 at the flat rate (3 weeks optimistic) |
| Overstock value, GLASS-18 | (1450 − 26·120/90·7)·7.90 = $9,537.93 | $9,537.93 | same |

**Deliverable excerpt** (Output format)

```
# Inventory plan — 2026-10-01 · 7 SKUs · service level A/B/C = 98/95/90%
## Order now (inventory position ≤ reorder point)
| SKU | Class | On hand + on order | ROP | Order qty | PO value | Stockout date | Last order date |
| THERMO-32 | AX | 1,600 | 1,728 | 2,520 (@$6.10, 2.5k break, 24-pack) | $15,372 | 2026-11-28 | 2026-09-28 (3 days ago) |
| CARRY-SLING | CX | 70 | — | reorder now (2.3 wks cover < 6.4 wk lead time) | | | |
RED ALERT: THERMO-32 — a PO placed today lands 11-15, after stock dips into safety stock on 11-12.
Air-freight ~300 units or accept 3 days of reduced buffer going into the Nov/Dec peak (Dec ≈ 1,438 units).
The 24-month average (20.7/day) would have said "not yet"; lead-time demand is 26.0/day.
## Overstock / dead stock (cash to free)
| GLASS-18 | 155 wks | $11,455 | markdown or bundle; pause reorder (excess $9,538) |
| NEON-LTD | no sales in 90 days | $1,612 | stop reorder; liquidate/bundle |
## Assumptions
- σLT 10 days (supplier data); holding 25%/yr; σd = 11.4/day (10% forecast-error floor applied)
- SS = z·√(LT·σd² + d²·σLT²), d = forecast demand over the lead time; EOQ = √(2DS/H)
## Total PO value: $15,372 (+ CARRY-SLING) · Cash freed if actions taken: ~$11,150
```

**Honest gaps.**

- σ uses a 10% floor when residuals are small. That is a policy choice, and the output states it.
- Health does not net out on-order stock.
- The forecast uses 30.4-day periods, not calendar months (under ±1 day on stockout dates).
- The seasonal model needs 24 or more months. Prediko and Inventory Planner fall back to category-level seasonality for SKUs with little history; we do not.

---

## 2. Product Listing Writer — vs Helium 10 (Listing Builder / Listing Analyzer)

**Scenario.** "Fix my Amazon listing for the Hydra 32 oz bottle." The input breaks limits the way real listings do:

- **Title:** 230 characters; "BEST", "Free Shipping", `!` and `{ }`; "water" ×3 and "bottle" ×4.
- **Bullets:** 6 of them, including a feature-only bullet, `<b>` HTML, a "money-back guarantee", "Ships in 24 hours" and "FDA approved".
- **Description:** `<p>` HTML and a keyword stuffed 4×.
- **Search terms:** commas, an ASIN, `yeti`, `hydro flask`, `thermos`, "best" and "new".

**Parity checklist**

| # | Documented capability | Source | Status | Why |
|---|---|---|---|---|
| 1 | Checks title character count and bullet length | [Helium 10 listing optimisation](https://www.helium10.com/tools/listing-optimization/); [RevenueGeeks guide](https://revenuegeeks.com/helium10-listing-analyzer/) | MATCHES | Per-field limits and fixes |
| 2 | Main-image formatting check | same | MISSING | No image analysis tool; the host AI would need vision |
| 3 | Keyword bank: where each keyword appears (title, bullets, description) and its match type (exact / broad) | [Helium 10 Listing Builder](https://www.helium10.com/tools/listing-optimization/listing-builder/) | MATCHES | `keyword_coverage`: exact vs indexed-by-words per field, plus stuffing and wasted backend bytes |
| 4 | Listing/SEO score based on keyword usage | [H10 KB: Listing Builder score](https://kb.helium10.com/hc/en-us/articles/29528827146779-Listing-Builder-Video-How-to-Measure-Your-Listing-s-Amazon-SEO-Score); [H10 blog](https://www.helium10.com/blog/elevate-your-amazon-listings-with-listing-builder-cutting-edge-scoring-system/) | PARTIAL | Weighted coverage, title score and bullet score. No search-volume weighting (that data is OOS) |
| 5 | Search-terms field up to 250 bytes | [H10 listing optimisation](https://www.helium10.com/tools/listing-optimization/) | MATCHES | Counts bytes, not characters |
| 6 | AI-generated title / bullets / description from keywords | [H10 Listing Builder](https://www.helium10.com/tools/listing-optimization/listing-builder/) | MATCHES | The host AI writes to the playbook's formula; the tools gate it |
| 7 | Compare drafts by score | same | PARTIAL | Each draft can be scored; there is no side-by-side tool |
| 8 | Amazon 2025 title rules: 200 chars, banned `! $ ? _ { } ^ ¬ ¦`, no word more than twice (not an H10 claim; Amazon policy) | [Search Engine Land](https://searchengineland.com/amazon-title-policy-update-2025-450485) | MATCHES | All three enforced |
| 9 | Search volume (Cerebro/Magnet) | H10 | OUT OF SCOPE | Keyword database |
| 10 | Sync to Seller Central | H10 | OUT OF SCOPE | Data sync |

**Correctness (planted-issue recall and precision)**

| Planted issue | Caught before | Caught after |
|---|---|---|
| Title 230 > 200; promo words; ALL CAPS; `! { }`; word repeats | yes | yes |
| 6 bullets; HTML; money-back; shipping info; "perfect" | yes | yes |
| `<p>` HTML in description | yes | yes |
| **"best" in the description** | **no** | yes |
| ASIN in search terms | yes | yes |
| **Competitor brands in search terms (yeti, hydro flask, thermos)** — [prohibited](https://sellscope.ai/blog/amazon-backend-search-terms-250-byte-limit) | **no** | yes |
| **"best", "new" in search terms** (subjective/temporary, prohibited) | **no** (only "wasted bytes") | yes |
| Description stuffing ("insulated water bottle" 4× = 27%) | yes | yes |
| FDA-approved / BPA-free claims → verify | yes | yes |
| Rewrite: 0 false positives (145-char title, 128-byte backend, 5 bullets ≤ 155 chars) | before the fix: a false "paragraph over 80 words" on the `<br>`-formatted description, and coverage **61%** for the clean listing vs **82%** for the stuffed one | PASS, bullets 100, description 100, indexed coverage 100% |

The coverage result was misleading before the fix. Amazon matches words across fields, so the old phrase-weighted score rewarded stuffing. `coverage_pct` is now word-level (indexed) coverage, and `phrase_coverage_pct` is reported separately.

**Deliverable excerpt**

```
# Amazon listing — Hydra 32 oz Insulated Water Bottle
**Title (145/200 chars):** Hydra Insulated Water Bottle 32 oz with Straw Lid, Leak Proof Stainless Steel Bottle,
Keeps Drinks Cold 24 Hours, for Gym, Hiking and Kids, Black
**Bullets:**
1. KEEPS DRINKS COLD 24 HOURS: Double-wall vacuum insulation keeps water ice cold for 24 hours and coffee hot …
2. LEAK PROOF STRAW LID: The locking straw lid is tested upside down in a gym bag for 8 hours, so you can …
3. FITS YOUR CUP HOLDER: The 3.1 inch base fits most car cup holders and bike cages …
4. EVERYTHING YOU NEED: 1 x 32 oz bottle, 1 x straw lid, 1 x chug lid and 1 x cleaning brush …
5. BUILT FOR ROUGH DAYS: 18/8 stainless steel body and a chip-resistant powder coat that survives 1 m drops …
**Backend keywords (128 bytes):** tumbler flask canteen hydration jug sports travel camping school office cycling …
## Compliance & coverage
limits: PASS all fields · keywords: 8/8 indexed, primary exact at char 6 · title score 94/100
removed: yeti / hydro flask / thermos (third-party brands), ASIN, "best", "new", "Free Shipping", "money-back",
"FDA approved" (claim needs documentation — not re-added), BPA-free (verify certificate before re-adding)
## Title A/B
A: Hydra Insulated Water Bottle 32 oz with Straw Lid, Leak Proo · B: Hydra 32 oz Insulated Water Bottle with Straw Lid, Leak Proo
```

**Honest gaps.**

- No image checks.
- No search-volume weighting.
- The built-in brand list (about 50 common brands) is not exhaustive; the playbook tells the AI to pass `competitor_brands`.
- The limits are a dated snapshot. Amazon's "less than 250 bytes" wording may mean 249 is the maximum; we flag at more than 250.

---

## 3. E-com Pricing — vs TrueProfit / Prisync

**Scenario.** A Shopify linen pillow cover at $48:

- **Costs:** COGS $13.50 landed; free shipping costs $7.20; packaging $1.10; Shopify Payments 2.9% + $0.30.
- **Returns:** 12% return rate. Return cost $10.53 = label $6.50 + handling $2.00 + 15% of COGS written off.
- **Question:** "Should we run 20% off for Black Friday week?" Baseline 260 units, last year's lift +45%, $1,500 promo cost.
- **Also given:** a $44 → $48 price test (310 → 285 units/week) and 8 competitor prices; rating 4.7 vs market 4.4.

**Parity checklist**

| # | Documented capability | Source | Status | Why |
|---|---|---|---|---|
| 1 | Per-order/product profit with COGS, shipping, transaction fees, custom costs | [TrueProfit pricing & features](https://trueprofit.io/pricing) | MATCHES | Full order P&L, now with a correct return model |
| 2 | Compare ROAS to break-even ROAS | [TrueProfit: what is a good ROAS](https://trueprofit.io/blog/what-is-a-good-roas) | MATCHES | Break-even ROAS, max CPA, target ROAS |
| 3 | Most/least profitable products (Product Analytics) | [TrueProfit pricing](https://trueprofit.io/pricing) | PARTIAL | One product per call; no catalogue ranking |
| 4 | Minimum price / margin floor protection | [Prisync dynamic pricing rules](https://prisync.com/features/repricing-dynamic-pricing-rules/) | MATCHES | `floor_price_at_min_margin` |
| 5 | Position rules vs market (cheapest / average / most expensive) | same | MATCHES | Percentile, index to median, P25–P75 band, rating-justified premium |
| 6 | Automated repricing; competitor price scraping | Prisync | OUT OF SCOPE | |
| 7 | Real-time order and ad sync | TrueProfit | OUT OF SCOPE | |

**Correctness**

| Check | Independent value | Agent |
|---|---|---|
| CM2 at $48 (return refunded + restocked; outbound shipping, packaging and processing fee sunk — [Shopify keeps card fees on refunds](https://help.shopify.com/en/manual/payments/shopify-payments/payouts/refunds)) | $19.10 (39.8%) | $19.10 (39.8%). **Before the fix: $20.30** — outbound shipping and fees were treated as recovered on returns, and the old comment called this "conservative" |
| Gross margin vs markup | 71.9% vs 255.6% | 71.9% vs 255.6% |
| Break-even ROAS | 48 / 19.104 = 2.51× | 2.51× |
| Floor price at 30% CM2 | $39.46 (CM2 = 30.0% there) | $39.46 |
| Price for 40% CM2 | $48.21 → charm $48.95 | $48.21 → $48.95 |
| 20% off break-even units | (260·19.10 + 1500) / 10.93 = 591.6 → **+127.5%** | 592, +127.5% → "Losing trade" |
| Same promo with a COGS-only "variable cost" (the trap) | d/(m−d) = 0.2/0.519 = +38.6%, shows **+$417 profit** | The tool gives exactly that wrong answer when fed COGS only. The playbook now requires CM2 at both prices |
| Arc elasticity $44→$48 | −0.966 | −0.97 (inelastic) |
| Competitor median / percentile | 47.0 / 50th | 47.0 / 50th |

**Deliverable excerpt**

```
# Pricing — Linen pillow cover · recommended price $48.95
## Unit economics at $48 (per order)
| Price | 48.00 | 100% |   COGS 13.50 (28.1%) · ship 7.20 (15.0%) · box 1.10 (2.3%) · fees 1.69 (3.5%) · returns 5.40 (11.2%)
| Contribution margin (CM2) | 19.10 | 39.8% |
Break-even ROAS: 2.51× · Max CPA: $19.10 · Floor price (min CM2 30%): $39.46
## Recommendation
Move to $48.95: the $44→$48 test was inelastic (E = −0.97; profit +16%), and 4.7★ vs a 4.4★ market supports
+7.5% over the $47 median. $48.95 hits the 40% CM2 target.
## Promo guardrails
20% off needs +128% units (592 vs 260) to break even; last year's +45% loses ≈ $2,345 → do NOT run it.
Even 10% off needs +66% units (431 vs 260) with the $1,500 promo cost → no sitewide discount this week.
Preferred lever: gift-with-purchase or bundle; returns cost 11% of price — fix those first.
## Assumptions & formulas
Return = refund + restock; outbound ship, box, card fee sunk; return cost = label + handling + 15% COGS write-off.
```

**Honest gaps.**

- We model a single product, with no catalogue-level ranking.
- Marketplace referral fees are assumed refunded on return. Amazon keeps an admin fee (20% of the referral, up to $5) that we do not model.
- The +7.5% premium from the rating gap is a heuristic, and the output labels it as one.

---

## 4. Store CRO — vs Lucky Orange

**Scenario.** One month of data: 84k sessions, 1,160 orders, $100.5k revenue, 55% margin, split by device:

- **Mobile:** 62k sessions, CVR 0.84%, checkout completion 41.9%.
- **Desktop:** 22k sessions, CVR 2.91%.

The owner also asks:

- Is the mobile PDP test (sticky add-to-cart) a win at day 10? Control 402/9,850 vs variant 468/9,910.
- What free-shipping threshold should we set? (400 real order values, shipping $8.40)
- Please rank 5 test ideas.

**Parity checklist**

| # | Documented capability | Source | Status | Why |
|---|---|---|---|---|
| 1 | Conversion funnels: steps, drop-off count and % per step | [Lucky Orange conversion funnels](https://www.luckyorange.com/conversion-funnels) | MATCHES | Also benchmarks each step and sizes the gap in orders and $ |
| 2 | Rank stages by absolute drop-off volume, not % | [LO funnel best practices](https://www.luckyorange.com/blog/posts/conversion-funnel-best-practices) | MATCHES | Ranked by orders gained at benchmark |
| 3 | Segment funnels (device etc.) | [LO funnel analysis](https://www.luckyorange.com/blog/posts/how-to-analyze-conversion-funnels-pro) | PARTIAL | Run once per segment; no segment parameter |
| 4 | Click a step to watch the abandoners' recordings | LO funnels page | OUT OF SCOPE | Recordings |
| 5 | Heatmaps, recordings, form analytics, polls, chat | [LO pricing](https://www.luckyorange.com/pricing) | OUT OF SCOPE | Data collection |

Beyond what Lucky Orange documents, the agent also does A/B significance and planning, free-shipping threshold economics, AOV levers and ICE prioritisation.

**Correctness**

| Check | Independent value | Agent |
|---|---|---|
| Published z-test example, 80/200 vs 60/200 ([Wikipedia](https://en.wikipedia.org/wiki/Two-proportion_Z-test)) | z 2.0966, p 0.0360 | z 2.097, p 0.036 |
| Scenario test | z 2.197, p 0.02802, CI +0.069 to +1.213 pp, lift +15.71% | identical |
| Sample size, MDE 10% (Fleiss, no continuity correction) | 38,655 per arm → 38 days | 38,655, 38 days → 6 full weeks |
| **Decision at day 10 (25.5% of the planned sample)** | not callable | **before the fix: "WIN"**; after: "PROVISIONAL / NOT YET" |
| Mobile add-to-cart gain at the 6% benchmark | (3,720 − 2,480) × 520/2,480 = 260 orders | 260 |
| Mobile checkout gain at the 58% benchmark | 0.58 × 1,240 − 520 = 199 | 199 |
| Desktop (every step above benchmark) | no leak | before the fix: "#1 leak … worth ~0 orders"; after: "no leak here" |
| Free shipping at $115: share already above / in nudge band | recount of the 400 orders | matches |

**Deliverable excerpt**

```
# CRO audit — Hydra store · Sep 2026 · CVR 1.38% (benchmark 1.5-3%)
## Funnel (mobile — desktop beats every benchmark, the leak is mobile-only)
| Step | Rate | Benchmark | Orders lost/month | Rank |
| sessions → add to cart | 4.00% | 6.0% | 260 ($20.8k) | 1 |
| checkout → order | 41.94% | 58.0% | 199 ($15.9k) | 2 |
## #1 leak: mobile add-to-cart, then mobile checkout completion (41.9% vs desktop 62.8% on the same checkout)
Fix now (no test): repair the broken mobile review widget.
Test: Shop Pay / Apple Pay express on mobile checkout (ICE 448, ~49 orders/mo expected).
## Running PDP test (day 10): +15.7% ATC, p = 0.028 — PROVISIONAL, do not call.
Only 25.5% of the planned 38,655/arm; run to 6 full weeks (planned MDE 10%).
## AOV plan
Free shipping is a conversion bet here: every candidate is within noise of break-even (break-even lift 7-11%).
Test $105-115 (≈1.2-1.3× AOV $88.9), not the $135 argmax that only ~20% of orders would reach.
Best AOV lever: free gift over $100 → +$1,131 contribution/month.
```

**Honest gaps.**

- The free-shipping model credits the conversion lift only on qualifying baskets. With default assumptions its argmax is therefore always the highest threshold tested. We now warn when this happens rather than remodelling it.
- Benchmarks are blended across devices, so mobile is judged against blended rates.
- The tool suggests up to 8 weeks of runtime; the playbook says at most 4.

---

## 5. Review Responder — vs Judge.me

**Scenario.** 30 recent reviews of the bottle (average 3.33). Planted:

- 4 "leaking lid" reviews, worded without the word "defect";
- an injury review (a sharp lid edge cut a child's lip, urgent care);
- a courier-theft review;
- a review containing a phone number;
- a "cheaper on Temu" review;
- "does not fit my cup holder" (sizing).

The owner asks for 3 replies (the injury review, Dana's 1★, a 5★) and a plan to reach 4.5★ from 4.21 over 180 reviews.

**Parity checklist**

| # | Documented capability | Source | Status | Why |
|---|---|---|---|---|
| 1 | AI reply drafted per review, tone options, editable before posting | [Judge.me: Replying to reviews](https://judge.me/help/en/articles/8375131-replying-to-reviews) | MATCHES | Host AI drafts to AAO/TSA; `lint_response` gates it (specificity, one apology, offline path, no money/PII/admissions) |
| 2 | Public vs private (email) reply | same | PARTIAL | Public replies plus an offline path; no separate private-reply template |
| 3 | AI review insights: recurring topics (fit, quality, shipping) with sentiment | [Judge.me: AI review insights](https://judge.me/help/en/articles/13002535-showing-ai-product-review-insights-in-the-review-widget) | MATCHES (was BELOW) | Issue table with share and average rating per topic. The leak topic was missed before the fix |
| 4 | Automated moderation / replies (Sentimo) | [Judge.me + Sentimo](https://judge.me/help/en/articles/13264069-automating-review-moderation-and-replies-with-sentimo) | OUT OF SCOPE | Automation / posting |
| 5 | Review collection and widgets | Judge.me | OUT OF SCOPE | |

**Correctness**

| Check | Independent value | Agent after (before) |
|---|---|---|
| Average rating | 100/30 = 3.33 | 3.33 |
| Leaking-lid reviews | R03, R19, R22, R29 = 13.3% | same, escalated upstream. **Before: 0 tagged**; R03 and R22 untagged, R19 tagged only price/returns |
| Injury review R06 | must be first and escalated | first, `safety_escalations`. **Before: 2nd, tagged only "damaged_on_arrival"** |
| Reportable: R10 courier, R13 phone number, R25 competitor | 3 | 3 (before: not flagged in the batch) |
| "does not fit" (R05) | sizing | sizing (before: untagged) |
| Precision: "leak proof, never leaks", "no spills" | not a leak | not a leak |
| 5★ needed: k = n(T−A)/(5−T) = 180·0.24/0.55 | 78.5 → 79 | 79 |
| Realistic blend (85% 5★, 15% 2.5★) | 246.9 → 247; 83/month for 3 months | 247; 83 |

**Deliverable excerpt**

```
# Review replies — Shopify (Judge.me) · 30 reviews · avg 3.33 (5★11 4★5 3★3 2★5 1★6)
## Priority queue
| 1 | 1★ | safety_injury | ESCALATE today — human owner + counsel | Jess R. |
| 2 | 1★ | shipping_delay, damaged_on_arrival, customer_service | reply today | Dana K. |
| 3 | 1★ | leaking, price_value, returns_refund | reply today | Drew Y. |
## Replies
### 1 — 1★ Jess R. — safety_injury
Jess, I'm so sorry about your son's lip and the trip to urgent care. I hope he is healing well. I've shared
what you described about the cracked lid and the sharp edge with our product safety team today, and I'd like
to hear the details from you directly so we can look after you properly. Please email me at
care@hydrabottles.com or call our care line and ask for me. — Maya, Head of Customer Care
_(lint: 100/100 · ready; the first draft said "should never reach a family … same batch" → blocked: concedes cause)_
## Issues to fix upstream
| leaking lid | 13.3% | 1.75★ | product/QA | "The straw lid leaks in my bag every single time" |
| damaged on arrival | 10% | 1.33★ | ops (packaging) | "box was crushed … thin mailer" |
| lid injury (1) | — | 1★ | product safety + counsel | R06 |
Report: R13 (phone number), R25 (competitor promo), R10 (courier-only). Reply to them anyway.
## Rating plan
79 straight 5★ (≈247 at a realistic mix) take 4.21 → 4.45 (shows 4.5). At 22/month that is 11 months → 83/month
needed for a 3-month goal: post-delivery review request at delivered + 3 days.
```

**Honest gaps.**

- Tagging is regex-based. Unusual phrasing still ends up in `untagged_ids`, and the playbook now tells the AI to read those itself.
- There is no semantic clustering of topics the way Judge.me's AI does it.

---

## 6. Support Desk — vs Gorgias

**Scenario.** It is Friday 2026-10-02 16:30, business hours Mon–Fri 9–18. The queue has 20 tickets. Planted:

- **T02**, an injury with no "injury" keyword: "the plastic cut my daughter's finger … 3 stitches at the ER";
- **T05**, "It wouldn't hurt to send tracking emails";
- **T16**, "I pressed the button";
- **T04**, a cancellation phrased as "ordered the wrong size";
- **T09**, "My refund still hasn't arrived" (third contact);
- **T15**, "came without the chug lid";
- **T14**, a 300-unit logo order;
- **T20**, a journalist;
- **T06**, a chargeback.

**Parity checklist**

| # | Documented capability | Source | Status | Why |
|---|---|---|---|---|
| 1 | Detect intent and sentiment on incoming messages; rules to tag, prioritise and route | [Gorgias Rules](https://www.gorgias.com/product/rules); [intents overview (3P)](https://www.getmacha.com/blog/gorgias-tags-explained) | MATCHES (was BELOW) | Category, P1–P4, flags, needs-human |
| 2 | SLA policies for first response and resolution; pause outside business hours | [Gorgias SLA policies](https://docs.gorgias.com/en-US/sla-policies-536784) | MATCHES | Business-hours clock with holidays, breach and remaining time |
| 3 | SLA conditions (priority, VIP tag) | same | MATCHES | SLA per priority; VIP/high-value bump |
| 4 | Macros with variables auto-filled from ticket/customer data | [Gorgias macro variables](https://docs.gorgias.com/en-US/macro-variables-101-81845) | MATCHES | `lint_macro` fills `{{vars}}`/fallbacks and catches unfilled ones, plus tone |
| 5 | SLA report (adherence) | [Gorgias SLA report](https://docs.gorgias.com/en-US/gorgias-sla-report-536755) | PARTIAL | `support_metrics` gives FRT median/p90, contact rate and staffing, but no adherence % |
| 6 | Macro actions (tag, set priority), inbox | Gorgias | OUT OF SCOPE | Helpdesk actions |
| 7 | AI Agent resolving and sending | [Gorgias AI Agent pricing](https://www.gorgias.com/blog/ai-agent-pricing) | OUT OF SCOPE | Sending |

**Correctness**

| Check | Independent value | Agent after | Before fix |
|---|---|---|---|
| T02 injury ticket | P1, first | **P1 safety, #1 in queue** | **"other" P4, #20 (last)** |
| T05 "wouldn't hurt" | WISMO P3 | wismo P3 | **safety P1, #1 in queue** |
| T16 "pressed" | not an escalation | damaged P2, no escalation | needs_human (false "press" hit) |
| T04 / T15 / T09 / T14 | cancel P2 / missing item / refund status P2 / wholesale | same | wrong item / other P4 / WISMO / other |
| Waiting time, business clock (T08 Thu 17:30 → Fri 16:30) | 8.0 h (minute-by-minute count) | 8.0 | 23 h (calendar vs business SLA) |
| P2 4h from Fri 16:20 | Mon 11:20 | Mon 11:20 | same |
| P2 24h resolution from Fri 16:20 | Wed 13:20 | Wed 13:20 | same |
| With Monday a holiday | Tue 11:20 | Tue 11:20 | same |
| P1 1h on the calendar clock from Fri 15:55 | Fri 16:55 | Fri 16:55 | same |
| T08 breach | due Fri 12:30, 4.0 h overdue | same | same |

**Deliverable excerpt**

```
# Triage — 20 tickets · Fri 2026-10-02 16:30
| T02 | safety | P1 | due 16:55 today (calendar) | injury ("cut", stitches, ER) — human owner now, preserve photos |
| T20 | legal_press | P1 | overdue 0.8h | journalist asking about lid safety — route to founder, no comment until T02 reviewed |
| T06 | chargeback_fraud | P1 | overdue 2.2h | dispute opened — finance |
| T09 | return_refund | P2 | 16 business h waiting | 3rd contact, heated |
| T18 | wismo | P2 | VIP $230, 2nd message | …
# Ticket T02 — safety · P1 · due Fri 16:55 (0.4h remaining)
## Reply (ready to send)
Hi Rosa,
I'm so sorry your daughter was hurt, and I hope her finger is healing well after the stitches. I've read your
message and I'm handling this myself. I've passed your report and order #4402 to our product safety lead
today. Please reply with the photos when you can, and keep the lid if possible. I'll call you today at a time
that suits you, and you'll have a written update from me by Monday.
Thank you,
Maya
## Internal note
Action: refund + replacement held until safety lead reviews · Escalate: YES — injury; loop in counsel;
link to review R06 (same failure mode) and the journalist ticket T20. No liability language in writing.
(lint: ready · tone 100/100)
```

**Honest gaps.**

- Triage is rule-based. Gorgias uses ML intent detection across 24 intents; ours is regex, and the playbook now tells the AI to skim P3/P4 tickets for injury language.
- There is no aggregate SLA-adherence report.

---

## 7. Email Flows — vs Klaviyo

**Scenario.** A skincare brand (consumable, AOV $62, margin 70%) sends:

- order histories for 120 customers (52 repeat buyers, 117 gaps);
- flow stats for abandoned checkout, welcome and win-back (the win-back flow has 94% delivery and a 0.24% spam rate);
- 4 candidate subject lines, including "Re: your order".

A cart is abandoned Saturday at 22:15.

**Parity checklist**

| # | Documented capability | Source | Status | Why |
|---|---|---|---|---|
| 1 | Time delays between flow messages, relative to the trigger | [Klaviyo: timing of a flow](https://help.klaviyo.com/hc/en-us/articles/360046164352) | MATCHES | Exact local timestamps with quiet hours and ≥ 12h spacing |
| 2 | Flow filter "Placed Order zero times since starting this flow" | [Klaviyo: abandoned cart flow](https://help.klaviyo.com/hc/en-us/articles/115002779411) | MATCHES | Exit and suppression rules in every schedule |
| 3 | Expected date of next order / average time between orders (needs 500+ customers, 180 days, 3+ order buyers) | [Klaviyo predictive analytics](https://help.klaviyo.com/hc/en-us/articles/360020919731) | PARTIAL | Store-level median/p75 cycle drives the timing (works from ~10 gaps), not per-customer predictions |
| 4 | Benchmarks vs a peer group (e.g. placed-order rate) | [Klaviyo benchmarks](https://help.klaviyo.com/hc/en-us/articles/360050110072) | PARTIAL | Static published bands per flow type, not live peer data |
| 5 | Win-back timed off last purchase (their example: 75 + 15 days) | [Klaviyo: timing of a flow](https://help.klaviyo.com/hc/en-us/articles/360046164352) | MATCHES | Offsets from the measured p75 gap, now passed straight to the scheduler |
| 6 | Sending, segmentation, SMS | Klaviyo | OUT OF SCOPE | |

**Correctness**

| Check | Independent value | Agent |
|---|---|---|
| Median / p75 gap, repeat rate | 37 / 49 days, 43.3% | 37 / 49, 43.3% |
| Win-back email 1 (last order 08-20 14:05) | +49 d → 10-08 14:05 | same. **Before: the scheduler used 1.5 × median = 55.5 d**, contradicting `purchase_cycle` |
| Abandoned checkout, Sat 22:15 trigger | 23:15 Sat (urgent) / Mon 10:00 / Wed 10:00 | same |
| Abandoned checkout placed-order rate | 61/4,060 = 1.50% (band 3–5%) | 1.5% |
| What to fix first | conversion (half the floor) ahead of unsubs 0.54% (just over 0.5%) | conversion. **Before: "list health"** (fixed check order) |
| Win-back fix first | deliverability (94.2% < 97%) | deliverability |
| Upside at benchmark low | (0.03 − 0.015) × 4,060 × $62 = $3,769.6 | $3,769.6 |
| Revenue gap | 4,100 × (3% − 1.49%) × $62 = $3,838.42/mo | $3,838.42 |
| "Re: your order" | deceptive (FTC CAN-SPAM) → fail | 50/100 (before: 75) |

**Deliverable excerpt**

```
# Abandoned checkout — trigger: checkout started · exit: placed order · filters: no order in 7 days, not in win-back
| # | Send (local) | Delay | Goal | Subject (≤45) | CTA |
| 1 | Sat 23:15 | 1 h | reminder, plain text, no offer | Your serum is still in your cart | Return to checkout |
| 2 | Mon 10:00 | 24 h → quiet hours | objections: shipping/returns/reviews | Still deciding? 2,400 reviews help | See reviews |
| 3 | Wed 10:00 | 72 h | last call; small incentive allowed (70% margin) | Last call on your Vitamin C serum | Complete order |
## Revenue at stake
4,100 triggers × 3.0-5.0% × $62 = $7,626-12,710/mo; today $3,788 → gap $3,838/mo ($46k/yr, $2,687 contribution)
## Fix order (diagnostics)
Abandoned checkout: conversion first (1.50% vs 3% floor) — landing page + objection email; watch unsubs 0.54%.
Win-back: deliverability first (94.2% delivered, 0.24% spam) — suppress 180-day unengaged, sunset at day 111.
Win-back timing from your data: day 49 (p75), 64, 98 — not "30/60/90".
```

**Honest gaps.**

- There are no per-customer next-order predictions.
- Benchmarks are static.
- We design flows; Klaviyo builds and sends them.

---

## Files changed

- `hundred/agents/ecommerce/inventory_planner.py`: decomposition forecast, lead-time demand, `stockout_days`, forecast-profile `stock_cover`, forecast velocity in health, EOQ in-tier candidate, playbook.
- `hundred/agents/ecommerce/product_listing.py`: backend brand/subjective checks, description promo check, indexed vs phrase coverage, `<br>`-aware lint, playbook.
- `hundred/agents/ecommerce/ecom_pricing.py`: return model, floor/target price formulas, CM2 inputs to `discount_impact`, playbook.
- `hundred/agents/ecommerce/store_cro.py`: `ab_test` decision (planned sample, full weeks), no-leak verdict, free-shipping warnings, playbook.
- `hundred/agents/ecommerce/review_responder.py`: leak/safety/delivery tags with negation, policy flags, safety escalation, safety-admission lint, playbook.
- `hundred/agents/ecommerce/support_desk.py`: negation-aware safety detection, P1 ordering, category rules, business-clock waiting, empathy/mirroring, playbook.
- `hundred/agents/ecommerce/email_flows.py`: measured win-back/sunset offsets, severity-ranked diagnostics, fake "RE:" and cliché subjects, playbook.
- `tests/agents/test_ecommerce_*.py`:
  - 20 new unit tests.
  - 3 assertions updated to the corrected behaviour: the returns model, `coverage_pct` → `phrase_coverage_pct`, and flow `fix_first`.
- `tests/scenarios/test_ecommerce.py`: 14 replayable scenario tests.
