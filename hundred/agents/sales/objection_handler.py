"""Objection Crusher — classifies objections, isolates the real one, and answers with numbers instead of adjectives."""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from ...core import Agent, ToolError
from . import _common as c

AGENT = Agent(
    slug="objection-handler",
    name="Objection Crusher",
    category="sales",
    tagline="Turn 'too expensive', 'not now' and 'we use a competitor' into the next step — with a classifier, ROI math and a script.",
    description=(
        "Handles sales objections the way top closers do: classifies what was actually said (price, timing, "
        "authority, need, competitor, trust, status quo, feature gap), detects smokescreens, chooses the right "
        "response framework, and computes the ROI, payback and cost-of-delay numbers that make the rebuttal "
        "land. Also mines your objection log to show which objection is really costing you deals and at which stage."
    ),
    triggers=[
        "how do I respond to this objection",
        "prospect says it's too expensive / no budget",
        "they said not right now / bad timing / call me next quarter",
        "they're going with a competitor — what do I say",
        "build an ROI argument / cost of inaction for this deal",
        "analyze my objections log",
    ],
    examples=[
        "Prospect replied: 'Love it but the price is double what we pay now.' How do I respond?",
        "They said 'we're happy with HubSpot'. Give me the reply and the questions to ask.",
        "Our tool is $24k/yr, saves each of 6 analysts about 5 hours a week. Build the ROI rebuttal.",
        "Here are 40 objections from last quarter with stage and outcome — what's the pattern?",
    ],
    connectors=["Gmail", "Salesforce", "HubSpot", "Slack", "Gong"],
    playbook="""
    ## Standard
    You are a closer who treats an objection as information, not resistance. Excellent
    means: the real objection is identified (the stated one often isn't), it is isolated
    ("if we solved X, is there anything else?"), and the response gives the prospect a
    fact or a number they didn't have — never a discount, never an argument. The one
    metric: **objections converted into an agreed next step**. A reply that "wins the
    point" and loses the conversation is a failure.

    ## Intake
    You need the objection verbatim (their words, not the rep's summary), the stage of
    the deal, and the pricing/value facts if an ROI rebuttal is needed. If the objection
    is paraphrased, ask for the exact wording — one question — because "expensive" and
    "we can't justify it" are different objections. Otherwise proceed with stated
    assumptions.

    ## Procedure
    1. **Classify.** Call `objection_handler__classify_objection` with the verbatim text
       and stage. It returns the primary and secondary category, confidence, whether it
       looks like a smokescreen (a polite exit dressed as an objection), the recommended
       framework, and the isolation question. Trust the classifier over your first read —
       "we don't have budget" in stage 1 is usually *need*, not *price*. For price objections
       it also returns the sub-type(s) (sticker shock / budget / value gap / competitor
       cheaper); answer each sub-type it finds with its own move — "double what we pay for X,
       and I can't justify it" is a TCO comparison *and* a value rebuild, not one rebuttal.
    2. **Isolate before you answer.** Every response begins with the isolation question
       from step 1 or an acknowledgement + clarifying question (LAER: Listen, Acknowledge,
       Explore, Respond). Answering the stated objection without exploring costs you the
       real one.
    3. **Quantify when the objection is price, value or timing.** Call
       `objection_handler__roi_rebuttal` with the price and the value drivers you know
       (hours saved × people × hourly cost, revenue lift, risk/error cost). Use its ROI,
       payback and cost-of-delay figures verbatim. If you lack inputs, ask the prospect
       for them in the response — "how many hours a week does your team spend on X?" is
       itself a great objection response.
    4. **Reframe the number.** For price objections also call
       `objection_handler__reframe_price` to express the price per user per day, per
       working hour, and as a fraction of one hire; use the framing that is smallest
       relative to the value driver. Never argue the total.
    5. **Write the response** in the prospect's channel (email reply, call script, or
       Slack message): acknowledge (≤ 1 sentence), isolate (1 question), reframe with the
       number, one proof point, one next-step ask. Under 120 words for email.
    6. **Pattern-check the pipeline** when the user shares several objections: call
       `objection_handler__objection_log_stats` to count by category and stage and the win
       rate when each is raised. Price objections concentrated in late stages usually
       mean discovery skipped impact; competitor objections early mean weak positioning.
       Report the top fix.

    ## Frameworks
    - **LAER** (Listen, Acknowledge, Explore, Respond) — the default sequence.
    - **Isolate-and-close:** "Setting price aside for a second — is everything else what
      you need?" Then the objection is the only thing between you and a yes.
    - **Feel-Felt-Found:** only for trust objections, and only with a real named customer.
    - **Cost of inaction:** delay cost per month = annual value / 12. Say "each month of
      waiting costs about $X" rather than "we're worth it".
    - **Price categories by response:** *sticker shock* (reframe per unit + payback);
      *budget* (phase the rollout, align to fiscal year, or find the budget owner);
      *value gap* (go back to discovery — they don't believe the outcome); *competitor
      cheaper* (total cost of ownership, not licence price).
    - **Smokescreen tells:** "send me some information", "let me think about it",
      "circle back next quarter" with no specifics. Respond with a diagnostic question,
      not a pitch, and offer a graceful exit — people tell the truth when leaving is easy.
    - **Never** discount to answer a price objection before the value is agreed; a
      discount confirms the price was padded.
    - **Match the person, not just the objection.** Read their style from how they write
      and talk (a labelled guess, never a claim about their personality): *direct/driver*
      (short, blunt, results words) → lead with the number and the ask, skip the empathy
      paragraph; *analytical* (questions about detail, method, proof) → show the ROI inputs
      and a reference, no superlatives; *relational/steady* (team, "we", risk of change) →
      stress low-disruption rollout and a named peer; *expressive* (enthusiasm, vision) →
      open with the outcome story, then the number. Same facts, different order.

    ## Output format
    ```
    ## What they actually said
    "<verbatim>" → **<category>** (<confidence>%) · secondary: <category> · price sub-type(s): <…> · smokescreen: <yes/no>
    Style read (guess): <direct / analytical / relational / expressive> — <the words that suggest it>

    ## Isolate first
    "<isolation question>"

    ## The numbers
    <ROI / payback / cost of delay / reframed price — from the tools>

    ## Response (<channel>, <n> words)
    <acknowledge → isolate → reframe + proof → single next-step ask>

    ## If they push back again
    - <second-line response>
    - <walk-away line that keeps the door open>
    ```

    ## Anti-patterns
    - Answering the first objection at face value. Isolate, then answer.
    - "I understand, but…" — the "but" deletes the acknowledgement.
    - Feature dumps in response to price. Price objections are value objections.
    - Discounting on the first "too expensive". Ask what they compared it to.
    - Trash-talking the competitor. Ask what they like about it, then position on the gap.
    - Made-up ROI. Every number must come from the tool with inputs the prospect gave.
    """,
)

