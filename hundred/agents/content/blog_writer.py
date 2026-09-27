"""Blog Writer — search-intent articles with a measured structure, readability and keyword placement."""

from __future__ import annotations

import re
from collections import Counter
from typing import Literal

from ...core import Agent, ToolError
from ...lib import text
from . import _common as c

AGENT = Agent(
    slug="blog-writer",
    name="Blog Writer",
    category="content",
    tagline="Plan, write and lint blog posts that rank and get read: structure, readability and keyword placement measured, not guessed.",
    description=(
        "Runs the full editorial workflow for a long-form article: builds a word budget per section from the "
        "target length and format, drafts against search intent, then lints the result — heading hierarchy, "
        "thin or bloated sections, intro length, sentence and paragraph readability, passive voice, keyword "
        "density and placement (title, first 100 words, H2s, close), link mix and meta length. Produces a "
        "publish-ready post plus a scorecard, and publishes to your CMS when a connector is available."
    ),
    triggers=[
        "write a blog post / article about X",
        "outline a long-form article for a keyword",
        "review my blog draft for structure, readability and SEO",
        "is my keyword density OK / where should the keyword go",
        "turn these notes into a 1,500-word post",
        "improve the headings and intro of this article",
    ],
    examples=[
        "Write a 1,800-word how-to on 'cold email deliverability' for founders. Primary keyword: cold email deliverability.",
        "Here's my draft on remote onboarding — check the structure, readability and keyword use before I publish.",
        "Outline a comparison post: Notion vs Confluence for engineering teams, ~2,000 words.",
    ],
    connectors=["WordPress", "Webflow", "Ghost", "HubSpot", "Notion", "Google Docs"],
    playbook="""
    ## Standard
    You are a senior content editor at a publication whose posts rank and get finished. A post is
    excellent when a reader who arrived from search gets their answer in the first screen, keeps
    scrolling because every H2 promises something specific, and leaves having done something.
    The one metric: **would this outrank the current top-3 results for the query and would a
    human finish it?** Both, or it isn't done.

    ## Intake
    You need: the topic or primary keyword, the reader (who and what they already know), and
    the goal (rank / convert / build trust). Assume a target length by intent if none given:
    how-to or guide 1,500-2,200 words; listicle 1,200-1,800; opinion 700-1,000; news 400-700;
    comparison 1,500-2,500. Assume a smart practitioner reader and a Flesch-Kincaid grade of
    7-9. State assumptions in one line and proceed. Ask only when the topic is ambiguous
    enough that two different articles could result.

    ## Procedure
    1. **Lock intent and angle.** Classify the query: informational, commercial, transactional,
       navigational. Write a one-line promise the post makes ("After this you will be able
       to…"). Pick an angle the top results miss: a contrarian take, a specific audience, a
       number-driven method, first-hand data. Never "The Ultimate Guide to X" without one.
    2. **Budget the structure.** Call `blog_writer__word_budget` with the target length and
       format. It returns the intro/body/conclusion split, how many H2s to use and the words
       per section. Build the outline to that budget: every H2 is a promise phrased the way
       readers search ("How to warm up a domain in 14 days"), not a label ("Domain warming").
    3. **Write in order: intro → body → conclusion → title → meta.** Intro rules (APP or PAS):
       first sentence states the reader's situation or the surprising fact; by the end of
       paragraph two they know exactly what they'll get; primary keyword in the first 100
       words. Body: one idea per H2, a concrete example or number in each, short paragraphs
       (≤ 4 sentences), lists only for genuinely parallel items. Conclusion: not a summary —
       a next action plus the one thing to remember.
    4. **Lint the structure.** Call `blog_writer__outline_lint` on the full markdown. Fix every
       flag: one H1 (or none if the CMS adds it), no skipped levels, no heading > 70 chars,
       no section under 80 words or over 400, intro ≤ 150 words, a conclusion/next-step
       section, one H2 per ~250-350 words.
    5. **Lint readability.** Call `blog_writer__readability_report`. Targets: grade 7-9,
       average sentence 15-20 words, no sentence > 30 words, passive ≤ 10% of sentences,
       no paragraph > 120 words, transition words in ≥ 25% of sentences. Rewrite until it
       passes — do not lower the bar for "technical" content; lower the jargon instead.
    6. **Audit keywords and meta.** Call `blog_writer__keyword_audit` with the primary keyword,
       secondaries, title and meta description. Requirements: primary in title, H1, first 100
       words, at least one H2, and the last paragraph; density 0.5-2.0% (over 2.5% is
       stuffing — cut); each secondary keyword at least once, ideally in an H2/H3; title
       ≤ 60 chars with the keyword near the front; meta 120-155 chars with the keyword and a
       reason to click. Use the returned slug.
    7. **Final pass.** Add: an internal link every ~300 words where it genuinely helps; 2-4
       external links to primary sources (not competitors); alt text on every image
       (descriptive, keyword once at most); an FAQ H2 if the query has "People also ask"
       style sub-questions. Then publish via the CMS connector as a *draft*, or deliver the
       markdown.

    ## Frameworks
    - **Intent → format map**: "how to" → step-by-step with numbered H2s; "best / top" →
      listicle with criteria stated first; "X vs Y" → comparison table then verdict;
      "what is" → definition in the first 50 words, then depth; "why" → argument with
      evidence per section.
    - **Skyscraper-with-a-twist**: match the depth of the top results, then add one thing
      they lack (data, a template, a worked example, a decision rule).
    - **Inverted pyramid per section**: the takeaway sentence first, the explanation second,
      the example third. Skimmers get value from bolded first sentences alone.
    - **The 5-second test**: the title + first two sentences must tell a reader whether
      this is for them.

    ## Output format
    ```
    **Title:** <≤ 60 chars, keyword near front>
    **Slug:** /<from keyword_audit>
    **Meta description:** <120-155 chars>
    **Target reader / intent:** <one line> · **Length:** N words · ~M min read

    # <H1>
    <intro ≤ 150 words: situation → promise → what's inside>

    ## <H2 phrased as a promise>
    <body: takeaway first, then explanation, then example>
    …

    ## <Conclusion / Next steps>
    <one action + one thing to remember + CTA>

    ---
    **Scorecard:** Structure ✅/⚠️ · Readability grade N · Keyword density N% · Placement N/5 · Links: X internal, Y external
    **Open items:** <facts to verify, images needed, internal links to add>
    ```

    ## Anti-patterns
    - Intros that start with the history of the topic or "In today's digital landscape". Start with the reader.
    - H2s that are nouns ("Benefits") instead of promises ("Why warm-up cuts bounce rates by half").
    - Keyword stuffing and exact-match repetition; use natural variants after the required placements.
    - Uniform section lengths for their own sake; length follows the value of the point.
    - Conclusions titled "Conclusion" that summarise. End with the action.
    - Claiming statistics without a source. Every number gets a link or a "[verify]" flag.
    - Publishing without the lint tools — the numbers are the review, not your impression.
    """,
)

