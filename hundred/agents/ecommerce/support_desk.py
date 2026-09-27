"""Support Desk — triage, macros, tone and SLA math for an e-commerce help desk that customers actually rate 5 stars."""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timedelta

from ...core import Agent, ToolError
from ...lib import text
from ._common import mean, median, pct, percentile

AGENT = Agent(
    slug="support-desk",
    name="Support Desk",
    category="ecommerce",
    tagline="Triage tickets, build macros that sound human, check tone, and hit SLAs with business-hour math done right.",
    description=(
        "Runs an e-commerce support desk like a top CX lead: classifies incoming tickets by issue and "
        "priority with the right SLA, builds and lints reply macros (placeholders filled, structure "
        "complete, no policy-speak), scores tone for empathy and ownership before anything is sent, "
        "computes SLA deadlines and breaches on a business-hours clock with holidays, and turns "
        "raw ticket stats into contact rate, first-response medians, CSAT and staffing needs."
    ),
    triggers=[
        "reply to this customer complaint / support ticket",
        "write a support macro / canned response",
        "triage these support tickets",
        "when is this ticket's SLA due / did we breach SLA",
        "check the tone of this customer service reply",
        "how many support agents do we need",
        "analyze our support metrics / CSAT / first response time",
    ],
    examples=[
        "Customer says their order arrived broken and it's the second time — draft the reply and tell me what to offer.",
        "Here are 40 tickets from this morning. Triage them by priority and tell me which need a human first.",
        "Ticket came in Friday 16:40, our SLA is 8 business hours (Mon-Fri 9-18). When is it due and are we late?",
    ],
    connectors=["Gorgias", "Zendesk", "Shopify", "Gmail", "Intercom", "Slack"],
    playbook="""
    ## Standard
    You are the head of CX at a DTC brand where support is a profit centre: the one metric
    that matters is **CSAT on resolved tickets** with **first-contact resolution** as the
    lever. An excellent reply resolves the issue in one message, states exactly what happens
    next and when, sounds like a person, and never makes the customer do work the company
    could do. Every reply is judged by: would this customer reorder?

    ## Intake
    You need the ticket text(s), the order context if available (order value, date,
    shipping status, customer's history), your policies (returns window, refund vs
    replacement rules, what agents may offer without approval) and your SLA/business hours.
    Ask at most 3 questions only if you cannot proceed; otherwise assume sensible DTC
    defaults (30-day returns, replace-first for damage, 8-business-hour first response)
    and state them.

    ## Procedure
    1. **Triage first.** For any batch (or a single ticket you are unsure about) call
       `support_desk__triage_tickets`. It assigns issue category, priority P1-P4, the SLA
       hours for that priority, sentiment and escalation flags (chargeback, legal, safety,
       press, repeat contact). Handle P1s before drafting anything else. Skim every P3/P4
       yourself for injury language the rules missed — a missed safety ticket is the one
       mistake that cannot be fixed with a good reply.
    2. **Compute the clock.** Call `support_desk__sla_deadline` with the ticket's created
       time, the SLA and your business hours/holidays. It returns the due time, whether it
       is breached and the remaining time. Never estimate business hours by hand — Friday
       afternoon + weekend + holiday is exactly where humans get it wrong.
    3. **Draft the reply** using the CARE structure (Frameworks): acknowledge the specific
       problem in the customer's words, take ownership, state the resolution and the next
       step with a date, close with a personal line. Pick the resolution with the policy
       ladder: replace > partial refund/credit > full refund; offer up-front what a fair
       person would, do not make them ask twice.
    4. **Lint before sending.** Run `support_desk__lint_macro` on the draft (with the
       variables filled) — it catches unfilled placeholders, missing structure elements,
       policy-speak and length problems — and `support_desk__tone_check` for the empathy/
       ownership score. Fix anything below 75 before replying. For macros meant for reuse,
       keep placeholders and make sure each has a fallback.
    5. **Act if connected.** With Gorgias/Zendesk/Intercom: set the priority and tags from
       triage, draft (never send) the reply, apply the macro. With Shopify: check order
       status/fulfilment before promising anything. Without connectors, output the reply
       ready to paste plus the internal note (what to refund/reship).
    6. **Report the desk** when asked with `support_desk__support_metrics`: contact rate per
       100 orders, median/p90 first response and resolution, CSAT, reopen rate and the
       agents needed at your hours and occupancy. Tie every recommendation to one of them.
    7. **Self-check**: the reply answers the actual question, contains a date or timeframe,
       has one clear next step, no "unfortunately", no policy quoted as an excuse, ≤ 150
       words unless the issue is technical.

    ## Frameworks
    - **CARE reply:** Confirm (what happened, in their words) → Apologise once, specifically
      → Resolve (what you are doing, already done where possible) → Expect (what happens
      next, by when, and how to reach you).
    - **Priority & SLA (business hours unless stated):** P1 safety/legal/chargeback/press
      or VIP outage: 1h first response, 4h resolution — on the calendar clock
      (`calendar_hours: true`): an injury report on Friday evening cannot wait for Monday.
      Within P1: injury/safety first, then legal/press, then chargebacks. P2 damaged/wrong/missing item,
      repeat contact, order > $200: 4h / 24h. P3 WISMO, returns, sizing: 8h / 48h.
      P4 feedback, product questions, pre-sales: 24h / 5 days.
    - **Resolution ladder for damage/defect:** reship immediately (no photo demand under
      $50), ask for a photo above that only if fraud rate warrants, refund without return
      when return shipping > 40% of item value.
    - **Contact-rate benchmark:** 5-10 tickets per 100 orders is healthy for DTC; > 15 means
      a product, shipping or expectation problem, not a support problem. WISMO > 30% of
      tickets → fix tracking emails and delivery estimates.
    - **Tone rules:** first person singular ("I've refunded"), present/past tense for
      things already done, one apology, no "unfortunately", no "as per our policy", no
      "sorry for any inconvenience", no exclamation marks in a complaint reply.
    - **Staffing:** agents = (weekly tickets × handle time) ÷ (agent hours × occupancy
      0.75-0.85) — plus 15-20% shrinkage for breaks, training and leave.
    - Scope note: chargebacks, injury claims and legal threats go to a human owner the same
      day; do not commit to liability language in writing.

    ## Output format
    ```
    # Ticket <id> — <category> · <priority> · due <time> (<remaining / BREACHED>)
    ## Reply (ready to send)
    Hi <name>,
    <CARE reply, ≤ 150 words, one next step with a date>
    <sign-off, first name>
    ## Internal note
    Action: <refund $X / reship SKU / tag> · Offer ladder used: <…> · Escalate: <yes/no — why>
    ## Macro (if reusable)
    <template with {{placeholders}} and fallbacks>
    ```
    For a batch: a triage table (id, category, priority, due, flags) sorted by priority,
    then replies for the P1/P2s.

    ## Anti-patterns
    - Opening with "Thank you for reaching out" and an apology "for any inconvenience".
    - Asking the customer for the order number when it is in the ticket.
    - Quoting policy as the reason for the answer instead of solving the problem.
    - Promising "as soon as possible". Give a date.
    - Two replies where one would do: the "we've received your request" auto-reply is not a
      first response — the SLA clock counts until a human answers.
    - Treating a 1-star review threat as pressure rather than a P2 to resolve well.
    """,
)

