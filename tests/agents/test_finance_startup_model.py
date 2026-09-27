"""Startup Financial Model tools — MRR compounding, hiring burn, runway, round sizing."""

import pytest

from hundred.agents.finance.startup_model import AGENT as A
from hundred.core import ToolError


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_mrr_projection_first_month_and_target():
    out = call("mrr_projection", starting_mrr=42000, months=24, new_mrr_monthly=6000, new_mrr_growth_pct=5, churn_pct=2.5, expansion_pct=1, target_mrr=100000, start_month="2026-09-27")
    m1 = out["monthly"][0]
    assert m1["churn"] == -1050.0 and m1["expansion"] == 420.0 and m1["ending_mrr"] == 47370.0
    assert m1["label"] == "2026-09"  # month 1 is labelled with start_month's month
    assert out["monthly"][1]["new"] == 6300.0  # new MRR compounds 5%
    assert out["target_reached_month"] == 10
    assert out["cmgr_pct"] == 7.9
    assert abs(out["ending_arr"] - out["ending_mrr"] * 12) < 0.1


def test_mrr_projection_steady_state_and_validation():
    out = call("mrr_projection", starting_mrr=10000, months=12, new_mrr_monthly=1000, churn_pct=5)
    assert out["steady_state_mrr_if_new_flat"] == 20000.0
    with pytest.raises(ToolError):
        call("mrr_projection", starting_mrr=100, months=0, new_mrr_monthly=1)


def test_hiring_plan_burn_loaded_costs_and_flags():
    out = call(
        "hiring_plan_burn",
        hires=[{"role": "eng", "start_month": 1, "annual_salary": 160000, "count": 2}, {"role": "sales", "start_month": 3, "annual_salary": 140000, "monthly_extra": 3000}],
        months=6,
        existing_monthly_costs=20000,
        existing_headcount=3,
        existing_payroll_monthly=40000,
    )
    assert out["hires"][0]["loaded_monthly_cost"] == 34666.67  # 160k*1.3/12*2
    assert out["burn_series"][0] == 94666.67
    assert out["burn_series"][2] == 112833.33
    assert out["ending_headcount"] == 6
    assert out["cumulative_burn"] == 640666.67
    assert out["monthly"][2]["starts"] == ["sales"]
    with pytest.raises(ToolError):
        call("hiring_plan_burn", hires=[{"role": "x", "start_month": 9, "annual_salary": 1}], months=6)


def test_runway_projection_zero_cash_and_milestone():
    out = call("runway_projection", cash=300000, monthly_revenue=[20000] * 12, monthly_costs=[80000] * 12, milestone_month=6, start_month="2026-09-27")
    assert out["zero_cash_month"] == 6
    assert out["zero_cash_label"] == "2027-02"  # month 6, counting Sep 2026 as month 1
    assert out["runway_months"] == 5
    assert out["lowest_cash"]["amount"] == -420000.0
    assert out["milestone_covered_with_buffer"] is False
    ok = call("runway_projection", cash=300000, monthly_revenue=[20000, 40000, 60000, 90000, 100000], monthly_costs=[80000], gross_margin_pct=80)
    assert ok["zero_cash_month"] is None and ok["breakeven_month"] == 5
    with pytest.raises(ToolError):
        call("runway_projection", cash=1, monthly_revenue=[], monthly_costs=[])


def test_fundraise_sizing_dilution_with_pool():
    out = call("fundraise_sizing", monthly_burn=95000, runway_months_target=24, buffer_months=6, pre_money_valuation=12000000, option_pool_pct=10, founder_ownership_pct=80)
    assert out["raise_amount"] == 2850000.0
    assert out["post_money"] == 14850000.0
    assert out["investor_ownership_pct"] == 19.2
    assert out["founders_after_pct"] == 56.6  # 80% × (1 − 19.2% − 10%)
    assert out["effective_pre_money_after_pool"] == 10515000.0
    grow = call("fundraise_sizing", monthly_burn=100000, runway_months_target=12, buffer_months=0, burn_growth_pct_monthly=5)
    assert grow["raise_amount"] == 1592000.0  # sum of 100k × 1.05^k, k=0..11, rounded up to $1k
    with pytest.raises(ToolError):
        call("fundraise_sizing", monthly_burn=0)
