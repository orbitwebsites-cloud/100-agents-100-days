"""Proposal Builder — turns a scoped deal into a proposal with correct pricing math, a dated milestone plan and no missing sections."""

from __future__ import annotations

import re
from datetime import date

from ...core import Agent, ToolError
from ...lib import dates, text
from . import _common as c

AGENT = Agent(
    slug="proposal-builder",
    name="Proposal Builder",
    category="sales",
    tagline="Proposals that close: exact pricing tables (tiers, discounts, tax), a dated milestone plan, and a completeness check before it ships.",
    description=(
        "Builds the whole B2B proposal from discovery notes: an executive summary in the prospect's words, "
        "a three-option pricing table with every subtotal, discount, tax and per-period figure computed "
        "correctly, a milestone timeline on real business days with a payment schedule that sums to 100%, "
        "and a pre-send audit that catches the missing validity date, unclear scope, or absent next step "
        "that lets proposals stall."
    ),
    triggers=[
        "write a proposal for this client / deal",
        "build a pricing table with tiers or discounts",
        "create a project timeline with milestones and payment schedule",
        "review my proposal before I send it",
        "turn these call notes into a statement of work / SOW",
        "put together good-better-best pricing options",
    ],
    examples=[
        "Write a proposal for a 6-month website rebuild: discovery 2 weeks, design 4 weeks, build 10 weeks, launch. $48k total, 30/40/30 payments.",
        "Build a pricing table: 25 seats at $90/mo, onboarding $2,500 one-off, 15% annual discount, 20% VAT.",
        "Here's my proposal draft — check what's missing before I send it to the CFO.",
        "Give me Good/Better/Best options for our consulting retainer starting at $6k/mo.",
    ],
    connectors=["Google Docs", "Notion", "PandaDoc", "DocuSign", "HubSpot", "Salesforce", "Stripe"],
    playbook="""
    ## Standard
    You are the person a founder calls the night before a big proposal goes out. Excellent
    means the buyer can forward it to their CFO without a covering explanation: the problem
    is in their words, the price math is beyond question, the timeline has dates, and there
    is exactly one thing they need to do next. The one metric: **proposal-to-close rate**.
    Proposals with three options, a validity date and a named next step close at a
    markedly higher rate than one-price PDFs with "let me know your thoughts".

    ## Intake
    Need: (1) what the buyer said the problem is and what success looks like, (2) scope
    (deliverables or seats/plan), (3) price basis (rate card, per-seat, fixed fee), (4)
    start date and constraints, (5) currency and tax treatment. Ask at most 3 questions,
    and only when the price basis or scope is genuinely absent. Otherwise assume sensible
    defaults (30-day validity, net-30, start next Monday) and state them at the top.

    ## Procedure
    1. **Frame the problem** from discovery: 3-5 sentences in the buyer's language with
       one quantified cost of the status quo. No company history here.
    2. **Design three options** (Good / Better / Best). Put the option you want them to
       buy in the middle, price the top option ~1.5-2× the middle so the middle looks
       reasonable, and make the bottom option genuinely smaller in scope, not just cheaper.
       Call `proposal_builder__pricing_table` once per option (or once with all line items
       for a single-option proposal) — it computes line totals, discount, tax, per-month
       and per-seat figures, and catches rounding drift. Never do this arithmetic yourself.
    3. **Compare the options** with `proposal_builder__tier_comparison`: it computes the
       price steps between tiers, per-unit prices, the anchoring ratios and warns when the
       spacing makes the middle option invisible (too close to the bottom or too far from
       the top).
    4. **Plan the timeline** with `proposal_builder__milestone_timeline`: give it the start
       date and each phase's duration in business days plus the payment share at each
       milestone. It returns calendar dates skipping weekends and holidays, the cumulative
       cash schedule, and rejects shares that don't sum to 100%. Every phase needs a
       deliverable and an acceptance criterion in the document.
    5. **Write the document** in the output format. Keep it under ~1,200 words for deals
       under $50k; longer proposals get an appendix, not a longer body.
    6. **Audit before sending** with `proposal_builder__proposal_audit` on the full text.
       It checks required sections, the validity date, a single clear CTA, assumptions and
       exclusions, payment terms, readability and hedging language. Fix every "missing"
       item; explain any "weak" item you consciously leave.
    7. If the user's AI has Docs/Notion/PandaDoc, create the document; otherwise output it
       ready to paste. Never send it — the user reviews first.

    ## Frameworks
    - **Proposal spine:** Summary → Situation (their words) → Objectives (measurable) →
      Approach & deliverables → Timeline → Investment (3 options) → Why us (3 proof
      points) → Terms & assumptions → Next step (one action, one date).
    - **Pricing psychology:** three options; middle is the target; annual prepay discount
      10-20% (never more without a term extension); quote per-month for SaaS and total for
      services; show the discount as a line, not baked into the unit price.
    - **Payment schedules:** services 30/40/30 or 50/50 for < 6 weeks; retainers monthly
      in advance; SaaS annual upfront or quarterly with a 5-8% premium. Deposit before
      work starts, always.
    - **Validity:** 14-30 days. A proposal without an expiry has no reason to be answered.
    - **Scope protection:** an "Assumptions & exclusions" section is the cheapest
      insurance against scope creep; list what is NOT included explicitly.
    - Not legal advice: for liability caps, IP assignment and termination clauses, flag
      for a lawyer.

    ## Output format
    ```
    # Proposal: <outcome-focused title> — prepared for <buyer>, <date>
    Valid until <date> · Prepared by <user>

    ## Summary
    <3 sentences: their problem, our approach, the result and price of the recommended option.>

    ## Your situation
    <problem in their words, one quantified cost>

    ## Objectives
    1. <measurable>
    ## Approach & deliverables
    | Phase | What you get | Acceptance criterion |
    ## Timeline
    | Milestone | Date | Payment |
    ## Investment
    | | Good | Better ★ | Best |
    |---|---|---|---|
    | Scope | … | … | … |
    | Price | … | … | … |
    ## Why us
    - <proof 1> …
    ## Assumptions & exclusions
    ## Terms
    ## Next step
    <one action, by <date>>
    ```

    ## Anti-patterns
    - Opening with "About us". The first page is about them.
    - One price, no options — you are negotiating against "no" instead of against "which".
    - Arithmetic done by hand. A wrong subtotal ends the buyer's trust in every other number.
    - "Approximately 6-8 weeks" timelines. Dates, computed on business days.
    - No validity date, no next step, "let me know if you have questions".
    - Hedging language ("we hope to", "should be able to") — it reads as doubt.
    - Burying assumptions. Undocumented assumptions become unpaid work.
    """,
)