PRIORITY_SLA = {"P1": (1, 4), "P2": (4, 24), "P3": (8, 48), "P4": (24, 120)}  # (first response h, resolution h) business hours
WEEKDAY_IDX = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _parse_dt(value: str, name: str) -> datetime:
    try:
        return datetime.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        raise ToolError(f"{name} must be ISO like 2026-10-02T16:40, got {value!r}") from None


def _business_hours_between(start: datetime, end: datetime, bh_start: float, bh_end: float, days: set[int], holidays: set) -> float:
    """Business hours elapsed between two datetimes (fractional)."""
    if end <= start:
        return 0.0
    total, cur = 0.0, start
    while cur < end:
        day_open = cur.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=bh_start)
        day_close = cur.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=bh_end)
        if cur.weekday() in days and cur.date() not in holidays:
            seg_start = max(cur, day_open)
            seg_end = min(end, day_close)
            if seg_end > seg_start:
                total += (seg_end - seg_start).total_seconds() / 3600
        cur = cur.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return total


def _add_business_hours(start: datetime, hours: float, bh_start: float, bh_end: float, days: set[int], holidays: set) -> datetime:
    remaining, cur = hours, start
    for _ in range(3660):  # ~10 years of days max
        day0 = cur.replace(hour=0, minute=0, second=0, microsecond=0)
        day_open, day_close = day0 + timedelta(hours=bh_start), day0 + timedelta(hours=bh_end)
        if cur.weekday() in days and cur.date() not in holidays and cur < day_close:
            seg_start = max(cur, day_open)
            avail = (day_close - seg_start).total_seconds() / 3600
            if avail >= remaining:
                return seg_start + timedelta(hours=remaining)
            remaining -= avail
        cur = day0 + timedelta(days=1)
    raise ToolError("SLA horizon too long to compute.")


