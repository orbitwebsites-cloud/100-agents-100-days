# Hundred: comparable pricing for the Engineering, Product & Design, Career & HR and E-commerce packs

Researched 2026-09-27. Every price below was either read on the vendor's own pricing page (**1P**) or, where the vendor page was blocked, empty or unpublished, taken from a dated third-party write-up (**3P**, marked). If a price is not public, it says "not public". Anything I estimated rather than read is marked **[INFERENCE]**.

## Method (applies to every category)

- **Entry price:** the lowest paid plan. I use the monthly-billed price where one exists and note the annual price beside it. The price is per seat where the vendor charges per seat.
- **Median comparable:** the median of the entry prices that have a number. Rows that are "not public", free only, or one-time fees are left out of the median.
- **Overlap weights [INFERENCE]:** high = 0.6, partial = 0.3, low = 0.1. Even "high" is below 1.0 because Hundred never hosts a UI, never stores data, never runs automation (PR webhooks, monitors, schedulers) and never integrates with the customer's store or repo. The customer's own AI does all of that.
- **Overlap-weighted replaced value [INFERENCE]:** for each agent, I take the most representative comparable, multiply its price by the overlap weight, and add up the results. This estimates the monthly spend one buyer could credibly treat as "covered".
- **Partial-substitute discount:** applied on top of the overlap weighting, for the reasons given in each category.
- **Price cross-check:** the pack should cost less than buying each agent separately at $4.99.

---

## 1. Engineering

Agents: code-reviewer, bug-hunter, sql-wizard, api-designer, test-writer, regex-builder, commit-crafter, incident-commander, system-design, security-auditor.

| Tool | Plan | $/mo | Billing | Job | Overlap | Source | Date seen |
|---|---|---|---|---|---|---|---|
| CodeRabbit | Essentials | $30/dev (monthly); $24/dev (annual) | per dev | AI PR code review | partial (code-reviewer) | https://www.coderabbit.ai/pricing (1P) | 2026-09-27 |
| Greptile | Pro | $30/seat | monthly | AI PR review with codebase context | partial (code-reviewer) | https://www.greptile.com/pricing (1P) | 2026-09-27 |
| Qodo | Pro Team | $30/mo base, credit-based ($0.012/credit; 2,500 credits ≈ 18 reviews); up to 30 users | monthly | AI code review | partial (code-reviewer, test-writer) | https://www.qodo.ai/pricing/ (1P) | 2026-09-27 |
| GitHub Copilot | Pro (Pro+ $39, Max $100) | $10 | monthly, individual | General AI coding: tests, commit messages, review | low (it is the *host* AI, not something we replace) | https://github.com/features/copilot/plans (1P). Business/Enterprise prices were not shown on the fetched page | 2026-09-27 |
| Sentry | Team $26/mo + **Seer AI debugging $40 per active contributor/mo** | $26 + $40/contributor | monthly or annual | Error monitoring + AI root cause | partial (bug-hunter, via Seer) | https://sentry.io/pricing/ ; https://docs.sentry.io/pricing/ (1P) | 2026-09-27 |
| Snyk | Team | "starting at $25/month"; teams up to 10 devs (the page does not say whether this is per dev) | monthly | SCA/SAST scanning | low (security-auditor; we do not scan repos) | https://snyk.io/plans/ (1P) | 2026-09-27 |
| GitGuardian | Starter free (≤25 devs); Growth/Enterprise | not public | contact sales | Secret scanning | partial (secret-scan part of security-auditor) | https://www.gitguardian.com/pricing (1P) | 2026-09-27 |
| incident.io | Team | $19/user (monthly); $15 (annual); on-call +$10 | per user | Incident workflow + postmortems | low (incident-commander) | https://incident.io/pricing (1P) | 2026-09-27 |
| Rootly | Incident Response Essentials | $20/user (billing term not stated) | per user | Incident management | low (incident-commander) | https://rootly.com/pricing (1P) | 2026-09-27 |
| FireHydrant | Pro | $25/responder | annual | Incident management / runbooks | low (incident-commander) | https://firehydrant.com/pricing/ (1P) | 2026-09-27 |
| Stoplight | Basic | $56/mo (monthly), $44 (annual); 3 users included (≈ $18.67/user), extra users $14/$11 | per workspace | API design, OpenAPI docs, mocks | partial (api-designer) | https://stoplight.io/pricing (1P) | 2026-09-27 |
| Postman | Solo ($9 annual); Team $19/user (annual) | $9 | annual (monthly price not shown) | API client and collaboration | low (api-designer) | https://www.postman.com/pricing/ (1P) | 2026-09-27 |
| AI2sql | Start | $9 (monthly); $84/yr; $29 lifetime option | monthly/annual | Natural language to SQL | high (sql-wizard) | https://www.ai2sql.io/pricing (1P) | 2026-09-27 |
| EverSQL (Aiven) | SQL optimizer | free; paid tiers not found | n/a | SQL optimization | high (sql-wizard) | https://aiven.io/tools/sql-query-optimizer (search snippet only) | 2026-09-27 |
| regex101 | Free; Pro | Pro price not public (shown only at checkout) | n/a | Regex testing | high (regex-builder) | https://docs.regex101.com/application/regex101-pro/ (1P) | 2026-09-27 |
| AutoRegex | paid | "from $3.49/mo" | n/a | AI regex generation | high (regex-builder) | https://aitools.fyi/autoregex (3P directory, unverified) | 2026-09-27 |
| Swimm | n/a | not public ("based on lines of code") | contact sales | Code documentation | low | https://swimm.io/pricing (1P) | 2026-09-27 |

