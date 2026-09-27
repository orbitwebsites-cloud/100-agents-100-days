"""Case Study Writer — customer stories with numbers that are right and framed to sell."""

from __future__ import annotations

import math
import re

from ...core import Agent, ToolError
from ...lib import text
from . import _common as c

AGENT = Agent(
    slug="case-study-writer",
    name="Case Study Writer",
    category="content",
    tagline="Turn a customer win into a case study with correct, credible numbers and a story where the customer is the hero.",
    description=(
        "Writes B2B case studies the way the best content marketers do: challenge → solution → results, "
        "customer as hero, every metric formatted correctly (percent change vs percentage points vs x-fold, "
        "small-base warnings, rounding rules), a headline built on the strongest verified number, pull "
        "quotes scored for specificity, and an ROI summary the buyer's finance team will accept. Lints the "
        "draft for vague quantifiers, marketing-speak and missing sections before it ships."
    ),
    triggers=[
        "write a case study from these notes / this interview",
        "format these before/after metrics for a case study",
        "is this a 2x or a 100% increase — how do I phrase it",
        "review my case study draft",
        "calculate the ROI for a customer story",
        "pick the best customer quote for a case study",
    ],
    examples=[
        "Here's the interview transcript with Acme's ops lead plus their before/after numbers. Write the case study.",
        "Support tickets went from 1,240/month to 610, CSAT from 71% to 88%. Format these for the headline and results box.",
        "Which of these six quotes should be the pull quote, and why?",
    ],
    connectors=["HubSpot", "Notion", "Google Docs", "Salesforce", "Webflow"],
    playbook="""
    ## Standard
    You are the case-study lead at a B2B company whose stories close deals because sales can
    hand them to a sceptical buyer. Excellent means: a specific, verifiable headline number; a
    story a prospect recognises as their own situation; the customer, not the product, is the
    hero; and every claim survives the customer's legal review. The one metric: **would a
    prospect forward this to their boss as evidence?**

    ## Intake
    You need: the customer (company, role of the champion), the before/after numbers, and what
    they did with the product. Assume a 700-1,200 word written case study with a results box
    unless told otherwise. If you have an interview transcript, mine it for numbers, quotes
    and the "moment it clicked". Ask only if there are no numbers at all — a case study
    without a number is a testimonial; say so and offer to write that instead.

    ## Procedure
    1. **Get the numbers right first.** List every before/after pair and call
       `case_study_writer__format_metrics`. It computes the change, decides between percent,
       percentage points and x-fold framing, applies rounding rules, flags small bases and
       percent-of-percent traps, and ranks the metrics by impact. The top-ranked metric
       becomes the headline; the next 2-3 become the results box. Never compute these in your
       head — "12% to 31%" is 19 points and 2.6x, *not* a 158% increase in the headline.
    2. **If cost and benefit are known**, call `case_study_writer__roi_summary` for ROI %,
       net gain and payback months. Present ROI only when the customer confirmed the inputs;
       otherwise show the operational metrics only.
    3. **Pick the quotes.** Call `case_study_writer__quote_check` with every candidate quote.
       Use the highest-scoring one as the pull quote (near the top, after the headline) and
       one specific quote per section. Rewrite nothing inside quotation marks; if a quote
       needs trimming, use ellipses and get sign-off.
    4. **Write the story** in this order: Headline (customer + number + outcome) → Snapshot
       box (industry, size, product used, results) → The situation (their world before: the
       pain in their words, what they had tried) → The turning point (why they chose to act,
       what the decision looked like) → What they did (the solution as *their* actions; the
       product appears as the tool) → Results (numbers with time frames and baselines) →
       What's next + one-line CTA. Time frames on every number ("in 90 days", "quarter over
       quarter").
    5. **Lint.** Call `case_study_writer__story_lint` with the draft plus the customer and
       product names. Fix every flag: missing sections, no number in the first 100 words,
       product mentioned more than the customer, vague quantifiers ("significantly"),
       marketing-speak, quotes with no attribution, results without baselines or time frames.
    6. **Prepare for approval.** Produce the approval checklist: every number's source, every
       quote's speaker, logo permission, any confidential detail to redact. Then deliver; file
       to Docs/Notion/HubSpot if the connector exists.

    ## Frameworks
    - **Headline formula**: `<Customer> <verb> <metric> <by N% / to N / Nx> in <time frame> with <Product>`.
      Verbs: cut, doubled, tripled, grew, halved, recovered, eliminated. No "leverages".
    - **Framing rules**: use x-fold when the ratio ≥ 2 ("2.6x more demos"); percent for
      changes under 100%; percentage points when both numbers are rates ("from 12% to 31%,
      +19 points"); absolute numbers when the base is small ("from 3 to 11 customers", never
      "267% growth"); round to whole percents above 10, one decimal below.
    - **Hero ratio**: the customer's name should appear at least 1.5x as often as the
      product's. "They" did it; the product "enabled" it.
    - **Quote quality**: specific (a number, a named thing, a before/after), first person,
      12-35 words, sounds spoken. "Great tool, highly recommend" is not a quote — it's noise.
    - **Length**: web case study 700-1,200 words; one-pager 350-500; slide 60-80 words + 3 metrics.

    ## Output format
    ```
    # <Customer> cut <metric> by <N%> in <time frame> with <Product>

    | Industry | Size | Product | Results |
    |---|---|---|---|

    > "<pull quote — specific, ≤ 35 words>" — <Name>, <Title>, <Customer>

    ## The situation
    ## The turning point
    ## What <Customer> did
    ## The results
    - **<metric>:** <before> → <after> (<change>) in <time frame>
    ## What's next
    <one line + CTA>

    ---
    **Approval checklist:** numbers sourced ☐ · quotes attributed ☐ · logo permission ☐ · confidential details ☐
    **Metric framing notes:** <from format_metrics — e.g. "19 points, not 158%">
    ```

    ## Anti-patterns
    - Product-hero writing: "Our platform empowered Acme to…". The customer acts; the product assists.
    - Percent-of-percent inflation ("158% increase in conversion") and small-base percentages.
    - Numbers without baselines or time frames ("saved 40%" — of what, since when?).
    - Vague quantifiers: significantly, dramatically, countless, a lot. Replace with the number or cut.
    - Quotes that sound like marketing copy; quotes with no name and title.
    - Burying the result on page 2. Headline and pull quote carry the number.
    - Publishing without approval. Every case study goes to the customer first.
    """,
)


