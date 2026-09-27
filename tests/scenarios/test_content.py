"""Replayable evaluation scenarios for the content category (see evals/content.md).

Each test replays one realistic customer job through the agent's tools, in playbook order,
and asserts values that were verified independently: hand counts, hand-computed Flesch
scores from dictionary syllables, cumulative timestamps done by arithmetic, and a
from-the-spec X weighted counter defined in this file (no import from hundred for truth).
"""

import re
import unicodedata
from datetime import date

from hundred import registry

COPY_DRAFT = (
    "In today's fast-paced world, it is important to note that most small teams are basically drowning in meetings. At the end of the day, a meeting that could have been an email is really just a very expensive way to feel busy.\n"
    '\n'
    'Last quarter a decision was made by our leadership team to cancel every recurring meeting for 30 days. It was honestly quite scary. The calendar was cleared by Priya on a Friday, and on Monday morning the office felt strangely quiet. We were not sure if anything would get done at all.\n'
    '\n'
    "Here is what happened. The number of meetings dropped from 41 a week to 9. Engineers shipped 3 features that had been stuck in the backlog since March, and the support team was able to answer tickets in under two hours for the first time in it's history. Nobody missed the standup. Some people did miss the Friday demo, so we brought it back.\n"
    '\n'
    "In order to make this work, we utilized a simple rule: if a meeting doesn't have a written agenda and a decision to make, it doesn't happen. We also wrote down every decision in a shared doc so that the people who wasn't in the room could see what was decided and why it was decided, which turned out to be the most valuable part of the whole the experiment.\n"
    '\n'
    'We are not saying meetings are bad. We are saying that most of them are a habit rather than a tool, and that habits can be broken if you are willing to feel uncomfortable for a few weeks.  If you want to try it, start with one team, one month, and one rule.\n'
)

COPY_EDIT = (
    'Most small teams are drowning in meetings. A meeting that could have been an email is an expensive way to feel busy.\n'
    '\n'
    'Last quarter our leadership team cancelled every recurring meeting for 30 days. It was scary. Priya cleared the calendar on a Friday, and on Monday morning the office felt quiet. We were not sure anything would get done.\n'
    '\n'
    'Here is what happened. Meetings dropped from 41 a week to 9. Engineers shipped three features that had been stuck in the backlog since March. For the first time in its history, the support team answered tickets in under two hours. Nobody missed the standup. Some people did miss the Friday demo, so we brought it back.\n'
    '\n'
    "To make this work, we used one rule: if a meeting doesn't have a written agenda and a decision to make, it doesn't happen. We also logged every decision in a shared doc, so people who weren't in the room could see what we decided and why. That log turned out to be the most valuable part of the experiment.\n"
    '\n'
    'We are not saying meetings are bad. We are saying most of them are a habit, not a tool, and you can break a habit if you are willing to feel uncomfortable for a few weeks. If you want to try it, start with one team, one month, and one rule.\n'
)

X_SOURCE = (
    'We raised our prices by 40% last spring and lost exactly 11 customers out of 380. Here is what we learned.\n'
    '\n'
    'Most founders price by looking at competitors. That anchors you to their mistakes. We priced by looking at what our customers would lose if we disappeared: about $2,000 a month in analyst time for a typical team.\n'
    '\n'
    'We grandfathered every existing customer for 6 months. Nobody likes a surprise invoice, and the goodwill paid for itself in referrals.\n'
    '\n'
    'We added an annual plan at two months free. 31% of new customers chose it in the first quarter, which cut our churn in half because annual customers simply do not churn mid-year.\n'
    '\n'
    'We stopped offering discounts on sales calls. Instead, sales could offer a longer trial. Deals closed at the same rate and the average contract value went up 22%.\n'
    '\n'
    'The 11 customers who left were all on our cheapest plan and all using one feature. We should have built a lite tier for them years ago, and now we have.\n'
    '\n'
    'The biggest lesson: a price increase is a product announcement. Tell customers what they get, not what they pay. 🚀🇺🇸\n'
    '\n'
    'Full breakdown with the spreadsheet on our blog at pricingnotes.io/raise — and the template is free.\n'
)

LI_DRAFT = (
    "I'm excited to share some reflections from the last quarter at Northwind. As many of you know, we've been growing the #sales team quite a bit this year, and I've learned a lot along the way.\n"
    '\n'
    'Last quarter I made a hiring mistake. I hired the candidate with the best resume instead of the one who asked the best questions. **Four months later we parted ways**, and it cost us roughly $38,000 in salary, recruiting fees and lost pipeline.\n'
    '\n'
    "Here's what I changed:\n"
    '- I now ask every candidate to bring three questions about our customers\n'
    '- I score the questions, not the answers\n'
    '- I involve one of our top reps in every final round\n'
    '\n'
    "Since then we've made 6 hires and all 6 are still here and hitting quota. The questions a candidate asks tell you how they will sell. I wrote more about the scorecard here: https://northwind.example.com/blog/hiring-scorecard\n"
    '\n'
    'Thoughts? #hiring #leadership #salesleadership #startups #recruiting #b2b\n'
)

LI_FINAL = (
    'My worst hire last year cost us $38,000.\n'
    'I picked the best resume over the best questions.\n'
    '\n'
    'Four months in, we parted ways.\n'
    'Salary, recruiting fees and lost pipeline added up fast.\n'
    '\n'
    'So I changed one thing in how we hire at Northwind:\n'
    '→ Every candidate brings three questions about our customers\n'
    '→ We score the questions, not the answers\n'
    '→ One of our top reps sits in every final round\n'
    '\n'
    "Since then we've made 6 hires.\n"
    'All 6 are still here and hitting quota.\n'
    '\n'
    'The questions a candidate asks tell you how they will sell.\n'
    'Your interview loop is probably grading the wrong half of the conversation.\n'
    '\n'
    "What's the one question a candidate asked you that told you everything?\n"
    '\n'
    '#SalesHiring #SalesLeadership #Recruiting\n'
)

