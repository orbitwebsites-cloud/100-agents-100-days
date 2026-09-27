"""Brand Voice Guardian — measures a brand's voice from samples and holds every draft to it."""

from __future__ import annotations

import re
import statistics
from collections import Counter

from ...core import Agent, ToolError
from ...lib import text
from ._common import count_emoji, require_text

AGENT = Agent(
    slug="brand-voice",
    name="Brand Voice Guardian",
    category="marketing",
    tagline="Turn 'sounds like us' into numbers: extract the voice from real samples, then score every draft against it.",
    description=(
        "Builds a measurable voice profile from a brand's best writing — sentence rhythm, word "
        "length, pronoun mix, contractions, questions, exclamation and emoji habits, jargon, "
        "passive voice, reading grade and signature words — then scores any new draft against "
        "that profile, flags exactly where it drifts, enforces the banned/preferred lexicon and "
        "brand-name casing, and places the text on the four classic tone dimensions. Produces a "
        "one-page voice guide writers and AI tools can actually follow."
    ),
    triggers=[
        "does this sound like our brand",
        "create a brand voice guide / tone of voice guidelines",
        "rewrite this in our brand voice",
        "check copy against our style guide",
        "extract our tone from these examples",
        "make our AI content sound consistent",
    ],
    examples=[
        "Here are 6 of our best blog intros and 4 emails. Build our voice profile and a one-page guide.",
        "Score this landing page draft against our voice profile and tell me what to change.",
        "Banned words: leverage, synergy, utilize. Preferred: 'customers' not 'users'. Check this post.",
    ],
    connectors=["Notion", "Google Docs", "HubSpot", "Slack", "Confluence"],
    playbook="""
    ## Standard
    You are the brand editor whose sign-off every piece of copy needs. Excellent means: the
    voice is defined by measurable habits (not adjectives like "friendly"), every draft is
    scored against them, and each drift comes with a concrete rewrite. The metric that
    matters is the on-voice score of shipped copy — and its consistency across writers and
    AI tools. Never judge voice by feel when a tool can measure it.

    ## Intake
    Need: 3+ samples of writing the brand is proud of (ideally 500+ words total, mixed
    formats), and the draft to check (if any). If samples are missing, ask for them — a
    profile from one paragraph is noise. If a lexicon (banned/preferred terms) exists, get
    it; otherwise proceed without and say so. Ask at most 3 questions.

    ## Procedure
    1. **Measure the voice.** Call `brand_voice__extract_voice_profile` with the samples.
       Read the profile: sentence length and variance (rhythm), word length and grade
       (plainness), pronoun mix (who the brand centres), contractions and questions
       (warmth), exclamation/emoji (energy), passive and jargon rates (directness), and the
       signature words. Note the "low sample" warning if present and hedge accordingly.
    2. **Place the tone.** Call `brand_voice__tone_dimensions` on the combined samples to
       position the brand on funny–serious, formal–casual, respectful–irreverent,
       enthusiastic–matter-of-fact. Describe each as a range, with a "we do / we don't"
       pair (see Frameworks).
    3. **Check any draft.** Call `brand_voice__score_against_profile` with the draft and the
       profile from step 1. Then call `brand_voice__lexicon_check` with the banned and
       preferred terms and brand-name spellings. Every drift the tools return gets a
       specific rewrite in your response; don't just list metrics.
    4. **Rewrite if asked.** Change only what drifts. Keep the author's meaning and
       structure; voice edits are surgical, not a rewrite from scratch. Re-run step 3 on
       your rewrite and report the before/after score.
    5. **Deliver** the voice guide or the review in the output format. The guide must be
       short enough to paste into an AI system prompt (≤ 300 words).

    ## Frameworks
    - **Voice vs tone:** voice is constant (the measured profile); tone flexes by context
      (an outage email is calmer than a launch post). Say which tone the draft needs.
    - **NN/g four dimensions:** funny–serious, formal–casual, respectful–irreverent,
      enthusiastic–matter-of-fact. Position each as a point on a −1..+1 line.
    - **"We do / we don't" pairs** make guides usable: "We say 'you'll be set up in 4
      minutes'; we don't say 'our seamless onboarding experience'."
    - **Tolerance bands** (used by the scorer): a draft is on-voice when sentence length
      is within ±25 % of the profile, reading grade within ±1.5, pronoun mix and
      contraction rate within ±40 % relative, and no banned terms. Score ≥ 80 ships;
      60-79 needs the listed edits; < 60 is off-brand.
    - **Signature words** are the brand's distinctive vocabulary (frequent in samples,
      rare in general English) — sprinkle, don't stuff: 1-3 per 300 words.
    - **Casing** is voice too: "GitHub", "iPhone", "HubSpot" — one wrong casing reads as
      an outsider.

    ## Output format
    ```
    # Brand voice — <brand>
    **Sounds like:** <one sentence, e.g. "a sharp colleague explaining, never a brochure">
    **Tone position:** funny ←●→ serious (+0.4) · formal ←●→ casual (−0.3) · …

    ## The numbers (from <n> samples, <words> words)
    | Habit | Target | Band |
    |---|---|---|
    | Sentence length | 14 words | 10-18 |
    | Reading grade | 7 | ≤ 8.5 |
    | Pronouns per 100 words | you 3.1 · we 1.2 · I 0 | you > we |
    | Contractions | 60 % of eligible | ≥ 40 % |
    | Questions / exclamations / emoji | 1 per 200 w / 0 / 0 | … |

    ## We do / we don't
    - We say "<example>" · We don't say "<example>"

    ## Lexicon
    Banned: … · Preferred: <old → new> · Casing: …

    ## Draft review (if a draft was given): <score>/100
    | Drift | Draft | Target | Rewrite |
    |---|---|---|---|
    ```

    ## Anti-patterns
    - Voice guides made of adjectives ("bold, human, authentic") with no examples or numbers.
    - Rewriting a draft into a different structure when only three sentences drift.
    - Profiling from a single sample or from copy the brand isn't proud of.
    - Treating tone as fixed: a refund email in launch-post energy.
    - Flagging every "we" — the target is the ratio, not zero.
    - Keyword-stuffing signature words.
    """,
)

