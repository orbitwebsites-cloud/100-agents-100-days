"""Grant Writer — budgets that reconcile, sections that fit the limits, criteria-aligned narratives, and a compliant timeline."""

from __future__ import annotations

import re
from datetime import timedelta

from ...core import Agent, ToolError
from ...lib import dates, text as textlib
from ._common import SCOPE_NOTE, add_months, check_rows, check_text, money, parse_date, to_float

AGENT = Agent(
    slug="grant-writer",
    name="Grant Writer",
    category="legal",
    tagline="Win more grants: a budget that reconciles to the cent, sections that fit the limits, and every scoring criterion covered.",
    description=(
        "Works like a senior development officer with a 40% hit rate: builds the budget table with direct, "
        "fringe, indirect (NICRA/de minimis/MTDC-aware) and cost-share math that adds up and respects caps, "
        "checks every narrative section against the funder's word/character/page limits, scores the draft "
        "against the published review criteria to find under-weighted gaps, lints objectives for SMART "
        "compliance, and generates the project timeline with reporting deadlines the funder actually enforces."
    ),
    triggers=[
        "write / help me write a grant proposal",
        "build a grant budget with indirect costs",
        "does my proposal fit the word / page limits",
        "map my proposal to the funder's scoring criteria",
        "grant project timeline and reporting deadlines",
        "make these objectives SMART",
    ],
    examples=[
        "We're applying for a $150k foundation grant for a youth coding program. Here's our draft narrative and the RFP — review it.",
        "Build the budget: 1 FTE at $70k, 0.5 FTE at $60k, fringe 28%, $12k equipment, $8k travel, 10% de minimis indirect, $50k cost share required.",
        "The RFP scores need (30), approach (30), capacity (20), evaluation (20). Here's our draft — where are we weak?",
    ],
    connectors=["Google Docs", "Google Sheets", "Notion", "Airtable"],
    playbook="""
    ## Standard
    You are a senior grant writer. Excellent proposals are reviewer-shaped: they answer each
    scoring criterion in the order and weight the funder published, with numbers everywhere a
    reviewer could ask "how many / how much / by when". The budget reconciles to the narrative
    line by line, and nothing exceeds a limit by a single word. The one metric that matters is
    **reviewer score**, so every paragraph earns points against a named criterion or gets cut.

    **Scope note (include once in every output):** drafting aid, not legal or financial advice.
    Funder rules (allowable costs, indirect rates, cost-share, reporting) are set by each program's
    guidelines and, for US federal awards, 2 CFR 200 — verify the current NOFO/RFP and consult your
    finance office before submission.

    ## Intake
    Proceed with what you have. Ask (max 3) only if you cannot infer: (1) the funder's criteria and
    weights (or the RFP text), (2) budget parameters (amount requested, indirect rate, cost-share
    requirement, allowable costs), (3) section limits (words/pages/characters). If limits aren't
    given, assume common ones (need/problem 500 words, approach 1000, evaluation 500, budget
    justification 500) and say so.

    ## Procedure
    1. **Decode the RFP.** Extract: eligibility, amount range, criteria + weights, required
       sections and limits, deadline, reporting requirements, allowable/unallowable costs,
       indirect policy, cost-share/match. Put them in a table at the top of your working notes.
    2. **Build the budget first.** Call `grant_writer__budget_table` with line items (category,
       description, quantity, unit cost, or salary + FTE), fringe rate, indirect rate and base
       (de minimis 15% on MTDC, negotiated rate, or funder cap), cost-share requirement and the
       request cap. It computes personnel with fringe, MTDC (excludes equipment > $5k, tuition,
       participant support, rent, subaward amounts above $25k), indirect, total, cost-share required
       and provided, and flags over-cap or unallowable-looking items. The narrative must match
       these numbers exactly.
    3. **Write objectives** as SMART statements and check each with the SMART lint inside
       `grant_writer__criteria_coverage` (objectives array). "Serve 120 youth (ages 14-18) in 3
       cohorts by 2027-06-30, with 80% completing ≥ 30 hours" scores; "empower young people" doesn't.
    4. **Draft each section** to its criterion. Open every section with the direct answer to the
       criterion's question. Use the funder's own vocabulary (if they say "outcomes", don't say
       "impact"). Cite baseline data with sources; never invent statistics.
    5. **Score the draft.** Call `grant_writer__criteria_coverage` with the section texts and the
       criteria (name, weight, keywords/questions). It measures how much text and how many
       criterion keywords each criterion gets versus its weight, flags criteria that are
       under-covered relative to their weight, and lints objectives for SMART. Rebalance before
       polishing.
    6. **Check limits.** Call `grant_writer__check_section_limits` with each section and its limit
       (words, characters, or pages with the funder's formatting). Cut anything over — reviewers
       and portals both truncate. Aim for 90-98% of each limit: under-using space reads as thin.
    7. **Build the timeline.** Call `grant_writer__project_timeline` with start date, duration,
       milestones and reporting cadence. It returns phase dates, report due dates (typically 30
       days after each period; final report 90-120 days after the end date), and flags milestones
       that fall outside the period of performance.
    8. **Assemble** in the output format with a compliance checklist. File to Docs/Notion if
       connected; put the budget in Sheets/Airtable if connected.

    ## Frameworks
    - **Logic model:** Inputs → Activities → Outputs (counts) → Outcomes (changes, short/medium)
      → Impact. Reviewers look for outputs and outcomes with numbers and a data source.
    - **SMART objectives:** Specific (who/what), Measurable (number or %), Achievable (baseline
      cited), Relevant (to the funder's priority), Time-bound (date).
    - **Budget norms:** personnel + fringe typically 60-75% of direct costs for program grants;
      evaluation 5-10%; indirect per NICRA or the 15% de minimis (2 CFR 200.414 as revised 2024);
      foundations often cap indirect at 10-15% of total or 0%.
    - **Criterion-weighted length:** a criterion worth 30% of the score should get roughly 30% of
      the narrative space. ±10 points is fine; a 30-point criterion with 10% of the text is a gap.
    - **Reviewer heuristics:** they read the abstract, the budget and the evaluation plan first;
      a mismatch between any two kills the proposal.

    ## Output format
    ```
    # Proposal: <Project> — <Funder / program> — request $<X> — due <date>
    **Compliance:** eligibility ✓ · limits ✓ (all sections ≤ limit) · budget reconciles ✓ · attachments: <list>
    **Scope note:** drafting aid, not legal/financial advice; verify the current guidelines.

    ## Criteria coverage
    | Criterion | Weight | Share of text | Keyword hits | Status |

    ## Sections
    ### <Section name> (<n>/<limit> words)
    <text>
    …
    ## Objectives (SMART)
    1. By <date>, <who> will <measurable result> as measured by <source>. (baseline: …)

    ## Budget
    | Category | Item | Calc | Amount |
    | Personnel | Program Director, 1.0 FTE × $70,000 | | $70,000 |
    | … | | Total direct | $… |
    | Indirect | 15% de minimis on MTDC $… | | $… |
    | | | TOTAL REQUEST | $… |
    Cost share: required $… · provided $… (source)

    ## Timeline & reporting
    | Milestone / report | Date |

    ## Before submitting
    - [ ] <checklist items>
    ```

    ## Anti-patterns
    - Writing the narrative first and back-filling the budget. Reviewers spot a budget that doesn't match activities.
    - "Empower", "transform", "innovative" with no numbers. Every claim needs a count, a %, or a date.
    - Ignoring criterion weights. A beautiful 800-word need statement for a 10-point criterion is wasted.
    - Exceeding limits by "a little". Portals truncate; reviewers penalise.
    - Inventing baselines or citing stats without a source. Use your data or a named public source; otherwise say "baseline to be established in month 1".
    - Indirect on the wrong base (applying the rate to equipment or subawards) — the funder's finance reviewer will catch it.
    """,
)