NL_ISSUE = (
    "Hope you're all doing well! It's been a busy week here at Ledgerline HQ. The team spent most of it at an offsite in Lisbon, and we came back with a lot of ideas, a few sunburns and a new favourite pastry. Before we get into it, a quick reminder that our spring pricing workshop is still open, and that we're hiring a second support engineer. Now, on to this week's issue, which is a long one.\n"
    '\n'
    "## The lead: Stripe's new fee tiers, explained\n"
    '\n'
    "Stripe changed how it prices international cards this month. If more than a fifth of your revenue comes from outside your home country, your effective rate probably went up. We ran the numbers for three sample businesses: a US SaaS company with 30% EU customers pays about 0.4 points more per transaction, a UK marketplace pays about 0.2 points more, and a US-only shop pays nothing extra. The full model, including a spreadsheet you can copy, is [here](https://ledgerline.example.com/blog/stripe-fees?ref=nl&src=email%20footer#model). If you only read one thing this week, read that. The short version: check your Stripe dashboard's fee breakdown for the last 90 days, compare it with the previous 90, and if the gap is more than 0.3 points, it's worth renegotiating or routing EU cards through a local acquirer. We've put together a checklist of the questions to ask your account manager, and the three things that most often move the rate. [Read more](https://ledgerline.example.com/blog/stripe-fees). For most of our readers the change is small, but for a few of you it will be the biggest cost increase of the year, and it lands quietly.\n"
    '\n'
    '## Quick hits\n'
    '\n'
    '- Paddle published its annual SaaS benchmarks; median net revenue retention fell to 101%. http://paddle.example.com/benchmarks-2026\n'
    '- A good thread on why invoice reminders should come from a person, not a noreply address: [this](https://x.com/someone/status/123).\n'
    '- We updated our dunning email templates. [Download them](https://ledgerline.example.com/templates/dunning?utm_source=site).\n'
    '\n'
    '## From the community\n'
    '\n'
    'Maria from a 12-person agency asked how to handle clients who pay 60 days late. Our answer: put a 2% late fee in the contract, send the first reminder on day 1 rather than day 30, and offer card payment on every invoice. Readers who tried the day-1 reminder report getting paid about 9 days sooner.\n'
    '\n'
    "That's all for this week — hit reply and tell us what you'd like us to cover next.\n"
)

YT_SCRIPT = (
    '## HOOK\n'
    '[B-ROLL: inbox with 0 replies, then 14 replies]\n'
    'Twenty cold emails. Fourteen replies. Same product, same list, same week. The only thing I changed was the first line.\n'
    "By the end of this video you'll have the exact three-line structure I used, and you'll know the one word that quietly kills most cold emails.\n"
    "I've sent about nine thousand cold emails for two startups, so I've made every mistake in this video at least twice.\n"
    '\n'
    '## MISTAKE 1: YOU OPEN WITH YOURSELF\n'
    'Here\'s how most cold emails start. "Hi, my name is Sam and I\'m the founder of a company that helps teams with their workflows." Read that as the person getting it. Nothing in that sentence is about them. They don\'t know you, they didn\'t ask for you, and you just spent their first three seconds on your job title.\n'
    '[ON-SCREEN: "Me, me, me" counter]\n'
    "The fix is simple. Your first line should be about something they did, said, or published in the last thirty days. A podcast episode, a job post, a product launch. If you can't find one, you're emailing the wrong person.\n"
    '[INTERRUPT: cut to whiteboard]\n'
    "And here's the test I use. Cover the signature. If the first line could be sent to a thousand people without changes, rewrite it.\n"
    '\n'
    '## MISTAKE 2: YOU ASK FOR TOO MUCH\n'
    'The second mistake is the ask. "Would you be open to a thirty minute call next week to explore synergies?" That\'s a big ask from a stranger. Thirty minutes is a meeting, and a meeting needs a reason.\n'
    '[B-ROLL: calendar filling up]\n'
    'Ask for something they can say yes to in five seconds. "Worth a look?" or "Should I send the two-minute version?" Small asks get replies, and replies start conversations. Conversations turn into calls.\n'
    "Now, the third mistake is the one that cost me a client, and I'll get to it in a minute. First, the structure.\n"
    '\n'
    '## THE THREE-LINE STRUCTURE\n'
    'Line one is about them. Line two is the one result you got for someone like them, with a number. Line three is the small ask.\n'
    '[ON-SCREEN: three lines appearing one by one]\n'
    'Here\'s a real one. "Saw your post about onboarding taking six weeks. We got a forty-person team down to nine days. Worth a two-minute video on how?" That\'s it. Twenty-nine words. It got a reply in eleven minutes.\n'
    "If this is useful, subscribe, because next week I'm breaking down follow-ups, which is where most replies actually come from.\n"
    '\n'
    '## MISTAKE 3: THE WORD THAT KILLS REPLIES\n'
    'So here\'s the mistake that cost me a client. The word is "just." "Just checking in." "Just following up." "Just wanted to see." It sounds polite. It reads as "I have nothing new to say."\n'
    '[INTERRUPT: story cut, B-ROLL of old email thread]\n'
    'I sent "just following up" to a head of sales four times. On the fifth email I sent a two-line note with a new number from a customer in her industry. She replied in an hour and signed a month later. She told me later she\'d never opened the first four.\n'
    'Every follow-up needs a new reason to reply. A new number, a new example, a new question. Never "just."\n'
    '\n'
    '## CLOSE\n'
    'So, the first line is about them, the ask is small, and every follow-up brings something new. Try it on your next twenty emails and count the replies.\n'
    '[END SCREEN]\n'
    "If you want the follow-up playbook, it's the next video, right here.\n"
)

