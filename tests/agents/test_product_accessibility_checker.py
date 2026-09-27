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
        ("#777777", "#fff", 4.47, False, True),  # WebAIM shows 4.47 (truncated), exact 4.478
        ("#3b82f6", "white", 3.67, False, True),  # WebAIM 3.67
        ("#5a7c87", "#ffffff", 4.49, False, True),  # exact 4.499 — must never display as a failing "4.5"
        ("rgb(255,255,255)", "rgb(255,255,255)", 1.0, False, False),
    ],
)
def test_contrast_ratio_known_values(fg, bg, ratio, aa_normal, aa_large):
    out = call("contrast_ratio", foreground=fg, background=bg)
    assert out["ratio"] == ratio
    assert out["aa_normal_text"] is aa_normal and out["aa_large_text"] is aa_large


def test_contrast_ratio_large_text_threshold_and_alpha():
    out = call("contrast_ratio", foreground="#777777", background="#ffffff", font_px=19, bold=True)
    assert out["text_size"] == "large" and out["this_text"]["aa"] is True
    small_bold = call("contrast_ratio", foreground="#777777", background="#ffffff", font_px=18, bold=True)
    assert small_bold["text_size"] == "normal"  # 14pt bold = 18.66px; 18px bold is still "normal"
    half = call("contrast_ratio", foreground="#00000080", background="#ffffff")
    assert 3.9 < half["ratio"] < 4.1 and half["foreground"].startswith("#7f7f7f") and "flattened" in half["foreground"]


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


def test_lint_html_accessible_names_from_img_alt_are_not_flagged():
    out = call("lint_html", html='<a href="/"><img src="h.svg" alt="Acme home"></a><button><img src="a.svg" alt="Create account"></button>'
               '<button><svg aria-label="Close dialog"></svg></button>')
    assert not any("no accessible name" in f["problem"] for f in out["findings"])


def test_lint_html_eval_regressions_empty_heading_idrefs_duplicate_label_autocomplete():
    html = ('<h1>Sign up</h1><h2></h2>'
            '<input type="email" id="email" autocomplete="nope">'
            '<input type="checkbox" id="email"><label for="email">News</label>'
            '<input type="tel" aria-labelledby="missing">'
            '<input type="text" autocomplete="shipping street-address"><label>ok <input autocomplete="off"></label>')
    f = call("lint_html", html=html)["findings"]
    probs = [x["problem"] for x in f]
    assert "empty heading (no text)" in probs
    assert any("missing id 'missing'" in p for p in probs)
    assert any("attaches to an earlier element" in p for p in probs)
    assert any(x["severity"] == "blocker" and "duplicate id" in x["problem"] for x in f)
    assert [x["criterion"] for x in f if "autocomplete" in x["problem"]] == ["1.3.5"]  # only "nope" is invalid


def test_suggest_color_ratios_are_truncated_like_webaim():
    out = call("suggest_color", foreground="#9ca3af", background="#ffffff", target_ratio=4.5)
    assert out["suggestion"] == "#727780" and out["current_ratio"] == 2.53  # WebAIM: 2.53 and 4.50


def test_simulate_color_blindness_matches_machado_reference_and_flags_luminance_twins():
    out = call("simulate_color_blindness", colors=["#d73d3d", "#178841"])
    sim = out["simulated"][0]
    assert (sim["protanopia"], sim["deuteranopia"], sim["tritanopia"]) == ("#6a613b", "#908238", "#ec003f")  # colorspacious 1.1.2
    assert out["collapsed"][0]["collapses_for"] == ["achromatopsia"] and out["collapsed"][0]["contrast_between"] == 1.0
    with pytest.raises(ToolError):
        call("simulate_color_blindness", colors=["#fff"], pairs=[["#fff"]])


def test_lint_html_main_landmark_and_platform_targets():
    out = call("lint_html", html='<html lang="en"><head><title>x</title></head><body><h1>x</h1><div>content</div></body></html>')
    assert any(f["problem"] == "no <main> landmark" for f in out["findings"])
    t = call("target_size", targets=[{"name": "fab", "width": 44, "height": 44}])["targets"][0]
    assert t["ios_44pt"] is True and t["android_48dp"] is False
