"""Shared helpers for the Product & Design agents (stdlib only)."""

from __future__ import annotations

import math
import re
from collections import Counter

from ...core import ToolError
from ...lib import text

MAX_TEXT = 200_000
MAX_ROWS = 500

AMBIGUOUS_WORDS = (
    "fast", "quick", "quickly", "easy", "easily", "simple", "user-friendly", "intuitive", "robust",
    "scalable", "efficient", "seamless", "appropriate", "adequate", "sufficient", "reasonable",
    "etc", "and/or", "as needed", "if possible", "where applicable", "minimal", "optimal", "best",
    "flexible", "modern", "clean", "nice", "good", "better", "some", "several", "various", "many",
    "soon", "timely", "real-time", "improve", "enhance", "support", "handle", "usually", "normally",
)
_AMBIG_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in AMBIGUOUS_WORDS) + r")\b", re.I)


def check_text(value: str, label: str = "text", max_len: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolError(f"{label} is empty.")
    if len(value) > max_len:
        raise ToolError(f"{label} too long ({len(value):,} chars; max {max_len:,}). Split it.")
    return value


def check_rows(rows: list, label: str = "rows", max_rows: int = MAX_ROWS) -> list:
    if not isinstance(rows, list) or not rows:
        raise ToolError(f"{label} is empty — pass at least one item.")
    if len(rows) > max_rows:
        raise ToolError(f"Too many {label} ({len(rows)}; max {max_rows}).")
    return rows


def ambiguous_terms(s: str) -> list[str]:
    """Words that make a requirement untestable ("fast", "easy", "etc")."""
    seen: list[str] = []
    for m in _AMBIG_RE.finditer(s or ""):
        w = m.group(1).lower()
        if w not in seen:
            seen.append(w)
    return seen


_SUFFIX_RE = re.compile(r"(ations|ation|ings|ing|als|al|ed|es|s)$")


def stem(w: str) -> str:
    """Tiny consistent stemmer: approve / approved / approval / approvals → approv."""
    if len(w) <= 4:
        return w
    w2 = _SUFFIX_RE.sub("", w)
    if len(w2) < 3:
        w2 = w
    if len(w2) > 4 and w2.endswith("e"):
        w2 = w2[:-1]
    return w2


def term_set(s: str) -> frozenset[str]:
    """Lower-cased content words of a string, stopwords removed, light stemming."""
    out = set()
    for w in text.words(s.lower()):
        if w in text.STOPWORDS or len(w) < 3:
            continue
        out.add(stem(w))
    return frozenset(out)


def jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def pct(part: float, whole: float, nd: int = 1) -> float:
    return round(100.0 * part / whole, nd) if whole else 0.0


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def stdev(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def top_counts(items: list[str], n: int = 20) -> list[dict]:
    c = Counter(i.strip().lower() for i in items if i and i.strip())
    return [{"item": k, "count": v} for k, v in c.most_common(n)]


def to_float(value, label: str, lo: float | None = None, hi: float | None = None) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ToolError(f"{label} must be a number, got {value!r}.") from None
    if math.isnan(f) or math.isinf(f):
        raise ToolError(f"{label} must be a finite number.")
    if lo is not None and f < lo:
        raise ToolError(f"{label} must be >= {lo}, got {f}.")
    if hi is not None and f > hi:
        raise ToolError(f"{label} must be <= {hi}, got {f}.")
    return f
