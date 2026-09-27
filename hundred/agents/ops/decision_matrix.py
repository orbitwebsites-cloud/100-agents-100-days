"""Decision Matrix — weighted scoring, sensitivity, expected value and AHP weights for decisions that matter."""

from __future__ import annotations

import math
from itertools import combinations

from ...core import Agent, ToolError
from ._common import as_float, as_str, md_table, require_list

AGENT = Agent(
    slug="decision-matrix",
    name="Decision Matrix",
    category="ops",
    tagline="Make the big call with weighted scoring, expected value and a sensitivity check that shows how robust the winner is.",
    description=(
        "Runs a structured decision the way a strategy consultant or staff engineer would: clarifies the "
        "options and criteria, derives weights (including AHP pairwise comparison with a consistency check), "
        "scores on a normalised scale, computes expected value with regret for uncertain outcomes, and "
        "stress-tests the winner — which weight or score change would flip it. You get a recommendation "
        "with its fragility stated, not a table that flatters a foregone conclusion."
    ),
    triggers=[
        "help me decide between these options",
        "build a decision matrix / weighted scoring",
        "should we do A or B",
        "expected value of these scenarios",
        "how sensitive is this decision to the weights",
        "compare vendors / tools / job offers / cities objectively",
    ],
    examples=[
        "Help me choose between three job offers — comp, growth, commute, team, and I care most about growth.",
        "Should we build or buy the billing system? Here are the costs and probabilities of each scenario.",
        "We scored four cloud providers on 6 criteria; tell me how robust the winner is.",
        "I keep going back and forth on moving to Austin vs staying in NYC. Structure this.",
    ],
    connectors=["Notion", "Google Sheets", "Google Docs", "Slack", "Confluence"],
    playbook="""
    ## Standard
    You are a decision analyst. An excellent decision memo is one the user could hand to a
    sceptical board member: the criteria are the real drivers, the weights were chosen before
    the scores, the winner's margin and fragility are explicit, and the reversible/irreversible
    nature of the choice is named. The one metric: **would the recommendation survive the
    user changing their mind about one weight by 10 points?** If not, say so — that is the answer.

    ## Intake
    You need: the options (2-8), what the user is optimising for, and any hard constraints.
    Ask at most 2 questions, only if the options or the goal are missing. If criteria or
    weights are missing, propose 4-7 criteria yourself (MECE: no overlaps like "cost" and
    "price"), propose weights, state them as assumptions, and proceed. Separate constraints
    (must-haves: pass/fail) from criteria (better/worse) before scoring anything.

    ## Procedure
    1. **Frame.** Write the decision in one sentence ("Which X should we choose to achieve Y
       by Z?"). Classify it: reversible (two-way door — decide fast, 70% information) or
       irreversible (one-way door — slow down, full analysis). Note the default: what
       happens if no decision is made.
    2. **Knock out.** Apply must-have constraints first. An option that fails one is out
       regardless of score; say which constraint killed it.
    3. **Weights before scores.** If the user has a clear ranking of criteria, convert it
       to weights (rank-sum or 100-point split). If they are unsure, run
       `decision_matrix__pairwise_weights` with pairwise comparisons ("how much more does
       growth matter than commute? 3×"); it returns weights and a consistency ratio — if
       CR > 0.10, the judgements contradict each other: show the worst triad and ask them
       to re-judge that one pair. Lock weights before looking at scores (anchoring).
    4. **Score** each option on each criterion 1-5 (or paste raw numbers like cost and
       mark the criterion `normalise: true`, `direction: "lower"`). Write a one-line
       justification per cell. Call `decision_matrix__weighted_score`. Report totals,
       margin, per-criterion winners and any dominated option.
    5. **Stress-test.** Always call `decision_matrix__sensitivity_check` on the same
       inputs. Report: which criterion's weight would flip the winner and by how much;
       the smallest single score change that flips it; and whether equal weights give the
       same winner. Margin < 5 points on a 100 scale or a flip within ±10 weight points
       = "close call" — then recommend the reversible option or gathering one specific
       piece of information.
    6. **Under uncertainty** (outcomes depend on things you don't control), model each
       option as scenarios with probabilities and payoffs and call
       `decision_matrix__expected_value`. Report EV, downside (worst case, probability of
       loss), and max regret. Prefer the higher-EV option unless the worst case is
       unsurvivable — then minimise regret.
    7. **Pre-mortem.** One paragraph: "It's a year later and this choice failed. Why?"
       Add the top mitigation to the recommendation.
    8. **Recommend.** One option, one sentence, with the margin and the fragility. Then
       the next concrete action and the date to revisit.

    ## Frameworks
    - **Weighted scoring (SMART / Kepner-Tregoe)**: constraints → criteria → weights →
      scores → sensitivity. Never skip the last step.
    - **AHP pairwise (Saaty)**: 1 = equal, 3 = moderate, 5 = strong, 7 = very strong,
      9 = extreme. Consistency ratio ≤ 0.10 is acceptable.
    - **Expected value**: EV = Σ p × payoff. Use only when probabilities are defensible;
      otherwise use scenario ranges and minimax regret.
    - **One-way vs two-way doors (Bezos)**; **70% rule**: for reversible decisions, decide
      with ~70% of the information you wish you had.
    - **WRAP (Heath)**: Widen options (never a binary; add "do nothing" and "do both
      small"), Reality-test assumptions, Attain distance (10/10/10: how will you feel in
      10 minutes / 10 months / 10 years), Prepare to be wrong (tripwires).

    ## Output format
    ```
    # Decision: <one sentence>
    **Type:** reversible / irreversible · **Default if no decision:** <…> · **Decide by:** <date>

    ## Constraints (pass/fail)
    | Option | <must-have 1> | <must-have 2> | In? |

    ## Scoring (weights locked before scoring)
    | Criterion (weight) | Option A | Option B | Option C |
    |---|---|---|---|
    | … | 4 — <why> | 2 — <why> | 5 — <why> |
    | **Total /100** | **72** | **61** | **74** |

    ## Robustness
    Margin: X pts. Flips if <criterion> weight moves from W to W' (Δ ±N). Equal weights: <same/different winner>.
    Verdict: robust / close call.

    ## Recommendation
    <Option> — because <the two criteria that decided it>. Fragility: <…>.
    Pre-mortem risk: <…> → mitigation: <…>. Revisit on <date> if <tripwire>.
    ```

    ## Anti-patterns
    - Scoring first, then tuning weights until the favourite wins. Lock weights first and
      say so in the memo.
    - Ten criteria, half of them overlapping. Overlap double-counts; keep 4-7 MECE criteria.
    - A matrix with no sensitivity check. A 74-vs-72 "winner" is a coin flip; report it as one.
    - Treating a must-have as a weighted criterion. Constraints are pass/fail, applied first.
    - Doing arithmetic by hand. Weighted sums and normalisations go through the tools.
    - Hiding the default option. "Do nothing" is always on the list, with its own score.
    - Presenting EV without the downside. A +$2M EV with a 30% chance of bankruptcy is not
      a good bet for a company that can't survive it.
    """,
)

