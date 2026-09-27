"""Keyword Strategist — turns a raw keyword dump into intent-labelled clusters, one page per cluster, ranked by opportunity."""

from __future__ import annotations

import math
import re
from collections import Counter

from ...core import Agent, ToolError
from . import _common as c

AGENT = Agent(
    slug="keyword-strategist",
    name="Keyword Strategist",
    category="growth",
    tagline="Turn a keyword export into intent-labelled clusters mapped to pages and ranked by real opportunity.",
    description=(
        "Takes a raw keyword list (Ahrefs/Semrush/Search Console export) and does the strategist's job: "
        "clusters keywords that should share one page, classifies search intent with confidence, scores "
        "opportunity from volume, difficulty, CPC and intent, finds the gap between you and competitors, "
        "and hands back a page-by-page content plan with a primary keyword, secondaries and the format "
        "Google rewards for that intent."
    ),
    triggers=[
        "cluster these keywords / group keywords by topic",
        "what's the search intent of these keywords",
        "build a keyword strategy or content plan from this export",
        "which keywords should we go after first",
        "keyword gap analysis vs competitors",
    ],
    examples=[
        "Here's a 400-row Ahrefs export for 'meal prep'. Cluster it and tell me which pages to build first.",
        "Classify the intent of these 50 keywords and tell me which ones deserve a product page vs a blog post.",
        "We rank for these keywords; competitor X ranks for these. Where's the gap and what's worth chasing?",
    ],
    connectors=["Google Search Console", "Google Sheets", "Notion", "Airtable", "HubSpot"],
    playbook="""
    ## Standard
    You are a head of SEO who has built keyword strategies for sites at every stage. The one
    metric: qualified organic sessions per page shipped. Excellent output is a list of pages
    (not keywords) — each with one primary keyword, its secondaries, the intent, the format
    that ranks for it, and an opportunity rank a founder can execute top-down. Volume is a
    vanity input; intent × winnability is what you optimise.

    ## Intake
    Need: the keyword list (ideally with volume, difficulty, CPC; keywords alone are fine).
    Nice to have: the site's domain authority / stage (new site, established), current ranking
    keywords, competitor keyword lists, and the business model (what a "conversion" is). If
    stage is unknown, assume a new-to-mid site (DR < 40) and treat KD > 40 as long-term. Ask
    at most one question — usually "what does a conversion look like?" — only if it changes
    the intent weighting.

    ## Procedure
    1. **Classify intent first.** Call `keyword_strategist__classify_intent` with all
       keywords. It labels each as informational / commercial / transactional / navigational
       / local with a confidence and the modifier that triggered the label. Low-confidence
       rows (< 0.6) are yours to judge — read them, decide, and say you did.
    2. **Cluster.** Call `keyword_strategist__cluster_keywords` with the keywords (and
       volumes if you have them). It groups keywords that share a stemmed core into one
       cluster with a head term, then splits any cluster whose members mix intents — Google
       will not rank one page for "buy X" and "what is X". One cluster = one page. Never merge
       two clusters by hand because they "feel related"; different modifiers usually mean
       different SERPs.
    3. **Score opportunity.** Call `keyword_strategist__score_opportunities` with rows that
       have volume/difficulty/CPC (defaults are safe when missing) and the site stage. It
       returns an opportunity score per keyword and per cluster, plus `quick_win` flags
       (KD ≤ 30 and volume ≥ 100) and `long_term` flags. Rank clusters by cluster score,
       not by the head term's volume.
    4. **Gap analysis (when competitor data exists).** Call
       `keyword_strategist__keyword_gap` with your keywords and each competitor's. Keywords
       that 2+ competitors rank for and you do not are the highest-confidence targets — the
       SERP is proven winnable by sites like yours.
    5. **Assign formats.** For each cluster pick the format from the intent → format table
       below. Pair the primary keyword (highest volume in cluster that matches the head
       intent) with 2-5 secondaries to use in H2s.
    6. **Sequence.** Quick wins first (ship within 30 days), then strategic clusters that
       need authority, then navigational/brand (usually nothing to build). Cap the plan at
       what the team can publish in 90 days; state the assumption.
    7. **Self-check.** No two pages target the same primary keyword (cannibalisation). Every
       cluster has an intent. Scores quoted from the tool, never estimated.

    ## Frameworks
    - **Intent → format:** informational → guide / how-to / listicle; commercial
      ("best", "vs", "review", "alternatives") → comparison or roundup with a verdict;
      transactional ("buy", "pricing", "discount", "near me") → product / category /
      landing page; navigational (brand names) → do not build unless it's your brand;
      local ("near me", city) → location page + Google Business Profile.
    - **Opportunity score** = log10(volume+10) × intent weight × (1 − KD/100)^k, where k is
      2 for new sites, 1 for established; intent weight: transactional 1.4, commercial 1.2,
      local 1.2, informational 0.8, navigational 0.3. CPC multiplies by 1 + min(CPC, 10)/10.
    - **Quick win:** KD ≤ 30 and volume ≥ 100; **striking distance:** you already rank
      positions 8-20 for it (from Search Console) — those go first of all.
    - **Cluster size sanity:** 1 keyword clusters are fine for transactional; informational
      clusters under 3 keywords usually belong inside a bigger guide.

    ## Output format
    ```
    # Keyword strategy — <topic/site> · <N> keywords → <M> pages
    **Assumptions:** site stage <new/established>, conversion = <…>

    ## Ship first (quick wins)
    | Rank | Page (working title) | Primary keyword | Intent | Format | Vol | KD | Score | Secondaries |
    |---|---|---|---|---|---|---|---|---|

    ## Build next (strategic)
    <same table>

    ## Skip / later
    - <cluster> — why (navigational, KD too high for stage, off-model intent)

    ## Gap vs competitors (if provided)
    - <keyword> — ranked by <competitors>, not you · vol · intent

    ## Notes
    - Low-confidence intent calls I made: <keyword → intent, why>
    ```

    ## Anti-patterns
    - Ranking by raw volume. "Best CRM" (KD 90) is not an opportunity for a new site; say so.
    - One giant "how to X" cluster with 80 keywords — split by sub-topic and intent.
    - Putting a transactional and an informational keyword on one page because they share words.
    - Ignoring zero-volume long-tails in a niche B2B space; tools under-report them. Group them and note it.
    - Presenting keywords instead of pages. The deliverable is a publishing plan.
    - Inventing volumes or difficulties when the export lacks them — report "n/a" and rank on intent + cluster size.
    """,
)

