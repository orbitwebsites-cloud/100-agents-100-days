# Hundred — Go-To-Market Playbook

Owner: Growth. Status: v1, pre-launch. Companion files:
[LAUNCH_COPY.md](LAUNCH_COPY.md) · [EMAIL_SEQUENCES.md](EMAIL_SEQUENCES.md) · [DIRECTORY_SUBMISSIONS.md](DIRECTORY_SUBMISSIONS.md)

> **Honesty rules for everything we publish.** No invented stats, no fake seat
> counters, no fabricated testimonials, no "#1" claims. Every number in this
> document marked *estimate* or *assumption* is a planning input, not a promise.
> Replace assumptions with our own data after 2 weeks of launch traffic. Anything
> marked **[verify]** was true to our knowledge at writing time but moves fast
> (MCP directories, host-app menus, platform rules, tool pricing). Check it before acting.

Placeholders used across all marketing files:
`{SITE}` storefront URL · `{FREE_MCP_URL}` the keyless URL for the free agents ·
`{FOUNDER_LINK}` founding-member checkout · `{SEATS_LEFT}` live seat count (real, from Stripe) ·
`{DAY}` build-in-public day number · `{REF_LINK}` a customer's referral link.

---

## 0. The strategy on one screen

1. **The wedge is how it installs, not how many agents there are.** "Paste one URL into the AI you already pay for." Nobody learns a new app. Every piece of copy leads with that.
2. **The proof is the tools.** The skeptic's question is "isn't this just prompts?" We answer it with side-by-side demos where the raw AI gets the math, the limits or the dates wrong and the agent's deterministic tool gets them right. Only show failures we actually captured.
3. **Get many customers early by stacking launches into 30 days:** MCP directories (week 1), a Show HN that people can try with no signup because of the free agents (week 2), Product Hunt (week 3), Reddit and niche communities all month, with the build-in-public daily post running under all of it.
4. **Founding Member ($14.99/mo All-Access, locked for life, 500 seats) is the launch offer.** It is our urgency, our early cash and our retention lever in one. The seat counter must be real.
5. **Free agents (Meeting Ops, Copy Editor) are the top of the funnel.** They need no key, so they're what we list everywhere and what we tell HN to try. Email capture happens on the install page, never behind a wall.
6. **Compounding channels start day 1 but pay off after week 8:** programmatic SEO (agent pages + free web versions of our calculators), affiliates at 30% recurring, give-a-month/get-a-month referrals, creator partnerships.
7. **Retention is mostly plumbing:** card-expiry warnings, dunning before cut-off, instant restore, a monthly "new agents shipped" email. Most early churn will be involuntary (failed cards) or non-activation. Both can be fixed.
8. **Unit economics are unusually good** (no LLM cost on our side), so we can afford 30% affiliate commissions and free months. We can't afford paid ads at a $13 blended price, so we don't run them beyond one capped test.

Base-case targets (*estimates*, see §13): **~64 paying by day 30, ~270 by week 12, ~1,000 around month 8.**

---

## 1. Positioning

### 1.1 What we are, in one breath
Hundred is 100 expert agents that plug into the AI you already use (Claude, ChatGPT, Cursor, VS Code, and others) through one URL. Each agent is a top-practitioner playbook plus deterministic tools (calculators, scorers, validators) for the parts AI gets wrong.

### 1.2 The alternatives the buyer is actually comparing us to
| Alternative | What they'd say | Our line |
|---|---|---|
| Just prompting ChatGPT/Claude | "I can ask it myself." | You can, and it will guess the arithmetic, miscount the 300-char limit and skip steps an expert wouldn't. The agent runs the procedure and calls real tools. |
| Prompt libraries / custom GPTs | "There are free GPTs for this." | Those are prompts with no tools, and they only work in one app. Ours run in whichever AI you use and do real computation. |
| Standalone AI SaaS (Jasper-style, sales AI tools) | "I already have a tool for cold email." | That's another tab and another login at $50+/mo. Ours is $4.99 inside the chat you already have open. |
| Building it yourself (devs) | "I could write an MCP server." | You could. We already did it 100 times, keep it tested and push updates to you automatically. |

### 1.3 One-liner options (A/B test the top 3 on the hero)
1. **"100 expert agents. One URL. Works inside the AI you already use."** (clearest; default)
2. **"Stop prompting. Plug in a specialist."** (punchy; good for ads/social)
3. **"Your AI is smart. Now give it the playbook and the calculator."** (explains the mechanism)
4. **"Expert agents for Claude, ChatGPT and Cursor, from $4.99."** (SEO and directory friendly)
5. **"The expert's checklist and the expert's math, inside your chat."** (for non-technical ICPs)

### 1.4 Messaging pillars (every asset hits at least two)
- **Zero switching:** paste one URL, keep your AI, keep your chats.
- **Gets the numbers right:** deterministic tools for math, limits, dates and scoring.
- **Expert procedure:** named frameworks (MEDDPICC, RICE, Van Westendorp, STAR…), exact output templates, anti-patterns.
- **Always improving:** agents update centrally; you get improvements without doing anything.
- **Cheap and granular:** one agent for $4.99, or everything for less than one lunch a month.

### 1.5 Objection bank (use verbatim in replies, FAQ, sales emails)
- *"It's just prompts."* → "Half of it is a prompt: the expert procedure. The other half is code: the A/B significance test, the 13-week cash forecast, the 300-char LinkedIn limit check. Try the same task with and without it. Copy Editor is free, no signup: {FREE_MCP_URL}."
- *"Does my AI support this?"* → Keep a live compatibility table on the site: host, plan required, setup steps, last verified date. **[verify]** each host's plan requirements before publishing. ChatGPT connector/developer-mode availability and Claude custom-connector availability have changed by plan tier more than once.
- *"Is my data safe?"* → "No LLM runs on our side. Your AI sends a tool call, our server computes the result and returns it. [State exactly what's logged and for how long, and link the privacy policy.]" Write this only once the logging policy is final.
- *"What if my card fails?"* → "Access pauses and comes back the moment payment goes through. You don't lose anything."
- *"Why $4.99 when there are free GPTs?"* → "Free GPTs don't run the math and don't follow you to Cursor. Start with the free agents and upgrade if they earn it."

### 1.6 Demo formats that prove the claim (build these before launch)
Record screen captures of real sessions. Never stage a failure.
1. **Limits demo:** ask a raw AI for a 300-char LinkedIn connection note and count the characters on screen, then run LinkedIn Prospector. Its checker reports the exact count.
2. **Stats demo:** A/B test data in a raw AI gives a "significant!" verdict; A/B Test Analyst runs the two-proportion z-test and adds a peeking warning.
3. **Dates demo:** "Follow up in 5 business days" across a holiday/weekend, with Follow-Up Machine's cadence dates.
4. **Money demo:** Freelance Tax Estimator's quarterly estimate or Cash Flow Forecaster's runway, with the math shown. Include the scope note that it isn't tax advice.
5. **Install demo (the most important asset):** a 20-second cut of copying the URL, pasting it into Claude, and the first tool call. Make one per host.

---

## 2. ICPs, ranked by who pays first

**Hard qualifier for every ICP:** they already use an MCP-capable AI (a paid Claude or ChatGPT plan where connectors are enabled, or Cursor/VS Code/Windsurf/Claude Code/Gemini CLI). If they don't, they aren't a customer yet. Don't spend on them.

