"""Product Listing Writer tools — marketplace limits, keyword coverage, title and bullet scoring."""

import pytest

from hundred.agents.ecommerce.product_listing import AGENT as A
from hundred.core import ToolError


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


TITLE = "Hydra Insulated Water Bottle 32 oz, Stainless Steel Leak Proof Bottle with Straw Lid for Gym, Travel and Hiking"
BULLETS = [
    "KEEPS DRINKS COLD 24 HOURS: Double-wall vacuum insulation holds ice for a full day so your water is still cold after the gym",
    "LEAK PROOF STRAW LID: Silicone seal and locking latch survive a bag toss; open with one hand while you drive",
    "Made of 18/8 stainless steel.",
    "BEST SELLER: Free shipping on every order!",
    "KEEPS DRINKS COLD 24 HOURS: Double wall vacuum insulation holds ice all day so water stays cold",
]
DESC = "The Hydra 32 oz insulated water bottle keeps drinks cold for 24 hours and hot for 12. <b>Fits</b> most car cup holders (3.6 in base). Dishwasher safe lid. BPA-free Tritan straw."


def test_check_marketplace_limits_amazon_rules():
    out = call(
        "check_marketplace_limits", marketplace="amazon", title=TITLE, bullets=BULLETS, description=DESC,
        backend_keywords="hydro flask water bottle thermos flask canteen insulated water bottle 32oz B08XYZ1234",
    )
    assert out["passes"] is False
    joined = " ".join(out["fails"])
    assert "promo language" in joined and "HTML" in joined and "ASIN" in joined
    assert out["fields"]["title"]["chars"] == len(TITLE)
    assert out["fields"]["backend_keywords"]["bytes"] == 85
    assert "insulated" in out["fields"]["backend_keywords"]["duplicated_from_title_bullets"]
    assert out["claims_to_verify"] == ["bpa-free"]
    long_title = call("check_marketplace_limits", marketplace="amazon", title="Best Seller! " + "Water Bottle " * 16)
    assert any("> 200 max" in f for f in long_title["fails"])
    assert any("special characters" in f for f in long_title["fails"])
    assert any("repeats a word" in f for f in long_title["fails"])


def test_check_marketplace_limits_etsy_shopify_and_overrides():
    etsy = call(
        "check_marketplace_limits", marketplace="etsy", title="Personalised Leather Journal, Custom Name Notebook, Gift for Him",
        tags=["leather journal", "personalised journal", "custom notebook", "gift for him", "journal", "leather journal", "a very long tag that exceeds twenty"],
    )
    assert any("duplicate tags" in f for f in etsy["fails"])
    assert any("> 20" in f for f in etsy["fails"])
    assert any("of 13 tags used" in w for w in etsy["warnings"])
    shop = call("check_marketplace_limits", marketplace="shopify", title="Hydra Bottle", seo_title="x" * 75, meta_description="y" * 200)
    assert any("SEO title 75" in f for f in shop["fails"])
    assert any("meta description 200" in w for w in shop["warnings"])
    over = call("check_marketplace_limits", marketplace="amazon", title=TITLE, bullets=["A" * 300], overrides={"bullet_chars_max": 500})
    assert not any("bullet 1:" in f and "chars" in f for f in over["fails"])


def test_check_marketplace_limits_rejects_unknown_marketplace():
    with pytest.raises(ToolError):
        call("check_marketplace_limits", marketplace="temu", title=TITLE)
    with pytest.raises(ToolError):
        call("check_marketplace_limits", marketplace="amazon", title="   ")


def test_keyword_coverage_maps_fields():
    out = call(
        "keyword_coverage",
        keywords=["insulated water bottle", "32 oz", "leak proof", "stainless steel water bottle", "gym water bottle", "straw lid", "hot and cold", "bike bottle cage"],
        title=TITLE, bullets=BULLETS, description=DESC, backend_keywords="thermos flask canteen insulated",
    )
    by = {k["keyword"]: k for k in out["keywords"]}
    assert by["insulated water bottle"]["status"] == "exact" and by["insulated water bottle"]["title_char_position"] == 6
    assert by["leak proof"]["exact_in"] == ["title", "bullets"]
    assert by["stainless steel water bottle"]["status"].startswith("partial")
    assert out["missing"] == ["bike bottle cage"]
    assert out["backend_wasted_words"] == ["insulated"]
    # weights: primary 3 + 4 secondary × 2 + 3 long-tail × 1 = 14; exact 3+2+2+1 = 8, partial 2·0.5+2·0.5+1·0.5 = 2.5 → 75%
    assert out["phrase_coverage_pct"] == 75.0
    # indexed (word-level, how Amazon matches): everything but "bike bottle cage" (weight 1) → 13/14
    assert out["coverage_pct"] == round(100 * 13 / 14, 1)


def test_keyword_coverage_rejects_empty_keywords():
    with pytest.raises(ToolError):
        call("keyword_coverage", keywords=[], title=TITLE)


def test_score_title():
    good = call("score_title", title=TITLE, marketplace="amazon", primary_keyword="insulated water bottle", brand="Hydra", attributes=["32 oz", "stainless steel", "leak proof", "straw lid"])
    assert good["score"] == 100 and good["checks"]["brand_first"] is True
    bad = call("score_title", title="BEST water bottle bottle bottle cheap sale", marketplace="amazon", primary_keyword="insulated water bottle", brand="Hydra", attributes=["32 oz", "leak proof"])
    assert bad["score"] < 40
    assert any("insulated water bottle" in f for f in bad["fixes"])
    assert any("promo" in f for f in bad["fixes"]) and any("repeated" in f for f in bad["fixes"])
    late = call("score_title", title="Stainless Steel Leak Proof Bottle with Straw Lid for Gym, Travel, Hiking and Camping — Hydra Insulated Water Bottle", marketplace="ebay", primary_keyword="insulated water bottle")
    assert any("mobile cut" in f for f in late["fixes"]) and any("80 chars" in f for f in late["fixes"])


def test_score_title_rejects_missing_keyword():
    with pytest.raises(ToolError):
        call("score_title", title=TITLE, marketplace="amazon", primary_keyword="")


def test_bullet_lint_flags_feature_only_promo_and_duplicates():
    out = call("bullet_lint", bullets=BULLETS, description=DESC)
    b = {r["n"]: r for r in out["bullets"]}
    assert b[1]["score"] == 100 and b[1]["has_lead_in"] is True
    assert b[3]["has_lead_in"] is False and any("feature-only" in i for i in b[3]["issues"])
    assert any("promo" in i for i in b[4]["issues"])
    assert any("overlaps heavily with bullet 1" in i for i in b[5]["issues"])
    assert out["bullets_score"] == round((100 + 90 + 60 + 55 + 90) / 5)
    assert out["description"]["fk_grade"] < 8 and out["description"]["score"] >= 80


def test_bullet_lint_rejects_empty():
    with pytest.raises(ToolError):
        call("bullet_lint", bullets=["", "  "])
