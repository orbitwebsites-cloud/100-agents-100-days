"""Budget Coach — a personal-finance plan with exact debt payoff math, not vibes."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from ...core import Agent, ToolError
from ._common import (
    CENT,
    MAX_MONTHS,
    ZERO,
    D,
    add_months,
    amortize,
    as_rate,
    bound_rows,
    money,
    monthly_payment,
    month_label,
    parse_iso,
    ratio_to_pct,
    require_nonneg,
    require_positive,
)

AGENT = Agent(
    slug="budget-coach",
    name="Budget Coach",
    category="finance",
    tagline="A 50/30/20 budget, a debt payoff plan with exact interest math, and a savings runway you can actually follow.",
    description=(
        "Builds a personal budget the way a fee-only financial planner would: classifies every expense "
        "into needs/wants/savings against 50/30/20 targets, simulates debt payoff month by month "
        "(snowball vs avalanche, with the real interest cost of each), sizes the emergency fund, computes "
        "amortised loan payments and affordability ratios (28/36 rule), and turns it into a one-page "
        "plan with dates. Every number comes from exact monthly-compounding math, never estimates."
    ),
    triggers=[
        "help me make a budget / 50/30/20 plan",
        "should I pay off debt with snowball or avalanche",
        "how long to pay off my credit cards / student loans",
        "can I afford this car / house / rent",
        "how much should my emergency fund be and how long to save it",
        "what is the monthly payment on a loan",
    ],
    examples=[
        "I take home $5,200/month. Rent $1,800, car $420, groceries $600, eating out $450, subscriptions $90, savings $200. Fix my budget.",
        "I have three cards: $4,200 at 24.99% (min $120), $1,100 at 19.9% (min $35), $8,500 at 17% (min $210). I can put $700/month total. Snowball or avalanche?",
        "Can I afford a $2,400/month mortgage on $9,000 gross with a $450 car payment and $300 in student loans?",
    ],
    connectors=["Google Sheets", "Notion", "YNAB", "Plaid"],
    playbook="""
    ## Standard
    You are a fee-only certified financial planner running a first-session budget review. Excellent
    means: the client leaves with one page that says exactly where each dollar goes next month, the
    one debt to attack first with the date it dies, and a savings number with a deadline. The metric
    that matters is **months to financial slack**: how many months until the emergency fund is funded
    and the highest-rate debt is gone. Not financial advice for legal purposes; flag a licensed advisor
    for tax, investment allocation, or bankruptcy questions.

    ## Intake
    You need: monthly take-home pay (after tax), every recurring expense with an amount, every debt
    (balance, APR, minimum payment), and current savings. Ask at most 3 questions and only if a number
    is missing that blocks the math (e.g. no take-home pay). If APRs are unknown, assume 22% for credit
    cards, 7% for auto, 6.5% for student loans, and say so. Never ask for account numbers or logins.

    ## Procedure
    1. **Classify and score the budget.** Sort every expense into `needs` (rent/mortgage, utilities,
       groceries, insurance, minimum debt payments, transport to work), `wants` (dining out,
       subscriptions, hobbies, upgrades) or `savings` (emergency fund, retirement, extra debt payments).
       Call `budget_coach__budget_50_30_20` with take-home pay and the classified list. It returns
       actual vs target for each bucket, the surplus/deficit, the savings rate and the three largest
       wants. Use its `gap` numbers verbatim.
    2. **Size the emergency fund.** Essentials = the `needs` total from step 1. Call
       `budget_coach__savings_goal` with target = 3× essentials (single income, stable job) or 6×
       (variable income, dependents, one earner), current savings and the monthly contribution the
       budget allows. It returns the funded date with compounding. Starter goal: $1,000 first, always.
    3. **Simulate the debt plan.** Call `budget_coach__debt_payoff` twice: once with
       `method="avalanche"` and once with `method="snowball"`, same `extra_monthly`. Compare
       `total_interest` and `months_to_debt_free`. Recommend avalanche unless the snowball is within
       10% of the interest cost or the client has said motivation is the problem — then snowball, and
       say what it costs. If the tool returns `pays_off: false`, that is the headline: the minimums do
       not cover interest, and the plan must free cash first.
    4. **Test any big purchase.** For a house, car or new loan, call `budget_coach__debt_to_income`
       with gross monthly income, housing payment and all debt payments. Front-end > 28% or back-end
       > 36% means "not yet" with the exact dollar amount to cut or earn. For the payment itself, call
       `budget_coach__loan_payment` — never compute an amortised payment in your head, and show the
       interest saved by any extra principal payment the budget can support.
    5. **Order the moves.** Sequence is fixed unless the client overrides it: (a) $1,000 starter fund,
       (b) employer retirement match if any (free money beats 24% interest), (c) debts above ~7% APR,
       (d) full emergency fund, (e) debts below 7% alongside investing.
    6. **Write the plan** in the output format. Every line has a dollar amount and a date.

    ## Frameworks
    - **50/30/20** (Warren, *All Your Worth*): needs ≤ 50%, wants ≤ 30%, savings + extra debt ≥ 20%
      of take-home. High-cost-of-living variant: 60/20/20 — say which you are using.
    - **Avalanche vs snowball**: avalanche (highest APR first) minimises interest; snowball (smallest
      balance first) maximises early wins. The difference is usually small when balances are similar.
    - **28/36 rule**: housing ≤ 28% of gross, all debt ≤ 36% of gross. Lenders stretch to 43%; you
      should not plan on it.
    - **Emergency fund**: 3 months of *essentials* (not income) as baseline, 6 for variable income.
    - **Savings rate benchmarks**: 10% is the floor, 15% including employer match for retirement
      on track, 20%+ is the 50/30/20 target.

    ## Output format
    ```
    # Budget plan — <Month YYYY>
    **Take-home:** $X · **Needs:** $A (a% vs 50%) · **Wants:** $B (b% vs 30%) · **Savings/debt:** $C (c% vs 20%)
    **Verdict:** <one sentence: surplus/deficit and the single biggest lever>

    ## Cuts (ranked by dollars freed)
    | Line item | Now | Target | Freed/month |

    ## Debt plan — <avalanche|snowball>
    Extra payment: $X/month → debt-free <YYYY-MM>, total interest $Y (vs $Z paying minimums)
    | # | Debt | Balance | APR | Paid off |

    ## Savings
    Emergency fund target $X (N months of essentials) → funded <YYYY-MM> at $Y/month

    ## Next 30 days
    1. <action with amount and date>
    ```

    ## Anti-patterns
    - Classifying minimum debt payments as "savings". They are needs; only *extra* payments count.
    - Quoting a payoff date without running `budget_coach__debt_payoff`. Interest compounds monthly and
      rollover changes everything — mental math is always wrong here.
    - Telling someone to cut coffee when rent is 45% of take-home. Attack the biggest line first.
    - Recommending snowball silently. Always show what the motivational path costs in dollars.
    - Building a budget that sums to more than 100% of income and calling it "aspirational".
    """,
)

BUCKETS = ("needs", "wants", "savings")
DEFAULT_TARGETS = {"needs": Decimal("50"), "wants": Decimal("30"), "savings": Decimal("20")}


@AGENT.tool
def budget_50_30_20(take_home_monthly: float, expenses: list[dict], targets_pct: dict | None = None) -> dict:
    """Score a monthly budget against 50/30/20 targets and find the surplus, deficit and biggest levers.

    Call after classifying every expense as needs / wants / savings. Returns actual vs target per
    bucket in dollars and percent, the unallocated surplus (or deficit), the savings rate and the
    largest wants to cut first.

    Args:
        take_home_monthly: Monthly after-tax income in dollars.
        expenses: List of {"name": str, "amount": number, "bucket": "needs"|"wants"|"savings"}.
        targets_pct: Optional override like {"needs": 60, "wants": 20, "savings": 20}. Must sum to 100.
    """
    income = require_positive(D(take_home_monthly, "take_home_monthly"), "take_home_monthly")
    rows = bound_rows(expenses, "expenses")
    targets = dict(DEFAULT_TARGETS)
    if targets_pct:
        targets = {b: D(targets_pct.get(b, 0), f"targets_pct.{b}") for b in BUCKETS}
        if sum(targets.values()) != 100:
            raise ToolError("targets_pct must sum to 100")
    totals = {b: ZERO for b in BUCKETS}
    items = []
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ToolError(f"expenses[{i}] must be an object with name, amount, bucket")
        bucket = str(row.get("bucket", "")).strip().lower()
        if bucket not in BUCKETS:
            raise ToolError(f"expenses[{i}] ({row.get('name', '?')}): bucket must be one of {BUCKETS}, got {bucket!r}")
        amount = require_nonneg(D(row.get("amount"), f"expenses[{i}].amount"), f"expenses[{i}].amount")
        totals[bucket] += amount
        items.append({"name": str(row.get("name", f"item {i}")), "amount": money(amount), "bucket": bucket})
    allocated = sum(totals.values())
    surplus = income - allocated
    buckets = {}
    for b in BUCKETS:
        target_amt = income * targets[b] / 100
        buckets[b] = {
            "actual": money(totals[b]),
            "actual_pct": ratio_to_pct(totals[b] / income),
            "target": money(target_amt),
            "target_pct": float(targets[b]),
            "gap": money(totals[b] - target_amt),
            "status": ("over" if totals[b] > target_amt else "under") if b != "savings" else ("short" if totals[b] < target_amt else "on track"),
        }
    wants_sorted = sorted((x for x in items if x["bucket"] == "wants"), key=lambda x: -x["amount"])[:3]
    savings_rate = ratio_to_pct((totals["savings"] + max(surplus, ZERO)) / income)
    if surplus < 0:
        verdict = f"Deficit of ${money(-surplus):,.2f}/month — spending exceeds take-home; cut before anything else."
    elif totals["needs"] > income * targets["needs"] / 100:
        verdict = f"Needs are {buckets['needs']['actual_pct']}% of take-home (target {float(targets['needs'])}%) — a fixed-cost problem; wants cuts alone will not fix it."
    elif totals["wants"] > income * targets["wants"] / 100:
        verdict = f"Wants are over by ${buckets['wants']['gap']:,.2f}/month — that is the lever; redirect it to savings/debt."
    else:
        verdict = f"Budget is within targets with ${money(surplus):,.2f}/month unallocated — assign it explicitly to a goal."
    return {
        "take_home": money(income),
        "allocated": money(allocated),
        "surplus": money(surplus),
        "buckets": buckets,
        "savings_rate_pct": savings_rate,
        "largest_wants": wants_sorted,
        "verdict": verdict,
        "next_step": "Assign every dollar of surplus to the emergency fund or extra debt payment, then run budget_coach__debt_payoff.",
    }


def _simulate(debts: list[dict], extra: Decimal, method: str, start: date) -> dict:
    """Month-by-month rollover simulation. Debts are dicts with Decimal balance/apr/min."""
    state = [dict(d) for d in debts]
    for s in state:
        s["interest_paid"] = ZERO
        s["paid_off_month"] = None
    total_interest = ZERO
    month = 0
    schedule_points = []
    while any(s["balance"] > 0 for s in state) and month < MAX_MONTHS:
        month += 1
        open_debts = [s for s in state if s["balance"] > 0]
        # accrue interest first
        for s in open_debts:
            i = (s["balance"] * s["apr"] / 12).quantize(CENT, rounding=ROUND_HALF_UP)
            s["balance"] += i
            s["interest_paid"] += i
            total_interest += i
        # minimums
        pool = extra if method != "minimum" else ZERO
        for s in open_debts:
            pay = min(s["min"], s["balance"])
            s["balance"] -= pay
            pool += s["min"] - pay  # leftover minimum from a nearly-paid debt rolls forward
        # rollover targets
        if method != "minimum":
            order = sorted(
                (s for s in state if s["balance"] > 0),
                key=(lambda s: s["balance"]) if method == "snowball" else (lambda s: (-s["apr"], s["balance"])),
            )
            for s in order:
                if pool <= 0:
                    break
                pay = min(pool, s["balance"])
                s["balance"] -= pay
                pool -= pay
        for s in state:
            if s["balance"] <= 0 and s["paid_off_month"] is None:
                s["paid_off_month"] = month
        if month <= 24 or month % 12 == 0:
            schedule_points.append({"month": month, "date": month_label(add_months(start, month)), "total_balance": money(sum(s["balance"] for s in state))})
    pays_off = all(s["balance"] <= 0 for s in state)
    return {
        "pays_off": pays_off,
        "months": month if pays_off else None,
        "total_interest": money(total_interest),
        "debts": [
            {
                "name": s["name"],
                "paid_off_month": s["paid_off_month"],
                "paid_off_date": month_label(add_months(start, s["paid_off_month"])) if s["paid_off_month"] else None,
                "interest_paid": money(s["interest_paid"]),
                "remaining_balance": money(s["balance"]),
            }
            for s in state
        ],
        "balance_curve": schedule_points,
    }


@AGENT.tool
def debt_payoff(
    debts: list[dict],
    extra_monthly: float = 0,
    method: Literal["avalanche", "snowball", "minimum"] = "avalanche",
    start_date: str = "",
) -> dict:
    """Simulate debt payoff month by month with rollover, returning payoff dates and total interest.

    Handles the case where minimums do not cover interest (never pays off). Compares against
    paying minimums only so you can quote interest saved. Monthly compounding, half-up rounding.

    Args:
        debts: List of {"name": str, "balance": number, "apr": percent like 24.99, "min_payment": number}.
        extra_monthly: Extra dollars per month on top of all minimums, applied to the target debt.
        method: "avalanche" (highest APR first), "snowball" (smallest balance first) or "minimum" (no extra, no rollover).
        start_date: YYYY-MM-DD of the first payment. Defaults to today.
    """
    rows = bound_rows(debts, "debts", limit=50)
    extra = require_nonneg(D(extra_monthly, "extra_monthly"), "extra_monthly")
    start = parse_iso(start_date, "start_date") if start_date else date.today()
    parsed = []
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ToolError(f"debts[{i}] must be an object")
        bal = require_positive(D(row.get("balance"), f"debts[{i}].balance"), f"debts[{i}].balance")
        apr = as_rate(row.get("apr", 0), f"debts[{i}].apr")
        if apr < 0 or apr > 2:
            raise ToolError(f"debts[{i}].apr looks wrong ({row.get('apr')}); give a percent like 24.99")
        mn = require_nonneg(D(row.get("min_payment", 0), f"debts[{i}].min_payment"), f"debts[{i}].min_payment")
        parsed.append({"name": str(row.get("name") or f"debt {i}"), "balance": bal, "apr": apr, "min": mn})
    first_interest = sum((d["balance"] * d["apr"] / 12) for d in parsed)
    total_payment = sum(d["min"] for d in parsed) + extra
    if total_payment <= first_interest:
        shortfall = first_interest - total_payment + CENT
        return {
            "method": method,
            "pays_off": False,
            "months_to_debt_free": None,
            "monthly_payment_total": money(total_payment),
            "monthly_interest_now": money(first_interest),
            "min_extra_to_progress": money(shortfall),
            "verdict": (
                f"Never pays off: ${money(total_payment):,.2f}/month does not cover ${money(first_interest):,.2f} of monthly interest. "
                f"Free at least ${money(shortfall):,.2f}/month more before any plan works."
            ),
        }
    result = _simulate(parsed, extra, method, start)
    baseline = _simulate(parsed, ZERO, "minimum", start)
    order = sorted(parsed, key=(lambda s: s["balance"]) if method == "snowball" else (lambda s: (-s["apr"], s["balance"])))
    interest_saved = (Decimal(str(baseline["total_interest"])) - Decimal(str(result["total_interest"]))) if baseline["pays_off"] else None
    months = result["months"]
    verdict = (
        f"{method.title()}: debt-free in {months} months ({month_label(add_months(start, months))}), total interest ${result['total_interest']:,.2f}"
        + (f" — saves ${money(interest_saved):,.2f} vs minimums only ({baseline['months']} months)." if interest_saved is not None else ". Paying minimums only never clears the balance.")
        if result["pays_off"]
        else f"Does not clear within {MAX_MONTHS} months — increase extra_monthly."
    )
    return {
        "method": method,
        "pays_off": result["pays_off"],
        "months_to_debt_free": months,
        "debt_free_date": month_label(add_months(start, months)) if months else None,
        "monthly_payment_total": money(total_payment),
        "total_interest": result["total_interest"],
        "attack_order": [d["name"] for d in order],
        "debts": result["debts"],
        "balance_curve": result["balance_curve"],
        "minimums_only": {"pays_off": baseline["pays_off"], "months": baseline["months"], "total_interest": baseline["total_interest"] if baseline["pays_off"] else None},
        "interest_saved_vs_minimums": money(interest_saved) if interest_saved is not None else None,
        "verdict": verdict,
    }


@AGENT.tool
def loan_payment(principal: float, apr: float, months: int, extra_payment: float = 0) -> dict:
    """Compute the amortised monthly payment and total interest, plus the effect of extra principal.

    Monthly compounding (APR/12), standard annuity formula. With extra_payment it re-runs the
    schedule to show months and interest saved.

    Args:
        principal: Loan amount in dollars.
        apr: Annual percentage rate, e.g. 6.5 for 6.5%.
        months: Term in months (360 for a 30-year mortgage).
        extra_payment: Optional extra dollars paid toward principal every month.
    """
    p = require_positive(D(principal, "principal"), "principal")
    rate = as_rate(apr, "apr")
    if rate < 0 or rate > 1:
        raise ToolError("apr must be a percent between 0 and 100")
    if months < 1 or months > MAX_MONTHS:
        raise ToolError(f"months must be between 1 and {MAX_MONTHS}")
    extra = require_nonneg(D(extra_payment, "extra_payment"), "extra_payment")
    pay = monthly_payment(p, rate, months).quantize(CENT, rounding=ROUND_HALF_UP)
    base = amortize(p, rate, pay, max_months=months + 2)
    total_interest = Decimal(str(base["total_interest"])) if base["pays_off"] else p * rate / 12 * months
    out = {
        "monthly_payment": money(pay),
        "months": months,
        "total_paid": money(pay * base["months"]) if base["pays_off"] else money(pay * months),
        "total_interest": money(total_interest),
        "interest_share_of_payments_pct": ratio_to_pct(total_interest / (pay * months)) if pay else 0.0,
        "first_month_interest": money(p * rate / 12),
        "first_month_principal": money(pay - p * rate / 12),
    }
    if extra > 0:
        acc = amortize(p, rate, pay + extra)
        out["with_extra"] = {
            "payment": money(pay + extra),
            "months": acc["months"],
            "months_saved": months - acc["months"] if acc["months"] else None,
            "total_interest": acc["total_interest"],
            "interest_saved": money(total_interest - Decimal(str(acc["total_interest"]))) if acc["pays_off"] else None,
        }
    out["verdict"] = f"${out['monthly_payment']:,.2f}/month for {months} months; ${out['total_interest']:,.2f} of interest ({out['interest_share_of_payments_pct']}% of every dollar paid)." + (
        f" Adding ${money(extra):,.2f}/month finishes {out['with_extra']['months_saved']} months early and saves ${out['with_extra']['interest_saved']:,.2f}." if extra > 0 and out["with_extra"].get("interest_saved") is not None else ""
    )
    return out


@AGENT.tool
def savings_goal(target: float, current: float = 0, monthly_contribution: float = 0, apy: float = 0, months: int = 0) -> dict:
    """Months to reach a savings target with monthly compounding, or the monthly amount a deadline needs.

    Give monthly_contribution to get the funded date; give months instead to get the required
    contribution. Use for emergency funds, down payments and sinking funds.

    Args:
        target: Goal amount in dollars.
        current: Amount already saved.
        monthly_contribution: Dollars added each month (leave 0 if solving for it).
        apy: Annual yield on the savings, e.g. 4.5 for a high-yield account. 0 for a checking account.
        months: Deadline in months (only when solving for the contribution).
    """
    tgt = require_positive(D(target, "target"), "target")
    cur = require_nonneg(D(current, "current"), "current")
    contrib = require_nonneg(D(monthly_contribution, "monthly_contribution"), "monthly_contribution")
    rate = as_rate(apy, "apy") / 12
    if cur >= tgt:
        return {"already_funded": True, "surplus": money(cur - tgt), "verdict": "Goal already funded — redirect contributions to the next priority."}
    gap = tgt - cur
    if months > 0:
        if months > MAX_MONTHS:
            raise ToolError(f"months must be <= {MAX_MONTHS}")
        if rate == 0:
            needed = (tgt - cur) / months
        else:
            growth = (1 + rate) ** months
            needed = (tgt - cur * growth) * rate / (growth - 1)
        needed = max(needed, ZERO)
        return {
            "solve_for": "monthly_contribution",
            "required_monthly": money(needed),
            "months": months,
            "gap_today": money(gap),
            "interest_earned": money(tgt - cur - needed * months) if needed > 0 else money(tgt - cur * (1 + rate) ** months),
            "verdict": f"Save ${money(needed):,.2f}/month for {months} months to reach ${money(tgt):,.2f}.",
        }
    if contrib <= 0:
        if rate == 0 or cur == 0:
            return {"reachable": False, "gap_today": money(gap), "verdict": "With no contribution and no yield the goal is never reached."}
    bal, n, earned = cur, 0, ZERO
    while bal < tgt and n < MAX_MONTHS:
        interest = (bal * rate).quantize(CENT, rounding=ROUND_HALF_UP)
        bal += interest + contrib
        earned += interest
        n += 1
    if bal < tgt:
        return {"reachable": False, "gap_today": money(gap), "verdict": f"Not reachable within {MAX_MONTHS} months at ${money(contrib):,.2f}/month."}
    funded = add_months(date.today(), n)
    return {
        "solve_for": "months",
        "months": n,
        "funded_by": month_label(funded),
        "gap_today": money(gap),
        "total_contributed": money(contrib * n),
        "interest_earned": money(earned),
        "verdict": f"${money(contrib):,.2f}/month reaches ${money(tgt):,.2f} in {n} months ({month_label(funded)}), earning ${money(earned):,.2f} in interest.",
    }


@AGENT.tool
def debt_to_income(gross_monthly_income: float, housing_payment: float, other_debt_payments: float = 0, proposed_new_payment: float = 0) -> dict:
    """Front-end and back-end debt-to-income ratios against the 28/36 rule, with the dollar gap.

    Use before any "can I afford this" answer. Reports the ratios today and with the proposed
    payment, and the maximum payment that keeps both ratios inside the rule.

    Args:
        gross_monthly_income: Pre-tax monthly income.
        housing_payment: Rent or full mortgage payment (PITI: principal, interest, taxes, insurance, HOA).
        other_debt_payments: Sum of monthly minimums on cars, cards, student loans (not utilities).
        proposed_new_payment: A new monthly payment being considered (added to the back-end ratio; if housing_payment is 0 it is treated as the housing payment).
    """
    income = require_positive(D(gross_monthly_income, "gross_monthly_income"), "gross_monthly_income")
    housing = require_nonneg(D(housing_payment, "housing_payment"), "housing_payment")
    other = require_nonneg(D(other_debt_payments, "other_debt_payments"), "other_debt_payments")
    new = require_nonneg(D(proposed_new_payment, "proposed_new_payment"), "proposed_new_payment")
    if housing == 0 and new > 0:
        housing_after, other_after = new, other
    else:
        housing_after, other_after = housing, other + new
    front_now, back_now = housing / income, (housing + other) / income
    front_after, back_after = housing_after / income, (housing_after + other_after) / income
    max_housing = income * Decimal("0.28")
    max_total = income * Decimal("0.36")
    room_back = max_total - (housing + other)
    room_front = max_housing - housing
    if back_after <= Decimal("0.36") and front_after <= Decimal("0.28"):
        verdict = f"Affordable by the 28/36 rule: front-end {ratio_to_pct(front_after)}%, back-end {ratio_to_pct(back_after)}%."
    elif back_after <= Decimal("0.43"):
        verdict = f"Stretch: back-end {ratio_to_pct(back_after)}% is over 36% (lenders may approve up to 43%). Cut ${money((housing_after + other_after) - max_total):,.2f}/month of payments to fit."
    else:
        verdict = f"Not affordable: back-end {ratio_to_pct(back_after)}% exceeds even the 43% lending ceiling."
    return {
        "front_end_pct": ratio_to_pct(front_now),
        "back_end_pct": ratio_to_pct(back_now),
        "with_proposed": {"front_end_pct": ratio_to_pct(front_after), "back_end_pct": ratio_to_pct(back_after)},
        "limits": {"front_end_pct": 28, "back_end_pct": 36, "lender_ceiling_pct": 43},
        "max_housing_payment": money(max_housing),
        "max_total_debt_payments": money(max_total),
        "room_for_new_payment": money(max(min(room_back, room_front if housing == 0 else room_back), ZERO)),
        "verdict": verdict,
    }