CONCLUSION_WORDS = re.compile(r"\b(conclusion|takeaways?|next steps?|wrap[- ]?up|summary|final thoughts|what now|tl;?dr|bottom line|faq|frequently asked)\b", re.I)
TRANSITIONS = {
    "however", "therefore", "moreover", "furthermore", "consequently", "meanwhile", "nevertheless", "instead",
    "because", "so", "but", "yet", "then", "first", "second", "third", "finally", "next", "also", "although",
    "while", "since", "thus", "hence", "for example", "for instance", "in short", "in other words", "still",
    "as a result", "in fact", "that means", "which means", "here's", "this is why", "the catch", "put simply",
}


@AGENT.tool
def word_budget(target_words: int, format: Literal["how-to", "listicle", "guide", "opinion", "comparison", "news"] = "guide", sections: int = 0, keyword: str = "") -> dict:
    """Turn a target length and format into a section-by-section word budget (intro, N H2s, conclusion, FAQ) plus reading time.

    Call before outlining. Picks the number of H2 sections from the length if you don't
    give one, and tells you where the keyword must appear.

    Args:
        target_words: Total words the post should be (300-8000).
        format: how-to, listicle, guide, opinion, comparison or news — sets intro/conclusion share and section shape.
        sections: Number of H2 sections you already know you want (0 = let the tool choose).
        keyword: Primary keyword, used to prescribe placements in the budget.
    """
    if not 300 <= target_words <= 8000:
        raise ToolError("target_words must be between 300 and 8000.")
    if sections < 0 or sections > 30:
        raise ToolError("sections must be 0-30.")
    intro_share = {"how-to": 0.08, "listicle": 0.07, "guide": 0.09, "opinion": 0.12, "comparison": 0.08, "news": 0.20}[format]
    close_share = {"how-to": 0.07, "listicle": 0.06, "guide": 0.07, "opinion": 0.12, "comparison": 0.10, "news": 0.05}[format]
    faq_share = 0.08 if format in ("how-to", "guide", "comparison") and target_words >= 1200 else 0.0
    body_words = int(target_words * (1 - intro_share - close_share - faq_share))
    per_section = {"how-to": 250, "listicle": 180, "guide": 300, "opinion": 220, "comparison": 280, "news": 150}[format]
    n = sections or max(2, min(12, round(body_words / per_section)))
    base, rem = divmod(body_words, n)
    plan = [{"part": "Intro", "words": int(target_words * intro_share), "must": ["reader's situation in sentence 1", "promise by end of paragraph 2", f"keyword '{keyword}' in first 100 words" if keyword else "primary keyword in first 100 words"]}]
    label = {"how-to": "Step", "listicle": "Item", "guide": "Section", "opinion": "Argument", "comparison": "Criterion", "news": "Section"}[format]
    for i in range(n):
        must = ["takeaway sentence first", "one concrete example or number"]
        if i == 0 and keyword:
            must.append(f"H2 contains '{keyword}' or a close variant")
        if format == "comparison" and i == n - 1:
            must.append("verdict table or decision rule")
        plan.append({"part": f"{label} {i + 1} (H2)", "words": base + (1 if i < rem else 0), "must": must})
    if faq_share:
        plan.append({"part": "FAQ (H2 + 3-5 H3 questions)", "words": int(target_words * faq_share), "must": ["questions phrased as people search them", "answers ≤ 60 words each"]})
    plan.append({"part": "Conclusion / next step", "words": int(target_words * close_share), "must": ["one action", "one thing to remember", f"keyword '{keyword}' once" if keyword else "primary keyword once", "CTA"]})
    total = sum(p["words"] for p in plan)
    return {
        "target_words": target_words,
        "format": format,
        "h2_sections": n,
        "budget": plan,
        "budget_total": total,
        "reading_minutes": round(target_words / 238, 1),
        "structure_rules": [f"one H2 per ~{per_section} words", "paragraphs ≤ 4 sentences", "no section under 80 words", "intro ≤ 150 words"],
        "summary": f"{format}: intro {plan[0]['words']}w → {n} H2 sections of ~{base}w → {'FAQ → ' if faq_share else ''}close {plan[-1]['words']}w (~{round(target_words / 238)} min read).",
    }


