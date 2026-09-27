# Career & HR — parity evaluation

Evaluated 2026-09-27 against the paid tools a customer would otherwise buy for the **overlapping job**
(prices from `marketing/pricing_research/eng_product_career_ecom.md`). We could not run the competitors,
so each checklist uses only features the vendor **documents** (URL cited). The scenarios, inputs and
hand-verified numbers are replayable in `tests/scenarios/test_career.py` (26 tests).

**Method.** For each agent: `python -m hundred.admin brief <slug> "<task>"` → follow the playbook →
call every tool with `python -m hundred.admin run <slug> <tool> -` → write the deliverable in the
playbook's output format → check every planted item and number by hand or with stdlib-only reference
code (the helpers at the top of the scenario file never import `hundred`).

**Scoring.** MATCHES = 1, PARTIAL = 0.5, MISSING = 0. OUT OF SCOPE items (job-board search, tracking
databases, live video/voice, HRIS/ATS systems of record, human coaches) are listed but not scored.

## Overview

| Agent | Comparable & price | Checklist | Correctness checks (planted / hand-verified) | Verdict | Fixes made |
|---|---|---|---|---|---|
| resume-optimizer | Jobscan Premium, $49.95/mo ($89.95/qtr) | 8.5 / 11 | 6/6 must-have + 5/5 nice-to-have gaps found, 0 false keywords after fix (before: 3 false incl. "growth" as a must-have); tenure 27/33/44 mo, total 104 mo, 7-mo gap ✓ | **AT PAR** | 6: clause-level must/nice, literal ATS match, "A or B" counted once, duty-only repeat rule, acronym noise, irregular verbs; + years_required |
| cover-letter | Kickresume Premium, $24/mo (Teal+ $29/30 days) | 4.5 / 6 | 12/12 planted clichés, 0 false; coverage: title-only mention now "partial" | **AT PAR** | 5: coverage requires >½ of a requirement's skills, evidence window ±1 sentence, greeting/sign-off not paragraphs, "fast learner", "Gainsight." extraction |
| interview-coach | Final Round AI Pro, $25+/mo; Yoodli $8–20/mo | 7 / 9 | all-"we" story: we=11, I=0, 7 "we" in Action ✓ (was **not flagged** before fix); fillers 13 hand-counted ✓; 48 s spoken ✓ | **AT PAR** (text) · BELOW on spoken delivery | 4: "we"-actor Action cues + story-wide ownership, "like"-as-verb, spread prep plan, non-inclusive wording |
| salary-negotiator | Levels.fyi negotiation coaching, $1,250 one-time | 3.5 / 5 | Offer A 237/246/261/261k, B 267.5/242.5k×3, avg 251,250 vs 248,750 ✓; Amazon 5/15/40/40 vest calendar ✓; 10-yr value $114,638.79 ✓ | **AT PAR** on math & scripts · **BELOW** overall (no market data) | 2: cumulative "crossover" (B wins unless you stay 4 yrs), `semiannual` cadence for Amazon |
| job-description | Textio (~$10–25k/yr, 3P); Datapeople (~$11k/yr, 3P) | 7.5 / 10 | 7/7 GFK masculine + 2 slang + 1 feminine + 11/11 exclusionary, 0 false positives on 3 decoys; band 80–110k: Q1 87.5k, mid 95k, spread 37.5%, CR 1.032 ✓ | **AT PAR** | 5: GFK 2011 stem list (strong vs functional), plural forms, context vetoes ("paid family leave", "mature product"), benefits lines not requirements, exclusionary/trait flags in requirement audit |
| hiring-scorecard | Greenhouse Recruiting (price not public; Datapeople ~$11k/yr is the pricing-file comp) | 6.5 / 7 | 7/7 protected criteria refused, 0/5 job-related refused; Dana 70.6 / Luis 58.1 ✓; outlier Jordan −1.58 vs median rater ✓; 5/5 biased feedback remarks struck | **ABOVE** on scoring/debrief analysis | 5: protected-term coverage (age, sex, religion, pregnancy stems…), refusal before the 8-item cap, decision sensitivity per rater, median-based leniency, protected sentences ≠ evidence |
| performance-review | Lattice Performance, $10/seat; 15Five Kona Coach, $19/manager | 4.5 / 6 | 16/16 planted phrases (7 personality/protected, 6 vague, 2 absolutes, 1 peer comparison) + recency ✓; goals 100/70/80/150 → 97.0% ✓ | **AT PAR** | 6: dead stems `pregnan`/`religio` fixed, "pleasure to work with"/"solid"/"seems"/"committed", Snyder-2014 gender note, SBI never launders a trait, median-manager calibration, "Q1 2027" excluded from cycle |
| onboarding-planner | BambooHR onboarding (3P $10–25/employee/mo) | 3.5 / 5 | day 30/60/90 = Dec 22 / Jan 21 / Feb 22 (Sat→Mon) ✓; phase business days 20/18/21 ✓; pre-boarding −15…−1 ✓; 4 planted plan errors caught ✓ | **AT PAR** | 1: "end of week 1" = Wed Nov 25 (3 working days) + separate day-5 date + warning (was reporting Tue Dec 1 as end of week 1) |

