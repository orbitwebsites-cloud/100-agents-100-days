"""Freelance Tax Estimator tools — SE tax, brackets, safe harbor, deductions, deadlines."""

import pytest

from hundred.agents.finance.freelance_tax import AGENT as A
from hundred.core import ToolError


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_quarterly_estimate_single_95k_by_hand():
    # 2026 defaults: std deduction 16,100; brackets 12,400 / 50,400 / 105,700 (Rev. Proc. 2025-32)
    out = call("quarterly_estimate", net_se_income=95000, filing_status="single")
    se = out["se_tax"]
    assert se["se_base_92_35pct"] == 87732.5
    assert se["social_security"] == 10878.83
    assert se["medicare"] == 2544.24
    assert se["total"] == 13423.07
    it = out["income_tax"]
    assert it["agi"] == 88288.46
    assert it["qbi_deduction"] == 14437.69  # 20% x (88,288.46 - 16,100)
    assert it["taxable_income"] == 57750.77
    assert it["federal_income_tax"] == 7417.17  # 1,240 + 4,560 + 1,617.17
    assert it["marginal_rate_pct"] == 22.0
    assert out["total_tax"] == 20840.24
    assert out["quarterly_payment"] == 5210.06
    assert out["set_aside_pct_of_net"] == 21.9
    assert out["combined_marginal_rate_pct"] == 30.5  # not 22 + 14.13: half-SE and QBI shrink the income-tax bite
    assert out["for_deduction_value"] == {**out["for_deduction_value"], "marginal_income_rate_pct": 16.36, "se_rate_effective_pct": 14.13}
    assert "2026" in out["defaults_used"][0] and "verify" in out["defaults_used"][0]
    assert "not tax advice" in out["scope_note"]


def test_quarterly_estimate_wage_base_and_overrides():
    out = call("quarterly_estimate", net_se_income=200000, filing_status="single", w2_wages=50000, w2_withholding=6000, apply_qbi_deduction=False)
    # SS room = 184500 - 50000 = 134500 → 12.4% = 16678.00; Medicare on full base; surtax on SE above (200k - wages)
    assert out["se_tax"]["social_security"] == 16678.0
    assert out["se_tax"]["additional_medicare"] == 312.3  # (184,700 - 150,000) x 0.9%
    assert out["se_tax"]["half_se_deduction"] == round((16678.0 + 5356.3) / 2, 2)  # surtax not deductible
    rich = call("quarterly_estimate", net_se_income=100000, w2_wages=250000, apply_qbi_deduction=False)
    assert rich["se_tax"]["additional_medicare"] == 831.15  # wages already over 200k: surtax on all 92,350 of SE base, not on wages too
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
    assert by["mileage"]["deductible"] == 2900.0  # 4,000 x 72.5¢ (2026 Jan-Jun default)
    assert by["home_office"]["deductible"] == 1500.0 and "capped" in by["home_office"]["rule"]
    assert by["meals"]["deductible"] == 1400.0
    assert by["phone"]["deductible"] == 720.0
    assert by["entertainment"]["deductible"] == 0.0
    assert by["health_insurance"]["tax_saved"] == 1420.35  # income tax only: 6000 x 22% / (1 - 14.13%/2)
    assert by["meals"]["tax_saved"] == 505.82  # 1400 × 36.13%
    with pytest.raises(ToolError):
        call("deduction_value", expenses=[{"type": "yacht", "amount": 1}], marginal_income_rate_pct=22)


def test_payment_deadlines_weekend_rollover():
    out = call("payment_deadlines", tax_year=2026, as_of="2026-09-27", annual_amount=20000)
    assert out["quarters_elapsed"] == 3
    assert out["next"]["quarter"] == 4 and out["next"]["due"] == "2027-01-15" and out["next"]["days_remaining"] == 110
    assert out["next"]["amount"] == 5000.0
    y28 = call("payment_deadlines", tax_year=2028, as_of="2026-09-27")
    # Apr 15 2028 is a Saturday and Emancipation Day (Sun Apr 16) is observed Mon Apr 17 -> Tue Apr 18
    assert y28["deadlines"][0]["due"] == "2028-04-18" and y28["deadlines"][0]["adjusted_from_15th"] is True
    assert y28["deadlines"][3]["due"] == "2029-01-16"  # Jan 15 2029 is MLK Day
    # IRS-published dates: 2022 Q1 due Apr 18 2022; 2023 Q4 due Jan 16 2024
    assert call("payment_deadlines", tax_year=2022, as_of="2022-01-01")["deadlines"][0]["due"] == "2022-04-18"
    assert call("payment_deadlines", tax_year=2023, as_of="2023-01-01")["deadlines"][3]["due"] == "2024-01-16"
    assert call("payment_deadlines", tax_year=2022, as_of="2022-01-01")["deadlines"][3]["due"] == "2023-01-17"  # IRS: "Final 2022 quarterly estimated tax payment due January 17"
    with pytest.raises(ToolError):
        call("payment_deadlines", tax_year=1900)
