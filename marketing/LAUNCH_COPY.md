# Hundred — Launch Copy

Ready-to-post copy. Strategy and timing live in [GO_TO_MARKET.md](GO_TO_MARKET.md).

**Before posting anything:**
- Swap placeholders: `{SITE}`, `{FREE_MCP_URL}`, `{FOUNDER_LINK}`, `{SEATS_LEFT}` (read it live from Stripe, never estimate), `{DAY}`, `{MRR}`, `{REF_LINK}`, `{FIRST_NAME}`, `{AGENCY}`, `{YOUR_NAME}`.
- Anything in `[brackets]` is a slot you fill with a **real** number, quote or observation. Never publish a bracket with a made-up value.
- Only film "the raw AI got it wrong" demos when you actually reproduced the failure. If the raw AI gets it right on the day, film the extra thing the agent adds (the power check, the exact count, the dates) instead.
- Use a redacted or demo license key in every screenshot and video.
- Links: on X and LinkedIn, put links in the first reply/comment. Both platforms have historically given lower reach to posts with outbound links.

---

## 1. Landing page — hero variants (A/B test)

### Variant A — "One URL" (default control)
- **Headline:** 100 expert agents. One URL. Works inside the AI you already use.
- **Subhead:** Paste one link into Claude, ChatGPT, Cursor or VS Code and your AI gets expert playbooks plus real calculators, scorers and validators for sales, marketing, finance, engineering and more. No new app to learn.
- **Primary CTA:** Start 7-day free trial
- **Secondary CTA:** Try 2 agents free, no signup →
- **Under-CTA line:** Founding members: everything for $14.99/mo, locked for life. {SEATS_LEFT} of 500 seats left.

### Variant B — "Stop prompting"
- **Headline:** Stop prompting. Plug in a specialist.
- **Subhead:** Each Hundred agent is the procedure a top practitioner follows, plus code for the parts AI gets wrong: the math, the character limits, the dates, the scoring. It runs inside the chat you already have open.
- **Primary CTA:** Get the Founding Member seat, $14.99/mo for life
- **Secondary CTA:** See all 100 agents
- **Under-CTA line:** 7-day free trial · Cancel in two clicks · Works with Claude, ChatGPT, Cursor, VS Code, Windsurf, Gemini CLI, Claude Code

### Variant C — "Gets the numbers right"
- **Headline:** Your AI is smart. Now give it the playbook and the calculator.
- **Subhead:** A/B significance, 13-week cash forecasts, 300-character limits, business-day follow-ups, MEDDPICC scores. Hundred's agents compute them with real code instead of letting your AI guess. One URL, 100 experts, from $4.99/mo.
- **Primary CTA:** Start free trial
- **Secondary CTA:** Watch the 20-second setup
- **Under-CTA line:** No LLM runs on our side. Your AI does the talking; our tools do the math.

**Social-proof strip (only once real):** "[N] founding members" · real quotes with name + role + permission · host logos only if their brand guidelines allow it [verify], otherwise plain text names.

---

## 2. Product Hunt

- **Name:** Hundred
- **Tagline (≤60 chars [verify limit]):** `100 expert AI agents inside Claude, ChatGPT & Cursor` (52)
  - Alt: `Plug 100 expert agents into the AI you already use` (50)
- **Description (≤260 chars [verify limit]):**
  > Hundred gives your AI 100 expert agents through one URL. Each is a pro playbook plus real tools (calculators, scorers, validators) for sales, marketing, finance, code and more. Works in Claude, ChatGPT, Cursor & VS Code. 2 agents free.
- **Topics:** Artificial Intelligence, Productivity, Developer Tools, SaaS [verify available topics]
- **Gallery order:** (1) hero: "One URL → 100 experts" (2) 20-s install in Claude (3) side-by-side: raw AI vs agent with tool call visible (4) category grid of all 100 (5) pricing incl. founder seats (6) host compatibility.