def _fmt_num(v: float, unit: str) -> str:
    u = (unit or "").strip()
    if abs(v) >= 1000 and float(v).is_integer():
        s = f"{int(v):,}"
    elif float(v).is_integer():
        s = str(int(v))
    else:
        s = f"{v:,.1f}" if abs(v) >= 10 else f"{v:,.2f}".rstrip("0").rstrip(".")
    if u in ("$", "€", "£"):
        return f"{u}{s}"
    if u in ("%", "pp", "pts"):
        return f"{s}%"
    return f"{s} {u}".strip()


def _fmt_pct(p: float) -> str:
    return f"{round(p)}%" if abs(p) >= 10 else f"{round(p, 1)}%"


@AGENT.tool
def format_metrics(metrics: list[dict]) -> dict:
    """Compute and frame before/after metrics: % change, percentage points, x-fold, direction, rounding, small-base and percent-of-percent warnings; ranks by impact and drafts headline phrasings.

    Call before writing anything with a number in it. Each metric: {"name", "before",
    "after", "unit" ("%", "$", "hrs", "tickets"…), "higher_is_better" (default true),
    "timeframe" (optional, e.g. "90 days")}.

    Args:
        metrics: List of metric objects (1-50) with name, before, after, optional unit, higher_is_better and timeframe.
    """
    if not isinstance(metrics, list) or not metrics:
        raise ToolError("metrics must be a non-empty list of {name, before, after, ...}.")
    if len(metrics) > 50:
        raise ToolError("Max 50 metrics per call.")
    rows = []
    for i, m in enumerate(metrics, 1):
        if not isinstance(m, dict):
            raise ToolError(f"Metric {i} must be an object.")
        name = str(m.get("name", "")).strip() or f"metric {i}"
        try:
            before = float(str(m.get("before", "")).replace(",", "").replace("$", "").replace("%", ""))
            after = float(str(m.get("after", "")).replace(",", "").replace("$", "").replace("%", ""))
        except ValueError:
            raise ToolError(f"Metric '{name}': before/after must be numbers.") from None
        unit = str(m.get("unit", "") or "").strip()
        hib = m.get("higher_is_better", True)
        hib = True if hib is None else bool(hib)
        tf = str(m.get("timeframe", "") or "").strip()
        is_rate = unit in ("%", "pp", "pts", "percent")
        delta = after - before
        warnings = []
        pct_change = None if before == 0 else 100.0 * delta / abs(before)
        if before == 0:
            warnings.append("Before is 0 — no percent change exists; state the absolute numbers.")
        improved = (delta > 0) if hib else (delta < 0)
        if delta == 0:
            improved = None
        fold = None
        if before > 0 and after > 0:
            fold = after / before if hib else before / after
        if not is_rate and unit not in ("$", "€", "£") and 0 < before < 20:
            warnings.append(f"Small base ({_fmt_num(before, unit)}) — say 'from {_fmt_num(before, unit)} to {_fmt_num(after, unit)}', not a percent.")
        if is_rate:
            warnings.append(f"Both numbers are rates — say '{round(abs(delta), 1):g} points' ({before:g}% → {after:g}%), not '{_fmt_pct(abs(pct_change)) if pct_change is not None else '?'} {'increase' if delta > 0 else 'decrease'}'.")
        # choose framing
        framing = "absolute"
        phrase = f"from {_fmt_num(before, unit)} to {_fmt_num(after, unit)}"
        if is_rate:
            framing = "percentage points"
            phrase = f"from {before:g}% to {after:g}% ({'+' if delta > 0 else ''}{round(delta, 1):g} points)"
        elif before > 0 and 0 < before < 20 and unit not in ("$", "€", "£"):
            framing = "absolute"
        elif fold is not None and fold >= 2:
            framing = "x-fold"
            fx = math.floor(fold * 10) / 10
            span = f"(from {_fmt_num(before, unit)} to {_fmt_num(after, unit)})"
            if 1.95 <= fold < 2.1:
                phrase = f"{'doubled' if hib else 'halved'} {name} {span}"
            elif 2.95 <= fold < 3.1:
                phrase = f"{'tripled' if hib else 'cut'} {name} {'' if hib else '3x '}{span}".replace("  ", " ")
            elif hib:
                phrase = f"{fx:g}x more {name} {span}"
            else:
                phrase = f"cut {name} {fx:g}x {span}"
        elif pct_change is not None:
            framing = "percent"
            verb = ("grew" if delta > 0 else "cut") if hib else ("cut" if delta < 0 else "grew")
            if hib and delta < 0:
                verb = "fell"
            phrase = f"{verb} {name} {_fmt_pct(abs(pct_change))} (from {_fmt_num(before, unit)} to {_fmt_num(after, unit)})"
            if abs(pct_change) == 50 and delta < 0:
                phrase = f"halved {name} (from {_fmt_num(before, unit)} to {_fmt_num(after, unit)})"
            if abs(pct_change) == 100 and delta > 0:
                phrase = f"doubled {name} (from {_fmt_num(before, unit)} to {_fmt_num(after, unit)})"
        if tf:
            phrase += f" in {tf}"
        if improved is False:
            warnings.append("This metric moved the wrong way — do not headline it; explain or omit.")
        impact = 0.0
        if improved:
            impact = (fold if fold else 1.0) if not is_rate else 1 + abs(delta) / 25
            if before < 20 and not is_rate and unit not in ("$", "€", "£"):
                impact *= 0.5
        rows.append({
            "name": name, "before": before, "after": after, "unit": unit, "timeframe": tf or None,
            "delta": round(delta, 2), "pct_change": round(pct_change, 1) if pct_change is not None else None,
            "points_change": round(delta, 1) if is_rate else None,
            "fold": round(fold, 2) if fold else None, "improved": improved,
            "framing": framing, "phrase": phrase, "warnings": warnings, "_impact": impact,
        })
    ranked = sorted(rows, key=lambda r: -r["_impact"])
    for r in rows:
        r.pop("_impact")
    headline = ranked[0]
    return {
        "metrics": rows,
        "ranked_names": [r["name"] for r in ranked],
        "headline_metric": headline["name"],
        "headline_phrase": headline["phrase"],
        "results_box": [r["phrase"] for r in ranked[1:4]],
        "warnings": [f"{r['name']}: {w}" for r in rows for w in r["warnings"]],
        "summary": f"Headline on '{headline['name']}': {headline['phrase']}." + (f" {len([w for r in rows for w in r['warnings']])} framing warning(s)." if any(r["warnings"] for r in rows) else ""),
    }