CATEGORIES = {"personnel", "fringe", "travel", "equipment", "supplies", "contractual", "subaward", "construction", "participant_support", "rent", "tuition", "evaluation", "other"}
MTDC_EXCLUDED = {"equipment", "construction", "participant_support", "rent", "tuition"}


@AGENT.tool
def budget_table(line_items: list[dict], fringe_rate_pct: float = 0.0, indirect_rate_pct: float = 0.0, indirect_base: str = "mtdc", request_cap: float = 0.0, cost_share_required_pct: float = 0.0, cost_share_provided: float = 0.0, indirect_cap_pct_of_total: float = 0.0) -> dict:
    """Compute a grant budget: personnel × FTE, fringe, MTDC, indirect, totals, cost share, and cap checks.

    Args:
        line_items: List of {"category": personnel|fringe|travel|equipment|supplies|contractual|subaward|construction|
            participant_support|rent|tuition|evaluation|other, "description": str, and EITHER "amount": dollars OR
            "salary": annual dollars + "fte": 0-1 (+ optional "months": 12) OR "quantity" + "unit_cost"}.
        fringe_rate_pct: Fringe benefits as % of salaries (applied to personnel items; default 0). Add explicit "fringe" items instead if preferred.
        indirect_rate_pct: Indirect/F&A rate % (e.g. 15 for de minimis, or your negotiated rate).
        indirect_base: "mtdc" (modified total direct costs — excludes equipment, construction, participant support, rent, tuition and subaward amounts over $25k), "tdc" (total direct), or "salaries" (salaries + fringe only).
        request_cap: Maximum request allowed by the funder (0 = none).
        cost_share_required_pct: Required match as % of the request (e.g. 25 for a 1:4 match). 0 = none.
        cost_share_provided: Dollar value of match you will provide (cash + in-kind).
        indirect_cap_pct_of_total: Funder cap on indirect as % of the total award (e.g. 10). 0 = none.
    """
    rows = check_rows(line_items, "line_items", 300)
    fringe = to_float(fringe_rate_pct, "fringe_rate_pct", 0, 100) / 100
    ind_rate = to_float(indirect_rate_pct, "indirect_rate_pct", 0, 100) / 100
    base_kind = str(indirect_base).strip().lower()
    if base_kind not in {"mtdc", "tdc", "salaries"}:
        raise ToolError("indirect_base must be 'mtdc', 'tdc' or 'salaries'.")
    cap = to_float(request_cap, "request_cap", 0)
    cs_pct = to_float(cost_share_required_pct, "cost_share_required_pct", 0, 1000) / 100
    cs_prov = to_float(cost_share_provided, "cost_share_provided", 0)
    ind_cap = to_float(indirect_cap_pct_of_total, "indirect_cap_pct_of_total", 0, 100) / 100
    table, by_cat, flags = [], {}, []
    salaries = 0.0
    for i, raw in enumerate(rows):
        if not isinstance(raw, dict):
            raise ToolError(f"line_items[{i}] must be an object.")
        cat = str(raw.get("category", "other")).strip().lower().replace(" ", "_")
        if cat not in CATEGORIES:
            raise ToolError(f"line_items[{i}]: unknown category {cat!r}. Use one of {', '.join(sorted(CATEGORIES))}.")
        desc = str(raw.get("description", "")).strip() or cat
        if raw.get("salary") is not None:
            sal = to_float(raw["salary"], f"{desc}: salary", 0)
            fte = to_float(raw.get("fte", 1), f"{desc}: fte", 0, 1)
            months = to_float(raw.get("months", 12), f"{desc}: months", 0.1, 60)
            amount = sal * fte * months / 12
            calc = f"${sal:,.0f} × {fte:g} FTE × {months:g}/12"
            if cat == "personnel":
                salaries += amount
        elif raw.get("quantity") is not None:
            q = to_float(raw["quantity"], f"{desc}: quantity", 0)
            uc = to_float(raw.get("unit_cost"), f"{desc}: unit_cost", 0)
            amount = q * uc
            calc = f"{q:g} × ${uc:,.2f}"
        else:
            amount = to_float(raw.get("amount"), f"{desc}: amount", 0)
            calc = "lump sum"
            if cat == "personnel":
                salaries += amount
        if cat == "equipment" and amount < 5000:
            flags.append(f"'{desc}' ${amount:,.0f} is under the $5,000 equipment threshold — classify as supplies (it then counts toward MTDC)")
        table.append({"category": cat, "description": desc, "calc": calc, "amount": round(amount, 2)})
        by_cat[cat] = by_cat.get(cat, 0.0) + amount
    fringe_amt = salaries * fringe
    if fringe_amt:
        table.append({"category": "fringe", "description": f"Fringe benefits {fringe * 100:g}% of salaries ${salaries:,.0f}", "calc": f"{fringe * 100:g}% × ${salaries:,.0f}", "amount": round(fringe_amt, 2)})
        by_cat["fringe"] = by_cat.get("fringe", 0.0) + fringe_amt
    total_direct = sum(by_cat.values())
    # MTDC
    sub = by_cat.get("subaward", 0.0)
    sub_items = [t for t in table if t["category"] == "subaward"]
    sub_in_mtdc = sum(min(t["amount"], 25_000) for t in sub_items)
    excluded = sum(v for k, v in by_cat.items() if k in MTDC_EXCLUDED) + (sub - sub_in_mtdc)
    mtdc = total_direct - excluded
    base_amt = {"mtdc": mtdc, "tdc": total_direct, "salaries": salaries + fringe_amt}[base_kind]
    indirect = base_amt * ind_rate
    total = total_direct + indirect
    if ind_cap and total and indirect / total > ind_cap + 1e-9:
        allowed = ind_cap * total_direct / (1 - ind_cap)
        flags.append(f"Indirect ${indirect:,.0f} is {100 * indirect / total:.1f}% of total; funder caps at {ind_cap * 100:g}% → reduce indirect to ${allowed:,.0f}")
        indirect = allowed
        total = total_direct + indirect
    if cap and total > cap:
        flags.append(f"Total ${total:,.0f} exceeds the ${cap:,.0f} cap by ${total - cap:,.0f} — cut direct costs by ${(total - cap) / (1 + ind_rate if base_kind == 'tdc' else 1):,.0f}")
    cs_required = total * cs_pct
    if cs_pct and cs_prov < cs_required:
        flags.append(f"Cost share short: required ${cs_required:,.0f} ({cs_pct * 100:g}% of request), provided ${cs_prov:,.0f} — gap ${cs_required - cs_prov:,.0f}")
    pers_share = (by_cat.get("personnel", 0) + by_cat.get("fringe", 0)) / total_direct if total_direct else 0
    if total_direct and pers_share > 0.85:
        flags.append(f"Personnel + fringe = {pers_share * 100:.0f}% of direct costs — reviewers may ask what the program spends on participants")
    if by_cat.get("evaluation", 0) == 0:
        flags.append("No evaluation line — most funders expect 5-10% of direct costs for evaluation")
    return {
        "lines": table,
        "by_category": {k: round(v, 2) for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1])},
        "salaries": round(salaries, 2),
        "fringe": round(fringe_amt, 2),
        "total_direct": round(total_direct, 2),
        "mtdc": round(mtdc, 2),
        "indirect_base": base_kind,
        "indirect_base_amount": round(base_amt, 2),
        "indirect_rate_pct": ind_rate * 100,
        "indirect": round(indirect, 2),
        "total_request": round(total, 2),
        "cost_share": {"required": round(cs_required, 2), "provided": round(cs_prov, 2), "gap": round(max(0.0, cs_required - cs_prov), 2)},
        "total_project_cost": round(total + cs_prov, 2),
        "category_pct_of_direct": {k: round(100 * v / total_direct, 1) for k, v in by_cat.items()} if total_direct else {},
        "flags": flags,
        "verdict": f"Total request {money(total)} (direct {money(total_direct)} + indirect {money(indirect)})" + (f"; {len(flags)} flag(s)" if flags else " — reconciles"),
        "scope_note": SCOPE_NOTE,
    }


