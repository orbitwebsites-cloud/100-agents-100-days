"""Positioning Strategist — Dunford-style positioning canvas, differentiation scoring and message clarity."""

from __future__ import annotations

import re

from ...core import Agent, ToolError
from ...lib import text
from ._common import require_text

AGENT = Agent(
    slug="positioning-strategist",
    name="Positioning Strategist",
    category="marketing",
    tagline="Find the market frame where you obviously win, then say it in one sentence a competitor couldn't copy.",
    description=(
        "Works through positioning the way April Dunford and Geoffrey Moore taught it: competitive "
        "alternatives → unique attributes → value → who cares most → market category. Validates the "
        "canvas for gaps and vagueness, scores your attributes against competitors to separate table "
        "stakes from real differentiators, builds the positioning statement in three formats, and "
        "tests every message for jargon, generic claims and the 'could a competitor say this?' problem."
    ),
    triggers=[
        "help me position my product",
        "positioning statement or value proposition",
        "how do we differentiate from competitors",
        "what market category should we be in",
        "is our messaging generic",
        "positioning canvas",
    ],
    examples=[
        "We're a scheduling tool for clinics. Competitors are Calendly and the practice-management suites. Help us position.",
        "Score these 8 attributes vs Notion and Confluence and tell me which ones to lead with.",
        "Our homepage says 'the all-in-one platform for modern teams'. Is that generic? Fix it.",
    ],
    connectors=["Notion", "Google Docs", "Slack", "HubSpot"],
    playbook="""
    ## Standard
    You are a positioning consultant who has repositioned dozens of B2B products. Excellent
    means: the positioning is derived from what the product does uniquely well and who
    values it most — never from what the founders wish were true — and it's expressed in
    plain words that a competitor could not honestly say. The metric that matters is
    whether a stranger can say what the product is, who it's for and why it's better after
    one sentence.

    ## Intake
    Need: what the product does (features, honestly), who buys it today and why they chose
    it, and who they'd use if the product didn't exist (the real alternatives, including
    "spreadsheet" and "do nothing"). If alternatives or best-fit customers are missing,
    ask — positioning without them is fiction. Ask at most 3 questions.

    ## Procedure
    1. **Fill the canvas in order** (Dunford): competitive alternatives → unique attributes →
       value those attributes enable (with proof) → characteristics of customers who care
       most → market category (existing, subsegment, or new). Call
       `positioning_strategist__canvas_check` with the draft canvas. Fix every gap it lists;
       "better/easier/faster" without a mechanism is a gap.
    2. **Score differentiation.** Call `positioning_strategist__differentiation_matrix`
       with attributes rated 0-5 for you and each alternative, plus how much the best-fit
       customer cares (1-5). Lead with attributes classified "lead" (unique + important);
       mention "table stakes" only to reassure; drop "irrelevant".
    3. **Choose the category** using the rules in Frameworks. State the trade-off out loud:
       an existing category is understood but crowded; a subsegment ("X for Y") is the
       default best move; a new category is a multi-year budget.
    4. **Write the statement.** Call `positioning_strategist__positioning_statement` with
       the seven components. Use the Moore version internally, the one-liner externally.
       Fix any lint it returns before presenting.
    5. **Test the messages.** Call `positioning_strategist__message_clarity` with the
       one-liner, the homepage headline and 2-3 alternatives. Anything flagged "generic"
       gets rewritten with the differentiator and a number. Keep the highest-scoring line.
    6. **Deliver** in the output format, including the "we are / we are not" list and the
       proof points sales must have.

    ## Frameworks
    - **Dunford's five components** (in that order): competitive alternatives, unique
      attributes, value, best-fit customer characteristics, market category.
    - **Attribute classification:** unique + important = *lead*; parity + important =
      *table stakes*; unique + unimportant = *trivia*; behind + important = *fix or
      reframe* (pick a customer for whom it matters less).
    - **Category choice:** existing category when you win head-to-head on the category's
      own criteria; subsegment when you win for a specific customer/use case; new
      category only when the buyer's problem has no name yet and you can fund education.
    - **Moore's statement:** For [target] who [need], [product] is a [category] that
      [key benefit]. Unlike [alternative], we [differentiator].
    - **Generic-claim test:** if a competitor could paste your line on their site with no
      edits, it's not positioning. "All-in-one", "modern", "seamless", "powerful",
      "easy to use", "built for teams" fail by default.
    - **Proof beats adjectives:** every value claim ships with a number, a customer name,
      or a mechanism ("because it reads the ledger directly, not a CSV").

    ## Output format
    ```
    # Positioning — <product>
    **One-liner:** <≤ 15 words>
    **Category:** <existing / subsegment / new> — <why this frame>

    ## Canvas
    - Alternatives: …  - Unique attributes: …  - Value (+proof): …
    - Best-fit customers: …  - Category: …

    ## Differentiation
    | Attribute | Us | <Alt 1> | <Alt 2> | Importance | Class |
    |---|---|---|---|---|---|
    Lead with: … · Table stakes: … · Don't mention: …

    ## Statement (Moore)
    For … who …, <product> is a … that …. Unlike …, we ….

    ## We are / we are not
    - We are … · We are not …

    ## Messages tested
    | Line | Score | Verdict |
    ```

    ## Anti-patterns
    - Positioning against the market leader when your buyers actually use a spreadsheet.
    - Leading with a unique attribute nobody values (trivia).
    - Inventing a category to avoid comparison; buyers compare anyway.
    - Claims a competitor could copy verbatim.
    - Three target customers "so we don't limit ourselves" — that's no target.
    - Confusing mission ("empower every business") with positioning.
    """,
)

