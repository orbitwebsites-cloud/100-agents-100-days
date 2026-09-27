"""Newsletter Editor tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("newsletter-editor")

ISSUE = (
    "Hi all, quick intro here.\n\n## Lead: Stripe changed fees\n\n" + "Here is the lead story sentence with detail. " * 30
    + "[Read the full analysis](https://example.com/fees?ref=x) and [here](https://example.com/fees).\n\n"
    "## Quick hits\n\nOne liner. https://foo.com/bar\n\n## Close\n\nThanks for reading, hit reply. — Sam"
)


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_issue_audit_sections_and_balance():
    out = call("issue_audit", markdown=ISSUE, target_minutes=3)
    assert out["words"] == 270  # headings count toward reading time; sections exclude them
    assert out["reading_minutes"] == 1.1
    lead = next(s for s in out["sections"] if s["section"].startswith("Lead"))
    assert lead["words"] == 246 and lead["links"] == 2 and lead["share_pct"] > 90
    flags = " ".join(out["flags"])
    assert "thin" in flags and "split it or cut" in flags and "stub" in flags
    assert out["links"] == 3


def test_issue_audit_rejects_short():
    with pytest.raises(ToolError):
        call("issue_audit", markdown="Too short.")
    with pytest.raises(ToolError):
        call("issue_audit", markdown=ISSUE, target_minutes=0)


def test_subject_line_check_scores_bad_and_good():
    bad = call("subject_line_check", subject="FREE!!! Newsletter #42 Weekly update", preheader="View in browser")
    assert bad["score"] < 45
    assert "free" in bad["spam_triggers"]
    assert any("View in browser" in f for f in bad["preheader"]["flags"])
    good = call("subject_line_check", subject="The 3-email sequence that got 41% replies", preheader="Plus the exact send times we tested across 12,000 sends")
    assert good["score"] >= 80
    assert good["fits_mobile"] is False and good["fits_desktop"] is True
    assert good["preheader"]["in_range"] is True


def test_subject_line_check_rejects_empty():
    with pytest.raises(ToolError):
        call("subject_line_check", subject="")


def test_link_audit_flags_anchors_and_utm():
    out = call("link_audit", markdown=ISSUE)
    assert out["count"] == 3
    assert out["unique_destinations"] == 2
    flags = " ".join(out["flags"])
    assert "generic anchor" in flags and "naked URL" in flags and "without UTM" in flags and "duplicate" in flags
    assert out["urls_to_tag"] == ["https://example.com/fees?ref=x", "https://example.com/fees", "https://foo.com/bar"]
    assert out["by_domain"]["example.com"] == 2


def test_link_audit_rejects_empty():
    with pytest.raises(ToolError):
        call("link_audit", markdown="  ")


def test_tag_links_preserves_query_and_fragment():
    out = call("tag_links", urls=["https://example.com/fees?ref=x#top", "mailto:a@b.com", "https://x.com/?utm_source=old", "foo.com/bar"], campaign="Issue 42")
    assert out["tagged"][0] == "https://example.com/fees?ref=x&utm_source=newsletter&utm_medium=email&utm_campaign=issue-42#top"
    assert out["results"][1]["status"] == "skipped: not a web link"
    assert out["results"][2]["status"].startswith("already tagged — left alone")
    assert "missing utm_medium, utm_campaign" in out["results"][2]["status"]
    assert out["tagged"][3] == "https://foo.com/bar?utm_source=newsletter&utm_medium=email&utm_campaign=issue-42"
    assert out["tagged_count"] == 2 and out["skipped_count"] == 2
    re_tagged = call("tag_links", urls=["https://x.com/?utm_source=old&page=2"], campaign="c", overwrite=True)
    assert re_tagged["tagged"][0] == "https://x.com/?page=2&utm_source=newsletter&utm_medium=email&utm_campaign=c"


def test_tag_links_requires_campaign():
    with pytest.raises(ToolError):
        call("tag_links", urls=["https://a.com"], campaign="")
    with pytest.raises(ToolError):
        call("tag_links", urls=[], campaign="x")
