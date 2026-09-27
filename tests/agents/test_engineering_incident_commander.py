"""Incident Commander tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("incident-commander")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


EVENTS = [
    "14:02 deploy of pricing-service v2.3 rolled out",
    "14:09 alerts fired for checkout 5xx",
    "14:12 on-call acked and declared incident",
    "14:31 root cause identified: null plan in pricing",
    "14:35 rolled back pricing-service to v2.2",
    "15:20 error rate back to normal, incident resolved",
]


def test_build_timeline_metrics_and_milestones():
    out = call("build_timeline", events=EVENTS, incident_date="2026-09-27")
    m = out["metrics"]
    assert m == {"time_to_detect_min": 7.0, "time_to_acknowledge_min": 3.0, "time_to_identify_min": 22.0, "time_to_mitigate_min": 33.0, "time_to_resolve_min": 78.0, "total_span_min": 78.0}
    assert out["milestones"]["mitigated"] == "2026-09-27 14:35"
    assert out["events"][1]["delta"] == "7m" and out["events"][-1]["elapsed"] == "1h 18m"
    assert len(out["comms_gaps"]) == 1 and out["comms_gaps"][0]["gap"] == "45m"
    assert out["summary"].startswith("TTD: 7m · TTA: 3m")


def test_build_timeline_midnight_rollover():
    out = call("build_timeline", events=["23:50 errors began", "23:55 customer reported failures", "00:10 paged"])
    assert [e["time"] for e in out["events"]] == ["23:50", "23:55", "00:10 (+1d)"]
    assert out["metrics"]["time_to_detect_min"] == 5.0


def test_build_timeline_rejects_untimed():
    with pytest.raises(ToolError):
        call("build_timeline", events=["something happened", "then more"])


def test_error_budget_time_basis():
    out = call("error_budget", slo_pct=99.9, window_days=30, downtime_minutes=38, elapsed_days=20)
    assert out["budget_minutes"] == 43.2
    assert out["consumed_pct"] == 88.0
    assert out["burn_rate"] == 1.32
    assert out["projected_exhaustion_day"] == 22.7
    assert out["status"] == "burning fast"
    assert out["burn_rate_alerts"][0] == {"burn_rate": 14.4, "long_window": "1h", "short_window": "5m", "budget_consumed_pct": 2, "error_rate_threshold_pct": 1.44}


def test_error_budget_event_basis_exhausted():
    out = call("error_budget", slo_pct=99.95, bad_events=1200, total_events=2_000_000, elapsed_days=10)
    assert out["consumed_pct"] == 120.0 and out["status"] == "exhausted" and out["remaining_minutes"] == 0


def test_error_budget_rejects_bad_inputs():
    with pytest.raises(ToolError):
        call("error_budget", slo_pct=100)
    with pytest.raises(ToolError):
        call("error_budget", slo_pct=99.9, bad_events=5)


def test_grade_severity_rules():
    assert call("grade_severity", users_affected_pct=30, core_functionality_down=True)["severity"] == "SEV1"
    assert call("grade_severity", users_affected_pct=0, data_loss=True)["severity"] == "SEV1"
    assert call("grade_severity", users_affected_pct=10, core_functionality_down=True)["severity"] == "SEV2"
    assert call("grade_severity", users_affected_pct=3, degraded=True)["severity"] == "SEV3"
    assert call("grade_severity", users_affected_pct=50, core_functionality_down=True, customer_facing=False)["severity"] == "SEV3"
    assert call("grade_severity", users_affected_pct=0)["severity"] == "SEV4"
    out = call("grade_severity", users_affected_pct=30, core_functionality_down=True)
    assert out["response"]["ack_minutes"] == 5 and out["escalate_if"] == []


def test_grade_severity_rejects_bad_pct():
    with pytest.raises(ToolError):
        call("grade_severity", users_affected_pct=150)


PM = """# Postmortem
## Summary
Checkout failed for 30% of users for 78 minutes.
## Impact
30% of users, 12,400 failed orders, ~$40k revenue.
## Timeline
14:02 deploy
## Root cause
The pricing service returned null because the enterprise plan was missing from the config map, which meant checkout could not compute totals. Bob should have tested it.
## Action items
- [ ] Add config validation in CI — @alice — 2026-10-05
- [ ] Add alert on pricing null rate — owner: bob, due 2026-10-10
- [ ] Be more careful
## Lessons learned
Human error was the root cause.
"""


def test_check_postmortem_findings():
    out = call("check_postmortem", text=PM)
    assert set(out["sections_missing"]) == {"detection", "contributing factors", "response/mitigation"}
    assert len(out["action_items"]) == 3 and out["action_items_complete"] == 2
    assert [b["phrase"] for b in out["blame_flags"]] == ["Bob should have", "Human error"]
    assert any("vague action item" in f for f in out["findings"])
    assert out["quantified_statements"] >= 3
    assert out["score"] < 60


def test_check_postmortem_rejects_empty():
    with pytest.raises(ToolError):
        call("check_postmortem", text=" ")
