"""Ad Copy Lab — platform-exact ad copy: limits, angle coverage, scoring and the budget math behind it."""

from __future__ import annotations

import math
import re
from collections import Counter
from itertools import permutations
from typing import Literal

from ...core import Agent, ToolError
from ...lib import text
from ._common import CTA_VERBS, POWER_WORDS, caps_ratio, count_emoji, spam_hits, visible_len

AGENT = Agent(
    slug="ad-copy-lab",
    name="Ad Copy Lab",
    category="marketing",
    tagline="Ship ad copy that fits every platform limit, covers every angle, and pencils out on CPA before you spend.",
    description=(
        "Writes and pressure-tests paid ad copy for Google RSA, Meta, LinkedIn, X, TikTok, Pinterest, "
        "Microsoft and Reddit. Validates every asset against the real character and asset-count limits, "
        "counts the RSA combinations your pins leave, maps headlines to persuasion angles so the set "
        "isn't ten ways of saying the same thing, scores each line on a 100-point rubric, and runs the "
        "CPC → CPA → ROAS math so the copy is built for the economics of the campaign."
    ),
    triggers=[
        "write Google ads / responsive search ad headlines",
        "write Facebook / Meta / Instagram ad copy",
        "LinkedIn or TikTok ad copy",
        "check my ad copy against character limits",
        "generate ad headline variants",
        "will this campaign be profitable at this CPC",
    ],
    examples=[
        "Write 15 RSA headlines and 4 descriptions for our project-management app targeting 'team task software'.",
        "Here are 6 Meta primary texts — check limits and tell me which angles I'm missing.",
        "CPC is $2.40, landing page converts at 3%, AOV $85 at 60% margin. Does $150/day make sense?",
    ],
    connectors=["Google Ads", "Meta Ads", "LinkedIn Ads", "Google Sheets", "HubSpot"],
    playbook="""
    ## Standard
    You are a performance copywriter who has managed seven-figure ad accounts. Excellent
    means: every asset fits its platform limit with room, the set covers at least five
    distinct persuasion angles, each line makes one specific promise, and the economics
    (target CPA, break-even ROAS) were checked before writing. The metric that matters is
    cost per qualified conversion, not clicks.

    ## Intake
    Need: platform, offer/product, the single primary conversion, the audience's job-to-be-done,
    and a keyword or trigger context (search term for Google; interest/creative context for
    social). If the platform is missing, ask. If economics (CPC, CVR, AOV) are missing, assume
    category-typical values, state them, and continue. Ask at most 3 questions, only if you
    cannot proceed.

    ## Procedure
    1. **Check the economics first** with `ad_copy_lab__ad_math` using known or assumed CPC,
       CTR, CVR, AOV and margin. If break-even ROAS isn't reachable at a plausible CVR, say so
       before writing a word — copy can't fix a broken funnel.
    2. **Draft the asset set** for the platform. For Google RSA write 15 headlines and 4
       descriptions; at least 3 headlines contain the keyword, 3 name a benefit, 2 carry a
       proof point (number, rating, customer count), 2 handle an objection, 2 are CTAs, and
       none duplicate another's meaning. For Meta write 3-5 primary texts with the hook in
       the first 125 characters (the "See more" fold), plus 5 headlines ≤ 40 chars.
    3. **Validate limits** with `ad_copy_lab__validate_platform_copy`. Fix every asset that
       overflows; do not truncate with "…" — rewrite. For RSA, respect the pin plan the tool
       reports: pinning more than one position kills combinations and Ad Strength.
    4. **Check angle coverage** with `ad_copy_lab__angle_coverage`. If fewer than 5 angles
       are represented, or one angle owns > 40 % of lines, rewrite the surplus lines into
       the missing angles (see Frameworks).
    5. **Score and rank** every headline / primary text with `ad_copy_lab__score_ad_copy`.
       Keep lines ≥ 65; rewrite lines < 50 using the fixes returned. Never ship a line the
       tool flags for policy (excessive punctuation, ALL CAPS, "click here").
    6. **Deliver** in the output format, with the test plan: which 2-3 angles to test
       first, what "winning" means (CPA target from step 1), and the minimum spend before
       judging (≥ 50 conversions per variant or 2 weeks).

    ## Frameworks
    - **Angle library:** benefit, feature/how, social proof, urgency/scarcity, price/value,
      objection-kill, question, how-to, fear/loss, curiosity, identity ("for ops leads
      who…"), comparison ("vs spreadsheets"). Great sets touch ≥ 5.
    - **Limits (chars):** Google/Microsoft RSA headline 30, description 90, path 15;
      Meta primary text 125 before fold (write to it), headline 40, description 30;
      LinkedIn intro 150 before fold (600 max), headline 70; X 280; TikTok ad text 100;
      Pinterest title 100 (40 visible), description 500; Reddit title 300.
    - **Hook formula for social:** first line = specific outcome + who it's for + the
      unexpected element. Never open with the brand name.
    - **Numbers beat adjectives:** "Set up in 4 minutes" > "Quick setup". Odd numbers and
      non-round numbers read as measured, not made up.
    - **Ad math rules:** break-even ROAS = 1 / margin; target CPA = AOV × margin × (1 −
      target profit share); max CPC = target CPA × CVR.

    ## Output format
    ```
    # Ad copy — <platform> · <campaign / ad group>
    **Economics:** CPC $x · CVR y % · CPA $z (target $t) · break-even ROAS r
    **Audience & angle plan:** <who> · angles: <list>

    ## Assets
    | # | Asset | Text | Chars | Angle | Score |
    |---|---|---|---|---|---|

    ## Pins / structure notes
    <RSA pins, Meta fold hooks, LinkedIn intro fold, etc.>

    ## Test plan
    - Test 1: <angle A vs angle B>, success = CPA ≤ $t, judge after ≥ 50 conv/variant
    - Guardrails: CTR ≥ x %, landing-page bounce ≤ y %

    ## Rejected lines & why
    - "<line>" — <overflow / duplicate angle / policy / score 42>
    ```

    ## Anti-patterns
    - Fifteen headlines that are the same benefit with synonyms swapped.
    - Leading with the brand name or "Welcome to".
    - Exclamation marks in Google headlines (policy) and ALL-CAPS words anywhere.
    - Writing Meta primary text with the offer after the fold.
    - Superlatives with no proof ("best", "#1") — replace with a number or drop.
    - Judging a variant after 8 clicks.
    """,
)

