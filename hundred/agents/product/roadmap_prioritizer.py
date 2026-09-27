"""Roadmap Prioritizer — RICE, Kano, opportunity scoring and capacity-checked MoSCoW for real roadmaps."""

from __future__ import annotations

from collections import Counter

from ...core import Agent, ToolError
from ._common import check_rows, pct, to_float

AGENT = Agent(
    slug="roadmap-prioritizer",
    name="Roadmap Prioritizer",
    category="product",
    tagline="Rank your backlog with RICE, Kano, and opportunity scores — then check the plan actually fits capacity.",
    description=(
        "Prioritises like a head of product: scores initiatives with RICE (with confidence discounting "
        "and effort sanity checks), classifies features with the full Kano evaluation table from survey "
        "pairs, computes Ulwick opportunity scores from importance/satisfaction data, and stress-tests a "
        "MoSCoW plan against real team capacity so 'Must' never exceeds 60%. Outputs a ranked roadmap "
        "with the reasoning stakeholders can argue with — and a sensitivity check showing which ranks are fragile."
    ),
    triggers=[
        "prioritise my roadmap / backlog",
        "RICE score these features",
        "Kano analysis of survey results",
        "what should we build next quarter",
        "does this MoSCoW plan fit our capacity",
        "opportunity scoring / importance vs satisfaction",
    ],
    examples=[
        "Here are 14 candidate features with reach, impact, confidence and effort — rank them with RICE.",
        "We ran a Kano survey on 6 features (functional/dysfunctional answers per respondent). Classify each.",
        "We have 3 engineers for a 6-week cycle; here's our Must/Should/Could list with estimates — does it fit?",
    ],
    connectors=["Linear", "Jira", "Productboard", "Notion", "Google Sheets", "Airtable"],
    playbook="""
    ## Standard
    You are a head of product who ships the *right* things. Excellent prioritisation is transparent
    (anyone can see why #1 beats #2), honest about uncertainty (confidence is a discount, not a
    vibe), and capacity-bound (a ranked list that doesn't fit the quarter is a wish list). The one
    metric that matters is **value shipped per engineering-week** — so every ranking is
    per-unit-of-effort, and you always show what got cut and why.

    ## Intake
    Proceed with what you have. Ask (max 3) only if you cannot infer: (1) the planning horizon and
    team capacity (people × weeks), (2) the strategic goal this cycle serves (one sentence), (3) a
    common unit for reach (users/month, accounts, transactions). Missing estimates → make a
    conservative assumption, label it, continue.

    ## Procedure
    1. **Normalise the inputs.** Reach in the same unit per quarter; impact on the 0.25/0.5/1/2/3
       scale (minimal/low/medium/high/massive); confidence as 100/80/50% (never higher than 80%
       without data, never below 50% — below 50% is a research task, not a roadmap item); effort in
       person-weeks.
    2. **Score.** Call `roadmap_prioritizer__rice_score` with the list. It computes RICE =
       (Reach × Impact × Confidence) / Effort, ranks, and flags: confidence < 50% (should be a
       spike), effort < 0.5 weeks (bundle it), and any item whose rank would flip if its estimate
       were 30% off (fragile ranks). Show fragile ranks as ties, not false precision.
    3. **If you have survey data** (functional/dysfunctional answers), call
       `roadmap_prioritizer__kano_classify`. It applies the Kano evaluation table per respondent,
       gives the category by majority, the Better/Worse coefficients (Berger et al.), and flags
       Questionable/Reverse answers. Must-be features go first (absence kills), Performance next
       (proportional value), Attractive for differentiation, Indifferent → cut.
    3b. **If deadlines or experiments drive the backlog**, call `roadmap_prioritizer__wsjf_ice_score`:
       method "wsjf" (SAFe: cost of delay = business value + time criticality + risk reduction,
       ÷ job size, all on the 1-2-3-5-8-13-20 relative scale) for time-sensitive work, or "ice"
       (impact × confidence × ease, 1-10 each) for growth-experiment triage. Use it alongside RICE,
       not instead of it, and say which items change rank between the two.
    4. **If you have importance/satisfaction ratings** (JTBD outcome surveys), call
       `roadmap_prioritizer__opportunity_score`. Opportunity = Importance + max(Importance −
       Satisfaction, 0) on a 1-10 scale: > 15 is a top opportunity, 12-15 worth pursuing, < 10
       over-served — consider cutting investment.
    5. **Fit to capacity.** Call `roadmap_prioritizer__capacity_check` with the ranked items, their
       MoSCoW labels and effort, plus capacity. It applies the DSDM rule (Must ≤ 60% of capacity,
       Must + Should ≤ 80%, ≥ 20% contingency), shows the cut line, and lists what falls below it.
       If Must exceeds 60%, demote items — do not shrink estimates.
    6. **Reconcile.** Where RICE, Kano and strategy disagree, strategy wins, then Kano must-bes,
       then RICE. Say explicitly which items were moved by judgement and why.
    7. **Write the roadmap** in the output format: ranked table, cut line, what's below it, the
       fragile ranks, and the three assumptions that would change the answer most.
    8. If Linear/Jira/Productboard is connected, update priorities/labels; otherwise output to paste.

    ## Frameworks
    - **RICE (Intercom):** Reach (per quarter) × Impact (0.25-3) × Confidence (0.5-1.0) ÷ Effort
      (person-weeks). Use it for comparable, well-understood items.
    - **Kano evaluation table:** each (functional, dysfunctional) answer pair maps to
      Must-be / One-dimensional (Performance) / Attractive / Indifferent / Reverse / Questionable.
      Better = (A+O)/(A+O+M+I); Worse = −(O+M)/(A+O+M+I).
    - **Opportunity scoring (Ulwick):** Imp + max(Imp − Sat, 0). Sort by score; the top quartile is
      where under-served needs live.
    - **MoSCoW / DSDM:** Must ≤ 60% effort; Should + Could is your contingency. A plan with 90% Must
      has no prioritisation and will slip.
    - **Cost of delay:** for time-sensitive items (compliance dates, seasonal), override RICE and note it.

    ## Output format
    ```
    # Roadmap — <cycle> (<capacity> person-weeks, goal: <one sentence>)
    ## Ranked
    | Rank | Item | RICE | Kano | MoSCoW | Effort | Cum. effort | Note |
    |---|---|---|---|---|---|---|---|
    — cut line at <N> person-weeks (Must 55%, Should 25%, contingency 20%) —
    | … below the line … |

    ## Why this order
    - #1 over #2 because …  · Fragile: #4/#5 are within estimate error — treat as a tie.
    ## Moved by judgement
    - <item>: RICE rank 7 → 2 (compliance deadline 2026-11-30)
    ## Assumptions that would change the answer
    1. …  2. …  3. …
    ## Cut this cycle (and where it goes)
    - <item> → next cycle / needs research spike / kill
    ```

    ## Anti-patterns
    - Confidence of 90-100% on things nobody has validated. Confidence is your discount for ignorance.
    - Ranking by RICE score to two decimals. Estimates are ±30%; show ties.
    - "Everything is a Must." If Must > 60% of capacity the plan is fiction.
    - Ignoring effort < 0.5 weeks items — bundle quick wins into a single line so they don't dominate the rank.
    - Treating Kano "Attractive" as more important than "Must-be". Absence of a must-be loses customers; absence of a delighter loses nothing.
    - Not showing the cut line. The value of prioritisation is in what you say no to.
    """,
)