_RI = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49, 11: 1.51, 12: 1.48, 13: 1.56, 14: 1.57, 15: 1.59}


def _prep(options: list, criteria: list, scale_max: float) -> tuple[list[dict], list[dict], list[list[float]]]:
    """Validate and return (options, criteria, matrix of normalised scores on 0..scale_max)."""
    options = require_list(options, "options", 30, min_len=2)
    criteria = require_list(criteria, "criteria", 25)
    if not (1 <= scale_max <= 100):
        raise ToolError("scale_max must be between 1 and 100.")
    crit = []
    for i, c in enumerate(criteria, 1):
        if isinstance(c, str):
            c = {"name": c, "weight": 1}
        if not isinstance(c, dict):
            raise ToolError(f"criteria[{i}] must be {{'name', 'weight', 'direction', 'normalise'}}.")
        name = as_str(c.get("name"), f"criteria[{i}].name", max_len=80)
        w = as_float(c.get("weight", 1), f"criteria[{i}].weight", lo=0)
        direction = str(c.get("direction", "higher")).lower()
        if direction not in ("higher", "lower"):
            raise ToolError(f"criteria[{i}].direction must be 'higher' or 'lower'.")
        crit.append({"name": name, "weight": w, "direction": direction, "normalise": bool(c.get("normalise", False))})
    if sum(c["weight"] for c in crit) <= 0:
        raise ToolError("At least one criterion needs a positive weight.")
    names = [c["name"] for c in crit]
    if len(set(n.lower() for n in names)) != len(names):
        raise ToolError("Criteria names must be unique.")
    opts, raw = [], []
    for i, o in enumerate(options, 1):
        if not isinstance(o, dict):
            raise ToolError(f"options[{i}] must be {{'name', 'scores': {{criterion: value}}}}.")
        oname = as_str(o.get("name"), f"options[{i}].name", max_len=80)
        scores = o.get("scores")
        if not isinstance(scores, dict):
            raise ToolError(f"options[{i}] ({oname}) needs a 'scores' object keyed by criterion name.")
        lower = {str(k).lower(): v for k, v in scores.items()}
        row = []
        for c in crit:
            if c["name"].lower() not in lower:
                raise ToolError(f"Option {oname!r} has no score for criterion {c['name']!r}.")
            v = as_float(lower[c["name"].lower()], f"{oname}.{c['name']}")
            if not c["normalise"] and not (0 <= v <= scale_max):
                raise ToolError(f"{oname}.{c['name']} = {v} is outside 0..{scale_max}. Use normalise: true for raw numbers.")
            row.append(v)
        opts.append({"name": oname})
        raw.append(row)
    if len(set(o["name"].lower() for o in opts)) != len(opts):
        raise ToolError("Option names must be unique.")
    # normalise columns
    matrix = [r[:] for r in raw]
    for j, c in enumerate(crit):
        col = [r[j] for r in raw]
        if c["normalise"]:
            lo, hi = min(col), max(col)
            for i, v in enumerate(col):
                matrix[i][j] = scale_max if hi == lo else (v - lo) / (hi - lo) * scale_max
        if c["direction"] == "lower":
            for i in range(len(col)):
                matrix[i][j] = scale_max - matrix[i][j]
    return opts, crit, matrix