PAGE_WORDS = {"single": 500, "1.5": 375, "double": 250}


@AGENT.tool
def check_section_limits(sections: list[dict]) -> dict:
    """Check each proposal section against its word / character / page limit and readability; report cuts needed.

    Args:
        sections: List of {"name": str, "text": str, "limit": number, "unit": "words"|"characters"|"pages",
            "spacing": "single"|"1.5"|"double" (for pages; default single ≈ 500 words/page at 12pt)}.
    """
    rows = check_rows(sections, "sections", 60)
    out, over_any = [], False
    total_words = 0
    for i, raw in enumerate(rows):
        if not isinstance(raw, dict) or not str(raw.get("text", "")).strip():
            raise ToolError(f"sections[{i}] needs 'name', non-empty 'text', 'limit' and 'unit'.")
        name = str(raw.get("name", f"section {i + 1}"))
        body = check_text(str(raw["text"]), name)
        unit = str(raw.get("unit", "words")).strip().lower()
        if unit not in {"words", "characters", "pages"}:
            raise ToolError(f"{name}: unit must be words, characters or pages.")
        limit = to_float(raw.get("limit"), f"{name}: limit", 0.1)
        nwords = len(textlib.words(body))
        nchars = len(body)
        total_words += nwords
        if unit == "words":
            used, limit_v = nwords, limit
        elif unit == "characters":
            used, limit_v = nchars, limit
        else:
            spacing = str(raw.get("spacing", "single")).strip().lower()
            wpp = PAGE_WORDS.get(spacing)
            if not wpp:
                raise ToolError(f"{name}: spacing must be single, 1.5 or double.")
            used, limit_v = round(nwords / wpp, 2), limit
        pct_used = round(100 * used / limit_v, 1)
        fits = used <= limit_v
        over_any |= not fits
        r = textlib.readability(body)
        status = "OVER — cut" if not fits else "thin — under 75% of the limit" if pct_used < 75 else "good"
        cut = None
        if not fits:
            cut = f"cut {used - limit_v:g} {unit}" if unit != "pages" else f"cut ≈ {round((used - limit_v) * PAGE_WORDS.get(str(raw.get('spacing', 'single')).lower(), 500))} words"
        out.append({"name": name, "words": nwords, "characters": nchars, "used": used, "limit": limit_v, "unit": unit, "pct_of_limit": pct_used, "fits": fits, "status": status, "cut_needed": cut, "fk_grade": r["fk_grade"], "avg_words_per_sentence": r.get("avg_words_per_sentence")})
    return {
        "sections": out,
        "total_words": total_words,
        "all_fit": not over_any,
        "over_limit": [s["name"] for s in out if not s["fits"]],
        "thin": [s["name"] for s in out if s["fits"] and s["pct_of_limit"] < 75],
        "verdict": "All sections within limits" if not over_any else f"{len([s for s in out if not s['fits']])} section(s) over limit — cut before submitting",
    }


