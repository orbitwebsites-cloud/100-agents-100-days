"""Pitch Deck Coach — investor-grade deck structure, market sizing that survives diligence, and raise math."""

from __future__ import annotations

import re

from ...core import Agent, ToolError
from ...lib import text
from ._common import check_rows, to_float

AGENT = Agent(
    slug="pitch-deck-coach",
    name="Pitch Deck Coach",
    category="product",
    tagline="Fix your deck's story, size the market bottom-up, and get the raise math right before investors do it for you.",
    description=(
        "Coaches founders the way a partner-level investor reads a deck: checks the slide sequence against "
        "the Sequoia/YC canonical structure and flags missing or misordered slides, computes TAM/SAM/SOM "
        "both top-down and bottom-up and refuses SOM claims that don't reconcile, runs the raise math "
        "(pre/post-money, dilution, option pool shuffle, runway months against burn), and audits per-slide "
        "text density so every slide survives the 3-second glance. Ends with the exact investor objections to prepare for."
    ),
    triggers=[
        "review my pitch deck / investor deck",
        "what slides should a seed deck have",
        "calculate TAM SAM SOM for my startup",
        "how much should we raise / dilution / runway math",
        "is my deck too wordy",
        "prepare me for investor questions on this deck",
    ],
    examples=[
        "Here are the 14 slide titles and bullets from our seed deck — what's missing and what's in the wrong order?",
        "We sell to dental clinics in the US at $400/month; there are ~200k clinics. Size the market properly.",
        "We want to raise $2.5M at a $12M post with a 10% option pool; burn is $140k/month. Run the numbers.",
    ],
    connectors=["Google Slides", "Notion", "Google Sheets", "Pitch", "Canva"],
    playbook="""
    ## Standard
    You are a partner at a seed fund who has read 5,000 decks. An excellent deck answers, in
    order, in under 3 minutes of reading: why this, why now, why you, how big, how it works, what
    traction proves it, and what the money buys. The one metric that matters is **meeting
    conversion** — a deck's job is to earn the next call, not to explain everything. Be direct: a
    founder is paying you to hear what an investor will think but won't say.

    ## Intake
    Proceed with what you have. Ask (max 3) only if you cannot infer: (1) stage and round size,
    (2) business model and price point, (3) current traction (revenue, users, growth rate). If the
    deck is a set of slide titles, coach structure; if it includes text, coach content too.

    ## Procedure
    1. **Check the skeleton.** Read every slide and classify it yourself into the canonical 12
       (title, problem, solution, why_now, market, product, business_model, traction,
       competition, team, financials_ask, use_of_funds; or appendix/other), then call
       `pitch_deck_coach__check_deck_structure` with the slide titles in order, the stage and your
       `slide_types`. Good decks use claim titles ("Front desks lose 11 hours a week…") that carry
       no section keyword, so without `slide_types` the tool's keyword fallback can report a slide
       as "missing" that is really there — never tell a founder a slide is missing on keyword
       matching alone. It reports missing and out-of-order slides and flags a deck over 15-18
       slides. Fix order before wording: problem before solution, traction before ask.
    2. **Size the market properly.** Call `pitch_deck_coach__market_size` with a bottom-up input
       (number of target customers × annual contract value, with a realistic capture % for SOM)
       and, if available, a top-down TAM. It returns TAM/SAM/SOM, the implied share of SAM that the
       SOM represents, and a plausibility flag (SOM > 10% of SAM within 5 years is rarely believed;
       TAM < $1B usually fails the venture-scale test — but say so, don't inflate). Present the
       bottom-up number; cite the top-down only as a sanity check.
    3. **Run the raise math.** Call `pitch_deck_coach__raise_math` with amount, valuation (pre or
       post), option pool, monthly burn and expected burn growth. It returns dilution, post-money
       ownership, runway months (target 18-24 to the next milestone), and the milestone date. If
       runway < 18 months, either raise more or cut burn — never present a 12-month plan.
    4. **Audit density.** Call `pitch_deck_coach__slide_density` with each slide's text. It flags
       slides > 40 words, > 6 bullets, font-shrinking walls of text, missing headline claims
       (the slide title should be the takeaway: "Churn fell to 1.2% after onboarding redesign",
       not "Traction"), and slides with no number at all.
    5. **Stress-test the narrative.** For each of these, write the investor's likely objection and
       the one-sentence answer the deck should contain: (a) why now, (b) why isn't this a feature of
       an incumbent, (c) what's the wedge and the expansion, (d) unit economics at scale, (e) what
       kills this company.
    6. **Deliver** in the output format: structure fixes, per-slide notes, numbers, objections. Give
       the one change that most improves the deck first.
    7. If Google Slides/Notion is connected, apply structural edits or leave comments; otherwise
       output the revised outline ready to paste.

    ## Frameworks
    - **Canonical order (Sequoia / YC):** Title → Problem → Solution → Why now → Market → Product →
      Business model → Traction → Competition → Team → Financials & ask → Use of funds. Seed decks:
      10-15 slides. Series A: add unit economics, GTM engine, and hiring plan.
    - **Bottom-up market sizing:** # of reachable customers × ACV. SAM = the segment you can
      actually serve with today's product and channels; SOM = what you can win in ~5 years given
      sales capacity — usually 1-5% of SAM for a new entrant.
    - **Headline test:** each slide's title is a complete sentence with the takeaway. If every
      title is read in sequence, the story should hold.
    - **Raise sizing:** raise = (monthly burn × 18-24 months) + buffer for the milestone that
      unlocks the next round (typically 3x revenue or the key proof point). Standard seed dilution
      15-25%; if your math implies > 30%, raise less or restructure.

    ## Output format
    ```
    # Deck review: <Company> — <stage> raise of $<X>
    **The one change:** <the single highest-leverage fix>

    ## Structure (score <n>/12 canonical slides)
    Missing: <…> · Out of order: <…> · Length: <n> slides (target 10-15)
    Proposed order: 1. … 2. … 3. …

    ## Slide-by-slide
    | # | Slide | Headline should say | Fix |

    ## Numbers
    Market: TAM $X (top-down) / SAM $Y / SOM $Z (bottom-up: N customers × $ACV × capture%)
    Raise: $A at $B post → C% dilution (incl. D% pool) · Runway E months to <milestone> by <date>

    ## Objections to prepare for
    1. "<objection>" → <one-sentence answer + which slide carries it>

    ## Scope note
    Valuation and market figures are planning estimates, not advice; verify inputs before sharing with investors.
    ```

    ## Anti-patterns
    - Top-down TAM only ("1% of a $50B market"). Investors discount it to zero; show bottom-up.
    - Solution before problem. Nobody cares about the product until they feel the pain.
    - Slide titles that are labels ("Team", "Market"). Titles are claims.
    - Competition slide with no competitors, or a 2×2 where you're top right on made-up axes. Name real alternatives including "do nothing".
    - Raising for 12 months of runway. You'll be fundraising again in 6.
    - Hiding the ask. Amount, what it buys, and the milestone it reaches — on one slide.
    - Vanity traction (sign-ups, "pipeline") instead of revenue, retention and growth rate.
    """,
)

