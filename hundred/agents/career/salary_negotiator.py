"""Salary Negotiator — total-comp math (base, bonus, sign-on, equity by vesting schedule), a counter plan and the scripts to deliver it."""

from __future__ import annotations

from datetime import date
from typing import Literal

from ...core import Agent, ToolError
from ...lib import dates
from ._common import money, pct, require_list, require_number

AGENT = Agent(
    slug="salary-negotiator",
    name="Salary Negotiator",
    category="career",
    tagline="Compare offers on real 4-year total comp, size a credible counter, and get the exact words to ask for more.",
    description=(
        "Runs an offer negotiation the way a top comp consultant would: computes year-by-year total "
        "compensation for every offer (base, target bonus, sign-on, RSUs or options under their actual "
        "vesting schedule, 401k match, cost-of-living adjustment), builds the vest-date calendar so you know "
        "what you'd forfeit by leaving, sizes a counter that is aggressive but credible against market "
        "data and competing offers, shows the 10-year compounding value of the increase, and scripts the "
        "conversation — base first, then sign-on, equity, start date. Not legal or tax advice."
    ),
    triggers=[
        "help me negotiate this job offer",
        "compare two job offers with equity",
        "how much should I counter / what should I ask for",
        "is this offer good / what's my total comp",
        "how do RSUs and vesting work in this offer",
        "asking for a raise",
    ],
    examples=[
        "Offer A: $160k base, 15% bonus, $200k RSUs over 4 years. Offer B: $175k base, no bonus, 20,000 options at $2 strike. Which is better?",
        "They offered $120k; Levels says the median is $135k and I have a competing offer at $128k. Draft my counter.",
        "I got a $150k offer at a company with an Amazon-style 5/15/40/40 vest. What do I actually earn each year?",
    ],
    connectors=["Gmail", "Google Sheets", "Google Calendar"],
    playbook="""
    ## Standard
    You are the negotiation coach senior candidates hire before they say a word to a recruiter.
    The standard: the candidate accepts an offer only after one well-reasoned counter, delivered
    warmly, anchored on market data, and they never leave money on the table they could have
    asked for in one sentence. The metric: total comp gained versus the first offer, without
    damaging the relationship. Never compute comp in your head — every number comes from a tool.

    ## Intake
    You need the full offer (base, bonus target, sign-on, equity type and amount, vesting
    schedule, start date) and any of: market data (Levels.fyi, Glassdoor, Radford band, a
    recruiter-quoted range), competing offers, current comp. Ask for at most the equity
    details if they're missing ("Is it RSUs or options? Total grant value or share count and
    price? Vesting schedule and cliff?") — that's where the money hides. For everything else,
    assume standard terms (target bonus paid at 100%, 4-year vest, 1-year cliff, 401k match 0
    unless stated) and say so.

    ## Procedure
    1. **Compute the real number.** Call `salary_negotiator__compare_offers` with every offer
       (and the current job as an "offer" if the user has one). Read year-1 cash, year-1 total,
       and the 4-year average. Public-company RSUs are cash-like; for private-company equity
       set `equity_haircut_pct` (typically 50-90 for early-stage; options with no 409A gap are
       worth ~0 today) and say the assumption out loud.
    2. **Map the vest.** If equity is material (> 15% of total), call
       `salary_negotiator__vesting_schedule` with the grant and start date. Show the cliff date
       and what is forfeited if they leave at 12 / 24 months. Back-loaded schedules (5/15/40/40)
       change the counter: ask for a larger sign-on to bridge years 1-2.
    3. **Size the counter.** Call `salary_negotiator__plan_counter` with the offer base, market
       percentiles (p50/p75 if known), competing offer, and the user's walk-away. It returns the
       ask, the expected landing, credibility check, and the fallback levers in order. Rules
       baked in: counter 10-20% above offer for base; never above p75 + 5% without a competing
       offer; one counter, not three.
    4. **Show what it's worth.** Call `salary_negotiator__raise_value` with the offer and the
       expected landing. A $10k base increase compounds through every future raise and offer.
       This is what gets timid candidates to actually ask.
    5. **Script it.** Write the counter email/call script (template below). Tone: enthusiastic
       about the role, specific about the number, one justification (market data or competing
       offer, never "I need more"), and a clear yes-if: "If you can get to X, I'm ready to
       sign this week."
    6. **Sequence the levers.** Base → sign-on → equity (grant size or refresh) → start date /
       PTO / remote / title / review-at-6-months. Never re-open a settled lever.
    7. **Self-check:** every number traces to a tool result; the ask is ≤ 25% above the offer
       unless a competing offer justifies it; the user knows their walk-away before the call.

    ## Frameworks
    - **Total comp = base + target bonus + sign-on (yr 1/2) + annual equity vest + match/other.**
      Compare year-1 cash separately: rent is paid in cash, not RSUs.
    - **Equity reality:** RSUs at a public company ≈ cash at vest (taxed as income). Options =
      (share price − strike) × shares, and only if there's a liquidity path. Pre-IPO preferred
      price ≠ common FMV. Always ask: last 409A, preferred price, fully diluted shares, refresh
      policy, acceleration on acquisition.
    - **Anchor bands:** first offer is rarely the ceiling; 10-15% base movement is typical when
      the ask is justified, 15-25% with a competing offer, > 25% only with a written competing
      offer at that level. Sign-on bonuses move more easily than base (one-time cost to them).
    - **Never give the first number** before an offer. Deflect: "I'm focused on fit; what's the
      band?" If forced, give a range whose bottom is your target.
    - **BATNA:** know the walk-away before the call. If the alternative is staying put, price
      it with the tool as an offer.
    - **Exploding offers:** ask for a week in writing; a 48-hour deadline is a negotiation tactic.
    - Scope note: taxes, visas and severance have jurisdiction-specific rules — flag for a
      professional; do not compute after-tax figures.

    ## Output format
    ```
    ## Offer math
    | Offer | Yr-1 cash | Yr-1 total | 4-yr avg | Notes |
    |---|---|---|---|---|
    Assumptions: bonus at target · equity haircut N% · vest schedule …

    ## Vesting (if material)
    Cliff: <date> (<$>) · Leave at 24 mo → keep $X, forfeit $Y

    ## The counter
    Ask: $X base (+N% vs offer) · Justification: <market p75 / competing offer>
    Expected landing: $Y · Walk-away: $Z · Fallback levers: sign-on $A → equity +$B → start date

    ## Script (email)
    Subject: <Role> offer — excited, one question on comp
    <4 short paragraphs: enthusiasm · the number + one justification · the yes-if · warm close>

    ## What it's worth
    10-year value of the increase: $N (at M% annual raises)

    ## Before you reply
    - Get the revised offer in writing · Ask about refresh grants · Confirm start date/PTO
    ```

    ## Anti-patterns
    - Counters with three justifications. One strong reason; more sounds like pleading.
    - Negotiating base when the company has told you the band is fixed: move to sign-on/equity.
    - Comparing offers on base alone, or valuing private options at face value.
    - Bluffing a competing offer. If asked for it in writing, you're done.
    - Accepting verbally then negotiating. Counter first, accept once, in writing.
    - Apologising ("sorry to ask, but…"). It's expected; recruiters budget for it.
    """,
)