CATEGORIES = {
    "price": r"\b(expensive|price|pricing|cost(?:s|ly)?|too much|budget|afford|cheaper|discount|money|\$|per seat|per user|roi|justify)\b",
    "timing": r"\b(not (?:right )?now|later|next (?:quarter|year|month)|q[1-4]|busy|bad time|timing|priority|priorities|circle back|revisit|after (?:the )?\w+|no bandwidth|too soon|down the road)\b",
    "authority": r"\b(boss|manager|director|vp|cfo|ceo|board|committee|not my (?:decision|call)|need to (?:ask|check|run it by|talk to)|decision maker|procurement|approval|sign[- ]?off)\b",
    "need": r"\b(don'?t need|no need|not a (?:priority|fit|problem)|we'?re (?:fine|good|ok|okay)|not sure (?:we|it)|why would we|what'?s the point|doesn'?t apply|not relevant|works fine)\b",
    "competitor": r"\b(competitor|already (?:use|have|using|working with)|we use|going with|chose|switched to|another vendor|alternative|in[- ]house|build it ourselves|salesforce|hubspot|incumbent|current (?:vendor|provider|tool))\b",
    "trust": r"\b(never heard|too small|startup|risky|risk|proof|references|case stud|guarantee|security|compliance|reliable|track record|reviews|who else uses|been burned|last vendor)\b",
    "status_quo": r"\b(happy with|works for us|always done|no reason to change|too much (?:effort|work|disruption)|migration|switching cost|change management|retrain|our team won'?t)\b",
    "feature_gap": r"\b(doesn'?t (?:do|have|support|integrate)|missing|lacks?|no (?:api|integration|mobile|sso)|need it to|can'?t do|does it (?:do|support)|only if)\b",
}
_CAT_RES = {k: re.compile(v, re.I) for k, v in CATEGORIES.items()}
SMOKESCREEN_RE = re.compile(r"\b(send (?:me|us|over) (?:some|more|the) (?:info|information|details|material)|think about it|let me think|get back to you|not the right time|circle back|touch base later|keep (?:me|us) (?:posted|in mind)|reach out (?:next|in))\b", re.I)
PRICE_SUBTYPES = {
    "competitor_cheaper": (r"\b(cheaper|(?:double|twice|triple|\d+x|half) (?:what|the price)|more than (?:what )?we (?:pay|paid)|what we pay (?:for|to)|compared (?:to|with)|(?:other|another) (?:quote|vendor|option) (?:is|was|came in)|lower quote|undercut)\b",
                           "Compare total cost of ownership (licence + the work it removes + switching), not licence price; ask what the cheaper option includes."),
    "value_gap": (r"\b(can'?t justify|not worth|don'?t see (?:the )?(?:value|roi)|hard to justify|justify (?:it|the|this|\$)|what(?:'s| is) the roi|prove (?:the )?(?:value|roi))\b",
                  "Go back to discovery: rebuild the value with their numbers (ROI, payback, cost of delay) before touching price."),
    "budget": (r"\b(no budget|(?:don'?t|do not) have (?:the )?budget|budget (?:is )?(?:frozen|cut|spent|allocated|set)|not in (?:the|this year'?s|our) budget|next (?:year'?s|fiscal) budget|can'?t afford|funding)\b",
               "Phase the rollout, align the start to the fiscal year, or find who owns the budget — don't discount."),
    "sticker_shock": (r"\b(expensive|too much|pricey|steep|sticker|a lot of money|high(?:er)? than (?:expected|we thought))\b",
                      "Reframe per user per day and anchor on payback; ask what they expected and why."),
}
_PRICE_SUB_RES = {k: re.compile(v[0], re.I) for k, v in PRICE_SUBTYPES.items()}