Platform = Literal["google_rsa", "microsoft_rsa", "meta", "linkedin", "x", "tiktok", "pinterest", "reddit"]

LIMITS: dict[str, dict] = {
    "google_rsa": {
        "headlines": {"max_chars": 30, "min_count": 3, "max_count": 15, "label": "headline"},
        "descriptions": {"max_chars": 90, "min_count": 2, "max_count": 4, "label": "description"},
        "primary_texts": None,
        "paths": {"max_chars": 15, "min_count": 0, "max_count": 2, "label": "display path"},
        "policy": {"no_exclamation_in_headlines": True, "max_exclamation_descriptions": 1},
    },
    "meta": {
        "headlines": {"max_chars": 40, "min_count": 1, "max_count": 5, "label": "headline", "soft": True},
        "descriptions": {"max_chars": 30, "min_count": 0, "max_count": 5, "label": "description", "soft": True},
        "primary_texts": {"max_chars": 125, "min_count": 1, "max_count": 5, "label": "primary text", "soft": True, "hard_max": 2200},
        "paths": None,
        "policy": {},
    },
    "linkedin": {
        "headlines": {"max_chars": 70, "min_count": 1, "max_count": 1, "label": "headline", "hard_max": 200},
        "descriptions": {"max_chars": 100, "min_count": 0, "max_count": 1, "label": "description", "hard_max": 300},
        "primary_texts": {"max_chars": 150, "min_count": 1, "max_count": 1, "label": "intro text", "soft": True, "hard_max": 600},
        "paths": None,
        "policy": {},
    },
    "x": {
        "headlines": {"max_chars": 70, "min_count": 0, "max_count": 1, "label": "card headline"},
        "descriptions": None,
        "primary_texts": {"max_chars": 280, "min_count": 1, "max_count": 1, "label": "post text"},
        "paths": None,
        "policy": {},
    },
    "tiktok": {
        "headlines": None,
        "descriptions": None,
        "primary_texts": {"max_chars": 100, "min_count": 1, "max_count": 1, "label": "ad text", "min_chars": 1},
        "paths": None,
        "policy": {},
    },
    "pinterest": {
        "headlines": {"max_chars": 100, "min_count": 1, "max_count": 1, "label": "title", "visible": 40},
        "descriptions": {"max_chars": 500, "min_count": 0, "max_count": 1, "label": "description", "visible": 50},
        "primary_texts": None,
        "paths": None,
        "policy": {},
    },
    "reddit": {
        "headlines": {"max_chars": 300, "min_count": 1, "max_count": 1, "label": "title"},
        "descriptions": None,
        "primary_texts": None,
        "paths": None,
        "policy": {},
    },
}
LIMITS["microsoft_rsa"] = LIMITS["google_rsa"]