VAGUE = re.compile(r"\b(better|best|easy|easier|easiest|simple|simpler|fast|faster|powerful|modern|seamless|robust|intuitive|innovative|all-in-one|all in one|world-class|cutting-edge|next-gen|smart|efficient|effective|great|amazing|leading|comprehensive|holistic|end-to-end|scalable|flexible|user-friendly|streamlined|optimized|optimised)\b", re.I)
GENERIC_CLAIMS = [
    "all-in-one", "all in one", "modern teams", "built for teams", "easy to use", "powerful", "seamless", "the platform for",
    "the future of", "reimagine", "reimagining", "empower", "supercharge", "next generation", "world-class", "best-in-class",
    "for everyone", "any business", "businesses of all sizes", "trusted by thousands", "revolutionary", "game-changing", "smarter way",
    "better way", "simplify", "streamline", "workflow", "collaboration platform", "growth platform", "insights", "unlock",
]
CANVAS_FIELDS = ["competitive_alternatives", "unique_attributes", "value", "best_fit_customers", "market_category"]


def _as_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        parts = [p.strip(" -•\t") for p in re.split(r"\n|;", v) if p.strip(" -•\t")]
        return parts
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    return [str(v)]


@AGENT.tool
def canvas_check(canvas: dict) -> dict:
    """Validate a positioning canvas (Dunford's five components) for missing pieces, thin sections and vague claims.

    Call with the draft canvas; fix every gap before scoring differentiation.

    Args:
        canvas: {"competitive_alternatives": [...], "unique_attributes": [...], "value": [...], "best_fit_customers": [...], "market_category": str, "trends": [...] (optional)}. Lists may be strings separated by newlines.
    """
    if not isinstance(canvas, dict) or not canvas:
        raise ToolError("canvas must be an object with the five components.")
    sections = {}
    gaps, vague_hits = [], []
    minimums = {"competitive_alternatives": 2, "unique_attributes": 3, "value": 2, "best_fit_customers": 2, "market_category": 1}
    for field in CANVAS_FIELDS:
        items = _as_list(canvas.get(field))
        sections[field] = items
        if len(items) < minimums[field]:
            gaps.append(f"{field}: {len(items)} item(s), need ≥ {minimums[field]}" + (" (include 'spreadsheet' / 'do nothing' if true)" if field == "competitive_alternatives" else ""))
        for it in items:
            v = sorted({m.lower() for m in VAGUE.findall(it)})
            if v and field in ("unique_attributes", "value", "market_category"):
                has_mechanism = bool(re.search(r"\d|because|by |via |without|only|first|built on|reads|connects|runs|in \d", it, re.I))
                if not has_mechanism:
                    vague_hits.append({"section": field, "item": it, "vague_words": v, "fix": "Add the mechanism or a number: what specifically makes it so?"})
    alts = [a.lower() for a in sections["competitive_alternatives"]]
    if alts and not any(re.search(r"spreadsheet|excel|manual|do nothing|status quo|in-house|email|nothing|homegrown|agency|hire", a) for a in alts):
        gaps.append("competitive_alternatives lists only named products — most buyers' real alternative is a spreadsheet, a person, or doing nothing. Add it if true.")
    attrs = sections["unique_attributes"]
    vals = sections["value"]
    if attrs and vals and len(vals) < len(attrs) / 2:
        gaps.append("value: fewer value statements than attributes — each lead attribute needs the value it enables.")
    proof = sum(1 for v in vals if re.search(r"\d|customer|case|study|e\.g\.|for example|named", v, re.I))
    if vals and proof == 0:
        gaps.append("value: no proof anywhere (numbers, named customers, examples).")
    cust = sections["best_fit_customers"]
    if cust and all(re.search(r"^(small|mid|large|enterprise|smb|companies|businesses|teams)\b", c, re.I) and not re.search(r"who|that|with|using|when|because", c, re.I) for c in cust):
        gaps.append("best_fit_customers: only size/firmographics — add behavioural characteristics (what they already do/use/believe).")
    cat = sections["market_category"]
    cat_kind = None
    if cat:
        c0 = cat[0].lower()
        cat_kind = "subsegment" if re.search(r"\bfor\b", c0) else "new category" if re.search(r"new|first|category|pioneer", c0) else "existing category"
    trends = _as_list(canvas.get("trends"))
    filled = sum(1 for f in CANVAS_FIELDS if sections[f])
    score = round(100 * (filled / len(CANVAS_FIELDS)) * (1 - min(0.5, 0.1 * len(gaps))) * (1 - min(0.3, 0.05 * len(vague_hits))))
    return {
        "sections": sections,
        "trends": trends,
        "category_kind": cat_kind,
        "gaps": gaps,
        "vague_claims": vague_hits,
        "completeness_score": score,
        "ready": not gaps and not vague_hits,
        "summary": f"Canvas {score}/100: {filled}/5 sections, {len(gaps)} gap(s), {len(vague_hits)} vague claim(s)." + (" Ready for differentiation scoring." if not gaps and not vague_hits else ""),
    }


