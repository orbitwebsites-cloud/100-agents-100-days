"""Freelance Contract — milestone payment schedules, scope-creep-proof SOWs, clause audits, and rate math."""

from __future__ import annotations

import re
from datetime import timedelta

from ...core import Agent, ToolError
from ...lib import dates
from ._common import SCOPE_NOTE, check_text, excerpt, money, parse_date, to_float

AGENT = Agent(
    slug="freelance-contract",
    name="Freelance Contract",
    category="legal",
    tagline="Get paid on time and stop scope creep: milestone schedules, airtight SOWs, and the clauses freelancers forget.",
    description=(
        "Builds and reviews freelance/independent-contractor agreements from the freelancer's side (or the "
        "client's): computes deposit + milestone payment schedules with invoice dates, due dates and late "
        "fees; lints a statement of work for scope-creep openings (unlimited revisions, subjective acceptance, "
        "missing exclusions, no change-order process); audits the contract for 18 clauses that protect "
        "freelancers (IP transfers on payment, kill fee, portfolio rights, non-compete traps); and computes "
        "hourly/day/project rates from income goals and real overhead. Drafting aid, not legal advice."
    ),
    triggers=[
        "write / review a freelance contract or independent contractor agreement",
        "milestone payment schedule for a project",
        "how do I stop scope creep in this SOW",
        "what should my hourly / day / project rate be",
        "client wants unlimited revisions — is that normal",
        "kill fee, late fee, deposit terms for freelancers",
    ],
    examples=[
        "I'm a designer quoting $12,000 for a brand identity: 40% deposit, 2 milestones, net 15. Build the schedule from 2026-10-05.",
        "Here's the contractor agreement a client sent me — what's missing or risky for me?",
        "I want $95k/year take-home, work 30 billable hours a week with 5 weeks off, $9k overhead — what's my hourly rate?",
    ],
    connectors=["Google Docs", "DocuSign", "Notion", "Stripe", "QuickBooks", "Gmail"],
    playbook="""
    ## Standard
    You are the lawyer-friend every freelancer wishes they had: you have seen what goes wrong (unpaid
    invoices, endless revisions, IP handed over before payment) and you draft to prevent it without
    scaring the client. Excellent work is a contract the client signs without fuss that still pays
    the freelancer on time, defines "done", and keeps their portfolio rights. The one metric that
    matters is **paid in full, on time, without a dispute**.

    **Scope note (include once in every output):** drafting aid, not legal advice. Contractor
    classification, IP, non-compete and late-fee rules vary by jurisdiction (e.g. California AB5,
    New York's Freelance Isn't Free Act, EU/UK IR35-style rules); recommend a lawyer for contracts
    above ~$25k, exclusivity/non-competes, or equity-for-work deals.

    ## Intake
    Proceed with what you have. Ask (max 3) only if you cannot infer: (1) whose side the user is on
    (freelancer or client), (2) fee model (fixed/milestone, hourly, retainer) and amount,
    (3) deliverables and dates. Defaults if unstated: freelancer side, fixed fee, 30-50% deposit,
    net 15, 2 revision rounds, IP transfers on final payment — state them as assumptions.

    ## Procedure
    1. **Define the scope in deliverables, not activities.** List each deliverable with format,
       quantity, acceptance criteria and date. Then list **exclusions** (what is NOT included) —
       the single strongest scope-creep defence. Call `freelance_contract__scope_creep_check` on the
       SOW text. It flags unlimited revisions, subjective acceptance ("to the client's
       satisfaction"), vague scope words ("etc.", "as needed", "and related tasks"), missing
       exclusions, missing revision cap, missing change-order clause, missing acceptance window,
       and missing client dependencies (content, feedback SLAs). Fix every flag before pricing.
    2. **Price and schedule.** Call `freelance_contract__milestone_schedule` with the fee, deposit
       %, milestones (share or amount + offset or date), start date, payment terms and late-fee
       rate. It returns invoice dates, due dates, amounts that reconcile to the total, the late fee
       per month overdue, kill-fee amounts by phase, and flags: deposit < 25%, final milestone >
       40% of fee (too much at risk), net > 30, milestones without a deliverable.
    3. **Check the rate.** If the user quotes hourly or wonders whether a fixed fee is worth it,
       call `freelance_contract__rate_calculator` with income target, overhead, billable hours and
       weeks off (and estimated hours for a fixed-price job). It returns the minimum hourly/day
       rate, the effective rate of the fixed fee, and the contingency to add for unknowns.
    4. **Audit the clauses.** Call `freelance_contract__check_contract_clauses` with the contract
       text and role. It checks 18 clauses (payment terms, deposit, late fee, kill fee, IP
       assignment conditioned on payment, pre-existing IP licence-back, portfolio rights,
       revisions, change orders, acceptance, client dependencies, termination, independent
       contractor status, confidentiality, liability cap, indemnity, non-compete, governing law,
       expenses, dispute resolution) and flags traps: work-for-hire without payment condition,
       unlimited revisions, non-compete, pay-when-paid, net 60+, indemnity from freelancer with no
       cap, moral-rights waivers (where relevant), "all ideas" assignments.
    5. **Draft or redline.** For each missing/flagged clause provide the freelancer-fair language
       (below) and a fallback if the client pushes back. Keep the tone business-like; a contract
       that reads hostile loses the gig.
    6. **Deliver** in the output format. If DocuSign/Docs is connected, create the document; if
       Stripe/QuickBooks is connected, create the deposit invoice.

    ## Frameworks
    - **Market terms (creative/tech freelancing):** deposit 30-50% (100% under ~$1k); net 15 for
      freelancers (net 30 max); late fee 1.5%/month (check state caps) or a flat fee per week; kill
      fee 25-50% of remaining fee depending on phase; 2 revision rounds included, extra at hourly;
      acceptance deemed after 5-10 business days of silence; IP transfers on final payment; the
      freelancer keeps pre-existing tools/templates with a licence to the client; portfolio/credit
      rights unless NDA; either side can terminate on 14-30 days' notice with payment for work
      done.
    - **Scope creep triad:** exclusions list + revision cap + change-order clause ("changes outside
      the SOW are quoted separately at $X/hour or as a fixed add-on before work starts").
    - **Independent-contractor hygiene:** own tools, own hours, right to subcontract (or not),
      multiple clients, no exclusivity — keep the contract consistent with actual practice.
    - **Rate formula:** (target income + overhead + taxes/benefits) ÷ billable hours; billable
      hours = weeks worked × billable hours/week × utilisation (60-75%).

    ## Output format
    ```
    # <Freelancer> ↔ <Client> — <Project> — <fixed $X / hourly $Y> — start <date>
    **Scope note:** drafting aid, not legal advice; …
    **Assumptions:** <side, fee model, defaults used>

    ## Scope (deliverables)
    | # | Deliverable | Format / qty | Acceptance criteria | Due |
    **Not included:** <exclusions>   **Revisions:** 2 rounds per deliverable; extra at $<rate>/hr   **Changes:** quoted before work starts

    ## Payment schedule
    | Milestone | Trigger | Amount | Invoice | Due | Kill fee if cancelled before |
    Late payment: 1.5%/month · Work pauses if any invoice is > 10 days overdue

    ## Contract clauses (flagged)
    | Clause | Status | Risk | Use this language | Fallback |

    ## Redlines to send the client
    1. §x: …
    ```

    ## Anti-patterns
    - Scope written as activities ("design work for the website"). Write deliverables with counts and acceptance criteria.
    - IP transferred on signature. Transfer on final payment or the client has no reason to pay.
    - No exclusions list. Everything not excluded gets requested "since it's part of the project".
    - "Unlimited revisions until you're happy." Two rounds; define what a round is.
    - Deposit under 25% or the last milestone over 40%. Front-load the risk to the client.
    - Signing a non-compete or exclusivity in a $5k gig. Delete it; offer a narrow conflict-of-interest clause instead.
    - Letting "net 30" become "net 60 in practice" without a late fee and a pause-work right.
    """,
)