FRAMEWORK = {
    "price": ("Isolate → reframe per unit → payback + cost of delay", "Setting price aside for a moment — is everything else what you'd need? And what are you comparing the price to?"),
    "timing": ("Cost of delay → shrink the first step", "What changes next quarter that makes it easier then? And what does the delay cost you in the meantime?"),
    "authority": ("Champion-enable → offer to co-present", "What would your <boss> need to see to say yes — and would it help if we built that summary together?"),
    "need": ("Return to discovery (Problem → Implication)", "Fair enough. When X goes wrong today, what does it cost you — time, money, or risk?"),
    "competitor": ("Acknowledge → find the gap → TCO not licence", "What do you like most about them? And if you could change one thing, what would it be?"),
    "trust": ("Proof: named customer + reversible first step", "What would you need to see to feel confident — a reference, a pilot, or a security review?"),
    "status_quo": ("Quantify the hidden cost of 'fine' → low-risk pilot", "Totally fair. If nothing changed for another year, what would that look like?"),
    "feature_gap": ("Confirm criticality → workaround or roadmap", "Is that a must-have for going live, or a nice-to-have? How are you doing it today?"),
}


@AGENT.tool
def classify_objection(objection: str, stage: str = "unknown") -> dict:
    """Classify an objection (price/timing/authority/need/competitor/trust/status_quo/feature_gap), spot smokescreens, pick the framework.

    Call first with the prospect's verbatim words. Returns primary + secondary category
    with confidence, the smokescreen flag, the response framework, the isolation question,
    and for price objections the sub-type(s): sticker_shock, budget, value_gap, competitor_cheaper.

    Args:
        objection: The objection exactly as the prospect said or wrote it.
        stage: Deal stage when raised: discovery, evaluation, proposal, negotiation, or unknown.
    """
    if not objection or not objection.strip():
        raise ToolError("objection text is empty.")
    if len(objection) > 5_000:
        raise ToolError("Objection over 5k chars — paste just the objection, not the whole thread.")
    scores = {k: len(rx.findall(objection)) for k, rx in _CAT_RES.items()}
    st = stage.strip().lower()
    # stage priors: early-stage "no budget" is usually need; late-stage timing is usually authority/priority
    if st in ("discovery", "unknown", "") and scores["price"] and not re.search(r"\b(expensive|cheaper|discount|per (?:seat|user))\b", objection, re.I):
        scores["need"] += 1
    if st in ("proposal", "negotiation") and scores["timing"]:
        scores["authority"] += 0.5
    total = sum(scores.values())
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    if total == 0:
        primary, secondary, conf = "need", None, 25
    else:
        primary = ranked[0][0]
        secondary = ranked[1][0] if ranked[1][1] > 0 else None
        conf = int(round(100 * ranked[0][1] / total))
        conf = max(35, min(95, conf))
    smoke = bool(SMOKESCREEN_RE.search(objection)) and not re.search(r"\b(because|since|specifically|the reason)\b", objection, re.I)
    n_words = len(objection.split())
    if n_words <= 6 and total <= 1:
        smoke = smoke or primary in ("timing", "need")
    framework, isolate = FRAMEWORK[primary]
    price_subtypes = [k for k, rx in _PRICE_SUB_RES.items() if rx.search(objection)] if "price" in (primary, secondary) or scores["price"] else []
    return {
        "primary": primary,
        "secondary": secondary,
        "confidence_pct": conf,
        "signal_counts": {k: v for k, v in scores.items() if v},
        "smokescreen": smoke,
        "framework": framework,
        "price_subtypes": price_subtypes,
        "price_responses": {k: PRICE_SUBTYPES[k][1] for k in price_subtypes},
        "isolation_question": isolate,
        "stage": st or "unknown",
        "verdict": f"{primary} objection ({conf}% confident)" + (f", possibly {secondary}" if secondary else "") + (" — reads as a smokescreen: ask a diagnostic question and make leaving easy." if smoke else "."),
    }


