"""Negotiation Coach — ZOPA/BATNA maths, a concession ladder that shrinks, package comparisons at present value, and trades ranked by cost-to-you vs value-to-them."""

from __future__ import annotations

from ...core import Agent, ToolError
from . import _common as c

AGENT = Agent(
    slug="negotiation-coach",
    name="Negotiation Coach",
    category="sales",
    tagline="Walk into the negotiation knowing your ZOPA, your anchor, your concession ladder and what every trade really costs — before they ask.",
    description=(
        "Prepares and runs B2B price and terms negotiations like a trained negotiator: computes the zone of "
        "possible agreement from both sides' walk-aways and BATNAs, sets a defensible anchor, builds a "
        "concession ladder where each move is smaller than the last and always paired with a get, compares "
        "multi-year, discount and payment-term packages at present value so a 'cheaper' deal doesn't cost "
        "you more, and ranks trades by cost to you versus value to them."
    ),
    triggers=[
        "help me negotiate this deal / prepare for a pricing negotiation",
        "they want a discount — how should I respond",
        "what's my BATNA / ZOPA / walk-away",
        "plan my concessions",
        "compare 1-year vs 3-year deal with different discounts",
        "what should I ask for in return for a discount",
    ],
    examples=[
        "They're asking for 25% off our $120k proposal. Our floor is $96k. Build my concession plan.",
        "Compare: 1 year at $100k with 10% off, vs 3 years at $100k/yr with 18% off paid annually upfront.",
        "Procurement says they have a cheaper quote. What's my ZOPA and where do I anchor?",
        "List of things they want: net-60, price lock, extra seats, SLA. What do I give and what do I get?",
    ],
    connectors=["Gmail", "Salesforce", "HubSpot", "DocuSign", "Slack", "Google Sheets"],
    playbook="""
    ## Standard
    You are a negotiation coach trained in the Harvard principled-negotiation tradition
    with the pragmatism of a sales VP who has closed a thousand deals. Excellent means:
    every number is prepared before the conversation (walk-away, target, anchor, ladder),
    nothing is given without a get, and the deal that closes is the deal that was planned.
    The one metric: **realised price vs. target** — with the relationship intact. A
    discount that buys nothing back is a failure even when the deal closes.

    ## Intake
    You need: the current proposal price and structure, your floor (walk-away) and target,
    what they've asked for (verbatim if possible), what you know of their alternatives and
    deadline, and what you could trade (term, payment timing, scope, seats, references,
    start date). If the floor is missing, ask for it — one question — because every
    other number depends on it. Otherwise assume and label.

    ## Procedure
    1. **Map the zone.** Call `negotiation_coach__zopa_batna` with your walk-away and
       target, your estimate of their walk-away and target, and the value of each side's
       best alternative. It returns whether a ZOPA exists, its width, the midpoint, your
       recommended anchor (ambitious but inside their plausible range), and a power
       read (whose BATNA is stronger). No ZOPA → the job is to change the package, not
       to argue price.
    2. **Build the ladder.** Call `negotiation_coach__concession_ladder` with the anchor
       (or current price), the floor and the number of moves you're willing to make. It
       splits the room into decreasing steps (e.g. 50/30/15/5%), so each concession
       signals you're near the end, and attaches a required "get" to each step. Never
       make a step bigger than the previous one — buyers read the pattern.
    3. **Price the packages.** When term, discount or payment timing are in play, call
       `negotiation_coach__compare_packages` with each option. It computes total contract
       value, effective discount, present value at your cost of capital, and ranks them so
       "18% off for 3 years upfront" can be compared honestly with "10% off for 1 year".
       Recommend the one with the highest PV to you that still gives them a headline win.
    4. **Rank the trades.** Call `negotiation_coach__trade_ranker` with everything they
       asked for and everything you could ask for, each rated cost-to-you and
       value-to-them 1-5. It returns the cheap gives (low cost, high value — lead with
       these), the expensive gives (protect), and matched pairs ("if net-60, then annual
       prepay"). Build MESOs (multiple equivalent simultaneous offers) from the pairs:
       2-3 packages of equal value to you, different shape for them.
    5. **Script the conversation:** opening (restate agreed value, then the anchor with a
       reason), response to the first ask (silence → clarifying question → conditional
       "if… then…"), the ladder steps with their gets, and the walk-away line. Rehearse
       the two hardest objections.
    6. **Deliver** in the output format. Include the numbers table — the user will have
       it open during the call.

    ## Frameworks
    - **BATNA / ZOPA:** your reservation price is set by your BATNA, not your hopes.
      ZOPA = [their walk-away, your walk-away] when it exists; the midpoint is where
      un-prepared negotiations land; anchoring moves the landing toward the anchor.
    - **Anchor rule:** anchor first when you know more than they do; anchor high but
      justify with a reason (scope, value, comparables); an anchor with no reason is
      a bluff.
    - **Concession pattern:** decreasing size (e.g. 50% / 30% / 15% / 5% of the room),
      slowing pace, every step conditional ("if you can do X, I can do Y"), never a
      round number, never two moves in a row without a get.
    - **Trade currencies:** term length, payment timing (upfront is worth 3-8% to you),
      start date, scope/seats, price lock/escalator, case study/reference, logo rights,
      SLA level, support tier, renewal terms, exclusivity, referrals.
    - **Discount hygiene:** every discount has a reason and an expiry; never discount
      for nothing; never split the difference on the first ask; "what would you need
      to make this work today?" beats "what if I gave you 10%?".
    - **Present value:** compare multi-year deals at your cost of capital (10-20% for
      most SaaS/services businesses); a bigger discount for upfront cash is often
      rational — the tool shows when.
    - Not legal advice: liability, indemnity and termination terms go to a lawyer.

    ## Output format
    ```
    ## Numbers (keep open during the call)
    | Walk-away | Target | Anchor | ZOPA | Their est. walk-away | Power |
    |---|---|---|---|---|---|

    ## Concession ladder
    | Step | Price | Move | % of room | Only if they give |
    |---|---|---|---|---|

    ## Packages compared
    | Option | TCV | Effective discount | PV to us | Headline for them |

    ## Trades
    Cheap gives: … · Protect: … · Pairs: if <ask> → then <get>

    ## Script
    **Open:** …
    **When they ask for <x>:** …
    **Ladder step 1/2/3:** …
    **Walk-away line:** …
    ```

    ## Anti-patterns
    - Negotiating without a written walk-away. You will accept their number.
    - Giving the first concession unconditionally "to build goodwill". It builds appetite.
    - Equal-sized concessions. They signal there is always more.
    - Comparing a 3-year discount to a 1-year discount on headline % alone.
    - Trading on price when they'd value payment terms, start date or scope more.
    - Filling silence. After you state a number, stop talking.
    - Treating procurement's "we have a cheaper quote" as fact without asking what it includes.
    """,
)