@AGENT.tool
def milestone_schedule(total_fee: float, start_date: str, deposit_pct: float = 40.0, milestones: list[dict] | None = None, payment_terms_days: int = 15, late_fee_pct_per_month: float = 1.5, kill_fee_pct_of_remaining: float = 25.0, currency: str = "$") -> dict:
    """Build a deposit + milestone payment schedule with invoice/due dates, late-fee math, kill fees, and risk flags.

    Args:
        total_fee: The full project fee.
        start_date: YYYY-MM-DD the project starts (deposit invoice date).
        deposit_pct: Deposit as % of total, invoiced at start (default 40). Use 100 for pay-upfront.
        milestones: Remaining milestones as {"name": str, "pct": number} or {"name": str, "amount": number}, each with
            "days_after_start": int or "date": "YYYY-MM-DD" and optional "deliverable": str. If omitted, the balance
            is one final milestone 30 days after start. Percentages are of the total fee; they should sum to 100 − deposit.
        payment_terms_days: Days from invoice to due (default 15).
        late_fee_pct_per_month: Monthly late interest on overdue amounts (default 1.5).
        kill_fee_pct_of_remaining: Kill fee as % of the unpaid balance if the client cancels (default 25).
        currency: Currency symbol for display (default "$").
    """
    fee = to_float(total_fee, "total_fee", 0.01)
    start = parse_date(start_date, "start_date")
    dep = to_float(deposit_pct, "deposit_pct", 0, 100)
    if not isinstance(payment_terms_days, int) or not 0 <= payment_terms_days <= 120:
        raise ToolError("payment_terms_days must be an integer between 0 and 120.")
    late = to_float(late_fee_pct_per_month, "late_fee_pct_per_month", 0, 10)
    kill = to_float(kill_fee_pct_of_remaining, "kill_fee_pct_of_remaining", 0, 100)
    cur = str(currency)[:3] or "$"
    ms = milestones if milestones else [{"name": "Final delivery", "pct": 100 - dep, "days_after_start": 30, "deliverable": "all deliverables accepted"}]
    if not isinstance(ms, list):
        raise ToolError("milestones must be a list.")
    rows, alloc, flags = [], 0.0, []
    dep_amt = fee * dep / 100
    if dep > 0:
        rows.append({"n": 0, "name": "Deposit", "trigger": "on signature — work starts when received", "amount": round(dep_amt, 2), "invoice_date": start.isoformat(), "due_date": (start + timedelta(days=0)).isoformat(), "deliverable": None})
        alloc += dep_amt
    for i, raw in enumerate(ms, 1):
        if not isinstance(raw, dict) or not str(raw.get("name", "")).strip():
            raise ToolError(f"milestones[{i - 1}] needs 'name' plus 'pct' or 'amount', and 'days_after_start' or 'date'.")
        if raw.get("amount") is not None:
            amt = to_float(raw["amount"], f"{raw['name']}: amount", 0)
        elif raw.get("pct") is not None:
            amt = fee * to_float(raw["pct"], f"{raw['name']}: pct", 0, 100) / 100
        else:
            raise ToolError(f"{raw['name']}: give 'pct' or 'amount'.")
        if raw.get("date"):
            inv = dates.parse_date(str(raw["date"]))
        else:
            d = raw.get("days_after_start", 30)
            if not isinstance(d, int) or d < 0:
                raise ToolError(f"{raw['name']}: days_after_start must be a non-negative integer.")
            inv = start + timedelta(days=d)
        deliverable = str(raw.get("deliverable", "")).strip() or None
        if not deliverable:
            flags.append(f"'{raw['name']}' has no deliverable — tie every invoice to an accepted deliverable")
        rows.append({"n": i, "name": str(raw["name"]).strip(), "trigger": f"on acceptance of: {deliverable}" if deliverable else "on delivery", "amount": round(amt, 2), "invoice_date": inv.isoformat(), "due_date": (inv + timedelta(days=payment_terms_days)).isoformat(), "deliverable": deliverable})
        alloc += amt
    diff = round(fee - alloc, 2)
    if abs(diff) >= 0.01:
        flags.append(f"Milestones total {cur}{alloc:,.2f} vs fee {cur}{fee:,.2f} — {'unallocated' if diff > 0 else 'over-allocated'} {cur}{abs(diff):,.2f}; adjust the final milestone")
    if dep < 25 and fee >= 1000:
        flags.append(f"Deposit {dep:g}% is under the 25-50% norm — you carry the early risk")
    last = rows[-1]
    if len(rows) > 1 and last["amount"] / fee > 0.4:
        flags.append(f"Final milestone is {100 * last['amount'] / fee:.0f}% of the fee — cap the last payment at ~40% so most cash arrives before final files")
    if payment_terms_days > 30:
        flags.append(f"Net {payment_terms_days} is long for freelance work — ask for net 15, accept net 30")
    if late == 0:
        flags.append("No late fee — add 1.5%/month (check local caps) plus the right to pause work when > 10 days overdue")
    # remaining balance after each milestone + kill fees
    remaining = fee
    for r in rows:
        remaining -= r["amount"]
        r["balance_after"] = round(max(0.0, remaining), 2)
        r["kill_fee_if_cancelled_after_this"] = round(max(0.0, remaining) * kill / 100, 2)
    late_per_month = {r["name"]: round(r["amount"] * late / 100, 2) for r in rows if r["amount"]}
    end = max(dates.parse_date(r["due_date"]) for r in rows)
    return {
        "total_fee": round(fee, 2),
        "currency": cur,
        "schedule": rows,
        "allocated": round(alloc, 2),
        "unallocated": diff,
        "cash_before_final_delivery_pct": round(100 * (fee - last["amount"]) / fee, 1),
        "late_fee_per_month_by_invoice": late_per_month,
        "late_fee_daily_rate_pct": round(late / 30, 4),
        "kill_fee_pct_of_remaining": kill,
        "last_payment_due": end.isoformat(),
        "flags": flags,
        "clause": (f"Fees: {cur}{fee:,.2f} total. A non-refundable deposit of {dep:g}% ({cur}{dep_amt:,.2f}) is due on signature; remaining amounts are invoiced on acceptance of each milestone and due within {payment_terms_days} days. "
                   f"Overdue amounts accrue interest at {late:g}% per month (or the maximum permitted by law). Work pauses while any invoice is more than 10 days overdue. "
                   f"If the Client cancels, the Client pays for work completed plus a cancellation fee of {kill:g}% of the remaining balance."),
        "verdict": f"{len(rows)} payment(s); {round(100 * (fee - last['amount']) / fee)}% of cash arrives before final delivery" + (f"; {len(flags)} flag(s)" if flags else " — healthy schedule"),
        "scope_note": SCOPE_NOTE,
    }


