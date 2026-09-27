"""Vendor Evaluator — RFP scoring with knockouts, multi-year TCO, contract-risk review and SLA math."""

from __future__ import annotations

from datetime import date, timedelta

from ...core import Agent, ToolError
from ...lib import dates
from ._common import as_float, as_str, as_str_list, md_table, require_dict, require_list

AGENT = Agent(
    slug="vendor-evaluator",
    name="Vendor Evaluator",
    category="ops",
    tagline="Pick the right vendor: must-have knockouts, weighted RFP scores, true 3-year TCO and a contract red-flag review.",
    description=(
        "Runs a procurement-grade vendor selection: separates must-haves from nice-to-haves, scores RFP "
        "responses on weighted criteria with category subtotals, computes total cost of ownership over 3-5 "
        "years (seats, growth, escalators, implementation, internal labour, exit cost, NPV), reviews contract "
        "terms for auto-renewal traps and missing protections with exact notice deadlines, and turns SLA "
        "percentages into minutes of allowed downtime and credits owed."
    ),
    triggers=[
        "compare these vendors / tools / SaaS options",
        "score the RFP responses",
        "what's the total cost of ownership over 3 years",
        "review this contract / MSA / order form for red flags",
        "when do I need to cancel to avoid auto-renewal",
        "what does 99.9% uptime actually mean",
    ],
    examples=[
        "We have proposals from 3 CRM vendors — here are the criteria, scores and pricing. Which one and why?",
        "Vendor A is $40/seat with a $20k setup, Vendor B is $55/seat all-in. 120 seats growing 20%/yr — 3-year TCO?",
        "Here are the key terms of the order form. Anything I should push back on before signing Friday?",
        "Their SLA is 99.5% with 10% credits — how many hours of downtime a month is that?",
    ],
    connectors=["Google Sheets", "Notion", "Google Docs", "Slack", "DocuSign", "HubSpot"],
    playbook="""
    ## Standard
    You are a head of procurement who has negotiated hundreds of SaaS and services contracts.
    Excellent means: the recommendation is defensible to the CFO (true cost, not sticker
    price), to the CISO (must-haves verified, not promised), and to the team (weighted on
    what they actually need). The one metric: **decision quality a year later** — no
    surprise renewals, no hidden costs, no "we didn't know it couldn't do X".

    ## Intake
    Need: the shortlist (2-6 vendors), what the tool must do (must-haves), what matters
    (criteria + rough weights), pricing details, and headcount now and in 3 years. Ask at
    most 2 questions, only if pricing or must-haves are missing entirely. Otherwise assume
    (e.g. 3-year horizon, 8% discount rate, 15% seat growth) and state it.

    ## Procedure
    1. **Split must-haves from criteria.** Must-haves are pass/fail (SSO/SAML, SOC 2 Type
       II, data residency, API, required integration, accessibility, budget ceiling). Everything
       else is a weighted criterion in 4-6 categories: functionality, usability, security &
       compliance, support & vendor viability, integration, cost. Lock weights before scoring.
    2. **Score** each vendor 1-5 per criterion with a one-line evidence note (demo seen /
       reference confirmed / claimed in RFP). Call `vendor_evaluator__score_rfp`. It applies
       knockouts (a vendor failing a must-have is out, whatever its score), computes weighted
       totals, category subtotals, gap to leader, and flags unverified must-haves.
    3. **Price the truth.** Price only the vendors that passed the must-haves — a knocked-out
       vendor's low TCO is irrelevant (include it only as a labelled reference). For each gather: one-time implementation, per-seat price,
       platform fees, annual increase (escalator), internal hours for setup and ongoing admin,
       exit/migration cost. Call `vendor_evaluator__calculate_tco` with a 3-year (or 5-year)
       horizon. Report TCO, NPV, cost per seat-month, and hidden-cost share. Sticker price
       under 60% of TCO is normal — say so.
    4. **Review the paper.** Extract the terms from the order form/MSA and call
       `vendor_evaluator__contract_risk_check`. It computes the exact cancellation-notice
       deadline and ranks red flags. Present the top 3-5 asks in priority order. This is not
       legal advice — flag anything on liability, indemnity, IP or data protection for counsel.
    5. **Translate the SLA.** Call `vendor_evaluator__sla_downtime` with the promised uptime
       and credit tiers (and, for a real outage, the `month` it happened in — a 30-day
       month allows ~1.5% less downtime than the average the headline figure uses). Report allowed downtime per month in minutes/hours and whether the
       credits are meaningful (usually they are not: 10% of a month's fee for 36 hours down).
    6. **Reference-check plan.** For the top 2: three questions to ask a customer of similar
       size — "what broke in the first 90 days", "how did support behave during an outage",
       "what did the renewal price increase look like".
    7. **Recommend** one vendor, the negotiation asks, and the decision the user should
       make by when. Act via connectors if present (sheet with scores/TCO; doc with the memo).

    ## Frameworks
    - **Weighting benchmarks**: functionality 30-40%, security/compliance 15-20%, usability
      15%, integration 10-15%, vendor viability & support 10-15%, cost 10-20% (cost is
      handled in TCO too — do not double-weight it).
    - **TCO formula**: subscription × seats × growth × escalator + platform fees +
      implementation + internal labour + training + exit cost, discounted at the company's
      cost of capital (8-12% for most SMBs).
    - **Negotiation levers**: multi-year with price cap (3-5%/yr), opt-out at 12 months,
      ramped seats, free implementation, removed auto-renew or 30-day notice, SLA with
      service credits AND termination right after 3 breaches, data export in standard
      format within 30 days of termination.
    - **Red-flag thresholds**: notice period > 60 days; auto-renew with term > 12 months;
      no price cap; liability cap < 12 months' fees; uptime < 99.9% for a system-of-record;
      unilateral right to change terms; payment terms < net-30.

    ## Output format
    ```
    # Vendor selection — <category> (<date>)
    **Recommendation:** <Vendor> · **3-yr TCO:** $X (NPV $Y) · **Score:** N/100 vs runner-up M · **Decide by:** <date>

    ## Must-haves
    | Must-have | Vendor A | Vendor B | Vendor C |
    | SSO/SAML | ✅ verified | ❌ | ⚠ claimed |

    ## Weighted score
    | Category (weight) | A | B | C |
    | … | | | |
    | **Total /100** | | | |

    ## 3-year TCO
    | | A | B | C |
    | Year 1 / 2 / 3 | | | |
    | **Total (NPV)** | | | |
    | Hidden-cost share | | | |

    ## Contract red flags (top asks, in order)
    1. <flag> → ask: <specific clause change>
    …
    Cancellation notice deadline: <date> (N days from today)

    ## SLA in plain terms
    99.9% = 43.8 min/month allowed downtime; credit at breach = $X (Y% of fee).

    ## Reference-check questions
    ```
    Scope note: not legal advice; route liability/indemnity/IP/data-protection clauses to counsel.

    ## Anti-patterns
    - Comparing sticker prices. Implementation, admin time and exit cost routinely double it.
    - Scoring must-haves as 1-5 criteria. Missing SOC 2 is not "a 2 on security" — it's out.
    - Letting the vendor's demo script drive the criteria. Score against the team's workflow.
    - Missing the notice window. Compute the date; put it in the calendar; two reminders.
    - Averaging unverified claims with verified ones. Mark evidence level per score.
    - Ignoring the exit. Ask "how do we get our data out" before signing, not after.
    """,
)