@AGENT.tool
def outline_lint(markdown: str) -> dict:
    """Lint a post's heading hierarchy and section sizes: H1 count, skipped levels, long headings, thin/bloated sections, intro length, conclusion, links and images.

    Call on the full markdown draft after writing and again after fixes. Returns the
    heading tree with word counts per section and a prioritised list of structural fixes.

    Args:
        markdown: The full article in markdown (headings with #, ##, ###).
    """
    c.guard(markdown, "Markdown")
    secs = c.sections(markdown)
    headings = [s for s in secs if s["level"] > 0]
    if not headings:
        raise ToolError("No markdown headings found (lines starting with #, ##, ###). Add headings, then lint.")
    plain = c.strip_markdown(markdown)
    total_words = len(text.words(plain))
    flags: list[str] = []
    h1s = [s for s in headings if s["level"] == 1]
    if len(h1s) > 1:
        flags.append(f"{len(h1s)} H1s — keep exactly one (the title) or none if the CMS adds it.")
    prev = 0
    for s in headings:
        if prev and s["level"] > prev + 1:
            flags.append(f"Skipped level: H{prev} → H{s['level']} at '{s['title'][:50]}' (line {s['line']}).")
        prev = s["level"]
        if len(s["title"]) > 70:
            flags.append(f"Heading too long ({len(s['title'])} chars): '{s['title'][:60]}…' — ≤ 70.")
        if len(text.words(s["title"])) <= 1 and s["level"] >= 2:
            flags.append(f"One-word heading '{s['title']}' (line {s['line']}) — phrase it as a promise or question.")
    dupes = [t for t, n in Counter(s["title"].strip().lower() for s in headings).items() if n > 1]
    for d in dupes:
        flags.append(f"Duplicate heading: '{d}'.")
    h2s = [s for s in headings if s["level"] == 2]
    intro = next((s for s in secs if s["level"] == 0), None)
    intro_words = intro["words"] if intro else 0
    if h1s and not intro:
        # text between H1 and the first H2 is the intro
        first_h1 = h1s[0]
        intro_words = first_h1["words"]
    if intro_words == 0:
        flags.append("No intro before the first H2 — add 60-150 words: situation → promise.")
    elif intro_words > 150:
        flags.append(f"Intro is {intro_words} words — cut to ≤ 150; the promise must land on screen one.")
    section_report = []
    for s in headings:
        if s["level"] <= 2:
            # words of this H2 including its H3 children
            idx = secs.index(s)
            child_words = 0
            for nxt in secs[idx + 1:]:
                if nxt["level"] <= s["level"]:
                    break
                child_words += nxt["words"]
            own = s["words"] + child_words
        else:
            own = s["words"]
        entry = {"level": s["level"], "title": s["title"], "line": s["line"], "words": own, "share_pct": c.pct(own, total_words)}
        if s["level"] == 2:
            if own < 80:
                entry["flag"] = "thin (< 80 words) — merge or add an example"
            elif own > 400:
                entry["flag"] = "bloated (> 400 words) — split into H3s or two H2s"
        section_report.append(entry)
    thin = [e for e in section_report if e.get("flag", "").startswith("thin")]
    bloated = [e for e in section_report if e.get("flag", "").startswith("bloated")]
    if thin:
        flags.append(f"{len(thin)} thin H2 section(s): {', '.join(e['title'][:30] for e in thin[:4])}.")
    if bloated:
        flags.append(f"{len(bloated)} bloated H2 section(s): {', '.join(e['title'][:30] for e in bloated[:4])}.")
    if h2s and total_words:
        words_per_h2 = total_words / len(h2s)
        if words_per_h2 > 450:
            flags.append(f"Only {len(h2s)} H2s for {total_words} words (~{int(words_per_h2)} words each) — add subheads every 250-350 words.")
        elif words_per_h2 < 120:
            flags.append(f"{len(h2s)} H2s for {total_words} words — too choppy; merge to ~250-350 words per H2.")
    if not h2s:
        flags.append("No H2 sections — structure the body with ## headings.")
    last_h2 = h2s[-1] if h2s else None
    if last_h2 and not CONCLUSION_WORDS.search(last_h2["title"]) and not re.search(r"\b(next|start|get|try|what to do|now)\b", last_h2["title"], re.I):
        flags.append(f"Last H2 '{last_h2['title'][:40]}' isn't a close — end with a next-step/takeaways/FAQ section.")
    lk = c.links(markdown)
    images = c.MD_IMAGE_RE.findall(markdown)
    missing_alt = sum(1 for alt, _ in images if not alt.strip())
    if missing_alt:
        flags.append(f"{missing_alt} image(s) without alt text.")
    if total_words >= 800 and len(lk) < 2:
        flags.append("Fewer than 2 links in an 800+ word post — add sources and internal links.")
    questions = [s["title"] for s in headings if s["title"].rstrip().endswith("?")]
    lists = len(re.findall(r"^\s*(?:[-*+]|\d+[.)])\s+", markdown, re.M))
    tables = len(re.findall(r"^\s*\|.*\|\s*$", markdown, re.M))
    return {
        "total_words": total_words,
        "reading_minutes": round(total_words / 238, 1),
        "h1_count": len(h1s),
        "h2_count": len(h2s),
        "h3_count": sum(1 for s in headings if s["level"] == 3),
        "intro_words": intro_words,
        "sections": section_report,
        "question_headings": questions,
        "links": len(lk),
        "images": len(images),
        "list_items": lists,
        "table_rows": tables,
        "flags": flags,
        "verdict": "Structure passes." if not flags else f"{len(flags)} structural fix(es) before publishing.",
    }