**Median comparable:** $25/seat/mo. This covers 12 priced rows (9, 9, 10, 19, 20, 25, 25, 30, 30, 30, 40, 56), using Seer's $40 for Sentry and Stoplight Basic's $56. The paid AI code-review tools cluster tightly at **$24–30 per dev**.

**Overlap-weighted replaced value [INFERENCE]:**

| Agent | Comparable used | Price × weight | Value |
|---|---|---|---|
| code-reviewer | CodeRabbit | $30 × 0.3 | $9.0 |
| bug-hunter | Sentry Seer | $40 × 0.3 | $12.0 |
| sql-wizard | AI2sql | $9 × 0.6 | $5.4 |
| api-designer | Stoplight, per user | $18.67 × 0.3 | $5.6 |
| test-writer | Copilot Pro as proxy; no standalone paid test tool found | $10 × 0.3 | $3.0 |
| regex-builder | AutoRegex (3P); regex101 is free | $3.49 × 0.6 | $2.1 |
| commit-crafter | No paid comparable; free inside Copilot/Cursor | — | $0 |
| incident-commander | incident.io | $19 × 0.1 | $1.9 |
| system-design | No comparable found | — | $0 |
| security-auditor | Snyk | $25 × 0.1 | $2.5 |
| **Total** | | | **≈ $41.5/seat/mo** |

**Discount: 50–60% [INFERENCE].**
- Engineers already pay $10–39 for a host AI (Copilot/Cursor), and those tools already do tests and commit messages. That price is their mental ceiling for "AI help".
- CodeRabbit and Seer are worth what they cost because they run *automatically* (on every PR, on every error). Hundred only runs when someone asks.
- We cannot prove "we caught it before merge", which is the ROI story those vendors sell.
- $41.5 × 0.40–0.50 ≈ **$17–21**.

**Recommended pack price: $15–19 per seat/mo** (suggest $19 monthly, $15/mo billed annually).
- Buying all 10 agents at $4.99 costs $49.90, so the pack is a 62–70% bundle discount.
- The pack comes in below one CodeRabbit seat ($24–30) and just below Copilot Business territory.