### Maker first comment
> Hey Product Hunt, I'm {YOUR_NAME}. I've been building Hundred in public as "100 Agents · 100 Days."
>
> **The problem:** I use Claude and ChatGPT all day, and they're brilliant at language and unreliable at the boring parts: counting characters, doing significance tests, scheduling around weekends, scoring against a rubric. And every "AI tool" wanted me to learn another app.
>
> **What Hundred is:** 100 agents, each built from two things:
> 1. **A playbook**: the procedure a top practitioner follows (named frameworks, thresholds, an exact output template, the mistakes amateurs make).
> 2. **Tools**: deterministic code for the parts LLMs get wrong. Your AI calls them; they return exact answers.
>
> You paste **one URL** into the AI you already use (Claude, ChatGPT, Cursor, VS Code, Windsurf, Gemini CLI, Claude Code) and it can use the agents you've unlocked.
>
> **Try it with no signup:** Meeting Ops and Copy Editor are free forever: {FREE_MCP_URL}
>
> **Pricing:** $4.99/mo per agent, $14.99 for any 5 or a whole category, $29.99 for everything. For launch: **Founding Member, everything for $14.99/mo locked for life, first 500 people** ({SEATS_LEFT} left).
>
> What I'd love from you: tell me which agent you'd want next, and where setup confused you. I'm here all day.

---

## 3. Show HN

**Title (≤80 chars):** `Show HN: Hundred – 100 expert agents for any MCP client, as one URL`

**URL:** the try-it page with `{FREE_MCP_URL}` visible (not the pricing page).

**Text:**
> I've been building 100 agents in 100 days, in public. Each one is delivered over MCP, so you add a single URL to Claude, ChatGPT (developer mode), Cursor, VS Code, Claude Code etc. and your existing AI can use them.
>
> An "agent" here is deliberately unglamorous: an expert playbook (the procedure, thresholds, output template, anti-patterns) plus 3–7 deterministic tools for the parts LLMs are bad at. Examples: a two-proportion z-test with a peeking warning (A/B Test Analyst), a critical-path scheduler (Project Planner), a 13-week cash forecast (Cash Flow Forecaster), SERP pixel-width estimation (Meta Writer), a conventional-commit linter (Commit Crafter).
>
> Design choices that might interest HN:
> - No LLM runs on our side. Tools are stdlib + pydantic, no network or file I/O, and run in under 100 ms. Your model does the reasoning; our server does the arithmetic.
> - Each tool must compute something the model would otherwise get wrong or skip. Thin wrappers that echo input fail our test suite.
> - Agents update centrally, so a fixed playbook or tool reaches everyone immediately.
>
> Two agents (Meeting Ops, Copy Editor) are free with no key, so you can try it without signing up: {FREE_MCP_URL}
>
> Paid is $4.99/mo per agent up to $29.99 for everything. The honest criticism I expect is "half of this is prompts." That's true, and I'd like to hear where you think the playbook half does or doesn't earn its keep compared with just asking the model.
>
> Repo: [link]. Happy to answer anything about the MCP side, host quirks, or the business.

**Prepared answers for likely comments:**
- *"This is prompt engineering."* → "Partly, yes. The tools are the part that isn't. For example [paste a real case where the raw model got a number wrong and the tool didn't]."
- *"Why should I pay when I can self-host from the repo?"* → "You can [state license]. People pay for one URL that works in every client and stays updated."
- *"Key in URL is insecure."* → "Agreed it's not ideal. It's what works across all clients today. Keys are rotatable, rate-limited per key [state what's true]. OAuth is [on the roadmap / shipped]."
- *"What data do you log?"* → [exact, true answer from the privacy policy].

---

## 4. X posts (10)

All under 280 characters. Links go in the first reply.

1. > Day {DAY}/100 of building 100 AI agents in public.
   >
   > The rule: every agent has to beat just prompting ChatGPT.
   >
   > How: an expert's playbook + real code for the parts AI gets wrong (math, limits, dates, scoring).
   >
   > Today's: [agent]. Demo below.

2. > Your AI can write a LinkedIn connection note.
   >
   > It can't reliably count to 300.
   >
   > So one of our agents counts for it. Every time.
   >
   > That's the whole idea behind Hundred: let the model write, let code do the math.

3. > You don't need another AI app.
   >
   > You need your AI to be better at your job.
   >
   > Hundred = 100 expert agents you add to Claude, ChatGPT or Cursor with one URL.
   >
   > 2 are free forever. No signup. Link below.

4. > Founding Member seats are open.
   >
   > All 100 agents, every future agent, $14.99/mo, locked for life.
   >
   > 500 seats. {SEATS_LEFT} left right now (live count from Stripe, not a marketing number).