@AGENT.tool
def roi_summary(annual_benefit: float, annual_cost: float, one_time_cost: float = 0.0, months: int = 12) -> dict:
    """ROI %, net gain, payback months and benefit-cost ratio for a customer story over a given period.

    Call only with customer-confirmed inputs. Benefit = savings + incremental gross profit
    attributable to the product; cost = subscription + implementation.

    Args:
        annual_benefit: Annualised value the customer gained (savings + incremental profit).
        annual_cost: Annual recurring cost of the product/service.
        one_time_cost: Implementation, migration or training cost paid once.
        months: Period to evaluate over (1-60; default 12).
    """
    if annual_benefit < 0 or annual_cost < 0 or one_time_cost < 0:
        raise ToolError("Amounts cannot be negative.")
    if not 1 <= months <= 60:
        raise ToolError("months must be 1-60.")
    if annual_cost == 0 and one_time_cost == 0:
        raise ToolError("Need a non-zero cost to compute ROI.")
    frac = months / 12.0
    gain = annual_benefit * frac
    cost = one_time_cost + annual_cost * frac
    net = gain - cost
    roi = 100.0 * net / cost
    monthly_net = (annual_benefit - annual_cost) / 12.0
    payback = None
    if monthly_net > 0:
        payback = one_time_cost / monthly_net if one_time_cost else 0.0
        if payback == 0.0:
            payback = round(annual_cost / annual_benefit * 12, 1) if annual_benefit else None
    ratio = gain / cost if cost else None
    phrasing = f"{round(roi):,}% ROI over {months} months" if roi >= 0 else f"negative ROI ({round(roi):,}%) over {months} months"
    if payback is not None and payback > 0:
        phrasing += f"; paid back in {round(payback, 1):g} months"
    notes = []
    if roi > 1000:
        notes.append("ROI above 1,000% reads as implausible to finance — show the inputs or use the benefit-cost ratio.")
    if payback is None:
        notes.append("Benefit does not exceed cost annually — no payback; do not claim ROI.")
    return {
        "months": months,
        "total_benefit": round(gain, 2),
        "total_cost": round(cost, 2),
        "net_gain": round(net, 2),
        "roi_pct": round(roi, 1),
        "benefit_cost_ratio": round(ratio, 2) if ratio is not None else None,
        "payback_months": round(payback, 1) if payback is not None else None,
        "monthly_net": round(monthly_net, 2),
        "phrasing": phrasing,
        "notes": notes,
        "verdict": phrasing + ".",
    }