BLOG_DRAFT = (
    '# The Remote Onboarding Checklist Every Manager Needs\n'
    'Starting a new job is hard. Starting a new job from your kitchen table, with nobody to ask where the coffee is or who owns the billing system, is harder. Most managers know this, but most of them still run onboarding the way they did in an office: a laptop, a welcome email, and a hope that the new person figures things out. That hope costs you. New hires who feel lost in their first month are far more likely to leave in their first year, and every departure means another round of recruiting.\n'
    '\n'
    '## Before day one\n'
    "Send the laptop at least five days early. Ship it with every account already created, because nothing kills first-day energy like an afternoon spent waiting for IT tickets. Write a one-page plan for the first two weeks, and share it before the start date so the new hire can read it on their own time. Assign a buddy who is not their manager. The buddy's job is to answer the questions people are too embarrassed to ask their boss.\n"
    '\n'
    '## Day one\n'
    'Keep day one light. A welcome call with the team, a thirty-minute walkthrough of the tools, and one small task they can finish before the end of the day. Finishing something on day one matters more than learning everything.\n'
    '\n'
    '## The first week\n'
    'In the first week the new hire should meet everyone they will work with regularly. Book those calls for them rather than asking them to do it, because a new person will not want to bother a senior colleague. Give them one real piece of work with a clear definition of done. Check in at the end of every day for fifteen minutes. These check-ins can be dropped in week two, but in week one they are the difference between a new hire who feels supported and one who feels abandoned.\n'
    '\n'
    '## Thirty days\n'
    "At thirty days, hold a structured review. Ask what surprised them, what they still don't understand, and what they would change about onboarding. Write the answers down. The best improvements to a remote onboarding checklist come from the people who just went through it, and it is a mistake to wait for exit interviews to hear them.\n"
    '\n'
    '## Tools\n'
    'Use whatever tools your team already uses. A shared document is enough for the plan. A recurring calendar invite is enough for the check-ins. What matters is that the process is written down and that someone owns it.\n'
)

CS_DRAFT = (
    '# Harbor Freight Co. cut first-response time 87% in 90 days with Deskly\n'
    '\n'
    '| Industry | Size | Product | Results |\n'
    '|---|---|---|---|\n'
    '| Logistics | 240 employees | Deskly Help Center + AI triage | 87% faster first response · CSAT 71% → 88% |\n'
    '\n'
    '> "We went from answering tickets the next morning to answering them before lunch. Our CSAT went from 71 to 88 in one quarter." — Dana Ruiz, Head of Support, Harbor Freight Co.\n'
    '\n'
    '## The situation\n'
    'In early 2026 Harbor Freight Co.\'s eight-person support team was handling 1,240 tickets a month. Most of them were the same five questions about shipment tracking. Customers waited an average of 9.5 hours for a first response, and CSAT had fallen to 71%. "We were drowning in \'where is my package\' emails," Ruiz said.\n'
    '\n'
    '## The turning point\n'
    "After a peak-season week in which the backlog passed 400 open tickets, Ruiz's team decided to stop hiring their way out of the problem. They set a goal: answer the repetitive questions before they became tickets.\n"
    '\n'
    '## What Harbor Freight Co. did\n'
    "Harbor Freight Co. published 38 help articles covering the top tracking questions, then turned on Deskly's AI triage to route everything else to the right agent. The team rewrote the three most-read articles every two weeks based on search data. Deskly's integration with their shipping system let agents see tracking status inside each ticket.\n"
    '\n'
    '## The results\n'
    'Within 90 days:\n'
    '- **First-response time:** from 9.5 hours to 1.2 hours (87% faster)\n'
    '- **Monthly tickets:** from 1,240 to 610, down 51%\n'
    '- **CSAT:** from 71% to 88% (+17 points)\n'
    '\n'
    '"Deskly is a great tool, highly recommend," said Ruiz.\n'
    '\n'
    "## What's next\n"
    'Harbor Freight Co. is rolling out the same approach to its carrier-support queue in Q1. See how Deskly can help your support team — book a demo.\n'
)

SPEECH_DRAFT = (
    '## OPENING\n'
    'Good evening everyone, my name is Tom and I have known Daniel for twenty-two years, which is exactly 8,036 days, or roughly 34.7% of my entire life, and I have the photographs to prove every single one of them. [laugh]\n'
    '\n'
    'What do you say about a man who once drove four hours to return a borrowed ladder? [pause]\n'
    '\n'
    '## BODY\n'
    'We met at school when we were eleven. He was the new kid, and he sat next to me because it was the only empty seat. He has been sitting next to me ever since.\n'
    '\n'
    'Daniel is the friend who shows up. He showed up when I moved house three times in one year. He showed up when my dad was in hospital. He showed up with soup, with jokes, and with a very large ladder. [laugh]\n'
    '\n'
    'And then, four years ago, he met Priya. I knew it was serious when he asked me to help him choose a restaurant. Daniel has eaten the same sandwich for lunch since 2009. [laugh] He does not choose restaurants.\n'
    '\n'
    "Priya, you should know what you are getting. You are getting a man who reads the manual before he opens the box. You are getting a man who remembers your mother's birthday and your cat's birthday. You are getting a man who will drive four hours for you, and back again, without being asked.\n"
    '\n'
    'It is not the grand gestures that make a marriage, it is the small ones, repeated for a lifetime.\n'
    '\n'
    '## CLOSE\n'
    'So, would you all please raise your glasses. [pause] To the friend who shows up, to the woman who made him choose a restaurant, and to the small gestures, repeated for a lifetime. To Daniel and Priya! [applause]\n'
)

