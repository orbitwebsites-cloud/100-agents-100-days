"""PRD Writer tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("prd-writer")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


FULL_PRD = """
# PRD: SSO
## Problem
Admins at mid-market customers need to provision users through their identity provider because manual invites take hours, but today every seat is invited by hand, which costs support 40 tickets a month and blocks enterprise deals.
## Users
Primary persona: IT admin at a 200-2000 person company. Secondary: security reviewer. Not for: consumer accounts or free plans in any form.
## Goals and non-goals
Goals: close enterprise deals, cut provisioning time. Non-goals: SCIM deprovisioning, custom attribute mapping, and mobile SSO are out of scope for this release.
## Success metrics
Metric: enterprise deals blocked by SSO. Baseline 6 per quarter. Target 0 per quarter by 2027-03-31. Source: CRM lost-reason field.
## Requirements
FR-001 The system MUST accept SAML 2.0 assertions from Okta and Azure AD. FR-002 The system MUST reject assertions older than 5 minutes. NFR-001 Login round trip SHOULD complete within 2 seconds at P95.
## UX and flows
Entry point from Settings > Security. States: empty (no IdP configured), loading, error (invalid metadata), success. Wireframes linked in Figma.
## Edge cases
1. IdP metadata expires. 2. User exists with password login. 3. Clock skew beyond 5 minutes on the IdP side.
## Dependencies
Depends on the auth service and the billing plan flag. Legal review needed for the data processing addendum.
## Risks
Risk: Azure AD quirks. Likelihood medium, impact high, mitigation: test tenant.
## Rollout
Feature flag at 5% of enterprise tenants, then 50%, then 100%. Kill switch in admin. Comms via changelog.
## Open questions
| # | Question | Owner | Needed by |
| 1 | Do we support IdP-initiated login? | Sam | 2026-10-15 |
## Appendix
Competitive notes and research links.
"""


def test_check_completeness_full_prd_scores_high():
    out = call("check_completeness", prd_text=FULL_PRD)
    assert out["score"] >= 80
    assert out["missing"] == []
    assert out["numbered_requirements"] == 3
    assert "Ready" in out["verdict"]


def test_check_completeness_thin_draft_lists_missing():
    out = call("check_completeness", prd_text="# Dashboard\n## Solution\nBuild a dashboard with charts and filters so people can see data.")
    assert out["score"] < 50
    missing = {m["section"] for m in out["missing"]}
    assert {"problem", "metrics", "requirements", "rollout"} <= missing
    assert any("non-goals" in n for n in out["notes"])


def test_check_completeness_rejects_empty():
    with pytest.raises(ToolError):
        call("check_completeness", prd_text="   ")


def test_number_requirements_ids_priorities_and_flags():
    out = call(
        "number_requirements",
        requirements=[
            "The system must return search results within 200 ms at P95.",
            "Users should be able to export and/or import data easily.",
            "The page could show a tooltip on hover.",
        ],
    )
    ids = [r["id"] for r in out["requirements"]]
    assert ids == ["NFR-001", "FR-001", "FR-002"]
    assert [r["priority"] for r in out["requirements"]] == ["MUST", "SHOULD", "COULD"]
    assert out["requirements"][0]["issues"] == []
    issues = " ".join(out["requirements"][1]["issues"])
    assert "ambiguous" in issues and "easily" in issues and "compound" in issues
    assert out["by_priority"] == {"MUST": 1, "SHOULD": 1, "COULD": 1}
    assert out["flagged"] == 1


def test_number_requirements_rejects_bad_start():
    with pytest.raises(ToolError):
        call("number_requirements", requirements=["The system must log in."], start=0)
    with pytest.raises(ToolError):
        call("number_requirements", requirements=[])


def test_lint_user_stories_detects_structure_problems():
    out = call(
        "lint_user_stories",
        stories=[
            {"story": "As an IT admin, I want to upload IdP metadata, so that my users can sign in with Okta", "criteria": ["Given valid metadata, when I upload it, then the IdP is listed as active"]},
            {"story": "As a user, I want to export data", "criteria": []},
            {"story": "Export stuff quickly", "criteria": ["it works"]},
        ],
    )
    assert out["passing"] == 1
    assert out["stories"][0]["role"] == "IT admin"
    s2 = " ".join(out["stories"][1]["issues"])
    assert "generic" in s2 and "so that" in s2 and "no acceptance criteria" in s2
    assert any("not in" in i for i in out["stories"][2]["issues"])


def test_lint_user_stories_rejects_non_object():
    with pytest.raises(ToolError):
        call("lint_user_stories", stories=["As a user I want things"])


def test_check_success_metrics_computes_lift_and_flags():
    out = call(
        "check_success_metrics",
        metrics=[
            {"name": "weekly active exporters", "baseline": 400, "target": 520, "timeframe": "90 days after launch", "source": "Amplitude event export_completed", "type": "primary"},
            {"name": "engagement", "baseline": "", "target": 1000, "timeframe": "soon", "source": ""},
            {"name": "support tickets", "baseline": 100, "target": 40, "timeframe": "by 2027-01-31", "source": "Zendesk", "type": "guardrail"},
        ],
    )
    assert out["metrics"][0]["lift_rel_pct"] == 30.0
    assert out["metrics"][0]["issues"] == []
    m2 = " ".join(out["metrics"][1]["issues"])
    assert "baseline" in m2 and "timeframe" in m2 and "source" in m2
    assert any("-60" in i for i in out["metrics"][2]["issues"])
    assert out["ready"] == 1
    assert out["notes"] == []


def test_check_success_metrics_rejects_bad_rows():
    with pytest.raises(ToolError):
        call("check_success_metrics", metrics=["nps"])
