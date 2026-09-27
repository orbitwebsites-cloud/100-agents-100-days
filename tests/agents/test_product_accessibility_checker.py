"""Accessibility Checker tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("accessibility-checker")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_contrast_ratio_black_on_white_is_21():
    out = call("contrast_ratio", foreground="#000000", background="#ffffff")
    assert out["ratio"] == 21.0
    assert out["aaa_normal_text"] is True and out["non_text_ui"] is True


@pytest.mark.parametrize(
    "fg,bg,ratio,aa_normal,aa_large",
    [
        ("#767676", "#ffffff", 4.54, True, True),
        ("#777777", "#fff", 4.48, False, True),
        ("#3b82f6", "white", 3.68, False, True),
        ("rgb(255,255,255)", "rgb(255,255,255)", 1.0, False, False),
    ],
)
def test_contrast_ratio_known_values(fg, bg, ratio, aa_normal, aa_large):
    out = call("contrast_ratio", foreground=fg, background=bg)
    assert out["ratio"] == ratio
    assert out["aa_normal_text"] is aa_normal and out["aa_large_text"] is aa_large


def test_contrast_ratio_large_text_threshold_and_alpha():
    out = call("contrast_ratio", foreground="#777777", background="#ffffff", font_px=18, bold=True)
    assert out["text_size"] == "large" and out["this_text"]["aa"] is True
    half = call("contrast_ratio", foreground="#00000080", background="#ffffff")
    assert 5.0 < half["ratio"] < 6.0 and "flattened" in half["foreground"]


def test_contrast_ratio_rejects_bad_colour():
    with pytest.raises(ToolError):
        call("contrast_ratio", foreground="#12", background="#fff")


def test_suggest_color_finds_passing_shade():
    out = call("suggest_color", foreground="#3b82f6", background="#ffffff", target_ratio=4.5)
    assert out["already_passes"] is False
    assert out["suggestion"] == "#3472d8" and out["options"][0]["ratio"] >= 4.5
    check = call("contrast_ratio", foreground=out["suggestion"], background="#ffffff")
    assert check["aa_normal_text"] is True
    ok = call("suggest_color", foreground="#000", background="#fff")
    assert ok["already_passes"] is True


def test_suggest_color_rejects_bad_adjust():
    with pytest.raises(ToolError):
        call("suggest_color", foreground="#000", background="#fff", adjust="both")


HTML = """<html><head><title></title></head><body>
<h1>Sign up</h1><h3>Details</h3>
<img src="hero.png">
<img src="a.jpg" alt="a.jpg">
<label for="email">Email</label><input id="email" type="email">
<input type="password" placeholder="Password">
<a href="/x"></a>
<a href="/pricing">click here</a>
<div onclick="go()">Go</div>
<button aria-label="Close">×</button>
<div id="dup"></div><div id="dup"></div>
<table><tr><td>1</td></tr></table>
</body></html>"""


def test_lint_html_reports_structure_findings():
    out = call("lint_html", html=HTML)
    f = out["findings"]
    crit = {(x["criterion"], x["problem"]) for x in f}
    assert ("1.1.1", "no alt attribute") in crit
    assert ("1.1.1", "alt is a filename or 'image of'") in crit
    assert any("form control has no label" in x["problem"] and "placeholder" in x["fix"] for x in f)
    assert any("no accessible name" in x["problem"] for x in f)
    assert any("not descriptive" in x["problem"] for x in f)
    assert any("clickable div" in x["problem"] for x in f)
    assert any("duplicate id" in x["problem"] for x in f)
    assert any("heading level skips" in x["problem"] for x in f)
    assert ("3.1.1", "no lang attribute") in crit
    assert ("2.4.2", "missing or empty page title") in crit
    assert any("<th>" in x["problem"] for x in f)
    assert out["counts"]["blocker"] == 4
    assert out["stats"]["headings"] == [1, 3] and out["stats"]["images"] == 2
    assert f[0]["severity"] == "blocker" and f[-1]["severity"] == "minor"


def test_lint_html_clean_fragment_has_no_blockers():
    out = call("lint_html", html='<h2>Card</h2><img src="x.png" alt="Team photo at the 2026 offsite"><button>Save changes</button>')
    assert out["counts"]["blocker"] == 0 and out["counts"]["major"] == 0


def test_lint_html_rejects_empty():
    with pytest.raises(ToolError):
        call("lint_html", html="")


def test_target_size_thresholds():
    out = call("target_size", targets=[{"name": "icon", "width": 20, "height": 20}, {"name": "icon spaced", "width": 20, "height": 20, "spacing": 6}, {"name": "cta", "width": 48, "height": 44}, {"name": "link", "width": 12, "height": 12, "inline": True}])
    t = {r["name"]: r for r in out["targets"]}
    assert t["icon"]["aa_2_5_8"] is False and t["icon spaced"]["aa_2_5_8"] is True
    assert t["cta"]["aaa_2_5_5"] is True and t["link"]["aa_2_5_8"] is True
    assert out["aa_failures"] == 1 and out["aaa_failures"] == 2


def test_target_size_rejects_bad_dims():
    with pytest.raises(ToolError):
        call("target_size", targets=[{"name": "x", "width": "big", "height": 10}])
