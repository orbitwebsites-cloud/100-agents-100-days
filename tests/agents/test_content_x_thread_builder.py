"""X Thread Builder tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("x-thread-builder")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_score_hook_rewards_specific_result():
    out = call("score_hook", hook="I grew my SaaS to $10k MRR in 6 months. Here's what worked:")
    assert out["score"] >= 75
    assert out["hook_type"] == "specific result"
    assert out["fits_280"] is True


def test_score_hook_punishes_soft_opener_links_hashtags():
    out = call("score_hook", hook="I'm excited to share a thread 🧵 #saas https://x.com/abc")
    assert out["score"] < 30
    assert any("soft opener" in r for r in out["reasons"])
    assert any("link in the hook" in r for r in out["reasons"])
    assert "Remove hashtags/links from the hook." in out["fixes"]


def test_score_hook_rejects_empty():
    with pytest.raises(ToolError):
        call("score_hook", hook="")


def test_count_post_uses_x_weighted_rules():
    out = call("count_post", post="Check https://example.com/very/long/url/that/is/long 👍")
    assert out["raw_chars"] == 54
    assert out["weighted_chars"] == 32  # "Check " (6) + 23 + " " (1) + emoji (2)
    assert out["urls"] == 1 and out["emoji"] == 1
    over = call("count_post", post="Sentence one is here. " * 15)
    assert over["fits"] is False and over["over_by"] == 50
    assert over["trim_to_fit"] and len(over["trim_to_fit"]) <= 280


def test_count_post_rejects_empty():
    with pytest.raises(ToolError):
        call("count_post", post="   ")


def test_split_thread_breaks_at_sentences_and_numbers():
    src = "First para sentence one. Sentence two is here.\n\n" + "This is a long sentence that keeps going. " * 12
    out = call("split_thread", source=src, numbering="1/N")
    assert out["count"] == 3
    assert out["posts"][0]["text"] == "1/3 First para sentence one. Sentence two is here."
    assert out["all_fit"] is True
    assert all(p["text"].endswith(".") for p in out["posts"])
    packed = call("split_thread", source=src, numbering="none", paragraph_mode="pack")
    assert packed["count"] == 3
    assert not packed["posts"][0]["text"].startswith("1/")


def test_split_thread_rejects_bad_limit():
    with pytest.raises(ToolError):
        call("split_thread", source="Some text here.", max_chars=10)


def test_lint_thread_catches_everything():
    out = call("lint_thread", posts=["1/ Hook here", "2/ And this https://a.com", "4/ x", "2/ And this https://a.com", "5/ bye"])
    flags = " ".join(out["flags"])
    assert "Post 2: link before the last post" in flags
    assert "dangling conjunction" in flags
    assert "duplicate of post 2" in flags
    assert "Numbering out of sequence" in flags
    assert "no CTA" in flags
    assert out["clean"] is False


def test_lint_thread_clean_case():
    out = call("lint_thread", posts=["1/ 3 pricing mistakes I see in 90% of decks:", "2/ Anchoring low. Fix: lead with the top tier.", "3/ Follow for more; full guide: https://a.com"])
    assert out["clean"] is True
    assert out["posts"][2]["weighted_chars"] == 3 + len("Follow for more; full guide: ") + 23


def test_lint_thread_rejects_bad_input():
    with pytest.raises(ToolError):
        call("lint_thread", posts=[])
    with pytest.raises(ToolError):
        A.get_tool("lint_thread").call({"posts": "not a list"})


# twitter-text v3 conformance (WeightedTweetsWithDiscountedEmojiCounterTest in
# https://github.com/twitter/twitter-text/blob/master/conformance/validate.yml)
X_CONFORMANCE = [
    ("Hi http://test.co", 26),
    ("http://test.co", 23),
    ("285 chars-" + "xxxxxxxxxx-" * 25, 285),
    ("https://www.twitter.com/aloha " * 10, 240),
    ("H🐱☺👨‍👩‍👧‍👦", 7),
    ("😷👾😡🔥💩", 10),
    ("🙋🏽👨‍🎤", 4),
    ("1⃣", 2),
    ("Unicode 10.0 emoji: 🤪; 🧕; 🧕🏾; 🏴\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f", 34),
    ("Unicode 9.0 emoji: 🤠; 💃; 💃🏾", 29),
    ("randomurlrandomurlrandomurlrandomurlrandomurlrandomurlrandomurls.com", 68),  # 64-char label: not a URL
    ("example.com", 23),  # urls_without_protocol: domain + gTLD
    ("foo.co.jp", 23),
    ("ÁB", 2),  # NFC: Á is one character
]


@pytest.mark.parametrize("post,expected", X_CONFORMANCE)
def test_count_post_matches_twitter_text_conformance(post, expected):
    assert call("count_post", post=post)["weighted_chars"] == expected


def test_flag_is_one_emoji_and_bare_domain_is_a_link():
    out = call("count_post", post="Made in the 🇺🇸 — details at acme.io/pricing.")
    assert out["emoji"] == 1 and out["urls"] == 1
    assert out["weighted_chars"] == len("Made in the ") + 2 + len(" — details at ") + 23 + 1