def _totals(crit: list[dict], matrix: list[list[float]], weights: list[float] | None = None, scale_max: float = 5) -> list[float]:
    w = weights if weights is not None else [c["weight"] for c in crit]
    tot = sum(w)
    wn = [x / tot for x in w]
    return [100 * sum(wn[j] * row[j] for j in range(len(row))) / scale_max for row in matrix]


@AGENT.tool
def weighted_score(options: list[dict], criteria: list[dict], scale_max: float = 5) -> dict:
    """Weighted decision matrix: normalised totals /100, ranking, margin, per-criterion winners, dominated options.

    Scores are 1..scale_max per criterion; raw numbers (cost in dollars, latency) can be passed
    with the criterion marked normalise: true and direction: "lower" where smaller is better.

    Args:
        options: List of {"name": str, "scores": {criterion_name: number}}.
        criteria: List of {"name": str, "weight": number (any scale, normalised), "direction": "higher"|"lower", "normalise": bool}.
        scale_max: Top of the scoring scale (default 5; use 10 for 1-10 scores).
    """
    opts, crit, matrix = _prep(options, criteria, scale_max)
    totals = _totals(crit, matrix, scale_max=scale_max)
    wsum = sum(c["weight"] for c in crit)
    ranked = sorted(range(len(opts)), key=lambda i: -totals[i])
    margin = round(totals[ranked[0]] - totals[ranked[1]], 1)
    per_crit = []
    for j, c in enumerate(crit):
        col = [matrix[i][j] for i in range(len(opts))]
        best = max(col)
        per_crit.append({"criterion": c["name"], "weight_pct": round(100 * c["weight"] / wsum, 1), "best": [opts[i]["name"] for i in range(len(opts)) if col[i] == best], "spread": round(best - min(col), 2)})
    dominated = []
    for a, b in combinations(range(len(opts)), 2):
        if all(matrix[a][j] >= matrix[b][j] for j in range(len(crit))) and any(matrix[a][j] > matrix[b][j] for j in range(len(crit))):
            dominated.append({"option": opts[b]["name"], "dominated_by": opts[a]["name"]})
        elif all(matrix[b][j] >= matrix[a][j] for j in range(len(crit))) and any(matrix[b][j] > matrix[a][j] for j in range(len(crit))):
            dominated.append({"option": opts[a]["name"], "dominated_by": opts[b]["name"]})
    rows = []
    for rank, i in enumerate(ranked, 1):
        contrib = {c["name"]: round(100 * (c["weight"] / wsum) * matrix[i][j] / scale_max, 1) for j, c in enumerate(crit)}
        top = max(contrib, key=contrib.get)
        weakest = min(range(len(crit)), key=lambda j: matrix[i][j] / scale_max)
        rows.append(
            {
                "rank": rank,
                "option": opts[i]["name"],
                "total": round(totals[i], 1),
                "gap_to_leader": round(totals[ranked[0]] - totals[i], 1),
                "normalised_scores": {c["name"]: round(matrix[i][j], 2) for j, c in enumerate(crit)},
                "contribution": contrib,
                "strongest_criterion": top,
                "weakest_criterion": crit[weakest]["name"],
            }
        )
    closeness = "clear" if margin >= 10 else "moderate" if margin >= 5 else "CLOSE CALL"
    table = md_table(
        ["Criterion (w%)"] + [o["name"] for o in opts],
        [[f"{c['name']} ({round(100 * c['weight'] / wsum)}%)"] + [round(matrix[i][j], 1) for i in range(len(opts))] for j, c in enumerate(crit)]
        + [["**Total /100**"] + [f"**{round(totals[i], 1)}**" for i in range(len(opts))]],
    )
    return {
        "winner": opts[ranked[0]]["name"],
        "runner_up": opts[ranked[1]]["name"],
        "margin_points": margin,
        "closeness": closeness,
        "ranking": rows,
        "per_criterion": per_crit,
        "dominated_options": dominated,
        "weights_pct": {c["name"]: round(100 * c["weight"] / wsum, 1) for c in crit},
        "markdown_table": table,
        "verdict": f"{opts[ranked[0]]['name']} leads with {round(totals[ranked[0]], 1)}/100, {margin} points ahead of {opts[ranked[1]]['name']} ({closeness}). "
        + ("Run sensitivity_check before committing." if margin < 10 else "Confirm with sensitivity_check.")
        + (f" Dominated: {', '.join(d['option'] for d in dominated)}." if dominated else ""),
    }


