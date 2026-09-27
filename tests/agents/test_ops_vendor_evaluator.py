"""Vendor Evaluator tools — RFP scoring, TCO, contract risk, SLA math."""

import pytest

from hundred.agents.ops import vendor_evaluator
from hundred.core import ToolError

A = vendor_evaluator.AGENT


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_score_rfp_knockouts_and_weighted_totals():
    out = call(
        "score_rfp",
        vendors=[
            {"name": "Acme", "scores": {"Features": 5, "Security": 3, "Price": 2}, "must_haves": {"SSO": True, "SOC2": True}},
            {"name": "Beta", "scores": {"Features": 3, "Security": 5, "Price": 5}, "must_haves": {"SSO": False, "SOC2": True}},
            {"name": "Gamma", "scores": {"Features": 4, "Security": 4, "Price": 4}, "must_haves": {"SSO": "yes"}},
        ],
        criteria=[{"name": "Features", "weight": 50, "category": "Functionality"}, {"name": "Security", "weight": 30, "category": "Security"}, {"name": "Price", "weight": 20, "category": "Cost"}],
        must_haves=["SSO", "SOC2"],
    )
    assert out["knocked_out"] == [{"vendor": "Beta", "failed": ["SSO"]}]
    assert [r["vendor"] for r in out["ranking"]] == ["Gamma", "Acme"]
    acme = next(r for r in out["all_vendors"] if r["vendor"] == "Acme")
    assert acme["score"] == 76.0  # 0.5*5 + 0.3*3 + 0.2*2 = 3.8 / 5
    assert acme["by_category"]["Functionality"]["points"] == 50.0
    gamma = out["ranking"][0]
    assert gamma["score"] == 80.0 and gamma["unverified_must_haves"] == ["SOC2"]
    assert "Unverified" in out["verdict"]
    with pytest.raises(ToolError, match="no score"):
        call("score_rfp", vendors=[{"name": "X", "scores": {"A": 1}}], criteria=[{"name": "A"}, {"name": "B"}])


def test_calculate_tco_growth_escalator_npv():
    out = call(
        "calculate_tco",
        vendors=[
            {"name": "Cheap sticker", "per_seat_month": 40, "seats": 100, "seat_growth_pct_yr": 0, "one_time": 30000, "internal_hours_per_month": 40},
            {"name": "All-in", "per_seat_month": 55, "seats": 100, "seat_growth_pct_yr": 0, "one_time": 0, "internal_hours_per_month": 5},
        ],
        years=3, discount_rate_pct=10, hourly_rate=100, billing="arrears",
    )
    by = {v["vendor"]: v for v in out["ranking"]}
    # Cheap: sub 48k/yr + internal 48k/yr = 96k/yr, + 30k y1 -> 318k. All-in: 66k + 6k = 72k/yr -> 216k
    assert by["Cheap sticker"]["total_nominal"] == 318000 and by["All-in"]["total_nominal"] == 216000
    assert by["Cheap sticker"]["year_1"] == 126000
    assert by["All-in"]["npv"] == round(72000 / 1.1 + 72000 / 1.21 + 72000 / 1.331)
    assert by["All-in"]["rank"] == 1 and by["Cheap sticker"]["delta_vs_cheapest"] > 0
    assert "lowest sticker price but not the lowest TCO" in out["verdict"]
    adv = call("calculate_tco", vendors=[{"name": "All-in", "per_seat_month": 55, "seats": 100, "internal_hours_per_month": 5}], years=3, discount_rate_pct=10, hourly_rate=100)
    # default billing = annual in advance: subscription at t=0,1,2; internal labour at year ends
    assert adv["ranking"][0]["npv"] == round(66000 * (1 + 1 / 1.1 + 1 / 1.21) + 6000 * (1 / 1.1 + 1 / 1.21 + 1 / 1.331))
    grow = call("calculate_tco", vendors=[{"name": "G", "per_seat_month": 10, "seats": 100, "seat_growth_pct_yr": 20, "annual_increase_pct": 5}], years=2, discount_rate_pct=0)
    y2 = grow["ranking"][0]["by_year"][1]
    assert y2["seats"] == 120.0 and y2["subscription"] == round(10 * 12 * 120 * 1.05)
    with pytest.raises(ToolError):
        call("calculate_tco", vendors=[{"name": "X", "per_seat_month": -5}])