IMPACT_SCALE = {"minimal": 0.25, "low": 0.5, "medium": 1.0, "high": 2.0, "massive": 3.0}


def _impact(v) -> float:
    if isinstance(v, str) and v.strip().lower() in IMPACT_SCALE:
        return IMPACT_SCALE[v.strip().lower()]
    return to_float(v, "impact", 0.05, 10)


def _confidence(v) -> float:
    c = to_float(v, "confidence", 0, 100)
    return c / 100 if c > 1 else c


@AGENT.tool
def rice_score(items: list[dict], fragility_pct: float = 30.0) -> dict:
    """Compute RICE = Reach × Impact × Confidence ÷ Effort, rank, and flag fragile ranks and bad inputs.

    Args:
        items: List of {"name": str, "reach": number per quarter, "impact": 0.25|0.5|1|2|3 or
            minimal|low|medium|high|massive, "confidence": 0-1 or 0-100, "effort": person-weeks}.
        fragility_pct: Estimate error to test rank stability against (default 30%).
    """
    rows = check_rows(items, "items")
    err = to_float(fragility_pct, "fragility_pct", 0, 90) / 100
    scored = []
    for i, raw in enumerate(rows):
        if not isinstance(raw, dict) or not str(raw.get("name", "")).strip():
            raise ToolError(f"items[{i}] needs a 'name' plus reach/impact/confidence/effort.")
        reach = to_float(raw.get("reach"), f"{raw['name']}: reach", 0)
        impact = _impact(raw.get("impact"))
        conf = _confidence(raw.get("confidence"))
        effort = to_float(raw.get("effort"), f"{raw['name']}: effort", 0.01)
        score = reach * impact * conf / effort
        flags = []
        if conf < 0.5:
            flags.append("confidence < 50% — this is a research spike, not a roadmap item")
        if conf > 0.8 and not raw.get("evidence"):
            flags.append("confidence > 80% with no evidence field — justify or set to 80%")
        if effort < 0.5:
            flags.append("effort < 0.5 weeks — bundle with other quick wins")
        scored.append({"name": str(raw["name"]).strip(), "reach": reach, "impact": impact, "confidence": conf, "effort": effort, "rice": round(score, 1), "flags": flags})
    scored.sort(key=lambda r: -r["rice"])
    for rank, r in enumerate(scored, 1):
        r["rank"] = rank
    # fragility: would rank change if this item's score moved by ±err?
    for idx, r in enumerate(scored):
        lo, hi = r["rice"] * (1 - err), r["rice"] * (1 + err)
        neighbours = []
        if idx > 0 and scored[idx - 1]["rice"] <= hi:
            neighbours.append(scored[idx - 1]["name"])
        if idx + 1 < len(scored) and scored[idx + 1]["rice"] >= lo:
            neighbours.append(scored[idx + 1]["name"])
        r["fragile_with"] = neighbours
    total_effort = sum(r["effort"] for r in scored)
    fragile = [r["name"] for r in scored if r["fragile_with"]]
    # tiers: consecutive items whose ranks could swap within the estimate error are one tie group
    tiers: list[list[str]] = []
    for idx, r in enumerate(scored):
        if idx > 0 and scored[idx - 1]["name"] in r["fragile_with"]:
            tiers[-1].append(r["name"])
        else:
            tiers.append([r["name"]])
    for r in scored:
        r["tier"] = next(t for t, grp in enumerate(tiers, 1) if r["name"] in grp)
    return {
        "ranked": scored,
        "tiers": tiers,
        "total_effort_weeks": round(total_effort, 1),
        "fragile_ranks": fragile,
        "flagged": [r["name"] for r in scored if r["flags"]],
        "summary": f"#1 {scored[0]['name']} (RICE {scored[0]['rice']}); {len(fragile)} rank(s) within ±{int(err * 100)}% estimate error — present the {len(tiers)} tiers, not {len(scored)} ranks.",
    }


