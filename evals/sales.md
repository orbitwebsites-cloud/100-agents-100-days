# Sales: evaluation against paid comparables

Evaluated 2026-09-27. There are 10 agents in `hundred/agents/sales/`.

**Method.** For each agent:
1. Pick the most-overlapping paid tool from `marketing/pricing_research/sales_marketing.md` and build a parity checklist from that tool's own documentation (cited; third-party reviews only where the vendor page doesn't list the checks).
2. Write a realistic customer request with invented data (a weak cold email, a messy pipeline export, call transcripts, a LinkedIn profile) and run it the way the customer's AI would: `python -m hundred.admin brief <slug> …`, then each prescribed tool via `hundred.admin run`, then the deliverable in the playbook's output format.
3. Check every number independently: hand counts, dictionary syllable counts for Flesch, stdlib business-day and present-value helpers that import nothing from `hundred`, and published reference values.
4. Fix what was wrong (tool code + unit test in `tests/agents/test_sales_*.py`, or playbook text) and re-run.
5. Save each scenario as a replayable test in `tests/scenarios/test_sales.py` (10 scenario tests, one per agent).

We could not run the competitors, so **MATCHES** means we produce the same documented output, not that it is better. Capabilities that need sending, recording, hosting, contact data or native CRM sync are **OUT OF SCOPE**, not failures.

## Overview