SPEECH_FINAL = (
    '## OPENING\n'
    'What do you say about a man who once drove four hours to return a borrowed ladder? [pause]\n'
    '\n'
    "I'm Tom. I've known Daniel for twenty-two years. That's about a third of my life, and I have the photos to prove it. [laugh]\n"
    '\n'
    '## BODY\n'
    'We met at school when we were eleven. He was the new kid, and he sat next to me because it was the only empty seat. He has been sitting next to me ever since.\n'
    '\n'
    'Daniel is the friend who shows up. He showed up when I moved house three times in one year. He showed up when my dad was in hospital. He showed up with soup, with jokes, and with a very large ladder. [laugh]\n'
    '\n'
    'Four years ago, he met Priya. I knew it was serious when he asked me to help him choose a restaurant. Daniel has eaten the same sandwich for lunch since 2009. [laugh] He does not choose restaurants.\n'
    '\n'
    "Priya, you should know what you are getting. You are getting a man who reads the manual before he opens the box. You are getting a man who remembers your mother's birthday and your cat's birthday. You are getting a man who will drive four hours for you, and back again, without being asked.\n"
    '\n'
    'It is not the grand gestures that make a marriage. It is the small ones, repeated for a lifetime. [pause]\n'
    '\n'
    '## CLOSE\n'
    'So please raise your glasses. [pause] To the man who drove four hours to return a ladder. To the woman who made him choose a restaurant. And to the small gestures, repeated for a lifetime. To Daniel and Priya! [applause]\n'
)

X_THREAD = ['1/ We raised prices 40% and lost 11 of 380 customers.\n\nThe 5 decisions that made it work:', '2/ We priced on what customers would lose without us, not on competitors.\n\nFor a typical team: about $2,000 a month in analyst time. That number set the new price.', '3/ Every existing customer kept their old price for 6 months.\n\nNobody likes a surprise invoice. The goodwill paid for itself in referrals.', "4/ We added an annual plan with two months free.\n\n31% of new customers picked it in the first quarter. Churn halved, because annual customers don't churn mid-year.", '5/ Sales stopped discounting on calls. They could offer a longer trial instead.\n\nClose rate held. Average contract value rose 22%.', '6/ The 11 who left were all on the cheapest plan, all using one feature.\n\nWe should have built them a lite tier years ago. Now we have.', '7/ The lesson: a price increase is a product announcement. Tell customers what they get, not what they pay. 🚀🇺🇸\n\nFull breakdown + free spreadsheet template: pricingnotes.io/raise\n\nFollow for the next one on annual plans.']


# ── independent ground truth (does not import hundred) ────────────────────────
WORD = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)*")


def ref_words(s: str) -> int:
    # Word/Google Docs convention, independent of our tokenizer: whitespace-separated tokens that
    # contain a letter or digit ("fast-paced", "$38,000" and a URL are one word each).
    return len([t for t in s.split() if re.search(r"[^\W_]", t)])


def ref_spoken_words(s: str) -> int:
    # What a listener hears as separate words: hyphenated compounds and digit groups split
    # ("fast-paced" = 2). Timing tools count this way; independent of our tokenizer.
    return len(WORD.findall(s))


def ref_sentences(s: str) -> int:
    return len(re.findall(r"[^.!?]+[.!?]+", s))


def flesch(words: int, sentences: int, syllables: int) -> tuple[float, float]:
    """Flesch Reading Ease and Flesch-Kincaid grade from hand counts."""
    wps, spw = words / sentences, syllables / words
    return 206.835 - 1.015 * wps - 84.6 * spw, 0.39 * wps + 11.8 * spw - 15.59


_REF_TLDS = {"com", "org", "net", "io", "co", "md"}
_REF_URL = re.compile(r"https?://\S+|(?<![\w@.-])(?:[a-z0-9-]+\.)+([a-z]{2,})(?:/[^\s]*)?", re.I)


def ref_x_weight(s: str) -> int:
    """twitter-text v3 weighting written from the spec: NFC; link = 23 (trailing '.' is text);
    any emoji sequence = 2; U+0000-10FF, U+2000-200D, U+2010-201F, U+2032-2037 = 1; else 2."""
    s = unicodedata.normalize("NFC", s)
    total, rest, last = 0, [], 0
    for m in _REF_URL.finditer(s):
        if m.group(0).lower().startswith("http") or (m.group(1) or "").lower() in _REF_TLDS:
            url = m.group(0).rstrip(".,!?")
            rest.append(s[last:m.start()])
            total += 23
            last = m.start() + len(url)
    rest.append(s[last:])
    t, i = "".join(rest), 0
    while i < len(t):
        cp = ord(t[i])
        if 0x1F1E6 <= cp <= 0x1F1FF:  # flag = two regional indicators
            total, i = total + 2, i + 2
            continue
        if 0x1F300 <= cp <= 0x1FAFF or 0x2600 <= cp <= 0x27BF:
            total, i = total + 2, i + 1
            while i < len(t) and (ord(t[i]) in (0xFE0F, 0x200D) or 0x1F3FB <= ord(t[i]) <= 0x1F3FF or (i and ord(t[i - 1]) == 0x200D)):
                i += 1
            continue
        total += 1 if (cp <= 4351 or 8192 <= cp <= 8205 or 8208 <= cp <= 8223 or 8242 <= cp <= 8247) else 2
        i += 1
    return total


def mmss(sec: float) -> str:
    sec = int(sec + 0.5)
    return f"{sec // 60}:{sec % 60:02d}"


def call(slug: str, tool: str, **kwargs):
    return registry.get(slug).get_tool(tool).call(kwargs)


