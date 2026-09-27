# Product & Design — parity evaluation

Evaluated 2026-09-27 against the paid tool a customer would otherwise buy for the **overlapping job**
(prices from `marketing/pricing_research/eng_product_career_ecom.md`, except PitchBob, read on its own
page). We could not run the competitors, so each checklist uses only features the vendor **documents**
(URL cited). Every scenario, input and verified number is replayable in `tests/scenarios/test_product.py`
(52 tests).

**Method.** For each agent: `python -m hundred.admin brief <slug> "<task>"` → follow the playbook → call
each tool with `python -m hundred.admin run <slug> <tool> -` → write the deliverable in the playbook's
output format → check every planted item and number against an outside reference or by hand. The
reference helpers in the scenario file (`_wcag_ratio`, `_nps`, `_kano`) are written from the published
formulas and never import `hundred`. The outside references are WebAIM's contrast-checker API
(<https://webaim.org/resources/contrastchecker/>, queried live), the published Kano evaluation table
(Berger et al. 1993; <https://foldingburritos.com/blog/kano-model/>), colorspacious 1.1.2 (an
independent implementation of Machado et al. 2009 colour-blindness simulation) and W3C's "Text size in
translation" (<https://www.w3.org/International/articles/article-text-size>).

**Scoring.** MATCHES = 1, PARTIAL = 0.5, MISSING = 0. OUT OF SCOPE items are listed but not scored:
hosted repositories, dashboards, survey collection, video, browser extensions, Figma plugins, team
workspaces and version history.

## Overview

| Agent | Comparable & price | Checklist | Correctness checks | Verdict | Fixes |
|---|---|---|---|---|---|
| accessibility-checker | Stark Premium, $16.50/seat/mo billed yearly (min 3 seats) | 6 / 8 | 18/18 planted HTML defects found, 0 false positives (before: 14/18, 2 FP). 12/12 colour pairs match WebAIM on pass/fail. 11/12 match WebAIM's displayed ratio exactly; the 12th (14.67) differs only because WebAIM shows 3 significant figures above 10:1 (before: 5/12, including **4.499 shown as "4.5:1 — FAIL"**). 7/7 suggested colours pass in WebAIM. Colour-blindness simulations match colorspacious on 12/12 values | **AT PAR** | 8: truncate ratios instead of rounding; `<img alt>` inside link/button counts as its name; empty headings; broken aria-labelledby; label[for] + duplicate id; autocomplete validity (1.3.5); new colour-blindness simulator tool; `<main>` landmark; iOS 44pt / Android 48dp targets |
| feedback-analyzer | Survicate Growth, $114/mo billed yearly | 5 / 6 | NPS 15.0 ±18.0 and 3 segments match hand calculation. Theme tagging vs hand labels: precision 0.87, recall 0.99 (before: 0.82 / 0.89). Driver gap −4.83 and fix priorities match hand calculation | **AT PAR** (ABOVE on statistics) | 4: judge period-over-period change against the margin of the *difference* (was single-period margin); plural-aware taxonomy; "export"/"import" removed from integrations; `score` passed through to driver analysis |
| roadmap-prioritizer | Productboard Plus, $25/maker/mo | 5.5 / 6 | 12/12 RICE scores by hand. 6/6 Kano classes and Better/Worse coefficients match the published table. Capacity numbers 28.8 / 62.5% / 0.9 / 12.1 match hand calculation. WSJF 31/8 = 3.88 | **ABOVE** on scoring | 4: new `framework_score` tool (WSJF, ICE, value/effort, weighted drivers); RICE tie tiers; Coulds treated as contingency; "−0.0" |
| interview-synthesizer | Condens Lite, €15/mo (Dovetail self-serve discontinued) | 5.5 / 6 | Tag counts and saturation curve match hand counts. Clustering pairwise F1 0.86 (was 0.58). Signal sentences: 26/26 in the scenario (was 18/26; tuned on it), **5/12 on unseen notes** | **AT PAR** (the keyword signal net is weak) | 4: consistent stemming; clustering on shared "linking" words, default threshold 0.34; wider pain/frequency/hypothetical patterns; playbook tells the AI to read every interview in full |
| prd-writer | ChatPRD Pro, $15/mo | 5 / 6 | Draft completeness 48/100 matches hand calculation. 22/22 planted PRD defects found, 0 false positives (before: 20/22, 3 FP including "by Q4 2026" rejected as a deadline). Rewritten PRD scores 100 | **AT PAR** (ABOVE on auditability) | 4: quarter/month deadlines accepted; compound "…and can…" requirements; stem-aware circular "so that"; broader observable-verb list |
| ux-writer | Frontitude UX Writing Assistant seat, $25/mo | 5 / 6 | 15/15 planted copy problems found, 0 false positives, 5/5 decoys clean (before: 11/15, 5 FP). Localisation checked against 18 real UI translations: the old estimate came in too short on 9/18; the new layout budget on 2/18 | **AT PAR** | 7: Title Case detection ("Log In"); nouns used as verbs on buttons ("Logout"); "Are you sure?"; no false error codes or blame; inflection- and hyphen-aware synonym matching; sign-in/out pairing; W3C/IBM length budget; glossary block-list |
| pitch-deck-coach | PitchBob AI deck feedback, $29.90 | 5 / 7 | TAM/SAM/SOM 648M / 226.8M / 6.804M and 1,418 customers by hand. Dilution 20.83%, effective pre-money $8.3M, runway 15.9 mo (= ln 1.6 / ln 1.03), 18-month need $3,278,021, all by hand. Structure 12/12 with the AI's slide types | **AT PAR** | 5: `slide_types` (claim-style titles no longer reported "missing"); word-boundary section matching; `existing_cash` and burn-growth-aware raise advice; TAM ratio wording; "we only need 1% of the market" flag |

Test summary: `pytest -q tests/agents -k product tests/scenarios/test_product.py` → 161 passed;
`pytest -q tests/test_library.py` → 303 passed.

**Where a plain AI (no tools) would likely slip: not measured.** We did not run a no-tools baseline, so
we don't claim one. The traps below were observed in naive methods during this run (including our own
tools before they were fixed):
- Rounding #5A7C87 on white to "4.5:1" when it fails AA. WebAIM truncates to 4.49.
- Calling a −7 NPS move significant when judged against one period's ±18 instead of the ±25.5 margin of a change.
- Reading "export" as an integration.
- Treating two short sticky notes as unrelated because they use "approve", "approved" and "approvals".
- Estimating a 12-character German button at +35% when W3C/IBM put 11-20-character strings at 180-200% of the English length.
- Survicate's own NPS help article words the formula backwards ("subtract the percentage of Promoters from the percentage of Detractors"; <https://help.survicate.com/en/articles/4149462-a-comprehensive-guide-to-nps-surveys>). Its worked example (70% − 10% = 60) is correct.