def _norm_key(s: str) -> frozenset[str]:
    return frozenset(w for w in (x.lower() for x in text.words(s)) if w not in text.STOPWORDS)


def _check_group(items: list[str], rule: dict, group: str, policy: dict) -> tuple[list[dict], list[str]]:
    rows, issues = [], []
    n = len(items)
    if rule is None:
        if items:
            issues.append(f"{group}: this platform has no such field; {n} item(s) ignored.")
        return rows, issues
    if n < rule["min_count"]:
        issues.append(f"{rule['label']}s: need at least {rule['min_count']}, got {n}.")
    if n > rule["max_count"]:
        issues.append(f"{rule['label']}s: max {rule['max_count']}, got {n} — drop the weakest {n - rule['max_count']}.")
    seen: list[tuple[frozenset[str], int]] = []
    for i, raw in enumerate(items, 1):
        s = str(raw).strip()
        L = visible_len(s)
        flags = []
        limit = rule["max_chars"]
        hard = rule.get("hard_max")
        if L > limit:
            if rule.get("soft") and (hard is None or L <= hard):
                flags.append(f"{L - limit} chars past the {limit}-char fold — truncated with 'See more'")
            else:
                flags.append(f"OVER LIMIT by {L - limit} chars (max {limit})")
        if hard and L > hard:
            flags.append(f"exceeds hard cap {hard}")
        if rule.get("visible") and L > rule["visible"]:
            flags.append(f"only first {rule['visible']} chars show in feed")
        if not s:
            flags.append("empty")
        if L and L < 12 and group != "paths":
            flags.append("very short — wasted real estate")
        if policy.get("no_exclamation_in_headlines") and group == "headlines" and "!" in s:
            flags.append("policy: exclamation marks not allowed in Google/Microsoft headlines")
        if re.search(r"[!?.]{2,}", s):
            flags.append("policy: repeated punctuation")
        if caps_ratio(s) > 0.5 and len(text.words(s)) > 1:
            flags.append("mostly ALL CAPS — policy risk and reads as shouting")
        if re.search(r"\bclick here\b", s, re.I):
            flags.append("policy: 'click here' is disallowed on Google")
        if group != "paths" and s and not any(c.isalpha() for c in s):
            flags.append("no words")
        key = _norm_key(s)
        for k, j in seen:
            if key and k and len(key & k) / len(key | k) >= 0.6:
                flags.append(f"near-duplicate of #{j}")
                break
        seen.append((key, i))
        rows.append({"n": i, "text": s, "chars": L, "limit": limit, "fits": not any("OVER" in f or "exceeds" in f for f in flags), "flags": flags})
    return rows, issues


def _rsa_combinations(headlines: list[str], descriptions: list[str], pins: dict[str, list[int]]) -> int:
    """Ordered (headline1, headline2, headline3) × (desc1, desc2) selections that respect pins."""
    h_idx = list(range(1, len(headlines) + 1))
    d_idx = list(range(1, len(descriptions) + 1))
    h_pin = {int(k[1:]): v for k, v in pins.items() if k.startswith("h")}
    d_pin = {int(k[1:]): v for k, v in pins.items() if k.startswith("d")}

    def ok(seq: tuple[int, ...], pin: dict[int, list[int]]) -> bool:
        for pos, item in enumerate(seq, 1):
            allowed = pin.get(item)
            if allowed and pos not in allowed:
                return False
            # if any asset is pinned to this position, position must use a pinned asset
            pinned_here = [a for a, p in pin.items() if pos in p]
            if pinned_here and item not in pinned_here:
                return False
        return True

    h_count = sum(1 for seq in permutations(h_idx, min(3, len(h_idx))) if ok(seq, h_pin)) if h_idx else 0
    d_count = sum(1 for seq in permutations(d_idx, min(2, len(d_idx))) if ok(seq, d_pin)) if d_idx else 0
    return h_count * d_count


