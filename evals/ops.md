# Ops category — product evaluation (2026-09-27)

**Scope.** All 9 agents in `hundred/agents/ops/`, including the free lead magnet **meeting-ops**.

**Method.** Each agent was run the way a customer's AI would run it:
1. `python -m hundred.admin brief <slug> "<task>"` to get the playbook.
2. `python -m hundred.admin run <slug> <tool> '<json>'` for every tool call.
3. The final deliverable written in the playbook's Output format.

**How the numbers were checked.** Every number was re-computed by separate scripts that do not import `hundred`: hand CPM, a hand PERT/normal CDF, stdlib `zoneinfo`, a brute-force slot search, a 0.01-step weight sweep, power-iteration AHP, and hand TCO/SLA/date arithmetic.

**Regression tests.** Every scenario is replayable in `tests/scenarios/test_ops.py`, which has 16 tests asserting the verified values.

**What the checklists cover.** Competitor capabilities come only from the vendors' own docs, fetched or searched on 2026-09-27; URLs are given per agent. Recording, calendar/mail sync, background automation and team workspaces are marked OUT OF SCOPE, not failures.

## Overview

The checklist column is written as M / P / X / O:
- **M** = MATCHES
- **P** = PARTIAL
- **X** = MISSING
- **O** = OUT OF SCOPE