CANON: list[tuple[str, str, str]] = [
    ("title", r"\btitle\b|\bcover\b|\bintro\b|company name|welcome", "one-line what-we-do + stage"),
    ("problem", r"\bproblems?\b|\bpain\b|\bchallenges?\b|status quo|\b(?:lose|loses|losing|lost|waste|wastes|wasting|struggle|struggles)\b", "who hurts, how much, quantified"),
    ("solution", r"\bsolution\b|what we do|our approach|how it works|product overview|\bintroducing\b|\bmeet \w+", "the insight, in one sentence"),
    ("why_now", r"why now|\btiming\b|\btrends?\b|\bshift\b|tailwinds?|inflection", "the change that makes this possible today"),
    ("market", r"\bmarket\b|\btam\b|\bsam\b|\bsom\b|market size|\bopportunity\b", "bottom-up sizing"),
    ("product", r"\bproduct\b|\bdemo\b|screenshots?|how it works|\bfeatures?\b|\bplatform\b", "2-3 screenshots, the magic moment"),
    ("business_model", r"business model|\bpricing\b|revenue model|how we make money|monetization|monetisation|unit economics", "who pays, how much, gross margin"),
    ("traction", r"\btraction\b|\bmetrics\b|\bgrowth\b|\brevenue\b|\bcustomers\b|\bresults\b|\bkpis?\b|\bmrr\b|\barr\b", "revenue/retention/growth rate chart"),
    ("competition", r"competition|competitors?|competitive|landscape|alternatives|\bmoat\b|differentiation", "real alternatives incl. do-nothing; your wedge"),
    ("team", r"\bteam\b|\bfounders?\b|who we are|about us|advisors", "why this team wins, in one line each"),
    ("financials_ask", r"\bfinancials?\b|projections?|\bforecast\b|the ask|\bask\b|\braise\b|\braising\b|\bround\b|\bfunding\b|\binvestment\b", "3-yr projection + amount"),
    ("use_of_funds", r"use of (?:funds|proceeds)|\bmilestones\b|\broadmap\b|next 18 months|what we'll do", "what the money buys and the milestone it reaches"),
]
# Checked before the generic list so a slide labelled "Use of funds: …" or "Why now: …" is not stolen by "funding"/"today".
_PRIORITY = ("use_of_funds", "why_now", "business_model", "competition", "team", "traction", "market")
STAGE_LEN = {"pre-seed": (8, 12), "seed": (10, 15), "series-a": (12, 18), "series-b": (14, 20)}


