"""Lead Qualifier tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("lead-qualifier")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)

ICP = {
    "industry": {"values": ["saas", "fintech"], "weight": 4},
    "employees": {"values": ["51-500"], "weight": 4},
    "seniority": {"values": ["vp", "director"], "weight": 3},
    "country": {"values": ["us", "uk"], "weight": 2},
    "tech": {"values": ["salesforce"], "weight": 3},
}


def test_parse_titles_seniority_function_and_role():
    out = call("parse_titles", titles=["VP Sales Engineering", "Head of Revenue Operations", "CFO", "Marketing Intern", "Sales Development Representative", "Founder & CEO"], buying_functions=["sales", "ops"])
    rows = {r["title"]: r for r in out["titles"]}
    assert rows["VP Sales Engineering"]["seniority"] == "vp" and rows["VP Sales Engineering"]["function"] == "engineering"
    assert rows["CFO"]["seniority"] == "c_level" and rows["CFO"]["function"] == "finance"
    assert rows["Marketing Intern"]["negative_signal"] is True and rows["Marketing Intern"]["role"] == "none"
    assert rows["Sales Development Representative"]["role"] == "user"
    assert rows["Founder & CEO"]["role"] == "buyer"
    assert out["buyers"] == 2


def test_parse_titles_bad_input():
    with pytest.raises(ToolError):
        call("parse_titles", titles=[])


def test_icp_fit_score_weights_and_caps():
    out = call(
        "icp_fit_score",
        icp=ICP,
        leads=[
            {"name": "Dana", "title": "Ops Manager", "industry": "fintech", "employees": 120, "country": "UK", "tech": "Salesforce, Slack"},
            {"name": "Bob", "title": "Student", "industry": "retail", "employees": 5000, "country": "BR", "email": "bob@gmail.com"},
        ],
    )
    dana, bob = out["ranked"]
    assert dana["name"] == "Dana" and dana["score"] == 91 and dana["tier"] == "A"  # 14.5 / 16
    assert any(m["criterion"] == "seniority" and m["points"] == 1.5 for m in dana["missed"])
    assert bob["tier"] == "D" and bob["score"] <= 34
    assert any("tier D" in c for c in bob["caps"])
    assert out["distribution"] == {"A": 1, "B": 0, "C": 0, "D": 1}


def test_icp_fit_score_unknown_fields_get_partial_credit_and_bad_input():
    out = call("icp_fit_score", icp={"industry": {"values": ["saas"], "weight": 4}}, leads=[{"name": "X"}])
    assert out["ranked"][0]["score"] == 25
    with pytest.raises(ToolError):
        call("icp_fit_score", icp={}, leads=[{"name": "X"}])
    with pytest.raises(ToolError):
        call("icp_fit_score", icp={"industry": {"values": ["saas"], "weight": 50}}, leads=[{"name": "X"}])


def test_qualification_grade_bant_and_champ():
    out = call("qualification_grade", framework="BANT", ratings={"budget": 1, "authority": {"score": 2, "evidence": "CFO signs"}, "need": 3, "timeline": 2})
    assert out["total"] == 8 and out["grade"] == "SQL"
    assert [g["element"] for g in out["gaps"]] == ["budget"]
    weak = call("qualification_grade", framework="champ", ratings={"challenges": 1, "authority": 0, "money": 1, "prioritization": 1})
    assert weak["grade"] == "unqualified" and weak["total"] == 3


def test_qualification_grade_bad_input():
    with pytest.raises(ToolError):
        call("qualification_grade", framework="SPIN", ratings={"need": 2})
    with pytest.raises(ToolError):
        call("qualification_grade", framework="BANT", ratings={"need": 7})


def test_route_lead_matrix():
    hot = call("route_lead", fit_score=80, intent="high")
    assert hot["owner"] == "AE" and hot["response_sla"] == "5 minutes" and hot["priority"] == 1
    referral = call("route_lead", fit_score=70, intent="medium", source="referral")
    assert referral["adjusted_fit"] == 80 and referral["tier"] == "A" and referral["owner"] == "SDR"
    cold = call("route_lead", fit_score=20, intent="low")
    assert cold["owner"] == "decline" and cold["priority"] == 6
    after_hours = call("route_lead", fit_score=90, intent="high", business_hours=False)
    assert "next business day" in after_hours["response_sla"]


def test_route_lead_bad_input():
    with pytest.raises(ToolError):
        call("route_lead", fit_score=120, intent="high")
    with pytest.raises(ToolError):
        call("route_lead", fit_score=50, intent="hot")


def test_country_matching_is_whole_word_with_aliases():
    icp = {"country": {"values": ["us", "uk"], "weight": 1}}
    leads = [{"name": "au", "country": "Australia"}, {"name": "ua", "country": "Ukraine"}, {"name": "usa", "country": "United States"}, {"name": "gb", "country": "England"}, {"name": "ru", "country": "Russia"}]
    by = {r["name"]: r["score"] for r in call("icp_fit_score", icp=icp, leads=leads)["ranked"]}
    assert by == {"au": 0, "ua": 0, "usa": 100, "gb": 100, "ru": 0}


def test_function_criterion_derived_from_title():
    icp = {"seniority": {"values": ["vp"], "weight": 1}, "function": {"values": ["sales", "ops"], "weight": 1}}
    leads = [{"name": "se", "title": "VP Sales Engineering"}, {"name": "revops", "title": "VP Revenue Operations"}, {"name": "ceo", "title": "CEO"}]
    by = {r["name"]: r for r in call("icp_fit_score", icp=icp, leads=leads)["ranked"]}
    assert by["se"]["score"] == 50 and by["revops"]["score"] == 100
    assert any(m["criterion"] == "function" and m["points"] == 1 for m in by["ceo"]["matched"])  # exec counts as buyer
    assert call("parse_titles", titles=["VP Revenue Operations"])["titles"][0]["function"] == "ops"


def test_company_size_far_outside_band_caps_at_tier_c():
    icp = {"industry": {"values": ["saas"], "weight": 4}, "employees": {"values": ["51-500"], "weight": 1}}
    out = call("icp_fit_score", icp=icp, leads=[{"name": "tiny", "industry": "SaaS", "employees": "8"}, {"name": "near", "industry": "SaaS", "employees": "620"}])
    by = {r["name"]: r for r in out["ranked"]}
    assert by["tiny"]["score"] == 54 and by["tiny"]["tier"] == "C" and "capped at tier C" in by["tiny"]["caps"][0]
    assert by["near"]["score"] == 90 and by["near"]["caps"] == []