| Agent | Comparable & price (monthly, [annual]) | Checklist M/P/X/O | Correctness checks (independent) | Verdict (overlapping job) | Fixes made |
|---|---|---|---|---|---|
| **meeting-ops** (free) | Fireflies Pro $18 [$10]; also Fathom Premium $20, Otter Pro $16.99 | 5 / 4 / 0 / 3 | Action-item recall 6/6 (sample) + 9/9 (messy Otter export); 0 invented; 13/13 due dates; 3/3 decisions; retraction and reassignment caught | **AT PAR** (was BELOW: wrong due date on the shipped sample) | "EOD Thursday" resolved to *today*; "next Tuesday" came out 13 days away; "Attendees" was counted as a speaker; Otter/Fireflies/VTT exports now parsed; decisions, retractions and meeting date added; month-name dates; playbook reassignment rule |
| **project-planner** | Smartsheet Pro $12 [$9] | 5 / 2 / 1 / 0 | 24/24 float values (TF + FF), length, critical path; calendar end date; PERT E/σ/P80/P90 and dates; 5/5 slips; typed-link variant | **AT PAR**, ABOVE on schedule risk | SS/FF/SF + lag/lead links; PERT now returns calendar dates and P(plan holds); playbook no longer labels the most-likely plan date "P50" |
| **time-blocker** | Reclaim Starter $12 [$10] | 3 / 3 / 0 / 2 | 5/5 DST-week conversions; slot search matches brute force on 2 dates; audit 835 min / 31% / 3 fragments / 5 back-to-back; pack-day invariants | **AT PAR** (was BELOW: audit said RED 58% for a 31% week) | Audit counted focus blocks and all-day items as meetings and dropped meeting-free days; pack_day put prep after the call and made 5-min deep slivers; fall-back ambiguity warning |
| **inbox-triage** | Superhuman Pro $15 [$12] | 3 / 2 / 0 / 3 | 15/15 actions vs evaluator labels (10/15 before fixes); 5/5 deadlines; reply length | **AT PAR** | Cold-pitch detection; thanks-only → archive; "Reply now" only when urgent or VIP; greeting/sign-off not counted as sentences |
| **sop-writer** | Scribe Pro Personal $35 [$25] | 2 / 2 / 0 / 3 | Cycle time (18 / 1,728 min / 1.04% PCE / 2 handoffs); review dates incl. Aug 31 + 6 mo → Feb 28; RACI 2/2 invalid rows; lint 5/5 planted defects | **AT PAR** on writing a text SOP; Scribe's screen capture is out of scope | "Support agent:" actor prefix not recognised; "Issue the refund" not treated as irreversible; a 24 h wait reported as "3.0 workdays" |
| **okr-coach** | Perdoo Premium €6.40/user (annual/quarterly only); Weekdone ~$9.86 | 3 / 4 / 0 / 1 | 4 KRs: progress/status/need-per-week; regression slope/R²/projection/hit date; check-in and scoring calendar | **AT PAR** on coaching and grading; tracking is out of scope | Period now inclusive (Q4 = 92 d; last-day need-rate was 0); stay-above/below KR types; holidays (scoring had landed on Jan 1) |
| **status-reporter** | Asana Starter $13.49 [$10.99] status updates; Weekdone | 4 / 1 / 1 / 2 | 4 metrics × (RAG, previous RAG, Δ); milestone slip with holidays; lint on a real draft | **AT PAR** | Milestone/week-over-week slips ignored holidays (5 wd instead of 3, contradicting project-planner); lint false positives (asks-before-progress, table read as a 30-word sentence) |
| **decision-matrix** | TransparentChoice (quote-only) | 4 / 2 / 0 / 1 | AHP weights (geo-mean exact, eigenvector ±0.0005), CR; totals; 4 flip points vs 0.01-step sweep; EV/σ/regret | **AT PAR** | Weight flips now exact (were integer steps, up to 0.65 pt off); smallest score flip rounded up (−0.04 would not flip); group AHP (geometric mean of judges) |
| **vendor-evaluator** | Vendr (median $47,000/yr) | 3 / 1 / 1 / 2 | RFP totals; 3-yr TCO and NPV (both conventions); notice deadline; SLA breach and credit | **AT PAR** on analysis; **BELOW** on price benchmarks (a data moat, can't be fixed here) | Notice deadline was 1 day late; missed-window case now gives the next deadline; SLA checked over the real calendar month; NPV billing timing stated; knocked-out vendors excluded from TCO; $1 rounding drift |

**Tests after the fixes:**
- `pytest -q tests/agents -k ops tests/scenarios/test_ops.py` → **103 passed**
- `pytest -q tests/test_library.py` → **303 passed**

**Issues outside my edit scope (described, not edited):**
- **`hundred/lib/text.py` `sentences()`** counts "Hi Dana," and "Best,\nAlex" as sentences, and turns a markdown table into one long "sentence". I worked around both inside inbox-triage and status-reporter. Any other agent that lints replies or reports with it will over-count the same way.
- **`hundred/admin.py brief`** throws a `BrokenPipeError` traceback when piped into `head`. Cosmetic.

**What a plain AI got wrong, observed in this session.** I made each of these mistakes myself while writing test expectations by hand, and the tools caught all three:
1. **PERT date.** I put the P50 end date of a 14.17-working-day chain on the 14th working day. It is the 15th.
2. **AHP weight.** I rounded 0.59054 to 0.5906.
3. **Portal calendar.** I first mapped the calendar from the wrong start week.

**Which bugs the tools had, and a plain AI working carefully would not.** These are bugs where the tool, not an unaided AI, would have misled the user:
- "EOD Thursday" resolved to Monday.
- A 31% meeting week reported as 58% RED.
- A contract notice deadline one day late.
- An SLA breach reported as "within SLA".

---

## 1. meeting-ops (free lead magnet) — vs Fireflies / Fathom / Otter

### Scenario

**A. Shipped sample.** `samples/standup_transcript.txt`: a Monday product sync. The date is not stated, so I assumed 2026-09-28.

**B. Messy Otter-style export I wrote.** A 6-person launch sync, 2026-10-07, in the format `Name  0:41` with the text on the next line. It contains:
- filler and crosstalk;
- a vendor decision after debate;
- a launch-date change that was proposed and then reversed;
- "someone should ping legal" (no owner);
- a runbook Carlos offered and Priya **reassigned** to Aisha;
- a commitment **retracted** mid-sentence ("scratch that");
- a hypothetical ("maybe someday rebuild the admin panel");
- deadline phrases: *EOD Thursday, Friday, Next Tuesday, Monday, October 15th, tomorrow, end of next week, once the fix is out*.

**Ground truth:** 9 real commitments, 3 decisions, 2 open questions and 1 noise line.

### Parity checklist

| # | Documented capability | Source | Hundred | Why |
|---|---|---|---|---|
| 1 | Meeting overview / 1-sentence gist | [Fireflies summary schema](https://docs.fireflies.ai/schema/summary) (`overview`, `gist`) | MATCHES | TL;DR section |
| 2 | Action items list | [Fireflies Super Summaries](https://fireflies.ai/blog/fireflies-launches-ai-super-summaries); [Fathom](https://www.fathom.ai/overview) | MATCHES | Commitment candidates → classified list; 9/9 recall |
| 3 | Assigns action items to participants | [Otter Action Items](https://help.otter.ai/hc/en-us/articles/25983095114519-Action-Items-Overview) (search snippet); Fathom "who they're assigned to" | MATCHES | Owner per item. Ambiguous owners become open questions, never auto-assigned |
| 4 | Decisions in the structured summary | [Fireflies pricing blog](https://fireflies.ai/blog/fireflies-pricing-which-plan-is-right-for-you): "Structured AI summary with topics, decisions, and Action Items" | MATCHES | New `decision_candidates` (3/3) |
| 5 | Keywords / topics | Fireflies schema `keywords`, `topics_discussed` | PARTIAL | The host AI writes a Topics line; no extraction tool |
| 6 | Timestamped outline / citations to the exact moment | Fireflies `outline`; Fathom "citations that link to the exact moment" | PARTIAL | A quote plus a line number per item; no link into a recording (there is none) |
| 7 | Speaker analytics: talk time, WPM, sentiment | Fireflies pricing blog | PARTIAL | Talk share only; no WPM or sentiment |
| 8 | Follow-up email draft | Fireflies "AI Skills"; Fathom "Draft recap emails" | MATCHES | In the output format; saved as a Gmail draft via the customer's connector |
| 9 | Push action items to Slack/Asana/Jira | Fireflies "AI Skills" | PARTIAL | Only through the customer's own connectors |
| — | Recording/transcription, cross-meeting AskFred, CRM field updates | Fireflies | OUT OF SCOPE | — |

Beyond parity: none of the three vendors' docs mention turning "Friday" or "EOD Thursday" into a calendar date. Ours does, and flags ambiguous "next X".

### Correctness

| Check | Ground truth | Before fix | After fix |
|---|---|---|---|
| Sample speakers | Priya, Marcus, Dana | + "Attendees" (2.9% talk share) | ✔ |
| Sample "by end of day Thursday" (Priya's exec update), meeting Mon 09-28 | Thu 2026-10-01 | **Mon 2026-09-28** (EOD matched first) | ✔ |
| "next Tuesday" said Wed 09-23 | Tue 09-29 | Tue 10-06 (13 days out) | ✔ (flags "confirm" when ambiguous) |
| Otter export speakers | 6 named people | 0. The old regex needs "Name: text", so every candidate was unattributed | ✔ 6 |
| Commitment recall, messy transcript | 9 lines | (unattributed) | 9/9; noise line not a candidate |
| Due dates, messy transcript | 10-08, 10-09, 10-13, 10-12, 10-15, 10-08, 10-16, none, 10-31 | "next Tuesday" 10-20; "October 15th" unrecognised | 9/9 |
| Reassignment / retraction | Aisha owns the runbook; the dashboard refresh is dropped | not surfaced | Both surfaced; playbook rule "the last word wins" |
| Invented items in the final list | 0 | — | 0. Two undated items flagged "no date — confirm" |

### Deliverable excerpt (messy transcript)

```
# Launch Sync — 2026-10-07
**Attendees:** Priya Shah, Jordan Lee, Mei Chen, Aisha Bello, Carlos Ruiz, Dev Patel · **Length:** ~5 min · **Talk share:** Priya 47%, Jordan 21%, Mei 9%, Aisha 8%, Carlos 8%, Dev 7%
**Topics:** SSO vendor, launch date, Acme renewal, cutover runbook, churn numbers
## TL;DR
Okta chosen for SSO, launch stays Oct 15, legacy dashboard is switched off at month end. 9 owned actions, 2 need dates.
## Decisions
- SSO is Okta, not Auth0 — _"Then let's go with Okta. Final call"_
- Launch stays Thu 2026-10-15 — _"let's keep the fifteenth"_
- Legacy analytics dashboard is retired on 2026-10-31; nobody refreshes it — _"Nobody refresh it."_
## Action items
| # | Task | Owner | Due | Source |
|---|---|---|---|---|
| 1 | Ship the SSO redirect-loop fix to staging | Jordan Lee | Thu 10-08 | "…by EOD Thursday" |
| 2 | Send Acme the renewal proposal (multi-year discount) | Mei Chen | Fri 10-09 | "…by Friday" |
| 3 | Write the migration cutover runbook | Aisha Bello | Tue 10-13 | reassigned from Carlos; "Next Tuesday" |
| 4 | Pull Q3 churn cohort numbers | Dev Patel | Mon 10-12 | "…by Monday" |
| 5 | Update the board deck with new churn numbers | Priya Shah | Thu 10-15 | "…by October 15th" |
| 6 | Book the load-test environment | Jordan Lee | Thu 10-08 | "…tomorrow" |
| 7 | Send Priya the deploy notes after the fix ships | Jordan Lee | no date — confirm | "once the fix is out" |
| 8 | Schedule the launch retro | Aisha Bello | Fri 10-16 | "end of next week" |
| 9 | Leave migration notes in the runbook doc | Carlos Ruiz | no date — confirm (before he is out 10-12) | "I'll just leave them in the doc" |
## Open questions
- Who owns legal review of Acme's DPA redlines? → suggested owner: Mei Chen
- Enterprise pricing: per-seat vs flat → suggested owner: Priya Shah, after the Acme numbers
```

### Honest gaps
- **Talk share.** It comes from word counts, not audio time. There are no WPM or sentiment figures.
- **Candidates are regex-driven.** A commitment phrased without any trigger ("the deck's on me") is only caught by the host AI's reading. The playbook tells it to read in context, but the tool will not surface such a line.
- **"Carlos is out next week."** The date conflict it creates for item 9 is left to the host AI's judgement; no tool checks it.

---

## 2. project-planner — vs Smartsheet

### Scenario
"Customer portal v2", as a project manager would hand it over:
- 12 tasks with finish-to-start dependencies, plus a zero-day go-live milestone;
- start Mon 2026-11-09;
- holidays: Thanksgiving Thu/Fri (Nov 26–27) and Christmas Day;
- PERT three-point estimates on the critical chain;
- a slip report as of 2026-11-30.

A second run uses a typed-link variant: `T5 = T2 SS+2`, `T10 = T5:FF+1`, `T11 = T8+2`.

### Parity checklist

| # | Capability | Source | Hundred | Why |
|---|---|---|---|---|
| 1 | Dependencies auto-calculate dates | [Smartsheet predecessors](https://help.smartsheet.com/articles/765727-enabling-dependencies-using-predecessors) | MATCHES | CPM forward/backward pass |
| 2 | FS / FF / SS / SF links with lag and lead | same | MATCHES (after fix) | Was FS-only. Now accepts `"T3 SS+2"`, `"T4:FF"`, `"T2+3"`, `"T5-2"` |
| 3 | Critical path highlighted | [Smartsheet critical path](https://help.smartsheet.com/articles/1979152-tracking-a-project-s-critical-path) | MATCHES | Also gives explicit total and free float, which the Smartsheet docs don't mention |
| 4 | Working days, non-working days, holidays | predecessors article | MATCHES | Plus custom work weeks (mon-thu) |
| 5 | Gantt view | predecessors article | PARTIAL | Text Gantt, not interactive |
| 6 | Baselines and variance in working days | [Smartsheet baselines](https://help.smartsheet.com/learning-track/project-fundamentals-part-2-project-settings/baselines-and-critical-path) | MATCHES | `slip_report` |
| 7 | Auto-update when dates change | critical path article | PARTIAL | Re-run on request; no live sheet |
| 8 | Hour, partial-day and elapsed ("e3d") durations | predecessors article | MISSING | Working days only (fractions are accepted) |

### Correctness

| Check | Independent value | Tool |
|---|---|---|
| Project length / critical path | 26 wd; T1→T3→T4→T7→T8→T11→T12 | ✔ |
| Total float | T2 3, T5 3, T6 9, T9 10, T10 8, rest 0 | ✔ all 12 |
| Free float | T2 **0** (TF 3), T9 10, T10 8 | ✔ |
| Plan end / T5 straddles Thanksgiving | Wed 2026-12-16 / 11-19 → 12-01 | ✔ |
| PERT E, σ, P80, P90 | 28.333, 2.186, 30.173, 31.135 | ✔ (rounded to 2 dp) |
| P(most-likely plan holds) | Φ((26 − 28.33)/2.186) = 14.3% | ✔ (new) |
| P50 / P80 / P90 dates | 12-21 / 12-23 / 12-24 | ✔ (new) |
| Slips (working days, holidays excluded) | 1, 0, 3, 5, 5 → AMBER | ✔ |
| Typed-link variant | project 28; T2 LF 14; T5 FF 0; T10 TF 15 | ✔ (hand-computed) |

**The misleading playbook item (fixed).** The Output format said `**End date (P50):**`, and step 3 said to use the schedule's dates verbatim. The schedule is built from most-likely durations, and here that date has only a **14%** chance of holding. The old `buffer_for_p80` (P80 − P50 = 1.8 d) also understated the buffer actually needed beyond the published plan: 4.2 days.

### Deliverable excerpt

```
# Customer portal v2 — plan (start 2026-11-09)
**Plan date (most-likely):** 2026-12-16 (14% chance) · **P50:** 2026-12-21 · **Commit (P80):** 2026-12-23 · **Working days:** 26 · **Critical path:** T1 → T3 → T4 → T7 → T8 → T11 → T12
| ID | Task | Owner | Days | Start | End | Float | Critical |
| T1 | Requirements sign-off | Priya | 3 | 2026-11-09 | 2026-11-11 | 0 | YES |
| T2 | UX design | Dana | 5 | 2026-11-12 | 2026-11-18 | 3 |  |
| T4 | Backend build | Marcus | 8 | 2026-11-16 | 2026-11-25 | 0 | YES |
| T5 | Frontend build (spans Thanksgiving) | Lena | 7 | 2026-11-19 | 2026-12-01 | 3 |  |
| T7 | Data migration scripts | Marcus | 5 | 2026-11-30 | 2026-12-04 | 0 | YES |
| T11 | UAT with pilot customers | Priya | 4 | 2026-12-11 | 2026-12-16 | 0 | YES |
Backend build*         2026-11-16 2026-11-25 ·······██████████·····················
Frontend build         2026-11-19 2026-12-01 ··········█████████████···············
Data migration scri*   2026-11-30 2026-12-04 ·····················█████············
## Buffer
Plan = 26 d, chain P50 = 28.3 d, σ = 2.2 → P80 = 30.2 d: 4.2-day buffer after UAT, commit to Dec 23.
## Slip report (as of 11-30): AMBER — Backend +3 wd (Dec 2), go-live forecast Dec 23 (+5 wd).
```

### Honest gaps
- No resource levelling: owner overload is not checked.
- No interactive Gantt.
- No elapsed-time durations.
- The Gantt is text and is capped at 120 columns.

---

## 3. time-blocker — vs Reclaim.ai

### Scenario
- **Convert a time in the DST gap week.** Tue 2026-10-27 10:00 New York → London, Berlin, Sydney, Bangalore. Europe left DST on Oct 25; the US leaves on Nov 1.
- **Find a 30-min slot** for SF, London and Bangalore on Oct 27 and on Nov 3.
- **Plan a day.** 7 tasks around 3 meetings, with peak hours 08:00–11:00 and a prep task that must happen before a 13:00 call.
- **Audit a week** (Oct 19–23) with 22 real-looking events, including two self-booked focus blocks, a meeting-free Friday, and an all-day item exported as 00:00→00:00.

### Parity checklist

| # | Capability | Source | Hundred | Why |
|---|---|---|---|---|
| 1 | Auto-schedule tasks by priority before due dates | [Reclaim features](https://help.reclaim.ai/en/articles/6210740-features-in-reclaim); [Tasks](https://help.reclaim.ai/en/articles/5108936-tasks-overview) (search snippet) | PARTIAL | Priorities, plus `due_by` time-of-day (new). Plans one day, not multi-day due dates |
| 2 | Break long tasks into chunks (min/max duration) | Tasks overview | MATCHES | ≤ max block, no deep block under 25 min (fixed) |
| 3 | Weekly focus-time goal, defended automatically | features | PARTIAL | Plans and audits focus; can't defend it in the background |
| 4 | Buffer time between meetings | features | MATCHES | `buffer_minutes` |
| 5 | Meeting scheduling across working hours and time zones | [Smart Meetings](https://reclaim.ai/features/smart-meetings) (search snippet) | PARTIAL | DST-correct slot search with ranked compromises; can't read other people's calendars without a connector |
| 6 | Stats: where time goes | features | MATCHES | `audit_calendar` gives load, fragmentation, focus blocks and category mix |
| — | Habits auto-scheduling; calendar sync; Slack status | features | OUT OF SCOPE | Background automation |

### Correctness

| Check | Independent (stdlib zoneinfo / brute force / hand) | Tool before → after |
|---|---|---|
| NY 10:00 Oct 27 → London / Berlin / Sydney / Bangalore | 14:00 / 15:00 / **Wed** 01:00 / 19:30 | ✔ / ✔ |
| Best SF–London–Bangalore slot, Oct 27 | 14:00 UTC (SF 07:00, Arjun 19:30), pain 2 | ✔ |
| Same on Nov 3 (after US DST ends) | no 07:00–20:00 overlap | ✔ |
| 2026-11-01 01:30 New York | ambiguous (happens twice) | silently EDT → **warning** |
| Week meeting minutes Mon–Fri | 195, 160, 240, 240, 0 = 835 min = 30.9% AMBER | **25.9 h, 58% RED** → ✔ |
| Fragments < 30 min / back-to-back | 3 / 5 | 4 / 6 → ✔ |
| Prep task before 13:00 call | must end ≤ 13:00 | 14:10–14:40 → 11:45–12:15 |
| Deep blocks ≥ 25 min | yes | 5-min sliver at 09:35 → none |

### Deliverable excerpt (calendar audit + day plan)

```
## Calendar audit (Oct 19–23, work 09:00–18:00)
Meeting load: 31% (AMBER) · 13.9 h of 45 h · Fragments: 3 gaps < 30 min · Back-to-back: 5 · Focus you booked yourself: 3 h
Worst days: Wed & Thu (240 min). Meeting-free: Fri 10-23 (keep it). All-day "Team offsite prep" ignored.
Top 3 changes: 1. Wed 10:00–11:45 is three back-to-back meetings (vendor demo, design review, partner sync) — move two to the afternoon band.
2. Switch to 25/50-min meetings: 5 zero-gap transitions this week. 3. Move Thursday's 09:30 standup + 09:45 pricing workshop so the morning stays open.

# Tue 2026-10-27 — plan (work 08:00–17:30, peak 08:00–11:00)
| 08:00–09:30 | Focus: Write Q4 board memo (1/2) | deep | P1 |
| 10:00–10:30 | Standup | meeting | |
| 10:40–11:40 | Focus: Write Q4 board memo (2/2) | deep | P1 |
| 11:45–12:15 | Prep for Acme call | shallow | P1, before 13:00 |
| 12:15–12:45 | Lunch | | |
| 13:00–14:00 | Acme customer call | meeting | |
| 14:10–14:55 | Focus: Review Acme contract redlines | deep | P1 |
**Focus time:** 4h 10m · **Meetings:** 2h (21%) · **Unscheduled:** 5 min of competitor teardown → Wed
## Meeting slot (SF · London · Bangalore, 30 min): no slot inside everyone's hours.
Least painful: Tue 10-27 14:00 UTC = Maya 07:00 PDT / Tom 14:00 GMT / Arjun 19:30 IST. From Nov 3 there is no overlap at all → go async.
```

### Honest gaps
- Plans one day at a time; it does not spread tasks across a week toward due dates.
- Can't read attendees' free/busy without a calendar connector.
- Nothing re-plans automatically when the day changes.

---

## 4. inbox-triage — vs Superhuman

### Scenario
Founder alex@northwind.io has 15 emails on Tue 2026-09-29. VIPs: the board investor (harborvc.com), key customer acme.com, and cofounder Jamie. The inbox contains:
- a board deck request ("by Thursday");
- an SSO outage complaint from a customer ("need an answer today");
- a cofounder asking to approve an offer ("EOD tomorrow");
- a vendor renewal ("confirm by October 15", 12% increase);
- a coffee invite;
- a missing-receipts request from accounting;
- a cold recruiter pitch;
- a customer's "Thanks, that worked!";
- a CC'd FYI;
- GitHub, AWS billing, Google Calendar and Okta notifications;
- two newsletters.

**Labels.** I (the evaluator) labelled all 15 as an EA would.

**Caveat.** I wrote the labels after the first run, so the fixed rules could be overfitted. To counter that, the fixes are generic rules (not tuned per email) and have separate unit tests on different emails.

### Parity checklist

| # | Capability | Source | Hundred | Why |
|---|---|---|---|---|
| 1 | Split important from the rest (VIPs, team, newsletters) | [Superhuman AI](https://superhuman.com/ai); search snippet on Split Inbox | MATCHES | Scored 0–100 with named reasons, sorted into action buckets |
| 2 | Auto Labels: marketing, **cold pitches**, social, needs response | superhuman.com/ai | MATCHES (after fix) | Cold outreach was scored 65 "Reply today"; now archived |
| 3 | Auto Archive | superhuman.com/ai | PARTIAL | Decides; the archiving itself needs the mail connector |
| 4 | 1-line summary per conversation | superhuman.com/ai "Auto Summarize" | MATCHES | Host AI plus `extract_asks` (asks, deadline) |
| 5 | Instant Reply / Write with AI in your voice | superhuman.com/ai | PARTIAL | Drafts with a template QA; no learned personal style |
| — | Auto Reminders, Ask AI across inbox + calendar, Smart Scheduling | superhuman.com/ai | OUT OF SCOPE | Background, or needs a mailbox index |

### Correctness

| Check | Truth | Before | After |
|---|---|---|---|
| Actions (15 emails) | 3 reply now, 3 today, 7 archive, 2 unsubscribe | 10/15 (cold pitch "Reply today" 65; VIP thanks "Reply today"; coffee, renewal and receipts "Reply now" while tagged Q2) | **15/15** |
| Deadlines | Thu 10-01, today 09-29, 09-30, 10-15, Fri 10-02 | "by October 15" unresolved (no month names) | 5/5 |
| Reply-now order | outage (today) → offer (tomorrow) → deck (Thu) | same | same |
| 4-sentence reply with greeting and sign-off | 4 sentences, ready | 6 → "Not ready" | 4 → ready |
| 30-min session | outage, deck, receipts (2-min rule), renewal; offer flagged "later today" | same | same |

### Deliverable excerpt

```
# Inbox triage — Tue 2026-09-29, 15 emails, ~47 min of work
**Reply now (≥70)**
| # | From | Subject | Why | Ask | Deadline | Min |
| 2 | Dana White (Acme, VIP) | SSO outage this morning | VIP, direct, due today | root cause + SLA credit? | today | 15 |
| 5 | Jamie (cofounder) | Offer — approve? | VIP, money, competing offer | approve $185k | Wed 09-30 EOD | 15 |
| 1 | Sarah Kim (board) | Board deck | VIP, 2 questions | send Q3 deck; still on for the 8th? | Thu 10-01 | 5 |
**Reply today (45-69 or no deadline pressure)**
- Brightline renewal (+12%) → task "Counter at ≤5% cap" due 10-13, reply today to acknowledge
- Coffee next week (Tom Reyes) · Missing receipts → do by Fri 10-02
**Archive:** 7 (cold recruiter pitch, VIP thanks-only, CC FYI, GitHub, AWS invoice, calendar invite, Okta sign-in)
**Unsubscribe/digest:** Lenny's Newsletter, SaaStr Events
## Drafts
### Re: SSO outage this morning (to Dana)
Hi Dana, Thanks for flagging this, and sorry for the disruption. Root cause: an expired SAML signing certificate on our side, fixed at 9:32. The 90 minutes count toward your SLA; the credit will appear on your next invoice. I will send the written incident report by Thursday, Oct 1. Best, Alex
## Session plan (30 min)
1. [2] Receipts → 2. [15] SSO outage → 3. [5] Board deck → 4. [5] Brightline · Offer approval (15 min, due tomorrow) right after the session.
```

### Honest gaps
- The minute estimates are heuristic. "Upload 3 receipts" is estimated at 2 minutes.
- Nothing follows up automatically.
- Style matching depends on the host AI.

---

## 5. sop-writer — vs Scribe

### Scenario
Refund processing for a support team. The inputs are:
- a first-draft SOP written from voice-memo notes, with 7 steps containing planted defects: narration, a missing else-branch, two actions in one step, an irreversible refund with no verification, and "should … as needed";
- a revised 10-step draft;
- a RACI with two invalid rows;
- touch and wait times per step;
- a v1.3 → v2.0 major revision with a 6-month review, effective 2026-10-01, plus an edge case effective 2026-08-31.

### Parity checklist

| # | Capability | Source | Hundred | Why |
|---|---|---|---|---|
| 1 | Step-by-step guide generated from a process | [Scribe SOP](https://scribe.com/lp/sop) | MATCHES | From notes or a transcript, not screen capture |
| 2 | Auto-captured, annotated screenshots | [Scribe guides](https://scribe.com/lp/guides) (search snippet) | OUT OF SCOPE | — |
| 3 | AI-generated titles, descriptions, contents | Scribe guides | MATCHES | — |
| 4 | Alerts / tips inside steps | Scribe guides | PARTIAL | Exceptions and escalation table; no inline tip blocks |
| 5 | Redact/blur sensitive info in screenshots | Scribe guides | OUT OF SCOPE | — |
| 6 | Share/export (link, PDF, HTML, Markdown, Notion/Confluence) | Scribe SOP + guides | PARTIAL | Markdown plus the customer's connectors; no PDF |
| 7 | Discovers frequently-run workflows | Scribe SOP | OUT OF SCOPE | — |

Beyond parity: step lint, RACI validation, cycle time/PCE and review dates. None of these appear in Scribe's docs.

### Correctness

| Check | Truth | Tool |
|---|---|---|
| Draft defects flagged | steps 2, 3, 4, 5 plus the irreversible refund in step 4 | 4/4 steps. The irreversible flag was **missed before the fix**: "Support agent:" wasn't parsed as an actor and "Issue the refund" wasn't matched |
| Revised draft score | ≥ 85 | 88 |
| Touch / lead / PCE / handoffs | 18 / 1,728 min / 1.04% / 2 | ✔ |
| Human label for a 1,440-min wait | 1.0 day | **"3.0 workdays"** → "1.0 days" |
| Next review date | 2026-10-01 + 6 mo = 2027-04-01 (186 d); 2026-08-31 + 6 mo = 2027-02-28 (154 d) | ✔ |
| RACI | 2 invalid rows (C+I same person; 2 Accountable) + Support lead bottleneck (60%) | ✔ |

### Deliverable excerpt

```
# SOP-CS-CUSTOMER-REFUND-PROCESSING: Customer refund processing   v2.0 · Owner: Support lead · Effective: 2026-10-01 · Review by: 2027-04-01
**Purpose** Refund eligible orders the same day without paying out ineligible or unapproved refunds.
**Trigger** Refund request ticket in Zendesk → **End state** Stripe shows Refunded, customer notified, ticket Solved.
## Procedure
1. Support agent: Open the refund request in Zendesk.
2. Check the order date in Shopify → Orders.
3. If the order is 30 days old or less: go to step 5. Otherwise: go to step 4.
4. Assign the ticket to the Support lead with the macro Refund-over-30-days. Stop here.
5. If the refund is over $500: go to step 6. Otherwise: go to step 7.
6. Finance: Approve the refund in the Zendesk approval field within 1 business day.
7. Issue the refund in Stripe → Payments → Refund.
8. Verify that Stripe shows the payment status Refunded.
9. Send the customer the Refund-confirmed macro in Zendesk.
10. Set the ticket to Solved with tag refund-processed.
## Cycle time
Lead time ~1.2 days (touch 18 min, wait 1.2 days, PCE 1.0%, 2 handoffs). Biggest wait: Finance approval (1.0 days) → pre-approve refunds ≤ $1,000.
## RACI (fix before publishing): reconciliation has 2 Accountable (Finance lead, CFO) — pick one; Finance is both C and I on exceptions.
```

### Honest gaps
- No screenshots; that is Scribe's main value.
- The linter is regex-based. It still flags "Send the customer…" as needing a verify step, which is defensible but strict.

---

## 6. okr-coach — vs Perdoo

### Scenario
A growth team's Q4 2026 OKRs:
- **Draft set:** one bad objective ("Launch the new onboarding flow and grow revenue 30%") and one good one.
- **Grading:** 4 KRs graded on 2026-11-13, including a "decrease" KR.
- **Forecast:** 7 weekly activation readings projected to Dec 31.
- **Cadence:** check-in calendar with holidays.
- **Guardrail:** a "stay above" KR (gross margin ≥ 75%).

### Parity checklist

| # | Capability | Source | Hundred | Why |
|---|---|---|---|---|
| 1 | AI coach sharpens objectives and tightens KRs | [perdoo.com](https://www.perdoo.com/) (search snippet: AI Coach "Vince") | MATCHES | `lint_okrs` plus the rewrite pattern |
| 2 | KR target types: increase, decrease, stay at or above/below, binary, milestone | [Perdoo: Add Key Results](https://support.perdoo.com/en/articles/1588530-add-key-results) | PARTIAL | Increase, decrease and stay above/below (new). Binary and milestone are deliberately flagged as anti-patterns |
| 3 | Status auto-set from progress vs expected progress | [Perdoo goal statuses](https://support.perdoo.com/en/articles/4640875-goal-statuses) | MATCHES | Explicit thresholds (Perdoo publishes none) |
| 4 | 3–5 KRs per objective guidance | Add Key Results | MATCHES | — |
| 5 | Weekly check-ins | perdoo.com (search snippet) | PARTIAL | Cadence calendar; check-ins aren't collected or stored |
| 6 | Progress dashboards / reports | perdoo.com | PARTIAL | Markdown tables |
| 7 | Strategy map / alignment | perdoo.com | PARTIAL | Playbook cascade check only |
| — | Team workspace, 1:1s, reviews | perdoo.com | OUT OF SCOPE | — |

### Correctness

| Check | Independent | Tool |
|---|---|---|
| Period / elapsed / weeks left | 92 days / 46.74% / 7.0 | ✔ (was 91 d; on Dec 31 need-per-week was **0**) |
| Activation 31→45, now 37 | 42.9%, on track, 0.4, need 1.14/wk vs 0.98 | ✔ |
| MRR 180→240, now 196 | 26.7%, at risk, need 6.29/wk | ✔ |
| First response 9h→4h, now 8 | 20.0%, off track | ✔ |
| Forecast | slope 1.0/wk, R² 0.985, 44.07 at Dec 31, hits 45 on 2027-01-06 → misses | ✔ |
| Scoring day with holidays | first working day after Dec 31 = Mon 2027-01-04 | was Fri **2027-01-01** (New Year's Day) → ✔ |
| Lint score | O1 52, O2 100 → 76 | ✔ |

### Deliverable excerpt

```
# OKRs — Growth, Q4 2026            Lint score: 76/100 → rewrite O1
## O1: Make self-serve onboarding effortless   (supports company KR: net new ARR)
| KR | Type | Baseline → Target | Current | Progress | Status | Score |
| KR1.1 Increase week-1 activation from 31% to 45% | aspirational | 31 → 45 | 37 | 42.9% (time 46.7%) | on track | 0.4 |
| KR1.2 Grow MRR from $180k to $240k | committed | 180 → 240 | 196 | 26.7% | at risk | 0.3 |
**Rewrites**
- ~~Launch the new onboarding flow and grow revenue 30%~~ → **Make self-serve onboarding effortless** — project + number + two goals in one
- ~~Launch onboarding v2~~ → initiative feeding KR1.1 · ~~Hire 2 growth engineers~~ → initiative
## O2: Make support feel instant for every customer
| KR2.1 Reduce median first response from 9h to 4h | committed | 9 → 4 | 8 | 20.0% | off track | 0.2 |
## Recovery actions
- KR1.1: "on track" by the 10-pt rule, but the trend (R² 0.98) lands at 44.1 on Dec 31 → add one activation experiment/week (owner PM, from Nov 16).
- KR1.2: need 6.3k/wk vs 2.6k/wk achieved (2.4×) → propose descope to $220k or a pricing change by Nov 20.
- KR2.1: need 0.57 h/wk faster, running 0.16 → add weekend coverage rota (Support lead, Nov 16).
## Cadence
Check-ins: Mondays Oct 5 … Dec 28 (13) · Mid-cycle review: Nov 16 · Draft next: Dec 9–23 · Score: Mon 2027-01-04 · Retro: 2027-01-07
```

### Honest gaps
- Nothing stored between sessions: no history, no dashboards.
- Binary and milestone KRs are not graded as their own types.

---

## 7. status-reporter — vs Asana status updates (and Weekdone)

### Scenario
The Friday exec update for "Portal v2", week of 2026-11-20. It uses the same project calendar as §2:
- 4 metrics with last week's values, two of them lower-is-better;
- milestones including the Thanksgiving week;
- last week's vs this week's task list: shipped, slipped, added, dropped, stale;
- a 233-word draft to lint.

### Parity checklist

| # | Capability | Source | Hundred | Why |
|---|---|---|---|---|
| 1 | On track / at risk / off track statuses | [Asana status updates](https://asana.com/features/project-management/status-updates) | MATCHES | Computed RAG with explicit thresholds |
| 2 | AI suggests the status from project data (completion, overdue, milestones) | same page; [Smart Status](https://help.asana.com/s/article/smart-status) (search snippet) | PARTIAL | From supplied metrics, milestones and items; live data needs a connector |
| 3 | AI-drafted update | Asana status updates | MATCHES | — |
| 4 | Auto-generated charts | Asana status updates | MISSING | Tables only |
| 5 | Reusable templates | Asana status updates | MATCHES | Fixed output format |
| 6 | Embedded task lists (completed / in progress) | Asana; [Weekdone](https://weekdone.com/weekly-progress-reporting-software) PPP | MATCHES | `week_over_week` |
| — | Posting reminders; multi-user comments | Asana | OUT OF SCOPE | — |

### Correctness

| Check | Hand | Tool |
|---|---|---|
| Sign-ups 34/40, prev 28 | 85.0% AMBER (prev 70% RED) | ✔ |
| P1 bugs ≤5, now 9, prev 12 (lower is better) | 5/9 = 55.6% RED | ✔ |
| Coverage 78/80; p95 1450 vs ≤1500 ms | 97.5% GREEN; 103.4% GREEN | ✔ overall RED, 3 RAG changes |
| Backend 11-25 → 12-02 slip | 3 wd (Thanksgiving excluded) | **5 wd** → 3 wd (now matches project-planner) |
| Lint of a correct draft | asks come before progress; no sentence > 30 words | "asks after progress" (matched "shipped" in the TL;DR) and table read as a sentence → 100/100 |

### Deliverable excerpt

```
**Portal v2 — week of 2026-11-20 — 🔴 RED** (last week: 🟡 AMBER)
**TL;DR**
- Okta SSO shipped; pilot sign-ups 34 of 40 (+6 vs last week).
- Backend build slipped 3 working days to Dec 2, which pushes go-live from Dec 16 to Dec 23.
- Open P1 bugs are 9 against a target of 5 (down from 12): we need one more engineer on bug triage.
**Asks / decisions needed**
- Approve moving Lena from docs to P1 triage for 2 weeks — by Nov 24 — from Priya.
- Confirm the Dec 23 go-live with the two pilot customers — by Nov 25 — from Mei.
**Progress**
| Metric | Target | This week | Last week | Δ | RAG |
| Pilot sign-ups | 40 | 34 | 28 | +6 | AMBER |
| Open P1 bugs | ≤5 | 9 | 12 | -3 | RED |
- Shipped: Okta SSO. Slipped: Backend build (+3 wd). Added: Frontend build. Dropped: pricing page copy.
**Risks & issues**
- 🔴 Issue: 9 open P1 bugs; UAT cannot start; mitigation: Lena on triage; owner Marcus; review Nov 27.
- 🟡 Risk: security review not started, due Nov 24; owner Raj; start Monday.
```

### Honest gaps
- No charts.
- Project data only arrives if the user pastes it or a connector supplies it.
- `week_over_week` matches items by exact name, so a renamed task shows up as removed plus added.

---

## 8. decision-matrix — vs TransparentChoice (AHP decision software)

### Scenario
Where should a US-customer SaaS company open its second office: Lisbon, Austin, Toronto, or stay remote-only (the "do nothing" option)?
- **Weights:** set by AHP pairwise judgements.
- **Scores:** raw cost per engineer ($95k–$175k) normalised, plus 1–5 scores on the other criteria.
- **Stress test:** sensitivity check on the result.
- **Lease decision:** a 3-year lease vs 12-month coworking, compared on EV and regret.

### Parity checklist

| # | Capability | Source | Hundred | Why |
|---|---|---|---|---|
| 1 | Pairwise comparisons → criteria weights | [TransparentChoice AHP](https://www.transparentchoice.com/ahp-software) | MATCHES | — |
| 2 | Consistency ratio check | same | MATCHES | Also names the worst triad |
| 3 | Sensitivity analysis | same | MATCHES (after fix) | Exact flip points |
| 4 | Weighted scoring of alternatives | same | MATCHES | Plus dominance detection |
| 5 | Group decision-making | same | PARTIAL | Geometric-mean aggregation of several judges (new); no workshop or voting UI |
| 6 | Visualisations (matrices, efficient frontiers) | same | PARTIAL | Tables |
| — | "Pick many" portfolio optimisation | same | OUT OF SCOPE | A different job |

**Price.** TransparentChoice publishes no price ("book a call").

### Correctness

| Check | Independent | Tool before → after |
|---|---|---|
| AHP weights | geo-mean 0.4668 / 0.1603 / 0.2776 / 0.0953 (eigenvector 0.4673 / 0.1601 / 0.2772 / 0.0954); λ 4.031; CR 0.0115 | ✔ |
| Totals | Austin 80.16, Toronto 79.74, Remote 72.64, Lisbon 64.67 | ✔ |
| Weight flip points (0.01-step sweep) | Talent 45.54, Cost 16.83, TZ 11.05, QoL 11.38 | 45 / 17 / 11 / 12 (integer steps; distances overstated by up to 0.65 pt) → 45.5 / 16.8 / 11.1 / 11.4 |
| Smallest score flip | Austin Talent −0.045 | −0.04 (would not flip) → −0.05 |
| Equal weights | Toronto | ✔ |
| EV / σ / max regret | lease 195k / 307,774 / 550k; coworking 169k / 105,399 / 150k → EV and regret disagree | ✔ |

### Deliverable excerpt

```
# Decision: Where do we open office #2 to hire senior engineers who overlap US customers, by Q2 2027?
**Type:** hard to reverse (lease) · **Default if no decision:** stay remote-only · **Decide by:** 2026-10-15
## Scoring (weights locked first, via AHP; CR 0.01)
| Criterion (w%) | Lisbon | Austin | Toronto | Remote-only |
| Talent pool (47%) | 3 | 5 | 4 | 4 |
| Cost (16%, $95k–175k normalised) | 5 | 0 | 2.2 | 3.4 |
| Time-zone overlap (28%) | 2 | 5 | 5 | 3 |
| Quality of life (10%) | 5 | 3 | 4 | 4 |
| **Total /100** | 64.7 | **80.2** | 79.7 | 72.6 |
## Robustness
Margin 0.4 pts — CLOSE CALL, FRAGILE. Flips to Toronto if Talent drops 1.1 pts (to 45.5%), Cost rises 0.8 pts, or QoL rises 1.8 pts. Equal weights → Toronto.
## Recommendation
Toronto and Austin are tied within judgement error; pick on one fact: run a 2-week sourcing test in both (target 20 qualified senior applicants each).
Whichever city wins: take 12-month coworking, not a 3-year lease — lease EV +$195k vs +$169k, but a 10% downturn costs $600k
(max regret $550k vs $150k). Revisit the lease on 2027-09-30 if headcount there reaches 12.
```

### Honest gaps
- There is no group-workshop flow: the host AI has to collect each person's judgements.
- No charts.
- The criteria still come from the user; the tool can't tell you whether they are the right ones.

---

## 9. vendor-evaluator — vs Vendr

### Scenario
Choosing a helpdesk for 60 support agents growing 20%/yr. The inputs are:
- **RFP:** 7 weighted criteria and 3 must-haves (SSO, SOC 2 Type II, EU residency). SupportHub has SOC 2 Type I only; Helply's EU residency is "unverified".
- **TCO:** a 3-year TCO with implementation, internal hours, training, escalators and exit cost.
- **Contract:** the incumbent's order form: start 2025-12-01, 12 months, auto-renews, **60-day** notice, 9% price cap, 99.5% SLA with 5%/10% credits, liability capped at 6 months, unilateral changes, net-15.
- **SLA:** a 218-minute outage in November 2026.

### Parity checklist

| # | Capability | Source | Hundred | Why |
|---|---|---|---|---|
| 1 | Extract pricing, commercial terms, renewal dates | [Vendr contract analysis](https://www.vendr.com/contract-analysis) | MATCHES | The host AI extracts, the tool computes |
| 2 | Track renewal dates and notice periods | Vendr contract analysis; search snippets | MATCHES (after fix) | Exact deadline, send-by date, next cycle if missed. No background reminders |
| 3 | Evaluate special terms and risks | Vendr contract analysis | MATCHES | Ranked red flags with asks |
| 4 | Price benchmarks (35,000+) | Vendr (search snippets) | MISSING | No pricing dataset. This is Vendr's moat and can't be fixed here |
| 5 | Negotiation anchors, acceptable price ranges | Vendr contract analysis | PARTIAL | Generic levers and thresholds; no market data |
| — | Negotiates for you; agreement portfolio and spend view | Vendr | OUT OF SCOPE | — |

Beyond parity: must-have knockouts, weighted RFP scoring, TCO/NPV and SLA math. The Vendr page does not document these.

### Correctness

| Check | Independent | Tool before → after |
|---|---|---|
| RFP totals | Helply 78.0, DeskPro 76.0, SupportHub 85.0 (OUT) | ✔ |
| 3-yr totals | SupportHub 181,082; Helply 191,744; DeskPro 244,518 | +$1 drift (sum of rounded years) → ✔ |
| NPV at 8% | advance: 165,238 / 175,254 / 222,738; arrears: 154,369 / 165,840 / 213,742 | Arrears only, convention not stated → default advance, convention stated |
| Notice deadline ("60 days prior to the end of the term", term ends 2026-11-30) | **Thu 2026-10-01**, 4 days left | Fri 10-02, 5 days, "set reminders 30 and 7 days before" → ✔ 10-01, send by 09-28 |
| Missed window (start 2025-11-15) | deadline 2026-09-15 passed; next 2027-09-15 | "PASSED" only → next deadline given |
| 218-min outage, Nov 2026 (30 d) | 99.4954% → breach, 5% = $120 vs $5,450 loss | **"within SLA", $0** → ✔ |

### Deliverable excerpt

```
# Vendor selection — Helpdesk (2026-09-27)
**Recommendation:** Helply, if EU residency is verified in writing by Oct 9 · **3-yr TCO:** $191,744 (NPV $175,254) · **Score:** 78.0 vs DeskPro 76.0 · **Decide by:** 2026-10-15
## Must-haves: SupportHub OUT (SOC 2 Type I only) · Helply ⚠ EU residency claimed, not verified
## 3-year TCO (60 seats +20%/yr, 8%, annual in advance)
| | Helply | DeskPro | (SupportHub, ref.) |
| Year 1 / 2 / 3 | 65,280 / 54,300 / 72,165 | 95,080 / 61,269 / 88,170 | 50,880 / 57,905 / 72,297 |
| Total (NPV) | 191,744 (175,254) | 244,518 (222,738) | 181,082 (165,238) |
| Hidden-cost share | 28% | 46% | 12% |
DeskPro has the lowest sticker price but the highest TCO: implementation + 20 h/month admin.
## Incumbent contract — act this week
Cancellation notice deadline: **Thu 2026-10-01** (60 days before the term's last day, 11-30) — 4 days. Send written notice by Mon 09-28.
Top asks if you stay: 1. Liability cap 6 → 12 months ($14,400 today) 2. Remove unilateral term changes 3. Price cap 9% → ≤5% 4. Termination for convenience 5. Net-30
## SLA in plain terms
99.5% = 216 min allowed in November (30 d). November's 218-min outage = 99.495% → BREACH: credit 5% = $120 vs ~$5,450 outage cost (2.2% covered).
Scope note: not legal advice; route liability and unilateral-change clauses to counsel.
```

### Honest gaps
- No price benchmarks or negotiation data. This is the one BELOW that we can't close in software.
- Renewal reminders depend on the customer's calendar connector.

---

## Files changed

**Agents** (`hundred/agents/ops/`):
- `_common.py`: shared date resolver
- `meeting_ops.py`
- `project_planner.py`
- `time_blocker.py`
- `inbox_triage.py`
- `sop_writer.py`
- `okr_coach.py`
- `status_reporter.py`
- `decision_matrix.py`
- `vendor_evaluator.py`

**Tests:**
- `tests/agents/test_ops_*.py`: 9 files, with new and updated unit tests
- `tests/scenarios/test_ops.py`: new, 16 replayable scenarios