SCOPE_FLAGS: list[tuple[str, int, str, str]] = [
    (r"unlimited (?:revisions|rounds|changes|edits|iterations)|revisions? until (?:you|the client|they)(?: are| is)? (?:happy|satisfied)|as many (?:revisions|changes) as", 3, "unlimited revisions", "Two rounds of revisions per deliverable are included; a round is one consolidated set of written feedback. Further rounds at $[rate]/hour or a quoted fixed fee."),
    (r"to (?:the )?(?:client'?s?|customer'?s?|your) (?:complete |full |reasonable )?satisfaction|until (?:the )?client (?:is )?satisfied|(?:sole|absolute) (?:discretion|judgment) of the client", 3, "subjective acceptance standard", "Deliverables are accepted when they materially conform to the specifications in this SOW. Client will review within 5 business days and provide written acceptance or a consolidated list of non-conformities; silence is acceptance."),
    (r"\betc\.?\b|and (?:so on|the like|similar)|and (?:related|other|any other|additional|associated) (?:tasks|work|services|items|deliverables|duties)|as (?:needed|required|requested|necessary)|ongoing (?:support|maintenance)(?! .{0,40}(?:hours|retainer|\$))", 2, "open-ended scope language", "Replace with a closed list of deliverables. Add: 'Anything not listed above is out of scope and will be quoted separately.'"),
    (r"any (?:changes|modifications|revisions) (?:requested|required) by (?:the )?client (?:shall|will) be (?:made|included|performed)(?! .{0,60}(?:change order|additional fee|quoted|at the rate))", 2, "client changes included at no charge", "Changes to the scope, specifications or timeline require a written change order stating the fee and schedule impact, agreed before work starts."),
    (r"(?:reasonable|minor) (?:additional )?(?:changes|requests|tasks) (?:at no|without) (?:additional |extra )?(?:charge|cost)", 2, "'reasonable changes free' — undefined", "Define the included revision rounds instead; 'reasonable' is decided by the client."),
    (r"available (?:at all times|24/7|on demand|whenever)|respond (?:immediately|within (?:the )?(?:hour|1 hour|2 hours))", 1, "availability / response-time promise", "Freelancer will respond to Client communications within 1 business day during business hours."),
    (r"time is of the essence", 1, "'time is of the essence' — turns any delay into a breach", "Delete, or make delivery dates dependent on Client meeting its dependencies (content, feedback, approvals)."),
]
SCOPE_REQUIRED: list[tuple[str, str, int, str]] = [
    ("deliverables_list", r"deliverables?|will (?:deliver|provide|produce)|scope of work", 3, "Add a numbered deliverables list with format, quantity and acceptance criteria."),
    ("exclusions", r"not include|excluded|out of scope|does not include|exclusions?|outside (?:the |of )?scope", 3, "Add an explicit exclusions list — the strongest scope-creep defence."),
    ("revision_cap", r"\d+ (?:\(\d+\) )?(?:rounds?|revisions?|iterations?)|(?:one|two|three) (?:rounds?|revisions?)|revision rounds?", 3, "Add: '2 rounds of revisions per deliverable included; additional rounds at $X/hour.'"),
    ("change_order", r"change (?:order|request)s?|scope change|changes? (?:to|in) (?:the )?scope .{0,60}(?:written|agreed|quoted|fee)", 3, "Add a change-order clause: changes are quoted in writing and agreed before work starts."),
    ("acceptance_window", r"(?:within|after) \d+ (?:business |working )?days .{0,60}(?:accept|approv|review|feedback)|deemed accepted|acceptance (?:period|window)", 2, "Add: 'Client reviews within 5 business days; no written objection = accepted.'"),
    ("client_dependencies", r"client (?:will|shall|must) (?:provide|supply|deliver)|client(?:'s)? (?:responsibilities|obligations|dependencies)|depends? on (?:the )?client|materials? (?:from|provided by) (?:the )?client", 2, "Add client dependencies (content, access, feedback SLA) and state that delays shift the schedule day-for-day."),
    ("dates", r"\d{4}-\d{2}-\d{2}|(?:january|february|march|april|may|june|july|august|september|october|november|december) \d{1,2}|within \d+ (?:days|weeks)|by (?:week|day) \d+", 1, "Add delivery dates or durations for each deliverable."),
    ("assumptions", r"assum(?:es|ptions?)|based on|provided that|subject to", 1, "Add assumptions (e.g. 'up to 5 pages', 'one language', 'client supplies copy')."),
]