| Rank | ICP | Why they pay first | Entry agents | Best offer | Where they are |
|---|---|---|---|---|---|
| 1 | **Indie hackers, solo founders, build-in-public followers** | They follow the 100-day story, value "support the builder + get tools," understand founder pricing, and already use Claude/Cursor. They need sales, marketing and finance help all at once. | unit-economics, pricing-strategist, cold-email, launch-planner, investor-update, landing-page-cro | Founding Member | X, Indie Hackers, r/SideProject, r/SaaS, r/startups, PH |
| 2 | **Developers on Cursor / Claude Code / VS Code** | Lowest setup friction: they already know what an MCP URL is. They discover through directories. Skeptical, but they convert when a free agent proves value. | code-reviewer, sql-wizard, regex-builder, commit-crafter, incident-commander, system-design | Engineering Category Pack, then Founder | MCP directories, r/cursor, r/ClaudeAI, r/mcp, HN, dev.to |
| 3 | **Freelancers & small agencies (marketing, content, SEO, 2–20 people)** | They live in Claude/ChatGPT all day, bill hourly, and a $15–30 tool that saves an hour pays back in a day. One owner can buy for the whole team (several subscriptions). | ad-copy-lab, seo-auditor, meta-writer, proposal-builder, content-repurposer, brand-voice, schema-markup | Marketing / SEO / Content Pack, All-Access | LinkedIn, agency Slack groups, r/PPC, r/SEO, cold email |
| 4 | **Individual sales reps, SDRs, founders doing sales** | High willingness to pay and clear ROI (meetings booked). Corporate AI policies can block custom connectors, so target reps on personal plans and founder-sellers first. | cold-email, linkedin-prospector, objection-handler, discovery-call, follow-up-machine | Sales Pack | LinkedIn, RevGenius-type communities, r/sales |
| 5 | **Creators** (YouTube, short-form, newsletters, podcasts) | Repeated daily use, price-sensitive, highly vocal. Every creator customer is also a potential affiliate. | youtube-scripter, short-video-scripter, x-thread-builder, sponsorship-pricer, content-calendar | Creators Pack / Starter Stack | YouTube, TikTok, r/NewTubers, creator newsletters |
| 6 | **E-commerce operators** (Shopify/Etsy/Amazon) | Clear money math (break-even ROAS, reorder points), but lower AI-connector adoption today. | ecom-pricing, product-listing, inventory-planner, email-flows | E-commerce Pack | r/shopify, r/ecommerce, Shopify community |
| 7 | **Job seekers & career switchers** | High intent but short lifetime (they churn when hired) and many are on free AI plans. Take them via SEO and singles; don't chase them. | resume-optimizer, interview-coach, salary-negotiator | Single agent (annual is a hard sell) | SEO, r/resumes |

**Order of attack:** ICP 1 and 2 in weeks 1–4 (launch channels), ICP 3 and 4 from week 3 (communities, cold outreach, LinkedIn), ICP 5 via creator partnerships from week 4, ICPs 6 and 7 via SEO from week 6.

---

## 3. The offer stack

### 3.1 What we sell (facts, don't change)
| Plan | Price | Role in the funnel |
|---|---|---|
| Free agents: Meeting Ops, Copy Editor | $0, no key | Lead magnet, directory listings, HN try-it, SEO |
| Single agent | $4.99/mo · $49.90/yr | Entry for narrow jobs (career, one-off use) |
| Starter Stack (any 5) | $14.99/mo | Price anchor: "5 for the price of 3" |
| Category Pack | $14.99/mo per category | Role-based buyers (sales rep, agency) |
| All-Access | $29.99/mo · $299/yr | The long-term flagship after founder seats are gone |
| **Founding Member All-Access** | **$14.99/mo, locked for life, first 500 seats** | **The launch offer** |
| 7-day free trial | card required | Applies to paid plans |

### 3.2 How to present it (operator notes)
- **During the founder window, Founder dominates Starter Stack and Category Pack.** Same price, strictly more value. That's fine and intentional: we want every early buyer on All-Access-for-life. It gives the highest retention and the most word of mouth. On the pricing page show Founder first. Show Single second, for people who genuinely need one agent. Collapse Starter/Pack under "More options" until seats run out.
- **The seat counter must read from Stripe** (count of active + ever-sold founder subscriptions, per our seat policy). Never hard-code or "round down." If we get caught faking scarcity, the build-in-public brand is dead.
- **Decide and publish the founder policy before launch** (recommendation, not yet a fact): *"Your founder price is locked for as long as your subscription stays active. If you cancel, the price and the seat are gone."* Also decide whether seats freed by cancellation return to the pool. Recommendation: they don't; "500 ever sold" is simpler and more honest. This policy powers the dunning and cancel-flow copy.
- **After 500 seats:** All-Access $29.99 becomes the hero with annual ($299, "2 months free") as default toggle; Starter Stack and Category Pack come back to the front as the "cheaper than All-Access" options.
- **Trial:** 7 days, card required. Card-required trials generally convert at much higher rates than no-card trials but produce fewer trial starts. We use the free agents as the no-card top of funnel to offset that.
- **Refund policy (recommendation):** publish a plain one: "Forgot to cancel your trial? Email us within 7 days of the first charge and we'll refund it." Costs little and removes the #1 fear of card-required trials. It also prevents chargebacks, which cost more than refunds.

### 3.3 Lead magnets beyond the two free agents
| Magnet | How | Cost | Metric |
|---|---|---|---|
| Free agents via `{FREE_MCP_URL}` | Install page shows the URL openly. Optional "email me setup steps + tips" field under it. | $0 | Free-URL installs (unique sessions calling a tool), email opt-in rate on install page |
| Free web calculators (from our deterministic tools) | Expose ~20 tools as simple web forms (A/B significance, LinkedIn 300-char checker, SERP pixel width, reorder point, 1RM, break-even ROAS…). CTA: "Use this inside your AI →" | Dev time only (~1–2 h per tool once the form template exists, *estimate*) | Organic sessions per tool page, tool→trial click-through |
| "The Playbook" PDF per category | Condensed, readable version of 3–4 agent playbooks per category, email-gated | Writing time | Opt-ins, opt-in→trial within 14 days |

---

## 4. Funnel instrumentation (set up before any launch traffic)

We control the MCP server, so we can see real usage per license key. That's unusual for a SaaS and we should use it everywhere.

**Events to log** (server + site + Stripe webhooks):
`site_visit` (with UTM/referrer) · `install_page_view` · `free_url_first_call` (anonymous session) · `email_captured` ·
`trial_started` (Stripe `customer.subscription.created` with trial) · `key_first_call` (first tool call on a license key) ·
`agent_called` (slug, host client if detectable) · `trial_converted` (first paid invoice) ·
`payment_failed` (`invoice.payment_failed`) · `access_cut` · `access_restored` · `canceled` (with reason) · `referral_attributed` · `affiliate_attributed`.

**North-star and guardrails**
| Metric | Definition | Why |
|---|---|---|
| **Activated trial rate** | % of trials with ≥1 tool call on their key within 24 h | The #1 predictor we control; setup friction kills card-required trials |
| **Weekly active keys** | Keys with ≥1 tool call in the last 7 days / paying keys | Leading indicator of churn |
| Trial→paid | first invoice paid / trials started (cohort by week) | Core conversion |
| Visitor→trial | trials / unique visitors | Landing page + offer health |
| Involuntary churn | subs lost to failed payment / total subs | Fixable with dunning |
| Voluntary churn | cancellations / subs at start of month | Product/value health |
| Founder seats sold | from Stripe, live | Scarcity + cash |

**Stack (estimates, [verify] current pricing):** Plausible or PostHog for site analytics ($0–$20/mo at this scale) · Stripe Billing + Customer Portal · an email tool that accepts webhook-triggered events (Loops, Customer.io, Kit, or Resend + our own cron; $0–$50/mo early) · Rewardful/Tolt/FirstPromoter for affiliates (~$30–$100/mo) · a single spreadsheet or Metabase dashboard updated daily.

---

## 5. Channels ranked by speed-to-first-customer × cost

Score each 1–5 (Speed: 5 = customers this week; Cost: 5 = ~free). **Score = Speed × Cost.**

