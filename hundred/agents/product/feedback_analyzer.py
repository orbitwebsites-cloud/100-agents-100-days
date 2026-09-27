"""Feedback Analyzer — NPS/CSAT/CES with confidence intervals, theme counting, and a prioritised fix list."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

from ...core import Agent, ToolError
from ._common import check_rows, mean, pct, to_float

AGENT = Agent(
    slug="feedback-analyzer",
    name="Feedback Analyzer",
    category="product",
    tagline="Turn survey scores and open-text feedback into NPS with error bars, ranked themes, and what to fix first.",
    description=(
        "Analyses customer feedback like a VoC (voice-of-customer) lead: computes NPS, CSAT and CES "
        "correctly with margins of error and segment splits, tags open-text responses against a theme "
        "taxonomy and counts responses (not mentions), scores sentiment per theme with a product-specific "
        "lexicon, runs a driver analysis to show which themes separate detractors from promoters, and "
        "ranks fixes by frequency × severity × reach. Output is a one-page readout leadership acts on."
    ),
    triggers=[
        "calculate NPS / CSAT / CES from survey results",
        "analyse customer feedback / survey comments",
        "what are people complaining about most",
        "find themes in app store reviews or support tickets",
        "which issues hurt our NPS the most",
        "summarise this feedback for leadership",
    ],
    examples=[
        "Here are 220 NPS responses (score + comment + plan). What's our NPS, and what drives detractors?",
        "Categorise these 150 app store reviews into themes and tell me the top 5 fixes.",
        "CSAT dropped from 4.4 to 4.1 last month — here are the comments. Why?",
    ],
    connectors=["Google Sheets", "Airtable", "Zendesk", "Intercom", "Notion", "Slack"],
    playbook="""
    ## Standard
    You are a voice-of-customer lead. Excellent feedback analysis is quantified (every theme has a
    count and a share of responses), honest about statistical noise (NPS on 100 responses carries
    a ±10-17 point margin), and ends in a ranked list of fixes with an expected metric impact. The one metric that
    matters is **fixes shipped that moved the score** — so the readout is short, ranked, and names
    the driver behind the number.

    ## Intake
    Proceed with what you have. Ask (max 3) only if needed: (1) which survey type (NPS 0-10, CSAT
    1-5, CES 1-7) and the time window, (2) segment fields available (plan, tenure, platform),
    (3) the previous period's score and n for a delta. If comments come without scores, skip driver
    analysis and say so.

    ## Procedure
    1. **Compute the score correctly.** Call `feedback_analyzer__score_survey` with the raw scores
       and survey type (plus segment labels if any). It returns NPS (promoters 9-10 minus
       detractors 0-6), CSAT (% 4-5 of 5), or CES, each with the 95% margin of error, the
       distribution, and per-segment scores with a minimum-n warning (n < 30 → don't quote). Never
       compute NPS in your head; never quote a segment score below n = 30 without the caveat.
    2. **Build the theme taxonomy.** Start from the tool's default taxonomy (pricing, performance,
       bugs, usability, onboarding, support, missing feature, integrations, reliability, mobile,
       billing, documentation) and add ≤ 5 product-specific themes with keywords you saw in a first
       skim.
    3. **Tag and count.** Call `feedback_analyzer__count_themes` with the responses and taxonomy.
       It tags each comment by keyword match, counts *responses* per theme (a 300-word rant is one
       response), splits by segment and by score band, and scores sentiment per theme. Read the
       untagged sample it returns and add themes if > 20% is untagged.
    4. **Find the drivers.** Call `feedback_analyzer__driver_analysis` with the tagged rows. For
       each theme it compares the mean score of responses mentioning it vs not, and the detractor
       rate — the themes with the largest negative gap are your NPS drivers. Ignore themes with
       n < 10.
    5. **Rank the fixes.** Call `feedback_analyzer__prioritize_fixes` with frequency, severity
       (1-3: annoyance / blocks a task / causes churn), and reach (segments affected). It computes
       priority = frequency share × severity × reach and returns the ordered list with the share of
       detractors each fix would address. Top 3 go in the readout.
    6. **Write the readout** in the output format. Lead with the number and its delta, then the
       three drivers with quotes, then fixes. Report what is *not* a problem too (top praise) — it's
       what marketing should say.
    7. Post to Slack/Notion if connected; otherwise output ready to paste.

    ## Frameworks
    - **NPS** = %promoters(9-10) − %detractors(0-6); range −100..100. SaaS median ≈ 30-40 (varies
      by source); B2C consumer apps often lower. Margin of error ≈ 1.96 × √(p_p(1−p_p) + p_d(1−p_d) + 2·p_p·p_d)/n.
    - **CSAT** = % of responses rating 4 or 5 (on 1-5). **CES** (1-7): report mean and % ≥ 5.
    - **Minimum n:** don't report a segment under 30; don't claim a change smaller than the MoE of the
      change — both periods are noisy, so it is ≈ MoE × √2 for equal n (pass previous_n).
    - **Response-level counting:** themes are counted per response; a theme's share is
      responses-with-theme ÷ responses-with-comment.
    - **Severity scale:** 1 annoyance, 2 blocks a task (workaround exists), 3 blocks a task / churn risk.

    ## Output format
    ```
    # Feedback readout — <period> (n=<responses>, <n_comments> comments)
    **NPS: 32 (±8)** — was 29 (Δ +3, within noise) · Promoters 45% · Passives 42% · Detractors 13%
    By segment: Enterprise 48 (n=61) · SMB 21 (n=140) · Free — n=18, not reported

    ## What's driving detractors
    | Theme | Responses | Share | Mean score (with / without) | Detractor rate |
    1. <Theme> — 34 (15%) — 5.1 vs 8.2 — "quote" (SMB, score 3)
    2. …

    ## Top praise (say this in marketing)
    - <theme> — 27% of promoters mention it

    ## Fix list (ranked)
    | # | Fix | Addresses | Detractors covered | Severity | Owner |
    ## Method
    Tagged N/M comments (X% untagged); segments under n=30 not reported.
    ```

    ## Anti-patterns
    - Quoting NPS to a decimal or celebrating a 2-point move on n=80. Show the error bar.
    - Counting mentions. One angry customer is one response.
    - "Users want more features." Which feature, how many asked, from which segment?
    - Theming by reading 20 comments and extrapolating. Tag them all; report the untagged rate.
    - Ignoring passives. They're the cheapest promoters to create.
    - A readout with no fix list. Analysis without a decision is a chart.
    """,
)

DEFAULT_TAXONOMY: dict[str, list[str]] = {
    "pricing": ["price", "pricing", "pricey", "overpriced", "expensive", "cost", "costly", "cheap", "cheaper", "afford", "worth", "value for money", "too much money"],
    "performance": ["slow", "lag", "laggy", "speed", "fast", "load", "loading", "load time", "freeze", "freezes", "sluggish", "performance", "takes forever", "times out", "timeout"],
    "bugs": ["bug", "bugs", "crash", "crashes", "crashed", "broken", "glitch", "error", "errors", "doesn't work", "does not work", "not working"],
    "usability": ["confusing", "intuitive", "easy to use", "hard to use", "clunky", "ui", "ux", "interface", "navigate", "navigation", "find", "cluttered", "simple", "simplest", "layout"],
    "onboarding": ["onboarding", "setup", "set up", "getting started", "tutorial", "learning curve", "sign up", "signup", "first time"],
    "support": ["support", "customer service", "help desk", "response time", "ticket", "chat support", "no reply", "helpful staff"],
    "missing_feature": ["missing", "wish", "would be nice", "would love", "need a way", "needs a", "please add", "feature request", "add the ability", "lack", "lacks", "no way to", "can't do", "cannot do"],
    # "export"/"import" deliberately NOT here: CSV/PDF export is a core feature, and export bugs are bugs, not integrations
    "integrations": ["integration", "integrate", "api", "zapier", "slack", "salesforce", "hubspot", "sync with", "webhook", "connect to"],
    "reliability": ["downtime", "outage", "down", "unreliable", "reliable", "uptime", "lost data", "data loss", "stable", "unstable"],
    "mobile": ["mobile", "iphone", "android", "ios", "app store", "phone", "tablet", "ipad"],
    "billing": ["billing", "invoice", "charged", "refund", "subscription", "cancel", "renewal", "credit card", "payment"],
    "documentation": ["documentation", "docs", "help center", "help article", "guide", "manual", "instructions", "faq"],
}
POSITIVE = re.compile(r"\b(love|loved|great|excellent|amazing|awesome|fantastic|perfect|easy|helpful|smooth|fast|reliable|intuitive|best|happy|pleased|wonderful|brilliant|recommend|impressed|seamless|delight\w*)\b", re.I)
NEGATIVE = re.compile(r"\b(hate|hated|terrible|awful|horrible|worst|slow|broken|bug|bugs|crash\w*|confusing|frustrat\w*|annoy\w*|useless|expensive|disappoint\w*|poor|bad|difficult|hard|missing|unreliable|clunky|painful|lost|fail\w*|can'?t|cannot|never|nightmare|waste)\b", re.I)
NEGATOR = re.compile(r"\b(not|no|never|isn'?t|wasn'?t|don'?t|doesn'?t|didn'?t|hardly|barely)\s+(?:\w+\s+)?$", re.I)


def _sentiment(s: str) -> float:
    """-1..1 lexicon score with simple negation flipping."""
    pos = neg = 0
    for rx, sign in ((POSITIVE, 1), (NEGATIVE, -1)):
        for m in rx.finditer(s):
            before = s[max(0, m.start() - 20) : m.start()]
            val = -sign if NEGATOR.search(before) else sign
            if val > 0:
                pos += 1
            else:
                neg += 1
    tot = pos + neg
    return round((pos - neg) / tot, 2) if tot else 0.0


def _moe_nps(pp: float, pd: float, n: int) -> float:
    var = pp * (1 - pp) + pd * (1 - pd) + 2 * pp * pd
    return round(100 * 1.96 * math.sqrt(max(var, 0) / n), 1)


@AGENT.tool
def score_survey(scores: list[float], survey: str = "nps", segments: list[str] | None = None, previous_score: float | None = None, previous_n: int | None = None) -> dict:
    """Compute NPS / CSAT / CES with 95% margin of error, distribution, and per-segment scores (min n=30).

    Args:
        scores: One numeric score per response (NPS 0-10, CSAT 1-5, CES 1-7).
        survey: "nps", "csat" or "ces".
        segments: Optional segment label per response, same length and order as scores.
        previous_score: Last period's headline score, to judge whether the change beats the noise.
        previous_n: Last period's number of responses. The change is tested against the margin of error of the
            DIFFERENCE of two samples (both periods' noise), not this period's margin alone; if omitted, the
            previous period is assumed to have the same n (difference MoE = this MoE × √2).
    """
    rows = check_rows(scores, "scores", 50_000)
    kind = str(survey).strip().lower()
    if kind not in {"nps", "csat", "ces"}:
        raise ToolError("survey must be 'nps', 'csat' or 'ces'.")
    hi = {"nps": 10, "csat": 5, "ces": 7}[kind]
    lo = 0 if kind == "nps" else 1
    vals = [to_float(v, f"scores[{i}]", lo, hi) for i, v in enumerate(rows)]
    if segments is not None and len(segments) != len(vals):
        raise ToolError(f"segments has {len(segments)} labels but scores has {len(vals)} values.")

    def headline(xs: list[float]) -> dict:
        n = len(xs)
        if kind == "nps":
            p = sum(1 for x in xs if x >= 9) / n
            d = sum(1 for x in xs if x <= 6) / n
            return {"score": round(100 * (p - d), 1), "moe": _moe_nps(p, d, n), "promoters_pct": round(100 * p, 1), "passives_pct": round(100 * (1 - p - d), 1), "detractors_pct": round(100 * d, 1), "n": n}
        if kind == "csat":
            sat = sum(1 for x in xs if x >= 4) / n
            return {"score": round(100 * sat, 1), "moe": round(100 * 1.96 * math.sqrt(sat * (1 - sat) / n), 1), "mean": round(mean(xs), 2), "n": n}
        m = mean(xs)
        sd = math.sqrt(sum((x - m) ** 2 for x in xs) / max(1, n - 1)) if n > 1 else 0.0
        return {"score": round(m, 2), "moe": round(1.96 * sd / math.sqrt(n), 2), "pct_easy": round(100 * sum(1 for x in xs if x >= 5) / n, 1), "n": n}

    head = headline(vals)
    dist = Counter(int(v) for v in vals)
    by_seg = {}
    if segments:
        groups: dict[str, list[float]] = defaultdict(list)
        for s, v in zip(segments, vals):
            groups[str(s).strip() or "unknown"].append(v)
        for s, xs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            h = headline(xs)
            h["reportable"] = len(xs) >= 30
            by_seg[s] = h
    delta = None
    if previous_score is not None:
        prev = to_float(previous_score, "previous_score")
        n_now = head["n"]
        n_prev = int(to_float(previous_n, "previous_n", 2)) if previous_n is not None else n_now
        # SE of a difference of independent estimates = √(se₁² + se₂²); the previous period's variance is
        # approximated by this period's (its distribution is unknown), scaled by its own n
        moe_diff = round(head["moe"] * math.sqrt(1 + n_now / n_prev), 1)
        change = round(head["score"] - prev, 1)
        delta = {"previous": prev, "previous_n": n_prev, "change": change, "moe_of_change": moe_diff, "beats_noise": abs(change) > moe_diff}
    return {
        "survey": kind,
        **head,
        "distribution": {str(k): dist[k] for k in sorted(dist)},
        "by_segment": by_seg,
        "delta": delta,
        "verdict": f"{kind.upper()} {head['score']} (±{head['moe']}, n={head['n']})" + (f"; change of {delta['change']:+} is {'real' if delta['beats_noise'] else 'within noise'} (±{delta['moe_of_change']} for a change)" if delta else ""),
        "note": "Do not quote segments with reportable=false (n<30). NPS benchmarks vary widely by industry; compare to your own history first.",
    }


@AGENT.tool
def count_themes(responses: list[dict], taxonomy: dict[str, list[str]] | None = None, sample_untagged: int = 10) -> dict:
    """Tag open-text feedback against a theme taxonomy and count responses per theme, by segment and score band.

    Args:
        responses: List of {"text": str, "score": number (optional), "segment": str (optional)}; up to 5000.
        taxonomy: {"theme": ["keyword", ...]} — defaults to a 12-theme SaaS taxonomy; your themes are merged in.
        sample_untagged: How many untagged comments to return so you can extend the taxonomy (default 10).
    """
    rows = check_rows(responses, "responses", 5000)
    tax = {k: list(v) for k, v in DEFAULT_TAXONOMY.items()}
    if taxonomy:
        if not isinstance(taxonomy, dict):
            raise ToolError("taxonomy must be an object of theme → keyword list.")
        for k, v in taxonomy.items():
            if not isinstance(v, list) or not v:
                raise ToolError(f"taxonomy['{k}'] must be a non-empty list of keywords.")
            tax[str(k).strip().lower()] = [str(w).lower() for w in v][:50]
    # optional plural suffix so "costs", "loads", "integrations" match their singular keyword
    patterns = {t: re.compile(r"\b(?:" + "|".join(re.escape(w) for w in ws) + r")(?:s|es)?\b", re.I) for t, ws in tax.items()}
    counts: Counter = Counter()
    by_seg: dict[str, Counter] = defaultdict(Counter)
    by_band: dict[str, Counter] = defaultdict(Counter)
    sentiment: dict[str, list[float]] = defaultdict(list)
    examples: dict[str, list[str]] = defaultdict(list)
    tagged_rows, untagged, with_comment = [], [], 0
    for i, raw in enumerate(rows):
        if not isinstance(raw, dict):
            raise ToolError(f"responses[{i}] must be an object with 'text'.")
        t = str(raw.get("text", "")).strip()
        if not t:
            continue
        with_comment += 1
        seg = str(raw.get("segment", "")).strip() or None
        score = raw.get("score")
        band = None
        if score is not None:
            sc = to_float(score, f"responses[{i}].score")
            band = "detractor" if sc <= 6 else "passive" if sc <= 8 else "promoter"
        themes = [th for th, rx in patterns.items() if rx.search(t)]
        sent = _sentiment(t)
        for th in themes:
            counts[th] += 1
            sentiment[th].append(sent)
            if seg:
                by_seg[th][seg] += 1
            if band:
                by_band[th][band] += 1
            if len(examples[th]) < 3:
                examples[th].append(t[:200])
        if not themes and len(untagged) < max(0, sample_untagged):
            untagged.append(t[:200])
        tagged_rows.append({"i": i, "themes": themes, "score": sc if band else None, "sentiment": sent, "band": band, "segment": seg})
    untagged_total = sum(1 for r in tagged_rows if not r["themes"])
    table = [
        {"theme": th, "responses": c, "share_pct": pct(c, with_comment), "sentiment": round(mean(sentiment[th]), 2), "by_segment": dict(by_seg[th]), "by_band": dict(by_band[th]), "examples": examples[th]}
        for th, c in counts.most_common()
    ]
    return {
        "responses_with_comment": with_comment,
        "tagged": with_comment - untagged_total,
        "untagged": untagged_total,
        "untagged_pct": pct(untagged_total, with_comment),
        "themes": table,
        "untagged_sample": untagged,
        "tagged_rows": tagged_rows,
        "next_step": "Pass tagged_rows (rows with a score) straight to feedback_analyzer__driver_analysis.",
        "verdict": (f"Top theme: {table[0]['theme']} ({table[0]['share_pct']}%)" if table else "No themes matched") + (f"; {pct(untagged_total, with_comment)}% untagged — extend the taxonomy" if with_comment and untagged_total / with_comment > 0.2 else ""),
    }


@AGENT.tool
def driver_analysis(tagged_rows: list[dict], min_n: int = 10) -> dict:
    """Find which themes drive the score: mean score and detractor rate with vs without each theme.

    Args:
        tagged_rows: List of {"themes": [str], "score": number} — e.g. from count_themes with scores added, or your own tagging.
        min_n: Minimum responses mentioning a theme for it to be reported (default 10).
    """
    rows = check_rows(tagged_rows, "tagged_rows", 5000)
    if not isinstance(min_n, int) or min_n < 1:
        raise ToolError("min_n must be a positive integer.")
    scored, skipped = [], 0
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            raise ToolError(f"tagged_rows[{i}] needs 'themes' and a numeric 'score'.")
        if r.get("score") is None:
            skipped += 1  # e.g. count_themes rows whose response had no score
            continue
        themes = r.get("themes") or []
        if not isinstance(themes, list):
            raise ToolError(f"tagged_rows[{i}].themes must be a list.")
        scored.append(({str(t).lower() for t in themes}, to_float(r["score"], f"tagged_rows[{i}].score", 0, 10)))
    if len(scored) < 2:
        raise ToolError("Need at least 2 scored rows for driver analysis.")
    all_scores = [s for _, s in scored]
    overall_mean = mean(all_scores)
    overall_det = sum(1 for s in all_scores if s <= 6) / len(all_scores)
    themes = sorted({t for ts, _ in scored for t in ts})
    out = []
    for th in themes:
        with_ = [s for ts, s in scored if th in ts]
        without = [s for ts, s in scored if th not in ts]
        if len(with_) < min_n or not without:
            continue
        gap = mean(with_) - mean(without)
        det_with = sum(1 for s in with_ if s <= 6) / len(with_)
        out.append({"theme": th, "n": len(with_), "mean_with": round(mean(with_), 2), "mean_without": round(mean(without), 2), "gap": round(gap, 2), "detractor_rate_pct": round(100 * det_with, 1), "detractor_share_pct": pct(sum(1 for s in with_ if s <= 6), sum(1 for s in all_scores if s <= 6))})
    out.sort(key=lambda r: r["gap"])
    negatives = [r for r in out if r["gap"] < -0.5]
    positives = [r for r in out if r["gap"] > 0.5]
    return {
        "responses": len(scored),
        "skipped_unscored": skipped,
        "overall_mean": round(overall_mean, 2),
        "overall_detractor_pct": round(100 * overall_det, 1),
        "drivers": out,
        "negative_drivers": [r["theme"] for r in negatives],
        "positive_drivers": [r["theme"] for r in reversed(positives)],
        "verdict": (f"Biggest drag: {negatives[0]['theme']} (gap {negatives[0]['gap']}, {negatives[0]['detractor_share_pct']}% of detractors)" if negatives else "No theme with a gap below −0.5 at this n"),
    }


@AGENT.tool
def prioritize_fixes(fixes: list[dict], total_responses: int) -> dict:
    """Rank fixes by frequency share × severity × reach, with the share of feedback each one addresses.

    Args:
        fixes: List of {"fix": str, "responses": int mentioning the problem, "severity": 1-3
            (1 annoyance, 2 blocks task with workaround, 3 blocks task / churn risk), "reach": 1-3
            (1 one segment, 2 several, 3 all), "effort": optional 1-3}.
        total_responses: Number of responses with comments (denominator for the share).
    """
    rows = check_rows(fixes, "fixes")
    if not isinstance(total_responses, int) or total_responses < 1:
        raise ToolError("total_responses must be a positive integer.")
    out = []
    for i, raw in enumerate(rows):
        if not isinstance(raw, dict) or not str(raw.get("fix", "")).strip():
            raise ToolError(f"fixes[{i}] needs 'fix', 'responses', 'severity' and 'reach'.")
        n = int(to_float(raw.get("responses"), "responses", 0, total_responses))
        sev = to_float(raw.get("severity"), "severity", 1, 3)
        reach = to_float(raw.get("reach"), "reach", 1, 3)
        effort = to_float(raw.get("effort", 2), "effort", 1, 3)
        share = n / total_responses
        priority = round(100 * share * sev * reach / 9, 1)  # normalised so max = 100 when share=1, sev=3, reach=3
        out.append({"fix": str(raw["fix"]).strip(), "responses": n, "share_pct": round(100 * share, 1), "severity": sev, "reach": reach, "effort": effort, "priority": priority, "priority_per_effort": round(priority / effort, 1)})
    out.sort(key=lambda r: (-r["priority"], -r["priority_per_effort"]))
    for rank, r in enumerate(out, 1):
        r["rank"] = rank
    top3 = out[:3]
    covered = min(100.0, round(sum(r["share_pct"] for r in top3), 1))
    return {"ranked": out, "top_3": [r["fix"] for r in top3], "top_3_cover_pct": covered, "verdict": f"Fix #1: {out[0]['fix']} (priority {out[0]['priority']}); top 3 address up to {covered}% of comments"}