@AGENT.tool
def sensitivity_check(options: list[dict], criteria: list[dict], scale_max: float = 5) -> dict:
    """Stress-test a decision matrix: which weight change or single score change flips the winner, and equal-weights result.

    Args:
        options: Same as weighted_score: {"name", "scores": {criterion: value}}.
        criteria: Same as weighted_score: {"name", "weight", "direction", "normalise"}.
        scale_max: Top of the scoring scale (default 5).
    """
    opts, crit, matrix = _prep(options, criteria, scale_max)
    base_w = [c["weight"] for c in crit]
    wsum = sum(base_w)
    base_pct = [100 * w / wsum for w in base_w]
    totals = _totals(crit, matrix, scale_max=scale_max)
    winner = max(range(len(opts)), key=lambda i: totals[i])
    n = len(crit)
    weight_flips = []
    for j in range(n):
        flip = None
        # sweep this criterion's weight share from 0..100 %, others scaled proportionally
        others = [base_pct[k] for k in range(n) if k != j]
        others_sum = sum(others) or 1.0
        best_delta = None
        for share in range(0, 101):
            w = [share if k == j else base_pct[k] * (100 - share) / others_sum for k in range(n)]
            if sum(w) <= 0:
                continue
            t = _totals(crit, matrix, w, scale_max)
            new_winner = max(range(len(opts)), key=lambda i: t[i])
            if new_winner != winner:
                delta = share - base_pct[j]
                if best_delta is None or abs(delta) < abs(best_delta):
                    best_delta, flip = delta, {"criterion": crit[j]["name"], "current_weight_pct": round(base_pct[j], 1), "flip_at_weight_pct": share, "delta_pct_points": round(delta, 1), "new_winner": opts[new_winner]["name"]}
        weight_flips.append(flip or {"criterion": crit[j]["name"], "current_weight_pct": round(base_pct[j], 1), "flip_at_weight_pct": None, "delta_pct_points": None, "new_winner": None})
    fragile = [f for f in weight_flips if f["delta_pct_points"] is not None and abs(f["delta_pct_points"]) <= 10]
    # smallest single-cell score change that flips the winner
    cell_flips = []
    for i in range(len(opts)):
        for j in range(n):
            share = base_pct[j] / 100
            per_point = 100 * share / scale_max  # total change per 1 score point
            if per_point <= 0:
                continue
            if i == winner:
                # winner's score drops until runner-up overtakes
                runner = max((k for k in range(len(opts)) if k != winner), key=lambda k: totals[k])
                needed = (totals[winner] - totals[runner]) / per_point
                room = matrix[i][j]
                if needed <= room:
                    cell_flips.append({"option": opts[i]["name"], "criterion": crit[j]["name"], "change": round(-needed, 2) + 0.0, "becomes_winner": opts[runner]["name"]})
            else:
                needed = (totals[winner] - totals[i]) / per_point
                room = scale_max - matrix[i][j]
                if needed <= room:
                    cell_flips.append({"option": opts[i]["name"], "criterion": crit[j]["name"], "change": round(needed, 2), "becomes_winner": opts[i]["name"]})
    cell_flips.sort(key=lambda x: abs(x["change"]))
    eq = _totals(crit, matrix, [1.0] * n, scale_max)
    eq_winner = opts[max(range(len(opts)), key=lambda i: eq[i])]["name"]
    smallest_cell = cell_flips[0] if cell_flips else None
    robust = not fragile and (smallest_cell is None or abs(smallest_cell["change"]) > 1) and eq_winner == opts[winner]["name"]
    label = "ROBUST" if robust else "FRAGILE" if (fragile and smallest_cell and abs(smallest_cell["change"]) <= 1) else "MODERATE"
    return {
        "winner": opts[winner]["name"],
        "margin_points": round(sorted(totals, reverse=True)[0] - sorted(totals, reverse=True)[1], 1),
        "robustness": label,
        "weight_flips": weight_flips,
        "fragile_criteria": [f["criterion"] for f in fragile],
        "smallest_score_flip": smallest_cell,
        "score_flips": cell_flips[:10],
        "equal_weights_winner": eq_winner,
        "equal_weights_agrees": eq_winner == opts[winner]["name"],
        "verdict": f"{opts[winner]['name']} is {label.lower()}. "
        + (f"Flips if {', '.join(f['criterion'] + ' moves ' + str(f['delta_pct_points']) + ' pts' for f in fragile)}. " if fragile else "No criterion flips it within ±10 weight points. ")
        + (f"Smallest score change that flips it: {smallest_cell['option']} on {smallest_cell['criterion']} by {smallest_cell['change']:+g}. " if smallest_cell else "")
        + f"Equal weights → {eq_winner}.",
    }