5. > Week [N] numbers, building in public:
   >
   > MRR: ${MRR}
   > Trials: [N]
   > Founder seats: [N]/500
   > Best channel: [channel]
   > Biggest flop: [thing]
   >
   > What I'm changing next week: [one change]

6. > Things LLMs get confidently wrong that we moved into code:
   >
   > • A/B significance
   > • business days
   > • character limits
   > • critical path
   > • CAC payback
   > • reorder points
   >
   > The model decides what to do. The tool gets the number right.

7. > No LLM runs on our servers.
   >
   > Your AI does the reasoning. Our MCP server does deterministic tool calls in under 100ms.
   >
   > Result: ~95% gross margin, so one agent can cost $4.99/mo instead of $49.

8. > Setting up Hundred in Claude:
   >
   > 1. Settings → Connectors
   > 2. Add custom connector
   > 3. Paste your URL
   >
   > That's it. 20-second video below.
   >
   > (Cursor, ChatGPT, VS Code steps in the reply.)
   *[verify menu names on the day you post]*

9. > Hot take: "AI agents" don't need to be autonomous to be useful.
   >
   > They need to follow the procedure an expert follows and not screw up the arithmetic.
   >
   > Building 100 of those. Day {DAY}.

10. > Free forever, no key, no signup:
    >
    > • Meeting Ops: turns a transcript into notes, decisions and owners
    > • Copy Editor: passive voice, adverbs, clichés, readability
    >
    > One URL into your AI. If they're useful, the other 98 are too.

---

## 5. X threads (2)

### Thread A — Launch

1/ I'm building 100 AI agents in 100 days, in public.
Today they're for sale, and the first 500 people get everything for $14.99/mo, for life.
Here's what they are and why they're different 🧵

2/ The problem: your AI is great with words and shaky with rules.
It miscounts character limits, calls a weak A/B test "significant," schedules follow-ups on Sunday, and skips the steps an expert wouldn't.

3/ Each Hundred agent is two things:
• a playbook: the exact procedure a top practitioner follows
• tools: real code for the math, limits, dates and scoring
Your AI reads the playbook and calls the tools.

4/ You don't install an app. You paste ONE URL into the AI you already use:
Claude, ChatGPT, Cursor, VS Code, Windsurf, Gemini CLI, Claude Code.
Your chats, your model, plus 100 specialists.

5/ 12 categories: sales, marketing, content, SEO, ops, finance, engineering, product, career, creators, e-commerce, legal/admin.
Examples: Cold Email Closer, A/B Test Analyst, Cash Flow Forecaster, Code Reviewer, Resume Optimizer.

6/ Two are free forever, no signup: Meeting Ops and Copy Editor.
Try those first. If they don't earn a spot in your workflow, the rest won't either.

7/ Pricing:
• $4.99/mo per agent
• $14.99 any 5, or a whole category
• $29.99 everything
• Founding Member: everything for $14.99, locked for life. 500 seats.
7-day free trial.

8/ Why so cheap? No LLM runs on our side, so our costs are tiny and we pass that on.
Links in the next post. Tell me which agent you want built next 👇

### Thread B — How it's built (dev audience)

1/ How we built 100 MCP agents without running a single LLM on our servers 🧵

2/ An agent = a Python module with a playbook (≥450 words: standard, intake, procedure, frameworks, output template, anti-patterns) and 3–7 typed tools.
Dropping the file in the right folder registers it everywhere: catalog, storefront, MCP server, billing.

3/ The tools are strict: stdlib + pydantic, no network, no file I/O, no randomness, <100ms.
Each must compute something the model would get wrong or skip. A tool that echoes its input fails our test suite.

4/ Tool names are namespaced `<agent>__<tool>` (≤64 chars) so hosts can route cleanly when many agents are loaded.
The playbook tells the model exactly when to call each one.

5/ Every tool has tests asserting real computed values plus a bad-input test that must raise a clear error.
Library-wide tests enforce metadata quality: taglines, trigger phrasings, examples.

6/ Delivery: one MCP endpoint, license key → entitlements computed from the Stripe subscription.
Card fails → access pauses. Payment succeeds → access is back instantly. No manual support.

