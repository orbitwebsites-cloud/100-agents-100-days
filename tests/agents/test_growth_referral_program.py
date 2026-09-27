"""Referral Program Designer tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("referral-program")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_viral_coefficient_projection():
    out = call("viral_coefficient", invites_per_user=1.8, invite_conversion_rate=12, seed_users=2000, cycle_time_days=10, horizon_days=90)
    assert out["k_factor"] == 0.216
    assert out["amplification"] == 1.28
    assert out["cycles_in_horizon"] == 9
    assert out["projection"][0] == {"cycle": 1, "day": 10, "referred_this_cycle": 432, "organic_this_cycle": 0, "total_users": 2432}
    assert 2540 <= out["users_at_horizon"] <= 2560
    assert "healthy" in out["verdict"]
    viral = call("viral_coefficient", invites_per_user=4, invite_conversion_rate=0.3, seed_users=100, cycle_time_days=7, horizon_days=28)
    assert viral["k_factor"] == 1.2 and viral["amplification"] is None and viral["doubling_cycles"] == 3.8
    with pytest.raises(ToolError):
        call("viral_coefficient", invites_per_user=-1, invite_conversion_rate=0.1)


def test_reward_economics_works_and_fails():
    ok = call("reward_economics", arpu_monthly=29, gross_margin_pct=70, monthly_churn_pct=4, paid_cac=180, referrer_reward=30, referee_reward=30)
    assert ok["ltv"] == 507.5
    assert ok["contribution_per_month"] == 20.3
    assert ok["cost_per_referred_customer"] == 60.0
    assert ok["payback_months"] == 2.96
    assert ok["reward_ceiling"]["recommended_max_total"] == 169.17
    assert ok["checks"] == {"below_paid_cac": True, "within_ltv_third": True, "payback_under_6_months": True}
    assert ok["verdict"].startswith("Economics work")
    bad = call("reward_economics", arpu_monthly=29, gross_margin_pct=0.7, monthly_churn_pct=0.04, paid_cac=180, referrer_reward=150, referee_reward=100, reward_conversion_rate=0.5)
    assert bad["cost_per_referred_customer"] == 500.0
    assert bad["verdict"].startswith("Economics do not work")
    assert any("paid CAC" in f for f in bad["fixes"]) and any("first payment" in f for f in bad["fixes"])
    override = call("reward_economics", arpu_monthly=100, gross_margin_pct=50, monthly_churn_pct=0, paid_cac=0, referrer_reward=50, ltv_override=1200)
    assert override["ltv"] == 1200 and override["expected_lifetime_months"] == 24.0
    with pytest.raises(ToolError):
        call("reward_economics", arpu_monthly=29, gross_margin_pct=70, monthly_churn_pct=0, paid_cac=180, referrer_reward=30)


def test_referral_funnel_finds_weakest_step():
    out = call("referral_funnel", active_users=10000, share_rate=8, invite_click_rate=0.25, click_signup_rate=0.15)
    assert out["funnel"] == {"sharers": 800.0, "invites": 2400.0, "clicks": 600.0, "signups": 90.0, "qualified": 40.5}
    assert out["assumed_from_benchmark"] == ["invites_per_sharer", "signup_qualified_rate"]
    assert out["fix_first"] == "click_signup_rate"
    assert out["implied_k"] == 0.004
    assert out["upside_by_step"][0]["lift_to_top_of_range_adds"] == 54
    with pytest.raises(ToolError):
        call("referral_funnel", active_users=0)


def test_compare_rewards_ranks_by_net_value():
    out = call("compare_rewards", structures=[{"name": "one-sided $20", "referrer_reward": 20, "expected_conversion": 0.08}, {"name": "two-sided 20/20", "referrer_reward": 20, "referee_reward": 20, "expected_conversion": 0.14}, {"name": "huge 200/200", "referrer_reward": 200, "referee_reward": 200, "expected_conversion": 0.3}, {"name": "signup-paid", "referrer_reward": 10, "referee_reward": 10, "expected_conversion": 0.1, "paid_on": "signup", "signup_to_paid": 0.3}], ltv=507, paid_cac=180, contribution_per_month=20.3)
    ranked = [(r["name"], r["rank"]) for r in out["ranked"]]
    assert ranked[0] == ("two-sided 20/20", 1)
    assert ranked[-1] == ("huge 200/200", 4)  # over LTV/3 sinks regardless of conversion
    signup = next(r for r in out["ranked"] if r["name"] == "signup-paid")
    assert signup["cost_per_customer"] == 66.67  # (10+10)/0.3 — paying at signup triples the cost
    assert signup["net_value_per_100_invites"] == 4403.3
    assert out["ranked"][0]["net_value_per_100_invites"] == 6538.0
    assert out["recommended"] == "two-sided 20/20"
    with pytest.raises(ToolError):
        call("compare_rewards", structures=[{"name": "x"}], ltv=100, paid_cac=10)