CONTRACTION_RE = re.compile(r"\b\w+n['’]t\b|\b(?:I|you|we|they|he|she|it|that|there|what|who|let)['’](?:ll|re|ve|d|s|m)\b", re.I)
EXPANDABLE_RE = re.compile(r"\b(do not|does not|did not|cannot|can not|will not|would not|should not|could not|is not|are not|was not|were not|have not|has not|had not|it is|that is|there is|we are|you are|they are|we will|you will|I am|we have|you have|I will|I have|let us)\b", re.I)
PRONOUNS = {"you": r"\b(you|your|yours|yourself)\b", "we": r"\b(we|our|ours|us|ourselves)\b", "i": r"\b(i|my|mine|me|myself)\b", "they": r"\b(they|their|them|theirs)\b"}
JARGON = frozenset(
    """synergy leverage utilize utilise seamless robust cutting-edge best-in-class next-generation
    innovative revolutionary world-class holistic paradigm scalable turnkey disruptive empower
    reimagine transform ecosystem frictionless unlock elevate streamline end-to-end solution
    solutions state-of-the-art game-changing optimize optimise facilitate impactful actionable
    bandwidth circle-back deep-dive low-hanging ideate incentivize incentivise""".split()
)
COMMON = frozenset(
    text.STOPWORDS
    | set(
        """one two new get got make made like also well way time day year years people even much many
        things thing need want use used using see know think going go good great really still back
        every first last long right work team teams product products help take give find keep let
        best better around over out into through before after since without within always never
        here there where than then them these those come came look looks said say says""".split()
    )
)
ADVERB_RE = re.compile(r"\b\w{4,}ly\b", re.I)
HUMOR_RE = re.compile(r"\b(lol|haha|joke|pun|nerd|weird|silly|awkward|literally|honestly|okay so|plot twist|spoiler|shh|ahem)\b|😂|🙃|😅|🤷|🎉", re.I)
IRREVERENT_RE = re.compile(r"\b(damn|hell|crap|screw|sucks|badass|heck|nope|yep|whatever|meh|ugh|yikes|guess what|spoiler)\b", re.I)
ENTHUSIASM_RE = re.compile(r"\b(excited|thrilled|love|amazing|awesome|incredible|can't wait|huge|fantastic|delighted|obsessed|wow|yay|finally)\b|!", re.I)
FORMAL_RE = re.compile(r"\b(therefore|thus|hence|furthermore|moreover|regarding|pursuant|accordingly|shall|whom|herein|notwithstanding|in accordance|please be advised|kindly|we regret|we are pleased)\b", re.I)
CASUAL_RE = re.compile(r"\b(gonna|wanna|kinda|sorta|yeah|yep|nope|hey|folks|stuff|cool|super|pretty much|a bunch|tons of|btw|fyi|tbh)\b", re.I)