**Core/lib notes (described, not edited).**
- `python -m hundred.admin brief … | head` raises `BrokenPipeError` in `hundred/admin.py` (cosmetic).
- The tests deselected by `-k product` grew between runs (888 → 968) because other categories were being edited in parallel. No product test was affected.

---

## 1. Accessibility Checker vs Stark

**Scenario.** "Audit our sign-up page before release; here's the HTML and our palette."

The input is a full sign-up page with 18 planted defects:
- missing `lang` and an empty `<title>`;
- a logo with no alt text, and `alt="hero.jpg"`;
- an unlabelled `<select>`;
- a phone field with `aria-labelledby` pointing at a missing id;
- a newsletter checkbox reusing `id="email"`, so its `<label for>` names the email field;
- an icon-only close button, an empty `<a href="#">` and an `<input type=image>` without alt;
- a "Click here" link;
- h1→h3 and an empty `<h2>`;
- an untitled captcha iframe;
- a clickable `<div>`;
- `tabindex="3"`;
- `autocomplete="nope"`.

It also has decoys that must *not* be flagged: a home link whose only content is `<img alt="Acme home">`, a submit button named by `<img alt>`, a wrapped label and a `for=` label.

The palette has 12 text/UI pairs and there are 6 touch targets.

**Parity checklist.** Stark's Figma/browser suite, <https://www.getstark.co/figma/>. The HTML rule list is cross-checked against axe-core, <https://github.com/dequelabs/axe-core/blob/develop/doc/rule-descriptions.md>.

| Stark feature (documented) | Status | Why |
|---|---|---|
| Contrast checker (AA/AAA) | MATCHES | `contrast_ratio`: exact WCAG formula; 12/12 pass/fail equal to WebAIM |
| Colour suggestions | MATCHES | `suggest_color`: nearest hue-preserving shade; 7/7 re-verified in WebAIM |
| Vision simulator (protanopia, tritanopia, achromatopsia…) | MATCHES (added) | `simulate_color_blindness`: Machado 2009 matrices; equal to colorspacious; flags pairs that collapse |
| Touch targets (web, iOS, Android) | MATCHES (added platforms) | 2.5.8 / 2.5.5 plus iOS 44pt and Android 48dp |
| Focus order | PARTIAL | positive tabindex, clickable divs and a keyboard walkthrough by reasoning; no visual focus-order annotation |
| Landmarks | PARTIAL | `<main>` and skip link only; no header/nav/section landmark map |
| Alt-text annotations | PARTIAL | missing / filename / too-long alt; no keyword-stuffing check |
| Typography | PARTIAL | only the large-text threshold; no line-height or spacing (1.4.12) checks |
| Live preview in the browser | OUT OF SCOPE | browser extension |
| Continuous scanning of design files, repos and live sites | OUT OF SCOPE | hosted monitoring |

axe-core rules covered after the fix:
- WCAG A/AA: image-alt, label, button-name, link-name, html-has-lang, document-title, duplicate-id-aria, frame-title, select-name, input-image-alt, autocomplete-valid.
- Best practice: tabindex, heading-order, empty-heading.

Not covered: `list` structure. DOM-computed colour-contrast is out of scope because we take colour pairs, not rendered CSS.

**Correctness.**

| Check | Reference | Tool after fix | Before fix |
|---|---|---|---|
| Planted HTML defects | 18 | 18/18, plus the real missing skip link | 14/18: missed broken aria-labelledby, empty heading, autocomplete and the duplicate-id label mix-up |
| False positives | 0 | 0 | 2 (home link and submit button "have no accessible name") |
| #767676 / #777777 / #3B82F6 on white | WebAIM 4.54 / 4.47 / 3.67 | 4.54 / 4.47 / 3.67 | 4.54 / **4.48 / 3.68** |
| #5A7C87 on white (exact 4.4991) | WebAIM 4.49, fails AA | "4.49:1 — FAIL" | **"4.5:1 — FAIL"** |
| 12 pairs, pass/fail | WebAIM | 12/12 | 12/12 |
| Suggested #727780, #69707D/#F3F4F6, white/#178841, #929599, #D73D3D, #597B86, #7198C3 | WebAIM 4.50, 4.52, 4.53, 3.00, 4.54, 4.56, 3.00 | same | same |
| Deuteranopia of #D73D3D / #178841 | colorspacious #908238 / #7C7346 | same | tool didn't exist |
| Targets: 16×16 (4px gap), 20×20 (8px gap), 18×18 (2px gap) | 2.5.8: fail / pass (20+8 ≥ 24) / fail | same | same |