@AGENT.tool
def check_deck_structure(slide_titles: list[str], stage: str = "seed", slide_types: list[str] | None = None) -> dict:
    """Map slides to the canonical investor-deck structure; report missing, misordered and extra slides.

    Claim-style titles ("Front desks lose 11 hours a week…") often carry no section keyword, so pass
    `slide_types` with your own classification of each slide; the keyword matcher is only a fallback.

    Args:
        slide_titles: Slide titles in deck order (one per slide).
        stage: "pre-seed", "seed", "series-a" or "series-b" (sets the length target).
        slide_types: Optional canonical type per slide, same order and length as slide_titles — one of title,
            problem, solution, why_now, market, product, business_model, traction, competition, team,
            financials_ask, use_of_funds, appendix, other. Overrides keyword matching slide by slide.
    """
    titles = check_rows(slide_titles, "slide_titles", 60)
    st = str(stage).strip().lower().replace(" ", "-")
    if st not in STAGE_LEN:
        raise ToolError("stage must be pre-seed, seed, series-a or series-b.")
    valid_types = {k for k, _, _ in CANON} | {"appendix", "other"}
    if slide_types is not None:
        if len(slide_types) != len(titles):
            raise ToolError(f"slide_types has {len(slide_types)} entries but slide_titles has {len(titles)}.")
        bad = [t for t in slide_types if str(t).strip().lower() not in valid_types]
        if bad:
            raise ToolError(f"Unknown slide type(s) {bad}; use one of {', '.join(sorted(valid_types))}.")
    regexes = {k: rx for k, rx, _ in CANON}
    mapping, found_order = [], []
    for i, t in enumerate(titles, 1):
        s = str(t).strip()
        if not s:
            raise ToolError(f"slide_titles[{i - 1}] is empty.")
        match, source = None, "keyword"
        if slide_types is not None:
            match, source = str(slide_types[i - 1]).strip().lower(), "given"
            if match in {"appendix", "other"}:
                match = None
        else:
            # an explicit "Label: claim" prefix wins; then the specific sections; then the generic order
            head = s.split(":", 1)[0] if ":" in s[:40] else ""
            for key in [k for k, _, _ in CANON] if head else []:
                if re.search(regexes[key], head, re.I):
                    match = key
                    break
            if match is None:
                for key in list(_PRIORITY) + [k for k, _, _ in CANON if k not in _PRIORITY]:
                    if re.search(regexes[key], s, re.I):
                        match = key
                        break
        if i == 1 and match is None and slide_types is None:
            match = "title"
        mapping.append({"slide": i, "title": s, "canonical": match, "source": source})
        if match and match not in found_order:
            found_order.append(match)
    canon_keys = [k for k, _, _ in CANON]
    missing = [{"slide": k, "should_contain": why} for k, _, why in CANON if k not in found_order]
    # order violations: count inversions relative to canonical order
    idx = {k: i for i, k in enumerate(canon_keys)}
    inversions = [(a, b) for i, a in enumerate(found_order) for b in found_order[i + 1 :] if idx[a] > idx[b]]
    critical_order = []
    if "solution" in found_order and "problem" in found_order and found_order.index("solution") < found_order.index("problem"):
        critical_order.append("solution appears before problem")
    if "financials_ask" in found_order and "traction" in found_order and found_order.index("financials_ask") < found_order.index("traction"):
        critical_order.append("ask appears before traction")
    lo, hi = STAGE_LEN[st]
    n = len(titles)
    label_titles = [m["title"] for m in mapping if len(text.words(m["title"])) <= 2 and m["canonical"] not in ("title", None)]
    unmapped = [m["title"] for m in mapping if m["canonical"] is None]
    if unmapped and slide_types is None:
        problems_hint = f"{len(unmapped)} slide(s) matched no section keyword — classify them and re-run with slide_types before trusting 'missing'"
    else:
        problems_hint = None
    score = len(found_order)
    problems = []
    if problems_hint:
        problems.append(problems_hint)
    if missing:
        problems.append(f"missing {len(missing)} canonical slide(s): {', '.join(m['slide'] for m in missing)}")
    if critical_order:
        problems.extend(critical_order)
    if len(inversions) > 3:
        problems.append(f"{len(inversions)} order inversions vs the Sequoia/YC sequence — fine only if deliberate (e.g. traction up front because it is your strongest card); otherwise follow proposed_order")
    if n > hi:
        problems.append(f"{n} slides — over the {lo}-{hi} target for {st}; move detail to appendix")
    if n < lo:
        problems.append(f"{n} slides — under the {lo}-{hi} target; you're probably skipping traction or market")
    if len(label_titles) >= n / 2:
        problems.append(f"{len(label_titles)} slide titles are labels, not claims — rewrite as takeaways")
    proposed = [k for k in canon_keys if k in found_order or k in {m["slide"] for m in missing}]
    return {
        "slides": n,
        "stage": st,
        "length_target": f"{lo}-{hi}",
        "canonical_score": f"{score}/12",
        "mapping": mapping,
        "missing": missing,
        "order_inversions": [f"{a} before {b}" for a, b in inversions],
        "critical_order_problems": critical_order,
        "label_titles": label_titles,
        "unmapped": unmapped,
        "proposed_order": proposed,
        "problems": problems,
        "verdict": "Structure is sound — coach content next" if not problems else problems[0],
    }


