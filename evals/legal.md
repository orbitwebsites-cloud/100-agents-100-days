# Legal & Admin: parity evaluation

Evaluated 2026-09-27. There are five agents in `hundred/agents/legal/`. We can't run the competitors (we have no accounts). So each agent is compared with the paid tool that overlaps it most, using only what that tool **documents** about the shared job (cited). Each agent was then run through one realistic scenario exactly as a customer's AI would run it: `python -m hundred.admin brief …`, then `… run <slug> <tool> -`. The results were checked by hand with a stdlib-only script that does not import `hundred`. Every scenario can be replayed with `tests/scenarios/test_legal.py` (15 tests).

The scenario documents were written for this eval. No third-party contract text was used. Each one has planted issues. "Recall" means planted issues caught. "Precision" means false alarms on market-standard clauses.

## Overview

| Agent | Comparable & price (lowest paid, monthly) | Checklist score (in-scope) | Recall / correctness (after fixes) | Verdict | Fixes made |
|---|---|---|---|---|---|
| contract-reviewer | Rocket Lawyer Standard (Rocket Copilot Contract Review), $34.99; Spellbook for the market-comparison item | 8 MATCHES · 0 PARTIAL · 0 MISSING · 2 OUT OF SCOPE | 7/7 planted issues caught. 0 serious false alarms on a market-standard control version. All dates were hand-verified, including the Sunday notice deadline. | **AT PAR**. Before the fixes it was **BELOW**: it cleanly caught only 2/7 planted issues and gave a wrong notice date. | cap / termination / price / data / forum / indemnity checks; extract_deadlines anchors; weekend note; regex false matches |
| privacy-policy | Termly Starter, $14/website | 6 MATCHES · 2 PARTIAL · 0 MISSING · 2 OUT OF SCOPE | GDPR yes, CCPA no, CalOPPA yes. Matches Civ. Code 1798.140(d) and the $26,625,000 threshold. 0 false regimes. The audit caught 2/2 deleted sections. | **AT PAR**. Before the fixes it was **BELOW**: it flagged a PIPEDA false alarm for California users and over-applied CCPA. | whole-word region matching; CCPA prong (B) = buy/sell/share; CalOPPA regime + DNT sections; classification fixes; lint/audit false alarms |
| nda-drafter | Rocket Lawyer NDA document + AI review, $34.99 | 7 MATCHES · 1 PARTIAL · 0 MISSING · 1 OUT OF SCOPE | 6/6 planted issues caught, 0 false alarms (before the fixes: 5/6 caught, 3 false alarms). Dates hand-verified. Its own draft passes its own review from all 3 sides. | **AT PAR** (above the comparable on exclusions: 5 vs 2) | exclusion regexes; IP-assignment regex; "exclusive jurisdiction" and bond false alarms; term parsing skips the non-solicit; no-early-termination option |
| grant-writer | Grantable Starter, $50 | 3 MATCHES · 3 PARTIAL · 0 MISSING · 3 OUT OF SCOPE | Budget matches 2 CFR 200.1 as revised in 2024 to the dollar: MTDC $199,000, indirect $29,850. Federal final report is due 2029-04-30. Before the fixes, MTDC was $186,800 (**−$1,830 of indirect**). | **AT PAR** on writing plus budget. It has no RFP-parsing tool and no budget-justification generator. | 2024 Uniform Guidance thresholds ($10k per unit, $50k per subaward, 15%) plus a pre-2024 mode; per-unit equipment test; one allowance per subaward across years; correct over-cap cut; 120-day federal final report; SMART regex |
| freelance-contract | Bonsai Essentials, $25 | 9 MATCHES · 1 PARTIAL · 0 MISSING · 1 OUT OF SCOPE | 8/8 planted issues caught. Before the fixes there were 2 false alarms, one of them a severity-3 "non-compete". Schedule and rate math hand-verified. | **AT PAR**. It covers more of the content job than Bonsai's documented designer template (kill fee, review of the client's paper), but it has no fixed full-contract template. | "exclusive jurisdiction" non-compete false alarm; word-number payment terms |

**Test summary (final run):**
- `pytest -q tests/agents -k legal tests/scenarios/test_legal.py`: **64 passed**
- `pytest -q tests/test_library.py`: **303 passed**

**Scope note check.** Every tool output of all five agents now has a `scope_note` that contains "not legal (advice)". The scenario tests assert this on every call. Before this eval, 6 tools had no scope note: extract_deadlines, renewal_calendar, calculate_terms, check_section_limits, criteria_coverage and project_timeline. Privacy and grant outputs also used the contract-law note, which was the wrong one for them. They now have their own notes:
- privacy: "…not a compliance certification…"
- grants: "…confirm with the NOFO/RFP and your finance office"

The notes sit next to concrete asks and computed numbers. They don't replace them.