@AGENT.tool
def validate_platform_copy(
    platform: Platform,
    headlines: list[str] = [],
    descriptions: list[str] = [],
    primary_texts: list[str] = [],
    paths: list[str] = [],
    pins: dict = {},
    keyword: str = "",
) -> dict:
    """Validate ad assets against a platform's exact character limits, asset counts, pins and policy rules.

    Call after drafting and before delivering. For Google/Microsoft RSA it also counts the
    ad combinations that survive your pins and checks keyword presence in headlines.

    Args:
        platform: One of google_rsa, microsoft_rsa, meta, linkedin, x, tiktok, pinterest, reddit.
        headlines: Headline / title assets.
        descriptions: Description assets.
        primary_texts: Primary / intro / post text assets (Meta, LinkedIn, X, TikTok).
        paths: Display-path fragments (Google/Microsoft RSA only).
        pins: RSA pins as {"h1": [1], "h4": [2], "d2": [1]} meaning headline 1 pinned to position 1, etc.
        keyword: Target keyword; checks how many headlines include it (Google/Microsoft).
    """
    if platform not in LIMITS:
        raise ToolError(f"Unknown platform {platform!r}. Use one of: {', '.join(LIMITS)}.")
    total_items = len(headlines) + len(descriptions) + len(primary_texts) + len(paths)
    if total_items == 0:
        raise ToolError("Provide at least one asset (headlines, descriptions, primary_texts or paths).")
    if total_items > 200:
        raise ToolError("Too many assets (max 200 per call).")
    rules = LIMITS[platform]
    out: dict = {"platform": platform, "issues": []}
    for group, items in (("headlines", headlines), ("descriptions", descriptions), ("primary_texts", primary_texts), ("paths", paths)):
        rows, issues = _check_group([str(x) for x in items], rules.get(group), group, rules["policy"])
        out[group] = rows
        out["issues"].extend(issues)
    if platform in ("google_rsa", "microsoft_rsa"):
        try:
            pin_map = {str(k).lower(): [int(p) for p in v] for k, v in (pins or {}).items()}
        except (TypeError, ValueError):
            raise ToolError('pins must look like {"h1": [1], "d2": [1]}.') from None
        for k, v in pin_map.items():
            if not re.fullmatch(r"[hd]\d{1,2}", k) or any(p < 1 or p > (3 if k[0] == "h" else 2) for p in v):
                raise ToolError(f"Bad pin {k!r}: headline positions are 1-3, description positions 1-2.")
        combos = _rsa_combinations(headlines, descriptions, pin_map) if headlines and descriptions else 0
        unpinned = _rsa_combinations(headlines, descriptions, {}) if headlines and descriptions else 0
        out["rsa_combinations"] = combos
        out["rsa_combinations_unpinned"] = unpinned
        if pin_map and unpinned and combos / unpinned < 0.25:
            out["issues"].append(f"Pins cut combinations to {combos:,} of {unpinned:,} ({100 * combos / unpinned:.0f}%) — expect 'Poor' Ad Strength.")
        if keyword:
            kw = keyword.lower()
            with_kw = [r["n"] for r in out["headlines"] if kw in r["text"].lower()]
            out["headlines_with_keyword"] = with_kw
            if len(with_kw) < 3 and len(headlines) >= 5:
                out["issues"].append(f"Only {len(with_kw)} headline(s) contain '{keyword}' — Google recommends the keyword in ≥ 3 headlines.")
    overflow = sum(1 for g in ("headlines", "descriptions", "primary_texts", "paths") for r in out[g] if not r["fits"])
    dupes = sum(1 for g in ("headlines", "descriptions", "primary_texts") for r in out[g] if any("duplicate" in f for f in r["flags"]))
    policy = sum(1 for g in ("headlines", "descriptions", "primary_texts") for r in out[g] if any(f.startswith("policy") for f in r["flags"]))
    out["ready"] = overflow == 0 and policy == 0 and not out["issues"]
    out["summary"] = (
        f"{platform}: {overflow} over limit, {dupes} near-duplicate, {policy} policy flag(s), {len(out['issues'])} structural issue(s). "
        + ("Ready to upload." if out["ready"] else "Fix the flagged assets before upload.")
    )
    return out


