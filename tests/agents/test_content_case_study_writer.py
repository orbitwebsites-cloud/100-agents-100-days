"""Case Study Writer tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("case-study-writer")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_format_metrics_framing_rules():
    out = call("format_metrics", metrics=[
        {"name": "support tickets", "before": 1240, "after": 610, "unit": "tickets", "higher_is_better": False, "timeframe": "90 days"},
        {"name": "CSAT", "before": 71, "after": 88, "unit": "%"},
        {"name": "demos", "before": 40, "after": 130},
        {"name": "customers", "before": 3, "after": 11},
        {"name": "churn", "before": 5, "after": 7, "unit": "%", "higher_is_better": False},
    ])
    m = {r["name"]: r for r in out["metrics"]}
    assert m["support tickets"]["pct_change"] == -50.8 and m["support tickets"]["fold"] == 2.03
    assert m["support tickets"]["phrase"] == "halved support tickets (from 1,240 tickets to 610 tickets) in 90 days"
    assert m["CSAT"]["framing"] == "percentage points" and m["CSAT"]["points_change"] == 17
    assert "17 points" in m["CSAT"]["warnings"][0] and "24% increase" in m["CSAT"]["warnings"][0]
    assert m["demos"]["phrase"] == "3.2x more demos (from 40 to 130)"
    assert m["customers"]["framing"] == "absolute" and "Small base" in m["customers"]["warnings"][0]
    assert m["churn"]["improved"] is False and any("wrong way" in w for w in m["churn"]["warnings"])
    assert out["headline_metric"] == "demos"


def test_format_metrics_rejects_non_numbers():
    with pytest.raises(ToolError):
        call("format_metrics", metrics=[{"name": "x", "before": "lots", "after": 5}])
    with pytest.raises(ToolError):
        call("format_metrics", metrics=[])


def test_roi_summary_math():
    out = call("roi_summary", annual_benefit=120000, annual_cost=30000, one_time_cost=15000, months=12)
    assert out["total_cost"] == 45000 and out["net_gain"] == 75000
    assert out["roi_pct"] == 166.7
    assert out["payback_months"] == 2.0
    assert out["benefit_cost_ratio"] == 2.67
    neg = call("roi_summary", annual_benefit=10000, annual_cost=30000)
    assert neg["roi_pct"] < 0 and neg["payback_months"] is None


def test_roi_summary_rejects_zero_cost():
    with pytest.raises(ToolError):
        call("roi_summary", annual_benefit=1000, annual_cost=0)


def test_quote_check_picks_specific_quote():
    out = call("quote_check", quotes=[
        "Great tool, highly recommend!",
        "We went from 1,240 tickets a month to 610 in one quarter, and my team finally got their evenings back.",
        "The platform empowers seamless synergies.",
    ])
    assert out["pull_quote"].startswith("We went from 1,240")
    assert out["pull_quote_score"] >= 80
    assert len(out["discard"]) == 2
    weak = next(r for r in out["ranked"] if r["quote"].startswith("Great"))
    assert any("generic praise" in x for x in weak["reasons"])


def test_quote_check_rejects_empty():
    with pytest.raises(ToolError):
        call("quote_check", quotes=["", "x"])


def test_story_lint_flags_hero_and_baselines():
    draft = (
        "# Acme cut support tickets 51% in 90 days with Zendo\n\n## The challenge\nAcme had 1,240 tickets a month. "
        "\"It was significantly painful,\" said Jane Doe, VP Ops.\n\n## The solution\nAcme rolled out Zendo across three teams. "
        "Zendo did stuff. Zendo is great. We think Zendo rocks.\n\n## The results\nTickets fell 51%. CSAT up 17 points.\n\nBook a demo today."
    )
    out = call("story_lint", draft=draft, customer_name="Acme", product_name="Zendo")
    assert out["customer_mentions"] == 3 and out["product_mentions"] == 5
    flags = " ".join(out["flags"])
    assert "Hero check" in flags
    assert "significantly" in flags
    assert "without baselines" in flags
    assert "no time frame" in flags
    assert out["quotes"] == 1 and out["unattributed_quotes"] == 0
    assert out["sections_found"] == {"challenge": True, "solution": True, "results": True}


def test_story_lint_requires_customer():
    with pytest.raises(ToolError):
        call("story_lint", draft="word " * 60, customer_name="")


def test_round_half_up_and_continuous_units():
    out = call("format_metrics", metrics=[{"name": "resolutions", "before": 400, "after": 650}, {"name": "response time", "before": 9.5, "after": 1.2, "unit": "hrs", "higher_is_better": False}])
    m = {r["name"]: r for r in out["metrics"]}
    assert "63%" in m["resolutions"]["phrase"]
    assert m["response time"]["warnings"] == [] and m["response time"]["phrase"].startswith("cut response time 87%")


def test_payback_never_shortens_when_cost_rises():
    base = call("roi_summary", annual_benefit=186000, annual_cost=36000, billing="annual_upfront")
    more = call("roi_summary", annual_benefit=186000, annual_cost=36000, one_time_cost=12000, billing="annual_upfront")
    assert (base["payback_months"], more["payback_months"]) == (2.3, 3.1)
    assert "1 months" not in call("roi_summary", annual_benefit=186000, annual_cost=36000, one_time_cost=12000)["phrasing"]
