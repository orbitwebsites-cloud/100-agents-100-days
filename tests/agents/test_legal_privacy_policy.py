"""Privacy Policy Drafter tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("privacy-policy")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_classify_data_inventory_categories_and_flags():
    out = call(
        "classify_data_inventory",
        data_items=[
            {"data": "email address", "purpose": "account login, marketing newsletter", "retention": "until account deletion"},
            {"data": "GPS location", "purpose": "show nearby stores"},
            {"data": "health conditions", "purpose": "personalise plans", "shared_with": "Mixpanel, AWS"},
            {"data": "advertising ID", "purpose": "retargeting ads", "shared_with": "Meta"},
        ],
    )
    items = {i["data"]: i for i in out["items"]}
    assert "contact" in items["email address"]["categories"]
    bases = [b["basis"] for b in items["email address"]["lawful_bases"]]
    assert any("contract" in b for b in bases) and any("consent" in b for b in bases)
    assert items["GPS location"]["cpra_sensitive"] is True and items["GPS location"]["gdpr_special_category"] is False
    assert items["health conditions"]["gdpr_special_category"] is True
    assert out["special_category_data"] == ["health conditions"]
    assert out["sale_or_share_candidates"] == ["advertising ID"]
    assert out["recipients"] == ["AWS", "Meta", "Mixpanel"]
    assert out["dpia_recommended"] is True


def test_classify_data_inventory_rejects_missing_data():
    with pytest.raises(ToolError):
        call("classify_data_inventory", data_items=[{"purpose": "x"}])


def test_check_applicability_thresholds():
    out = call("check_applicability", company_country="US", user_regions=["US", "EU"], annual_revenue_usd=5_000_000, consumers_per_year=150_000, sells_or_shares_data=True)
    assert "GDPR (EU/EEA)" in out["regime_names"]
    states = next(r for r in out["regimes"] if r["regime"] == "US state privacy laws")["states"]
    laws = {s["law"] for s in states}
    assert "CCPA/CPRA" in laws and "VCDPA" in laws and "UCPA" not in laws
    small = call("check_applicability", company_country="US", user_regions=["US"], annual_revenue_usd=1_000_000, consumers_per_year=5_000)
    assert any("below state thresholds" in n for n in small["regime_names"])
    kids = call("check_applicability", company_country="UK", user_regions=["UK", "US"], audience="children")
    assert any("COPPA" in n for n in kids["regime_names"]) and any("UK GDPR" in n for n in kids["regime_names"])


def test_check_applicability_rejects_bad_audience():
    with pytest.raises(ToolError):
        call("check_applicability", company_country="US", user_regions=["US"], audience="everyone")
    with pytest.raises(ToolError):
        call("check_applicability", company_country="US", user_regions=[])


POLICY = """Privacy Policy. Effective January 1, 2026. Acme Inc is the data controller; contact us at privacy@acme.com.
Information we collect: identifiers such as name and email, internet activity, and geolocation data. We use it to provide the service
under the performance of a contract and for our legitimate interests in security. We share it with service providers such as Stripe and AWS.
International transfers rely on standard contractual clauses. We retain account data for 2 years after closure. You have the right to access,
rectify, erase, restrict, port and object, and to withdraw consent and lodge a complaint with a supervisory authority; we respond within one month.
California residents: we do not sell or share personal information; you have the right to know, delete, correct and to non-discrimination; we
honor Global Privacy Control signals and respond within 45 days; we verify requests and accept authorized agents. Cookies are described below.
Children under 13 may not use the service. We use encryption. We will post changes to this policy here."""


def test_required_sections_audits_existing_policy():
    out = call("required_sections", regimes=["GDPR", "CCPA"], policy_text=POLICY)
    assert out["regimes_applied"] == ["CCPA", "GDPR"]
    missing = {m["section"] for m in out["missing"]}
    assert "automated" in missing and "lookback" in missing
    assert "lawful_basis" not in missing and "transfers" not in missing and "gpc" not in missing
    assert out["coverage_pct"] >= 70
    bare = call("required_sections", regimes=["COPPA"])
    assert bare["coverage_pct"] is None and bare["required_count"] == 16


def test_required_sections_rejects_bad_type():
    with pytest.raises(ToolError):
        call("required_sections", regimes="GDPR")


def test_lint_policy_text_scores_vagueness():
    bad = call("lint_policy_text", policy_text="We take your privacy seriously. From time to time we may share your information with partners for business purposes, including but not limited to marketing. We keep data as long as necessary.")
    phrases = {f["phrase"].lower() for f in bad["vague_phrases"]}
    assert "from time to time" in phrases and "including, but not limited to".replace(", ", " ") in phrases or "including but not limited to" in phrases
    assert "effective_date" in bad["missing_basics"] and "contact_channel" in bad["missing_basics"]
    assert bad["score"] < 60
    good = call("lint_policy_text", policy_text=POLICY)
    assert good["score"] > bad["score"] and good["basics"]["contact_channel"] is True


def test_lint_policy_text_rejects_bad_grade():
    with pytest.raises(ToolError):
        call("lint_policy_text", policy_text=POLICY, target_grade=30)


def test_check_applicability_whole_word_regions_and_ccpa_prong_b():
    ca = call("check_applicability", company_country="US", user_regions=["California"], consumers_per_year=150_000)
    assert not any("PIPEDA" in n for n in ca["regime_names"]) and "CalOPPA (California)" in ca["regime_names"]
    assert "US state privacy laws" not in ca["regime_names"] and ca["not_triggered_notes"]
    assert call("check_applicability", company_country="US", user_regions=["Austria"])["regime_names"] == ["GDPR (EU/EEA)"]
    bought = call("check_applicability", company_country="US", user_regions=["California"], consumers_per_year=150_000, buys_personal_data=True)
    assert "US state privacy laws" in bought["regime_names"]
