"""Inventory Planner — textbook-correct reorder points, safety stock, EOQ, and stockout dates per SKU."""

from __future__ import annotations

import math
from datetime import date, timedelta

from ...core import Agent, ToolError
from ...lib import dates
from ._common import mean, money, pct, require_positive, stdev, z_for_service_level

AGENT = Agent(
    slug="inventory-planner",
    name="Inventory Planner",
    category="ecommerce",
    tagline="Reorder points, safety stock, EOQ and stockout dates computed correctly for every SKU — no more gut-feel POs.",
    description=(
        "Turns your sales history and supplier lead times into a purchase plan: forecasts demand with "
        "trend and seasonality, sets service levels by ABC/XYZ class, computes safety stock with the "
        "correct combined demand + lead-time variability formula, reorder points, economic order "
        "quantities (with MOQs and price breaks), and the exact date each SKU runs out and the last day "
        "you can still order. Every number is computed by tools, never estimated."
    ),
    triggers=[
        "when should I reorder this product / SKU",
        "how much safety stock do I need",
        "calculate reorder point / EOQ / order quantity",
        "when will I run out of stock",
        "which products are overstocked or dead stock",
        "build a purchase order plan / inventory forecast",
        "ABC analysis of my inventory",
    ],
    examples=[
        "We sell ~40 units/day of SKU A123 with a std dev of 12, supplier lead time is 21 days ± 4. What's my reorder point at 97% service level?",
        "Here's 18 months of monthly sales for our top 20 SKUs plus on-hand — tell me what to order this week and what's dead stock.",
        "Annual demand 12,000 units, $85 per PO, unit cost $6.40, holding cost 25%/yr, MOQ 1,000. What quantity should I order?",
    ],
    connectors=["Shopify", "Google Sheets", "Airtable", "Notion", "Slack"],
    playbook="""
    ## Standard
    You are a top-1% DTC inventory planner: the person who keeps in-stock rate above 97%
    on A-items while holding the least cash in stock. The one metric that matters is
    **lost-sales avoided per dollar of inventory** — stockouts on winners are the most
    expensive mistake in e-commerce, overstock on losers is the second. You never
    compute inventory math in your head; every number comes from a tool and is shown with
    its inputs so the buyer can defend the PO.

    ## Intake
    You need, per SKU: recent demand history (daily/weekly/monthly units, ideally 12+
    periods), on-hand and on-order quantities, supplier lead time (average and, if known,
    variability), and — for order quantities — order cost, unit cost, holding-cost rate,
    MOQ and price breaks. Ask at most 3 questions and only if you truly cannot proceed
    (e.g. no demand data at all). Otherwise assume and state: lead-time std dev = 20% of
    the mean if unknown; holding cost = 25% of unit cost per year; service level by ABC
    class (A 98%, B 95%, C 90%); review period 0 (continuous review) unless they say they
    order on a fixed cadence.

    ## Procedure
    1. **Forecast demand per SKU.** Call `inventory_planner__forecast_demand` with the
       period history (ending with the last complete period) and `lead_time_days`. It
       returns the demand std dev per day (the σd the safety-stock formula needs), trend,
       seasonal indices if there are ≥ 24 months, a forecast for the horizon, and the
       forecast demand over the coming lead time. Its `use_for_reorder_point` field tells
       you which daily demand to use: for seasonal or trending SKUs use
       `forecast_daily_demand_over_lead_time` — the historical average under-orders ahead
       of a peak and over-orders ahead of a trough; for stable SKUs `daily_demand_mean`.
       Pass `stockout_days` when the SKU was out of stock in any period — lost sales are
       not low demand. Always use its `daily_demand_std`, never your own averages. If history is < 4
       periods, say the forecast is low-confidence and use a wider service level margin.
    2. **Classify the catalogue** with `inventory_planner__abc_xyz_classify` when there are
       ≥ 5 SKUs. A = the SKUs that make the first 80% of revenue; XYZ = demand stability.
       AX gets the tightest control (highest service level, most frequent review); CZ gets
       make-to-order or a minimal stock policy.
    3. **Set safety stock and reorder point** with `inventory_planner__reorder_point`,
       passing lead-time variability whenever it exists (it is usually the biggest driver
       of safety stock, and amateurs ignore it). Pass `review_period_days` for periodic
       ordering. The tool also tells you whether the inventory position (on hand + on
       order) is already below the reorder point — i.e. **order now**.
    4. **Size the order** with `inventory_planner__economic_order_quantity`. Give it order
       cost, unit cost, holding rate, MOQ and price breaks; it evaluates every price break
       correctly (all-units discount) and reports the cheapest feasible quantity plus what
       the MOQ costs you versus the pure EOQ. Cap the order at ~90 days of forecast demand
       for fashion/seasonal goods unless the price break justifies it, and say so.
    5. **Date everything** with `inventory_planner__stock_cover`. Pass the forecast
       (`forecast_per_period` + `period`) for seasonal/trending SKUs so the burn rate
       follows the peak. It projects the stockout
       date from on-hand, incoming shipments and forecast demand, and back-calculates the
       last order date (stockout date − lead time − safety buffer). Any SKU whose last
       order date is in the past is a red alert at the top of the output.
    6. **Audit health** with `inventory_planner__inventory_health` on the full list: sell-
       through, weeks of supply, turns, dead stock value, overstock. This is where cash is
       freed: propose markdowns/bundles for overstock and stop-reorder for dead SKUs. For
       seasonal SKUs pass `forecast_units_next_period` so weeks of supply use the coming
       season, not the trailing one; where health says "hold" but the reorder point says
       order now, the reorder point wins.
    7. **Self-check** silently: units are consistent (daily vs monthly); lead time in
       days; service levels stated; order quantities ≥ MOQ; total PO value summed and
       compared to the buyer's cash budget if given.

    ## Frameworks
    - **Safety stock (combined variability):** SS = z × √(LT·σd² + d²·σLT²), where d and σd
      are daily demand mean/std, LT and σLT lead-time mean/std in days. With a review
      period R (periodic ordering), LT becomes LT + R. z from the cycle service level:
      90% → 1.28, 95% → 1.645, 97% → 1.88, 98% → 2.05, 99% → 2.33.
    - **Reorder point:** ROP = d × LT + SS. Order-up-to level (periodic) S = d × (LT + R) + SS.
    - **EOQ:** Q* = √(2DS/H), H = holding rate × unit cost. Total relevant cost at Q:
      D·S/Q + Q·H/2 (+ D·c with price breaks). Cost curve is flat near Q*: ±20% on Q
      changes cost by ~2%, so rounding to case packs is fine; halving Q is not.
    - **Service level by class:** A 97-99%, B 94-96%, C 88-92%. Raising 95% → 99% roughly
      doubles safety stock (z 1.645 → 2.33) — make that trade explicit in dollars.
    - **Weeks of supply thresholds:** < lead time in weeks = stockout risk; > 26 = overstock
      for evergreen, > 12 for seasonal; 0 sales in 90 days with stock = dead.
    - **Lead-time variability beats demand variability:** with d = 40/day, σd = 12, LT = 21,
      σLT = 4, the lead-time term (40² × 4² = 25,600) dwarfs the demand term (21 × 144 = 3,024).
      Negotiating σLT down from 4 to 2 days cuts safety stock more than any forecasting trick.

    ## Output format
    ```
    # Inventory plan — <date> · <n> SKUs · service level A/B/C = 98/95/90%
    ## Order now (inventory position ≤ reorder point)
    | SKU | Class | On hand + on order | ROP | Order qty | PO value | Stockout date | Last order date |
    ## Order soon (within 14 days)
    | … same columns … |
    ## Overstock / dead stock (cash to free)
    | SKU | Weeks of supply | Stock value | Action (markdown / bundle / stop reorder) |
    ## Assumptions
    - lead-time std dev, holding rate, service levels, forecast confidence
    ## Total PO value: $X · Cash freed if actions taken: $Y
    ```
    Every quantity in the tables must come from a tool result; cite the formula once in
    Assumptions so the buyer can audit it.

    ## Anti-patterns
    - Using a monthly average as "daily demand" without dividing by days in period.
    - Using the 12- or 24-month average as lead-time demand for a seasonal SKU right before
      its peak — the ROP says "not yet" while the peak eats the stock.
    - Sizing annual demand for EOQ from last year's total on a growing SKU; use the
      12-period forecast total.
    - Ignoring lead-time variability, or adding safety stock as a flat "2 weeks extra".
    - Safety stock computed as z × σd × LT (linear) instead of z × σd × √LT — this
      over-stocks by a factor of √LT and is the most common spreadsheet error.
    - Ordering the EOQ for a product with 6 weeks of trend decline — check the forecast trend
      and cut the horizon.
    - Reporting a reorder point without telling the buyer whether they are already below it.
    - Presenting numbers with false precision (order 1,237.4 units); round to pack sizes.
    """,
)

