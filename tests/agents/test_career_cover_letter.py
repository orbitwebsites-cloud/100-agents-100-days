"""Cover Letter Writer tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("cover-letter")

JD = """Customer Success Manager
Responsibilities:
- Own renewals for a book of 60 mid-market SaaS accounts
Requirements:
- 3+ years in customer success or account management
- Track record of improving net revenue retention
- Experience with Salesforce and Gainsight
Nice to have:
- SQL
"""
LETTER = """Dear Acme Hiring Team,

Acme's move upmarket this year, announced with the Enterprise tier, is exactly the shift I led at Beta. As a Customer Success Manager for 60 mid-market accounts, my focus was renewals and expansion.

At Beta, net revenue retention rose from 98% to 112% over four quarters after I rebuilt the renewal playbook around usage signals in Salesforce and Gainsight. Renewal calls moved 90 days earlier. Expansion revenue doubled in the accounts I ran, and the team adopted the playbook company-wide.

In the first 90 days at Acme, the plan would be a health-score audit of the top 20 accounts and a renewal forecast the sales team trusts.

A 20-minute call would let me walk through the playbook and how it maps to Acme's book. Thank you for reading.

Jane Doe
"""


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_extract_requirements_ranks_must_haves_and_separates_duties():
    out = call("extract_requirements", job_description=JD)
    assert out["counts"] == {"must": 3, "nice": 1, "unclear": 0, "duties": 1}
    assert {p["text"] for p in out["priority"]} == {
        "3+ years in customer success or account management",
        "Track record of improving net revenue retention",
        "Experience with Salesforce and Gainsight",
    }
    assert out["responsibilities"][0]["text"].startswith("Own renewals")
    assert out["years_required"] == 3
    assert out["nice_to_have"][0]["skills"] == ["sql"]


def test_extract_requirements_rejects_bad_top_n():
    with pytest.raises(ToolError):
        call("extract_requirements", job_description=JD, top_n=9)


def test_requirement_coverage_maps_evidence():
    out = call(
        "requirement_coverage",
        letter=LETTER,
        requirements=["Experience with Salesforce and Gainsight", "Track record of improving net revenue retention", "Fluent Mandarin"],
    )
    rows = out["requirements"]
    assert rows[0]["covered"] and rows[0]["matched_terms"] == ["gainsight", "salesforce"] and rows[0]["quantified"]
    assert rows[1]["covered"] and "112%" in rows[1]["evidence_sentence"]
    assert rows[2]["covered"] is False
    assert out["coverage_pct"] == 66.7


def test_requirement_coverage_rejects_empty_requirements():
    with pytest.raises(ToolError):
        call("requirement_coverage", letter=LETTER, requirements=[""])


def test_check_letter_scores_good_and_bad_drafts():
    good = call("check_letter", letter=LETTER, job_description=JD, company="Acme", role="Customer Success Manager")
    assert good["i_sentence_pct"] == 0.0
    assert good["cliches"] == []
    assert good["company_mentions"] == 4 and good["role_mentioned"] is True
    assert good["jd_term_overlap"]["pct"] > 40
    assert good["issues"] == [f"{good['words']} words — under 250 reads as low effort"]
    bad = call(
        "check_letter",
        letter="I am writing to apply for the job. I am a team player and hard worker. I look forward to hearing from you.",
        company="Acme",
        role="CSM",
    )
    assert bad["score"] < 20
    assert bad["i_sentence_pct"] == 100.0
    assert {c["term"] for c in bad["cliches"]} == {"i am writing to", "team player", "hard worker", "i look forward to hearing from you"}
    assert any("company name" in i for i in bad["issues"]) and any("no hook" in i for i in bad["issues"])


def test_check_letter_rejects_empty():
    with pytest.raises(ToolError):
        call("check_letter", letter="  ")


def test_requirement_coverage_marks_title_mentions_partial():
    out = call("requirement_coverage", letter="I am applying for the Customer Success Manager role. I have used Salesforce.", requirements=["Experience with Salesforce and Gainsight"])
    row = out["requirements"][0]
    assert row["status"] == "partial" and row["skills_missing"] == ["gainsight"] and out["partial"] == [1]