@AGENT.tool
def sla_deadline(
    created_at: str,
    sla_hours: float = 0.0,
    priority: str = "P3",
    business_hours_start: float = 9.0,
    business_hours_end: float = 18.0,
    business_days: list[str] | None = None,
    holidays: list[str] | None = None,
    responded_at: str = "",
    now: str = "",
    calendar_hours: bool = False,
) -> dict:
    """Compute when a ticket's SLA is due on a business-hours clock (weekends/holidays skipped), how much is left, and whether it was breached.

    Args:
        created_at: Ticket creation time, ISO local time (2026-10-02T16:40).
        sla_hours: SLA in hours; 0 to use the default first-response SLA for the priority.
        priority: P1-P4 (used for the default SLA and reported back).
        business_hours_start: Support opens at this hour (9 = 09:00; 8.5 = 08:30).
        business_hours_end: Support closes at this hour (18 = 18:00).
        business_days: Days support runs, e.g. ["mon","tue","wed","thu","fri"] (default). Use all seven for 24/7 teams.
        holidays: Dates (YYYY-MM-DD) support is closed.
        responded_at: When the first human reply went out (ISO), to check breach; empty if not yet.
        now: Current time (ISO) for "time remaining"; defaults to the real now.
        calendar_hours: True to run the clock 24/7 regardless of business hours.
    """
    pr = priority.upper().strip()
    if pr not in PRIORITY_SLA:
        raise ToolError("priority must be P1, P2, P3 or P4.")
    hours = sla_hours if sla_hours > 0 else PRIORITY_SLA[pr][0]
    if hours > 24 * 90:
        raise ToolError("sla_hours over 90 days is not an SLA.")
    created = _parse_dt(created_at, "created_at")
    if not 0 <= business_hours_start < business_hours_end <= 24:
        raise ToolError("business hours must satisfy 0 <= start < end <= 24.")
    day_names = [d.lower()[:3] for d in (business_days or ["mon", "tue", "wed", "thu", "fri"])]
    if any(d not in WEEKDAY_IDX for d in day_names):
        raise ToolError("business_days must be names like mon, tue, wed, thu, fri, sat, sun.")
    days = {WEEKDAY_IDX[d] for d in day_names}
    hol = set()
    for h in holidays or []:
        hol.add(_parse_dt(str(h), "holiday").date())
    if calendar_hours:
        bh_s, bh_e, days = 0.0, 24.0, set(range(7))
        hol = set()
    else:
        bh_s, bh_e = business_hours_start, business_hours_end
    due = _add_business_hours(created, hours, bh_s, bh_e, days, hol)
    ref = _parse_dt(now, "now") if now else datetime.now()
    responded = _parse_dt(responded_at, "responded_at") if responded_at else None
    out = {
        "priority": pr,
        "sla_hours": hours,
        "clock": "calendar" if calendar_hours else f"business {bh_s:g}-{bh_e:g}, days {sorted(days)}",
        "created_at": created.strftime("%Y-%m-%d %H:%M (%a)"),
        "due_at": due.strftime("%Y-%m-%d %H:%M (%a)"),
        "calendar_hours_until_due": round((due - created).total_seconds() / 3600, 1),
    }
    if responded:
        used = _business_hours_between(created, responded, bh_s, bh_e, days, hol)
        out.update(
            {
                "responded_at": responded.strftime("%Y-%m-%d %H:%M (%a)"),
                "business_hours_to_respond": round(used, 2),
                "breached": responded > due,
                "over_by_hours": round(max(0.0, used - hours), 2),
                "verdict": f"{'BREACHED' if responded > due else 'Met'}: responded after {used:.1f} business hours vs {hours:g}h SLA (due {due.strftime('%a %H:%M')}).",
            }
        )
    else:
        elapsed = _business_hours_between(created, ref, bh_s, bh_e, days, hol)
        remaining = hours - elapsed
        out.update(
            {
                "as_of": ref.strftime("%Y-%m-%d %H:%M (%a)"),
                "business_hours_elapsed": round(elapsed, 2),
                "business_hours_remaining": round(remaining, 2),
                "breached": ref > due,
                "status": "BREACHED" if ref > due else ("at risk (< 25% left)" if remaining < 0.25 * hours else "on track"),
                "verdict": f"Due {due.strftime('%a %Y-%m-%d %H:%M')}; {abs(remaining):.1f} {'calendar' if calendar_hours else 'business'} hours {'overdue' if remaining < 0 else 'remaining'}.",
            }
        )
    return out


# Injury language: matched only when not negated ("it wouldn't hurt to…", "no injuries") — see _safety_hit.
SAFETY_RE = re.compile(
    r"\b(injur\w*|hurt|hurts|burn(ed|t|s)?|caught fire|on fire|fire hazard|smok(e|ed|ing)|explod\w*|allerg\w*|rash|hives|hospital\w*|"
    r"emergency room|\ber\b|urgent care|stitch(es)?|bleed\w*|blood|chok\w*|toxic|poison\w*|recall\w*|sharp edges?|"
    r"cut (my|his|her|their|our|me|him|them)\b|cut (a |the )?(finger|hand|lip|mouth|thumb|face)|electric shock|shocked (me|him|her)|unsafe|dangerous)",
    re.I,
)
SAFETY_NEGATION = re.compile(r"\b(wouldn'?t|would not|won'?t|will not|doesn'?t|does not|didn'?t|did not|never|no|not|without)\s+(\w+\s+){0,1}$", re.I)
SAFETY_QUESTION_RE = re.compile(r"\b(is it safe|safe to (drink|use|eat)|is this (safe|normal)|bpa|lead (paint|content))\b", re.I)


def _safety_hit(low: str) -> str | None:
    for m in SAFETY_RE.finditer(low):
        if SAFETY_NEGATION.search(low[max(0, m.start() - 25) : m.start()]):
            continue
        return m.group(0)
    return None