# Kano evaluation table: rows = functional answer, cols = dysfunctional answer
_KANO_ANS = {"like": 0, "must-be": 1, "must be": 1, "expect": 1, "neutral": 2, "live-with": 3, "live with": 3, "tolerate": 3, "dislike": 4}
_KANO_TABLE = [
    # dys:   like   must  neutral  live   dislike
    ["Q", "A", "A", "A", "O"],   # func = like
    ["R", "I", "I", "I", "M"],   # func = must-be
    ["R", "I", "I", "I", "M"],   # func = neutral
    ["R", "I", "I", "I", "M"],   # func = live-with
    ["R", "R", "R", "R", "Q"],   # func = dislike
]
_KANO_NAMES = {"M": "Must-be", "O": "One-dimensional (Performance)", "A": "Attractive", "I": "Indifferent", "R": "Reverse", "Q": "Questionable"}
_KANO_ORDER = {"M": 0, "O": 1, "A": 2, "I": 3, "R": 4, "Q": 5}


def _kano_code(ans) -> int:
    if isinstance(ans, int) and 1 <= ans <= 5:
        return ans - 1
    key = str(ans).strip().lower()
    if key not in _KANO_ANS:
        raise ToolError(f"Kano answer {ans!r} must be one of like / must-be / neutral / live-with / dislike (or 1-5).")
    return _KANO_ANS[key]


