"""Unit Economics tools — LTV/CAC, retention, cohorts, contribution, efficiency."""

import pytest

from hundred.agents.finance.unit_economics import AGENT as A
from hundred.core import ToolError


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_ltv_cac_gross_margin_basis():
    out = call("ltv_cac", arpa_monthly=220, gross_margin_pct=78, monthly_churn_pct=2.1, cac=2900)
    assert out["gross_profit_per_month"] == 171.6
    assert out["customer_lifetime_months"] == 47.6
    assert out["ltv_gross_margin"] == 8171.43
    assert out["ltv_to_cac"] == 2.82
    assert out["cac_payback_months"] == 16.9
    assert "Churn is the constraint" in out["verdict"]
    healthy = call("ltv_cac", arpa_monthly=500, gross_margin_pct=80, monthly_churn_pct=1, cac=3000, segment="smb", annual_discount_rate_pct=10)
    assert healthy["ltv_to_cac"] == 13.33
    assert healthy["ltv_discounted"] < healthy["ltv_gross_margin"]
    capped = call("ltv_cac", arpa_monthly=100, gross_margin_pct=80, monthly_churn_pct=1, cac=500, monthly_expansion_pct=2)
    assert capped["lifetime_capped_at_120_months"] is True
    with pytest.raises(ToolError):
        call("ltv_cac", arpa_monthly=100, gross_margin_pct=150, monthly_churn_pct=1, cac=500)


def test_retention_metrics_grr_nrr_quick_ratio():
    out = call("retention_metrics", starting_revenue=2400000, churned=180000, contraction=60000, expansion=410000, new=900000, starting_logos=200, churned_logos=12)
    assert out["grr_pct"] == 90.0
    assert out["nrr_pct"] == 107.1
    assert out["quick_ratio"] == 5.46
    assert out["ending_revenue"] == 3470000.0
    assert out["logo_churn_pct"] == 6.0
    leaky = call("retention_metrics", starting_revenue=100000, churned=25000, expansion=30000)
    assert leaky["nrr_pct"] == 105.0 and any("GRR" in f for f in leaky["flags"])
    with pytest.raises(ToolError):
        call("retention_metrics", starting_revenue=100, churned=200)


def test_cohort_analysis_curve_and_shape():
    out = call("cohort_analysis", cohorts=[{"cohort": "a", "values": [100, 80, 70, 65, 63, 62]}, {"cohort": "b", "values": [200, 150, 130, 125, 122]}])
    assert out["cohorts"][1]["retention_pct"][1] == 75.0
    assert out["retention_at"]["m1"] == 77.5
    assert out["retention_at"]["m3"] == 63.8
    assert out["late_slope_pts_per_month"] == -1.83
    assert out["shape"].startswith("still falling")
    flat = call("cohort_analysis", cohorts=[{"cohort": "a", "values": [100, 70, 60, 58, 57.5, 57.2, 57]}])
    assert flat["shape"].startswith("flattening")
    with pytest.raises(ToolError):
        call("cohort_analysis", cohorts=[{"cohort": "a", "values": [0, 1]}])


def test_contribution_margin_and_breakeven():
    out = call("contribution_margin", price=50, variable_costs=[{"name": "hosting", "amount": 4}, {"name": "commission", "pct": 10}], fixed_costs_monthly=20000, payment_fee_pct=2.9, units_per_month=800)
    assert out["variable_cost_per_unit"] == 10.45
    assert out["contribution_per_unit"] == 39.55
    assert out["contribution_margin_pct"] == 79.1
    assert out["breakeven_units_monthly"] == 506.0
    assert out["breakeven_revenue_monthly"] == 25300.0
    assert out["operating_profit_monthly"] == 11640.0
    neg = call("contribution_margin", price=10, variable_costs=[{"name": "x", "amount": 12}])
    assert "Negative contribution" in neg["verdict"]
    with pytest.raises(ToolError):
        call("contribution_margin", price=0, variable_costs=[])


def test_efficiency_metrics():
    out = call("efficiency_metrics", net_new_arr=500000, sales_marketing_spend=800000, net_burn=900000, revenue_growth_pct=65, profit_margin_pct=-30)
    assert out["magic_number"] == 2.5
    assert out["burn_multiple"] == 1.8
    assert out["rule_of_40"] == 35.0
    assert "missed by 5.0" in out["verdict"]
    yearly = call("efficiency_metrics", net_new_arr=500000, sales_marketing_spend=800000, period="year")
    assert yearly["magic_number"] == 0.63
    with pytest.raises(ToolError):
        call("efficiency_metrics", net_new_arr=1, sales_marketing_spend=0)