@AGENT.tool
def score_rfp(vendors: list[dict], criteria: list[dict], must_haves: list[str] = [], scale_max: float = 5) -> dict:
    """Score RFP responses: must-have knockouts, weighted totals /100, category subtotals, gap to leader, unverified flags.

    Args:
        vendors: List of {"name": str, "scores": {criterion: 1..scale_max}, "must_haves": {requirement: true|false|"unverified"}}.
        criteria: List of {"name": str, "weight": number, "category": optional grouping like "Security"}.
        must_haves: Names of pass/fail requirements every vendor must meet.
        scale_max: Top of the scoring scale (default 5).
    """
    vendors = require_list(vendors, "vendors", 30)
    criteria = require_list(criteria, "criteria", 40)
    must = as_str_list(must_haves, "must_haves", 40)
    if not (1 <= scale_max <= 100):
        raise ToolError("scale_max must be between 1 and 100.")
    crit = []
    for i, c in enumerate(criteria, 1):
        if isinstance(c, str):
            c = {"name": c, "weight": 1}
        if not isinstance(c, dict):
            raise ToolError(f"criteria[{i}] must be {{'name','weight','category'}}.")
        crit.append({"name": as_str(c.get("name"), f"criteria[{i}].name", max_len=80), "weight": as_float(c.get("weight", 1), f"criteria[{i}].weight", lo=0), "category": as_str(c.get("category", "General"), "category", required=False, max_len=40) or "General"})
    wsum = sum(c["weight"] for c in crit)
    if wsum <= 0:
        raise ToolError("Criteria weights must sum to more than 0.")
    results, knocked = [], []
    for i, v in enumerate(vendors, 1):
        if not isinstance(v, dict):
            raise ToolError(f"vendors[{i}] must be {{'name','scores','must_haves'}}.")
        name = as_str(v.get("name"), f"vendors[{i}].name", max_len=80)
        scores = v.get("scores")
        if not isinstance(scores, dict):
            raise ToolError(f"Vendor {name!r} needs a 'scores' object keyed by criterion.")
        low = {str(k).lower(): val for k, val in scores.items()}
        mh = {str(k).lower(): val for k, val in (v.get("must_haves") or {}).items()} if isinstance(v.get("must_haves"), dict) else {}
        failed, unverified = [], []
        for m in must:
            val = mh.get(m.lower())
            if val is False or (isinstance(val, str) and val.strip().lower() in ("no", "false", "fail", "n")):
                failed.append(m)
            elif val is True or (isinstance(val, str) and val.strip().lower() in ("yes", "true", "pass", "y", "verified")):
                continue
            else:
                unverified.append(m)
        total, by_cat, weakest = 0.0, {}, None
        for c in crit:
            if c["name"].lower() not in low:
                raise ToolError(f"Vendor {name!r} has no score for {c['name']!r}.")
            s = as_float(low[c["name"].lower()], f"{name}.{c['name']}", lo=0, hi=scale_max)
            pts = 100 * (c["weight"] / wsum) * s / scale_max
            total += pts
            cat = by_cat.setdefault(c["category"], {"points": 0.0, "max": 0.0})
            cat["points"] += pts
            cat["max"] += 100 * c["weight"] / wsum
            if weakest is None or s < weakest[1]:
                weakest = (c["name"], s)
        row = {
            "vendor": name,
            "score": round(total, 1),
            "by_category": {k: {"points": round(vv["points"], 1), "of": round(vv["max"], 1), "pct": round(100 * vv["points"] / vv["max"]) if vv["max"] else None} for k, vv in by_cat.items()},
            "weakest_criterion": weakest[0] if weakest else None,
            "failed_must_haves": failed,
            "unverified_must_haves": unverified,
            "eligible": not failed,
        }
        if failed:
            knocked.append({"vendor": name, "failed": failed})
        results.append(row)
    eligible = sorted([r for r in results if r["eligible"]], key=lambda r: -r["score"])
    for rank, r in enumerate(eligible, 1):
        r["rank"] = rank
        r["gap_to_leader"] = round(eligible[0]["score"] - r["score"], 1)
    for r in results:
        r.setdefault("rank", None)
        r.setdefault("gap_to_leader", None)
    cats = list(dict.fromkeys(c["category"] for c in crit))
    table = md_table(
        ["Category (weight%)"] + [r["vendor"] for r in results],
        [[f"{cat} ({round(sum(c['weight'] for c in crit if c['category'] == cat) / wsum * 100)}%)"] + [r["by_category"].get(cat, {}).get("points", 0) for r in results] for cat in cats]
        + [["**Total /100**"] + [f"**{r['score']}**" + (" (OUT)" if not r["eligible"] else "") for r in results]],
    )
    if not eligible:
        verdict = "Every vendor fails at least one must-have: " + "; ".join(f"{k['vendor']}: {', '.join(k['failed'])}" for k in knocked) + ". Re-check the requirements or widen the shortlist."
    else:
        lead = eligible[0]
        verdict = f"{lead['vendor']} leads at {lead['score']}/100"
        if len(eligible) > 1:
            verdict += f", {eligible[1]['gap_to_leader']} ahead of {eligible[1]['vendor']}" + (" (close — verify with references and TCO)" if eligible[1]["gap_to_leader"] < 5 else "")
        verdict += "."
        if knocked:
            verdict += " Knocked out: " + ", ".join(f"{k['vendor']} ({', '.join(k['failed'])})" for k in knocked) + "."
        unv = [r for r in eligible if r["unverified_must_haves"]]
        if unv:
            verdict += " Unverified must-haves: " + "; ".join(f"{r['vendor']}: {', '.join(r['unverified_must_haves'])}" for r in unv) + " — get evidence before deciding."
    return {"ranking": eligible, "all_vendors": results, "knocked_out": knocked, "categories": cats, "markdown_table": table, "verdict": verdict}