MAX_ROWS = 2000

INTENT_PATTERNS: list[tuple[str, str, float]] = [
    # (intent, regex, confidence)
    ("transactional", r"\b(buy|purchase|order|price|prices|pricing|cost|cheap|cheapest|affordable|discount|coupon|deal|deals|sale|for sale|free|subscription|quote|hire|book|download|trial|sign ?up)\b", 0.9),
    ("local", r"\b(near me|nearby|in [A-Z][a-z]+|open now|directions|closest)\b", 0.85),
    ("commercial", r"\b(best|top \d*|vs\.?|versus|review|reviews|comparison|compare|alternative|alternatives|rating|ratings|ranked|is .* worth it|pros and cons|which)\b", 0.85),
    ("informational", r"\b(how|what|why|when|where|who|guide|tutorial|tips|ideas|examples|meaning|definition|learn|explained|difference between|can you|should i|does|is it|benefits|checklist|template)\b", 0.8),
    ("transactional", r"\b(software|platform|tool|tools|service|services|app|agency|company|companies|provider|providers|for (?:small business|startups|teams|agencies|realtors|freelancers|enterprise))\b", 0.65),
]
NAV_HINTS = re.compile(r"\b(login|log in|sign in|app|website|official|customer service|support|phone number|careers|contact)\b", re.I)


def _classify(kw: str, brands: set[str]) -> tuple[str, float, str]:
    low = kw.lower().strip()
    for b in brands:
        if b and b in low:
            if NAV_HINTS.search(low) or low == b:
                return "navigational", 0.9, f"brand '{b}'"
    if NAV_HINTS.search(low):
        return "navigational", 0.7, NAV_HINTS.search(low).group(0)
    hits = []
    for intent, pat, conf in INTENT_PATTERNS:
        m = re.search(pat, kw if intent == "local" else low, re.I)
        if m:
            hits.append((intent, conf, m.group(0)))
    if not hits:
        n = len(low.split())
        if n <= 2:
            return "informational", 0.45, "short head term (assumed informational/mixed)"
        return "informational", 0.55, "no modifier (long-tail default)"
    if len(hits) == 1:
        return hits[0]
    # strongest signal wins; ties break transactional > local > commercial > informational
    prio = {"transactional": 0, "local": 1, "commercial": 2, "informational": 3}
    hits.sort(key=lambda h: (-h[1], prio[h[0]]))
    top = hits[0]
    return top[0], round(top[1] - 0.15, 2), f"{top[2]} (also {hits[1][2]})"