MAX_ROWS = 500


def _period_days(period: str) -> float:
    return {"daily": 1.0, "weekly": 7.0, "monthly": 365.0 / 12.0}[period]


def _seasonal_decompose(xs: list[float]) -> tuple[list[float], float, float]:
    """Classical multiplicative decomposition (Hyndman & Athanasopoulos, FPP3 §3.4).

    1. 2×12 centred moving average = trend-cycle; 2. seasonal ratio x / CMA averaged per month
    and normalised to mean 1; 3. least-squares trend on the *deseasonalised* series.
    Fitting a straight line to raw seasonal data instead biases the slope by where the peaks
    fall (a Q4 peak at the start of the window drags the trend negative even when the SKU is
    growing year on year) — the forecast then under-shoots every peak.
    """
    n = len(xs)
    ratios: list[list[float]] = [[] for _ in range(12)]
    for i in range(6, n - 6):
        cma = (0.5 * xs[i - 6] + sum(xs[i - 5 : i + 6]) + 0.5 * xs[i + 6]) / 12
        if cma > 0:
            ratios[i % 12].append(xs[i] / cma)
    raw = [mean(v) if v else 1.0 for v in ratios]
    norm = mean(raw) or 1.0
    seasonal = [r / norm for r in raw]
    ds = [x / seasonal[i % 12] if seasonal[i % 12] > 0 else x for i, x in enumerate(xs)]
    mx = (n - 1) / 2
    md = mean(ds)
    mxx = sum((i - mx) ** 2 for i in range(n))
    slope = sum((i - mx) * (d - md) for i, d in enumerate(ds)) / mxx if mxx else 0.0
    return seasonal, slope, md - slope * mx