# ── 1. copy-editor (free) — flabby 280-word blog post ─────────────────────────
def test_copy_editor_diagnose_baseline():
    out = call("copy-editor", "diagnose", draft=COPY_DRAFT)
    b = out["baseline"]
    assert b["words"] == ref_words(COPY_DRAFT) == 281
    assert b["sentences"] == ref_sentences(COPY_DRAFT) == 16
    # hand-identified passives: "a decision was made by", "was cleared by Priya", "what was decided … why it was decided", "habits can be broken"
    assert b["passive_sentences"] == 4
    assert {a for a, _ in out["findings"]["adverbs"]} == {"basically", "honestly", "really", "strangely"}
    # basically, really, just, very, quite — "rather than" is not a hedge
    assert {h["phrase"] for h in out["findings"]["hedges"]} == {"basically", "really", "just", "very", "quite"}
    assert b["cliches"] == 2 and b["ai_tells"] == 2


def test_copy_editor_find_replacements_saves_ten_words():
    out = call("copy-editor", "find_replacements", draft=COPY_DRAFT)
    # "it is important to note that" (-6) + "was able to"→"could" (-2) + "in order to"→"to" (-2) + "utilized"→"used" (0)
    assert out["words_saved"] == 10 == ref_words(COPY_DRAFT) - ref_words(out["rewritten"])
    assert {e["from"] for e in out["edits"]} == {"it is important to note that", "was able to", "in order to", "utilized"}
    assert "To make this work, we used a simple rule" in out["rewritten"]


def test_copy_editor_proof_catches_planted_errors():
    issues = [i["issue"] for i in call("copy-editor", "style_check", draft=COPY_DRAFT)["issues"]]
    assert any("'in it's history'" in i for i in issues)
    assert any("'people who wasn't'" in i for i in issues)
    assert any("'the whole the'" in i for i in issues)
    assert any(i == "double space" for i in issues)
    # a correct capital "I" is never an error
    clean = call("copy-editor", "style_check", draft="I think I was right, so I left early.")
    assert not [i for i in clean["issues"] if i["kind"] == "error"]


def test_copy_editor_spelling_variant_comes_from_the_original():
    out = call("copy-editor", "style_check", draft=COPY_EDIT, original=COPY_DRAFT)
    assert out["spelling_variant"] == "US"  # the author wrote "utilized"
    assert [i["issue"] for i in out["issues"]] == ["'cancelled' is UK spelling; the original is US"]


def test_copy_editor_readability_diff_matches_hand_counts():
    out = call("copy-editor", "readability_diff", before=COPY_DRAFT, after=COPY_EDIT)
    assert (out["before"]["words"], out["after"]["words"]) == (281, ref_words(COPY_EDIT)) == (281, 228)
    assert (out["before"]["sentences"], out["after"]["sentences"]) == (16, ref_sentences(COPY_EDIT)) == (16, 18)
    assert out["after"]["passive_sentences"] == 0 and out["after"]["hedges"] == 0
    assert out["words_change_pct"] == round(100 * (228 - 281) / 281, 1) == -18.9
    assert out["warnings"] == []  # "3 features" → "three features" is not a lost number


def test_copy_editor_flesch_against_hand_syllable_counts():
    # "Most small teams are drowning in meetings. A meeting that could have been an email is an
    # expensive way to feel busy." — 22 words, 2 sentences, 29 syllables (dictionary)
    p = "Most small teams are drowning in meetings. A meeting that could have been an email is an expensive way to feel busy."
    fre, fk = flesch(22, 2, 29)
    got = call("copy-editor", "readability_diff", before=p, after=p)["before"]
    assert abs(got["flesch_reading_ease"] - fre) <= 0.05 and abs(got["fk_grade"] - fk) <= 0.05
    # paragraph 2 of the draft: 52 words, 4 sentences, 78 dictionary syllables. The heuristic
    # syllable counter (hundred/lib/text.py) says 79 ("strangely" = 3), so allow its drift.
    p2 = COPY_DRAFT.split("\n\n")[1]
    fre2, fk2 = flesch(52, 4, 78)
    got2 = call("copy-editor", "readability_diff", before=p2, after=p2)["before"]
    assert got2["words"] == 52 and got2["sentences"] == 4
    assert abs(got2["flesch_reading_ease"] - fre2) <= 2.0 and abs(got2["fk_grade"] - fk2) <= 0.3


# ── 2. x-thread-builder — pricing post → thread ───────────────────────────────
def test_x_thread_hooks_ranked():
    best = call("x-thread-builder", "score_hook", hook="We raised prices 40% and lost 11 of 380 customers. The 5 decisions that made it work:")
    weak = call("x-thread-builder", "score_hook", hook="A thread on pricing 🧵")
    assert best["score"] >= 75 and weak["score"] < 60
    assert best["weighted_chars"] == ref_x_weight("We raised prices 40% and lost 11 of 380 customers. The 5 decisions that made it work:") == 85


def test_x_thread_split_never_cuts_a_sentence():
    out = call("x-thread-builder", "split_thread", source=X_SOURCE)
    assert out["all_fit"] and out["count"] == 8
    for p in out["posts"]:
        assert p["weighted_chars"] == ref_x_weight(p["text"]) <= 280
        assert re.search(r"[.!?:]$|[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF]$", p["text"])


def test_x_thread_final_thread_counts_and_lint():
    out = call("x-thread-builder", "lint_thread", posts=X_THREAD)
    assert out["clean"] is True
    assert [p["weighted_chars"] for p in out["posts"]] == [ref_x_weight(p) for p in X_THREAD] == [89, 163, 138, 163, 130, 135, 223]


def test_x_count_flag_and_bare_domain():
    # a flag is ONE emoji (2), a bare domain is a t.co link (23) — the two errors used to cancel out
    assert call("x-thread-builder", "count_post", post="Made in the 🇺🇸")["weighted_chars"] == ref_x_weight("Made in the 🇺🇸") == 14
    assert call("x-thread-builder", "count_post", post="Details: pricingnotes.io/raise")["weighted_chars"] == ref_x_weight("Details: pricingnotes.io/raise") == 32
    # a bare domain before the last post is a link before the last post
    posts = list(X_THREAD)
    posts[2] = posts[2] + " More at pricingnotes.io/raise"
    assert any(f.startswith("Post 3: link before the last post") for f in call("x-thread-builder", "lint_thread", posts=posts)["flags"])