Test summary: `pytest -q tests/agents -k career tests/scenarios/test_career.py` → 99 passed;
`pytest -q tests/test_library.py` → 303 passed.

**Where a plain AI (no tools) would likely slip — not measured.** We did not run a no-tools baseline, so
we don't claim one. The traps these scenarios contain, which we had to check by hand: the 4-year
leader (Offer A) *loses* on cumulative pay at 1, 2 and 3 years; Amazon's year-2 vest is two 7.5%
payments, not one 15%; the Monday-before-Thanksgiving hire has a 3-day first week, so "end of week 1"
and "day 5" are different dates; day 90 lands on a Saturday; in a 4-interviewer panel the harsh
outlier makes a normal interviewer look lenient against the panel *mean* (+0.65).

**Core/lib notes (described, not edited).** `hundred/admin.py brief` raises `BrokenPipeError` when piped
into `head` (cosmetic). At one point during the run the registry printed "skipping agent module
hundred.agents.legal.contract_reviewer: f-string expression part cannot include a backslash" (another
category's file, being edited in parallel); it had cleared by the final `test_library.py` run.

---

## 1. Resume Optimizer — vs Jobscan

**Scenario.** "Tailor my resume to this Product Manager II, Growth JD at Ledgerly." Input: Maya Chen, a
mid-level PM (3 roles, Jun 2017 – present, a 7-month gap), and a JD whose must-haves plant six gaps the
resume doesn't name (A/B testing, Amplitude/Mixpanel, stakeholder management, OKRs, prioritization,
go-to-market) and five nice-to-have gaps (B2B, SaaS, payments/fintech, Stripe, Python).

**Parity checklist** — Jobscan match report, <https://www.jobscan.co/resume-scanner>:

| Jobscan feature (documented) | Status | Why |
|---|---|---|
| Match Rate % | MATCHES | must / nice / overall coverage %, before → after |
| Hard skills | MATCHES | curated lexicon + aliases + JD proper nouns; all planted gaps found |
| Soft skills | PARTIAL | only the soft skills in our lexicon (communication, stakeholder management, collaboration…) |
| Other keywords (titles, certs, tools) | MATCHES | acronyms, tools and the title check |
| Searchability / ATS tips: contact, headings, file type, dates | MATCHES | `check_ats_format` |
| Job title match | MATCHES | `title_in_resume` |
| Recruiter tips: measurable results | MATCHES | `score_bullets` quantified % and XYZ rewrites |
| Recruiter tips: word count / length | MATCHES | page estimate vs the 1-page/2-page rule |
| Recruiter tips: job level match | PARTIAL | `years_required` vs `total_months` (added); no seniority-title comparison |
| ATS-specific tips (detects the company's ATS) | MISSING | we have no employer→ATS data |
| Spelling / grammar | PARTIAL | left to the host AI; no deterministic check |

**Correctness.**

| Check | Expected (by hand) | Tool (after fix) | Before fix |
|---|---|---|---|
| Planted must-have gaps | 6 | 6/6 tagged must | 6/6, but **PM experience mis-tiered as nice** ("…, ideally in B2B SaaS") |
| Planted nice gaps | 5 | 5/5 | 4/5 — "payments" not in the lexicon |
| False keywords | 0 | 0 | "ii", "ny" as keywords; team name "growth" as a **must-have** |
| "analytics" (resume says "Google Analytics") | present | matched (literal) | reported missing |
| Amplitude **or** Mixpanel | 1 requirement | 1 (`alternatives`) | 2 misses |
| Must-have coverage | 4/10 = 40% | 40.0% | 18.2% (2/11) |
| Tenure per role | 27 / 33 / 44 mo | 27 / 33 / 44 | ✓ |
| Total / gap | 104 mo = 8 y 8 m; Sep 2019–Mar 2020 = 7 mo | ✓ | ✓ |
| "Ran experiments…" bullet | action verb | 100 | "does not start with an action verb" (75) |

**Deliverable excerpt** (output format of the playbook):

```
## Fit snapshot
Must-have coverage: before 40% → after 80% · Nice-to-have: 12.5% → 50% · Pages: ~0.6 · Parse risks: 0
Missing (cannot honestly claim): OKRs, Amplitude/Mixpanel, Stripe, Python, payments/fintech
## Fixes applied
- Headline → "Product Manager — Growth & Activation (B2B SaaS)" · JD-matching bullets moved first in each role
- Summary said "6+ years"; compute_tenure gives 8 yrs 8 mo total (6 yrs 5 mo in B2B SaaS) — corrected
## Bullet rewrites (before → after, score)
- "Responsible for the driver onboarding roadmap and backlog in Jira" (33) →
  "Owned roadmap prioritization for driver onboarding, shipping [N, confirm] releases in 2025 via a scored Jira backlog" (100)
- "Worked with engineering and design on various improvements to the dispatch app" (40) →
  "Drove stakeholder management across engineering, design and sales, cutting dispatch support tickets ~[X%, confirm]" (100)
- "Ran experiments on pricing page copy that lifted paid conversion from 3.1% to 3.8%" (100) → keep; add "A/B testing" verbatim
## Timeline check
Total experience: 8 yrs 8 mo · Median tenure: 2 yrs 9 mo · Gaps: Sep 2019 – Mar 2020, 7 mo
(suggest a one-line "Career break — <reason, confirm with you>" entry; don't hide it)
## Before you send
1. Every [confirm] number must be yours — delete it if you can't stand behind it.
```

**Honest gaps.** No employer→ATS lookup; soft-skill list is small; the tool can't know that "ran
experiments" *is* A/B testing — the playbook's AI does that mapping, and the "after" 80% depends on it
doing so truthfully (placeholders `[N, confirm]` instead of invented numbers).

---

## 2. Cover Letter Writer — vs Kickresume AI Cover Letter Writer (and Teal+)

**Scenario.** Same candidate and JD. The user pastes a generic draft (12 planted clichés: "To Whom It May
Concern", "I am writing to", "passionate", "results-driven", "team player", "proven track record",
"perfect fit", "your innovative company", "fast learner", "hit the ground running", "fast-paced
environment", "I look forward to hearing from you") and asks for a letter that works.

**Parity checklist** — <https://www.kickresume.com/en/ai-cover-letter-writer/>:

| Kickresume feature (documented) | Status | Why |
|---|---|---|
| Enter job title + paste the job ad → tailored letter | MATCHES | `extract_requirements` → letter answers the top 3 |
| "Choose one of your resumes" to use real experience | MATCHES | playbook maps each requirement to resume evidence; never fabricates |
| Regenerate / rewrite any part | MATCHES | host AI iterates; `check_letter` re-scores each pass |
| Length guidance 250–400 words, 2–4 body paragraphs | MATCHES | 250–350 words, 3–5 body paragraphs checked |
| 9 visual templates | MISSING | we deliver text into the user's doc |
| ATS-friendly structure/formatting | PARTIAL | plain-text structure; no file rendering |

**Correctness.**

| Check | Expected | Tool | Before fix |
|---|---|---|---|
| Planted clichés found | 12 | 12, 0 false positives | 11 ("fast learner" missed) |
| Bad draft: "I am writing to apply for the Product Manager II position" vs "4+ yrs PM experience, ideally B2B SaaS" | not an answer | `partial` (1 of 3 skills) | **covered** |
| Bad draft: "I have used SQL." vs "SQL and A/B testing" | not an answer | `partial`, skills_missing = a/b testing | **covered** |
| Good letter paragraphs | 5 body paragraphs | 5 | 7 (greeting + contact line counted) → false "use 4 paragraphs" issue |
| "…Salesforce and Gainsight." | both skills | both | the shared extractor dropped a capitalised product name before a sentence-final period |
| Good letter | 250–350 words, 0 clichés | 287 words, 100/100, 3/3 covered, 2 quantified | 95 |

**Deliverable excerpt:**

```
**Subject (if emailed):** Application — Product Manager II, Growth — Maya Chen
Dear Ledgerly Growth Hiring Team,
Twenty thousand small businesses trust Ledgerly with their back office, and the moment that decides
whether a new one stays is the first invoice paid. That activation moment is what I have spent eight
years improving, which is why the Product Manager II, Growth role stands out to me.
At Cartwheel Logistics, a B2B SaaS platform for freight carriers, I own the carrier sign-up funnel.
Cutting the form from 14 fields to 6 raised completed sign-ups 23% in two quarters. … One pricing-page
test lifted paid conversion from 3.1% to 3.8%.
… I have not used OKRs formally, but every quarter I tied our roadmap to two measurable targets …
Your posting also asks for Amplitude or Mixpanel. My analytics work has been in Looker and SQL …
---
Score: 100/100 · Words: 287 · Requirements covered: 3/3 · "I" sentences: 11.8%
Why this works: opens on Ledgerly's own activation moment; every proof has a number; the two gaps
(OKRs, Amplitude) are named honestly instead of bluffed.
```

**Honest gaps.** No visual templates. Coverage is lexical: it proves the letter *names* the
requirement's skills near a number, not that the evidence is persuasive — that stays the host AI's job.

---

## 3. Interview Coach — vs Final Round AI and Yoodli

**Scenario.** "Final-round PM interview at Ledgerly on Thu Oct 8; here's my answer to 'tell me about a
launch'." The answer is all "we" (11 "we/our/the team", 0 "I"). Also a rambling "tell me about yourself"
with planted fillers, and a prep plan from Mon Sep 28 at 2 h/day.

**Parity checklist** — <https://www.finalroundai.com/>, Yoodli features per
<https://www.geekwire.com/2023/speech-analysis-startup-releases-ai-tool-that-simulates-difficult-job-interview-conversations/>
and <https://makerstack.co/reviews/yoodli-review/>:

| Feature (documented) | Status | Why |
|---|---|---|
| Practice by scenario (behavioral, product case, coding, system design…) — Final Round | PARTIAL | behavioral + role-family banks; no coding/system-design drills |
| Post-session debrief: what worked, what to fix, readiness — Final Round | MATCHES | `check_star_story` / `lint_answer` score, issues and fixes |
| Re-drill weak spots — Final Round | PARTIAL | playbook re-runs the weakest stories; no cross-session memory |
| Filler words — Yoodli | MATCHES | `lint_answer` |
| Weak / hedging language — Yoodli | MATCHES | "I think", "kind of", "I guess"… |
| Pacing (wpm) — Yoodli | PARTIAL | spoken length estimated at 150 wpm from text; no audio |
| Conciseness — Yoodli | MATCHES | run-on sentences, length budget |
| Non-inclusive language — Yoodli | MATCHES | added in this eval (was MISSING) |
| AI roleplay interviewer — Yoodli/Final Round | PARTIAL | host AI can roleplay in text; no voice |
| Eye contact, body language (video) | OUT OF SCOPE | |
| Live interview copilot (answers during a real interview) | OUT OF SCOPE | |

**Correctness.**

| Check | Expected (by hand) | Tool (after fix) | Before fix |
|---|---|---|---|
| "we/our/the team" in story | 11 | we_total 11, I 0 | not reported |
| "we" in the Action | 7 | 7 → issue "Action uses 'we' 7× vs 'I' 0×" | **Action not detected, ownership not flagged**; "Situation 74%" |
| Words / spoken time | 120 / 48 s at 150 wpm | 120 / 48 | ✓ |
| Rewritten "I" story | — | 100/100, A 51.6% | — |
| "like" fillers in "…who, like, really loves data… I just really like growth stuff and things like that" | 2 (the verb is not a filler) | 2 | 3 |
| Prep plan Sep 28 → Oct 8 | 10 days; 11 h of phases + 1 h light day + 0.5 h | 12.5 h, light review Wed Oct 7 | phases crammed into Sep 28–Oct 3, then **3 idle days** |

**Deliverable excerpt:**

```
### Story 1 — Carrier sign-up rescue (covers: ownership, execution, influence) · ~74 sec · score 100
**S:** Q3 activation target at risk; sign-up conversion stuck at 40%. **T:** My job: find the drop-off
before quarter close. **A:** I pulled the funnel in SQL (60% of abandons on page 2 of a 14-field form);
I watched 30 session recordings; I proposed 6 fields; when Compliance pushed back I agreed a 7-day
grace period with their lead; I designed the A/B test with a pre-set +10% bar. **R:** sign-ups +23%,
Q3 target hit a month early, sign-up tickets down a third. **Reflection:** I now meet the blocking team in week one.
## Delivery notes
- Original answer: "we" 7× vs "I" 0× in the Action — the panel can't see your part; no reflection line; 48 s is thin.
- "Tell me about yourself": 13 fillers/hedges (33% of words), no number, doesn't restate the question.
## Prep schedule
| Mon 9/28 | Research | 1.5 | … | Tue 10/6 | Buffer | 0 | Wed 10/7 | Light review + logistics | 1.0 | Thu 10/8 | Interview 14:00 |
```

**Honest gaps.** Text only: no voice pacing, no video, no coding/system-design drills. Against Yoodli's
spoken-delivery analytics we are BELOW; on the content of a behavioral answer we are at par.

---

## 4. Salary Negotiator — vs Levels.fyi negotiation coaching

**Scenario.** "Offer A: $165k base, $60k + $45k sign-on, $240k RSUs on an Amazon-style 5/15/40/40 vest.
Offer B: $175k base, 10% bonus, $25k sign-on, $200k RSUs, 4-year even vest with a 1-year cliff. I'm on
$150k + 8%. Market p50 $170k, p75 $185k. Which is better, and what do I counter A with?"

**Parity checklist** — <https://www.levels.fyi/services/> (vesting reference:
<https://www.levels.fyi/blog/unique-vesting-schedules.html>):

| Levels.fyi feature (documented) | Status | Why |
|---|---|---|
| Offer evaluation incl. equity analysis (startup & Big Tech) | MATCHES | `compare_offers` (RSU/options/haircut), `vesting_schedule` |
| Personalized negotiation scripts | MATCHES | playbook email/call script + `script_line` |
| Strategy call (what to ask for, which levers) | MATCHES | `plan_counter` ask/landing/levers, `raise_value` |
| Data Explorer (market comp data) | MISSING | the user must bring p50/p75; we have no comp dataset |
| Follow-up calls and email support through the process | PARTIAL | the host AI conversation; no human |
| Recruiter coaches with 8+ years' experience | OUT OF SCOPE | human service |
| Guaranteed $10k+ increase or refund | OUT OF SCOPE | |

**Correctness** (all by hand):

| Check | Expected | Tool |
|---|---|---|
| Offer A by year | 165+60+12 = 237k; 165+45+36 = 246k; 165+96 = 261k; 261k | ✓ |
| Offer B by year | 192.5+25+50 = 267.5k; 242.5k × 3 | ✓ |
| 4-yr average | A 251,250; B 248,750; Stay 162,000 | ✓ |
| Year-1 cash | A 225,000; B 217,500 | ✓ |
| Cumulative leader | B 267.5/510/752.5k vs A 237/483/744k → **B leads through year 3**, A only at year 4 | ✓ `crossover` (added) |
| Amazon vest, semiannual | 12k @12 mo; 18k @18; 18k @24; 48k × 4 | ✓ (`semiannual` added) |
| Leave at 24 mo | A keeps 48k (20%), forfeits 192k; B keeps 100k (50%) | ✓ |
| Even vest cliff | 2027-11-02, $50,000; 13 events | ✓ |
| Counter | ask = p75 185k (+12.1%); landing (165+185)/2 = 175k | ✓ |
| 10-yr value of +$10k at 3% | 10,000 × Σ1.03^k (k=0..9) = $114,638.79 | ✓ |

**Deliverable excerpt:**

```
## Offer math
| Offer | Yr-1 cash | Yr-1 total | 4-yr avg | Notes |
| A (Amazon 5/15/40/40) | $225,000 | $237,000 | $251,250 | back-loaded; wins only if you stay 4 yrs |
| B (even, 1-yr cliff)  | $217,500 | $267,500 | $248,750 | leads on cumulative pay at years 1-3 |
| Stay                  | $162,000 | $162,000 | $162,000 | |
Assumptions: bonus at target · public RSUs, no haircut, no price growth · sign-on in yrs 1-2
## Vesting (A)
Cliff: 2027-11-02 ($12,000) · Leave at 24 mo → keep $48,000, forfeit $192,000
## The counter (A)
Ask: $185,000 base (+12.1%) · Justification: market p75 · Expected landing: $175,000 · Walk-away: $170,000
Fallback levers: sign-on +$15,000 → equity +$40,000 → review at 6 months
## What it's worth
10-year value of the increase: $114,639 (at 3% annual raises)
```

**Honest gaps.** No market data — the single most valuable thing Levels.fyi sells alongside coaching.
No human judgment on a specific recruiter. No tax math (deliberately out of scope).

---

## 5. Job Description Writer — vs Textio and Datapeople

**Scenario.** "Our Enterprise AE posting has had 4 applicants in two weeks — fix it." The posting plants
7 Gaucher–Friesen–Kay masculine words, 2 slang terms, 1 feminine word, 11 exclusionary phrases, no pay
range, and 3 decoys that must **not** be flagged ("paid family leave", "a mature product line",
"Lead demos… operations leaders").

**Word list.** Gaucher, D., Friesen, J., & Kay, A. C. (2011). *Evidence that gendered wording in job
advertisements exists and sustains gender inequality.* JPSP 101(1), 109–128, Appendix A — the stem list
as reproduced in the open-source Gender Decoder
(<https://github.com/lovedaybrooke/gender-decoder/blob/master/app/wordlists.py>).

**Parity checklist** — Textio <https://textio.com/products/recruiting>; Datapeople
<https://help.datapeople.io/article/126-5-tips-for-getting-started-with-datapeoples-language-analytics-for-job-posts>
and <https://datapeople.io/blog/what-job-description-software-should-do/>:

| Feature (documented) | Status | Why |
|---|---|---|
| Gender Meter — Textio | MATCHES | GFK lean; strong (trait) vs functional stems reported separately |
| Age Graph — Textio | PARTIAL | age-coded term list; no generational-appeal model |
| Bias / exclusionary language — Datapeople (yellow) | MATCHES | origin, age, ability, appearance, gendered nouns/pronouns |
| Skills/requirements: fluff and soft skills — Datapeople (red) | MATCHES | `audit_requirements` |
| Content structure: perks, diversity statement, sections — Datapeople | MATCHES | `check_structure` |
| Jargon / corporate-speak / impersonal — Datapeople (blue) | MATCHES | jargon list, "the candidate" vs "you" |
| Title optimization for candidate search — Datapeople | PARTIAL | playbook title rules + slang flags; no search-volume data |
| Pay-transparency compliance — Datapeople | PARTIAL | salary presence and placement; no per-jurisdiction rule engine |
| Textio Score (outcome-trained prediction) | MISSING | we have no hiring-outcome data |
| AI first draft | MATCHES | host AI following the playbook template |
| Pipeline analytics — Datapeople Insights | OUT OF SCOPE | ATS data |

**Correctness.**

| Check | Planted | Found (after fix) | Before fix |
|---|---|---|---|
| GFK masculine (aggressive, competitive, dominate, ambitious, assertive, self-reliant, decisive) | 7 | 7 | 7 — but the old list was exact words only (inflections such as "ambition", "competing", "aggressively" could not match) and not the full GFK list |
| Slang (rockstar, crush) | 2 | 2 | 2 |
| Feminine (supportive) | 1 | 1 | 1 |
| Exclusionary | 11 | 11 | 9 — **"digital natives", "recent graduates" missed (plurals)** |
| Decoy "paid family leave" | 0 | 0 | would count (bare "family" in the old list; by inspection) |
| Decoy "mature product line" | 0 | 0 | would count (bare "mature"; by inspection) |
| "Base plus commission" as a nice-to-have requirement | 0 | 0 | counted as 1 nice-to-have |
| Requirement audit | cut #2 (trait list), #4 (culture fit); rewrite #1, #3, #5 | ✓ | no exclusionary/trait flags on requirement lines |
| Band 80–110k, candidate 98k | Q1 87.5k, mid 95k, Q3 102.5k, spread 37.5%, CR 1.032, 60% penetration | ✓ | ✓ |

**Deliverable excerpt** (rewrite; audit re-run: inclusive 100/100 neutral, structure 97/100):

```
# Account Executive, Mid-Market · Sales · Austin, TX (on-site) · $85,000 – $110,000 base + uncapped commission (OTE $170k–$220k)
**Why this role exists** — Plant managers still run production on whiteboards and spreadsheets, and our
customers cut downtime by a fifth in their first year. You will bring that result to 40 named accounts in Texas.
**What you'll do**
- Run the full sales cycle, from discovery to signed contract, for 40 named accounts
- Close $1.2M in new annual revenue in your first full year, with support from a sales engineer
**What you bring (must-haves)**
- A track record of closing B2B SaaS deals with a sales cycle of 60 days or more
- Fluent professional English, written and spoken
- A bachelor's degree or equivalent experience
**Equal opportunity** — … If you need a reasonable accommodation at any stage, email hiring@northbeam.example.
---
Audit: lean neutral · exclusionary 0 · requirements 5 must / 2 nice · 325 words · grade 8.7 · pay posted ✓
Removed: rockstar, aggressive, competitive, dominate, crush, "young and energetic", "digital natives", "he will",
"work hard, play hard", "we're a family", "recent graduates", "native English speaker", "culture fit", "guys", "lift 50 lbs"
```

**Honest gaps.** No outcome-trained score (Textio's moat), no age *model*, no jurisdiction rule engine
for pay transparency. The GFK list is word-level: it cannot tell "lead the market" (trait-ish) from
"lead demos" (functional) — we report functional stems as weak rather than guess.

---

## 6. Hiring Scorecard — vs Greenhouse structured hiring

**Scenario.** "Build a scorecard for a Senior Data Analyst; panel Priya, Tom, Alex, Jordan." The request
includes 7 criteria that proxy for protected characteristics ("Culture fit", "Under 35 years old",
"Christian values", "No childcare constraints", "Male leadership presence", "Pregnancy plans", "Speaks
without an accent"). Then 4 interviewers' ratings for Dana and Luis, where Jordan is a harsh outlier,
and Jordan's written feedback with 5 planted biased remarks plus a decoy ("race condition").

**Parity checklist** — <https://www.greenhouse.com/interviewing-decision-making>,
<https://support.greenhouse.io/hc/en-us/articles/4414777492891-Scorecard-overview>,
<https://support.greenhouse.io/hc/en-us/articles/360018399451-Assign-or-edit-focus-attributes-on-a-scorecard>:

| Greenhouse feature (documented) | Status | Why |
|---|---|---|
| Role requirements defined in advance | MATCHES | `build_scorecard` weights, must-haves, anchors |
| Interview kits with questions per interviewer | MATCHES | per-interviewer kit |
| Focus attributes per interview | MATCHES | each competency to ≥ 2 interviewers, ≤ 3 per interviewer |
| Scorecard: attribute ratings + overall recommendation (Definitely Not / No / Yes / Strong Yes) | MATCHES | 1–4 anchored scale + weighted decision thresholds |
| Key takeaways / private notes | PARTIAL | feedback audited and rewritten; we store nothing |
| Interviewer calibration report (tough vs easy) | MATCHES | leniency vs the median interviewer; plus per-rater decision sensitivity |
| Anti-bias reminders | MATCHES | protected criteria refused; biased remarks struck before filing |
| Anonymized take-home tests | OUT OF SCOPE | ATS feature |
| Self-scheduling, automated reminders | OUT OF SCOPE | |
| Voice AI interviews | OUT OF SCOPE | |

**Correctness.**

| Check | Expected (by hand) | Tool (after fix) | Before fix |
|---|---|---|---|
| Protected criteria refused | 7/7 | 7/7 with reason | tool errored (>8 items); by list inspection "Under 35 years old", "Christian values", "No childcare constraints", "Male leadership presence", "Pregnancy plans" had no matching term (`pregnan` entry could never match) |
| Job-related criteria refused | 0/5 | 0 | 0 |
| Dana weighted score | (30·3 + 25·2.5 + 20·3.5 + 15·2 + 10·3)/400 = 70.6 → hire | 70.6, hire | ✓ |
| Luis | 58.1; SQL 2.0 and Exp 2.0 < 2.5 → no hire | ✓ | ✓ |
| Dana without Jordan / without Alex | 83.8 strong hire / 57.5 must-have fail | ✓ `decision_hinges_on` = Alex, Jordan (added) | not computed |
| Outlier | Jordan 1.25 vs median rater 2.83 → −1.58 | only Jordan flagged | **Alex also flagged** (+0.65 vs panel mean) |
| Feedback: nervous, accent, energy, culture fit, kids | 5 | 5; "race condition" not flagged | 5, plus "race condition" would have been flagged as "race" (by inspection) |
| Evidence ratio (protected sentence isn't evidence) | 3/7 = 42.9% | 42.9% | 57.1% ("she mentioned she has two kids" counted as evidence) |

**Deliverable excerpt:**

```
## Candidate scores (after loop)
| Candidate | Weighted | Must-haves | Disagreements | Decision |
| Dana | 70.6 | pass (Exp 2.5 = bar) | Experimentation: Alex 4, Jordan 1 · Ownership: Alex 3, Jordan 1 | hire — hinges on Alex/Jordan |
| Luis | 58.1 | SQL 2.0, Experimentation 2.0 < 2.5 | Experimentation: Alex 3, Jordan 1 | no hire (must-have below bar) |
## Debrief agenda
1. Must-have bar: Luis — SQL and Experimentation averaged 2.0; no hire unless the panel names contrary evidence.
2. Dana — decision flips without either Alex (→ 57.5, no hire) or Jordan (→ 83.8, strong hire): both state evidence first.
3. Rater calibration: Jordan averages −1.58 vs the median interviewer.
## Feedback audit
Jordan: evidence 42.9% · struck: "nervous", "accent", "energy", "culture fit", "two kids" · keep: the sample-size
answer and the 10-minute race-condition fix · rewrite: rate the experimentation answer against anchor 1-4.
Refused rubric items (not job-related): Culture fit, Under 35 years old, Christian values, No childcare constraints,
Male leadership presence, Pregnancy plans, Speaks without an accent.
```

**Honest gaps.** Not an ATS: nothing is stored, scheduled or anonymized. Protected-term screening is a
lexicon plus an age-threshold pattern — a determined user can phrase around it; the playbook's intake
rule ("never ask for, record or consider…") is the second line of defence.

---

## 7. Performance Review Writer — vs Lattice (and 15Five Kona Coach)

**Scenario.** "Check this review before I submit it" — a Jan–Dec 2026 review of Priya with 16 planted
problems (pleasure to work with, helpful, pleasant, abrasive, emotional, maternity, "less committed";
solid, seems, great job, has potential, needs to improve, communication skills; always, never; "Unlike
Tom") and only Nov/Dec examples. Goals: ship billing v2 (done), NPS 40→50 (47), P1 incidents ≤ 4 (5),
onboard 2 engineers (3).

**Parity checklist** — <https://lattice.com/platform/performance/reviews>,
<https://help.lattice.com/hc/en-us/articles/26263030050839-Lattice-AI-Reviews-Writing-Assistant>
(3P summary of Writing Assist: grammar, clarity, bias checks), 15Five Kona pricing in the pricing file:

| Lattice feature (documented) | Status | Why |
|---|---|---|
| AI draft from performance signals | PARTIAL | drafts from the manager's notes + goal math; no data integrations |
| Writing assist: bias checks | MATCHES | personality, gender-skewed, protected, vague, absolutes, peer comparison, recency |
| Writing assist: grammar / clarity / tone | PARTIAL | host AI; our tool measures evidence density, not grammar |
| Goals / OKRs in reviews | MATCHES | `goal_attainment` (higher/lower/baseline, cap, weights) — live goal sync out of scope |
| Calibration workflows and rating distributions | MATCHES | `calibrate_ratings` (distribution vs curve, lenient/harsh managers) |
| Demographic rating analytics | OUT OF SCOPE | needs HRIS demographics we deliberately don't take |
| AI peer-feedback summaries | PARTIAL | host AI can summarize pasted feedback; no feedback store |
| Review cycle management | OUT OF SCOPE | system of record |

**Correctness.**

| Check | Expected | Tool (after fix) | Before fix |
|---|---|---|---|
| Planted phrases | 16 | 16 | 12 — "pleasure to work with", "solid", "seems", "committed" missed |
| Protected stems ("pregnancy", "religious") | flagged | flagged | never (`pregnan`, `religio` were whole-word entries) |
| Recency | 2/2 dated examples in Q4 → flag | flag, months 2026-11/12 | ✓ |
| Goal attainment | 100, (47−40)/(50−40) = 70, 4/5 = 80, min(150, 150) = 150 | ✓ | ✓ |
| Weighted | (100·30 + 70·30 + 80·20 + 150·20)/100 = 97.0 → meets | ✓ | ✓ |
| SBI for "is abrasive and always shoots down ideas" | no trait laundering | placeholder "[what did they do… — not 'abrasive']" | "you abrasive and always shoots down ideas" |
| Calibration (Ana 4.75, Ben 3.0, Cal 3.25) | Ana lenient only | ✓ vs median manager | Ben also "harsh" (−0.67 vs org mean) |
| Rewritten review | clean | 100/100; "Q1 2027" not counted in the 2026 cycle | "Q1 2027" read as Feb 2026 |

**Deliverable excerpt:**

```
# Performance review — Priya — Jan–Dec 2026
**Overall rating:** meets (weighted goal attainment 97.0%)
## Goals
| Ship billing v2 | 1 | 1 | 100% | 30 | NPS 40→50 | 50 | 47 | 70% | 30 |
| P1 incidents ≤ 4 (lower is better) | 4 | 5 | 80% | 20 | Onboard 2 engineers | 2 | 3 | 150% (cap) | 20 |
## Strengths
- **Launch execution** — During the November billing v2 launch, you wrote the rollback runbook and ran two dry runs
  with support, which meant cutover finished with zero customer-facing errors and 3 hours ahead of schedule.
## Growth areas
- **Hearing proposals out** — In the June and September planning meetings, you rejected three proposals before their
  owners finished presenting, which meant two were not raised again. Expectation: ask one clarifying question
  before giving a view, starting Q1 2027 planning.
---
Language audit: personality:outcome 0:23 · recency ok (6 dated examples, Feb–Nov) · absolutes 0 · bias terms 0
Removed from the draft: "maternity leave… less committed" (protected — raise with HR, not in a review).
```

**Honest gaps.** No data integrations (Lattice pulls goals, 1:1s and feedback); no demographic
analysis; month names without a year are assumed to be in the cycle (a forward "February" check-in
counts as Feb 2026).

---

## 8. Onboarding Planner — vs BambooHR onboarding

**Scenario.** "New Senior PM starts Monday Nov 23, 2026 (Thanksgiving Thu/Fri off). Build the 30-60-90
and pre-boarding checklist." Company holidays: Nov 26–27, Dec 24–25, Jan 1, MLK Jan 18, Presidents' Day
Feb 15. Plus a draft plan with 4 planted errors (item due on Thanksgiving, item due Christmas Day, day-90
review on a Saturday, an item with no owner).

**Parity checklist** — <https://www.bamboohr.com/platform/onboarding/>,
<https://www.bamboohr.com/product-updates/onboarding-task-and-notifications-updates>:

| BambooHR feature (documented) | Status | Why |
|---|---|---|
| Customizable checklists / templates by role and work mode | MATCHES | pre-boarding list (remote vs on-site lead times) + role 30-60-90 |
| Tasks with assignees and due dates relative to hire date | MATCHES | business-day, holiday-aware due dates |
| Automated reminders / notifications | PARTIAL | only via the customer's calendar/task connectors |
| Pre-onboarding packet (first-day details, intros) | PARTIAL | day-1 agenda, welcome note, dated intro schedule; no forms |
| Get-to-know-you emails | PARTIAL | "team told who's joining" task; host AI drafts the post |
| E-signatures (I-9, tax, direct deposit) | OUT OF SCOPE | |
| Progress-tracking dashboard | OUT OF SCOPE | system of record |

**Correctness** (reference code in the scenario file, no `hundred` imports):

| Check | Expected | Tool (after fix) | Before fix |
|---|---|---|---|
| Day 30 / 60 / 90 | Dec 22 (Tue) / Jan 21 (Thu) / Sat Feb 20 → **Mon Feb 22** | ✓ `moved: true` | ✓ |
| End of week 1 | Wed Nov 25 — only 3 working days | ✓ + warning | **Tue Dec 1** reported as "end of week 1", no warning |
| Day-5 check-in | 5th working day = Tue Dec 1 | ✓ `day_5` | — |
| Phase business days | 20 / 18 / 21 | ✓ | ✓ |
| 1:1s | Tue Nov 24, …, MLK → Tue Jan 19, Presidents' Day → Tue Feb 16 | ✓ | ✓ |
| Pre-boarding (−15 … −1 business days) | Nov 2 … Nov 20; 4 overdue as of Nov 12; 7 business days left | ✓ | ✓ |
| Intros | week 1 = Nov 24–25 × 3/day = 6; 7th priority-1 → Mon Nov 30 | ✓ | ✓ |
| Plan lint | Nov 26 → Nov 30, Dec 25 → Dec 28, Feb 20 → Feb 22, 1 missing owner | 4/4 | 4/4 |

**Deliverable excerpt:**

```
# Onboarding — <Name>, Senior Product Manager — starts 2026-11-23 (Mon)
Manager: Lena Ortiz · Buddy: Sam Park · 1:1: every Mon (Tue after MLK / Presidents' Day) ·
Reviews: day 30 2026-12-22 · day 60 2027-01-21 · day 90 2027-02-22 (Feb 20 is a Saturday)
⚠ Week 1 has 3 working days (Thanksgiving). Days 1-3: access, manager, buddy, 6 intros max. Day-5 check-in: Tue Dec 1.
## Pre-boarding (owner → due)
- [ ] Offer signed and countersigned — HR — 2026-11-02 (overdue)
- [ ] Equipment ordered — IT — 2026-11-09 (overdue)
- [ ] Buddy assigned and briefed — Manager — 2026-11-16
- [ ] Day-1 agenda sent — Manager — 2026-11-20
## Days 1-30 — Learn (ends 2026-12-22, 20 business days)
| Ship the onboarding-checklist copy fix and demo it | deliverable | New hire | 2026-12-16 (day 24) | shown at sprint review |
| Read activation research | learning | New hire | 2026-11-30 (moved from Thanksgiving) | notes shared |
## Plan check
Score 86/100 · flags: 1 item without an owner (pricing proposal) · 3 items on a weekend/holiday (moved above)
```

**Honest gaps.** Not a system of record: no forms, e-signatures, reminders or progress dashboard unless
the customer's AI has calendar/task connectors. Holidays must be supplied — there is no built-in
holiday calendar per country.