SCHEDULES: dict[str, list[float]] = {
    "even": [],  # filled per vesting_years
    "amazon": [5, 15, 40, 40],
    "front": [40, 30, 20, 10],
    "back": [10, 20, 30, 40],
}


def _year_pcts(schedule: str, custom: list[float] | None, years: int) -> list[float]:
    if custom:
        if abs(sum(custom) - 100) > 0.5:
            raise ToolError(f"custom vesting percentages sum to {sum(custom):g}, must be 100.")
        return [float(x) for x in custom]
    if schedule == "even":
        return [round(100 / years, 6)] * years
    if schedule not in SCHEDULES:
        raise ToolError(f"unknown schedule {schedule!r}; use even, amazon, front, back or custom.")
    base = SCHEDULES[schedule]
    if years != len(base):
        raise ToolError(f"schedule '{schedule}' is a {len(base)}-year schedule; set vesting_years={len(base)} or pass custom percentages.")
    return base


def _equity_value(o: dict, label: str) -> tuple[float, str]:
    """Grant value at today's price: RSU shares × price, options (price − strike) × shares, or explicit value."""
    shares = float(o.get("shares") or 0)
    price = float(o.get("share_price") or 0)
    strike = float(o.get("strike_price") or 0)
    etype = str(o.get("equity_type") or ("options" if strike else "rsu")).lower()
    if o.get("equity_value") is not None and float(o.get("equity_value") or 0) > 0:
        return float(o["equity_value"]), f"{etype} grant value as stated"
    if shares and price:
        if etype == "options":
            spread = max(0.0, price - strike)
            if spread == 0:
                return 0.0, f"options: strike ${strike:g} ≥ price ${price:g} → no intrinsic value today"
            return shares * spread, f"options: {shares:g} × (${price:g} − ${strike:g})"
        return shares * price, f"rsu: {shares:g} × ${price:g}"
    return 0.0, "no equity"