def _metrics(sample: str) -> dict:
    ws = text.words(sample)
    ss = text.sentences(sample) or ([sample] if ws else [])
    n = len(ws) or 1
    lens = [len(text.words(s)) for s in ss] or [0]
    contractions = len(CONTRACTION_RE.findall(sample))
    expandable = len(EXPANDABLE_RE.findall(sample))
    rd = text.readability(sample)
    starts = Counter((text.words(s)[0].lower() if text.words(s) else "") for s in ss)
    return {
        "words": len(ws),
        "sentences": len(ss),
        "avg_sentence_words": round(statistics.fmean(lens), 1),
        "sentence_length_sd": round(statistics.pstdev(lens), 1) if len(lens) > 1 else 0.0,
        "short_sentences_pct": round(100 * sum(1 for x in lens if x <= 8) / len(lens), 1),
        "long_sentences_pct": round(100 * sum(1 for x in lens if x >= 25) / len(lens), 1),
        "avg_word_chars": round(sum(len(w) for w in ws) / n, 2),
        "long_words_pct": round(100 * sum(1 for w in ws if len(w) >= 9) / n, 1),
        "fk_grade": rd["fk_grade"] or 0.0,
        "pronouns_per_100": {k: round(100 * len(re.findall(p, sample, re.I)) / n, 2) for k, p in PRONOUNS.items()},
        "contraction_rate_pct": round(100 * contractions / (contractions + expandable), 1) if (contractions + expandable) else None,
        "questions_per_100": round(100 * sample.count("?") / n, 2),
        "exclamations_per_100": round(100 * sample.count("!") / n, 2),
        "emoji_per_100": round(100 * count_emoji(sample) / n, 2),
        "passive_pct": round(100 * len(text.passive_sentences(sample)) / max(1, len(ss)), 1),
        "adverbs_per_100": round(100 * len(ADVERB_RE.findall(sample)) / n, 2),
        "jargon_per_100": round(100 * sum(1 for w in ws if w.lower() in JARGON) / n, 2),
        "numbers_per_100": round(100 * len(re.findall(r"\d[\d,.]*", sample)) / n, 2),
        "and_but_openers_pct": round(100 * (starts["and"] + starts["but"] + starts["so"]) / max(1, len(ss)), 1),
    }