CATEGORY_RULES: list[tuple[str, str, str]] = [  # (category, regex, suggested macro) — safety is detected separately by _safety_hit
    ("chargeback_fraud", r"\b(chargeback|dispute(d)? (the|my|this|a) (charge|payment)|opened a dispute|unauthori[sz]ed|fraud|scam|don'?t recogni[sz]e (this|the) charge)\b", "escalate_finance"),
    ("legal_press", r"\b(lawyer|attorney|legal action|sue|suing|lawsuit|bbb|better business|journalist|reporter|press (inquiry|enquiry|request)|the press|media inquiry|consumer protection)\b", "escalate_lead"),
    ("cancel_change", r"\b(cancel\w*|change (my|the) (order|address|size)|update (my|the) address|wrong address|change of address|just moved)\b", "cancel_or_change"),
    ("damaged_defective", r"\b(broken|damaged|defective|cracked|leak(s|ing|ed)?|doesn'?t work|not working|stopped working|faulty|torn|dented|snapped|stuck|won'?t (open|close|seal))\b", "damage_reship"),
    ("wrong_or_missing_item", r"\b(wrong (item|size|colou?r|product|order)|missing (item|part|piece|lid)|received (the )?wrong|not what i ordered|incomplete|came without|arrived without|(was|is) missing|not in the box|supposed to be in the box)\b", "wrong_item_fix"),
    ("return_refund", r"(\brefund\b.{0,40}\b(hasn'?t|has not|not yet|still|never)\b|\b(where is|waiting (on|for)) my refund\b)", "refund_status"),
    ("wismo", r"\b(where is my|where'?s my|tracking|hasn'?t (arrived|shipped)|not (arrived|received|delivered)|still waiting|delivery (date|estimate)|when will (it|my order) (arrive|ship)|late)\b", "wismo_update"),
    ("return_refund", r"\b(refund|return|money back|send it back|exchange)\b", "return_process"),
    ("payment_account", r"\b(charged twice|double charged|payment (failed|declined)|card|login|password|account|subscription|invoice|receipt)\b", "account_help"),
    ("discount_promo", r"\b(discount|coupon|promo|code (didn'?t|doesn'?t|isn'?t) work|price match|sale price)\b", "promo_help"),
    ("wholesale_b2b", r"\b(bulk|wholesale|corporate|with (our|my) logo|custom logo|reseller|\d{3,} (units|bottles|pieces))\b", "sales_handoff"),
    ("product_question", r"\b(does it|is it|will it|compatible|how (do|does|to)|what size|which size|fit|material|ingredients|instructions|dimensions)\b", "presales_answer"),
    ("feedback", r"\b(love|great|thank(s| you)|disappointed|terrible|worst|never again|feedback|suggestion)\b", "feedback_thanks"),
]
P1_RE = re.compile(r"\b(chargeback|unauthori[sz]ed|fraud|lawyer|attorney|legal action|lawsuit|sue you|suing|journalist|reporter|the press|press (inquiry|enquiry)|bbb|consumer protection)\b", re.I)
P1_ORDER = {"safety": 0, "legal_press": 1, "chargeback_fraud": 2}
REPEAT_RE = re.compile(r"\b(second|third|3rd|2nd|fourth|again|still (no|waiting|haven'?t)|no (one|body) (has )?(replied|responded|answered)|(twice|three times|several times)|last time|previous(ly)? (email|message|ticket))\b", re.I)
NEG_RE = re.compile(r"\b(angry|furious|unacceptable|ridiculous|disgusted|disappointed|terrible|worst|awful|horrible|never again|pathetic|useless|scam|joke)\b", re.I)
POS_RE = re.compile(r"\b(love|great|amazing|thank(s| you)|awesome|perfect|happy|wonderful|appreciate)\b", re.I)