@AGENT.tool
def differentiation_matrix(attributes: list[dict], competitors: list[str] = []) -> dict:
    """Classify each attribute as lead / table stakes / trivia / fix-or-reframe from 0-5 ratings vs competitors and importance.

    Call after the canvas passes; lead with the "lead" attributes.

    Args:
        attributes: List of {"attribute": str, "us": 0-5, "competitors": {"Name": 0-5, ...}, "importance": 1-5} (importance = how much the best-fit customer cares).
        competitors: Optional list of competitor names to enforce (missing ratings are flagged).
    """
    if not attributes or len(attributes) > 60:
        raise ToolError("Provide 1-60 attributes.")
    rows, missing = [], []
    lead_score = total_weight = 0.0
    for raw in attributes:
        if not isinstance(raw, dict) or not str(raw.get("attribute", "")).strip():
            raise ToolError("Each attribute needs an 'attribute' name.")
        name = str(raw["attribute"]).strip()
        try:
            us = float(raw.get("us"))
            imp = float(raw.get("importance", 3))
            comps = {str(k): float(v) for k, v in (raw.get("competitors") or {}).items()}
        except (TypeError, ValueError):
            raise ToolError(f"{name}: 'us', 'importance' and competitor ratings must be numbers.") from None
        if not 0 <= us <= 5 or not 1 <= imp <= 5 or any(not 0 <= v <= 5 for v in comps.values()):
            raise ToolError(f"{name}: ratings 0-5, importance 1-5.")
        for c in competitors:
            if c not in comps:
                missing.append(f"{name}: no rating for {c}")
        best_comp = max(comps.values()) if comps else 0.0
        gap = us - best_comp
        if gap >= 1.5:
            uniqueness = "unique"
        elif gap >= 0.5:
            uniqueness = "ahead"
        elif gap > -0.5:
            uniqueness = "parity"
        else:
            uniqueness = "behind"
        important = imp >= 4
        if uniqueness in ("unique", "ahead") and important:
            cls = "lead"
        elif uniqueness == "parity" and important:
            cls = "table stakes"
        elif uniqueness in ("unique", "ahead") and not important:
            cls = "trivia" if imp <= 2 else "supporting"
        elif uniqueness == "behind" and important:
            cls = "fix or reframe"
        else:
            cls = "irrelevant"
        weight = imp
        total_weight += weight
        lead_score += weight * max(0.0, gap) / 5
        rows.append({"attribute": name, "us": us, "best_competitor": max(comps, key=comps.get) if comps else None, "best_competitor_score": best_comp, "gap": round(gap, 1), "importance": imp, "uniqueness": uniqueness, "class": cls})
    order = {"lead": 0, "fix or reframe": 1, "table stakes": 2, "supporting": 3, "trivia": 4, "irrelevant": 5}
    rows.sort(key=lambda r: (order[r["class"]], -r["importance"], -r["gap"]))
    by_class: dict[str, list[str]] = {}
    for r in rows:
        by_class.setdefault(r["class"], []).append(r["attribute"])
    diff_index = round(100 * lead_score / total_weight) if total_weight else 0
    leads = by_class.get("lead", [])
    advice = []
    if not leads:
        advice.append("No lead attributes: either narrow the best-fit customer (so importance rises on what you're unique at) or the product needs a wedge feature.")
    if len(leads) > 3:
        advice.append(f"{len(leads)} lead attributes — pick the top 2-3; more dilutes the message.")
    if by_class.get("fix or reframe"):
        advice.append("Behind on important attributes: " + ", ".join(by_class["fix or reframe"]) + " — reposition toward customers who care less about these, or close the gap.")
    return {
        "matrix": rows,
        "by_class": by_class,
        "lead_with": leads[:3],
        "differentiation_index": diff_index,
        "missing_ratings": missing,
        "advice": advice,
        "summary": f"Differentiation index {diff_index}/100. Lead: {', '.join(leads[:3]) or 'none'}. Table stakes: {len(by_class.get('table stakes', []))}. Fix/reframe: {len(by_class.get('fix or reframe', []))}.",
    }