@AGENT.tool
def extract_voice_profile(samples: list[str], brand_name: str = "") -> dict:
    """Measure a brand's voice from writing samples: rhythm, plainness, pronouns, contractions, energy, jargon and signature words.

    Call first with 3+ samples the brand is proud of. The returned "profile" is the input to score_against_profile.

    Args:
        samples: Writing samples (blog intros, emails, product copy). More and more varied is better.
        brand_name: The brand's name, excluded from signature words.
    """
    samples = [str(s) for s in samples if str(s).strip()]
    if not samples:
        raise ToolError("Provide at least one non-empty sample.")
    if len(samples) > 100 or sum(len(s) for s in samples) > 400_000:
        raise ToolError("Too much text: max 100 samples / 400k chars.")
    combined = "\n\n".join(samples)
    agg = _metrics(combined)
    per_sample = [_metrics(s) for s in samples]
    total_words = agg["words"]
    warnings = []
    if len(samples) < 3:
        warnings.append(f"Only {len(samples)} sample(s) — profile is indicative, not reliable. Get 3+.")
    if total_words < 400:
        warnings.append(f"Only {total_words} words — rates below are noisy; treat bands as wide.")
    # Signature words: frequent here, not common English, not the brand name.
    brand_words = {w.lower() for w in text.words(brand_name)}
    freq = Counter(w.lower() for w in text.words(combined) if len(w) > 3 and w.lower() not in COMMON and w.lower() not in brand_words and not w.isdigit())
    sig = [w for w, c in freq.most_common(40) if c >= 2 and (c / total_words) >= 0.002][:12]
    # Consistency across samples: coefficient of variation of sentence length.
    sl = [m["avg_sentence_words"] for m in per_sample if m["words"] >= 20]
    consistency = round(statistics.pstdev(sl) / statistics.fmean(sl), 2) if len(sl) > 1 and statistics.fmean(sl) else None
    p = agg["pronouns_per_100"]
    centre = max(p, key=p.get) if any(p.values()) else "none"
    grade = agg["fk_grade"]
    descriptors = []
    descriptors.append("short, punchy sentences" if agg["avg_sentence_words"] <= 12 else "conversational-length sentences" if agg["avg_sentence_words"] <= 18 else "long, flowing sentences")
    descriptors.append("plain words" if grade <= 8 else "professional register" if grade <= 11 else "dense/academic register")
    descriptors.append(f"centres '{centre}'")
    if agg["contraction_rate_pct"] is not None:
        descriptors.append("contracts freely" if agg["contraction_rate_pct"] >= 50 else "rarely contracts" if agg["contraction_rate_pct"] <= 20 else "mixed contractions")
    descriptors.append("high energy (!/emoji)" if agg["exclamations_per_100"] + agg["emoji_per_100"] >= 0.8 else "measured energy")
    if agg["questions_per_100"] >= 0.5:
        descriptors.append("asks the reader questions")
    if agg["jargon_per_100"] >= 0.5:
        descriptors.append("jargon-heavy (consider trimming)")
    if agg["numbers_per_100"] >= 1.0:
        descriptors.append("specific with numbers")
    profile = {k: v for k, v in agg.items()}
    profile["signature_words"] = sig
    return {
        "profile": profile,
        "samples": len(samples),
        "total_words": total_words,
        "per_sample_sentence_length": sl,
        "cross_sample_consistency_cv": consistency,
        "voice_in_words": ", ".join(descriptors),
        "signature_words": sig,
        "warnings": warnings,
        "summary": f"{len(samples)} samples / {total_words} words: {agg['avg_sentence_words']}-word sentences, grade {grade}, pronoun centre '{centre}', contractions {agg['contraction_rate_pct']}%, jargon {agg['jargon_per_100']}/100w.",
    }


_BANDS = [
    # key, tolerance type, tolerance, label, fix
    ("avg_sentence_words", "rel", 0.25, "sentence length", "Split or join sentences to match the brand's rhythm."),
    ("fk_grade", "abs", 1.5, "reading grade", "Swap long words for short ones (or vice versa) to match the register."),
    ("contraction_rate_pct", "abs", 25, "contraction rate", "Contract ('we're', 'don't') or expand to match."),
    ("exclamations_per_100", "abs", 0.6, "exclamation rate", "Match the brand's energy — add or remove '!'."),
    ("questions_per_100", "abs", 0.6, "question rate", "The brand asks (or doesn't ask) the reader questions — match it."),
    ("emoji_per_100", "abs", 0.5, "emoji rate", "Match emoji usage."),
    ("passive_pct", "abs", 15, "passive voice", "Rewrite passive sentences as subject-verb-object."),
    ("jargon_per_100", "abs", 0.5, "jargon", "Cut buzzwords; say the plain thing."),
    ("long_words_pct", "abs", 6, "long-word share", "Adjust word length to the brand's plainness."),
]


