"""Budget Coach tools — exact amortisation, payoff ordering, never-pays-off detection."""

import pytest

from hundred.agents.finance.budget_coach import AGENT as A
from hundred.core import ToolError


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_budget_50_30_20_buckets_and_gaps():
    out = call(
        "budget_50_30_20",
        take_home_monthly=5200,
        expenses=[
            {"name": "rent", "amount": 1800, "bucket": "needs"},
            {"name": "car", "amount": 420, "bucket": "needs"},
            {"name": "groceries", "amount": 600, "bucket": "needs"},
            {"name": "eating out", "amount": 450, "bucket": "wants"},
            {"name": "subscriptions", "amount": 90, "bucket": "wants"},
            {"name": "savings", "amount": 200, "bucket": "savings"},
        ],
    )
    assert out["buckets"]["needs"]["actual"] == 2820.0
    assert out["buckets"]["needs"]["actual_pct"] == 54.2
    assert out["buckets"]["needs"]["gap"] == 220.0  # 2820 - 2600
    assert out["surplus"] == 1640.0
    assert out["largest_wants"][0]["name"] == "eating out"
    assert "fixed-cost" in out["verdict"]


def test_budget_rejects_bad_bucket_and_targets():
    with pytest.raises(ToolError):
        call("budget_50_30_20", take_home_monthly=5000, expenses=[{"name": "x", "amount": 10, "bucket": "fun"}])
    with pytest.raises(ToolError):
        call("budget_50_30_20", take_home_monthly=5000, expenses=[{"name": "x", "amount": 10, "bucket": "needs"}], targets_pct={"needs": 60, "wants": 30, "savings": 30})


def test_loan_payment_matches_textbook_mortgage():
    out = call("loan_payment", principal=300000, apr=6.5, months=360, extra_payment=200)
    assert out["monthly_payment"] == 1896.20
    assert out["first_month_interest"] == 1625.0
    assert out["with_extra"]["months"] == 277
    assert out["with_extra"]["interest_saved"] > 100000


def test_loan_payment_zero_rate():
    out = call("loan_payment", principal=1200, apr=0, months=12)
    assert out["monthly_payment"] == 100.0
    assert out["total_interest"] == 0.0


def test_debt_payoff_avalanche_vs_snowball_and_minimums():
    debts = [
        {"name": "Card A", "balance": 4200, "apr": 24.99, "min_payment": 120},
        {"name": "Card B", "balance": 1100, "apr": 19.9, "min_payment": 35},
        {"name": "Card C", "balance": 8500, "apr": 17, "min_payment": 210},
    ]
    av = call("debt_payoff", debts=debts, extra_monthly=335, method="avalanche", start_date="2026-10-01")
    sn = call("debt_payoff", debts=debts, extra_monthly=335, method="snowball", start_date="2026-10-01")
    assert av["attack_order"] == ["Card A", "Card B", "Card C"]
    assert sn["attack_order"] == ["Card B", "Card A", "Card C"]
    assert av["months_to_debt_free"] == 28
    assert av["debt_free_date"] == "2029-02"
    assert av["total_interest"] < sn["total_interest"]
    assert av["minimums_only"]["months"] == 64
    assert av["interest_saved_vs_minimums"] > 5000


def test_debt_payoff_never_pays_off():
    out = call("debt_payoff", debts=[{"name": "A", "balance": 4200, "apr": 24.99, "min_payment": 50}])
    assert out["pays_off"] is False
    assert out["monthly_interest_now"] == 87.47
    assert out["min_extra_to_progress"] == 37.48


def test_debt_payoff_rejects_bad_apr():
    with pytest.raises(ToolError):
        call("debt_payoff", debts=[{"name": "A", "balance": 100, "apr": 500, "min_payment": 10}])


def test_savings_goal_both_directions():
    months = call("savings_goal", target=10000, current=1000, monthly_contribution=500, apy=4.5)
    assert months["months"] == 18
    assert months["interest_earned"] == 362.39
    contrib = call("savings_goal", target=10000, current=1000, apy=4.5, months=12)
    assert contrib["required_monthly"] == 730.91
    with pytest.raises(ToolError):
        call("savings_goal", target=0)


def test_debt_to_income_28_36():
    out = call("debt_to_income", gross_monthly_income=9000, housing_payment=2400, other_debt_payments=750)
    assert out["front_end_pct"] == 26.7
    assert out["back_end_pct"] == 35.0
    assert out["room_for_new_payment"] == 90.0
    stretch = call("debt_to_income", gross_monthly_income=9000, housing_payment=2400, other_debt_payments=750, proposed_new_payment=400)
    assert stretch["with_proposed"]["back_end_pct"] == 39.4
    assert "Stretch" in stretch["verdict"]
    with pytest.raises(ToolError):
        call("debt_to_income", gross_monthly_income=0, housing_payment=100)