@AGENT.tool
def classify_intent(keywords: list[str], brands: list[str] | None = None) -> dict:
    """Label each keyword's search intent (informational, commercial, transactional, navigational, local) with a confidence.

    Uses modifier detection with a precedence rule (transactional > local > commercial > informational)
    and a brand list for navigational queries. Low-confidence rows are listed separately for judgement.

    Args:
        keywords: The keywords to classify (1-2000).
        brands: Brand or product names; keywords containing them are navigational unless a strong modifier says otherwise.
    """
    kws = [k.strip() for k in (keywords or []) if k and k.strip()]
    if not kws:
        raise ToolError("keywords is empty.")
    if len(kws) > MAX_ROWS:
        raise ToolError(f"Too many keywords ({len(kws)}); max {MAX_ROWS} per call.")
    brand_set = {b.lower().strip() for b in (brands or []) if b.strip()}
    rows, counts = [], Counter()
    for k in kws:
        intent, conf, why = _classify(k, brand_set)
        counts[intent] += 1
        rows.append({"keyword": k, "intent": intent, "confidence": conf, "signal": why})
    low_conf = [r["keyword"] for r in rows if r["confidence"] < 0.6]
    fmt = {"informational": "guide / how-to / listicle", "commercial": "comparison / roundup with verdict", "transactional": "product / category / landing page", "navigational": "none unless it is your brand", "local": "location page + Google Business Profile"}
    return {
        "rows": rows,
        "counts": dict(counts),
        "low_confidence": low_conf,
        "format_by_intent": fmt,
        "summary": f"{len(rows)} keywords: " + ", ".join(f"{n} {i}" for i, n in counts.most_common()) + (f"; {len(low_conf)} need judgement." if low_conf else "."),
    }


@AGENT.tool
def cluster_keywords(keywords: list[str], volumes: list[int] | None = None, min_similarity: float = 0.5, split_by_intent: bool = True) -> dict:
    """Group keywords that should share one page into clusters with a head term, split by intent.

    Stems and strips stopwords, then merges keywords whose token sets overlap at or above the
    similarity threshold (Jaccard, greedy by volume). The head term is the highest-volume (or
    shortest) member. Clusters mixing intents are split so each page has one intent.

    Args:
        keywords: The keywords to cluster (2-2000).
        volumes: Optional monthly search volumes aligned with keywords; used to pick head terms and order clusters.
        min_similarity: Jaccard threshold on stemmed tokens for joining a cluster (0.2-0.9; 0.5 default, lower = bigger clusters).
        split_by_intent: If true, a cluster containing several intents is split into one cluster per intent.
    """
    kws = [k.strip() for k in (keywords or []) if k and k.strip()]
    if len(kws) < 2:
        raise ToolError("Need at least 2 keywords to cluster.")
    if len(kws) > MAX_ROWS:
        raise ToolError(f"Too many keywords ({len(kws)}); max {MAX_ROWS}.")
    if not 0.2 <= min_similarity <= 0.9:
        raise ToolError("min_similarity must be between 0.2 and 0.9.")
    if volumes is not None and len(volumes) != len(keywords or []):
        raise ToolError("volumes must be the same length as keywords.")
    vol = {k: int(v) for k, v in zip(keywords or [], volumes or [])} if volumes else {}
    order = sorted(range(len(kws)), key=lambda i: (-vol.get(kws[i], 0), len(kws[i])))
    tok = {k: set(c.tokens(k)) or {k.lower()} for k in kws}
    clusters: list[dict] = []
    for i in order:
        k = kws[i]
        best, best_sim = None, 0.0
        for cl in clusters:
            sim = c.jaccard(tok[k], cl["core"])
            if sim > best_sim:
                best, best_sim = cl, sim
        if best is not None and best_sim >= min_similarity:
            best["members"].append(k)
            best["core"] = best["core"] & tok[k] if best["core"] & tok[k] else best["core"]
        else:
            clusters.append({"head": k, "members": [k], "core": set(tok[k])})
    if split_by_intent:
        out = []
        for cl in clusters:
            groups: dict[str, list[str]] = {}
            for m in cl["members"]:
                groups.setdefault(_classify(m, set())[0], []).append(m)
            if len(groups) == 1:
                out.append(cl)
            else:
                for intent, ms in groups.items():
                    out.append({"head": ms[0], "members": ms, "core": cl["core"], "split_from": cl["head"], "intent": intent})
        clusters = out
    result = []
    for cl in clusters:
        members = cl["members"]
        head = max(members, key=lambda m: (vol.get(m, 0), -len(m)))
        total = sum(vol.get(m, 0) for m in members)
        intent = cl.get("intent") or _classify(head, set())[0]
        result.append(
            {
                "head": head,
                "intent": intent,
                "size": len(members),
                "total_volume": total if vol else None,
                "core_tokens": sorted(cl["core"]),
                "members": sorted(members, key=lambda m: -vol.get(m, 0)),
                "split_from": cl.get("split_from"),
                "note": "thin cluster — consider folding into a broader guide" if len(members) < 3 and intent == "informational" else "",
            }
        )
    result.sort(key=lambda r: (-(r["total_volume"] or 0), -r["size"]))
    singletons = sum(1 for r in result if r["size"] == 1)
    return {
        "clusters": result,
        "cluster_count": len(result),
        "singletons": singletons,
        "pages_to_build": len(result),
        "summary": f"{len(kws)} keywords → {len(result)} clusters ({singletons} singletons). Threshold {min_similarity}; lower it if clusters look fragmented.",
    }