@AGENT.tool
def expected_value(options: list[dict]) -> dict:
    """Expected value, spread, downside and (when scenarios match) max regret for options with probabilistic outcomes.

    Args:
        options: List of {"name": str, "outcomes": [{"name": str, "probability": 0-1 (or %), "value": number}]}. Probabilities per option must sum to 1.
    """
    options = require_list(options, "options", 20)
    rows = []
    for i, o in enumerate(options, 1):
        if not isinstance(o, dict):
            raise ToolError(f"options[{i}] must be {{'name', 'outcomes': [...]}}.")
        name = as_str(o.get("name"), f"options[{i}].name", max_len=80)
        outs = require_list(o.get("outcomes"), f"{name}.outcomes", 50)
        parsed = []
        for k, oc in enumerate(outs, 1):
            if not isinstance(oc, dict):
                raise ToolError(f"{name}.outcomes[{k}] must be {{'name','probability','value'}}.")
            p = as_float(oc.get("probability", oc.get("p")), f"{name}.outcomes[{k}].probability", lo=0, hi=100)
            if p > 1:
                p /= 100
            v = as_float(oc.get("value", oc.get("payoff")), f"{name}.outcomes[{k}].value")
            parsed.append({"name": as_str(oc.get("name") or f"scenario {k}", "name", max_len=60), "p": p, "v": v})
        psum = sum(x["p"] for x in parsed)
        if abs(psum - 1) > 0.011:
            raise ToolError(f"{name}: probabilities sum to {psum:.3f}, not 1. Fix them (they must be exhaustive and exclusive).")
        ev = sum(x["p"] * x["v"] for x in parsed)
        var = sum(x["p"] * (x["v"] - ev) ** 2 for x in parsed)
        sd = math.sqrt(var)
        worst = min(parsed, key=lambda x: x["v"])
        best = max(parsed, key=lambda x: x["v"])
        p_loss = sum(x["p"] for x in parsed if x["v"] < 0)
        downside = sum(x["p"] * x["v"] for x in parsed if x["v"] < 0)
        rows.append(
            {
                "option": name,
                "expected_value": round(ev, 2),
                "std_dev": round(sd, 2),
                "coefficient_of_variation": round(sd / abs(ev), 2) if ev else None,
                "best_case": {"scenario": best["name"], "value": best["v"], "probability": best["p"]},
                "worst_case": {"scenario": worst["name"], "value": worst["v"], "probability": worst["p"]},
                "probability_of_loss": round(p_loss, 3),
                "expected_loss": round(downside, 2),
                "outcomes": [{"name": x["name"], "probability": x["p"], "value": x["v"], "weighted": round(x["p"] * x["v"], 2)} for x in parsed],
            }
        )
    ranked = sorted(rows, key=lambda r: -r["expected_value"])
    # regret: only if all options share the same scenario names
    scen_sets = [tuple(sorted(x["name"].lower() for x in r["outcomes"])) for r in rows]
    regret = None
    if len(rows) > 1 and len(set(scen_sets)) == 1:
        scen = [x["name"] for x in rows[0]["outcomes"]]
        table = {}
        for s in scen:
            best_in_state = max(next(x["value"] for x in r["outcomes"] if x["name"] == s) for r in rows)
            for r in rows:
                val = next(x["value"] for x in r["outcomes"] if x["name"] == s)
                table.setdefault(r["option"], {})[s] = round(best_in_state - val, 2)
        regret = {"by_option": {o: {"regrets": t, "max_regret": max(t.values())} for o, t in table.items()}}
        regret["minimax_choice"] = min(regret["by_option"], key=lambda o: regret["by_option"][o]["max_regret"])
    lead = ranked[0]
    verdict = f"Highest EV: {lead['option']} ({lead['expected_value']:g}, σ {lead['std_dev']:g}, worst case {lead['worst_case']['value']:g} with p={lead['worst_case']['probability']:g})."
    if len(ranked) > 1:
        verdict += f" Runner-up {ranked[1]['option']} at {ranked[1]['expected_value']:g}."
    if regret:
        verdict += f" Minimax-regret pick: {regret['minimax_choice']}."
        if regret["minimax_choice"] != lead["option"]:
            verdict += " EV and regret disagree — decide based on whether the worst case is survivable."
    return {"ranking": ranked, "regret": regret, "verdict": verdict}