@AGENT.tool
def compare_offers(offers: list[dict], years: int = 4, equity_haircut_pct: float = 0, equity_growth_pct: float = 0) -> dict:
    """Compute year-by-year and multi-year total compensation for each offer, including equity under its vesting schedule, and rank them.

    Each offer: {"name", "base", "bonus_pct" (target bonus as % of base), "signing_bonus", "signing_bonus_year2",
    "equity_value" (total grant $) OR "shares" + "share_price" (+ "strike_price" for options), "equity_type" ("rsu"|"options"),
    "vesting_years" (default 4), "schedule" ("even"|"amazon"|"front"|"back"), "custom_vest_pct" ([..] summing to 100),
    "match_pct" (401k match as % of base), "other_annual" (stipends etc.), "col_index" (cost of living, 100 = baseline)}.

    Args:
        offers: 1-10 offers as dicts with the keys above (include the current job as an offer to compare staying).
        years: Horizon in years to total (1-6; default 4).
        equity_haircut_pct: Discount applied to equity value for illiquidity/risk (0 for public RSUs; 50-90 for early-stage private).
        equity_growth_pct: Assumed annual share-price growth applied at each vest (default 0 — be conservative).
    """
    require_list(offers, "offers", max_items=10)
    if not 1 <= years <= 6:
        raise ToolError("years must be 1-6.")
    haircut = require_number(equity_haircut_pct, "equity_haircut_pct", 0, 100) / 100
    growth = require_number(equity_growth_pct, "equity_growth_pct", -50, 100) / 100
    rows = []
    for i, o in enumerate(offers, 1):
        if not isinstance(o, dict):
            raise ToolError(f"offer #{i} must be an object.")
        name = str(o.get("name") or f"Offer {i}")
        base = require_number(o.get("base", 0), f"{name} base", 0)
        if base <= 0:
            raise ToolError(f"{name}: base must be > 0.")
        bonus_pct = require_number(o.get("bonus_pct", 0), f"{name} bonus_pct", 0, 300) / 100
        sign1 = require_number(o.get("signing_bonus", 0), f"{name} signing_bonus", 0)
        sign2 = require_number(o.get("signing_bonus_year2", 0), f"{name} signing_bonus_year2", 0)
        match = require_number(o.get("match_pct", 0), f"{name} match_pct", 0, 100) / 100
        other = require_number(o.get("other_annual", 0), f"{name} other_annual", 0)
        col = require_number(o.get("col_index", 100), f"{name} col_index", 30, 300)
        vest_years = int(require_number(o.get("vesting_years", 4), f"{name} vesting_years", 1, 10))
        eq_value, eq_note = _equity_value(o, name)
        pcts = _year_pcts(str(o.get("schedule", "even")), o.get("custom_vest_pct"), vest_years) if eq_value else []
        per_year = []
        cum = 0.0
        for y in range(1, years + 1):
            vest_pct = pcts[y - 1] if y - 1 < len(pcts) else 0.0
            equity = eq_value * vest_pct / 100 * (1 + growth) ** y * (1 - haircut)
            bonus = base * bonus_pct
            signing = sign1 if y == 1 else sign2 if y == 2 else 0.0
            cash = base + bonus + signing
            total = cash + equity + base * match + other
            cum += total
            per_year.append({"year": y, "base": money(base), "bonus": money(bonus), "signing": money(signing), "equity_vested": money(equity), "match": money(base * match), "other": money(other), "cash": money(cash), "total": money(total), "cumulative": money(cum)})
        avg = cum / years
        rows.append(
            {
                "name": name,
                "equity_grant_value": money(eq_value),
                "equity_note": eq_note,
                "vest_pct_by_year": pcts,
                "year_1_cash": per_year[0]["cash"],
                "year_1_total": per_year[0]["total"],
                "total_over_horizon": money(cum),
                "average_annual": money(avg),
                "equity_share_of_total_pct": pct(sum(p["equity_vested"] for p in per_year), cum),
                "col_index": col,
                "average_annual_col_adjusted": money(avg * 100 / col),
                "by_year": per_year,
            }
        )
    ranked = sorted(rows, key=lambda r: -r["average_annual_col_adjusted"])
    best = ranked[0]
    for r in rows:
        r["gap_to_best_annual"] = money(best["average_annual_col_adjusted"] - r["average_annual_col_adjusted"])
    cash_best = max(rows, key=lambda r: r["year_1_cash"])
    notes = [f"Bonus assumed paid at target; equity haircut {equity_haircut_pct:g}%, growth {equity_growth_pct:g}%/yr; sign-on counted in year 1 (and 2 if given)."]
    if cash_best["name"] != best["name"]:
        notes.append(f"{cash_best['name']} pays the most year-1 cash (${cash_best['year_1_cash']:,.0f}); {best['name']} wins on {years}-yr average — equity-weighted.")
    high_eq = [r["name"] for r in rows if r["equity_share_of_total_pct"] > 40]
    if high_eq:
        notes.append(f"Equity is > 40% of total for {', '.join(high_eq)} — confirm liquidity path, refresh policy and ask for a larger sign-on to de-risk years 1-2.")
    return {
        "horizon_years": years,
        "ranking": [r["name"] for r in ranked],
        "best": best["name"],
        "offers": rows,
        "notes": notes,
        "verdict": f"{best['name']} leads on {years}-year average total comp (${best['average_annual_col_adjusted']:,.0f}/yr COL-adjusted)"
        + (f", ahead of {ranked[1]['name']} by ${ranked[0]['average_annual_col_adjusted'] - ranked[1]['average_annual_col_adjusted']:,.0f}/yr." if len(ranked) > 1 else "."),
    }