**Plain-AI baseline.** Not measured: we did not run a no-agent baseline, so we make no claims about one. What we did observe is that **this brief itself** gave the pre-2024 grant thresholds ("$5,000 equipment threshold, first $25k of subawards"). The pre-fix tool combined those old thresholds with the 2024 15% de minimis rate. Any model that works from recalled rules instead of the current eCFR text is exposed to the same error.

---

## 1. Contract Reviewer

**Comparable.** Rocket Lawyer Standard, $34.99/mo ([pricing research](../marketing/pricing_research/ops_finance_legal.md)), which includes Rocket Copilot Contract Review.

**Scenario.** "Here's the SaaS agreement a vendor sent us. We're the customer (Cascade Outdoor Supply, Portland, Oregon). $4,000/month. What should we push back on, and when do we have to give notice?"
- The document is a 1,576-word *Software Subscription Agreement* with Stratus Ledger Systems, LLC, a Florida company. It is effective 2026-10-31, a month-end date chosen on purpose.
- It has 7 planted issues:
  1. Auto-renewal with 90 days' notice.
  2. Uncapped customer indemnity ("not subject to any limitation of liability").
  3. The vendor's cap is set at 1 month of fees.
  4. Unilateral fee changes at any time.
  5. Only the vendor may terminate for convenience, and fees are non-cancellable.
  6. Florida law with exclusive venue in Miami-Dade.
  7. A perpetual licence to Customer Data, vendor ownership of "derived" data, and no statement that the customer owns its data.
- Market-standard controls:
  - mutual confidentiality with the 4 exclusions
  - 30-day cure period
  - net-30 payment
  - 99.9% SLA with credits
  - a performance warranty with a disclaimer
  - mutual consequential-damages exclusion
  - assignment "not unreasonably withheld"
  - force majeure
  - insurance

**Parity checklist**