@AGENT.tool
def kano_classify(features: list[dict]) -> dict:
    """Classify features from Kano survey pairs using the standard evaluation table + Better/Worse coefficients.

    Args:
        features: List of {"name": str, "responses": [{"functional": "like|must-be|neutral|live-with|dislike",
            "dysfunctional": same}, ...]}. Answers may also be 1-5 in that order.
    """
    rows = check_rows(features, "features")
    out = []
    for i, raw in enumerate(rows):
        if not isinstance(raw, dict) or not str(raw.get("name", "")).strip():
            raise ToolError(f"features[{i}] needs a 'name' and 'responses'.")
        responses = raw.get("responses") or []
        if not isinstance(responses, list) or not responses:
            raise ToolError(f"{raw['name']}: responses must be a non-empty list of functional/dysfunctional pairs.")
        counts: Counter = Counter()
        for r in responses[:2000]:
            if not isinstance(r, dict):
                raise ToolError(f"{raw['name']}: each response must be an object with functional and dysfunctional.")
            counts[_KANO_TABLE[_kano_code(r.get("functional"))][_kano_code(r.get("dysfunctional"))]] += 1
        n = sum(counts.values())
        a, o, m, ind = counts["A"], counts["O"], counts["M"], counts["I"]
        denom = a + o + m + ind
        better = round(pct(a + o, denom) / 100, 2) if denom else None
        worse = (round(-pct(o + m, denom) / 100, 2) + 0.0) if denom else None  # + 0.0 avoids "-0.0"
        # majority category among valid ones, ties broken by M > O > A > I
        valid = [(c, counts[c]) for c in "MOAI" if counts[c]]
        if valid:
            top = max(valid, key=lambda kv: (kv[1], -_KANO_ORDER[kv[0]]))
            category = top[0]
            clear = top[1] / max(1, denom) >= 0.5
        else:
            category, clear = ("Q" if counts["Q"] >= counts["R"] else "R"), False
        notes = []
        if counts["Q"] / n > 0.1:
            notes.append(f"{pct(counts['Q'], n)}% questionable answers — check question wording")
        if counts["R"] / n > 0.2:
            notes.append(f"{pct(counts['R'], n)}% reverse — some users don't want this; consider making it optional")
        if not clear and valid:
            notes.append("no majority category — mixed segments; split respondents before deciding")
        out.append({
            "name": str(raw["name"]).strip(),
            "category": _KANO_NAMES[category],
            "code": category,
            "respondents": n,
            "counts": {_KANO_NAMES[k]: counts[k] for k in "MOAIRQ"},
            "better": better,
            "worse": worse,
            "clear_majority": clear,
            "notes": notes,
        })
    out.sort(key=lambda f: (_KANO_ORDER[f["code"]], -(f["better"] or 0)))
    return {
        "features": out,
        "build_order": [f["name"] for f in out if f["code"] in "MOA"],
        "cut_candidates": [f["name"] for f in out if f["code"] in "IR"],
        "summary": "; ".join(f"{f['name']}: {f['category']}" for f in out),
    }


_FIB = (1, 2, 3, 5, 8, 13, 20, 40, 100)