| # | Channel | Speed | Cost | Score | Primary ICP | Role |
|---|---|---|---|---|---|---|
| 1 | Warm network + waitlist founder offer | 5 | 5 | 25 | 1 | First 20–50 customers |
| 2 | MCP directory listings | 4 | 5 | 20 | 2, 1 | Steady, compounding dev discovery |
| 3 | Show HN (try-it-free angle) | 5 | 4 | 20 | 2, 1 | One-day spike + credibility |
| 4 | Reddit value posts | 4 | 5 | 20 | all, per category | Targeted spikes; high ban risk if done wrong |
| 5 | Product Hunt | 4 | 4 | 16 | 1 | Spike + backlinks + directory crawl |
| 6 | Build-in-public daily (X, LinkedIn) | 3 | 5 | 15 | 1, 3, 4 | The engine that feeds every other channel |
| 7 | Free agents as lead magnet | 3 | 5 | 15 | all | Top of funnel for everything |
| 8 | Niche communities (Slack/Discord/forums) | 3 | 5 | 15 | 3, 4, 5 | Category-specific trust |
| 9 | Cold outreach to agencies/teams | 3 | 4 | 12 | 3, 4 | Multi-subscription deals |
| 10 | Creator partnerships | 3 | 3 | 9 | 5, 1 | Borrowed audiences |
| 11 | Affiliate program (30% recurring) | 2 | 4 | 8 | all | Scales after proof exists |
| 12 | Short-form video (TikTok/Shorts/Reels) | 2 | 4 | 8 | 5, 1 | Lottery tickets with long tails |
| 13 | Referral loop (give a month/get a month) | 2 | 3 | 6 | existing customers | Needs a customer base first |
| 14 | Paid ads | 5 | 1 | 5 | — | One capped test only |
| 15 | YouTube long-form | 1 | 4 | 4 | 2, 5 | Slow but evergreen search traffic |
| 16 | Programmatic SEO + free calculators | 1 | 4 | 4 | all | Biggest long-term channel; start week 1, pays from month 3+ |

Low-scoring channels still start early when they compound (SEO, YouTube, affiliates). The score says where the *first* customers come from, not what to ignore.

---

## 6. Channel playbooks

Each has: **How** (exact steps) · **Cost** · **Metric** · **Target** (*estimate*) · **Kill/iterate rule**.

### 6.1 Warm network + waitlist → founding members
**How**
1. Export every contact you have: X followers who engaged in the last 90 days, LinkedIn 1st-degree connections, email list, GitHub stargazers of this repo, people who replied to build-in-public posts.
2. Send personal DMs (not a blast) in batches of 20/day: 2 sentences of context and a direct founder link. Copy: LAUNCH_COPY.md §11. Ask for feedback, not a purchase. Those who want it will buy.
3. Pre-launch (days −7 to 0): "founding member list" page with email capture. On day 1, email the list first and give them 48 h before public announcement ("early access to the 500 seats").
4. Post the founder announcement (LAUNCH_COPY.md §10) pinned on X and LinkedIn.

**Cost:** $0, ~1–2 h/day for a week. **Metric:** DMs sent → replies → founder checkouts. **Target:** 20–50 founder seats in week 1 (*estimate*; depends entirely on existing audience size). **Iterate:** if reply rate < 20% on DMs, the message is too salesy; lead with "can I get your eyes on this" instead.

### 6.2 MCP directory listings (the early-volume channel)
Full checklist, copy and assets: **DIRECTORY_SUBMISSIONS.md**. Summary:

**How**
1. Prepare one asset kit: logo (512×512 and 400×400), 6 screenshots, 160-char description, long description, tags, install snippets per host, privacy policy URL, support email, GitHub repo link.
2. Submit in waves: **Day 1–3:** Official MCP Registry, Smithery, mcp.so, PulseMCP, Glama, mcpservers.org, Cursor Directory, awesome-mcp-servers PR, MCP Market. **Week 2:** Cline marketplace, LobeHub, Claude Code plugin marketplace repo, Gemini CLI extension. **Week 2–4 (longer review):** Anthropic Claude connector directory, OpenAI/ChatGPT apps directory.
3. **List the free agents as their own keyless entry wherever allowed.** Directories and their users strongly prefer servers that work without signup. The paid "Hundred" listing links to the free one and vice versa.
4. Add "one-click install" buttons on our site: Cursor deeplink, VS Code install link, Claude Code `claude mcp add` command, copy-paste JSON for Windsurf/Gemini CLI. **[verify]** each deeplink format against current docs.
5. Every listing URL gets a UTM (`?utm_source=smithery&utm_medium=directory`) so we know which directories convert.
6. Re-check listings monthly: update description when agent count or pricing changes, respond to reviews/comments.

**Critical [verify] items before relying on the big two:**
- **Anthropic's connector directory** reviews submissions against a directory policy. Check whether a license-key-in-URL auth model is accepted or whether OAuth is expected, and what's required (privacy policy, support contact, security review). If OAuth is required, that's a product task. Start it in week 1 because review takes time.
- **OpenAI's app directory** is built around the Apps SDK (MCP-based) with its own review guidelines. Check eligibility for apps that require an external paid subscription, rules on linking to external checkout, and whether upsell text in tool responses is allowed.

**Cost:** $0 (a few directories sell "featured" slots; skip until we know organic conversion). ~1 day for the kit, ~2–4 h for submissions. **Metric:** installs and trials by `utm_source=<directory>`; free-URL first calls by referrer. **Target:** 10–40 trials/month from directories combined by month 2 (*estimate*; directory traffic is uneven and changes with their ranking algorithms). **Iterate:** after 30 days, double down (screenshots, reviews, updates) on the top 3 directories by trials and ignore the rest.

### 6.3 Show HN
**How**
1. Post on a weekday morning US Eastern time (Tuesday–Thursday is common practice). Title format: `Show HN: Hundred – 100 expert agents for any MCP client, as one URL`. Copy: LAUNCH_COPY.md §3.
2. **The link must let people try without signup:** point to a page where `{FREE_MCP_URL}` is copy-pasteable and the two free agents work instantly. HN punishes signup walls.
3. The first comment (by founder) is technical and honest: what's playbook and what's code, why no LLM runs server-side, what's deterministic, what isn't great yet, pricing in one line.
4. Stay in the thread for 6–8 hours. Answer every question, concede valid criticism fast, never argue.
5. **Do not ask anyone to upvote.** HN detects and penalizes voting rings. Sharing the link with "I'd love feedback in the thread" is fine.
6. If it doesn't catch, HN allows reposting a Show HN that got no traction after some time. **[verify]** current guidance in the HN FAQ/Show HN rules. Don't repost within days.

**Cost:** $0, one full day. **Metric:** HN referrer visits, free-URL first calls from HN, trials within 72 h. **Target:** highly variable, from ~0 to several thousand visits (*estimate*). Plan for the downside. **Iterate:** if it flops, the content becomes a blog post ("What we learned shipping 100 MCP agents") for a later submission as a regular link.

### 6.4 Reddit (value-first, rules-compliant)
**Rules we follow:** read each subreddit's rules and self-promo policy before posting ([verify] every time, they change). Keep the classic 90/10 ratio: 9 of 10 of our contributions are pure help. Post from a real, aged account with history. Disclose "I built this" whenever the product is mentioned. Never post the same text to multiple subs on the same day. Never use alt accounts to upvote or comment.

**How**
1. Pick 2 subreddits per category (list below). Spend week 1 commenting helpfully, with no links.
2. Post **value posts**: the actual playbook content (checklist, framework, thresholds) written for that sub, fully useful on its own. Product mention only where rules allow, usually a single line at the end or only in reply to "what tool is this?" Templates: LAUNCH_COPY.md §9.
3. Use weekly self-promo threads where they exist (many subs have "Share your project"/"Feedback Friday"-type threads). **[verify]** thread names per sub.
4. Track each post in a sheet: sub, date, upvotes, comments, UTM clicks, trials.

