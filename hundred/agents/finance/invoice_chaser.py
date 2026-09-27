"""Invoice Chaser — gets late invoices paid with an aging report, exact late fees, and a dunning cadence."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from ...core import Agent, ToolError
from ...lib import dates, text
from ._common import D, ZERO, as_rate, bound_rows, money, parse_iso, ratio_to_pct, require_nonneg, require_positive

AGENT = Agent(
    slug="invoice-chaser",
    name="Invoice Chaser",
    category="finance",
    tagline="Turn overdue invoices into cash: aging report, exact late fees, and a dunning sequence that stays polite until it shouldn't.",
    description=(
        "Runs accounts-receivable collections like a controller. Builds the aging report (current / 1-30 / "
        "31-60 / 61-90 / 90+ with DSO and customer concentration), computes late fees to the cent under "
        "your contract terms, generates a dated dunning schedule with escalating tone per touch, and "
        "lints every chase email so it contains the invoice number, amount, due date, payment link and a "
        "single clear ask. Drafts go out through Gmail or your invoicing tool when connected."
    ),
    triggers=[
        "chase an overdue / late invoice",
        "write a payment reminder email",
        "build an accounts receivable aging report",
        "calculate the late fee on an invoice",
        "set up a dunning sequence / collections cadence",
        "what is our DSO",
    ],
    examples=[
        "Invoice #1042 for $8,500 was due August 15 and still isn't paid. Write the reminder and tell me what late fee I can add (1.5%/month in the contract).",
        "Here's my open invoice list as of today — give me the aging report and who to chase first.",
        "Set up a reminder schedule for a $12k invoice due on the 30th so I never have to think about it.",
    ],
    connectors=["Gmail", "QuickBooks", "Xero", "Stripe", "HubSpot", "Slack"],
    playbook="""
    ## Standard
    You are a collections-savvy controller. Excellent means: cash arrives sooner without burning the
    relationship. The one metric is **DSO (days sales outstanding)** trending down; the operating
    proxy is the share of AR over 60 days, which should be under 10%. Every message you write names
    one invoice, one amount, one date, one action. Late fees are contract terms, not threats;
    statutory limits vary by jurisdiction, so state the fee as "per your agreement" and flag a lawyer
    before adding a fee not in the signed terms.

    ## Intake
    Needed: invoice number, amount, issue date, due date, customer name, and what has already been
    sent. For a portfolio: the open-invoice list. Ask at most 3 questions only if the due date or
    amount is missing. Assume net-30 terms and today's date when not given, and say so.

    ## Procedure
    1. **Build the picture.** For any list of invoices call `invoice_chaser__aging_report` with the
       open invoices and the as-of date. It returns bucket totals, DSO (if you pass trailing revenue),
       customer concentration and a ranked chase list (largest × oldest first). Chase in that order;
       do not start with the friendliest customer.
    2. **Price the lateness.** For each invoice past due, call `invoice_chaser__late_fee` with the
       contract's fee terms (monthly %, annual %, or flat) and grace period. Quote the fee only if the
       terms allow it; otherwise report it as leverage you do not have and recommend adding
       a late-fee clause to future contracts (1.5%/month is the common commercial term).
    3. **Schedule the touches.** Call `invoice_chaser__dunning_schedule` with the due date and
       amount. It returns dated touches (business-day adjusted) with channel, tone and subject line,
       and tells you which touch is due *now*. Do not skip ahead: a "final notice" as the first
       message destroys goodwill and rarely accelerates payment.
    4. **Write the message for the current touch.** Rules: subject carries the invoice number and
       amount; first line states the fact (invoice, amount, due date, days past due); second line is
       the ask with a specific date; include the payment link or remittance details; one message, one
       invoice; under 150 words until the final notice. Then call
       `invoice_chaser__chase_message_lint` and fix every issue it reports before sending.
    5. **Escalate correctly.** Touch 3+ moves from AP contact to the person who signed the deal.
       Touch 5 (30+ days) states consequences: late fee applied, service pause date, or referral to
       collections after a named date. Never threaten what you will not do.
    6. **Act.** With Gmail: create drafts (never auto-send). With QuickBooks/Xero/Stripe: attach the
       reminder to the invoice record and log the touch. Without connectors: output ready-to-paste
       messages plus the schedule as a table.

    ## Frameworks
    - **Aging buckets:** current, 1-30, 31-60, 61-90, 90+. Probability of collecting drops sharply
      past 90 days; treat 90+ as a write-off risk and escalate to a call, not an email.
    - **DSO** = AR ÷ credit sales in period × days in period. Compare to your payment terms: DSO
      more than 1.5× terms means your process, not your customers, is the problem.
    - **Cadence (net-30 default):** T-7 friendly heads-up, T+1 due-date notice, T+7 second notice,
      T+14 phone call + email, T+30 final notice with fee, T+45 escalation/collections referral.
    - **Tone ladder:** helpful → factual → firm → formal → consequence. One step per touch.
    - **Chase priority score** = amount × days overdue; work the top of the list every morning.

    ## Output format
    ```
    # Collections brief — <YYYY-MM-DD>
    **Open AR:** $X across N invoices · **Over 60 days:** y% · **DSO:** Z days (terms: net-30)

    ## Chase list (today)
    | # | Customer | Invoice | Amount | Days late | Touch due | Late fee |

    ## Message — <touch name> for <invoice>
    Subject: <…>
    <body ≤150 words>

    ## Schedule for <invoice>
    | Touch | Date | Channel | Tone |

    ## Process fixes
    - <one line each: terms, deposits, late-fee clause, auto-reminders>
    ```

    ## Anti-patterns
    - "Just checking in on that invoice" — no number, no amount, no date, no ask.
    - Apologising for asking to be paid. State facts, ask clearly, thank them once.
    - Computing days overdue or fees in your head. Use the tools; off-by-one days become wrong fees.
    - Sending the whole ladder in one email. One touch, one tone, one ask.
    - Chasing a $200 invoice before a $20,000 one because the small one is older.
    """,
)

BUCKETS = [("current", -10**9, 0), ("1-30", 1, 30), ("31-60", 31, 60), ("61-90", 61, 90), ("90+", 91, 10**9)]


def _bucket(days_late: int) -> str:
    for name, lo, hi in BUCKETS:
        if lo <= days_late <= hi:
            return name
    return "current"


@AGENT.tool
def aging_report(invoices: list[dict], as_of: str = "", revenue_last_90_days: float = 0, payment_terms_days: int = 30) -> dict:
    """Build an AR aging report: bucket totals, DSO, customer concentration and a ranked chase list.

    Pass every open (unpaid or partly paid) invoice. Bucket = days past due as of `as_of`.
    Chase priority = outstanding amount × days overdue, so big-and-old rises to the top.

    Args:
        invoices: List of {"id": str, "customer": str, "amount": number, "due": "YYYY-MM-DD", "paid": number (optional, default 0)}.
        as_of: Report date YYYY-MM-DD. Defaults to today.
        revenue_last_90_days: Credit sales in the trailing 90 days; needed to compute DSO (0 = skip DSO).
        payment_terms_days: Your standard terms (30 for net-30), used to judge DSO.
    """
    rows = bound_rows(invoices, "invoices")
    today = parse_iso(as_of, "as_of") if as_of else date.today()
    buckets = {name: {"amount": ZERO, "count": 0} for name, _, _ in BUCKETS}
    by_customer: dict[str, Decimal] = defaultdict(lambda: ZERO)
    items = []
    total = ZERO
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ToolError(f"invoices[{i}] must be an object")
        amount = require_positive(D(row.get("amount"), f"invoices[{i}].amount"), f"invoices[{i}].amount")
        paid = require_nonneg(D(row.get("paid", 0), f"invoices[{i}].paid"), f"invoices[{i}].paid")
        outstanding = amount - paid
        if outstanding <= 0:
            continue
        due = parse_iso(row.get("due", ""), f"invoices[{i}].due")
        days_late = (today - due).days
        b = _bucket(days_late)
        buckets[b]["amount"] += outstanding
        buckets[b]["count"] += 1
        customer = str(row.get("customer") or "unknown")
        by_customer[customer] += outstanding
        total += outstanding
        items.append(
            {
                "id": str(row.get("id") or f"#{i}"),
                "customer": customer,
                "outstanding": money(outstanding),
                "due": due.isoformat(),
                "days_late": max(days_late, 0),
                "bucket": b,
                "priority_score": money(outstanding * max(days_late, 0)),
            }
        )
    if total <= 0:
        raise ToolError("No outstanding balance on any invoice — nothing to age")
    over_60 = buckets["61-90"]["amount"] + buckets["90+"]["amount"]
    overdue = total - buckets["current"]["amount"]
    chase = sorted((x for x in items if x["days_late"] > 0), key=lambda x: -x["priority_score"])
    conc = sorted(by_customer.items(), key=lambda kv: -kv[1])
    top_customer_share = ratio_to_pct(conc[0][1] / total) if conc else 0.0
    dso = None
    dso_note = "pass revenue_last_90_days to compute DSO"
    if revenue_last_90_days and D(revenue_last_90_days) > 0:
        dso = round(float(total / D(revenue_last_90_days) * 90), 1)
        dso_note = (
            f"DSO {dso} days vs net-{payment_terms_days} terms: "
            + ("healthy" if dso <= payment_terms_days * 1.2 else "slow — process problem, tighten cadence" if dso <= payment_terms_days * 1.5 else "critical — more than 1.5x terms")
        )
    verdict = (
        f"${money(total):,.2f} open across {len(items)} invoices; {ratio_to_pct(overdue / total)}% overdue, "
        f"{ratio_to_pct(over_60 / total)}% over 60 days ({'target <10%' if over_60 / total >= Decimal('0.1') else 'within target'}). "
        + (f"Chase {chase[0]['customer']} {chase[0]['id']} first." if chase else "Nothing overdue yet — schedule pre-due reminders.")
    )
    return {
        "as_of": today.isoformat(),
        "total_outstanding": money(total),
        "overdue_total": money(overdue),
        "overdue_pct": ratio_to_pct(overdue / total),
        "over_60_pct": ratio_to_pct(over_60 / total),
        "buckets": {k: {"amount": money(v["amount"]), "count": v["count"], "pct": ratio_to_pct(v["amount"] / total)} for k, v in buckets.items()},
        "dso_days": dso,
        "dso_note": dso_note,
        "customer_concentration": [{"customer": c, "outstanding": money(a), "pct": ratio_to_pct(a / total)} for c, a in conc[:5]],
        "top_customer_share_pct": top_customer_share,
        "chase_list": chase[:25],
        "verdict": verdict,
    }


@AGENT.tool
def late_fee(
    amount: float,
    due_date: str,
    as_of: str = "",
    fee_type: Literal["monthly_pct", "annual_pct", "flat"] = "monthly_pct",
    rate: float = 1.5,
    grace_days: int = 0,
    cap_pct: float = 0,
    compounding: bool = False,
) -> dict:
    """Compute the late fee owed on an overdue invoice to the cent, under the contract's terms.

    monthly_pct: rate% per 30-day period, pro-rated daily (simple) or compounded per full month.
    annual_pct: rate% per year pro-rated daily. flat: a fixed fee once past the grace period.
    States the fee as contractual — verify the clause exists and any statutory cap in your jurisdiction.

    Args:
        amount: Outstanding invoice amount.
        due_date: Due date YYYY-MM-DD.
        as_of: Date to compute through, YYYY-MM-DD. Defaults to today.
        fee_type: "monthly_pct" (default, e.g. 1.5%/month), "annual_pct" (e.g. 8% p.a.) or "flat".
        rate: Percent for pct types (1.5 = 1.5%), or the dollar amount for "flat".
        grace_days: Days after due date before fees start.
        cap_pct: Maximum total fee as a percent of the invoice amount (0 = no cap).
        compounding: For monthly_pct, compound each full month on the running balance instead of simple interest.
    """
    amt = require_positive(D(amount, "amount"), "amount")
    due = parse_iso(due_date, "due_date")
    today = parse_iso(as_of, "as_of") if as_of else date.today()
    if grace_days < 0 or grace_days > 365:
        raise ToolError("grace_days must be between 0 and 365")
    r = D(rate, "rate")
    if r < 0:
        raise ToolError("rate cannot be negative")
    days_late = (today - due).days
    chargeable = max(days_late - grace_days, 0)
    if days_late <= 0:
        return {"days_late": 0, "chargeable_days": 0, "fee": 0.0, "total_due": money(amt), "verdict": f"Not yet due — due {due.isoformat()}, {-days_late} days from {today.isoformat()}."}
    if fee_type == "flat":
        fee = r if chargeable > 0 else ZERO
        basis = f"flat ${money(r):,.2f} once past {grace_days}-day grace"
    elif fee_type == "annual_pct":
        fee = amt * (r / 100) * Decimal(chargeable) / Decimal(365)
        basis = f"{r}% p.a. simple, pro-rated {chargeable} days"
    else:
        if compounding:
            full_months, rem = divmod(chargeable, 30)
            bal = amt
            for _ in range(full_months):
                bal += bal * r / 100
            bal += bal * (r / 100) * Decimal(rem) / Decimal(30)
            fee = bal - amt
            basis = f"{r}%/month compounded over {full_months} full month(s) + {rem} days"
        else:
            fee = amt * (r / 100) * Decimal(chargeable) / Decimal(30)
            basis = f"{r}% per 30 days simple, pro-rated {chargeable} days"
    capped = False
    if cap_pct and D(cap_pct) > 0 and fee > amt * D(cap_pct) / 100:
        fee = amt * D(cap_pct) / 100
        capped = True
    fee_m = money(fee)
    return {
        "days_late": days_late,
        "chargeable_days": chargeable,
        "fee": fee_m,
        "fee_pct_of_invoice": ratio_to_pct(fee / amt, 2),
        "total_due": money(amt + fee),
        "basis": basis + (" (capped)" if capped else ""),
        "daily_accrual": money(amt * (r / 100) / Decimal(30 if fee_type == "monthly_pct" else 365)) if fee_type != "flat" and not capped else 0.0,
        "verdict": f"{days_late} days past due; late fee ${fee_m:,.2f} ({basis}); total now due ${money(amt + fee):,.2f}.",
        "scope_note": "Charge only if your signed terms include this clause; statutory caps on late interest vary by jurisdiction — verify before invoicing the fee.",
    }


TOUCHES = [
    (-7, "pre-due reminder", "email", "helpful", "Invoice {id} ({amount}) due {due}"),
    (1, "due-date notice", "email", "factual", "Invoice {id} ({amount}) was due {due}"),
    (7, "second notice", "email", "firm", "Overdue: invoice {id} ({amount}) — 7 days past due"),
    (14, "call + email", "phone", "firm", "Follow-up on invoice {id} ({amount}) — payment date?"),
    (30, "final notice", "email", "formal", "Final notice: invoice {id} ({amount}) — late fee applies"),
    (45, "escalation", "email", "consequence", "Invoice {id} ({amount}) — referral to collections on {escalation_date}"),
]


@AGENT.tool
def dunning_schedule(due_date: str, amount: float, invoice_id: str = "", as_of: str = "", offsets_days: list[int] | None = None) -> dict:
    """Generate the dated dunning sequence for one invoice and say which touch is due now.

    Default cadence: T-7, T+1, T+7, T+14 (call), T+30 (final notice, fee), T+45 (escalation).
    Dates that land on a weekend roll to the next business day. Pass offsets_days to use your own cadence.

    Args:
        due_date: Invoice due date YYYY-MM-DD.
        amount: Invoice amount (used in subject lines).
        invoice_id: Invoice number for subject lines.
        as_of: Today's date YYYY-MM-DD; defaults to today. Determines the current touch.
        offsets_days: Optional custom offsets from the due date, e.g. [-3, 1, 10, 20, 35].
    """
    due = parse_iso(due_date, "due_date")
    amt = require_positive(D(amount, "amount"), "amount")
    today = parse_iso(as_of, "as_of") if as_of else date.today()
    if offsets_days:
        if len(offsets_days) > 12 or any(abs(o) > 365 for o in offsets_days):
            raise ToolError("offsets_days: at most 12 offsets, each within ±365 days")
        base = [(o, *TOUCHES[min(i, len(TOUCHES) - 1)][1:]) for i, o in enumerate(sorted(offsets_days))]
    else:
        base = TOUCHES
    inv = invoice_id or "(invoice)"
    amount_s = f"${money(amt):,.2f}"
    escalation_date = due + timedelta(days=60)
    touches = []
    for n, (offset, name, channel, tone, subject) in enumerate(base, 1):
        d = due + timedelta(days=offset)
        while d.weekday() >= 5:
            d += timedelta(days=1)
        touches.append(
            {
                "touch": n,
                "name": name,
                "date": d.isoformat(),
                "weekday": d.strftime("%a"),
                "offset_days": offset,
                "channel": channel,
                "tone": tone,
                "subject": subject.format(id=inv, amount=amount_s, due=due.isoformat(), escalation_date=escalation_date.isoformat()),
                "status": "sent/past" if d < today else "due today" if d == today else "upcoming",
            }
        )
    days_late = (today - due).days
    current = next((t for t in reversed(touches) if dates.parse_date(t["date"]) <= today), None)
    nxt = next((t for t in touches if dates.parse_date(t["date"]) > today), None)
    return {
        "invoice": inv,
        "due": due.isoformat(),
        "as_of": today.isoformat(),
        "days_late": max(days_late, 0),
        "touches": touches,
        "current_touch": current,
        "next_touch": nxt,
        "verdict": (
            f"{max(days_late, 0)} days past due — send touch {current['touch']} ({current['name']}, {current['tone']}) now; next is {nxt['name']} on {nxt['date']}."
            if current and nxt
            else f"Not yet due — first touch ({touches[0]['name']}) goes on {touches[0]['date']}."
            if not current
            else f"All touches exhausted ({current['name']} on {current['date']}) — hand to collections or legal."
        ),
    }


AGGRESSIVE = re.compile(r"\b(immediately|unacceptable|ridiculous|lawyer|sue|legal action|ignoring|excuses?|disappointed|last chance|you people)\b", re.I)
APOLOGETIC = re.compile(r"\b(sorry to bother|apologi[sz]e for|hate to ask|just checking in|no rush|whenever you get a chance|if it'?s not too much trouble)\b", re.I)
ASK_RE = re.compile(r"\b(please (?:pay|remit|send|confirm|let (?:me|us) know)|can you (?:confirm|pay|send)|we (?:need|require)|kindly (?:remit|pay|confirm)|by (?:end of|eod|close of business|\w+day|\d{1,2}(?:st|nd|rd|th)?|20\d\d))\b", re.I)
LINK_RE = re.compile(r"(https?://\S+|pay(?:ment)? link|bank details|wire|ACH|account (?:number|no\.?)|remit(?:tance)? (?:to|details))", re.I)
DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.? \d{1,2}(?:st|nd|rd|th)?(?:,? \d{4})?|\d{1,2}(?:st|nd|rd|th)? (?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*)\b", re.I)


@AGENT.tool
def chase_message_lint(message: str, invoice_id: str, amount: float, due_date: str, touch: int = 2) -> dict:
    """Score a payment-chase email 0-100 and list the exact fixes before it goes out.

    Checks the message carries the invoice number, the amount, the due date, a payment method or
    link, one specific ask with a deadline, and that tone matches the touch (no apologising early,
    no aggression before the final notice). Enforces the 150-word cap for touches 1-4.

    Args:
        message: The full email including a "Subject:" line if there is one.
        invoice_id: The invoice number that must appear.
        amount: The outstanding amount that must appear (any common formatting).
        due_date: Due date YYYY-MM-DD that must be referenced.
        touch: Which touch in the sequence this is (1-6); sets tone and length expectations.
    """
    if not message.strip():
        raise ToolError("message is empty")
    if len(message) > 20_000:
        raise ToolError("message too long (20k chars max)")
    if not 1 <= touch <= 6:
        raise ToolError("touch must be 1-6")
    amt = require_positive(D(amount, "amount"), "amount")
    due = parse_iso(due_date, "due_date")
    body = message
    subject = ""
    m = re.search(r"^\s*subject:\s*(.+)$", message, re.I | re.M)
    if m:
        subject = m.group(1).strip()
        body = message[m.end():]
    words = len(text.words(body))
    issues, score = [], 100
    inv_re = re.escape(str(invoice_id).strip())
    if not re.search(inv_re, message, re.I):
        issues.append(f"invoice number {invoice_id!r} not mentioned")
        score -= 20
    amt_variants = {f"{money(amt):,.2f}", f"{money(amt):,.0f}", f"{money(amt):.2f}", f"{money(amt):.0f}"}
    if not any(v in message for v in amt_variants):
        issues.append(f"amount ${money(amt):,.2f} not mentioned")
        score -= 20
    if not DATE_RE.search(message):
        issues.append(f"due date ({due.isoformat()}) not referenced")
        score -= 15
    if not LINK_RE.search(message):
        issues.append("no payment link or remittance details")
        score -= 15
    if not ASK_RE.search(message):
        issues.append("no explicit ask with a deadline (e.g. 'please remit by Friday 10 Oct')")
        score -= 15
    if subject:
        if not re.search(inv_re, subject, re.I):
            issues.append("subject line should carry the invoice number")
            score -= 5
        if len(subject) > 70:
            issues.append(f"subject is {len(subject)} chars; keep under 70")
            score -= 3
    else:
        issues.append("no Subject: line")
        score -= 5
    if touch <= 4 and words > 150:
        issues.append(f"{words} words; touches 1-4 should be under 150")
        score -= 10
    if touch >= 5 and words > 300:
        issues.append(f"{words} words; even a final notice should be under 300")
        score -= 5
    if (a := APOLOGETIC.search(message)):
        issues.append(f"apologetic phrase {a.group(0)!r} weakens the ask — state facts instead")
        score -= 10
    if touch < 5 and (g := AGGRESSIVE.search(message)):
        issues.append(f"aggressive wording {g.group(0)!r} is too early for touch {touch}")
        score -= 10
    if message.count("?") > 2:
        issues.append("more than two questions — one ask only")
        score -= 5
    score = max(score, 0)
    return {
        "score": score,
        "words": words,
        "subject": subject or None,
        "issues": issues,
        "ready_to_send": score >= 85 and not any(k in " ".join(issues) for k in ("not mentioned", "no explicit ask")),
        "verdict": "Ready to send." if score >= 85 else f"Fix {len(issues)} issue(s) before sending; the ask must be unmissable.",
    }
