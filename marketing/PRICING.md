# Pricing: what every pack can sell for, and why

This is a decision memo built on researched prices, not guesses. The sources are in
`marketing/pricing_research/`: 5 files and about 120 comparable products. Every price
there has a source URL and was checked on 2026-09-27. Figures from third-party write-ups
or estimates are labelled as such. Anything below marked *(judgement)* is reasoning,
not data.

## 1. The evidence in six findings

1. **Bundles elsewhere cost 1.5–3.8× one product, usually 2.5–3×.** Adobe All Apps
   is 3.0× one app. Setapp is about 2.6×. JetBrains All Products is 1.5× its
   flagship IDE ($29.90 vs $19.90). Our current All-Access is **6×** a single agent
   ($29.99 / $4.99), well outside that band. *(bundles.md §1)*
2. **Buyers carry a $20 reference price in their heads.** ChatGPT Plus, Claude Pro,
   Gemini Pro, Perplexity and Cursor Pro all cost $20. AI add-ons on top of a base plan
   run $7–10/mo. Platforms that offer unlimited agents cost $19–30/mo (Relevance AI
   $19, Composio $29, Lindy $29.99, Zapier Pro $29.99). *(bundles.md §2–4)*
3. **Professionals compare us with the tools that do the same job.** The typical
   cheapest paid plan in each function:

   | Function | Typical cheapest paid plan |
   |---|---|
   | Sales | $47/seat |
   | Founder finance | about $72 |
   | Marketing | about $34 |
   | SEO | $34–44 |
   | Engineering | $25/seat |
   | Legal (self-serve) | $27 |
   | E-commerce | $34–44 |
   | Ops | $17 |

   We are a partial substitute: we don't send, store, sync or automate anything. So
   each study applied an explicit 40–80% discount to the value we replace.
   *(sales_marketing.md, eng_product_career_ecom.md, ops_finance_legal.md,
   content_seo_creator.md)*
4. **Consumers pay about $10/mo, less for occasional needs.** RevenueCat's 2026
   medians: all apps $10, Health & Fitness $9.99, Productivity $7.99, Travel $4.99.
   YNAB and Monarch cost $14.99/mo, or $8.33–9.08/mo when billed annually.
   *(content_seo_creator.md, ops_finance_legal.md)*
5. **Cheap plans churn and lose more to fees.**
   - AI products under $50/mo keep only 23% of their revenue a year later (ChartMogul
     2025).
   - Low-priced apps convert trials at 4.4% vs 8.9% for high-priced ones (RevenueCat
     2026).
   - A $4.99 charge nets **$4.51** after Stripe and Stripe Billing fees (9.6% lost).
     A $29.99 charge nets **$28.61** (4.6% lost).
   - So the $4.99 single is the way in and a price anchor. Real revenue has to come
     from packs, All-Access and annual plans. *(bundles.md §5, §8)*
6. **$14.99 is doing three jobs today:** any-5, a category pack and founder
   All-Access. Once the founder seats are visible, nobody has a reason to buy the
   other two. *(bundles.md, implications §3)*

## 2. How the two views fit together *(judgement)*

The bundle study and the category studies seem to disagree. The bundle study says
All-Access should be $15–20; the category studies say the Sales pack alone is worth
$25–39. They are pricing **different buyers against different anchors**:

- An **individual** compares us with their $20 AI subscription. Add-ons at $7–10 and
  bundles at $15–30 feel normal to them.
- A **professional** compares a pack with the $30–120/seat tool it partly replaces.

So the ratio evidence should apply to a **pack**, not to a single agent. A category
pack is like one Adobe app: it covers a whole job function. A single agent is more
like one feature. JetBrains is the closest match to our shape: a flagship product at
$19.90 and everything at $29.90, a 1.5× step. Setapp and Microsoft 365 step up
1.3–2× per rung.

## 3. Recommended price ladder