@AGENT.tool
def forecast_demand(
    history: list[float],
    period: str = "monthly",
    horizon_periods: int = 3,
    recent_weight_periods: int = 0,
    lead_time_days: float = 0.0,
    stockout_days: list[float] | None = None,
) -> dict:
    """Forecast demand from a units-sold history and return the daily mean/std the safety-stock formula needs.

    Fits a linear trend (least squares) and, with 24+ monthly points, multiplicative seasonal
    indices by classical decomposition (centred moving average, trend fitted on the
    deseasonalised series). History must end with the last *complete* period; forecast period 1
    is the one starting now. Pass lead_time_days to get the forecast demand over the coming lead
    time — use that (not the historical average) for reorder points on trending/seasonal SKUs.

    Args:
        history: Units sold per period, oldest first (e.g. 12 monthly totals).
        period: Period length of each history point: "daily", "weekly" or "monthly".
        horizon_periods: How many future periods to forecast (1-24).
        recent_weight_periods: If > 0, compute the baseline from only the last N periods (use after a step change, e.g. a viral spike or delisting).
        lead_time_days: Optional supplier lead time in days; returns lead_time_demand_forecast and forecast_daily_demand_over_lead_time.
        stockout_days: Optional days out of stock in each history period (same length as history). Sales in those periods are scaled up to true demand (units × period days ÷ in-stock days) so a stockout is not forecast as low demand.
    """
    if period not in ("daily", "weekly", "monthly"):
        raise ToolError("period must be 'daily', 'weekly' or 'monthly'.")
    if not history or len(history) < 2:
        raise ToolError("Need at least 2 periods of history (12+ recommended).")
    if len(history) > 2000:
        raise ToolError("History too long (2000 periods max).")
    if any(h < 0 for h in history):
        raise ToolError("History contains negative units.")
    if not 1 <= horizon_periods <= 24:
        raise ToolError("horizon_periods must be 1-24.")
    if lead_time_days < 0 or lead_time_days > 730:
        raise ToolError("lead_time_days must be 0-730.")
    xs = [float(h) for h in history]
    days = _period_days(period)
    adjusted_periods = []
    if stockout_days:
        if len(stockout_days) != len(xs):
            raise ToolError("stockout_days must have one value per history period.")
        for i, so in enumerate(stockout_days):
            so = float(so or 0)
            if so < 0 or so >= days:
                raise ToolError(f"stockout_days[{i}] must be 0 to < {days:g} (a fully out-of-stock period carries no demand signal — drop it).")
            if so > 0:
                xs[i] = xs[i] * days / (days - so)
                adjusted_periods.append(i)
    base = xs[-recent_weight_periods:] if 0 < recent_weight_periods < len(xs) else xs
    n = len(xs)
    seasonal: list[float] | None = None
    if period == "monthly" and n >= 24:
        seasonal, slope, intercept = _seasonal_decompose(xs)
    else:
        # least-squares trend on the full series
        mx = (n - 1) / 2
        mxy = sum((i - mx) * (x - mean(xs)) for i, x in enumerate(xs))
        mxx = sum((i - mx) ** 2 for i in range(n))
        slope = mxy / mxx if mxx else 0.0
        intercept = mean(xs) - slope * mx

    def _fc(k: int) -> float:
        """Forecast for future period k (1 = the period starting now)."""
        i = n - 1 + k
        # after a declared step change the trend line is meaningless: use the flat recent baseline
        val = intercept + slope * i if recent_weight_periods == 0 else mean(base)
        if seasonal:
            val *= seasonal[i % 12]
        return max(0.0, val)

    forecast = [round(_fc(k), 1) for k in range(1, horizon_periods + 1)]
    base_mean = mean(base)
    raw_std = stdev(base)
    # σ for safety stock is the *unexplained* variation: residuals around trend (and season),
    # otherwise a steadily growing SKU looks far more volatile than it is.
    if recent_weight_periods == 0 and n >= 4:
        fitted = [(intercept + slope * i) * (seasonal[i % 12] if seasonal else 1.0) for i in range(n)]
        resid = [x - f for x, f in zip(xs, fitted)]
        base_std = math.sqrt(sum(r * r for r in resid) / (n - 2))
    else:
        base_std = raw_std
    # forecast error is never zero in practice: floor σ at 10% of the baseline
    std_floor_applied = base_std < 0.10 * base_mean
    base_std = max(base_std, 0.10 * base_mean)
    daily_mean = base_mean / days
    # variance scales linearly with time: σ_daily = σ_period / √days
    daily_std = base_std / math.sqrt(days)
    trend_pct_per_period = (slope / base_mean * 100) if base_mean else 0.0
    cv = base_std / base_mean if base_mean else 0.0
    if n < 4:
        confidence = "low (fewer than 4 periods)"
    elif cv > 1.0:
        confidence = "low (demand CV > 1 — lumpy)"
    elif cv > 0.5:
        confidence = "medium (CV 0.5-1)"
    else:
        confidence = "good (CV < 0.5)"
    out = {
        "periods": n,
        "period": period,
        "baseline_per_period": round(base_mean, 2),
        "std_per_period": round(base_std, 2),
        "raw_std_per_period": round(raw_std, 2),
        "std_floor_applied": std_floor_applied,
        "daily_demand_mean": round(daily_mean, 3),
        "daily_demand_std": round(daily_std, 3),
        "coefficient_of_variation": round(cv, 3),
        "trend_units_per_period": round(slope, 3),
        "trend_pct_per_period": round(trend_pct_per_period, 2),
        "seasonal_indices": [round(s, 3) for s in seasonal] if seasonal else None,
        "forecast": forecast,
        "forecast_total": round(sum(forecast), 1),
        "forecast_daily_by_period": [round(f / days, 3) for f in forecast],
        "confidence": confidence,
        "stockout_adjusted_periods": adjusted_periods,
    }
    shifts = bool(seasonal) or abs(trend_pct_per_period) >= 2.0
    if lead_time_days > 0:
        # integrate the per-period forecast over the next lead_time_days
        remaining, k, ltd = lead_time_days, 1, 0.0
        while remaining > 1e-9:
            take = min(days, remaining)
            ltd += _fc(k) * take / days
            remaining -= take
            k += 1
        out["lead_time_days"] = lead_time_days
        out["lead_time_demand_forecast"] = round(ltd, 1)
        out["forecast_daily_demand_over_lead_time"] = round(ltd / lead_time_days, 3)
        out["lead_time_demand_at_historical_average"] = round(daily_mean * lead_time_days, 1)
    out["use_for_reorder_point"] = (
        "forecast_daily_demand_over_lead_time (seasonal/trending SKU — the historical average misstates lead-time demand)"
        if shifts else "daily_demand_mean (stable SKU)"
    )
    lt_note = (
        f" Lead-time demand over {lead_time_days:g} days: {out['lead_time_demand_forecast']:.0f} units "
        f"({out['forecast_daily_demand_over_lead_time']:.1f}/day) vs {out['lead_time_demand_at_historical_average']:.0f} at the historical average."
        if lead_time_days > 0 else ""
    )
    out["summary"] = (
        f"{daily_mean:.1f} units/day historical average (σ {daily_std:.1f}/day), trend {trend_pct_per_period:+.1f}%/period, "
        f"next {horizon_periods} {period} periods ≈ {sum(forecast):.0f} units.{lt_note} Confidence: {confidence}."
    )
    return out