| # | Documented capability of the comparable | Status | Why |
|---|---|---|---|
| 1 | "highlight key terms" ([rocketlawyer.com/get-started/contract-review](https://www.rocketlawyer.com/get-started/contract-review)) | MATCHES | `detect_clauses` quotes 26 clause types. |
| 2 | "flag potential risks" / "red flags" (same page; [newsroom](https://www.rocketlawyer.com/newsroom/rocket-lawyer-launches-rocket-copilot-contract-review)) | MATCHES | 7/7 planted issues, each with an excerpt and a severity. |
| 3 | "see if there are any red flags or missing information" ([rocketlawyer.com/contract-review](https://www.rocketlawyer.com/contract-review?click=nav-top_contract-review)) | MATCHES | Missing clauses are flagged: no cap, no data-ownership statement, no governing law, and so on. |
| 4 | Common red flags: "Automatic renewal clauses", "No liability cap", "Unfair indemnity clauses", one-sided termination, arbitration ([RL guide](https://www.rocketlawyer.com/contract-review/why-get-a-contract-reviewed-by-a-lawyer)) | MATCHES | All of these are detected. It also reads the cap in months and who it protects. |
| 5 | "explains contracts in clear, simple language" (newsroom) | MATCHES | The playbook requires a "Why it matters to you" line for every flag, written by the host AI. |
| 6 | "know what to ask for and when to push back" (get-started page) | MATCHES | Every flag has `ask_for`; the playbook adds a fallback and a paste-ready redline list. |
| 7 | "Compare contracts to industry standards" ([spellbook.com](https://spellbook.com/)) | MATCHES | Market positions are in the playbook. `liability_exposure` puts $ figures against the 12-month norm. |
| 8 | "Negotiate from your side" (spellbook.com) | MATCHES | `my_role` flips every flag. The customer and vendor results differ in the tests. |
| 9 | Ask a Legal Pro follow-up questions (newsroom) | OUT OF SCOPE | Attorney access. |
| 10 | Encrypted upload, e-sign (RocketSign) | OUT OF SCOPE | We host no documents and offer no e-signature. |

**Beyond parity:**
- a computed renewal calendar with a weekend adjustment
- dollar exposure math
- a home-jurisdiction check

We found no documentation that the comparable does these.

**Correctness**

| Item | Tool (after fix) | Hand check | Pre-fix |
|---|---|---|---|
| Planted-issue recall | 7/7 | — | 2 clean (auto-renewal, indemnity) + 1 weak (data at sev 1, wrong ask); the cap, price change, termination and forum were **missed** |
| False alarms on the market-standard control | 0 at severity ≥2; score 5, "Routine" | — | "one-way indemnity" fired whenever the vendor's indemnity came *before* the customer's; auto-renewal was sev 2 even with a 30-day notice |
| Clause detection | the cap is found at §11.2 | — | "limitation of liability" matched "Florida **limited liability company**"; "governing law" matched "re**venue**s" |
| Initial term end | 2027-10-30 | 2026-10-31 + 12 months → anniversary 2027-10-31, so the last day is 2027-10-30 | reported 2027-10-31 |
| Non-renewal notice deadline | 2027-08-01 (Sun); weekend note says send by 2027-07-30 | 2027-10-30 − 90 days = 2027-08-01, a Sunday; the Friday before is 07-30 | **2027-01-29** (90 days *after* the effective date) |
| Reminder | 2027-07-02 | 08-01 − 30 days | same |
| Renewal 1 | 2027-10-31 → 2028-10-30, notice by 2028-08-01 | ✓ | same |
| "Longest notice period" | 90 days | 90 | **1,095 days** (3-year confidentiality survival misread as a notice period) |
| Liability cap | $4,000, vendor-only; market $48,000 | $48,000 × 1/12 | "uncapped exposure: nothing beyond the cap", which is wrong when the cap isn't mutual |

**Deliverable excerpt (Output format)**
```
# Contract review: Stratus Ledger Software Subscription Agreement — reviewing as customer — 2026-09-27
**Verdict:** do not sign as-is · Risk score 100/100
**Scope:** Drafting/review aid, not legal advice. Recommend counsel: uncapped indemnity + out-of-state exclusive venue.
## Deal-breakers
1. §10.1/§11.2 Indemnity & cap — "Customer's obligations under this Section 10.1 are not subject to any limitation of liability" while
   "PROVIDER'S AGGREGATE LIABILITY… SHALL NOT EXCEED THE FEES PAID… IN THE ONE (1) MONTH PRECEDING"
   Why: you carry unlimited liability; theirs is $4,000. Ask: mutual cap at 12 months' fees ($48,000), super-cap 2-3× for data/IP.
   Fallback: your indemnity limited to third-party claims from your content, under the same cap.
2. §3.2 Fees — "Provider may change the Fees… at any time upon written notice". Ask: fixed for the Initial Term; renewal increases ≤ greater of CPI or 5%, 60 days' notice.
3. §5.1/§5.3 Termination — vendor may terminate for convenience on 30 days; your fees are non-cancellable. Ask: mutual right, or delete theirs; pro-rata refund.
4. §6.1/§6.2 Data — perpetual, irrevocable licence to Customer Data "for Provider's other products"; vendor owns derived data.
   Ask: "As between the parties, Customer owns Customer Data"; licence only to provide the Services during the Term.
## Negotiate
5. §4.2 Auto-renewal, 90 days' notice → 30 days, or a vendor reminder 30 days before the window closes.
6. §13.1 Florida law, exclusive Miami-Dade venue → Oregon, or the defendant's home courts; at minimum non-exclusive.
## Accept (standard)
- §7 Confidentiality · §8 SLA 99.9% w/ credits · §9 warranty · §11.1 mutual consequential exclusion · §12 insurance · §14.1 assignment · §14.2 force majeure
## Key dates
| Last day to send non-renewal notice | 2027-08-01 (Sun) — send by Fri 2027-07-30 | 308 | reminder 2027-07-02 |
| Promotional pricing ends / initial term ends | 2027-02-28 / 2027-10-30 | | auto-renews to 2028-10-30 |
## Liability snapshot
Cap: $4,000 (1 month), vendor-only · Carve-outs: none · Your uncapped exposure: everything incl. §10.1 · Market: $48,000 mutual
```

**Honest gaps**
- Detection is regex-based. Drafting that avoids the patterns can still get past it, for example a cap written as "the amount of the most recent invoice". To cover this, the playbook now says in plain words that the AI must read the definitions, fees, term, termination, liability, indemnity and data clauses itself.
- The lopsided indemnity case isn't named precisely. Here the vendor's indemnity covered only US patents and copyrights, and the customer's covered everything. The tool no longer labels it "one-way" (which would be false), and it catches the uncapped carve-out. It does not compare how broad the two indemnities are.
- `my_jurisdiction` is a substring match on the governing-law and venue text. A value such as "OR" would not work; the customer must pass the full state or country name.

---

## 2. Privacy Policy Drafter

**Comparable.** Termly Starter, $14/mo per website ([termly.io/pricing](https://termly.io/pricing/)).

**Scenario.** "We're Habitloop, a Delaware startup based in Denver. We run a habit-tracking app with users in Germany, France and California. We collect email, name, password, IP address and device info, usage analytics (GA4 and Mixpanel), and payments through Stripe. We keep the card brand and last 4 digits. We also receive support emails. Revenue is $1.8M and we have 42,000 California users. We don't sell or share data for ads. Which laws apply? Draft the policy."

Truth, set from the statutes:
- **GDPR applies.** The company offers services to EU residents (Art. 3(2)(a)), so it needs an Art. 27 representative.
- **CCPA does not apply.** Revenue of $1.8M is below $26,625,000 ([privacy.ca.gov](https://privacy.ca.gov/laws-and-regulations/monetary-thresholds-in-the-ccpa/), in effect from 2025-01-01). The 100,000 prong is not met: it counts consumers whose PI the business "buys, sells, or shares", and it has 42,000 and neither sells nor shares ([Civ. Code 1798.140(d)(1)](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1798.140)). The 50% prong is at 0%.
- **CalOPPA applies.** It has no threshold (B&P §22575).
- **PIPEDA, UK GDPR and COPPA do not apply.**

**Parity checklist**

| # | Documented capability of Termly ([generator page](https://termly.io/products/privacy-policy-generator/)) | Status | Why |
|---|---|---|---|
| 1 | Questionnaire about your business and data practices | MATCHES | The playbook intake plus `classify_data_inventory`, which assigns a category, a lawful basis and flags per element. |
| 2 | Laws covered: GDPR, UK GDPR, CCPA/CPRA, CalOPPA, PIPEDA, Australia Privacy Act | MATCHES | All six are in `check_applicability`. CalOPPA was **added in this eval**; before, it was only a mention and had no required sections. |
| 3 | "We cover 25+ laws and 80+ regions" | PARTIAL | We cover about 17: GDPR/UK, 9 US states, CalOPPA, COPPA, PIPEDA, LGPD, Australia and Switzerland. |
| 4 | Output says what is collected, why, whether it is shared or sold, and user rights | MATCHES | `required_sections` produces a 25-item checklist for GDPR + CalOPPA. The draft covers 100% of it. |
| 5 | Cookie and tracker disclosures | PARTIAL | Cookies are a required section, and the ePrivacy opt-in flag is on every analytics item. Termly also has a cookie policy generator and a consent banner (out of scope). |
| 6 | Data retention periods | MATCHES | Missing retention is flagged per item, and the lint checks that a period is stated. |
| 7 | Company contact details | MATCHES | Core section plus the lint. |
| 8 | Publish as HTML, hosted link or embed | OUT OF SCOPE | Hosting. |
| 9 | "We monitor new and changing privacy laws and update our generator" | OUT OF SCOPE | Auto-updating hosted policy. Our thresholds are dated in the scope note. |
| 10 | "not a lawyer or a law firm… does not provide legal advice" | MATCHES | Privacy-specific scope note. |

**Beyond parity:**
- an applicability verdict computed from the thresholds, with near-miss notes
- an audit of an existing policy against the checklist
- a Flesch-Kincaid readability lint

**Correctness**

| Item | Tool (after fix) | Statute / hand check | Pre-fix |
|---|---|---|---|
| GDPR | applies (Art. 3(2)), Art. 27 representative noted | ✓ | ✓ |
| CCPA at $1.8M / 42k | not applicable | ✓ | ✓ |
| CCPA at 150k consumers, no sale or share | **not applicable**, with a note citing (d)(1)(B) | ✓ (the prong counts buy/sell/share) | **applied** ("≥ 100,000 consumers/households") |
| CCPA at 150k consumers, sharing | applies | ✓ | ✓ |
| CalOPPA | its own regime, with DNT, cross-site tracking, review/change and notify-of-changes sections | §22575(b) | only a mention in a footnote; no DNT check |
| "California" as a user region | no PIPEDA | ✓ | **PIPEDA (Canada)**, because "ca" was a substring of "california" |
| "Austria" as a user region | GDPR only | ✓ | GDPR + **US state laws + Australia**, because "us" and "au" are substrings of "austria" |
| Card brand + last 4 digits | not CPRA-sensitive | 1798.140(ae) requires a card number *plus* an access code | sensitive |
| Support emails sent to the company | not sensitive (the company is the intended recipient) | 1798.140(ae) | sensitive |
| "IP address" / "usage events" | device/network, analytics | — | "contact" (it matched "address") / "identity" (u-s-**age**) |
| Policy audit | 100% present. When §5 and the DNT sentence are deleted: missing = {transfers, dnt} | exact | "sources" falsely reported missing |
| Lint | grade 7.5, score 95 | — | 2 false vague-phrase hits |

**Deliverable excerpt**
```
# Privacy Policy — Habitloop, Inc. — Effective 2026-10-01   (Readability: grade 7.5)
**Applies:** GDPR (Art. 3(2) — EU representative required) · CalOPPA.  **Does not apply (yet):** CCPA/CPRA — revenue $1.8M < $26,625,000,
42k CA consumers and no buying/selling/sharing (1798.140(d)(1)(B)); re-check if you add an ad pixel. UK GDPR, PIPEDA, COPPA: no users/audience.
**Scope note:** drafting aid, not legal advice and not a compliance certification; thresholds as published for 2025-26 — verify.
## Data map (confirm this first)
| Data | Source | Purpose | Legal basis (GDPR) | Shared with | Retention | Sensitive? |
| Email | you | account, service email; newsletter | contract; consent (newsletter) | AWS, Postmark | account + 30 days | no |
| Password hash | you | login | contract | AWS | life of account | CPRA SPI (moot: CCPA n/a) |
| IP, device | automatic | security; analytics | legitimate interests; consent for analytics cookies | AWS, Google | 90 days | no |
| Usage events, _ga/Mixpanel cookies | automatic | product analytics | consent (ePrivacy Art. 5(3) banner) | Mixpanel, Google | 13-14 months | no |
| Card brand, last 4, billing country | Stripe | billing; tax | contract; legal obligation | Stripe | 7 years | no |
| Support messages | you | support | contract | Help Scout | 3 years | no |
## Policy
1. Who we are … EU representative under Art. 27: [EU REPRESENTATIVE NAME AND ADDRESS]
8. Cookies and tracking … "Our site does not respond to browser Do Not Track signals… we do not allow third parties to collect
   personal information about your activity across other websites" (CalOPPA §22575(b)(5)-(6))
## Open items for the company
- Appoint the EU representative. · Confirm GA4 Google Signals / ads features are OFF (otherwise "sharing" under CPRA once in scope).
```

**Honest gaps**
- There are no US state laws beyond the 9 listed, for example Delaware, Iowa, Tennessee or Minnesota. Termly claims 25+ laws.
- There is no cookie scanner and no consent banner (out of scope). The policy goes stale when laws change, and nothing warns the customer.
- Presence checks in the audit are regex-based. A section that matches a pattern but gets the substance wrong still passes. The host AI's drafting quality decides substance.

---

## 3. NDA Drafter

**Comparable.** Rocket Lawyer Standard, $34.99. It includes the NDA documents and the Copilot review of any contract.

**Scenario.** "A retailer sent us their NDA before a pilot. We're Brightpath Labs, the recipient. Anything I should push back on?"
- The document is a one-way "Confidentiality Agreement", effective 2026-11-02, governed by Delaware law.
- It has 6 planted issues:
  1. A 10-year term.
  2. A 24-month non-solicit and no-hire covering employees and customers.
  3. No independent-development exclusion.
  4. Assignment to the discloser of "suggestions, improvements… derivative works".
  5. One-way attorneys' fees.
  6. "any and all information… whether or not marked".
- Market-standard controls:
  - the public, prior-possession and third-party exclusions (each phrased non-standardly on purpose)
  - compelled disclosure
  - need-to-know representatives
  - return/destroy within 30 days
  - injunctive relief
  - "exclusive jurisdiction" in Wilmington

**Parity checklist**

| # | Documented capability ([RL mutual NDA](https://www.rocketlawyer.com/business-and-contracts/intellectual-property/confidentiality-agreements/document/mutual-non-disclosure-agreement), [RL confidentiality agreements](https://www.rocketlawyer.com/business-and-contracts/intellectual-property/confidentiality-agreements)) | Status | Why |
|---|---|---|---|
| 1 | Unilateral (one-way) and mutual agreements | MATCHES | `build_nda(mutual=…)` |
| 2 | Survival period for non-use and non-disclosure | MATCHES | `calculate_terms` gives the term, survival, return date and trade-secret carve-out, all dated. |
| 3 | Exclusions: prior possession; third-party source | MATCHES (more complete than the comparable) | We include 5 standard exclusions; the RL sample shows 2. |
| 4 | Return of materials on request | MATCHES | 30 days, with an archival-copy carve-out. |
| 5 | Governing law | MATCHES | |
| 6 | Non-solicit / non-circumvention of business contacts | PARTIAL | We offer only an optional *employee* non-solicit, and no non-circumvention clause. |
| 7 | Equitable relief | MATCHES | |
| 8 | AI review of an incoming NDA (Contract Review, §1) | MATCHES | 6/6 planted issues, 0 false alarms. |
| 9 | E-signature (RocketSign) | OUT OF SCOPE | |

**Correctness**

| Item | Tool (after fix) | Hand check | Pre-fix |
|---|---|---|---|
| Recall | 6/6 | — | 5/6: **missed** the IP assignment ("hereby assigns… all right, title and interest in any suggestions, improvements") |
| False alarms | 0 | — | **3**: "already known" reported missing (the text says "rightfully in Recipient's possession"); "third party" reported missing ("received by Recipient from a third party"); "exclusivity/no-shop" raised by "exclusive jurisdiction" |
| Term detection | 10 years, sev 2, non-solicit ignored | — | 10 years at sev 1. It read only the *first* years/months duration, so a non-solicit placed earlier would have hidden the term. |
| Term end as written | 2036-11-01 | 2026-11-02 + 120 months − 1 day | ✓ (the "early termination 2026-12-02" was fictional; that date is now suppressed) |
| Counter (24-month term + 36-month survival) | term 2028-11-01, obligations 2031-11-01 | ✓ | ✓ |
| Own draft reviewed as discloser | 0 findings | — | "Bond required", raised by our own "*without the need to post a bond*" |

**Deliverable excerpt**
```
# NDA review — One-way (Northwind → Brightpath) — effective 2026-11-02 — reviewing as recipient
**Key dates as written:** obligations run to 2036-11-01 (10 years, no early termination) · return/destroy 30 days after request
**Scope note:** drafting aid, not legal advice; non-solicit/no-hire enforceability varies by state — have counsel check before signing.
## Findings (from recipient's side)
| # | Clause | Issue | Sev | Market position | Ask / fallback |
| 1 | §3 Exclusions | no independently-developed exclusion | 3 | all five standard | add (d) independently developed without use of CI |
| 2 | §9 Improvements | "hereby assigns… any suggestions, improvements… derivative works" | 3 | NDA grants no IP | delete; fallback: feedback licence only |
| 3 | §7 Non-solicit | 24 months, employees + customers + no-hire | 2 | none in an NDA | delete; fallback mutual, 12 months, employees only, ads carve-out |
| 4 | §2 Definition | "any and all information… whether or not marked" | 2 | marked or reasonably understood | narrow |
| 5 | §6 Term | 10 years | 2 | 2-3 yrs + ≤3 yrs survival; trade secrets perpetual | 24-month term, 36-month survival (ends 2031-11-01) |
| 6 | §10 Fees | recipient pays discloser's attorneys' fees | 1 | prevailing party | make mutual |
Also: you will disclose your own product in the proposal — ask for a mutual NDA (draft attached: 11 clauses, 5 exclusions).
```

**Honest gaps**
- There is no non-circumvention clause option.
- One-way-dressed-as-mutual detection is a heuristic.
- Enforceability of the non-solicit by state (for example California B&P §16600) is left to the host AI and counsel. The tool does not encode state rules.

---

## 4. Grant Writer

**Comparable.** Grantable Starter, $50/mo ([grantable.co/pricing](https://www.grantable.co/pricing)).

**Scenario.** "Build our budget for a $250,000, 2-year federal award (cap includes indirect). We're a nonprofit with no NICRA, so we use the 15% de minimis rate."
- **Budget lines:**
  - Director: $70k at 0.25 FTE
  - Coordinator: $52k at 0.5 FTE
  - fringe at 30%
  - 6 trips at $1,200
  - an $18,000 lab trailer
  - 4 laptops at $1,800
  - $6,500 supplies
  - 40 stipends at $250
  - a $15,000 external evaluator
  - a university subaward of $40k in year 1 and $20k in year 2
- **Timeline:** starts 2027-01-01, semiannual reports. Also: "which criterion is weakest?"

Truth ([2 CFR 200.1](https://www.law.cornell.edu/cfr/text/2/200.1), revised for awards made on or after 2024-10-01):
- **MTDC** includes "up to the first $50,000 of each subaward".
- **Equipment** means ≥ $10,000 *per unit*, or the entity's capitalization level if that is lower.
- **De minimis rate** is up to 15% of MTDC ([200.414(f)](https://www.law.cornell.edu/cfr/text/2/200.414)).
- **Final reports** are due within 120 days ([200.344(b)](https://www.law.cornell.edu/cfr/text/2/200.344)).

The **$5,000 / $25,000 / 10%** figures in the brief are the rules for awards made *before* 2024-10-01 ([summary, e.g. Univ. of Hawaii ORS](https://research.hawaii.edu/ors/home/uniform-guidance-updates-effective-october-1-2024/)). Both rule sets are now supported.

**Parity checklist**

| # | Documented Grantable capability ([grantable.co](https://www.grantable.co/)) | Status | Why |
|---|---|---|---|
| 1 | "drafts proposals in your voice" / inline AI drafting | MATCHES | The host AI drafts to the playbook, with each section opening on its criterion. |
| 2 | "turns the RFP into a checklist" | PARTIAL | Playbook step 1 has the AI build the requirements table. There is no parsing tool. |
| 3 | Budget "calculations, error detection… suggest budget categories you might overlook" ([Grantable blog](https://www.grantable.co/blog/how-to-create-grant-budgets-that-win-special-grant-budget-template-5e1c6)) | MATCHES | `budget_table` does 2 CFR 200 MTDC, the equipment reclassification, cap/cost-share/de-minimis flags and the missing-evaluation flag. |
| 4 | "generate… budget justifications" (same blog) | PARTIAL | The playbook requires the narrative to match the table. There is no justification generator. |
| 5 | "inline suggestions that… catch gaps before reviewers do" | MATCHES | `criteria_coverage` (weight vs text share), SMART lint and `check_section_limits`. |
| 6 | "Track deadlines and your pipeline in list, board, and calendar views" | PARTIAL | `project_timeline` computes the award's report deadlines and calendar entries. The pipeline board is hosted (out of scope). |
| 7 | Funder research ("screening 990 filings") | OUT OF SCOPE | Grant database. |
| 8 | "library that never forgets" | OUT OF SCOPE | Storage. |
| 9 | Self-populating dashboard | OUT OF SCOPE | |

**Correctness**

| Item | Tool (after fix) | Hand (2 CFR 200.1, 2024) | Pre-fix |
|---|---|---|---|
| Salaries / fringe / direct | $87,000 / $26,100 / $237,000 | ✓ | ✓ |
| Laptops ($1,800 per unit) | reclassified as supplies, **in** MTDC | $1,800 < $10,000 per unit | kept as "equipment" and **excluded**. The test used the line total ($7,200 ≥ $5,000), not the unit cost. |
| Subaward ($40k + $20k, one subrecipient) | $50,000 in MTDC | first $50,000 *of each subaward* | $45,000: min(line, $25k) was applied per *line* |
| MTDC | **$199,000** | $199,000 | $186,800 |
| Indirect at 15% | **$29,850** | ✓ | $28,020 (under-recovers $1,830) |
| Total vs $250k cap | $266,850; cut **$14,652** of MTDC-eligible costs or $16,850 of excluded costs | 16,850 ÷ 1.15 | told the user to "cut direct costs by $16,850", which is too much |
| Same budget under pre-2024 rules (10%) | MTDC $174,000, indirect $17,400 | ✓ | — (mode did not exist) |
| Revised budget (Coordinator at 0.4 FTE, 5 trips) | $249,922, fits | ✓ | — |
| Period end / semiannual reports due | 2028-12-31 / 2027-07-30, 2028-01-30, 2028-07-30 | ✓ | ✓ |
| Final report due | **2029-04-30** (`federal_award`) | 2028-12-31 + 120 days | 90-day default (2029-03-31) unless the AI knew to pass 120 |
| SMART lint: "Empower young people to love technology" | 0/4 | fails all four | scored "measurable-source" because "techno**log**y" matched `log` |

**Deliverable excerpt**
```
# Proposal: Rural Middle-School Computing — federal program — request $249,922 — due <NOFO date>
**Compliance:** budget reconciles ✓ · under $250,000 cap ✓ · 2 CFR 200 (2024) MTDC ✓ · final report 2029-04-30
**Scope note:** drafting aid, not legal or financial advice; confirm with the NOFO and your finance office.
## Criteria coverage
| Evaluation | 30 | 14% of text | 0% keywords | under-covered vs weight — expand: instruments, data collection, analysis |
## Budget
| Personnel | Program Director, $70,000 × 0.25 FTE × 24/12 | | $35,000 |
| Personnel | Program Coordinator, $52,000 × 0.4 FTE × 24/12 | | $41,600 |
| Fringe | 30% × $76,600 | | $22,980 |
| Travel | 5 trips × $1,200 | | $6,000 |
| Equipment | Mobile STEM lab trailer (1 × $18,000) — excluded from MTDC | | $18,000 |
| Supplies | Laptops 4 × $1,800 (under $10k/unit → supplies) + curriculum $6,500 | | $13,700 |
| Participant support | 40 stipends × $250 — excluded from MTDC | | $10,000 |
| Contractual | External evaluator | | $15,000 |
| Subaward | State University (Y1 $40,000 + Y2 $20,000); first $50,000 in MTDC | | $60,000 |
| | | Total direct | $222,280 |
| Indirect | 15% de minimis on MTDC $184,280 | | $27,642 |
| | | TOTAL REQUEST | $249,922 |
## Timeline & reporting
| Semiannual reports | 2027-07-30 · 2028-01-30 · 2028-07-30 | Final (120 days, 2 CFR 200.344) | 2029-04-30 |
Flag: "Evaluation report" (month 25) falls outside the period of performance — move it to month 24 or fund it pre-award.
```

**Honest gaps**
- There is no RFP-to-checklist parser and no budget-justification generator. Grantable documents both.
- Keyword coverage is literal. For example "partners" isn't matched by "State University faculty". This underrates on-topic text, and the playbook asks the AI to use the funder's vocabulary to compensate.
- There is no funder database or pipeline (out of scope).

---

## 5. Freelance Contract

**Comparable.** Bonsai Essentials, $25/mo ([hellobonsai.com/pricing](https://www.hellobonsai.com/pricing)).

**Scenario.** "I'm Maya Ortiz, a brand designer. Fernhill Coffee sent this contractor agreement and SOW for $9,600. What do I push back on? Build me a payment schedule. Is $9,600 enough for about 80 hours?"
- It has 8 planted issues:
  1. "unlimited revisions until Client is satisfied"
  2. "to Client's complete satisfaction"
  3. "related marketing materials as needed, etc." and "ongoing support"
  4. no change-order process
  5. work-for-hire "from the moment of creation"
  6. net 60
  7. "Client may terminate… at any time, for any reason" with no payment for work done
  8. no deposit
- Controls:
  - independent-contractor clause
  - confidentiality
  - Oregon law with "exclusive jurisdiction"

**Parity checklist**

| # | Documented Bonsai capability ([designer template](https://www.hellobonsai.com/contract-template/freelance-design)) | Status | Why |
|---|---|---|---|
| 1 | Scope: deliverables, revisions, file handoff | MATCHES | `scope_creep_check` plus the deliverables table in the Output format. |
| 2 | Revision rounds; extras priced ("Additional revisions" fee) | MATCHES | Revision-cap check and language. |
| 3 | Written change orders (hellobonsai.com search result: templates "require written change orders signed by both sides"; not on the fetched designer page) | MATCHES | |
| 4 | "non-refundable deposit of twenty-five percent (25%)" | MATCHES | Deposit is 40% by default; below 25% is flagged. |
| 5 | Milestone payment schedule | MATCHES | `milestone_schedule` with invoice and due dates. |
| 6 | Late fee "1.5% per month" | MATCHES | |
| 7 | Kill fee (hellobonsai.com search result: "kill fees if a project is cancelled"; the fetched designer template has none) | MATCHES (more complete than Bonsai's designer template) | Computed per phase. |
| 8 | IP transfers "once the Client pays for it in full" | MATCHES | Flags work-for-hire that isn't conditioned on payment. |
| 9 | Termination on 14 days' notice; independent contractor; confidentiality; liability capped at 12 months' fees | MATCHES | |
| 10 | A complete ready-to-sign contract document | PARTIAL | The host AI assembles it from the clause language the tool returns. There is no fixed, versioned template tool. |
| 11 | E-signature, invoicing | OUT OF SCOPE | |

**Correctness**

| Item | Tool (after fix) | Hand check | Pre-fix |
|---|---|---|---|
| Recall | 8/8 (scope 6/6, traps 4/4, missing deposit, kill fee, IP on payment, change orders) | — | 8/8 |
| False alarms | 0 | — | **"Non-compete / exclusivity", sev 3**, from "courts… have exclusive jurisdiction"; "Payment terms missing" even though "within sixty (60) days of receiving the invoice" is a payment term |
| Schedule | $3,840 due 2027-01-05; $2,880 due 2027-02-16; $2,880 due 2027-03-30 | 40/30/30 of $9,600; +15 days | ✓ |
| Kill fee after deposit / late fee | $1,440 / $43.20 per month | 25% × $5,760; 1.5% × $2,880 | ✓ |
| Rate | minimum $109.53/hr → $110 | (85,000 × 1.253 + 8,000) × 1.1 ÷ (46 × 25) | ✓ |
| Fixed-fee check | effective $100/hr, quote $10,560 | 9,600 ÷ 96 h; 96 × $110 | ✓ |

**Deliverable excerpt**
```
# Ortiz Studio ↔ Fernhill Coffee Roasters — Brand identity — fixed $9,600 (recommend $10,560) — start 2027-01-05
**Scope note:** drafting aid, not legal advice; Oregon contractor rules apply — lawyer recommended for work-for-hire/IP terms.
## Scope (deliverables)
| 1 | Logo concepts | 3 concepts, PDF | materially matches brief | 2027-02-01 |
| 2 | Final identity | logo suite, palette, typography, 2 bag designs (AI/SVG/PNG) | conforms to approved concept | 2027-03-15 |
**Not included:** other marketing materials, web, ongoing support (quoted separately)  **Revisions:** 2 rounds each; extra at $110/hr  **Changes:** written change order first
## Payment schedule
| Deposit 40% | signature | $3,840 | 2027-01-05 | 2027-01-05 | kill fee after: $1,440 |
| Concepts 30% | acceptance of 3 concepts | $2,880 | 2027-02-01 | 2027-02-16 | $720 |
| Final 30% | acceptance of final files | $2,880 | 2027-03-15 | 2027-03-30 | — |
Late payment: 1.5%/month ($43.20 per $2,880 invoice) · Work pauses if any invoice is > 10 days overdue
## Redlines to send the client
1. §2: replace "unlimited revisions until Client is satisfied" with two rounds + 5-business-day review, silence = acceptance.
2. §5: "Upon receipt of full payment, Designer assigns… final Deliverables"; concepts/drafts and pre-existing tools stay with Designer.
3. §4: 40% deposit on signature; milestone invoices net 15 (fallback net 30), not net 60 on completion.
4. §6: either party on 14 days' notice; Client pays for work performed + 25% of remaining fee.
5. §1: delete "as needed, etc." and "ongoing support"; add the exclusions list and change-order clause.
```

**Honest gaps**
- There is no ready-made full template (see item 10).
- Contractor-classification rules (AB5, NY Freelance Isn't Free Act) are named in the scope note but not checked.
- Late-fee caps by state are not encoded.

---

## Outside `hundred/agents/legal/` (described, not edited)

- `hundred/admin.py` `brief`/`run` raise `BrokenPipeError` when output is piped into `head`. This is a cosmetic CLI issue and did not affect the eval.
- `hundred/core.py` and `hundred/lib/` had no issues on this category's paths. `lib/dates.fmt` and `lib/text.readability` gave correct results for every value checked.