# ── 3. linkedin-ghostwriter — post that buries its hook ────────────────────────
def test_linkedin_draft_check_flags_every_problem():
    out = call("linkedin-ghostwriter", "post_check", post=LI_DRAFT)
    assert out["chars"] == len(LI_DRAFT.strip())
    assert len(out["hashtags"]) == len(re.findall(r"#[A-Za-z]\w*", LI_DRAFT)) == 7
    flags = " | ".join(out["flags"])
    for needle in ("soft opener", "7 hashtags", "inside the body", "link(s) in the body", "**bold**", "'Thoughts?'"):
        assert needle in flags, needle


def test_linkedin_format_moves_every_hashtag_once():
    out = call("linkedin-ghostwriter", "format_post", draft=LI_DRAFT)
    body, _, tagline = out["formatted"].rpartition("\n\n")
    assert tagline == "#sales #hiring #leadership"
    assert "#" not in body and "**" not in body
    assert out["formatted"].count("#hiring") == 1
    assert out["chars"] == len(out["formatted"])


def test_linkedin_final_post_ready():
    out = call("linkedin-ghostwriter", "post_check", post=LI_FINAL)
    first3 = LI_FINAL.split("\n")[:4]  # line, line, blank, line
    assert out["chars"] == len(LI_FINAL.strip()) == 709
    assert out["fold_desktop_chars"] == len("\n".join(first3)) + 1 == 124
    assert out["hashtags"] == ["SalesHiring", "SalesLeadership", "Recruiting"]
    assert out["you_count"] == 4 and out["i_count"] == 3
    assert out["flags"] == [] and out["ready"] is True
    hook = call("linkedin-ghostwriter", "score_hook", hook="My worst hire last year cost us $38,000.\nI picked the best resume over the best questions.")
    assert hook["score"] >= 75 and hook["chars"] == 90 and hook["hook_type"] == "confession"


# ── 4. newsletter-editor — issue with a throat-clearing intro and messy links ─
def _sections(md: str) -> dict[str, int]:
    parts = re.split(r"^## ", md, flags=re.M)
    out = {"(intro)": ref_words(parts[0])}
    for p in parts[1:]:
        title, _, body = p.partition("\n")
        out[title.strip()] = ref_words(re.sub(r"\]\([^)]*\)", "]", body))  # link targets aren't read
    return out


def test_newsletter_audit_counts_and_flags():
    out = call("newsletter-editor", "issue_audit", markdown=NL_ISSUE, target_minutes=3)
    secs = _sections(NL_ISSUE)
    heading_words = sum(ref_words(h) for h in re.findall(r"^## (.*)$", NL_ISSUE, flags=re.M))
    total = sum(secs.values()) + heading_words  # headings are read too
    assert out["words"] == total == 383
    assert [r["words"] for r in out["sections"]] == list(secs.values()) == [77, 182, 39, 73]
    assert out["reading_minutes"] == round(total / 238, 1)
    lead = "The lead: Stripe's new fee tiers, explained"
    assert out["lead_share_pct"] == round(100 * secs[lead] / total, 1)
    assert any(f.startswith("Opens with a greeting") for f in out["flags"])


def test_newsletter_link_audit_and_tagging():
    la = call("newsletter-editor", "link_audit", markdown=NL_ISSUE)
    assert la["count"] == 5
    assert "partial UTM tags (missing utm_medium, utm_campaign) — re-tag with overwrite=true" in la["links"][4]["issues"]
    tl = call("newsletter-editor", "tag_links", urls=["https://ledgerline.example.com/blog/stripe-fees?ref=nl&src=email%20footer#model", "ledgerline.example.com/pricing?plan=pro,team"], campaign="Issue 58")
    assert tl["tagged"] == [
        "https://ledgerline.example.com/blog/stripe-fees?ref=nl&src=email%20footer&utm_source=newsletter&utm_medium=email&utm_campaign=issue-58#model",
        "https://ledgerline.example.com/pricing?plan=pro,team&utm_source=newsletter&utm_medium=email&utm_campaign=issue-58",
    ]


def test_newsletter_subject_lines():
    label = call("newsletter-editor", "subject_line_check", subject="Newsletter #58: Stripe fees, benchmarks and more")
    good = call("newsletter-editor", "subject_line_check", subject="Stripe raised your fees. Here's the math", preheader="Three sample businesses, one spreadsheet, and the 0.3-point test")
    spam = call("newsletter-editor", "subject_line_check", subject="FREE checklist: cut your Stripe fees NOW!!!")
    assert good["chars"] == len("Stripe raised your fees. Here's the math") == 40 and good["fits_mobile"]
    assert good["preheader"]["chars"] == 64 and good["preheader"]["in_range"]
    assert label["score"] < 75 <= good["score"]
    assert spam["score"] < 60 and "free" in spam["spam_triggers"]


# ── 5. youtube-scripter — 3.5-minute cold-email video ─────────────────────────
def _spoken(md: str) -> list[int]:
    words = []
    for block in re.split(r"^## .*$", md, flags=re.M)[1:]:
        words.append(ref_spoken_words(re.sub(r"\[[^\]]*\]", " ", block)))
    return words


def test_youtube_timing_and_chapters():
    out = call("youtube-scripter", "script_timing", script=YT_SCRIPT, wpm=150, target_minutes=3.5)
    per = _spoken(YT_SCRIPT)
    # "[END SCREEN]" is a bracket line, so the CLOSE block splits in two sections
    assert out["spoken_words"] == sum(per) == 523
    assert out["runtime"] == mmss(523 / 150 * 60) == "3:29"
    words = [s["words"] for s in out["sections"]]
    starts, acc = [], 0
    for w in words:
        starts.append(mmss(acc / 150 * 60))
        acc += w
    assert [s["start"] for s in out["sections"]] == starts == ["0:00", "0:27", "1:16", "1:54", "2:30", "3:12", "3:24"]
    assert out["flags"] == []
    ch = [c for c in out["chapters"] if c["title"] != "END SCREEN"]
    built = call("youtube-scripter", "build_chapters", chapters=ch)
    assert [r["timestamp"] for r in built["chapters"]] == starts[:-1] and built["valid"] is True


