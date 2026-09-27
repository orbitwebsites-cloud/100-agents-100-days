# Hundred — Email Sequences

Strategy context: [GO_TO_MARKET.md](GO_TO_MARKET.md) §4 (events) and §9 (retention).

## 0. Ground rules and plumbing

**Sender:** `{YOUR_NAME} <you@{SITE}>`, a real person who reads replies. Every email invites a reply.
**Format:** plain text or near-plain HTML, one primary CTA, under ~150 words unless noted. Mobile-first.
**Placeholders:** `{FIRST_NAME}` (fallback: "there"), `{PLAN_NAME}`, `{AGENT_NAME}` (the first agent they picked, or the most-called one), `{AGENT_EXAMPLE}` (first entry of that agent's `examples`), `{MCP_URL_HINT}` ("the URL on your install page"; **never put the full keyed URL in email**), `{INSTALL_LINK}`, `{PORTAL_LINK}` (Stripe Customer Portal session link), `{TRIAL_END_DATE}`, `{PRICE}`, `{SEATS_LEFT}`, `{REF_LINK}`, `{NEW_AGENTS}`, `{CALL_LINK}` (booking link).

**Triggers (from our events; see GTM §4):**
| Event | Source |
|---|---|
| `trial_started` | Stripe `customer.subscription.created` with `status=trialing` |
| `key_first_call` / `agent_called` | our MCP server logs per license key |
| `trial_will_end` | Stripe `customer.subscription.trial_will_end` (fires ~3 days before trial end [verify]); we also schedule our own day-5 send |
| `trial_converted` | first `invoice.paid` with amount > 0 |
| `payment_failed` | `invoice.payment_failed` |
| `access_cut` / `access_restored` | our entitlement service |
| `card_expiring` | Stripe expiring-card notifications / scheduled check on the PaymentMethod's exp month [verify best event] |
| `canceled` | `customer.subscription.deleted` (+ cancellation reason from Customer Portal) |
| `email_captured` (free) | install page opt-in |

**Classification:** trial reminders, dunning, access and receipt emails are **transactional** (always sent). Onboarding tips, nurture and win-back are **marketing**: include an unsubscribe link and a physical address, honor opt-outs immediately, and send marketing email only to people who opted in where the law requires it (e.g., EU/UK). This isn't legal advice; check with counsel for your jurisdictions.

**Suppression:** stop onboarding/conversion emails the moment someone converts or cancels; stop win-back on unsubscribe, complaint, or re-subscribe; never send more than one marketing email per day per person.

**Policy decisions these emails depend on (decide before launch):**
1. Does a founder **trial** reserve a seat? Recommendation: yes. The seat counts at checkout, and is released if the trial is cancelled before the first charge.
2. Is the founder price kept through a failed-payment period? Recommendation: yes while the subscription is recoverable (past_due); lost only if it's cancelled.
3. **Grace window before access is cut.** Current behavior: access is cut on decline. Recommendation: 3 days. Copy for both options is below.

---

## 1. Trial onboarding (days 0, 1, 3, 5, 6)

Day 0 = trial start. First charge happens on day 7.

### 1.0 — Day 0, immediately: Welcome + setup
**Subject:** You're in. Here's the 20-second setup
**Preview:** One URL, pasted once, and your AI has {PLAN_NAME}.
> Hi {FIRST_NAME},
>
> Welcome to Hundred. Your trial runs until **{TRIAL_END_DATE}**.
>
> **Setup (20 seconds):**
> 1. Open your install page: {INSTALL_LINK}
> 2. Copy your personal URL (keep it private; it contains your key)
> 3. Paste it into your AI. The page has steps for Claude, ChatGPT, Cursor, VS Code, Claude Code, Windsurf and Gemini CLI.
>
> **Then try this exact message:**
> "{AGENT_EXAMPLE}"
>
> If anything's confusing, just reply. I'm the founder and I read every one. Tell me what you want to use Hundred for and I'll point you to the best agent to start with.
>
> {YOUR_NAME}

**CTA:** Open install page · **Metric:** % with `key_first_call` within 24 h (target ≥70%, our internal goal)

### 1.1a — Day 1: NOT activated (no tool call yet)
**Subject:** Stuck on setup? (2-minute fix)
**Preview:** The 3 things that usually go wrong, and a human if none fit.
> Hi {FIRST_NAME},
>
> I noticed Hundred hasn't been called from your AI yet. Usually it's one of these:
>
> 1. **Plan doesn't allow custom connectors.** Some AI plans don't. The install page lists what works [verify table is current].
> 2. **URL pasted without the key part.** Copy it again with the button on {INSTALL_LINK}.
> 3. **The AI doesn't know to use it.** Name the agent in your first message: "Use {AGENT_NAME} to…"
>
> Still stuck? Grab 10 minutes and I'll set it up with you: {CALL_LINK}
>
> {YOUR_NAME}

**Metric:** activation within 24 h of this email; calls booked.

### 1.1b — Day 1: Activated
**Subject:** Nice. {AGENT_NAME} is live. 3 things to try next
> Hi {FIRST_NAME},
>
> Your AI just used {AGENT_NAME}. Here are three requests that get the most out of it:
>
> 1. [example 2 from the agent's `examples`]
> 2. [example 3]
> 3. "What would a top [role] check that I haven't?" (Every agent has an anti-patterns list; ask for it.)
>
> Tip: your plan also includes [2 related agents in their plan]. Try "{related agent example}".
>
> {YOUR_NAME}

**Metric:** distinct agents used by day 3; days-active in week 1.

### 1.2 — Day 3: Depth (both branches, content adapts)
**Subject:** The part of Hundred your AI can't fake
**Preview:** Why the answers have exact numbers.
> Hi {FIRST_NAME},
>
> Quick peek under the hood, because it changes how you'll use it.
>
> Every agent has two halves: a **playbook** (the procedure an expert follows) and **tools**: real code that does the math, counts characters, schedules business days and scores against rubrics. Your AI decides *what* to do; the tools make sure the numbers are *right*.
>
> So lean on it for the precise stuff:
> - [plan-specific example 1, e.g. "Is this A/B result significant? 480/10,000 vs 540/10,000"]
> - [plan-specific example 2]
>
> What's one task you do every week that you'd hand to an expert if you could? Reply. That's how we pick what to build next.
>
> {YOUR_NAME}

**Metric:** replies (qualitative), calls per active key days 3–5.

### 1.3 — Day 5: Trial ends in 2 days (transactional, always send)
**Subject:** Your trial ends {TRIAL_END_DATE}
**Preview:** No surprises: here's what happens next.
> Hi {FIRST_NAME},
>
> Heads-up so nothing surprises you: your Hundred trial ends on **{TRIAL_END_DATE}**, and your card will be charged **{PRICE}** for {PLAN_NAME}.
>
> - **Keep it:** do nothing.
> - **Change plan** (fewer agents, or everything): {PORTAL_LINK}
> - **Cancel:** two clicks at {PORTAL_LINK}. No email to me required.
>
> [If activated:] So far you've used [N] agents across [N] days. [If founder plan:] Your founder price of $14.99/mo is locked for as long as you stay.
>
> {YOUR_NAME}

**Metric:** cancellations before charge (healthy ones), support tickets about surprise charges (target: zero).

### 1.4 — Day 6: Tomorrow (+ best plan for them)
**Subject:** Tomorrow: your trial becomes {PLAN_NAME}
**Preview:** One thing to check before it does.
> Hi {FIRST_NAME},
>
> Your trial converts tomorrow. One check: **are you on the right plan?**
>
> [Branch A: Single/Starter customer who called ≥3 agents or asked for agents outside their plan]
> You've reached for agents outside your plan [N] times. Founding Member gets you all 100 for $14.99/mo, locked for life. {SEATS_LEFT} of 500 seats left. Switch: {PORTAL_LINK}
>
> [Branch B: Founder/All-Access]
> You're set: every agent, every future one. Nothing to do.
>
> [Branch C: not activated]
> You haven't had a chance to use it yet. Rather than pay for something you haven't tried, cancel here ({PORTAL_LINK}), or reply and I'll get you set up today.
>
> {YOUR_NAME}

**Metric:** trial→paid by branch, plan upgrades before first charge. *(Branch C costs some conversions and saves chargebacks and bad word of mouth. Keep it.)*

---

## 2. Trial-to-paid conversion (behavior-triggered, runs alongside §1)

| Trigger | Email | Goal |
|---|---|---|
| 48 h after trial start, still 0 calls | **"Want me to set it up for you?"** Personal, 3 lines, booking link {CALL_LINK}. Sent after 1.1a only if still inactive. | Activation |
| A single-agent trial calls ≥10 times in 3 days | **"You're a power user already"**: show what else is in their category; suggest Category Pack or Founder. | Plan upgrade |
| Asked their AI for something a different agent covers (if the discovery tool logs it) | **"There's an agent for that"**: name it, one example, link to add it. | Expansion |
| `trial_converted` | **2.1 Welcome to paid** (below) | Confidence, referral seed |
| Trial canceled before charge | **2.2 Exit question** (below) | Learning |

### 2.1 — Welcome to paid
**Subject:** You're officially in. Thank you
> Hi {FIRST_NAME},
>
> Your first payment went through. Thank you; it genuinely keeps this project going.
>
> Three things worth knowing:
> 1. **Agents improve automatically.** When we upgrade a playbook or tool, you get it the next time your AI calls it. Nothing to reinstall.
> 2. **New agents ship regularly.** You'll get a short "What shipped" email once a month.
> 3. **Give a month, get a month:** {REF_LINK}. Your friend's first paid month is free, and so is your next one when they subscribe.
>
> {YOUR_NAME}

### 2.2 — Exit question (trial canceled)
**Subject:** One question (and no hard feelings)
> Hi {FIRST_NAME},
>
> You cancelled your trial, no problem. Could you hit reply with one word?
>
> **Setup** · **Price** · **Didn't need it** · **Missing an agent** · **Other**
>
> Every answer gets read and it directly changes what we build. The two free agents (Meeting Ops, Copy Editor) keep working with no key if you want them: {FREE_MCP_URL}
>
> {YOUR_NAME}

**Metric:** reply rate; tag reasons weekly.

### 2.3 — Day 14 of paid: referral + affiliate
**Subject:** Know someone who'd use {AGENT_NAME}?
> Short one: if a friend or teammate would get value from Hundred, send them {REF_LINK}. Their first month is free and your next month is too. Write about AI tools? Our affiliate program pays 30% recurring: [affiliate link].

### 2.4 — Day 45 of paid (monthly All-Access or Single only): annual switch
**Subject:** 2 months free if you switch to annual
> You've used Hundred for about six weeks. If it's staying in your workflow, annual billing gives you 2 months free: $299/yr for All-Access (vs $359.88 monthly) or $49.90/yr per agent (vs $59.88). Switch in the portal: {PORTAL_LINK}. If you're not sure yet, ignore this. Monthly is fine.

*(Founders are on a locked monthly price; don't send them this one.)*

---

## 3. Dunning (payment failed)

Pre-conditions: Stripe Smart Retries on; Customer Portal allows card updates; `{PORTAL_LINK}` is a fresh portal session link (or a link to a page that creates one after login).

### 3.P — Before it happens: card expiring (30 days and 7 days before)
**Subject:** Your card for Hundred expires soon
> Hi {FIRST_NAME}, the card ending in [last4] expires at the end of [month]. To keep {PLAN_NAME} running without a hiccup, update it here (30 seconds): {PORTAL_LINK}. [Founder:] This keeps your $14.99 founder price safe.

**Metric:** % of expiring cards updated before expiry.

### 3.0 — Immediate: payment failed
**Subject:** Your Hundred payment didn't go through
**Preview:** Usually a quick fix. Here's the link.

*Version for a 3-day grace window (recommended):*
> Hi {FIRST_NAME},
>
> Your payment of {PRICE} for {PLAN_NAME} didn't go through. Banks decline for all kinds of harmless reasons (a fraud check, a new card, a limit).
>
> **Your agents keep working for now.** Update your card here and you're done: {PORTAL_LINK}
>
> We'll retry automatically too. If it still fails by [date = +3 days], access will pause until payment succeeds, and it resumes the moment it does.
>
> {YOUR_NAME}

*Version for the current behavior (access cut immediately on decline):*
> Hi {FIRST_NAME},
>
> Your payment of {PRICE} for {PLAN_NAME} didn't go through, so your agents are **paused** for now.
>
> Nothing is lost. Update your card here and access comes back **the moment the payment succeeds**: {PORTAL_LINK}
>
> Banks decline for harmless reasons all the time (fraud checks, new cards, limits). If you think it's a mistake, a quick call to your bank usually fixes it.
>
> {YOUR_NAME}

### 3.1 — +1 day
**Subject:** Quick reminder: update your card for Hundred
> Hi {FIRST_NAME}, just a nudge: your last payment for Hundred still hasn't gone through. It takes 30 seconds to fix: {PORTAL_LINK}
>
> [Founder:] Your founder price ($14.99/mo for life) is still reserved for you. It's only lost if the subscription ends.
>
> Anything wrong on our side? Reply and I'll sort it.

### 3.2 — +3 days
**Subject:** [Action needed] Hundred access pauses tomorrow
*(Grace-window version; with instant cut, subject becomes "Your Hundred agents are still paused.")*
> Hi {FIRST_NAME},
>
> We've tried a few times and the payment for {PLAN_NAME} still isn't going through. **If it isn't resolved, your agents pause tomorrow.**
>
> Update your card: {PORTAL_LINK}
>
> If you'd rather cancel or switch to a cheaper plan, that's fine too. Same link, no hard feelings.

### 3.3 — Access-cut notice (sent at the moment access pauses; grace-window version only)
**Subject:** Your Hundred agents are paused
> Hi {FIRST_NAME},
>
> Because the payment didn't go through, your agents are paused. Your AI will get a "subscription inactive" message if it tries to call them.
>
> **Nothing is deleted.** Update your card and everything resumes the moment the payment succeeds: {PORTAL_LINK}
>
> [Founder:] Your founder price is held until [date when Stripe will cancel the subscription]. After that it's released.

### 3.4 — Restored (sent on `invoice.paid` after a failure)
**Subject:** You're back. Everything's working again
> Hi {FIRST_NAME}, payment received. Your agents are active again right now, with nothing to reconnect. [Founder:] Your $14.99 founder price is intact. Thanks for sorting it!

**Dunning metrics (weekly):** recovery rate (recovered $ / failed $), median time-to-recover, % recovered by retry vs by card update, support tickets about access loss.

**Final step (Stripe-driven):** when retries are exhausted and the subscription is cancelled, send a plain final notice ("your subscription has ended; you can restart anytime at {SITE}; [founder:] the founder price has been released") and enter them into §4 win-back at day 7.

---

## 4. Win-back (days 7, 30, 60 after cancellation)

Lead with what's new, not discounts (pricing is fixed). Personalize by their cancellation reason where we have it. Suppress anyone who unsubscribed, complained or already came back.

### 4.1 — Day 7
**Subject:** Did we miss something?
> Hi {FIRST_NAME},
>
> You left Hundred a week ago. [If reason known:] You mentioned **[reason]**. [Response by reason:]
> - *Setup:* I'd love to fix that personally. 10 minutes: {CALL_LINK}
> - *Price:* single agents start at $4.99/mo; you may only need one or two.
> - *Missing agent:* here's what we've shipped since: {NEW_AGENTS}
> - *Didn't need it:* totally fair. The free agents still work: {FREE_MCP_URL}
>
> Either way, thanks for trying it.
>
> {YOUR_NAME}

### 4.2 — Day 30
**Subject:** {N} new agents since you left
> Hi {FIRST_NAME},
>
> Quick update since you cancelled:
> - New: {NEW_AGENTS} (one line each)
> - Improved: [the agent they used most], [what changed, concretely]
>
> Your old URL works again the moment you restart: {SITE}/restart
>
> If a friend who's a customer sends you their referral link, your first month is free.

### 4.3 — Day 60 (last one)
**Subject:** Last note from me
> Hi {FIRST_NAME}, this is the last win-back email you'll get. If Hundred ever fits again, restarting takes a minute and your settings come back: {SITE}/restart. [If founder seats remain and they weren't a founder:] {SEATS_LEFT} founding seats are still open at $14.99/mo for life. [If they were a founder:] Founder pricing isn't available again, but All-Access annual works out to about $24.92/mo.
>
> Thanks again for giving it a shot. {YOUR_NAME}

**Metric:** reactivations per 100 churned by day 90; reply reasons.

---

## 5. Free-agent user nurture → paid

For people who opted in on the free install page (`email_captured`). They use Meeting Ops and/or Copy Editor with no key. Goal: one paid agent that fits their job, then Founder/All-Access.

| Day | Subject | Content | CTA |
|---|---|---|---|
| F0 | Your free agents: setup in 20 seconds | The keyless URL, per-host steps, one example message for each free agent. "Reply with your job title and I'll tell you which agent would save you the most time." | Install page |
| F2 | The Copy Editor trick most people miss | Ask for a *readability diff* between two drafts. Show the before/after numbers. Also Meeting Ops: paste a transcript, get decisions + owners. | Try it |
| F5 | What the other 98 do (for your job) | 3 agents picked by their reply or segment (default: Cold Email Closer, A/B Test Analyst, Cash Flow Forecaster), one line + one example each. | See the catalog |
| F9 | How it gets numbers right | The playbook + tools explanation with one real demo GIF. "Free agents use the same engine." | Start 7-day trial |
| F14 | Founding seats: {SEATS_LEFT} left | Plain founder offer: everything for $14.99/mo for life, trial, cancel anytime. Honest line: "If the free ones are all you need, keep using them. They're free forever." | Claim a seat |
| F21 | Build-in-public note | Latest real numbers + what shipped + ask for a reply on what to build. Then move them to the monthly "What shipped" list. | Reply / follow |

**Full copy for F0 and F14 (the two that matter most):**

**F0 — Subject:** Your free agents: setup in 20 seconds
> Hi {FIRST_NAME},
>
> Here's your free, no-signup URL: {FREE_MCP_URL}
>
> Paste it into your AI (steps for every app: {INSTALL_LINK}), then try:
> - **Copy Editor:** "Edit this for clarity and tell me the readability score before and after: [paste text]"
> - **Meeting Ops:** "Here's my meeting transcript. Give me the decisions, action items and owners: [paste]"
>
> They're free forever. What's your job? Reply with it and I'll tell you which of the other 98 agents would save you the most time.
>
> {YOUR_NAME}

**F14 — Subject:** Founding seats: {SEATS_LEFT} left
> Hi {FIRST_NAME},
>
> You've had the free agents for two weeks. If you want the rest, now is the cheapest it will ever be: **Founding Member** is all 100 agents plus every future one for **$14.99/mo, locked for life**. After 500 seats it's $29.99.
>
> 7-day free trial, cancel in two clicks: {FOUNDER_LINK}
>
> If the free ones are all you need, that's genuinely fine. They stay free.
>
> {YOUR_NAME}

**Metrics:** opt-in rate on install page, F-sequence open/click (directional only; opens are unreliable due to privacy features), free→trial within 30 days (*assumption to validate: 3–8%*).

---

## 6. Monthly "What shipped" (all paying customers + opted-in free users)

**Subject:** What shipped in [Month]: [headline agent] + [N] more
> - **New agents:** {NEW_AGENTS} (one line + one example each)
> - **Improved:** [agent]: [concrete change, e.g., "now warns when your A/B test is underpowered"]
> - **From a customer:** [real use case, with permission]
> - **Numbers (build in public):** [MRR, customers, seats left]
> - **Your plan:** [All-Access/Pack/Founder: "all of these are already in your plan"] · [Single/Starter: "add any of these from {PORTAL_LINK}"]

**Metric:** click-through to new agents; voluntary churn in the 30 days after vs before the email started (retention effect).