@AGENT.tool
def score_against_profile(draft: str, profile: dict, banned_terms: list[str] = []) -> dict:
    """Score a draft 0-100 against a voice profile and list every metric that drifts outside the tolerance band, with fixes.

    Call with the "profile" object returned by extract_voice_profile.

    Args:
        draft: The text to check.
        profile: The profile dict from extract_voice_profile (or a hand-set one with the same keys).
        banned_terms: Words/phrases the brand never uses; each occurrence costs points.
    """
    d = require_text(draft, "draft")
    if not isinstance(profile, dict) or "avg_sentence_words" not in profile:
        raise ToolError("profile must be the 'profile' object from extract_voice_profile.")
    m = _metrics(d)
    drifts, on_target = [], []
    penalty = 0.0
    for key, kind, tol, label, fix in _BANDS:
        target = profile.get(key)
        actual = m.get(key)
        if target is None or actual is None:
            continue
        band = abs(target) * tol if kind == "rel" else tol
        diff = actual - target
        if abs(diff) > band:
            severity = min(3.0, abs(diff) / band)
            penalty += 8 * severity
            drifts.append({"metric": label, "draft": actual, "target": target, "band": f"±{round(band, 2)}", "direction": "higher" if diff > 0 else "lower", "fix": fix})
        else:
            on_target.append(label)
    # Pronoun centre
    tp, dp = profile.get("pronouns_per_100", {}), m["pronouns_per_100"]
    if tp and any(tp.values()):
        t_centre = max(tp, key=tp.get)
        d_centre = max(dp, key=dp.get) if any(dp.values()) else "none"
        if d_centre != t_centre and tp[t_centre] > 0:
            penalty += 12
            drifts.append({"metric": "pronoun centre", "draft": d_centre, "target": t_centre, "band": "same", "direction": "shifted", "fix": f"Rewrite sentences around '{t_centre}' (brand centres the {'reader' if t_centre == 'you' else t_centre})."})
        else:
            on_target.append("pronoun centre")
    # Signature words
    sig = [w for w in profile.get("signature_words", [])]
    low = d.lower()
    sig_used = [w for w in sig if re.search(rf"\b{re.escape(w)}\b", low)]
    if sig and m["words"] >= 150 and not sig_used:
        penalty += 5
        drifts.append({"metric": "signature words", "draft": "none", "target": ", ".join(sig[:5]), "band": "≥1 per 300 words", "direction": "missing", "fix": "Use one or two of the brand's signature words where natural."})
    # Banned
    banned_hits = []
    for term in banned_terms[:200]:
        t = str(term).strip().lower()
        if t and re.search(rf"\b{re.escape(t)}\b", low):
            cnt = len(re.findall(rf"\b{re.escape(t)}\b", low))
            banned_hits.append({"term": term, "count": cnt})
            penalty += 6 * cnt
    score = max(0, min(100, round(100 - penalty)))
    grade = "on-voice" if score >= 80 else "needs edits" if score >= 60 else "off-brand"
    return {
        "score": score,
        "grade": grade,
        "draft_metrics": m,
        "drifts": drifts,
        "on_target": on_target,
        "signature_words_used": sig_used,
        "banned_hits": banned_hits,
        "summary": f"{score}/100 — {grade}. {len(drifts)} drift(s)" + (f": {', '.join(x['metric'] for x in drifts[:4])}" if drifts else "") + (f"; banned: {', '.join(b['term'] for b in banned_hits)}" if banned_hits else "") + ".",
    }


@AGENT.tool
def lexicon_check(content: str, banned_terms: list[str] = [], preferred_terms: dict = {}, proper_casing: list[str] = []) -> dict:
    """Find banned terms, non-preferred synonyms (with the replacement), and mis-cased brand/product names, with positions.

    Call on every draft when a lexicon exists. preferred_terms maps the wrong word to the right one.

    Args:
        content: The text to check.
        banned_terms: Terms never to use (e.g. ["leverage", "synergy"]).
        preferred_terms: Map of avoid → use, e.g. {"users": "customers", "utilize": "use"}.
        proper_casing: Correctly-cased names to enforce, e.g. ["GitHub", "iPhone", "HubSpot"].
    """
    c = require_text(content, "content")
    if len(banned_terms) > 500 or len(preferred_terms) > 500 or len(proper_casing) > 200:
        raise ToolError("Lexicon too large (max 500 banned, 500 preferred, 200 casing entries).")
    low = c.lower()
    findings = []
    for term in banned_terms:
        t = str(term).strip()
        if not t or len(t) > 80:
            continue
        for mt in re.finditer(rf"\b{re.escape(t.lower())}\b", low):
            findings.append({"type": "banned", "term": c[mt.start() : mt.end()], "position": mt.start(), "context": c[max(0, mt.start() - 30) : mt.end() + 30].replace("\n", " "), "fix": "remove or rephrase"})
    for wrong, right in preferred_terms.items():
        w = str(wrong).strip()
        if not w or len(w) > 80:
            continue
        for mt in re.finditer(rf"\b{re.escape(w.lower())}\b", low):
            findings.append({"type": "preferred", "term": c[mt.start() : mt.end()], "position": mt.start(), "context": c[max(0, mt.start() - 30) : mt.end() + 30].replace("\n", " "), "fix": f"use '{right}'"})
    for name in proper_casing:
        nm = str(name).strip()
        if not nm or len(nm) > 60:
            continue
        for mt in re.finditer(rf"\b{re.escape(nm.lower())}\b", low):
            found = c[mt.start() : mt.end()]
            if found != nm:
                findings.append({"type": "casing", "term": found, "position": mt.start(), "context": c[max(0, mt.start() - 30) : mt.end() + 30].replace("\n", " "), "fix": f"write '{nm}'"})
    findings.sort(key=lambda f: f["position"])
    counts = Counter(f["type"] for f in findings)
    return {
        "findings": findings,
        "counts": dict(counts),
        "clean": not findings,
        "summary": "Lexicon clean." if not findings else f"{len(findings)} issue(s): {counts.get('banned', 0)} banned, {counts.get('preferred', 0)} non-preferred, {counts.get('casing', 0)} casing.",
    }