def _num(v, name: str, row: int) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ToolError(f"Line {row}: {name} must be a number, got {v!r}.") from None
    if f < 0:
        raise ToolError(f"Line {row}: {name} cannot be negative.")
    return f


@AGENT.tool
def pricing_table(
    line_items: list[dict],
    discount_pct: float = 0.0,
    tax_rate_pct: float = 0.0,
    term_months: int = 12,
    currency: str = "USD",
    seats: int = 0,
) -> dict:
    """Compute a proposal pricing table: line totals, subtotal, discount, tax, grand total, per-month and per-seat figures.

    Call once per pricing option. Line items: {"name": str, "qty": number, "unit_price": number,
    "period": "one_time" | "month" | "year", "discount_pct": number (optional line-item discount)}
    — monthly items are multiplied by term_months. Every amount is rounded to the cent once, and
    totals are sums of the rounded figures, so the table always adds up.

    Args:
        line_items: Up to 100 line items, each with name, qty, unit_price, period (one_time/month/year) and optional discount_pct (0-100, applied to that line before any overall discount).
        discount_pct: Percentage discount applied to the recurring subtotal after line discounts (0-100); one-time items are not discounted.
        tax_rate_pct: Sales tax / VAT percentage applied after discount (0-50).
        term_months: Contract length in months (1-60) used to annualise/monthlyise recurring items.
        currency: ISO currency code for display (default USD).
        seats: Number of seats/users for per-seat figures (0 = skip).
    """
    if not line_items:
        raise ToolError("line_items is empty.")
    if len(line_items) > 100:
        raise ToolError("Max 100 line items.")
    if not 0 <= discount_pct <= 100 or not 0 <= tax_rate_pct <= 50:
        raise ToolError("discount_pct 0-100 and tax_rate_pct 0-50.")
    if not 1 <= term_months <= 60:
        raise ToolError("term_months must be 1-60.")
    if seats < 0:
        raise ToolError("seats cannot be negative.")
    cur = currency.strip().upper()[:3] or "USD"
    lines, one_time, recurring = [], 0.0, 0.0
    for i, li in enumerate(line_items, 1):
        if not isinstance(li, dict):
            raise ToolError(f"Line {i} is not a dict.")
        name = str(li.get("name", "")).strip() or f"Item {i}"
        qty = _num(li.get("qty", 1), "qty", i)
        unit = _num(li.get("unit_price", 0), "unit_price", i)
        period = str(li.get("period", "one_time")).strip().lower().replace("-", "_")
        if period in ("once", "onetime", "one_off", "setup"):
            period = "one_time"
        if period in ("monthly", "mo"):
            period = "month"
        if period in ("annual", "yearly", "yr"):
            period = "year"
        if period not in ("one_time", "month", "year"):
            raise ToolError(f"Line {i}: period must be one_time, month or year.")
        line_disc = _num(li.get("discount_pct", 0), "discount_pct", i)
        if line_disc > 100:
            raise ToolError(f"Line {i}: discount_pct must be 0-100.")
        if period == "one_time":
            gross = qty * unit
        elif period == "month":
            gross = qty * unit * term_months
        else:
            gross = qty * unit * term_months / 12
        gross = c.money(gross)
        line_discount = c.money(gross * line_disc / 100)
        total = c.money(gross - line_discount)
        if period == "one_time":
            one_time += total
        else:
            recurring += total
        row = {"name": name, "qty": qty, "unit_price": c.money(unit), "period": period, "line_total_for_term": total}
        if line_disc:
            row.update({"line_gross": gross, "line_discount_pct": line_disc, "line_discount": line_discount})
        lines.append(row)
    one_time, recurring = c.money(one_time), c.money(recurring)
    # round each figure once, then derive totals from the rounded figures (no drift between rows and total)
    discount = c.money(recurring * discount_pct / 100)
    after_discount = c.money(recurring - discount + one_time)
    tax = c.money(after_discount * tax_rate_pct / 100)
    grand = c.money(after_discount + tax)
    monthly_recurring = (recurring - discount) / term_months
    out = {
        "currency": cur,
        "term_months": term_months,
        "lines": lines,
        "one_time_subtotal": c.money(one_time),
        "recurring_subtotal_for_term": c.money(recurring),
        "discount_pct": discount_pct,
        "discount_amount": c.money(discount),
        "subtotal_after_discount": c.money(after_discount),
        "tax_rate_pct": tax_rate_pct,
        "tax_amount": c.money(tax),
        "grand_total": c.money(grand),
        "recurring_per_month_after_discount": c.money(monthly_recurring),
        "annualised_recurring": c.money(monthly_recurring * 12),
        "total_contract_value_ex_tax": c.money(after_discount),
        "effective_discount_pct_on_total": round(100 * discount / (recurring + one_time), 2) if (recurring + one_time) else 0.0,
    }
    if seats:
        out["per_seat_per_month"] = c.money(monthly_recurring / seats)
        out["per_seat_per_year"] = c.money(monthly_recurring * 12 / seats)
    warnings = []
    if discount_pct > 20:
        warnings.append(f"{discount_pct}% discount — above the 10-20% norm; require a give (longer term, case study, upfront payment).")
    if one_time and recurring and one_time > recurring:
        warnings.append("One-time fees exceed the recurring total — buyers read this as a services deal; consider amortising onboarding.")
    out["warnings"] = warnings
    out["display_rows"] = [
        f"{l['name']}: {l['qty']:g} × {cur} {l['unit_price']:,.2f} /{l['period'].replace('_', '-')}"
        + (f" − {l['line_discount_pct']:g}%" if l.get("line_discount_pct") else "")
        + f" = {cur} {l['line_total_for_term']:,.2f}" for l in lines
    ] + [
        f"Discount ({discount_pct}% on recurring): -{cur} {discount:,.2f}" if discount else "",
        f"Tax ({tax_rate_pct}%): {cur} {tax:,.2f}" if tax else "",
        f"Total for {term_months} months: {cur} {grand:,.2f}",
    ]
    out["display_rows"] = [r for r in out["display_rows"] if r]
    out["verdict"] = f"{cur} {grand:,.2f} total for {term_months} months ({cur} {monthly_recurring:,.2f}/month recurring after {discount_pct}% discount" + (f", {cur} {one_time:,.2f} one-time" if one_time else "") + ")."
    return out


