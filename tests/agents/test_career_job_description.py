"""Job Description Writer tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("job-description")

JD = """Backend Rockstar Engineer
Remote (US) · $150,000 – $190,000 + equity
About the role
We're a fast-paced family looking for an aggressive, competitive ninja who can dominate our backend. He will hit the ground running.
What you'll do
- Ship the payments service so that checkout latency drops under 200ms
- Own on-call for the API tier
- Mentor two engineers
Requirements
- 7+ years of Go experience
- Bachelor's degree in Computer Science
- Excellent communication skills
- Native English speaker
- Experience with Kubernetes
- Experience with k8s and container orchestration
- Passionate team player
- Strong SQL
- Experience with distributed systems
Nice to have
- Rust
What we offer
- Health, dental, 401k match
Equal opportunity employer.
"""


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_check_inclusive_language_finds_coded_and_exclusionary_terms():
    out = call("check_inclusive_language", job_description=JD)
    assert out["lean"] == "masculine" and out["masculine_count"] == 6
    assert {f for h in out["masculine_coded"] for f in h["matched"]} == {"aggressive", "competitive", "dominate", "fast-paced", "ninja", "rockstar"}
    assert {h["term"] for h in out["masculine_coded"] if h["source"] == "GFK 2011"} == {"aggress*", "compet*", "domina*"}
    assert {h["term"] for h in out["exclusionary"]} == {"family", "he will", "native english speaker"}
    assert out["gendered_pronouns"] == 1
    assert out["score"] < 40
    assert any("native english speaker" in f for f in out["fixes"])
    clean = call("check_inclusive_language", job_description="You will build the payments service with two engineers and ship every two weeks.")
    assert clean["lean"] == "neutral" and clean["score"] == 100


def test_check_inclusive_language_rejects_empty():
    with pytest.raises(ToolError):
        call("check_inclusive_language", job_description=" ")


def test_check_structure_counts_sections_and_requirements():
    out = call("check_structure", job_description=JD)
    assert out["sections"]["eeo"] and out["sections"]["benefits"] and not out["sections"]["process"]
    assert out["requirements"]["must"] == 9 and out["requirements"]["nice"] == 1 and out["requirements"]["duties"] == 3
    assert out["salary_range"] == "$150,000 – $190,000" and out["salary_above_fold"] is True
    assert out["location_stated"] is True
    assert any("9 must-have" in i for i in out["issues"]) and any("under 300" in i for i in out["issues"])


def test_check_structure_rejects_empty():
    with pytest.raises(ToolError):
        call("check_structure", job_description="")


def test_audit_requirements_flags_proxies_duplicates_and_overflow():
    out = call(
        "audit_requirements",
        requirements=[
            "7+ years of Go experience",
            "Bachelor's degree in Computer Science",
            "Excellent communication skills",
            "Experience with Kubernetes",
            "Experience with Kubernetes and container orchestration",
            "Passionate team player",
            "Strong SQL",
            "Experience with distributed systems",
            "Rust is a plus",
        ],
        role_level="junior",
    )
    rows = out["requirements"]
    assert rows[0]["years"] == 7 and rows[0]["rewrite"] == "demonstrated Go experience"
    assert any("contradicts the level" in f for f in rows[0]["flags"])
    assert any("degree" in f for f in rows[1]["flags"])
    assert any("duplicates #4" in f for f in rows[4]["flags"])
    assert any("buzzword" in f for f in rows[5]["flags"])
    assert rows[8]["tier"] == "nice"
    assert out["must_have"] == 8 and out["over_limit_by"] == 1
    assert set(out["recommend_cut"]) == {5, 6}


def test_audit_requirements_rejects_empty_line():
    with pytest.raises(ToolError):
        call("audit_requirements", requirements=["Go", ""])


def test_build_salary_band_math():
    out = call("build_salary_band", midpoint=150000, spread_pct=40, candidate_salary=160000)
    assert out["band"] == {"min": 125000, "q1": 137500, "midpoint": 150000, "q3": 162500, "max": 175000}
    assert out["posting_range_hiring"] == "$125,000 – $150,000"
    assert out["candidate"]["compa_ratio"] == 1.067 and out["candidate"]["range_penetration_pct"] == 70.0
    assert out["candidate"]["zone"].startswith("Q3")
    from_minmax = call("build_salary_band", band_min=120000, band_max=180000)
    assert from_minmax["band"]["midpoint"] == 150000 and from_minmax["spread_pct"] == 50.0


def test_build_salary_band_rejects_missing_inputs():
    with pytest.raises(ToolError):
        call("build_salary_band")
    with pytest.raises(ToolError):
        call("build_salary_band", band_min=100000, band_max=90000)


def test_inclusive_language_skips_benefit_and_product_uses():
    out = call("check_inclusive_language", job_description="You get paid family leave and work on a mature product line. We value core competencies.")
    assert out["exclusionary"] == [] and out["masculine_coded"] == []