@AGENT.tool
def calculate_tco(vendors: list[dict], years: int = 3, discount_rate_pct: float = 8.0, hourly_rate: float = 75.0, billing: str = "annual_advance") -> dict:
    """Multi-year total cost of ownership per vendor: seats × growth × escalator, fees, implementation, internal labour, exit, NPV.

    Args:
        vendors: List of {"name", "per_seat_month", "seats", "seat_growth_pct_yr", "platform_fee_yr", "annual_increase_pct", "one_time", "internal_hours_setup", "internal_hours_per_month", "training", "exit_cost", "other_annual"}. Missing fields default to 0.
        years: Horizon in years (1-10). Use 3 for SaaS, 5 for systems of record.
        discount_rate_pct: Annual discount rate for NPV (default 8).
        hourly_rate: Fully loaded internal hourly cost used to price internal hours (default 75).
        billing: When subscription/platform fees are paid, for NPV: "annual_advance" (default — standard SaaS order forms bill each year up front) or "arrears" (end of each year). Internal labour, other costs and exit are discounted at year end; one-time costs at signing.
    """
    if billing not in ("annual_advance", "arrears"):
        raise ToolError("billing must be 'annual_advance' or 'arrears'.")
    vendors = require_list(vendors, "vendors", 20)
    if not (1 <= years <= 10):
        raise ToolError("years must be 1-10.")
    r = as_float(discount_rate_pct, "discount_rate_pct", lo=0, hi=50) / 100
    rate = as_float(hourly_rate, "hourly_rate", lo=0, hi=1000)
    out = []
    for i, v in enumerate(vendors, 1):
        if not isinstance(v, dict):
            raise ToolError(f"vendors[{i}] must be an object with pricing fields.")
        name = as_str(v.get("name"), f"vendors[{i}].name", max_len=80)
        g = lambda k, lo=0.0, hi=None: as_float(v.get(k, 0), f"{name}.{k}", lo=lo, hi=hi, default=0.0)
        psm, seats = g("per_seat_month"), g("seats")
        growth, esc = g("seat_growth_pct_yr", -100, 500) / 100, g("annual_increase_pct", -100, 100) / 100
        platform, one_time, training, exit_cost, other = g("platform_fee_yr"), g("one_time"), g("training"), g("exit_cost"), g("other_annual")
        setup_h, admin_h = g("internal_hours_setup"), g("internal_hours_per_month")
        raw_total = 0.0
        yearly, npv, subscription_total, hidden_total = [], one_time + training + setup_h * rate, 0.0, one_time + training + setup_h * rate
        for y in range(1, years + 1):
            seats_y = seats * (1 + growth) ** (y - 1)
            escal = (1 + esc) ** (y - 1)
            sub = psm * 12 * seats_y * escal + platform * escal
            internal = admin_h * 12 * rate
            ex = exit_cost if y == years else 0.0
            year_cost = sub + internal + other + ex + (one_time + training + setup_h * rate if y == 1 else 0.0)
            subscription_total += sub
            hidden_total += internal + ex
            npv += sub / (1 + r) ** (y - 1 if billing == "annual_advance" else y) + (internal + other + ex) / (1 + r) ** y
            raw_total += year_cost
            yearly.append({"year": y, "seats": round(seats_y, 1), "subscription": round(sub), "internal_labour": round(internal), "one_time": round(one_time + training + setup_h * rate) if y == 1 else 0, "exit": round(ex), "other": round(other), "total": round(year_cost)})
        total = raw_total  # sum unrounded years; rounding each year first drifts by a dollar or two
        seat_months = sum(yr["seats"] for yr in yearly) * 12
        out.append(
            {
                "vendor": name,
                "years": years,
                "total_nominal": round(total),
                "npv": round(npv),
                "sticker_subscription_only": round(subscription_total),
                "hidden_cost_share_pct": round(100 * hidden_total / total) if total else 0,
                "avg_cost_per_seat_month": round(total / seat_months, 2) if seat_months else None,
                "year_1": yearly[0]["total"],
                "by_year": yearly,
            }
        )
    out.sort(key=lambda x: x["npv"])
    cheapest = out[0]
    for o in out:
        o["rank"] = out.index(o) + 1
        o["delta_vs_cheapest"] = round(o["npv"] - cheapest["npv"])
        o["delta_vs_cheapest_pct"] = round(100 * (o["npv"] - cheapest["npv"]) / cheapest["npv"], 1) if cheapest["npv"] else None
    table = md_table(
        ["Vendor"] + [f"Year {y}" for y in range(1, years + 1)] + ["Total", "NPV", "Hidden %", "$/seat-mo"],
        [[o["vendor"]] + [yr["total"] for yr in o["by_year"]] + [o["total_nominal"], o["npv"], o["hidden_cost_share_pct"], o["avg_cost_per_seat_month"]] for o in out],
    )
    verdict = f"Cheapest over {years} years: {cheapest['vendor']} at ${cheapest['total_nominal']:,} (NPV ${cheapest['npv']:,}, {cheapest['hidden_cost_share_pct']}% hidden costs)."
    if len(out) > 1:
        verdict += f" {out[1]['vendor']} costs ${out[1]['delta_vs_cheapest']:,} ({out[1]['delta_vs_cheapest_pct']}%) more."
    lowest_sticker = min(out, key=lambda o: o["sticker_subscription_only"])
    if lowest_sticker["vendor"] != cheapest["vendor"]:
        verdict += f" Note: {lowest_sticker['vendor']} has the lowest sticker price but not the lowest TCO."
    return {"ranking": out, "assumptions": {"years": years, "discount_rate_pct": discount_rate_pct, "hourly_rate": rate, "billing": billing, "npv_timing": "one-time at signing; subscription at the start of each year" if billing == "annual_advance" else "one-time at signing; subscription at the end of each year"}, "markdown_table": table, "verdict": verdict}