**Deliverable (excerpt).**
```
# Accessibility audit — Acme sign-up — target WCAG 2.2 AA
**Verdict:** 9 blockers · 6 major · 4 minor — a keyboard/screen-reader user can NOT complete sign-up
## Blockers
| 1 | email + newsletter checkbox (id="email" ×2) | 1.3.1/4.1.2 | label "Send me product news" names the EMAIL field; checkbox unlabelled | unique ids; <label for="email">Email</label> |
| 2 | <select id=country> | 1.3.1/4.1.2 | no label | <label for="country">Country</label> |
| 3 | phone <input> | 4.1.2 | aria-labelledby="phone-lbl" → no such id | visible <label for> |
| 4 | "Continue" <div onclick> | 4.1.2/2.1.1 | not focusable, no role | <button type="submit"> |
| 5 | close ×, <a href="#">, <input type=image> | 4.1.2/2.4.4/1.1.1 | no accessible name | aria-label="Close"; delete empty link; alt="Continue" |
| 6 | logo <img> | 1.1.1 | no alt | alt="Acme" |
## Major
tabindex=3 on password (2.4.3) · captcha iframe untitled (4.1.2) · no lang (3.1.1) · empty <title> (2.4.2) · alt="hero.jpg" (1.1.1) · autocomplete="nope" → "email" (1.3.5)
## Contrast table
| Pair | Ratio | Normal | Large | UI 3:1 | Nearest passing |
| placeholder #9CA3AF/#FFF | 2.53:1 | fail | fail | fail | #727780 (4.50) |
| helper #6B7280/#F3F4F6 | 4.39:1 | fail | pass | pass | #69707D (4.52) |
| CTA #FFF on #22C55E | 2.27:1 | fail | fail | fail | bg #178841 (4.53) |
| error #EF4444/#FFF | 3.76:1 | fail | pass | pass | #D73D3D (4.54) |
| caption #5A7C87/#FFF | 4.49:1 | fail | pass | pass | #597B86 (4.56) |
| input border #D1D5DB · focus ring #93C5FD | 1.47 · 1.80 | — | — | fail | #929599 · #7198C3 (3.00) |
Colour-only meaning: new error #D73D3D and success #178841 are luminance twins (1.0:1) — identical in greyscale. Add ✕/✓ icons (1.4.1).
Targets: close icon 16×16 and checkbox 18×18 fail 2.5.8 → 24×24 hit area.
Automated checks find roughly 30-40% of WCAG issues; this audit is not a conformance certificate.
```

**Honest gaps.**
- We lint pasted markup. We can't compute contrast from rendered CSS, hover or focus states, or images of text.
- Colour-blindness "collapse" uses a CIE76 ΔE < 10 threshold. That is a heuristic, not a WCAG number.
- Suggested colours land exactly on the threshold (4.50, 3.00) with no safety margin. Designers may want one.

---

## 2. Feedback Analyzer vs Survicate

**Scenario.** "Here are last quarter's 80 NPS responses (score, plan, comment). What's our NPS, what drives detractors, and what should we fix first? Last quarter was 22."

Input: 80 hand-written responses.
- 34 promoters, 24 passives and 22 detractors.
- Plans: Pro 47, Starter 27, Enterprise 6.
- 67 have comments, and every comment is hand-labelled with its true theme(s).

**Parity checklist.** Sources: <https://help.survicate.com/en/articles/4149462-a-comprehensive-guide-to-nps-surveys> and <https://survicate.com/software/ai-survey/>.

| Survicate feature (documented) | Status | Why |
|---|---|---|
| NPS calculation with promoter/passive/detractor split | MATCHES | `score_survey`, plus a 95% margin of error. Survicate documents no margin or significance |
| Segment / filter by attributes (plan, tier) | MATCHES | per-segment NPS with an n < 30 "don't quote" guard |
| AI grouping of open text into topics | MATCHES | `count_themes`: 12-theme taxonomy plus custom themes; counts responses, not mentions |
| Sentiment | PARTIAL | lexicon score per theme; not validated against labels |
| Trends over time | PARTIAL | two-period change tested against the margin of the difference; no multi-period series |
| Ask AI questions about the feedback | MATCHES | the host AI reads the tagged rows |
| Survey collection / distribution | OUT OF SCOPE | we analyse, they collect |
| Insights Hub / dashboards | OUT OF SCOPE | hosted system of record |

**Correctness.**