@AGENT.tool
def triage_tickets(
    tickets: list[dict],
    vip_order_value: float = 200.0,
    now: str = "",
    business_hours_start: float = 9.0,
    business_hours_end: float = 18.0,
    business_days: list[str] | None = None,
) -> dict:
    """Classify tickets by issue category and priority (P1-P4) with SLA hours, sentiment, repeat-contact and escalation flags; returns a sorted queue.

    Args:
        tickets: List of {"id": str, "subject": str, "body": str, "order_value": float (optional), "created_at": ISO (optional), "customer_orders": int lifetime orders (optional)}.
        vip_order_value: Order value at or above which a ticket is bumped one priority level.
        now: Current time (ISO) to compute waiting hours from created_at; defaults to real now.
        business_hours_start: Support opens (hour); waiting time vs SLA is measured on the business clock like sla_deadline.
        business_hours_end: Support closes (hour).
        business_days: Days support runs (default mon-fri); all seven for a 24/7 desk.
    """
    if not tickets:
        raise ToolError("tickets is empty.")
    if len(tickets) > 500:
        raise ToolError("Max 500 tickets per call.")
    ref = _parse_dt(now, "now") if now else datetime.now()
    day_names = [d.lower()[:3] for d in (business_days or ["mon", "tue", "wed", "thu", "fri"])]
    if any(d not in WEEKDAY_IDX for d in day_names):
        raise ToolError("business_days must be names like mon, tue, wed, thu, fri, sat, sun.")
    bdays = {WEEKDAY_IDX[d] for d in day_names}
    if not 0 <= business_hours_start < business_hours_end <= 24:
        raise ToolError("business hours must satisfy 0 <= start < end <= 24.")
    rows, cats = [], Counter()
    for t in tickets:
        tid = str(t.get("id", len(rows) + 1))
        body = f"{t.get('subject', '')}\n{t.get('body', '')}"
        if len(body) > 20000:
            raise ToolError(f"ticket {tid}: text too long (20k chars max).")
        low = body.lower()
        category, macro = "other", "manual_reply"
        safety_term = _safety_hit(low)
        if safety_term:
            category, macro = "safety", "escalate_safety"
        else:
            for cat, rx, m in CATEGORY_RULES:
                if re.search(rx, low):
                    category, macro = cat, m
                    break
        flags = []
        if safety_term:
            flags.append(f"escalate: possible injury/safety (“{safety_term}”) — human owner today, preserve evidence, no liability language")
        elif P1_RE.search(low):
            flags.append("escalate: legal/finance/press keyword")
        safety_question = bool(SAFETY_QUESTION_RE.search(low)) and not safety_term
        if safety_question:
            flags.append("safety question — answer with facts (materials, certifications) the same day")
        if category == "wholesale_b2b":
            flags.append("sales lead — route to wholesale owner")
        repeat = bool(REPEAT_RE.search(low))
        if repeat:
            flags.append("repeat contact")
        neg, pos = len(NEG_RE.findall(low)), len(POS_RE.findall(low))
        sentiment = "negative" if neg > pos else ("positive" if pos > neg else "neutral")
        if low.count("!") >= 3 or sum(1 for w in text.words(body) if len(w) > 3 and w.isupper()) >= 3:
            flags.append("heated tone")
        try:
            value = float(t.get("order_value") or 0)
        except (TypeError, ValueError):
            raise ToolError(f"ticket {tid}: order_value must be numeric.") from None
        if category in ("safety", "chargeback_fraud", "legal_press"):
            pr = 1
        elif category in ("damaged_defective", "wrong_or_missing_item", "cancel_change") or safety_question:
            pr = 2
        elif category in ("wismo", "return_refund", "payment_account"):
            pr = 3
        else:
            pr = 4
        # bumps never create a P1 — that is reserved for safety / legal / finance
        if repeat or sentiment == "negative":
            pr = max(2, pr - 1) if pr > 1 else pr
        if value >= vip_order_value or int(t.get("customer_orders") or 0) >= 5:
            pr = max(2, pr - 1) if pr > 1 else pr
            flags.append("VIP / high value")
        if category == "cancel_change":
            flags.append("time-critical: act before fulfilment")
        waiting_h = waiting_bh = None
        if t.get("created_at"):
            created = _parse_dt(str(t["created_at"]), f"ticket {tid} created_at")
            waiting_h = round((ref - created).total_seconds() / 3600, 1)
            # P1 runs on the calendar clock (safety/legal cannot wait for Monday); the rest on business hours
            if pr == 1:
                waiting_bh = waiting_h
            else:
                waiting_bh = round(_business_hours_between(created, ref, business_hours_start, business_hours_end, bdays, set()), 1)
            if waiting_bh > PRIORITY_SLA[f"P{pr}"][0]:
                flags.append(f"waiting {waiting_bh:g} {'calendar' if pr == 1 else 'business'} h > P{pr} first-response SLA ({PRIORITY_SLA[f'P{pr}'][0]}h)")
        cats[category] += 1
        rows.append(
            {
                "id": tid,
                "category": category,
                "priority": f"P{pr}",
                "sla_first_response_h": PRIORITY_SLA[f"P{pr}"][0],
                "sla_resolution_h": PRIORITY_SLA[f"P{pr}"][1],
                "sentiment": sentiment,
                "flags": flags,
                "suggested_macro": macro,
                "waiting_hours": waiting_h,
                "waiting_sla_hours": waiting_bh,
                "needs_human": pr == 1 or any(f.startswith("escalate:") for f in flags),
            }
        )
    rows.sort(key=lambda r: (r["priority"], P1_ORDER.get(r["category"], 9), -(r["waiting_sla_hours"] or 0)))
    n = len(rows)
    wismo_share = cats.get("wismo", 0) / n
    insights = []
    if wismo_share > 0.30:
        insights.append(f"WISMO is {100 * wismo_share:.0f}% of tickets — fix tracking emails / delivery estimates before hiring.")
    if (cats.get("damaged_defective", 0) + cats.get("wrong_or_missing_item", 0)) / n > 0.15:
        insights.append("Damage/wrong-item over 15% — packaging or pick accuracy problem, escalate to ops.")
    return {
        "queue": rows,
        "category_counts": dict(cats.most_common()),
        "priority_counts": dict(Counter(r["priority"] for r in rows)),
        "needs_human_now": [r["id"] for r in rows if r["needs_human"]],
        "insights": insights,
        "summary": f"{n} tickets: {dict(Counter(r['priority'] for r in rows))}; {len([r for r in rows if r['needs_human']])} need a human now. Top category: {cats.most_common(1)[0][0]}.",
    }