@AGENT.tool
def zopa_batna(
    our_walkaway: float,
    our_target: float,
    their_walkaway_estimate: float,
    their_target_estimate: float = 0.0,
    our_batna_value: float = 0.0,
    their_batna_value: float = 0.0,
    we_are_seller: bool = True,
) -> dict:
    """Compute the zone of possible agreement, midpoint, recommended anchor and a power read from both sides' walk-aways and BATNAs.

    Call first. As the seller, your walk-away is the lowest price you'd accept and their
    walk-away is the most they'd pay; as the buyer, reverse. Estimates are fine — label them.

    Args:
        our_walkaway: Our reservation price (seller: minimum acceptable; buyer: maximum acceptable).
        our_target: The price we're aiming to close at.
        their_walkaway_estimate: Our best estimate of their reservation price.
        their_target_estimate: Our estimate of the price they're aiming for (0 = unknown).
        our_batna_value: Value to us of our best alternative if no deal (0 = unknown).
        their_batna_value: Estimated value to them of their best alternative (0 = unknown).
        we_are_seller: True if we're selling (default), False if buying.
    """
    for name, v in (("our_walkaway", our_walkaway), ("our_target", our_target), ("their_walkaway_estimate", their_walkaway_estimate)):
        if v <= 0:
            raise ToolError(f"{name} must be > 0.")
    if we_are_seller and our_target < our_walkaway:
        raise ToolError("As seller, our_target must be ≥ our_walkaway.")
    if not we_are_seller and our_target > our_walkaway:
        raise ToolError("As buyer, our_target must be ≤ our_walkaway.")
    if we_are_seller:
        low, high = our_walkaway, their_walkaway_estimate
    else:
        low, high = their_walkaway_estimate, our_walkaway
    exists = high >= low
    width = c.money(high - low) if exists else 0.0
    mid = c.money((low + high) / 2) if exists else None
    if exists:
        # anchor: beyond target, but inside what they could plausibly justify (≤ their walk-away + ~10% for seller)
        if we_are_seller:
            anchor = min(their_walkaway_estimate * 1.10, max(our_target * 1.12, our_target + 0.35 * (their_walkaway_estimate - our_target))) if their_walkaway_estimate > our_target else our_target * 1.08
            anchor = max(anchor, our_target)
        else:
            anchor = max(their_walkaway_estimate * 0.90, min(our_target * 0.88, our_target - 0.35 * (our_target - their_walkaway_estimate))) if their_walkaway_estimate < our_target else our_target * 0.92
            anchor = min(anchor, our_target)
        anchor = c.money(anchor)
    else:
        anchor = None
    target_in_zopa = exists and low <= our_target <= high
    target_pos = round((our_target - low) / (high - low), 2) if exists and high > low else None
    power = "balanced"
    reasons = []
    if our_batna_value and their_batna_value:
        if our_batna_value > their_batna_value * 1.2:
            power, r = "ours", "our alternative is worth more than theirs"
        elif their_batna_value > our_batna_value * 1.2:
            power, r = "theirs", "their alternative is worth more than ours"
        else:
            r = "alternatives roughly equal"
        reasons.append(r)
    elif our_batna_value:
        reasons.append("only our BATNA is known — find out theirs before conceding")
    else:
        reasons.append("no BATNA values given — the side with the better alternative holds the power; find out")
    if exists and width / max(low, 1) < 0.05:
        reasons.append("ZOPA is under 5% of price — small room; negotiate on non-price terms")
    advice = []
    if not exists:
        gap = c.money(low - high)
        advice.append(f"No overlap: gap of ${gap:,.0f}. Change the package (scope, term, payment timing) or walk — don't discount into a loss.")
    else:
        advice.append(f"Anchor at ${anchor:,.0f} with a stated reason; expect to land near ${mid:,.0f} without anchoring.")
        if target_pos is not None and target_pos < 0.3:
            advice.append("Your target sits in the bottom 30% of the ZOPA — raise it; you're leaving money on the table.")
    return {
        "role": "seller" if we_are_seller else "buyer",
        "zopa_exists": exists,
        "zopa_low": c.money(low) if exists else None,
        "zopa_high": c.money(high) if exists else None,
        "zopa_width": width,
        "zopa_width_pct_of_target": round(100 * width / our_target, 1) if exists else 0.0,
        "midpoint": mid,
        "our_target": c.money(our_target),
        "target_in_zopa": target_in_zopa,
        "target_position_in_zopa": target_pos,
        "recommended_anchor": anchor,
        "their_target_estimate": c.money(their_target_estimate) if their_target_estimate else None,
        "power": power,
        "power_reasons": reasons,
        "advice": advice,
        "verdict": (f"ZOPA ${low:,.0f}–${high:,.0f} (width ${width:,.0f}); midpoint ${mid:,.0f}; anchor ${anchor:,.0f}. Power: {power}." if exists else f"No ZOPA — gap ${c.money(low - high):,.0f}. Restructure or walk."),
    }


