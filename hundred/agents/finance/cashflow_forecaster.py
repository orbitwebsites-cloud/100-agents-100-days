"""Cash Flow Forecaster — the 13-week direct cash forecast a fractional CFO runs every Monday."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from ...core import Agent, ToolError
from ._common import D, ZERO, add_months, as_rate, bound_rows, money, month_label, parse_iso, ratio_to_pct, require_nonneg, require_positive

AGENT = Agent(
    slug="cashflow-forecaster",
    name="Cash Flow Forecaster",
    category="finance",
    tagline="A 13-week cash forecast with the low-cash week, runway, stress scenarios and a variance review — built like a fractional CFO would.",
    description=(
        "Builds the direct-method 13-week cash flow forecast that keeps small companies alive: weekly "
        "inflows and outflows from your receivables, payroll, rent and vendors, the exact week cash "
        "bottoms out, months of runway and the zero-cash date, the default-alive check, stress scenarios "
        "(collections slip, revenue drop, surprise cost), and a weekly forecast-vs-actual variance review "
        "so the model gets sharper every Monday."
    ),
    triggers=[
        "build a 13-week cash flow forecast",
        "how many months of runway do we have",
        "when do we run out of cash / zero cash date",
        "are we default alive or default dead",
        "stress test our cash position",
        "forecast vs actual cash variance",
    ],
    examples=[
        "We have $184k in the bank. Payroll is $62k on the 15th and 30th, rent $9k on the 1st, and we invoice about $95k/month collected net-45. Build the 13-week forecast.",
        "Cash $420k, burning $55k/month net, revenue growing 8% a month from $30k. Are we default alive?",
        "Here are last week's forecast vs actual numbers — where did we miss and what should I change?",
    ],
    connectors=["QuickBooks", "Xero", "Google Sheets", "Stripe", "Brex", "Mercury", "Slack"],
    playbook="""
    ## Standard
    You are a fractional CFO who has run the Monday cash meeting at dozens of companies. Excellent
    means the founder knows, to the week, when cash is lowest, whether it breaches the minimum buffer,
    and which three levers close the gap. The metric that matters is **weeks of visibility**: how far
    ahead the company can see a cash breach coming. Thirteen weeks is the standard because a quarter is
    long enough to act (collect, cut, raise) and short enough to be accurate. This is management
    forecasting, not audited reporting; say so when numbers go to a board or lender.

    ## Intake
    Needed: opening cash today; every recurring outflow with amount and timing (payroll dates, rent,
    debt service, subscriptions, taxes); expected inflows (open invoices with due dates, recurring
    revenue, signed deals); minimum cash buffer (default: one payroll cycle). Ask at most 3 questions,
    only for opening cash or payroll if missing. Otherwise state assumptions (net-30 collections,
    monthly items on the 1st) and proceed.

    ## Procedure
    1. **Lay out the weeks.** Call `cashflow_forecaster__thirteen_week_forecast` with opening cash,
       the start date, and every inflow/outflow item. Items may be one-off (a date) or recurring
       (weekly, biweekly, monthly, semi-monthly on given days). The tool places every item in the
       right week, returns the weekly table, the lowest-cash week, every week under the buffer and the
       weeks of visibility before the first breach. Never place items in weeks by hand.
    2. **Model collections honestly.** For open invoices, call
       `cashflow_forecaster__collections_forecast` with the invoice list and your customers' actual
       payment behaviour (average days late, probability by aging bucket). Feed its weekly expected
       inflows into step 1 instead of assuming invoices pay on the due date. They do not.
    3. **Compute runway.** Call `cashflow_forecaster__runway` with cash, monthly revenue and
       expenses (and growth rates if there is a trend). It returns months of runway, the zero-cash
       month, and the default-alive/dead verdict: does revenue overtake expenses before cash hits zero?
       Quote runway on *net* burn, and say gross burn separately.
    4. **Stress it.** Call `cashflow_forecaster__stress_test` with the weekly net flows from step 1
       and three shocks: collections slip 2-4 weeks, revenue down 20-30%, one surprise cost equal to a
       payroll. Pass the same `min_cash_buffer` as step 1. Report the minimum cash under each and
       the first week under the buffer. If any scenario breaches zero inside 13 weeks, the plan
       section leads with the mitigation, not the base case; if one only breaches the buffer, name
       the lever that restores it and its week.
    5. **Review last week** (when actuals exist). Call `cashflow_forecaster__variance_review` with
       forecast and actual by week. Anything off by more than 10% or $10k gets a named cause and a
       change to the next forecast's assumption. Accuracy should improve week over week.
    6. **Recommend levers**, in order of speed: collect faster (deposits, shorter terms, chase list),
       defer non-critical spend, negotiate vendor terms, draw a credit line, cut headcount, raise.
       Each lever gets a dollar amount and the week it lands.

    ## Frameworks
    - **Direct method, weekly, 13 weeks**: receipts and disbursements by week, not P&L accruals.
    - **Minimum cash buffer**: at least one full payroll cycle, ideally 4-6 weeks of operating costs.
    - **Runway** = cash ÷ net monthly burn; **default alive** (Paul Graham) = revenue growth reaches
      break-even before cash reaches zero on current trajectory.
    - **Forecast accuracy target**: within 5% on total outflows, within 10% on inflows by week 4 of
      running the process.
    - **Cash conversion levers**: DSO down (deposits, net-15, autopay), DPO up (net-45 vendors),
      inventory down. Each day of DSO is (annual revenue ÷ 365) in cash.

    ## Output format
    ```
    # 13-week cash forecast — week of <YYYY-MM-DD>
    **Opening cash:** $X · **Low point:** $Y in week N (<date>) · **Buffer:** $Z · **Runway:** M months (zero cash <YYYY-MM>) · **Default:** alive|dead

    ## Weekly view
    | Wk | Week of | Inflows | Outflows | Net | Closing | vs buffer |

    ## Stress scenarios
    | Scenario | Min cash | Week | Under buffer from | Below zero? |

    ## Variance (last week)
    <forecast vs actual, biggest miss, assumption changed>

    ## Levers (ranked by speed)
    1. <lever> — $amount, lands week N
    ```

    ## Anti-patterns
    - Forecasting collections on invoice due dates. Use observed pay behaviour.
    - Monthly granularity. Payroll on the 15th and a low point on the 12th hide inside a monthly view.
    - Reporting runway on gross burn or on a single good month of revenue.
    - Burying the breach week under a table. It is the first line of the brief.
    - Doing the week placement or compounding in your head. Call the tools every time.
    """,
)

FREQ = ("once", "weekly", "biweekly", "monthly", "semimonthly")


def _placements(item: dict, start: date, weeks: int, idx: int) -> list[tuple[int, Decimal]]:
    """Return (week_index, amount) placements for an item over the horizon."""
    amount = require_nonneg(D(item.get("amount"), f"item[{idx}].amount"), f"item[{idx}].amount")
    freq = str(item.get("frequency", "once")).lower().strip()
    if freq not in FREQ:
        raise ToolError(f"item[{idx}] ({item.get('name', '?')}): frequency must be one of {FREQ}")
    end = start + timedelta(weeks=weeks)
    out = []

    def week_of(d: date) -> int | None:
        if d < start or d >= end:
            return None
        return (d - start).days // 7

    if freq == "once":
        if item.get("date"):
            d = parse_iso(item["date"], f"item[{idx}].date")
            w = week_of(d)
        elif item.get("week"):
            w = int(item["week"]) - 1
            if not 0 <= w < weeks:
                raise ToolError(f"item[{idx}]: week must be 1-{weeks}")
        else:
            raise ToolError(f"item[{idx}] ({item.get('name', '?')}): one-off items need a date or week")
        if w is not None:
            out.append((w, amount))
    elif freq in ("weekly", "biweekly"):
        first = parse_iso(item["date"], f"item[{idx}].date") if item.get("date") else start
        step = 7 if freq == "weekly" else 14
        d = first
        while d < end:
            w = week_of(d)
            if w is not None:
                out.append((w, amount))
            d += timedelta(days=step)
    else:
        days = item.get("days") or ([int(item.get("day", 1))] if freq == "monthly" else [15, 30])
        days = [int(x) for x in days]
        if any(not 1 <= x <= 31 for x in days):
            raise ToolError(f"item[{idx}]: days must be 1-31")
        m = start.replace(day=1)
        for k in range(0, weeks // 4 + 3):  # enough calendar months to cover a 26-week horizon
            month_start = add_months(m, k)
            for dd in days:
                try:
                    d = month_start.replace(day=dd)
                except ValueError:
                    d = add_months(month_start, 1) - timedelta(days=1)
                w = week_of(d)
                if w is not None:
                    out.append((w, amount))
    return out


@AGENT.tool
def thirteen_week_forecast(
    opening_cash: float,
    start_date: str,
    inflows: list[dict],
    outflows: list[dict],
    min_cash_buffer: float = 0,
    weeks: int = 13,
) -> dict:
    """Place every inflow and outflow into weekly buckets and return the 13-week cash table with the low point.

    Items: {"name": str, "amount": number, "frequency": "once"|"weekly"|"biweekly"|"monthly"|"semimonthly",
    "date": "YYYY-MM-DD" (one-off, or first occurrence for weekly/biweekly), "week": 1-13 (alternative to date for one-offs),
    "day": 1-31 (monthly), "days": [15, 30] (semimonthly; a day past month end clamps to the last day)}.

    Args:
        opening_cash: Cash in the bank at the start of week 1.
        start_date: Monday of week 1, YYYY-MM-DD.
        inflows: List of expected receipts (see item format above).
        outflows: List of disbursements (see item format above). Use positive amounts.
        min_cash_buffer: Minimum cash you refuse to go below (e.g. one payroll). Weeks under it are flagged.
        weeks: Horizon in weeks, 4-26. Default 13.
    """
    cash = D(opening_cash, "opening_cash")
    start = parse_iso(start_date, "start_date")
    buffer = require_nonneg(D(min_cash_buffer, "min_cash_buffer"), "min_cash_buffer")
    if not 4 <= weeks <= 26:
        raise ToolError("weeks must be between 4 and 26")
    if not inflows and not outflows:
        raise ToolError("Give at least one inflow or outflow item")
    for lst, name in ((inflows, "inflows"), (outflows, "outflows")):
        if len(lst) > 300:
            raise ToolError(f"{name}: at most 300 items")
    wk_in = defaultdict(lambda: ZERO)
    wk_out = defaultdict(lambda: ZERO)
    detail_in = defaultdict(list)
    detail_out = defaultdict(list)
    for i, item in enumerate(inflows, 1):
        for w, a in _placements(item, start, weeks, i):
            wk_in[w] += a
            detail_in[w].append(str(item.get("name", f"inflow {i}")))
    for i, item in enumerate(outflows, 1):
        for w, a in _placements(item, start, weeks, i):
            wk_out[w] += a
            detail_out[w].append(str(item.get("name", f"outflow {i}")))
    rows, bal = [], cash
    low = (None, None)
    breach_weeks, first_breach = [], None
    for w in range(weeks):
        net = wk_in[w] - wk_out[w]
        bal += net
        if low[1] is None or bal < low[1]:
            low = (w + 1, bal)
        if bal < buffer:
            breach_weeks.append(w + 1)
            first_breach = first_breach or (w + 1)
        rows.append(
            {
                "week": w + 1,
                "week_of": (start + timedelta(weeks=w)).isoformat(),
                "inflows": money(wk_in[w]),
                "outflows": money(wk_out[w]),
                "net": money(net),
                "closing_cash": money(bal),
                "vs_buffer": money(bal - buffer),
                "items": {"in": detail_in[w], "out": detail_out[w]},
            }
        )
    total_in = sum(wk_in.values())
    total_out = sum(wk_out.values())
    weekly_net = (total_in - total_out) / weeks
    low_date = (start + timedelta(weeks=low[0] - 1)).isoformat()
    verdict = (
        f"Cash bottoms at ${money(low[1]):,.2f} in week {low[0]} ({low_date}); ends at ${money(bal):,.2f}. "
        + (f"Buffer breached in week {first_breach} — {first_breach - 1} week(s) of visibility to act." if first_breach else "Stays above the buffer all 13 weeks." if buffer else "No buffer set — set one equal to a payroll cycle.")
    )
    return {
        "start": start.isoformat(),
        "weeks": weeks,
        "opening_cash": money(cash),
        "closing_cash": money(bal),
        "total_inflows": money(total_in),
        "total_outflows": money(total_out),
        "avg_weekly_net": money(weekly_net),
        "low_point": {"week": low[0], "week_of": low_date, "cash": money(low[1])},
        "buffer": money(buffer),
        "weeks_below_buffer": breach_weeks,
        "first_breach_week": first_breach,
        "weeks_of_visibility": (first_breach - 1) if first_breach else weeks,
        "weekly": rows,
        "verdict": verdict,
    }


@AGENT.tool
def runway(
    cash: float,
    monthly_revenue: float,
    monthly_expenses: float,
    revenue_growth_pct: float = 0,
    expense_growth_pct: float = 0,
    start_month: str = "",
    max_months: int = 60,
) -> dict:
    """Months of runway, zero-cash date, and the default-alive/dead verdict with growth compounding.

    Projects month by month: revenue and expenses each compound at their growth rate; cash falls by
    the net burn. Default alive = revenue crosses expenses before cash crosses zero.

    Args:
        cash: Cash on hand today.
        monthly_revenue: Cash revenue collected this month.
        monthly_expenses: Total cash expenses this month (gross burn).
        revenue_growth_pct: Month-over-month revenue growth, e.g. 8 for 8%.
        expense_growth_pct: Month-over-month expense growth (hiring), e.g. 2.
        start_month: YYYY-MM-DD of month 1 (the month the revenue/expense figures describe); defaults to today.
        max_months: Projection horizon (12-120).
    """
    c = D(cash, "cash")
    rev = require_nonneg(D(monthly_revenue, "monthly_revenue"), "monthly_revenue")
    exp = require_nonneg(D(monthly_expenses, "monthly_expenses"), "monthly_expenses")
    g_r = as_rate(revenue_growth_pct, "revenue_growth_pct")
    g_e = as_rate(expense_growth_pct, "expense_growth_pct")
    if g_r < Decimal("-0.9") or g_r > 1 or g_e < Decimal("-0.9") or g_e > 1:
        raise ToolError("growth rates must be between -90 and 100 percent per month")
    if not 12 <= max_months <= 120:
        raise ToolError("max_months must be 12-120")
    start = parse_iso(start_month, "start_month") if start_month else date.today()
    # month 1 is the current month (the one monthly_revenue/monthly_expenses describe), so month m is start + (m - 1)
    label = lambda m: month_label(add_months(start, m - 1))  # noqa: E731
    net_burn = exp - rev
    simple_runway = float(c / net_burn) if net_burn > 0 else None
    bal, r, e = c, rev, exp
    zero_month, breakeven_month, path, peak_burn = None, None, [], ZERO
    cum_burn = ZERO
    for m in range(1, max_months + 1):
        burn = e - r
        peak_burn = max(peak_burn, burn)
        bal -= burn
        cum_burn += max(burn, ZERO)
        if breakeven_month is None and r >= e:
            breakeven_month = m
        if zero_month is None and bal <= 0:
            zero_month = m
        if m <= 24:
            path.append({"month": label(m), "revenue": money(r), "expenses": money(e), "net_burn": money(burn), "cash": money(bal)})
        if zero_month and breakeven_month:
            break
        r *= 1 + g_r
        e *= 1 + g_e
    if breakeven_month and (zero_month is None or breakeven_month <= zero_month):
        status = "default alive"
        cash_needed = None
    else:
        status = "default dead"
        cash_needed = None
        if breakeven_month and zero_month:
            # extra cash to survive until breakeven: rerun cumulative burn to breakeven month
            bal2, r2, e2, need = c, rev, exp, ZERO
            for _ in range(breakeven_month):
                bal2 -= e2 - r2
                need = min(need, bal2)
                r2 *= 1 + g_r
                e2 *= 1 + g_e
            cash_needed = money(-need) if need < 0 else 0.0
    verdict = (
        f"{status[0].upper()}{status[1:]}: "
        + (f"revenue covers expenses in month {breakeven_month} ({label(breakeven_month)})" if breakeven_month else f"revenue never covers expenses within {max_months} months")
        + (f"; cash runs out in month {zero_month} ({label(zero_month)})." if zero_month else "; cash never runs out on this path.")
        + (f" Need ~${cash_needed:,.0f} more to reach breakeven." if cash_needed else "")
    )
    return {
        "net_burn_now": money(net_burn),
        "gross_burn_now": money(exp),
        "runway_months_simple": round(simple_runway, 1) if simple_runway is not None else None,
        "runway_months_with_growth": zero_month,
        "zero_cash_month": label(zero_month) if zero_month else None,
        "breakeven_month": label(breakeven_month) if breakeven_month else None,
        "calendar_note": f"month 1 = {label(1)} (the month the revenue/expense inputs describe); cash is checked at each month end",
        "status": status,
        "additional_cash_to_breakeven": cash_needed,
        "peak_monthly_burn": money(peak_burn),
        "path": path,
        "verdict": verdict,
    }


@AGENT.tool
def collections_forecast(
    invoices: list[dict],
    start_date: str,
    avg_days_late: int = 12,
    collect_prob_by_bucket: dict | None = None,
    weeks: int = 13,
) -> dict:
    """Convert open invoices into expected weekly cash receipts using real payment behaviour, not due dates.

    Each invoice's expected pay date = due date + avg_days_late; expected amount = outstanding ×
    collection probability for its current aging bucket. Already-overdue invoices are expected in
    week 1-2. Returns weekly expected inflows ready to feed into the 13-week forecast.

    Args:
        invoices: List of {"id": str, "amount": number, "due": "YYYY-MM-DD", "paid": number (optional)}.
        start_date: Monday of forecast week 1, YYYY-MM-DD.
        avg_days_late: Your customers' observed average days past due at payment (0 if they pay on time).
        collect_prob_by_bucket: Optional {"current": 0.98, "1-30": 0.95, "31-60": 0.85, "61-90": 0.6, "90+": 0.3}.
        weeks: Horizon in weeks (4-26).
    """
    rows = bound_rows(invoices, "invoices")
    start = parse_iso(start_date, "start_date")
    if not 0 <= avg_days_late <= 180:
        raise ToolError("avg_days_late must be 0-180")
    if not 4 <= weeks <= 26:
        raise ToolError("weeks must be 4-26")
    probs = {"current": Decimal("0.98"), "1-30": Decimal("0.95"), "31-60": Decimal("0.85"), "61-90": Decimal("0.6"), "90+": Decimal("0.3")}
    if collect_prob_by_bucket:
        for k, v in collect_prob_by_bucket.items():
            if k not in probs:
                raise ToolError(f"collect_prob_by_bucket: unknown bucket {k!r}")
            p = D(v, f"collect_prob_by_bucket.{k}")
            if not 0 <= p <= 1:
                raise ToolError(f"collect_prob_by_bucket.{k} must be between 0 and 1")
            probs[k] = p
    weekly = defaultdict(lambda: ZERO)
    detail, expected_total, face_total, beyond = [], ZERO, ZERO, ZERO
    end = start + timedelta(weeks=weeks)
    for i, row in enumerate(rows, 1):
        outstanding = D(row.get("amount"), f"invoices[{i}].amount") - D(row.get("paid", 0), f"invoices[{i}].paid")
        if outstanding <= 0:
            continue
        due = parse_iso(row.get("due", ""), f"invoices[{i}].due")
        days_late = (start - due).days
        bucket = "current" if days_late <= 0 else "1-30" if days_late <= 30 else "31-60" if days_late <= 60 else "61-90" if days_late <= 90 else "90+"
        expected_date = max(due + timedelta(days=avg_days_late), start + timedelta(days=3 if days_late > 0 else 0))
        if days_late > 30:
            expected_date = start + timedelta(days=10)  # already chased: assume within two weeks or not at all
        expected = outstanding * probs[bucket]
        face_total += outstanding
        expected_total += expected
        if expected_date >= end:
            beyond += expected
            wk = None
        else:
            wk = (expected_date - start).days // 7 + 1
            weekly[wk] += expected
        detail.append({"id": str(row.get("id") or f"#{i}"), "outstanding": money(outstanding), "bucket": bucket, "expected_week": wk, "expected_date": expected_date.isoformat(), "probability": float(probs[bucket]), "expected_amount": money(expected)})
    items = [{"name": f"collections wk{w}", "amount": money(weekly[w]), "frequency": "once", "week": w} for w in sorted(weekly)]
    return {
        "face_value": money(face_total),
        "expected_in_horizon": money(sum(weekly.values())),
        "expected_beyond_horizon": money(beyond),
        "expected_loss": money(face_total - expected_total),
        "haircut_pct": ratio_to_pct((face_total - expected_total) / face_total) if face_total else 0.0,
        "weekly_inflows": items,
        "invoices": detail,
        "verdict": f"Expect ${money(sum(weekly.values())):,.2f} of ${money(face_total):,.2f} face value inside {weeks} weeks (haircut {ratio_to_pct((face_total - expected_total) / face_total) if face_total else 0}%); feed weekly_inflows into thirteen_week_forecast.",
    }


@AGENT.tool
def stress_test(
    opening_cash: float,
    weekly_inflows: list[float],
    weekly_outflows: list[float],
    collections_delay_weeks: int = 3,
    revenue_drop_pct: float = 25,
    surprise_cost: float = 0,
    surprise_cost_week: int = 4,
    min_cash_buffer: float = 0,
) -> dict:
    """Run base, delayed-collections, revenue-drop, surprise-cost and combined scenarios and report minimum cash.

    Takes the weekly inflow/outflow arrays from the forecast. Delay shifts all inflows later by N
    weeks (cash arriving past the horizon is lost from view); drop scales inflows down; surprise adds
    a one-off outflow. Combined applies all three.

    Args:
        opening_cash: Cash at the start of week 1.
        weekly_inflows: Inflow per week, week 1 first (from thirteen_week_forecast).
        weekly_outflows: Outflow per week, week 1 first.
        collections_delay_weeks: Weeks to shift inflows later in the delay scenario (0-8).
        revenue_drop_pct: Percent reduction of inflows in the drop scenario, e.g. 25.
        surprise_cost: One-off unexpected outflow amount (0 to skip that scenario).
        surprise_cost_week: Week the surprise lands.
        min_cash_buffer: The buffer from thirteen_week_forecast (e.g. one payroll); each scenario also reports the first week under it.
    """
    cash = D(opening_cash, "opening_cash")
    if not weekly_inflows or len(weekly_inflows) != len(weekly_outflows):
        raise ToolError("weekly_inflows and weekly_outflows must be non-empty and the same length")
    if len(weekly_inflows) > 52:
        raise ToolError("at most 52 weeks")
    if not 0 <= collections_delay_weeks <= 8:
        raise ToolError("collections_delay_weeks must be 0-8")
    drop = as_rate(revenue_drop_pct, "revenue_drop_pct")
    if not 0 <= drop <= 1:
        raise ToolError("revenue_drop_pct must be 0-100")
    inflows = [require_nonneg(D(x, f"weekly_inflows[{i}]"), "inflow") for i, x in enumerate(weekly_inflows)]
    outflows = [require_nonneg(D(x, f"weekly_outflows[{i}]"), "outflow") for i, x in enumerate(weekly_outflows)]
    n = len(inflows)
    surprise = require_nonneg(D(surprise_cost, "surprise_cost"), "surprise_cost")
    if not 1 <= surprise_cost_week <= n:
        raise ToolError(f"surprise_cost_week must be 1-{n}")
    buffer = require_nonneg(D(min_cash_buffer, "min_cash_buffer"), "min_cash_buffer")

    def run(ins, outs):
        bal, low, low_wk, breach, under = cash, cash, 0, None, None
        for w in range(n):
            bal += ins[w] - outs[w]
            if bal < low:
                low, low_wk = bal, w + 1
            if breach is None and bal < 0:
                breach = w + 1
            if under is None and buffer > 0 and bal < buffer:
                under = w + 1
        return {"min_cash": money(low), "min_week": low_wk, "ending_cash": money(bal), "breach_week": breach, "buffer_breach_week": under}

    def delayed(ins, k):
        return [ZERO] * k + ins[: n - k] if k else list(ins)

    def dropped(ins):
        return [x * (1 - drop) for x in ins]

    def surprised(outs):
        outs = list(outs)
        outs[surprise_cost_week - 1] += surprise
        return outs

    scenarios = {
        "base": run(inflows, outflows),
        f"collections_delayed_{collections_delay_weeks}w": run(delayed(inflows, collections_delay_weeks), outflows),
        f"revenue_down_{int(drop * 100)}pct": run(dropped(inflows), outflows),
    }
    if surprise > 0:
        scenarios["surprise_cost"] = run(inflows, surprised(outflows))
    scenarios["combined"] = run(delayed(dropped(inflows), collections_delay_weeks), surprised(outflows) if surprise > 0 else outflows)
    breaches = [k for k, v in scenarios.items() if v["breach_week"]]
    under_buffer = [k for k, v in scenarios.items() if v["buffer_breach_week"]]
    worst = min(scenarios.items(), key=lambda kv: kv[1]["min_cash"])
    cushion = money(min(v["min_cash"] for v in scenarios.values()))
    buffer_note = (
        f" {len(under_buffer)} scenario(s) dip under the ${money(buffer):,.0f} buffer ({', '.join(under_buffer)}) — "
        f"top-up needed to hold the buffer in the worst case: ${money(max(buffer - Decimal(str(cushion)), ZERO)):,.0f}."
        if under_buffer
        else (f" All scenarios hold the ${money(buffer):,.0f} buffer." if buffer > 0 else "")
    )
    return {
        "scenarios": scenarios,
        "scenarios_breaching_zero": breaches,
        "scenarios_below_buffer": under_buffer,
        "buffer": money(buffer),
        "worst_case": {"scenario": worst[0], **worst[1]},
        "cash_needed_to_survive_worst": money(-Decimal(str(cushion))) if cushion < 0 else 0.0,
        "verdict": (
            f"{len(breaches)} of {len(scenarios)} scenarios go below zero (worst: {worst[0]}, ${worst[1]['min_cash']:,.2f} in week {worst[1]['min_week']}). "
            + (f"Line up ${money(-Decimal(str(cushion))):,.0f} of levers or credit before week {min(v['breach_week'] for v in scenarios.values() if v['breach_week'])}." if breaches else "Cash stays above zero in every shock.")
            + buffer_note
        ),
    }


@AGENT.tool
def variance_review(rows: list[dict], tolerance_pct: float = 10, tolerance_abs: float = 10000) -> dict:
    """Compare forecast vs actual cash by week and line, flag the misses that matter, and score accuracy.

    A miss is flagged when it exceeds BOTH tolerances or either one by 2x. Returns per-row variance,
    cumulative variance, inflow/outflow accuracy and the rows to explain in the Monday meeting.

    Args:
        rows: List of {"week": str|int, "line": str (optional), "forecast_inflow": n, "actual_inflow": n, "forecast_outflow": n, "actual_outflow": n}.
        tolerance_pct: Percent variance that counts as a miss (default 10).
        tolerance_abs: Dollar variance that counts as a miss (default 10000).
    """
    data = bound_rows(rows, "rows")
    tol_p = D(tolerance_pct, "tolerance_pct") / 100
    tol_a = D(tolerance_abs, "tolerance_abs")
    out, flagged = [], []
    f_in = f_out = a_in = a_out = ZERO
    abs_err_in = abs_err_out = ZERO
    for i, r in enumerate(data, 1):
        if not isinstance(r, dict):
            raise ToolError(f"rows[{i}] must be an object")
        fi, ai = D(r.get("forecast_inflow", 0), f"rows[{i}].forecast_inflow"), D(r.get("actual_inflow", 0), f"rows[{i}].actual_inflow")
        fo, ao = D(r.get("forecast_outflow", 0), f"rows[{i}].forecast_outflow"), D(r.get("actual_outflow", 0), f"rows[{i}].actual_outflow")
        f_in, a_in, f_out, a_out = f_in + fi, a_in + ai, f_out + fo, a_out + ao
        abs_err_in += abs(ai - fi)
        abs_err_out += abs(ao - fo)
        var_in, var_out = ai - fi, ao - fo
        net_var = var_in - var_out
        issues = []
        for label, var, base in (("inflow", var_in, fi), ("outflow", var_out, fo)):
            p = abs(var) / base if base else (Decimal(1) if var else ZERO)
            big = abs(var) >= tol_a
            wide = p >= tol_p
            if (big and wide) or abs(var) >= 2 * tol_a or p >= 2 * tol_p:
                if label == "inflow":
                    direction = "short" if var < 0 else "ahead (favourable)"
                else:
                    direction = "over forecast" if var > 0 else "under forecast (favourable)"
                issues.append(f"{label} {direction} by ${money(abs(var)):,.2f} ({ratio_to_pct(p)}%)")
        row_out = {"week": r.get("week", i), "line": r.get("line"), "inflow_variance": money(var_in), "outflow_variance": money(var_out), "net_variance": money(net_var), "issues": issues}
        out.append(row_out)
        if issues:
            flagged.append(row_out)
    acc_in = ratio_to_pct(1 - abs_err_in / f_in) if f_in else None
    acc_out = ratio_to_pct(1 - abs_err_out / f_out) if f_out else None
    net_total = (a_in - a_out) - (f_in - f_out)
    return {
        "rows": out,
        "flagged": flagged,
        "totals": {"forecast_inflow": money(f_in), "actual_inflow": money(a_in), "forecast_outflow": money(f_out), "actual_outflow": money(a_out), "net_variance": money(net_total)},
        "accuracy": {"inflow_pct": acc_in, "outflow_pct": acc_out, "target_inflow_pct": 90, "target_outflow_pct": 95},
        "verdict": (
            f"Net cash came in ${money(abs(net_total)):,.2f} {'better' if net_total >= 0 else 'worse'} than forecast; "
            f"{len(flagged)} row(s) need an explanation. Inflow accuracy {acc_in}% (target 90), outflow accuracy {acc_out}% (target 95)."
        ),
    }