@AGENT.tool
def reorder_point(
    daily_demand_mean: float,
    daily_demand_std: float,
    lead_time_days: float,
    lead_time_std_days: float = 0.0,
    service_level: float = 95.0,
    review_period_days: float = 0.0,
    on_hand: float = -1.0,
    on_order: float = 0.0,
) -> dict:
    """Compute safety stock (combined demand + lead-time variability) and the reorder point; say whether to order now.

    Uses SS = z·√(LT·σd² + d²·σLT²) with LT extended by the review period for periodic
    ordering. Returns ROP, order-up-to level, and the inventory-position check.

    Args:
        daily_demand_mean: Average units sold per day (d).
        daily_demand_std: Standard deviation of daily demand (σd). Use forecast_demand's daily_demand_std.
        lead_time_days: Average supplier lead time in days, order placed → stock sellable.
        lead_time_std_days: Standard deviation of lead time in days (0 if perfectly reliable).
        service_level: Cycle service level as percent (95) or fraction (0.95). 50-99.99.
        review_period_days: Days between order reviews if you order on a fixed cadence; 0 for continuous review.
        on_hand: Units currently in stock (sellable). Pass -1 to skip the order-now check.
        on_order: Units already ordered and not yet received.
    """
    d = require_positive("daily_demand_mean", daily_demand_mean, allow_zero=True)
    sd = require_positive("daily_demand_std", daily_demand_std, allow_zero=True)
    lt = require_positive("lead_time_days", lead_time_days)
    slt = require_positive("lead_time_std_days", lead_time_std_days, allow_zero=True)
    rp = require_positive("review_period_days", review_period_days, allow_zero=True)
    z = z_for_service_level(service_level)
    horizon = lt + rp
    demand_term = horizon * sd**2
    lead_term = d**2 * slt**2
    ss = z * math.sqrt(demand_term + lead_term)
    cycle_stock = d * lt
    rop = cycle_stock + ss
    order_up_to = d * horizon + ss
    driver = "lead-time variability" if lead_term > demand_term else "demand variability"
    out = {
        "z": round(z, 3),
        "service_level_pct": round(service_level if service_level > 1 else service_level * 100, 2),
        "expected_demand_over_lead_time": round(cycle_stock, 1),
        "safety_stock": math.ceil(ss),
        "reorder_point": math.ceil(rop),
        "order_up_to_level": math.ceil(order_up_to) if rp > 0 else None,
        "safety_stock_days_of_cover": round(ss / d, 1) if d else None,
        "variance_split": {"demand_term": round(demand_term, 1), "lead_time_term": round(lead_term, 1), "dominant": driver},
        "formula": "SS = z·√((LT+R)·σd² + d²·σLT²); ROP = d·LT + SS",
    }
    if on_hand >= 0:
        position = on_hand + on_order
        gap = position - rop
        out["inventory_position"] = round(position, 1)
        out["order_now"] = position <= rop
        out["units_above_reorder_point"] = round(gap, 1)
        out["days_until_reorder_point"] = round(gap / d, 1) if d and gap > 0 else 0.0
        out["verdict"] = (
            f"ORDER NOW: position {position:.0f} ≤ ROP {math.ceil(rop)}."
            if position <= rop
            else f"Not yet: {gap:.0f} units above ROP ≈ {gap / d if d else 0:.0f} days until reorder."
        )
    else:
        out["verdict"] = f"ROP {math.ceil(rop)} = {cycle_stock:.0f} lead-time demand + {math.ceil(ss)} safety stock (z={z:.2f}); driver: {driver}."
    return out