@AGENT.tool
def roi_rebuttal(
    annual_price: float,
    hours_saved_per_week: float = 0.0,
    people_affected: int = 1,
    hourly_cost: float = 0.0,
    annual_revenue_lift: float = 0.0,
    annual_risk_or_error_cost_avoided: float = 0.0,
    implementation_cost: float = 0.0,
    weeks_per_year: int = 48,
) -> dict:
    """Compute ROI %, payback months and cost of delay from price and the value drivers the prospect gave you.

    Call for any price, budget, timing or value objection. Pass only the drivers you actually
    have evidence for — zero is fine — and never invent hourly costs (use fully loaded cost ≈ 1.3× salary/2080).

    Args:
        annual_price: Your annual price for this deal.
        hours_saved_per_week: Hours saved per affected person per week.
        people_affected: Number of people who save those hours.
        hourly_cost: Fully-loaded hourly cost of those people.
        annual_revenue_lift: Extra annual revenue or gross profit attributable to the product.
        annual_risk_or_error_cost_avoided: Annual cost of errors, penalties, churn or downtime avoided.
        implementation_cost: One-time setup/migration/training cost (default 0).
        weeks_per_year: Working weeks used to annualise hours (default 48).
    """
    if annual_price <= 0:
        raise ToolError("annual_price must be > 0.")
    for name, v in (("hours_saved_per_week", hours_saved_per_week), ("hourly_cost", hourly_cost), ("annual_revenue_lift", annual_revenue_lift), ("annual_risk_or_error_cost_avoided", annual_risk_or_error_cost_avoided), ("implementation_cost", implementation_cost)):
        if v < 0:
            raise ToolError(f"{name} cannot be negative.")
    if people_affected < 1 or not 1 <= weeks_per_year <= 52:
        raise ToolError("people_affected ≥ 1 and weeks_per_year 1-52.")
    if hours_saved_per_week * people_affected > 24 * 7 * people_affected:
        raise ToolError("hours_saved_per_week exceeds hours in a week.")
    hours_year = hours_saved_per_week * people_affected * weeks_per_year
    time_value = c.money(hours_year * hourly_cost)
    annual_value = c.money(time_value + annual_revenue_lift + annual_risk_or_error_cost_avoided)
    first_year_cost = c.money(annual_price + implementation_cost)
    net_year1 = c.money(annual_value - first_year_cost)
    net_year_n = c.money(annual_value - annual_price)
    roi_year1 = round(100 * net_year1 / first_year_cost, 1) if first_year_cost else None
    roi_steady = round(100 * net_year_n / annual_price, 1)
    monthly_value = annual_value / 12
    payback_months = round(first_year_cost / monthly_value, 1) if monthly_value > 0 else None
    breakeven_hours_per_week = round(annual_price / (hourly_cost * people_affected * weeks_per_year), 2) if hourly_cost > 0 else None
    three_year_net = c.money(3 * annual_value - 3 * annual_price - implementation_cost)
    verdict_parts = []
    if annual_value == 0:
        verdict_parts.append("No value drivers supplied — ask the prospect for hours/week and hourly cost before arguing ROI.")
    elif roi_steady < 0:
        verdict_parts.append(f"Negative ROI ({roi_steady}%) on the drivers given — do not present this; find more value or reduce scope.")
    elif payback_months and payback_months > 12:
        verdict_parts.append(f"Payback {payback_months} months — weak; a first-year ROI pitch won't land. Lead with a 3-year view (${three_year_net:,.0f} net) or phase pricing.")
    else:
        verdict_parts.append(f"ROI {roi_steady}% steady-state, payback {payback_months} months, delay costs ${monthly_value:,.0f}/month.")
    return {
        "annual_price": c.money(annual_price),
        "first_year_cost": first_year_cost,
        "hours_saved_per_year": round(hours_year, 1),
        "time_value_per_year": time_value,
        "annual_value": annual_value,
        "net_benefit_year1": net_year1,
        "net_benefit_steady_state": net_year_n,
        "roi_pct_year1": roi_year1,
        "roi_pct_steady_state": roi_steady,
        "payback_months": payback_months,
        "value_to_price_multiple": round(annual_value / annual_price, 2),
        "cost_of_delay": {"per_month": c.money(monthly_value), "per_week": c.money(annual_value / 52), "per_day": c.money(annual_value / 365)},
        "breakeven_hours_saved_per_person_per_week": breakeven_hours_per_week,
        "three_year_net": three_year_net,
        "talk_track": (
            f"Every month this waits costs about ${monthly_value:,.0f}; the product pays for itself in {payback_months} months."
            if payback_months and payback_months <= 12 else "Get the prospect's own numbers before quoting ROI."
        ),
        "verdict": " ".join(verdict_parts),
    }


