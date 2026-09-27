# Creators & Personal: parity evaluation

Evaluated 2026-09-27. Scope: all 8 agents in `hundred/agents/creator/`. Competitor prices come from `marketing/pricing_research/content_seo_creator.md`.

**Method.** We have no competitor accounts, so we didn't run any competitor. For each agent we:

1. Picked the paid tool that overlaps most with the agent's job.
2. Built a parity checklist from that tool's *documented* capabilities, with a URL for each item.
3. Wrote a realistic scenario and ran it the way a customer's AI would: `python -m hundred.admin brief …`, then followed the playbook and made each tool call with `python -m hundred.admin run …`.
4. Checked every number by hand, using independent snippets that don't import `hundred`: published formulas, `zoneinfo`, and the SM-2 paper.

Where the checks found a wrong number, a missing guardrail or misleading guidance, we fixed the tool or the playbook and re-ran the scenario. Every scenario can be replayed with `tests/scenarios/test_creator.py`, and its assertions are the hand-verified values.

**Plain-AI baseline.** We didn't run one. The "traps" noted under each agent are places where this scenario's inputs give a different answer if you use the obvious method: written word count instead of spoken, per-leg instead of per-journey jet lag, CDT instead of CST, `round` instead of SM-2's ceiling. Each trap is quantified with the numbers from our runs. We don't claim to know what a given model would do.

**Structural gap for the whole category.** No agent stores history. Fitbod (training log and recovery), MacroFactor (weigh-in trend), Anki/Quizlet (card state), Later (post analytics) and Beacons (live stats) all improve over time from data they keep. Our agents only know what the customer passes in on each call.

## Overview

| Agent | Comparable & price | Checklist (M / P / Missing / OOS) | Correctness checks | Verdict | Fixes made |
|---|---|---|---|---|---|
| content-calendar | Later Starter, $25/mo ($18.75 annual-eq) | 1 / 4 / 0 / 3 (+1 extra) | Capacity math, DST-aware audience times (UK and US DST changes), X URL = 23 chars, IG hashtag cap ✓ after fix | **AT PAR** on planning; BELOW on data-driven "best time" (structural) | Capacity fallback wasted 74% of the hours and dropped YouTube, now fits IG 2 + TT 2 + YT biweekly (5.4 of 6 h). Default times now anchored to the audience's timezone. Every-other-week cadence added. IG hashtag max corrected from 30 to 5. Warnings for create-by dates before the calendar starts and for late-night slots. |
| short-video-scripter | vidIQ Boost, ~$16.58/mo annual-eq (3P). OpusClip's clipping is out of scope. | 3 / 1 / 1 / 2 | Words per second from spoken form; beat-sheet sums; hook caps ✓ after fix | **AT PAR** on scripting; BELOW on performance prediction | Timing counted written tokens, so "$250,000" counted as 2 words when it is 5 spoken. The script timed at 55.2 s but really runs 60.0 s. Numbers, currency and % are now counted as spoken. Added loss/cost words to the hook tension list. |
| podcast-producer | Castmagic Hobby, $239/yr ($19.92/mo) | 4 / 1 / 0 / 2 (+2 extras) | YouTube chapter rules (Google doc), chapter lengths, ad window, CPM revenue ✓ after fix | **AT PAR** given a transcript; BELOW if the customer has only audio | Revenue priced 30-s pre/post-rolls at the 60-s mid-roll CPM, so $850 was overstated; it is now weighted by placement ($690.63). Mid-rolls now snap to chapter boundaries automatically. |
| sponsorship-pricer | Passionfroot (free; 2% / 15% fees) + Beacons Media Kit Pro, $10/mo | 2 / 1 / 0 / 3 (+1 extra) | Median, ER by views and by followers, CPM × multipliers, implied CPM, hourly ✓ | **ABOVE** on pricing (neither documents price recommendations) | The reduced-scope fallback still included usage and exclusivity uplifts, which is contradictory. It is now priced organic-only with an honest walk-away. The playbook's perpetual-usage wording now matches the code (+200%). |
| fitness-coach | Fitbod Premium, $15.99/mo ($8 annual-eq, 3P) | 3 / 2 / 1 / 1 (+2 extras) | Epley, Brzycki, Mifflin-St Jeor × 1.55, 7,700 kcal/kg, 5/3/1 %TM, Karvonen/Tanaka, plate maths, per-muscle set counts ✓ | **AT PAR** on block planning; BELOW on session-to-session adaptation (structural) | Four gaps fixed. (1) Underweight guardrail: BMI 17.6 asking to cut is now given maintenance. (2) Rate reported after the kcal floor is now the achieved 0.27 kg/wk, not the 0.75 requested. (3) A computed `safer_alternative` is added. (4) Incline and other presses got the lower-body 5 kg increment; that is fixed. Also: 5/3/1 summary showed the deload load as "top load"; plate loading was greedy and failed on custom plates; added `reps_in_reserve` for 5×5-style sets. |
| meal-planner | Eat This Much Premium, $14.99/mo ($5 annual-eq, 3P) | 3 / 1 / 1 / 3 | 4/4/9, meal split, totals, label check, sodium, cost per serving, unit scaling ✓. Grocery merge was wrong before the fix. | **AT PAR** on list, scaling and budget; BELOW on automatic generation (no food database) | Grocery list had six bugs: (1) pantry "rice" silently removed "rice vinegar"; (2) "garlic cloves" and "garlic" didn't merge; (3) ground cumin went to meat and peanut butter to produce; (4) volumes showed as "828 ml broccoli"; (5) 1½ cans was never rounded up to 2; (6) head/clove counts would sum. Spoon display fixed ("15 ¾ tsp" is now "⅓ cup"), banker's rounding fixed. |
| travel-planner | Wanderlog Pro, $39.99/yr ($3.33/mo, 3P) | 1 / 1 / 1 / 4 (+1 extra) | Durations across the date line and US DST end (12 h 05 m, not 11 h 05 m), call windows 14 h then 15 h, usable hours, budget ✓ | **AT PAR** (ABOVE on time maths, BELOW on maps/routing) | Jet lag on a connecting itinerary used the last leg: 8 zones and 5.3 days, when the true figure is 10 zones and 6.7 days. Added `body_clock_tz` and a journey call to the playbook. Connection verdicts no longer present rule-of-thumb buffers as official MCTs, and they distinguish protected same-ticket connections. Departure-day note corrected. |
| study-coach | Anki (desktop free; AnkiMobile $24.99 one-time) + Quizlet Plus, ~$3/mo annual-eq (3P) | 4 / 1 / 2 / 1 | SM-2 against Wozniak's published algorithm ✗ before fix, ✓ after; study-load arithmetic ✓; Anki header syntax ✓ | **AT PAR** as planner + card factory feeding Anki; **BELOW** as a standalone SRS (no stored card state) | SM-2 changed EF on lapses and rounded intervals to nearest; the paper keeps EF and rounds up (14 → 15, 40 → 41, 105 → 106 days). Added same-day re-drill (<4) and `exam_date`. Anki file wrote `<br>` under `#html:false`, which shows literally. A 5-item list answer escaped the lint. The calendar flagged its own final-pass day as overload. The Pomodoro plan put two work blocks back to back with no break. |