@AGENT.tool
def economic_order_quantity(
    annual_demand: float,
    order_cost: float,
    unit_cost: float,
    holding_cost_pct: float = 25.0,
    moq: float = 0.0,
    price_breaks: list[dict] | None = None,
    pack_size: float = 0.0,
) -> dict:
    """Compute EOQ = √(2DS/H), then the cheapest feasible order quantity given MOQ, pack size and all-units price breaks.

    Reports orders per year, days between orders, and total annual cost (purchase + ordering +
    holding) for the EOQ, the MOQ, and each price break so the trade-off is explicit.

    Args:
        annual_demand: Units demanded per year (D).
        order_cost: Fixed cost per purchase order in currency (S): admin, freight minimums, inspection.
        unit_cost: Base unit cost (c) before any price break.
        holding_cost_pct: Annual holding cost as percent of unit cost (capital + storage + shrink + obsolescence). 20-30 typical.
        moq: Supplier minimum order quantity, 0 if none.
        price_breaks: Optional list of {"min_qty": int, "unit_cost": float} all-units discounts (order ≥ min_qty → every unit at that cost).
        pack_size: Round quantities up to a multiple of this (case/pallet size); 0 for none.
    """
    D = require_positive("annual_demand", annual_demand)
    S = require_positive("order_cost", order_cost)
    c = require_positive("unit_cost", unit_cost)
    if not 0 < holding_cost_pct <= 200:
        raise ToolError("holding_cost_pct must be between 0 and 200 (percent per year).")
    i = holding_cost_pct / 100.0
    moq = require_positive("moq", moq, allow_zero=True)
    pack = require_positive("pack_size", pack_size, allow_zero=True)

    def _round_up(q: float) -> float:
        q = max(q, moq)
        if pack:
            q = math.ceil(q / pack) * pack
        return q

    def _total_cost(q: float, cost: float) -> dict:
        H = i * cost
        ordering = D * S / q
        holding = q * H / 2
        return {"purchase": money(D * cost), "ordering": money(ordering), "holding": money(holding), "total": money(D * cost + ordering + holding)}

    H0 = i * c
    eoq_raw = math.sqrt(2 * D * S / H0)
    candidates = []
    tiers = [{"min_qty": 0, "unit_cost": c}] + sorted(
        [{"min_qty": float(b.get("min_qty", 0)), "unit_cost": float(b.get("unit_cost", c))} for b in (price_breaks or [])[:20]],
        key=lambda b: b["min_qty"],
    )
    for t_idx, tier in enumerate(tiers):
        cost = tier["unit_cost"]
        if cost <= 0:
            raise ToolError("price break unit_cost must be > 0.")
        H = i * cost
        q_star = math.sqrt(2 * D * S / H)
        upper = tiers[t_idx + 1]["min_qty"] if t_idx + 1 < len(tiers) else float("inf")
        feasible = tier["min_qty"] <= q_star < upper
        if feasible or q_star < tier["min_qty"]:
            q = q_star if feasible else tier["min_qty"]
            q = _round_up(q)
        else:
            # EOQ lies above this tier: the cheapest in-tier quantity is the largest one below the next break
            q = (math.floor((upper - 1) / pack) * pack) if pack else upper - 1
            if q < max(moq, tier["min_qty"]):
                continue
        if q < tier["min_qty"]:
            q = tier["min_qty"]
        # after rounding q could cross into next tier — fine, but cost stays this tier's only if within tier
        if q >= upper:
            continue
        cand = {"tier_min_qty": tier["min_qty"], "unit_cost": cost, "eoq_at_this_price": round(q_star, 1), "eoq_feasible_in_tier": feasible, "order_qty": round(q, 1)}
        cand.update(_total_cost(q, cost))
        candidates.append(cand)
    best = min(candidates, key=lambda x: x["total"])
    q = best["order_qty"]
    orders_per_year = D / q
    eoq_total = _total_cost(eoq_raw, c)["total"]
    constraint_cost = money(max(0.0, best["total"] - eoq_total))
    saving_vs_eoq = money(max(0.0, eoq_total - best["total"]))
    return {
        "eoq_unconstrained": round(eoq_raw, 1),
        "holding_cost_per_unit_year": money(H0),
        "recommended_order_qty": q,
        "recommended_unit_cost": best["unit_cost"],
        "orders_per_year": round(orders_per_year, 2),
        "days_between_orders": round(365 / orders_per_year, 1),
        "annual_cost_breakdown": {k: best[k] for k in ("purchase", "ordering", "holding", "total")},
        "po_value": money(q * best["unit_cost"]),
        "constraint_cost_per_year_vs_eoq": constraint_cost,
        "saving_per_year_vs_base_eoq": saving_vs_eoq,
        "candidates": candidates,
        "formula": "EOQ = √(2DS/H), H = holding% × unit cost; total = D·c + D·S/Q + Q·H/2",
        "verdict": (
            f"Order {q:,.0f} units at {best['unit_cost']:.2f} (PO {q * best['unit_cost']:,.0f}), "
            f"{orders_per_year:.1f} orders/yr every {365 / orders_per_year:.0f} days. Unconstrained EOQ {eoq_raw:,.0f}."
            + (f" MOQ/pack rounding costs {constraint_cost:,.0f}/yr vs EOQ." if constraint_cost else "")
            + (f" Price break saves {saving_vs_eoq:,.0f}/yr vs ordering the base EOQ." if saving_vs_eoq else "")
        ),
    }