_SMART_NUMBER = re.compile(r"\b\d[\d,.]*\s*%?|\bpercent\b|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|twenty|fifty|hundred)\b", re.I)
_SMART_DATE = re.compile(r"\b(?:by|before|within|during|in)\s+(?:\d{4}-\d{2}-\d{2}|(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}|q[1-4]\s*\d{4}|(?:month|year|quarter|week)s?\s+\d+|\d+\s+(?:months|weeks|years)|the end of|20\d{2})\b|\b20\d{2}\b", re.I)
_SMART_MEASURE = re.compile(r"\bas measured by|measured (?:by|through|via)|using|per\b|survey|assessment|attendance|records?|data|pre-?/?post|tracked|log", re.I)
_SMART_WHO = re.compile(r"\b(?:youth|students?|participants?|families|children|adults|residents|patients|clients|teachers|women|men|veterans|seniors|households|farmers|members|organi[sz]ations?|schools?|communit(?:y|ies)|people)\b", re.I)
_VAGUE = re.compile(r"\b(empower|transform|raise awareness|enhance|improve|support|strengthen|promote|foster|engage|build capacity)\b", re.I)


@AGENT.tool
def criteria_coverage(sections: list[dict], criteria: list[dict], objectives: list[str] | None = None) -> dict:
    """Score the draft against the funder's weighted criteria (text share + keyword hits) and lint objectives for SMART.

    Args:
        sections: List of {"name": str, "text": str, "criterion": str (optional — which criterion the section answers)}.
        criteria: List of {"name": str, "weight": number (points or %), "keywords": [str, ...] (the funder's words/questions)}.
        objectives: Optional list of objective statements to lint for Specific/Measurable/Achievable/Relevant/Time-bound.
    """
    secs = check_rows(sections, "sections", 60)
    crits = check_rows(criteria, "criteria", 30)
    total_weight = 0.0
    parsed = []
    for i, c in enumerate(crits):
        if not isinstance(c, dict) or not str(c.get("name", "")).strip():
            raise ToolError(f"criteria[{i}] needs 'name' and 'weight'.")
        w = to_float(c.get("weight"), f"{c['name']}: weight", 0)
        kws = [str(k).strip().lower() for k in (c.get("keywords") or []) if str(k).strip()]
        if not kws:
            kws = [w2 for w2 in textlib.words(str(c["name"]).lower()) if w2 not in textlib.STOPWORDS]
        parsed.append({"name": str(c["name"]).strip(), "weight": w, "keywords": kws[:40]})
        total_weight += w
    if total_weight <= 0:
        raise ToolError("criteria weights must sum to more than 0.")
    all_text = ""
    sec_words = {}
    for i, s in enumerate(secs):
        if not isinstance(s, dict) or not str(s.get("text", "")).strip():
            raise ToolError(f"sections[{i}] needs 'name' and non-empty 'text'.")
        body = check_text(str(s["text"]), str(s.get("name", f"section {i + 1}")))
        all_text += "\n" + body
        sec_words[i] = len(textlib.words(body))
    total_words = sum(sec_words.values()) or 1
    lower = all_text.lower()
    results, gaps = [], []
    for c in parsed:
        weight_pct = 100 * c["weight"] / total_weight
        assigned = sum(sec_words[i] for i, s in enumerate(secs) if str(s.get("criterion", "")).strip().lower() == c["name"].lower())
        hits = {k: len(re.findall(r"\b" + re.escape(k) + r"\b", lower)) for k in c["keywords"]}
        matched = sum(1 for v in hits.values() if v)
        kw_cov = 100 * matched / len(c["keywords"]) if c["keywords"] else 0
        text_share = 100 * assigned / total_words if assigned else None
        status = "ok"
        if kw_cov < 50:
            status = "gap — funder vocabulary missing"
        if text_share is not None and text_share < weight_pct - 10:
            status = "under-covered vs weight"
        if text_share is not None and text_share > weight_pct + 15:
            status = "over-invested vs weight"
        if status != "ok":
            gaps.append(f"{c['name']} ({weight_pct:.0f}% weight): {status}" + (f" — {text_share:.0f}% of text" if text_share is not None else "") + f", {kw_cov:.0f}% keywords")
        results.append({"criterion": c["name"], "weight_pct": round(weight_pct, 1), "text_share_pct": None if text_share is None else round(text_share, 1), "keyword_coverage_pct": round(kw_cov, 1), "missing_keywords": [k for k, v in hits.items() if not v][:10], "status": status})
    weighted_score = sum(min(1.0, r["keyword_coverage_pct"] / 80) * r["weight_pct"] for r in results)
    smart = []
    if objectives:
        for o in objectives[:50]:
            s = str(o).strip()
            if not s:
                continue
            checks = {"specific_who": bool(_SMART_WHO.search(s)), "measurable": bool(_SMART_NUMBER.search(s)), "time_bound": bool(_SMART_DATE.search(s)), "measurement_source": bool(_SMART_MEASURE.search(s)), "vague_verb": bool(_VAGUE.search(s))}
            score = sum(1 for k in ("specific_who", "measurable", "time_bound", "measurement_source") if checks[k]) - (1 if checks["vague_verb"] else 0)
            fixes = []
            if not checks["specific_who"]:
                fixes.append("name the population")
            if not checks["measurable"]:
                fixes.append("add a number or %")
            if not checks["time_bound"]:
                fixes.append("add a date")
            if not checks["measurement_source"]:
                fixes.append("say how it is measured")
            if checks["vague_verb"]:
                fixes.append("replace the vague verb with an observable result")
            smart.append({"objective": s[:200], "score": max(0, score), "of": 4, "checks": checks, "fixes": fixes})
    return {
        "criteria": results,
        "gaps": gaps,
        "weighted_coverage_score": round(weighted_score, 1),
        "total_words": total_words,
        "objectives": smart,
        "objectives_passing": sum(1 for s in smart if s["score"] >= 4),
        "verdict": (f"Weighted coverage {round(weighted_score)}/100; " + (f"{len(gaps)} criterion gap(s) — fix these first" if gaps else "criteria balanced")) + (f"; {sum(1 for s in smart if s['score'] >= 4)}/{len(smart)} objectives SMART" if smart else ""),
        "template_objective": "By <date>, <number> <population> will <observable result> (from baseline <x>), as measured by <instrument/source>.",
    }