@AGENT.tool
def concession_ladder(opening_price: float, floor_price: float, steps: int = 3, gets: list[str] | None = None, pattern: str = "decreasing") -> dict:
    """Split the room between your opening and your floor into shrinking, conditional concession steps with a 'get' per step.

    Call after zopa_batna. Patterns: decreasing (default: e.g. 50/30/15/5% of the room),
    or firm (60/30/10, signals a hard floor fast). Prices are rounded to non-round numbers on purpose.

    Args:
        opening_price: Your anchor or current quoted price.
        floor_price: Your walk-away price (must be below opening for a seller).
        steps: Number of concessions you're prepared to make, 1-5.
        gets: What you'll ask for in return, in the order you'd trade them (optional; defaults provided).
        pattern: decreasing or firm.
    """
    if opening_price <= 0 or floor_price <= 0:
        raise ToolError("Prices must be > 0.")
    if floor_price >= opening_price:
        raise ToolError("floor_price must be below opening_price (seller's ladder).")
    if not 1 <= steps <= 5:
        raise ToolError("steps must be 1-5.")
    pat = pattern.strip().lower()
    if pat not in ("decreasing", "firm"):
        raise ToolError("pattern must be decreasing or firm.")
    room = opening_price - floor_price
    shares = {
        "decreasing": {1: [1.0], 2: [0.65, 0.35], 3: [0.5, 0.3, 0.2], 4: [0.45, 0.3, 0.15, 0.10], 5: [0.4, 0.27, 0.17, 0.10, 0.06]},
        "firm": {1: [1.0], 2: [0.75, 0.25], 3: [0.6, 0.3, 0.1], 4: [0.55, 0.28, 0.12, 0.05], 5: [0.5, 0.25, 0.13, 0.08, 0.04]},
    }[pat][steps]
    default_gets = [
        "annual prepayment (or shorter payment terms)",
        "multi-year term or auto-renewal",
        "signed by <date> (deadline concession)",
        "case study / reference call / logo rights",
        "reduced scope or later start date",
    ]
    gets = [g for g in (gets or []) if str(g).strip()] or default_gets
    ladder, price = [], opening_price
    reserve = 0.05 * room if steps >= 2 else 0.0  # hold back 5% of the room as a final 'closer'
    usable = room - reserve
    cum = 0.0
    for i, sh in enumerate(shares, 1):
        move = usable * sh
        cum += move
        price = opening_price - cum
        # make the number look calculated, not round: nudge to end in a non-zero unit
        nudged = round(price / 10) * 10 + (3 if price >= 1000 else 0)
        if nudged <= floor_price + reserve:
            nudged = price
        ladder.append({
            "step": i,
            "price": c.money(nudged),
            "move": c.money(opening_price - nudged - sum(l["move"] for l in ladder)),
            "move_pct_of_room": round(100 * move / room, 1),
            "discount_from_opening_pct": round(100 * (opening_price - nudged) / opening_price, 1),
            "only_if": gets[(i - 1) % len(gets)],
            "script": f"If you can commit to {gets[(i - 1) % len(gets)]}, I can get to ${nudged:,.0f}.",
        })
    final_gap = c.money(ladder[-1]["price"] - floor_price)
    return {
        "opening_price": c.money(opening_price),
        "floor_price": c.money(floor_price),
        "room": c.money(room),
        "room_pct_of_opening": round(100 * room / opening_price, 1),
        "pattern": pat,
        "ladder": ladder,
        "held_in_reserve": c.money(final_gap),
        "reserve_use": f"${final_gap:,.0f} kept for a final 'meet me at' close — only for a signature on the spot.",
        "rules": ["Never two moves without a get.", "Each move smaller than the last.", "State the reason with every number.", "After the number, stop talking."],
        "verdict": f"{steps} steps from ${opening_price:,.0f} down to ${ladder[-1]['price']:,.0f} (floor ${floor_price:,.0f}); moves {', '.join(str(l['move_pct_of_room']) + '%' for l in ladder)} of the room.",
    }