@AGENT.tool
def stock_cover(
    on_hand: float,
    daily_demand: float = 0.0,
    lead_time_days: float = 0.0,
    safety_stock: float = 0.0,
    incoming: list[dict] | None = None,
    today: str = "",
    daily_demand_std: float = 0.0,
    forecast_per_period: list[float] | None = None,
    period: str = "monthly",
) -> dict:
    """Project the stockout date and the last safe order date from on-hand stock, incoming shipments and demand.

    Simulates day by day so incoming POs are counted when they land, not before. For seasonal or
    trending SKUs pass forecast_per_period (forecast_demand's `forecast`, period 1 starting today)
    so the burn rate follows the forecast instead of a flat average. Returns days of cover, the
    date stock hits safety stock, the date it hits zero, and order-by date.

    Args:
        on_hand: Sellable units in stock today.
        daily_demand: Forecast average units sold per day (flat). Ignored when forecast_per_period is given.
        lead_time_days: Supplier lead time in days.
        safety_stock: Safety stock level (units) — the buffer you do not want to dip into.
        incoming: Optional list of {"qty": units, "arrives": "YYYY-MM-DD"} purchase orders in transit.
        today: Today's date as YYYY-MM-DD (defaults to the real today).
        daily_demand_std: Optional daily demand std dev; adds a pessimistic (+1σ) stockout date.
        forecast_per_period: Optional per-period demand forecast starting today (e.g. monthly units); the last value repeats beyond the list.
        period: Length of each forecast_per_period value: "daily", "weekly" or "monthly".
    """
    oh = require_positive("on_hand", on_hand, allow_zero=True)
    d = require_positive("daily_demand", daily_demand, allow_zero=True)
    lt = require_positive("lead_time_days", lead_time_days, allow_zero=True)
    ss = require_positive("safety_stock", safety_stock, allow_zero=True)
    start = dates.parse_date(today) if today else date.today()
    profile: list[float] | None = None
    pdays = 1.0
    if forecast_per_period:
        if period not in ("daily", "weekly", "monthly"):
            raise ToolError("period must be 'daily', 'weekly' or 'monthly'.")
        if len(forecast_per_period) > 2000 or any(float(f) < 0 for f in forecast_per_period):
            raise ToolError("forecast_per_period must be ≤ 2000 non-negative values.")
        pdays = _period_days(period)
        profile = [float(f) / pdays for f in forecast_per_period]
    arrivals: dict[date, float] = {}
    for po in (incoming or [])[:100]:
        try:
            arr = dates.parse_date(str(po.get("arrives", "")))
        except ToolError:
            raise ToolError(f"incoming shipment needs arrives as YYYY-MM-DD, got {po.get('arrives')!r}") from None
        qty = float(po.get("qty", 0))
        if qty <= 0:
            raise ToolError("incoming shipment qty must be > 0.")
        arrivals[arr] = arrivals.get(arr, 0.0) + qty

    def rate_on(day: int) -> float:
        if profile is None:
            return d
        return profile[min(int(day / pdays), len(profile) - 1)]

    def simulate(extra: float) -> tuple[date | None, date | None]:
        stock = oh
        hit_ss = zero = None
        for day in range(0, 730):
            cur = start + timedelta(days=day)
            stock += arrivals.get(cur, 0.0)
            if hit_ss is None and stock <= ss and (ss > 0 or stock <= 0):
                hit_ss = cur
            if stock <= 0:
                zero = cur
                break
            stock -= rate_on(day) + extra
        return hit_ss, zero

    if (profile is None and d == 0) or (profile is not None and not any(profile)):
        return {"days_of_cover": None, "stockout_date": None, "verdict": "No demand — stock never runs out; check for dead stock instead."}
    hit_ss, zero = simulate(0.0)
    pess = simulate(daily_demand_std)[1] if daily_demand_std > 0 else None
    total_incoming = sum(arrivals.values())
    if profile is None:
        days_cover = (oh + total_incoming) / d
    else:
        days_cover = float((zero - start).days) if zero else 730.0
    order_by = (zero - timedelta(days=math.ceil(lt))) if zero else None
    order_by_safe = (hit_ss - timedelta(days=math.ceil(lt))) if hit_ss else None
    status = "ok"
    if order_by_safe and order_by_safe <= start:
        status = "order overdue" if (order_by and order_by <= start) else "order now"
    elif order_by_safe and (order_by_safe - start).days <= 14:
        status = "order within 14 days"
    return {
        "today": start.isoformat(),
        "on_hand": oh,
        "incoming_units": total_incoming,
        "demand_basis": "forecast profile" if profile is not None else "flat daily demand",
        "days_of_cover_incl_incoming": round(days_cover, 1),
        "weeks_of_cover": round(days_cover / 7, 1),
        "date_hits_safety_stock": hit_ss.isoformat() if hit_ss else None,
        "stockout_date": zero.isoformat() if zero else None,
        "stockout_date_pessimistic": pess.isoformat() if pess else None,
        "last_order_date_to_protect_safety_stock": order_by_safe.isoformat() if order_by_safe else None,
        "last_order_date_before_zero": order_by.isoformat() if order_by else None,
        "status": status,
        "verdict": (
            f"{days_cover:.0f} days of cover. Hits safety stock {hit_ss.isoformat() if hit_ss else 'never'}, zero "
            f"{zero.isoformat() if zero else 'never (within 2 years)'}; place PO by "
            f"{order_by_safe.isoformat() if order_by_safe else 'n/a'} ({status})."
        ),
    }


