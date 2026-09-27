"""Meta Writer tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("meta-writer")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_serp_preview_measures_pixels_and_truncates():
    long_title = "The Complete, Definitive and Ultimate Guide to Sourdough Starter Maintenance | BakeHouse"
    out = call("serp_preview", title=long_title, description="Keep your starter alive with a 5-step feeding schedule.", url="https://bakehouse.com/guides/sourdough-starter")
    t = out["title"]["desktop"]
    assert t["fits"] is False
    assert 800 < t["px"] < 860
    assert t["visible"].endswith("…")
    assert t["visible"].startswith("The Complete, Definitive and Ultimate Guide to")
    assert out["title"]["mobile"]["fits"] is True
    assert out["description"]["desktop"]["fits"] is True
    assert out["breadcrumb"] == "bakehouse.com › guides › sourdough-starter"
    assert "cut on desktop" in out["verdict"]


def test_serp_preview_width_depends_on_glyphs():
    wide = call("serp_preview", title="W" * 30)["title"]["desktop"]["px"]
    narrow = call("serp_preview", title="i" * 30)["title"]["desktop"]["px"]
    assert wide > 2.5 * narrow
    with pytest.raises(ToolError):
        call("serp_preview", title="   ")


def test_score_title_good_vs_bad():
    good = call("score_title", title="Standing Desk for Small Spaces: 7 Picks Under $300 | DeskLab", keyword="standing desk for small spaces", brand="DeskLab")
    assert good["score"] >= 80
    assert good["keyword_position"] == 0
    assert "number" in good["click_triggers"]
    bad = call("score_title", title="DESKLAB | Home", keyword="standing desk", brand="DeskLab")
    assert bad["score"] < 50
    assert any("missing" in f for f in bad["fixes"])
    assert any("Brand first" in f for f in bad["fixes"])
    repeated = call("score_title", title="Standing Desk | Standing Desk for Small Spaces | Standing Desk", keyword="standing desk")
    assert any("repeated" in f.lower() for f in repeated["fixes"])
    assert any("separator" in f for f in repeated["fixes"])


def test_score_title_bad_input():
    with pytest.raises(ToolError):
        call("score_title", title="x", keyword="")


def test_score_description_checks():
    good = call("score_description", description="Compare 7 standing desks for small spaces under 30 inches wide, with real measurements, prices and our pick for studio apartments.", keyword="standing desks for small spaces")
    assert good["score"] >= 80 and good["fits_desktop"] and good["has_number"] and good["has_keyword"]
    bad = call("score_description", description="We are a leading provider of desks.", keyword="standing desk", title="Standing desk")
    assert bad["score"] < 50
    assert any("Company-speak" in f for f in bad["fixes"])
    assert any("too short" in f for f in bad["fixes"])
    dup = call("score_description", description="Standing desks for small spaces guide and picks", keyword="standing desks", title="Standing desks for small spaces guide and picks")
    assert dup["title_overlap"] == 1.0
    assert any("restates the title" in f for f in dup["fixes"])
    with pytest.raises(ToolError):
        call("score_description", description="", keyword="x")


def test_audit_snippets_finds_duplicates_and_limits():
    rows = [
        {"url": "/a", "title": "Standing Desk Guide", "description": "x" * 30},
        {"url": "/b", "title": "standing desk guide"},
        {"url": "/c", "title": "Standing Desks Guide 2026", "description": "y" * 200},
        {"url": "/d", "title": ""},
        {"url": "/e", "title": "W" * 60, "description": "z" * 30},
    ]
    out = call("audit_snippets", rows=rows)
    c = out["counts"]
    assert c["duplicate_title_groups"] == 1
    assert out["duplicate_titles"][0]["urls"] == ["/a", "/b"]
    assert c["near_duplicate_title_pairs"] == 2
    assert c["missing_title"] == 1
    assert c["missing_description"] == 2
    assert c["title_too_long"] == 1
    assert c["description_too_long"] == 1
    assert out["problems"][0]["severity"] == "high"
    with pytest.raises(ToolError):
        call("audit_snippets", rows=[])