@AGENT.tool
def scope_creep_check(sow_text: str) -> dict:
    """Score a statement of work 0-100 for scope-creep exposure: open-ended language, missing exclusions/revision cap/change orders, subjective acceptance.

    Args:
        sow_text: The scope / statement-of-work text (or the whole contract).
    """
    text = check_text(sow_text, "sow_text")
    findings, score = [], 100
    for rx, sev, label, fix in SCOPE_FLAGS:
        m = re.search(rx, text, re.I | re.S)
        if m:
            findings.append({"type": "risky language", "severity": sev, "issue": label, "excerpt": excerpt(text, m, 140), "use_instead": fix})
            score -= {1: 5, 2: 10, 3: 18}[sev]
    for key, rx, sev, fix in SCOPE_REQUIRED:
        if not re.search(rx, text, re.I | re.S):
            findings.append({"type": "missing", "severity": sev, "issue": key.replace("_", " "), "excerpt": None, "use_instead": fix})
            score -= {1: 4, 2: 8, 3: 12}[sev]
    deliverable_lines = len(re.findall(r"(?m)^\s*(?:[-*•]|\d+[.)])\s+.{8,}", text))
    numbers = len(re.findall(r"\b\d+\b", text))
    if deliverable_lines == 0:
        findings.append({"type": "structure", "severity": 1, "issue": "no bulleted/numbered deliverables", "excerpt": None, "use_instead": "List deliverables one per line with a count and format."})
        score -= 4
    if numbers < 3:
        findings.append({"type": "structure", "severity": 1, "issue": "almost no numbers (quantities, rounds, days)", "excerpt": None, "use_instead": "Quantify: pages, screens, words, rounds, business days."})
        score -= 4
    findings.sort(key=lambda f: -f["severity"])
    score = max(0, score)
    return {
        "score": score,
        "findings": findings,
        "risky_language": [f["issue"] for f in findings if f["type"] == "risky language"],
        "missing": [f["issue"] for f in findings if f["type"] == "missing"],
        "deliverable_lines": deliverable_lines,
        "verdict": "Tight scope" if score >= 80 else "Some openings — fix the top findings" if score >= 55 else "Scope-creep magnet — rewrite with exclusions, revision cap and change orders",
        "scope_note": SCOPE_NOTE,
    }


