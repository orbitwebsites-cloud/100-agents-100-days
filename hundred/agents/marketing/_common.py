"""Shared helpers for the marketing agents (skipped by the registry: underscore module).

Stats: normal CDF via math.erf and an inverse-normal (Acklam's rational approximation
refined with one Halley step, |error| < 1e-12). Plus the spam-trigger lexicon and
character helpers that several copy agents share.
"""

from __future__ import annotations

import math
import re

from ...core import ToolError

# ── statistics ──────────────────────────────────────────────


def norm_cdf(z: float) -> float:
    """Standard normal CDF Φ(z)."""
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


_A = (-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02, 1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00)
_B = (-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02, 6.680131188771972e01, -1.328068155288572e01)
_C = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00, -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00)
_D = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00, 3.754408661907416e00)


def norm_ppf(p: float) -> float:
    """Inverse standard normal CDF (quantile). 0 < p < 1."""
    if not 0.0 < p < 1.0:
        raise ToolError(f"Probability must be strictly between 0 and 1, got {p}")
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        x = (((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]) / ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1)
    elif p <= phigh:
        q = p - 0.5
        r = q * q
        x = (((((_A[0] * r + _A[1]) * r + _A[2]) * r + _A[3]) * r + _A[4]) * r + _A[5]) * q / (((((_B[0] * r + _B[1]) * r + _B[2]) * r + _B[3]) * r + _B[4]) * r + 1)
    else:
        q = math.sqrt(-2 * math.log(1 - p))
        x = -(((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]) / ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1)
    # One step of Halley's method against the exact CDF to polish to ~1e-12.
    e = norm_cdf(x) - p
    u = e * math.sqrt(2 * math.pi) * math.exp(x * x / 2)
    x = x - u / (1 + x * u / 2)
    return x


def chi2_sf_1df(x: float) -> float:
    """Survival function of chi-square with 1 degree of freedom."""
    if x <= 0:
        return 1.0
    return 2 * (1 - norm_cdf(math.sqrt(x)))


def chi2_sf(x: float, k: int) -> float:
    """Chi-square survival function for integer df k >= 1 (series / recurrence, exact for the cases we use)."""
    if x <= 0:
        return 1.0
    if k == 1:
        return chi2_sf_1df(x)
    if k == 2:
        return math.exp(-x / 2)
    # Recurrence: Q(x, k) = Q(x, k-2) + (x/2)^(k/2 - 1) e^{-x/2} / Γ(k/2)
    return chi2_sf(x, k - 2) + math.exp((k / 2 - 1) * math.log(x / 2) - x / 2 - math.lgamma(k / 2))


# ── copy helpers ───────────────────────────────────────────

# Spam-filter trigger lexicon. Single words are matched on word boundaries, phrases as substrings.
SPAM_PHRASES = [
    "act now", "limited time", "buy now", "click here", "order now", "risk-free", "no obligation",
    "double your", "make money", "earn money", "lowest price", "save big", "once in a lifetime",
    "don't miss", "apply now", "offer expires", "exclusive deal", "last chance", "no cost",
    "credit card", "be amazed", "act immediately", "call now", "dear friend", "this isn't spam",
    "not spam", "you have been selected", "free gift", "free access", "fast cash", "get paid",
    "instant income", "lose weight", "satisfaction guaranteed", "while supplies last", "100% free",
    "free trial", "cash bonus", "special promotion", "million dollars", "winner", "congratulations",
    "guarantee", "guaranteed", "urgent", "miracle", "unlimited", "clearance", "giveaway", "prize",
    "cheap", "$$$", "!!!", "free",
]

EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\U00002B00-\U00002BFF✀-➿️]"
)
POWER_WORDS = frozenset(
    """new proven instantly you your free now discover secret guaranteed easy simple fast finally
    stop unlock boost double save win exclusive limited only because how why what results
    best more without never today ready effortless surprising bold""".split()
)
CTA_VERBS = frozenset("get start try book claim download join learn see shop discover buy sign schedule request grab watch read unlock reserve".split())


def spam_hits(text: str) -> list[str]:
    low = (text or "").lower()
    hits = []
    for phrase in SPAM_PHRASES:
        if phrase in ("free", "cheap", "winner", "urgent", "prize", "guarantee", "guaranteed", "unlimited", "clearance", "giveaway", "miracle", "congratulations"):
            if re.search(rf"\b{re.escape(phrase)}\b", low):
                hits.append(phrase)
        elif phrase in low:
            hits.append(phrase)
    return sorted(set(hits))


def caps_ratio(text: str) -> float:
    letters = [c for c in (text or "") if c.isalpha()]
    if not letters:
        return 0.0
    return round(sum(1 for c in letters if c.isupper()) / len(letters), 2)


def count_emoji(text: str) -> int:
    return len(EMOJI_RE.findall(text or ""))


def visible_len(text: str) -> int:
    """Character count as platforms count it: variation selectors/ZWJ dropped, each emoji = 1."""
    t = (text or "").replace("️", "").replace("‍", "")
    return len(t)


def pct(n: float, d: float, digits: int = 2) -> float:
    return round(100.0 * n / d, digits) if d else 0.0


def require_text(value: str, label: str, max_chars: int = 200_000) -> str:
    if value is None or not str(value).strip():
        raise ToolError(f"{label} is empty.")
    if len(value) > max_chars:
        raise ToolError(f"{label} too long ({len(value):,} chars; max {max_chars:,}).")
    return value


# ── US time zones (rule-based, no tz database needed) ──────────────────────


def _nth_sunday(year: int, month: int, n: int):
    from datetime import date, timedelta

    first = date(year, month, 1)
    return first + timedelta(days=(6 - first.weekday()) % 7 + 7 * (n - 1))


def us_utc_offset(local_wall_time, standard_offset: int) -> int:
    """UTC offset in hours for a US zone at a local wall-clock time (naive datetime).

    US rule since 2007: daylight time from the second Sunday in March, 02:00 local, to the
    first Sunday in November, 02:00 local. standard_offset is -5 for Eastern, -8 for Pacific.
    """
    from datetime import datetime

    y = local_wall_time.year
    start = datetime.combine(_nth_sunday(y, 3, 2), datetime.min.time()).replace(hour=2)
    end = datetime.combine(_nth_sunday(y, 11, 1), datetime.min.time()).replace(hour=2)
    naive = local_wall_time.replace(tzinfo=None)
    return standard_offset + 1 if start <= naive < end else standard_offset