def _add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    y += d.year
    m += 1
    day = min(d.day, [31, 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return date(y, m, day)


@AGENT.tool
def vesting_schedule(
    grant_value: float,
    start_date: str,
    vesting_years: int = 4,
    cliff_months: int = 12,
    frequency: Literal["monthly", "quarterly", "annual"] = "quarterly",
    schedule: Literal["even", "amazon", "front", "back", "custom"] = "even",
    custom_vest_pct: list[float] | None = None,
    leave_date: str = "",
) -> dict:
    """Build the exact vest-date calendar for an equity grant (cliff, cadence, back-loaded schedules) and what leaving on a date forfeits.

    Args:
        grant_value: Total grant value in dollars (or share count — the math is proportional).
        start_date: Vesting commencement date, YYYY-MM-DD (usually the start date).
        vesting_years: Total vesting period in years (1-10).
        cliff_months: Months before the first vest (0 = no cliff; 12 is standard).
        frequency: Vest cadence after the cliff: monthly, quarterly or annual.
        schedule: Per-year split: even, amazon (5/15/40/40), front (40/30/20/10), back (10/20/30/40) or custom.
        custom_vest_pct: Per-year percentages summing to 100 when schedule is custom.
        leave_date: Optional YYYY-MM-DD to compute vested vs forfeited if the person leaves that day.
    """
    grant = require_number(grant_value, "grant_value", 0)
    if grant <= 0:
        raise ToolError("grant_value must be > 0.")
    start = dates.parse_date(start_date)
    if not 1 <= vesting_years <= 10:
        raise ToolError("vesting_years must be 1-10.")
    if not 0 <= cliff_months <= vesting_years * 12:
        raise ToolError("cliff_months must be between 0 and the full vesting period.")
    if schedule == "custom" and not custom_vest_pct:
        raise ToolError("schedule 'custom' needs custom_vest_pct.")
    year_pcts = _year_pcts(schedule if schedule != "custom" else "even", custom_vest_pct if schedule == "custom" else None, vesting_years)
    step = {"monthly": 1, "quarterly": 3, "annual": 12}[frequency]
    total_months = vesting_years * 12
    # Amount accrued per month, by year of service.
    monthly_accrual = [grant * year_pcts[y] / 100 / 12 for y in range(vesting_years)]
    events = []
    accrued_unpaid = 0.0
    cum = 0.0
    for m in range(1, total_months + 1):
        accrued_unpaid += monthly_accrual[(m - 1) // 12]
        is_vest_point = m >= cliff_months and (m == cliff_months or (m - cliff_months) % step == 0 or m == total_months)
        if cliff_months == 0 and m % step != 0 and m != total_months:
            is_vest_point = False
        if is_vest_point and accrued_unpaid > 0:
            cum += accrued_unpaid
            events.append({"n": len(events) + 1, "date": _add_months(start, m).isoformat(), "month": m, "amount": money(accrued_unpaid), "cumulative": money(cum), "cumulative_pct": pct(cum, grant), "cliff": m == cliff_months and cliff_months > 0})
            accrued_unpaid = 0.0
    leave = None
    if leave_date:
        ld = dates.parse_date(leave_date)
        vested = sum(e["amount"] for e in events if dates.parse_date(e["date"]) <= ld)
        leave = {"leave_date": ld.isoformat(), "vested": money(vested), "vested_pct": pct(vested, grant), "forfeited": money(grant - vested), "next_vest": next((e["date"] for e in events if dates.parse_date(e["date"]) > ld), None)}
    cliff_event = next((e for e in events if e["cliff"]), None)
    by_year = {f"year_{y + 1}": money(grant * year_pcts[y] / 100) for y in range(vesting_years)}
    return {
        "grant_value": money(grant),
        "start_date": start.isoformat(),
        "end_date": _add_months(start, total_months).isoformat(),
        "schedule": schedule,
        "year_pcts": year_pcts,
        "by_year": by_year,
        "cliff": {"months": cliff_months, "date": cliff_event["date"], "amount": cliff_event["amount"]} if cliff_event else None,
        "events": events,
        "event_count": len(events),
        "if_leave": leave,
        "verdict": (f"{len(events)} vest events from {events[0]['date']} to {events[-1]['date']}; " if events else "")
        + (f"cliff {cliff_event['date']} pays ${cliff_event['amount']:,.0f}. " if cliff_event else "no cliff. ")
        + (f"Year-1 vest is only {year_pcts[0]:g}% — negotiate sign-on to bridge." if year_pcts[0] < 20 else ""),
    }


@AGENT.tool
def plan_counter(
    offer_base: float,
    walk_away_base: float,
    target_base: float = 0,
    market_p50: float = 0,
    market_p75: float = 0,
    competing_offer_base: float = 0,
    current_base: float = 0,
    band_max: float = 0,
) -> dict:
    """Size a credible counter: the ask, expected landing, credibility check and fallback levers (sign-on, equity) in order.

    Rules: anchor at the strongest justified number (p75 / competing offer / target), keep the ask
    10-25% above the offer unless a competing offer justifies more, never below your walk-away.

    Args:
        offer_base: Base salary offered.
        walk_away_base: The minimum base you would accept (your BATNA line).
        target_base: The base you actually want (optional).
        market_p50: Market median base for the role/level/location, if known.
        market_p75: Market 75th percentile base, if known.
        competing_offer_base: Base from a competing written offer, if any.
        current_base: Your current base, if employed.
        band_max: Top of the company's stated band for the role, if the recruiter shared it.
    """
    offer = require_number(offer_base, "offer_base", 1)
    walk = require_number(walk_away_base, "walk_away_base", 0)
    target = require_number(target_base, "target_base", 0)
    p50 = require_number(market_p50, "market_p50", 0)
    p75 = require_number(market_p75, "market_p75", 0)
    comp = require_number(competing_offer_base, "competing_offer_base", 0)
    cur = require_number(current_base, "current_base", 0)
    band = require_number(band_max, "band_max", 0)
    if walk > offer * 1.6:
        raise ToolError("walk_away_base is more than 60% above the offer — this isn't a negotiation, it's a mismatch; reconsider the role or the walk-away.")
    candidates = []
    if p75:
        candidates.append(("market p75", p75))
    if comp:
        candidates.append(("competing offer", comp * 1.05))
    if target:
        candidates.append(("your target", target))
    if p50 and not p75:
        candidates.append(("market median +10%", p50 * 1.10))
    if not candidates:
        candidates.append(("standard 12% counter", offer * 1.12))
    justification, anchor = max(candidates, key=lambda c: c[1])
    ceiling = offer * (1.35 if comp else 1.25)
    ask = min(anchor, ceiling)
    if band:
        ask = min(ask, band)
    ask = max(ask, offer * 1.08)  # a counter under 8% isn't worth the conversation
    if walk > ask:
        ask = walk
    ask = round(ask / 500) * 500  # round, human number
    ask_pct = pct(ask - offer, offer)
    expected = round((offer + ask) / 2 / 500) * 500
    if comp and comp > expected:
        expected = round(comp / 500) * 500
    credibility = "strong" if (comp or p75) else "moderate" if (p50 or target) else "weak — get market data before the call"
    if ask_pct > 25 and not comp:
        credibility = "at risk — > 25% above offer without a competing offer; expect pushback"
    below_market = p50 and offer < p50
    levers = []
    gap = max(0.0, ask - expected)
    levers.append({"lever": "base", "ask": money(ask), "why": justification, "note": "ask first; everything else is fallback"})
    levers.append({"lever": "signing bonus", "ask": money(round(gap * 1.5 / 500) * 500 or round(offer * 0.10 / 500) * 500), "why": "bridges the base gap for year 1-2; one-time cost is easier for them to approve", "note": "ask if base is 'fixed by the band'"})
    levers.append({"lever": "equity", "ask": money(round(gap * 4 / 1000) * 1000 or round(offer * 0.25 / 1000) * 1000), "why": "4-year value of the base gap; grants are often more flexible than base", "note": "ask for grant size or a guaranteed refresh at 12 months"})
    levers.append({"lever": "review at 6 months", "ask": None, "why": "written comp review with a target number", "note": "use when they can't move now"})
    levers.append({"lever": "start date / PTO / remote / title", "ask": None, "why": "non-cash, low cost to them", "note": "last; never trade base for these"})
    script_line = f"Based on {justification}, I'm looking for ${ask:,.0f} on base. If you can get there, I'm ready to sign this week."
    if comp:
        script_line = f"I have a written offer at ${comp:,.0f}; I'd much rather join you. At ${ask:,.0f} base I'd sign this week."
    warnings = []
    if cur and offer < cur * 1.10:
        warnings.append(f"offer is only {pct(offer - cur, cur)}% above current base — a move usually needs ≥ 10-15% to be worth the risk")
    if below_market:
        warnings.append(f"offer is ${p50 - offer:,.0f} below market median — say so explicitly, it is your strongest line")
    if band and ask >= band:
        warnings.append("ask hits the top of the stated band — expect to win it only with a competing offer; shift weight to sign-on/equity")
    return {
        "offer_base": money(offer),
        "ask_base": money(ask),
        "ask_pct_above_offer": ask_pct,
        "justification": justification,
        "expected_landing": money(expected),
        "expected_pct_above_offer": pct(expected - offer, offer),
        "walk_away_base": money(walk),
        "credibility": credibility,
        "levers_in_order": levers,
        "script_line": script_line,
        "warnings": warnings,
        "verdict": f"Counter at ${ask:,.0f} (+{ask_pct}%) citing {justification}; expect to land near ${expected:,.0f}. Credibility: {credibility}.",
    }


@AGENT.tool
def raise_value(base_before: float, base_after: float, years: int = 10, annual_raise_pct: float = 3.0, bonus_pct: float = 0, match_pct: float = 0) -> dict:
    """Show what a base-salary increase is worth over time: the gap compounds through every future percentage raise, bonus and match.

    Args:
        base_before: Base before negotiating (the offer, or current salary).
        base_after: Base after negotiating (the landing).
        years: Horizon in years (1-40; default 10).
        annual_raise_pct: Assumed annual raise applied to base each year (default 3).
        bonus_pct: Target bonus as % of base, if bonus scales with base (default 0).
        match_pct: Retirement match as % of base (default 0).
    """
    b0 = require_number(base_before, "base_before", 1)
    b1 = require_number(base_after, "base_after", 0)
    if not 1 <= years <= 40:
        raise ToolError("years must be 1-40.")
    r = require_number(annual_raise_pct, "annual_raise_pct", -20, 50) / 100
    bp = require_number(bonus_pct, "bonus_pct", 0, 300) / 100
    mp = require_number(match_pct, "match_pct", 0, 100) / 100
    mult = 1 + bp + mp
    by_year = []
    cum_before = cum_after = 0.0
    for y in range(1, years + 1):
        g = (1 + r) ** (y - 1)
        a, b = b0 * g * mult, b1 * g * mult
        cum_before += a
        cum_after += b
        by_year.append({"year": y, "before": money(a), "after": money(b), "difference": money(b - a), "cumulative_difference": money(cum_after - cum_before)})
    diff = cum_after - cum_before
    minutes_value = diff / 20 if diff > 0 else 0  # value per minute of a 20-minute negotiation call
    return {
        "increase": money(b1 - b0),
        "increase_pct": pct(b1 - b0, b0),
        "years": years,
        "annual_raise_pct": annual_raise_pct,
        "total_difference": money(diff),
        "year_final_difference": by_year[-1]["difference"],
        "by_year": by_year,
        "per_minute_of_a_20_minute_call": money(minutes_value),
        "verdict": f"A ${b1 - b0:,.0f} ({pct(b1 - b0, b0)}%) base increase is worth ${diff:,.0f} over {years} years at {annual_raise_pct:g}% raises"
        + (f" — about ${minutes_value:,.0f} per minute of a 20-minute conversation." if diff > 0 else "."),
    }