@AGENT.tool
def reframe_price(annual_price: float, users: int = 1, fte_annual_cost: float = 0.0, alternative_annual_cost: float = 0.0, working_days: int = 250) -> dict:
    """Express a price per user/month, per day, per working hour and as a fraction of one hire, plus the delta vs an alternative.

    Call for sticker-shock objections. Pick the framing that is smallest relative to the
    value driver (e.g. "$4 per user per day" against "5 hours saved a week").

    Args:
        annual_price: Annual contract price.
        users: Seats or users covered (default 1).
        fte_annual_cost: Fully-loaded annual cost of one hire in the role affected (0 = skip).
        alternative_annual_cost: Annual cost of the incumbent/competitor or the manual process (0 = skip).
        working_days: Working days per year for per-day framing (default 250).
    """
    if annual_price <= 0 or users < 1 or working_days < 1 or working_days > 366:
        raise ToolError("annual_price > 0, users ≥ 1, working_days 1-366.")
    if fte_annual_cost < 0 or alternative_annual_cost < 0:
        raise ToolError("Costs cannot be negative.")
    per_user_year = annual_price / users
    out = {
        "annual_price": c.money(annual_price),
        "per_month": c.money(annual_price / 12),
        "per_user_per_year": c.money(per_user_year),
        "per_user_per_month": c.money(per_user_year / 12),
        "per_user_per_day": c.money(per_user_year / working_days),
        "per_user_per_working_hour": c.money(per_user_year / (working_days * 8)),
        "per_day_total": c.money(annual_price / working_days),
    }
    framings = [f"${out['per_user_per_day']:,.2f} per user per working day", f"${out['per_user_per_month']:,.0f} per user per month"]
    if fte_annual_cost > 0:
        share = annual_price / fte_annual_cost
        out["share_of_one_fte"] = round(share, 3)
        out["fte_hours_equivalent_per_year"] = round(share * working_days * 8)
        framings.append(f"{round(100 * share, 1)}% of one {'' if share < 1 else 'additional '}hire" if share < 1 else f"{round(share, 1)}× one hire — be careful, this framing hurts you")
    if alternative_annual_cost > 0:
        delta = annual_price - alternative_annual_cost
        out["delta_vs_alternative"] = c.money(delta)
        out["delta_pct_vs_alternative"] = round(100 * delta / alternative_annual_cost, 1)
        out["delta_per_user_per_month"] = c.money(delta / users / 12)
        framings.append(f"{'+' if delta >= 0 else '-'}${abs(delta) / users / 12:,.2f} per user per month vs the alternative")
    out["framings"] = framings
    out["recommended_framing"] = framings[0]
    out["verdict"] = f"Say '{framings[0]}', not '${annual_price:,.0f} a year'."
    return out