PAYMENT_TIMING = {"annual_upfront": 0.0, "upfront": 0.0, "quarterly": 0.375, "monthly": 0.458, "annual_arrears": 1.0, "net30": 0.08, "net60": 0.16, "net90": 0.25}


@AGENT.tool
def compare_packages(packages: list[dict], cost_of_capital_pct: float = 12.0) -> dict:
    """Compare deal packages (term, discount, escalator, payment timing) on TCV, effective discount and present value to you.

    Call when term or payment terms are on the table. Package: {"name": str, "annual_price": number
    (list, before discount), "term_years": number, "discount_pct": number, "escalator_pct": number (yearly uplift),
    "payment": "annual_upfront" | "quarterly" | "monthly" | "annual_arrears" | "net30" | "net60" | "net90",
    "one_time_fees": number}.

    Args:
        packages: 1-8 packages to compare.
        cost_of_capital_pct: Your annual cost of capital / discount rate for present value (default 12).
    """
    if not packages or len(packages) > 8:
        raise ToolError("Give 1-8 packages.")
    if not 0 <= cost_of_capital_pct <= 60:
        raise ToolError("cost_of_capital_pct must be 0-60.")
    r = cost_of_capital_pct / 100
    rows = []
    for i, p in enumerate(packages, 1):
        if not isinstance(p, dict):
            raise ToolError(f"Package {i} is not a dict.")
        try:
            annual = float(p.get("annual_price", 0))
            years = float(p.get("term_years", 1))
            disc = float(p.get("discount_pct", 0))
            esc = float(p.get("escalator_pct", 0))
            fees = float(p.get("one_time_fees", 0))
        except (TypeError, ValueError):
            raise ToolError(f"Package {i}: numeric fields must be numbers.") from None
        if annual <= 0 or years <= 0 or years > 10 or not 0 <= disc < 100 or not -20 <= esc <= 50 or fees < 0:
            raise ToolError(f"Package {i}: annual_price > 0, term_years 0-10, discount_pct 0-99, escalator_pct -20..50, fees ≥ 0.")
        pay = str(p.get("payment", "annual_upfront")).strip().lower().replace(" ", "_").replace("-", "_")
        if pay not in PAYMENT_TIMING:
            raise ToolError(f"Package {i}: payment must be one of {', '.join(PAYMENT_TIMING)}.")
        offset = PAYMENT_TIMING[pay]  # fraction of a year, on average, that cash arrives after the year starts
        tcv, pv, list_total = fees, fees, 0.0
        yearly = []
        full_years = int(years)
        partial = years - full_years
        for y in range(full_years + (1 if partial > 0 else 0)):
            frac = 1.0 if y < full_years else partial
            list_price = annual * ((1 + esc / 100) ** y) * frac
            price = list_price * (1 - disc / 100)
            list_total += list_price
            tcv += price
            pv += price / ((1 + r) ** (y + offset))
            yearly.append(c.money(price))
        eff_disc = round(100 * (1 - (tcv - fees) / list_total), 2) if list_total else 0.0
        rows.append({
            "name": str(p.get("name", f"Option {i}")),
            "term_years": years,
            "discount_pct": disc,
            "escalator_pct": esc,
            "payment": pay,
            "yearly_prices": yearly,
            "tcv": c.money(tcv),
            "acv": c.money((tcv - fees) / years),
            "list_total": c.money(list_total),
            "effective_discount_pct": eff_disc,
            "present_value": c.money(pv),
            "pv_per_year": c.money(pv / years),
            "cash_in_first_12_months": c.money(fees + (yearly[0] if pay in ("annual_upfront", "upfront", "net30", "net60", "net90") else yearly[0] * (1 - offset) if pay in ("quarterly", "monthly") else 0.0)),
        })
    best_pv = max(rows, key=lambda x: x["present_value"])
    best_pv_year = max(rows, key=lambda x: x["pv_per_year"])
    cheapest_for_them = min(rows, key=lambda x: x["acv"])
    notes = []
    if best_pv is not best_pv_year:
        notes.append(f"'{best_pv['name']}' has the highest total PV but '{best_pv_year['name']}' earns more per year — pick by whether you value locked revenue or rate.")
    for row in rows:
        if row["payment"] in ("monthly", "quarterly", "annual_arrears") and row["discount_pct"] >= 15:
            notes.append(f"'{row['name']}': {row['discount_pct']}% off with {row['payment']} payment — you're giving the cash-timing benefit and the discount; make the discount conditional on upfront payment.")
    return {
        "cost_of_capital_pct": cost_of_capital_pct,
        "packages": sorted(rows, key=lambda x: -x["present_value"]),
        "highest_pv": best_pv["name"],
        "highest_pv_per_year": best_pv_year["name"],
        "lowest_annual_cost_for_buyer": cheapest_for_them["name"],
        "notes": notes,
        "verdict": f"Highest PV to you: '{best_pv['name']}' (PV ${best_pv['present_value']:,.0f}, TCV ${best_pv['tcv']:,.0f}, effective discount {best_pv['effective_discount_pct']}%)." + (" " + notes[0] if notes else ""),
    }