ANGLE_PATTERNS: dict[str, re.Pattern] = {
    "social_proof": re.compile(r"\b(\d[\d,.]*\s*(k|m|\+)?\s*(customers|users|teams|companies|reviews|brands|people|marketers)|rated|trusted by|loved by|★|stars|award|#1)\b", re.I),
    "urgency": re.compile(r"\b(today|now|ends|last chance|limited|only \d+|hurry|deadline|this week|before|expires|left)\b", re.I),
    "price_value": re.compile(r"(\$|€|£|\b\d+\s?%\s?off|\bfree\b|\bsave\b|per month|/mo|pricing|plans? from|no credit card|cheaper|affordable|discount)", re.I),
    "how_to": re.compile(r"\b(how to|guide|step[- ]by[- ]step|learn|tutorial|ways to)\b", re.I),
    "question": re.compile(r"\?"),
    "objection_kill": re.compile(r"\b(no (setup|contract|coding|code|credit card|commitment)|without|cancel anytime|in \d+ (minutes?|seconds?|hours?|days?)|easy|simple|hassle-free|migrate|import)\b", re.I),
    "fear_loss": re.compile(r"\b(stop|losing|lose|missing|mistakes?|risk|wasting|avoid|never again|tired of|broken|leak)\b", re.I),
    "comparison": re.compile(r"\b(vs\.?|versus|alternative|instead of|switch from|better than|compare|unlike)\b", re.I),
    "identity": re.compile(r"\b(for|built for|made for|designed for)\s+(small|busy|growing|remote|modern|startups?|founders|teams|agencies|marketers|developers|ops|hr|sales|smbs?|enterprises?|creators|freelancers)\b", re.I),
    "feature": re.compile(r"\b(with|includes?|built-in|integrat|automat|ai-powered|dashboard|template|sync|api|analytics|real-time|reports?)\b", re.I),
    "benefit": re.compile(r"\b(get|grow|boost|double|cut|reduce|faster|more|less|increase|improve|save time|close more|ship|win|hit|reach)\b", re.I),
    "curiosity": re.compile(r"\b(secret|why|what|nobody|surprising|weird|truth|behind|hidden|actually)\b", re.I),
}
ANGLE_ORDER = list(ANGLE_PATTERNS)


def _angles_for(line: str) -> list[str]:
    hits = [a for a in ANGLE_ORDER if ANGLE_PATTERNS[a].search(line)]
    # Curiosity via "why/what" is only meaningful in a question or without a benefit verb.
    return hits or ["generic"]


@AGENT.tool
def angle_coverage(lines: list[str], min_angles: int = 5) -> dict:
    """Map each headline / primary text to persuasion angles and report which angles the set is missing.

    Call on a drafted set to stop it being one idea rephrased fifteen times.

    Args:
        lines: Headlines or primary texts to classify.
        min_angles: Minimum distinct angles a good set should cover (default 5).
    """
    if not lines:
        raise ToolError("lines is empty.")
    if len(lines) > 200:
        raise ToolError("Too many lines (max 200).")
    per_line = []
    counts: Counter[str] = Counter()
    for i, raw in enumerate(lines, 1):
        s = str(raw).strip()
        angles = _angles_for(s)
        primary = angles[0]
        counts[primary] += 1
        per_line.append({"n": i, "text": s, "primary_angle": primary, "all_angles": angles})
    n = len(lines)
    covered = [a for a in ANGLE_ORDER if counts[a]]
    missing = [a for a in ANGLE_ORDER if not counts[a]]
    dominant = counts.most_common(1)[0]
    dominance_pct = round(100 * dominant[1] / n, 1)
    fixes = []
    if len(covered) < min_angles:
        fixes.append(f"Only {len(covered)} angle(s) covered; rewrite lines into: {', '.join(missing[: min_angles - len(covered) + 1])}.")
    if dominance_pct > 40 and n >= 5:
        fixes.append(f"'{dominant[0]}' owns {dominance_pct}% of lines — move {dominant[1] - max(1, round(0.4 * n))} of them to other angles.")
    if counts["generic"]:
        fixes.append(f"{counts['generic']} line(s) hit no angle — they're vague; add a number, a who, or a specific outcome.")
    return {
        "lines": per_line,
        "angle_counts": dict(counts.most_common()),
        "angles_covered": len(covered),
        "angles_missing": missing,
        "dominant_angle": {"angle": dominant[0], "share_pct": dominance_pct},
        "meets_bar": len(covered) >= min_angles and dominance_pct <= 40 and not counts["generic"],
        "fixes": fixes,
        "summary": f"{len(covered)} of {len(ANGLE_ORDER)} angles covered across {n} lines; dominant: {dominant[0]} ({dominance_pct}%).",
    }


