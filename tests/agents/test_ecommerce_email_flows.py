"""Email Flows tools — schedules, purchase-cycle maths, subject lint, diagnostics."""

import pytest

from hundred.agents.ecommerce.email_flows import AGENT as A
from hundred.core import ToolError


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_flow_schedule_abandoned_checkout_quiet_hours():
    out = call("flow_schedule", flow="abandoned_checkout", trigger_at="2026-10-03T22:15")
    e = out["emails"]
    assert [x["delay_hours"] for x in e] == [1, 24, 72]
    assert e[0]["send_at_local"].startswith("2026-10-03 23:15") and "time-sensitive" in e[0]["adjustment"]
    assert e[1]["send_at_local"].startswith("2026-10-05 10:00")  # 24h lands 22:15 (quiet) → next sending day 10:00
    assert e[2]["send_at_local"].startswith("2026-10-07 10:00")
    assert e[0]["incentive_allowed"] is False and e[2]["incentive_allowed"] is True


def test_flow_schedule_keeps_daytime_hour_and_uses_cycle():
    w = call("flow_schedule", flow="welcome", trigger_at="2026-10-03T14:00")
    assert [x["send_at_local"][:16] for x in w["emails"]] == ["2026-10-03 14:00", "2026-10-05 14:00", "2026-10-07 14:00", "2026-10-10 14:00", "2026-10-17 14:00"]
    wb = call("flow_schedule", flow="win_back", trigger_at="2026-10-03T14:00", cycle_days=40)
    assert [x["delay_hours"] for x in wb["emails"]] == [60 * 24, 78 * 24, 120 * 24]  # p75≈1.5×cycle, then ×1.3, ×2
    pp = call("flow_schedule", flow="post_purchase", trigger_at="2026-10-03T14:00", delivery_days=4, cycle_days=30)
    assert pp["emails"][2]["delay_hours"] == 4 * 24 + 72  # review request = delivered + 3 days
    assert pp["emails"][4]["delay_hours"] == 30 * 0.8 * 24


def test_flow_schedule_rejects_unknown_flow_and_bad_time():
    with pytest.raises(ToolError):
        call("flow_schedule", flow="cart_thing", trigger_at="2026-10-03T14:00")
    with pytest.raises(ToolError):
        call("flow_schedule", flow="welcome", trigger_at="next tuesday")


def test_purchase_cycle_offsets_from_gaps():
    customers = [{"customer": i, "order_dates": ["2026-01-01", "2026-01-31", "2026-03-02"]} for i in range(6)]  # gaps 30, 30
    customers += [{"customer": 100 + i, "order_dates": ["2026-01-01", "2026-02-15"]} for i in range(2)]  # gap 45
    customers += [{"customer": 200, "order_dates": ["2026-02-02"]}]
    out = call("purchase_cycle", customers=customers)
    assert out["gaps_observed"] == 14 and out["reliable"] is True
    assert out["median_gap_days"] == 30.0
    assert out["repeat_rate_pct"] == round(100 * 8 / 9, 1)
    assert out["offsets_days"]["replenishment_reminder"] == 24
    assert out["offsets_days"]["sunset"] == 90
    assert out["offsets_days"]["winback_start"] == round(out["p75_gap_days"])


def test_purchase_cycle_fallback_and_bad_dates():
    out = call("purchase_cycle", customers=[{"customer": 1, "order_dates": ["2026-01-01", "2026-02-01"]}], category_default_days=45)
    assert out["reliable"] is False and out["median_gap_days"] == 45.0
    with pytest.raises(ToolError):
        call("purchase_cycle", customers=[{"customer": 1, "order_dates": ["Jan 1st"]}])


def test_subject_line_check_scores_and_flags():
    out = call(
        "subject_line_check",
        subjects=["Still thinking it over?", "FREE SHIPPING!!! Act now and save $$$ on your order today", "Your cart, {{ first_name }}"],
        preview_texts=["We saved your bag for 24 hours — plus what other customers say", "View in browser", ""],
    )
    good, bad, tok = out["results"]
    assert good["score"] == 100 and "question" in good["strengths"]
    assert bad["score"] < 40
    assert any("spam triggers" in i and "act now" in i for i in bad["issues"])
    assert any("ALL CAPS" in i for i in bad["issues"])
    assert any("boilerplate" in i for i in bad["preview_issues"])
    assert any("personalisation token" in i for i in tok["issues"])
    assert out["best"] == "Still thinking it over?"


def test_subject_line_check_rejects_empty_list():
    with pytest.raises(ToolError):
        call("subject_line_check", subjects=[])


def test_flow_diagnostics_rates_and_weakest_step():
    out = call("flow_diagnostics", flows=[{"name": "AC", "type": "abandoned_cart", "sent": 4100, "opens": 1650, "clicks": 210, "orders": 61, "revenue": 3900, "unsubscribes": 22, "spam_complaints": 2}])
    f = out["flows"][0]
    assert f["open_rate_pct"] == round(100 * 1650 / 4100, 1)
    assert f["click_to_open_pct"] == round(100 * 210 / 1650, 1)
    assert f["placed_order_rate_pct"] == 1.49
    assert f["revenue_per_recipient"] == round(3900 / 4100, 2)
    assert f["unsubscribe_rate_pct"] == 0.54
    assert f["fix_first"] == "list health"
    assert any("placed-order" in p for p in f["problems"])
    assert f["upside_if_at_benchmark_low"] == round((0.03 - 61 / 4100) * 4100 * (3900 / 61), 2)


def test_flow_diagnostics_rejects_inconsistent_counts():
    with pytest.raises(ToolError):
        call("flow_diagnostics", flows=[{"name": "x", "type": "welcome", "sent": 100, "opens": 150, "clicks": 1, "orders": 0}])


def test_flow_revenue_model_gap():
    out = call("flow_revenue_model", flow="abandoned_checkout", monthly_triggers=2000, aov=62, current_placed_order_rate_pct=1.5, gross_margin_pct=55)
    assert out["revenue_per_month_at_benchmark"] == [3720.0, 6200.0]
    assert out["current_revenue_per_month"] == 1860.0
    assert out["gap_to_benchmark_low"] == 1860.0
    assert out["gap_contribution"] == 1023.0
    assert sum(e["share_pct"] for e in out["per_email_revenue_split_at_low"]) == 100
    with pytest.raises(ToolError):
        call("flow_revenue_model", flow="sunset", monthly_triggers=10, aov=5)