7/ Why no LLM server-side: the user already pays for a frontier model. We supply procedure + precision. Margins stay high and prices stay at $4.99.

8/ Try the free agents in your client with no signup (link below). Roast the architecture in the replies, that's how it gets better.

---

## 6. LinkedIn posts (5)

*(First ~210 characters show before "see more"; the hook has to land there.)*

### LI-1 — Launch / thesis
> Your team doesn't need another AI tool. They need the AI they already pay for to be good at their job.
>
> For the last [N] days I've been building 100 "expert agents" in public. Each one packs two things into your existing AI:
>
> → The playbook a top practitioner follows. Not "write a cold email," but the actual procedure: subject line under ~45 characters, one ask, personalization tokens checked, follow-ups on business days only.
>
> → Real tools for the parts AI gets wrong: calculators, scorers, validators. The AI decides what to do; the code gets the numbers right.
>
> They install by pasting one URL into Claude, ChatGPT, Cursor or VS Code. No new app, no new login for your team.
>
> Two agents are free forever (Meeting Ops and Copy Editor). The first 500 founding members get all 100 for $14.99/month, locked for life.
>
> Link in the first comment. I'd genuinely like to know: which part of your job does your AI still get wrong?

### LI-2 — Sales leaders (MEDDPICC)
> Most discovery calls fail the same way: the rep talks too much and qualifies too little.
>
> Here's the scorecard we built into our Discovery Call Coach agent. Steal it even if you never use the tool:
>
> M, Metrics: did they quantify the pain?
> E, Economic buyer: do we know who signs?
> D, Decision criteria: what does "good" look like to them?
> D, Decision process: what are the steps and the dates?
> P, Paper process: legal, procurement, security?
> I, Identify pain: in their words, not ours?
> C, Champion: who sells for us when we're not there?
> C, Competition: including "do nothing"?
>
> The agent reads a call transcript, scores each letter, and measures talk ratio and question count with code instead of guessing.
>
> It runs inside the Claude or ChatGPT your reps already use. Link in comments.

### LI-3 — Build-in-public numbers
> Week [N] of building 100 AI agents in 100 days. Real numbers:
>
> • MRR: ${MRR}
> • Paying customers: [N]
> • Founding member seats: [N] of 500
> • Trial → paid: [N]%
> • Best channel this week: [channel], [why]
> • What flopped: [thing], [what I learned]
>
> The surprise of the week: [one honest observation].
>
> Next week I'm testing [one experiment]. I'll report back either way.

### LI-4 — Agency owners
> If you run a marketing or content agency, you're probably paying for five AI tools your team half-uses.
>
> We took a different approach: expert agents that live inside the Claude or ChatGPT your team already has open.
>
> • Ad Copy Lab checks every variant against the platform's character limits before the client sees it
> • SEO Auditor runs a real on-page audit (title, meta, h1, alt, canonical, links)
> • Proposal Builder does the pricing-table math, tiers, discounts, tax
> • Brand Voice Guardian scores drafts against the client's voice profile
>
> One URL per person. From $14.99/month for a whole category.
>
> I'll personally set it up with your team on a 15-minute call. Comment "setup" or DM me.

### LI-5 — Founder economics
> Why can we charge $4.99/month for an AI agent when most AI tools charge $30–$100?
>
> Because we don't run the AI.
>
> Our customers already pay for Claude or ChatGPT. When they use one of our agents, their AI does the reasoning and calls our tools for the precise parts (math, dates, limits, scoring). Those tools are plain, fast code.
>
> No model bills on our side means ~95% gross margin on most plans, which means we can price for individuals, not just enterprise budgets.
>
> One thing I didn't expect: on the $4.99 plan, card processing's fixed fee eats almost 10%. Pricing lessons come from everywhere.
>
> Building all 100 in public. Follow along.

---

## 7. Install & pricing page microcopy

