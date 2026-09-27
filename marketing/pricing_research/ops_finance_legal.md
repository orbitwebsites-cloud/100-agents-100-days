# Hundred pricing research: Operations, Finance, Legal packs

Researched 2026-09-27. Every price comes from a page fetched or a search result read on 2026-09-27. "Official" means the vendor's own pricing page. "3rd-party" means a review or aggregator site, used only when the vendor page didn't render or doesn't publish prices. Lines marked **[INFERENCE]** are my reasoning, not published data.

Conventions:
- **$/mo** is the lowest *paid* plan for one user, **billed monthly**. The annual-billing equivalent is in brackets.
- **Overlap** says how much of the comparable's job a Hundred agent does, running inside the customer's own AI. We host no UI, store no data, have no bank or accounting feeds, send nothing on our own, offer no e-signature, and give no legal or tax advice.
  - high: we do most of the job.
  - partial: we do the thinking and drafting, but the tool's automation or data is what people pay for.
  - low: mostly a different job.
- **Overlap weights** used in the replaced-value math **[INFERENCE]**: I set a weight per job, between 0.1 and 0.5, and the weight is shown in each calculation.

---

## 1. OPERATIONS & PRODUCTIVITY

Agents: meeting-ops (free), inbox-triage, sop-writer, project-planner (critical path), okr-coach, status-reporter, decision-matrix, time-blocker, vendor-evaluator.

