"""Landing Page CRO tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("landing-page-cro")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


PAGE = """Plan projects your team actually finishes
Trusted by 12,000 teams. No credit card required.
[Start my free trial]
Our platform leverages seamless synergy to empower you.
We built it for remote teams who lose tasks in Slack.
[Book a demo]
"""


def test_audit_page_scores_dimensions_and_flags_structure():
    out = call("audit_page", page_text=PAGE, form_fields=6, nav_links=5, load_time_seconds=4, traffic_source="google ads: team project planning")
    assert 0 <= out["score"] <= 100
    assert set(out["dimensions"]) == {"value_proposition", "clarity", "relevance", "anxiety", "distraction", "urgency"}
    assert out["stats"]["jargon"] == ["empower", "seamless", "synergy"]
    assert out["stats"]["ctas_detected"] == ["book a demo", "start my free trial"]
    assert out["stats"]["message_match_ratio"] == 0.2
    assert out["fixes"][0].startswith("Speed")
    clean = call("audit_page", page_text=PAGE, form_fields=2, nav_links=0)
    assert clean["score"] > out["score"]


def test_audit_page_rejects_empty():
    with pytest.raises(ToolError):
        call("audit_page", page_text="")


def test_headline_clarity_grades():
    bad = call("headline_clarity", headline="Reimagining the future of work for modern teams", cta_label="Submit")
    assert bad["grade"] in ("C", "F")
    assert bad["checks"]["no_jargon"] is False and bad["checks"]["cta_ok"] is False
    good = call("headline_clarity", headline="Plan projects your team actually finishes", subheadline="Task software trusted by 12,000 remote teams", cta_label="Start my free trial")
    assert good["grade"] == "A" and good["passed"] == "9/10"


def test_headline_clarity_rejects_empty():
    with pytest.raises(ToolError):
        call("headline_clarity", headline=" ")


def test_funnel_leaks_math():
    out = call("funnel_leaks", steps=[{"name": "visits", "count": 40000}, {"name": "pricing", "count": 6200}, {"name": "signup", "count": 900}, {"name": "paid", "count": 210}], value_per_final_conversion=500)
    assert out["overall_conversion_pct"] == 0.525
    assert out["steps"][1]["step_conversion_pct"] == 15.5
    assert out["steps"][2]["lost"] == 5300
    assert out["biggest_leak_by_lost_conversions"]["step"] == "signup"
    assert out["biggest_leak_by_rate"]["step"] == "signup"  # 85.48% drop vs 84.5% at pricing
    assert abs(out["biggest_leak_by_rate"]["drop_pct"] - 85.48) < 0.01
    assert out["value_of_10pct_fix_at_biggest_leak"]["extra_final_conversions"] == 21.0
    assert out["value_of_10pct_fix_at_biggest_leak"]["extra_value"] == 10500.0


def test_funnel_leaks_rejects_growing_funnel():
    with pytest.raises(ToolError):
        call("funnel_leaks", steps=[{"name": "a", "count": 10}, {"name": "b", "count": 20}])


def test_lift_value():
    out = call("lift_value", monthly_visitors=18000, current_cvr_pct=2.1, target_cvr_pct=2.6, value_per_conversion=300)
    assert out["extra_conversions_per_month"] == 90.0
    assert out["extra_revenue_per_month"] == 27000.0
    assert out["extra_revenue_over_horizon"] == 324000.0
    assert abs(out["relative_lift_pct"] - 23.8) < 0.1


def test_lift_value_rejects_bad_rate():
    with pytest.raises(ToolError):
        call("lift_value", monthly_visitors=100, current_cvr_pct=150, target_cvr_pct=2, value_per_conversion=1)


def test_test_sample_size_and_runtime_advice():
    out = call("test_sample_size", baseline_cvr_pct=2.1, expected_relative_lift_pct=15, monthly_visitors=18000)
    assert out["visitors_per_variant"] == 34908
    assert out["weeks_needed"] == 17
    assert out["recommendation"].startswith("17 weeks is too long")
    quick = call("test_sample_size", baseline_cvr_pct=5, expected_relative_lift_pct=30, monthly_visitors=100000)
    assert quick["weeks_needed"] == 1


def test_test_sample_size_rejects_zero_lift():
    with pytest.raises(ToolError):
        call("test_sample_size", baseline_cvr_pct=2, expected_relative_lift_pct=0)


def test_bad_arguments_raise_clean_error():
    with pytest.raises(ToolError):
        A.get_tool("funnel_leaks").call({"steps": "visits"})