@AGENT.tool
def score_ad_copy(line: str, max_chars: int = 30, keyword: str = "", asset_type: Literal["headline", "description", "primary_text"] = "headline") -> dict:
    """Score one ad line 0-100 on specificity, hook, CTA, fit-to-limit and policy risk, with concrete fixes.

    Call on every drafted line; keep ≥ 65, rewrite < 50.

    Args:
        line: The ad line to score.
        max_chars: Character limit for this asset (e.g. 30 for RSA headline, 125 for Meta primary text fold).
        keyword: Target keyword or phrase; rewarded when present.
        asset_type: headline, description or primary_text — changes what "good" means.
    """
    s = (line or "").strip()
    if not s:
        raise ToolError("line is empty.")
    if len(s) > 5000:
        raise ToolError("line too long (max 5000 chars).")
    if max_chars < 5 or max_chars > 5000:
        raise ToolError("max_chars must be between 5 and 5000.")
    ws = text.words(s)
    low = s.lower()
    L = visible_len(s)
    score = 50
    reasons, fixes = [], []
    # Fit
    if L > max_chars:
        score -= 30
        reasons.append(f"over limit by {L - max_chars}")
        fixes.append(f"Cut to ≤ {max_chars} chars.")
    elif L >= 0.7 * max_chars:
        score += 10
        reasons.append("uses the space well")
    elif L < 0.4 * max_chars:
        score -= 8
        reasons.append("leaves most of the limit unused")
        fixes.append("Add a specific outcome or proof to use the space.")
    # Specificity: numbers
    if re.search(r"\d", s):
        score += 12
        reasons.append("contains a number")
    else:
        fixes.append("Add a concrete number (time saved, %, count, price).")
    # Keyword
    if keyword and keyword.lower() in low:
        score += 10
        reasons.append("contains keyword")
    elif keyword:
        fixes.append(f"Include '{keyword}' for relevance/Quality Score.")
    # Second person / power words
    if re.search(r"\b(you|your)\b", low):
        score += 6
        reasons.append("speaks to 'you'")
    pw = [w for w in (x.lower() for x in ws) if w in POWER_WORDS]
    if pw:
        score += min(8, 3 * len(pw))
        reasons.append(f"power words: {', '.join(sorted(set(pw))[:4])}")
    # CTA
    first = ws[0].lower() if ws else ""
    has_cta = first in CTA_VERBS or any(w.lower() in CTA_VERBS for w in ws[:2])
    if asset_type in ("description", "primary_text"):
        if has_cta or re.search(r"\b(get|start|try|book|join|download|see|learn) \w+", low):
            score += 8
            reasons.append("has a call to action")
        else:
            fixes.append("End with a verb-first CTA (Start free trial, Book a demo).")
    elif has_cta:
        score += 5
        reasons.append("verb-first")
    # Superlatives without proof
    if re.search(r"\b(best|#1|leading|world-class|premier|ultimate|top-rated)\b", low) and not re.search(r"\d", s):
        score -= 10
        reasons.append("unproven superlative")
        fixes.append("Replace the superlative with a number or a named proof.")
    # Brand-first
    if asset_type == "primary_text" and re.match(r"^(welcome to|introducing|at [A-Z])", s):
        score -= 10
        reasons.append("opens with the brand, not the reader")
        fixes.append("Open with the reader's outcome or problem; brand goes later.")
    # Policy / hygiene
    if "!" in s and asset_type == "headline":
        score -= 15
        reasons.append("exclamation in headline (Google policy)")
        fixes.append("Remove the exclamation mark.")
    if re.search(r"[!?.]{2,}", s):
        score -= 10
        reasons.append("repeated punctuation")
    if caps_ratio(s) > 0.5 and len(ws) > 1:
        score -= 15
        reasons.append("ALL CAPS")
        fixes.append("Use sentence or title case.")
    if count_emoji(s) > 2:
        score -= 5
        reasons.append("emoji overload")
    hits = spam_hits(s)
    if hits:
        score -= min(15, 5 * len(hits))
        reasons.append(f"spam-trigger words: {', '.join(hits[:3])}")
    # Readability: long words
    long_words = [w for w in ws if len(w) >= 12]
    if long_words:
        score -= 4
        fixes.append(f"Shorten long words: {', '.join(long_words[:2])}.")
    if asset_type == "primary_text":
        # Hook in first 125
        head = s[:125]
        if not re.search(r"\d|\?|you", head, re.I):
            score -= 8
            fixes.append("Put a number, a question or 'you' in the first 125 chars (the fold).")
    score = max(0, min(100, score))
    grade = "ship" if score >= 65 else "revise" if score >= 50 else "rewrite"
    return {
        "line": s,
        "chars": L,
        "max_chars": max_chars,
        "score": score,
        "grade": grade,
        "reasons": reasons,
        "fixes": fixes,
        "angles": _angles_for(s),
        "verdict": f"{score}/100 — {grade}." + (f" Top fix: {fixes[0]}" if fixes else ""),
    }


