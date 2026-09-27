"""Freelance Contract tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("freelance-contract")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_milestone_schedule_amounts_dates_and_kill_fees():
    out = call(
        "milestone_schedule",
        total_fee=12000,
        start_date="2026-10-05",
        deposit_pct=40,
        milestones=[
            {"name": "Concepts", "pct": 30, "days_after_start": 21, "deliverable": "3 logo concepts"},
            {"name": "Final", "pct": 30, "days_after_start": 45, "deliverable": "final files"},
        ],
        payment_terms_days=15,
        late_fee_pct_per_month=1.5,
        kill_fee_pct_of_remaining=25,
    )
    s = out["schedule"]
    assert [(r["name"], r["amount"]) for r in s] == [("Deposit", 4800.0), ("Concepts", 3600.0), ("Final", 3600.0)]
    assert s[1]["invoice_date"] == "2026-10-26" and s[1]["due_date"] == "2026-11-10"
    assert s[0]["kill_fee_if_cancelled_after_this"] == 1800.0 and s[2]["balance_after"] == 0.0
    assert out["late_fee_per_month_by_invoice"]["Concepts"] == 54.0
    assert out["cash_before_final_delivery_pct"] == 70.0
    assert out["unallocated"] == 0.0 and out["flags"] == []


def test_milestone_schedule_flags_risky_terms():
    out = call("milestone_schedule", total_fee=10000, start_date="2026-10-05", deposit_pct=10, milestones=[{"name": "Final", "pct": 80, "days_after_start": 30}], payment_terms_days=45, late_fee_pct_per_month=0)
    flags = " ".join(out["flags"])
    assert "Deposit 10%" in flags and "Final milestone is 80%" in flags and "Net 45" in flags and "No late fee" in flags
    assert "unallocated" in flags and out["unallocated"] == 1000.0


def test_milestone_schedule_rejects_bad_fee():
    with pytest.raises(ToolError):
        call("milestone_schedule", total_fee=0, start_date="2026-10-05")


def test_scope_creep_check_scores():
    bad = call("scope_creep_check", sow_text="Design work for the website with unlimited revisions until the client is satisfied, and related tasks as needed.")
    assert bad["score"] < 30
    assert "unlimited revisions" in bad["risky_language"] and "subjective acceptance standard" in bad["risky_language"]
    assert "exclusions" in bad["missing"] and "change order" in bad["missing"]
    good = call(
        "scope_creep_check",
        sow_text="""Deliverables:
1. Logo in SVG and PNG (3 concepts, 1 final) by 2026-11-10.
2. Brand guide PDF, up to 12 pages, by 2026-12-01.
Not included: website design, social templates, printing.
Two (2) rounds of revisions per deliverable; further rounds at $120/hour via a written change order agreed before work starts.
Client will provide copy and feedback within 5 business days; delays shift dates day-for-day. Deliverables are deemed accepted after 5 business days without written objection.
Assumptions: one language, client supplies photography.""",
    )
    assert good["score"] >= 80 and good["verdict"] == "Tight scope"


def test_scope_creep_check_rejects_empty():
    with pytest.raises(ToolError):
        call("scope_creep_check", sow_text="")


CLIENT_PAPER = """Independent Contractor Agreement. Contractor shall perform the services. All work product is work made for hire and Company
owns all ideas conceived during the term. Contractor shall not provide services to any competitor of Company. Payment is net 60.
Contractor shall indemnify and hold harmless Company. Company may terminate this agreement at any time without notice. Confidential
information must be protected. This agreement is governed by the laws of California."""


def test_check_contract_clauses_freelancer_side():
    out = call("check_contract_clauses", contract_text=CLIENT_PAPER, my_role="freelancer")
    traps = [t["flag"] for t in out["traps"]]
    assert "Work-for-hire / assignment not conditioned on payment" in traps
    assert "Non-compete / exclusivity" in traps and "Payment terms of net 60 or longer" in traps
    assert "One-way indemnity from the freelancer" in traps
    assert "Client can terminate at any time with no payment for work done" in traps
    missing = {m["clause"] for m in out["missing"]}
    assert {"Deposit / upfront payment", "Late fee / interest / pause right", "Kill fee / early termination payment", "Revision rounds defined", "Liability cap"} <= missing
    assert out["risk_score"] >= 40 and "Do not sign" in out["verdict"]
    assert any(r.startswith("Add Deposit") for r in out["redlines"])


def test_check_contract_clauses_client_side_differs():
    out = call("check_contract_clauses", contract_text=CLIENT_PAPER, my_role="client")
    assert "Non-compete / exclusivity" not in [t["flag"] for t in out["traps"]]
    assert out["risk_score"] < 40


def test_check_contract_clauses_rejects_bad_role():
    with pytest.raises(ToolError):
        call("check_contract_clauses", contract_text=CLIENT_PAPER, my_role="agency")


def test_rate_calculator_math():
    out = call("rate_calculator", target_income=95000, billable_hours_per_week=30, weeks_off=5, annual_overhead=9000, self_employment_tax_pct=15.3, benefits_pct=10, profit_margin_pct=10)
    assert out["billable_weeks"] == 47 and out["billable_hours_per_year"] == 1410
    # 95000*(1.253)+9000 = 128035; *1.1 = 140838.5; /1410 = 99.885
    assert out["annual_revenue_needed"] == 140838 or out["annual_revenue_needed"] == 140839
    assert out["minimum_hourly"] == 99.89 and out["hourly_rate_rounded"] == 100.0 and out["day_rate"] == 800.0


def test_rate_calculator_fixed_fee_check():
    out = call("rate_calculator", target_income=95000, billable_hours_per_week=30, weeks_off=5, annual_overhead=9000, fixed_fee=8000, estimated_hours=100, contingency_pct=20)
    ff = out["fixed_fee_check"]
    assert ff["hours_with_contingency"] == 120.0 and ff["effective_hourly_rate"] == 66.67
    assert ff["recommended_fixed_fee"] == 12000 and "Underpriced" in ff["verdict"]


def test_rate_calculator_rejects_partial_fixed_fee():
    with pytest.raises(ToolError):
        call("rate_calculator", target_income=50000, fixed_fee=1000)