def test_contract_risk_check_deadline_and_flags():
    out = call(
        "contract_risk_check",
        terms={"start_date": "2025-11-15", "term_months": 12, "auto_renew": True, "notice_days": 90, "price_cap_pct": None, "sla_uptime_pct": 99.5, "sla_credits": False, "data_export": True, "liability_cap_months": 6, "soc2": True, "dpa": True},
        today="2026-08-01",
        annual_fees=120000,
    )
    assert out["renewal_date"] == "2026-11-15"
    # term's last day is 2026-11-14; 90 days before it is 2026-08-16 (counting from the renewal date would be a day late)
    assert out["term_end_date"] == "2026-11-14"
    assert out["notice_deadline"] == "2026-08-16" and out["days_until_notice_deadline"] == 15
    assert out["recommended_send_by"] == "2026-08-12"
    issues = " ".join(f["issue"] for f in out["flags"])
    assert "90-day notice" in issues and "No cap" in issues and "Liability capped at 6" in issues and "$60,000" in issues
    assert out["flags"][0]["severity"] == "high"
    assert out["risk_level"] in ("MEDIUM", "HIGH")
    with pytest.raises(ToolError):
        call("contract_risk_check", terms={"renewal_date": "next year"})


def test_sla_downtime_minutes_and_credits():
    out = call("sla_downtime", uptime_pct=99.9, monthly_fee=10000, credit_tiers=[{"below_pct": 99.9, "credit_pct": 10}, {"below_pct": 99.0, "credit_pct": 25}], actual_downtime_minutes=600, outage_cost_per_hour=5000)
    assert out["allowed_downtime_minutes"]["per_month"] == 43.8
    assert out["allowed_downtime_minutes"]["per_year"] == 526.0
    assert out["actual"]["breach"] is True and out["actual"]["credit_pct"] == 25 and out["actual"]["credit_usd"] == 2500.0
    assert out["actual"]["your_outage_cost_usd"] == 50000.0 and out["actual"]["credit_covers_pct_of_loss"] == 5.0
    assert out["actual"]["over_allowance_minutes"] == 556.2
    with pytest.raises(ToolError):
        call("sla_downtime", uptime_pct=50)


def test_bad_arguments_raise_clean_error():
    with pytest.raises(ToolError):
        A.get_tool("score_rfp").call({"vendors": "Acme", "criteria": []})


def test_missed_notice_window_gives_next_cycle_deadline():
    out = call("contract_risk_check", terms={"start_date": "2025-11-15", "term_months": 12, "auto_renew": True, "notice_days": 60}, today="2026-09-27")
    assert out["notice_deadline"] == "2026-09-15" and out["days_until_notice_deadline"] == -12
    assert out["next_renewal_date"] == "2027-11-15" and out["next_notice_deadline"] == "2027-09-15"


def test_sla_breach_measured_over_the_actual_calendar_month():
    tiers = [{"below_pct": 99.5, "credit_pct": 5}, {"below_pct": 99.0, "credit_pct": 10}]
    avg = call("sla_downtime", uptime_pct=99.5, monthly_fee=2400, credit_tiers=tiers, actual_downtime_minutes=218)
    nov = call("sla_downtime", uptime_pct=99.5, monthly_fee=2400, credit_tiers=tiers, actual_downtime_minutes=218, month="2026-11")
    assert avg["actual"]["breach"] is False  # 218 < 219.2 min in an average month
    assert nov["allowed_downtime_minutes"]["this_month"] == 216.0 and nov["actual"]["breach"] is True and nov["actual"]["credit_usd"] == 120.0