@AGENT.tool
def objection_log_stats(objections: list[dict]) -> dict:
    """Mine an objection log: frequency by category and stage, win rate when each is raised, and the top fix.

    Call when the user shares several objections (e.g. from CRM notes or call recordings).
    Each row: {"category": str, "stage": str, "outcome": "won"|"lost"|"open", "text": str (optional)}.
    Rows without a category are classified from their text.

    Args:
        objections: List of objection rows, max 2000.
    """
    if not objections:
        raise ToolError("objections list is empty.")
    if len(objections) > 2000:
        raise ToolError("Max 2000 rows per call.")
    by_cat: Counter[str] = Counter()
    by_stage: Counter[str] = Counter()
    cat_stage: dict[str, Counter[str]] = defaultdict(Counter)
    outcomes: dict[str, Counter[str]] = defaultdict(Counter)
    for i, row in enumerate(objections):
        if not isinstance(row, dict):
            raise ToolError(f"Row {i + 1} is not a dict.")
        cat = str(row.get("category", "")).strip().lower().replace(" ", "_")
        if not cat:
            txt = str(row.get("text", "")).strip()
            if not txt:
                raise ToolError(f"Row {i + 1} has neither category nor text.")
            cat = classify_objection(txt)["primary"]
        if cat not in CATEGORIES:
            raise ToolError(f"Row {i + 1}: unknown category {cat!r}. Use: {', '.join(CATEGORIES)}.")
        stage = str(row.get("stage", "unknown")).strip().lower() or "unknown"
        outcome = str(row.get("outcome", "open")).strip().lower() or "open"
        if outcome not in ("won", "lost", "open"):
            raise ToolError(f"Row {i + 1}: outcome must be won, lost or open.")
        by_cat[cat] += 1
        by_stage[stage] += 1
        cat_stage[cat][stage] += 1
        outcomes[cat][outcome] += 1
    n = len(objections)
    table = []
    for cat, count in by_cat.most_common():
        won, lost = outcomes[cat]["won"], outcomes[cat]["lost"]
        decided = won + lost
        table.append({
            "category": cat,
            "count": count,
            "share_pct": c.pct(count, n),
            "won": won,
            "lost": lost,
            "open": outcomes[cat]["open"],
            "win_rate_when_raised_pct": c.pct(won, decided) if decided else None,
            "most_common_stage": cat_stage[cat].most_common(1)[0][0],
        })
    insights = []
    top = table[0]
    insights.append(f"'{top['category']}' is {top['share_pct']}% of objections (most often at {top['most_common_stage']}).")
    late_price = sum(cat_stage["price"][s] for s in ("proposal", "negotiation"))
    if by_cat["price"] and late_price / by_cat["price"] >= 0.6:
        insights.append("Price objections cluster late — discovery isn't establishing impact before the proposal. Fix: quantify cost of the problem before showing a number.")
    early_comp = sum(cat_stage["competitor"][s] for s in ("discovery", "unknown"))
    if by_cat["competitor"] and early_comp / by_cat["competitor"] >= 0.6:
        insights.append("Competitor objections appear early — positioning/differentiation is unclear in outbound and first calls.")
    worst = [r for r in table if r["win_rate_when_raised_pct"] is not None and (r["won"] + r["lost"]) >= 3]
    if worst:
        w = min(worst, key=lambda r: r["win_rate_when_raised_pct"])
        insights.append(f"Lowest win rate when raised: '{w['category']}' at {w['win_rate_when_raised_pct']}% (n={w['won'] + w['lost']}) — build a standard response and drill it.")
    if by_cat["authority"] / n >= 0.25:
        insights.append("≥ 25% authority objections — reps are selling to non-decision-makers; multi-thread earlier.")
    return {
        "total": n,
        "by_category": table,
        "by_stage": dict(by_stage.most_common()),
        "insights": insights,
        "top_fix": insights[1] if len(insights) > 1 else insights[0],
        "verdict": insights[0] + (" " + insights[1] if len(insights) > 1 else ""),
    }
