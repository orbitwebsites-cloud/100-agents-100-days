"""Resume Optimizer tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("resume-optimizer")

JD = """Senior Product Manager
About the role
You'll own the roadmap for our payments product.
Requirements:
- 5+ years of product management experience
- Strong SQL and analytics skills; experience with A/B testing
- Experience with Stripe or payments APIs
Nice to have:
- Figma and user research experience
- Python
"""
RESUME = """Jane Doe
jane@example.com | (415) 555-0100 | linkedin.com/in/janedoe
Summary
Product manager with 6 years across fintech.
Experience
Product Manager, Acme — Jan 2020 – Present
- Led roadmap for payments APIs, increasing conversion 12% by launching Stripe integration
- Responsible for SQL dashboards
Education
BS Computer Science, State University, 2016
Skills
SQL, Figma, roadmapping
"""


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_match_keywords_splits_must_and_nice():
    out = call("match_keywords", resume=RESUME, job_description=JD, job_title="Senior Product Manager")
    matched = {m["term"] for m in out["matched"]}
    missing = {m["term"]: m["tier"] for m in out["missing"]}
    assert {"sql", "stripe", "figma", "product management"} <= matched
    assert missing["a/b testing"] == "must"
    assert missing["python"] == "nice"
    assert out["title_in_resume"] is False
    assert 0 < out["must_have_coverage_pct"] < 100
    assert "auto-reject" in out["ats_truth"]


def test_match_keywords_needs_a_real_jd():
    with pytest.raises(ToolError):
        call("match_keywords", resume=RESUME, job_description="hello there friend")


def test_score_bullets_rewards_xyz_and_flags_weak():
    out = call(
        "score_bullets",
        bullets=[
            "Led roadmap for payments APIs, increasing conversion 12% by launching Stripe integration",
            "Responsible for SQL dashboards",
            "I was a team player who helped with various tasks",
        ],
    )
    strong, weak, awful = out["bullets"]
    assert strong["score"] >= 90 and strong["xyz_structure"] is True
    assert weak["score"] < 60 and any("weak opener" in i for i in weak["issues"])
    assert any("team player" in i for i in awful["issues"]) and "first-person pronoun" in awful["issues"]
    assert out["needs_rewrite"] == [1, 2]
    assert out["quantified_pct"] == 33.3


def test_score_bullets_rejects_empty_bullet():
    with pytest.raises(ToolError):
        call("score_bullets", bullets=["Led team", "   "])


def test_check_ats_format_detects_sections_and_risks():
    out = call("check_ats_format", resume=RESUME, years_experience=6)
    assert out["sections_found"] == {"experience": True, "education": True, "skills": True, "summary": True}
    assert out["contact"] == {"email": True, "phone": True, "linkedin": True}
    assert out["parse_risks"] == []
    bad = "John\nWORK\nSummer '19 - Fall '20\tAcme\t\t\tNYC ★★★\n" + "x " * 1300
    out2 = call("check_ats_format", resume=bad, years_experience=3)
    risks = " ".join(out2["parse_risks"])
    assert "unparseable dates" in risks and "Experience" in risks and "pages" in risks and "symbols" in risks
    assert out2["parse_score"] < 50


def test_check_ats_format_rejects_empty():
    with pytest.raises(ToolError):
        call("check_ats_format", resume="")


def test_compute_tenure_gaps_totals_and_overlaps():
    out = call(
        "compute_tenure",
        roles=[
            {"title": "PM", "company": "Acme", "start": "Jan 2020", "end": "present"},
            {"title": "APM", "company": "Beta", "start": "2017-06", "end": "2019-03"},
            {"title": "Advisor", "start": "2018-01", "end": "2018-12"},
        ],
        as_of="2026-09-27",
    )
    assert out["timeline"][0]["title"] == "APM" and out["timeline"][0]["months"] == 22
    assert out["timeline"][-1]["tenure"] == "6 yrs 9 mo"
    assert out["total_months"] == 22 + 81  # overlap deduped, gap excluded
    assert out["gaps"] == [{"months": 9, "from": "2019-04", "to": "2019-12", "label": "9 mo"}]
    assert out["overlaps"][0]["months"] == 12
    assert out["job_hopping_flag"] is False


def test_compute_tenure_rejects_bad_dates():
    with pytest.raises(ToolError):
        call("compute_tenure", roles=[{"title": "x", "start": "sometime", "end": "2020-01"}])
    with pytest.raises(ToolError):
        call("compute_tenure", roles=[{"title": "x", "start": "2021-01", "end": "2020-01"}])