| Rung | Price | Annual | Reasoning |
|---|---|---|---|
| Single agent | **$4.99/mo** | $49.90/yr | Kept as you set it. It sits at the low end of the $9–30 range suggested for a paid MCP server and just under the ~$6 one-time prompt median. It's an entry product; all of a customer's agents go on one subscription and one charge, so the 30¢ fee isn't paid per agent (already built that way). |
| **Everyday pack** | **$9.99/mo** | $99/yr | For consumer and light-use jobs. Equals the RevenueCat consumer median and the AI add-on range ($7–10). |
| **Pro pack** | **$19.99/mo** | $199/yr | For a whole professional job function. Inside or near the researched range for 7 of the 9 pro packs (table below). Stays under the $20 AI anchor so it reads as an add-on. |
| **All-Access** | **$29.99/mo** | $299/yr | 1.5× a Pro pack, the same step as JetBrains. It matches the agent-platform prices buyers compare against ($29–29.99), and it costs about what the Sales pack alone is worth ($29 research anchor). Anyone who needs two Pro packs should upgrade. |
| Founding Member | **$14.99/mo, locked** | — | First 500 seats. At Adobe's 3× ratio, $14.97 is a market-normal All-Access price, so this is a genuine early-adopter deal and still costs above $4.51 per customer to serve. |
| Any-5 | **Drop it** | — | Every buyer it would attract is better served by a pack or the founder offer. Bring it back as "Pick 5 across packs, $14.99" after founder seats sell out, if the data asks for it. |

Every plan should offer annual billing at two months free (17%). The market's annual
discount runs 17–40%, and annual billing reduces both churn and the fixed 30¢ card fee.

### Pack by pack

"Researched range" is what the category study recommended after its partial-substitute
discount. "À la carte" is the cost of the pack's agents bought singly at $4.99 each.

| Pack (agents) | Tier | Price | Researched range | Replaced value | Key comparables | À la carte |
|---|---|---|---|---|---|---|
| **Sales** (10) | Pro | $19.99 | $25–39 (anchor $29) | ~$101 | Lavender $29, Apollo $59, lemlist $69, Sales Navigator $119.99 | $49.90 |
| **Marketing** (10) | Pro | $19.99 | $19–29 (anchor $24) | ~$104 | Jasper $69, Anyword $49, Unbounce $29 | $49.90 |
| **Founder Finance** (6) | Pro | $19.99 | $29–49 (anchor $39) | ~$118 | Float $130, Visible $69, Baremetrics $75, LivePlan $20 | $29.94 |
| **Engineering** (10, + accessibility-checker) | Pro | $19.99 | $15–19 | ~$41.5 | CodeRabbit/Greptile/Qodo $24–30/dev | $49.90 |
| **SEO & Growth** (8) | Pro | $19.99 | $12–19 (anchor $15) | ~$41 | Ahrefs Starter $29, BrightLocal $29–39, Screaming Frog $23.25 | $39.92 |
| **Product** (6, minus accessibility) | Pro | $19.99 | $15–19 | ~$47 | ChatPRD Pro $15, Dovetail, Maze | $29.94 |
| **Legal & Admin** (5) | Pro | $19.99 | $14.99–24.99 (anchor $19.99) | ~$48 | Rocket Lawyer $34.99, LegalZoom $39–43, Termly $14 | $24.95 |
| **E-commerce** (7), per store | Pro | $19.99 | $15–25 | ~$50/store | Prediko $49, Prisync $99, Judge.me $15 | $34.93 |
| **People / HR** (4) | Pro | $19.99 | $15–19 (or $19–29 with team features) | ~$47/seat | 15Five AI coach $19/manager, Lattice $10/seat | $19.96 |
| **Operations** (9, Meeting Ops free) | Everyday | $9.99 | $12.99–19.99 (anchor $14.99) | ~$32 | Motion, Reclaim, Superhuman, SaneBox $9.49 | $39.92 |
| **Content & Creator** (8 content + 4 creator) | Everyday | $9.99 | Content $9–15, Creator Studio $7–10 | ~$33 + ~$11 | Grammarly Pro $12 (annual), Typefully, Taplio $39+, Descript | $59.88 |
| **Job Search** (4) | Everyday | $9.99/mo or $24.99 per 90 days | $9–15/mo or $19–29 per 90 days | ~$25 | Jobscan $49.95/mo or $89.95/qtr, Teal+ $29/30 days | $19.96 |
| **Personal** (money: 3 + life: 4) | Everyday | $9.99 | Money $6.99–9.99, Life $4.99–6.99 | — | YNAB/Monarch $14.99 ($8.33–9.08 annual), MacroFactor $89.99/yr | $34.93 |

