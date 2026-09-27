"""Local SEO tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("local-seo")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


LISTINGS = [
    {"source": "gbp", "name": "Joe's Plumbing LLC", "address": "123 North Main Street, Suite 4, Austin, TX 78701", "phone": "(512) 555-0100", "website": "https://joesplumbing.com"},
    {"source": "yelp", "name": "Joe's Plumbing", "address": "123 N. Main St. #4, Austin, TX 78701-1234", "phone": "512.555.0100", "website": "http://www.joesplumbing.com/"},
    {"source": "facebook", "name": "Joes Plumbing & Heating", "address": "125 N Main St Ste 4 Austin TX 78701", "phone": "512-555-0199"},
]


def test_nap_consistency_normalises_and_flags_real_mismatches():
    out = call("nap_consistency", listings=LISTINGS)
    assert out["canonical"] == {"name": "Joe's Plumbing LLC", "address": "123 North Main Street, Suite 4, Austin, TX 78701", "phone": "(512) 555-0100", "phone_digits": "5125550100"}
    assert {(m["source"], m["field"]) for m in out["mismatches"]} == {("facebook", "name"), ("facebook", "address"), ("facebook", "phone")}
    assert [t["status"] for t in out["table"]] == ["ok", "ok", "name, address, phone"]
    assert {c["field"] for c in out["cosmetic_variants"]} == {"name", "address", "phone"}
    assert out["consistency_pct"] == 67
    clean = call("nap_consistency", listings=LISTINGS[:2])
    assert clean["mismatches"] == [] and clean["verdict"].startswith("NAP is consistent")
    with pytest.raises(ToolError):
        call("nap_consistency", listings=[LISTINGS[0]])


def test_gbp_completeness_scores_and_orders_fixes():
    out = call("gbp_completeness", profile={"primary_category": "Plumber", "name_clean": True, "phone": "x", "hours": True, "description": "a" * 300, "photos": 4, "posts_days_since_last": 40, "review_response_rate": 95, "bogus": 1})
    assert out["score"] == 48 and out["grade"] == "D"
    assert out["missing"][0]["field"] in ("photos", "services_or_products")
    assert out["missing"][0]["weight"] == 8
    assert out["unknown_fields_ignored"] == ["bogus"]
    assert "review_response_rate" in out["present"]
    full = call("gbp_completeness", profile={"primary_category": "Plumber", "secondary_categories": ["Drainage service"], "name_clean": True, "address_or_service_area": "x", "phone": "x", "website": "x", "hours": True, "description": "a" * 400, "photos": 30, "services_or_products": 8, "attributes": 5, "posts_days_since_last": 3, "qa_seeded": True, "reviews_count": 50, "review_response_rate": 1})
    assert full["score"] == 100 and full["missing"] == []
    with pytest.raises(ToolError):
        call("gbp_completeness", profile={})


def test_review_stats_math_and_velocity():
    out = call("review_stats", reviews=[{"date": "2026-09-01", "rating": 5}, {"date": "2026-08-15", "rating": 4}, {"date": "2026-07-10", "rating": 2}, {"date": "2026-03-10", "rating": 5}, {"date": "2026-02-01", "rating": 5}], target_rating=4.5, today="2026-09-27")
    assert out["average"] == 4.2 and out["displayed_rating"] == 4.2
    assert out["distribution"] == {"5": 3, "4": 1, "3": 0, "2": 1, "1": 0}
    assert out["five_star_reviews_needed_for_target"] == 3  # (21+15)/8 = 4.5
    assert out["velocity_per_month_last_90d"] == 1.0
    assert out["trend"] == "accelerating"
    assert out["days_since_last_review"] == 26
    eighty_seven = call("review_stats", reviews=[{"rating": 4}] * 87, target_rating=4.5)
    assert eighty_seven["five_star_reviews_needed_for_target"] == 87
    assert call("review_stats", reviews=[{"rating": 5}] * 3, target_rating=4.5)["five_star_reviews_needed_for_target"] == 0
    with pytest.raises(ToolError):
        call("review_stats", reviews=[{"rating": 6}])
    with pytest.raises(ToolError):
        call("review_stats", reviews=[{"rating": 5, "date": "last week"}])


def test_review_response_lint_passes_good_and_blocks_bad():
    good = call("review_response_lint", review="They were 40 minutes late and the plumber was rude about it.", rating=2, response="Hi Dana, thank you for telling us. Being 40 minutes late and then rude about it is not the plumbing service we promise in Austin, and I am sorry — that is on us. I have spoken with the plumber and we are changing how we confirm arrival windows. Please call me directly at (512) 555-0100 so I can make this right. — Joe", reviewer_name="Dana", business_keywords=["plumbing", "austin"])
    assert good["passes"] is True and good["score"] == 100 and good["issues"] == []
    assert "apologises" in good["good"] and "takes ownership" in good["good"] and "moves it offline" in good["good"]
    bad = call("review_response_lint", review="Rude", rating=1, response="Dear valued customer, that is not true, you were late. We will give you a discount if you remove the review.", reviewer_name="Sam")
    assert bad["blocking"] is True and bad["passes"] is False
    assert any("Incentive" in i for i in bad["issues"])
    assert any("Defensive" in i for i in bad["issues"])
    assert any("Template phrase" in i for i in bad["issues"])
    pos = call("review_response_lint", review="Great service, fast install", rating=5, response="Thanks Mia! Glad the install was fast. See you next time.", reviewer_name="Mia")
    assert pos["sentiment"] == "positive" and pos["passes"] is True
    with pytest.raises(ToolError):
        call("review_response_lint", review="x", rating=9, response="y")
    with pytest.raises(ToolError):
        call("review_response_lint", review="x", rating=3, response="")
