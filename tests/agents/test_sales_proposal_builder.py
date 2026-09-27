"""Proposal Builder tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("proposal-builder")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_pricing_table_totals_discount_tax_and_per_seat():
    out = call(
        "pricing_table",
        line_items=[{"name": "Seats", "qty": 25, "unit_price": 90, "period": "month"}, {"name": "Onboarding", "qty": 1, "unit_price": 2500, "period": "one_time"}],
        discount_pct=15,
        tax_rate_pct=20,
        term_months=12,
        seats=25,
    )
    assert out["recurring_subtotal_for_term"] == 27000.0
    assert out["discount_amount"] == 4050.0
    assert out["subtotal_after_discount"] == 25450.0
    assert out["tax_amount"] == 5090.0
    assert out["grand_total"] == 30540.0
    assert out["recurring_per_month_after_discount"] == 1912.5
    assert out["per_seat_per_month"] == 76.5
    assert out["one_time_subtotal"] == 2500.0


def test_pricing_table_bad_input():
    with pytest.raises(ToolError):
        call("pricing_table", line_items=[])
    with pytest.raises(ToolError):
        call("pricing_table", line_items=[{"name": "x", "qty": 1, "unit_price": 10, "period": "weekly"}])
    with pytest.raises(ToolError):
        call("pricing_table", line_items=[{"name": "x", "qty": 1, "unit_price": 10}], discount_pct=120)


def test_tier_comparison_steps_and_warnings():
    out = call("tier_comparison", tiers=[{"name": "Good", "price": 4000, "units": 10}, {"name": "Better", "price": 6000, "units": 20, "recommended": True}, {"name": "Best", "price": 11000, "units": 50}])
    tiers = out["tiers"]
    assert tiers[1]["step_up_from_previous"] == 2000.0 and tiers[1]["step_up_pct"] == 50.0
    assert tiers[2]["multiple_of_lowest"] == 2.75
    assert tiers[2]["per_unit"] == 220.0
    assert out["recommended"] == "Better" and out["warnings"] == []
    weak = call("tier_comparison", tiers=[{"name": "A", "price": 100}, {"name": "B", "price": 110}, {"name": "C", "price": 120}])
    assert any("anchor is too weak" in w for w in weak["warnings"]) and any("nobody upgrades" in w for w in weak["warnings"])


def test_tier_comparison_bad_input():
    with pytest.raises(ToolError):
        call("tier_comparison", tiers=[{"name": "only", "price": 10}])
    with pytest.raises(ToolError):
        call("tier_comparison", tiers=[{"name": "a", "price": 0}, {"name": "b", "price": 5}])


def test_milestone_timeline_business_days_and_payments():
    out = call(
        "milestone_timeline",
        start_date="2026-10-03",  # Saturday → Monday 10-05
        milestones=[{"name": "Discovery", "business_days": 10, "payment_pct": 30}, {"name": "Design", "business_days": 20, "payment_pct": 40}, {"name": "Build", "business_days": 50, "payment_pct": 30}],
        total_price=48000,
    )
    assert out["start"] == "2026-10-05"
    ms = out["milestones"]
    assert (ms[0]["start"], ms[0]["end"]) == ("2026-10-05", "2026-10-16")
    assert (ms[1]["start"], ms[1]["end"]) == ("2026-10-19", "2026-11-13")
    assert ms[2]["end"] == "2027-01-22" and out["finish"] == "2027-01-22"
    assert out["total_business_days"] == 80
    assert out["payment_total_pct"] == 100.0 and out["issues"] == []
    assert out["payment_schedule"][-1]["amount"] == 14400.0
    bad = call("milestone_timeline", start_date="2026-10-05", milestones=[{"name": "A", "business_days": 5, "payment_pct": 50}])
    assert any("sum to 50" in i for i in bad["issues"])


def test_milestone_timeline_holidays_and_bad_input():
    out = call("milestone_timeline", start_date="2026-11-23", milestones=[{"name": "A", "business_days": 4, "payment_pct": 100}], holidays=["2026-11-26"])
    assert out["milestones"][0]["end"] == "2026-11-27"
    with pytest.raises(ToolError):
        call("milestone_timeline", start_date="2026-10-05", milestones=[])
    with pytest.raises(ToolError):
        call("milestone_timeline", start_date="2026-10-05", milestones=[{"name": "A", "business_days": -3}])


FULL = """# Proposal: Faster dispatch for Acme
Valid until 2026-10-30
## Summary
Acme loses 30 hours a week to spreadsheet routing. We will replace it in 8 weeks.
## Your situation
Dispatch is manual and costs $20,000 a month in overtime.
## Objectives
1. Cut dispatch time by 25% by 2026-12-15.
## Approach & deliverables
Discovery, design, build. Acceptance: routes generated in under 5 minutes.
## Timeline
Discovery 2026-10-05 to 2026-10-16; build to 2027-01-22.
## Investment
| | Good | Better | Best |
| Price | $32,000 | $48,000 | $75,000 |
## Why us
Northwind cut dispatch time 22% with us.
## Assumptions & exclusions
Data migration from the current spreadsheet is included; hardware is not included.
## Terms
Net 30. 30% deposit at signature.
## Next step
Sign the order form by 2026-10-15 and we start on 2026-10-19.
""" + "This paragraph adds detail about the phases and the team. " * 20


def test_proposal_audit_full_and_thin():
    good = call("proposal_audit", proposal_text=FULL, deal_value=48000)
    assert good["sections_missing"] == []
    assert good["has_validity_date"] is True
    assert "sign" in good["closing_ctas"]
    assert good["score"] >= 80 and good["ready_to_send"] is True
    thin = call("proposal_audit", proposal_text="# Proposal\n## Summary\nWe hope to build your site.\n## Investment\n$48,000\n", deal_value=48000)
    assert thin["score"] < 40 and thin["ready_to_send"] is False
    assert "next_step" in thin["sections_missing"] and thin["hedges"] == ["we hope to"]


def test_proposal_audit_bad_input():
    with pytest.raises(ToolError):
        call("proposal_audit", proposal_text="   ")
