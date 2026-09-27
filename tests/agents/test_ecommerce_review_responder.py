"""Review Responder tools — tagging, reply lint, rating maths, policy checks."""

import pytest

from hundred.agents.ecommerce.review_responder import AGENT as A
from hundred.core import ToolError


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


REVIEWS = [
    {"id": "r1", "rating": 2, "text": "Took 3 weeks to arrive and the lid was cracked. Support never answered my emails.", "reviewer": "Dana", "date": "2026-09-25"},
    {"id": "r2", "rating": 5, "text": "Love it, keeps ice all day and fits my car cup holder. Highly recommend.", "reviewer": "Sam", "date": "2026-08-01"},
    {"id": "r3", "rating": 3, "text": "Runs small, had to size up. Otherwise decent quality for the price.", "date": "2026-09-20"},
    {"id": "r4", "rating": 1, "text": "Stopped working after two weeks. Want a refund.", "date": "2026-09-26"},
]


def test_tag_reviews_tags_queue_and_aggregates():
    out = call("tag_reviews", reviews=REVIEWS, today="2026-09-27")
    by = {r["id"]: r for r in out["reviews"]}
    assert set(by["r1"]["issue_tags"]) == {"shipping_delay", "damaged_on_arrival", "customer_service"}
    assert by["r1"]["sentiment"] == "negative" and by["r1"]["urgency"] == "reply today" and by["r1"]["days_old"] == 2
    assert by["r2"]["issue_tags"] == ["praise_quality"] and by["r2"]["urgency"] == "optional / sample"
    assert "sizing_fit" in by["r3"]["issue_tags"] and by["r3"]["sentiment"] == "mixed"
    assert set(by["r4"]["issue_tags"]) == {"defect_quality", "returns_refund"}
    assert out["queue_order"][:2] == ["r4", "r1"] and out["queue_order"][-1] == "r2"
    assert out["average_rating"] == 2.75 and out["distribution"] == {"1": 1, "2": 1, "3": 1, "5": 1}
    assert out["negative_share_pct"] == 50.0
    assert out["issues"][0]["share_pct"] == 25.0
    assert out["escalate_upstream"] == []  # too few reviews per issue to escalate


def test_tag_reviews_rejects_bad_rating():
    with pytest.raises(ToolError):
        call("tag_reviews", reviews=[{"id": "x", "rating": 7, "text": "ok"}])
    with pytest.raises(ToolError):
        call("tag_reviews", reviews=[])


GOOD = (
    "Hi Dana, I'm sorry your bottle took three weeks and arrived with a cracked lid, and that our support emails went unanswered — that is on us. "
    "I've sent a new lid today and we've fixed the inbox routing that swallowed your messages. If anything else is off, email me directly at "
    "care@hydra.com and I'll make it right. — Maya, Customer Care"
)
BAD = "We are sorry you feel that way. However, our policy states shipping times are estimates. We have refunded you $10 and applied a 20% off coupon. Order #12345. Thank you for your feedback!"


def test_lint_response_good_and_bad():
    good = call("lint_response", response=GOOD, review_text=REVIEWS[0]["text"], rating=2, reviewer_name="Dana", platform="amazon")
    assert good["score"] == 100 and good["ready_to_post"] is True
    assert "cracked" in good["mirrored_terms"]
    bad = call("lint_response", response=BAD, review_text=REVIEWS[0]["text"], rating=2, reviewer_name="Dana")
    assert bad["score"] < 30 and bad["ready_to_post"] is False
    joined = " ".join(bad["issues"])
    for needle in ("non-apology", "defensive", "public money", "personal/order data", "no offline path", "template smell", "by name"):
        assert needle in joined
    positive = call("lint_response", response="Thanks Sam — glad it fits the cup holder and keeps the ice going all day. Tip: leave the lid off overnight and it never picks up a smell. — Maya", review_text=REVIEWS[1]["text"], rating=5, reviewer_name="Sam")
    assert positive["score"] >= 90


def test_lint_response_rejects_bad_input():
    with pytest.raises(ToolError):
        call("lint_response", response="", review_text="x", rating=2)
    with pytest.raises(ToolError):
        call("lint_response", response="Hi", review_text="x", rating=9)


def test_rating_math_formula():
    # k = 180·(4.5 − 4.2) ÷ (5 − 4.5) = 108
    out = call("rating_math", current_average=4.2, review_count=180, target_average=4.5, monthly_reviews=20)
    assert out["reviews_needed_if_all_new_rating"] == 108
    assert out["blended_new_rating"] == round(0.85 * 5 + 0.15 * 2.5, 2)
    assert out["reviews_needed_realistic"] == 432
    assert out["average_after_one_1_star"] == round((4.2 * 180 + 1) / 181, 3)
    assert out["five_stars_to_offset_one_1_star"] == 4  # (4.2−1)/(5−4.2) = 4
    assert out["months_at_current_velocity"] == 21.6
    already = call("rating_math", current_average=4.6, review_count=50, target_average=4.5)
    assert already["reviews_needed"] == 0


def test_rating_math_rejects_impossible():
    with pytest.raises(ToolError):
        call("rating_math", current_average=4.2, review_count=100, target_average=4.8, new_rating=4.5)
    with pytest.raises(ToolError):
        call("rating_math", current_average=6, review_count=100, target_average=4.8)


def test_check_reportable():
    courier = call("check_reportable", review_text="The FedEx driver left it on the porch and it was stolen. Never got it.", platform="amazon", fulfilled_by_platform=True)
    assert courier["likely_removable"] is True and "courier" in courier["reportable_reasons"][0]["reason"]
    honest = call("check_reportable", review_text="Product broke in a week, poor quality.", platform="google")
    assert honest["reportable_reasons"] == [] and honest["likely_removable"] is False
    pii = call("check_reportable", review_text="Terrible. Call me at 555-123-4567 and explain yourselves.", platform="etsy")
    assert any("personal information" in r["reason"] for r in pii["reportable_reasons"])
    with pytest.raises(ToolError):
        call("check_reportable", review_text="   ")
