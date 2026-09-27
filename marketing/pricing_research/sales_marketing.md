# Hundred: pricing research for the Sales and Marketing packs

Researched 2026-09-27. Every price below was seen on 2026-09-27 at the URL given.
Source quality tags:
- **[official]**: the vendor's own pricing page.
- **[3p]**: third-party article or estimate. Used only where the vendor page is JS-rendered, hides prices or is sales-led.
- **[not public]**: the vendor publishes no price.
- **INFERENCE**: our own reasoning, not a published number.

Overlap scale (how much of the tool's *job* one of our agents does inside the customer's AI):
- **High** = 0.8: the core job is the same. We still don't send, store or host anything.
- **Partial** = 0.4: we do the thinking and math part, and the tool's value is mostly infrastructure.
- **Low** = 0.15: the tool's value is mostly data, sending, hosting, recording or integration that we don't provide.

These weights are INFERENCE.

---

## 1. SALES: comparable tools

| Tool | Lowest paid plan (and relevant plan) | $/seat/mo | Billing | Job it does | Overlap with our agent(s) | Typical buyer | Source | Date |
|---|---|---|---|---|---|---|---|---|
| Lavender (Email Coach) | Starter | $29 monthly / $27 annual. Individual Pro $49/$45. Team $99/$89 per seat | Monthly or annual | Real-time scoring and coaching of sales emails, personalization | **High**: cold-email. Partial: follow-up-machine | Individual SDR/AE | https://www.lavender.ai/coach [official] | 2026-09-27 |
| Regie.ai | Pro (1 user) | $49 monthly / $41 annual. Team $150/$125 per seat, min 2 seats | Monthly or annual | AI prospecting, research, sequence drafting, dialer | **High**: cold-email, follow-up-machine. Partial: lead-qualifier, linkedin-prospector | SDR teams, founders | https://www.regie.ai/pricing [official] | 2026-09-27 |
| Apollo.io | Basic | $59 monthly / $49 annual. Professional $99/$79. Organization $149/$119 | Per user, monthly or annual | B2B contact database, enrichment, sequences, lead scoring | Partial: lead-qualifier. Low: cold-email, linkedin-prospector (value is the data) | SDRs, founders | apollo.io/pricing renders prices in JS, so no $ was visible to the fetch. Figures from https://www.warmly.ai/p/blog/apollo-pricing [3p], matching several 2026 search results | 2026-09-27 |
| Instantly.ai | Outreach Growth | $47 monthly / $37.60 annual, **per workspace, not per seat** | Monthly or annual | Cold-email sending infrastructure, warmup, sequences | Partial: cold-email, follow-up-machine (we don't send) | Founders, agencies, lean outbound | https://instantly.ai/pricing [official] | 2026-09-27 |
| lemlist | Email plan | $69 monthly / $55 annual (unlimited users). Multichannel $109/$87 per user | Monthly, quarterly or annual | Multichannel outreach sequences, personalization | Partial: cold-email, follow-up-machine, linkedin-prospector | Founders, SDRs, agencies | https://www.lemlist.com/pricing [official] | 2026-09-27 |
| LinkedIn Sales Navigator | Core | $119.99 monthly / $89.99 per month on annual ($1,079.88/yr) | Per license | LinkedIn lead search, lead lists, InMail | Low: linkedin-prospector (value is the data and InMail) | SDR/AE, founders | https://business.linkedin.com/sales-solutions/compare-plans [official] | 2026-09-27 |
| Crystal (Predictions for sales) | Premium | $59 monthly / ~$49.17 annual ($590/yr) | Monthly or annual | DISC personality profiles of prospects, how to sell to and negotiate with them | Low: negotiation-coach, objection-handler, discovery-call-coach | AEs, founders | https://www.crystalknows.com/pricing [official] | 2026-09-27 |
| PandaDoc | Starter | $35 monthly / $19 annual. Business $65/$49 | Per seat | Proposals, quotes, pricing tables, e-sign, tracking | Partial: proposal-builder (we build content, pricing tables and timelines, with no e-sign or tracking) | AEs, founders, agencies | pandadoc.com/pricing returned 429 to the fetch. Figures from search results citing https://www.pandadoc.com/pricing/ plus https://costbench.com/software/contract-management/pandadoc/ [3p] | 2026-09-27 |
| Proposify | Basic | $29 monthly / $19 annual. Team $41 annual / $49 quarterly | Per user | Proposal software (10 sends/mo on Basic) | Partial: proposal-builder | Agencies, AEs, founders | https://www.proposify.com/pricing [official] | 2026-09-27 |
| Fathom | Premium (lowest paid) and Business (CRM sync plus coaching) | Premium $20 monthly / $16 annual. **Business $34 monthly / $25 annual** | Per user | Call recording and AI notes. Business adds CRM field sync, coaching metrics and AI scorecards | Partial: sales-call-debrief, discovery-call-coach (we don't record or transcribe) | AEs, founders | https://www.fathom.ai/pricing [official] | 2026-09-27 |
| HubSpot Sales Hub | Starter | $20 monthly per seat as listed. The page currently shows a **$7/seat/mo promotional** annual price for new customers. Pro $100 monthly / $90 annual | Per seat | CRM, pipeline, sequences, basic forecasting | Low: pipeline-forecaster, follow-up-machine | Founders, SMB sales | https://www.hubspot.com/pricing/sales/starter [official] | 2026-09-27 |
| Gong | Core (+ Engage and Forecast add-ons) | **[not public]**. 3p estimate ~$1,300–1,600/user/yr (about $108–133/mo), plus a $5k–50k/yr platform fee and $7.5k+ onboarding | Annual contract | Conversation intelligence, deal coaching, forecasting | Partial: discovery-call-coach (MEDDPICC, talk ratio), sales-call-debrief, pipeline-forecaster | Sales leaders and RevOps at mid-market and enterprise | https://marketbetter.ai/blog/gong-pricing-breakdown-2026/ and https://revenuegrid.com/blog/gong-pricing/ [3p] | 2026-09-27 |
| Clari | Core | **[not public]**. 3p estimate ~$100–120/user/mo annual. Small teams rarely pay under ~$24k/yr | Annual contract | Revenue forecasting, pipeline inspection | Low: pipeline-forecaster | CRO, RevOps | https://revenuegrid.com/blog/clari-pricing/ and https://marketbetter.ai/blog/clari-pricing-breakdown-2026/ [3p] | 2026-09-27 |
| Chorus (ZoomInfo) | n/a | **[not public]**. Bundled into ZoomInfo contracts. 3p: $35k–60k+/yr for 10 users in bundles | Annual contract | Conversation intelligence | Partial: sales-call-debrief, discovery-call-coach | Enterprise sales orgs | https://www.claap.io/blog/gong-vs-chorus-which-is-better-and-why [3p] | 2026-09-27 |

### Sales tool-spend benchmarks (cited)
- **Optifai sales tech stack benchmark** (N=938 B2B companies, data Jan–Sep 2025): the average stack has **8.3 tools costing $187/rep/month (~$2,244/yr)**. Industry figures: SaaS $412/rep/mo, financial services $572. Separately, "73% of teams waste $2,340/rep/year on overlapping tools." Source: https://optif.ai/media/articles/sales-tech-stack-benchmark-2025 (vendor-published, method not independently verified; seen 2026-09-27).
- A figure of "$371 per SDR per month on technologies" and "$8,000–16,000 per SDR seat annually" (ZoomInfo + Outreach/Salesloft + Salesforce + Sales Nav) appeared in search results tied to https://stealthagents.com/research/cost-of-hiring-an-sdr-2026 and The Bridge Group context (https://www.bridgegroupinc.com/research/2025-sdr-models-metrics-report-the-bridge-group). **Not verified against the primary report.** Treat it as directional only.

---

## 2. MARKETING: comparable tools

| Tool | Lowest paid plan (and relevant plan) | $/seat/mo | Billing | Job it does | Overlap with our agent(s) | Typical buyer | Source | Date |
|---|---|---|---|---|---|---|---|---|
| Jasper | Pro | $69 monthly / $59 annual per seat. Business custom | Per seat | AI marketing copy, brand voice, campaigns | **High**: ad-copy-lab, email-campaign. Partial: brand-voice guardian, press-release pro, launch-planner | Content and marketing teams | https://www.jasper.ai/pricing [official] | 2026-09-27 |
| Copy.ai | Chat | $29 monthly / $24 annual **for 5 seats** (~$5.80/seat monthly). Growth $1,000/mo (75 seats) | Monthly or annual | AI chat and workflow copywriting | Partial: ad-copy-lab, email-campaign (mostly generic LLM chat, which the customer already has) | SMB marketers, GTM teams | https://www.copy.ai/prices [official] | 2026-09-27 |
| Anyword | Starter (1 seat) | $49 monthly / $39 annual. Data-Driven $99/$79 (3 seats) | Monthly or annual | Ad and landing copy with predictive performance scores and channel formats | **High**: ad-copy-lab. Partial: landing-page-cro, email-campaign | Performance marketers | https://www.anyword.com/pricing [official] | 2026-09-27 |
| WRITER | Starter | writer.com/plans shows **no $** ("monthly or annual per-seat plans"). 3p: $39 monthly / $29 annual per user | Per seat | Enterprise AI writing with enforced brand and style guides | **High**: brand-voice guardian. Partial: press-release pro, email-campaign | Content and brand teams | https://writer.com/plans/ [official, no price] and https://www.eesel.ai/blog/writer-com-pricing [3p] | 2026-09-27 |
| Grammarly | Pro | $12/mo as displayed (the page does not say whether that is the annual rate). Pro includes 1 brand tone and 1 style guide | Per member | Writing correction, tone, brand tone | Partial: brand-voice guardian | Everyone | https://www.grammarly.com/plans [official] | 2026-09-27 |
| Unbounce | Starter. AI copywriting starts at Build | Starter $29 monthly / $22 annual. **Build $99 / $74** (AI copywriting). Experiment $149/$112 (A/B testing) | Per account | Landing page builder and hosting, A/B tests, AI copy. Note: Unbounce now exposes MCP on all plans | Low: landing-page-cro (they build, host and test; we audit and rewrite). Low: ab-test-analyst | Demand-gen marketers, agencies | https://unbounce.com/pricing/ [official] | 2026-09-27 |
| VWO Testing | Starter / Growth | **[not public on page]** (wingify.com/pricing shows tiers without $). 3p: Starter ~$314/mo at 10K MTU. Growth $665 annual / $798 monthly at 100K MTU (from in-app checkout, May 2026). Vendr median ~$16.7k/yr | Per account, MTU-based | A/B and multivariate experimentation platform | Low: ab-test-analyst (we do significance and sample-size math only; they run the experiments) | CRO and growth teams | https://wingify.com/pricing/ [official, no $]; https://www.conversionwax.com/vwo-pricing/ and https://www.mida.so/blog/how-much-is-vwo [3p] | 2026-09-27 |
| Optimizely | n/a | **[not public]**, sales-led | Annual contract | Experimentation and CMS | Low: ab-test-analyst, landing-page-cro | Enterprise | Not verified; no public price found | 2026-09-27 |
| Semrush Content Toolkit (ContentShake successor) | Content | **$60/mo billed annually** (monthly rate not shown). +$20/mo per extra user | Annual shown | SEO content ideas, AI writing "in your brand voice", optimization | Partial: brand-voice guardian. Low: positioning-strategist, persona-builder, email-campaign | Content and SEO marketers, SMB | https://www.semrush.com/pricing/content/ [official] | 2026-09-27 |
| Semrush AI PR Toolkit (formerly Prowly) | Base | **$149/mo billed annually**. Pro $279, Business $499 | Annual shown | Media database, journalist recommendations, pitching, press-release writing help, monitoring | Partial/Low: press-release pro (we write and score the release; their value is the media database and pitching) | PR pros, founders, agencies | https://www.semrush.com/pricing/pr/ [official]; prowly.com now redirects users to it | 2026-09-27 |
| Semrush SEO toolkit | SEO | $139 monthly / $117.33 annual | Per account (+$45/mo per extra user) | SEO research, rank tracking | Low: positioning-strategist, persona-builder (reference only) | SEO marketers | https://www.semrush.com/prices/ [official] | 2026-09-27 |
| Mailchimp | Standard | "Starting at" $20/mo (Essentials $13), scales with contacts | Per account | Email campaign sending and automation | Low: email-campaign writer (they send; we write and structure) | SMB marketers | https://mailchimp.com/pricing/marketing/ [official] | 2026-09-27 |
| HubSpot Marketing Hub | Starter | Shown as $7/seat/mo promotional, "reduced from $20/month". Pro $800/mo (3 seats) | Per seat | Marketing CRM, email, forms, landing pages | Low: email-campaign, marketing-budget planner | SMB marketers | https://www.hubspot.com/pricing/marketing [official] | 2026-09-27 |
| Evan Miller A/B sample-size calculator | Free | $0 | n/a | Sample size and significance math | Direct substitute for ab-test-analyst's math | CRO practitioners | https://www.evanmiller.org/ab-testing/sample-size.html (free web page) | 2026-09-27 |

### Marketing tool-spend benchmarks (cited)
- **Gartner 2026 CMO Spend Survey** (401 CMOs):
  - Martech share of the marketing budget is at a **five-year low of 19.4%**, down from 26.6% in 2021.
  - **56%** increased the share of martech spend on consumption- or usage-based pricing.
  - Marketing budgets are **7.8% of company revenue**, and **15.3%** of the marketing budget goes to AI initiatives.
  - Sources: https://www.chiefmarketer.com/gartner-cmo-spend-survey-budgets-reflect-increase-in-consumption-based-martech-paid-media-spend/ (article dated 2026-06-24) and the Gartner press release title at https://www.gartner.com/en/newsroom/press-releases/2026-05-11-gartner-2026-cmo-spend-survey-finds-cmos-allocate-15-point-3-percent-of-marketing-budgets-to-ai-but-only-30-percent-are-ready-to-scale-ai-capabilities. The direct fetch was blocked (403), so these numbers are via the article and search snippet. Seen 2026-09-27.
- Gartner 2025 (for trend): martech was 22.4% of budget, and budgets were 7.7% of revenue. https://www.gartner.com/en/newsroom/press-releases/2025-05-12-gartner-2025-cmo-spend-survey-reveals-marketing-budgets-have-flatlined-at-seven-percent-of-overall-company-revenue (via search snippet; direct fetch 403).
- There is no credible published "per marketer seat" tool-spend figure, so none is quoted.
- Baseline the customer already pays for the AI Hundred runs in: Claude Pro is $20 monthly / $16.67 annual, and Claude Team Standard is $25 monthly / $20 annual per seat. Source: https://claude.com/pricing [official]. (chatgpt.com/pricing returned 403 and was not verified.)

---

## 3. Reasoning and price range: SALES pack

**Median comparable price.** This uses public, lowest-paid, per-seat or per-account prices on monthly billing. It excludes Gong, Clari and Chorus, which are not public.

| Price set | Values (sorted) | Median |
|---|---|---|
| Monthly billing (n = 11) | 20, 29, 29, 34, 35, 47, 49, 59, 59, 69, 119.99 | **$47/mo** |
| Annual-equivalent | 7 (promo), 19, 19, 25, 27, 37.60, 41, 49, 49.17, 55, 89.99 | **$37.60/mo** |

**Overlap-weighted replaced value (INFERENCE).** We pick one representative tool per job cluster the pack covers, using its monthly price, then multiply by the overlap weight.

| Job cluster (our agents) | Representative tool | Price | Weight | Replaced value |
|---|---|---|---|---|
| Write, score and sequence emails (cold-email, follow-up-machine) | Lavender Starter | $29 | High 0.8 | $23.20 |
| Qualification and ICP scoring (lead-qualifier) | Apollo Basic | $59 | Low 0.15 | $8.85 |
| LinkedIn prospecting (linkedin-prospector) | Sales Navigator Core | $119.99 | Low 0.15 | $18.00 |
| Proposals (proposal-builder) | PandaDoc Starter | $35 | Partial 0.4 | $14.00 |
| Call coaching and debrief (discovery-call-coach, sales-call-debrief, objection-handler) | Fathom Business | $34 | Partial 0.4 | $13.60 |
| Buyer psychology and negotiation (negotiation-coach) | Crystal Premium | $59 | Low 0.15 | $8.85 |
| Forecasting (pipeline-forecaster) | Clari, 3p estimate ~$100 | ~$100 | Low 0.15 | ~$15.00 |
| **Total** | Sticker price of the whole stack: ~$436/mo | | | **~$101/mo** ($86 without the non-public Clari estimate) |

**Discount: 60–70% (INFERENCE), for four reasons.**
1. **No execution layer.** We don't send email, dial, record calls, e-sign, or hold contact data. Most buyers keep a sender (Instantly, lemlist or Apollo) and a CRM, so Hundred adds to that stack more than it replaces it.
2. **No native integration.** Results pass through the customer's AI chat, with no Gmail or Salesforce sidebar and no team dashboard.
3. **The customer pays for the runtime.** They need a $20/mo Claude Pro or ChatGPT seat. A raw LLM already gets them some of the way, and we sell the gap between that and expert output.
4. **What offsets the discount.** Hundred adds deterministic math (MEDDPICC scoring, talk ratio, ICP scores, forecast math, pricing tables) and expert playbooks. That covers the "coach" layer, which Gong and Lavender charge the most for.

**Replaced value after discount:** $101 × 0.30–0.40 = **~$30–40/mo**. Using only public prices: $86 × 0.30–0.40 = $26–34.

**Recommended Sales pack price: $29/mo monthly (range $25–39), about $24/mo billed annually.**
- It equals the cheapest single high-overlap point tool (Lavender Starter at $29) but covers 10 jobs.
- It is 38% below the $47 monthly-billing median and ~15% of the $187/rep/mo average stack spend (Optifai).
- Going above $39 would put it next to Regie Pro ($49) and Apollo Basic ($59), which do send and hold data. That comparison is hard to win.

**Single-agent value** (price × overlap × (1 − 0.65 discount), INFERENCE):

| Agent | Calculation | Value | Verdict against $4.99 |
|---|---|---|---|
| cold-email | $29 × 0.8 × 0.35 | ~$8 | Clearly above. **Supports $7.99–9.99 standalone** |
| proposal-builder | $35 (PandaDoc) × 0.4 × 0.35 | ~$4.90 | At $4.99 |
| sales-call-debrief | $34 (Fathom Business) × 0.4 × 0.35 | ~$4.76 | At $4.99 |
| discovery-call-coach | Gong-class tools at ~$110+/mo | Could justify more | But Gong buyers are enterprise, not our impulse buyer. Keep $4.99 |
| lead-qualifier, linkedin-prospector, negotiation-coach, objection-handler, pipeline-forecaster | Low overlap or free-prompt substitutes | Under $4.99 | $4.99 is at or above their value. Best sold in the pack |

Ten agents at $4.99 is $49.90 à la carte, so a $29 pack is about 42% off. That makes a clean bundle story.

---

## 4. Reasoning and price range: MARKETING pack

**Median comparable price.** This uses public, lowest-paid plans and excludes VWO and Optimizely, which have no public price.

| Price set | Values (sorted) | Median |
|---|---|---|
| Lowest paid plan (n = 10) | 12, 20, 20, 29, 29, 39 (Writer, 3p), 49, 60, 69, 149 | **~$34/mo** |
| With Unbounce at its AI-copy tier ($99) instead of $29 | 12, 20, 20, 29, 39, 49, 60, 69, 99, 149 | **~$44/mo** |

**Overlap-weighted replaced value (INFERENCE):**

| Job cluster (our agents) | Representative tool | Price | Weight | Replaced value |
|---|---|---|---|---|
| Ad and performance copy with platform limits (ad-copy-lab, plus email-campaign copy) | Anyword Starter | $49 | High 0.8 | $39.20 |
| Brand voice enforcement (brand-voice guardian) | WRITER Starter (3p) | $39 | Partial 0.4 | $15.60 |
| Landing-page CRO (landing-page-cro) | Unbounce Build | $99 | Low 0.15 | $14.85 |
| Content, positioning and personas (positioning-strategist, persona-builder, launch-planner) | Semrush Content | $60 | Low 0.15 | $9.00 |
| Press releases (press-release pro) | Semrush AI PR Base | $149 | Low 0.15 | $22.35 |
| Email campaigns (email-campaign writer) | Mailchimp Standard | $20 | Low 0.15 | $3.00 |
| A/B stats (ab-test-analyst) | VWO / free calculators | n/a | n/a | **$0**. Free calculators such as Evan Miller's already do the math, so the market price for it is zero |
| Budget, CAC and LTV (marketing-budget planner) | Spreadsheet or HubSpot | n/a | n/a | **$0**. No priced standalone comparable found |
| **Total** | Sticker price of the whole stack: ~$416/mo | | | **~$104/mo** |

**Discount: 70–80% (INFERENCE).** This is steeper than Sales, for four reasons.
1. **Writing is the LLM's native strength.** The customer's own Claude or ChatGPT already writes ads, emails and releases passably. Copy.ai sells chat at $29 for 5 seats (~$5.80/seat), which shows how much generic AI copy has been commoditized.
2. **Much of the remaining value is infrastructure.** We don't host pages (Unbounce), run experiments (VWO), send email (Mailchimp) or hold a media database (Semrush PR).
3. **Martech budgets are under pressure.** The martech share of marketing budgets is at a five-year low of 19.4%, and buyers are moving to usage-based pricing (Gartner 2026). Marketers are cutting tools, not adding seats.
4. **What offsets the discount.** Hundred adds deterministic validators (per-platform character limits, significance and sample size, CAC/LTV math) and brand-voice scoring, which a raw LLM gets wrong.

**Replaced value after discount:** $104 × 0.20–0.30 = **~$21–31/mo**.

**Recommended Marketing pack price: $24/mo monthly (range $19–29), about $19/mo billed annually.**
- It sits below Jasper Pro ($59–69), Anyword ($39–49) and Semrush Content ($60), and around Unbounce Starter and Copy.ai Chat ($29).
- If the business wants a single price for both packs, **$29** is still defensible for Marketing: it is below the ~$34 median and inside the replaced-value range. **$24** is the safer conversion price.

**Single-agent value** (INFERENCE, 0.3 retained):

| Agent | Calculation | Value | Verdict against $4.99 |
|---|---|---|---|
| ad-copy-lab | $49 (Anyword) × 0.8 × 0.3 | ~$11.80 | Clearly above. **Supports $7.99–9.99 standalone** |
| press-release pro | $149 × 0.15 × 0.3 | ~$6.70 | Modestly above |
| brand-voice guardian | $39 × 0.4 × 0.3 | ~$4.70 | At $4.99 |
| landing-page-cro | $99 × 0.15 × 0.3 | ~$4.50 | At $4.99 |
| ab-test-analyst | Market price ~$0 (free calculators) | ~$0 | $4.99 is above what the math alone is worth. It sells only as part of the pack or on playbook quality |
| marketing-budget planner, persona-builder, positioning-strategist, launch-planner | No priced comparable | Under $4.99 | Pack-only value |

---

## 5. Summary

| | Sales pack | Marketing pack |
|---|---|---|
| Median comparable (lowest paid, monthly billing) | $47/mo | ~$34/mo (~$44 using AI-copy tiers) |
| Overlap-weighted replaced value | ~$101/mo ($86 public-only) | ~$104/mo |
| Discount | 60–70% | 70–80% |
| Discounted value | ~$30–40 | ~$21–31 |
| **Recommended pack price** | **$29/mo** (range $25–39; ~$24 annual) | **$24/mo** (range $19–29; ~$19 annual) |
| Single agents clearly worth more than $4.99 | cold-email (~$8) | ad-copy-lab (~$12), press-release pro (~$7) |

Main caveats:
- Gong, Clari, Chorus, VWO Growth, Optimizely and the WRITER price are not public or come from third parties.
- The Apollo and PandaDoc figures are from third parties because the official pages could not be read by the fetch tool.
- The overlap weights and discounts are judgment calls (INFERENCE) and should be tested with pricing experiments.