@AGENT.tool
def quote_check(quotes: list[str]) -> dict:
    """Score customer quotes 0-100 for specificity (numbers, named things, before/after), spoken voice, length (12-35 words) and marketing-speak; picks the pull quote.

    Call with every candidate quote. Never edit inside the quotation marks — pick, don't polish.

    Args:
        quotes: Candidate quotes as spoken (1-40).
    """
    if not isinstance(quotes, list) or not quotes:
        raise ToolError("quotes must be a non-empty list.")
    if len(quotes) > 40:
        raise ToolError("Max 40 quotes per call.")
    scored = []
    for q in quotes:
        q = str(q or "").strip().strip('"“”')
        if not q:
            raise ToolError("Empty quote in the list.")
        ws = text.words(q)
        n = len(ws)
        score = 40
        reasons = []
        if re.search(r"\d", q):
            score += 20
            reasons.append("+20 has a number")
        if re.search(r"\b(from|to|before|after|now|used to|instead of|went from|down from|up from)\b", q, re.I):
            score += 10
            reasons.append("+10 before/after contrast")
        if c.proper_nouns(q):
            score += 8
            reasons.append("+8 names something specific")
        if re.search(r"\b(i|we|my|our|me|us)\b", q, re.I):
            score += 6
            reasons.append("+6 first person")
        if 12 <= n <= 35:
            score += 10
            reasons.append(f"+10 {n} words — pull-quote length")
        elif n < 8:
            score -= 10
            reasons.append(f"-10 {n} words — too thin")
        elif n > 50:
            score -= 8
            reasons.append(f"-8 {n} words — trim with ellipses (get sign-off)")
        weak = c.find_phrases(q, c.WEAK_PRAISE)
        if weak:
            pen = min(25, 8 * len(weak))
            score -= pen
            reasons.append(f"-{pen} generic praise: {', '.join(w['phrase'] for w in weak[:3])}")
        buzz = c.find_phrases(q, c.CLICHES + ["solution", "solutions", "empower", "empowers", "streamline", "streamlined", "synergies", "cutting-edge", "innovative", "world-class", "robust", "scalable"])
        if buzz:
            score -= 8
            reasons.append(f"-8 sounds like marketing copy ({buzz[0]['phrase']})")
        if re.search(r"\b(product|platform|tool|software|solution)\b", q, re.I) and not re.search(r"\d", q):
            score -= 4
            reasons.append("-4 about the product, not the outcome")
        if q.count(",") >= 4 or n > 40:
            score -= 3
            reasons.append("-3 doesn't sound spoken")
        if q.strip().endswith(("!", "!!")):
            score -= 3
            reasons.append("-3 exclamation mark")
        scored.append({"quote": q, "words": n, "score": max(0, min(100, score)), "reasons": reasons})
    ranked = sorted(scored, key=lambda s: -s["score"])
    return {
        "ranked": ranked,
        "pull_quote": ranked[0]["quote"],
        "pull_quote_score": ranked[0]["score"],
        "usable": [s["quote"] for s in ranked if s["score"] >= 60],
        "discard": [s["quote"] for s in ranked if s["score"] < 45],
        "verdict": f"Pull quote ({ranked[0]['score']}/100): \"{ranked[0]['quote'][:90]}\"",
    }


