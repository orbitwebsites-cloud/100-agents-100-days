"""Support Desk tools — business-hour SLA math, triage, macro lint, tone, metrics."""

import pytest

from hundred.agents.ecommerce.support_desk import AGENT as A
from hundred.core import ToolError


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_sla_deadline_business_hours_across_weekend():
    # Fri 16:40 + 8 business hours (9-18): 1h20 Fri + 6h40 Mon → Mon 15:40
    out = call("sla_deadline", created_at="2026-10-02T16:40", sla_hours=8, now="2026-10-05T12:00")
    assert out["due_at"].startswith("2026-10-05 15:40")
    assert out["business_hours_elapsed"] == 4.33
    assert out["business_hours_remaining"] == 3.67
    assert out["breached"] is False and out["status"] == "on track"


def test_sla_deadline_breach_holiday_and_calendar_clock():
    late = call("sla_deadline", created_at="2026-10-02T16:40", sla_hours=8, responded_at="2026-10-05T16:00")
    assert late["breached"] is True and late["business_hours_to_respond"] == 8.33 and late["over_by_hours"] == 0.33
    hol = call("sla_deadline", created_at="2026-10-02T16:40", sla_hours=8, holidays=["2026-10-05"], now="2026-10-05T12:00")
    assert hol["due_at"].startswith("2026-10-06 15:40")
    p1 = call("sla_deadline", created_at="2026-10-02T16:40", priority="P1", calendar_hours=True)
    assert p1["sla_hours"] == 1 and p1["due_at"].startswith("2026-10-02 17:40")
    after_hours = call("sla_deadline", created_at="2026-10-03T11:00", sla_hours=2)  # Saturday → Monday 11:00
    assert after_hours["due_at"].startswith("2026-10-05 11:00")


def test_sla_deadline_rejects_bad_input():
    with pytest.raises(ToolError):
        call("sla_deadline", created_at="last friday", sla_hours=8)
    with pytest.raises(ToolError):
        call("sla_deadline", created_at="2026-10-02T16:40", priority="P9")
    with pytest.raises(ToolError):
        call("sla_deadline", created_at="2026-10-02T16:40", business_hours_start=18, business_hours_end=9)


def test_triage_tickets_categories_priorities_flags():
    out = call(
        "triage_tickets",
        tickets=[
            {"id": "1", "subject": "Broken on arrival AGAIN", "body": "This is the second time my order arrived cracked. Unacceptable!!!", "order_value": 45, "created_at": "2026-10-01T09:00"},
            {"id": "2", "subject": "Where is my order", "body": "Tracking has not updated in 5 days", "created_at": "2026-10-05T10:00"},
            {"id": "3", "subject": "Question", "body": "Does it fit a 15 inch laptop? What size should I get"},
            {"id": "4", "subject": "chargeback", "body": "I have filed a chargeback with my bank and contacted my lawyer"},
        ],
        now="2026-10-05T12:00",
    )
    by = {r["id"]: r for r in out["queue"]}
    assert by["4"]["category"] == "chargeback_fraud" and by["4"]["priority"] == "P1" and by["4"]["needs_human"]
    assert by["1"]["category"] == "damaged_defective" and by["1"]["priority"] == "P2"
    assert "repeat contact" in by["1"]["flags"] and "heated tone" in by["1"]["flags"]
    assert by["1"]["waiting_hours"] == 99.0 and any("SLA" in f for f in by["1"]["flags"])
    assert by["2"]["category"] == "wismo" and by["2"]["priority"] == "P3"
    assert by["3"]["category"] == "product_question" and by["3"]["priority"] == "P4"
    assert out["queue"][0]["priority"] == "P1"
    assert out["needs_human_now"] == ["4"]


def test_triage_tickets_rejects_empty_and_bad_value():
    with pytest.raises(ToolError):
        call("triage_tickets", tickets=[])
    with pytest.raises(ToolError):
        call("triage_tickets", tickets=[{"id": "x", "body": "hi", "order_value": "lots"}])


def test_tone_check_flags_policy_speak():
    out = call(
        "tone_check",
        reply="Unfortunately, as per our policy we cannot refund shipping. Sorry for any inconvenience! Please be advised that your request has been forwarded.",
        customer_message="My package arrived broken and I want a refund for the shipping",
    )
    assert out["score"] < 30
    assert "unfortunately" in out["policy_speak"] and "sorry for any inconvenience" in out["policy_speak"]
    assert out["ownership_phrases"] == 0 and out["has_timeframe"] is False
    assert "refund" in out["customer_terms_addressed"]
    good = call("tone_check", reply="Hi Ana, I'm sorry that your mug arrived cracked — that shouldn't have happened. I've already sent a replacement; it ships today and you'll get tracking tomorrow. Thanks, Maya")
    assert good["score"] >= 90 and "send" in good["verdict"]


def test_tone_check_rejects_empty():
    with pytest.raises(ToolError):
        call("tone_check", reply="   ")


def test_lint_macro_fills_and_checks_structure():
    tpl = (
        "Hi {{first_name | there}},\n\nI'm sorry your {{product}} arrived cracked — that shouldn't have happened. "
        "I've already sent a replacement (order {{order_number}}); it ships today and you'll get tracking by email tomorrow.\n\n"
        "If anything else is off, just hit reply and I'll sort it.\n\nThanks,\nMaya"
    )
    out = call("lint_macro", template=tpl, variables={"product": "mug", "order_number": "#1042"})
    assert out["filled"].startswith("Hi there,")
    assert "#1042" in out["filled"] and "{{" not in out["filled"]
    assert out["fallbacks_used"] == ["first_name"]
    assert out["placeholders_missing"] == []
    assert all(out["structure"].values())
    assert out["ready_to_send"] is True
    bad = call("lint_macro", template="Dear [CUSTOMER NAME], unfortunately we cannot help with {order}.", variables={})
    assert bad["ready_to_send"] is False
    assert "[CUSTOMER NAME]" in bad["placeholders_missing"] and "{order}" in bad["placeholders_missing"]
    assert "gives_timeframe" in bad["issues"][1]


def test_lint_macro_rejects_empty():
    with pytest.raises(ToolError):
        call("lint_macro", template="")


def test_support_metrics_maths():
    out = call(
        "support_metrics", tickets=900, orders=6000,
        first_response_minutes=[30, 45, 60, 120, 600, 1500, 90, 80, 70, 65], resolution_hours=[2, 5, 8, 30, 48],
        csat_scores=[5, 5, 4, 3, 5, 2, 4, 5], reopened=60, handle_time_minutes=8, agent_hours_per_week=40, occupancy_pct=80, shrinkage_pct=15,
    )
    assert out["contact_rate_per_100_orders"] == 15.0
    assert out["first_response_minutes"]["median"] == 75.0
    assert out["first_response_minutes"]["p90"] == 690.0
    assert out["csat_pct"] == 75.0
    assert out["reopen_rate_pct"] == 6.7
    assert out["productive_hours_per_agent_week"] == round(40 * 0.85 * 0.8, 1)
    assert out["agents_needed"] == round(210 * 8 / 60 / 27.2, 2)
    assert out["agents_needed_rounded_up"] == 2
    assert any("contact rate" in f for f in out["findings"])


def test_support_metrics_rejects_bad_input():
    with pytest.raises(ToolError):
        call("support_metrics", tickets=10, orders=100, period_days=0)