@AGENT.tool
def readability_report(markdown: str, target_grade: float = 8.0) -> dict:
    """Readability lint for prose: grade level, sentence/paragraph length distribution, long sentences listed, passive %, transition-word share.

    Call after drafting; rewrite until it passes. Lists the exact sentences over 30 words
    and paragraphs over 120 words so you can fix them one by one.

    Args:
        markdown: The article (markdown is stripped before analysis).
        target_grade: Flesch-Kincaid grade to aim for (default 8; use 10-12 for technical or academic readers).
    """
    c.guard(markdown, "Markdown")
    if not 3 <= target_grade <= 16:
        raise ToolError("target_grade must be between 3 and 16.")
    plain = c.strip_markdown(markdown)
    ws = text.words(plain)
    if len(ws) < 20:
        raise ToolError("Need at least 20 words of prose to measure readability.")
    sents = text.sentences(plain)
    lens = [len(text.words(s)) for s in sents]
    rd = text.readability(plain)
    passive = text.passive_sentences(plain)
    paras = c.paragraphs(plain)
    para_lens = [len(text.words(p)) for p in paras]
    long_sents = sorted([{"words": n, "sentence": s[:220]} for s, n in zip(sents, lens) if n > 30], key=lambda d: -d["words"])
    long_paras = [{"words": n, "starts": p[:80]} for p, n in zip(paras, para_lens) if n > 120]
    transitions = sum(1 for s in sents if any(re.search(r"\b" + re.escape(t) + r"\b", s[:50].lower()) for t in TRANSITIONS))
    buckets = {"≤10": 0, "11-20": 0, "21-30": 0, ">30": 0}
    for n in lens:
        buckets["≤10" if n <= 10 else "11-20" if n <= 20 else "21-30" if n <= 30 else ">30"] += 1
    you = sum(1 for w in ws if w.lower() in ("you", "your", "you're", "yours"))
    fixes = []
    grade = rd["fk_grade"] or 0
    if grade > target_grade + 1:
        fixes.append(f"Grade {grade} vs target {target_grade}: shorten sentences (avg {rd['avg_words_per_sentence']}) and swap long words.")
    if long_sents:
        fixes.append(f"{len(long_sents)} sentences over 30 words — split each at 'and', 'which' or the comma.")
    passive_pct = c.pct(len(passive), max(1, len(sents)))
    if passive_pct > 10:
        fixes.append(f"Passive voice in {passive_pct}% of sentences (target ≤ 10%).")
    if long_paras:
        fixes.append(f"{len(long_paras)} paragraphs over 120 words — break at the idea change.")
    trans_pct = c.pct(transitions, max(1, len(sents)))
    if trans_pct < 25:
        fixes.append(f"Transition words in only {trans_pct}% of sentences (target ≥ 25%) — the argument may read as a list of facts.")
    if buckets["≤10"] + buckets["11-20"] < 0.5 * len(lens):
        fixes.append("Fewer than half the sentences are under 20 words — the post reads as dense.")
    if you == 0 and len(ws) > 300:
        fixes.append("The word 'you' never appears — address the reader directly.")
    passes = not fixes
    return {
        "words": len(ws),
        "sentences": len(sents),
        "paragraphs": len(paras),
        "fk_grade": grade,
        "target_grade": target_grade,
        "flesch_reading_ease": rd["flesch_reading_ease"],
        "reading_level": rd.get("reading_level"),
        "avg_sentence_words": rd["avg_words_per_sentence"],
        "sentence_length_buckets": buckets,
        "long_sentences": long_sents[:15],
        "long_paragraphs": long_paras[:10],
        "avg_paragraph_words": round(sum(para_lens) / max(1, len(para_lens)), 1),
        "passive_sentences": len(passive),
        "passive_pct": passive_pct,
        "passive_examples": [s[:160] for s in passive[:6]],
        "transition_sentence_pct": trans_pct,
        "you_count": you,
        "fixes": fixes,
        "verdict": "Readability passes." if passes else f"{len(fixes)} readability fix(es) needed.",
    }