SECTION_KEYS = {
    "challenge": r"\b(challenge|problem|situation|before|background|the pain|context)\b",
    "solution": r"\b(solution|what (they|we|[A-Z]\w+) did|approach|implementation|the fix|turning point|how)\b",
    "results": r"\b(results?|outcomes?|impact|after|the numbers|by the numbers)\b",
}


@AGENT.tool
def story_lint(draft: str, customer_name: str, product_name: str = "") -> dict:
    """Lint a case-study draft: required sections, number in the first 100 words, customer-vs-product mention ratio (hero check), vague quantifiers, marketing-speak, unattributed quotes, results without baselines/time frames, length.

    Call on the finished draft; fix every flag before approval.

    Args:
        draft: The case study in markdown.
        customer_name: The customer's company name as used in the draft.
        product_name: Your product/company name as used in the draft (optional; enables the hero-ratio check).
    """
    c.guard(draft, "Draft")
    if not customer_name or not customer_name.strip():
        raise ToolError("customer_name is required.")
    plain = c.strip_markdown(draft)
    ws = text.words(plain)
    total = len(ws)
    if total < 50:
        raise ToolError("Draft has fewer than 50 words.")
    flags: list[str] = []
    secs = c.sections(draft)
    heads = " | ".join(s["title"] for s in secs if s["level"] > 0)
    found = {k: bool(re.search(pat, heads, re.I)) for k, pat in SECTION_KEYS.items()}
    missing = [k for k, v in found.items() if not v]
    if missing and heads:
        flags.append(f"Missing section(s): {', '.join(missing)} — readers and sales scan for challenge / solution / results.")
    elif not heads:
        flags.append("No headings — structure as challenge → solution → results.")
    first100 = " ".join(ws[:100])
    if not re.search(r"\d", first100):
        flags.append("No number in the first 100 words — the headline or the first paragraph must carry the result.")
    title_line = next((ln.strip("# ").strip() for ln in draft.splitlines() if ln.strip()), "")
    if title_line and not re.search(r"\d", title_line):
        flags.append("Headline has no number.")
    cust = len(re.findall(r"(?<!\w)" + re.escape(customer_name.strip()) + r"(?!\w)", plain, re.I))
    prod = len(re.findall(r"(?<!\w)" + re.escape(product_name.strip()) + r"(?!\w)", plain, re.I)) if product_name.strip() else 0
    we_our = sum(1 for w in ws if w.lower() in ("we", "our", "us"))
    if cust == 0:
        flags.append(f"'{customer_name}' never appears in the draft.")
    if product_name.strip() and prod and cust < 1.5 * prod:
        flags.append(f"Hero check: '{customer_name}' ×{cust} vs '{product_name}' ×{prod} — the customer should appear ≥ 1.5x as often.")
    if we_our > cust and cust:
        flags.append(f"'We/our/us' ×{we_our} outnumber the customer ×{cust} — rewrite with the customer as the actor.")
    vague = c.find_phrases(plain, c.VAGUE_QUANTIFIERS)
    if vague:
        flags.append("Vague quantifiers: " + ", ".join(f"{v['phrase']} ×{v['count']}" for v in vague[:6]) + " — replace with the number or cut.")
    buzz = c.find_phrases(plain, c.CLICHES + c.AI_TELLS[:30])
    if buzz:
        flags.append("Marketing-speak/clichés: " + ", ".join(b["phrase"] for b in buzz[:6]) + ".")
    quotes = re.findall(r"[\"“]([^\"”]{20,600})[\"”]", draft)
    unattributed = 0
    for q in quotes:
        idx = draft.find(q)
        after = draft[idx + len(q): idx + len(q) + 160]
        if not re.search(r"(—|–|-|,)\s*[A-Z][\w.'-]+|\b(said|says|explains|explained|adds|added|notes|noted|recalls)\b", after):
            unattributed += 1
    if unattributed:
        flags.append(f"{unattributed} quote(s) without a name/title attribution right after them.")
    if not quotes:
        flags.append("No customer quotes — at least one pull quote and one per section.")
    results_sec = next((s for s in secs if re.search(SECTION_KEYS["results"], s["title"], re.I)), None)
    if results_sec:
        body = c.strip_markdown(results_sec["body"])
        pct_only = len(re.findall(r"\b\d+(?:\.\d+)?%", body))
        from_to = len(re.findall(r"\bfrom\b[^.\n]{1,60}\bto\b", body, re.I))
        timeframes = len(re.findall(r"\b(\d+\s*(?:days?|weeks?|months?|quarters?|years?)|q[1-4]|quarter over quarter|year over year|yoy|qoq|within|since)\b", body, re.I))
        if pct_only and not from_to:
            flags.append("Results give percentages without baselines — add 'from X to Y' for each.")
        if not timeframes:
            flags.append("Results have no time frame — add 'in 90 days' / 'quarter over quarter'.")
        if not re.search(r"\d", body):
            flags.append("Results section has no numbers.")
    if total < 500:
        flags.append(f"{total} words — short for a web case study (700-1,200); fine for a one-pager.")
    elif total > 1500:
        flags.append(f"{total} words — long; cut toward 1,200 or move detail to an appendix.")
    if not re.search(r"\b(get started|book a demo|talk to|see how|learn how|contact|try|request|schedule)\b", plain[-400:], re.I):
        flags.append("No CTA in the close.")
    return {
        "words": total,
        "sections_found": found,
        "customer_mentions": cust,
        "product_mentions": prod,
        "we_our_mentions": we_our,
        "hero_ratio": round(cust / prod, 2) if prod else None,
        "quotes": len(quotes),
        "unattributed_quotes": unattributed,
        "vague_quantifiers": vague[:10],
        "flags": flags,
        "ready_for_approval": not flags,
        "verdict": "Draft passes lint — send for customer approval." if not flags else f"{len(flags)} fix(es) before approval.",
    }