| Check | By hand | Tool | Before fix |
|---|---|---|---|
| NPS, MoE | (34 − 22)/80 = 15.0. √((.425 + .275 − .15²)/80) × 1.96 = ±18.0 | 15.0 ±18.0 | same |
| Pro / Starter / Enterprise | 25.5 ±23.2 (n=47, reportable) / 3.7 ±29.9 (n=27, not) / −16.7 (n=6, not) | same | same |
| Change vs 22 | −7 against ±25.5 (18.0 × √2) → noise | noise, ±25.5 | noise, but tested against ±18.0. A +8 move on n=400 (±7.7 per period, ±10.9 for a change) was called **"real"** |
| Theme precision / recall (strict single-label) | hand labels | 0.87 / 0.99 | 0.82 / 0.89. "export" → integrations (3 FP); missed "costs", "load", "pricey", "cheaper", "simplest" |
| Bugs driver | mean 2.8 vs 7.63 → −4.83; 5 of 20 commented detractors = 25% | −4.83, 25% | same |
| Fix priority = share × severity × reach / 9 | performance 14/67·2·3/9 = 13.9; export 5/67·3·3/9 = 7.5 | same | same |

**Deliverable (excerpt).**
```
# Feedback readout — Q3 2026 (n=80, 67 comments)
**NPS: 15 (±18)** — was 22 (Δ −7, within noise; a change needs > ±25.5) · Promoters 42.5% · Passives 30% · Detractors 27.5%
By segment: Pro 25.5 (±23, n=47) · Starter n=27 and Enterprise n=6 — not reported (n < 30)
## What's driving detractors
| Theme | Responses | Share | Mean score (with / without) | Detractor rate |
1. Performance on big boards — 14 (20.9%) — 5.71 vs 7.68 — 57% (40% of detractors)
   "Takes 10 seconds to load a project, my team gave up waiting." (Pro, 5)
2. Export crashes / truncation — 5 (7.5%) — 2.8 vs 7.63 — 100% (25% of detractors)
   "Export to CSV crashes the app every single time." (Pro, 0)
3. Pricing: the Starter→Pro step — 9 (13.4%) — 6.22 vs 7.43 — 44%; 8 of 9 are Starter
## Top praise (say this in marketing)
- Support — 8 responses, mean 9.5 · Ease of use — 12, mean 9.2 · Templates — 6, mean 9.5
## Fix list (ranked)
| 1 | Board load + drag performance | performance | 8 of 20 | 2 | Eng: platform |
| 2 | Fix CSV/PDF export crashes | bugs | 5 of 20 | 3 | Eng: reporting |
| 3 | Calendar/Slack/Salesforce integrations | integrations | 3 of 20 | 2 | PM: integrations |
## Method
Tagged 64/67 comments (4.5% untagged); segments under n=30 not reported.
```

**Honest gaps.**
- Keyword tagging still produces defensible-but-double labels, e.g. "Missing a Salesforce integration" → integrations + missing_feature. It also makes rare literal errors: "adds up fast" → performance.
- The sentiment lexicon is unvalidated.
- The change test approximates the previous period's variance with this period's.

---

## 3. Roadmap Prioritizer vs Productboard

**Scenario.** "Rank these 12 backlog items with RICE, classify the 6 we surveyed with Kano, and tell me what fits in Q4. We have 4 engineers × 12 weeks at 75% focus."

Input:
- 12 items with reach, impact, confidence and effort. Planted traps: confidence 30%, confidence 100% with and without evidence, and a 0.4-week item.
- 6 features × 12 Kano answer pairs. One feature has 25% reverse and 17% questionable answers.
- A MoSCoW draft whose Must items take 62.5% of capacity.

**Parity checklist.** Source: <https://support.productboard.com/hc/en-us/articles/7400189831955-Model-common-prioritization-frameworks-in-Productboard>, which documents RICE, WSJF, ICE and Value/Effort via formula fields, plus drivers.

| Productboard feature (documented) | Status | Why |
|---|---|---|
| RICE formula | MATCHES | `rice_score` plus flags and ±30% tie tiers |
| WSJF | MATCHES (added) | `framework_score` method "wsjf" |
| ICE | MATCHES (added) | method "ice" |
| Value for effort | MATCHES (added) | method "value_effort" |
| Drivers with weights (weighted scoring) | MATCHES (added) | method "weighted": driver scores 0-5 × weights |
| Custom formula fields | PARTIAL | four fixed formulas plus weighted drivers; no arbitrary expressions |
| Roadmap views, linking feedback to features | OUT OF SCOPE | system of record |

Beyond Productboard's documented frameworks: Kano classification, Ulwick opportunity scores, a DSDM capacity check and rank-fragility tiers.

**Correctness.**

| Check | By hand | Tool | Before fix |
|---|---|---|---|
| RICE × 12 | e.g. PDF fix 7000·0.5·1/1 = 3500; Slack 6000·1·0.8/2 = 2400; SSO 600·3·0.8/6 = 240 | all 12 equal | same |
| Kano (published table, mode, ties M>O>A>I) | SSO M (.17/−.83), Dark mode A (.75/−.08), Recurring O (.67/−.67), AI summaries A (.57/0.0), PDF fix M (.25/−.92), Shortcuts I | 6/6 equal | equal, but AI summaries' Worse printed as "−0.0" |
| Capacity | 36 × 0.8 = 28.8 plannable; Must 22.5/36 = 62.5%; demote 22.5 − 21.6 = 0.9; cut 40.9 − 28.8 = 12.1 | same | same |
| Final plan (Must 14.5) | 40.3% Must; Must+Should 25.9 ≤ 28.8 | "fits (Coulds are the buffer)" | "**does not fit**": Could items counted against the plannable weeks as well as the 20% contingency, which double-counts it |
| WSJF | SSO (13+13+5)/8 = 3.88; Audit (5+8+8)/3 = 7.0 | same | tool didn't exist |