def _abc(revenue_share_cum: float) -> str:
    return "A" if revenue_share_cum <= 0.80 else ("B" if revenue_share_cum <= 0.95 else "C")


def _xyz(cv: float | None) -> str:
    if cv is None:
        return "?"
    return "X" if cv < 0.5 else ("Y" if cv <= 1.0 else "Z")


POLICY = {
    "AX": ("98-99%", "continuous review, weekly; automate reorder; tight forecasting"),
    "AY": ("97-98%", "continuous review; larger safety stock; watch promos"),
    "AZ": ("95-97%", "manual review weekly; consider make-to-order or supplier VMI; big safety stock is costly"),
    "BX": ("95-96%", "periodic review biweekly"),
    "BY": ("94-95%", "periodic review biweekly"),
    "BZ": ("92-94%", "periodic review monthly; small lots"),
    "CX": ("90-92%", "periodic review monthly; order in economic lots"),
    "CY": ("88-90%", "monthly; minimal safety stock"),
    "CZ": ("85-88%", "order-to-demand or delist; do not hold safety stock"),
}


@AGENT.tool
def abc_xyz_classify(skus: list[dict]) -> dict:
    """Classify SKUs by revenue contribution (ABC, 80/15/5) and demand stability (XYZ by coefficient of variation) with a service-level policy per cell.

    Args:
        skus: List of {"sku": str, "revenue": float, "demand_history": [units per period...]} (demand_history optional; without it XYZ is "?").
    """
    if not skus:
        raise ToolError("skus is empty.")
    if len(skus) > MAX_ROWS:
        raise ToolError(f"Too many SKUs ({len(skus)}); max {MAX_ROWS} per call.")
    rows = []
    for s in skus:
        try:
            rev = float(s.get("revenue", 0))
        except (TypeError, ValueError):
            raise ToolError(f"revenue must be numeric for {s.get('sku')!r}") from None
        if rev < 0:
            raise ToolError(f"revenue cannot be negative for {s.get('sku')!r}")
        hist = [float(x) for x in (s.get("demand_history") or [])][:500]
        cv = (stdev(hist) / mean(hist)) if len(hist) >= 3 and mean(hist) > 0 else None
        rows.append({"sku": str(s.get("sku", "?")), "revenue": rev, "cv": cv})
    total = sum(r["revenue"] for r in rows)
    if total <= 0:
        raise ToolError("Total revenue is 0 — nothing to classify.")
    rows.sort(key=lambda r: -r["revenue"])
    cum = 0.0
    counts: dict[str, int] = {}
    out = []
    for r in rows:
        cum += r["revenue"]
        abc = _abc(cum / total)
        xyz = _xyz(r["cv"])
        cell = abc + xyz
        counts[cell] = counts.get(cell, 0) + 1
        sl, policy = POLICY.get(cell, ("95%", "review monthly"))
        out.append(
            {
                "sku": r["sku"],
                "revenue": money(r["revenue"]),
                "revenue_share_pct": pct(r["revenue"] / total),
                "cumulative_share_pct": pct(cum / total),
                "abc": abc,
                "cv": round(r["cv"], 2) if r["cv"] is not None else None,
                "xyz": xyz,
                "class": cell,
                "target_service_level": sl,
                "policy": policy,
            }
        )
    a_count = sum(1 for r in out if r["abc"] == "A")
    return {
        "skus": out,
        "class_counts": dict(sorted(counts.items())),
        "a_items": a_count,
        "a_items_pct_of_catalogue": pct(a_count / len(out)),
        "summary": f"{a_count} of {len(out)} SKUs ({100 * a_count / len(out):.0f}%) make the first 80% of revenue. Class mix: {dict(sorted(counts.items()))}.",
    }