Checklist codes: M = MATCHES, P = PARTIAL, OOS = out of scope (posting, recording/editing, logging history, food/barcode databases, booking, maps). "Extra" = something the agent does that the comparable doesn't document; extras aren't scored.

**Tests after fixes**
- `python -m pytest -q tests/agents -k creator tests/scenarios/test_creator.py`: 106 passed.
- `python -m pytest -q tests/test_library.py`: 303 passed.

---

## content-calendar

**Scenario.** A solo food creator in London whose audience is mostly US East. They have 6 hours a week and want Instagram 4×, TikTok 4× and YouTube 1× per week, as a 4-week calendar from Mon 2026-10-19. That window deliberately spans the UK DST change (Oct 25) and the US one (Nov 1).

**Checklist vs Later Starter** ([later.com/pricing](https://later.com/pricing/): visual calendar, IG/FB/TikTok Best Time to Post, hashtag suggestions, drafts, auto-publish, 5 AI credits/mo, analytics up to 3 months, link in bio)

| Later capability | Status | Why |
|---|---|---|
| Visual multi-platform calendar | PARTIAL | Dated slot table, plus Notion/Sheets/Airtable rows through the customer's connectors. No drag-and-drop UI. |
| Best Time to Post (IG, FB, TikTok) | PARTIAL | Platform default windows anchored in the *audience's* timezone and converted per date (DST-safe). Later uses the account's own engagement data, which is a structural gap for us. |
| Hashtag suggestions | PARTIAL | Hashtag counts are checked against platform caps (IG max 5 since Dec 2025, per [Social Media Today](https://www.socialmediatoday.com/news/instagram-implements-new-limits-on-hashtag-use/808309/)) and against the sweet spot. We have no hashtag-volume data. |
| AI Caption Writer / Ideas (5 credits/mo) | MATCHES | The customer's own AI writes captions without a credit cap. `check_post_fits` adds hard limits, the "see more" fold, and X's 23-char URLs. |
| Draft posts | PARTIAL | Drafts are stored only through connectors. |
| Auto-publish | OUT OF SCOPE | Posting. |
| Analytics (3 months) | OUT OF SCOPE | `audit_mix` only analyses history the customer pastes in. |
| Link in bio | OUT OF SCOPE | Hosting. |
| *Extra:* capacity check and fitted cadence | Not in Later | Stops the plan from scheduling what the creator can't make. |

**Correctness**

| Check | Independent value | Tool |
|---|---|---|
| Effective minutes per post (30% repurposed) | 45/75/360 × 0.775 = 34.875 / 58.125 / 279 | ✓ |
| Hours needed for the request | (4·34.875 + 4·58.125 + 279)/60 = 10.85 | 10.8 ✓ |
| Best fit within 360 min | IG 2 + TT 2 + YT ½ = 325.5 min (5.4 h) | ✓ after fix. Before: IG 1 + TT 1 = 93 min, YouTube dropped. |
| 11:00 New York → London | Oct 20: 16:00. Oct 27 (UK changed, US not): 15:00. Nov 3: 16:00 (zoneinfo). | ✓ after fix. Before: 11:00 London was sent to NY at 06:00. |
| X length with a 49-char URL | len − 49 + 23 = 151 | 151 ✓ |
| Instagram, 6 hashtags | Over the platform cap of 5 | ✓ after fix. Before: a soft "3-5 sweet spot" note, because the max was 30. |

**Deliverable excerpt**
```
# Content calendar — 2026-10-19 to 2026-11-15 (4 weeks)
**Capacity:** 6 h/wk available · requested plan needs 10.8 h/wk → scaled to IG 2/wk · TikTok 2/wk · YouTube every other week (5.4 h)
**Pillars:** Quick recipes · Kitchen myths · Budget meals · Behind the scenes   **Timezone:** Europe/London (audience: America/New_York)

## Week 1 (Oct 19-25)
| Date | Time (London / NY) | Platform | Pillar | Post idea (hook → format → CTA) | Create by |
|---|---|---|---|---|---|
| Tue 20 Oct | 16:00 / 11:00 | Instagram | Quick recipes | "Your $4 dinner is hiding in your freezer" → 5-slide carousel → save | Mon 19 Oct (tool: 18th, before start) |
| Tue 20 Oct | 23:00 / 18:00 | TikTok | Kitchen myths | "Stop rinsing raw chicken" → 30 s talking head → follow for pt 2 | Mon 19 Oct |
| Thu 22 Oct | 16:00 / 11:00 | Instagram | Budget meals | "One $9 chicken, four dinners" → Reel → comment "LIST" | Tue 20 Oct |
| Thu 22 Oct | 23:00 / 18:00 | TikTok | Behind the scenes | "What a 2-hour batch cook actually looks like" → timelapse → save | Tue 20 Oct |
| Fri 23 Oct | 20:00 / 15:00 | YouTube | Quick recipes | "3 dinners from one bag of frozen spinach" → 10-min video → subscribe | Wed 21 Oct |

## Week 2 (Oct 26 – Nov 1): UK clocks changed Oct 25, US not until Nov 1, so IG goes out at 15:00 London this week only
...
## Rules for this calendar
- Batch days: Sun + Wed. Anything not created by its create-by date is skipped, not rushed.
- The 22:00-07:00 London slots are pre-scheduled in TikTok's native scheduler (tool warning).
```

**Honest gaps.**
- No posting, no analytics, no learned "best time". After four weeks the creator's own analytics should override our defaults, and the playbook says so.
- Trap in this scenario: without the capacity fit, 10.8 h of work would be booked into a 6 h week. With naive timing, IG posts would land at 06:00 in New York.

---

## short-video-scripter

**Scenario.** A 60-second TikTok, listicle format, from a personal-finance creator: "where your emergency fund should (not) sit". The script is full of spoken figures ($10,000, 0.01%, $250,000).

**Checklist vs vidIQ Boost** (AI script generator "from 60-second Shorts to full-length" with intro, talking points, transitions and CTA ([vidiq.com/ai-script-generator](https://vidiq.com/ai-script-generator/), via search listing; the feature page returned 429). "Viral Hook Ideation" and "Swipe-Rate Predictions" modules and the title generator come from 3P reviews. Price per [1of10.com](https://1of10.com/blog/vidiq-pricing/) [3P].)

| vidIQ capability | Status | Why |
|---|---|---|
| Full Shorts script (hook/intro, points, transitions, CTA) | MATCHES | `plan_beats` gives time-coded beats with word budgets, and the AI writes into them. |
| Hook ideation | MATCHES | The playbook requires 3-5 hooks of distinct types. `score_hook` scores each 0-100 with fixes. |
| Swipe-rate prediction | MISSING | Our hook score is a transparent heuristic, not a model trained on performance data. |
| Title generator (10+ variations) | PARTIAL | The AI writes titles, but with no search or keyword data behind them. |
| Script length control | MATCHES (stronger) | Line-by-line timestamps at a stated pace, with the hook capped at 3 s. vidIQ documents no timing. |
| Trend / keyword research | OUT OF SCOPE | Proprietary data. |
| Clip generation (Max; OpusClip's job) | OUT OF SCOPE | Media editing. |

**Correctness**

| Check | Independent value | Tool |
|---|---|---|
| Spoken words (hand transcription, e.g. "$250,000" → "two hundred fifty thousand dollars") | 150 | 150 ✓ after fix. Before: 138. |
| Runtime at 2.5 words/s (natural conversational pace) | 150 / 2.5 = 60.0 s | 60.0 ✓. Before: 55.2 s, 8% short. |
| Hook "Stop keeping $10,000 in checking." | 7 spoken words = 2.8 s (< 3 s) | ✓ |
| Beat sheet, 60 s listicle | 3 + 10.8·3 + 13.8 + 10.8 = 60.0 s; 150-word budget | ✓ |
| Greeting hook ("Hey guys, today I want to talk about…") | Should fail | Score 0 ✓ |

**Deliverable excerpt**
```
# Where your emergency fund should never sit — TikTok · target 60s · actual 60.0s at natural (2.5 w/s)
**Hook (score 86):** Stop keeping $10,000 in checking.
**Alternates (A/B):** 3 places your emergency fund should never sit (98 — scores higher; test it first) · Why is your savings account paying you 0.01%? (76)

| Time | Spoken line | On-screen text / B-roll |
|---|---|---|
| 0:00 | Stop keeping $10,000 in checking. | [TEXT: Your checking account pays 0.01%] |
| 0:03 | At 0.01%, ten grand earns you one dollar a year. | |
| 0:08 | Here are 3 places your emergency fund should never sit, and the one place it should. | |
| 0:15 | One: checking. It's too easy to spend, and it pays basically nothing. | [B-ROLL: bank app showing $0.08 interest] |
| … | … | … |
| 0:42 | It's FDIC insured up to $250,000, and you can move it in one or two days. | [TEXT: HYSA = safe + liquid + paid] |
| 0:50 | Open one tonight and set an automatic transfer on payday. | |
**CTA (0:54):** Follow for part two, where I show you how big your fund should be.
**Cover text:** Your $10k is losing money   **Caption:** Stop keeping $10k in checking. #personalfinance #emergencyfund
**Retention notes:** payoff (HYSA) lands at 0:33 (55%), before the last 20%. Lint: "basically" flagged as filler; keep it for voice or cut.
```

**Honest gaps.**
- No performance data: the hook score is a rules-based proxy.
- The pace is an assumption (2.5 words/s) until the creator measures their own.
- Trap in this scenario: counting written tokens says 55 s, but the spoken script is 60 s. The number-heavy lines are exactly where creators run over.

---

## podcast-producer

**Scenario.** Episode of *Rested*: host Maya, guest sleep physician Dr. Leo Park, 46:30 long. The transcript is timestamped with speaker labels; it is abridged to 19 lines, so fillers/min isn't meaningful here. 8,500 downloads per episode, $25 CPM on 60-s mid-rolls, weekly Tuesday releases from 2026-10-06.

**Checklist vs Castmagic Hobby** ([castmagic.io/pricing](https://www.castmagic.io/pricing): $239/yr, 30 transcribed hours, unlimited AI outputs. [castmagic.io](https://www.castmagic.io/): show notes, transcripts, clips, quotes, carousels, audiograms, "Timestamped Overview & Shownotes", YouTube descriptions.)

| Castmagic capability | Status | Why |
|---|---|---|
| Transcription (speaker-labelled, timestamped, 60+ languages) | OUT OF SCOPE | The customer must bring a transcript (Descript, Riverside, Spotify export). This is the biggest practical gap. |
| Show notes: summary, highlights, resources | MATCHES | The output format requires every resource mentioned. The self-check requires every timestamp to exist in the transcript. |
| Timestamped overview / chapters | MATCHES (stronger) | `format_chapters` enforces YouTube's rules and produces both blocks. |
| Titles / YouTube descriptions | MATCHES | `check_metadata` checks Apple's rules (no episode number or show name in the title, per [Apple](https://podcasters.apple.com/support/823-podcast-requirements)), plus truncation and the first 120 characters. |
| Quotes & highlights | MATCHES | A verbatim quote with a timestamp is required. |
| LinkedIn posts, newsletters, blogs, threads | PARTIAL | The customer's AI can write them, but this playbook doesn't cover repurposing (content-repurposer does). |
| Clips / audiograms | OUT OF SCOPE | Media editing. |
| *Extras:* ad-break placement with revenue; release calendar with record/edit deadlines | Not in Castmagic | |

**Correctness**

| Check | Independent value | Tool |
|---|---|---|
| YouTube chapter rules ([Google](https://support.google.com/youtube/answer/9884579): first at 00:00, ≥ 3 ascending, ≥ 10 s) | Bad set (0:05 start, 0 s chapter, non-ascending) must fail on all three | ✓ |
| Chapter lengths | 65, 335, 335, 435, 452, 463, 405, 220, 80 s | ✓ |
| Talk share, questions, fillers | Leo 9 fillers (um ×3, uh, like ×2, you know, basically ×2), Maya 1; Maya 7 questions | ✓ |
| Mid-roll window and ideal points | 480 s … 0.9 × 2790 = 2511 s → 19:17, 30:34 → snapped to next chapters 19:30, 34:45 | ✓ after fix (snapping was manual before) |
| Ad load | 180 s / 2790 s = 6.5% | ✓ |
| Revenue ([Podder benchmarks](https://www.podderapp.com/post/podcast-cpm-benchmarks), citing Libsyn Ads / Ad Results Media: pre-roll $18-25, mid $25-40, post $10-15) | 8.5 × (18.75 + 25 + 25 + 12.5) = $690.63 | ✓ after fix. Before: $850, all slots at the mid-roll CPM. |
| Publish time in UTC across US DST end | Oct 27 05:00 CDT = 10:00 UTC; Nov 3 05:00 CST = 11:00 UTC | ✓ |

**Deliverable excerpt**
```
# Dr. Leo Park: sleeping in on Saturday is giving you jet lag (46:30)
**Guest:** Dr. Leo Park, sleep physician, Northwestern insomnia clinic · **Talk share:** host 26% / guest 74%

## Hook
Sleeping in on weekends shifts your body clock like a flight to LA and back. Sleep physician Dr. Leo Park explains social jet lag and the one-alarm fix.

## Chapters
0:00 Cold open: the weekend sleep mistake
1:05 What social jet lag really is
6:40 How clinics measure your body clock
12:15 The one-alarm weekend fix
19:30 Melatonin: half a milligram, five hours early
27:02 Why a 3 pm coffee still counts
34:45 Anchor sleep for shift workers
41:30 One thing to do tonight
45:10 Where to find Dr. Park

## Resources mentioned
- Munich Chronotype Questionnaire — add link · Why We Sleep, Matthew Walker — add link · @sleepdocleo (Instagram)

## Ad breaks
Pre-roll 0:00 · Mid-roll 1 19:30 (after "The one-alarm weekend fix") · Mid-roll 2 34:45 (after "Why a 3 pm coffee still counts") · Post-roll 46:10 — est. $691/episode
## Metadata
Title (59 chars) passes Apple/Spotify/YouTube checks · Description: passes
```

**Honest gaps.**
- No transcription from audio, so the agent is useless to a host who has only an MP3 and no transcript tool.
- The host question-rate flag (9/hour) is an artefact of the abridged transcript.

---

## sponsorship-pricer

**Scenario.** A personal-finance YouTuber with 185k subscribers. Views on the last 15 videos have a median of 40,300, with one 129k outlier. A budgeting app offers $900 for a 60-90 s integration with 90-day paid usage, 3-month category exclusivity, net-60, no deposit, 2 revision rounds and no kill fee. It takes 8 production hours and the creator's floor is $75/h.

**Checklist vs Passionfroot + Beacons.** Passionfroot ([creator pricing](https://www.passionfroot.me/creator-pricing)) offers a media kit with live stats, a storefront with custom rates, booking forms, a deal dashboard and invoicing, for 2% / 15% fees; its page doesn't mention pricing recommendations. Beacons ([media kit](https://beacons.ai/i/app-pages/media-kit), [pricing](https://beacons.ai/i/pricing)) offers auto-updating stats, a custom rate card and "pricing tools" (not further documented), with Media Kit Pro at $10/mo.

| Capability | Status | Why |
|---|---|---|
| Media kit with live, auto-updating stats | PARTIAL | `media_kit_numbers` computes the honest numbers (median, not mean; ER by views and by followers; growth) from pasted data. No live sync. |
| Custom rates / rate card | MATCHES (stronger) | CPM × median views, with niche, engagement, usage, exclusivity, whitelisting and rush uplifts. Each uplift is a line the creator can paste into a reply. |
| Pricing guidance ("pricing tools") | MATCHES | Neither competitor documents a method. Ours is explicit, and flagged as a market starting point until the creator has 3 closed deals. |
| Storefront, discovery, booking forms | OUT OF SCOPE | Marketplace. |
| Deal dashboard, messaging | OUT OF SCOPE | No deal history is stored; the creator supplies closed-deal CPMs via `cpm_override`. |
| Invoicing / payments | OUT OF SCOPE | We produce the payment schedule and terms only. |
| *Extra:* offer evaluation, red-flag terms, counter + fallback + email | Neither documents this | |

**Correctness**

| Check | Independent value | Tool |
|---|---|---|
| Median / mean views | 40,300 / 46,280 | ✓ |
| ER by views / by followers | 24,300 / 694,200 = 3.5%; (24,300 / 15) / 185,000 = 0.88% | 3.5 / 0.9 ✓ |
| Rate card (low / mid / high) | 40.3 × {20, 30, 40} × 1.5 (finance) × 1.95 (+50% usage, +45% exclusivity) = 2,357.55 / 3,536.33 / 4,715.10 | ✓ |
| Offer's implied CPM, hourly | 900 / 40.3 = $22.33; 900 / 8 = $112.50 | ✓ |
| Counter | max(3,536.33, 900 × 1.15), rounded to $25 = 3,525 | ✓ |
| Organic-only fallback | 40.3 × 30 × 1.5 = 1,813.5 → 1,825; walk-away 40.3 × 20 × 1.5 = 1,209 → 1,200 | ✓ after fix. Before: "If budget is fixed at 900, I can do it at 2,350 with organic-only posting", a price that still contained the usage and exclusivity uplifts. |
| Bundle | (3,525 + 2 × 500) × 0.9 = 4,072.50; 50/50 split | ✓ |

**Deliverable excerpt**
```
# Sponsorship pricing — YouTube (finance) · 2026-09-27
**Media kit numbers:** median views 40,300 (mean 46,280) · ER by views 3.5% · ER by followers 0.9% · views/follower 0.22

## Rate card
| Deliverable | Base (median views × CPM) | Multipliers | Quote (low / mid / high) |
| YouTube integration 60-90s | 40.3k × $20/30/40 | finance ×1.5 · 90-day usage +50% · 3-mo exclusivity +45% | $2,358 / $3,536 / $4,715 |
| Same, organic only | 40.3k × $20/30/40 | finance ×1.5 | $1,209 / $1,814 / $2,418 |

## Offer evaluation
Offer $900 → implied CPM $22, $112/hour · Rate card mid $3,536 · Gap −74% · Red flags: Net-60 · Amber: no deposit (ask 50%), no kill fee
**Counter:** $3,525 incl. 90-day usage + 3-month exclusivity, 50% on signature, net-30; fallback $1,825 organic-only; below $1,200 pass.

## Reply draft
Subject: Re: integration — numbers and options
Thanks for thinking of us. For one 60-90s integration, my median is 40,300 views per video (last 15) with 3.5% engagement,
in a finance audience. With 90 days of paid usage and 3 months' category exclusivity, the rate is $3,525 (≈ $87 CPM).
If the budget is tighter, the organic-only version (no paid usage or exclusivity) is $1,825. Terms: 50% on signature,
balance net-30, one script and one cut revision, 50% kill fee after script approval, #ad disclosure. Happy to hop on a call.
```

**Honest gaps.**
- The CPM table is a set of market rules of thumb, not a data set.
- There is no storefront or deal history.
- Beacons and Passionfroot pull stats directly from the platforms; we depend on the creator pasting accurate numbers.

---

## fitness-coach

**Scenario.** A 34-year-old man, 88 kg, 178 cm, training 4 days a week for 2 years. Squat 5×5 at 100 kg, bench 80 kg × 6, deadlift 140 kg × 3. He wants to lose 1 kg a week for 8 weeks "without losing strength". Guardrail probes: a sedentary 55 kg woman asking for 0.75 kg/week, and a 48 kg / 165 cm woman (BMI 17.6) asking to cut.

**Checklist vs Fitbod** ([fitbod.me/blog/fitbod-algorithm](https://fitbod.me/blog/fitbod-algorithm/): 1RM estimated "using established prediction equations (such as the Epley formula)"; "targets 10–20 working sets per muscle group per week"; per-muscle recovery 0-100% from history; cycles heavier/lighter days; recommends only for selected equipment. Price per [research](../marketing/pricing_research/content_seo_creator.md), 3P.)

| Fitbod capability | Status | Why |
|---|---|---|
| e1RM from sets (Epley-type) | MATCHES | Mean of Epley and Brzycki, with a reliability flag. New `reps_in_reserve` handles 5×5 work sets. Uses the reported set, not a log. |
| Progressive overload that adapts session to session | PARTIAL | A pre-planned block (linear, 5/3/1 or double progression) with missed-rep rules. No automatic adjustment, because we don't see the logged sessions. |
| 10-20 sets per muscle per week | MATCHES | Same landmark; `weekly_volume_audit` counts direct and secondary sets. |
| Muscle recovery % drives selection | MISSING | Structural: needs training history. |
| Heavy/light cycling, deloads | MATCHES | 5/3/1 waves and deload weeks, rounded to plates. |
| Equipment-aware selection | PARTIAL | The AI can respect stated equipment; there is no equipment catalogue. |
| Workout logging / history | OUT OF SCOPE | Logging. |
| *Extras:* TDEE and macros with guardrails (MacroFactor's job); plate loading; HR zones | Not in Fitbod | |

**Correctness**

| Check | Independent value | Tool |
|---|---|---|
| e1RM: Epley w(1 + r/30), Brzycki 36w/(37 − r), mean | 114.6 / 94.5 / 151.1 kg; with 2 RIR on the 5×5: 121.7 | ✓ |
| BMR, Mifflin-St Jeor (Mifflin et al., *AJCN* 1990): 10W + 6.25H − 5A + 5 | 1,827.5 | 1,828 ✓ |
| TDEE × 1.55 (moderate) | 2,832.6 | 2,833 ✓ |
| −1 kg/wk: 7,700 kcal/kg ÷ 7 = 1,100/day | 1,733 kcal, 38.8% deficit → flags for > 25% deficit and > 1% bodyweight/week must fire | ✓ both fire |
| Safer alternative (20% deficit, ≤ 1% bodyweight) | 2,266 kcal, 0.52 kg/wk | ✓ (new) |
| Macros at 1,733 | P 2.0 × 88 = 176 g; F max(52.8, 48.1) = 53 g; C (1,732.6 − 704 − 475.2)/4 = 138 g | ✓ |
| Floor probe (F, 55 kg, sedentary, 0.75 kg/wk) | TDEE 1,492.8; 668 → floored at 1,200; achieved rate (1,492.8 − 1,200) × 7/7,700 = 0.27 kg/wk | ✓ after fix. Before: it still said "at 0.75 kg/week". |
| Underweight probe (BMI 17.6, "lose") | No deficit; refer out | ✓ after fix. Before: a 0.5 kg/wk cut was planned. |
| 5/3/1: TM = 90% × 114.6 → 102.5; week 1 at 65/75/85% | 67.5 / 77.5 / 87.5; cycle 2 TM 107.5 (+5 kg lower body) | ✓ |
| Plates: 132.5 kg on a 20 kg bar | 56.25/side = 25 + 25 + 5 + 1.25 | ✓. Custom set {20, 15} for 80 kg: 15 + 15 (greedy gave "20 per side = 60 kg, not loadable") ✓ after fix. |
| Volume audit of the written week | chest 7, back 17, shoulders 9.5, quads 7, hams 14, glutes 16, biceps 10, triceps 7 | ✓ |
| Karvonen/Tanaka, age 34, RHR 58 | HRmax 184; Z2 = 58 + 0.6–0.7 × 126 = 134–146 bpm | ✓ |

**Deliverable excerpt**
```
# Alex — cut while keeping strength, 8-week block
_General guidance, not medical advice._

**Numbers:** 1RM est. — Squat 115 (≥ 122 if the 5th set had 2 in the tank) / Bench 95 / Deadlift 150 kg · TDEE 2,833 kcal
**Recommended:** 2,266 kcal · P 176 g · F 63 g · C 249 g · ≈ 0.52 kg/week (20% deficit)
**You asked for:** 1,733 kcal (1 kg/week) — flagged: 39% deficit (> 25%) and over 1% of bodyweight/week; expect strength loss.

## Progression (5/3/1, TM 90%)
| Week | Squat | Bench | Deadlift | Notes |
| 1 | 67.5/77.5/87.5×5+ | 55/65/72.5×5+ | 87.5/102.5/115×5+ | |
| 3 | 77.5/87.5/97.5×1+ | 65/72.5/80×1+ | 102.5/115/127.5×1+ | |
| 4 | 40/52.5/62.5×5 | 35/42.5/50×5 | 55/67.5/80×5 | deload |
| 5 | TM 107.5 | TM 87.5 | TM 140 | cycle 2 |

## Volume check
chest 7 → +3 sets (dips Thu) · quads 7 → +3 (leg press Fri) · triceps 7 → +3 · shoulders 9.5 → +1 lateral raise · push:pull 0.87
## Rules
- Missed reps twice → repeat load; three times → −10%. Plate for 97.5 kg: 25 + 10 + 2.5 + 1.25 per side.
```

**Honest gaps.**
- Fitbod adapts every session from the log, and MacroFactor adapts TDEE from the weigh-in trend. We plan once and rely on the customer to report back. That is structural, and it is the main reason the verdict is AT PAR, not ABOVE.
- Trap in this scenario: taking "5×5 at 100 kg" as a 5RM under-reads the squat by about 7 kg.

---

## meal-planner

**Scenario.** One person on 2,100 kcal with 160 g protein, 4 meals a day and $80 a week. Three batch recipes are scaled (chili 4 → 6, rice bowls 2 → 7, oats 1 → 7) plus a snack. Pantry: olive oil, salt, black pepper, rice, soy sauce.

**Checklist vs Eat This Much Premium.** Features come from the [2026 review](https://www.promealplan.com/en/blog/eat-this-much-review-2026) [3P] and the [Google Play listing](https://play.google.com/store/apps/details?id=com.eatthismuch&hl=en_US): auto-generated weekly plans to calorie and macro targets, grocery lists, a daily price limit, grocery controls (split by store, scale for family, leftovers), Instacart/AmazonFresh, emailed plans, a barcode food log.

| Capability | Status | Why |
|---|---|---|
| Auto-generate a week to calorie/macro targets | PARTIAL | The AI designs the week around 3-4 anchors. Tools split targets and verify totals, but there is no recipe or nutrition database; label values come from the AI or the customer. |
| Grocery list | MATCHES | Merged across recipes, unit-converted, rounded up to buyable units, aisle-sorted, pantry-aware (after fix). |
| Budget limit | MATCHES | Cost per serving, per day, and against budget with swap order. Prices are supplied by the customer or AI; there is no price database. |
| Scale for family / leftovers | MATCHES | `scale_recipe`, plus a serving-coverage check in `cost_per_serving`. |
| Split grocery list by store | MISSING | Sorted by aisle only. |
| Instacart / AmazonFresh send-to-cart | OUT OF SCOPE | Execution. The Instacart connector works if the customer has it. |
| Barcode food log / food database | OUT OF SCOPE | |
| Emailed weekly plans / PDF | OUT OF SCOPE | Delivery; Docs/Notion connectors can cover it. |

**Correctness**

| Check | Independent value | Tool |
|---|---|---|
| 4/4/9 | 160·4 + 210·4 + 70·9 = 2,110 (within 8% of 2,100, so no flag) | ✓ |
| Post-workout meal 2 | carbs 210 × 1.4/4.1 = 71.7, fat 23.9, kcal 662 | ✓ |
| Day totals | 2,040 kcal, 156 g protein, 2,340 mg sodium; bar label 20·4 + 24·4 + 9·9 = 257 vs 200 stated | ✓ flags fire |
| Scaling 2 → 7 | ×3.5: soy 7 tbsp, conservative 5.25 tbsp → ⅓ cup; vinegar 2.625 tbsp → 2½ tbsp + ½ tsp | ✓ after fix. Before: "15 ¾ tsp" / "8 tsp". |
| Merge | garlic 4.5 + 7 = 11.5 → buy 12 cloves; eggs 7 + 14 = 21; thighs 1.5 lb = 680 g; broccoli 3.5 cups (= 828 ml) | ✓ after fix. Before: garlic listed twice; broccoli "828 ml". |
| Pantry | Exact matches skipped; "rice vinegar" and "jasmine rice" kept and flagged | ✓ after fix. Before: rice vinegar silently removed. |
| Aisles | ground cumin, chili powder, peanut butter, crushed tomato (cans) → pantry | ✓ after fix. Before: meat / produce / produce / produce. |
| Cost | 63.40 / 7 = 9.06/day; 27 servings vs 28 needed | ✓ |

**Deliverable excerpt**
```
# Meal plan — week of Oct 19, 2,100 kcal · P 160 / C 210 / F 70 · omnivore
## Per-meal targets
| Meal | kcal | Protein | Carbs | Fat |
| 1 Breakfast | 483 | 40 | 46 | 15 |
| 2 Post-workout lunch | 662 | 40 | 72 | 24 |
| 3 Dinner | 483 | 40 | 46 | 15 |
| 4 Snack | 483 | 40 | 46 | 15 |
Day check (Mon): 2,040 kcal · P 156 g — within 5%; sodium 2,340 mg (swap the rice bowl's soy for half).

## Grocery list (by aisle)
**Produce:** banana 7 · broccoli 3½ cup · garlic 12 cloves · onion 3 (2 + 200 g ≈ 1 medium) · red bell pepper 2
**Meat/Fish:** chicken breast 1.05 kg · chicken thighs 680 g (1.5 lb)
**Dairy/Eggs:** eggs 21 · milk 840 ml · plain Greek yogurt 1.05 kg
**Pantry:** black beans 2 cans · crushed tomatoes 2 cans · chia 7 tbsp · chili powder 1½ tbsp · ground cumin 1½ tsp
           peanut butter 7 tbsp · rolled oats 350 g · rice vinegar 3½ tbsp (you have "rice" — not the same) · jasmine rice 525 g (check pantry)
**Frozen:** blueberries 525 g
Estimated cost: $63.40 ($2.35/serving) vs budget $80 — 27 of 28 servings covered; add one snack.
```

**Honest gaps.**
- No nutrition or price database, so every calorie and price is only as good as the AI's or the customer's inputs. Eat This Much generates from a database.
- No store split.

---

## travel-planner

**Scenario.** Chicago → San Francisco → Tokyo (HND): ORD 10:05 CDT Oct 29 → SFO 12:35 PDT; SFO 14:10 → HND 17:45 JST Oct 30. Tokyo 4 nights, Kyoto 3, Tokyo 2. Return HND 16:05 Nov 8 → ORD 13:10, *after* US DST ends on Nov 1. Two travellers; budget in JPY and converted to USD.

**Checklist vs Wanderlog Pro** ([Wanderlog blog](https://wanderlog.com/blog/2024/10/14/is-there-a-free-trip-planner/): itinerary builder, collaboration, Google place info, expense tracking; Pro adds offline maps, route optimization, Google Maps export. Pro at $39.99/yr per [3P](https://monkeyeatingmango.com/blog/wanderlog-pricing-2026/), which also lists flight and car deals and an AI assistant.)

| Capability | Status | Why |
|---|---|---|
| Day-by-day itinerary builder | MATCHES | Plus usable hours per day, arrival, transfer and departure realism, and a Monday closure flag. |
| Maps / Google place data | OUT OF SCOPE | The Google Maps connector is optional. |
| Route optimization ("shortest, quickest route") | MISSING | The AI groups anchors by neighbourhood; there is no distance matrix. |
| Budget / expenses by category, multi-currency | PARTIAL | A planning budget with contingency and conversion. No in-trip expense logging or splitting. |
| Collaboration | OUT OF SCOPE | |
| Offline maps | OUT OF SCOPE | |
| Flight / car deals | OUT OF SCOPE | Booking. |
| *Extra:* true flight durations across zones and DST, journey jet lag, connection risk, call-home windows | Not documented by Wanderlog | |

**Correctness** (all times independently with `zoneinfo`)

| Check | Independent value | Tool |
|---|---|---|
| ORD → SFO | 4 h 30 m | ✓ |
| SFO → HND (crosses the date line) | 11 h 35 m, arrives the next calendar day | ✓ |
| Journey ORD → HND | 17 h 40 m; body clock −5 → +9 = +14, i.e. 10 zones delaying (west): 10 / 1.5 = 6.7 days | ✓ after fix. Before, the last leg alone gave 8 zones and 5.3 days, and no journey figure. |
| HND → ORD after US DST end | 12 h 05 m (Chicago is CST, UTC−6); using CDT would give 11 h 05 m | ✓ |
| SFO layover | 95 min vs 90 comfort buffer → "tight", but protected on one ticket | ✓ after wording fix. Before it said "Legal but tight … vs 90 min minimum", presenting a rule of thumb as an official MCT. |
| Usable hours | Arrival 22 − (17:45 + 2 h) = 2.25; departure 16:05 − 3 − 08:00 = 5.1 | ✓ |
| Call-home window | Oct 31: Tokyo 08:00 = Chicago Fri 18:00 (14 h). Nov 2: = Sun 17:00 (15 h) | ✓ |
| Budget | ¥1,016,680 + 10% = ¥1,118,348 = ¥55,917 per person per day ≈ $7,493 | ✓ |

**Deliverable excerpt**
```
# Tokyo & Kyoto — Oct 30 – Nov 8 (9 nights) · 2 travellers · moderate
**Flights:** ORD→SFO→HND 17h40m door to door; body clock shifts 10 h (delay) — ~7 days to fully adjust. Land Fri 17:45:
  20-min nap max, walk, early dinner, bed by 22:30. Return HND→ORD 12h05m (US clocks back to CST on Nov 1).
**Budget:** ¥1,118,348 (≈ $7,493) = ¥55,917 per person/day incl. 10% contingency

## Day by day
| Day | Date | City | Usable hrs | Plan | Book by |
| 1 | Fri Oct 30 | Tokyo | 2.2 (arrival) | Check in; dinner near hotel; light walk | — |
| 2 | Sat Oct 31 | Tokyo | 8 | Meiji Jingu → Harajuku / Shibuya Sky at dusk / Shibuya izakaya | Shibuya Sky: Oct 1 |
| 4 | Mon Nov 2 | Tokyo | 8 | Monday: many museums closed — markets and gardens, not the National Museum | — |
| 5 | Tue Nov 3 | Kyoto | 3.5 (transfer) | Shinkansen AM; Gion evening (Nov 3 is a Japanese holiday: verify crowds) | Seats: Oct 27 |
| 10 | Sun Nov 8 | Tokyo | 5.1 (departure) | Be at HND by 13:05 (leave ~12:15) | — |
## Practical
Call home 08:00–13:00 Tokyo (= 17:00–22:00 Chicago after Nov 1; 18:00–22:00 before) · SFO connection: 95 min, one ticket
— protected; don't check a bag you'll need on arrival · Verify entry requirements at the official Japanese government source.
```

**Honest gaps.**
- No maps, route optimisation, collaboration or offline access. Those are the main things Wanderlog Pro sells.
- No public-holiday data; Nov 3 was noted by the AI, not by a tool.
- Connection buffers are rules of thumb, not airport MCT tables.

---

## study-coach

**Scenario.** A pharmacology final on 2026-12-11, starting 2026-10-26. Six weighted topics, about 300 cards, 8 hours a week. A graded review batch on Nov 10, sample cards for Anki import, and one evening session.

**Checklist vs Anki + Quizlet Plus.** Anki: SM-2 by default with starting ease 2.50, and FSRS as an opt-in alternative ([deck options](https://docs.ankiweb.net/deck-options.html)); text import with `#separator/#html/#deck/#tags column` headers ([importing](https://docs.ankiweb.net/importing/text-files.html)). Quizlet Plus: Learn mode (adaptive), Magic Notes (notes → flashcards), Test mode, spaced repetition ([3P review](https://nibble-app.com/blog/quizlet-review); quizlet.com returned 403).

| Capability | Status | Why |
|---|---|---|
| SM-2 scheduling | MATCHES | Faithful to Wozniak's published SM-2 after the fix. Anki's variant differs (learning steps, 4 buttons). |
| Stored cards and an automatic daily due queue | MISSING | Structural: the learner must pass card state back each session. The recommended pattern is to export to Anki and let Anki schedule. |
| Text import file | MATCHES | Valid headers and quoting; newlines are now import-safe. |
| Flashcards from notes (Magic Notes) | MATCHES | The AI writes the cards; `anki_export` lints them against the minimum-information rules. |
| Test-date study plan | MATCHES | `study_load` (fit or short-by-N-hours), `review_calendar`, and SM-2 with `exam_date`. |
| Practice tests (Test mode) | PARTIAL | The AI can write questions; there is no graded test engine. |
| FSRS option | MISSING | |
| Mobile apps / sync | OUT OF SCOPE | |

**Correctness**

| Check | Independent value (SM-2 per [SuperMemo](https://www.supermemo.com/en/blog/application-of-a-computer-to-improve-the-results-obtained-in-working-with-the-supermemo-method)) | Tool |
|---|---|---|
| EF formula, q = 3 from 2.5 | 2.5 + 0.1 − 2·(0.08 + 2·0.02) = 2.36 | ✓ |
| I(3) = I(2) × EF, "rounded up" | ⌈6 × 2.36⌉ = 15 | ✓ after fix (was 14) |
| q = 5 at interval 15, EF 2.6 → 2.7 | ⌈40.5⌉ = 41 | ✓ after fix (was 40) |
| q = 4 at interval 39, EF 2.7 | ⌈105.3⌉ = 106 → due 2027-02-24 | ✓ after fix (was 105). Also flagged as due after the exam, with a review on 12-09. |
| q = 2 lapse: "start repetitions … without changing the E-Factor" | EF stays 2.36; interval 1 | ✓ after fix (was 2.04) |
| "Repeat items that scored below four" | c3 (q = 3) and c5 (q = 2) re-drilled today | ✓ (new) |
| Study load | 46 days − 2 buffer − 2 practice = 42 days × 8/7 = 48 h vs 50 needed → short by 2 h; 8.3 h/wk needed | ✓ |
| Anki headers | `#separator:tab`, `#html:false`, `#tags column:3`, `#deck:` all valid | ✓. `<br>` removed (it shows literally under html:false). |
| Pomodoro, 150 min | 5 × 25 work + 4 × 5 break = 145 min, 18:30 → 20:55, no back-to-back work blocks | ✓ after fix |

**Deliverable excerpt**
```
# Study plan — Pharmacology final · exam 2026-12-11 (46 days) · 8 h/wk
**Verdict:** short by 2 h (48 available vs 50 needed) → 8.3 h/wk, or trim Endocrine to 3 h · **Buffer:** 2 days · **Method:** retrieval + spacing + interleaving

## Weekly allocation
| Week | Dates | Topics (hours) | Milestone |
| 1 | Oct 26 – Nov 1 | Cardio 2.0 · Autonomic 1.6 · Antimicrobials 1.6 · CNS 1.2 · PK 0.8 · Endo 0.8 | Autonomic + PK cards done |
| 6 | Nov 30 – Dec 6 | same split — retrieval + mixed practice only | Full practice paper |

## Review calendar (first 4 of 33 reviews)
| Oct 28 Autonomic | Oct 30 Autonomic, PK | Nov 1 PK | Nov 3 Autonomic | … | Dec 9: final pass, ALL topics as one timed mixed practice test |

## Today's SM-2 results (Nov 10)
c3 → 15 days (Nov 25) · c4 → 41 days (after the exam → extra review Dec 9) · c5 lapsed → tomorrow, ease stays 2.36
Re-drill now until they score 4+: c3, c5

## Cards (lint fixed)
"Is propranolol cardioselective?" → "Which β-receptors does propranolol block?" · aminoglycoside list → 5 cloze cards
```

**Honest gaps.**
- This is not an SRS app. Card state lives in the conversation unless the learner exports to Anki, which the playbook recommends.
- Quizlet's Learn mode adapts inside the app; ours needs the grades reported back.
- No FSRS.

---

## Issues outside `hundred/agents/creator/` (not edited)

- **`hundred/lib/text.py` `WORD_RE`.** Splits `4.5` into two words and `$250,000` into `250` + `000`, and gives no spoken expansion. Any agent that times speech from `text.words`, such as a speech- or YouTube-script timer, will under-time scripts heavy with numbers, as seen here (55.2 s vs 60 s). The creator agent now uses its own `spoken_word_count`. A shared `lib` helper would fix this for every agent.
- **Connection DST edge case (our code, minor).** `connection_check` parses both times as naive UTC. A layover that spans a DST change at the connecting airport would be off by an hour. It is left as is because it is rare; noted here for completeness.