**Deliverable (excerpt).**
```
# Roadmap — Q4 2026 (36 person-weeks, goal: stop losing Pro accounts to export/perf pain; unblock Enterprise)
## Ranked
| Rank | Item | RICE | Kano | MoSCoW | Effort | Cum. | Note |
| 1 | PDF export fix | 3500 | Must-be | Must | 1 | 1 | evidence: 38 tickets |
| 2 | Custom fields in exports | 1867 | — | Must | 1.5 | 2.5 | tier 2 |
| 3 | SSO (SAML) | 240 | Must-be | Must | 6 | 8.5 | moved by judgement (Kano must-be, ENT deals) |
| 4 | Slack notifications | 2400 | — | Must | 2 | 10.5 | tier 2 |
| 5 | Recurring tasks | 2000 | Performance | Must | 4 | 14.5 | tier 2 |
| 6 | Keyboard shortcuts | 2000 | Indifferent | Should | 0.4 | 14.9 | bundle with quick wins |
| 7 | Audit log | 213 | — | Should | 3 | 17.9 | WSJF #1 (7.0): compliance deadline |
| 8 | Gantt dependencies | 313 | — | Should | 8 | 25.9 | 50% confidence |
— cut line at 28.8 pw (Must 40%, Should 32%, contingency 20%) —
| 9 | Bulk CSV import · 10 Dark mode (Attractive) | 1067 · 1125 | | Could | 5 | | contingency |
## Why this order
- RICE tiers at ±30%: {PDF fix} > {Slack, Recurring, Shortcuts, Custom fields} > {Dark mode, CSV} > {rest}. Inside a tier = tie.
## Moved by judgement
- SSO: RICE rank 11 → 3 (Kano must-be for 8/12; Enterprise pipeline) · Gantt: Must → Should (Must was 62.5% > 60%)
## Cut this cycle
- AI task summaries → research spike (30% confidence; 25% reverse) · Mobile offline mode → next cycle (10 pw, 50% confidence)
```

**Honest gaps.** No arbitrary formula builder. Fragility tiers test each item's own ±30%, not joint uncertainty.

---

## 4. Interview Synthesizer vs Condens

**Scenario.** "Synthesize these 6 discovery interviews about reporting and approvals. What are the themes, how strong is the evidence, and do we need more sessions?"

Input: 6 interviews (P1, P2, P5 SMB; P3, P4, P6 ENT) of hand-written notes with recurring pains:
- a weekly report rebuilt by hand in 4 of 6 interviews;
- approvals lost in email in 3 of 6;
- permissions in 2 of 6;
- one hypothetical ("I would probably use it") and one switching signal (evaluating Monday.com).

It also includes 19 hand-tagged observations as the clustering ground truth.

**Parity checklist.** Sources: <https://condens.io/analysis/> and <https://condens.io/ai/>.

| Condens feature (documented) | Status | Why |
|---|---|---|
| Highlight and tag quotes | MATCHES | `extract_signals` ranks quotes; the host AI tags them; `tag_frequency` counts interviews, not mentions |
| AI-suggested tags | MATCHES | the host AI proposes tags (playbook step 2) |
| Auto-clustering / affinity mapping | MATCHES (fixed) | `cluster_observations`: pairwise F1 0.86 vs ground truth |
| Clustering by auto-detected sentiment | PARTIAL | the host AI judges sentiment; no tool support |
| AI session summaries | MATCHES | the host AI, with evidence counts attached |
| Participant properties / segments | MATCHES | segment splits ("SMB 3/3, ENT 1/3") and evidence-strength rules |
| Highlight reels, transcription | OUT OF SCOPE | video |
| Repository search across projects | OUT OF SCOPE | hosted storage |

Beyond Condens's documented features: a saturation check (new themes per session) and interview-vs-mention counting.

**Correctness.**

| Check | By hand | Tool | Before fix |
|---|---|---|---|
| Interviews per tag | report 4 (7 mentions), approvals 3 (6), permissions 2 (3), setup 1, switching 1 | same; "strong" / "strong" / "moderate" | same |
| Segment split, report | SMB 3/3, ENT 1/3 | same | same |
| New themes per interview | 2, 1, 1, 0, 0, 1 → not saturated; run 1-2 more | same | same |
| Clustering, pairwise F1 | 5 true groups | 0.86 (4 clusters) | 0.58 (10 clusters: 6 approval notes split across 5 clusters because "approve/approved/approvals" stemmed differently) |
| Signal sentences, scenario | 26 | 26, hypothetical flagged | 18 (missed "problem", "drives me crazy", "lose track", "every Friday", "three hours") |
| Signal sentences, **unseen** notes | 12 | **5** | not run |