@AGENT.tool
def pairwise_weights(criteria: list[str], comparisons: list[dict]) -> dict:
    """Derive criteria weights from pairwise importance judgements (AHP) with a consistency ratio.

    Each comparison says how many times more important `a` is than `b` on Saaty's 1-9 scale
    (use 1/3 or 0.33 when b matters more). Missing pairs are assumed equal and flagged.

    Args:
        criteria: Criterion names (2-12).
        comparisons: List of {"a": criterion, "b": criterion, "ratio": 1-9 (or a fraction like 0.2)}.
    """
    criteria = [as_str(c, "criteria", max_len=80) for c in require_list(criteria, "criteria", 12, min_len=2)]
    if len(set(c.lower() for c in criteria)) != len(criteria):
        raise ToolError("Criteria names must be unique.")
    idx = {c.lower(): i for i, c in enumerate(criteria)}
    n = len(criteria)
    A = [[1.0] * n for _ in range(n)]
    given: set[tuple[int, int]] = set()
    for k, cmp in enumerate(require_list(comparisons, "comparisons", 200), 1):
        if not isinstance(cmp, dict):
            raise ToolError(f"comparisons[{k}] must be {{'a','b','ratio'}}.")
        a, b = str(cmp.get("a", "")).lower().strip(), str(cmp.get("b", "")).lower().strip()
        if a not in idx or b not in idx:
            raise ToolError(f"comparisons[{k}]: unknown criterion ({cmp.get('a')!r} / {cmp.get('b')!r}). Known: {', '.join(criteria)}.")
        if a == b:
            raise ToolError(f"comparisons[{k}]: a and b are the same criterion.")
        r = as_float(cmp.get("ratio"), f"comparisons[{k}].ratio")
        if not (1 / 9 - 1e-9 <= r <= 9 + 1e-9) or r <= 0:
            raise ToolError(f"comparisons[{k}].ratio must be between 1/9 and 9 (got {r}).")
        i, j = idx[a], idx[b]
        A[i][j], A[j][i] = r, 1 / r
        given.add((min(i, j), max(i, j)))
    missing = [f"{criteria[i]} vs {criteria[j]}" for i, j in combinations(range(n), 2) if (i, j) not in given]
    gm = [math.exp(sum(math.log(A[i][j]) for j in range(n)) / n) for i in range(n)]
    tot = sum(gm)
    w = [g / tot for g in gm]
    Aw = [sum(A[i][j] * w[j] for j in range(n)) for i in range(n)]
    lam = sum(Aw[i] / w[i] for i in range(n)) / n
    ci = (lam - n) / (n - 1) if n > 1 else 0.0
    ri = _RI.get(n, 1.59)
    cr = ci / ri if ri else 0.0
    worst_triad = None
    for i, j, k in combinations(range(n), 3):
        implied = A[i][j] * A[j][k]
        dev = abs(math.log(implied) - math.log(A[i][k]))
        if worst_triad is None or dev > worst_triad["deviation"]:
            worst_triad = {"criteria": [criteria[i], criteria[j], criteria[k]], "stated": f"{criteria[i]}/{criteria[k]} = {A[i][k]:.2f}", "implied": f"{criteria[i]}/{criteria[j]} × {criteria[j]}/{criteria[k]} = {implied:.2f}", "deviation": round(dev, 3)}
    ranked = sorted(range(n), key=lambda i: -w[i])
    return {
        "weights": {criteria[i]: round(w[i], 4) for i in range(n)},
        "weights_pct": {criteria[i]: round(100 * w[i], 1) for i in ranked},
        "ranking": [criteria[i] for i in ranked],
        "lambda_max": round(lam, 4),
        "consistency_index": round(ci, 4),
        "consistency_ratio": round(cr, 3),
        "consistent": cr <= 0.10,
        "most_inconsistent_triad": worst_triad if worst_triad and worst_triad["deviation"] > 0.05 else None,
        "assumed_equal_pairs": missing,
        "verdict": f"Weights: {', '.join(f'{criteria[i]} {round(100 * w[i])}%' for i in ranked)}. CR = {cr:.2f} "
        + ("(consistent)." if cr <= 0.10 else "(> 0.10: judgements contradict; re-judge the flagged triad).")
        + (f" {len(missing)} pair(s) assumed equal — confirm them." if missing else ""),
    }