**Subreddit map per category** ([verify] rules, activity and self-promo policy before posting; sizes and rules change):
| Category | Primary subs | Notes |
|---|---|---|
| AI hosts (all) | r/ClaudeAI, r/ChatGPTPro, r/cursor, r/mcp, r/ChatGPTCoding | Most receptive to MCP how-tos; still value-first |
| Launch / founders | r/SideProject, r/indiehackers, r/SaaS, r/startups, r/Entrepreneur | Several restrict promo to designated threads |
| Sales | r/sales, r/salestechniques, r/coldemail | r/sales is strict on vendors; lead with frameworks |
| Marketing | r/marketing, r/digital_marketing, r/PPC, r/copywriting, r/emailmarketing | r/PPC loves exact character-limit tables |
| Content & Writing | r/copywriting, r/freelanceWriters, r/content_marketing, r/Newsletters | Copy Editor (free) is the hook |
| SEO & Growth | r/SEO, r/TechSEO, r/bigseo, r/localseo | r/bigseo is very strict; comment-only for months |
| Ops & Productivity | r/productivity, r/projectmanagement, r/Notion | Meeting Ops (free) is the hook |
| Finance | r/smallbusiness, r/freelance, r/FPandA, r/Bookkeeping | Tax/money: always include scope notes; never give personal advice |
| Engineering | r/cursor, r/ClaudeAI, r/webdev (Showoff Saturday), r/ExperiencedDevs (comment-only) | Devs want repo links and honest limits |
| Product & Design | r/ProductManagement, r/UXDesign, r/userexperience | RICE/Kano content performs |
| Career & HR | r/resumes, r/jobs, r/careerguidance, r/recruiting, r/humanresources | Empathy first; no hard sell to job seekers |
| Creators | r/NewTubers, r/PartneredYoutube, r/podcasting, r/GetStudying | Timing math (words→runtime) is the hook |
| E-commerce | r/shopify, r/ecommerce, r/EtsySellers, r/FulfillmentByAmazon | Break-even ROAS / reorder point content |
| Legal & Admin | r/freelance, r/smallbusiness, r/nonprofit, r/grantwriting | Always "not legal advice"; never in legal-advice subs |

