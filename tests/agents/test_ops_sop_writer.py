"""SOP Writer tools — step linter, RACI, cycle time, control block."""

import pytest

from hundred.agents.ops import sop_writer
from hundred.core import ToolError

A = sop_writer.AGENT


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_lint_steps_flags_bad_and_passes_good():
    out = call(
        "lint_steps",
        steps=[
            "1. The agent then goes into Stripe and finds the charge.",
            "Exporting the report and emailing it to finance as needed.",
            "If the refund is over $500, get manager approval.",
            "Refund the customer in Stripe.",
            "Manager: Reviews the case appropriately.",
        ],
        roles=["Support agent", "Finance"],
    )
    s1, s2, s3, s4, s5 = out["steps"]
    assert any("does not open with a verb" in i for i in s1["issues"])
    assert any("gerund" in i for i in s2["issues"]) and any("vague" in i for i in s2["issues"]) and any("more than one action" in i for i in s2["issues"])
    assert any("else-branch" in i for i in s3["issues"])
    assert any("irreversible" in i for i in s4["issues"])
    assert any("not a defined role" in i for i in s5["issues"]) and any("third-person" in i for i in s5["issues"])
    assert out["score"] < 60
    good = call(
        "lint_steps",
        steps=[
            "Open the refund request in Zendesk.",
            "If the amount is over $500: go to step 3. Otherwise: go to step 4.",
            "Request approval from Finance in the #refunds Slack channel.",
            "Refund the charge in Stripe → status shows Refunded.",
            "Verify the refund appears on the customer's Stripe timeline.",
            "Reply to the customer with the refund macro in Zendesk.",
        ],
        roles=["Support agent", "Finance"],
    )
    assert good["score"] >= 85 and good["counts"]["flagged_steps"] == 0
    with pytest.raises(ToolError):
        call("lint_steps", steps=[])


def test_build_raci_validation_and_workload():
    out = call(
        "build_raci",
        activities=[
            {"activity": "Close books", "responsible": ["AP clerk"], "accountable": ["Controller"], "consulted": ["CFO"], "informed": ["CEO"]},
            {"activity": "Approve journal", "responsible": ["Controller"], "accountable": ["Controller", "CFO"], "consulted": [], "informed": ["Auditor", "Auditor"]},
            {"activity": "File taxes", "responsible": [], "accountable": ["Controller"], "consulted": ["CFO"], "informed": ["CFO"]},
        ],
    )
    assert out["valid"] is False
    assert any("2 Accountable" in i for i in out["activities"][1]["issues"])
    assert any("no Responsible" in i for i in out["activities"][2]["issues"]) and any("same row" in i for i in out["activities"][2]["issues"])
    assert out["workload"]["Controller"]["A"] == 3 and any("bottleneck" in f for f in out["flags"])
    assert out["activities"][1]["cells"]["Controller"] == "R/A"
    assert "| Activity | AP clerk | Controller |" in out["markdown_matrix"]
    with pytest.raises(ToolError):
        call("build_raci", activities=["Close books"])


def test_cycle_time_pce_and_handoffs():
    out = call(
        "cycle_time",
        steps=[
            {"step": "Submit request", "touch_minutes": 10, "wait_minutes": 0, "role": "Requester"},
            {"step": "Manager approval", "touch_minutes": 5, "wait_minutes": 480, "role": "Manager"},
            {"step": "Vendor setup", "touch_minutes": 30, "wait_minutes": 960, "role": "Procurement"},
            {"step": "Confirm", "touch_minutes": 5, "wait_minutes": 0, "role": "Requester"},
        ],
    )
    assert out["touch_time_minutes"] == 50 and out["wait_time_minutes"] == 1440 and out["lead_time_minutes"] == 1490
    assert out["process_cycle_efficiency_pct"] == 3.4 and out["handoffs"] == 3
    assert out["biggest_wait"]["step"] == "Vendor setup" and out["bottleneck_touch"]["role"] == "Procurement"
    assert out["by_role_touch_minutes"]["Requester"] == 15
    assert any("under 10%" in r for r in out["recommendations"])
    with pytest.raises(ToolError):
        call("cycle_time", steps=[{"step": "x", "touch_minutes": 0, "wait_minutes": 0}])


def test_sop_control_block_version_and_review_date():
    out = call("sop_control_block", title="Customer refund processing", owner="Head of Support", effective_date="2026-01-31", version="1.3", review_months=12, change_type="major", department="cs", as_of="2026-09-27")
    assert out["sop_id"] == "SOP-CS-CUSTOMER-REFUND-PROCESSIN" and out["version"] == "2.0" and out["previous_version"] == "1.3"
    assert out["next_review_date"] == "2027-01-31" and out["days_until_review"] == 126 and out["status"] == "active"
    assert out["requires_retraining"] is True
    minor = call("sop_control_block", title="X", owner="Y", effective_date="2025-08-31", version="2.0", review_months=6, change_type="minor", as_of="2026-09-27")
    assert minor["version"] == "2.1" and minor["next_review_date"] == "2026-02-28" and "OVERDUE" in minor["status"]
    with pytest.raises(ToolError):
        call("sop_control_block", title="X", owner="Y", effective_date="2026-01-01", version="v2")


def test_bad_arguments_raise_clean_error():
    with pytest.raises(ToolError):
        A.get_tool("cycle_time").call({"steps": "a,b"})