The reasoning behind the non-obvious calls:

- **Sales and Founder Finance are deliberately priced below their evidence.** Sales
  could hold $29 and Founder Finance $39. Holding them at $19.99 keeps the ladder
  clean, and a founder who needs both saves $10 by taking All-Access. The customers
  are worth more on All-Access than on either pack. If data later shows most Sales
  buyers don't want anything else, raise Sales to $24.99–29.
- **Operations is priced below its $14.99 anchor on purpose.** Its comparables are
  cheap ($17 median) and it contains the free lead-magnet agent. At $9.99 it's the
  natural first paid step for Meeting Ops users.
- **Content and Creator are merged.** The content study found creators and writers
  are nearly the same buyer, and the Creator pack alone ($7–10) was too thin to stand
  on its own.
- **Career & HR is split.** Job-seekers are short-term consumers used to 30- or
  90-day passes. HR buyers are businesses on per-seat annual contracts. One pack at
  one price fits neither.
- **Personal combines money and life** (fitness, meals, travel, study). Each alone
  prices at $4.99–7.99, which is barely above the single-agent price. Together, at
  $9.99, it undercuts YNAB/Monarch monthly and matches the RevenueCat median. It
  must say plainly that it keeps no workout, food or spending history. That's a
  structural gap against MacroFactor and YNAB, not a bug.
- **Accessibility-checker moves to Engineering.** It's bought by the developer who
  ships the UI (Stark $16.50, axe DevTools), not the product manager.

## 4. Single agents: under-priced, over-priced, and "should be free"

**Evidence says these are worth more than $4.99.** Option: a "Pro agent" single price
of $9.99 *(decision for you, since you set $4.99)*:

| Agent | Researched value | Why |
|---|---|---|
| grant-writer | $12.99–19.99 | Grant writers charge $1,500–5,000 per proposal; low legal risk |
| cashflow-forecaster | $9.99–14.99 | Float $105–130/mo; a 13-week build takes several CFO hours |
| ad-copy-lab | about $12 | Anyword $49, Jasper $69; exact limits per platform |
| code-reviewer, bug-hunter | $9.99+ | AI code review $24–30/dev; Sentry's AI add-on $40 |
| startup-model, pricing-strategist, investor-update | $7.99–9.99 | LivePlan $20, Visible $69, CFOs $175–500/hr |
| cold-email | about $8 | Lavender $29 |
| contract-reviewer | $7.99–9.99, **no higher** | One lawyer review costs $250–600, but see the liability note below |
| linkedin-ghostwriter, local-seo, programmatic-seo, salary-negotiator, job-description, inventory-planner, ecom-pricing | $6.99–9.99 | Comparables cost $19–69/mo, or $1,250+ for human negotiation coaching |