@AGENT.tool
def positioning_statement(target: str, need: str, product: str, category: str, key_benefit: str, primary_alternative: str, differentiator: str) -> dict:
    """Assemble Moore's positioning statement, a one-liner and an "X for Y" line, and lint them for vagueness, length and overlap.

    Call once the lead attributes are chosen. Fix the lint before presenting.

    Args:
        target: Who it's for, with a behavioural trait ("ops leads at 50-500 person SaaS companies who run onboarding in spreadsheets").
        need: The need or problem statement.
        product: Product name.
        category: The market category / frame ("client onboarding platform").
        key_benefit: The primary value, ideally with a number.
        primary_alternative: The main competitive alternative ("spreadsheets and email" or a named product).
        differentiator: The unique attribute + mechanism ("connects to the ledger directly, so numbers are never stale").
    """
    fields = {"target": target, "need": need, "product": product, "category": category, "key_benefit": key_benefit, "primary_alternative": primary_alternative, "differentiator": differentiator}
    for k, v in fields.items():
        if not str(v or "").strip():
            raise ToolError(f"{k} is empty.")
        if len(str(v)) > 500:
            raise ToolError(f"{k} is over 500 chars.")
    t, n, p, c, b, a, d = (str(v).strip().rstrip(".") for v in fields.values())
    # Avoid "For X who … who …" when the target already carries its behavioural "who" clause.
    n_clause = re.sub(r"^who\s+", "", n, flags=re.I)
    joiner = " and " if re.search(r"\bwho\b", t, re.I) else " who "
    has_article = re.match(r"^(a|an|the)\s", c, re.I)
    art = "" if has_article else ("an " if re.match(r"^[aeiou]", c, re.I) else "a ")
    moore = f"For {t}{joiner}{n_clause}, {p} is {art}{c} that {b}. Unlike {a}, we {d}."
    one_liner = f"{p}: {'' if has_article else 'the '}{c} for {t} — {b}."
    x_for_y = f"{p} is {art}{c} for {t}."
    lint = []
    words_moore = len(text.words(moore))
    if words_moore > 60:
        lint.append(f"Moore statement is {words_moore} words; cut to ≤ 60.")
    if len(text.words(one_liner)) > 22:
        lint.append("One-liner over 22 words — tighten the benefit or the target.")
    for k in ("key_benefit", "differentiator", "category"):
        v = fields[k]
        vg = sorted({m.lower() for m in VAGUE.findall(v)})
        if vg and not re.search(r"\d|because|by |via |without|only|reads|connects|runs", v, re.I):
            lint.append(f"{k} uses vague words ({', '.join(vg)}) with no mechanism or number.")
    if not re.search(r"\d", b) and not re.search(r"\d", d):
        lint.append("No number anywhere in benefit or differentiator — add one proof point.")
    if not re.search(r"\b(who|that|with|using|when|running|struggling)\b", t, re.I):
        lint.append("Target has no behavioural trait — add 'who …' so it's not just a job title.")
    bw = set(w.lower() for w in text.words(b)) - text.STOPWORDS
    dw = set(w.lower() for w in text.words(d)) - text.STOPWORDS
    if bw and dw and len(bw & dw) / len(bw | dw) > 0.5:
        lint.append("Benefit and differentiator say the same thing — the differentiator should be the *how*, the benefit the *what you get*.")
    for gc in GENERIC_CLAIMS:
        if gc in moore.lower():
            lint.append(f"Generic claim '{gc}' — a competitor could say it. Replace with your mechanism.")
            break
    if a.lower() in (p.lower(),):
        lint.append("Alternative equals product name.")
    return {
        "moore_statement": moore,
        "one_liner": one_liner,
        "x_for_y": x_for_y,
        "word_counts": {"moore": words_moore, "one_liner": len(text.words(one_liner))},
        "lint": lint,
        "ready": not lint,
        "summary": f"Statement built ({words_moore} words); {len(lint)} lint issue(s)." + (" " + lint[0] if lint else " Ready."),
    }