| Tool | Lowest paid plan | $/mo (monthly) [annual equiv.] | Billing notes | Job | Overlap w/ Hundred | Buyer | Source | Seen |
|---|---|---|---|---|---|---|---|---|
| Otter.ai | Pro | $16.99 [$8.33] | per user; free Basic tier exists | Meeting transcription + summaries | low-partial (meeting-ops structures agendas, minutes and actions; doesn't record) | founder/team | https://otter.ai/pricing (official) | 2026-09-27 |
| Fireflies.ai | Pro | $18 [$10] | per seat | Meeting notetaker | low-partial (meeting-ops) | founder/team | https://fireflies.ai/blog/fireflies-pricing-which-plan-is-right-for-you (official blog, 2026-07-10; pricing page didn't render prices) | 2026-09-27 |
| Fathom (meetings) | Premium | $20 [$16] | per user; Team $19 [$15], min 2 users | Meeting notetaker | low-partial (meeting-ops) | founder/team | https://fathom.ai/pricing (official) | 2026-09-27 |
| Superhuman | Pro | $15 [$12] | per user | AI email client / triage | partial (inbox-triage, when the customer's AI has a mail connector) | founder/exec | https://superhuman.com/plans (official) | 2026-09-27 |
| SaneBox | Snack | $9.49 [annual figure unverified: 3rd-party sources conflict] | 1 mailbox; Lunch $15.99 monthly | Automatic inbox filtering | partial (inbox-triage) | founder/consumer | https://aiproductivity.ai/pricing/sanebox/ (3rd-party, updated Jun 2026; official page didn't render prices) | 2026-09-27 |
| Motion | Pro AI | $19 [$12.73] | per seat | AI auto-scheduling + projects | partial (time-blocker, project-planner) | founder/freelancer | https://www.usemotion.com/pricing (official) | 2026-09-27 |
| Reclaim.ai | Starter | $12 [$10] | per seat; free Lite tier | Calendar time-blocking | partial (time-blocker) | founder/knowledge worker | https://reclaim.ai/pricing (official); the fetched page appeared to swap the annual and monthly labels, so figures are confirmed by https://www.morgen.so/blog-posts/reclaim-pricing (3rd-party) | 2026-09-27 |
| Sunsama | Pro | $22 [$17] | single plan | Daily planning / timeboxing | partial (time-blocker) | founder/freelancer | https://www.sunsama.com/pricing (official) | 2026-09-27 |
| Scribe | Pro Personal | $35 [$25] | 1 seat; Pro Team $17 [$13], min 5 seats | SOP / how-to guide capture | partial (sop-writer drafts SOPs; no automatic screen capture) | ops lead/founder | https://scribe.com/pricing (official) | 2026-09-27 |
| Tango | Pro | $26 [$22] | per user for 1–2 users; $20 [$15] for 3+ | SOP / workflow capture | partial (sop-writer) | ops lead | https://www.tango.ai/pricing (official) | 2026-09-27 |
| Asana | Starter | $13.49 [$10.99] | per user | Project/work management | low-partial (project-planner, status-reporter; Asana is the system of record) | team/founder | https://asana.com/pricing (official) | 2026-09-27 |
| monday.com | Basic (Work Mgmt) | $12 [$9] per seat, **3-seat minimum**, so $36 [$27] floor | seat minimum | Work management | low-partial | team | https://www.polarishq.co/cost/monday-pricing and https://get-alfred.ai/blog/monday-pricing (3rd-party; official page rendered inconsistent min-seat data) | 2026-09-27 |
| Smartsheet | Pro | $12 [$9] | per member | Gantt / critical path / PM | partial (project-planner critical path) | ops/PMO | https://costbench.com/software/project-management/smartsheet/ and https://www.softr.io/blog/smartsheet-pricing (3rd-party; the official page rendered garbled multi-currency numbers) | 2026-09-27 |
| Perdoo | Premium | €6.40/user [annual or quarterly only] | free up to 5 users | OKR software | partial (okr-coach: coaching and quality scoring, not tracking) | team lead/founder | https://www.perdoo.com/pricing (official) | 2026-09-27 |
| Weekdone | Paid (volume tiers) | ~$9.86/user annual for 4–6 users (monthly ~20% higher) | free up to 3 users | OKRs + weekly status | partial (okr-coach, status-reporter) | team lead | https://www.tability.io/compare/platform/weekdone (3rd-party, verified 2026-07-31); official https://weekdone.com/prices shows tiers but no per-user figure | 2026-09-27 |
| Quantive (context) | Discontinued | n/a (historically from $18/user) | acquired by WorkBoard, May 2025 | Enterprise OKR | n/a | enterprise | https://www.tability.io/compare/platform/quantive (3rd-party) | 2026-09-27 |
| Vendr (context) | Platform | median **$47,000/yr** (range $10,932–$230,631) | annual | SaaS procurement + negotiation | low (vendor-evaluator is a scoring framework; Vendr has price data + negotiators) | finance/procurement | https://www.vendr.com/marketplace/vendr (Vendr's own buyer data) | 2026-09-27 |

**Stats (single-seat, excl. context rows).** The 13 US$ single-seat rows are Otter through Smartsheet; Perdoo (€) and Weekdone (tiered) are left out:
- Median monthly-billed price: **$16.99**. Range: $9.49–$35.
- Median annual-equivalent: **~$11.50**.

### Reasoning: Operations pack

- **What a founder actually stacks** **[INFERENCE]**. The weight is the share of each tool's job we replace:

  | Job | Tool used as the price | Price | Weight |
  |---|---|---|---|
  | Meeting notes | Fireflies | $18 | 0.15 |
  | Inbox | Superhuman | $15 | 0.30 |
  | Planning / time-blocking | Motion | $19 | 0.35 |
  | SOPs | Tango | $26 | 0.40 |
  | PM | Asana | $13.49 | 0.20 |
  | OKRs | Weekdone | ~$9.86 | 0.50 |

  - The stack costs **~$101/mo**. Overlap-weighted replaced value is **~$32/mo**.
  - decision-matrix, status-reporter and vendor-evaluator have no direct paid SaaS equivalent at SMB level, so they add no dollars here. They are retention and value-add.
- **Partial-substitute discount: 40–55%** **[INFERENCE]**.
  - The customer must already pay for Claude or ChatGPT.
  - Nothing persists between sessions unless their AI stores it.
  - There is no calendar or mail automation running in the background. Motion, Reclaim and SaneBox work while the user is away; we don't.
  - Result: **~$14–19/mo**.
- **Ceiling check.** The pack should cost no more than one mid-priced tool in the category (median $16.99). If it costs more than Superhuman or Motion, it reads as expensive for "prompts + calculators".
- **Recommended Operations pack: $12.99–$19.99/mo. Anchor $14.99/mo, or $149/yr.** À-la-carte is 8 paid agents × $4.99 = $39.92, so the pack is a clear ~60% bundle discount.
- **Single agents at $4.99.** All are fine at $4.99.
  - sop-writer could carry $6.99–7.99, since Scribe Pro Personal is $35 and Tango $26. But those prices pay for automatic screenshot capture we don't do. Leaving it at $4.99 is defensible.
  - project-planner (deterministic critical-path math) is the strongest "expert tool" in the pack and makes good hero or free-trial bait.

---

## 2. FINANCE & MONEY

Agents: cashflow-forecaster (13-week), invoice-chaser, pricing-strategist, unit-economics, budget-coach, startup-model, expense-categorizer, freelance-tax estimator, investor-update writer.

### 2a. Founder / SMB finance comparables

| Tool | Lowest paid plan | $/mo (monthly) [annual equiv.] | Billing notes | Job | Overlap | Buyer | Source | Seen |
|---|---|---|---|---|---|---|---|---|
| Float | Essentials | $130 [$105] | single entity, <£2m revenue | Cash-flow forecasting synced to Xero/QBO | partial (cashflow-forecaster builds the 13-week model; no ledger sync) | founder/finance lead | https://floatapp.com/pricing (official) | 2026-09-27 |
| Fathom (fathomhq) | Starter | $59 (1 company) | monthly, no contract; the page says AUD is the base currency, so the USD figure may be a conversion | Management reporting / KPIs / forecasts | low-partial (unit-economics, investor-update) | finance lead/accountant | https://www.fathomhq.com/pricing (official); 3rd-party reports $50–65 | 2026-09-27 |
| LivePlan | Standard | $20 [$15] | Premium $40 [$30] | Business plan + forecast | partial-high (startup-model) | founder | https://www.liveplan.com/pricing (official) | 2026-09-27 |
| Causal | Startup | $250 (2 members) | 3rd-party; +$29/extra member | Financial modeling | partial (startup-model) | founder/finance lead | https://makerstack.co/reviews/causal-review/ (3rd-party via search; Causal is now owned by LucaNet) | 2026-09-27 |
| Runway (FP&A) | Not published | ~$6k–18k/yr (~$500–1,500/mo) | quote-only | FP&A / runway planning | partial (startup-model, cashflow) | finance lead | https://metapraxis.com/runway-implementation-cost (3rd-party estimate). runway.com is the AI-video Runway and is not comparable | 2026-09-27 |
| Finmark (context) | Discontinued | n/a | standalone product shut down 2026-04-01 per 3rd-party; folded into BILL | Startup modeling | n/a | founder | https://www.trustradius.com/products/finmark/pricing (3rd-party via search) | 2026-09-27 |
| ChartMogul | Pro | from $1,188/yr (= **$99/mo**, annual only) | free under $120K ARR; scales with ARR | SaaS metrics | partial (unit-economics: we compute LTV/CAC/payback from numbers the user gives; no Stripe sync) | SaaS founder | https://chartmogul.com/pricing/ (official) | 2026-09-27 |
| Baremetrics | Launch | $75 | up to 35% off annual; ≤$360K ARR | SaaS metrics + dunning add-ons | partial (unit-economics) | SaaS founder | https://baremetrics.com/pricing (official) | 2026-09-27 |
| ProfitWell Metrics (context) | Free | $0 | free; Price Intelligently consultancy divested by Paddle to SBI in 2024 (3rd-party), engagement pricing not public | SaaS metrics / pricing strategy | context: free metrics cap what unit-economics can charge; pricing-strategy consulting has no public price | SaaS founder | https://www.paddle.com/profitwell-metrics (official) | 2026-09-27 |
| Chaser | Compact | **$259** [$233] (£199 [£179]) | <£4m revenue, 4 users | Automated AR / invoice chasing | partial (invoice-chaser drafts the escalation sequence and schedule; doesn't auto-send from the AR ledger) | finance lead/SMB | https://www.chaserhq.com/chaser-pricing (official) | 2026-09-27 |
| Visible.vc | Base (founders) | $69 [$59] | free Starter (100 investors) | Investor updates + CRM/data room | high-partial (investor-update writer does the writing; Visible does sending, tracking, data room) | founder | https://visible.vc/pricing/ (official) | 2026-09-27 |
| Fractional CFO (human) | Hourly | median **~$300/hr** (band $175–500). Pre-seed $175–275, seed $225–350 | typical engagement $3k–15k/mo | 13-week cash, models, pricing, board updates | the gold-standard job we partly automate | founder | https://cfoadvisors.com/blog/fractional-cfo-hourly-rates-2026-benchmarks (published 2026-08-06) | 2026-09-27 |

**Stats.** Median monthly price of the 10 priced founder/SMB rows (Float, Fathom, LivePlan, Causal, ChartMogul, Baremetrics, Chaser, Visible, plus QB Solopreneur and Keeper Bookkeeping below): **~$72/mo**. Range: $20–$259.

### 2b. Consumer / freelancer money comparables

| Tool | Lowest paid plan | $/mo (monthly) [annual equiv.] | Billing notes | Job | Overlap | Buyer | Source | Seen |
|---|---|---|---|---|---|---|---|---|
| YNAB | Subscription | $14.99 [$9.08 = $109/yr] | 34-day trial | Zero-based budgeting (bank-linked) | partial (budget-coach does the method and coaching; no bank feed) | consumer | https://www.ynab.com/pricing (official) | 2026-09-27 |
| Monarch Money | Core | $14.99 [$8.33 = $99.99/yr]; Plus $199/yr, annual only | 7-day trial | Budget + net worth (bank-linked) | partial (budget-coach) | consumer | https://getfinny.app/blog/monarch-money-pricing-2026 (3rd-party, 2026-06-09); the official monarch.com/pricing page didn't render prices | 2026-09-27 |
| Copilot Money | Subscription | $13 [$7.92 = $95/yr] | Apple-only | Budget + auto-categorization | partial (budget-coach, expense-categorizer) | consumer | https://getfinny.app/blog/copilot-money-pricing-2026 (3rd-party, 2026-06-25); the official page returned 404 | 2026-09-27 |
| Keeper | Bookkeeping Only | $20 (monthly); Standard $199/yr ($16.58/mo) includes a tax-pro-signed return | 14-day trial | Write-off detection + filing | partial (expense-categorizer, freelance-tax estimator; we don't connect accounts or file) | freelancer | https://www.keepertax.com/pricing (official) | 2026-09-27 |
| QuickBooks Solopreneur | Solopreneur | $20 (promo $10 for 3 mo) | monthly | Categorization, Schedule C prep, quarterly estimates | partial (expense-categorizer, freelance-tax) | freelancer | https://quickbooks.intuit.com/solopreneur/ (official) | 2026-09-27 |

**Stats.** Consumer median **$14.99/mo** monthly-billed. Annual-equivalent median **~$8.70/mo**.

### Reasoning: Finance

- **The category splits cleanly into two buyers** **[INFERENCE]**:
  - Founders and finance leads pay $59–259/mo per tool.
  - Consumers and freelancers pay $13–20/mo.
  - One pack at one price will be too cheap for the first group or too expensive for the second. Recommend two packs.
- **Founder Finance pack**: cashflow-forecaster, invoice-chaser, pricing-strategist, unit-economics, startup-model, investor-update.

  | Job | Tool used as the price | Price | Weight |
  |---|---|---|---|
  | Cash forecasting | Float | $130 | 0.30 |
  | AR chasing | Chaser | $259 | 0.10 |
  | Startup model | LivePlan | $20 | 0.50 |
  | SaaS metrics | Baremetrics | $75 | 0.25 |
  | Investor updates | Visible | $69 | 0.35 |

  - Stack **~$553/mo**. Overlap-weighted replaced value **~$118/mo** **[INFERENCE]**.
  - Partial-substitute discount **55–70%**:
    - no bank or ledger feeds, which is the core of what Float, Chaser and Baremetrics charge for;
    - nothing runs on a schedule;
    - the user must paste or export their numbers.
  - That leaves **~$35–53/mo**.
  - Cross-check: one hour of a fractional CFO (~$300) buys ~6–8 months of the pack.
  - **Recommended: $29–49/mo. Anchor $39/mo, or $390/yr.** À-la-carte is 6 × $4.99 = $29.94, so at $39 the pack costs more than the singles. Either raise the key singles (below) or price the pack at $29.
- **Personal Money pack**: budget-coach, expense-categorizer, freelance-tax estimator.
  - YNAB $14.99 × 0.3 + Keeper $20 × 0.3 gives ~$10.50 replaced value. Discount ~30% because bank sync is the headline feature consumers pay for. That leaves **~$7**.
  - **Recommended: $6.99–9.99/mo. Anchor $7.99.** It must sit clearly below YNAB and Monarch annual-equivalents ($8.33–9.08) or it loses the comparison.
- **Single agents that look under-priced at $4.99** **[INFERENCE]**:

  | Agent | Suggested price | Why |
  |---|---|---|
  | cashflow-forecaster (13-week) | $9.99–14.99 | Float's floor is $105–130/mo. A 13-week build is typically several fractional-CFO hours at ~$300/hr. |
  | startup-model | $9.99 | LivePlan is $20, Causal $250. |
  | investor-update writer | $7.99–9.99 | Visible Base is $69. We do the part founders hate (writing), not the sending. |
  | pricing-strategist | $9.99 | Pricing consultancies don't publish prices, and CFO or consultant hours are $175–500. |
  | unit-economics | leave at $4.99 | ProfitWell Metrics is free and ChartMogul is free under $120K ARR, which caps what we can charge. |
  | invoice-chaser | leave at $4.99 | Its value is in automation we don't provide. |
- **Tax positioning.** Keep the freelance-tax estimator at **$4.99 or lower**.
  - Keeper's $199/yr includes a return "reviewed & signed by a tax pro". QuickBooks bundles TurboTax-backed help.
  - A premium price for our estimator implies preparer-grade reliance we can't back. Position it as a "quarterly estimate + safe-harbor calculator; confirm with a CPA/EA".
  - No filing, no advice language.

---

## 3. LEGAL & ADMIN

Agents: contract-reviewer, privacy-policy drafter, nda-drafter, grant-writer, freelance-contract.

| Tool | Lowest paid plan | $/mo (monthly) [annual equiv.] | Billing notes | Job | Overlap | Buyer | Source | Seen |
|---|---|---|---|---|---|---|---|---|
| Spellbook | Not published | 3rd-party reports ~$89 to ~$500/user/mo; quote-only, annual, reported 6-mo minimum | the official page says pricing is by team size, no numbers | AI contract drafting/review in Word (for lawyers) | partial (contract-reviewer; different buyer: lawyers) | law firm / in-house | https://www.spellbook.com/pricing (official: no price); estimates from https://www.hyperstart.com/blog/spellbook-pricing/ (3rd-party) | 2026-09-27 |
| LegalOn | Not published | 3rd-party: ~$3,500/user/yr entry (~$292/mo); up to ~$8,000/user/yr for all modules | quote-only, low confidence | AI contract review | partial (contract-reviewer) | in-house legal | https://www.vaquill.ai/blog/legalon-pricing (3rd-party, citing a June 2026 check) | 2026-09-27 |
| Ironclad (context) | CLM | median **$40,110/yr** (range $15,000–$107,025) | annual + implementation | Contract lifecycle mgmt | low | legal ops | https://www.vendr.com/marketplace/ironclad (Vendr buyer data) | 2026-09-27 |
| LegalZoom | Business Attorney Plan | $43.17 (6-mo term, $259) [$39.09 = $469/yr]; 3rd-party reports $49/mo after trial | includes **attorney review of contracts up to 10 pages**, 1-hr annual consult, e-sign, 150+ templates | Prepaid attorney + docs | partial (contract-reviewer, NDA; they have a real attorney) | founder/SMB | https://www.legalzoom.com/attorneys/ (official) | 2026-09-27 |
| Rocket Lawyer | Standard | $34.99 [$12.41 = $149/yr] | "Unlimited AI contract reviews", unlimited documents & e-signatures, 12 Ask-an-Attorney/yr | Docs + AI review + attorney Q&A | **high** on NDA / freelance-contract / contract review (plus e-sign and attorney access we lack) | founder/freelancer/consumer | https://www.rocketlawyer.com/pricing (official) | 2026-09-27 |
| Termly | Starter | $14 [$10] per website | free tier (1 policy) | Privacy/cookie policy + consent banner | partial (privacy-policy drafter; no hosted auto-updating policy or banner) | founder/SMB | https://termly.io/pricing/ (official) | 2026-09-27 |
| iubenda | Essentials | $6.99 [$5.99] | ≤25K pageviews | Privacy/cookie policy generator | partial | SMB | https://www.iubenda.com/en/pricing (official) | 2026-09-27 |
| Termageddon | Single license | $12 [$9.92 = $119/yr] per website | auto-updates policies when laws change | Policy generator | partial (the auto-update is their moat) | SMB/agency | https://termageddon.com/pricing/ (official) | 2026-09-27 |
| Bonsai | Essentials (first tier with contracts) | $25 [$19]; Basic $15 [$9] has no contracts | per user | Freelance contracts + proposals + invoices | partial (freelance-contract; no e-sign or invoicing) | freelancer | https://www.hellobonsai.com/pricing (official) | 2026-09-27 |
| HoneyBook | Starter | $29 (same on annual per page) | contracts + e-sign on all plans | Client management + contracts | low-partial | freelancer/creative | https://www.honeybook.com/pricing (official) | 2026-09-27 |
| Grantable | Starter | $50 (page says "save 17%" annually, no figure shown); nonprofit $25 for year 1 | Pro $150 | AI grant writing workspace | **high** (grant-writer) | nonprofit/founder | https://www.grantable.co/pricing (official) | 2026-09-27 |
| Instrumentl | Discover | $349 [$299] | up to 3 users | Grant prospecting database + tracking | low-partial (we don't have a funder database) | nonprofit | https://www.instrumentl.com/pricing (official) | 2026-09-27 |

**Human benchmarks:**

| Benchmark | Figure | Source | Seen |
|---|---|---|---|
| Average US lawyer hourly rate (Clio Legal Trends, as of Jan 2025) | **$349/hr**; corporate practice avg **$461/hr** | https://www.clio.com/blog/lawyer-statistics/ (via search snippet; direct fetch returned 403) | 2026-09-27 |
| Flat-fee NDA drafting (one FL firm) | **$139**, 48-hr turnaround | https://www.jdwoodslaw.com/services/nda (official firm page) | 2026-09-27 |
| NDA draft marketplace avg (ContractsCounsel) | ~$480 draft / ~$370 review (flat fee, 2026) | https://www.contractscounsel.com/b/non-disclosure-agreement-cost (via search snippet; fetch returned 503; unverified) | 2026-09-27 |
| Flat-rate contract review (Law 4 Small Business) | **$50/page, 5-page min (≥$250)** | https://www.l4sb.com/services/flat-rate-contract-review/ (official) | 2026-09-27 |
| Freelance grant writer | $50–95/hr mid-level, $95–150+/hr senior; foundation grant $1,500–5,000/proposal | https://grantable.co/how-much-does-a-grant-writer-cost (Grantable guide, "as of July 2026") | 2026-09-27 |
| FTC v. DoNotPay ("robot lawyer") | Final order approved 2025-01-16: $193,000 relief + ban on claiming lawyer-equivalence without evidence | https://www.ftc.gov/news-events/news/press-releases/2025/02/ftc-finalizes-order-donotpay-prohibits-deceptive-ai-lawyer-claims-imposes-monetary-relief-requires | 2026-09-27 |

**Stats (self-serve SMB tools).** Median monthly price of LegalZoom (6-mo rate), Rocket Lawyer, Termly, iubenda, Termageddon, Bonsai, HoneyBook and Grantable: **$27/mo**. Range: $6.99–$50. Annual-equivalent median **~$12.41**. Spellbook, LegalOn and Ironclad are enterprise or lawyer tools, 10–100× higher, and don't set our anchor.

### Reasoning: Legal & Admin

- **Replaced value** **[INFERENCE]**:

  | Job | Tool used as the price | Price | Weight |
  |---|---|---|---|
  | Docs + AI review | Rocket Lawyer | $34.99 | 0.4 |
  | Privacy policy | Termly | $14 | 0.3 |
  | Freelance contracts | Bonsai | $25 | 0.2 |
  | Grant writing | Grantable | $50 | 0.5 |

  - Stack ~$124/mo. Weighted **~$48/mo**.
- **Partial-substitute + liability discount: ~50%** **[INFERENCE]**.
  - No e-signature.
  - No attorney in the loop. LegalZoom and Rocket Lawyer both include real attorney access at $35–49/mo.
  - No auto-updating hosted policy. This is Termageddon's and Termly's moat.
  - Not legal advice.
  - Result: **~$24/mo**.
- **Recommended Legal & Admin pack: $14.99–24.99/mo. Anchor $19.99.** Stay clearly **below Rocket Lawyer Standard monthly ($34.99)**, because it includes attorney Q&A and e-sign. Customers will compare directly. À-la-carte is 5 × $4.99 = $24.95.
- **Is contract-reviewer under-priced at $4.99?**
  - On the value math, yes. One lawyer review is ~$250–600: $50/page × 5-page minimum, or 1–2 hrs at $349/hr.
  - But the *price* signals the reliance you invite. At $4.99–9.99 it reads as "issue-spotter before you call a lawyer". At $29+ it starts to read as "replaces the lawyer", which is exactly the claim the FTC penalized in DoNotPay.
  - **Recommendation: $7.99–9.99 max**, with the positioning built into the agent:
    - flags risk tiers;
    - produces a "questions for your lawyer" list;
    - hard escalation triggers (litigation, IP assignment, indemnity above X, regulated industries);
    - jurisdiction disclaimer.
  - Don't market "saves a $350/hr lawyer". Say "walk into your lawyer's office with a marked-up contract, and spend 15 minutes instead of 2 hours". The saving is a shorter lawyer engagement, not no lawyer.
- **grant-writer is the most under-priced agent in this category.**
  - Grantable's cheapest paid tier is $50/mo. Human writers charge $1,500–5,000 per foundation proposal.
  - Grant writing is not the practice of law, so the liability risk is low.
  - **Recommend $12.99–19.99 as a single**, or move it into a Nonprofit/Fundraising pack. It doesn't fit "Legal" buyers.
- **privacy-policy drafter: keep at $4.99.**
  - Hosted generators cost $5.99–14/mo and *auto-update when laws change* plus provide cookie banners. We produce a static draft that goes stale.
  - Add "re-run when you add a new tracker or processor" and "this is not a compliance certification" messaging.
- **nda-drafter and freelance-contract: keep at $4.99.**
  - A lawyer's flat-fee NDA is ~$139. Rocket Lawyer gives unlimited documents from $12.41/mo annual.
  - Our edge is tailoring inside the user's own AI, not price.
- **Liability and positioning flags (legal and tax)**:
  1. **Price implies reliance.** Keep legal and tax agents priced as *tools*: single digits per agent, pack under $25. Premium prices belong on non-regulated expertise (grants, CFO-style modeling).
  2. **No "lawyer/CPA replacement" claims.** The FTC's DoNotPay order: $193K relief plus a ban on unsubstantiated lawyer-equivalence claims.
  3. **Unauthorized practice of law and tax-preparer rules** **[INFERENCE; not legal advice; get counsel]**. Stay on the "information + drafting aid" side: no individualized "you should sign this", no filing, no "we guarantee compliance".
  4. **Build the disclaimers and escalation rules into the agent's playbook**, not just the footer. The customer's AI will surface them in context.
  5. Consider **ToS limitation-of-liability caps tied to fees paid**. A low price also keeps the damages exposure small.

---

## 4. Summary of recommendations

| Pack | Comparable median (monthly-billed) | Overlap-weighted replaced value | Discount applied | Recommended pack price | À-la-carte at $4.99 |
|---|---|---|---|---|---|
| Operations & Productivity (8 paid + meeting-ops free) | $16.99/tool | ~$32/mo | 40–55% | **$12.99–19.99 (anchor $14.99)** | $39.92 |
| Founder Finance (6 agents) | ~$72/tool | ~$118/mo | 55–70% | **$29–49 (anchor $39)** | $29.94, so raise key singles |
| Personal Money (3 agents) | $14.99/tool | ~$10.50/mo | ~30% | **$6.99–9.99 (anchor $7.99)** | $14.97 |
| Legal & Admin (5 agents) | $27/tool (SMB self-serve) | ~$48/mo | ~50% (partial + liability) | **$14.99–24.99 (anchor $19.99)** | $24.95 |

Under-priced at $4.99:

| Agent | Suggested price |
|---|---|
| cashflow-forecaster | $9.99–14.99 |
| startup-model | $9.99 |
| pricing-strategist | $9.99 |
| investor-update | $7.99–9.99 |
| grant-writer | $12.99–19.99 (consider moving out of Legal) |
| contract-reviewer | ≤$9.99 (hold the ceiling on purpose, for liability) |

Keep at $4.99 or lower: freelance-tax, privacy-policy, nda-drafter, unit-economics.

**Data-quality caveats:**
- SaneBox, Monarch, Copilot, Smartsheet, monday seat-minimum, Weekdone and Causal figures are 3rd-party because the vendor pages didn't render prices.
- Spellbook and LegalOn don't publish prices, so those are 3rd-party estimates.
- The Fathom (finance) USD figure may be converted from AUD.
- Quantive and Finmark are discontinued.
- No figures were invented. Where a number couldn't be verified, it is marked as such above.