**Single agents at $4.99:**
- **Underpriced:** bug-hunter (Seer costs $40 per contributor), code-reviewer (CodeRabbit/Greptile $24–30) and api-designer (Stoplight ≈ $19/user). security-auditor is also underpriced against Snyk, but its overlap is low and false negatives carry liability, so do not lean on it.
- **Overpriced / hard to sell alone:** regex-builder (regex101 is free), commit-crafter (free inside every host AI) and test-writer (commodity in the host AI). These work as bundle sweeteners but are weak on their own.
- **Fair:** sql-wizard (about half of AI2sql's $9), incident-commander and system-design (niche, no priced comparable).

**Coherent bundle?** Yes. There is one buyer: the individual engineer or a small eng team. incident-commander and system-design lean toward SRE/senior engineers, but the same person buys them.

---

## 2. Product & Design

Agents: prd-writer, interview-synthesizer, roadmap-prioritizer, ux-writer, feedback-analyzer (NPS), pitch-deck-coach, accessibility-checker.

| Tool | Plan | $/mo | Billing | Job | Overlap | Source | Date seen |
|---|---|---|---|---|---|---|---|
| ChatPRD | Pro | $15 (monthly); $179/yr (≈$14.92); Teams $29/seat | monthly/annual | AI PRD writing | high (prd-writer) | https://www.chatprd.ai/pricing (1P) | 2026-09-27 |
| Productboard | Plus | $25/maker (monthly); $19 (annual) | per maker | Feedback insights, prioritization, roadmaps | partial (roadmap-prioritizer, feedback-analyzer) | https://www.productboard.com/pricing/ (1P) | 2026-09-27 |
| Aha! | Ideas / Discovery from $39/user; Roadmaps from $59/user | $39 | per user; monthly by card or annual | Roadmapping system of record | low (roadmap-prioritizer) | https://www.aha.io/pricing (1P) | 2026-09-27 |
| Dovetail | Free; Enterprise | Enterprise not public; self-serve Professional reportedly discontinued July 2026 | contact sales | Research repository and synthesis | partial (interview-synthesizer) | https://dovetail.com/pricing/ (1P); discontinuation per https://formbricks.com/blog/dovetail-pricing (3P) | 2026-09-27 |
| Condens | Lite | €15 (monthly); €165/yr; Business €500/mo (annual) | per contributor | Research repository and synthesis | partial (interview-synthesizer) | https://condens.io/pricing/ (1P) | 2026-09-27 |
| Maze | n/a | not public ("Contact sales"). 3P sources quote about $99/mo but disagree with each other | n/a | Usability testing | low | https://maze.co/pricing/ (1P) | 2026-09-27 |
| Frontitude | Team | $200/mo (monthly), $160 (annual); **UX Writing Assistant seat $25 (monthly) / $20 (annual)** | per plan + seats | UX copy management and AI writing | partial (ux-writer) | https://www.frontitude.com/pricing (1P) | 2026-09-27 |
| Ditto | Individual / Pro / Enterprise | not public | contact sales | UX copy management | partial (ux-writer) | https://www.dittowords.com/pricing (1P) | 2026-09-27 |
| Survicate | Growth | $114 (annual) | monthly option exists | NPS/CSAT surveys and analysis | low (feedback-analyzer; we analyze, they collect) | https://survicate.com/pricing/ (1P) | 2026-09-27 |
| Delighted (Qualtrics) | n/a | **discontinued**; delighted.com redirects to Qualtrics ("no longer available") | n/a | NPS | n/a (context: NPS buyers are losing a cheap option) | https://www.qualtrics.com/delighted/ (1P) | 2026-09-27 |
| Pitch | Plus | €12 (monthly); €10 (annual) | per seat | Deck building | low (pitch-deck-coach) | https://pitch.com/pricing (1P) | 2026-09-27 |
| DocSend | Personal | $15 (monthly); $10 (annual) | per user | Deck sharing and analytics | low (pitch-deck-coach) | 3P: https://www.ellty.com/blog/docsend-pricing (docsend.com returned 403) | 2026-09-27 |
| Stark | Premium Pack | $198/user/yr = $16.50/seat/mo, minimum 3 seats | annual | Accessibility checks (contrast, etc.) | partial (accessibility-checker) | https://www.getstark.co/pricing/ (1P) | 2026-09-27 |
| axe DevTools (Deque) | Pro extension | not shown on the pricing page. 3P reports $45/mo or $500/yr; other 3P reports $79–99/mo. **Unverified** | n/a | Accessibility testing | partial (accessibility-checker) | https://www.deque.com/axe/devtools/pricing/ (1P, no price); 3P https://ratedwithai.com/blog/deque-axe-pricing-2026 | 2026-09-27 |

**Median comparable: about $21/seat/mo.**
- Priced rows: Pitch €12 (≈$14), ChatPRD 15, Stark 16.5, Condens €15 (≈$17), Productboard 25, Frontitude seat 25, Aha! 39, Survicate 114.
- EUR→USD conversion at about 1.15 is an **[INFERENCE]**.
- Using Frontitude's $200 plan instead of the $25 seat still gives about $21.

**Overlap-weighted replaced value [INFERENCE]:**

| Agent | Comparable used | Price × weight | Value |
|---|---|---|---|
| prd-writer | ChatPRD | $15 × 0.6 | $9.0 |
| interview-synthesizer | Condens | ≈$17 × 0.3 | $5.1 |
| roadmap-prioritizer | Productboard | $25 × 0.3 | $7.5 |
| ux-writer | Frontitude UXW seat | $25 × 0.3 | $7.5 |
| feedback-analyzer | Survicate | $114 × 0.1 | $11.4 |
| pitch-deck-coach | DocSend (3P) | $15 × 0.1 | $1.5 |
| accessibility-checker | Stark | $16.50 × 0.3 | $4.95 |
| **Total** | | | **≈ $47/seat/mo** |

**Discount: 55–65% [INFERENCE].**
- Productboard, Aha!, Dovetail and Condens sell a *system of record*: shared repositories, stakeholder views and history. Hundred is ephemeral and single-player.
- The accessibility tools crawl the live DOM. We only see pasted HTML or values.
- $47 × 0.35–0.45 ≈ **$16–21**.

**Recommended pack price: $15–19/mo** (suggest $15 to launch, matching ChatPRD Pro, the most direct substitute).
- 7 × $4.99 = $34.93, so this is a 46–57% bundle discount.

**Single agents at $4.99:**
- **Underpriced:** prd-writer (ChatPRD costs $15 and overlap is high), ux-writer (Frontitude's AI seat costs $20–25) and accessibility-checker (Stark $16.50; axe about $45 per 3P).
- **Overpriced / weak:** pitch-deck-coach. The need is episodic, overlap with Pitch/DocSend is low, and the buyer is a founder, not a PM.
- **Fair:** interview-synthesizer, roadmap-prioritizer and feedback-analyzer.

**Coherent bundle? Only partly [INFERENCE].**
- The PM core (prd, interviews, roadmap, feedback, plus ux-writer) fits one buyer.
- accessibility-checker belongs to designers or front-end engineers. Consider moving it to Engineering or a Design pack.
- pitch-deck-coach belongs to founders. Consider moving it to a Founder/Startup pack.

---

## 3. Career & HR: recommend splitting into two packs

This category mixes two buyers who pay very differently:
- **Job seekers:** consumers with a 1–3 month need who pay weekly, monthly or quarterly, often on a personal card.
- **HR teams and managers:** B2B buyers on annual contracts who compare against per-employee platforms.

One price would be too high for one group and too low for the other. **Recommendation: split them.**

### 3a. Job-seeker comparables (resume-optimizer, cover-letter, interview-coach, salary-negotiator)

| Tool | Plan | $/mo | Billing | Job | Overlap | Source | Date seen |
|---|---|---|---|---|---|---|---|
| Jobscan | Premium | $49.95 (monthly); $89.95/quarter (≈$29.98/mo) | monthly/quarterly | ATS resume match and optimization | high (resume-optimizer) | 3P, citing prices listed 2026-09-14: https://www.jobfinder-ai.com/blog/is-jobscan-worth-it (jobscan.co/pricing did not render) | 2026-09-27 |
| Teal | Teal+ | $13/week; $29 per 30 days; $79 per 90 days | weekly/monthly/quarterly | Resume builder, job tracker, AI cover letters | high (resume-optimizer, cover-letter) | 3P: https://applyarc.com/compare/teal-pricing (tealhq.com returned 403) | 2026-09-27 |
| Kickresume | Premium | $24 (monthly); $18/mo (quarterly, $54); $8/mo (yearly, $96) | monthly/quarterly/annual | Resume and cover-letter builder with AI writer and ATS check | high (resume-optimizer, cover-letter) | https://www.kickresume.com/en/pricing/ (1P) | 2026-09-27 |
| Final Round AI | Pro | "$25+/mo" (up to 40% off on longer terms; no free trial) | monthly+ | Mock and live interview copilot | partial (interview-coach) | https://www.finalroundai.com/pricing (1P) | 2026-09-27 |
| Yoodli | Pro / Advanced | $8 / $20 per month, billed annually (monthly price not shown) | annual | Speaking and interview practice | partial (interview-coach) | https://yoodli.ai/pricing (1P) | 2026-09-27 |
| Levels.fyi | Negotiation coaching (Standard / Premium / Leadership) | **one-time $1,250 / $2,450 / $5,000**, with a guaranteed increase of $10k / $15k / $40k or a refund | one-time | Human salary-negotiation coaching | low (salary-negotiator) | https://www.levels.fyi/services/ (1P) | 2026-09-27 |

**Median comparable (monthly subscriptions): $25/mo.** Values: 8, 24, 25, 29, 49.95. Levels.fyi is excluded because it is a one-time fee.

**Overlap-weighted replaced value [INFERENCE]:**

| Agent | Comparable used | Price × weight | Value |
|---|---|---|---|
| resume-optimizer | Median of Jobscan / Teal / Kickresume | $29 × 0.6 | $17.4 |
| cover-letter | Bundled in those same tools | incremental | $0 |
| interview-coach | Final Round | $25 × 0.3 | $7.5 |
| **Subtotal (subscriptions)** | | | **≈ $25/mo** |
| salary-negotiator | Levels.fyi Standard, spread over a 3-month search | $1,250 × 0.1 ÷ 3 | $41.7 |
| **Total including salary-negotiator** | | | **≈ $67/mo** |

**Discount: about 50% [INFERENCE].**
- ChatGPT/Claude already write decent resumes for free, so a job seeker has a free fallback.
- The need is short-lived, and there is no ATS-match UI or template rendering.
- $25 × 0.5 ≈ $12.5.
- salary-negotiator justifies a premium over that, not a multiple of it.

**Recommended price: $9–15/mo.** Better still, follow the market's billing norm with a time-boxed pass of **$19–29 per 90 days**, since Jobscan, Teal and Kickresume all sell quarterly.
- 4 × $4.99 = $19.96/mo.

**Single agents at $4.99:**
- **Underpriced:** salary-negotiator. One good negotiation is worth thousands, and the human alternative costs $1,250+. It could stand alone at $9–19 one-time.
- **Fair or overpriced:** cover-letter. It is bundled free in every resume tool and trivial for the host AI.
- **Fair:** resume-optimizer and interview-coach.

### 3b. HR / manager comparables (job-description, hiring-scorecard, performance-review, onboarding-planner)

| Tool | Plan | $/mo | Billing | Job | Overlap | Source | Date seen |
|---|---|---|---|---|---|---|---|
| Lattice | Performance | $10/seat (Goals $8, Engagement $4); minimum $4,000/yr | annual only | Performance-review platform | low–partial (performance-review) | https://lattice.com/pricing (1P) | 2026-09-27 |
| 15Five | Perform | $11/user; **Kona Coach $19/manager**; Engage $4 | annual | Performance reviews and AI manager coaching | low (platform); partial (Kona Coach) | https://www.15five.com/pricing (1P) | 2026-09-27 |
| Leapsome | Modules | not public (1P fetch blocked). 3P reports from about $8/user/mo | annual, via sales | Reviews, goals, onboarding | low | 3P: https://elearningindustry.com/leapsome-pricing | 2026-09-27 |
| BambooHR | Core / Pro / Elite | not public on 1P (fetch blocked). 3P reports $10 / $17 / $25 per employee/mo; flat from about $250/mo for ≤25 employees | via sales | HRIS including onboarding | low (onboarding-planner) | 3P: https://peoplemanagingpeople.com/tools/bamboohr-pricing/ | 2026-09-27 |
| Textio | n/a | not public. 3P reports about $10k–25k/yr | annual, via sales | Job-description and review language | partial (job-description, performance-review wording) | 3P: https://www.vendr.com/marketplace/textio | 2026-09-27 |
| Datapeople | n/a | not public. 3P (Vendr) reports a median of about $11k/yr | annual, via sales | Job-description optimization and hiring analytics | partial (job-description, hiring-scorecard) | 3P: https://www.vendr.com/marketplace/datapeople | 2026-09-27 |

**Median comparable:**
- **Per seat:** about $10–11/user/mo. Values: Lattice 10, 15Five 11, Kona Coach 19 (1P); with the 3P rows added (Leapsome 8, BambooHR 10), about $10. These are per *employee*, so a manager effectively carries 5–10 of them.
- **Org-level floor:** about $333/mo (Lattice's $4k/yr minimum). JD tools cost about $830–1,250/mo (3P).

**Overlap-weighted replaced value per HR/manager seat [INFERENCE].** Assumes about 8 reports per manager and about 10 hiring users sharing Textio:

| Agent | Comparable used | Price × weight | Value |
|---|---|---|---|
| job-description + hiring-scorecard | Textio, ≈ $10k/yr ÷ 12 ÷ 10 users ≈ $83 | $83 × 0.3 | $25 |
| performance-review (tool) | Lattice, $10 × 8 reports | $80 × 0.1 | $8 |
| performance-review (coaching) | Kona Coach | $19 × 0.3 | $5.7 |
| onboarding-planner | BambooHR (3P), $10 × 8 | $80 × 0.1 | $8 |
| **Total** | | | **≈ $47/seat/mo** |

**Discount: 50–60% [INFERENCE].**
- No HRIS or system of record, no review cycles or workflow, and HR data stays in the customer's AI.
- The real target is SMB HR people who are priced out of the $4k–25k/yr minimums.
- $47 × 0.4–0.5 ≈ **$19–23**.

**Recommended price: $19–29 per seat/mo** (suggest $24).
- It sits at or above Kona Coach ($19/manager) and far below every org minimum.
- 4 × $4.99 = $19.96, so the B2B pack is priced *above* the à la carte sum. That is only defensible with team or admin features. Otherwise drop to $15–19.

**Single agents at $4.99:**
- **Underpriced for B2B:** job-description. Textio/Datapeople cost $10k+/yr.
- **Fair:** hiring-scorecard, performance-review and onboarding-planner.

**Coherent bundle?** Yes, once split. The HR pack's buyer is an HR generalist or people manager at an SMB. The job-seeker pack's buyer is an individual consumer.

---

## 4. E-commerce

Agents: product-listing, review-responder, store-cro, inventory-planner, ecom-pricing, email-flows, support-desk.

| Tool | Plan | $/mo | Billing | Job | Overlap | Source | Date seen |
|---|---|---|---|---|---|---|---|
| Helium 10 | Platinum | $129 (monthly); $99 (annual); for $0–100k/yr sellers | monthly/annual | Amazon keyword, listing and ops suite | partial (product-listing; partly pricing/inventory) | https://www.helium10.com/pricing/ (1P) | 2026-09-27 |
| Jungle Scout | Catalyst Starter | $29 (monthly); $348/yr; Growth $49, Brand Owner $129 | monthly/annual | Amazon research and listing | partial (product-listing) | https://www.junglescout.com/pricing/catalyst-plans/ (1P) | 2026-09-27 |
| Describely | Pay-as-you-go | $0.75/product (≤500 products); High Volume custom | usage | AI product descriptions / SEO | high (product-listing) | https://describely.ai/pricing (1P) | 2026-09-27 |
| Inventory Planner (Sage) | n/a | not public ("Request pricing"; unlimited users) | quote | Demand forecasting and purchase orders | partial (inventory-planner) | https://www.inventory-planner.com/pricing/ (1P) | 2026-09-27 |
| Prediko | Under $100k GMV | $49 (monthly); 2 months free on annual; higher tiers not shown | monthly/annual | Shopify demand forecasting | partial (inventory-planner) | https://www.prediko.io/pricing (1P) | 2026-09-27 |
| Klaviyo | Email | about $20/mo entry (3P; the 1P page did not render tiers) | monthly | Email/SMS sending and flows | low (email-flows; they send, we design) | 3P: https://www.omnisend.com/blog/klaviyo-pricing/ | 2026-09-27 |
| Gorgias | Starter | $10/mo (50 tickets); Basic $60 (3P). **AI Agent $0.90 per resolved conversation ($1 on Starter)** (1P) | monthly | Helpdesk + AI agent | low–partial (support-desk) | AI Agent: https://www.gorgias.com/blog/ai-agent-pricing (1P). Plan prices: https://chatarmin.com/en/blog/gorgias-pricing (3P) | 2026-09-27 |
| Judge.me | Awesome | $15 flat (Free plan also available); includes AI replies | monthly | Review collection + AI replies | partial (review-responder) | 3P: https://eevy.ai/blog/judgeme-pricing and Judge.me help center (judge.me/pricing returned 403) | 2026-09-27 |
| Yotpo | Reviews Starter | $15 (≤50 orders) up to $129 (≤1,000 orders); Pro from $169 | monthly | Reviews/UGC | low–partial (review-responder) | https://www.yotpo.com/pricing.md (1P) | 2026-09-27 |
| Prisync | Professional (URL-based) | $99 (100 products) | monthly | Competitor price tracking / repricing | low (ecom-pricing; we calculate, they scrape) | https://prisync.com/pricing/ (1P) | 2026-09-27 |
| Lucky Orange | Build | $39 (monthly); $32 (annual) | monthly/annual | Heatmaps, recordings, CRO | low (store-cro) | https://www.luckyorange.com/pricing (1P) | 2026-09-27 |
| Hotjar (Contentsquare) | Growth | $49 (monthly); $39 (annual) (3P; hotjar.com/pricing redirects to Contentsquare, which showed no prices) | monthly/annual | Heatmaps and recordings | low (store-cro) | 3P: https://www.usercall.co/post/hotjar-pricing | 2026-09-27 |

**Median comparable:**
- **All priced rows: $34/mo.** Values: 10, 15, 15, 20, 29, 39, 49, 49, 99, 129.
- **1P rows only: $44/mo.** Values: 15, 29, 39, 49, 99, 129.

**Overlap-weighted replaced value [INFERENCE]:**

| Agent | Comparable used | Price × weight | Value |
|---|---|---|---|
| product-listing | Jungle Scout | $29 × 0.3 | $8.7 |
| review-responder | Judge.me | $15 × 0.3 | $4.5 |
| store-cro | Lucky Orange | $39 × 0.1 | $3.9 |
| inventory-planner | Prediko | $49 × 0.3 | $14.7 |
| ecom-pricing | Prisync | $99 × 0.1 | $9.9 |
| email-flows | Klaviyo | $20 × 0.1 | $2.0 |
| support-desk | Gorgias Starter $10 + about 50 AI resolutions × $1 | $60 × 0.1 | $6.0 |
| **Total** | | | **≈ $50/mo per store** |

**Discount: 60–70% [INFERENCE].** This is the steepest discount of the four categories:
- Merchants expect one-click Shopify App Store integration. Every competitor here connects to the store, syncs data and acts on it (sends, reprices, replies).
- With Hundred, the merchant has to export or paste data into their AI, and nothing runs unattended.
- $50 × 0.30–0.40 ≈ **$15–20**.

**Recommended pack price: $15–25/mo per store** (suggest $19).
- 7 × $4.99 = $34.93, so this is a 28–57% bundle discount.

**Single agents at $4.99:**
- **Underpriced:** inventory-planner (Prediko $49; Inventory Planner is quote-only) and ecom-pricing (Prisync $99, although overlap is low).
- **Overpriced / hard to sell alone:**
  - review-responder: Judge.me's $15 plan already includes AI replies, and there is a free tier.
  - email-flows: Klaviyo users get flow templates and AI inside the product.
- **Fair:** product-listing, store-cro and support-desk.

**Coherent bundle?** Yes. There is one buyer: the owner-operator of a Shopify/DTC store. Amazon-first sellers (Helium 10, Jungle Scout) are a slightly different sub-segment, but product-listing and ecom-pricing still serve them.

---

## Summary of recommendations

| Pack | Median comparable (entry, $/mo) | Overlap-weighted value | Discount | Recommended | À la carte at $4.99 |
|---|---|---|---|---|---|
| Engineering (10) | $25/seat | ≈ $41.5 | 50–60% | **$15–19/seat** | $49.90 |
| Product & Design (7) | ≈ $21/seat | ≈ $47 | 55–65% | **$15–19** (consider moving accessibility-checker and pitch-deck-coach out) | $34.93 |
| Career: job seekers (4) | $25 | ≈ $25 (≈ $67 including amortized negotiation coaching) | about 50% | **$9–15/mo, or $19–29 per 90 days** | $19.96 |
| HR / managers (4) | $10–11 per employee; org floor ≈ $333 | ≈ $47/seat | 50–60% | **$19–29/seat** (or $15–19 without team features) | $19.96 |
| E-commerce (7) | $34 (all rows) / $44 (1P only) | ≈ $50/store | 60–70% | **$15–25/store** | $34.93 |

**Caveats:**
- Rows marked 3P come from secondary sources because the vendor page was blocked (403), not rendered, or unpublished. Confirm them before citing externally.
- The overlap weights (0.6 / 0.3 / 0.1), per-seat assumptions (8 reports per manager, 10 Textio users, 50 AI resolutions a month, a 3-month job search) and the EUR→USD rate are all **[INFERENCE]**.