_BOOL_TRUE = ("yes", "true", "y", "1", "included")


def _add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    try:
        return d.replace(year=d.year + y, month=m + 1)
    except ValueError:  # Jan 31 + 1 month -> Feb 28/29
        return (d.replace(year=d.year + y, month=m + 1, day=1) + timedelta(days=31)).replace(day=1) - timedelta(days=1)


def _b(v) -> bool | None:
    if isinstance(v, bool):
        return v
    if v is None or v == "":
        return None
    return str(v).strip().lower() in _BOOL_TRUE


@AGENT.tool
def contract_risk_check(terms: dict, today: str = "", annual_fees: float = 0) -> dict:
    """Review order-form/MSA terms: auto-renew notice deadline (exact date), missing protections, ranked red flags and asks.

    Not legal advice — it applies procurement rules of thumb; liability, indemnity, IP and data-protection clauses need counsel.

    Args:
        terms: Object with any of: start_date, term_months, renewal_date (first day of the renewal term), term_end_date (last day of the current term), renewal_term_months, auto_renew (bool), notice_days, price_cap_pct, sla_uptime_pct, sla_credits (bool), termination_for_convenience (bool), termination_notice_days, data_export (bool), data_deletion_days, liability_cap_months (cap as months of fees), payment_terms_days, minimum_commit (bool), unilateral_changes (bool), soc2 (bool), dpa (bool).
        today: Today's date as YYYY-MM-DD (defaults to today) for deadline math.
        annual_fees: Annual contract value, used to express caps and credits in dollars (optional).
    """
    terms = require_dict(terms, "terms")
    now = dates.parse_date(today) if today else date.today()
    fees = as_float(annual_fees, "annual_fees", lo=0, default=0.0)
    t = {str(k).lower(): v for k, v in terms.items()}
    flags: list[dict] = []

    def flag(sev: str, issue: str, ask: str, weight: int) -> None:
        flags.append({"severity": sev, "issue": issue, "ask": ask, "weight": weight})

    renewal = None
    if t.get("renewal_date"):
        renewal = dates.parse_date(str(t["renewal_date"]))
    elif t.get("start_date") and t.get("term_months"):
        start = dates.parse_date(str(t["start_date"]))
        months = int(as_float(t["term_months"], "term_months", lo=1, hi=120))
        renewal = _add_months(start, months)
    if t.get("term_end_date"):
        renewal = dates.parse_date(str(t["term_end_date"])) + timedelta(days=1)
    auto = _b(t.get("auto_renew"))
    notice_days = int(as_float(t.get("notice_days"), "notice_days", lo=0, hi=365, default=0.0)) if t.get("notice_days") not in (None, "") else None
    term_months = int(as_float(t.get("term_months"), "term_months", lo=1, hi=120)) if t.get("term_months") not in (None, "") else None
    renewal_term = int(as_float(t.get("renewal_term_months"), "renewal_term_months", lo=1, hi=120)) if t.get("renewal_term_months") not in (None, "") else (term_months or 12)
    deadline = term_end = next_deadline = next_renewal = None
    if auto:
        nd = notice_days if notice_days is not None else 30
        if renewal:
            # "N days prior to the end of the term": the term's last day is the day BEFORE the renewal date;
            # counting from the renewal date would give a deadline one day too late.
            term_end = renewal - timedelta(days=1)
            deadline = term_end - timedelta(days=nd)
            if deadline < now:  # window missed: it renews; compute the next cycle's deadline
                next_renewal = _add_months(renewal, renewal_term)
                next_deadline = next_renewal - timedelta(days=1) - timedelta(days=nd)
        if notice_days is None:
            flag("medium", "Auto-renews but notice period not stated — assume 30 days until confirmed.", "Confirm the notice period in writing; ask for 30 days.", 2)
        elif notice_days > 60:
            flag("high", f"Auto-renew with {notice_days}-day notice — easy to miss.", "Reduce notice to 30 days, or remove auto-renew.", 3)
        if term_months and term_months > 12:
            flag("high", f"Auto-renews for another {term_months}-month term.", "Renewal term of 12 months max, or month-to-month after initial term.", 3)
    elif auto is None:
        flag("medium", "Auto-renewal not specified.", "Confirm whether the contract auto-renews and on what notice.", 2)
    cap = t.get("price_cap_pct")
    if cap in (None, ""):
        flag("high", "No cap on renewal price increases.", "Cap annual increases at 3-5% (or CPI) for renewals.", 3)
    else:
        capf = as_float(cap, "price_cap_pct", lo=0, hi=100)
        if capf > 7:
            flag("medium", f"Price cap of {capf:g}%/yr is above market (3-5%).", "Negotiate to ≤ 5%.", 2)
    sla = t.get("sla_uptime_pct")
    if sla in (None, ""):
        flag("medium", "No uptime SLA stated.", "Add 99.9% uptime with service credits and a termination right after 3 breaches in 12 months.", 2)
    else:
        slaf = as_float(sla, "sla_uptime_pct", lo=0, hi=100)
        if slaf < 99.9:
            flag("medium", f"SLA of {slaf:g}% allows ~{round((100 - slaf) / 100 * 43829.06)} min downtime per month.", "Ask for 99.9%+ for a business-critical system.", 2)
        if _b(t.get("sla_credits")) is False:
            flag("medium", "SLA has no service credits — it is a promise with no teeth.", "Add tiered credits (10/25/50% of monthly fee) and termination after repeated breach.", 2)
    if _b(t.get("termination_for_convenience")) is False:
        flag("medium", "No termination for convenience.", "Add termination for convenience on 60-90 days' notice after month 12 (pro-rated refund of prepaid fees).", 2)
    if _b(t.get("data_export")) is False or t.get("data_export") in (None, ""):
        flag("high", "Data export at termination not guaranteed.", "Full export in a standard format (CSV/JSON) within 30 days of termination, free of charge.", 3)
    if t.get("data_deletion_days") not in (None, "") and as_float(t["data_deletion_days"], "data_deletion_days", lo=0) > 90:
        flag("low", f"Data retained {t['data_deletion_days']} days after termination.", "Deletion within 30-90 days with written certification.", 1)
    liab = t.get("liability_cap_months")
    if liab not in (None, ""):
        lf = as_float(liab, "liability_cap_months", lo=0)
        if lf < 12:
            flag("high", f"Liability capped at {lf:g} months of fees (${round(fees * lf / 12):,} on ${fees:,.0f}/yr)." if fees else f"Liability capped at {lf:g} months of fees.", "Cap at 12 months' fees minimum; carve out data breach, confidentiality, IP indemnity (super-cap 2-3×). Route to counsel.", 3)
    else:
        flag("medium", "Liability cap not stated.", "Confirm the cap and carve-outs; route to counsel.", 2)
    pay = t.get("payment_terms_days")
    if pay not in (None, "") and as_float(pay, "payment_terms_days", lo=0) < 30:
        flag("low", f"Payment terms net-{int(as_float(pay, 'payment_terms_days'))}.", "Net-30 minimum; annual prepay only in exchange for a discount.", 1)
    if _b(t.get("unilateral_changes")) is True:
        flag("high", "Vendor may change terms unilaterally.", "Changes require mutual written agreement; at minimum, right to terminate on adverse change.", 3)
    if _b(t.get("minimum_commit")) is True and _b(t.get("termination_for_convenience")) is not True:
        flag("medium", "Minimum commitment with no exit.", "Ramp the commitment (e.g. 60% year 1) or add a 12-month opt-out.", 2)
    if _b(t.get("soc2")) is False:
        flag("high", "No SOC 2 (or equivalent) attestation.", "Require SOC 2 Type II or ISO 27001 within 12 months, with a termination right otherwise.", 3)
    if _b(t.get("dpa")) is False:
        flag("high", "No data processing agreement.", "Attach a DPA (GDPR/CCPA) before signature. Route to counsel/privacy.", 3)
    sev_order = {"high": 0, "medium": 1, "low": 2}
    flags.sort(key=lambda f: (sev_order[f["severity"]], -f["weight"]))
    score = max(0, 100 - sum({"high": 15, "medium": 8, "low": 3}[f["severity"]] for f in flags))
    risk = "HIGH" if score < 50 else "MEDIUM" if score < 75 else "LOW"
    days_left = (deadline - now).days if deadline else None
    deadline_note = None
    send_by = None
    if deadline:
        send_by = dates.add_business_days(deadline, -3) if days_left is not None and days_left >= 0 else None
        if days_left < 0:
            deadline_note = (
                f"Notice deadline {dates.fmt(deadline)} PASSED {-days_left} days ago: the contract renews on {renewal.isoformat()} "
                f"for {renewal_term} months. Next non-renewal deadline: {dates.fmt(next_deadline)}. Ask the vendor for a "
                f"one-time waiver now, and put the next deadline in the calendar."
            )
        elif days_left <= 7:
            deadline_note = f"Notice deadline {dates.fmt(deadline)} — only {days_left} days away: send written notice (per the notices clause) now, and get a delivery receipt."
        else:
            reminders = [r for r in (deadline - timedelta(days=30), deadline - timedelta(days=7)) if r > now]
            deadline_note = f"Notice deadline {dates.fmt(deadline)} — {days_left} days from {now.isoformat()}; send by {send_by.isoformat()} to allow for delivery" + (f"; reminders on {', '.join(r.isoformat() for r in reminders)}." if reminders else ".")
    return {
        "as_of": now.isoformat(),
        "renewal_date": renewal.isoformat() if renewal else None,
        "term_end_date": term_end.isoformat() if term_end else (renewal - timedelta(days=1)).isoformat() if renewal else None,
        "auto_renew": auto,
        "notice_deadline": deadline.isoformat() if deadline else None,
        "notice_deadline_rule": f"{notice_days if notice_days is not None else 30} days before the term's last day ({term_end.isoformat()}); notice must arrive on or before this date" if term_end else None,
        "recommended_send_by": send_by.isoformat() if send_by else None,
        "days_until_notice_deadline": days_left,
        "next_renewal_date": next_renewal.isoformat() if next_renewal else None,
        "next_notice_deadline": next_deadline.isoformat() if next_deadline else None,
        "deadline_note": deadline_note,
        "risk_score": score,
        "risk_level": risk,
        "flags": [{k: v for k, v in f.items() if k != "weight"} for f in flags],
        "top_asks": [f["ask"] for f in flags[:5]],
        "verdict": f"Contract risk {risk} ({score}/100): {sum(1 for f in flags if f['severity'] == 'high')} high, {sum(1 for f in flags if f['severity'] == 'medium')} medium, {sum(1 for f in flags if f['severity'] == 'low')} low flags. "
        + (deadline_note or "No auto-renew deadline computed.")
        + " Not legal advice.",
    }


