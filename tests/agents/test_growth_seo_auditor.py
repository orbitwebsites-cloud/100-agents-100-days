"""SEO Auditor tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("seo-auditor")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


BODY = "Cold brew coffee is easy. " + "Grind beans coarse and steep for twelve hours in cold water. " * 40
GOOD_HTML = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Cold Brew Coffee Guide | Beans</title>
<meta name="description" content="Learn how to brew cold brew coffee at home in 5 steps with our ratio chart and steep-time table.">
<link rel="canonical" href="https://beans.com/cold-brew">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta property="og:title" content="x"><meta property="og:description" content="y"><meta property="og:image" content="https://beans.com/i.jpg">
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"Article"}}</script>
</head><body>
<h1>How to Make Cold Brew Coffee</h1><p>{BODY}</p>
<h2>Cold brew coffee ratio</h2><p>Use 1:8.</p><h3>Steps</h3>
<img src="a.jpg" alt="cold brew coffee jar" width="1" height="1"><img src="b.jpg" alt="" width="1" height="1">
<a href="/beans">buy coffee beans</a><a href="/grinders">burr grinders</a><a href="/filters">paper filters</a>
<a href="https://x.com/a" rel="noopener" target="_blank">study on caffeine</a>
</body></html>"""

BAD_HTML = """<html><head><title>Home</title><meta name="robots" content="noindex,nofollow">
<link rel="canonical" href="https://other.com/page"></head>
<body><h2>Welcome</h2><h4>Skip</h4><p>Short.</p><img src="a.jpg"><a href="#">click here</a><a href="javascript:void(0)">here</a></body></html>"""


def test_audit_page_scores_a_good_page_high():
    out = call("audit_page", html=GOOD_HTML, url="https://beans.com/cold-brew", keyword="cold brew coffee")
    assert out["score"] >= 85
    assert out["indexable"] is True
    assert out["canonical_status"] == "self"
    inv = out["inventory"]
    assert inv["title"] == "Cold Brew Coffee Guide | Beans"
    assert inv["h1"] == ["How to Make Cold Brew Coffee"]
    assert inv["links_internal"] == 3 and inv["links_external"] == 1
    assert inv["images_missing_alt"] == 0 and inv["images_empty_alt"] == 1
    assert inv["jsonld_blocks"] == 1
    assert inv["word_count"] > 300
    assert not any(i["severity"] == "critical" for i in out["issues"])


def test_audit_page_flags_blockers():
    out = call("audit_page", html=BAD_HTML, url="https://beans.com/cold-brew", keyword="cold brew")
    assert out["indexable"] is False
    assert out["canonical_status"] == "points elsewhere"
    sev = {(i["severity"], i["element"]) for i in out["issues"]}
    assert ("critical", "robots") in sev
    assert ("critical", "canonical") in sev
    assert ("high", "h1") in sev
    assert ("high", "mobile") in sev
    assert out["issues"][0]["severity"] == "critical"
    assert out["score"] < 40
    assert "Not indexable" in out["verdict"]


def test_audit_page_title_pixels_not_chars():
    wide = "<html><head><title>" + "W" * 40 + "</title></head><body><p>x</p></body></html>"
    narrow = "<html><head><title>" + "i" * 40 + "</title></head><body><p>x</p></body></html>"
    w = call("audit_page", html=wide)
    n = call("audit_page", html=narrow)
    assert w["inventory"]["title_px"] > 600 > n["inventory"]["title_px"]
    assert any("truncates" in i["problem"] for i in w["issues"] if i["element"] == "title")
    assert not any("truncates" in i["problem"] for i in n["issues"] if i["element"] == "title")


def test_audit_page_rejects_empty_and_huge():
    with pytest.raises(ToolError):
        call("audit_page", html="   ")
    with pytest.raises(ToolError):
        call("audit_page", html="<p>" + "x" * 400_001)


def test_heading_outline_finds_skips_dupes_and_missing_h1():
    html = "<body><h2>A</h2><h4>B</h4><h2>A</h2><h3></h3></body>"
    out = call("heading_outline", html=html)
    probs = {p["problem"] for p in out["problems"]}
    assert "no H1" in probs
    assert "skips from H2 to H4" in probs
    assert "appears 2 times" in probs
    assert "empty heading" in probs
    assert out["counts"] == {"h1": 0, "h2": 2, "h3": 1, "h4": 1, "h5": 0, "h6": 0}
    assert out["outline"][1] == "      H4: B"


def test_heading_outline_clean():
    out = call("heading_outline", html="<h1>Title</h1><h2>How does it work?</h2><h3>Step</h3>")
    assert out["problems"] == []
    assert out["question_headings"] == 1