**Weak as paid singles, because free or built-in alternatives exist:**
- regex-builder (regex101 is free)
- ab-test-analyst (free calculators)
- commit-crafter and test-writer (the customer's own AI does most of it)
- cover-letter (resume tools include it)
- review-responder (Judge.me's $15 plan writes replies)
- email-flows (Klaviyo has AI built in)
- x-thread-builder, meta-writer, schema-markup (Yoast is $9.90, Hypefury $6)
- travel-planner, study-coach, meal-planner (Wanderlog $3.33, Anki free, Eat This Much $5)

**Recommendation:** make **regex-builder and ab-test-analyst free**, alongside Meeting
Ops and Copy Editor. The free alternatives mean they would sell poorly as $4.99
singles. As free agents they pull developers and marketers into installing the link,
the same way Meeting Ops does for operators. Keep the rest inside their packs and
don't advertise them as singles.

## 5. Legal and tax: price as a tool, never as a lawyer

The FTC's final order against DoNotPay's "robot lawyer" (January 2025) imposed $193K
in relief and banned claiming lawyer-equivalence without evidence. So:

- Market contract-reviewer and freelance-tax as a way to **shorten** the lawyer or
  accountant engagement, not replace it.
- Cap contract-reviewer at $9.99 as a single.
- Keep the scope notes and escalation triggers built into the agents (already done).
- Cap liability in the terms at fees paid.

## 6. What this does to revenue *(judgement, arithmetic from the research)*

Average revenue per paying customer rises from about $10–12 under the old ladder to
**about $16–20**. The old figure assumes most buyers take singles, any-5 or a $14.99
pack. The new figure assumes Pro packs at $19.99 and All-Access at $29.99 carry the
mix, with Everyday packs at $9.99. The single-agent share of revenue drops, which is
what the churn and fee evidence argues for. Treat these as planning figures to
replace with real conversion data after 100 customers.

## 7. Check before quoting publicly

Some prices come from third-party write-ups because the vendor page was blocked, was
missing or showed no price. Each is flagged in the research files. Among them:

- **Sales and marketing:** Apollo, PandaDoc, WRITER
- **Content and SEO:** Typefully, TubeBuddy, Moz, BrightLocal
- **Ops and finance:** SaneBox, Monarch, Copilot, Causal
- **Legal:** Spellbook, LegalOn
- **Engineering and product:** Jobscan, Teal, DocSend, Judge.me, Klaviyo, Gorgias
- **AI plans:** ChatGPT Go, Perplexity, Cursor Pro+ and Ultra

Mealime reportedly shuts down on 2026-10-21, which removes a cheap meal-planning
comparable.

## 8. The post-purchase upgrade offer (built)

Everyone who buys something cheaper than All-Access sees an All-Access offer on the
welcome page, before the setup instructions. The same offer goes in their welcome
email. It's valid for 48 hours and takes one click on the card they just used. It
replaces their plan, and billing starts when the trial ends.
(`hundred/server/upsell.py`)

**Offer price** = the higher of (half the All-Access list price) and (what they pay
now + $5). It's capped at what they pay now + $15, never goes above the list price,
and is rounded up to a .99 ending.

| They bought | They pay | Offer: all 100 agents | Extra per month | Off list |
|---|---|---|---|---|
| 1 agent | $4.99 | **$14.99, locked for life** | +$10.00 | 50% |
| 3 agents | $14.97 | $19.99 | +$5.02 | 33% |
| 1 pack or any-5 | $14.99 | $19.99 | +$5.00 | 33% |
| 6 agents | $29.94 | $29.99 | +$0.05 | 0% (same money, 20× the agents) |

Why it's shaped this way *(judgement)*:

- **The +$5 floor** means every acceptance raises revenue.
- **The 50%-off ceiling** makes the value gap absurd. A $4.99 buyer gets 20× the
  agents for 3× the price.
- **The +$15 cap** keeps the step small enough to accept on impulse.

It's also the right *product* move. The research shows cheap single-agent plans churn
hardest, while buyers with more agents in their daily workflow have more reasons to
stay. Measure the acceptance rate by plan and tune the floor and cap from real data.
I haven't cited an industry take-rate because I couldn't verify one.

**The one rule:** the offer can be unreasonably good, but the terms can't be hidden.
The price, "every month", "replaces your current plan", "starts when your trial ends"
and "cancel anytime" all sit next to the button. There's a plain "No thanks" link.
Links are signed and expire, and the server recalculates the price on click, so a
link can't be forged or re-priced. US rules on recurring charges (ROSCA, the FTC's
negative-option rules) require exactly this clear disclosure and express consent.
It's also what keeps chargebacks low.

Next step (not built): a reminder email 24 hours before the offer expires. That
needs a scheduled job.

## 9. Decisions for you

1. Adopt the ladder in §3: $4.99 single, $9.99 Everyday pack, $19.99 Pro pack, $29.99
   All-Access, $14.99 founder, and drop any-5?
2. Add a $9.99 "Pro agent" single price for the agents in §4, or keep every single at
   $4.99?
3. Make regex-builder and ab-test-analyst free?
4. Regroup the packs: split Career & HR, merge Content with Creator, combine money and
   life into Personal, move accessibility-checker to Engineering, split Finance into
   Founder Finance and Personal?

Any of these can be changed in `hundred/plans.py` and the pack definitions. Nothing
has been changed yet.