CONTRACT_CLAUSES: list[dict] = [
    {"key": "payment_terms", "label": "Payment terms (net days)", "rx": r"net (?:\d{1,3}|fifteen|thirty|sixty)|within (?:\d+|[a-z]+(?:-[a-z]+)?) (?:\(\d+\) )?(?:calendar |business )?days (?:of|after|from) (?:the )?(?:date of )?(?:invoice|receipt|receiving)|due (?:upon|on) receipt|payable within|(?:pay|paid|payable)[^.]{0,40}within (?:\d+|[a-z]+) (?:\(\d+\) )?days", "freelancer": 3, "client": 1, "language": "Invoices are due within 15 days of the invoice date."},
    {"key": "deposit", "label": "Deposit / upfront payment", "rx": r"deposit|upfront|up-front|advance payment|retainer|prior to (?:commencement|starting|the start)", "freelancer": 3, "client": 0, "language": "A non-refundable deposit of 40% is due on signature; work begins when it is received."},
    {"key": "late_fee", "label": "Late fee / interest / pause right", "rx": r"late (?:fee|charge|payment)|interest .{0,30}(?:per (?:month|annum)|%)|overdue|suspend (?:work|services) .{0,40}(?:unpaid|overdue)", "freelancer": 3, "client": 0, "language": "Overdue amounts accrue 1.5% per month; Freelancer may pause work while any invoice is more than 10 days overdue."},
    {"key": "kill_fee", "label": "Kill fee / early termination payment", "rx": r"kill fee|cancellation fee|early termination fee|terminat\w+ .{0,80}(?:pay(?:ment)? for (?:all )?work (?:performed|completed|done)|work to date|pro[- ]?rata)", "freelancer": 3, "client": 1, "language": "If Client terminates for convenience, Client pays for all work performed to date plus 25% of the remaining fee."},
    {"key": "ip_on_payment", "label": "IP transfers only on full payment", "rx": r"(?:upon|on|subject to|conditioned (?:up)?on|following) (?:receipt of )?(?:full|final) payment .{0,120}(?:assign|transfer|own|vest)|(?:assign|transfer|vest)\w* .{0,120}(?:upon|on|subject to|following) (?:receipt of )?(?:full|final) payment", "freelancer": 3, "client": 0, "language": "Upon receipt of full payment, Freelancer assigns to Client all rights in the final Deliverables. Until then, Freelancer retains all rights and Client has a revocable licence to review the work."},
    {"key": "preexisting_ip", "label": "Pre-existing IP / tools retained with licence-back", "rx": r"pre-?existing|background (?:ip|intellectual property|technology)|freelancer'?s? (?:tools|templates|libraries|know-?how)|retains? (?:all )?(?:rights|ownership) (?:in|to) .{0,40}(?:tools|materials|templates)", "freelancer": 2, "client": 1, "language": "Freelancer retains ownership of pre-existing materials, tools and generic components; Client receives a perpetual, non-exclusive licence to use them as incorporated in the Deliverables."},
    {"key": "portfolio", "label": "Portfolio / credit rights", "rx": r"portfolio|self-?promotion|display .{0,40}(?:work|deliverables)|credit(?:ed)? (?:as|for) .{0,30}(?:author|designer|developer|creator)|showcase", "freelancer": 2, "client": 0, "language": "Freelancer may display the Deliverables in its portfolio and identify Client as a client, after public launch or with Client's consent."},
    {"key": "revisions", "label": "Revision rounds defined", "rx": r"\d+ (?:\(\d+\) )?(?:rounds?|revisions?)|(?:one|two|three) (?:rounds?|revisions?)|revision rounds?", "freelancer": 3, "client": 2, "language": "Two rounds of revisions per deliverable are included; additional rounds are billed at $X/hour."},
    {"key": "change_orders", "label": "Change orders", "rx": r"change (?:order|request)s?|out[- ]of[- ]scope .{0,40}(?:quoted|billed|additional)|additional (?:work|services) .{0,60}(?:quoted|written|agreed|rate)", "freelancer": 3, "client": 2, "language": "Work outside the SOW requires a written change order with agreed fee and schedule impact before it starts."},
    {"key": "acceptance", "label": "Acceptance procedure with deemed acceptance", "rx": r"deemed accepted|acceptance (?:period|window|criteria|procedure)|within \d+ (?:business )?days .{0,60}(?:accept|approv|reject)", "freelancer": 2, "client": 2, "language": "Client reviews each deliverable within 5 business days and either accepts in writing or lists specific non-conformities; otherwise it is deemed accepted."},
    {"key": "client_dependencies", "label": "Client dependencies and delay consequences", "rx": r"client (?:will|shall|must) (?:provide|supply|deliver|make available)|client(?:'s)? (?:responsibilities|obligations|dependencies)|delay(?:s|ed)? (?:caused )?by (?:the )?client", "freelancer": 2, "client": 1, "language": "Client will provide content, access and feedback within 5 business days of request; delays extend the schedule day-for-day."},
    {"key": "termination", "label": "Termination on notice", "rx": r"terminat\w+ .{0,60}(?:notice|written)|either party may terminate", "freelancer": 2, "client": 2, "language": "Either party may terminate on 14 days' written notice; Client pays for work performed to the termination date."},
    {"key": "contractor_status", "label": "Independent contractor status", "rx": r"independent contractor|not an employee|no employment relationship|own (?:tools|equipment|hours)|responsible for (?:its|their|his|her) own taxes", "freelancer": 2, "client": 3, "language": "Freelancer is an independent contractor, controls how and when the work is done, uses its own equipment, may work for others, and is responsible for its own taxes and insurance."},
    {"key": "confidentiality", "label": "Confidentiality (mutual)", "rx": r"confidential", "freelancer": 1, "client": 2, "language": "Each party keeps the other's non-public information confidential and uses it only for this project, for 2 years after completion."},
    {"key": "liability_cap", "label": "Liability cap", "rx": r"limitation of liability|liability .{0,40}(?:shall not|will not) exceed|aggregate liability|in no event .{0,40}liable", "freelancer": 3, "client": 1, "language": "Each party's total liability under this agreement is limited to the fees paid or payable under the SOW; neither party is liable for indirect or consequential damages."},
    {"key": "governing_law", "label": "Governing law", "rx": r"governed by|governing law|laws of (?:the )?(?:state|commonwealth|province)|jurisdiction", "freelancer": 1, "client": 1, "language": "This agreement is governed by the laws of [Freelancer's state/country]."},
    {"key": "expenses", "label": "Expenses", "rx": r"expenses?|reimburs|out[- ]of[- ]pocket|stock (?:photos?|images?)|fonts?|licen[cs]e fees", "freelancer": 1, "client": 1, "language": "Pre-approved third-party costs (stock assets, fonts, hosting, travel) are reimbursed at cost plus 10% within 15 days."},
    {"key": "dispute", "label": "Dispute resolution", "rx": r"dispute|mediation|arbitration|good[- ]faith negotiation", "freelancer": 1, "client": 1, "language": "The parties will attempt to resolve disputes by good-faith negotiation for 30 days before any proceeding; the prevailing party recovers reasonable legal fees."},
]
CONTRACT_TRAPS: list[dict] = [
    {"rx": r"work (?:made )?for hire(?!.{0,200}(?:upon|on|subject to) (?:receipt of )?(?:full|final) payment)", "freelancer": 3, "client": 0, "flag": "Work-for-hire / assignment not conditioned on payment", "fix": "Condition the assignment on receipt of full payment; before that Client has a revocable review licence."},
    {"rx": r"(?:all|any) (?:ideas|concepts|inventions|works?|materials?) (?:conceived|created|developed|made) .{0,60}(?:during the term|in connection with|in the course of)(?!.{0,80}(?:deliverables|specifically for))", "freelancer": 3, "client": 0, "flag": "Assignment of everything created during the term (not just deliverables)", "fix": "Limit the assignment to the final Deliverables identified in the SOW; carve out pre-existing and general-purpose materials."},
    {"rx": r"unlimited (?:revisions|rounds|changes)|until (?:the )?client (?:is )?satisfied|to the client'?s? satisfaction", "freelancer": 3, "client": 0, "flag": "Unlimited revisions / subjective acceptance", "fix": "Two revision rounds; objective acceptance criteria; 5-business-day review window."},
    {"rx": r"non-?compet\w*|shall not .{0,60}(?:provide services to|work for|engage with) .{0,40}(?:competitor|competing|similar)|\bexclusivity\b|exclusive(?:ly)? (?:for|to) (?:the )?client|exclusive (?:basis|services|provider|relationship|engagement)|(?:work|provide services) exclusively", "freelancer": 3, "client": 0, "flag": "Non-compete / exclusivity", "fix": "Delete. Offer instead: 'Freelancer will not use Client's confidential information for any other client' and a narrow conflict-of-interest disclosure."},
    {"rx": r"pay(?:ment)?[- ]when[- ]paid|paid only (?:when|if|after) .{0,40}(?:client|customer) (?:receives|is paid)", "freelancer": 3, "client": 0, "flag": "Pay-when-paid", "fix": "Delete; payment is due on the invoice terms regardless of Client's customers."},
    {"rx": r"net (?:sixty|ninety|60|90|120)|within (?:sixty|ninety|60|90|120)\s*(?:\(\d+\)\s*)?days", "freelancer": 2, "client": 0, "flag": "Payment terms of net 60 or longer", "fix": "Net 15 (fallback net 30) with a 1.5%/month late fee."},
    {"rx": r"(?:freelancer|contractor|consultant|developer|designer) (?:shall|agrees to|will) (?:defend,? )?indemnif(?!.{0,300}(?:client|company) (?:shall|agrees to|will) (?:defend,? )?indemnif)", "freelancer": 3, "client": 0, "flag": "One-way indemnity from the freelancer", "fix": "Mutual indemnity limited to third-party claims caused by each party's own breach or IP infringement, capped at fees paid."},
    {"rx": r"waive[sd]? .{0,40}moral rights|moral rights .{0,40}waive", "freelancer": 1, "client": 0, "flag": "Moral rights waiver", "fix": "Acceptable in many commercial deals; ask for credit/portfolio rights in exchange."},
    {"rx": r"(?:sole|absolute) discretion", "freelancer": 2, "client": 1, "flag": "'Sole discretion' standard for the other side", "fix": "'reasonable discretion' or objective criteria."},
    {"rx": r"terminat\w+ .{0,40}(?:immediately|at any time|without (?:cause|notice))(?!.{0,120}(?:pay(?:ment)? for (?:all )?work|work performed|to date))", "freelancer": 2, "client": 0, "flag": "Client can terminate at any time with no payment for work done", "fix": "Termination on 14 days' notice with payment for work performed plus a kill fee."},
    {"rx": r"(?:set[- ]?off|withhold(?:ing)? payment|deduct(?:ion)? from (?:any )?(?:fees|payments?))", "freelancer": 2, "client": 0, "flag": "Client may withhold / set off payments", "fix": "Delete, or limit to disputed amounts on undisputed invoices paid in full."},
    {"rx": r"(?:must|shall) (?:work|be available|perform (?:the )?services) (?:from|at|on) (?:client'?s? )?(?:premises|office|\d{1,2}(?::\d{2})?\s?(?:am|pm) (?:to|-) \d)|fixed (?:hours|schedule)|report(?:s|ing)? to (?:a )?(?:manager|supervisor)", "freelancer": 2, "client": 3, "flag": "Employee-like control (fixed hours, supervision) — misclassification risk", "fix": "Freelancer controls schedule and location; deliverables and deadlines define the work, not hours."},
]