**Deliverable (excerpt).**
```
# Research synthesis: reporting & approvals discovery — 2026-09-27
**Sessions:** 6 · **Segments:** SMB (3), ENT (3) · **Saturation:** not yet — last 3 sessions added 0, 0, 1 new themes; run 1-2 more (ENT)
**Research question:** Where do agency and PMO teams lose time between doing the work and getting it signed off?
## Top findings (ranked by evidence)
### 1. Teams rebuild the same weekly status report by hand because exports lose formatting   Evidence: strong — 4/6, SMB 3/3, ENT 1/3
- Observation: 3-6 hours a week copying exports into Excel/slides, every Friday or Monday
- "Every Friday I spend about three hours rebuilding the client status report in Excel because the export loses all the formatting." — P1, SMB
- "My coordinators spend maybe 6 hours a week rebuilding it by hand from exports." — P4, ENT
- Opportunity: How might we make the weekly client report generate itself from the boards?
### 2. Approvals live in email and Slack, so teams lose track and cannot prove who approved what   Evidence: strong — 3/6, ENT 2/3, SMB 1/3
- "I cannot prove who approved what during an audit." — P3, ENT
- "A release slipped a week because an approval was sitting in someone's inbox." — P6, ENT (now evaluating Monday.com)
### 3. Permissions are configured board by board, slowing set-up and leaking data   Evidence: moderate — 2/6, ENT only
## Signals to watch (weak evidence)
- New-client board set-up takes two days — 1/6, SMB · AI weekly summary — hypothetical only (P5), not evidence
## Recommended decisions
| 1 | Build auto-generated weekly client report | Finding 1 | High |
| 2 | PRD for approvals with an audit log | Finding 2 | Medium-high (ENT-weighted) |
## What we still don't know
- Would SMBs pay for approvals? → 3 SMB sessions focused on sign-off
```

**Honest gaps.**
- `extract_signals` is a keyword net. On notes it was never tuned on it found 5 of 12 signal sentences ("reps forget to log calls" has no keyword). The playbook now says so and requires the AI to read every interview in full.
- The 26/26 scenario score was reached by widening the patterns on that same scenario, so it is not an independent measure.
- The clustering threshold (0.34) was chosen on this scenario's ground truth.

---

## 5. PRD Writer vs ChatPRD

**Scenario.** "Here's my half-finished PRD for Client Approvals. Score it, fix it, and get it ready for engineering."

The draft has:
- 6 sections, with edge cases, dependencies, risks, rollout and open questions missing, and no non-goals;
- requirements with "fast", "etc", "and/or", a two-behaviour sentence, missing modal verbs and 67% MUST;
- metrics "Approval engagement goes up" and a time-to-decision metric with an unknown baseline "by Q4 2026";
- a generic-role user story with a circular "so that", a story with no "so that" and no criteria, and one good story (decoy).

**Parity checklist.** Sources: <https://www.chatprd.ai/llms.txt>, <https://www.chatprd.ai/docs/writing-documents> and <https://www.chatprd.ai/docs>.

| ChatPRD feature (documented) | Status | Why |
|---|---|---|
| Draft PRDs / specs | MATCHES | playbook plus a 12-section output template |
| Improve an existing doc (edit / rewrite) | MATCHES | audit-first procedure; the rewritten draft goes from 48 to 100 |
| Turn research and meeting notes into specs | MATCHES | the scenario PRD cites the interview evidence (3/6, P3 and P6 quotes) |
| Connect product docs to AI coding tools via MCP | MATCHES | delivered natively over MCP; files to Notion/Confluence, tickets per MUST in Linear/Jira when connected |
| Templates (default, custom, team) | PARTIAL | one built-in template; the host AI can follow a user-supplied one, but nothing is stored |
| Review product strategy | PARTIAL | Amazon working-backwards and goal→metric checks only |
| Document versioning | OUT OF SCOPE | storage |
| Shared team context / projects | OUT OF SCOPE | workspace |

ChatPRD documents no scored completeness audit, ambiguity lint or metric validation. These deterministic checks are where we go beyond it.

**Correctness.**

| Check | By hand | Tool | Before fix |
|---|---|---|---|
| Completeness score | problem 14 + requirements 14 + half of users 10, goals 10, metrics 12, ux 8 (5 + 5 + 6 + 4) = 48 | 48, 6 missing sections, no non-goals | same |
| Requirement defects (6 lines) | no modal ×2, compound ×2, and/or, fast, etc, MUST 66.7% | all | missed "gets an email **and can** approve" (compound) |
| Metric defects | vague name, no baseline ×2, no source ×2, no guardrail | all | also rejected "**by Q4 2026**" as "no concrete timeframe" (false positive) |
| Story defects | generic role, circular "approve → approved", ambiguous "easy", missing so-that, no criteria | all | missed the circular story ("approve" ≠ "approved") |
| False positives | 0 | 0 | 3 (Q4 2026; "no observable behaviour" on "request approval" and "configure chains") |
| Final PRD | ≥ 80 to ship | 100, 8 numbered requirements | — |

**Deliverable (excerpt).**
```
# PRD: Client Approvals            Completeness: 100/100 · Status: Draft · Owner: PM
## 1. Problem   Account managers and PMO leads need client/compliance sign-off to ship, but approvals live in email and Slack,
   which costs a week of slip on at least one release (P6), a Friday afternoon of chasing (P2) and audit risk (P3). 3/6 interviews.
## 3. Goals / Non-goals   G1 median request→decision 3.0 → 1.0 day · G2 auditable record of approver, version, timestamp
   Non-goals: e-signature with legal effect; chains > 3 steps; Slack-native approve buttons; purchase approvals
## 4. Success metrics
| Median request-to-decision (primary) | 3.0 days | 1.0 day | 90 days after launch | approvals_events |
| Support tickets tagged approvals (guardrail) | 14/mo | ≤ 14/mo | 90 days after launch | Zendesk tag |
## 5. Requirements
| FR-001 | MUST | A member must be able to request approval on any task or file and pick 1-3 approvers. | approvers notified ≤ 60 s |
| FR-002 | MUST | The approver must receive an email with a signed link valid for 14 days. | expired link shows resend |
| FR-003 | MUST | A guest approver must be able to approve or reject without creating an account. | decision stored with email + IP |
| NFR-001 | MUST | The guest approval page must reach P95 load ≤ 2.0 s on 4G. | synthetic monitoring |
| FR-007 | COULD | Admins could configure 2-3 step sequential approval chains. | step 2 notified after step 1 |
## 12. Open questions
| 1 | Do Enterprise customers need SSO for internal approvers in v1? | PM | 2026-10-15 |
| 2 | Is guest IP storage acceptable under our DPA? | Legal | 2026-10-20 |
```