@AGENT.tool
def tone_dimensions(content: str) -> dict:
    """Place a text on the four tone dimensions (funny–serious, formal–casual, respectful–irreverent, enthusiastic–matter-of-fact) with evidence.

    Call on the brand samples to define the tone range, and on a draft to check it sits inside it.

    Args:
        content: The text to analyse (≥ 50 words for a stable reading).
    """
    c = require_text(content, "content")
    ws = text.words(c)
    n = len(ws) or 1
    per100 = lambda k: 100 * k / n  # noqa: E731
    m = _metrics(c)
    humor, irrev, enth = HUMOR_RE.findall(c), IRREVERENT_RE.findall(c), ENTHUSIASM_RE.findall(c)
    formal, casual = FORMAL_RE.findall(c), CASUAL_RE.findall(c)

    def clamp(x: float) -> float:
        return round(max(-1.0, min(1.0, x)), 2)

    # +1 = right-hand pole. funny(-1)…serious(+1)
    funny_serious = clamp(0.3 - 0.35 * per100(len(humor)) - 0.1 * m["emoji_per_100"] + 0.03 * max(0, m["fk_grade"] - 8))
    formal_casual = clamp(0.15 * per100(len(casual)) + 0.006 * (m["contraction_rate_pct"] or 40) - 0.3 - 0.2 * per100(len(formal)) - 0.04 * max(0, m["fk_grade"] - 9) + 0.05 * m["and_but_openers_pct"] / 10)
    respectful_irreverent = clamp(-0.3 + 0.5 * per100(len(irrev)) + 0.15 * per100(len(humor)))
    enth_matter = clamp(0.4 - 0.25 * per100(len(enth)) - 0.15 * m["emoji_per_100"])
    dims = {
        "funny_serious": {"score": funny_serious, "reads_as": "serious" if funny_serious > 0.2 else "funny" if funny_serious < -0.2 else "light", "evidence": sorted(set(x if isinstance(x, str) else x[0] for x in humor))[:5]},
        "formal_casual": {"score": formal_casual, "reads_as": "casual" if formal_casual > 0.2 else "formal" if formal_casual < -0.2 else "neutral", "evidence": {"formal_markers": sorted(set(x.lower() for x in formal))[:5], "casual_markers": sorted(set(x.lower() for x in casual))[:5], "contraction_rate_pct": m["contraction_rate_pct"], "fk_grade": m["fk_grade"]}},
        "respectful_irreverent": {"score": respectful_irreverent, "reads_as": "irreverent" if respectful_irreverent > 0.2 else "respectful" if respectful_irreverent < -0.2 else "balanced", "evidence": sorted(set(x.lower() for x in irrev))[:5]},
        "enthusiastic_matter_of_fact": {"score": enth_matter, "reads_as": "matter-of-fact" if enth_matter > 0.2 else "enthusiastic" if enth_matter < -0.2 else "warm", "evidence": {"markers": sorted(set(x.lower() for x in enth if x != "!"))[:5], "exclamations_per_100": m["exclamations_per_100"]}},
    }
    warning = "Under 50 words — tone reading is unstable." if n < 50 else ""
    return {
        "words": n,
        "dimensions": dims,
        "warning": warning,
        "summary": " · ".join(f"{label}: {v['reads_as']} ({v['score']:+.2f})" for label, v in zip(("funny–serious", "formal–casual", "respectful–irreverent", "enthusiastic–matter-of-fact"), dims.values())),
    }
