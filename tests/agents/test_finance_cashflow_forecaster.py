"""Cash Flow Forecaster tools — weekly placement, runway with growth, collections haircut, stress and variance."""

import pytest

from hundred.agents.finance.cashflow_forecaster import AGENT as A
from hundred.core import ToolError


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_thirteen_week_forecast_places_items_and_finds_low_point():
    out = call(
        "thirteen_week_forecast",
        opening_cash=184000,
        start_date="2026-09-28",
        inflows=[{"name": "collections", "amount": 22000, "frequency": "weekly"}, {"name": "grant", "amount": 10000, "frequency": "once", "date": "2026-11-05"}],
        outflows=[
            {"name": "payroll", "amount": 62000, "frequency": "semimonthly", "days": [15, 30]},
            {"name": "rent", "amount": 9000, "frequency": "monthly", "day": 1},
        ],
        min_cash_buffer=62000,
    )
    wk = {r["week"]: r for r in out["weekly"]}
    assert wk[1]["outflows"] == 71000.0  # payroll 30 Sep + rent 1 Oct
    assert wk[2]["outflows"] == 0.0
    assert wk[3]["outflows"] == 62000.0  # payroll 15 Oct
    assert wk[6]["inflows"] == 32000.0  # weekly + grant on 5 Nov (week of 2 Nov)
    assert out["low_point"]["week"] == 12
    assert out["low_point"]["cash"] == 59000.0
    assert out["first_breach_week"] == 12
    assert out["weeks_of_visibility"] == 11
    assert out["closing_cash"] == 81000.0


def test_thirteen_week_forecast_rejects_bad_frequency_and_missing_date():
    with pytest.raises(ToolError):
        call("thirteen_week_forecast", opening_cash=1, start_date="2026-09-28", inflows=[{"name": "x", "amount": 1, "frequency": "daily"}], outflows=[])
    with pytest.raises(ToolError):
        call("thirteen_week_forecast", opening_cash=1, start_date="2026-09-28", inflows=[{"name": "x", "amount": 1, "frequency": "once"}], outflows=[])


def test_runway_default_dead_and_alive():
    dead = call("runway", cash=420000, monthly_revenue=30000, monthly_expenses=85000, revenue_growth_pct=8, start_month="2026-09-27")
    assert dead["runway_months_simple"] == 7.6
    assert dead["runway_months_with_growth"] == 11
    assert dead["zero_cash_month"] == "2027-08"
    assert dead["breakeven_month"] == "2027-12"
    assert dead["status"] == "default dead"
    assert dead["additional_cash_to_breakeven"] > 40000
    alive = call("runway", cash=1000000, monthly_revenue=30000, monthly_expenses=85000, revenue_growth_pct=8, start_month="2026-09-27")
    assert alive["status"] == "default alive"
    assert alive["zero_cash_month"] is None
    with pytest.raises(ToolError):
        call("runway", cash=1, monthly_revenue=1, monthly_expenses=1, revenue_growth_pct=500)


def test_collections_forecast_applies_probabilities_and_delays():
    out = call(
        "collections_forecast",
        invoices=[{"id": "a", "amount": 10000, "due": "2026-10-05"}, {"id": "b", "amount": 5000, "due": "2026-09-01"}, {"id": "c", "amount": 4000, "due": "2026-06-01"}],
        start_date="2026-09-28",
        avg_days_late=10,
    )
    by_id = {i["id"]: i for i in out["invoices"]}
    assert by_id["a"]["bucket"] == "current" and by_id["a"]["expected_week"] == 3 and by_id["a"]["expected_amount"] == 9800.0
    assert by_id["b"]["bucket"] == "1-30" and by_id["b"]["expected_amount"] == 4750.0
    assert by_id["c"]["bucket"] == "90+" and by_id["c"]["expected_amount"] == 1200.0
    assert out["face_value"] == 19000.0
    assert out["haircut_pct"] == 17.1
    assert out["weekly_inflows"][0]["frequency"] == "once"
    with pytest.raises(ToolError):
        call("collections_forecast", invoices=[{"id": "a", "amount": 1, "due": "2026-10-05"}], start_date="2026-09-28", collect_prob_by_bucket={"current": 2})


def test_stress_test_scenarios():
    out = call("stress_test", opening_cash=100000, weekly_inflows=[20000] * 13, weekly_outflows=[25000] * 13, surprise_cost=40000, surprise_cost_week=4)
    s = out["scenarios"]
    assert s["base"]["min_cash"] == 35000.0 and s["base"]["breach_week"] is None
    assert s["collections_delayed_3w"]["min_cash"] == -25000.0 and s["collections_delayed_3w"]["breach_week"] == 9
    assert s["revenue_down_25pct"]["breach_week"] == 11
    assert s["combined"]["min_cash"] == -115000.0
    assert out["cash_needed_to_survive_worst"] == 115000.0
    with pytest.raises(ToolError):
        call("stress_test", opening_cash=1, weekly_inflows=[1, 2], weekly_outflows=[1])


def test_variance_review_flags_big_misses():
    out = call(
        "variance_review",
        rows=[
            {"week": 1, "forecast_inflow": 50000, "actual_inflow": 32000, "forecast_outflow": 40000, "actual_outflow": 41000},
            {"week": 2, "forecast_inflow": 50000, "actual_inflow": 49000, "forecast_outflow": 40000, "actual_outflow": 40500},
        ],
    )
    assert out["rows"][0]["inflow_variance"] == -18000.0
    assert "inflow short by $18,000.00 (36.0%)" in out["rows"][0]["issues"]
    assert out["rows"][1]["issues"] == []
    assert out["accuracy"]["inflow_pct"] == 81.0
    assert out["totals"]["net_variance"] == -20500.0
    with pytest.raises(ToolError):
        call("variance_review", rows=[])