def slugify(s: str) -> str:
    s = re.sub(r"[’'\"]", "", s.lower())
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    stop = {"a", "an", "the", "of", "to", "in", "for", "and", "or", "on", "with", "your", "is", "how", "what", "why"}
    parts = [p for p in s.split("-") if p and p not in stop]
    return "-".join(parts[:6]) or s[:60]


@AGENT.tool
def keyword_audit(markdown: str, primary_keyword: str, secondary_keywords: list[str] | None = None, title: str = "", meta_description: str = "") -> dict:
    """Keyword density and placement audit (title, H1, first 100 words, H2s, last paragraph, alt text) plus title/meta length checks and a URL slug.

    Call once the draft is finished. Density target 0.5-2.0%; over 2.5% is stuffing. Also
    scores placement out of 5 and reports each secondary keyword's coverage.

    Args:
        markdown: The full article in markdown.
        primary_keyword: The exact primary keyword phrase (2-6 words typical).
        secondary_keywords: Related phrases that should appear at least once, ideally in a heading.
        title: The SEO title tag (if separate from the H1). Checked for ≤ 60 chars and keyword position.
        meta_description: The meta description. Checked for 120-155 chars and keyword presence.
    """
    c.guard(markdown, "Markdown")
    kw = (primary_keyword or "").strip()
    if not kw or len(kw) > 100:
        raise ToolError("primary_keyword must be 1-100 characters.")
    secondary_keywords = [s.strip() for s in (secondary_keywords or []) if s and s.strip()][:20]
    plain = c.strip_markdown(markdown)
    ws = text.words(plain)
    if len(ws) < 50:
        raise ToolError("Need at least 50 words of prose to audit keyword use.")
    dens = text.keyword_density(plain, kw)
    secs = c.sections(markdown)
    headings = [s for s in secs if s["level"] > 0]
    h1 = next((s["title"] for s in headings if s["level"] == 1), "")
    h2s = [s["title"] for s in headings if s["level"] == 2]
    kw_re = re.compile(r"(?<!\w)" + r"\W+".join(re.escape(w) for w in text.words(kw)) + r"(?!\w)", re.I)
    first100 = " ".join(ws[:100])
    paras = c.paragraphs(plain)
    last_para = paras[-1] if paras else ""
    alts = [alt for alt, _ in c.MD_IMAGE_RE.findall(markdown)]
    eff_title = title or h1
    placements = {
        "title": bool(kw_re.search(eff_title)),
        "h1": bool(kw_re.search(h1)) if h1 else None,
        "first_100_words": bool(kw_re.search(first100)),
        "any_h2": any(kw_re.search(h) for h in h2s),
        "last_paragraph": bool(kw_re.search(last_para)),
        "image_alt": any(kw_re.search(a) for a in alts) if alts else None,
    }
    placement_score = sum(1 for k in ("title", "first_100_words", "any_h2", "last_paragraph") if placements[k]) + (1 if placements["h1"] or (placements["h1"] is None and placements["title"]) else 0)
    fixes = []
    if dens["density_pct"] < 0.5:
        fixes.append(f"Density {dens['density_pct']}% ({dens['occurrences']}×) is under 0.5% — use the exact phrase a few more times where natural.")
    elif dens["density_pct"] > 2.5:
        fixes.append(f"Density {dens['density_pct']}% ({dens['occurrences']}×) is stuffing — cut to ≤ 2% with variants and pronouns.")
    for k, label in (("title", "title"), ("first_100_words", "first 100 words"), ("any_h2", "at least one H2"), ("last_paragraph", "last paragraph")):
        if not placements[k]:
            fixes.append(f"Primary keyword missing from the {label}.")
    if eff_title:
        if len(eff_title) > 60:
            fixes.append(f"Title is {len(eff_title)} chars — trim to ≤ 60 so it isn't truncated in search results.")
        m = kw_re.search(eff_title)
        if m and m.start() > 30:
            fixes.append("Keyword sits late in the title — move it toward the front.")
    if meta_description:
        n = len(meta_description)
        if n < 120 or n > 155:
            fixes.append(f"Meta description is {n} chars — aim for 120-155.")
        if not kw_re.search(meta_description):
            fixes.append("Meta description doesn't contain the primary keyword.")
    secondary = []
    for s in secondary_keywords:
        sd = text.keyword_density(plain, s)
        s_re = re.compile(r"(?<!\w)" + r"\W+".join(re.escape(w) for w in text.words(s)) + r"(?!\w)", re.I)
        in_heading = any(s_re.search(h["title"]) for h in headings)
        secondary.append({"keyword": s, "occurrences": sd["occurrences"], "in_heading": in_heading})
        if sd["occurrences"] == 0:
            fixes.append(f"Secondary keyword '{s}' never appears.")
    # over-use of the exact phrase in headings
    kw_in_h2 = sum(1 for h in h2s if kw_re.search(h))
    if h2s and kw_in_h2 > max(2, len(h2s) // 2):
        fixes.append(f"Exact keyword in {kw_in_h2}/{len(h2s)} H2s — vary the phrasing.")
    return {
        "primary_keyword": kw,
        "occurrences": dens["occurrences"],
        "density_pct": dens["density_pct"],
        "density_band": "low" if dens["density_pct"] < 0.5 else "stuffing" if dens["density_pct"] > 2.5 else "good",
        "placements": placements,
        "placement_score": f"{placement_score}/5",
        "title": {"text": eff_title, "chars": len(eff_title), "fits_60": len(eff_title) <= 60} if eff_title else None,
        "meta_description": {"chars": len(meta_description), "in_range": 120 <= len(meta_description) <= 155, "has_keyword": bool(kw_re.search(meta_description))} if meta_description else None,
        "secondary": secondary,
        "suggested_slug": slugify(kw),
        "top_terms": [w for w, _ in text.top_terms(plain, 10)],
        "fixes": fixes,
        "verdict": "Keyword use passes." if not fixes else f"{len(fixes)} keyword/meta fix(es).",
    }