@AGENT.tool
def check_contract_clauses(contract_text: str, my_role: str = "freelancer") -> dict:
    """Audit a freelance/contractor agreement for 18 protective clauses and 12 traps, from the freelancer's or client's side, with replacement language.

    Args:
        contract_text: The full agreement (and SOW) text; up to 300k chars.
        my_role: "freelancer" (default) or "client".
    """
    text = check_text(contract_text, "contract_text")
    role = str(my_role).strip().lower()
    role = {"contractor": "freelancer", "consultant": "freelancer", "customer": "client", "company": "client"}.get(role, role)
    if role not in {"freelancer", "client"}:
        raise ToolError("my_role must be 'freelancer' or 'client'.")
    present, missing, score = [], [], 0
    for c in CONTRACT_CLAUSES:
        m = re.search(c["rx"], text, re.I | re.S)
        if m:
            present.append({"clause": c["label"], "excerpt": excerpt(text, m, 140)})
        else:
            sev = c[role]
            if sev:
                missing.append({"severity": sev, "clause": c["label"], "use_this_language": c["language"]})
                score += {1: 3, 2: 6, 3: 10}[sev]
    traps = []
    for t in CONTRACT_TRAPS:
        sev = t[role]
        if not sev:
            continue
        m = re.search(t["rx"], text, re.I | re.S)
        if m:
            traps.append({"severity": sev, "flag": t["flag"], "excerpt": excerpt(text, m, 160), "fix": t["fix"]})
            score += {1: 4, 2: 8, 3: 15}[sev]
    missing.sort(key=lambda x: -x["severity"])
    traps.sort(key=lambda x: -x["severity"])
    score = min(100, score)
    return {
        "role": role,
        "present": present,
        "missing": missing,
        "traps": traps,
        "clauses_present": len(present),
        "clauses_total": len(CONTRACT_CLAUSES),
        "risk_score": score,
        "deal_breakers": [t["flag"] for t in traps if t["severity"] == 3] + [m["clause"] for m in missing if m["severity"] == 3][:5],
        "verdict": "Sign — solid agreement" if score < 15 else "Negotiate the flagged items" if score < 40 else "Do not sign as-is — add the missing protections first",
        "redlines": [f"Add {m['clause']}: \"{m['use_this_language']}\"" for m in missing[:6]] + [f"Change '{t['flag']}': {t['fix']}" for t in traps[:6]],
        "scope_note": SCOPE_NOTE,
    }