@AGENT.tool
def market_size(target_customers: float, annual_revenue_per_customer: float, serviceable_pct: float = 100.0, capture_pct: float = 3.0, top_down_tam: float | None = None, years: int = 5) -> dict:
    """Bottom-up TAM/SAM/SOM with plausibility checks against venture-scale thresholds and top-down claims.

    Args:
        target_customers: Total number of potential customers worldwide (or in the market you define).
        annual_revenue_per_customer: Realistic ACV / ARPU in dollars.
        serviceable_pct: Share of TAM you can actually serve with today's product, geography and channels (default 100).
        capture_pct: Share of SAM you expect to win within `years` (default 3%; new entrants rarely exceed 5-10%).
        top_down_tam: Optional top-down TAM in dollars (analyst report) to reconcile against.
        years: Horizon for SOM (default 5).
    """
    n = to_float(target_customers, "target_customers", 1)
    acv = to_float(annual_revenue_per_customer, "annual_revenue_per_customer", 0.01)
    sam_pct = to_float(serviceable_pct, "serviceable_pct", 0.1, 100)
    cap = to_float(capture_pct, "capture_pct", 0.01, 100)
    if not isinstance(years, int) or not 1 <= years <= 10:
        raise ToolError("years must be an integer between 1 and 10.")
    tam = n * acv
    sam = tam * sam_pct / 100
    som = sam * cap / 100
    som_customers = n * sam_pct / 100 * cap / 100
    flags = []
    if tam < 1e9:
        flags.append(f"TAM ${tam / 1e9:.2f}B is under $1B — hard to argue venture scale; widen the segment, raise ACV, or position for a non-venture path")
    if cap > 10:
        flags.append(f"capture {cap}% of SAM in {years} years is rarely believed for a new entrant (typical 1-5%)")
    if top_down_tam is not None:
        td = to_float(top_down_tam, "top_down_tam", 1)
        ratio = tam / td
        if ratio > 1.5 or ratio < 0.33:
            rel = f"{ratio:.1f}× the top-down figure" if ratio >= 1 else f"only {ratio * 100:.1f}% of the top-down figure"
            flags.append(f"bottom-up TAM is {rel} (${tam:,.0f} vs ${td:,.0f}) — reconcile before presenting (different definitions?)")
    per_year_customers = som_customers / years
    return {
        "tam": round(tam),
        "sam": round(sam),
        "som": round(som),
        "som_customers": round(som_customers),
        "customers_to_win_per_year": round(per_year_customers, 1),
        "som_pct_of_tam": round(100 * som / tam, 2),
        "formula": f"TAM = {n:,.0f} × ${acv:,.0f} = ${tam:,.0f}; SAM = {sam_pct}% → ${sam:,.0f}; SOM = {cap}% of SAM → ${som:,.0f} (~{som_customers:,.0f} customers in {years} yrs)",
        "flags": flags,
        "verdict": "Defensible bottom-up sizing" if not flags else flags[0],
    }