_STANDARD_TIERS = [99.0, 99.5, 99.9, 99.95, 99.99, 99.999]
_MIN_PER_MONTH = 365.25 * 24 * 60 / 12  # 43829.06


@AGENT.tool
def sla_downtime(uptime_pct: float, monthly_fee: float = 0, credit_tiers: list[dict] = [], actual_downtime_minutes: float = -1, outage_cost_per_hour: float = 0, month: str = "") -> dict:
    """Turn an SLA percentage into allowed downtime per week/month/year, and compute the credit owed for an actual outage.

    Args:
        uptime_pct: Promised uptime, e.g. 99.9.
        monthly_fee: Monthly fee in dollars, to express credits in money (optional).
        credit_tiers: List of {"below_pct": 99.9, "credit_pct": 10} — credit as % of monthly fee when uptime falls below the threshold; highest matching credit applies.
        actual_downtime_minutes: Actual downtime in a month (optional, -1 = not provided).
        outage_cost_per_hour: Your cost of an outage per hour, to compare against credits (optional).
        month: The calendar month the outage happened in, "YYYY-MM". SLAs measure uptime per calendar month, so a 30-day month allows less downtime than the 30.44-day average; pass it whenever you check a real outage for breach/credit.
    """
    u = as_float(uptime_pct, "uptime_pct", lo=0, hi=100)
    if u < 90:
        raise ToolError("uptime_pct below 90 is not a meaningful SLA — check the number.")
    fee = as_float(monthly_fee, "monthly_fee", lo=0, default=0.0)
    down_frac = (100 - u) / 100
    allowed = {"per_week": round(down_frac * 7 * 24 * 60, 1), "per_month": round(down_frac * _MIN_PER_MONTH, 1), "per_year": round(down_frac * 365.25 * 24 * 60, 1)}
    ladder = [{"uptime_pct": t, "minutes_per_month": round((100 - t) / 100 * _MIN_PER_MONTH, 1), "hours_per_year": round((100 - t) / 100 * 365.25 * 24, 1)} for t in _STANDARD_TIERS]
    tiers = []
    for i, tier in enumerate(require_list(credit_tiers, "credit_tiers", 10, min_len=0), 1):
        if not isinstance(tier, dict):
            raise ToolError(f"credit_tiers[{i}] must be {{'below_pct','credit_pct'}}.")
        tiers.append({"below_pct": as_float(tier.get("below_pct"), f"credit_tiers[{i}].below_pct", lo=0, hi=100), "credit_pct": as_float(tier.get("credit_pct"), f"credit_tiers[{i}].credit_pct", lo=0, hi=100)})
    tiers.sort(key=lambda x: -x["below_pct"])
    month_minutes, month_label = _MIN_PER_MONTH, "average month (30.44 days)"
    if month:
        try:
            y, mo = (int(x) for x in str(month).strip()[:7].split("-"))
            first = date(y, mo, 1)
        except ValueError:
            raise ToolError(f"month must look like 2026-11, got {month!r}.") from None
        days_in = ((first.replace(day=28) + timedelta(days=4)).replace(day=1) - first).days
        month_minutes, month_label = days_in * 24 * 60, f"{first.strftime('%B %Y')} ({days_in} days)"
        allowed["this_month"] = round(down_frac * month_minutes, 1)
    actual = None
    if actual_downtime_minutes is not None and actual_downtime_minutes >= 0:
        act_up = 100 * (1 - actual_downtime_minutes / month_minutes)
        breach = act_up < u
        credit_pct = max((t["credit_pct"] for t in tiers if act_up < t["below_pct"]), default=0.0)
        credit_usd = round(fee * credit_pct / 100, 2)
        outage_cost = round(outage_cost_per_hour * actual_downtime_minutes / 60, 2) if outage_cost_per_hour else None
        actual = {
            "downtime_minutes": actual_downtime_minutes,
            "actual_uptime_pct": round(act_up, 4),
            "breach": breach,
            "measured_over": month_label,
            "over_allowance_minutes": round(max(0.0, actual_downtime_minutes - down_frac * month_minutes), 1),
            "credit_pct": credit_pct,
            "credit_usd": credit_usd,
            "your_outage_cost_usd": outage_cost,
            "credit_covers_pct_of_loss": round(100 * credit_usd / outage_cost, 1) if outage_cost else None,
        }
    verdict = f"{u:g}% uptime allows {allowed['per_month']:g} min ({allowed['per_month'] / 60:.1f} h) of downtime per month, {allowed['per_year'] / 60:.1f} h per year."
    if actual:
        verdict += f" Actual {actual_downtime_minutes:g} min = {actual['actual_uptime_pct']:.3f}% → " + ("BREACH" if actual["breach"] else "within SLA") + (f", credit {actual['credit_pct']:g}% (${actual['credit_usd']:,.2f})" if tiers else "") + (f" vs your loss ${actual['your_outage_cost_usd']:,.2f} ({actual['credit_covers_pct_of_loss']}% covered)" if actual["your_outage_cost_usd"] else "") + "."
    elif tiers and fee:
        verdict += f" Max credit on breach: {max(t['credit_pct'] for t in tiers):g}% = ${fee * max(t['credit_pct'] for t in tiers) / 100:,.2f}/month."
    return {"uptime_pct": u, "allowed_downtime_minutes": allowed, "standard_tiers": ladder, "credit_tiers": tiers, "actual": actual, "verdict": verdict}