**Cost:** $0, ~45 min/day. **Metric:** trials per post (UTM), post removal rate (if > 20%, we're reading rules badly). **Target:** 1 value post/day across rotating subs from week 2. Expect most posts to do little and ~1 in 10 to drive meaningful traffic (*assumption*). **Kill rule:** any ban or mod warning, stop posting in that sub and apologize to mods.

### 6.5 Product Hunt
**How**
1. **Two weeks before:** create the product page as "coming soon," collect followers, line up a hunter only if they're genuinely active (self-hunting is fine and common). Prepare the gallery: 5–6 images at the size PH recommends **[verify]** plus a 30–60 s video (the install demo).
2. **Launch day:** go live at 12:01 am Pacific (PH's day starts then). Tuesday–Thursday gets the most traffic and the most competition. Pick based on how strong our supporter base is. Copy: LAUNCH_COPY.md §2.
3. Post the maker comment immediately. Email the list and DM supporters with "we're live, feedback welcome." **Do not ask for upvotes explicitly** (against PH guidelines; [verify] current wording). Ask people to check it out and leave honest feedback.
4. No PH-only discount: pricing is fixed. The founder seat *is* the PH offer, plus the free agents to try with no signup.
5. Reply to every comment within 15 min all day. Post progress on X/LinkedIn every 3–4 hours (build-in-public content).

**Cost:** $0 (optional: $0–$300 for a pro gallery design, *estimate*). **Metric:** PH referrer visits → trials; upvote rank matters less than visits and trials. **Target:** a spike of hundreds to low thousands of visits and ~20–60 trials if top-10 of the day (*estimate*). **Iterate:** PH lets you launch again later with significant updates. The "100 agents done" milestone (day 100) is a natural second launch.

### 6.6 Build-in-public daily content engine ("100 Agents · 100 Days")
The spine of the whole plan. Every day produces one "atom" that feeds all platforms.

**The daily atom (60–90 min total):**
1. **Ship or spotlight agent #{DAY}.** Record a 30–60 s screen capture of it working in a real host, showing the tool call.
2. **Write the post:** hook (the problem), the demo, one surprising detail from the playbook (a threshold, an anti-pattern), the number of the day ("Day 23/100"), link in reply/comment.
3. **Publish:** X (native video + post; link in the first reply) → LinkedIn (native video or carousel, link in first comment) → TikTok/Shorts/Reels (vertical cut of the same video) → one line in the daily changelog on the site.
4. **Weekly (Fridays):** a numbers post, showing MRR, trials, founder seats sold, what worked and what flopped. Real numbers only. Openly sharing revenue is the build-in-public currency. If you won't share exact MRR, share ranges consistently.
5. **Weekly (Sunday):** a 3–5 min YouTube video: "This week's 7 agents" + one deep build lesson. Evergreen search value.

**Formats that tend to work** (rotate): before/after (raw AI vs agent), "I asked 3 AIs to…", teardown of an expert framework, revenue update, failure post, "how the tools work under the hood" (dev audience), customer's real use (with permission).

**Cost:** $0 cash; ~1.5 h/day. Optional $15–$30/mo for a scheduler (Typefully/Buffer, *estimate*, [verify]). **Metric:** profile→site clicks (UTM per platform), follower growth, weekly-post-driven trials. Don't optimize likes. **Target:** 1 post/day/platform for 100 days; X+LinkedIn drive ~20–30% of trials in month 1 (*assumption*). **Iterate:** every Friday, double the format that drove the most clicks that week.

### 6.7 Free agents as lead magnet
**How**
1. **Install page for free agents:** URL visible and copyable with no gate. Per-host tabs (Claude, ChatGPT, Cursor, VS Code, Claude Code, Windsurf, Gemini CLI) with 3-step instructions and a GIF each.
2. **Optional email capture** right below: "Want setup help + 1 tip a week for getting more out of your AI? (We'll also tell you when new free agents ship.)" Nurture: EMAIL_SEQUENCES.md §5.
3. **In-product discovery (product decision; check directory policies first):** a catalog tool on the free server, e.g. `hundred__find_agent`, that the AI calls when a user asks for something a paid agent covers. It returns the matching agent name, a one-line description and trial link. This must be factual and user-triggered (only when the request is out of scope), not ads in every response. **[verify]** Anthropic and OpenAI directory policies on promotional content in tool results before shipping.
4. Rotate a third free agent quarterly (e.g., a high-search-volume one like Resume Optimizer or A/B Test Analyst) as a fresh launch moment. This is a *recommendation*; today's free agents are only Meeting Ops and Copy Editor.

**Cost:** $0 (dev time for install page and optional discovery tool). **Metric:** free-URL weekly active sessions, install page → email opt-in %, free-user → trial % within 30 days. **Target:** email opt-in 10–25% of install-page visitors (*assumption*); free→trial 3–8% within 30 days (*assumption*).

### 6.8 Niche communities (category-specific)
**How**
1. Join 1–2 communities per priority category. Participate for 2 weeks before mentioning anything. Many Slack communities ban vendor promotion outside #promo/#tools channels. **[verify]** each community's rules; names and ownership change often.
2. Offer something useful and specific: "I turned [framework] into a free checklist/calculator. Here's the link, no signup" (link to a free web calculator page, not the pricing page).
3. Offer community-exclusive *access*, not discounts (pricing is fixed): e.g., "first 10 people from this community get a hands-on setup call."

| Category | Communities to evaluate ([verify] activity, rules, and whether paid) |
|---|---|
| Sales | RevGenius, RevOps Co-op, Pavilion (paid), LinkedIn sales groups |
| Marketing / Content | Superpath (content marketing), Online Geniuses, Exit Five (B2B, paid), Demand Curve community |
| SEO | Women in Tech SEO, Traffic Think Tank (paid), SEO communities on X |
| Engineering | MCP community Discord, Cursor forum, Anthropic/Claude developer Discord, dev.to, Hashnode |
| Product & Design | Mind the Product Slack, Lenny's community (paid), UX Slack groups |
| Founders / Finance | Indie Hackers, Microconf community, r/SaaS, local startup Slacks |
| Creators | Creator-economy newsletters' communities, YouTube creator Discords |
| E-commerce | Shopify Community forums, eCommerceFuel (paid), DTC Slack groups |
| Career / HR | r/recruiting, HR-focused LinkedIn groups, recruiter Slack groups |
| Legal / Admin | Freelancers Union, grant professional communities |

**Cost:** $0–$50/mo if we join one paid community for a priority ICP (*estimate*). **Metric:** trials per community (UTM `utm_source=<community>`), setup calls booked. **Target:** 3 communities producing ≥5 trials each in month 2 (*assumption*).

### 6.9 Cold outreach to agencies and small teams
**How**
1. **List building:** 300 agencies (marketing, content, SEO, PPC; 2–20 staff) from Clutch/agency directories/LinkedIn search. Capture the founder's name, a recent piece of their work and the service they sell. Use Lead Qualifier's ICP scorer on our own list (dogfooding makes good content).
2. **Infrastructure:** a separate sending domain (e.g., `tryhundred.[tld]`), SPF/DKIM/DMARC, 2–3 inboxes warmed for 2–3 weeks, ≤30–40 emails/inbox/day (*common practice, not a guarantee*). Tool: Instantly/Smartlead/lemlist ($30–$100/mo, *estimate*, [verify]).
3. **Sequence:** 3 steps (LAUNCH_COPY.md §13), written with our own Cold Email Closer (and say so; it's a proof point). Offer a 15-min screen-share where we set it up in their team's AI, not a demo.
4. **Compliance:** physical address and one-click opt-out in every email (CAN-SPAM); for EU/UK prospects, check the legitimate-interest basis under GDPR/PECR or exclude them. Honor opt-outs immediately.
5. **Deal shape:** they buy several subscriptions (one per person; Founder while seats last). If multiple agencies ask for a team plan/invoice billing, that's a pricing signal to log, not something we invent in the email.

**Cost:** ~$60–$150/mo tooling + domain (*estimate*); ~1 h/day. **Metric:** reply rate, positive reply rate, calls booked, subscriptions per closed agency. **Target:** 300 prospects → 5–10% reply → 10–15 calls → 5–8 agencies closed → 15–40 subscriptions in months 2–3 (*assumption*; cold email results vary widely). **Kill rule:** if positive reply < 1% after 300 sends, change the list or the offer before sending more.

### 6.10 Creator partnerships
**How**
1. **Targets:** YouTubers/newsletters/X accounts teaching Claude, ChatGPT or Cursor workflows (1k–100k audience); category experts (sales trainers, SEO educators, finance-for-freelancers creators).
2. **Offer:** free All-Access for life (costs us almost nothing: no LLM cost) + affiliate link at 30% recurring + a custom demo of the agents that fit their audience. Ask for an honest review, with no script approval beyond factual accuracy.
3. **Disclosure:** creators must disclose the relationship (FTC Endorsement Guides in the US; equivalent rules elsewhere). Put it in the agreement.
4. **Paid placements (later, once conversion is known):** AI newsletters sell sponsorships. Get rate cards and compare to our CAC ceiling (§13.3) before buying. Test only one at a time.
5. **Micro-creator flat fees:** $100–$500 per dedicated video for 5k–50k channels (*estimate*; rates vary a lot). Only after 2–3 free-product partnerships have shown what converts.

**Cost:** $0 for comped accounts; $0–$1,000/mo for paid tests (*estimate*). **Metric:** trials and MRR per creator (affiliate dashboard), cost per paid customer. **Target:** 10 creator conversations/week from week 3; 3–5 active creators by week 8 (*assumption*). **Kill rule:** paid placement with CAC > 3 months of ARPU is not repeated.

### 6.11 Affiliate program (30% recurring)
**How**
1. **Tool:** Rewardful, Tolt, FirstPromoter or PromoteKit. All integrate with Stripe subscriptions ([verify] pricing and features, roughly $30–$100/mo, *estimate*).
2. **Terms (recommended):** 30% recurring on every payment for 12 months per referred customer (or lifetime; lifetime recruits better, 12 months protects margin; see §13). 60-day cookie. Payout monthly via PayPal/Wise with a 30-day hold so trials/refunds settle first. $25 minimum payout. No bidding on our brand name in paid search. No coupon sites, no spam. Self-referrals are void.
3. **Recruit:** (a) every paying customer gets an "earn 30%" prompt in the day-14 email; (b) creators from §6.10; (c) agencies from §6.9 who resell setup services; (d) directory authors who write "best MCP servers" lists. DM template: LAUNCH_COPY.md §12.
4. **Enable:** an affiliate page with demo videos, per-category angles, copy snippets, screenshots and honest positioning (no income claims).

**Cost:** tool fee + 30% of affiliate revenue. **Metric:** active affiliates (≥1 referral/month), affiliate share of new MRR, affiliate-customer churn vs average. **Target:** 25 signed up / 5 active by week 8; affiliates 10–20% of new MRR by month 6 (*assumption*).

### 6.12 Referral loop (give a month / get a month)
**How**
1. Every paying customer gets `{REF_LINK}`. The referred friend gets their first paid month free (after the trial). When the friend's first real payment succeeds, the referrer gets a credit equal to one month of their own plan.
2. **Stripe implementation:** create a 100%-off-once coupon; generate a promotion code per customer (or use the affiliate tool's referral mode). Listen for `invoice.paid` on the referee's first non-zero invoice. Then apply a customer-balance credit to the referrer (`amount = −their monthly price`). Cap at 12 free months per referrer per year to limit abuse.
3. **Placement:** post-activation screen ("Loving it? Give a month, get a month"), day-14 email, the monthly "new agents" email, and in the cancel flow ("refer a friend and your next month is free instead").
4. **Founders:** the referrer's credit applies at their locked $14.99. The referee takes a founder seat only while seats remain.

**Cost:** one month of revenue per successful pair (about $13–$30, net cost lower because it's forgone revenue at ~95% margin). **Metric:** % of paying customers who share ≥1 link, referrals per 100 customers/month, K-factor (invites × conversion). **Target:** 5–10% of new customers from referrals by month 3 (*assumption*).

### 6.13 Short-form video (TikTok, YouTube Shorts, Reels)
**How:** vertical cuts of the daily demo, 20–40 s. The hook lands in the first 2 seconds, shows the failure or the payoff first, and puts the "how" after. Scripts: LAUNCH_COPY.md §8. Post the same video to all three; caption with the problem ("AI can't count to 300"). Link in bio → a mobile landing page with the free URL + founder offer.
**Cost:** $0; ~20 min/day on top of the daily atom (CapCut or similar free editor). **Metric:** profile visits → bio link clicks → trials (UTM per platform). Views are not the metric. **Target:** post daily for 30 days before judging; expect most videos to do little (*assumption*). **Kill rule:** after 30 posts, if bio clicks < 50 total, drop to 3/week and move time to LinkedIn.

### 6.14 YouTube long-form
**How:** weekly 5–10 min: "How to add expert agents to Claude in 60 seconds," "Cursor MCP setup for [task]," "I tested [agent] on real [data]." Titles target search ("Claude custom connector tutorial," "ChatGPT MCP developer mode setup"). Pin install links in the description.
**Cost:** $0; ~3 h/week. **Metric:** search views, description-link clicks, trials. **Target:** evergreen; judge at 12 weeks.

### 6.15 Programmatic SEO + free calculators
**How**
1. **Page types** (built from the registry metadata that already exists: name, tagline, description, triggers, examples):
   - 100 agent pages: `/agents/{slug}`, e.g. "Cold Email Closer: AI agent for cold email in Claude, ChatGPT & Cursor."
   - 12 category pages: `/category/{category}`, e.g. "AI agents for sales."
   - Host × agent pages only where they carry unique setup content: `/agents/{slug}/claude`, `/chatgpt`, `/cursor`.
   - ~20–40 **free web calculator pages** built from our deterministic tools (A/B significance, sample size, LinkedIn character counter, SERP pixel width checker, reorder point/EOQ, break-even ROAS, 1RM, Van Westendorp, LTV/CAC, 13-week cash flow template, business-day calculator…). These are real utilities with real search demand and they rank on usefulness, not word count.
   - "How to [task] with ChatGPT/Claude" guides built from each agent's playbook frameworks.
2. **Quality bar:** each page must have unique, useful content (the real frameworks, thresholds, examples, and a working tool or demo). Google's spam policies target scaled low-value content ([verify] current "scaled content abuse" policy). Run our own programmatic-seo agent's near-duplicate checker across page templates; anything > ~70% similar gets merged or rewritten.
3. **Technical:** JSON-LD (SoftwareApplication, FAQPage, HowTo where valid; use our Schema Markup Builder), internal links agent ↔ category ↔ calculator, sitemap, Google Search Console on day 1.
4. **AI answer visibility:** people increasingly ask their AI "what's the best MCP server for X." Clear, factual agent pages and directory presence help. Don't buy "AI SEO" services.

**Cost:** dev time, ~$0 cash. **Metric:** indexed pages, GSC impressions/clicks per page type, calculator→trial CTR. **Target:** first meaningful organic trials in month 3–4; organic ≥25% of trials by month 12 (*assumption*).

### 6.16 Paid ads (one capped test)
At ~$13–19 blended ARPU and ~6% monthly churn (*assumption*), a paid customer is worth roughly $190–$300 in contribution. Break-even CAC at 3-month payback is ~$36–$54 (§13.3). Cold paid social rarely hits that for a $5–$30 SaaS. **One test only:** $300 on X or Reddit ads to the free-agent install page (not the pricing page), measured on email capture and trial cost. If cost per trial < $15 at ~40% trial→paid, scale slowly; otherwise stop.

---

## 7. The first 100 customers plan (days 1–45)

Base-case target: **100 paying by ~week 6** (*estimate*). Where they come from (*planning split, not a forecast*):

| Source | Customers | How |
|---|---|---|
| Warm network, waitlist, GitHub stargazers | 25 | Founder DMs, 48-h early access (§6.1) |
| Show HN + Product Hunt | 20 | Two launch days, 1 week apart (§6.3, §6.5) |
| MCP directories | 15 | Wave 1 submissions day 1–3 (§6.2) |
| Build-in-public daily posts | 15 | 45 daily posts by week 6 (§6.6) |
| Reddit + communities | 15 | Value posts rotating across categories (§6.4, §6.8) |
| Cold outreach (agencies) | 5 | First 150 sends (§6.9) |
| Free-agent nurture → trial | 5 | Email sequence (EMAIL_SEQUENCES §5) |

**Founder-led conversion tactics for the first 100:**
- Personally email every trial within an hour of signup: "I'm the founder. Reply with what you want to use it for and I'll tell you which agent to try first." Replies are gold for copy and roadmap.
- Offer a 10-minute setup call to any trial with zero tool calls after 24 h. Setup friction is the likeliest killer.
- Ask every paying customer on day 10: "What almost stopped you from buying?" Put answers in the FAQ and hero.
- Ask the first 20 happy users for a one-sentence quote (with name/role, with written permission). Only real quotes go on the site.

## 8. The first 1,000 customers plan (weeks 6–35)

Base case reaches ~1,000 paying around month 8 (*estimate*). The mix shifts from launches to compounding channels:

| Phase | Weeks | Main engines | Key moves |
|---|---|---|---|
| **Sell out founders** | 6–20 | Daily content, directories, Reddit/communities, cold outreach | Public seat countdown in every weekly post; "last 100 seats" email to all free users and trial non-converters |
| **Post-founder flagship** | ~20+ | Affiliates, referrals, SEO calculators, creator partnerships | All-Access $29.99 with annual default toggle; Category Packs pushed on category landing pages |
| **Second launch** | Day 100 | PH relaunch, HN "what I learned," press/newsletters | "100 agents shipped in 100 days": the story's natural climax. Plan it from day 1. |
| **Category depth** | 12+ | Per-category landing pages, niche communities, category creators | Put the most effort into the top 3 categories by paid conversion; ignore vanity categories |

**Milestone gates:** don't start paid creator placements until trial→paid ≥ 35%. Don't expand cold outreach until positive reply ≥ 2%. Don't build more SEO templates until the first 100 agent pages are indexed and at least one page type shows clicks.

---

## 9. Retention & churn

Churn math matters more than acquisition at this price. Going from 8% to 5% monthly churn raises lifetime from ~12.5 to ~20 months.

### 9.1 Activation (days 0–7)
- Target: **≥70% of trials make a tool call within 24 h** (*our target, not a benchmark*).
- Post-checkout page shows the URL, the host picker and the exact steps, plus a "Send me a test prompt" button that copies an example first message for the agent they picked (from each agent's `examples`).
- Trigger emails on behavior (no call in 24 h → setup-help email; first call → "3 more things to try"). EMAIL_SEQUENCES §1.

### 9.2 Involuntary churn (failed payments) — fix first
- **Before it happens:** Stripe card account updater is on by default for many cards ([verify] coverage). Send card-expiring emails 30 and 7 days before expiry (Stripe setting or `customer.source.expiring`-style webhook, [verify] event name for PaymentMethods).
- **When it happens:** Stripe Smart Retries on; custom dunning emails (EMAIL_SEQUENCES §3) with a one-click Customer Portal link to update the card.
- **Grace window (recommendation):** current behavior cuts access automatically on decline. Recommend a 3-day grace period before cutting. Many declines are temporary (insufficient funds before payday, bank fraud checks), and cutting a working tool mid-task generates support load and anger. If we keep instant cut, the immediate dunning email doubles as the access-paused notice (alternate copy provided).
- **Restore:** access returns automatically on `invoice.paid`. Send a short "you're back" email so they trust the system.
- **Metric:** recovered revenue % of failed revenue (*target: recover the majority; track weekly*).

### 9.3 Voluntary churn
- **Monthly "What shipped" email** (1st of month): new agents, improved agents, one customer use case. All-Access and Pack customers get new agents automatically, so say so. This is the single best retention email for us.
- **Usage health score:** keys with no calls for 14 days get a "here's a 2-minute win with [agent in their plan]" email tailored to their plan's agents.
- **Cancel flow** (Stripe Customer Portal supports collecting cancellation reasons; retention offers/coupons in the portal may be available, [verify]): ask why (too expensive / not using / missing feature / setup trouble / other). Route: *too expensive* → suggest downgrading to Single agent(s). *Not using* → offer to switch agents. *Setup trouble* → book a call. **Founders get a clear warning** that cancelling gives up the lifetime price (per the published policy).
- **Annual upgrade at day 45 and day 90** for monthly All-Access and Single customers: "2 months free if you switch to annual." Annual customers churn less by construction.

### 9.4 Win-back
EMAIL_SEQUENCES §4: 7, 30 and 60 days after cancellation. Lead with "what's new since you left" (new agents, improvements), not discounts. Pricing is fixed, so the lever is value and the free month via referral from a friend. Suppress anyone who unsubscribed or complained.

---

## 10. Cash-injection tactics (annual & lifetime)

| Tactic | How | Cost | Metric |
|---|---|---|---|
| **Annual default toggle** after founder seats go | Pricing page defaults to annual for All-Access ($299) and Single ($49.90); show "2 months free" | $0 | % of new subs on annual |
| **"Switch to annual" campaign** | Email monthly All-Access customers at day 45/90; one-click switch via Customer Portal or a Stripe checkout link that prorates | $0 | Upgrades/month, cash collected |
| **Founder seat countdown pushes** | At 250, 400, 450, 490 seats sold: email free users + lapsed trials + social posts with the real number | $0 | Founder checkouts per push |
| **Single-agent annual for seasonal jobs** | Freelance Tax Estimator before quarterly deadlines, Resume Optimizer in hiring seasons: pitch annual | $0 | Annual singles sold |
| **Lifetime deal (NOT in current pricing — decision required)** | If cash is urgent: a capped lifetime All-Access offer (e.g., 100 seats) sold directly, not via marketplaces | Marketplaces like AppSumo take a large revenue share and bring high support load and price-anchoring problems ([verify] current terms) | Only consider if runway < 3 months. It converts future MRR into cash now. |
| **Gift/team bulk (NOT in current pricing — decision required)** | Agencies asking to pay for 5+ seats on one invoice: log demand; if ≥5 requests, design a team plan | — | Requests logged |

---

## 11. 30-day launch calendar

Assumes **Day 1 = a Monday**, public build-in-public already running, founder page and Stripe live, the free URL working. Every day also includes: the daily build-in-public atom (§6.6), replying to every comment/DM, and logging numbers.

| Day | Main action | Supporting actions | Metric to check that evening |
|---|---|---|---|
| −14 to −1 | Build asset kit, install page, demos, dunning + onboarding emails live, analytics, PH "coming soon" page | Warm 2 sending inboxes; start Reddit commenting (no links); write founder policy + FAQ | All events firing in a test purchase + a test failed card |
| 1 (Mon) | **Founder early access:** email waitlist + personal DMs (20) | Submit Official MCP Registry, Smithery, mcp.so | Founder checkouts, DM replies |
| 2 | DMs (20); submit PulseMCP, Glama, mcpservers.org | Post "Day {DAY}: we're open. 500 founder seats" on X + LinkedIn | Seats sold, directory confirmations |
| 3 | **Public founder announcement** (LAUNCH_COPY §10) | Submit Cursor Directory, awesome-mcp-servers PR, MCP Market; start Anthropic + OpenAI directory submissions | Visitor→trial %, activation % |
| 4 | Reddit value post #1 (r/ClaudeAI or r/cursor: MCP setup how-to) | DMs (20); founder emails each new trial personally | Trials from Reddit UTM |
| 5 (Fri) | **Week-1 numbers post** (real MRR, seats, trials) | Affiliate program page live (Rewardful/Tolt set up) | Activation %; fix top setup issue |
| 6 (Sat) | Short video #1–2 (install demo, limits demo) | YouTube long-form #1: "Add expert agents to Claude in 60 seconds" | Bio link clicks |
| 7 (Sun) | Rest + prep Show HN post and first comment | Line up 5 technical friends to read (not upvote) | — |
| 8 (Mon) | Reddit value post #2 (sales: cold-email checklist in r/sales or r/coldemail per rules) | Cold outreach: first 30 agency emails (inboxes warmed) | Reply rate |
| 9 (Tue) | **Show HN** (morning ET) | Stay in thread 6–8 h; X/LinkedIn "we're on HN" post | HN visits, free-URL calls, trials |
| 10 | HN follow-up: fix the top 3 issues raised; post "what HN taught us" | Submit Cline marketplace, LobeHub | Trials from HN over 48 h |
| 11 | Reddit value post #3 (marketing: ad character-limit table in r/PPC) | Creator outreach: 10 DMs (§6.10) | Creator replies |
| 12 (Fri) | **Week-2 numbers post**; first trial cohort converts (trial→paid %) | Personal thank-you to every new paying customer | Trial→paid (cohort 1) |
| 13 | Short videos #3–4 | Claude Code plugin marketplace repo + Gemini CLI extension | — |
| 14 | Prep PH gallery, maker comment, supporter list | Email free-agent users: "we launch on PH Wednesday" | — |
| 15 (Mon) | Reddit value post #4 (SEO: SERP pixel width in r/SEO per rules) | Cold outreach batch 2 (30); affiliate DMs to 10 happy customers | Positive replies |
| 16 (Tue) | Pre-PH: DM supporters "tomorrow" (no upvote asks) | LinkedIn post on the "why tools, not prompts" thesis | — |
| 17 (Wed) | **Product Hunt launch (12:01 am PT)** | Reply to every PH comment in <15 min; X/LinkedIn updates every 3–4 h | PH visits, trials, seats |
| 18 | PH recap post (real numbers) | Submit to BetaList, Uneed, Microlaunch, DevHunt, SaaSHub, AlternativeTo | Trials from PH over 48 h |
| 19 (Fri) | **Week-3 numbers post** | First creator partner onboarded (comped All-Access + affiliate link) | Affiliate signups |
| 20 | Short videos #5–6 (stats demo, dates demo) | YouTube #2: "ChatGPT developer mode + MCP setup" [verify] steps | — |
| 21 | Rest; review channel sheet | Pick the top 2 channels by trials to double | — |
| 22 (Mon) | Reddit value post #5 (finance: unit economics in r/SaaS, with scope note) | Cold outreach batch 3 (40); follow-ups on batches 1–2 | Calls booked |
| 23 | First 10 agent SEO pages live + 5 free calculators | Google Search Console submit sitemap | Pages indexed |
| 24 | Community post #1 (value post in one sales/marketing Slack, per rules) | Referral program live (give a month/get a month) | Referral link shares |
| 25 | LinkedIn carousel: "The 12 AI-agent checklists we built" | 10 more creator DMs | Creator replies |
| 26 (Fri) | **Week-4 numbers post**; seat countdown ("{SEATS_LEFT} left") | Email: founder seat update to all free users + lapsed trials | Founder checkouts from email |
| 27 | Short videos #7–8 | Ask first 20 happy customers for quotes (with permission) | Quotes collected |
| 28 | Rest; write 30-day retrospective | — | — |
| 29 (Mon) | Publish **30-day retrospective** (blog + X thread + LinkedIn): real numbers, what worked, what didn't | Submit retrospective to Indie Hackers | Retro traffic → trials |
| 30 | Plan month 2 from data: kill bottom 3 channels, double top 3 | Update DIRECTORY listings with new agent count; switch-to-annual email ready for day-45 cohort | Month-1 scorecard vs §12 targets |

---

## 12. 12-week roadmap with weekly targets (base case)

*Estimates from the model in §13, not promises.* Assumptions: visitor→trial 2.0%, trial→paid 40% (card-required trial), ~1.5% weekly churn (~6%/mo), ~75% of new buyers pick Founder while seats last. MRR ≈ founders × $14.99 + singles × ~$6.99 (avg ~1.4 agents).

| Week | Focus | Visitors | Trials | New paid | Total paid | Founder seats sold | MRR |
|---|---|---|---|---|---|---|---|
| 1 | Founder early access, directories wave 1 | 1,000 | 20 | 0 | 0 | 0 | $0 |
| 2 | Show HN, Reddit, directories wave 2 | 2,000 | 40 | 8 | 8 | 6 | ~$100 |
| 3 | Product Hunt, launch sites | 5,000 | 100 | 16 | 24 | 18 | ~$310 |
| 4 | Cold outreach, creators, first SEO pages | 3,000 | 60 | 40 | 64 | 48 | ~$825 |
| 5 | Referral live, community posts | 2,500 | 50 | 24 | 87 | 66 | ~$1,125 |
| 6 | Seat countdown #1, affiliates recruiting | 3,000 | 60 | 20 | 105 | 81 | ~$1,365 |
| 7 | Annual-switch email (day-45 cohort), YouTube cadence | 3,300 | 66 | 24 | 128 | 99 | ~$1,660 |
| 8 | 25 SEO pages + 10 calculators | 3,600 | 72 | 26 | 152 | 119 | ~$1,975 |
| 9 | Creator partnerships live (3–5) | 4,000 | 80 | 29 | 179 | 140 | ~$2,320 |
| 10 | Category landing pages for top 3 categories | 4,300 | 86 | 32 | 208 | 164 | ~$2,700 |
| 11 | Agency outreach round 2, first case study | 4,700 | 94 | 34 | 239 | 190 | ~$3,110 |
| 12 | Quarter retro, plan the day-100 relaunch | 5,000 | 100 | 38 | 273 | 218 | ~$3,550 |

**Scenario checkpoints (same model, different inputs):**
| Scenario | Inputs | Week 4 paid / MRR | Week 8 paid / MRR | Week 12 paid / MRR |
|---|---|---|---|---|
| Conservative | 50% of base traffic, 1.5% visitor→trial, 35% trial→paid, 2%/wk churn | 21 / ~$270 | 49 / ~$640 | 88 / ~$1,140 |
| Base | as above | 64 / ~$825 | 152 / ~$1,975 | 273 / ~$3,550 |
| Aggressive | 150% traffic, 2.5% visitor→trial, 50% trial→paid, 1.25%/wk churn | 149 / ~$1,935 | 359 / ~$4,665 | ~650 / ~$8,500 (founder seats sell out ~week 12) |

**Weekly review (every Friday, 30 min):** fill the table with actuals. If two consecutive weeks miss trials by > 30%, the problem is traffic (channels). If trials are on target but paid misses, it's activation/onboarding. If paid is fine but MRR misses, it's plan mix (too many singles). Fix the biggest gap first.

---

## 13. Unit economics & MRR model

### 13.1 Per-plan economics
Payment costs assume US cards at Stripe's standard 2.9% + $0.30 plus ~0.7% Stripe Billing fee (**[verify]** current Stripe pricing; international cards and currency conversion cost more; sales tax/VAT handling is extra). Infra is an *estimate* for a stateless MCP server with no LLM calls.

| Plan | Price | Payment fees (est.) | Net per charge | Net per month | Margin after fees |
|---|---|---|---|---|---|
| Single | $4.99/mo | ~$0.48 (9.6%) | $4.51 | $4.51 | ~90% |
| Single annual | $49.90/yr | ~$2.10 (4.2%) | $47.80 | $3.98 | ~96% |
| Starter Stack | $14.99/mo | ~$0.84 (5.6%) | $14.15 | $14.15 | ~94% |
| Category Pack | $14.99/mo | ~$0.84 (5.6%) | $14.15 | $14.15 | ~94% |
| All-Access | $29.99/mo | ~$1.38 (4.6%) | $28.61 | $28.61 | ~95% |
| All-Access annual | $299/yr | ~$11.06 (3.7%) | $287.94 | $23.99 | ~96% |
| Founding Member | $14.99/mo | ~$0.84 (5.6%) | $14.15 | $14.15 | ~94% |

**Takeaways:**
- The "~95% gross margin" claim holds for $14.99+ plans. **The $4.99 single loses ~10% to the fixed $0.30 fee.** Nudge singles toward annual or toward Starter Stack once they're at 3+ agents ("you're paying $14.97 for 3; get 5 for $14.99").
- Infra (hosting, logs, email) is a fixed cost, not a per-customer one, at our scale: plan ~$50–$200/mo total for the first 1,000 customers (*estimate*). Watch it, but it's not the constraint.
- **Tax:** selling digital services to consumers abroad (notably EU/UK VAT) can create obligations from the first sale. Decide early between Stripe Tax + our own registrations and a merchant-of-record option. **[verify]** with an accountant; this is not tax advice.

### 13.2 Customer value (*estimates*)
| Input | Founder-window | Post-founder |
|---|---|---|
| Blended ARPU (plan mix assumption) | ~$13/mo (75% Founder, 25% singles) | ~$19/mo (All-Access, packs, singles, some annual) |
| Contribution margin after payment fees | ~92% | ~94% |
| Monthly churn (assumption, replace with data) | 6% (base) | 6% (base) |
| Expected lifetime (1/churn) | ~16.7 months | ~16.7 months |
| **Contribution LTV** | **~$200** | **~$300** |
| Affiliate cost if referred (30% × 12 months, simplified) | ~$47 | ~$68 |

### 13.3 CAC ceilings (rules, not targets)
- **Payback ≤ 3 months** while bootstrapped: max CAC ≈ $36 (founder window) / ≈ $54 (post-founder).
- Organic/launch channels have ~$0 cash CAC. The real cost is founder time. Track hours per channel weekly and compare trials per hour.
- Affiliates at 30%/12 months fit easily inside the ceiling because we only pay on collected revenue.

### 13.4 12-month MRR model (*estimates*; month = ~4.3 weeks; months 1–3 come from the weekly model, months 4–12 from a monthly continuation)
| Month | Conservative paid | Conservative MRR | Base paid | Base MRR | Aggressive paid | Aggressive MRR |
|---|---|---|---|---|---|---|
| 1 | 21 | ~$270 | 64 | ~$825 | 149 | ~$1,935 |
| 3 | 88 | ~$1,140 | 273 | ~$3,550 | ~650 | ~$8,500 |
| 6 | 206 | ~$2,700 | 717 | ~$10,300 | 1,520 | ~$25,500 |
| 9 | 320 | ~$4,200 | 1,213 | ~$20,300 | 2,485 | ~$44,300 |
| 12 | 434 | ~$5,600 | 1,786 | ~$31,700 | 3,579 | ~$65,500 |

**Model inputs for months 4–12:**
| | Conservative | Base | Aggressive |
|---|---|---|---|
| Monthly visitors (month 4) and growth | 9,000, +5%/mo | 20,000, +8%/mo | 28,000, +7%/mo |
| Visitor→trial | 1.5% | 2.0% | 2.5% |
| Trial→paid | 35% | 40% | 45% |
| Monthly churn | 8% | 6% | 5% |
| Founder seats sold out | not within 12 months (~460 by month 12) | ~month 6 | ~week 12 |

Notes: the founder cap holds MRR down early (500 × $14.99 ≈ $7.5k MRR ceiling from founders), then ARPU steps up when All-Access at $29.99 becomes the flagship. Annual plans add cash up front beyond what MRR shows. Growth after month 3 depends mostly on SEO, affiliates and referrals compounding. If those channels aren't producing by month 4, expect the conservative line.

---

## 14. Risks and pre-launch fixes

| Risk | Why it matters | Action (owner: founder unless noted) |
|---|---|---|
| **Message mismatch in the repo** | `README.md` still says "Building 24 genuinely-agentic tools" and defines agents as things that "fire on their own and change something in the world," while the product is 100 playbook+tool agents over MCP. HN readers will quote the README against us. | Rewrite the README around the 100-agent MCP product before Show HN. Keep the Meeting Ops origin story as history. |
| **"It's just prompts" pile-on** | The most predictable criticism. | Lead with tool demos. Be upfront that part of it is a written playbook, and say why that's still worth $4.99. Keep Copy Editor free as proof. |
| **Public repo = self-hostable** | If the agents' code/playbooks are public, some devs will run them free. | That's fine for distribution and trust. Sell convenience: hosted, one URL, always updated, works in every host. Decide the license deliberately (open source vs source-available) before launch. |
| **Directory auth requirements** | Big directories may require OAuth rather than key-in-URL. | Check in week 1; plan OAuth work if needed ([verify]). |
| **License key in URL leaks** | Users share screenshots/configs; keys get reused. | Use redacted/demo keys in all marketing assets. Add a "rotate key" button. Rate-limit per key. Monitor keys used from many IPs. |
| **Host plan requirements** | Some ICPs' AI plans may not allow custom connectors. | Live compatibility table with "last verified" dates. Qualify in copy ("works with Claude Pro/Max, ChatGPT plans with developer mode…" [verify]). |
| **Instant access cut on decline** | Creates angry customers over temporary declines. | Recommend a 3-day grace window (§9.2). |
| **Founder seats cannibalize future ARPU** | 500 × $14.99 locked forever. | Accepted trade: cash + loyalty + advocates now. Don't extend the cap. |
| **Platform/community bans** | Reddit/Slack/HN can ban for promotion. | Value-first rules (§6.4), one account, disclose. |
| **Solo founder bandwidth** | This plan is ~4–6 h/day of GTM on top of building. | Daily atom template, batch video on weekends, drop the lowest-scoring channel first when overloaded. |

## 15. Operating cadence

- **Daily (90–120 min):** build-in-public atom, reply to everything, 1 Reddit/community contribution, personal email to new trials, check dashboard (trials, activation, failed payments).
- **Weekly (Fri):** numbers post, fill the §12 table with actuals, pick one experiment to start and one to kill.
- **Monthly (1st):** "What shipped" email, directory listing refresh, affiliate payouts, churn review (read every cancel reason).
- **Day 100:** second launch: "100 agents in 100 days, done." PH relaunch, HN "lessons" post, press pitch to AI newsletters, and the retrospective with real numbers.