@AGENT.tool
def wsjf_ice_score(items: list[dict], method: str = "wsjf") -> dict:
    """Score items with WSJF (SAFe cost of delay ÷ job size) or ICE (Impact × Confidence × Ease) and rank them.

    Use WSJF when time matters (deadlines, compliance, decaying opportunities); use ICE for quick
    growth-experiment triage. Both are the formulas Productboard/SAFe document.

    Args:
        items: For "wsjf": [{"name", "business_value", "time_criticality", "risk_reduction", "job_size"}] on the
            modified Fibonacci scale 1,2,3,5,8,13,20 (relative, smallest item = 1). For "ice":
            [{"name", "impact", "confidence", "ease"}] each 1-10.
        method: "wsjf" (default) or "ice".
    """
    rows = check_rows(items, "items")
    m = str(method).strip().lower()
    if m not in {"wsjf", "ice"}:
        raise ToolError("method must be 'wsjf' or 'ice'.")
    out = []
    for i, raw in enumerate(rows):
        if not isinstance(raw, dict) or not str(raw.get("name", "")).strip():
            raise ToolError(f"items[{i}] needs a 'name'.")
        name = str(raw["name"]).strip()
        notes = []
        if m == "wsjf":
            bv, tc, rr = (to_float(raw.get(k), f"{name}: {k}", 0, 100) for k in ("business_value", "time_criticality", "risk_reduction"))
            size = to_float(raw.get("job_size"), f"{name}: job_size", 0.5, 100)
            off = [k for k, v in (("business_value", bv), ("time_criticality", tc), ("risk_reduction", rr), ("job_size", size)) if v not in _FIB]
            if off:
                notes.append(f"not on the 1-2-3-5-8-13-20 scale: {', '.join(off)} — WSJF inputs are relative Fibonacci estimates")
            cod = bv + tc + rr
            score = cod / size
            out.append({"name": name, "cost_of_delay": round(cod, 1), "job_size": size, "score": round(score, 2), "notes": notes})
        else:
            imp, conf, ease = (to_float(raw.get(k), f"{name}: {k}", 1, 10) for k in ("impact", "confidence", "ease"))
            score = imp * conf * ease
            if conf >= 9:
                notes.append("confidence ≥ 9/10 — only with shipped evidence")
            out.append({"name": name, "impact": imp, "confidence": conf, "ease": ease, "score": round(score, 1), "notes": notes})
    out.sort(key=lambda r: -r["score"])
    for rank, r in enumerate(out, 1):
        r["rank"] = rank
    formula = "WSJF = (business value + time criticality + risk reduction) ÷ job size" if m == "wsjf" else "ICE = impact × confidence × ease (1-10 each, max 1000)"
    return {"method": m, "formula": formula, "ranked": out, "summary": f"#1 {out[0]['name']} ({m.upper()} {out[0]['score']}) — {formula}"}


@AGENT.tool
def opportunity_score(outcomes: list[dict]) -> dict:
    """Ulwick opportunity score: Importance + max(Importance − Satisfaction, 0), on a 1-10 scale.

    Args:
        outcomes: List of {"outcome": str, "importance": 1-10, "satisfaction": 1-10} (means from survey).
    """
    rows = check_rows(outcomes, "outcomes")
    out = []
    for i, raw in enumerate(rows):
        if not isinstance(raw, dict) or not str(raw.get("outcome", "")).strip():
            raise ToolError(f"outcomes[{i}] needs 'outcome', 'importance' and 'satisfaction'.")
        imp = to_float(raw.get("importance"), "importance", 1, 10)
        sat = to_float(raw.get("satisfaction"), "satisfaction", 1, 10)
        score = imp + max(imp - sat, 0)
        band = "top opportunity (>15)" if score > 15 else "worth pursuing (12-15)" if score >= 12 else "adequately served (10-12)" if score >= 10 else "over-served (<10) — reduce investment"
        out.append({"outcome": str(raw["outcome"]).strip(), "importance": imp, "satisfaction": sat, "opportunity": round(score, 1), "band": band})
    out.sort(key=lambda r: -r["opportunity"])
    for rank, r in enumerate(out, 1):
        r["rank"] = rank
    return {"ranked": out, "top": [r["outcome"] for r in out if r["opportunity"] > 15], "summary": f"#1 {out[0]['outcome']} ({out[0]['opportunity']})"}