@AGENT.tool
def inventory_health(skus: list[dict], period_days: int = 90, lead_time_days: float = 30.0, seasonal: bool = False) -> dict:
    """Audit sell-through, weeks of supply, turns and dead/overstock value across SKUs to find cash to free and stockout risks.

    Args:
        skus: List of {"sku": str, "on_hand": units, "units_sold": units sold in the period, "unit_cost": float, "received": units received in period (optional), "forecast_units_next_period": forecast units for the NEXT period_days (optional — use for seasonal SKUs so weeks of supply reflect the coming peak or trough, not the trailing period)}.
        period_days: Length of the sales period the units_sold figure covers (default 90).
        lead_time_days: Typical replenishment lead time — SKUs with less cover than this are stockout risks.
        seasonal: True for fashion/seasonal goods (overstock threshold 12 weeks instead of 26).
    """
    if not skus:
        raise ToolError("skus is empty.")
    if len(skus) > MAX_ROWS:
        raise ToolError(f"Too many SKUs ({len(skus)}); max {MAX_ROWS} per call.")
    if period_days <= 0:
        raise ToolError("period_days must be > 0.")
    over_wos = 12 if seasonal else 26
    lt_weeks = lead_time_days / 7
    rows, totals = [], {"stock_value": 0.0, "dead_value": 0.0, "overstock_value": 0.0, "stockout_risk_skus": 0, "dead_skus": 0, "overstock_skus": 0}
    for s in skus:
        try:
            oh = float(s.get("on_hand", 0))
            sold = float(s.get("units_sold", 0))
            cost = float(s.get("unit_cost", 0))
        except (TypeError, ValueError):
            raise ToolError(f"on_hand, units_sold and unit_cost must be numeric for {s.get('sku')!r}") from None
        if oh < 0 or sold < 0 or cost < 0:
            raise ToolError(f"negative values for {s.get('sku')!r}")
        received = s.get("received")
        weekly = sold / period_days * 7
        trailing_weekly = weekly
        fc = s.get("forecast_units_next_period")
        if fc not in (None, ""):
            try:
                fc = float(fc)
            except (TypeError, ValueError):
                raise ToolError(f"forecast_units_next_period must be numeric for {s.get('sku')!r}") from None
            if fc < 0:
                raise ToolError(f"negative forecast for {s.get('sku')!r}")
            weekly = fc / period_days * 7
        wos = (oh / weekly) if weekly > 0 else None
        denom = float(received) if received not in (None, 0, "") else (sold + oh)
        sell_through = sold / denom if denom > 0 else None
        avg_inv = (oh + (oh + sold)) / 2  # proxy: average of ending and beginning stock
        turns = (sold / avg_inv) * (365 / period_days) if avg_inv > 0 else None
        value = oh * cost
        totals["stock_value"] += value
        flags, action = [], "hold"
        if sold == 0 and oh > 0 and not weekly:
            flags.append("dead (0 sold)")
            totals["dead_value"] += value
            totals["dead_skus"] += 1
            action = "stop reorder; liquidate/bundle"
        elif wos is not None and wos > over_wos:
            flags.append(f"overstock ({wos:.0f} wks > {over_wos})")
            excess_units = max(0.0, oh - weekly * over_wos)
            totals["overstock_value"] += excess_units * cost
            totals["overstock_skus"] += 1
            action = "markdown or bundle excess; pause reorder"
        elif wos is not None and wos < lt_weeks:
            flags.append(f"stockout risk ({wos:.1f} wks < lead time {lt_weeks:.1f})")
            totals["stockout_risk_skus"] += 1
            action = "reorder now / expedite"
        rows.append(
            {
                "sku": str(s.get("sku", "?")),
                "on_hand": oh,
                "weekly_velocity": round(weekly, 2),
                "velocity_basis": "forecast" if fc not in (None, "") else "trailing",
                "trailing_weekly_velocity": round(trailing_weekly, 2),
                "weeks_of_supply": round(wos, 1) if wos is not None else None,
                "sell_through_pct": pct(sell_through) if sell_through is not None else None,
                "annualised_turns": round(turns, 1) if turns is not None else None,
                "stock_value": money(value),
                "flags": flags,
                "action": action,
            }
        )
    rows.sort(key=lambda r: (-(len(r["flags"])), -r["stock_value"]))
    totals = {k: (money(v) if isinstance(v, float) else v) for k, v in totals.items()}
    healthy = len(rows) - totals["dead_skus"] - totals["overstock_skus"] - totals["stockout_risk_skus"]
    return {
        "skus": rows,
        "totals": totals,
        "healthy_skus": healthy,
        "thresholds": {"overstock_weeks": over_wos, "stockout_risk_weeks": round(lt_weeks, 1)},
        "summary": (
            f"{len(rows)} SKUs, stock value {totals['stock_value']:,.0f}: {totals['stockout_risk_skus']} at stockout risk, "
            f"{totals['overstock_skus']} overstocked ({totals['overstock_value']:,.0f} excess), {totals['dead_skus']} dead ({totals['dead_value']:,.0f})."
        ),
    }
