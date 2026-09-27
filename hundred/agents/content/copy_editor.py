"""Copy Editor — a three-pass line edit with every change justified and measured.

Free forever: the content category's lead magnet. It has to feel like handing a
draft to the best line editor you have ever worked with.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter

from ...core import Agent, ToolError
from ...lib import text
from . import _common as c

AGENT = Agent(
    slug="copy-editor",
    name="Copy Editor",
    category="content",
    free=True,
    tagline="Paste a draft; get a tighter, clearer version with every cut justified and the improvement measured.",
    description=(
        "A professional three-pass line edit: structure, then sentences, then proof. Finds passive voice, "
        "limp adverbs, hedges, clichés, AI-sounding phrases, echo words and run-on sentences with exact "
        "locations; applies deterministic tighten-ups (in order to → to); checks house-style consistency "
        "(quotes, dashes, numbers, US/UK spelling); and proves the edit helped with a before/after "
        "readability diff. Preserves your voice and meaning — it edits, it doesn't rewrite."
    ),
    triggers=[
        "edit / proofread / tighten this draft",
        "make this clearer or shorter without changing the meaning",
        "check my writing for passive voice, adverbs, clichés",
        "does this sound like AI wrote it? make it sound human",
        "line edit this article, email, or landing page copy",
        "copyedit for consistency and style",
    ],
    examples=[
        "Edit this blog intro. Keep my voice, but it feels flabby: <draft>",
        "Proofread this customer email before I send it — it's going to 4,000 people.",
        "This landing page copy reads like ChatGPT wrote it. Fix that.",
        "Tighten this 900-word essay to 700 without losing the argument.",
    ],
    connectors=["Google Docs", "Notion", "Gmail", "Microsoft Word"],
    playbook="""
    ## Standard
    You are a senior line editor — the kind magazines keep on retainer. Excellent means the
    author reads the edit and thinks "that's what I meant, only better", never "you changed
    what I said". You cut, clarify and correct; you do not rewrite in your own voice, add ideas,
    or smooth out deliberate style. The one metric: **fewer words carrying the same meaning at
    a lower reading grade, with zero factual drift.** Every change must be explainable in one
    clause ("passive → active", "cliché", "redundant").

    ## Intake
    You need the draft. Assume the audience is a smart general reader (target Flesch-Kincaid
    grade 7-9) unless the text is clearly academic, legal or technical — then target grade
    10-12 and say so. Assume the author's spelling variant (US/UK) from the majority of the
    text. Ask a question only if (a) there's a hard length target you can't infer, or
    (b) the piece is legal/medical/financial copy where a cut could change liability. Never
    ask "what tone do you want?" — infer it from the draft and preserve it.

    ## Procedure
    1. **Diagnose before touching a word.** Call `copy_editor__diagnose` with the full draft.
       Read the score and every finding list. This is your edit plan: the findings with the
       highest counts are the pass-one priorities. Note the baseline numbers (words, grade,
       passive %, adverb rate) — you will prove improvement against them in step 6.
    2. **Pass one — structure (macro edit).** Before line edits: does the first paragraph
       earn the second? Is the point in the first 10% of the piece? Cut throat-clearing
       openers ("In today's world…", "As we all know…"), move the buried lede up, delete
       paragraphs that repeat an earlier one, and flag (don't fix) missing evidence. Keep the
       author's paragraph order unless a reorder is clearly better; then explain it.
    3. **Pass two — sentences (line edit).** Apply the canon, in this priority:
       - Zinsser's clutter test: every word must do work. Cut the ones that don't.
       - Active voice unless the actor is unknown or unimportant (Orwell rule 4). Passive
         is fine in "The suspect was arrested" — leave it when the receiver *is* the story.
       - One idea per sentence; > 30 words → split, unless it's a deliberate cadence.
       - Strong verb over verb + noun: "decide" not "make a decision".
       - Gopen & Swan: put the new/important information at the end of the sentence
         (the stress position) and the known context at the start.
       - Hedges and intensifiers: delete "very", "really", "just", "actually"; keep a hedge
         only where uncertainty is real.
       - Vary sentence length: after two long sentences, land a short one.
       Run `copy_editor__find_replacements` to apply the mechanical tighten-ups ("in order
       to" → "to", "utilize" → "use"). Use its `rewritten` text as your working copy, and
       list its edits in the change log so nothing looks like magic.
    4. **Pass three — proof (mechanics).** Call `copy_editor__style_check` on your edited
       text. Fix everything it flags: doubled words, spacing, mixed curly/straight quotes,
       spaced hyphens used as dashes, US/UK spelling drift, numerals under ten, "it's/its",
       Oxford-comma inconsistency. Pick the *author's majority* convention; never impose a
       house style they didn't ask for. If they name a style (AP, Chicago), apply it.
    5. **Meaning check.** Reread the original and your edit side by side. Any number, name,
       claim, qualifier ("some", "most", "up to") or negation that changed is a bug. Restore it.
    6. **Prove it.** Call `copy_editor__readability_diff` with original and edited text.
       Report the deltas. If word count dropped more than 35%, say explicitly that you cut
       content (list what) so the author can veto. If the grade went *up*, you made it worse
       — go back to pass two.
    7. **Deliver** in the output format. Then act: if the draft lives in Google Docs/Notion
       and the connector is available, apply the edit there (as suggestions when the
       platform supports it); otherwise return paste-ready text.

    ## Frameworks
    - **The 3-pass edit**: macro (structure) → line (sentences) → proof (mechanics). Never
      polish sentences in a paragraph you are about to cut.
    - **Targets for web/business copy**: passive ≤ 5% of sentences; adverbs ≤ 1 per 100
      words; average sentence 14-20 words with a standard deviation ≥ 6 (rhythm); no
      paragraph > 120 words; zero clichés; zero AI-tells; Flesch Reading Ease ≥ 60.
    - **Fiction / literary**: relax the adverb and length rules; protect voice; fragments are
      legal. Flag only genuine errors and echoes.
    - **The echo rule**: a distinctive word (≥ 5 letters, not a keyword) repeated within
      ~40 words is an echo unless it is deliberate anaphora.
    - **Orwell's six rules** as the tie-breaker; rule 6: break any rule sooner than say
      anything barbarous.

    ## Output format
    ```
    ## Edited text
    <the full edited draft, paste-ready — same paragraphing as the original unless noted>

    ## What changed
    | # | Original | Edited | Why |
    |---|---|---|---|
    | 1 | "…" | "…" | passive → active |
    (Group trivial mechanical fixes as one row: "12 × 'in order to' → 'to'".)

    ## Before → after
    Words: 912 → 704 (−23%) · Grade: 11.2 → 8.4 · Passive: 9 → 1 · Adverbs: 14 → 3 · FRE: 48 → 66

    ## Left alone (and why)
    - <deliberate passive / voice choices / claims that need the author's fact-check>

    ## Questions for the author
    - <only if a cut could change meaning or a fact needs checking; otherwise omit>
    ```

    ## Anti-patterns
    - Rewriting into your own cadence. If a sentence works, leave it — even if you'd say it differently.
    - "Improving" by adding: transitions, adjectives, a summary sentence. Editing removes.
    - Blind rules: killing every passive, every adverb, every "that". Judgement over regex.
    - Changing meaning quietly: "up to 40%" → "40%", "may" → "will", dropping a qualifier.
    - Homogenising voice into corporate neutral. Slang, fragments and humour stay if intentional.
    - Reporting "I improved readability" without the numbers. Always show the diff.
    - Fixing typos in quoted material. Mark them [sic] and tell the author.
    """,
)

ADVERB_WHITELIST = {
    "only", "early", "family", "reply", "supply", "apply", "july", "ally", "belly", "bully", "fly",
    "rally", "jelly", "holy", "ugly", "silly", "daily", "lily", "italy", "rely", "imply", "multiply",
    "assembly", "monopoly", "anomaly", "butterfly", "friendly", "lonely", "lovely", "likely", "elderly",
    "orderly", "costly", "deadly", "lively", "timely", "weekly", "monthly", "yearly", "hourly", "chilly",
    "hilly", "jolly", "folly", "tally", "dolly", "bodily", "unlikely", "sly", "ply", "italy", "fully",
    "comply", "gully", "sully", "willy", "billy", "polly", "molly", "sally", "wally", "kelly", "nelly",
    "smelly", "burly", "curly", "surly", "early", "pearly", "girly", "ghastly", "melancholy", "supply",
}

NOMINALISATIONS = [
    ("make a decision", "decide"), ("made a decision", "decided"), ("come to a conclusion", "conclude"),
    ("reach a conclusion", "conclude"), ("conduct an analysis", "analyse"), ("perform an analysis", "analyse"),
    ("provide assistance", "help"), ("give consideration to", "consider"), ("take into consideration", "consider"),
    ("make an assessment", "assess"), ("carry out an evaluation", "evaluate"), ("have a discussion", "discuss"),
    ("make a recommendation", "recommend"), ("provide an explanation", "explain"), ("make an announcement", "announce"),
    ("give an indication", "indicate"), ("take action", "act"), ("make a comparison", "compare"),
    ("make use of", "use"), ("is indicative of", "indicates"), ("is reflective of", "reflects"),
    ("put emphasis on", "emphasise"), ("place emphasis on", "emphasise"), ("make a payment", "pay"),
    ("have a tendency to", "tend to"), ("has a tendency to", "tends to"), ("make an attempt", "try"),
    ("give a presentation", "present"), ("make a contribution", "contribute"), ("is in agreement", "agrees"),
    ("are in agreement", "agree"), ("come to an agreement", "agree"), ("make an improvement", "improve"),
]

REPLACEMENTS: list[tuple[str, str]] = [
    ("in order to", "to"), ("in order for", "for"), ("at this point in time", "now"), ("at the present time", "now"),
    ("at this moment in time", "now"), ("due to the fact that", "because"), ("owing to the fact that", "because"),
    ("in light of the fact that", "because"), ("in view of the fact that", "because"), ("in the event that", "if"),
    ("for the purpose of", "to"), ("in spite of the fact that", "although"), ("despite the fact that", "although"),
    ("a large number of", "many"), ("a great number of", "many"), ("a majority of", "most"), ("the majority of", "most"),
    ("in close proximity to", "near"), ("prior to", "before"), ("subsequent to", "after"), ("with regard to", "about"),
    ("in regard to", "about"), ("in regards to", "about"), ("with respect to", "about"), ("in relation to", "about"),
    ("in reference to", "about"), ("in the near future", "soon"), ("on a daily basis", "daily"),
    ("on a weekly basis", "weekly"), ("on a monthly basis", "monthly"), ("on a regular basis", "regularly"),
    ("has the ability to", "can"), ("have the ability to", "can"), ("is able to", "can"), ("are able to", "can"),
    ("was able to", "could"), ("were able to", "could"), ("it is important to note that", ""), ("it should be noted that", ""),
    ("it is worth noting that", ""), ("needless to say,", ""), ("the fact that", "that"), ("each and every", "every"),
    ("first and foremost", "first"), ("in the process of", ""), ("as a matter of fact", "in fact"),
    ("at all times", "always"), ("in a timely manner", "promptly"), ("in a timely fashion", "promptly"),
    ("whether or not", "whether"), ("the reason is because", "because"), ("very unique", "unique"),
    ("past history", "history"), ("end result", "result"), ("final outcome", "outcome"), ("future plans", "plans"),
    ("advance planning", "planning"), ("free gift", "gift"), ("completely finished", "finished"),
    ("absolutely essential", "essential"), ("basic fundamentals", "fundamentals"), ("close proximity", "proximity"),
    ("added bonus", "bonus"), ("unexpected surprise", "surprise"), ("new innovation", "innovation"),
    ("utilize", "use"), ("utilise", "use"), ("utilizes", "uses"), ("utilises", "uses"), ("utilized", "used"),
    ("utilised", "used"), ("utilizing", "using"), ("utilising", "using"), ("commence", "start"), ("commenced", "started"),
    ("terminate", "end"), ("terminated", "ended"), ("endeavor to", "try to"), ("endeavour to", "try to"),
    ("facilitate", "help"), ("in terms of", "for"), ("sufficient", "enough"), ("approximately", "about"),
    ("numerous", "many"), ("additional", "more"), ("assistance", "help"), ("in the amount of", "for"),
    ("a total of", ""), ("in excess of", "more than"), ("in the vicinity of", "near"), ("with the exception of", "except"),
    ("in the absence of", "without"), ("is of the opinion that", "thinks"), ("in accordance with", "under"),
    ("notwithstanding", "despite"), ("on the grounds that", "because"), ("until such time as", "until"),
    ("at the conclusion of", "after"), ("during the course of", "during"), ("for the reason that", "because"),
    ("in the majority of cases", "usually"), ("in many cases", "often"), ("in most cases", "usually"),
    ("it is possible that", "perhaps"), ("there is no doubt that", "clearly"), ("take into account", "consider"),
    ("along the lines of", "like"), ("as to whether", "whether"), ("give rise to", "cause"), ("in the course of", "during"),
]
for _long, _short in NOMINALISATIONS:
    REPLACEMENTS.append((_long, _short))
JUDGEMENT_CALLS = {"approximately", "additional", "sufficient", "numerous", "assistance", "facilitate", "in terms of", "commence", "commenced", "terminate", "terminated", "in accordance with", "notwithstanding"}
QUOTE_RE = re.compile(r"\"[^\"\n]{1,400}\"|“[^”\n]{1,400}”")

TRANSITIONS = {
    "however", "therefore", "moreover", "furthermore", "consequently", "meanwhile", "nevertheless", "instead",
    "because", "so", "but", "yet", "then", "first", "second", "third", "finally", "next", "also", "although",
    "while", "since", "thus", "hence", "for example", "for instance", "in short", "in other words", "still",
}


def _sentences(plain: str) -> list[str]:
    return text.sentences(plain)


def _adverbs(ws: list[str]) -> list[str]:
    return [w for w in ws if len(w) > 4 and w.lower().endswith("ly") and w.lower() not in ADVERB_WHITELIST]


def _echoes(ws: list[str], window: int = 40) -> list[dict]:
    seen: dict[str, int] = {}
    out: list[dict] = []
    for i, w in enumerate(ws):
        lw = w.lower()
        if len(lw) < 5 or lw in text.STOPWORDS or lw.endswith("ing") and lw in ("thing", "being"):
            continue
        if lw in seen and i - seen[lw] <= window:
            out.append({"word": lw, "gap_words": i - seen[lw], "position_word": i + 1})
        seen[lw] = i
    dedup: dict[str, dict] = {}
    for e in out:
        dedup.setdefault(e["word"], {"word": e["word"], "count": 0, "min_gap": e["gap_words"]})
        dedup[e["word"]]["count"] += 1
        dedup[e["word"]]["min_gap"] = min(dedup[e["word"]]["min_gap"], e["gap_words"])
    return sorted(dedup.values(), key=lambda d: (-d["count"], d["min_gap"]))[:20]


@AGENT.tool
def diagnose(draft: str, genre: str = "web") -> dict:
    """Full diagnostic of a draft: score 0-100 plus every passive, adverb, hedge, cliché, AI-tell, echo and run-on with locations.

    Call first, before editing. Returns the baseline numbers you will beat and a
    prioritised fix list. Genre "web" (default), "business", "academic" or "fiction"
    changes the thresholds.

    Args:
        draft: The text to edit (markdown is fine — it is stripped for analysis).
        genre: One of web, business, academic, fiction. Sets tolerance for passive voice, adverbs and sentence length.
    """
    c.guard(draft, "Draft")
    genre = (genre or "web").lower().strip()
    if genre not in ("web", "business", "academic", "fiction"):
        raise ToolError("genre must be one of: web, business, academic, fiction")
    plain = c.strip_markdown(draft)
    ws = text.words(plain)
    if len(ws) < 5:
        raise ToolError("Draft has fewer than 5 words — nothing to diagnose.")
    sents = _sentences(plain)
    n_s = max(1, len(sents))
    rd = text.readability(plain)
    lens = [len(text.words(s)) for s in sents]
    passive = text.passive_sentences(plain)
    adverbs = _adverbs(ws)
    hedges = c.find_phrases(plain, c.HEDGES)
    cliches = c.find_phrases(plain, c.CLICHES)
    ai = c.find_phrases(plain, c.AI_TELLS)
    nominal = c.find_phrases(plain, [n for n, _ in NOMINALISATIONS])
    long_limit = {"web": 25, "business": 28, "academic": 35, "fiction": 40}[genre]
    long_sents = [{"words": n, "sentence": s[:200]} for s, n in zip(sents, lens) if n > long_limit]
    paras = c.paragraphs(plain)
    long_paras = [{"words": len(text.words(p)), "starts": p[:80]} for p in paras if len(text.words(p)) > 120]
    starts = [text.words(s)[0].lower() for s in sents if text.words(s)]
    same_start = []
    run = 1
    for i in range(1, len(starts)):
        run = run + 1 if starts[i] == starts[i - 1] else 1
        if run == 3:
            same_start.append({"word": starts[i], "sentence_index": i - 1})
    echoes = _echoes(ws)
    transitions = sum(1 for s in sents if any(re.search(r"\b" + re.escape(t) + r"\b", s[:40].lower()) for t in TRANSITIONS))
    stdev = round(statistics.pstdev(lens), 1) if len(lens) > 1 else 0.0
    per100 = lambda n: round(100.0 * n / len(ws), 2)  # noqa: E731

    passive_pct = c.pct(len(passive), n_s)
    adverb_rate = per100(len(adverbs))
    hedge_n = sum(h["count"] for h in hedges)
    ai_n = sum(h["count"] for h in ai)
    cliche_n = sum(h["count"] for h in cliches)
    tol_passive = {"web": 5, "business": 10, "academic": 20, "fiction": 10}[genre]
    tol_adverb = {"web": 1.0, "business": 1.5, "academic": 1.5, "fiction": 2.5}[genre]

    score = 100.0
    score -= max(0.0, passive_pct - tol_passive) * 1.5
    score -= max(0.0, adverb_rate - tol_adverb) * 8
    score -= per100(hedge_n) * 6
    score -= cliche_n * 4
    score -= ai_n * 3
    score -= len(long_sents) / n_s * 100 * 0.6
    score -= min(15, len(echoes) * 1.5)
    score -= len(same_start) * 2
    score -= len(long_paras) * 2
    if genre != "fiction" and rd["fk_grade"] is not None:
        target = 12 if genre == "academic" else 9
        score -= max(0.0, rd["fk_grade"] - target) * 3
    if stdev < 4 and len(lens) >= 6:
        score -= 6
    score = int(max(0, min(100, round(score))))

    fixes = []
    if passive_pct > tol_passive:
        fixes.append(f"Passive voice in {passive_pct}% of sentences (target ≤ {tol_passive}%): rewrite with the actor as subject.")
    if adverb_rate > tol_adverb:
        fixes.append(f"{len(adverbs)} -ly adverbs ({adverb_rate}/100 words): cut them or pick a stronger verb.")
    if hedge_n:
        fixes.append(f"{hedge_n} hedges/intensifiers: delete unless the uncertainty is real.")
    if cliche_n:
        fixes.append(f"{cliche_n} clichés: replace with a plain or specific phrase.")
    if ai_n:
        fixes.append(f"{ai_n} AI-sounding phrases: cut or replace with concrete language.")
    if long_sents:
        fixes.append(f"{len(long_sents)} sentences over {long_limit} words: split at the conjunction.")
    if echoes:
        fixes.append(f"Echoes: {', '.join(e['word'] for e in echoes[:5])} — vary or cut the repeat.")
    if same_start:
        fixes.append("Three+ consecutive sentences open with the same word: vary the openers.")
    if long_paras:
        fixes.append(f"{len(long_paras)} paragraphs over 120 words: break them.")
    if stdev < 4 and len(lens) >= 6:
        fixes.append(f"Sentence length is monotonous (σ = {stdev}): mix short punches with longer lines.")
    if rd["fk_grade"] and rd["fk_grade"] > (12 if genre == "academic" else 9) and genre != "fiction":
        fixes.append(f"Grade {rd['fk_grade']} is above target: shorter sentences, shorter words.")
    if nominal:
        fixes.append("Verb-noun pairs (make a decision → decide): use the verb.")

    verdict = (
        "Clean — proof pass only." if score >= 85 else
        "Solid draft — a line edit will lift it." if score >= 65 else
        "Needs a real edit — work the fix list top to bottom." if score >= 40 else
        "Structural problems — do the macro pass before touching sentences."
    )
    return {
        "score": score,
        "verdict": verdict,
        "genre": genre,
        "baseline": {
            "words": len(ws), "sentences": len(sents), "paragraphs": len(paras),
            "avg_sentence_words": rd.get("avg_words_per_sentence"), "sentence_length_stdev": stdev,
            "fk_grade": rd["fk_grade"], "flesch_reading_ease": rd["flesch_reading_ease"], "reading_level": rd.get("reading_level"),
            "passive_sentences": len(passive), "passive_pct": passive_pct,
            "adverbs": len(adverbs), "adverbs_per_100_words": adverb_rate,
            "hedges": hedge_n, "cliches": cliche_n, "ai_tells": ai_n,
            "long_sentences": len(long_sents), "transition_sentence_pct": c.pct(transitions, n_s),
        },
        "findings": {
            "passive": [s[:200] for s in passive[:25]],
            "adverbs": sorted(Counter(a.lower() for a in adverbs).most_common(25)),
            "hedges": hedges[:20],
            "cliches": cliches[:20],
            "ai_tells": ai[:20],
            "nominalisations": nominal[:15],
            "long_sentences": long_sents[:15],
            "echoes": echoes[:10],
            "same_opener_runs": same_start[:10],
            "long_paragraphs": long_paras[:10],
        },
        "fixes": fixes,
    }


@AGENT.tool
def find_replacements(draft: str, aggressive: bool = False) -> dict:
    """Apply the mechanical tighten-ups (in order to → to, utilize → use, make a decision → decide) and return the rewritten text plus an edit log.

    Case-preserving, whole-phrase, leaves quoted text alone. Use the `rewritten` text as
    your working copy and copy the `edits` into the change log.

    Args:
        draft: The text to tighten.
        aggressive: Also apply the judgement calls (approximately → about, additional → more, sufficient → enough) that occasionally change nuance.
    """
    c.guard(draft, "Draft")
    active = [(l, s) for l, s in REPLACEMENTS if aggressive or l not in JUDGEMENT_CALLS]
    lookup = {l.lower(): s for l, s in active}
    pat = re.compile(c.phrase_pattern(tuple(lookup)).pattern + r"(?P<tail>[ ,]*)", re.I)
    quoted = [m.span() for m in QUOTE_RE.finditer(draft)]
    counts: dict[str, int] = {}

    def sub(m: re.Match) -> str:
        if any(a <= m.start() < b for a, b in quoted):
            return m.group(0)
        src = m.group(0)[: len(m.group(0)) - len(m.group("tail"))]
        key = src.lower()
        counts[key] = counts.get(key, 0) + 1
        short_p = lookup[key]
        if short_p:
            rep = short_p[0].upper() + short_p[1:] if src[0].isupper() else short_p
            return rep + m.group("tail")
        # deletion: drop the phrase and the comma/space after it; re-capitalise the next word if it opened a sentence
        return "\u0001" if src[0].isupper() else ""

    out = pat.sub(sub, draft)
    if "\u0001" in out:
        out = re.sub(r"\u0001(\w)", lambda m: m.group(1).upper(), out).replace("\u0001", "")
    edits = [{"from": k, "to": lookup[k] or "(deleted)", "count": n} for k, n in counts.items()]
    out = re.sub(r"[ \t]{2,}", " ", out)
    before_w, after_w = len(text.words(draft)), len(text.words(out))
    total = sum(e["count"] for e in edits)
    return {
        "rewritten": out,
        "edits": sorted(edits, key=lambda e: -e["count"]),
        "total_edits": total,
        "words_before": before_w,
        "words_after": after_w,
        "words_saved": before_w - after_w,
        "summary": (f"{total} mechanical tighten-ups, {before_w - after_w} words saved." if total else "No mechanical tighten-ups found — the draft is already lean at the phrase level."),
    }


UK_MARKERS = re.compile(r"\b(colour|favour|honour|behaviour|labour|neighbour|centre|theatre|metre|litre|licence|defence|offence|programme|catalogue|analyse|organise|organisation|realise|recognise|travelled|travelling|cancelled|grey|cheque|tyre|kerb|aluminium|mould|plough|sceptical|practise|enquiry|whilst|amongst|learnt|spelt)\b", re.I)
US_MARKERS = re.compile(r"\b(color|favor|honor|behavior|labor|neighbor|center|theater|meter|liter|license|defense|offense|program|catalog|analyze|organize|organization|realize|recognize|traveled|traveling|canceled|gray|check|tire|curb|aluminum|mold|plow|skeptical|inquiry|learned|spelled)\b", re.I)
COMMON_ERRORS = [
    (r"\balot\b", "a lot"), (r"\birregardless\b", "regardless"), (r"\bcould of\b", "could have"), (r"\bshould of\b", "should have"),
    (r"\bwould of\b", "would have"), (r"\bit's own\b", "its own"), (r"\bits a\b", "it's a"), (r"\bits not\b", "it's not"),
    (r"\byour welcome\b", "you're welcome"), (r"\bthen again\b", None), (r"\bless (?:people|items|things|words|days|times|users|customers)\b", "fewer …"),
    (r"\bvery unique\b", "unique"), (r"\bmore unique\b", "unique"), (r"\bfor all intensive purposes\b", "for all intents and purposes"),
    (r"\bi\b(?![.'’])", "I (capitalise)"), (r"\bthe the\b", "the"), (r"\ba a\b", "a"), (r"\bto to\b", "to"), (r"\bin in\b", "in"), (r"\bof of\b", "of"),
    (r"\band and\b", "and"), (r"\bis is\b", "is"), (r"\bthat that\b", "that"), (r"\bcomprised of\b", "composed of / comprises"),
    (r"\bshould've of\b", "should have"), (r"\beveryday\s+(?:i|we|you|they|he|she)\b", "every day"), (r"\bloose\s+(?:the|a|my|our)\b", "lose"),
]


@AGENT.tool
def style_check(draft: str, style: str = "author") -> dict:
    """Proof pass: doubled words, spacing, mixed quote/dash styles, US-vs-UK drift, numerals, its/it's, Oxford-comma consistency, common errors.

    Run on the *edited* text as the final pass. Reports every inconsistency with a snippet
    so you can fix it, and which convention the author uses most (so you match it).

    Args:
        draft: The text to proof.
        style: "author" (default — match the author's majority convention), "ap" (AP style: spell out one-nine, no Oxford comma, US spelling) or "chicago" (spell out one-hundred, Oxford comma, US spelling).
    """
    c.guard(draft, "Draft")
    style = (style or "author").lower()
    if style not in ("author", "ap", "chicago"):
        raise ToolError("style must be author, ap or chicago")
    plain = c.strip_markdown(draft)
    issues: list[dict] = []

    def add(kind: str, msg: str, pos: int | None = None, count: int = 1):
        issues.append({"kind": kind, "issue": msg, "count": count, "snippet": c.context(plain, pos, 30) if pos is not None else ""})

    for m in re.finditer(r"[^\n\S]{2,}\S", plain):
        add("spacing", "double space", m.start())
    for m in re.finditer(r"\s+[,.;:!?](?!\.)", plain):
        add("spacing", "space before punctuation", m.start())
    for m in re.finditer(r"[a-z]\.\s+[a-z]{2,}", plain):
        add("capitalisation", "sentence starts lowercase", m.start())
    for pat, fix in COMMON_ERRORS:
        for m in re.finditer(pat, plain, re.I):
            if fix:
                add("error", f"'{m.group(0)}' → {fix}", m.start())
    straight = len(re.findall(r"\"", plain))
    curly = len(re.findall(r"[“”]", plain))
    if straight and curly:
        add("consistency", f"mixed straight ({straight}) and curly ({curly}) double quotes — pick one", count=straight + curly)
    em, en, spaced_hyphen, double_hyphen = plain.count("—"), plain.count("–"), len(re.findall(r"\w -{1} \w", plain)), plain.count("--")
    dash_styles = [n for n, v in (("em dash", em), ("en dash", en), ("spaced hyphen", spaced_hyphen), ("double hyphen", double_hyphen)) if v]
    if len(dash_styles) > 1:
        add("consistency", f"mixed dash styles: {', '.join(dash_styles)} — use one (em dash for asides, en dash for ranges)", count=em + en + spaced_hyphen + double_hyphen)
    if spaced_hyphen and not em:
        add("consistency", f"{spaced_hyphen} spaced hyphens used as dashes — use an em dash (—)", count=spaced_hyphen)
    uk = len(UK_MARKERS.findall(plain))
    us = len(US_MARKERS.findall(plain))
    variant = "UK" if uk > us else "US" if us > uk else "undetermined"
    if style in ("ap", "chicago"):
        variant = "US"
    if uk and us and variant != "undetermined":
        minority = UK_MARKERS if variant == "US" else US_MARKERS
        for m in list(minority.finditer(plain))[:10]:
            add("spelling", f"'{m.group(0)}' is {'UK' if variant == 'US' else 'US'} spelling; text is mostly {variant}", m.start())
    spell_limit = 100 if style == "chicago" else 9
    for m in re.finditer(r"(?<![\d.,$£€%:-])\b([1-9])\b(?![\d.,:%]|\s*(?:%|percent|am|pm|a\.m\.|p\.m\.|x\b|st\b|nd\b|rd\b|th\b|/))", plain):
        add("numbers", f"numeral '{m.group(1)}' in prose — spell out numbers under {spell_limit + 1} (keep digits for data, ages, money, %)", m.start())
    words_n = {"ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "fifty": 50, "hundred": 100}
    if style != "chicago":
        for m in re.finditer(r"\b(eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)\b(?!-)", plain, re.I):
            add("numbers", f"'{m.group(0)}' — use numerals for 10 and above", m.start())
    oxford = len(re.findall(r"\w+, \w+, (?:and|or) \w+", plain))
    no_oxford = len(re.findall(r"\w+, \w+ (?:and|or) \w+", plain))
    if oxford and no_oxford:
        add("consistency", f"Oxford comma used {oxford}×, omitted {no_oxford}× — be consistent", count=oxford + no_oxford)
    elif style == "ap" and oxford:
        add("consistency", f"AP style omits the serial comma ({oxford} found)", count=oxford)
    elif style == "chicago" and no_oxford:
        add("consistency", f"Chicago uses the serial comma ({no_oxford} missing)", count=no_oxford)
    pct_sign, pct_word = len(re.findall(r"\d%", plain)), len(re.findall(r"\d\s?percent\b", plain, re.I))
    if pct_sign and pct_word:
        add("consistency", f"'%' ({pct_sign}) and 'percent' ({pct_word}) both used", count=pct_sign + pct_word)
    for m in re.finditer(r"[!?]{2,}|!\s*!", plain):
        add("punctuation", "stacked punctuation (!!, ?!) — one mark", m.start())
    excl = plain.count("!")
    if excl > max(2, len(text.words(plain)) // 200):
        add("punctuation", f"{excl} exclamation marks — allow yourself one per piece", count=excl)
    for m in re.finditer(r"\(\s*\)|\[\s*\]", plain):
        add("punctuation", "empty brackets", m.start())
    for m in re.finditer(r"\bTBD\b|\bTODO\b|\bXXX\b|\[insert[^\]]*\]|\blorem ipsum\b", plain, re.I):
        add("placeholder", f"placeholder left in: '{m.group(0)}'", m.start())
    by_kind = Counter(i["kind"] for i in issues)
    return {
        "style_applied": style,
        "spelling_variant": variant,
        "issues": issues[:80],
        "issue_count": len(issues),
        "by_kind": dict(by_kind),
        "verdict": "Clean proof." if not issues else f"{len(issues)} mechanical issues — fix before delivery ({', '.join(f'{k} {v}' for k, v in by_kind.most_common())}).",
    }


@AGENT.tool
def readability_diff(before: str, after: str) -> dict:
    """Prove the edit helped: before/after words, grade, reading ease, sentence length, passive and adverb counts with deltas and warnings.

    Call last. Warns when you cut more than 35% of the words (content probably removed),
    when readability got worse, or when numbers/negations in the original went missing.

    Args:
        before: The original draft.
        after: Your edited version.
    """
    c.guard(before, "Original")
    c.guard(after, "Edited text")
    pb, pa = c.strip_markdown(before), c.strip_markdown(after)

    def stats(p: str) -> dict:
        rd = text.readability(p)
        ws = text.words(p)
        sents = text.sentences(p)
        lens = [len(text.words(s)) for s in sents]
        return {
            "words": len(ws), "sentences": len(sents),
            "avg_sentence_words": rd.get("avg_words_per_sentence", 0.0),
            "longest_sentence_words": max(lens) if lens else 0,
            "fk_grade": rd["fk_grade"], "flesch_reading_ease": rd["flesch_reading_ease"],
            "passive_sentences": len(text.passive_sentences(p)),
            "adverbs": len(_adverbs(ws)),
            "hedges": sum(h["count"] for h in c.find_phrases(p, c.HEDGES)),
            "cliches": sum(h["count"] for h in c.find_phrases(p, c.CLICHES)),
            "ai_tells": sum(h["count"] for h in c.find_phrases(p, c.AI_TELLS)),
        }

    b, a = stats(pb), stats(pa)
    if not b["words"] or not a["words"]:
        raise ToolError("Both texts need at least one word.")
    delta = {k: round((a[k] or 0) - (b[k] or 0), 1) for k in b}
    words_pct = round(100.0 * (a["words"] - b["words"]) / b["words"], 1)
    warnings = []
    if words_pct <= -35:
        warnings.append(f"Cut {abs(words_pct)}% of the words — list what content was removed so the author can veto.")
    if words_pct > 5:
        warnings.append("The edit is longer than the original. Editing should remove; check what you added.")
    if a["fk_grade"] is not None and b["fk_grade"] is not None and a["fk_grade"] > b["fk_grade"] + 0.3:
        warnings.append("Reading grade went UP. Re-do the line pass: shorter sentences, shorter words.")
    if a["passive_sentences"] > b["passive_sentences"]:
        warnings.append("More passive sentences than before.")
    nums_b = set(re.findall(r"\d[\d,.]*%?", pb))
    nums_a = set(re.findall(r"\d[\d,.]*%?", pa))
    missing = sorted(nums_b - nums_a)
    if missing:
        warnings.append(f"Numbers in the original not in the edit: {', '.join(missing[:10])} — confirm each was cut on purpose.")
    neg_b = len(re.findall(r"\b(not|never|no|n't|cannot|without)\b", pb, re.I))
    neg_a = len(re.findall(r"\b(not|never|no|n't|cannot|without)\b", pa, re.I))
    if abs(neg_b - neg_a) > max(2, neg_b * 0.3):
        warnings.append(f"Negation count changed {neg_b} → {neg_a}: check that no meaning flipped.")
    improved = sum([
        a["words"] <= b["words"], (a["fk_grade"] or 0) <= (b["fk_grade"] or 0), a["passive_sentences"] <= b["passive_sentences"],
        a["adverbs"] <= b["adverbs"], a["hedges"] <= b["hedges"], a["cliches"] <= b["cliches"], a["ai_tells"] <= b["ai_tells"],
    ])
    fre_line = f"FRE {b['flesch_reading_ease']} → {a['flesch_reading_ease']}"
    summary_line = (
        f"Words: {b['words']} → {a['words']} ({words_pct:+.0f}%) · Grade: {b['fk_grade']} → {a['fk_grade']} · "
        f"Passive: {b['passive_sentences']} → {a['passive_sentences']} · Adverbs: {b['adverbs']} → {a['adverbs']} · {fre_line}"
    )
    return {
        "before": b,
        "after": a,
        "delta": delta,
        "words_change_pct": words_pct,
        "summary_line": summary_line,
        "warnings": warnings,
        "verdict": ("Clear improvement on every axis." if improved == 7 and not warnings else
                    "Improved — but read the warnings." if improved >= 5 else
                    "Mixed result — the edit did not clearly help; revisit the line pass."),
    }
