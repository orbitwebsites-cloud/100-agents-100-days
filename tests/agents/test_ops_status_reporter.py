"""Status Reporter tools — RAG, week-over-week diff, milestone health, report linter."""

import pytest

from hundred.agents.ops import status_reporter
from hundred.core import ToolError

A = status_reporter.AGENT


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_compute_rag_thresholds_and_deltas():
    out = call(
        "compute_rag",
        metrics=[
            {"name": "Signups", "target": 1000, "current": 960, "previous": 900, "direction": "higher"},
            {"name": "p95 latency", "target": 300, "current": 340, "previous": 320, "direction": "lower", "unit": "ms"},
            {"name": "Churn", "target": 2.0, "current": 3.0, "previous": 2.5, "direction": "lower"},
        ],
    )
    s, lat, churn = out["metrics"]
    assert s["attainment_pct"] == 96.0 and s["rag"] == "GREEN" and s["delta"]["pct"] == 6.7 and s["delta"]["trend"] == "improving"
    assert lat["attainment_pct"] == 88.2 and lat["rag"] == "AMBER" and lat["delta"]["trend"] == "worsening"
    assert churn["attainment_pct"] == 66.7 and churn["rag"] == "RED"
    assert out["overall"] == "RED" and out["worst_metric"]["name"] == "Churn"
    assert out["biggest_mover"]["name"] == "Churn"
    with pytest.raises(ToolError):
        call("compute_rag", metrics=[{"name": "x", "target": 10, "current": 5}], green_pct=80, amber_pct=90)


def test_week_over_week_diff():
    out = call(
        "week_over_week",
        previous=[
            {"item": "Migrate auth", "status": "in progress", "due": "2026-10-09", "owner": "Sam"},
            {"item": "Write runbook", "status": "in progress", "due": "2026-10-02"},
            {"item": "Old task", "status": "todo"},
            {"item": "Nothing moved", "status": "in progress"},
        ],
        current=[
            {"item": "Migrate auth", "status": "in progress", "due": "2026-10-16", "owner": "Sam"},
            {"item": "write runbook", "status": "Done", "due": "2026-10-02"},
            {"item": "Nothing moved", "status": "in progress"},
            {"item": "New: load test", "status": "todo", "due": "2026-10-20"},
        ],
    )
    assert out["completed"][0]["item"] == "write runbook"
    assert out["slipped"][0]["item"] == "Migrate auth" and out["slipped"][0]["working_days"] == 5
    assert out["added"][0]["item"] == "New: load test" and out["removed"][0]["item"] == "Old task"
    assert out["stale"][0]["item"] == "Nothing moved"
    assert out["counts"]["open_now"] == 3 and out["throughput_pct_of_open"] == 25.0
    with pytest.raises(ToolError):
        call("week_over_week", previous=[], current=[])


def test_milestone_health_rag_rules():
    out = call(
        "milestone_health",
        milestones=[
            {"name": "Design freeze", "baseline": "2026-09-04", "actual": "2026-09-04"},
            {"name": "Beta", "baseline": "2026-09-18", "forecast": "2026-09-24"},
            {"name": "Load test", "baseline": "2026-09-25", "forecast": "2026-10-09"},
            {"name": "GA", "baseline": "2026-10-30", "forecast": "2026-10-30", "percent_complete": 20},
        ],
        as_of="2026-09-28",
    )
    by = {m["name"]: m for m in out["milestones"]}
    assert by["Design freeze"]["rag"] == "GREEN" and by["Design freeze"]["state"] == "done"
    assert by["Beta"]["state"] == "OVERDUE" and by["Beta"]["rag"] == "RED"
    assert by["Load test"]["slip_working_days"] == 10 and by["Load test"]["rag"] == "RED"
    assert by["GA"]["rag"] == "GREEN"
    assert out["overall"] == "RED" and out["overdue"] == ["Beta"] and out["next_milestone"]["name"] == "Beta"
    with pytest.raises(ToolError):
        call("milestone_health", milestones=[{"name": "x", "baseline": "2026-09-04"}], amber_max_days=0)


GOOD = """**Migration — week of 2026-09-28 — 🟡 AMBER** (last week: GREEN)

**TL;DR**
- Cutover moved from Oct 9 to Oct 16 (+5 working days) because the auth provider's SAML fix shipped late.
- Throughput 960 signups vs 1,000 target (96%, up from 900 last week).
- We need a decision on the freeze window by Wednesday.

**Asks / decisions needed**
- Approve the Oct 14-16 freeze window — by Sep 30 — from Priya.

**Progress**
- Shipped: runbook v2, load test at 2x traffic (p95 340 ms vs 300 ms target).
- Slipped: auth migration +5 days (SAML fix).

**Risks & issues**
- 🟡 SAML fix regresses SSO for 3 enterprise tenants — impact: 1,200 users — mitigation: staged rollout — owner: Sam — Oct 12.

**Next week**
- Complete SSO staged rollout to 2 tenants; finish data backfill (80% done); dry-run cutover on Oct 8.
"""

BAD = """Hi all, quick update. Things are going well and we are making good progress on the migration.
A delay was experienced on the auth work but the team is on track and should be done soon.
Several issues came up and we are looking into them. More next week."""


def test_lint_report_scores_good_vs_bad():
    good = call("lint_report", report=GOOD)
    bad = call("lint_report", report=BAD)
    assert good["score"] >= 80 and good["missing_sections"] == []
    assert bad["score"] < 50
    assert "status_line" in bad["missing_sections"] and "asks" in bad["missing_sections"]
    assert bad["vague_phrases"].get("making good progress") == 1 or bad["vague_phrases"].get("good progress") == 1
    assert bad["vague_phrases"].get("on track") == 1 and len(bad["passive_sentences"]) >= 1
    with pytest.raises(ToolError):
        call("lint_report", report="   ")


def test_bad_arguments_raise_clean_error():
    with pytest.raises(ToolError):
        A.get_tool("compute_rag").call({"metrics": {"name": "x"}})


def test_milestone_slip_skips_holidays():
    out = A.get_tool("milestone_health").call({"as_of": "2026-11-20", "holidays": ["2026-11-26", "2026-11-27"], "milestones": [{"name": "Backend", "baseline": "2026-11-25", "forecast": "2026-12-02"}]})
    assert out["milestones"][0]["slip_working_days"] == 3  # Thanksgiving Thu/Fri are not working days


def test_lint_uses_section_headings_and_ignores_tables():
    report = (
        "**Proj — 🟡 AMBER**\n\n**TL;DR**\n- We shipped SSO (+1 vs last week).\n\n**Asks**\n- Approve hire by Nov 24.\n\n"
        "**Progress**\n| Metric | Target | This week | Last week | Delta | RAG | Owner | Notes | More | Columns |\n|---|---|---|---|---|---|---|---|---|---|\n"
        "| A | 1 | 2 | 3 | +1 | G | x | y | z | w |\n| B | 1 | 2 | 3 | +1 | G | x | y | z | w |\n\n**Risks**\n- Risk 1, owner Raj.\n\n**Next week**\n- Ship 2."
    )
    out = A.get_tool("lint_report").call({"report": report})
    assert out["asks_before_progress"] is True and out["long_sentences"] == []
