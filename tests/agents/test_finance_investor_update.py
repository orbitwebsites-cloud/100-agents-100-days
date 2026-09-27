"""Investor Update Writer tools — deltas, growth series, runway line, draft lint."""

import pytest

from hundred.agents.finance.investor_update import AGENT as A
from hundred.core import ToolError


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_metric_deltas_mom_yoy_and_flags():
    out = call(
        "metric_deltas",
        metrics=[
            {"name": "MRR", "current": 84000, "prior_month": 78000, "prior_year": 41000, "unit": "$"},
            {"name": "Churn", "current": 2.4, "prior_month": 2.1, "unit": "%", "higher_is_better": False},
            {"name": "Customers", "current": 312, "prior_month": 298, "prior_year": 160},
        ],
        period_label="Sep 2026",
    )
    mrr, churn, cust = out["metrics"]
    assert mrr["mom"]["pct"] == 7.7 and mrr["mom"]["absolute"] == 6000.0 and mrr["mom"]["favourable"] is True
    assert mrr["yoy"]["pct"] == 104.9
    assert churn["mom"]["display"] == "+0.3 pts" and churn["mom"]["favourable"] is False
    assert churn["needs_explanation"] == ["MoM"]  # +14.3% relative
    assert cust["yoy"]["display"] == "+95.0% (+152)"
    assert out["markdown_table"].splitlines()[0] == "| Metric | Sep 2026 | MoM | YoY | Note |"
    assert "▼ +0.3 pts" in out["markdown_table"]
    with pytest.raises(ToolError):
        call("metric_deltas", metrics=[{"name": "x"}])


def test_growth_series_cmgr_and_trend():
    out = call("growth_series", values=[40, 44, 49, 53, 58, 64, 70, 75, 80, 84], name="MRR")
    assert out["cmgr_pct"] == 8.6
    assert out["total_growth_pct"] == 110.0
    assert out["last_3_avg_mom_pct"] == 6.3 and out["prior_3_avg_mom_pct"] == 9.7
    assert out["trend"] == "decelerating"
    assert out["months_to_double_at_cmgr"] == 8.4
    assert out["best_month_pct"] == 11.4
    with pytest.raises(ToolError):
        call("growth_series", values=[1, 2])


def test_runway_line_average_burn_and_hires():
    out = call("runway_line", cash=1900000, net_burn_months=[100000, 105000, 110000], as_of="2026-09-30", hires_planned_monthly_cost=30000)
    assert out["avg_net_burn"] == 105000.0
    assert out["runway_months"] == 18.1
    assert out["cash_out_month"] == "2028-03"
    assert out["with_planned_hires"]["runway_months"] == 14.1
    assert out["burn_trend"] == "rising" and out["fundraise_flag"] is False
    short = call("runway_line", cash=500000, net_burn_months=[60000], as_of="2026-09-30")
    assert short["fundraise_flag"] is True and "fundraising plan" in short["verdict"]
    positive = call("runway_line", cash=500000, net_burn_months=[-10000])
    assert positive["cash_flow_positive"] is True
    with pytest.raises(ToolError):
        call("runway_line", cash=1, net_burn_months=[])


GOOD = """Subject: Acme — Sep 2026 update
TL;DR: MRR $84k (+7.7% MoM), churn up to 2.4%, hiring a Head of Sales.
## KPIs
MRR $84k, customers 312, churn 2.4%, cash $1.9M, burn $110k.
## Highlights
- Closed 14 new customers ($6k new MRR).
## Lowlights
- Churn rose to 2.4% from 2.1%: two SMB accounts lost to budget cuts.
## Asks
- Intros to a Head of Sales at a Series B SaaS company.
## Runway
Cash $1.9M, burn $110k → 17 months of runway.
Thanks to Jane for the intro to Bob.
"""


def test_update_lint_sections_vague_and_asks():
    good = call("update_lint", draft=GOOD)
    assert good["missing_sections"] == [] and good["vague_phrases"] == []
    assert good["score"] == 90  # only the length issue
    assert good["ready_to_send"] is False  # too thin
    bad = call("update_lint", draft="Great month! We made a lot of progress and things are going well. Any help appreciated.")
    assert set(bad["missing_sections"]) >= {"tl;dr", "kpis", "lowlights", "runway"}
    assert "great month" in bad["vague_phrases"] and "a lot of" in bad["vague_phrases"]
    assert bad["score"] < 40
    vague_ask = call("update_lint", draft=GOOD.replace("Intros to a Head of Sales at a Series B SaaS company", "Any help appreciated"))
    assert any("asks are not specific" in i for i in vague_ask["issues"])
    with pytest.raises(ToolError):
        call("update_lint", draft="")
