"""Blog Writer tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("blog-writer")

MD = (
    "# Cold email deliverability guide\n\n"
    "Intro about cold email deliverability for founders. " + "Here is another intro sentence. " * 8 + "\n\n"
    "## Why cold email deliverability matters\n\n" + "Because inboxes filter aggressively, and so a warm domain wins. " * 20 + "\n\n"
    "## Warm up\n\n" + "Short. " * 10 + "\n\n"
    "#### Skipped\n\ntext here\n\n"
    "## Next steps\n\nDo this now with cold email deliverability. [Source](https://example.com) ![](img.png)"
)


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_word_budget_sums_and_sections():
    out = call("word_budget", target_words=1800, format="how-to", keyword="cold email deliverability")
    assert out["h2_sections"] == 6
    assert abs(out["budget_total"] - 1800) <= 6
    assert out["budget"][0]["part"] == "Intro" and out["budget"][0]["words"] == 144
    assert any("FAQ" in p["part"] for p in out["budget"])
    assert "cold email deliverability" in out["budget"][1]["must"][-1]
    assert out["reading_minutes"] == 7.6


def test_word_budget_respects_explicit_sections():
    out = call("word_budget", target_words=1000, format="opinion", sections=3)
    assert out["h2_sections"] == 3
    assert not any("FAQ" in p["part"] for p in out["budget"])


def test_word_budget_rejects_out_of_range():
    with pytest.raises(ToolError):
        call("word_budget", target_words=100)
    with pytest.raises(ToolError):
        call("word_budget", target_words=1000, format="haiku")


def test_outline_lint_flags_structure():
    out = call("outline_lint", markdown=MD)
    assert out["h1_count"] == 1 and out["h2_count"] == 3
    assert out["intro_words"] == 55
    flags = " ".join(out["flags"])
    assert "Skipped level: H2 → H4" in flags
    assert "thin" in flags
    assert "without alt text" in flags
    assert out["links"] == 1 and out["images"] == 1
    warm = next(s for s in out["sections"] if s["title"] == "Warm up")
    assert warm["words"] == 10 and warm["flag"].startswith("thin")


def test_outline_lint_requires_headings():
    with pytest.raises(ToolError):
        call("outline_lint", markdown="just a paragraph with no headings at all")


def test_readability_report_lists_long_sentences():
    long = "This sentence keeps going and going with clause after clause and never stops because the writer forgot that readers breathe and that commas are not periods at all. "
    out = call("readability_report", markdown=long * 3 + "Short one. " * 5)
    assert out["long_sentences"] and out["long_sentences"][0]["words"] == 31
    assert out["sentence_length_buckets"][">30"] == 3
    assert out["words"] == 103
    assert any("over 30 words" in f for f in out["fixes"])


def test_readability_report_rejects_short_and_bad_grade():
    with pytest.raises(ToolError):
        call("readability_report", markdown="too short")
    with pytest.raises(ToolError):
        call("readability_report", markdown=MD, target_grade=25)


def test_keyword_audit_density_and_placement():
    out = call("keyword_audit", markdown=MD, primary_keyword="cold email deliverability", secondary_keywords=["domain warm-up"], meta_description="x" * 130)
    assert out["occurrences"] == 4
    assert out["placements"]["title"] and out["placements"]["first_100_words"] and out["placements"]["any_h2"] and out["placements"]["last_paragraph"]
    assert out["placement_score"] == "5/5"
    assert out["suggested_slug"] == "cold-email-deliverability"
    assert out["secondary"][0]["occurrences"] == 0
    assert any("domain warm-up" in f for f in out["fixes"])
    assert any("Meta description doesn't contain" in f for f in out["fixes"])
    assert out["density_band"] in ("good", "stuffing")


def test_keyword_audit_rejects_missing_keyword():
    with pytest.raises(ToolError):
        call("keyword_audit", markdown=MD, primary_keyword="  ")