- **Install page H1:** Add Hundred to your AI in 20 seconds
- **Step 1:** Copy your URL (keep it private; it contains your key). [Copy button]
- **Step 2:** Pick your AI → tabs: Claude · ChatGPT · Cursor · VS Code · Claude Code · Windsurf · Gemini CLI. Each tab shows 3 steps and a GIF **[verify every host's current menu path and plan requirements; show a "last verified" date]**.
- **Step 3:** Try this first message: *(auto-filled from the chosen agent's `examples`)*
- **Stuck?** "Reply to your welcome email and a human (me) will get you set up."
- **Trial reassurance:** "7 days free. We email you 2 days before your trial ends. Cancel in two clicks."
- **Card-failure reassurance (FAQ):** "If a payment fails, access pauses and comes back the moment your card goes through. Nothing is lost."
- **Founder FAQ:** "Is the price really locked for life? Yes, for as long as your subscription stays active. [Final wording per the published founder policy.]"

---

## 8. TikTok / Shorts / Reels scripts (5)

Format: vertical, 20–40 s, captions burned in, hook in the first 2 seconds, payoff before explanation.

### V1 — "Your AI can't count to 300"
- **0–2 s (hook):** On-screen: *"ChatGPT can't count to 300."* VO: "Watch your AI fail a character limit."
- **2–10 s:** Screen: ask the raw AI for a LinkedIn connection note "under 300 characters." Paste into a character counter: **[real count]**. *(Only if reproduced.)*
- **10–22 s:** Same request with LinkedIn Prospector connected. Tool call visible → "[real count]/300 ✓".
- **22–30 s:** VO: "The AI writes. The tool counts. That's 1 of 100 agents you can add with one link."
- **CTA text:** "2 agents free, link in bio."

### V2 — "It said my A/B test won"
- **0–2 s:** On-screen: *"AI said my test won. It didn't."* (Only if reproduced; otherwise: *"AI skipped the one check that matters."*)
- **2–12 s:** Paste the real test numbers into a raw AI → its verdict.
- **12–25 s:** A/B Test Analyst runs the two-proportion z-test → p-value, power, and a warning about peeking early.
- **25–32 s:** VO: "Before you ship a 'winner,' let code do the stats."
- **CTA:** "Link in bio."

### V3 — "100 experts, one link"
- **0–2 s:** Hands copy a URL. On-screen: *"I added 100 experts to Claude with one link."*
- **2–12 s:** Paste into Claude's connector dialog (real UI, redacted key). Cut to the agent list.
- **12–28 s:** Rapid-fire 3 uses, 4 s each: cold email scored, 13-week cash forecast, resume vs job description keyword match.
- **28–35 s:** VO: "Works in ChatGPT, Cursor and VS Code too. Two are free."
- **CTA:** "Free ones, link in bio."

### V4 — "Your follow-up lands on a Saturday"
- **0–2 s:** On-screen: *"Your AI just scheduled your follow-up for Saturday."* (only if reproduced)
- **2–12 s:** Ask the raw AI for a 5-touch follow-up cadence "every 3 business days starting [date]." Circle the weekend/holiday date on screen.
- **12–25 s:** Follow-Up Machine returns exact business-day dates.
- **25–30 s:** VO: "Small thing. Costs deals. Fixed with code."
- **CTA:** "Link in bio."

### V5 — Build in public
- **0–2 s:** On-screen: *"Day {DAY} of building 100 AI agents. Here's my revenue."*
- **2–10 s:** Stripe dashboard with real MRR (blur customer names and emails).
- **10–25 s:** "Today I shipped [agent]. It [does X]. The hardest part was [real detail]."
- **25–35 s:** "[N] founding seats left at $14.99 for life. Follow to see if I make it to 100."
- **CTA:** "Follow for day {DAY+1}."

---

## 9. Reddit value posts (3)

Rules: read the sub's rules first; use its self-promo thread if required; disclose; don't cross-post the same day; stay in the comments. Each post must be useful even if nobody clicks anything.

### R1 — r/coldemail or r/sales (per rules)
**Title:** The pre-send checklist I run on every cold email sequence (steal it)

> I got tired of finding the same mistakes after a sequence had already gone out, so I wrote down every check I do before hitting send. Sharing in case it's useful:
>
> **Subject line**
> - Short: aim for roughly 45 characters or fewer so it isn't cut off on mobile
> - Test a lowercase, plain-text variant; it often looks less like marketing
> - No spam-trigger phrasing ("free!!!", "act now", ALL CAPS)
>
> **Body**
> - One ask per email. Two asks = zero answers
> - Check every personalization token actually filled. A literal `{{first_name}}` or "Hi ," kills trust instantly
> - Readability: short sentences; if it reads like a whitepaper, cut it in half
> - The first line is about them, not you
>
> **Sequence**
> - Follow-ups on business days only; watch holidays in the prospect's country
> - Each follow-up adds something new (a resource, a question, a proof point), never just "bumping this"
> - Plan the breakup email in advance
>
> **Deliverability basics**
> - SPF, DKIM, DMARC set up on the sending domain
> - Warm new inboxes before volume; keep daily sends per inbox modest
> - Plain text beats heavy HTML for cold
>
> What's on your list that I'm missing?
>
> *(Disclosure: I build a tool that automates some of these checks inside ChatGPT/Claude. Happy to share if anyone asks, but the list is the useful part.)*

### R2 — r/SaaS or r/startups (per rules)
**Title:** Unit economics formulas I wish I'd had at $0 MRR, with a worked example from my own pricing

> Writing these down because I kept googling them. All monthly figures.
>
> - **Gross margin** = (revenue − cost to serve) / revenue. *Include payment fees.*
> - **Customer lifetime (months)** ≈ 1 / monthly churn. 5% churn ≈ 20 months; 10% ≈ 10.
> - **LTV** ≈ ARPU × gross margin / monthly churn
> - **CAC payback (months)** = CAC / (ARPU × gross margin)
> - **NRR** = (starting MRR + expansion − contraction − churn) / starting MRR
>
> **Worked example (my actual prices, estimated churn):**
> - Plan: $14.99/mo. Card fees at 2.9% + $0.30 plus a ~0.7% billing fee ≈ $0.84 → ~94% margin
> - Assume 6% monthly churn → ~16.7-month lifetime → LTV ≈ $14.99 × 0.94 × 16.7 ≈ $235
> - If I want payback in 3 months, max CAC ≈ $14.99 × 0.94 × 3 ≈ $42
>
> **The thing that surprised me:** on my $4.99 plan, the fixed $0.30 card fee is ~6% on its own and ~10% with the percentage fees. Low-priced plans leak margin in ways the headline percentage hides. Annual billing fixes most of it.
>
> The churn number is an assumption until I have cohorts; I'll post real ones later.
>
> Any formulas you'd add? I'm especially unsure how people handle trials in payback math.
>
> *(Disclosure: I'm building Hundred, AI agents that do this math inside Claude/ChatGPT. The formulas work fine in a spreadsheet.)*

### R3 — r/PPC or r/marketing (per rules)
**Title:** Ad character limits cheat sheet (and why I stopped trusting AI to hit them)

> AI-written ad copy has a habit of blowing limits by a few characters, and the platform either rejects it or truncates it. Here's the reference I keep. **Check each platform's official spec page before relying on it; these change.**
>
> | Platform | Field | Limit |
> |---|---|---|
> | Google Ads RSA | Headline | 30 chars (up to 15 headlines) |
> | Google Ads RSA | Description | 90 chars (up to 4) |
> | Google Ads RSA | Display path | 15 chars each (2 fields) |
> | Meta | Primary text | [current recommended length from Meta's spec] |
> | Meta | Headline | [current recommended length] |
> | LinkedIn Sponsored Content | Intro text | [current recommended / max] |
> | LinkedIn Sponsored Content | Headline | [current recommended / max] |
> | X ads | Post text | 280 |
>
> *(Fill the bracketed rows from the official spec pages on the day you post; don't guess.)*
>
> **Workflow that fixed it for me:** have the AI generate 3× the variants you need, then *count with code* (a spreadsheet `LEN()` works) and drop anything over. Don't ask the model to self-check. It'll tell you 31 characters is 29.
>
> What fields do you find get truncated most?
>
> *(Disclosure: I built an agent that does the counting inside ChatGPT/Claude. The LEN() trick works just as well.)*

---

## 10. Founding-member announcement

### Social (X / LinkedIn)
> Founding Member seats are open.
>
> For the first 500 people:
> → All 100 Hundred agents
> → Every agent we ship after that
> → $14.99/month, locked for life (All-Access is $29.99)
> → A founder badge and a vote on what we build next
>
> 7-day free trial. {SEATS_LEFT} of 500 left, counted live from Stripe.
>
> When they're gone, they're gone. I won't reopen them.
>
> Link in the first comment/reply.

### Email to waitlist
**Subject:** Your founding seat is open (48 hours before everyone else)
**Preview:** All 100 agents, $14.99/mo, locked for life. 500 seats.

> Hi {FIRST_NAME},
>
> You asked to hear first, so here it is: Founding Member seats for Hundred are open to this list for 48 hours before I announce publicly.
>
> **What you get:** every agent (all 100, plus every future one) inside Claude, ChatGPT, Cursor, VS Code and more, through one URL. **$14.99/month, locked for as long as you're a member.** After the 500 seats, All-Access is $29.99.
>
> 7-day free trial, cancel in two clicks.
>
> → Claim a seat: {FOUNDER_LINK}
>
> Not sure yet? The two free agents need no signup: {FREE_MCP_URL}
>
> Reply with the job you'd use it for first and I'll point you to the right agent.
>
> {YOUR_NAME}
> Building 100 agents in 100 days

---

## 11. Warm-network DM (founder early access)

> Hey {FIRST_NAME}, quick one. I've been building 100 AI agents that plug into Claude/ChatGPT with one link (you might have seen the daily posts). Founding seats open today: everything for $14.99/mo locked for life, 500 seats.
>
> Not asking you to buy. I'd love 5 minutes of your eyes on it, especially [agent relevant to them], since you [their job]. Want the link?

---

## 12. Affiliate recruiting DMs

### To a creator
> Hi {FIRST_NAME}, I've watched your [specific video/post] on [Claude/Cursor/ChatGPT workflows]. [Genuine one-line reaction.]
>
> I build Hundred: 100 expert agents people add to their AI with one URL (playbook + real calculators; no LLM on our side). I think [2 agents relevant to their audience] fit your audience.
>
> Offer: free All-Access for life, no strings. If you ever want to cover it, the affiliate link pays 30% recurring [for 12 months / for life, per final terms]. Honest reviews only, including what's weak. Want access?

### To a happy customer (after ≥10 days of real usage)
> Hey {FIRST_NAME}, I noticed you've been using [agent] a lot. Thank you, genuinely.
>
> Two quick things: (1) if you know someone who'd like it, your link gives them a free month and gives you one too: {REF_LINK}. (2) If you'd rather earn cash, our affiliate program pays 30% recurring: [affiliate signup link]. Either way, what's one thing I should improve?

---

## 13. Cold email to agencies — 3-step sequence

Send from the warmed secondary domain. Plain text. Physical address + opt-out line in the footer. Written and checked with our own Cold Email Closer. Say so if asked; it's a proof point.

### Step 1 — Day 1
**Subject:** {AGENCY}'s team + Claude/ChatGPT
> Hi {FIRST_NAME},
>
> Saw [specific recent work: client campaign / blog post / case study]. [One genuine sentence about it.]
>
> Quick question: is your team already using Claude or ChatGPT for [ad copy / SEO audits / proposals]?
>
> I built Hundred, expert agents that plug into the AI your team already uses with one link. For agencies the useful ones are Ad Copy Lab (checks every variant against platform character limits), SEO Auditor (real on-page audit) and Proposal Builder (pricing-table math).
>
> Worth a 15-minute call where I set it up live with one of your people?
>
> {YOUR_NAME}
>
> *[Company address] · Not relevant? Reply "no" and I won't email again.*

### Step 2 — Day 4 (business days)
**Subject:** Re: {AGENCY}'s team + Claude/ChatGPT
> Hi {FIRST_NAME}, one concrete example instead of a pitch:
>
> [One real before/after: e.g., "We ran 30 AI-written Google RSA headlines through Ad Copy Lab; [N] were over 30 characters." Only a real result you measured.]
>
> Two agents are free if you want to poke at it without talking to me: {FREE_MCP_URL}
>
> {YOUR_NAME}

### Step 3 — Day 9 (business days)
**Subject:** Close the loop?
> Hi {FIRST_NAME}, I'll stop here. If AI tooling for the team comes up later, the offer stands: 15 minutes, I set it up with whoever does the most [copy / SEO / proposals] and you judge it on real client work.
>
> Founding seats (everything for $14.99/mo per person, locked for life) are still open while they last: {SEATS_LEFT} of 500 left.
>
> {YOUR_NAME}
