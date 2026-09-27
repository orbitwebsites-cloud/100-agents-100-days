"""LinkedIn Ghostwriter tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("linkedin-ghostwriter")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_score_hook_fold_and_specificity():
    out = call("score_hook", hook="We cut onboarding from 14 days to 3.\nOne change.")
    assert out["score"] >= 75
    assert out["fits_mobile_fold"] is True and out["chars"] == 48
    assert out["line_1"] == "We cut onboarding from 14 days to 3."
    assert out["hook_type"] == "specific result"
    assert not any("names something concrete (One)" in r for r in out["reasons"])


def test_score_hook_punishes_announcement():
    out = call("score_hook", hook="I'm thrilled to announce that I attended a conference last week and it was great and I learned so much from everyone there and wanted to share it with you all because it was amazing and long and so on and on and on and on and on and on and on.")
    assert out["score"] < 45
    assert out["fits_desktop_fold"] is False
    assert any("announcement opener" in f for f in out["fixes"])


def test_score_hook_rejects_empty():
    with pytest.raises(ToolError):
        call("score_hook", hook=" ")


def test_format_post_strips_markdown_and_moves_hashtags():
    draft = "**Big news**\n\n# Heading\n\nI turned down a $2M contract last week. Here is why I did it. It taught me something about saying no to the wrong customers, which is a lesson you can use too. Really.\n\n- one\n- two\n\n#Sales\n\nWhat would you have done?\n\n#Founders #B2B"
    out = call("format_post", draft=draft)
    f = out["formatted"]
    assert "**" not in f and "# Heading" not in f
    assert f.startswith("Big news\n\nHeading\n\n")
    assert "→ one\n→ two" in f
    assert f.endswith("#Sales #Founders #B2B")
    assert f.count("#Sales") == 1
    assert "I turned down a $2M contract last week.\nHere is why I did it." in f
    assert out["hashtags"] == ["Sales", "Founders", "B2B"]
    assert any("bold" in c for c in out["changes"]) and any("hashtags" in c for c in out["changes"])


def test_format_post_rejects_empty():
    with pytest.raises(ToolError):
        call("format_post", draft="")


def test_post_check_flags_real_problems():
    post = "I'm thrilled to announce our new #product launch https://example.com\n\n" + ("This is a long line of text that goes on. " * 8) + "\n\nThoughts?\n\n#a #b #c #d #e #f"
    out = call("post_check", post=post, hashtags_expected=3)
    flags = " ".join(out["flags"])
    assert "soft opener" in flags
    assert "7 hashtags" in flags
    assert "link(s) in the body" in flags
    assert "wall-of-text" in flags
    assert "Thoughts?" in flags
    assert out["ready"] is False
    assert out["fold_desktop_chars"] <= 210


def test_post_check_passes_a_good_post():
    post = "We cut onboarding from 14 days to 3.\n\nOne change.\n\nWe stopped sending a 40-page PDF and started with a 15-minute call. Customers told us what they needed. We built the checklist around that.\n\nThe lesson for you: ask before you document.\n\nWhat's the one document your customers never read?\n\n#CustomerSuccess #SaaS"
    out = call("post_check", post=post, hashtags_expected=2)
    assert out["flags"] == []
    assert out["ready"] is True
    assert out["hashtags"] == ["CustomerSuccess", "SaaS"]


def test_post_check_rejects_bad_hashtag_count():
    with pytest.raises(ToolError):
        call("post_check", post="hello there", hashtags_expected=99)


def test_engagement_rate_math_and_grade():
    out = call("engagement_rate", impressions=8000, reactions=120, comments=30, reposts=5, followers=20000)
    assert out["engagements"] == 155
    assert out["engagement_rate_pct"] == 1.94
    assert out["weighted_engagement_pct"] == 2.75
    assert out["comments_per_1000_impressions"] == 3.8
    assert out["reach_pct_of_followers"] == 40.0
    assert out["grade"] == "average"


def test_engagement_rate_rejects_zero_impressions():
    with pytest.raises(ToolError):
        call("engagement_rate", impressions=0, reactions=1)