@AGENT.tool
def raise_math(amount: float, valuation: float, valuation_is_post: bool = True, option_pool_pct: float = 0.0, monthly_burn: float = 0.0, burn_growth_pct_per_month: float = 0.0, start_date: str = "", existing_cash: float = 0.0) -> dict:
    """Compute dilution, post-money ownership, option-pool effect, and runway months for a fundraise.

    Args:
        amount: Dollars raised in this round.
        valuation: Pre- or post-money valuation in dollars (see valuation_is_post).
        valuation_is_post: True if `valuation` is post-money (default), False if pre-money.
        option_pool_pct: New option pool as % of post-money, created pre-money (the "pool shuffle"); 0 if none.
        monthly_burn: Net monthly burn after the raise (dollars). 0 skips runway.
        burn_growth_pct_per_month: Expected monthly growth in burn (e.g. 3 for 3%/month as you hire).
        start_date: YYYY-MM-DD the money lands (optional) to date the runway end.
        existing_cash: Cash already in the bank when the round closes (dollars); runway counts it too.
    """
    from ...lib import dates

    amt = to_float(amount, "amount", 1)
    val = to_float(valuation, "valuation", 1)
    pool = to_float(option_pool_pct, "option_pool_pct", 0, 50) / 100
    burn = to_float(monthly_burn, "monthly_burn", 0)
    growth = to_float(burn_growth_pct_per_month, "burn_growth_pct_per_month", 0, 30) / 100
    bank = to_float(existing_cash, "existing_cash", 0)
    post = val if valuation_is_post else val + amt
    pre = post - amt
    if pre <= 0:
        raise ToolError("Pre-money would be ≤ 0 — amount exceeds the post-money valuation.")
    investor_pct = amt / post
    founders_after = 1 - investor_pct - pool
    effective_pre = pre - pool * post  # pool carved out of pre-money reduces the effective pre
    flags = []
    if investor_pct > 0.30:
        flags.append(f"{investor_pct * 100:.1f}% dilution is above the 15-25% seed norm — raise less or negotiate valuation")
    if pool and pool * post > 0:
        flags.append(f"a {pool * 100:.0f}% pre-money pool lowers your effective pre-money from ${pre:,.0f} to ${effective_pre:,.0f}")
    runway = None
    if burn > 0:
        cash, months = amt + bank, 0
        b = burn
        while cash > 0 and months < 120:
            cash -= b
            if cash <= 0:
                break
            months += 1
            b *= 1 + growth
        # fractional last month
        months_f = months + (cash + b) / b if b else months
        runway = {"months": round(months_f, 1), "end_date": None, "target": "18-24 months"}
        if start_date:
            sd = dates.parse_date(start_date)
            end_month = sd.month - 1 + int(months_f)
            end = sd.replace(year=sd.year + end_month // 12, month=end_month % 12 + 1, day=1)
            runway["end_date"] = end.isoformat()
        if months_f < 18:
            need = sum(burn * (1 + growth) ** k for k in range(18))  # cash needed for 18 months at this burn path
            flags.append(f"runway {months_f:.1f} months < 18 — 18 months on this burn path needs ${need:,.0f}; raise ${need - amt - bank:,.0f} more or cut burn")
    return {
        "pre_money": round(pre),
        "post_money": round(post),
        "investor_pct": round(investor_pct * 100, 2),
        "option_pool_pct": round(pool * 100, 2),
        "founders_and_existing_pct": round(founders_after * 100, 2),
        "effective_pre_money": round(effective_pre),
        "price_per_pct": round(post / 100),
        "runway": runway,
        "flags": flags,
        "verdict": (f"${amt:,.0f} at ${post:,.0f} post → {investor_pct * 100:.1f}% to new investors" + (f"; runway {runway['months']} months" if runway else "")),
        "scope_note": "Planning estimate — term-sheet mechanics (liquidation preferences, SAFE caps/discounts, pro-rata) change these numbers; have counsel model the cap table.",
    }


@AGENT.tool
def slide_density(slides: list[dict]) -> dict:
    """Audit each slide's text for density, bullet count, label-titles and missing numbers.

    Args:
        slides: List of {"title": str, "body": str} in deck order.
    """
    rows = check_rows(slides, "slides", 60)
    out, clean = [], 0
    for i, raw in enumerate(rows, 1):
        if not isinstance(raw, dict):
            raise ToolError(f"slides[{i - 1}] must be an object with 'title' and 'body'.")
        title = str(raw.get("title", "")).strip()
        body = str(raw.get("body", "")).strip()
        words = len(text.words(body))
        bullets = len(re.findall(r"(?m)^\s*(?:[-*•▪]|\d+[.)])\s+", body))
        title_words = len(text.words(title))
        has_number = bool(re.search(r"\d", title + " " + body))
        issues = []
        if words > 40:
            issues.append(f"{words} words — cut to ≤ 40 (aim 20)")
        if bullets > 6:
            issues.append(f"{bullets} bullets — max 6")
        if title_words <= 2 and i > 1:
            issues.append("title is a label — make it the takeaway sentence")
        if title_words > 14:
            issues.append(f"title is {title_words} words — ≤ 12")
        if not has_number and i > 1 and words > 0:
            issues.append("no number on the slide — add the metric or size that proves the claim")
        if re.search(r"\b(?:need|capture|get|take|win|grab)s?\s+(?:just\s+|only\s+)?\d+(?:\.\d+)?\s?%\s+of\b|\b\d+(?:\.\d+)?\s?%\s+of\s+(?:a|the|this)\s+\$?[\d.,]+\s?[bmk]", title + " " + body, re.I):
            issues.append("'we only need 1% of the market' — top-down share claims are discounted to zero; show bottom-up customers × ACV")
        longest = max((len(text.words(s)) for s in text.sentences(body)), default=0)
        if longest > 25:
            issues.append(f"a {longest}-word sentence — slides are not paragraphs")
        if not issues:
            clean += 1
        out.append({"slide": i, "title": title, "words": words, "bullets": bullets, "has_number": has_number, "issues": issues})
    total_words = sum(s["words"] for s in out)
    return {
        "slides": out,
        "clean": clean,
        "count": len(out),
        "avg_words_per_slide": round(total_words / len(out), 1),
        "reading_time_min": round(total_words / 200, 1),
        "verdict": f"{clean}/{len(out)} slides pass; avg {round(total_words / len(out))} words/slide (target ≤ 30)",
    }