@AGENT.tool
def rate_calculator(target_income: float, billable_hours_per_week: float = 25, weeks_off: int = 6, annual_overhead: float = 8000, self_employment_tax_pct: float = 15.3, benefits_pct: float = 10, profit_margin_pct: float = 10, fixed_fee: float = 0, estimated_hours: float = 0, contingency_pct: float = 20) -> dict:
    """Compute the minimum hourly and day rate from an income goal, overhead, taxes and real billable hours; evaluate a fixed fee.

    Args:
        target_income: Net income you want to take home per year (before income tax, after business costs).
        billable_hours_per_week: Hours you can actually bill per week (25 is typical; admin/sales eat the rest).
        weeks_off: Weeks per year not working (holiday, sick, slow periods; 4-8 typical).
        annual_overhead: Software, equipment, insurance, accounting, workspace, marketing per year.
        self_employment_tax_pct: Payroll/self-employment tax you bear as a freelancer (US default 15.3%; adjust for your country).
        benefits_pct: Allowance for health, retirement, etc. as % of income (default 10).
        profit_margin_pct: Margin for reinvestment/risk on top of costs (default 10).
        fixed_fee: Optional fixed project fee to evaluate against your rate.
        estimated_hours: Your best estimate of hours for that fixed-fee project.
        contingency_pct: Buffer to add to the hour estimate for unknowns (default 20%).
    """
    income = to_float(target_income, "target_income", 1)
    bhw = to_float(billable_hours_per_week, "billable_hours_per_week", 1, 80)
    if not isinstance(weeks_off, int) or not 0 <= weeks_off <= 30:
        raise ToolError("weeks_off must be an integer between 0 and 30.")
    overhead = to_float(annual_overhead, "annual_overhead", 0)
    se_tax = to_float(self_employment_tax_pct, "self_employment_tax_pct", 0, 60) / 100
    benefits = to_float(benefits_pct, "benefits_pct", 0, 60) / 100
    margin = to_float(profit_margin_pct, "profit_margin_pct", 0, 80) / 100
    cont = to_float(contingency_pct, "contingency_pct", 0, 100) / 100
    weeks = 52 - weeks_off
    billable_hours = weeks * bhw
    gross_needed = income * (1 + se_tax + benefits) + overhead
    with_margin = gross_needed * (1 + margin)
    hourly = with_margin / billable_hours
    hourly_rounded = float(int(hourly / 5 + 0.999) * 5)
    day = hourly_rounded * 8
    week = hourly_rounded * bhw
    out = {
        "billable_weeks": weeks,
        "billable_hours_per_year": round(billable_hours),
        "annual_revenue_needed": round(with_margin),
        "breakdown": {"target_income": income, "self_employment_tax": round(income * se_tax), "benefits": round(income * benefits), "overhead": overhead, "profit_margin": round(gross_needed * margin)},
        "minimum_hourly": round(hourly, 2),
        "hourly_rate_rounded": hourly_rounded,
        "day_rate": day,
        "weekly_retainer": round(week),
        "note": "Quote 10-20% above the minimum; the minimum leaves no room for discounts or unbilled scope.",
        "scope_note": SCOPE_NOTE,
    }
    if fixed_fee or estimated_hours:
        ff = to_float(fixed_fee, "fixed_fee", 0)
        hrs = to_float(estimated_hours, "estimated_hours", 0)
        if ff <= 0 or hrs <= 0:
            raise ToolError("To evaluate a fixed fee, give both fixed_fee and estimated_hours > 0.")
        hrs_buffered = hrs * (1 + cont)
        effective = ff / hrs_buffered
        recommended = round(hrs_buffered * hourly_rounded)
        out["fixed_fee_check"] = {
            "fixed_fee": ff,
            "estimated_hours": hrs,
            "hours_with_contingency": round(hrs_buffered, 1),
            "effective_hourly_rate": round(effective, 2),
            "vs_minimum_pct": round(100 * (effective / hourly - 1), 1),
            "recommended_fixed_fee": recommended,
            "break_even_hours": round(ff / hourly_rounded, 1),
            "verdict": ("Fee covers your rate" if effective >= hourly else f"Underpriced by {money(recommended - ff)} — quote {money(recommended)} or cut scope"),
        }
    out["verdict"] = f"Minimum {money(hourly)}/hr → quote {money(hourly_rounded)}/hr ({money(day)}/day) on {round(billable_hours)} billable hours" + (f"; fixed fee: {out['fixed_fee_check']['verdict']}" if "fixed_fee_check" in out else "")
    return out