def test_content_signals_placement_and_density():
    out = call("content_signals", html=GOOD_HTML, keyword="cold brew coffee")
    p = out["placement"]
    assert p["title"] and p["h1"] and p["first_100_words"] and p["meta_description"] and p["subheadings"] and p["image_alt"]
    assert out["placement_score"] == "7/7"
    assert out["occurrences"] >= 3
    assert out["thin_content"] is False
    assert out["token_coverage"] == {"cold": True, "brew": True, "coffee": True}
    assert out["readability"]["words"] == out["word_count"]


def test_content_signals_detects_stuffing_and_thin():
    html = "<html><head><title>x</title></head><body><p>" + "cheap shoes " * 30 + "</p></body></html>"
    out = call("content_signals", html=html, keyword="cheap shoes")
    assert out["thin_content"] is True
    assert out["stuffing_risk"] is True
    assert out["density_pct"] > 50
    with pytest.raises(ToolError):
        call("content_signals", html=html, keyword="x")


def test_link_audit_classifies_and_lints():
    html = """<a href="/a">Pricing plans</a><a href="/a">plans</a><a href="/a">see pricing</a>
    <a href="https://ext.com/x" target="_blank">click here</a><a href="http://ext.com/y">http://ext.com/y</a>
    <a href="#">menu</a><a href="mailto:a@b.c">mail</a><a href="/img"><img src="i.png" alt="Logo"></a><a href="/e"></a>"""
    out = call("link_audit", html=html, base_url="https://site.com/page")
    assert out["counts"] == {"internal": 5, "external": 2, "non_navigational": 2, "external_nofollow": 0, "duplicate_internal_targets": 1}
    probs = {p["problem"] for p in out["problems"]}
    assert "generic anchor" in probs
    assert "target=_blank without rel=noopener" in probs
    assert "naked URL as anchor" in probs
    assert "http link on https page" in probs
    assert "non-crawlable href" in probs
    assert "empty anchor (no text or alt)" in probs
    assert any("3 different anchors" in p for p in probs)
    assert any(l["anchor"] == "Logo" for l in out["internal"])


def test_link_audit_bad_input():
    with pytest.raises(ToolError):
        call("link_audit", html="")
    with pytest.raises(ToolError):
        A.get_tool("link_audit").call({"html": 5})


def test_parameterised_url_gets_clean_canonical_and_url_hygiene():
    html = GOOD_HTML.replace('<link rel="canonical" href="https://beans.com/cold-brew">', "").replace('<img src="a.jpg"', '<img src="http://cdn.beans.com/a.jpg"')
    out = call("audit_page", html=html, url="https://beans.com/Cold_Brew?utm_source=x", keyword="cold brew coffee")
    canon = next(i for i in out["issues"] if i["element"] == "canonical")
    assert canon["severity"] == "high"
    assert 'href="https://beans.com/Cold_Brew"' in canon["fix"] and "utm_source" not in canon["fix"]
    url = next(i for i in out["issues"] if i["element"] == "url")
    assert "uppercase" in url["problem"] and "underscores" in url["problem"] and "query parameters" in url["problem"]
    assert "/cold-brew" in url["fix"]
    assert any(i["element"] == "security" and "Mixed content" in i["problem"] for i in out["issues"])
    clean = call("audit_page", html=GOOD_HTML, url="https://beans.com/cold-brew", keyword="cold brew coffee")
    assert not any(i["element"] in ("url", "security") for i in clean["issues"])


def test_content_signals_checks_keyword_in_slug():
    out = call("content_signals", html=GOOD_HTML, keyword="cold brew coffee", url="https://beans.com/cold-brew")
    assert out["placement"]["url"] is False and out["placement_score"].endswith("/8")
    assert any("URL slug lacks the keyword" in f for f in out["fixes"])
    ok = call("content_signals", html=GOOD_HTML, keyword="cold brew coffee", url="https://beans.com/cold-brew-coffee")
    assert ok["placement"]["url"] is True


def test_image_alt_length_and_size_attributes():
    html = GOOD_HTML.replace('<img src="b.jpg" alt="" width="1" height="1">', '<img src="b.jpg" alt="' + "cold brew coffee " * 8 + '">')
    out = call("audit_page", html=html, url="https://beans.com/cold-brew", keyword="cold brew coffee")
    probs = [i["problem"] for i in out["issues"] if i["element"] == "images"]
    assert "1 alt text(s) over 100 characters" in probs
    assert "1 image(s) lack width/height (layout shift / CLS)" in probs
