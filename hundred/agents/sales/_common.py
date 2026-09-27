"""Shared deterministic helpers for the Sales agents (stdlib only, no I/O).

Underscore module: skipped by the registry. Anything here is used by two or
more sales agents — transcript parsing, filler/question detection, money
rounding, and the spam-word list cold outreach is judged against.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date

from ...core import ToolError
from ...lib import dates, text

# ── transcripts ────────────────────────────────────────────────
SPEAKER_RE = re.compile(r"^\s*(?:\[?[\d:]{4,8}\]?\s*)?([A-Z][\w .'-]{0,40}?)\s*(?:\([^)]*\))?\s*:\s+(.+)$")

FILLERS = (
    "um", "uh", "you know", "sort of", "kind of", "basically", "actually",
    "literally", "right?", "i mean", "so yeah", "okay so", "honestly",
)
_FILLER_RE = re.compile(r"\b(" + "|".join(re.escape(f) for f in FILLERS) + r")\b", re.I)
# "like" is only a filler when set off by commas ("it was, like, huge" / "like, we tried"),
# never as a verb ("you'll like the dashboard") or a preposition ("teams like yours").
_LIKE_FILLER_RE = re.compile(r"(?:(?<=,)\s*like\b(?!\s+(?:a|an|the|this|that|yours?|ours?|them|us|me)\b)|(?:^|(?<=[.!?]))\s*like,)", re.I)
_TIMESTAMP_RE = re.compile(r"^\s*\[?((?:\d{1,2}:)?\d{1,2}:\d{2})\]?\s")

CLOSED_STARTS = re.compile(
    r"^(is|are|do|does|did|can|could|will|would|should|have|has|had|was|were|am|any|shall)\b", re.I
)
OPEN_STARTS = re.compile(r"^(what|how|why|tell me|walk me|describe|help me understand|when|where|who|which)\b", re.I)
LEADING_RE = re.compile(r"(\b(don'?t you|wouldn'?t you|isn'?t it|you'?d agree|you would agree)\b|,\s*(right|correct|yes|no)\s*\??\s*$)", re.I)
_LEAD_IN_RE = re.compile(r"^(and|so|but|also|ok|okay|great|got it|right|cool|sure|then|now|well)[,\s]+", re.I)


def parse_transcript(transcript: str, max_chars: int = 400_000) -> list[tuple[str | None, str]]:
    """Split a "Name: text" transcript into (speaker, text) turns. Unlabelled lines get speaker None."""
    if not transcript or not transcript.strip():
        raise ToolError("Transcript is empty.")
    if len(transcript) > max_chars:
        raise ToolError(f"Transcript too long ({max_chars // 1000}k chars max). Split it into parts.")
    turns: list[tuple[str | None, str]] = []
    for line in transcript.splitlines():
        if not line.strip():
            continue
        m = SPEAKER_RE.match(line)
        if m:
            turns.append((m.group(1).strip(), m.group(2).strip()))
        elif turns and turns[-1][0] is not None and not re.match(r"^\s*[\[\d]", line):
            # continuation of the previous speaker's paragraph
            spk, prev = turns[-1]
            turns[-1] = (spk, prev + " " + line.strip())
        else:
            turns.append((None, line.strip()))
    return turns


def match_speaker(name: str, speakers: list[str]) -> str | None:
    """Find the transcript speaker label that best matches a user-supplied name."""
    if not name:
        return None
    n = name.strip().lower()
    for s in speakers:
        if s.lower() == n:
            return s
    for s in speakers:
        if n in s.lower() or s.lower() in n:
            return s
    return None


def count_fillers(t: str) -> Counter[str]:
    out = Counter(m.group(1).lower() for m in _FILLER_RE.finditer(t or ""))
    n_like = len(_LIKE_FILLER_RE.findall(t or ""))
    if n_like:
        out["like"] += n_like
    return out


def transcript_span_minutes(transcript: str) -> float | None:
    """Call length from line timestamps ("[12:05] Name: ..." or "01:02:03 Name: ..."), first to last.

    Returns None when fewer than two timestamps are present. The last line's own duration is
    unknown, so this slightly under-counts; callers treat it as a floor.
    """
    secs = []
    for line in (transcript or "").splitlines():
        m = _TIMESTAMP_RE.match(line)
        if m:
            parts = [int(x) for x in m.group(1).split(":")]
            while len(parts) < 3:
                parts.insert(0, 0)
            secs.append(parts[0] * 3600 + parts[1] * 60 + parts[2])
    if len(secs) < 2 or secs[-1] <= secs[0]:
        return None
    return round((secs[-1] - secs[0]) / 60, 1)


def call_minutes_for(transcript: str, total_words: int, call_minutes: int) -> tuple[float, str, list[str]]:
    """Resolve call length: user-given > timestamps > 150 wpm estimate. Returns (minutes, source, warnings)."""
    warnings: list[str] = []
    span = transcript_span_minutes(transcript)
    if call_minutes and call_minutes > 0:
        minutes, source = float(call_minutes), "given"
        if total_words / minutes < 60:
            warnings.append(
                f"only {total_words} words for a {call_minutes}-minute call (~{round(total_words / minutes)} words/min; "
                "live speech runs 120-160) — this looks like a partial transcript, so per-minute rates "
                "(questions/30 min, fillers/min, words/min) are understated"
            )
    elif span:
        minutes, source = max(1.0, span), "timestamps"
    else:
        minutes, source = float(max(1, round(total_words / 150))), "estimated at 150 words/min"
    return minutes, source, warnings


def word_count(t: str) -> int:
    """Words as a person (or Word/Docs) counts them: a URL is one word, "30-minute" is one word."""
    t = re.sub(r"(https?://\S+|www\.\S+)", " URL ", t or "")
    return sum(1 for tok in t.split() if re.search(r"[A-Za-z0-9]", tok))


def questions_in(t: str) -> list[str]:
    """Return the question sentences in a piece of speech."""
    return [s for s in text.sentences(t) if s.rstrip().endswith("?")]


def classify_question(q: str) -> str:
    """open / closed / leading / multi (two questions in one)."""
    s = q.strip()
    for _ in range(3):
        s = _LEAD_IN_RE.sub("", s)
    if s.count("?") >= 2 or re.search(r"\?\s+(and|or)\b", s, re.I):
        return "multi"
    # "Who else is involved, and what's your timeline?" — two questions joined in one sentence
    if re.search(r",\s*(?:and|or|plus)\s+(?:what|how|why|who|when|where|which|is|are|do|does|did|can|could|would|will|have|has)\b", s, re.I):
        return "multi"
    if LEADING_RE.search(s):
        return "leading"
    if OPEN_STARTS.match(s):
        return "open"
    if CLOSED_STARTS.match(s):
        return "closed"
    # "You mentioned X — how does that affect…?" — an open stem later in the sentence
    if re.search(r"\b(what|how|why)\b", s, re.I):
        return "open"
    return "closed"


# ── money / numbers ────────────────────────────────────────────
def money(x: float) -> float:
    return round(float(x) + 1e-9, 2)


def pct(part: float, whole: float, digits: int = 1) -> float:
    return round(100.0 * part / whole, digits) if whole else 0.0


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise ToolError(msg)


def to_date(value: str, default: date | None = None) -> date:
    if not value or not str(value).strip():
        return default or date.today()
    return dates.parse_date(str(value))


def parse_holidays(holidays: list[str]) -> set[date]:
    return {dates.parse_date(h) for h in (holidays or [])[:200]}


# ── outreach language ──────────────────────────────────────────
SPAM_WORDS = (
    "free", "guarantee", "guaranteed", "act now", "limited time", "urgent", "winner", "congratulations",
    "no obligation", "risk-free", "risk free", "100%", "click here", "buy now", "cheap", "discount",
    "earn money", "make money", "cash", "credit", "double your", "exclusive deal", "special promotion",
    "once in a lifetime", "amazing", "incredible", "unbelievable", "best price", "lowest price",
    "no cost", "save big", "order now", "don't miss", "dont miss", "last chance", "apply now",
    "increase sales", "increase your", "boost your", "revolutionary", "game-changing", "game changing",
    "cutting-edge", "cutting edge", "world-class", "leading provider", "best-in-class", "synergy",
    "one-stop", "$$$", "!!!",
)
_SPAM_RE = re.compile(r"(?<![\w-])(" + "|".join(re.escape(w) for w in SPAM_WORDS) + r")(?![\w-])", re.I)

FLUFF_OPENERS = (
    "i hope this email finds you well", "hope you're doing well", "hope you are doing well",
    "hope all is well", "my name is", "i wanted to reach out", "i'm reaching out", "i am reaching out",
    "just checking in", "just following up", "touching base", "circling back", "quick question",
    "i know you're busy", "i know you are busy", "allow me to introduce", "we are a leading",
    "we're a leading",
)

MERGE_TOKEN_RE = re.compile(r"(\{\{[^}]{1,60}\}\}|\{[A-Za-z_][\w.]{0,40}\}|\[\[?[A-Za-z_ ]{1,40}\]\]?|%[A-Z_]{2,40}%)")


def spam_hits(t: str) -> list[str]:
    return sorted({m.group(1).lower() for m in _SPAM_RE.finditer(t or "")})


def fluff_hits(t: str) -> list[str]:
    low = (t or "").lower()
    return [f for f in FLUFF_OPENERS if f in low]


def unresolved_tokens(t: str) -> list[str]:
    return sorted({m.group(1) for m in MERGE_TOKEN_RE.finditer(t or "")})


def you_i_ratio(t: str) -> dict:
    ws = [w.lower() for w in text.words(t)]
    you = sum(1 for w in ws if w in ("you", "your", "yours", "you're", "you'll", "you've"))
    me = sum(1 for w in ws if w in ("i", "i'm", "i've", "i'll", "we", "we're", "we've", "our", "us", "my", "me"))
    return {"you_words": you, "i_we_words": me, "you_to_i_ratio": round(you / me, 2) if me else (float(you) if you else 0.0)}