PLACEHOLDER_RE = re.compile(r"\{\{\s*([\w.]+)\s*(?:\|\s*([^}]*?)\s*)?\}\}|\{(\w+)\}|\[(?:[A-Z][A-Z _]{1,30})\]")
POLICY_SPEAK = [
    "unfortunately", "as per our policy", "per our policy", "our policy states", "policy does not", "as i mentioned", "as stated",
    "as previously", "please be advised", "kindly", "do the needful", "sorry for any inconvenience", "sorry you feel", "we regret",
    "we are unable", "there is nothing we can do", "nothing we can do", "you should have", "you failed to", "it is not our",
    "not our fault", "calm down", "as soon as possible", "asap", "at your earliest convenience", "valued customer", "reaching out",
]
EMPATHY = [
    "i understand", "i can see", "that's frustrating", "that is frustrating", "i'm sorry that", "i am sorry that", "i'm sorry about",
    "i'd be frustrated", "thank you for your patience", "you're right", "you are right", "i get it", "completely understand", "that shouldn't have happened",
    "sorry this happened", "i'm so sorry", "i am so sorry", "sorry to hear", "sorry your", "i hope", "that must have been",
]
OWNERSHIP = re.compile(r"\b(i'?ve|i have|i'?ll|i will|i'?m|i am|we'?ve|we have|we'?ll|we will|i just|already|right now|today|tomorrow)\b", re.I)
DATE_RE = re.compile(r"\b(today|tomorrow|within \d+ (hours?|days?|business days?)|by (mon|tues|wednes|thurs|fri|satur|sun)day|by \d{1,2}(:\d{2})?\s?(am|pm)?|\d{1,2}[-/]\d{1,2}|\d{4}-\d{2}-\d{2}|in \d+ (hours?|days?)|\d+-\d+ (business )?days)\b", re.I)


def _tone(body: str) -> dict:
    low = body.lower()
    hits_policy = [p for p in POLICY_SPEAK if p in low]
    hits_emp = [e for e in EMPATHY if e in low]
    owner = len(OWNERSHIP.findall(body))
    apologies = len(re.findall(r"\b(sorry|apologi[sz]e|apologies)\b", low))
    exclam = body.count("!")
    rd = text.readability(body)
    passive = text.passive_sentences(body)
    long_sents = [s for s in text.sentences(body) if len(text.words(s)) > 25]
    has_date = bool(DATE_RE.search(body))
    score = 100
    fixes = []
    for p in hits_policy:
        score -= 12
        fixes.append(f"remove “{p}” — policy-speak / deflection")
    if not hits_emp:
        score -= 15
        fixes.append("acknowledge the specific problem in the customer's words (one sentence)")
    if owner == 0:
        score -= 15
        fixes.append("take ownership in first person: “I've refunded…”, “I'll ship…”")
    if apologies == 0:
        score -= 8
        fixes.append("apologise once, specifically")
    elif apologies > 1:
        score -= 6
        fixes.append(f"{apologies} apologies — one is enough; the rest reads as grovelling")
    if exclam > 0:
        score -= 5 * min(exclam, 3)
        fixes.append("drop exclamation marks in a service reply")
    if not has_date:
        score -= 12
        fixes.append("add a concrete timeframe (today / by Thursday / within 2 business days)")
    if rd["fk_grade"] and rd["fk_grade"] > 9:
        score -= 8
        fixes.append(f"reading grade {rd['fk_grade']} — shorten sentences, plain words (aim ≤ 8)")
    if passive:
        score -= 4 * min(len(passive), 2)
        fixes.append(f"{len(passive)} passive sentence(s) — say who did what")
    if long_sents:
        score -= 4
        fixes.append(f"{len(long_sents)} sentence(s) over 25 words")
    return {
        "score": max(0, score),
        "policy_speak": hits_policy,
        "empathy_markers": hits_emp,
        "ownership_phrases": owner,
        "apologies": apologies,
        "exclamation_marks": exclam,
        "has_timeframe": has_date,
        "fk_grade": rd["fk_grade"],
        "words": rd["words"],
        "fixes": fixes,
    }