@AGENT.tool
def project_timeline(start_date: str, duration_months: int, milestones: list[dict] | None = None, reporting: str = "quarterly", report_lag_days: int = 30, final_report_lag_days: int = 90) -> dict:
    """Generate the period of performance, phase/milestone dates, and every report due date; flag milestones outside the period.

    Args:
        start_date: YYYY-MM-DD project start.
        duration_months: Length of the period of performance in months.
        milestones: Optional list of {"name": str, "month": integer month number from start (1 = first month)} or {"name": str, "date": "YYYY-MM-DD"}.
        reporting: "monthly", "quarterly", "semiannual", "annual" or "none".
        report_lag_days: Days after each reporting period a report is due (default 30).
        final_report_lag_days: Days after the end date the final report is due (default 90; federal awards often 120).
    """
    start = parse_date(start_date, "start_date")
    if not isinstance(duration_months, int) or not 1 <= duration_months <= 120:
        raise ToolError("duration_months must be an integer between 1 and 120.")
    cadence = str(reporting).strip().lower()
    step = {"monthly": 1, "quarterly": 3, "semiannual": 6, "semi-annual": 6, "annual": 12, "none": 0}.get(cadence)
    if step is None:
        raise ToolError("reporting must be monthly, quarterly, semiannual, annual or none.")
    for name, v in (("report_lag_days", report_lag_days), ("final_report_lag_days", final_report_lag_days)):
        if not isinstance(v, int) or not 0 <= v <= 365:
            raise ToolError(f"{name} must be an integer between 0 and 365.")
    end = add_months(start, duration_months) - timedelta(days=1)
    reports = []
    if step:
        m = step
        n = 1
        while m < duration_months:
            period_end = add_months(start, m) - timedelta(days=1)
            reports.append({"report": f"{cadence.title()} report {n}", "period_end": period_end.isoformat(), "due": (period_end + timedelta(days=report_lag_days)).isoformat()})
            m += step
            n += 1
    reports.append({"report": "Final programmatic + financial report", "period_end": end.isoformat(), "due": (end + timedelta(days=final_report_lag_days)).isoformat()})
    ms_out, outside = [], []
    for i, raw in enumerate(milestones or []):
        if not isinstance(raw, dict) or not str(raw.get("name", "")).strip():
            raise ToolError(f"milestones[{i}] needs 'name' and 'month' or 'date'.")
        if raw.get("date"):
            d = dates.parse_date(str(raw["date"]))
        else:
            mo = raw.get("month")
            if not isinstance(mo, int) or mo < 1:
                raise ToolError(f"milestones[{i}]: 'month' must be a positive integer (1 = first month).")
            d = add_months(start, mo) - timedelta(days=1)
        ok = start <= d <= end
        if not ok:
            outside.append(str(raw["name"]))
        ms_out.append({"name": str(raw["name"]).strip(), "date": d.isoformat(), "month": ((d.year - start.year) * 12 + d.month - start.month) + 1, "within_period": ok})
    ms_out.sort(key=lambda x: x["date"])
    phases = [
        {"phase": "Start-up (hiring, agreements, baseline data)", "from": start.isoformat(), "to": (add_months(start, max(1, round(duration_months * 0.15))) - timedelta(days=1)).isoformat()},
        {"phase": "Implementation", "from": add_months(start, max(1, round(duration_months * 0.15))).isoformat(), "to": (add_months(start, max(2, round(duration_months * 0.85))) - timedelta(days=1)).isoformat()},
        {"phase": "Evaluation & close-out", "from": add_months(start, max(2, round(duration_months * 0.85))).isoformat(), "to": end.isoformat()},
    ]
    return {
        "period_of_performance": {"start": start.isoformat(), "end": end.isoformat(), "months": duration_months},
        "phases": phases,
        "milestones": ms_out,
        "milestones_outside_period": outside,
        "reports": reports,
        "calendar_entries": [{"title": r["report"] + " due", "date": r["due"]} for r in reports] + [{"title": m["name"], "date": m["date"]} for m in ms_out],
        "verdict": f"{duration_months}-month period ending {end.isoformat()}; {len(reports)} report(s), final due {reports[-1]['due']}" + (f"; {len(outside)} milestone(s) outside the period — move them" if outside else ""),
    }
