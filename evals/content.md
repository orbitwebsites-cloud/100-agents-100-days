# Content & Writing: evaluation against paid comparables

Evaluated 2026-09-27. There are 9 agents in `hundred/agents/content/`. The copy-editor is free and serves as the lead magnet.

**Method.** For each agent:
1. Pick the most-overlapping paid tool from `marketing/pricing_research/content_seo_creator.md` and build a parity checklist from that tool's own documentation (cited).
2. Write a realistic input and run it the way a customer's AI would: `brief`, then each tool in playbook order, then the deliverable.
3. Check every number independently: hand counts, Flesch scores from dictionary syllable counts, arithmetic timestamps, and a from-the-spec X counter. That counter was cross-checked against twitter-text's own conformance suite.
4. Fix what was wrong.
5. Save the scenario as a replayable test in `tests/scenarios/test_content.py` (28 tests).

We could not run the competitors, so "MATCHES" means we produce the same documented output. It does not mean we produce it better.

Features that need integrations Hundred doesn't have are **OUT OF SCOPE**, not failures. That covers posting, scheduling, analytics, UI previews, audio/video, hosted brand-voice storage and plagiarism indexes.

## Overview

| Agent | Comparable & price | Checklist (M / P / Missing / OOS) | Correctness checks passed | Verdict | Fixes made |
|---|---|---|---|---|---|
| copy-editor (free) | Grammarly Pro $30/mo ($12 annual-eq); Hemingway Plus $10 as the readability reference | 7 / 3 / 0 / 1 | 14/14 after fixes (7/14 before) | **AT PAR** on the line-edit job; **BELOW** Grammarly on exhaustive spelling and grammar detection (no dictionary or parser) | Every correct capital "I" was flagged as an error. Missed its/it's, agreement and stray-article errors. Added about 95 common misspellings. US/UK variant is now judged from the original. "rather than" was counted as a hedge. Spelling out "3" as "three" raised a false "lost number" warning. Added Grammarly's own conciseness examples. Playbook now requires a grammar read-through. |
| blog-writer | Jasper Pro $69/seat ($59 annual-eq) | 5 / 1 / 0 / 1 | 9/9 after fix (6/9 before) | **ABOVE** | "Keyword in first 100 words" passed whenever the H1 had the keyword. Headings were being read as sentences. |
| x-thread-builder | Typefully Creator $19/mo ($12.50) | 5 / 1 / 0 / 2 | 22/22 twitter-text conformance cases (17/22 before) + 5/5 scenario checks (2/5 before) | **AT PAR** | New X counter: NFC; flag = 2 (was 4); bare domains like `acme.io/x` = 23; keycaps; tag-sequence flags; labels over 63 chars aren't URLs; trailing "." isn't part of the link. Lint and hook scoring now see bare-domain links. |
| linkedin-ghostwriter | AuthoredUp Individual $19.95/mo | 4 / 1 / 0 / 2 | 7/7 after fixes (4/7 before) | **AT PAR** (ABOVE on lint) | `format_post` duplicated hashtags and left six on the last line. A weak "Thoughts?" close went unflagged when hashtags followed it. Added Unicode bold (AuthoredUp parity), `max_hashtags`, and the confession hook type. |
| newsletter-editor | beehiiv Scale (first plan with AI) ~$49/mo ($43); overlap Low | 2 / 1 / 0 / 3 | 10/10 after fixes (5/10 before) | **AT PAR** on the editing slice | `tag_links` re-encoded existing query strings (`%20` became `+`, `,` became `%2C`) while claiming to preserve them. A partially tagged link counted as tagged. Issue numbers ("#58") scored as specificity. No greeting-intro flag. |
| youtube-scripter | vidIQ Boost $39/mo ($16.58) | 4 / 2 / 0 / 2 | 9/9 after fixes (7/9 before) | **AT PAR** (ABOVE on timing, BELOW on title search data) | A final chapter under 10 s passed as valid (YouTube requires ≥ 10 s). Chapters rebuilt from rounded durations drifted 1 s. Added `script_timing.chapters`. |
| case-study-writer | Jasper Pro Case Study agent ($59–69) | 5 / 1 / 0 / 1 | 10/10 after fixes (5/10 before) | **ABOVE** | Payback got *shorter* when a one-time cost was added (two inconsistent models). 62.5% rounded to 62% (banker's rounding). Hours got a "small base" warning. Lower-is-better metrics were phrased as "cut 7.9x". Absolute phrases lacked the metric name. "1 months". |
| content-repurposer | Castmagic Hobby $239/yr ($19.92) | 2 / 1 / 0 / 4 | 6/6 after fixes (3/6 before) | **AT PAR** on the text-repurposing slice | The single carousel landed on a Monday despite the Tue–Thu rule. Two "strongest atom" leads were scheduled the same day. Instagram missed bare-domain links ("link in bio"). |
| speechwriter | Hemingway Editor Plus $10/mo (no speechwriting SaaS found) | 3 / 3 / 0 / 0 | 11/11 after fixes (4/10 comparable before) | **ABOVE** for the speech job, AT PAR on readability | Rounded the year 2009 to "about 2,000" and flagged it as a hard word. Missed "it is not X, it is Y" antithesis. Missed a 3-clause tricolon with 3 commas. "raise your glasses" wasn't read as a toast. Section times didn't add up to the total. "99%" was rendered as "nine in ten". |

"Correctness checks" counts the independently verified values listed in each section. "Before" counts come from running the same scenario on the unmodified tools.

### Test summary
- `python -m pytest -q tests/agents -k content tests/scenarios/test_content.py` → **154 passed**
- `python -m pytest -q tests/test_library.py` → **303 passed**

### Issues outside the content folder (reported, not edited)
- **`hundred/lib/text.py` `syllables()`** gets 15 of 30 dictionary-checked hard words wrong:
  - `created` → 1 and `decided` → 2: the `-ted`/`-ded` strip removes a spoken syllable.
  - `whole` and `rule` → 2: silent *e* after *l* is not stripped.
  - `idea`, `create`, `poem`, `science`, `being` are under-counted: vowel hiatus is treated as one vowel group.

  On ordinary prose the drift is small. Paragraph 2 of the copy-editor scenario comes out at 79 syllables against 78 in the dictionary, which gives FRE 65.1 against 66.7 and FK 7.4 against 7.2. So the "within ~5%" docstring holds for prose, not for individual words.
- **`hundred/lib/text.py` `words()`** splits hyphenated compounds, so `fast-paced` counts as 2. Word, Grammarly and Hemingway count it as 1, which gives 282 against 281 on the scenario draft.
- **`hundred/lib/text.py` `sentences()`** glues a heading line onto the next sentence when there's no blank line between them. blog-writer now drops headings before measuring, so it's worked around here. Other categories may still be affected.

---

## 1. copy-editor (free lead magnet): Grammarly Pro / Hemingway

**Scenario.** "Edit this blog post before it goes to 4,000 subscribers. Keep my voice." The input is a 282-word post about cancelling meetings. It has a throat-clearing opener, 4 passives, 4 adverbs and 5 hedges, "in order to" and "utilized", and 3 planted grammar errors: *in it's history*, *people who wasn't*, *the whole the experiment*. It also has a double space and a numeral under ten. Tools ran in order: `diagnose` → `find_replacements` → edit → `style_check(original=…)` → `readability_diff`.

**Parity checklist**
| # | Grammarly / Hemingway capability (source) | Hundred | Why |
|---|---|---|---|
| 1 | Spelling mistakes ([Grammarly plans](https://www.grammarly.com/plans)) | PARTIAL | About 95 common misspellings are caught deterministically. Everything else relies on the host AI's read-through, which the playbook now requires. There is no dictionary. |
| 2 | Grammar ([Grammarly plans](https://www.grammarly.com/plans)) | PARTIAL | Pattern rules cover its/it's, we/they *was*, *people … wasn't*, *more then*, stray articles and doubled words. All 3 planted errors are caught. It is not a parser. |
| 3 | Conciseness: "for the purposes of" → "to", "a number of" → "several" ([Grammarly conciseness](https://www.grammarly.com/blog/product/grammarly-conciseness-suggestions/)) | MATCHES | Over 130 phrase tighten-ups, case-preserving, with an edit log. Both of Grammarly's examples are included. |
| 4 | Passive voice ([Grammarly](https://www.grammarly.com/passive-voice-checker); [Hemingway](https://hemingwayapp.com/help/docs/highlighted-issues)) | MATCHES | Found all 4 hand-identified passives, with sentences. |
| 5 | Readability score + hard-to-read sentences ([Hemingway](https://hemingwayapp.com/help/docs/readability); Grammarly readability) | MATCHES | FK grade and FRE, plus the long sentences listed. Matches hand Flesch to within 0.05. |
| 6 | Weakeners: adverbs, qualifiers ([Hemingway](https://hemingwayapp.com/help/docs/highlighted-issues)) | MATCHES | Adverbs and hedges are listed with counts. "rather than" is no longer a false hit. |
| 7 | Simpler alternatives, e.g. utilize → use ([Hemingway](https://hemingwayapp.com/help/docs/highlighted-issues)) | MATCHES | Applied automatically, with `aggressive` covering the judgement calls. |
| 8 | Consistency: spelling variant, punctuation, Oxford comma ([Grammarly](https://www.grammarly.com/blog/writing-tips/consistency-issues-in-writing/)) | MATCHES | Quotes, dashes, Oxford comma, %/percent. US/UK is now judged from the author's original, including -ize/-ise. |
| 9 | Full-sentence rewrites, tone ([Grammarly plans](https://www.grammarly.com/plans)) | PARTIAL | The host AI rewrites and the playbook constrains it to preserve voice. There is no tone detector. |
| 10 | Plagiarism and AI-text detection (Grammarly Pro) | OUT OF SCOPE | Needs a web index or classifier. We only lint phrase-level "AI tells". |
| 11 | Overall score ([Grammarly Performance](https://support.grammarly.com/hc/en-us/articles/360007144751-What-is-Performance-and-how-is-it-calculated)) | MATCHES | A 0–100 score, plus a before/after diff that proves the edit helped. Neither Grammarly nor Hemingway documents that diff. |

**Correctness (independent)**
| Check | Expected | Actual before fix | Actual after fix |
|---|---|---|---|
| Words, draft | 282 (281 whitespace tokens; `fast-paced` = 2 by this convention) | 282 | 282 |
| Sentences draft / edit | 16 / 18 | 16 / 18 | 16 / 18 |
| Passives | 4 | 4 | 4 |
| Hedges | 5 (basically, really, just, very, quite) | 6 ("rather than" counted) | 5 |
| Words saved by tighten-ups | 10 (6+2+2+0) | 10 | 10 |
| FRE / FK on a 22-word passage, 29 dictionary syllables | 84.15 / 4.25 | 84.2 / 4.3 | 84.2 / 4.3 |
| FRE / FK on the 52-word paragraph, 78 syllables | 66.7 / 7.2 | 65.1 / 7.4 (heuristic 79 syllables) | same (lib issue; within tolerance) |
| "in it's history" flagged | yes | **no** | yes |
| "people who wasn't" flagged | yes | **no** | yes |
| "the whole the" flagged | yes | **no** | yes |
| Correct capital "I" not flagged | 0 errors | **every "I" flagged** | 0 |
| "cancelled" flagged in a US (utilized) draft | yes | **no** (no -ize markers; "check" counted as US) | yes |
| No lost-number warning for 3 → three | none | **false warning** | none |
| Words change | −19.1% | −19.1% | −19.1% |

**Deliverable excerpt**
```
## Edited text
Most small teams are drowning in meetings. A meeting that could have been an email is an expensive way to feel busy.

Last quarter our leadership team canceled every recurring meeting for 30 days. It was scary. Priya cleared the calendar on a Friday…
…For the first time in its history, the support team answered tickets in under two hours…
…so people who weren't in the room could see what we decided and why. That log turned out to be the most valuable part of the experiment.

## What changed
| 1 | "In today's fast-paced world, it is important to note that" | (cut) | cliché + throat-clearing |
| 2 | "a decision was made by our leadership team to cancel" | "our leadership team canceled" | passive → active |
| 3 | "in it's history" | "in its history" | its/it's |
| 4 | "the people who wasn't" | "people who weren't" | agreement |
| 5 | "the whole the experiment" | "the experiment" | stray article |
| 6 | 4 × mechanical: in order to → to, utilized → used, was able to → could, it is important to note that → (cut) | | tighten-ups |

## Before → after
Words: 282 → 228 (-19%) · Grade: 7.4 → 5.3 · Passive: 4 → 0 · Adverbs: 4 → 0 · FRE 73.7 → 79.7
```

**What a plain AI would likely get wrong (observed):** it can't count passives or words reliably, so it would claim "improved readability" with no numbers. The tools themselves were also wrong before this pass: they told the AI every "I" was an error and that the proof was clean while three grammar errors remained.

**Remaining gaps:** there is no dictionary spell-check and no grammar parser, so exhaustive detection depends on the host AI. That is the honest reason the verdict is BELOW Grammarly on its core job while AT PAR with Hemingway. There is no tone detector and no plagiarism check.

---

## 2. blog-writer: Jasper Pro (Blog Outline / Blog Post agents)

**Scenario.** "Review my 420-word draft on remote onboarding before I publish. Keyword: *remote onboarding checklist*." The keyword is in the H1 but not in the intro. The draft has 5 short H2s and a one-word "Tools" heading. Tools ran in order: `word_budget`, `outline_lint`, `readability_report`, `keyword_audit` with title and meta.

**Parity checklist**
| # | Jasper capability (source) | Hundred | Why |
|---|---|---|---|
| 1 | Outline with working titles, H2/H3 hierarchy, talking points, CTA placement ([Blog Outline agent](https://www.jasper.ai/agents/blog-outline)) | MATCHES | `word_budget` gives the section count, words per section and must-haves, including keyword placement. |
| 2 | Full draft from outline ([Blog Post agent](https://www.jasper.ai/agents/blog-post)) | MATCHES | The host AI drafts to the playbook. |
| 3 | "Integrates keywords naturally" (same) | MATCHES | `keyword_audit` *measures* density (0.5–2.0%), placement /5, secondaries, title ≤ 60 and meta 120–155. Jasper documents none of these checks. |
| 4 | Clear headings, scannable, SEO/AEO/GEO (same) | MATCHES | `outline_lint` checks H1 count, skipped levels, thin or bloated sections, the close, alt text and links. |
| 5 | Brand Voice / Style Guide ([pricing](https://www.jasper.ai/pricing)) | PARTIAL | Voice is mirrored from samples in the session. There is no stored voice profile. |
| 6 | Knowledge assets ([pricing](https://www.jasper.ai/pricing)) | OUT OF SCOPE | Hosted knowledge base. The customer's AI project files can stand in. |
| 7 | Rephrase & rewrite tone/length ([pricing](https://www.jasper.ai/pricing)) | MATCHES | Host AI. |

**Correctness (independent)**
| Check | Expected | Before | After |
|---|---|---|---|
| Total words | 421 (403 body + 18 heading) | 421 | 421 |
| Intro words (between H1 and first H2) | 94 | 94 | 94 |
| Per-H2 words (81, 40, 92, 57, 39) | hand count | match | match |
| Thin H2s | Day one, Thirty days, Tools | match | match |
| Keyword occurrences / density | 2 / 2·3/421 = 1.43% | 2 / 1.43 | 2 / 1.43 |
| Keyword in first 100 words of body | **False** (only in H1) | **True** | False |
| Body words / sentences for readability | 403 / 26 | 421 / 26 (headings glued into sentences) | 403 / 26 |
| Avg sentence length | 403/26 = 15.5 | 16.2 | 15.5 |
| Word budget total (900, how-to) | 72 + 765 + 63 = 900 | 900 | 900 |

**Deliverable excerpt**
```
**Title:** Remote Onboarding Checklist: 30 Days to a Confident New Hire (60 chars ✅)
**Slug:** /remote-onboarding-checklist
**Meta description:** A day-by-day remote onboarding checklist for managers: what to send before day one, how to run week one, and the 30-day review. (127 ✅)
**Scorecard:** Structure ⚠️ 4 fixes · Readability grade 6.2 (FRE 78) · Keyword density 1.43% · Placement 2/5 · Links: 0
**Fix list (in order):**
1. Put "remote onboarding checklist" in the intro's first 100 words (currently only in the H1).
2. Merge Day one + The first week; merge Thirty days into a "Your 30-day review" H2; rename "Tools" → "What to use (you already have it)".
3. Add a closing "Next steps" H2 with the keyword and one action; add 2+ links (sources + internal).
4. Split the 33-word sentence in "The first week"; add transitions (23% → ≥ 25%).
5. Use "onboarding buddy" once (secondary keyword never appears).
```

**What a plain AI would likely get wrong (observed):** without the fix, the tool itself told the AI the keyword was already in the intro, and a plain AI reading the H1 makes the same mistake.

**Remaining gaps:** no SERP or competitor data. The blog-writer covers what the page must contain, not what currently ranks. No stored brand voice.

---

## 3. x-thread-builder: Typefully Creator

**Scenario.** "Turn this 209-word pricing post into a thread; end with the newsletter link." The source has an emoji flag and a bare-domain link (`pricingnotes.io/raise`). Tools ran in order: `score_hook` ×3 → `split_thread` → rewrite → `count_post` → `lint_thread`.

**Parity checklist**
| # | Typefully capability (source) | Hundred | Why |
|---|---|---|---|
| 1 | Auto-split long text at paragraph/sentence boundaries ([changelog](https://typefully.com/changelog/better-thread-auto-split-for-drafts-99)) | MATCHES | `split_thread` produced 8 posts, none cut mid-sentence, all ≤ 280. |
| 2 | X-weighted character counter: links 23, emoji 2 ([counter](https://typefully.com/tools/twitter-character-counter)) | MATCHES (after fix) | Passes 22/22 of [twitter-text's conformance cases](https://github.com/twitter/twitter-text/blob/master/conformance/validate.yml), plus the bare-domain cases. |
| 3 | Auto-numbering ([changelog](https://typefully.com/changelog/automatic-tweet-numbering-51)) | MATCHES | `1/`, `1/N` and `(1/N)` styles, and lint checks the sequence. |
| 4 | Realistic / mobile preview ([help](https://help.typefully.com/preview)) | OUT OF SCOPE | UI. |
| 5 | AI flags weak hooks, suggests stronger ([Typefully AI](https://typefully.com/ai)) | MATCHES | `score_hook` gives 0–100 with the reasons and fixes. The host AI writes the alternatives. |
| 6 | AI learns your style from past posts ([Typefully AI](https://typefully.com/ai)) | PARTIAL | Voice is mirrored from samples in the session. There is no post history. |
| 7 | Hook generator in proven styles ([hook generator](https://typefully.com/tools/ai/hook-generator)) | MATCHES | Five hook-type frameworks, each scored. |
| 8 | Scheduling, publishing, analytics | OUT OF SCOPE | Needs integrations. |

**Correctness (independent: from-spec counter + twitter-text conformance)**
| Check | Expected | Before | After |
|---|---|---|---|
| twitter-text v3 weighted cases (22) | as published | 17/22 (NFC, keycap `1⃣`, tag-sequence flag +12, two invalid-host URLs) | 22/22 |
| "Made in the 🇺🇸" | 14 | 16 | 14 |
| "Details: pricingnotes.io/raise" | 9 + 23 = 32 | 30 | 32 |
| Bare domain in post 3 → "link before last post" | flagged | **not flagged** | flagged |
| Final thread per-post weights | 89, 163, 138, 163, 130, 135, 223 | same (post 7: flag +2 and domain −2 cancelled out by luck) | same |
| Hook weighted length | 85 | 85 | 85 |

**Deliverable excerpt**
```
**Hook score:** 87/100 (specific result) — number + promise, 85 chars, opens the loop
1/ We raised prices 40% and lost 11 of 380 customers.

The 5 decisions that made it work:
2/ We priced on what customers would lose without us, not on competitors.
For a typical team: about $2,000 a month in analyst time. That number set the new price.
3/ Every existing customer kept their old price for 6 months. …
4/ We added an annual plan with two months free. 31% of new customers picked it… Churn halved…
5/ Sales stopped discounting on calls… Average contract value rose 22%.
6/ The 11 who left were all on the cheapest plan, all using one feature…
7/ The lesson: a price increase is a product announcement… 🚀🇺🇸
Full breakdown + free spreadsheet template: pricingnotes.io/raise
Follow for the next one on annual plans.
---
**Lint:** ✅ all posts ≤ 280 (max 223) · link only in 7 · numbering OK
**Alt hooks (scored):** "Stop pricing by looking at competitors…" — 84 · "A thread on pricing 🧵" — 29
```

**What a plain AI would likely get wrong (observed):** it would treat `pricingnotes.io/raise` as 21 characters and the flag as 1 or 4. The old tool did both.

**Remaining gaps:** there is no preview UI and no memory of past posts. The TLD list is a snapshot from twitter-text.

---

## 4. linkedin-ghostwriter: AuthoredUp Individual

**Scenario.** "My post isn't getting engagement. Fix it." The draft opens with "I'm excited to share…" and buries the $38,000 hiring mistake in paragraph 2. It also has `**bold**`, markdown bullets, a body link, `#sales` mid-sentence, and 6 hashtags after "Thoughts?". Tools ran in order: `post_check` → `format_post` → `score_hook` ×3 → rewrite → `post_check`.

**Parity checklist**
| # | AuthoredUp capability (source) | Hundred | Why |
|---|---|---|---|
| 1 | "See more" fold preview, ~210 desktop / ~140 mobile ([AuthoredUp limits](https://authoredup.com/blog/linkedin-character-limit)) | MATCHES | Returns the exact fold text and character counts for desktop and mobile. There's no visual render. |
| 2 | 3,000-character limit (same) | MATCHES | Exact count. |
| 3 | Bold / italic formatting ([homepage](https://authoredup.com/)) | MATCHES (after fix) | Added `unicode_bold`. It used to only strip bold. |
| 4 | Readability grade while writing ([homepage](https://authoredup.com/)) | MATCHES | FK grade, with a flag above 10. |
| 5 | 150+ hooks, 100+ CTA/ending templates ([homepage](https://authoredup.com/)) | PARTIAL | Five hook types, each scored, plus close patterns. There is no 150-item library. |
| 6 | Snippets: saved signature and hashtags | OUT OF SCOPE | Needs storage. |
| 7 | Analytics, scheduling, best posting times | OUT OF SCOPE | Needs integrations. |

**Correctness**
| Check | Expected | Before | After |
|---|---|---|---|
| Final post characters | `len` = 709 | 709 | 709 |
| Desktop fold (3 non-empty lines incl. newline) | 40+1+49+2+31+1 = 124 | 124 | 124 |
| Hashtags in draft | 7 | 7 | 7 |
| "you" / "I" counts, final | 4 / 3 | 4 / 3 | 4 / 3 |
| `format_post`: each hashtag exactly once, one line at the end | yes | **no:** `#hiring` appeared twice, 6 tags left on the "Thoughts?" line, `#sales` left mid-sentence | yes |
| Weak "Thoughts?" close flagged when hashtags follow | yes | **no** | yes |
| Hook "My worst hire… cost us $38,000" chars / type | 90 / confession | 90 / number-list | 90 / confession |

**Deliverable excerpt**
```
**Hook score:** 92/100 (confession) · fold: 124/210 chars ✅ · 709/3,000 chars
My worst hire last year cost us $38,000.
I picked the best resume over the best questions.

Four months in, we parted ways.
…
So I changed one thing in how we hire at Northwind:
→ Every candidate brings three questions about our customers
→ We score the questions, not the answers
→ One of our top reps sits in every final round
…
What's the one question a candidate asked you that told you everything?

#SalesHiring #SalesLeadership #Recruiting
**First comment:** Our full hiring scorecard: https://northwind.example.com/blog/hiring-scorecard
**Alt hooks:** "Stop hiring the best resume. Hire the best questions." — 81 · "I'm excited to share…" — 54
**Check:** ✅ fold · ✅ length · ✅ no links in body · ✅ ends on a question
```

**Remaining gaps:** there is no visual preview, no hook library and no analytics. The fold is approximate by LinkedIn's own design; AuthoredUp says "roughly", too.

---

## 5. newsletter-editor: beehiiv Scale (AI); overlap Low

**Scenario.** "Edit Thursday's issue, give me subject lines, tag the links for issue 58." The 394-word issue opens with "Hope you're all doing well!". It has a `[here]` anchor on a URL with an existing query and fragment, a duplicate, a naked `http://` link, and a partially UTM-tagged link. Tools ran in order: `issue_audit` → `subject_line_check` ×4 → `link_audit` → `tag_links`.

**Parity checklist** ([beehiiv AI in the post editor](https://www.beehiiv.com/support/article/15882638374551-using-ai-features-in-the-beehiiv-post-editor), [beehiiv AI](https://www.beehiiv.com/features/artificial-intelligence))
| # | beehiiv capability | Hundred | Why |
|---|---|---|---|
| 1 | Generate text; shorten / extend / simplify | MATCHES | The host AI, following the playbook's edit pass and the audit's word targets. |
| 2 | Fix spelling & grammar | PARTIAL | Host AI only. The proof tool lives in copy-editor. |
| 3 | AI subject-line suggestions from content | MATCHES | Five candidates, each scored for mobile length, spam triggers, caps and preheader overlap. |
| 4 | Subject-line A/B test at send | OUT OF SCOPE | ESP sending. |
| 5 | Translate | OUT OF SCOPE | Not part of this agent. |
| 6 | AI images | OUT OF SCOPE | Media generation. |

**Correctness**
| Check | Expected | Before | After |
|---|---|---|---|
| Words incl. headings | 382 body + 12 heading = 394 | 394 | 394 |
| Section words | 77 / 186 / 44 / 75 | match | match |
| Reading time | 394/238 = 1.7 min | 1.7 | 1.7 |
| Lead share | 186/394 = 47.2% | 47.2 | 47.2 |
| `src=email%20footer` preserved | byte-for-byte | **`email+footer`** | preserved |
| `plan=pro,team` preserved | byte-for-byte | **`pro%2Cteam`** | preserved |
| `?utm_source=site` only → re-tag | flagged | **treated as tagged** | flagged |
| Greeting intro flagged | yes | **no** | yes |
| "Newsletter #58: …" (same preheader) is not a "send it" subject | < 75 | 75 | 65 |
| Subject char counts (40, 48, 43, 33) | `len` | match | match |

**Deliverable excerpt**
```
**Subject (recommended):** Stripe raised your fees. Here's the math — 81/100 (40 chars, fits mobile)
**Preheader:** Three sample businesses, one spreadsheet, and the 0.3-point test (64)
**A/B alternative:** Did Stripe just raise your rates? — 81/100
**Read time:** 1.7 min (394 words) · **Sections:** 3 · **Links:** 5 (4 tagged, 1 re-tag needed)
Tagged: https://ledgerline.example.com/blog/stripe-fees?ref=nl&src=email%20footer&utm_source=newsletter&utm_medium=email&utm_campaign=issue-58#model
**Changes made:** cut the 77-word greeting intro; "here"/"Read more"/"this" → descriptive anchors; merged the duplicate Stripe link into the close; http → https; linked the community answer to the late-fee template.
**Other subject lines tried:** "Newsletter #58: Stripe fees, benchmarks and more" — 65 · "FREE checklist: cut your Stripe fees NOW!!!" — 48 (spam: free, caps, !!!)
```

**Remaining gaps:** no sending, no A/B test, no open or click data. The overlap with an ESP is structurally low; the agent is an editor, not a platform.

---

## 6. youtube-scripter: vidIQ Boost (Script Writer)

**Scenario.** "Script a ~3.5-minute video: 3 cold-email mistakes, talking head + B-roll." Tools ran in order: `retention_beats`, then the 523-word script, then `script_timing` → `title_check` ×5 → `build_chapters`.

**Parity checklist** ([vidIQ Script Writer help](https://support.vidiq.com/en/articles/11526189-script-writer), [AI script generator](https://vidiq.com/ai-script-generator/), [title generator](https://vidiq.com/ai-title-generator/))
| # | vidIQ capability | Hundred | Why |
|---|---|---|---|
| 1 | Topic + length (5–30 min) + tone input | MATCHES | The beat sheet is built for the target length, and `script_timing` holds the draft to ±10%. |
| 2 | Script with intro, sections, CTA | MATCHES | Hook, open loop, interrupts, CTA placement and payoff. |
| 3 | Choose from 3 concept directions | PARTIAL | The host AI can offer angles, but the playbook doesn't require it. |
| 4 | Edit / regenerate sections, tone tweaks | MATCHES | Host AI. |
| 5 | Titles from real YouTube search data | PARTIAL | Titles are checked for length/sidebar truncation, keyword position, caps and clickbait. There's no search-volume data. |
| 6 | Description generator | MATCHES | Chapter block plus a check on the first 150 characters. |
| 7 | AI voice-over to test pacing | OUT OF SCOPE | Audio. Pacing is computed numerically instead. |
| 8 | Thumbnail maker | OUT OF SCOPE | Media. |

**Correctness**
| Check | Expected | Before | After |
|---|---|---|---|
| Spoken words (no headings / [stage] notes) | 523 | 523 | 523 |
| Runtime at 150 wpm | 523/150·60 = 209.2 s → 3:29 | 3:29 | 3:29 |
| Section starts from cumulative words | 0:00, 0:27, 1:16, 1:54, 2:30, 3:12, 3:24 | match | match |
| Chapters rebuilt for the description | same as the starts | **0:00…2:29** (rounded-duration drift) | exact (`chapters` output) |
| Last chapter under 10 s → invalid (YouTube: ["minimum length … 10 seconds"](https://support.google.com/youtube/answer/9884579)) | invalid | **valid** | invalid |
| Out-of-order start makes the set invalid | invalid | invalid (by accident) | invalid |
| Hook window, 5-min video | 5% of 300 s = 0:15 | 0:15 | 0:15 |
| Interrupts at 75 s spacing | 2 (90 s, 165 s) | 2 | 2 |
| Title character counts | `len` | match | match |

**Deliverable excerpt**
```
**Title (recommended):** Cold Email Mistakes: 3 That Kill Your Replies — 91/100 · **Alt:** I Sent 9,000 Cold Emails. These 3 Mistakes Cost Me the Most — 87/100
**Runtime:** 3:29 at 150 wpm (523 words) · target 3:30 ✅
## Script
### [0:00] HOOK
Twenty cold emails. Fourteen replies. Same product, same list, same week… [B-ROLL: inbox 0 → 14]
### [0:27] MISTAKE 1: YOU OPEN WITH YOURSELF … [INTERRUPT: cut to whiteboard]
### [1:16] MISTAKE 2 … ### [1:54] THE THREE-LINE STRUCTURE (in-body CTA) … ### [2:30] MISTAKE 3 (open-loop payoff)
### [3:12] CLOSE + END SCREEN
## Description (paste-ready)
Three cold email mistakes that kill replies, and the three-line structure that got 14 replies from 20 sends.
0:00 Intro
0:27 Mistake 1: opening with yourself
1:16 Mistake 2: asking for too much
1:54 The three-line structure
2:30 Mistake 3: the word that kills replies
3:12 Recap
```

**Remaining gaps:** there's no search or keyword data for titles (vidIQ's moat), no thumbnail, and no voice-over. The retention beats are heuristics, not the channel's own retention data.

---

## 7. case-study-writer: Jasper Pro (Case Study agent)

**Scenario.** "Support tickets went 1,240 → 610, CSAT 71% → 88%, first response 9.5 h → 1.2 h in 90 days… write the case study." The input has seven metrics, including one that moved the wrong way and a small base. Tools ran in order: `format_metrics` → `roi_summary` → `quote_check` → draft → `story_lint`.

**Parity checklist** ([Jasper Case Study agent](https://www.jasper.ai/agents/case-study))
| # | Jasper capability | Hundred | Why |
|---|---|---|---|
| 1 | Inputs: challenge, solution, outcomes | MATCHES | The playbook intake mines transcripts for numbers and quotes. |
| 2 | Challenge → solution → implementation → results | MATCHES | `story_lint` enforces the sections. |
| 3 | Long-form, publication-ready draft | MATCHES | Host AI following the playbook. |
| 4 | Brand Voice / Style Guide | PARTIAL | No stored profile. |
| 5 | Knowledge Base grounding | OUT OF SCOPE | Hosted KB. |
| 6 | Scannable headings for SEO | MATCHES | |
| 7 | Reuse across decks and one-pagers | MATCHES | Length variants for web, one-pager and slide. |

Jasper's page documents no metric handling or quote handling. Our `format_metrics`, `roi_summary` and `quote_check` do exactly the parts a buyer's finance and legal reviewers check.

**Correctness**
| Check | Expected | Before | After |
|---|---|---|---|
| 9.5 → 1.2 h | −87.4%; 9.5/1.2 = 7.92 → 7.9x | −87.4, "from 9.5 hrs to 1.2 hrs" + **small-base warning** | "cut first-response time 87% (…; 7.9x faster)", no warning |
| 400 → 650 | +62.5% → **63%** (half-up) | **62%** | 63% |
| 1,240 → 610 | −50.8% → "halved" | match | match |
| CSAT 71 → 88 | +17 points (not +23.9%) | match | match |
| 12% → 31% | +19 points | match (phrase lacked the metric name) | "trial-to-paid conversion from 12% to 31% (+19 points)" |
| 3 → 11 customers | absolute, not +267% | match | match |
| ROI 186k benefit, 36k/yr, 12k one-time | (186−48)/48 = 287.5%; BCR 3.875 | 287.5 / 3.88 | 287.5 / 3.88 |
| Payback, monthly billing | 12,000/12,500 = 0.96 mo | 1.0 ("paid back in **1 months**") | 1.0 ("in the first month") |
| Payback without the 12k one-time cost | ≤ with it | **2.3 mo** (switched model: more cost paid back *sooner*) | 0.0 monthly / 2.3 vs 3.1 annual-upfront |
| Customer / product mentions | 6 / 6 | 6 / 6 | 6 / 6 |

**Deliverable excerpt**
```
# Harbor Freight Co. cut first-response time 87% in 90 days with Deskly
| Industry | Size | Product | Results |
| Logistics | 240 employees | Deskly Help Center + AI triage | 87% faster first response · CSAT 71% → 88% |
> "We went from answering tickets the next morning to answering them before lunch. Our CSAT went from 71 to 88 in one quarter." — Dana Ruiz, Head of Support (quote score 86/100)
## The results
- **First-response time:** from 9.5 hours to 1.2 hours (87% faster, 7.9x) in 90 days
- **Monthly tickets:** halved, from 1,240 to 610 in 90 days
- **CSAT:** from 71% to 88% (+17 points) in 90 days
---
**Metric framing notes:** conversion is "+19 points", not "158%"; enterprise customers "from 3 to 11", not "267%"; support headcount rose 8 → 10 — omit or explain.
**Lint fixes to apply:** hero ratio 6:6 → rewrite the 2 product-led sentences with the customer as actor; cut "great tool, highly recommend" (quote score 7); extend to 700+ words for web or ship as a one-pager.
```

**Remaining gaps:** no stored brand voice or knowledge base. The hero-ratio check counts only the exact company name, so "the team" and "Ruiz" aren't credited.

---

## 8. content-repurposer: Castmagic Hobby

**Scenario.** "Turn this pricing post into X, LinkedIn and Instagram pieces over two weeks starting Monday 5 Oct." Tools ran in order: `atomize` → `platform_limits` → pieces → `fit_check` per platform → `repurpose_plan`.

**Parity checklist** ([castmagic.io](https://www.castmagic.io/))
| # | Castmagic capability | Hundred | Why |
|---|---|---|---|
| 1 | Audio/video/URL import and transcription | OUT OF SCOPE | We take text or transcripts. |
| 2 | Written outputs: blog, newsletter, LinkedIn, Instagram captions, Reel/TikTok scripts | MATCHES | The host AI writes each piece in the platform's native grammar, built around an atom. |
| 3 | Standout quotes and highlights | MATCHES | `atomize` ranks stats, contrasts, quotes, aphorisms and lists. |
| 4 | Timestamped, speaker-labelled transcripts | OUT OF SCOPE | Audio. |
| 5 | Captioned clips, audiograms, carousel images | OUT OF SCOPE | Media. We produce the carousel *outline*. |
| 6 | Brand-voice training, templates | PARTIAL | Session samples only. |
| 7 | RSS autopilot, API, MCP | OUT OF SCOPE | Automation. |

Castmagic documents no per-platform limit checks or calendar. We add weighted and fold fit checks, sentence-boundary trims, and a spaced schedule.

**Correctness**
| Check | Expected | Before | After |
|---|---|---|---|
| Pieces for 1,400 words (article) | x round(3.5·1.4) = 5, li 2, ig 1 | 5 / 2 / 1 | 5 / 2 / 1 |
| Same platform ≥ 2 days apart; weekdays only | all | all | all |
| Big pieces (thread / long post / carousel) Tue–Thu | all | **carousel on Mon** | Tue / Wed / Thu |
| Strongest-atom leads on distinct days | 3 dates | **X thread and LinkedIn lead both on Tue** | 3 dates |
| X fit-check weight | ref counter = 186 | 186 (two errors cancelling) | 186 (correct) |
| Instagram: bare-domain link → "link in bio" | flagged | **not flagged** | flagged |

**Deliverable excerpt**
```
**Source:** pricing post, 209 words · **Atoms used:** 8 of 10 · **Pieces:** 8 across X, LinkedIn, Instagram
| Date | Platform | Piece | Atom | Fit |
| Tue 2026-10-06 | X | Thread (lead) — "We raised prices 40% and lost 11 of 380…" | stat #1 | 7 posts, max 223/280 ✅ |
| Wed 2026-10-07 | LinkedIn | Long post (lead) — "A price increase is a product announcement." | aphorism | 498/3,000 · hook line 44 chars, inside the 210 fold ✅ |
| Thu 2026-10-08 | X | Post 2 — annual plan at two months free: 31% took it | stat #4 | 154/280 ✅ |
| Thu 2026-10-08 | Instagram | Carousel (lead) — 6 slides, "5 pricing decisions" | list | caption 155/2,200, first line 97 < 125-char preview ✅ · "link in bio" |
| Fri 2026-10-09 | LinkedIn | Post 2 — why we stopped discounting on sales calls | contrast | (to fit-check) |
| Mon 10-12 · Wed 10-14 · Fri 10-16 | X | Posts 3–5 (grandfathering, lite tier, $2,000 anchor) | stats | (to fit-check) |
**Unused atoms:** "Here is what we learned." (too weak), "Instead, sales could offer a longer trial." (merged into LinkedIn post 2)
```

**Remaining gaps:** no media or audio, no auto-import, no posting. Atom extraction is lexical, so weak sentences like "Here is what we learned." still rank as aphorisms.

---

## 9. speechwriter: Hemingway Editor Plus (readability overlap)

**Scenario.** "Here's my best-man toast. I talk fast. Tighten it for a 3-minute slot." The draft opens with a greeting and has a 42-word opening sentence, "exactly 8,036 days", "34.7%" and "since 2009". It has no callback to the opening. Tools ran in order: `timing` → `rhetoric_check` → `structure_map` → `speakability`, then the rewrite and a re-run of all four.

**Parity checklist** ([Hemingway readability](https://hemingwayapp.com/help/docs/readability), [highlights](https://hemingwayapp.com/help/docs/highlighted-issues), [quick start](https://hemingwayapp.com/help/docs/quick-start-guide))
| # | Hemingway capability | Hundred | Why |
|---|---|---|---|
| 1 | Readability grade | MATCHES | FK grade in `speakability`. |
| 2 | Hard / very hard sentences | MATCHES | Sentences over 20 words, flagged as one breath each. |
| 3 | Adverbs / passive / qualifiers | PARTIAL | Not flagged by the speech tools; copy-editor has them. |
| 4 | Simpler alternatives | PARTIAL | 4+ syllable words are flagged, but no substitute is suggested. |
| 5 | Word count, reading time | MATCHES | Also gives *speaking* time at the speaker's pace, plus pause, laugh and applause time and per-section timestamps. Hemingway has none of these. |
| 6 | Grammar (Plus) | PARTIAL | Host AI. |

No speechwriting SaaS with published pricing was found. The rhetoric, structure and speaking-time tools have no priced comparable, so the verdict is ABOVE for the speech job.

**Correctness**
| Check | Expected | Before | After |
|---|---|---|---|
| Spoken words, final | 264 (no headings or [marks]) | 264 | 264 |
| Total time | 264/150·60 + 3·2 + 3·3 + 8 + 7·0.5 = 132.1 s → 2:12 | 2:12 | 2:12 |
| Section durations sum to total | 132 ± 1 | **134 vs 137** (paragraph pauses missing) | 22 + 85 + 25 = 132 |
| Target (90% of 3 min) | 2:42 | 2:42 | 2:42 |
| "since 2009" | a year: not rounded, not a hard word | **"about 2,000"**, hard word | skipped |
| "8,036" / "34.7%" | about 8,000 / about a third | match | match |
| "99%" | "almost all" | "nine in ten" | "almost all" |
| "It is not the grand gestures… It is the small ones" | antithesis | **missed** | found |
| "To the friend…, to the woman…, and to the small gestures…" | close tricolon | **missed** (3 commas) | found |
| "raise your glasses… To Daniel and Priya!" | toast close | **"statement"** | toast |
| Opening/body/close shares, final | 41/264, 185/264, 38/264 = 15.5 / 70.1 / 14.4% | — | 15.5 / 70.1 / 14.4 |

**Deliverable excerpt**
```
**Occasion:** wedding · **Speaker:** best man (fast) · **Slot:** 3 min · **Runs:** 2:12 at 150 wpm (target 2:42 ✅)
**Message sentence:** "It is not the grand gestures that make a marriage. It is the small ones."
### OPENING (0:00–0:22)
What do you say about a man who once drove four hours to return a borrowed ladder? [pause]
I'm Tom. I've known Daniel for twenty-two years. That's about a third of my life… [laugh]
### BODY (0:22–1:47)
Daniel is the friend who shows up. He showed up when… He showed up when… He showed up with soup, with jokes, and with a very large ladder. [laugh]
…It is not the grand gestures that make a marriage. It is the small ones, repeated for a lifetime. [pause]
### CLOSE (1:47)
So please raise your glasses. [pause] To the man who drove four hours to return a ladder. To the woman who made him choose a restaurant. And to the small gestures, repeated for a lifetime. To Daniel and Priya! [applause]
**Devices:** tricolon ×3 · anaphora ×3 · antithesis ×1 · callback ✅ ("drove four hours to return a")
**Timing table:** Opening 0:00 · 0:22 · 41 w | Body 0:22 · 1:25 · 185 w | Close 1:47 · 0:25 · 38 w
```

**Remaining gaps:** device detection is pattern-based. It finds classic forms, not every rhetorical move. The syllable heuristic in `hundred/lib/text.py` affects the "hard words" list.