@AGENT.tool
def tone_check(reply: str, customer_message: str = "") -> dict:
    """Score a support reply 0-100 for empathy, ownership, policy-speak, timeframe, apologies and readability, with concrete fixes.

    Args:
        reply: The drafted reply text.
        customer_message: Optional original customer message — checks the reply addresses its key terms.
    """
    if not reply.strip():
        raise ToolError("reply is empty.")
    if len(reply) > 20000:
        raise ToolError("reply too long (20k chars max).")
    out = _tone(reply)
    if customer_message.strip():
        key = [re.sub(r"'s$", "", w.lower()) for w, _ in text.top_terms(customer_message, 8)]
        stems = {w.lower()[:5] for w in text.words(reply)}
        rl = reply.lower()
        # stem match so "daughter's"/"daughter", "snapped"/"snap", "refunded"/"refund" count as mirrored
        addressed = [w for w in key if w in rl or w[:5] in stems]
        out["customer_terms"] = key
        out["customer_terms_addressed"] = addressed
        if key and len(addressed) / len(key) < 0.3:
            out["score"] = max(0, out["score"] - 10)
            out["fixes"].append("reply barely references the customer's own words — mirror the specific issue")
    out["verdict"] = f"Tone {out['score']}/100 — " + ("send." if out["score"] >= 75 else f"fix {len(out['fixes'])} item(s) before sending.")
    return out


@AGENT.tool
def lint_macro(template: str, variables: dict | None = None, customer_message: str = "", max_words: int = 150) -> dict:
    """Fill a macro's placeholders, catch unfilled/missing ones, check CARE structure, policy-speak and length, and return the send-ready text.

    Supports {{name}}, {{name | fallback}}, {name} and [PLACEHOLDER] styles.

    Args:
        template: The macro or drafted reply with placeholders.
        variables: Values for placeholders, e.g. {"first_name": "Ana", "order_number": "#1042"}.
        customer_message: Optional original customer message for the tone check.
        max_words: Word limit for the filled reply (150 default; 250 for technical issues).
    """
    if not template.strip():
        raise ToolError("template is empty.")
    if len(template) > 20000:
        raise ToolError("template too long (20k chars max).")
    variables = variables or {}
    found, missing, used_fallback = [], [], []

    def sub(m: re.Match) -> str:
        name = m.group(1) or m.group(3)
        fallback = m.group(2)
        if name is None:  # [PLACEHOLDER] style
            token = m.group(0)
            key = token.strip("[]").strip().lower().replace(" ", "_")
            found.append(key)
            if key in variables and str(variables[key]).strip():
                return str(variables[key])
            missing.append(token)
            return token
        found.append(name)
        val = variables.get(name)
        if val is not None and str(val).strip():
            return str(val)
        if fallback is not None:
            used_fallback.append(name)
            return fallback.strip("'\" ")
        missing.append(m.group(0))
        return m.group(0)

    filled = PLACEHOLDER_RE.sub(sub, template)
    low = filled.lower()
    structure = {
        "greeting": bool(re.match(r"\s*(hi|hello|hey|dear)\b", low)),
        "acknowledges_problem": any(e in low for e in EMPATHY) or bool(re.search(r"\b(sorry|apologi[sz]e)\b", low)),
        "states_action": bool(OWNERSHIP.search(filled)),
        "gives_timeframe": bool(DATE_RE.search(filled)),
        "next_step_or_contact": bool(re.search(r"\b(reply|let me know|just hit reply|reach (me|us)|you'?ll (get|receive|see)|we'?ll (send|email|update)|track)\b", low)),
        "sign_off": bool(re.search(r"(thanks|thank you|best|cheers|warmly|regards|talk soon)[,!]?\s*\n?\s*\w*\s*$", low.strip())),
    }
    missing_structure = [k for k, v in structure.items() if not v]
    words = len(text.words(filled))
    tone = _tone(filled)
    issues = []
    if missing:
        issues.append(f"unfilled placeholders: {', '.join(dict.fromkeys(missing))}")
    if missing_structure:
        issues.append(f"missing structure: {', '.join(missing_structure)}")
    if words > max_words:
        issues.append(f"{words} words > {max_words} — cut to the resolution and next step")
    if re.search(r"\b(order (number|#|id)|which order)\b.*\?", low) and any(k in variables for k in ("order_number", "order_id", "order")):
        issues.append("asks for the order number although it is known")
    ready = not missing and not missing_structure and words <= max_words and tone["score"] >= 75
    return {
        "filled": filled,
        "placeholders_found": list(dict.fromkeys(found)),
        "placeholders_missing": list(dict.fromkeys(missing)),
        "fallbacks_used": used_fallback,
        "structure": structure,
        "words": words,
        "tone_score": tone["score"],
        "tone_fixes": tone["fixes"],
        "issues": issues,
        "ready_to_send": ready,
        "verdict": ("Ready to send." if ready else f"Not ready: {len(issues)} issue(s), tone {tone['score']}/100.") + (f" Fallbacks used for {', '.join(used_fallback)}." if used_fallback else ""),
    }