@AGENT.tool
def capacity_check(items: list[dict], capacity_weeks: float, must_max_pct: float = 60.0, contingency_pct: float = 20.0) -> dict:
    """Check a ranked MoSCoW plan against team capacity: Must ≤ 60%, cut line, and what falls below it.

    Args:
        items: Ranked list of {"name": str, "moscow": "must|should|could|wont", "effort": person-weeks}.
        capacity_weeks: Total person-weeks available this cycle (people × weeks × focus factor).
        must_max_pct: Maximum share of capacity Must items may take (DSDM default 60).
        contingency_pct: Share of capacity to keep unplanned (default 20).
    """
    rows = check_rows(items, "items")
    cap = to_float(capacity_weeks, "capacity_weeks", 0.1)
    must_max = to_float(must_max_pct, "must_max_pct", 10, 100) / 100
    contingency = to_float(contingency_pct, "contingency_pct", 0, 50) / 100
    plannable = cap * (1 - contingency)
    by_cat: Counter = Counter()
    cum, cut_line_after, table = 0.0, None, []
    for i, raw in enumerate(rows):
        if not isinstance(raw, dict) or not str(raw.get("name", "")).strip():
            raise ToolError(f"items[{i}] needs 'name', 'moscow' and 'effort'.")
        cat = str(raw.get("moscow", "")).strip().lower().replace("'", "").replace("’", "")
        cat = {"m": "must", "s": "should", "c": "could", "w": "wont", "won't": "wont", "wont have": "wont"}.get(cat, cat)
        if cat not in {"must", "should", "could", "wont"}:
            raise ToolError(f"{raw['name']}: moscow must be must/should/could/wont, got {raw.get('moscow')!r}.")
        effort = to_float(raw.get("effort"), f"{raw['name']}: effort", 0)
        if cat != "wont":
            by_cat[cat] += effort
        fits = cat != "wont" and cum + effort <= plannable
        if cat != "wont":
            cum += effort
        if not fits and cut_line_after is None and cat != "wont":
            cut_line_after = i
        table.append({"rank": i + 1, "name": str(raw["name"]).strip(), "moscow": cat, "effort": effort, "cumulative": round(cum, 1) if cat != "wont" else None, "fits": fits})
    must_share = by_cat["must"] / cap
    planned = by_cat["must"] + by_cat["should"] + by_cat["could"]
    problems = []
    if must_share > must_max:
        problems.append(f"Must = {pct(by_cat['must'], cap)}% of capacity (limit {int(must_max * 100)}%) — demote {round(by_cat['must'] - cap * must_max, 1)} weeks of Must to Should")
    if (by_cat["must"] + by_cat["should"]) / cap > 0.8:
        problems.append(f"Must+Should = {pct(by_cat['must'] + by_cat['should'], cap)}% — over the 80% guideline")
    notes = []
    committed = by_cat["must"] + by_cat["should"]
    if committed > plannable:
        problems.append(f"Planned {round(planned, 1)} weeks > plannable {round(plannable, 1)} (after {int(contingency * 100)}% contingency) — cut {round(planned - plannable, 1)} weeks")
    elif planned > plannable:
        # DSDM: Could items ARE the contingency — overflowing Coulds is expected, not a failed plan
        coulds = [t["name"] for t in table if t["moscow"] == "could" and not t["fits"]]
        notes.append(f"Must+Should fit; Could items {', '.join(coulds)} sit in the contingency — ship them only if the cycle runs clean")
    return {
        "capacity_weeks": cap,
        "plannable_weeks": round(plannable, 1),
        "effort_by_category": {k: round(v, 1) for k, v in by_cat.items()},
        "must_pct_of_capacity": pct(by_cat["must"], cap),
        "items": table,
        "cut_line_after_rank": cut_line_after if cut_line_after is None else cut_line_after,
        "below_the_line": [t["name"] for t in table if not t["fits"] and t["moscow"] != "wont"],
        "problems": problems,
        "notes": notes,
        "verdict": ("Plan fits with contingency" + (" (Coulds are the buffer)" if notes else "")) if not problems else "Plan does not fit — " + problems[0],
    }