def test_youtube_beats_and_titles():
    beats = call("youtube-scripter", "retention_beats", target_minutes=5, format="listicle", items=3)
    assert beats["hook_window"] == "0:00-0:15"  # 5% of 300 s
    assert beats["interrupts"] == 2  # 90 s and 165 s; the next (240 s) is inside the last 15 s of the body
    titles = ["Cold Email Mistakes: 3 That Kill Your Replies", "I Sent 9,000 Cold Emails. These 3 Mistakes Cost Me the Most", "COLD EMAIL SECRETS THEY DONT WANT YOU TO KNOW"]
    tc = call("youtube-scripter", "title_check", titles=titles, keyword="cold email")
    assert {r["title"]: r["chars"] for r in tc["ranked"]} == {t: len(t) for t in titles}
    assert tc["truncating"] == [t for t in titles if len(t) > 60] == []
    assert tc["ranked"][-1]["title"].startswith("COLD EMAIL SECRETS")
    short = call("youtube-scripter", "build_chapters", chapters=[{"title": "A", "duration": 30}, {"title": "B", "duration": 40}, {"title": "End", "duration": 5}])
    assert short["valid"] is False


# ── 6. blog-writer — 420-word onboarding post ─────────────────────────────────
def test_blog_keyword_placement_uses_body_not_title():
    out = call("blog-writer", "keyword_audit", markdown=BLOG_DRAFT, primary_keyword="remote onboarding checklist")
    body = "\n".join(l for l in BLOG_DRAFT.splitlines() if not l.startswith("#"))
    first100 = " ".join(WORD.findall(body)[:100]).lower()
    assert out["placements"]["first_100_words"] is ("remote onboarding checklist" in first100) is False
    assert out["placements"]["title"] is True and out["placements"]["any_h2"] is False
    assert out["occurrences"] == BLOG_DRAFT.lower().count("remote onboarding checklist") == 2
    assert out["density_pct"] == round(100 * 2 * 3 / ref_words(BLOG_DRAFT), 2) == 1.44


def test_blog_structure_and_readability_counts():
    lint = call("blog-writer", "outline_lint", markdown=BLOG_DRAFT)
    assert lint["total_words"] == ref_words(BLOG_DRAFT) == 416
    assert lint["intro_words"] == ref_words(BLOG_DRAFT.split("\n## ")[0].split("\n", 1)[1]) == 94
    h2 = {s["title"]: s["words"] for s in lint["sections"] if s["level"] == 2}
    for part in BLOG_DRAFT.split("\n## ")[1:]:
        title, _, body = part.partition("\n")
        assert h2[title] == ref_words(body)
    # "Before day one" is 79 words by Word's count ("first-day", "one-page" are one word each): thin (< 80).
    assert {s["title"] for s in lint["sections"] if s.get("flag", "").startswith("thin")} == {"Before day one", "Day one", "Thirty days", "Tools"}
    rr = call("blog-writer", "readability_report", markdown=BLOG_DRAFT)
    body = "\n".join(l for l in BLOG_DRAFT.splitlines() if not l.startswith("#"))
    assert rr["words"] == ref_words(body) == 398
    assert rr["sentences"] == ref_sentences(body) == 26
    assert rr["avg_sentence_words"] == round(398 / 26, 1)


# ── 7. case-study-writer — support-desk customer story ────────────────────────
METRICS = [
    {"name": "support tickets per month", "before": 1240, "after": 610, "unit": "tickets", "higher_is_better": False, "timeframe": "90 days"},
    {"name": "CSAT", "before": 71, "after": 88, "unit": "%", "timeframe": "90 days"},
    {"name": "first-response time", "before": "9.5", "after": "1.2", "unit": "hrs", "higher_is_better": False, "timeframe": "90 days"},
    {"name": "trial-to-paid conversion", "before": 12, "after": 31, "unit": "%"},
    {"name": "enterprise customers", "before": 3, "after": 11, "unit": "customers"},
    {"name": "support headcount", "before": 8, "after": 10, "unit": "people", "higher_is_better": False},
    {"name": "self-serve resolutions", "before": 400, "after": 650, "unit": "tickets"},
]


def test_case_study_metric_math():
    m = {r["name"]: r for r in call("case-study-writer", "format_metrics", metrics=METRICS)["metrics"]}
    assert m["first-response time"]["pct_change"] == round(100 * (1.2 - 9.5) / 9.5, 1) == -87.4
    assert m["first-response time"]["phrase"] == "cut first-response time 87% (from 9.5 hrs to 1.2 hrs; 7.9x faster) in 90 days"
    assert m["first-response time"]["warnings"] == []  # hours are not a small-base count
    assert m["CSAT"]["points_change"] == 88 - 71 == 17
    assert m["trial-to-paid conversion"]["phrase"] == "trial-to-paid conversion from 12% to 31% (+19 points)"
    assert m["enterprise customers"]["framing"] == "absolute"  # never "267% growth" on a base of 3
    assert m["support headcount"]["improved"] is False
    # 400 → 650 is exactly +62.5%: round half up → 63%, not banker's 62%
    assert m["self-serve resolutions"]["phrase"].startswith("grew self-serve resolutions 63%")
    assert m["support tickets per month"]["pct_change"] == round(100 * (610 - 1240) / 1240, 1) == -50.8


