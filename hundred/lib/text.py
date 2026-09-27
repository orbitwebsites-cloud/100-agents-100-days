"""Text statistics every writing agent needs: words, sentences, readability.

Pure stdlib, deterministic, fast. Readability uses the standard Flesch Reading
Ease and Flesch-Kincaid Grade formulas with a heuristic syllable counter that is
within ~5% of dictionary counts on ordinary English prose.
"""

from __future__ import annotations

import re
from collections import Counter

WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)*")
_SENT_SPLIT = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[\"'(\[]?[A-Z0-9])")
_ABBREV = re.compile(r"\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc|e\.g|i\.e|Inc|Ltd|Co|St|No)\.", re.I)

STOPWORDS = frozenset(
    """a about above after again against all am an and any are as at be because been before being
    below between both but by can could did do does doing down during each few for from further had
    has have having he her here hers herself him himself his how i if in into is it its itself just
    me more most my myself no nor not now of off on once only or other our ours ourselves out over own
    same she should so some such than that the their theirs them themselves then there these they this
    those through to too under until up very was we were what when where which while who whom why will
    with would you your yours yourself yourselves""".split()
)


def words(text: str) -> list[str]:
    return WORD_RE.findall(text or "")


def sentences(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    protected = _ABBREV.sub(lambda m: m.group(0).replace(".", "\u0000"), text)
    parts = []
    for block in re.split(r"\n\s*\n|\n(?=\s*[-*•\d]+[.)]?\s)", protected):
        parts.extend(_SENT_SPLIT.split(block.strip()))
    return [p.replace("\u0000", ".").strip() for p in parts if p.strip()]


def syllables(word: str) -> int:
    w = word.lower().strip("'’")
    if not w:
        return 0
    if w.isdigit():
        return max(1, len(w))
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|[^laeiouy]ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    count = len(re.findall(r"[aeiouy]{1,2}", w))
    return max(1, count)


def readability(text: str) -> dict:
    """Flesch Reading Ease + Flesch-Kincaid grade + basic counts."""
    ws = words(text)
    ss = sentences(text) or ([text] if ws else [])
    n_words, n_sents = len(ws), max(1, len(ss))
    if not n_words:
        return {"words": 0, "sentences": 0, "flesch_reading_ease": None, "fk_grade": None}
    n_syll = sum(syllables(w) for w in ws)
    wps = n_words / n_sents
    spw = n_syll / n_words
    fre = 206.835 - 1.015 * wps - 84.6 * spw
    grade = 0.39 * wps + 11.8 * spw - 15.59
    return {
        "words": n_words,
        "sentences": len(ss),
        "avg_words_per_sentence": round(wps, 1),
        "avg_syllables_per_word": round(spw, 2),
        "flesch_reading_ease": round(fre, 1),
        "fk_grade": round(max(0.0, grade), 1),
        "reading_level": reading_level(fre),
    }


def reading_level(fre: float) -> str:
    for floor, label in [
        (90, "very easy (5th grade)"),
        (80, "easy (6th grade)"),
        (70, "fairly easy (7th grade)"),
        (60, "plain English (8th-9th grade)"),
        (50, "fairly hard (10th-12th grade)"),
        (30, "hard (college)"),
    ]:
        if fre >= floor:
            return label
    return "very hard (graduate)"


def reading_time_minutes(text: str, wpm: int = 238) -> float:
    return round(len(words(text)) / wpm, 1)


def keyword_density(text: str, keyword: str) -> dict:
    ws = [w.lower() for w in words(text)]
    kw = [w.lower() for w in words(keyword)]
    if not ws or not kw:
        return {"occurrences": 0, "density_pct": 0.0}
    n = len(kw)
    hits = sum(1 for i in range(len(ws) - n + 1) if ws[i : i + n] == kw)
    return {"occurrences": hits, "density_pct": round(100 * hits * n / len(ws), 2)}


def top_terms(text: str, n: int = 15) -> list[tuple[str, int]]:
    ws = [w.lower() for w in words(text) if w.lower() not in STOPWORDS and len(w) > 2]
    return Counter(ws).most_common(n)


PASSIVE_RE = re.compile(
    r"\b(am|is|are|was|were|be|been|being)\s+(?:\w+ly\s+)?(\w+(?:ed|en)|built|made|done|given|taken|seen|known|shown|sent|held|told|found|kept|left|paid|sold|won)\b",
    re.I,
)


def passive_sentences(text: str) -> list[str]:
    return [s for s in sentences(text) if PASSIVE_RE.search(s)]


def truncate_report(text: str, limit: int) -> dict:
    """How a string fares against a hard character limit."""
    n = len(text)
    return {"chars": n, "limit": limit, "fits": n <= limit, "over_by": max(0, n - limit)}