@AGENT.tool
def support_metrics(
    tickets: int,
    orders: int,
    first_response_minutes: list[float] | None = None,
    resolution_hours: list[float] | None = None,
    csat_scores: list[float] | None = None,
    reopened: int = 0,
    period_days: int = 30,
    handle_time_minutes: float = 8.0,
    agent_hours_per_week: float = 40.0,
    occupancy_pct: float = 80.0,
    shrinkage_pct: float = 15.0,
) -> dict:
    """Turn raw desk data into contact rate, median/p90 first response and resolution, CSAT, reopen rate and the agents required.

    Args:
        tickets: Tickets created in the period.
        orders: Orders in the same period (for contact rate per 100 orders).
        first_response_minutes: First human response times in minutes (business-hour basis if you have it), one per ticket sampled.
        resolution_hours: Time to resolution in hours per resolved ticket.
        csat_scores: CSAT ratings on a 1-5 scale (or 0/1 thumbs); CSAT % = share of 4-5 (or 1).
        reopened: Tickets reopened after being solved.
        period_days: Days the ticket/order counts cover.
        handle_time_minutes: Average agent handle time per ticket incl. wrap-up.
        agent_hours_per_week: Scheduled hours per agent per week.
        occupancy_pct: Target share of scheduled time spent on tickets (75-85 typical).
        shrinkage_pct: Share of scheduled time lost to breaks, meetings, leave (15-20 typical).
    """
    if tickets < 0 or orders < 0 or period_days <= 0:
        raise ToolError("tickets/orders must be >= 0 and period_days > 0.")
    if not 0 < occupancy_pct <= 100 or not 0 <= shrinkage_pct < 100 or handle_time_minutes <= 0 or agent_hours_per_week <= 0:
        raise ToolError("occupancy 1-100, shrinkage 0-99, handle time and agent hours > 0.")
    frt = [float(x) for x in (first_response_minutes or []) if x is not None and x >= 0][:50000]
    res = [float(x) for x in (resolution_hours or []) if x is not None and x >= 0][:50000]
    csat = [float(x) for x in (csat_scores or []) if x is not None][:50000]
    contact_rate = 100 * tickets / orders if orders else None
    csat_pct = None
    if csat:
        if max(csat) <= 1:
            csat_pct = 100 * sum(1 for s in csat if s >= 1) / len(csat)
        else:
            csat_pct = 100 * sum(1 for s in csat if s >= 4) / len(csat)
    weekly_tickets = tickets / period_days * 7
    productive_hours = agent_hours_per_week * (1 - shrinkage_pct / 100) * (occupancy_pct / 100)
    agents_needed = weekly_tickets * handle_time_minutes / 60 / productive_hours if productive_hours else None
    findings = []
    if contact_rate is not None:
        if contact_rate > 15:
            findings.append(f"contact rate {contact_rate:.1f}/100 orders > 15 — a product/shipping/expectations problem, not a staffing one")
        elif contact_rate > 10:
            findings.append(f"contact rate {contact_rate:.1f}/100 orders — above the 5-10 healthy band; check WISMO share")
    if frt and median(frt) > 8 * 60:
        findings.append(f"median first response {median(frt) / 60:.1f}h > 8h — add coverage or macros for the top 3 categories")
    if frt and percentile(frt, 90) > 24 * 60:
        findings.append(f"p90 first response {percentile(frt, 90) / 60:.0f}h > 24h — the tail is where 1-star reviews come from")
    if csat_pct is not None and csat_pct < 85:
        findings.append(f"CSAT {csat_pct:.0f}% < 85% — review lowest-rated tickets by category")
    if tickets and reopened / tickets > 0.05:
        findings.append(f"reopen rate {100 * reopened / tickets:.1f}% > 5% — replies are not resolving first time")
    return {
        "period_days": period_days,
        "tickets": tickets,
        "orders": orders,
        "contact_rate_per_100_orders": round(contact_rate, 2) if contact_rate is not None else None,
        "first_response_minutes": {"median": round(median(frt), 1), "mean": round(mean(frt), 1), "p90": round(percentile(frt, 90), 1)} if frt else None,
        "resolution_hours": {"median": round(median(res), 1), "mean": round(mean(res), 1), "p90": round(percentile(res, 90), 1)} if res else None,
        "csat_pct": round(csat_pct, 1) if csat_pct is not None else None,
        "csat_responses": len(csat),
        "reopen_rate_pct": pct(reopened / tickets) if tickets else None,
        "weekly_tickets": round(weekly_tickets, 1),
        "productive_hours_per_agent_week": round(productive_hours, 1),
        "agents_needed": round(agents_needed, 2) if agents_needed is not None else None,
        "agents_needed_rounded_up": math.ceil(agents_needed) if agents_needed else None,
        "findings": findings,
        "summary": (
            (f"Contact rate {contact_rate:.1f}/100 orders. " if contact_rate is not None else "")
            + (f"Median FRT {median(frt) / 60:.1f}h (p90 {percentile(frt, 90) / 60:.0f}h). " if frt else "")
            + (f"CSAT {csat_pct:.0f}%. " if csat_pct is not None else "")
            + (f"Need {agents_needed:.1f} agents ({weekly_tickets:.0f} tickets/wk × {handle_time_minutes:g} min ÷ {productive_hours:.1f} productive h)." if agents_needed is not None else "")
        ),
    }