**Honest gaps.**
- Section detection is keyword/heading based, so a well-written section under an unusual heading can be missed.
- The body-length check counts words, not quality.
- Custom templates aren't stored.

---

## 6. UX Writer vs Frontitude UX Writing Assistant

**Scenario.** "Lint our auth, settings and billing strings (24) for length, tone and consistency, rewrite what fails, and tell me what will break in German."

Planted problems:
- "Log In" vs "Sign in to Acme";
- "E-mail address" vs "email";
- "Account Preferences" vs "Settings";
- "Remove account" vs "Deleting your account";
- "Logout" used as a verb;
- "Save Your Changes!";
- "Are you sure?" / "Yes";
- "Error 401: Invalid credentials supplied.";
- "Your account has been locked." with no next step;
- "Oops! Something went wrong.";
- a 137-character tooltip full of jargon.

Five correct strings are decoys.

**Parity checklist.** Sources: <https://write.frontitude.com/assistant-guides/team-guidelines>, <https://write.frontitude.com/assistant-guides/the-rewrite-feature> and <https://www.frontitude.com/guides/using-the-new-ux-writing-assistant>.

| Frontitude feature (documented) | Status | Why |
|---|---|---|
| Terminology block/allow lists | MATCHES (added) | `check_consistency(glossary={banned: preferred})` plus built-in synonym groups |
| Length limits (characters/words) | MATCHES | per-component budgets for 19 component types |
| Casing enforcement | MATCHES (fixed) | sentence case; Title Case detection now catches "Log In" |
| Component-linked rules | MATCHES | budgets and punctuation per component (button, error, toast…) |
| Voice and tone guidelines | PARTIAL | the playbook infers a 3-word voice; no stored team guideline |
| Rewrite with a 0-100 compliance score | PARTIAL | the host AI rewrites; `lint_error_message` scores errors 0-100; other strings get pass/fail |
| Translation memory | OUT OF SCOPE | storage |
| Figma plugin | OUT OF SCOPE | plugin |

**Correctness.**

| Check | Expected | Tool | Before fix |
|---|---|---|---|
| Planted problems | 15 | 15/15 | 11/15: missed "Log In" Title Case, Remove vs **Deleting**, "Logout" as a verb, "Are you sure?" |
| False positives on the table | 0 | 0; 5/5 decoys clean | 5: save↔"update" conflict; "email address" and "mail" counted as extra variants; "Your card has **expired**" read as error code "EXPIRED"; "has been locked" had "no statement of what happened"; "went **wrong**" counted as blame |
| Error scores | creds 10, locked 70 (what ✓, how ✗), oops 20, expired-card 100 | same | expired-card 90, locked 40 |
| "Save changes" (12 chars), container 16 | real: de 20, fr 29, fi 18 characters → all overflow | overflow de, fi; at risk fr | "fits" in fr; de estimated 17 |
| 18 real translations (6 strings × de/fr/fi) | real lengths | budget too short on 2/18 | typical estimate too short on 9/18 |

**Deliverable (excerpt).**
```
# Copy review: auth, settings, billing
Voice: plain, calm, direct · Case: sentence · Locale: en-US · Localised: yes (budget −25%)
| Key | Component | Before | After | Why |
| auth.cta | button | Log In | Sign in | sentence case; one term: sign in/out |
| settings.title | heading | Account Preferences | Settings | one concept = one word; sentence case |
| settings.save | button | Save Your Changes! | Save changes | verb+object, sentence case, no ! |
| settings.delete | button | Remove account | Delete account | "delete" everywhere (body says deleting) |
| settings.delete.confirm.title | dialog_title | Are you sure? | Delete your account? | name the action |
| settings.delete.confirm.cta | button | Yes | Delete account | button names the consequence |
| settings.logout | button | Logout | Sign out | verb form; pairs with Sign in |
| auth.email.label | label | E-mail address | Email address | "email" standard |
| settings.2fa.tooltip | tooltip | Two-factor authentication utilizes a time-based… | Enter the 6-digit code from your authenticator app. | 137 → 51 chars, no jargon |
## Error messages
| auth.error.creds | Error 401: Invalid credentials supplied. | That email and password don't match. Check them or reset your password. |
| auth.error.locked | Your account has been locked. | Your account is locked after 5 failed sign-ins. Reset your password to unlock it. |
| billing.error.card | Oops! Something went wrong. | We couldn't charge your card. Check the details or use another card. |
## Consistency fixes
- "Log In" (1) / "Sign in" (1) → Sign in; "Logout" → Sign out · "E-mail" → email · Preferences → Settings · Remove/erase → Delete
## Localisation risks
- settings.save "Save changes" (12 ch) in a 16-ch button → de/fi overflow (typical 17, budget 23), fr at risk (budget 18). Widen to 24 ch.
```

