"""Freelance Tax Estimator tools — SE tax, brackets, safe harbor, deductions, deadlines."""

import pytest

from hundred.agents.finance.freelance_tax import AGENT as A
from hundred.core import ToolError


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_quarterly_estimate_single_95k_by_hand():
    out = call("quarterly_estimate", net_se_income=95000, filing_status="single")
    se = out["se_tax"]
    assert se["se_base_92_35pct"] == 87732.5
    assert se["social_security"] == 10878.83
    assert se["medicare"] == 2544.24
    assert se["total"] == 13423.07
    it = out["income_tax"]
    assert it["agi"] == 88288.46
    assert it["qbi_deduction"] == 14657.69
    assert it["taxable_income"] == 58630.77
    assert it["federal_income_tax"] == 7812.77  # 1192.50 + 4386.00 + 2234.27
    assert it["marginal_rate_pct"] == 22.0
    assert out["total_tax"] == 21235.84
    assert out["quarterly_payment"] == 5308.96
    assert out["set_aside_pct_of_net"] == 22.4
    assert "approx" in out["defaults_used"][0]
    assert "not tax advice" in out["scope_note"]


def test_quarterly_estimate_wage_base_and_overrides():
    out = call("quarterly_estimate", net_se_income=200000, filing_status="single", w2_wages=50000, w2_withholding=6000, apply_qbi_deduction=False)
    # SS room = 176100 - 50000 = 126100 → 12.4% = 15636.40; Medicare on full base; surtax above 200k
    assert out["se_tax"]["social_security"] == 15636.4
    assert out["se_tax"]["additional_medicare"] == 312.3
    assert out["income_tax"]["qbi_deduction"] == 0.0
    custom = call("quarterly_estimate", net_se_income=50000, brackets=[[0, 10], [20000, 20]], standard_deduction=10000, ss_wage_base=100000, apply_qbi_deduction=False)
    assert custom["defaults_used"] == []
    assert custom["income_tax"]["marginal_rate_pct"] == 20.0
    with pytest.raises(ToolError):
        call("quarterly_estimate", net_se_income=50000, brackets=[[10, 10], [5, 20]])
    with pytest.raises(ToolError):
        call("quarterly_estimate", net_se_income=-5)


def test_safe_harbor_prior_year_and_high_income():
    out = call("safe_harbor", prior_year_total_tax=18400, prior_year_agi=140000, current_year_projected_tax=26000, paid_to_date=6000, quarters_elapsed=2)
    assert out["required_annual_payment"] == 18400.0
    assert out["basis"] == "prior-year"
    assert out["shortfall_now"] == 3200.0
    assert out["per_remaining_quarter"] == 6200.0
    assert out["on_track"] is False
    high = call("safe_harbor", prior_year_total_tax=18400, prior_year_agi=160000, current_year_projected_tax=26000)
    assert high["required_annual_payment"] == 20240.0
    falling = call("safe_harbor", prior_year_total_tax=30000, prior_year_agi=100000, current_year_projected_tax=10000)
    assert falling["required_annual_payment"] == 9000.0 and falling["basis"].startswith("current-year")
    with pytest.raises(ToolError):
        call("safe_harbor", prior_year_total_tax=1, prior_year_agi=1, current_year_projected_tax=1, quarters_elapsed=5)


def test_deduction_value_rules():
    out = call(
        "deduction_value",
        expenses=[
            {"type": "mileage", "miles": 4000},
            {"type": "home_office", "sqft": 400},
            {"type": "meals", "amount": 2800},
            {"type": "phone", "amount": 1200, "business_use_pct": 60},
            {"type": "entertainment", "amount": 500},
            {"type": "health_insurance", "amount": 6000},
        ],
        marginal_income_rate_pct=22,
    )
    by = {i["type"]: i for i in out["items"]}
    assert by["mileage"]["deductible"] == 2800.0
    assert by["home_office"]["deductible"] == 1500.0 and "capped" in by["home_office"]["rule"]
    assert by["meals"]["deductible"] == 1400.0
    assert by["phone"]["deductible"] == 720.0
    assert by["entertainment"]["deductible"] == 0.0
    assert by["health_insurance"]["tax_saved"] == 1320.0  # income tax only
    assert by["meals"]["tax_saved"] == 505.82  # 1400 × 36.13%
    with pytest.raises(ToolError):
        call("deduction_value", expenses=[{"type": "yacht", "amount": 1}], marginal_income_rate_pct=22)


def test_payment_deadlines_weekend_rollover():
    out = call("payment_deadlines", tax_year=2026, as_of="2026-09-27", annual_amount=20000)
    assert out["quarters_elapsed"] == 3
    assert out["next"]["quarter"] == 4 and out["next"]["due"] == "2027-01-15" and out["next"]["days_remaining"] == 110
    assert out["next"]["amount"] == 5000.0
    y28 = call("payment_deadlines", tax_year=2028, as_of="2026-09-27")
    assert y28["deadlines"][0]["due"] == "2028-04-17" and y28["deadlines"][0]["adjusted_from_15th"] is True
    with pytest.raises(ToolError):
        call("payment_deadlines", tax_year=1900)