def test_case_study_roi_payback_is_monotone_in_cost():
    a = call("case-study-writer", "roi_summary", annual_benefit=186000, annual_cost=36000, one_time_cost=12000)
    assert a["roi_pct"] == round(100 * (186000 - 48000) / 48000, 1) == 287.5
    assert a["benefit_cost_ratio"] == round(186000 / 48000, 2) == 3.88
    assert a["payback_months"] == round(12000 / ((186000 - 36000) / 12), 1) == 1.0
    up = call("case-study-writer", "roi_summary", annual_benefit=186000, annual_cost=36000, one_time_cost=12000, billing="annual_upfront")
    up0 = call("case-study-writer", "roi_summary", annual_benefit=186000, annual_cost=36000, billing="annual_upfront")
    assert up["payback_months"] == round(48000 / (186000 / 12), 1) == 3.1
    assert up0["payback_months"] == round(36000 / (186000 / 12), 1) == 2.3
    assert up["payback_months"] > up0["payback_months"]  # more cost can never pay back sooner


def test_case_study_quotes_and_lint():
    q = call("case-study-writer", "quote_check", quotes=[
        "We went from answering tickets the next morning to answering them before lunch. Our CSAT went from 71 to 88 in one quarter.",
        "Deskly is a great tool, highly recommend!",
    ])
    assert q["pull_quote"].startswith("We went from") and q["ranked"][0]["words"] == 23
    assert "Deskly is a great tool, highly recommend!" in q["discard"]
    lint = call("case-study-writer", "story_lint", draft=CS_DRAFT, customer_name="Harbor Freight Co.", product_name="Deskly")
    assert lint["customer_mentions"] == CS_DRAFT.count("Harbor Freight Co.") == 6
    assert lint["product_mentions"] == CS_DRAFT.count("Deskly") == 6
    assert any(f.startswith("Hero check") for f in lint["flags"])


# ── 8. content-repurposer — pricing post → X / LinkedIn / Instagram ───────────
def test_repurposer_plan_respects_spacing_rules():
    out = call("content-repurposer", "repurpose_plan", source_type="article", source_words=1400, platforms=["x", "linkedin", "instagram"], start_date="2026-10-05", weeks=2)
    assert out["pieces_per_platform"] == {"x": round(3.5 * 1.4), "linkedin": round(1.5 * 1.4), "instagram": round(1.0 * 1.4)} == {"x": 5, "linkedin": 2, "instagram": 1}
    cal = out["calendar"]
    assert len(cal) == 8 and out["unscheduled"] == {}
    days = {}
    for s in cal:
        d = date.fromisoformat(s["date"])
        assert d.weekday() < 5
        days.setdefault(s["platform"], []).append(d)
        if s["piece"].endswith("(lead)"):
            assert d.weekday() in (1, 2, 3), s  # thread / long post / carousel mid-week
    for ds in days.values():
        assert all((b - a).days >= 2 for a, b in zip(ds, ds[1:]))
    leads = [s["date"] for s in cal if s["atom_hint"] == "strongest atom"]
    assert len(leads) == len(set(leads)) == 3  # the strongest atom never lands twice on one day


def test_repurposer_fit_check_counts_like_each_platform():
    piece = "We raised prices 40% and lost 11 of 380 customers. The trick: grandfather everyone for 6 months, and sell the increase like a product launch. 🇺🇸 Full breakdown at pricingnotes.io/raise"
    x = call("content-repurposer", "fit_check", piece=piece, platform="x")
    assert x["chars"] == ref_x_weight(piece) == 186
    ig = call("content-repurposer", "fit_check", piece=piece, platform="instagram")
    assert ig["chars"] == len(piece) and ig["links"] == 1
    assert any("link in bio" in f for f in ig["flags"])


# ── 9. speechwriter — best-man toast, 3-minute slot, fast talker ──────────────
def _speech_words(md: str) -> int:
    return ref_spoken_words(re.sub(r"^## .*$|\[[^\]]*\]", " ", md, flags=re.M))


def test_speech_timing_matches_hand_math():
    out = call("speechwriter", "timing", script=SPEECH_FINAL, wpm=150, slot_minutes=3)
    words = _speech_words(SPEECH_FINAL)
    pauses = 3 * 2 + 3 * 3 + 8 + 0.5 * (len([p for p in SPEECH_FINAL.split("\n\n") if p.strip()]) - 1)
    assert out["spoken_words"] == words == 264
    assert out["total_seconds"] == round(words / 150 * 60 + pauses) == 132
    assert out["target"] == "2:42"  # 90% of 180 s
    assert sum(int(s["duration"].split(":")[0]) * 60 + int(s["duration"].split(":")[1]) for s in out["sections"]) in (131, 132, 133)
    assert out["flags"] == []


def test_speech_devices_and_structure():
    rc = call("speechwriter", "rhetoric_check", script=SPEECH_FINAL)
    assert rc["counts"]["antithesis"] >= 1  # "It is not the grand gestures… It is the small ones"
    assert any(d["part"] == "close" for d in rc["found"]["tricolon"])  # To the man… To the woman… And to the…
    assert rc["counts"]["callback"] >= 1 and rc["gaps"] == []
    sm = call("speechwriter", "structure_map", script=SPEECH_FINAL)
    assert sm["opening_hook"] == "question" and sm["closing_move"] == "toast" and sm["flags"] == []
    draft = call("speechwriter", "structure_map", script=SPEECH_DRAFT)
    assert draft["opening_hook"] == "greeting (weak)"


def test_speech_numbers_for_the_ear():
    sp = call("speechwriter", "speakability", script=SPEECH_DRAFT)
    said = {n["number"]: n["say"] for n in sp["numbers"]}
    assert said == {"8,036": "about 8,000", "34.7%": "about a third"}  # 2009 is a year, not "about 2,000"
    assert "2009" not in sp["hard_words"]