@AGENT.tool
def ad_math(
    daily_budget: float,
    cpc: float,
    cvr_pct: float,
    aov: float,
    margin_pct: float,
    ctr_pct: float = 0.0,
    target_profit_share_pct: float = 0.0,
) -> dict:
    """Project clicks, conversions, CPA, ROAS, break-even ROAS and the max CPC a campaign can afford.

    Call before writing copy so the creative is aimed at a CPA that actually works.

    Args:
        daily_budget: Daily spend in currency units.
        cpc: Expected cost per click.
        cvr_pct: Landing page conversion rate in percent (click → primary conversion).
        aov: Average order value / revenue per conversion.
        margin_pct: Gross margin in percent (e.g. 60).
        ctr_pct: Optional expected CTR in percent, to project impressions.
        target_profit_share_pct: Share of gross profit you want to keep after ad cost (e.g. 20 → target CPA leaves 20% profit).
    """
    for name, v in (("daily_budget", daily_budget), ("cpc", cpc), ("aov", aov)):
        if v <= 0:
            raise ToolError(f"{name} must be > 0.")
    if not 0 < cvr_pct <= 100 or not 0 < margin_pct <= 100 or not 0 <= target_profit_share_pct < 100 or ctr_pct < 0 or ctr_pct > 100:
        raise ToolError("cvr_pct and margin_pct must be in (0, 100]; target_profit_share_pct in [0, 100); ctr_pct in [0, 100].")
    cvr, margin, keep = cvr_pct / 100, margin_pct / 100, target_profit_share_pct / 100
    clicks = daily_budget / cpc
    conversions = clicks * cvr
    cpa = cpc / cvr
    revenue = conversions * aov
    gross_profit = revenue * margin
    roas = revenue / daily_budget
    break_even_roas = 1 / margin
    break_even_cpa = aov * margin
    target_cpa = break_even_cpa * (1 - keep)
    max_cpc = target_cpa * cvr
    net = gross_profit - daily_budget
    be_cvr = cpc / break_even_cpa
    out = {
        "daily": {
            "clicks": round(clicks, 1),
            "conversions": round(conversions, 2),
            "revenue": round(revenue, 2),
            "gross_profit_before_ads": round(gross_profit, 2),
            "net_after_ads": round(net, 2),
        },
        "monthly_30d": {"spend": round(30 * daily_budget, 2), "conversions": round(30 * conversions, 1), "net_after_ads": round(30 * net, 2)},
        "cpa": round(cpa, 2),
        "roas": round(roas, 2),
        "break_even_roas": round(break_even_roas, 2),
        "break_even_cpa": round(break_even_cpa, 2),
        "break_even_cvr_pct": round(100 * be_cvr, 2),
        "target_cpa": round(target_cpa, 2),
        "max_cpc_for_target": round(max_cpc, 2),
        "profitable": net > 0,
        "days_to_50_conversions": math.ceil(50 / conversions) if conversions > 0 else None,
    }
    if ctr_pct:
        out["daily"]["impressions"] = round(clicks / (ctr_pct / 100))
    if net > 0:
        verdict = f"Profitable: CPA {cpa:.2f} vs break-even {break_even_cpa:.2f}; ROAS {roas:.2f} vs break-even {break_even_roas:.2f}."
    else:
        verdict = f"Loses money: CPA {cpa:.2f} > break-even {break_even_cpa:.2f}. Need CVR ≥ {100 * be_cvr:.2f}% or CPC ≤ {max_cpc:.2f}."
    if target_profit_share_pct and cpa > target_cpa:
        verdict += f" Misses the {target_profit_share_pct:.0f}% profit target (CPA must be ≤ {target_cpa:.2f})."
    out["verdict"] = verdict
    return out