INTENT_WEIGHT = {"transactional": 1.4, "commercial": 1.2, "local": 1.2, "informational": 0.8, "navigational": 0.3}


@AGENT.tool
def score_opportunities(rows: list[dict], site_stage: str = "new", current_positions: dict[str, float] | None = None) -> dict:
    """Score keyword opportunity from volume, difficulty, CPC and intent, and flag quick wins and striking-distance terms.

    Score = log10(volume+10) × intent weight × (1 − KD/100)^k × (1 + min(CPC,10)/10), with k = 2 for new
    sites and 1 for established. Aggregates by cluster when rows carry a `cluster` field.

    Args:
        rows: List of {"keyword": str, "volume": int, "difficulty": 0-100, "cpc": float, "intent": str, "cluster": str}; only keyword is required.
        site_stage: "new" (DR < 40: difficulty punished hard) or "established".
        current_positions: Optional {keyword: current Google position} from Search Console; positions 8-20 are flagged striking distance.
    """
    if not rows:
        raise ToolError("rows is empty.")
    if len(rows) > MAX_ROWS:
        raise ToolError(f"Too many rows ({len(rows)}); max {MAX_ROWS}.")
    if site_stage not in ("new", "established"):
        raise ToolError("site_stage must be 'new' or 'established'.")
    k = 2 if site_stage == "new" else 1
    pos = {str(a).lower().strip(): float(b) for a, b in (current_positions or {}).items()}
    scored = []
    by_cluster: dict[str, dict] = {}
    for r in rows:
        kw = str(r.get("keyword", "")).strip()
        if not kw:
            raise ToolError("Every row needs a 'keyword'.")
        try:
            vol = max(0, int(r.get("volume") or 0))
            kd = float(r.get("difficulty")) if r.get("difficulty") is not None else None
            cpc = max(0.0, float(r.get("cpc") or 0))
        except (TypeError, ValueError):
            raise ToolError(f"Row {kw!r}: volume, difficulty and cpc must be numbers.") from None
        if kd is not None and not 0 <= kd <= 100:
            raise ToolError(f"Row {kw!r}: difficulty must be 0-100.")
        intent = str(r.get("intent") or _classify(kw, set())[0]).lower()
        w = INTENT_WEIGHT.get(intent, 0.8)
        kd_eff = 50.0 if kd is None else kd
        score = math.log10(vol + 10) * w * (1 - kd_eff / 100) ** k * (1 + min(cpc, 10) / 10)
        score = round(score * 25, 1)  # 0-~100 scale
        p = pos.get(kw.lower())
        flags = []
        if kd is not None and kd <= 30 and vol >= 100:
            flags.append("quick_win")
        if kd is not None and kd >= (60 if site_stage == "new" else 80):
            flags.append("long_term")
        if p is not None and 8 <= p <= 20:
            flags.append("striking_distance")
            score = round(score * 1.5, 1)
        if vol == 0:
            flags.append("zero_volume_reported")
        item = {"keyword": kw, "volume": vol, "difficulty": kd, "cpc": cpc, "intent": intent, "position": p, "score": score, "flags": flags}
        scored.append(item)
        cl = str(r.get("cluster") or "").strip()
        if cl:
            agg = by_cluster.setdefault(cl, {"cluster": cl, "keywords": 0, "volume": 0, "score": 0.0, "best": None})
            agg["keywords"] += 1
            agg["volume"] += vol
            agg["score"] += score
            if agg["best"] is None or score > agg["best"]["score"]:
                agg["best"] = {"keyword": kw, "score": score}
    scored.sort(key=lambda s: -s["score"])
    clusters = sorted(by_cluster.values(), key=lambda a: -a["score"])
    for a in clusters:
        a["score"] = round(a["score"], 1)
    quick = [s["keyword"] for s in scored if "quick_win" in s["flags"]]
    striking = [s["keyword"] for s in scored if "striking_distance" in s["flags"]]
    return {
        "site_stage": site_stage,
        "ranked": scored,
        "clusters": clusters,
        "quick_wins": quick,
        "striking_distance": striking,
        "long_term": [s["keyword"] for s in scored if "long_term" in s["flags"]],
        "summary": f"Top: '{scored[0]['keyword']}' ({scored[0]['score']}). {len(quick)} quick wins, {len(striking)} striking-distance terms. Striking distance first, then quick wins.",
    }