@AGENT.tool
def trade_ranker(trades: list[dict]) -> dict:
    """Rank negotiation trades by cost-to-you vs value-to-them, separate cheap gives from ones to protect, and pair asks with gets.

    Call with everything on the table. Trade: {"item": str, "side": "give" (they want it) | "get" (we want it),
    "cost_to_us": 1-5, "value_to_them": 1-5, "value_to_us": 1-5 (for gets), "cost_to_them": 1-5 (for gets)}.

    Args:
        trades: 2-40 trades with the fields above.
    """
    if not trades or len(trades) < 2 or len(trades) > 40:
        raise ToolError("Give 2-40 trades.")
    gives, gets = [], []
    for i, t in enumerate(trades, 1):
        if not isinstance(t, dict) or not str(t.get("item", "")).strip():
            raise ToolError(f"Trade {i} needs an 'item'.")
        side = str(t.get("side", "give")).strip().lower()
        if side not in ("give", "get"):
            raise ToolError(f"Trade {i}: side must be give or get.")

        def _r(key, default=3):
            v = t.get(key, default)
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise ToolError(f"Trade {i}: {key} must be an integer 1-5.") from None
            if not 1 <= v <= 5:
                raise ToolError(f"Trade {i}: {key} must be 1-5.")
            return v

        if side == "give":
            cost, val = _r("cost_to_us"), _r("value_to_them")
            gives.append({"item": t["item"], "cost_to_us": cost, "value_to_them": val, "leverage": round(val / cost, 2), "class": "cheap give — lead with it" if val >= 3 and cost <= 2 else "protect — expensive to us" if cost >= 4 else "filler — low value to them" if val <= 2 else "standard trade"})
        else:
            val, cost = _r("value_to_us"), _r("cost_to_them")
            gets.append({"item": t["item"], "value_to_us": val, "cost_to_them": cost, "leverage": round(val / cost, 2), "class": "easy ask — high value, cheap for them" if val >= 3 and cost <= 2 else "big ask — save for a big give" if cost >= 4 else "standard ask"})
    gives.sort(key=lambda g: -g["leverage"])
    gets.sort(key=lambda g: -g["leverage"])
    pairs = []
    for g, k in zip(gives, gets):
        pairs.append({"if_they_want": g["item"], "we_ask_for": k["item"], "net_to_us": k["value_to_us"] - g["cost_to_us"], "script": f"If we can do {g['item']}, would you be able to commit to {k['item']}?"})
    cheap = [g["item"] for g in gives if g["class"].startswith("cheap")]
    protect = [g["item"] for g in gives if g["class"].startswith("protect")]
    meso = []
    if len(gives) >= 2 and gets:
        meso = [
            {"package": "A", "we_give": [gives[0]["item"]], "we_get": [gets[0]["item"]]},
            {"package": "B", "we_give": [gives[1]["item"]], "we_get": [gets[0]["item"]] + ([gets[1]["item"]] if len(gets) > 1 else [])},
        ]
    return {
        "gives_ranked": gives,
        "gets_ranked": gets,
        "cheap_gives": cheap,
        "protect": protect,
        "pairs": pairs,
        "meso_packages": meso,
        "verdict": (f"Lead with: {', '.join(cheap) if cheap else 'nothing cheap — every give costs you; insist on gets'}. Protect: {', '.join(protect) if protect else 'nothing critical'}." + (f" First pair: if {pairs[0]['if_they_want']} → then {pairs[0]['we_ask_for']}." if pairs else " Add 'get' items — a negotiation with only gives is a discount.")),
    }