| Agent | Comparable & price | Checklist (in-scope matches, M/P/Missing/OOS) | Correctness checks passed | Verdict | Fixes made |
|---|---|---|---|---|---|
| cold-email | Lavender Email Coach Starter $29/mo ($27 annual) | 7/9 in-scope (7/2/0/2) | 14/14 after fixes (11/14 before) | **AT PAR** on email scoring; ABOVE on sequencing and campaign sizing (Lavender has neither) | Word count split URLs and hyphenated words (130 vs a true 119). Campaign sizing claimed "10,000 sends over 20 days = 10 mailboxes" though late cohorts finish after the window; added `sequence_span_days` (20 mailboxes to really finish). A plain closing question ("Should I?") scored as "no CTA". Playbook default rates now match the tool. |
| follow-up-machine | Regie.ai Pro $49/mo ($41 annual) | 4/6 in-scope (4/2/0/2) | 16/16 after fixes (11/16 before) | **AT PAR** on follow-up drafting and prioritisation; below on autonomy (OOS) | Cadence restarted at touch 1 and dated the first touch in the past; now takes `today` and `touches_done`. "Multiple asks" only counted `?` (3 asks read as 1). Word count split "8-clinic". |
| lead-qualifier | Apollo.io Basic $59/mo ($49 annual; 3p price) | 3/5 in-scope (3/2/0/2) | 15/15 after fixes (10/15 before) | **AT PAR** on rules-based fit scoring; BELOW Apollo's data-trained scoring (we calibrate from pasted history instead) | Substring matching: **"us" matched "Australia", "uk" matched "Ukraine"**. No function criterion, so "VP Sales Engineering" scored like "VP Sales". RevOps titles parsed as sales. Playbook promised a tier cap for far-out-of-band company size that the tool never applied. New `calibrate_weights` tool (win-rate lift per criterion, suggested weights, AUC). |
| pipeline-forecaster | Clari Core ~$100-120/user/mo (3p estimate, not public) | 6/7 in-scope (6/1/0/2) | 20/20 after fixes (16/20 before) | **AT PAR** on forecast math and inspection; BELOW on activity capture and dashboards (OOS) | Concentration risk named a slipped deal that isn't in the forecast (57.1%; truth: Atlas 50.7%). Late-stage deals with no next step stayed in commit. Coverage was fed all-dates weighted pipeline ($379k vs in-period $306k). Measured probabilities rounded 0.625 to 0.62. Added per-rep roll-up and a new `pipeline_changes` tool (week-over-week "what moved", Clari's forecast inspection). |
| proposal-builder | PandaDoc Starter $35/mo ($19 annual; 3p price) | 5/6 in-scope (5/1/0/2) | 16/16 after fixes (13/16 before) | **AT PAR** on pricing tables and structure; below on e-sign, tracking and templates (OOS or partial) | Tax of $2,845.325 showed as .33 in fields but .32 in the display rows and verdict (two different grand totals). The audit said "no prices found" for `USD 34,905.33`, the format our own pricing table prints. Added line-item % and flat discounts plus a flat total discount (PandaDoc parity). |
| discovery-call | Fathom Business $34/mo ($25 annual) | 4/6 in-scope (4/2/0/2) | 12/12 after fixes (6/12 before) | **AT PAR** on call metrics and MEDDPICC; ABOVE on question-quality grading and pre-call planning | "Who else…, and what's your timeline?" graded as open instead of double-barrelled. Pain, timeline and competition were reported "missed" although the prospect covered all three. Budget counted as "covered" because managers "spend three hours". "you'll like the dashboard" counted as a filler. Call length ignored timestamps. Added `compare_calls` (per-rep averages across calls, Fathom's team metrics). |
| sales-call-debrief | Fathom Business $34/mo ($25 annual) | 5/6 in-scope (5/1/0/2) | 14/14 after fixes (7/14 before) | **AT PAR** (ABOVE on next-step dating and buying temperature) | "end of next week" resolved to Monday instead of Friday. "next Tuesday" from a Thursday resolved 12 days out. A rep's "Could we…" proposal was missed. "a bit more than we budgeted" wasn't a negative, so the call read HOT. "34.8k" parsed as 34.8. The HubSpot payload used properties that don't exist (champion, risks, competitors) and was marked "ready to push". Words/min computed on a partial transcript. |
| objection-handler | Crystal Premium $59/mo ($49.17 annual) | 2/4 in-scope (2/2/0/2) | 12/12 (12/12 before) | **AT PAR** (ABOVE on quantified responses, which Crystal doesn't do; partial on personality-tailored tone) | Classifier didn't separate the four price sub-types the playbook prescribes (competitor-cheaper, value gap, budget, sticker shock); it now returns them with the move for each. Playbook adds a labelled "style read" (Crystal parity, no personality claims). |
| negotiation-coach | Crystal Premium $59/mo ($49.17 annual) | 2/3 in-scope (2/1/0/2) | 20/20 after fixes (17/20 before) | **AT PAR** (ABOVE on ZOPA, concession and PV maths; partial on personality-tailored advice) | "Cash in first 12 months" counted only 54% of monthly and 62.5% of quarterly year-1 payments. The recommended anchor ($123,200) was above the $120k proposal already sent; added `current_offer`. Style-adaptation guidance added. |
| linkedin-prospector | LinkedIn Sales Navigator Core $119.99/mo ($89.99 annual) | 1/4 in-scope (1/3/0/3) | 18/18 after fixes (16/18 before) | **BELOW** on the overlapping job. Sales Navigator finds signals across its member database; we only read profiles the user pastes. This is data-bound and not fixable here. | A 214-char note was reported as fitting although LinkedIn's help page gives 200 chars for free accounts; added `premium`. Missed the headline claim when the pasted profile starts with the name. |

"Correctness checks" counts the independently verified values listed in each section. "Before" counts are the failures we actually observed on the unmodified tools in the same scenario.

Test summary: `pytest -q tests/agents -k sales tests/scenarios/test_sales.py` gives 120 passed. `pytest -q tests/test_library.py` gives 303 passed.

---

## 1. cold-email (Cold Email Closer) vs Lavender Email Coach

**Scenario.** An SDR at DockPilot (dock scheduling software) pastes a 119-word first-touch email to Priya, VP Ops at Fernbrook Freight. It has a `{{first_name}}` token, "I hope this email finds you well", a feature list, a Calendly link and "quick question…!" as the subject. Trigger: Fernbrook posted three dispatcher openings. Proof: Harlow Logistics cut detention fees 31% in 8 weeks. Ask: fix it, build a 4-step sequence starting Tue 2026-10-06 (Oct 12 is a company holiday), and size a campaign for 15 meetings in October.

| # | Lavender capability (documented) | Status | Why |
|---|---|---|---|
| 1 | 0-100 email score; 90+ correlates with replies ([lavender.ai/coach](https://www.lavender.ai/coach)) | MATCHES | `audit_email_body` 0-100 with the exact rule failed |
| 2 | Email length, 50-125 words ideal ([woodpecker review](https://woodpecker.co/blog/lavender-ai/)) | MATCHES | Same band. A URL now counts as one word. |
| 3 | Reading level, grade 3-5 target (woodpecker) | MATCHES | FRE and FK grade reported (final email: FK 4.5). Our pass bar is FRE ≥ 60, looser than grade 3-5. |
| 4 | Subject line scoring: length, personalisation, spam (woodpecker) | MATCHES | `score_subject_line`, 30-char mobile flag, dead phrases, fake "Re:" |
| 5 | Personalisation signals | MATCHES | `check_personalization`: fields, trigger, 90-char preview |
| 6 | CTA quality and question count (woodpecker) | MATCHES | CTA count and type (interest vs time) |
| 7 | Emotional tone / confidence | PARTIAL | We check fluff, spam, you:I and exclamations, but have no tone or confidence classifier |
| 8 | Mobile optimisation preview ([lavender.ai/coach](https://www.lavender.ai/coach)) | PARTIAL | Subject length and paragraph length only; no rendered preview |
| 9 | AI email writer (lavender.ai/coach) | MATCHES | The customer's AI writes to the 4-beat playbook |
| 10 | Real-time coaching in Gmail/Outlook sidebar | OUT OF SCOPE | Browser extension |
| 11 | Personalization Assistant pulls prospect data into the inbox | OUT OF SCOPE | Contact data |

| Check | Expected (independent) | Tool (after fix) | Before |
|---|---|---|---|
| Draft word count | 119 (whitespace tokens, URL = 1) | 119 | 130 ✗ |
| Final word count | 58 (hand count) | 58 | 58 |
| Final Flesch Reading Ease | 74.4 (85 dictionary syllables / 58 words / 7 units) | 77.4 (heuristic syllables; within ±5, same pass) | same |
| Subject "dispatcher hiring at Fernbrook" chars | 30 | 30 | 30 |
| Send dates (Tue-Thu nudge, Oct 12 holiday) | 10-06, 10-08, 10-13, 10-20 (hand) | same | same |
| Step 2 "Want the one-page…?" counts as the CTA | yes | yes | "no CTA" ✗ |
| Prospects / raw list / sends / steady mailboxes | 2,500 / 2,578 / 10,000 / 10 | same | same |
| Mailboxes to finish all steps inside 20 business days | ⌈⌈2500/10⌉×4/50⌉ = 20 | 20 | not reported; verdict said 10 ✗ |

**Deliverable (excerpt).**
```
## Angle
Fernbrook posted three dispatcher openings this month → dock team growing fast → detention risk.
## Subject lines (scored)
1. dispatcher hiring at Fernbrook — 100/100   2. detention fees at Fernbrook — 100/100
## Step 1 — Day 0 (Tue 2026-10-06)
Subject: dispatcher hiring at Fernbrook
Hi Priya,
Saw Fernbrook posted three dispatcher openings this month. When a dock team grows that fast,
missed appointments tend to show up as detention fees.
Harlow Logistics had the same problem. After they moved dock booking into DockPilot, they cut
detention fees 31% in eight weeks.
Would it make sense to compare your numbers with theirs?
Jordan
_58 words · FRE 77.4 · FK 4.5 · spam 0 · CTA: interest_   (your draft: 0/100, 119 words, 2 links, {{first_name}})
## Step 2 — Thu 10-08 · proof   ## Step 3 — Tue 10-13 · new angle   ## Step 4 — Tue 10-20 · direct ask
## Campaign math
15 meetings ÷ 0.6% prospect→meeting = 2,500 prospects (2,578 before 3% bounces) → 10,000 sends.
Steady state is ~500 sends/day = 10 mailboxes. For every step AND reply to land in October, enrol
everyone in the first 10 business days: 250/day, peak 1,000 sends/day = 20 warmed mailboxes.
## Before you send
- 20 mailboxes on secondary domains, each warmed 2-3 weeks. If you can't, move the target to November.
```

**Remaining gaps.** Scores are rule-based. Lavender says its model is trained on reply outcomes, and we can't reproduce that calibration. No tone or confidence model. No rendered mobile preview. Our FRE uses a heuristic syllable counter (about 3 points high on this email).

## 2. follow-up-machine vs Regie.ai

**Scenario.** It is 2026-09-28. Proposal to Tom (Kestrel Dental, $42k) went out Sep 16. Tom replied Sep 17: "will review with our CFO after the board meeting on the 24th". The rep nudged on Sep 21 and has heard nothing since. The rep pastes a weak "just checking in" draft and a 6-deal pipeline.

| # | Regie.ai capability | Status | Why |
|---|---|---|---|
| 1 | Personalised follow-ups grounded in research ([regie.ai/features/email](https://www.regie.ai/features/email)) | MATCHES | Playbook value-add ladder; `score_follow_up` gates clichés, guilt, value and asks |
| 2 | "Works phone, email, and LinkedIn from one queue" (same) | MATCHES | Cadence rotates email → phone → LinkedIn → email → breakup |
| 3 | "Tees up your follow-up tasks, and ranks who to call next" (same) | MATCHES | `stale_deals` chase list ranked by amount × staleness |
| 4 | Next best action from intent/engagement signals ([regie.ai/prospecting-agents](https://www.regie.ai/prospecting-agents)) | PARTIAL | Decision uses dates, touches and promised dates; no engagement feed |
| 5 | "You read every draft before it goes out" (features/email) | MATCHES | We never send |
| 6 | "Every claim carries a source" (features/email) | PARTIAL | Value-add must tie to what they said, but there is no source attribution |
| 7 | Auto-pilot agents running daily | OUT OF SCOPE | Automation and hosting |
| 8 | Sending, dialer, CRM logging, 220M contact database | OUT OF SCOPE | |

| Check | Expected | Tool (after) | Before |
|---|---|---|---|
| Business days since Sep 21 touch / silent days | 5 / 11 | 5 / 11 | same |
| Next touches (touch 2, 3, 4) | today 09-28 (overdue since 09-25), +7 bd = 10-07, +12 bd = 10-23 | same | 09-25 (past), 10-01, 10-12, restarting at "touch 1, email" ✗✗✗ |
| Asks in the weak draft | 3 ("Let me know…", "Happy to hop on…", "Would Tuesday…?") | 3 | 1 ✗ |
| Good follow-up word count | 56 | 56 | 58 ✗ |
| Quiet business days and staleness for 6 deals | 5/1.0, 4/1.33, 19/1.9, 2/0.29, 16/3.2, 12/0.86 | same | same |
| Chase order / stale $ / share | Oakline, Summit, Kestrel, Brightwater / $148,500 / 87.4% | same | same |

**Deliverable (excerpt).**
```
## Decision
Follow up now — 5 business days since your Sep 21 touch ≥ the 4-day proposal gap; the board date (24th) passed.
$42k deal: call first, then email.
## Follow-up (56 words) — send Mon 2026-09-28 via phone + email
Subject: Re: Kestrel proposal
Hi Tom, Hope the board meeting on the 24th went well. You asked how long rollout takes across
9 clinics: our last 8-clinic group went live in 19 days, one clinic per day after training.
If it helps your CFO review, I can send a one-page rollout calendar for Kestrel. Should I send it over?
_score 100/100 · value-add: answer to their question · one ask_   (your draft: 0/100 — 3 asks, "just checking", guilt)
## Cadence
| 2 | Mon 09-28 | phone | overdue since 09-25 | 3 | Wed 10-07 | LinkedIn | 4 | Fri 10-23 | breakup email |
## Chase list
| 1 | Oakline Clinics | negotiation | $68,000 | 4 bd | 3 | call today — what's blocking signature |
| 2 | Summit Smiles | proposal | $23,500 | 16 bd | 5 | breakup email (4 touches, close date passed) |
| 3 | Kestrel Dental | proposal | $42,000 | 5 bd | 5 | call + email |
| 4 | Brightwater Ortho | discovery | $15,000 | 19 bd | 10 | email with new value |
```

**Remaining gaps.** No live engagement signals (opens, site visits). No autonomous daily runs. Priority ranks a 3.2× stale $23.5k deal above a 1.0× $42k deal by design (amount × staleness); some managers would rank it the other way.

## 3. lead-qualifier vs Apollo.io Scores

**Scenario.** A RevOps SaaS vendor sets its ICP as SaaS/fintech, 51-500 employees, VP/Director, sales or ops function, US/UK, on Salesforce. Eight inbound leads come in, including Liam in **Australia**, Olena in **Ukraine**, a **VP Sales Engineering**, an 8-person CEO, a 4,200-person bank and a marketing intern on Gmail. Also: BANT notes on the top lead.

| # | Apollo capability | Status | Why |
|---|---|---|---|
| 1 | "Define criteria, weightings, and variables" ([apollo.io/product/scores](https://www.apollo.io/product/scores)) | MATCHES | Weighted ICP dict |
| 2 | "Full visibility into the lead scoring criteria for every single lead" (same) | MATCHES | Matched/missed criteria with points |
| 3 | Filter and rank by score (same) | MATCHES | Ranked list, A-D tiers, distribution diagnosis |
| 4 | Fit + engagement scoring ([Apollo scoring guide](https://www.apollo.io/magazine/a-guide-to-creating-your-first-lead-scoring-model)) | PARTIAL | Intent is a 3-level routing input, not a scored engagement model |
| 5 | AI auto-score "from your CRM and Apollo account history" (product/scores; plans per [Scores overview](https://knowledge.apollo.io/hc/en-us/articles/4988048582285-Scores-Overview)) | PARTIAL | New `calibrate_weights` learns weights from pasted won/lost history (lift + AUC). Not a trained model on live CRM data. |
| 6 | Enrichment from 65+ attributes | OUT OF SCOPE | Data |
| 7 | Auto-enrol high scorers into sequences ([gtmworks](https://www.gtmworks.ai/blog/how-to-create-a-custom-account-score-in-apollo-io)) | OUT OF SCOPE | Sending |

| Check | Expected (hand, points / 19) | Tool (after) | Before |
|---|---|---|---|
| Maya (all six) | 100 A | 100 A | 100 |
| Liam (Australia ≠ US) | 17/19 = 89 A | 89 A | 100 ✗ ("us" in "australia") |
| Olena (Ukraine ≠ UK) | 12.5/19 = 66 B | 66 B | 72 ✗ ("uk" in "ukraine") |
| Carlos (engineering) | 16/19 = 84 A | 84 A | function never derived from title ✗ |
| Tom (620 employees near band) | 14/19 = 74 B | 74 B | 74 |
| Raj (8 employees) / Hannah (4,200) | capped at C (>3× outside band, per playbook) | 54 C / 54 C | no cap ✗ |
| Emily (intern + Gmail) | capped at D | 34 D | 34 D |
| "VP Revenue Operations" function | ops | ops | sales ✗ |
| Routes (100/high, 54/high, 34/high) | AE 5 min / SDR triage / decline | same | same |
| BANT 2/1/3/2 | 8/12, SQL, gap = authority | same | same |

**Deliverable (excerpt).**
```
## ICP used (weights)
industry: saas, fintech (w4) · size: 51-500 (w4) · seniority: vp, director (w3) · function: sales, ops (w3) · geo: US, UK (w2) · tech: Salesforce (w3)
## Ranked leads
| 1 | Maya Chen | Ledgerly | 100 | A | high (demo) | AE | 5 min | every criterion |
| 2 | Liam Walsh | Koala Payroll | 89 | A | high (pricing) | AE | 5 min | all but geo (Australia) — confirm you sell there |
| 3 | Carlos Ruiz | Stackwise | 84 | A | medium | SDR | 4 business h | VP but engineering — find the sales/ops buyer |
| 4 | Tom Okafor | Brightpath | 74 | B | low | nurture | — | 620 staff, HubSpot |
| 5 | Olena Kovalenko | Dnipro Soft | 66 | B | medium | SDR | 1 business day | manager, Ukraine, Pipedrive |
| 6 | Raj Patel | TinyBooks | 54 | C | high (trial) | self-serve / SDR triage | 1 day | 8 employees |
| 7 | Hannah Berg | Northbank | 54 | C | high (demo) | SDR triage | 1 day | bank, 4,200 staff |
| 8 | Emily Stone | Vaultline | 34 | D | high | decline / self-serve | courtesy | intern, Gmail |
## Distribution  A: 3 · B: 2 · C: 2 · D: 1 → usable list
## Qualification grade (Maya): BANT 8/12 → SQL. Gap: authority — "Who signs, and are they aware of this evaluation?"
```

**Remaining gaps.** No enrichment, so fields must be supplied. Weight calibration needs the customer's own won/lost export and is lift-based, not a multivariate model. Engagement is not scored.

## 4. pipeline-forecaster vs Clari

**Scenario.** A VP Sales is preparing a Q3 board forecast as of 2026-09-01. Quota is $600k and $310k is closed. There is a 10-deal export (one slipped twice, one stale negotiation, one negotiation with no next step, one already won), 12 closed deals of history, 4 quarters of forecast vs actual, and last week's snapshot.

| # | Clari capability | Status | Why |
|---|---|---|---|
| 1 | Forecast categories: pipeline / best case / commit ([clari.com forecast categories](https://www.clari.com/blog/defining-sales-forecast-categories-to-drive-reliable-revenue/)) | MATCHES | Commit now also requires a next step and recent activity |
| 2 | Forecast from pipeline status and historical trends ([Clari buyers' guide](https://www.clari.com/blog/a-revops-solution-buyers-guide-predictable-forecasting/)) | PARTIAL | Measured stage conversion + calibration multiplier; no activity-signal ML |
| 3 | Coverage vs past conversion rates ([sybill: Gong vs Clari](https://www.sybill.ai/blogs/gong-vs-clari)) | MATCHES | `coverage_ratio` with in-period pipeline, required win rate, recoverability |
| 4 | Pipeline inspection: stalled or risky deals (sybill) | MATCHES | Slipped, stale, no next step, concentration |
| 5 | Forecast inspection: "what changed since last week, which deals moved out" (sybill) | MATCHES | New `pipeline_changes` (was MISSING) |
| 6 | Roll-ups by rep/team (Clari dashboards) | MATCHES | New `by_owner` in `weighted_pipeline` (was MISSING) |
| 7 | Forecast accuracy history (buyers' guide) | MATCHES | `forecast_accuracy`: MAPE, bias, multiplier |
| 8 | Revenue analytics dashboards | OUT OF SCOPE | Hosting |
| 9 | Activity capture from email/calendar | OUT OF SCOPE | Integration |

| Check | Expected (independent) | Tool (after) | Before |
|---|---|---|---|
| Win rate / median / avg won cycle | 5/12 = 41.7% / 72 / 81.0 days (dates by hand) | same | same |
| Measured demo probability | 5/8 = 0.625 | 0.625 | 0.62 ✗ |
| Commit / best case / forecast | 158k / 157k / 236.5k (Harbor has no next step → best case) | same | 210k / 105k / 262.5k ✗ |
| Open / weighted in period | 395,000 / 305,901 | same | not reported; only all-dates 588k / 379,457 ✗ |
| Concentration | Atlas 120k / 236.5k = 50.7% | 50.7% | "Granite 57.1%" (slipped, not in forecast) ✗ |
| Granite probability (slipped 2×) | 0.714 / 2 = 0.357 | 0.357 | same |
| Gap / coverage / required win / deals needed | 290k / 1.36× / 73.4% / 6 | same | same (given the right inputs) |
| MAPE / calibration | 11.1% / 1,968k ÷ 2,170k = 0.907 | same | same |
| Week-over-week: in-period 645k → 545k | won 40k, lost 70k, pushed 30k, pulled 52k, removed 22k, +10k upsize | same | no tool ✗ |

**Deliverable (excerpt).**
```
# Forecast — Q3 2026 (as of 2026-09-01)
**Forecast:** $236,500 (range $158,000 – $315,000) · Weighted (in period): $305,901
**Quota:** $600,000 · Closed: $310,000 (51.7%) · Gap: $290,000 · Coverage: 1.36× (need 1.5×) · Days left: 21
## Commit
| Atlas Freight | $120,000 | negotiation | 09-18 | legal redlines 9/3 | 50.7% of forecast |
| Delta Dental Partners | $38,000 | contract | 09-05 | countersign | — |
## Best case
| Birchwood Health $60,000 proposal | Cobalt Retail $45,000 (stale 26 d) | Harbor Logistics $52,000 (no next step) |
## Risks
- Slipped: Granite $150k (twice, prob halved) · Stale: 2 deals $195k · Concentration: Atlas 50.7%
- Needs a 73.4% win rate on open pipeline vs 41.7% history; median cycle 72 days > 21 business days left → new pipeline can't land
## What changed since Aug 25
In-period $645,000 → $545,000: won $40k (Juniper), lost $70k (Lumen), pushed out $30k (Oriole), pulled in $52k (Harbor), vanished $22k (Pax)
## By rep  Dana $150,000 · Luis $86,500 · Priya $0
## Calibration  4 quarters over-forecast by 11.1% → ×0.907 = $214,506 → plan for a ~$75k-85k miss
```

**Remaining gaps.** No activity capture or ML. Close-date history ("slipped twice") must be supplied as `slips`. No dashboard.

## 5. proposal-builder vs PandaDoc

**Scenario.** Northstar proposes a 9-clinic rollout to Kestrel Dental with Good/Better/Best options: 25/40/60 seats at $65/mo, onboarding fees, $2,400/yr premium support, a $1,000/mo CSM on Best, 15% annual-prepay discount, 8.875% sales tax, a 45-business-day timeline over Thanksgiving, and 30/40/30 onboarding payments.

| # | PandaDoc capability | Status | Why |
|---|---|---|---|
| 1 | Pricing tables in every plan ([pandadoc.com pricing table](https://www.pandadoc.com/features/quote/pricing-table/)) | MATCHES | `pricing_table` |
| 2 | Line-item and total discounts, % or flat ([help: discounts and taxes](https://support.pandadoc.com/en/articles/9714706-pricing-table-discounts-and-taxes)) | MATCHES | Line-item % and flat, total % and flat added (was total-% only) |
| 3 | Taxes on the subtotal (same article) | MATCHES | Tax after discount, rounded once |
| 4 | Multiple options / quote builder ([quote builder](https://support.pandadoc.com/en/articles/9714713-add-and-set-up-quote-builder)) | MATCHES | One table per option + `tier_comparison` |
| 5 | Document expiration date ([auto expirations](https://support.pandadoc.com/en/articles/9714665-auto-expirations)) | MATCHES | Audit requires "Valid until"; auto-expiry itself is hosting |
| 6 | Templates / content library | PARTIAL | One proposal spine in the playbook; no saved template library |
| 7 | Client-editable optional items and quantities | OUT OF SCOPE | Interactive document |
| 8 | E-signature, open tracking, payments | OUT OF SCOPE | |

| Check | Expected (independent) | Tool (after) | Before |
|---|---|---|---|
| Better: discount / subtotal | 33,600 × 15% = 5,040 / 32,060 | same | same |
| Better: tax (half-up cents) | 32,060 × 8.875% = 2,845.325 → 2,845.33 | 2,845.33 everywhere | field .33, display row .32 ✗ |
| Better: grand total | 34,905.33 | same in fields, rows, verdict | verdict/rows 34,905.32 ✗ |
| Good / Best totals | 20,223.53 / 62,080.53 | same | same |
| Per seat per month (Better) | 28,560 / 12 / 40 = 59.50 | 59.5 | same |
| Milestone end dates | 10-09, 10-30, 11-06, 12-08 (skips Nov 26-27) | same | same |
| Onboarding payments 30/40/30 of $3,500 | 1,050 / 1,400 / 1,050 | same | same |
| Audit finds prices written "USD 34,905.33" | yes | yes | "no prices found" ✗ |

**Deliverable (excerpt).**
```
# Proposal: One schedule for all nine Kestrel clinics — prepared for Tom Becker, 2026-09-28
Valid until 2026-10-28 · Prepared by Sam Ortiz, Northstar
## Summary
Nine clinics run reminders nine ways; 14% of hygiene visits were no-shows last quarter. One workflow in
nine weeks. Recommended: Better, USD 34,905.33 for year one including tax.
## Timeline
| Signature | 2026-10-05 | 30% of onboarding (USD 1,050) |
| Migration done | 2026-10-30 | 40% (USD 1,400) |
| Training done | 2026-11-06 | — |
| Go-live & hypercare done | 2026-12-08 | 30% (USD 1,050) |
## Investment
| | Good | Better ★ | Best |
| Scope | 25 seats, 5 clinics | 40 seats, 9 clinics, premium support | 60 seats, premium support, CSM |
| Year 1 ex tax | USD 18,575.00 | USD 32,060.00 | USD 57,020.00 |
| Year 1 incl. 8.875% tax | USD 20,223.53 | USD 34,905.33 | USD 62,080.53 |
## Next step
Reply "Better" (or your choice) by 2026-10-02; we send the order form for e-signature; kickoff 2026-10-05.
_audit: 100/100 · 10/10 sections · validity date · one CTA · 12 price mentions_
```

**Remaining gaps.** No e-sign, tracking or interactive quotes (OOS). No reusable template library. `tier_comparison` flags a rising per-seat price whenever tiers bundle services. That is a heuristic warning the AI must explain.

## 6. discovery-call vs Fathom Business (coaching metrics + MEDDPICC)

**Scenario.** A Northstar rep's call with Dana, COO-reporting ops lead at a 9-clinic dental group. The timestamped transcript runs 3.9 minutes. The rep pitches for 78 words up front, asks a leading question and a double-barrelled one, and jumps to "Can I send a proposal?". Dana gives rich pain (14% no-shows, 60 empty chairs/week at ~$180, managers 3-4 h/day on phones, two staff lost), a timeline (live before the January insurance reset), a signer (COO, anything over $20k) and a competitor (Weave demo). Budget is never discussed.

| # | Fathom capability | Status | Why |
|---|---|---|---|
| 1 | Talk time distribution ([help: scorecards & behavioral metrics](https://help.fathom.video/en/articles/450176)) | MATCHES | Talk share per speaker |
| 2 | Number of questions asked (same) | MATCHES | Also typed open / closed / leading / double-barrelled |
| 3 | Monologue length (same) | MATCHES | Longest rep monologue and longest prospect story |
| 4 | Team averages across calls (same: "average call performance data for team members") | MATCHES | New `compare_calls` (was MISSING) |
| 5 | Sales templates: Sales, SPICED, MEDDPICC, BANT ([help: customizing summaries](https://help.fathom.video/en/articles/3239809)) | PARTIAL | MEDDPICC scorecard (BANT lives in lead-qualifier); no SPICED |
| 6 | "Coaching metrics & AI scorecards" ([fathom.ai/pricing](https://www.fathom.ai/pricing)) | PARTIAL | Weighted MEDDPICC with stage gates; no custom rubric |
| 7 | Real-time coaching during the call ([help](https://help.fathom.video/en/articles/295360)) | OUT OF SCOPE | Live audio |
| 8 | Recording and transcription | OUT OF SCOPE | |

| Check | Expected (independent) | Tool (after) | Before |
|---|---|---|---|
| Rep talk share | 49.3% (whitespace words) | 49.6% (±1) | same |
| Call length | 3:55 = 3.9 min from timestamps | 3.9 | ignored timestamps ✗ |
| Rep questions / types | 9: 5 closed, 2 open, 1 leading, 1 double-barrelled | same | 3 open, 0 double ✗ |
| Open % | 2/9 = 22.2% | 22.2 | 33.3 ✗ |
| Topics missed | budget only | budget | pain, timeline, competition "missed"; budget "covered" ✗ |
| Rep fillers | none ("you'll like the dashboard" is a verb) | {} | like ×2 ✗ |
| MEDDPICC raw / weighted / gate | 11/24 · 14.5/28.5 = 50.9% · blocked by Champion 1 < 2 | same | same |

**Deliverable (excerpt).**
```
# Discovery debrief — Kestrel Dental · 2026-09-28
## Snapshot
Talk ratio rep/prospect: 49.6/50.4% · Questions: 9 (22% open) in 3.9 min · Longest rep monologue: 78 words (a pitch, before any question)
Topics covered: pain, impact, timeline, decision process, competition, current solution · Missed: budget
## MEDDPICC scorecard (11/24 · 50.9% weighted · developing)
| Identify pain | 3 | "reminders are the first thing to drop… 3-4 hours a day on the phone" | — |
| Metrics | 2 | 14% no-shows; ~60 empty hygiene chairs/week at ~$180 | agree the target number |
| Economic buyer | 2 | COO Mark Feld signs >$20k | get Mark on call 2 |
| Champion | 1 | Dana engaged, untested | "Would you present this to Mark?" |
| Decision criteria 0 · Decision process 1 · Paper process 0 · Competition 2 (Weave demo, no decision)
## Stage recommendation
Stay in discovery — proposal gate needs Champion ≥ 2 (is 1). Don't send the proposal you offered yet.
## Top 3 fixes
1. You pitched for ~30 s before asking anything. 2. "You'd agree… right?" and "Who else…, and what's your timeline?" — one clean question at a time.
3. Budget never came up: "How are projects like this usually funded — existing budget or new approval?"
```

**Remaining gaps.** Topic detection is keyword-based: better now, but paraphrase-heavy calls can still slip through. The fixed MEDDPICC rubric has no SPICED or custom scorecards. No live coaching.

## 7. sales-call-debrief vs Fathom Business (summaries, action items, CRM sync)

**Scenario.** The last 2.8 minutes of an AP-automation demo, a Thursday call (2026-09-24) with Leo (controller) and Aisha (AP lead). Pricing is floated at ~$2,900/month, Leo says "a bit more than we budgeted", the rep proposes a CFO call "next Tuesday" and promises docs "by end of next week". The rep wants a HubSpot update.

| # | Fathom capability | Status | Why |
|---|---|---|---|
| 1 | "Advanced call summaries, including custom summaries" ([fathom.ai/pricing](https://www.fathom.ai/pricing)) | MATCHES | Playbook output format, with quotes |
| 2 | "AI-generated action items" (pricing) | MATCHES | `detect_next_steps`: owner, resolved date, real vs intention |
| 3 | "CRM field sync, updating records after meetings" (pricing) | MATCHES (mapping) / OUT OF SCOPE (push) | `map_crm_fields` validates and maps; the push needs the customer's CRM connector |
| 4 | "Coaching metrics" (pricing; [help 450176](https://help.fathom.video/en/articles/450176)) | MATCHES | `call_metrics` |
| 5 | "Deal View summarizing insights" across meetings (pricing) | PARTIAL | The AI can combine pasted calls; tools run per call |
| 6 | Ask Fathom natural-language Q&A over a meeting ([salesdorado review](https://salesdorado.com/en/revenue-operations/review-fathom/)) | MATCHES | The host AI answers from the transcript |
| 7 | Recording, transcription, meeting bot | OUT OF SCOPE | |

| Check | Expected (independent) | Tool (after) | Before |
|---|---|---|---|
| Talk shares Priya/Leo/Aisha | 60.3 / 28.2 / 11.5 | 60.3 / 28.3 / 11.4 (±0.5) | same |
| Length | 24:02 → 26:52 = 2.8 min | 2.8 | 2 (150 wpm guess); with call_minutes=32, 10 words/min ✗ |
| "next Tuesday" said Thu 09-24 | Tue 09-29 (next calendar week, meeting-ops convention) | 09-29 | line not detected; resolver gave 10-06 ✗ |
| "by end of next week" | Fri 10-02 | 10-02 | Mon 09-28 ✗ |
| Agreed next step date | 09-29 (CFO call, prospect sends invite) | 09-29 | 09-28 ✗ |
| Temperature | warm (5 positive types, 1 price concern) | warm | HOT ✗ |
| Amount "34.8k" | 34,800 | 34,800 | 34.8 ✗ |
| HubSpot payload | only real properties; champion/risks flagged as custom | yes | champion/risks/competitors in payload, "ready to push" ✗ |

**Deliverable (excerpt).**
```
# Call debrief — Harbourline Foods · 2026-09-24 · demo
**Metrics:** rep 60.3% talk (demo benchmark 60-65%) · 1 question · longest monologue 80 words (~32 s) · 2.8 min excerpt
**Temperature:** WARM — 5 positive signals, but "That's a bit more than we budgeted, honestly."
## What we learned
- Pain is quantified — "we lose about 20 hours a week keying invoices… paid a duplicate invoice twice last quarter"
- Rollout is being planned — "When we roll this out I'd want the controller in the pilot group too"
- Authority sits above Leo — "I'll need to run it by our CFO, Dan"
## Next step
**ROI review call with CFO Dan — Leo sends the invite — Tue 2026-09-29**
Also: Priya sends proposal + Netsuite security overview by Fri 2026-10-02
## CRM update (HubSpot)
| dealstage | presentationscheduled | amount | 34800 | closedate | 2026-10-30 (est.) |
| hs_next_step | Hold ROI review with CFO Dan Reyes on Tue Sep 29 | hs_forecast_probability | 0.35 |
Custom (create first or put in description): champion = Leo Grant · risks = price above budget; CFO not yet engaged
Task: due 2026-09-29
```

**Remaining gaps.** Signal and commitment detection is regex-based, so sarcasm and indirect phrasing need the AI's own read (the playbook says so). No multi-call deal view tool. "next <weekday>" follows the next-calendar-week convention and now flags when the other reading differs.

## 8. objection-handler vs Crystal (personality-based selling)

**Scenario.** At proposal stage a finance-ops lead writes: *"Honestly the price is almost double what we pay for Tipalti today, and I can't justify $38k a year to our CFO right now."* Value facts: 12 AP clerks save ~4 h/week each at a $38/h loaded cost, ~$9k/yr of duplicate-payment errors avoided, $4k implementation, Tipalti at $19,800/yr.

| # | Crystal capability | Status | Why |
|---|---|---|---|
| 1 | Personality (DISC) prediction from a LinkedIn profile ([crystalknows.com/pricing](https://www.crystalknows.com/pricing)) | OUT OF SCOPE | Data and model |
| 2 | Understand the motivation behind objections by personality ([Crystal sales resources](https://www.crystalknows.com/resource/improve-sales-effectiveness)) | PARTIAL | Playbook "style read" (labelled guess from their words); no data-backed profile |
| 3 | "Pricing Discussions — talk about money with confidence" ([solutions/sales](https://www.crystalknows.com/solutions/sales)) | MATCHES | Classify, price sub-types, ROI, payback, reframe |
| 4 | "Email Communication — understand your recipient's personality" (solutions/sales) | PARTIAL | Channel-specific response with style-ordered facts |
| 5 | Playbooks for a specific person and purpose ([crystalknows.com/why-crystal/playbooks](https://www.crystalknows.com/why-crystal/playbooks)) | MATCHES | Response plus push-back lines for this objection |
| 6 | Chrome extension on LinkedIn/Gmail | OUT OF SCOPE | |

| Check | Expected (independent) | Tool |
|---|---|---|
| Hours / time value / annual value | 4×12×48 = 2,304 h; ×$38 = $87,552; +$9,000 = $96,552 | same |
| ROI year 1 / steady | 54,152 / 42,400 = 127.7% · 58,152 / 38,400 = 151.4% | same |
| Payback / break-even hours | 42,400 ÷ 8,046 = 5.3 months · 38,400 ÷ 21,888 = 1.75 h/person/week | same |
| 3-year net | 3×96,552 − 3×38,400 − 4,000 = 170,456 | same |
| Per user per day / delta vs Tipalti | 38,400/12/250 = $12.80 · +$18,600 (+93.9%) | same |
| Price sub-types | competitor-cheaper ("double what we pay for Tipalti") + value gap ("can't justify") | same (not detected before) |

**Deliverable (excerpt).**
```
## What they actually said
"…almost double what we pay for Tipalti… can't justify $38k a year to our CFO" → **price** (67%) · secondary: authority
· sub-types: competitor-cheaper + value gap · smokescreen: no
Style read (guess): analytical — leads with a comparison and a justification problem, not emotion.
## Isolate first
"Setting price aside — is everything else what you'd need? And is Tipalti doing the invoice coding and 3-way match today?"
## The numbers
12 clerks × 4 h/week × 48 weeks × $38 = $87,552 + $9,000 errors avoided = $96,552/yr on a $38,400 price
→ ROI 151% steady-state (128% year 1), payback 5.3 months, each month of waiting ≈ $8,046. Break-even: 1.75 h/clerk/week.
Price: $12.80 per clerk per working day; +$18,600/yr vs Tipalti buys back ~2,300 clerk-hours.
## Response (email, 96 words)
Fair challenge — Tipalti is cheaper on licence. The comparison that matters for your CFO is total cost: your team
estimated ~4 hours a week per clerk still goes to manual coding. Across 12 clerks that's about $87k a year, plus
~$9k in duplicate payments. At $38.4k we pay back in about 5 months. Would it help if I put those numbers into a
one-page CFO summary using your own inputs, and we review it together Thursday?
```

**Remaining gaps.** No personality data. The style read is an explicit guess from the text. The classifier is keyword-based.

## 9. negotiation-coach vs Crystal (negotiation playbooks)

**Scenario.** Procurement at Meridian Health wants 25% off a $120,000/yr proposal that has already been sent. Floor $96k, target $110k, their estimated walk-away $115k. They hold a competitor quote worth ~$98k to them, and our BATNA is ~$60k. They ask for net-60, a 3-year price lock, extra seats and a 99.95% SLA. Options to compare: 1-yr 10% upfront, 3-yr 18% upfront, 2-yr 12% quarterly, 3-yr 15% + 5% escalator monthly, at 12% cost of capital.

| # | Crystal capability | Status | Why |
|---|---|---|---|
| 1 | DISC profile of the counterpart ([pricing](https://www.crystalknows.com/pricing)) | OUT OF SCOPE | Data |
| 2 | "How to Negotiate With Different Personalities" ([resource](https://www.crystalknows.com/resource/how-to-negotiate-with-personalities)) | PARTIAL | New counterpart-style guidance in the playbook (guess, labelled) |
| 3 | "Negotiation — create win-win situations" / "negotiate effectively" ([solutions/sales](https://www.crystalknows.com/solutions/sales)) | MATCHES | ZOPA, anchor, concession ladder, PV packages, trade pairs, MESOs |
| 4 | Playbook for a specific person and situation, e.g. "how to negotiate pricing with a new client" ([playbook update](https://www.crystalknows.com/resource/playbook-update)) | MATCHES | Deal-specific numbers table and script |
| 5 | Chrome extension | OUT OF SCOPE | |

| Check | Expected (independent) | Tool (after) | Before |
|---|---|---|---|
| ZOPA / width / midpoint | 96k-115k / 19k / 105.5k | same | same |
| Anchor | $120k (the sent proposal; can't re-anchor above it) | 120,000 | 123,200 ✗ |
| Ladder prices (95% of room usable, 50/30/20) | 108,603 / 101,763 / 97,203; reserve 1,203 | same | same |
| PV 3-yr 18% upfront | 98,400 × (1 + 1.12⁻¹ + 1.12⁻²) = 264,701.02 | same | same |
| PV 2-yr quarterly / 3-yr escalator monthly | 191,568.9 / 272,743.0 (stdlib PV at mean arrival 0.375 / 0.458 y) | same | same |
| Cash in first 12 months, quarterly / monthly | 105,600 / 102,000 (all year-1 instalments) | same | 66,000 / 55,284 ✗ |
| Cheap gives / protect | seats, net-60 / SLA (value÷cost) | same | same |

**Deliverable (excerpt).**
```
## Numbers (keep open during the call)
| Walk-away $96,000 | Target $110,000 | Anchor $120,000 (already sent) | ZOPA $96k–$115k | Their est. walk-away $115,000 | Power: theirs ($98k alt vs our $60k) |
## Concession ladder
| 1 | $108,603 | −$11,397 | 47.5% of room | annual prepayment |
| 2 | $101,763 | −$6,840 | 28.5% | 3-year term |
| 3 | $97,203 | −$4,560 | 19.0% | signature by Oct 30 |   reserve $1,203 for a signature on the spot
## Packages compared (PV at 12%)
| 3-yr 15% + 5% escalator, monthly | TCV $321,555 | 15.0% | PV $272,743 | "15% off" |
| 3-yr 18% upfront | TCV $295,200 | 18.0% | PV $264,701 | "18% off, locked 3 years" |
| 2-yr 12% quarterly | TCV $211,200 | PV $191,569 |  1-yr 10% upfront | $108,000 | PV $108,000 |
## Trades
Cheap gives: 10 extra seats, net-60 · Protect: 99.95% SLA · Pairs: if seats → case study + reference; if net-60 → annual prepay
## Script
_Style read (guess): direct — short procurement emails, a single number ask._
**Open:** restate the agreed value, hold $120k with its reason (9-clinic scope). Never go above it.
**When they ask for 25%:** silence → "What would the 25% need to buy you?" → "If you can prepay annually, I can get to $108,603."
**Walk-away line:** "Below $96k we'd both be better served by the other quote — the door stays open."
```

**Remaining gaps.** No personality data. The PV of monthly/quarterly payments uses a mean-arrival approximation (within $1 of an exact instalment schedule in this scenario).

## 10. linkedin-prospector vs LinkedIn Sales Navigator Core

**Scenario.** An SDR pastes Rachel Okonkwo's profile (VP Marketing at Quillbase since Jul 2026, a post on cutting MQL targets, 12 mutuals). The SDR's own draft note is pitchy and 214 characters. Plan: 140 prospects from Mon 2026-10-05 (Oct 12 holiday) and a 12-meetings/month target.

| # | Sales Navigator capability | Status | Why |
|---|---|---|---|
| 1 | "Changed jobs in past 90 days" spotlight ([lagrowthmachine guide](https://lagrowthmachine.com/how-to-use-linkedin-sales-navigator/)) | PARTIAL | Detected on a pasted profile (months in role); no database search |
| 2 | "Posted on LinkedIn" spotlight (same) | PARTIAL | Posts pulled from pasted activity |
| 3 | Shared connections / TeamLink (TeamLink is Advanced-only) (same) | PARTIAL | Mutual count or names from the paste |
| 4 | InMail and invitation-note limits ([LinkedIn help a411986](https://www.linkedin.com/help/linkedin/answer/a411986/inmail-character-limits), [a563153](https://www.linkedin.com/help/linkedin/answer/a563153)) | MATCHES | `check_message`, now account-aware (200 free / 300 Premium) |
| 5 | Lead and account search over the member database | OUT OF SCOPE | Data |
| 6 | 50 InMail credits/month and sending | OUT OF SCOPE | |
| 7 | Saved leads and alerts | OUT OF SCOPE | |

| Check | Expected (independent) | Tool (after) | Before |
|---|---|---|---|
| Months in role (Jul → Sep 2026) | 2 (calendar difference; LinkedIn shows "3 mos" inclusive) | 2 | 2 |
| Headline claim below the name line | found | found | missed ✗ |
| Pitchy note length | 214 chars | 214 | 214 |
| Fits a free account (LinkedIn help: 200 chars) | no, over by 14 | fits = false, over_by 14 | "fits" (limit 300) ✗ |
| Rewritten note | 150 chars ≤ 200 | 150, score 100 | — |
| Touch dates (8) | 10-05, 10-06, 10-08, 10-13, 10-15, 10-19, 10-23, 10-26 | same | same |
| Enrolment 140 at 20/day | 7 business days, last cohort 10-14 | same | same |
| Capacity for 12 meetings | ⌈12 / (0.35×0.25×0.30)⌉ = 458 invites, 5 weeks, 2 accounts/month | same | same |

**Deliverable (excerpt).**
```
## Hook
New role: VP Marketing at Quillbase since Jul 2026 (~3 months) — plus her post: "MQLs are a vanity metric… cut our MQL target by 40%"
## Connection note (150/200 chars — fits free and Premium)
Rachel, your post on cutting the MQL target 40% and still growing pipeline stuck with me. Curious what replaced MQLs on your dashboard at Quillbase.
## Message 1 — after acceptance (196 chars)
Thanks for connecting, Rachel. Congrats on the first quarter at Quillbase. When you swapped the MQL target for pipeline quality, what did you start measuring instead, and who owns that number now?
## Touch plan
| 0 | Mon 10-05 | LinkedIn | view + comment on the MQL post |  1 | Tue 10-06 | connect |
| 3 | Thu 10-08 | message 1 | 6 | Tue 10-13 | message 2 (Oct 12 holiday) | 10 | Thu 10-15 | email bridge |
| 14 | Mon 10-19 | engage | 18 | Fri 10-23 | breakup | 21 | Mon 10-26 | withdraw if pending |
## Capacity
140 prospects at 20/day = 7 business days (last cohort 10-14). 12 meetings ≈ 458 invites = 5 weeks on one
account → split across 2 reps or move part of the list to email.
```
(Message 1 as first drafted carried two questions. The playbook allows one; the checker allows up to two, so tighten it by hand.)

**Remaining gaps.** Everything Sales Navigator is paid for (search, filters across the member base, alerts, InMail credits) is data we don't have, hence **BELOW** on the overlapping job. Some third-party guides state 300 chars for all accounts; LinkedIn's own help page states 200. The tool follows LinkedIn and exposes `premium`.

---

## Issues outside the sales folder (not edited)
- None blocking. `hundred/lib/text.words` splits hyphenated words and URLs into several words. The sales agents now count words with `_common.word_count`; other categories that use `text.words` for "word count" targets inherit the same over-count.
- `hundred/lib/text.syllables` is a heuristic. On the cold-email scenario it gave FRE 77.4 vs 74.4 from dictionary syllables. That is within tolerance and did not change any pass/fail.