@AGENT.tool
def keyword_gap(ours: list[str], competitors: dict[str, list[str]]) -> dict:
    """Find keywords competitors rank for that you do not, weighted by how many competitors share them.

    Normalises keywords (case, stems) so 'crm software' and 'CRM softwares' match. Returns the gap
    sorted by competitor count, keywords unique to you, and overlap ratios per competitor.

    Args:
        ours: Keywords your site currently ranks for.
        competitors: {"competitor name": [their keywords]} — 1 to 10 competitors, up to 2000 keywords each.
    """
    if not competitors:
        raise ToolError("competitors is empty — pass at least one competitor's keyword list.")
    if len(competitors) > 10:
        raise ToolError("Max 10 competitors per call.")

    def norm(k: str) -> str:
        return " ".join(c.tokens(k, keep_stop=True))

    ours_map = {norm(k): k for k in ours if k.strip()}
    comp_maps: dict[str, dict[str, str]] = {}
    for name, kws in competitors.items():
        if len(kws) > MAX_ROWS:
            raise ToolError(f"Competitor {name!r} has too many keywords (max {MAX_ROWS}).")
        comp_maps[name] = {norm(k): k for k in kws if k and k.strip()}
    gap: dict[str, list[str]] = {}
    for name, m in comp_maps.items():
        for n in m:
            if n and n not in ours_map:
                gap.setdefault(n, []).append(name)
    all_comp = set().union(*[set(m) for m in comp_maps.values()])
    unique_to_us = [ours_map[n] for n in ours_map if n not in all_comp]
    gap_rows = []
    for n, names in gap.items():
        display = next(m[n] for m in comp_maps.values() if n in m)
        gap_rows.append({"keyword": display, "competitors": sorted(names), "competitor_count": len(names), "intent": _classify(display, set())[0]})
    gap_rows.sort(key=lambda r: (-r["competitor_count"], r["keyword"]))
    overlap = {name: {"shared": sum(1 for n in m if n in ours_map), "theirs": len(m), "overlap_pct": round(100 * sum(1 for n in m if n in ours_map) / max(1, len(m)), 1)} for name, m in comp_maps.items()}
    shared_by_2 = [r for r in gap_rows if r["competitor_count"] >= 2]
    return {
        "gap": gap_rows[:500],
        "gap_count": len(gap_rows),
        "high_confidence_gap": [r["keyword"] for r in shared_by_2[:50]],
        "unique_to_us": unique_to_us[:200],
        "overlap": overlap,
        "summary": f"{len(gap_rows)} keywords competitors rank for that you don't; {len(shared_by_2)} are shared by 2+ competitors (proven SERPs — target first).",
    }
