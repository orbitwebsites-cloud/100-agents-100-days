# Marketing agents: parity evaluation

Evaluated 2026-09-27. There are 10 agents in `hundred/agents/marketing/`. Competitor prices come from `marketing/pricing_research/sales_marketing.md` unless a row says otherwise.

**Method.** For each agent:
1. Build a parity checklist from the comparable's *documented* capabilities for the overlapping job, citing the URL.
2. Write a realistic customer request with invented data.
3. Run `python -m hundred.admin brief <slug>` and follow the playbook step by step, calling every prescribed tool with `hundred.admin run`.
4. Recompute every number the deliverable relies on, independently of our code. The tools used were scipy 1.17, statsmodels, numpy busday functions, `zoneinfo`, hand arithmetic, and published reference values.

Each scenario is replayable in `tests/scenarios/test_marketing.py`, which asserts the independently verified values.

**Scoring.**
- Checklist items are MATCHES, PARTIAL, MISSING or OUT OF SCOPE. OUT OF SCOPE covers publishing, sending, ad accounts, data sets, crawling and storage.
- The score counts MATCHES out of in-scope items.
- "Plain AI would get wrong" lists only things **observed in this run**, either in my own first drafts (acting as the customer's AI) or in the pre-fix tool output. Nothing in it is hypothesised.

## Overview

| Agent | Comparable & price (monthly) | Checklist (MATCHES / in-scope) | Correctness rows matching independent recomputation | Verdict | Fixes made |
|---|---|---|---|---|---|
| ab-test-analyst | Evan Miller's A/B Tools (free, $0; the market price for this math per the research file) | 6/8 (+1 PARTIAL) | 12/12 | **ABOVE** | Exact Pocock boundaries and peeking false-positive rates for 1–50 looks (the old table stopped at 10, then fell back to Bonferroni). Per-arm Wilson CIs. Absolute-MDE input. Stop date. One-sided Welch and per-arm mean CIs |
| ad-copy-lab | Anyword Starter $49 ($39 annual) | 4/7 (+3 PARTIAL) | 6/6 | **AT PAR** | The email spam lexicon was being applied to ads ("No credit card", "Free trial" penalised). Claim-risk lines can no longer grade "ship". Pin advice now follows Google's guidance. Keyword/brand headlines count as "relevance", not "generic". Break-even CPC in the loss verdict |
| brand-voice | WRITER Starter ~$39 (3p; $29 annual) | 4/9 (+4 PARTIAL) | 4/6 exact, 2 differ only by lib tokenizer (hyphens) | **AT PAR** (core); below WRITER on style-rule breadth | Added use-carefully terms and an inclusive-language check. Contractions are no longer "signature words" |
| email-campaign | Mailchimp Standard $20 | 5/6 (+1 PARTIAL) | 5/6 exact, 1 differs only by lib tokenizer (URLs) | **AT PAR** | `{{name\|fallback}}` merge tokens were invisible to the scanner, so misspelled tokens passed. Added an ALL-CAPS-word check and a >3 punctuation check. Subject length now counts merge tokens at rendered length |
| landing-page-cro | Unbounce Build $99 (+ free Landing Page Analyzer) | 4/7 (+2 PARTIAL) | 6/6 | **AT PAR** | Headlines, bullets and buttons were merged into one "sentence", which inflated the reading grade (a grade-A hero failed "readable"). The "google ads:" channel label counted as message-match words |
| launch-planner | Jasper Pro $69 (Campaign Brief agent + Product Launch Campaign app) | 5/6 (+1 PARTIAL) | 9/9 | **ABOVE** (planning) | Product Hunt 12:01 AM PT used a month-based DST rule (wrong in early March and early November). It now uses the real US rule, checked against `zoneinfo` for 2024–2030 |
| marketing-budget | HubSpot Marketing Hub Pro $800 (3 seats; campaign budget is Pro+) | 3/5 (+2 PARTIAL) | 8/8 (after fixes; 3 rows were wrong before) | **ABOVE** | The break-even month was never reported as month 1. Added payback of the budget's own cohort. Minimums were *added on top of* weight shares; the allocation is now proportional-with-bounds. Steady state now uses the inflated CAC. The playbook now floors proven channels |
| persona-builder | SurveyMonkey Premier $139 (annual; crosstabs are a paid feature) + Semrush Persona (free template) | 5/6 (+1 PARTIAL) | 5/5 | **ABOVE** | Cross-tab now has column % and % of total, plus cell-level significance (adjusted residuals). JTBD lowercased "I" ("When i close…"). The job story mixed persons ("Maya wants… costs me") |
| positioning-strategist | Jasper Pro $69 (Comparison Brief agent) | 3/5 (+1 PARTIAL) | 4/4 | **AT PAR** | The Moore statement produced "who … who …" whenever the target had the "who" clause its own lint asks for. "X for Y" line was missing its article |
| press-release | Semrush AI PR Toolkit Base $149 (annual) | 5/6 (+1 PARTIAL) | 5/6 exact, 1 differs only by lib tokenizer (accents, $6.5, U.S.) | **AT PAR** | AP state rule was pre-2014: it demanded abbreviations in body text. It now abbreviates in datelines, spells out in body, handles the 30 stand-alone dateline cities, and flags postal codes. ET DST rule fixed. Oxford-comma false positive on "Austin, Texas, and Denver" removed |

Correctness counts are rows of each agent's correctness table below. A row can hold several values; every one of them is asserted in `tests/scenarios/test_marketing.py`.

**Issues outside my folder (not edited, reported):**
- `hundred/lib/text.py` `WORD_RE = [A-Za-z0-9]+` splits any non-ASCII word. "cafés" becomes "caf" and "s", "José" becomes "Jos". It also splits "$6.5", "U.S." and hyphenated words into several tokens.
  - In the press scenario the lede is 30 words by whitespace count, but the tool counts 34. The release is 307 words, counted as 326, and the pitch 120, counted as 127.
  - A genuine 33-word lede with two accented names would be flagged as over 35.
  - The same inflation feeds every word-based metric: brand-voice rates, FK grade and email word bands.
  - Suggested fix: `[^\W_]+(?:['’][^\W_]+)*` with `re.UNICODE`, and keep decimals and abbreviations together.
- `hundred/lib/dates.py` has no holiday calendar. Every "business day" in launch-planner, press-release and email-campaign skips weekends only unless the AI passes `holidays` / `avoid_dates`. The playbooks tell it to, but a US federal-holiday default would remove the reliance on the AI remembering.

---

## 1. ab-test-analyst: A/B Test Analyst

**Comparable.** Evan Miller's A/B Tools are the free, respected reference that the research file names as the direct substitute. The sample-size inputs were read from the page source: `defaults.js` sets a 20 % baseline, 5 pp absolute MDE, α 0.05 and power 0.8. `sample-size-fixed.js` holds `num_subjects`, which uses baseline variance under H0.

**Scenario.** "Checkout redesign, 50/50 split, ran 14 days from 2026-09-14 and we looked at the dashboard every day. Control 18,240 visitors / 612 orders; variant 18,106 / 689. AOV control $84.20 (SD 61.5, n 612), variant $81.90 (SD 58.8, n 689). We planned to detect +10 %. 2,600 visitors a day. Did we win?"

**Parity checklist**

| # | Documented capability (source) | Status | Why |
|---|---|---|---|
| 1 | Sample size per variation from baseline, MDE, power, α ([sample-size](https://www.evanmiller.org/ab-testing/sample-size.html)) | MATCHES | `sample_size`, plus duration and stop date. At Evan Miller's own default it returns 1,094 vs his 1,030. A 400k-run simulation of the pooled z-test gives **80.0 % power at 1,094 and 77.8 % at 1,030**, so ours delivers the stated power |
| 2 | MDE as absolute or relative ([sample-size](https://www.evanmiller.org/ab-testing/sample-size.html)) | MATCHES (fixed) | Added `mde_absolute_pp` |
| 3 | Two-sample proportion test with p-value and verdict ([chi-squared](https://www.evanmiller.org/ab-testing/chi-squared.html)) | MATCHES | p equals scipy's χ² (no continuity correction) to 1e-15. We add CIs on absolute and relative lift and P(beat) |
| 4 | Confidence interval on each sample's rate ([chi-squared](https://www.evanmiller.org/ab-testing/chi-squared.html)) | MATCHES (fixed) | Wilson intervals per arm, matching statsmodels to 1e-3 |
| 5 | Two-sample t-test from mean/SD/n with CI, p, verdict ([t-test](https://www.evanmiller.org/ab-testing/t-test.html)) | MATCHES | Welch test, matching scipy `ttest_ind_from_stats` |
| 6 | One-sided hypotheses (d ≤ 0, d ≥ 0) for the t-test ([t-test](https://www.evanmiller.org/ab-testing/t-test.html)) | MATCHES (fixed) | `alternative` = two-sided / greater / less. Per-arm mean CIs added |
| 7 | Sequential sampling stopping rule ([sequential](https://www.evanmiller.org/ab-testing/sequential.html)) | PARTIAL | We correct fixed-horizon tests for repeated looks (exact Pocock per-look α). We don't offer Evan's "N conversions ahead" design |
| 8 | Count-data (Poisson) and survival-time tests (tool menu on each page) | MISSING | Rare in marketing A/B. Not built |

**Correctness (expected = independent)**

| Value | Expected (how) | Actual |
|---|---|---|
| SRM χ² / p | 0.49403 / 0.482135 (scipy chisquare) | 0.494 / 0.482135 |
| z / p | 2.309481 / 0.0209169 (hand; scipy χ²) | 2.3095 / 0.020917 |
| Relative lift, CI | 13.4149 %, [1.9155, 26.2118] (log-ratio delta, by hand) | 13.41 %, [1.92, 26.21] |
| Absolute-lift CI | [0.06806, 0.83215] pp | [0.068, 0.832] |
| Wilson CIs | control [3.1036, 3.6266] %, variant [3.5363, 4.0940] % (statsmodels) | [3.104, 3.627], [3.536, 4.094] |
| n per arm at 3.355 %, +10 % | 47,396.75 → 47,397 (Fleiss, by hand) | 47,397 |
| Days, stop date | 37 d → 42 d; reached 2026-10-20, stop 2026-10-25 (datetime) | same |
| Pocock per-look α, K = 14 | 0.0089 (numpy recursive integration, h = 0.025; reproduces Pocock's table: K = 5 0.0158, K = 10 0.0106) | 0.0089 (was: Bonferroni 0.00357) |
| Naive false positives, 14 looks | 22.0 % (same integration; reproduces Armitage 1969: 5 looks 0.142, 10 looks 0.193) | 22.0 % (was 21.4 %, interpolated) |
| Welch t / p / df / CI | −0.687312 / 0.4920123 / 1265.24 / [−8.865, 4.265] (scipy) | −0.6873 / 0.492012 / 1265.2 / [−8.865, 4.265] |
| One-sided (less) p | 0.246006 (= p/2) | 0.246006 |
| Evan Miller default | 1,030 (his formula, reproduced) vs ours 1,094 (power checked by simulation) | 1,094 plus method note |

**Deliverable excerpt**
```
# Experiment readout — Checkout redesign
Primary metric: order conversion · Runtime: 14 days · Looks: 14 (daily) · α (corrected): 0.0089 (Pocock)
| Arm | Visitors | Orders | Rate (95% CI) |
| Control | 18,240 | 612 | 3.355% (3.104–3.627) |
| Variant | 18,106 | 689 | 3.805% (3.536–4.094) |
Result: relative lift +13.4% (95% CI +1.9% to +26.2%), p = 0.021, P(variant > control) = 99%
Sample check: needed 47,397/arm for +10%; have ~18,200/arm → underpowered
SRM: pass (p = 0.48)
## Recommendation: KEEP RUNNING until 2026-10-25 (pre-planned sample reached 2026-10-20)
p = 0.021 would be a win on a single look, but after 14 daily peeks the bar is p < 0.0089;
a naive daily rule has a 22% false-positive rate. The test has 38% of its planned sample.
## What this does NOT tell us
- AOV is flat (−$2.30, 95% CI −$8.87 to +$4.27, p = 0.49): no evidence of revenue lift yet.
- Lift of +13% on checkout is below the Twyman threshold but check the variant's tracking.
## Next test
If it holds at 42 days: test the one-page payment step alone to isolate the driver.
```

**What a plain AI would get wrong (observed).** The `significance_test` verdict line reads "Variant wins … p = 0.0209". The only thing that overturns it is the peeking correction. Before the fix, the 14-look correction was Bonferroni (0.00357), a threshold 2.5× stricter than the correct Pocock bound. That would have told a team with p = 0.005 to keep waiting.

**Remaining gaps.** No Evan-style sequential design, no Poisson or survival tests. The Pocock/naive tables are exact for α ∈ {0.01, 0.05, 0.10} and 1–50 looks. Other α values are log-interpolated, and more than 50 looks falls back to Bonferroni, which is conservative.

---

## 2. ad-copy-lab: Ad Copy Lab

**Comparable.** Anyword Starter, $49/mo ($39 annual): [pricing](https://www.anyword.com/pricing), [ad copy generator](https://www.anyword.com/use-cases/ad-copy-generator), [performance marketers](https://www.anyword.com/performance-marketers). The RSA-limits claim comes from a third-party review: [aitoolvillage](https://aitoolvillage.com/tools/anyword.html).

**Scenario.** "Google RSA for Tallyo, an invoicing app, ad group 'freelance invoicing'. CPC $3.10, click-to-paid 4.2 %, first-year value $180, 85 % margin, $120/day. We want 20 % of gross profit left after ads."

**Parity checklist**

| # | Documented capability (source) | Status | Why |
|---|---|---|---|
| 1 | Copy for Facebook, Google, Twitter, LinkedIn and Pinterest ads ([ad copy generator](https://www.anyword.com/use-cases/ad-copy-generator)) | MATCHES | 8 platforms validated. Outbrain/Taboola headlines are not specifically modelled |
| 2 | RSA headlines/descriptions within character limits ([3p review](https://aitoolvillage.com/tools/anyword.html)) | MATCHES | Limits match [Google's help page](https://support.google.com/google-ads/answer/7684791?hl=en): 30/90/15 chars, 3–15 headlines, 2–4 descriptions. Also counts pin-surviving combinations |
| 3 | Predictive Performance Score per variation ([performance marketers](https://www.anyword.com/performance-marketers)) | PARTIAL | Our 0–100 score is a transparent rubric, not a model trained on ad outcomes |
| 4 | Age and gender analytics per variation ([ad copy generator](https://www.anyword.com/use-cases/ad-copy-generator)) | OUT OF SCOPE | Needs their impression data set |
| 5 | Tones, styles, copywriting frameworks; rewrite as "More engaging / Hard sell / Playful" ([ad copy generator](https://www.anyword.com/use-cases/ad-copy-generator)) | MATCHES | The customer's AI rewrites, and `angle_coverage` enforces ≥ 5 persuasion angles |
| 6 | Copy for customer personas ([ad copy generator](https://www.anyword.com/use-cases/ad-copy-generator)) | PARTIAL | Audience and JTBD come from intake. Full personas live in persona-builder |
| 7 | Identify the top variations before going live ([performance marketers](https://www.anyword.com/performance-marketers)) | MATCHES | Score, rank, and keep ≥ 65. Test plan with CPA target |
| 8 | 1 brand voice on Starter ([pricing](https://www.anyword.com/pricing)) | PARTIAL | Via the separate brand-voice agent |
| 9 | Connect to Facebook, LinkedIn, Google ads ([performance marketers](https://www.anyword.com/performance-marketers)) | OUT OF SCOPE | Needs an ad-account integration |

**Correctness**

| Value | Expected (hand) | Actual |
|---|---|---|
| Clicks / conv / net per day | 38.71 / 1.6258 / 128.75 | 38.7 / 1.63 / 128.75 |
| CPA / ROAS / BE ROAS / BE CPA | 73.81 / 2.4387 / 1.1765 / 153.00 | 73.81 / 2.44 / 1.18 / 153.0 |
| Target CPA / max CPC / BE CPC | 122.40 / 5.1408 / 6.426 | 122.4 / 5.14 / 6.43 |
| Days to 50 conversions / impressions | 31 / 774 | 31 / 774 |
| Longest headline / descriptions | 29 / 80–84 chars (`len`) | 29 / 80–84 |
| RSA combinations (H1 ∈ {h1, h3}) | 3,744 of 32,760 (itertools enumeration) | 3,744 / 32,760 |

**Deliverable excerpt**
```
# Ad copy — Google RSA · Tallyo / freelance invoicing
Economics: CPC $3.10 · CVR 4.2% · CPA $73.81 (target $122.40) · break-even ROAS 1.18 · max CPC $5.14
Audience & angle plan: freelancers who chase late invoices · angles: benefit, social proof,
  price/value, objection-kill, feature, question, identity, urgency (8, none > 20%)
| # | Asset | Text | Chars | Angle | Score |
| H1 (pin 1) | headline | Freelance Invoicing Made Fast | 29 | benefit | 73 |
| H3 (pin 1) | headline | Tallyo Freelance Invoicing | 26 | relevance | 70 |
| H2 | headline | Freelance Invoicing, 2 Clicks | 29 | relevance | 82 |
| H6 | headline | Trusted by 41,000 Freelancers | 29 | social proof | 72 |
| H8 | headline | No Credit Card to Start | 23 | objection-kill | 60 → revise |
| D2 | description | 41,000 freelancers get paid 9 days sooner on average. Start free, no card needed. | 81 | proof+CTA | — |
Pins: two keyword headlines share H1 (Google: pin 2-3 per position) → 3,744 combinations.
Test plan: social proof vs objection-kill; success = CPA ≤ $122.40; judge at ≥ 50 conv/variant (~31 days at $120/day).
Rejected: "Freelance Invoicing in 2 Clicks" — 31 chars, over the 30 limit.
```

**What a plain AI would get wrong (observed).**
- My own first draft had a 31-character headline. The validator caught it.
- Before the fix, the tool pushed the AI in the wrong direction on two points:
  - It penalised "No Credit Card to Start" and "Start Your Free Trial Today" as spam. That is the email lexicon, which doesn't apply to ads.
  - It told the AI to rewrite the three keyword headlines as "generic", which contradicts Google's ≥ 3 keyword-headline advice.
- A single pin to H1 was reported as "expect Poor Ad Strength", with no fix offered.

**Remaining gaps.** The score is not predictive of CTR/CVR. There are no demographic analytics, and there is no Outbrain/Taboola spec.

---

## 3. brand-voice: Brand Voice Guardian

**Comparable.** WRITER Starter, ~$39/mo (third-party price; writer.com shows none). Sources:
- [Suggestions](https://support.writer.com/article/249-using-suggestions): categories and the 0–100 style-guide score.
- [Voice](https://writer.com/blog/voice-feature/): profile from uploaded samples, multiple profiles.
- Term types (Approved / Don't use / Use carefully / Pending) come from the WRITER help center via search result [support.writer.com](https://support.writer.com/articles/2607647594-customizing-your-team-s-style-guide).

**Scenario.** Fernhill, a café bookkeeping app, sent 4 on-brand samples (282 words), a drafted product announcement written in corporate voice, and a lexicon: banned *leverage, solution, robust*; "users" → "you"; casing *Fernhill*.

**Parity checklist**

| # | Documented capability | Status | Why |
|---|---|---|---|
| 1 | Build a voice profile from uploaded sample copy ([voice](https://writer.com/blog/voice-feature/)) | MATCHES | `extract_voice_profile`: rhythm, grade, pronouns, contractions, energy, jargon, signature words |
| 2 | Multiple voice profiles for products, channels, audiences ([voice](https://writer.com/blog/voice-feature/)) | PARTIAL | Any number of profiles, but the AI has to keep the JSON. No storage |
| 3 | Terms: Approved / Don't use / Use carefully ([search result](https://support.writer.com/articles/2607647594-customizing-your-team-s-style-guide)) | MATCHES (fixed) | Banned, preferred (avoid → use), and `use_carefully` with the rule text. "Pending" is a review workflow, out of scope |
| 4 | Style rules: acronyms, sentence vs title case, dates/money ([suggestions](https://support.writer.com/article/249-using-suggestions)) | PARTIAL | Only brand-name casing is enforced |
| 5 | Clarity: sentence length, grade level, passive voice ([suggestions](https://support.writer.com/article/249-using-suggestions)) | MATCHES | All three measured against the brand's own bands |
| 6 | Delivery: tone ("passive aggressive?") ([suggestions](https://support.writer.com/article/249-using-suggestions)) | PARTIAL | NN/g four-dimension placement. No passive-aggression detector |
| 7 | Inclusivity suggestions ([suggestions](https://support.writer.com/article/249-using-suggestions)) | PARTIAL (fixed) | Starter list of 18 terms with alternatives. WRITER's set is curated and larger |
| 8 | Compliance: sensitive information ([suggestions](https://support.writer.com/article/249-using-suggestions)) | MISSING | Not built |
| 9 | Plagiarism check ([suggestions](https://support.writer.com/article/249-using-suggestions)) | OUT OF SCOPE | Needs a web index |
| 10 | Style-guide compliance score, 100 = perfect ([suggestions](https://support.writer.com/article/249-using-suggestions)) | MATCHES | 0–100 score against the measured profile, with per-metric drifts and fixes |

**Correctness**

| Value | Expected (independent) | Actual |
|---|---|---|
| Samples: sentences / avg length | 32 / 8.75 (whitespace tokens: 280) | 32 / 8.8 (282: tool splits "cash-up", "one-card") |
| "you" per 100 words (incl. you'll / you're) | 8.21 (23/280) | 8.16 (23/282) |
| Contractions / expandable forms | 17 / 0 → 100 % | 100 % |
| Draft: words / sentences / avg | 62 / 4 / 15.5 | 62 / 4 / 15.5 |
| Draft: "they" per 100 | 3.23 (2/62) | 3.23 |
| Lexicon positions | robust 34, solution 55, users 81 & 284, leverage 90 (`re.finditer`) | same |

**Deliverable excerpt**
```
# Brand voice — Fernhill
Sounds like: a sharp bookkeeper friend texting you the answer, never a brochure
Tone: serious (+0.30) · casual (+0.33) · respectful (−0.30) · matter-of-fact (+0.40)
## The numbers (4 samples, 282 words — low sample: bands are wide)
| Sentence length | 8.8 words | 6.6–11.0 |   | Reading grade | 2.8 | ≤ 4.3 |
| Pronouns /100 w | you 8.2 · we 2.5 · they 0.7 | you ≫ we |   | Contractions | 100% | ≥ 75% |
| Questions / exclamations / emoji | 0.35 / 0 / 0 per 100 w | … |
## We do / we don't
- We say "Split it in two taps" · We don't say "leverage our robust solution"
## Lexicon  Banned: leverage, solution, robust · Preferred: users → you · Casing: Fernhill
## Draft review: 0/100 → rewrite 100/100
| Drift | Draft | Target | Rewrite |
| Sentence length | 15.5 | 8.8 | "Your reports just got simpler." |
| Passive | 75% | 0% | "We rebuilt them so…" (not "have been redesigned by our team") |
| Pronoun centre | they | you | "Tap any number and you'll see the receipts behind it." |
| Contractions | 0% | 100% | "It's in your dashboard today." |
```

**What a plain AI would get wrong (observed).** Nothing observed in AI behaviour. Tool issues found:
- Contractions ("you'll", "doesn't", "that's") were listed as the brand's "signature words", which would have produced keyword-stuffing advice.
- "Use carefully" terms and inclusive language were impossible to express.

**Remaining gaps.**
- No acronym, date or money style rules, no PII/compliance scan, no plagiarism check.
- Profiles are not stored server-side.
- Word counts inherit the lib tokenizer issue for accented words.

---

## 4. email-campaign: Email Campaign Writer

**Comparable.** Mailchimp Standard, $20/mo. Sources:
- [Subject line helper](https://mailchimp.com/features/subject-line-helper/): word and character count, emoji, punctuation.
- [Best-practice research](https://mailchimp.com/help/best-practices-for-email-subject-lines/), via search result: ≤ 3 punctuation marks, ≤ 1 emoji.
- [Send Time Optimization](https://mailchimp.com/help/use-send-time-optimization/): Standard and up.
- [Content optimizer](https://mailchimp.com/resources/three-tips-for-optimizing-your-content-in-real-time/), via search result: link formatting, merge tags.
- [Campaign benchmarks](https://mailchimp.com/help/about-open-and-click-rates/).

**Scenario.** "3-email launch sequence for multi-site reports to 8,400 café customers, first send Tue 2026-10-13, B2B. Last month's send: 8,400 sent, 8,232 delivered, 3,120 opens, 402 clicks, 19 unsubs, 3 complaints, 57 conversions."

**Parity checklist**

| # | Documented capability | Status | Why |
|---|---|---|---|
| 1 | Subject line helper: word/char count, emoji, punctuation | MATCHES (fixed) | Plus 41-char mobile cut, spam words, ALL-CAPS words (new), > 3 punctuation (new), fake "Re:" |
| 2 | Preview text guidance | MATCHES | 40–90 chars, must add information, footer-text leak detection |
| 3 | AI writing of the email ("Write with AI") | MATCHES | The customer's AI writes to the playbook's one-CTA pattern |
| 4 | Content checks incl. link formatting and merge tags | MATCHES (fixed) | The `{{first_name\|there}}` form used to be invisible, so misspelled fallback tokens passed |
| 5 | A/B test subject lines: choose the pair | MATCHES | Ranked pair + 20 % split plan. *Running* the split and auto-sending the winner is OUT OF SCOPE |
| 6 | Send Time Optimization from per-contact engagement | OUT OF SCOPE | Needs send history. We give rule-based B2B/B2C windows and a weekend-safe calendar |
| 7 | Campaign report benchmarks vs industry | PARTIAL | Graded against all-industry bands, not per-industry peers |

**Correctness**

| Value | Expected (hand / `calendar`) | Actual |
|---|---|---|
| Delivery / bounce | 98.0 % / 2.0 % | 98.0 / 2.0 |
| Open / CTR / CTOR | 37.90 / 4.883 / 12.885 % | 37.9 / 4.88 / 12.88 |
| Unsub / complaint / click→conv | 0.2308 / 0.0364 / 14.18 % | 0.231 / 0.036 / 14.18 |
| Send dates | 10-13 Tue, 10-15 Thu, 10-18 Sun → 10-19 Mon | same, with Monday warning |
| Subject / preheader length | 22 / 74 chars | 22 / 74 |
| Body words | 133 by whitespace (URLs as one token) | 140 (lib splits URLs). Both inside the 50–200 band |

**Deliverable excerpt**
```
# Campaign — Multi-site reports · 3 emails · list: 8,400 café customers
Goal: open multi-site reports · Primary metric: CTOR on [Open multi-site reports] · Guardrail: unsub < 0.5%
| # | Send (PT) | Job | Subject A | Subject B |
| 1 | Tue 10-13, 09:00-11:00 | announce | Is site #2 quietly losing money? (84) | Close 3 sites in the time it took for 1 (80) |
| 2 | Thu 10-15 | proof: 41-minute close | … | … |
| 3 | Tue 10-20 (moved off Mon 10-19) | FAQ / objections | … | … |
Preheader: See money in, money out and what you owe for all your sites on one screen. (74)
Hi {{first_name|there}}, If you run more than one café, you probably close each site on its own…
[Open multi-site reports]   P.S. It's included in your current plan. Nothing to switch on.
Scan: clean (1 CTA, 1 content link, unsubscribe + postal address present)
## Last send: CTR 4.88% · CTOR 12.9% · unsub 0.23% · complaints 0.036% — healthy; next test: CTA copy
```

**What a plain AI would get wrong (observed).** Before the fix, the scanner reported `merge_tokens: []` for a body containing `{{first_name|there}}`. That is the fallback syntax the tool itself recommends, so a typo such as `{{frist_name|there}}` shipped unflagged.

**Remaining gaps.**
- No per-industry benchmarks.
- No data-driven send-time optimisation.
- No power check on the 20 % subject split. With ~840 per arm, only large differences are detectable, and the ab-test-analyst agent can size it.
- Holidays must be passed in explicitly.

---

## 5. landing-page-cro: Landing Page CRO

**Comparable.** Unbounce Build, $99/mo ($74 annual; AI copywriting). A/B testing with confidence intervals is on Experiment ($149). Sources:
- [Pricing](https://unbounce.com/pricing/).
- Landing Page Analyzer checks, via search result for [unbounce.com analyzer](https://unbounce.com/landing-pages/get-custom-reviews-landing-page-analyzer/): copy, message match, page speed, mobile, SEO, trust & security, industry benchmarks.

**Scenario.** Shiftly, a restaurant rota app. Paid page for "restaurant staff scheduling app" with a jargon hero, 3 CTAs, 6 nav links, 7-field form and 3.8 s load time. Traffic is 22,000 visits a month. Funnel: 22,000 visits → 5,300 pricing views → 528 trials → 118 paid. A trial is worth $42.50.

**Parity checklist**

| # | Documented capability | Status | Why |
|---|---|---|---|
| 1 | AI copywriting for page sections (Build) | MATCHES | The AI rewrites the hero and sections. `headline_clarity` gates the rewrite |
| 2 | Copy analysis (copy length) | MATCHES | Word count, reading grade (fixed), jargon, we:you |
| 3 | Message match to the traffic source | MATCHES (fixed) | The channel label no longer dilutes the ratio |
| 4 | Page speed | PARTIAL | Uses the load time the user supplies. We can't measure it |
| 5 | Mobile experience | OUT OF SCOPE | Needs rendering |
| 6 | SEO elements (title, meta, H1) | MISSING | Not in this agent. SEO agents in the growth category cover it |
| 7 | Trust & security | MATCHES | Anxiety dimension: guarantees, "no credit card", SOC 2, privacy, form length |
| 8 | Industry benchmarks | PARTIAL | Category baselines in the playbook only |
| 9 | A/B tests with confidence intervals (Experiment tier) | OUT OF SCOPE (running) | We size the test and set the ship/test decision |

**Correctness**

| Value | Expected (hand) | Actual |
|---|---|---|
| Step conversions | 24.09 / 9.96 / 22.35 % | same |
| Overall / biggest leak | 0.536 %; trial starts, 4,772 lost × 118/528 = 1,066.5 | same |
| 10 % fix at leak | 11.8 paid → $2,242 | same |
| Lift 2.4 → 2.9 % | +110/mo, $4,675/mo, $56,100/yr, +20.8 % | same |
| Test size | 17,510.98 → 17,511/variant; 6.92 → 7 weeks; bolder lift ⌈20·√(6.92/6)⌉ = 22 % | same |
| Message match | 1/4 = 0.25 | 0.25 |

**Deliverable excerpt**
```
# CRO audit — Shiftly paid landing page · score 44/100 (D)
Primary conversion: trial start · Now: 2.4% on 22,000/mo · Prize: +110 trials/mo ≈ $56,100/yr at 2.9%
| Dimension | Score | Biggest issue |
| Distraction | 30 | 6 nav links, 3 CTAs (Get started / Book a demo / Watch video) |
| Urgency | 30 | no reason to act now; 3.8 s load |
| Anxiety | 38 | 7-field form |
| Relevance | 40 | ad promise "restaurant staff scheduling app" → hero says "workforce management" (match 0.25) |
## Hero (5-second test: F → A)
- Now: "Reimagining workforce management for modern hospitality" / [Get started]
- Rewrite: "Build next week's restaurant rota in 20 minutes" / "Shiftly is a rota app that shows
  labor cost next to forecast sales. 1,200 restaurants use it to stay on budget." / [Start my free trial]
## Ranked fixes
1. Speed: 3.8 s → < 2.5 s before any copy test · 2. Hero rewrite (10-30%) · 3. One CTA, drop nav on paid
## Funnel leak: pricing → trial loses 4,772/mo (90%) — a 10% step gain ≈ +11.8 paid ≈ $2,242/mo
## Test plan: hero rewrite · 17,511 per arm · ~7 weeks → too long: ship it with a holdout, or test a ≥ 22% change
```

**What a plain AI would get wrong (observed).**
- Before the fix, the tool graded the rewritten hero "readable: False" at grade 14.6. That is a false fail from gluing headline and subheadline into one sentence, and it would have sent the AI to rewrite a good hero.
- It also scored message match 0.17 because "google" and "ads" counted as promise words.

**Remaining gaps.** No measured speed or mobile checks, no SEO elements, no per-industry benchmarks.

---

## 6. launch-planner: Launch Planner

**Comparable.** Jasper Pro, $69/mo ($59 annual).
- [Campaign Brief agent](https://www.jasper.ai/agents/campaign-brief) produces objectives & KPIs, channel mix, deliverable specs, timelines & milestones, and roles & approvals.
- [Product Launch Campaign agent](https://www.jasper.ai/agents/product-launch-campaign) produces channel-ready assets. Its page lists no timelines, checklists or go/no-go.
- The plan tier is stated for Jasper's other agents (Pro/Business) but not on these pages.

**Scenario.** "Launch multi-site reports Tue 2026-11-10 (medium) via landing page, blog, email, Product Hunt, LinkedIn, press, in-app, support. Goal 900 signups in launch week. Today is 2026-09-28." A status list is attached.

**Parity checklist**

| # | Documented capability | Status | Why |
|---|---|---|---|
| 1 | Objectives and KPIs | MATCHES | `launch_targets` shows whether the channel mix reaches the goal |
| 2 | Channel mix | MATCHES | 15 channel types with assets |
| 3 | Channel-specific deliverables with creative specs | MATCHES | Per-asset specs (sizes, char limits) and final-by dates |
| 4 | Timelines and milestones | MATCHES | Business-day countdown, compression when runway is short, overdue on re-run |
| 5 | Owners and approval checkpoints | MATCHES | Go/no-go gate: P0s force NO-GO, unowned items flagged |
| 6 | Channel-ready asset drafts (landing, PR, email, social sized per platform) | PARTIAL | The AI drafts. Validation lives in the sibling agents (ad-copy-lab, press-release, email-campaign) |
| 7 | Grounded in knowledge base, brand voice, style guide | OUT OF SCOPE | No stored KB |

**Correctness**

| Value | Expected (numpy busday / zoneinfo / hand) | Actual |
|---|---|---|
| Runway | 31 business days, 43 calendar | 31 / 43 |
| T-30 / T-25 / T-20 / T-12 / T-10 / T-5 / T-2 / T-1 | 09-29 / 10-06 / 10-13 / 10-23 / 10-27 / 11-03 / 11-06 / 11-09 | same |
| T+1 / T+7 / T+14 | 11-11 / 11-17 / 11-24 | same |
| Channel finals | press T-15 10-20, landing & PH T-7 10-30, LinkedIn T-2 11-06 | same |
| Target projection | 466.93 → gap 433.07; reset ≈ 420 | 466.9 / 433.1 / 420 |
| Readiness | (15 + 2.5 + 7.5)/35 = 71.4 → 71, NO-GO | 71, NO-GO |
| PH time 2026-11-10 | 00:01 PST = 03:01 EST → −359 min | −359 |
| PH time 2027-03-03 | −359 (PST still; DST starts 03-14) | −359 (was −419 before the fix) |
| DST helper | 0 mismatches vs `zoneinfo` for every hour 2024–2030, except the nonexistent 02:xx spring-forward hour | same |

**Deliverable excerpt**
```
# Launch plan — Multi-site reports · 2026-11-10 (Tuesday) · tier 2
Goal: 900 signups · Projected: 467 (short 433) · Runway: 31 business days (ok)
→ Close the gap: in-app + email reach is capped; add $3k paid + 2 partner newsletters, or reset goal to ~420
## Countdown
| T-30 | 09-29 Tue | Message hierarchy + tier locked (P0) | Mei |
| T-25 | 10-06 Tue | Pricing final; per-site billing tested (P0) | Raj |
| T-10 | 10-27 Tue | Embargoed press pitch sent | Lena |
| T-5  | 11-03 Tue | Landing page live (noindex), tracking verified (P0) · PH squad confirmed | Mei |
| T-2  | 11-06 Fri | Final QA of links/UTMs; emails scheduled (P0) | Mei |
## Launch day (ET): 03:01 PH live (00:01 PT) · 07:00 smoke test · 08:30 embargo lifts · 09:00 email + LinkedIn
  ⚠ 09:00 ET = 06:00 PT: schedule West-coast email/social for 09:00 PT
## Go/no-go: 71/100 · P0 blockers: per-site billing (in progress, Raj), rollback plan (not started, NO OWNER) → NO-GO
## After launch: T+1 11-11 thank-you + numbers · T+7 11-17 retro · T+14 11-24 second wave
```

**What a plain AI would get wrong (observed).** No AI error was observed; the dates were all tool-computed. One tool bug was found: the Product Hunt time used "Pacific = UTC-7 in months 3–10". For any launch between 1 and ~13 March that places 12:01 AM PT an hour off.

**Remaining gaps.**
- No holiday calendar by default.
- `launch_targets` suggests "more visitors at your best channel" even when that channel is reach-capped. The AI must judge.
- Asset drafting is not validated inside this agent.

---

## 7. marketing-budget: Marketing Budget Planner

**Comparable.** The research file found no priced standalone budget planner. The nearest documented feature is HubSpot Marketing Hub, whose campaign budget is **Professional and Enterprise only**. The research file lists Pro at $800/mo for 3 seats.
- [Campaign budget](https://knowledge.hubspot.com/campaigns/manage-your-campaign-budget): budget and spend items, budget total, spend total, remaining.
- [Ads analytics](https://knowledge.hubspot.com/ads/analyze-ad-campaigns-in-hubspot), via search result: cost per contact and customer, ROI estimate, AI summaries.
- Free [ROAS calculator](https://www.hubspot.com/ads-calculator).

**Scenario.** SaaS with ARPU $79, 78 % margin, 3.5 % churn and 1,450 customers. Last month: Google $18k → 120 customers, Meta $10k → 45, LinkedIn $6k → 12, Content $2k + $4k freelancer → 30. Next month's budget is $40k with a $2.5k TikTok test. October pacing: $21,300 spent by the 14th.

**Parity checklist**

| # | Documented capability | Status | Why |
|---|---|---|---|
| 1 | Budget and spend items with budget total, spend total, remaining | PARTIAL | `pacing_check` gives remaining, pace and a daily target. Line items live in the AI's table or the customer's sheet (no storage) |
| 2 | Cost per contact and per customer by campaign | MATCHES | Fully loaded and paid-only CAC per channel, LTV:CAC, payback |
| 3 | ROI estimate from average sale price and contact-to-customer rate, or deals | PARTIAL | ROAS from revenue and LTV-based returns. No lead→customer funnel input |
| 4 | Auto-sync spend from connected ad accounts | OUT OF SCOPE | Integration |
| 5 | AI summaries comparing campaigns | MATCHES | Ranked CAC, verdicts and a reallocation with expected customers |
| 6 | ROAS calculator (free) | MATCHES | Break-even ROAS, and ad_math in ad-copy-lab |

**Correctness**

| Value | Expected (hand / scipy brentq / independent loop) | Actual |
|---|---|---|
| LTV / max CAC / payback / ratio | 1,760.57 / 586.86 / 3.44 mo / 8.30 | 1,760.57 / 586.86 / 3.4 / 8.3 |
| CAC per channel, blended | 150 / 222.22 / 500 / 200; 193.24 | same |
| Reallocation | $1,800 LinkedIn → Google, +8.4 customers | same |
| Allocation (bounded proportional) | G 14,937.08 · M 10,082.02 · L 4,480.90 · C 8,000 · T 2,500 | same (old algorithm: G 14,030, L 6,000 at max) |
| Pacing | 18,064.52 expected; 1.179×; 47,164.29 projected; $1,100/day | same |
| Projection m1 / m12 | cumulative +58,976.91 → break-even **month 1**; 2,779.54 customers, MRR 219,583.70, cumulative 1,192,248.76 | month 1 (was "month 2"); same values |
| Cohort payback | month 6; cohort cumulative 335,254.38 at m12 | 6; 335,254.38 |
| Steady state | 40,000 / 240.27 / 0.035 = 4,757 | 4,757 (was 5,914 at the un-inflated CAC) |

**Deliverable excerpt**
```
# Marketing budget — November · total $40,000
Ceiling: LTV $1,761 · max CAC (3:1) $587 · payback target ≤ 12 mo · break-even ROAS 1.28
| Channel | Spend | Cust | CAC | LTV:CAC | Payback | Verdict |
| Google Search | 18,000 | 120 | 150 | 11.7 | 2.4 | scale |
| Content/SEO | 2,000 + 4,000 fixed | 30 | 200 (67 paid-only) | 8.8 | 3.2 | scale |
| Meta | 10,000 | 45 | 222 | 7.9 | 3.6 | scale |
| LinkedIn | 6,000 | 12 | 500 | 3.5 | 8.1 | hold — worst CAC |
## Allocation (floors at current spend for proven channels)
| Google 18,000 (=) | Meta 10,000 (=) | Content 6,500 (+500) | LinkedIn 3,000 (−3,000) | TikTok test 2,500 (new, kill date 12-15) |
Core/emerging/experimental: 70 / 23.8 / 6.2
## Pacing: over pace 1.18× on day 14/31 → cut to $1,100/day (from $1,521) or land at $47,164 (+18%)
## Projection: 2,780 customers and MRR $219.6k after 12 months; this budget's own cohort pays back in month 6
Move money when: CAC > $587 two weeks running · ROAS < 1.28 · CAC +25% as spend rises
```

**What a plain AI would get wrong (observed).**
- Following the old playbook literally ("weight = 1/CAC") cut Google, the best channel, from $18k to $14k. The old tool then added LinkedIn's $3k minimum *on top of* its weight share, pinning it at the $6k maximum.
- The tool also reported a break-even month of 2 when contribution was positive from month 1. It judged the spend with existing customers' margin included, which says nothing about whether the $40k/month pays back.

**Remaining gaps.**
- No line-item budget ledger or ad-account sync.
- No lead-stage funnel ROI.
- The allocation is proportional to the weight the AI chooses; there is no fitted marginal-return curve per channel.

---

## 8. persona-builder: Persona Builder

**Comparable.** The research file has no priced persona tool: Semrush Persona is a free template ([news post](https://www.semrush.com/news/271737-free-semrush-persona-tool-design-your-buyer-personas-in-less-time/)). The overlapping paid job is survey cross-tab analysis, which SurveyMonkey sells.
- [Crosstabs](https://help.surveymonkey.com/en/surveymonkey/analyze/crosstabs/): count, % of total, row %, column %, up to 5 × 10 questions.
- [Significance](https://help.surveymonkey.com/en/surveymonkey/analyze/significant-differences/): 95 %, ≥ 30 per group, paid feature.
- Crosstabs are on Premier, $139/mo annual, per a third-party source: [jotform](https://www.jotform.com/blog/surveymonkey-pricing/).

**Scenario.** 150 survey rows from café owners (sites, top pain, role, tools as multi-select, hours on books) → personas for the multi-site launch.

**Parity checklist**

| # | Documented capability | Status | Why |
|---|---|---|---|
| 1 | Crosstab counts | MATCHES | — |
| 2 | Row %, column %, % of total | MATCHES (fixed) | Column % and % of total added |
| 3 | Highlight statistically significant differences at 95 % | MATCHES (fixed) | Global χ² plus per-cell adjusted residuals (\|r\| > 1.96). SurveyMonkey doesn't name its test, so individual highlights may differ |
| 4 | ≥ 30 responses per group before significance | MATCHES | Warns under 30 per group and when expected cells are < 5 |
| 5 | Up to 5 column × 10 row questions at once | PARTIAL | One pair per call. The AI loops |
| 6 | Customisable persona template (Semrush) | MATCHES | Template in the playbook, plus a completeness and evidence scorecard |
| 7 | Save, share, collaborate | OUT OF SCOPE | Storage |
| 8 | Survey collection | OUT OF SCOPE | — |

**Correctness**

| Value | Expected (scipy / numpy) | Actual |
|---|---|---|
| χ² / df / p / V | 23.998 / 6 / 0.000523 / 0.2828 | 23.998 / 6 / 0.00052 / 0.283 |
| Expected cells < 5 | 2 | 2 (warned) |
| Adjusted residuals over 1.96 | −4.21, +3.21, +2.84, −2.15, +1.97 (5 cells) | same 5 cells |
| Col % / % of total (1 site × cash-up) | 66.7 / 20.0 | same |
| Multi-select % (Excel, QuickBooks, Square, Xero) | 60 / 40 / 40 / 20 | same |

**Deliverable excerpt**
```
# Persona — Multi-site Maya, owner-operator (2-5 sites) · evidence: 6 interviews, 55 survey rows
Job: When I close the month across my three cafés, I want to see every site side by side,
     so I can spot the losing site before it costs me another month.
Trigger: opening a second site · Today they use: an Excel workbook per site + QuickBooks · Buying role: economic buyer + user
| Top pains | 1. stitching sites by hand — multi-site reporting is top pain for 45.5% (n=55; +2.84 adj. residual) |
| Contrast | single-site owners over-index on cash-up (42.9%, +3.21) — that's the anti-persona |
| Where to reach | hospitality association newsletters, accountant referrals |
Evidence note: χ² = 24.0, df 6, p = 0.0005 (V = 0.28); the 6+ sites group (n=25) is directional only.
Scorecard: 100/100 — complete.
```

**What a plain AI would get wrong (observed).** Before the fix, the tool itself produced "When i close the month…". The job story read "…Maya wants to…, so they can spot the site… before it costs me another month", mixing grammatical persons.

**Remaining gaps.** One cross-tab pair per call. No weighting or multiple-comparison adjustment across the cell highlights. No storage or sharing.

---

## 9. positioning-strategist: Positioning Strategist

**Comparable.** The research file lists no priced tool whose core job is positioning. The nearest documented feature is Jasper Pro's ($69/mo) [Comparison Brief agent](https://www.jasper.ai/agents/comparison-brief), which is included in Pro and Business. It analyses competitive strengths across features, pricing, use cases and audiences, pinpoints dimensions of genuine advantage, and writes positioning briefs using brand voice and a knowledge base.

**Scenario.** Shiftly vs the three real alternatives: a spreadsheet rota, a POS scheduling module, and enterprise workforce suites.

**Parity checklist**

| # | Documented capability | Status | Why |
|---|---|---|---|
| 1 | Analyse competitive strengths across features, pricing, use cases, audiences | MATCHES | Differentiation matrix over any attributes and alternatives, including "spreadsheet" and "do nothing" |
| 2 | Pinpoint dimensions of genuine advantage | MATCHES | lead / table stakes / trivia / fix-or-reframe classification |
| 3 | Messaging that positions the brand advantageously while credible | MATCHES | Moore statement, one-liner and "X for Y" with lint. Generic-claim test on every message |
| 4 | Brand voice and style-guide integration | PARTIAL | Separate brand-voice agent |
| 5 | Knowledge-base grounding | OUT OF SCOPE | Storage |
| 6 | Optimise for AI-engine comparative queries | MISSING | Growth-category (AEO) job |
| 7 | Research competitor content from URLs | OUT OF SCOPE | No crawling. The customer's AI can browse |

**Correctness**

| Value | Expected (hand, playbook rules) | Actual |
|---|---|---|
| Classes | +1/imp 5 → lead; 0/4 → table stakes; −1/5 → fix or reframe; −5/2 → irrelevant | same |
| Differentiation index | Σ imp·max(0,gap)/5 ÷ Σ imp = 1/16 → 6 | 6 |
| Canvas | category "…for independent restaurant groups" → subsegment; only vague item "Easy to use" | same |
| Moore statement length | ≤ 60 words | 57 |

**Deliverable excerpt**
```
# Positioning — Shiftly
One-liner: Build next week's rota in 20 minutes and see labor cost before you publish.
Category: subsegment — "labor-cost scheduling for independent restaurant groups" (wins on labor %, not payroll)
| Attribute | Us | Sheet | POS | Suite | Imp | Class |
| Labor cost vs forecast while scheduling | 5 | 1 | 2 | 4 | 5 | lead |
| POS sales read directly | 5 | 0 | 5 | 3 | 4 | table stakes |
| Multi-site labor reporting | 4 | 1 | 1 | 5 | 5 | fix or reframe → target 2-15 sites |
| Payroll built in | 0 | 0 | 2 | 5 | 2 | don't mention |
Moore: For restaurant groups with 2-15 sites who track labor % weekly and need to hit their labor target
without a spreadsheet, Shiftly is a labor-cost scheduling app that keeps labor within 1 point of target.
Unlike spreadsheet rotas and POS add-ons, we read sales straight from your POS and price every shift before you publish.
We are: the labor-% tool for GMs who build rotas · We are not: HR/payroll, enterprise WFM
Messages: "The all-in-one workforce platform…" 50 — generic, a competitor could say it
```

**What a plain AI would get wrong (observed).**
- The old tool emitted "For restaurant groups … who track labor % weekly **who** need to…". Its own lint ("Target has no behavioural trait — add 'who …'") guaranteed that grammar error.
- It also wrote "Shiftly is labor-cost scheduling app…", with no article.

**Remaining gaps.**
- Ratings are the customer's judgement; there is no market data behind them.
- No AEO optimisation and no competitor crawling.

---

## 10. press-release: Press Release Pro

**Comparable.** Semrush AI PR Toolkit Base, $149/mo billed annually.
- [Pricing](https://www.semrush.com/pricing/pr/): "AI for email and press release writing", media database, journalist recommendations, pitching tool, email analytics.
- Prowly's generator asks ~10 tailored questions and reviews drafts against "11 key criteria" per a search result for [prowly.com](https://prowly.com/ai-press-release-generator/). The page fetch itself didn't show the criteria.

**AP reference for the fix.** AP Stylebook, 2014: "Spell out state names in the body of stories. Datelines continue to use abbreviations" ([AP on X](https://x.com/APStylebook/status/461879050324434945), [Poynter](https://www.poynter.org/reporting-editing/2014/ap-tells-reporters-spell-out-names-of-states-in-stories/)).

**Scenario.** "Fernhill raised a $6.5M seed led by Harbor Light Ventures. Embargo lifts Tue Oct. 13, 6 a.m. ET. Draft the release and the pitch to a food-business reporter."

**Parity checklist**

| # | Documented capability | Status | Why |
|---|---|---|---|
| 1 | AI press-release writing | MATCHES | The AI drafts to the inverted-pyramid template |
| 2 | Guided intake of ~10 tailored questions (Prowly) | PARTIAL | We ask ≤ 3 and use [bracket] placeholders |
| 3 | Review of the draft against best-practice criteria, showing where to edit | MATCHES (fixed) | AP lint with positions and a 19-check structure score. The state rule is now correct |
| 4 | Release structure incl. boilerplate | MATCHES | Checks boilerplate, contact, end mark. Auto-inserting a *stored* boilerplate is out of scope |
| 5 | AI pitch-email writing | MATCHES | `pitch_email_check`: ≤ 150 words, personalisation, one ask, attachments, hype |
| 6 | Follow-up scheduling | MATCHES | Business-day pitch, follow-up and lift dates across time zones. Sending is out of scope |
| 7 | Media database, AI journalist recommendations | OUT OF SCOPE | Data set |
| 8 | Email analytics and media monitoring | OUT OF SCOPE | Integration |

**Correctness**

| Value | Expected (numpy busday / zoneinfo / len) | Actual |
|---|---|---|
| Pitch / follow-up / exclusive dates | 10-05 Mon / 10-09 Fri / 09-30 Wed | same |
| Lift in zones | 06:00 EDT · 03:00 PDT · 11:00 BST | same |
| Headline | 57 chars, 9 words | 57 |
| Pitch subject | 53 chars | 53 |
| Lede words | 30 (whitespace) | 34: lib tokenizer inflates "cafés", "$6.5", "U.S.", "multi-site". Passes ≤ 35 either way |
| AP findings on the draft | 6 real errors: dateline state, month, "twenty", "stated", "!", postal "OR" | all 6, plus 1 correct title-case check. Oxford-comma false positive removed |

**Deliverable excerpt**
```
# Fernhill Raises $6.5 Million to Speed Up Café Bookkeeping
PORTLAND, Ore., Oct. 13, 2026 — Fernhill, the bookkeeping app for independent cafés, today announced
a $6.5 million seed round led by Harbor Light Ventures to expand its multi-site reporting to
restaurant groups across the U.S.
More than 4,800 cafés use Fernhill … closed three sites in 41 minutes on average, down from about two hours.
"Café owners shouldn't lose a Sunday every month to spreadsheets," said Priya Nair, chief executive
officer of Fernhill. …
The company has customers in Portland, Oregon, Austin, Texas, and Denver …
## About Fernhill … Media contact: Lena Brooks, press@fernhill.example, 503-555-0147
###
AP: clean · Structure: A (19/19)
## Pitch (120 words) Subject: Embargoed: café bookkeeping app Fernhill raises $6.5M — score 100, send
## Timing: exclusive offer Wed 9-30 · pitch Mon 10-5 · follow-up Fri 10-9 · lift Tue 10-13 6 a.m. ET / 3 a.m. PT / 11 a.m. London
  ⚠ 3 a.m. PT: West-coast outlets will pick it up late — consider an exclusive with a West-coast outlet
```

**What a plain AI would get wrong (observed).**
- Before the fix, the tool told the AI to change "Portland, Oregon" in body text to "Portland, Ore." That is the pre-2014 AP rule, the opposite of current AP.
- It did not tell the AI that "SAN FRANCISCO, Calif." datelines take no state.
- It flagged "Austin, Texas, and Denver" as an Oxford comma.
- The ET window check used "EDT in months 3–10", wrong for early March and the first week of November in some years.

**Remaining gaps.**
- No media database, journalist matching or monitoring.
- Word counts are inflated for non-ASCII and hyphenated words (lib tokenizer).
- "Tex."-style obsolete abbreviations for never-abbreviated states are not flagged.