**Honest gaps.**
- The localisation numbers are length heuristics, not translations. The W3C/IBM budget overshoots real translations on average (mean absolute error 7.7 characters vs 4.7 for the typical estimate). We keep both numbers and call the gap between them "at risk".
- Synonym groups are a fixed list, and a team glossary is needed for product nouns.
- Readability is Flesch-Kincaid on very short strings, so the grade is noisy.

---

## 7. Pitch Deck Coach vs PitchBob

**Scenario.** "Review our 12-slide seed deck (ChairTime, an AI front desk for dental practices). We're raising $2.5M on a $12M post-money SAFE with a 10% pool. Burn is $140k/month growing 3%/month, and we have $300k in the bank. Our market slide says $12B."

Planted issues:
- claim-style titles with no section keyword;
- a top-down "$12B, we only need 1%" market slide;
- a bottom-up TAM under $1B (135,000 practices × $4,800);
- runway under 18 months once burn grows;
- "Why now" after the market slide;
- a label-only "Product demo" title.

**Parity checklist.** Source: <https://pitchbob.io/products/ai-pitch-deck-feedback> ($29.90).

| PitchBob feature (documented) | Status | Why |
|---|---|---|
| Slide-by-slide analysis | MATCHES | `slide_density` plus the host AI's per-slide notes |
| Market size assessment | MATCHES | `market_size`: bottom-up TAM/SAM/SOM, <$1B and top-down-mismatch flags |
| Idea, team, competition, technology, advantages, risks | MATCHES | playbook step 5: investor objections (why now, incumbent feature, wedge, unit economics, what kills it) |
| Business model | MATCHES | canonical slide check plus the unit-economics objection |
| Financial metrics | PARTIAL | raise, dilution and runway maths; no LTV/CAC or projection model (CAC payback is quoted, not checked) |
| Investor readability score | PARTIAL | words/bullets/label-titles/numbers per slide; no single score |
| Overall 1-10 rating | MISSING | deliberately not produced: a number with no rubric would be made up |
| Benchmark vs 15,000 decks | OUT OF SCOPE | proprietary dataset |

**Correctness.**

| Check | By hand | Tool | Before fix |
|---|---|---|---|
| TAM / SAM / SOM | 135,000 × 4,800 = 648.0M; × 35% = 226.8M; × 3% = 6.804M; 1,417.5 → 1,418 customers; 283.5/yr | same | same, but the ratio was printed as "**0.1×** the top-down figure" (actually 5.4%) |
| Dilution | 2.5/12 = 20.83%; founders 100 − 20.83 − 10 = 69.17%; effective pre-money 9.5M − 1.2M = 8.3M | same | same |
| Runway (cash 2.8M, 3% growth) | 140k·(1.03^m − 1)/0.03 = 2.8M → m = ln 1.6 / ln 1.03 = 15.90 mo; ends Feb 2028 | 15.9, 2028-02-01 | no `existing_cash` parameter, so the $300k was ignored; advice was "raise $2,520,000 − 2.5M more" with **no burn growth** |
| 18-month need | 140k·(1.03^18 − 1)/0.03 = $3,278,021 → raise $478,021 more | same | tool didn't compute it |
| Structure | 12/12 canonical slides | 12/12 with `slide_types`; the keyword fallback maps 11/12 and warns | 10/12: **"missing problem, solution"**, so the tool's headline verdict was wrong |

**Deliverable (excerpt).**
```
# Deck review: ChairTime — seed raise of $2.5M
**The one change:** replace "$12B market, we only need 1%" with the bottom-up number — and be honest that it's $648M.
## Structure (score 12/12 canonical slides)
Missing: none · Out of order: Why now (7) after Market (6); Traction (4) before Product — fine, it's your strongest card · Length: 12 (target 10-15)
Proposed order: Title · Problem · Solution · Why now · Market · Product · Business model · Traction · Competition · Team · Ask · Use of funds
## Slide-by-slide
| 5 | Product demo | "Books a new patient in 40 seconds, no human" | label title, no number |
| 6 | A $12B dental software market | "135,000 US practices × $4,800 = $648M TAM" | top-down 1% claim; bottom-up is 5.4% of it |
| 9 | Competition | "Weave and NexHealth remind; we book" | add one number (e.g. booking rate vs voicemail) |
## Numbers
Market: TAM $648M (bottom-up) / SAM $226.8M (35% on cloud PMS) / SOM $6.8M (3% in 5 yrs = 1,418 practices, ~284/yr) · top-down $12B not reconciled
Raise: $2.5M at $12M post → 20.8% dilution (+10% pool; effective pre $8.3M) · Runway 15.9 months with the $300k in the bank, to Feb 2028
→ below 18 months: 18 months on this burn path needs $3.28M — raise ~$3.0M or hold burn growth at 0% (then 20 months)
## Objections to prepare for
1. "Sub-$1B TAM — how is this venture scale?" → expansion: multi-location groups + orthodontics/vets (slide 6)
2. "Isn't this a Weave feature?" → they remind, we book and back-fill; 22% MoM growth with 1.1% churn (slide 9)
Valuation and market figures are planning estimates, not advice; verify inputs before sharing with investors.
```
(Flat-burn check: 2.8M / 140k = 20.0 months.)

**Honest gaps.**
- No LTV/CAC or 3-year projection maths, and no single "investor score".
- The keyword fallback still misses slides like "Our AI books…" (solution). The playbook now makes the AI classify slides itself.
- Market inputs (135,000 practices, 35% serviceable) are the founder's, not verified.