@AGENT.tool
def message_clarity(messages: list[str]) -> dict:
    """Score positioning lines 0-100 for specificity vs generic claims, jargon, readability and length; rank them.

    Call on the one-liner, homepage headline and alternatives; keep the top scorer, rewrite the rest.

    Args:
        messages: Candidate lines (headline, one-liner, tagline). 1-50 items.
    """
    if not messages or len(messages) > 50:
        raise ToolError("Provide 1-50 messages.")
    rows = []
    for raw in messages:
        s = require_text(str(raw), "message", 2000).strip()
        low = s.lower()
        ws = text.words(s)
        score = 60
        notes = []
        generic = [g for g in GENERIC_CLAIMS if g in low]
        if generic:
            score -= min(40, 15 * len(generic))
            notes.append(f"generic: {', '.join(generic[:3])}")
        vague = sorted({m.lower() for m in VAGUE.findall(s)})
        if vague:
            score -= min(20, 5 * len(vague))
            notes.append(f"vague: {', '.join(vague[:3])}")
        if re.search(r"\d", s):
            score += 15
            notes.append("has a number")
        who = bool(re.search(r"\bfor\b\s+\w+", low)) or bool(re.search(r"\b(teams|founders|clinics|agencies|marketers|developers|ops|finance|hr|sales|managers|freelancers|schools|restaurants|shops|creators)\b", low))
        if who:
            score += 10
            notes.append("names who it's for")
        else:
            notes.append("no audience named")
        what = bool(re.search(r"\b(app|software|platform|tool|service|api|plugin|crm|marketplace|system|dashboard|assistant|agent|network|course|kit)\b", low)) or bool(re.search(r"\b(is|helps|lets|turns|replaces)\b", low))
        if what:
            score += 5
        else:
            notes.append("doesn't say what it is")
        mech = bool(re.search(r"\b(because|by|via|without|instead of|unlike|so you|so that|directly|automatically)\b", low))
        if mech:
            score += 8
            notes.append("has a mechanism/contrast")
        n = len(ws)
        if n > 20:
            score -= 10
            notes.append(f"{n} words — too long")
        elif n < 4:
            score -= 10
            notes.append("too short to say anything")
        rd = text.readability(s)
        if rd["fk_grade"] and rd["fk_grade"] > 10:
            score -= 8
            notes.append(f"grade {rd['fk_grade']}")
        competitor_copyable = bool(generic) or (not who and not mech and not re.search(r"\d", s))
        score = max(0, min(100, score))
        rows.append({"message": s, "score": score, "words": n, "competitor_could_say_it": competitor_copyable, "notes": notes})
    rows.sort(key=lambda r: -r["score"])
    best = rows[0]
    return {
        "ranked": rows,
        "best": best["message"],
        "summary": f"Best: '{best['message']}' ({best['score']}/100). {sum(1 for r in rows if r['competitor_could_say_it'])} of {len(rows)} lines could be said by a competitor.",
    }