@AGENT.tool
def tier_comparison(tiers: list[dict], units_label: str = "seats") -> dict:
    """Compare Good/Better/Best tiers: price steps, per-unit price, anchoring ratios and spacing warnings.

    Call after pricing each option. Tiers: {"name": str, "price": number, "units": number (optional),
    "recommended": bool (optional)}. Prices must be on the same basis (all monthly or all total).

    Args:
        tiers: 2-5 tiers in ascending price order (the tool sorts them if not).
        units_label: What "units" means for per-unit maths (seats, hours, pages...).
    """
    if not tiers or not 2 <= len(tiers) <= 5:
        raise ToolError("Give 2-5 tiers.")
    rows = []
    for i, t in enumerate(tiers, 1):
        if not isinstance(t, dict):
            raise ToolError(f"Tier {i} is not a dict.")
        price = _num(t.get("price", None), "price", i)
        if price == 0:
            raise ToolError(f"Tier {i}: price must be > 0.")
        units = _num(t.get("units", 0), "units", i)
        rows.append({"name": str(t.get("name", f"Tier {i}")), "price": c.money(price), "units": units or None, "recommended": bool(t.get("recommended", False))})
    rows.sort(key=lambda r: r["price"])
    base = rows[0]["price"]
    for i, r in enumerate(rows):
        r["multiple_of_lowest"] = round(r["price"] / base, 2)
        r["step_up_from_previous"] = c.money(r["price"] - rows[i - 1]["price"]) if i else 0.0
        r["step_up_pct"] = round(100 * (r["price"] - rows[i - 1]["price"]) / rows[i - 1]["price"], 1) if i else 0.0
        r["per_unit"] = c.money(r["price"] / r["units"]) if r["units"] else None
    warnings, advice = [], []
    rec = [r for r in rows if r["recommended"]]
    if len(rec) > 1:
        warnings.append("More than one tier marked recommended — mark exactly one.")
    if len(rows) >= 3:
        mid = rows[len(rows) // 2]
        top, bottom = rows[-1], rows[0]
        if not rec:
            advice.append(f"Mark '{mid['name']}' as recommended — the middle option is where the anchor works.")
        elif rec[0] is not mid:
            advice.append(f"The recommended tier is '{rec[0]['name']}' but anchoring works best on the middle tier ('{mid['name']}').")
        ratio_top_mid = top["price"] / mid["price"]
        ratio_mid_bot = mid["price"] / bottom["price"]
        if ratio_top_mid < 1.3:
            warnings.append(f"Top tier is only {ratio_top_mid:.2f}× the middle — the anchor is too weak; make Best ≥ 1.5× Better or fold it into Better.")
        if ratio_top_mid > 3:
            warnings.append(f"Top tier is {ratio_top_mid:.1f}× the middle — reads as a joke option; buyers dismiss it and the anchor collapses.")
        if ratio_mid_bot < 1.2:
            warnings.append(f"Middle is only {ratio_mid_bot:.2f}× the bottom — nobody upgrades for that little; widen the scope gap or the price gap.")
        if ratio_mid_bot > 2.5:
            warnings.append(f"Middle is {ratio_mid_bot:.1f}× the bottom — buyers will take the cheap one; add a stepping-stone or raise the base.")
    per_units = [r for r in rows if r["per_unit"]]
    if len(per_units) >= 2:
        for a, b in zip(per_units, per_units[1:]):
            if b["per_unit"] > a["per_unit"]:
                warnings.append(f"Per-{units_label} price rises from '{a['name']}' to '{b['name']}' ({a['per_unit']} → {b['per_unit']}) — bigger tiers must be cheaper per {units_label}.")
    return {
        "tiers": rows,
        "recommended": (rec[0]["name"] if rec else (rows[len(rows) // 2]["name"] if len(rows) >= 3 else rows[-1]["name"])),
        "price_range": {"low": rows[0]["price"], "high": rows[-1]["price"], "spread_x": round(rows[-1]["price"] / base, 2)},
        "warnings": warnings,
        "advice": advice,
        "verdict": (f"{len(rows)} tiers, {rows[0]['price']:,.0f} → {rows[-1]['price']:,.0f} ({rows[-1]['multiple_of_lowest']}× spread). " + (warnings[0] if warnings else "Spacing supports the middle anchor.")),
    }


@AGENT.tool
def milestone_timeline(start_date: str, milestones: list[dict], total_price: float = 0.0, holidays: list[str] | None = None, deposit_pct: float = 0.0) -> dict:
    """Turn phase durations into dated milestones on business days with a payment schedule that must sum to 100%.

    Call for every proposal with phases or deliverables. Milestones: {"name": str, "business_days": int,
    "payment_pct": number (optional), "deliverable": str (optional)}.

    Args:
        start_date: Project start, YYYY-MM-DD (moved to the next business day if it isn't one).
        milestones: 1-40 phases in order, each with business_days and optional payment_pct / deliverable.
        total_price: Total project price to compute payment amounts (0 = percentages only).
        holidays: Dates (YYYY-MM-DD) to skip.
        deposit_pct: Percentage invoiced at signature, before the first phase (counts toward the 100%).
    """
    start = c.to_date(start_date)
    if not milestones or len(milestones) > 40:
        raise ToolError("Give 1-40 milestones.")
    if total_price < 0 or not 0 <= deposit_pct <= 100:
        raise ToolError("total_price ≥ 0 and deposit_pct 0-100.")
    hols = c.parse_holidays(holidays or [])
    while start.weekday() >= 5 or start in hols:
        start = dates.add_business_days(start, 1, hols)
    rows, cursor, cum_pct = [], start, deposit_pct
    payments = []
    if deposit_pct:
        payments.append({"milestone": "Signature (deposit)", "date": start.isoformat(), "payment_pct": deposit_pct, "amount": c.money(total_price * deposit_pct / 100) if total_price else None, "cumulative_pct": deposit_pct})
    for i, m in enumerate(milestones, 1):
        if not isinstance(m, dict):
            raise ToolError(f"Milestone {i} is not a dict.")
        try:
            days = int(m.get("business_days", 0))
        except (TypeError, ValueError):
            raise ToolError(f"Milestone {i}: business_days must be an integer.") from None
        if days < 0 or days > 500:
            raise ToolError(f"Milestone {i}: business_days must be 0-500.")
        pay = _num(m.get("payment_pct", 0), "payment_pct", i)
        phase_start = cursor
        end = dates.add_business_days(cursor, days, hols) if days else cursor
        # the phase occupies `days` business days starting on phase_start; end is the last working day
        if days:
            end = dates.add_business_days(phase_start, days - 1, hols)
        cum_pct += pay
        row = {
            "n": i,
            "name": str(m.get("name", f"Phase {i}")),
            "deliverable": str(m.get("deliverable", "")).strip() or None,
            "start": phase_start.isoformat(),
            "end": end.isoformat(),
            "end_weekday": end.strftime("%a"),
            "business_days": days,
            "calendar_days": (end - phase_start).days + 1 if days else 0,
            "payment_pct": pay,
            "amount": c.money(total_price * pay / 100) if total_price else None,
            "cumulative_pct": round(cum_pct, 2),
        }
        rows.append(row)
        if pay:
            payments.append({"milestone": row["name"], "date": end.isoformat(), "payment_pct": pay, "amount": row["amount"], "cumulative_pct": round(cum_pct, 2)})
        cursor = dates.add_business_days(end, 1, hols) if days else cursor
    total_bd = sum(r["business_days"] for r in rows)
    finish = rows[-1]["end"]
    issues = []
    if abs(cum_pct - 100) > 0.01:
        issues.append(f"payment percentages sum to {round(cum_pct, 2)}%, not 100% — fix before sending")
    if not deposit_pct and rows and rows[0]["payment_pct"] == 0:
        issues.append("no deposit and no payment at the first milestone — you'd be financing the client")
    if payments and payments[-1]["payment_pct"] > 40:
        issues.append(f"{payments[-1]['payment_pct']}% due at the final milestone — cap the final payment at ~30-40% to limit acceptance-stall risk")
    return {
        "start": start.isoformat(),
        "finish": finish,
        "total_business_days": total_bd,
        "total_calendar_days": (dates.parse_date(finish) - start).days + 1,
        "total_weeks": round(((dates.parse_date(finish) - start).days + 1) / 7, 1),
        "milestones": rows,
        "payment_schedule": payments,
        "payment_total_pct": round(cum_pct, 2),
        "issues": issues,
        "verdict": f"{len(rows)} phases, {total_bd} business days, {start.isoformat()} → {finish}." + (" ISSUES: " + "; ".join(issues) if issues else " Payments sum to 100%."),
    }


REQUIRED_SECTIONS = {
    "summary": r"(executive )?summary|overview|at a glance",
    "situation": r"situation|background|your challenge|the problem|current state|context",
    "objectives": r"objectives?|goals?|success criteria|outcomes?",
    "approach": r"approach|deliverables?|scope|solution|what you get|statement of work|methodology",
    "timeline": r"timeline|schedule|milestones?|phases?",
    "investment": r"investment|pricing|price|fees?|cost|options?",
    "why_us": r"why (us|we|choose)|about us|our (team|experience)|case stud|clients|proof|results",
    "assumptions": r"assumptions?|exclusions?|out of scope|not included",
    "terms": r"terms|payment terms|conditions|agreement",
    "next_step": r"next steps?|how to proceed|to get started|acceptance|sign",
}
HEDGES = ("we hope to", "should be able to", "we'll try", "we will try", "hopefully", "we think we can", "may be able to", "attempt to", "aim to", "possibly")
VALIDITY_RE = re.compile(r"\b(valid (?:until|through|for)|expires?|expiry|expiration|good (?:until|through))\b", re.I)
CTA_RE = re.compile(r"\b(sign|countersign|reply|confirm|approve|book|schedule|call|choose|select|let us know|accept|e-?sign|docusign)\b", re.I)


@AGENT.tool
def proposal_audit(proposal_text: str, deal_value: float = 0.0) -> dict:
    """Audit a proposal before sending: required sections, validity date, single CTA, hedging, length and readability.

    Call on the full proposal text as the last step. Returns missing/weak items with fixes
    and a 0-100 send-readiness score.

    Args:
        proposal_text: The complete proposal (markdown or plain text).
        deal_value: Deal value, used to judge appropriate length (0 = unknown).
    """
    if not proposal_text or not proposal_text.strip():
        raise ToolError("proposal_text is empty.")
    if len(proposal_text) > 200_000:
        raise ToolError("Proposal over 200k chars.")
    headings = [h.strip() for h in re.findall(r"^\s{0,3}(?:#{1,4}\s+|\d+[.)]\s+|[A-Z][A-Za-z &/]{2,40}:?\s*$)(.*)$", proposal_text, flags=re.M)]
    heading_blob = " | ".join(headings).lower() if headings else ""
    low = proposal_text.lower()
    found, missing = [], []
    for key, rx in REQUIRED_SECTIONS.items():
        r = re.compile(rx, re.I)
        if r.search(heading_blob) or r.search(low):
            found.append(key)
        else:
            missing.append(key)
    n_words = len(text.words(proposal_text))
    read = text.readability(proposal_text)
    hedges = [h for h in HEDGES if h in low]
    has_validity = bool(VALIDITY_RE.search(proposal_text))
    has_date = bool(re.search(r"\b(20\d{2}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/20\d{2}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? \d{1,2},? 20\d{2})\b", low))
    tail = proposal_text[-1500:]
    tail_ctas = set(m.lower() for m in CTA_RE.findall(tail))
    n_options = len(re.findall(r"\b(option [abc1-3]|good|better|best|starter|standard|premium|essential|professional|enterprise|basic|plus|pro)\b", low))
    money_mentions = re.findall(r"[$£€]\s?\d[\d,]*(?:\.\d+)?", proposal_text)
    passive = len(text.passive_sentences(proposal_text))
    score, fixes = 100, []
    critical = {"investment", "next_step", "approach"}
    for m in missing:
        score -= 12 if m in critical else 6
        fixes.append(f"missing section: {m.replace('_', ' ')}")
    if not has_validity:
        score -= 10
        fixes.append("no validity/expiry date — add 'Valid until <date>' (14-30 days out)")
    if not has_date:
        score -= 5
        fixes.append("no dates anywhere — timeline needs calendar dates")
    if not tail_ctas:
        score -= 10
        fixes.append("no call to action near the end — one action, one date")
    elif len(tail_ctas) > 3:
        score -= 5
        fixes.append(f"{len(tail_ctas)} different asks at the end ({', '.join(sorted(tail_ctas))}) — keep one")
    if hedges:
        score -= min(15, 5 * len(hedges))
        fixes.append("hedging language: " + ", ".join(f"'{h}'" for h in hedges))
    if not money_mentions:
        score -= 10
        fixes.append("no prices found — the investment section must show numbers")
    if n_options < 2 and "investment" in found:
        fixes.append("looks like a single-price proposal — consider three options (Good/Better/Best)")
        score -= 4
    fre = read.get("flesch_reading_ease") or 0
    if fre < 40:
        score -= 8
        fixes.append(f"Flesch Reading Ease {fre} — too dense; shorter sentences, fewer nouns-as-verbs")
    if passive > max(3, n_words // 100):
        score -= 5
        fixes.append(f"{passive} passive sentences — say who does what")
    if deal_value and deal_value < 50_000 and n_words > 1800:
        score -= 6
        fixes.append(f"{n_words} words for a ${deal_value:,.0f} deal — cut to ≤ 1,200 and move detail to an appendix")
    elif n_words < 250:
        score -= 10
        fixes.append(f"only {n_words} words — too thin to justify a price")
    score = max(0, min(100, score))
    return {
        "score": score,
        "ready_to_send": score >= 80 and not (critical & set(missing)),
        "sections_found": found,
        "sections_missing": missing,
        "has_validity_date": has_validity,
        "closing_ctas": sorted(tail_ctas),
        "hedges": hedges,
        "words": n_words,
        "flesch_reading_ease": fre,
        "passive_sentences": passive,
        "price_mentions": len(money_mentions),
        "fixes": fixes,
        "verdict": f"{score}/100 — " + (f"{len(missing)} section(s) missing; " if missing else "all sections present; ") + (fixes[0] if fixes else "ready to send."),
    }
