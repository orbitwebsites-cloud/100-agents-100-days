"""Replayable evaluation scenarios for the Product & Design agents (see evals/product.md).

Each scenario is the realistic input used in the evaluation, run through the tools exactly as the
customer's AI would call them, with assertions on values verified independently: WCAG ratios against
WebAIM's contrast-checker API, Kano classes against the published evaluation table, and NPS, RICE,
TAM/SAM/SOM, dilution and runway by hand. The helper maths in this file (`_wcag_ratio`, `_nps`,
`_kano`) is written from the published formulas and does not import any Hundred code.
"""

import itertools
import math
from collections import Counter, defaultdict

import pytest

from hundred import registry


def run(slug, tool, **kwargs):
    return registry.get(slug).get_tool(tool).call(kwargs)


# ══════════════════════════════════════════════════════════════════════════════
# 1. accessibility-checker — sign-up page with 18 planted WCAG defects + a colour palette
# ══════════════════════════════════════════════════════════════════════════════

SIGNUP_HTML = """<!doctype html>
<html>
<head><meta charset="utf-8"><title></title></head>
<body>
<header>
  <a href="/"><img src="/img/home.svg" alt="Acme home"></a>
  <img src="/img/logo.png">
  <button class="close"><svg aria-hidden="true" viewBox="0 0 16 16"><path d="M2 2l12 12"/></svg></button>
</header>
<main id="main">
  <h1>Create your account</h1>
  <img src="/img/hero.jpg" alt="hero.jpg">
  <h3>Your details</h3>
  <form>
    <label>Full name <input type="text" name="name" autocomplete="name"></label>
    <input type="email" id="email" name="email" placeholder="Email address" autocomplete="nope">
    <label for="pw">Password</label>
    <input type="password" id="pw" name="pw" tabindex="3">
    <select id="country" name="country"><option>United States</option></select>
    <input type="tel" name="phone" aria-labelledby="phone-lbl">
    <h2></h2>
    <input type="checkbox" id="email" name="newsletter"> <label for="email">Send me product news</label>
    <p>By signing up you agree to our terms. <a href="/terms">Click here</a></p>
    <iframe src="https://captcha.example.com/widget"></iframe>
    <div class="btn" onclick="submitForm()">Continue</div>
    <button type="submit"><img src="/img/arrow.svg" alt="Create account"></button>
    <input type="image" src="/img/go.png">
  </form>
  <a href="#"></a>
</main>
</body>
</html>
"""

# (severity, problem substring) for each planted defect — the ground truth
A11Y_PLANTED = [
    ("major", "no lang attribute"),                          # P1  3.1.1
    ("major", "missing or empty page title"),                # P2  2.4.2
    ("blocker", "no alt attribute"),                         # P3  logo 1.1.1
    ("major", "alt is a filename"),                          # P4  hero.jpg 1.1.1
    ("blocker", "duplicate id (2×) used by a label"),        # P5  email field gets the checkbox's label
    ("blocker", "<select id='country'>"),                    # P6  unlabelled select
    ("blocker", "missing id 'phone-lbl'"),                   # P7  broken aria-labelledby
    ("blocker", "button has no accessible name"),            # P8  icon-only close button
    ("minor", "'Click here' is not descriptive"),            # P9  2.4.4
    ("minor", "skips from h1 to h3"),                        # P10 1.3.1
    ("minor", "empty heading"),                              # P11 axe empty-heading
    ("blocker", "attaches to an earlier element"),           # P12 checkbox unlabelled via duplicate id
    ("major", "iframe without title"),                       # P13 4.1.2
    ("blocker", "clickable div"),                            # P14 4.1.2
    ("major", "positive tabindex"),                          # P15 2.4.3
    ("blocker", "image button without alt"),                 # P16 input type=image
    ("blocker", "a has no accessible name"),                 # P17 empty <a href="#">
    ("major", "invalid autocomplete value 'nope'"),          # P18 1.3.5 (axe autocomplete-valid)
]

# WebAIM contrast checker API (webaim.org/resources/contrastchecker/?fcolor=..&bcolor=..&api), fetched 2026-09-27
WEBAIM = {
    ("767676", "ffffff"): 4.54, ("777777", "ffffff"): 4.47, ("3b82f6", "ffffff"): 3.67,
    ("9ca3af", "ffffff"): 2.53, ("ffffff", "22c55e"): 2.27, ("6b7280", "f3f4f6"): 4.39,
    ("2563eb", "ffffff"): 5.16, ("d1d5db", "ffffff"): 1.47, ("ef4444", "ffffff"): 3.76,
    ("93c5fd", "ffffff"): 1.80, ("5a7c87", "ffffff"): 4.49,
    ("1f2937", "ffffff"): 14.6,  # WebAIM prints 3 significant figures above 10:1; exact 14.679
}
WEBAIM_AA_NORMAL = {k: v >= 4.5 for k, v in WEBAIM.items()}
# suggest_color outputs, each re-checked in WebAIM: all pass their target exactly as WebAIM reports
WEBAIM_SUGGESTIONS = {("727780", "ffffff"): 4.50, ("69707d", "f3f4f6"): 4.52, ("ffffff", "178841"): 4.53,
                      ("929599", "ffffff"): 3.00, ("d73d3d", "ffffff"): 4.54, ("597b86", "ffffff"): 4.56, ("7198c3", "ffffff"): 3.00}


def _wcag_ratio(a, b):
    """WCAG 2.x contrast from the spec formula (independent of the tool)."""
    def lum(h):
        def lin(c):
            v = c / 255
            return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
        r, g, bl = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(bl)
    hi, lo = sorted([lum(a), lum(b)], reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_a11y_lint_finds_every_planted_defect_with_no_false_positives():
    out = run("accessibility-checker", "lint_html", html=SIGNUP_HTML)
    f = out["findings"]
    text = [f"{x['severity']}|{x['element']}|{x['problem']}" for x in f]
    for sev, needle in A11Y_PLANTED:
        assert any(t.startswith(sev) and needle in t for t in text), f"missed planted defect: {needle}"
    # 18 planted + the genuine missing skip link; nothing else
    assert len(f) == 19 and out["counts"] == {"blocker": 9, "major": 6, "minor": 4}
    assert any("no skip link" in x["problem"] for x in f)
    # decoys: <a><img alt="Acme home"></a>, <button><img alt="Create account"></button>, wrapped/for= labels
    assert not any("'/'" in x["element"] for x in f)
    assert sum("button has no accessible name" in x["problem"] for x in f) == 1
    assert not any("id='pw'" in x["element"] and "label" in x["problem"] for x in f)


@pytest.mark.parametrize("pair,webaim", sorted(WEBAIM.items()))
def test_a11y_contrast_matches_webaim_and_spec(pair, webaim):
    fg, bg = pair
    out = run("accessibility-checker", "contrast_ratio", foreground="#" + fg, background="#" + bg)
    exact = _wcag_ratio(fg, bg)
    assert out["ratio"] == math.floor(exact * 100) / 100  # truncated, never rounded up
    if exact < 10:
        assert out["ratio"] == webaim
    assert out["aa_normal_text"] is WEBAIM_AA_NORMAL[pair]


def test_a11y_borderline_pair_is_not_displayed_as_passing():
    out = run("accessibility-checker", "contrast_ratio", foreground="#5a7c87", background="#ffffff", font_px=13)
    assert out["ratio_text"] == "4.49:1" and out["aa_normal_text"] is False and "FAIL" in out["verdict"]


@pytest.mark.parametrize("fg,bg,target,adjust,expected", [
    ("9ca3af", "ffffff", 4.5, "foreground", "727780"), ("6b7280", "f3f4f6", 4.5, "foreground", "69707d"),
    ("ffffff", "22c55e", 4.5, "background", "178841"), ("d1d5db", "ffffff", 3, "foreground", "929599"),
    ("ef4444", "ffffff", 4.5, "foreground", "d73d3d"), ("5a7c87", "ffffff", 4.5, "foreground", "597b86"),
    ("93c5fd", "ffffff", 3, "foreground", "7198c3"),
])
def test_a11y_suggested_colours_pass_in_webaim(fg, bg, target, adjust, expected):
    out = run("accessibility-checker", "suggest_color", foreground="#" + fg, background="#" + bg, target_ratio=target, adjust=adjust)
    assert out["suggestion"] == "#" + expected
    pair = (expected, bg) if adjust == "foreground" else (fg, expected)
    assert WEBAIM_SUGGESTIONS[pair] >= target and _wcag_ratio(*pair) >= target


def test_a11y_target_sizes():
    out = run("accessibility-checker", "target_size", targets=[
        {"name": "modal close (icon)", "width": 16, "height": 16, "spacing": 4},
        {"name": "social login icons", "width": 20, "height": 20, "spacing": 8},
        {"name": "newsletter checkbox", "width": 18, "height": 18, "spacing": 2},
        {"name": "show-password toggle", "width": 24, "height": 24},
        {"name": "Create account button", "width": 320, "height": 44},
        {"name": "terms link", "width": 60, "height": 16, "inline": True},
    ])
    aa = {t["name"]: t["aa_2_5_8"] for t in out["targets"]}
    # 2.5.8: 24px, or 24px circles centred on each target don't intersect (size + gap ≥ 24 for equal targets)
    assert aa == {"modal close (icon)": False, "social login icons": True, "newsletter checkbox": False,
                  "show-password toggle": True, "Create account button": True, "terms link": True}
    assert out["aa_failures"] == 2 and out["aaa_failures"] == 4


# ══════════════════════════════════════════════════════════════════════════════
# 2. feedback-analyzer — 80 NPS responses, hand-labelled themes
# ══════════════════════════════════════════════════════════════════════════════

# (score, segment, comment, true_themes) — hand-labelled ground truth
NPS = [
 # --- detractors (22) ---
 (2, "Pro", "Syncing a big project takes forever, the board is so slow it freezes.", {"performance"}),
 (3, "Pro", "Loading the timeline view is painfully slow every morning.", {"performance"}),
 (4, "Pro", "Performance has gotten worse since the redesign, pages lag constantly.", {"performance"}),
 (5, "Starter", "It's slow. Really slow on our office wifi.", {"performance"}),
 (6, "Pro", "Laggy when more than 3 people edit the same board.", {"performance"}),
 (1, "Enterprise", "Sluggish with our 40k tasks, the search times out.", {"performance"}),
 (5, "Pro", "Takes 10 seconds to load a project, my team gave up waiting.", {"performance"}),
 (6, "Starter", "The board freezes whenever I drag a card between columns.", {"performance"}),
 (0, "Pro", "Export to CSV crashes the app every single time.", {"bugs"}),
 (2, "Pro", "PDF export is broken, it cuts off half the page.", {"bugs"}),
 (3, "Enterprise", "Reports export fails with an error for any board over 500 rows.", {"bugs"}),
 (4, "Starter", "Crashed twice during our client demo when exporting. Embarrassing.", {"bugs"}),
 (5, "Pro", "Exported spreadsheets are missing the custom fields, looks like a bug.", {"bugs"}),
 (3, "Starter", "Way too expensive for a team of four.", {"pricing"}),
 (4, "Starter", "The price jumped 40% at renewal with no warning.", {"pricing"}),
 (6, "Starter", "Hard to justify the cost when free tools do most of this.", {"pricing"}),
 (5, "Starter", "Not worth the money for a small agency.", {"pricing"}),
 (4, "Pro", "No Google Calendar integration, so deadlines live in two places.", {"integrations"}),
 (6, "Pro", "We need it to sync with Outlook calendars, it doesn't.", {"integrations"}),
 (5, "Enterprise", "Missing a proper Salesforce integration, our sales team won't adopt it.", {"integrations"}),
 (6, "Pro", "", set()),
 (3, "Starter", "", set()),
 # --- passives (24) ---
 (7, "Starter", "Good tool but a bit pricey for what we use.", {"pricing"}),
 (8, "Starter", "Solid, though the per-seat price adds up fast.", {"pricing"}),
 (7, "Starter", "Would be a 10 if it were cheaper.", {"pricing"}),
 (8, "Pro", "Fine overall. Pricing tiers are confusing.", {"pricing"}),
 (7, "Starter", "Decent value, but the jump from Starter to Pro is steep.", {"pricing"}),
 (8, "Pro", "Pretty good, costs more than Trello though.", {"pricing"}),
 (7, "Pro", "Wish it had recurring tasks.", {"missing_feature"}),
 (8, "Pro", "Please add Gantt dependencies, we still use a spreadsheet for that.", {"missing_feature"}),
 (7, "Pro", "Would love a time-tracking feature.", {"missing_feature"}),
 (8, "Starter", "Needs a Slack integration that posts task updates.", {"integrations"}),
 (7, "Pro", "Lacks an API for our internal dashboards.", {"integrations"}),
 (8, "Pro", "Occasionally slow to load big boards, otherwise good.", {"performance"}),
 (7, "Pro", "Good, but the search is sluggish.", {"performance"}),
 (8, "Starter", "Works well, sometimes laggy on older laptops.", {"performance"}),
 (7, "Starter", "Fine, a bit slow at peak hours.", {"performance"}),
 (8, "Pro", "The mobile app is missing half the features.", {"mobile"}),
 (7, "Starter", "Android app logs me out every day.", {"mobile"}),
 (8, "Pro", "iPhone app is okay but notifications are unreliable.", {"mobile"}),
 (7, "Starter", "Mobile editing is clunky.", {"mobile"}),
 (8, "Pro", "", set()),
 (7, "Starter", "", set()),
 (8, "Pro", "", set()),
 (7, "Enterprise", "", set()),
 (8, "Pro", "", set()),
 # --- promoters (34) ---
 (9, "Pro", "So easy to use, the whole team was productive on day one.", {"usability"}),
 (10, "Pro", "Clean interface and very intuitive.", {"usability"}),
 (9, "Starter", "Easy to use and nice to look at.", {"usability"}),
 (10, "Pro", "The simplest project tool we've tried.", {"usability"}),
 (9, "Pro", "Intuitive drag and drop boards, love it.", {"usability"}),
 (10, "Starter", "Super easy to use for non-technical clients.", {"usability"}),
 (9, "Pro", "Layout is clear, I always know where things are.", {"usability"}),
 (10, "Pro", "Easy to use, easy to roll out.", {"usability"}),
 (9, "Enterprise", "Intuitive enough that nobody needed training.", {"usability"}),
 (10, "Pro", "The UI just makes sense.", {"usability"}),
 (10, "Pro", "Support replied in 20 minutes and fixed our import.", {"support"}),
 (9, "Starter", "Customer service is outstanding, real humans who care.", {"support"}),
 (10, "Pro", "Best support team of any SaaS we pay for.", {"support"}),
 (9, "Pro", "Support helped us migrate from Asana in one afternoon.", {"support"}),
 (10, "Enterprise", "Our account manager and support are fantastic.", {"support"}),
 (9, "Pro", "Chat support is quick and helpful.", {"support"}),
 (10, "Starter", "Great customer service.", {"support"}),
 (9, "Pro", "Helpful staff and a great product.", {"support"}),
 (10, "Pro", "The templates saved us hours setting up client projects.", {"templates"}),
 (9, "Starter", "Love the agency templates.", {"templates"}),
 (10, "Pro", "Templates for sprints are perfect.", {"templates"}),
 (9, "Pro", "Great templates library.", {"templates"}),
 (10, "Starter", "Reusable templates are a huge time saver.", {"templates"}),
 (9, "Pro", "Templates plus automations = magic.", {"templates"}),
 (10, "Pro", "Fast and reliable, never had downtime.", {"performance", "reliability"}),
 (9, "Pro", "Quick, stable, does what it says.", {"reliability"}),
 (10, "Starter", "Everything just works.", set()),
 (9, "Pro", "Great product.", set()),
 (10, "Pro", "", set()),
 (9, "Starter", "", set()),
 (10, "Pro", "", set()),
 (9, "Pro", "", set()),
 (10, "Starter", "", set()),
 (9, "Pro", "", set()),
]


def _nps(scores):
    """NPS and 95% MoE by hand: Var(P−D) = (p + d − (p − d)²)/n for a multinomial sample."""
    n = len(scores)
    p = sum(s >= 9 for s in scores) / n
    d = sum(s <= 6 for s in scores) / n
    return round(100 * (p - d), 1), round(100 * 1.96 * math.sqrt((p + d - (p - d) ** 2) / n), 1)


def test_feedback_nps_and_margin_by_hand():
    scores = [r[0] for r in NPS]
    out = run("feedback-analyzer", "score_survey", scores=scores, survey="nps", segments=[r[1] for r in NPS], previous_score=22)
    assert (out["score"], out["moe"]) == _nps(scores) == (15.0, 18.0)
    assert (out["promoters_pct"], out["passives_pct"], out["detractors_pct"]) == (42.5, 30.0, 27.5)
    assert out["delta"] == {"previous": 22.0, "change": -7.0, "beats_noise": False}
    seg = out["by_segment"]
    for name in ("Pro", "Starter", "Enterprise"):
        assert (seg[name]["score"], seg[name]["moe"]) == _nps([r[0] for r in NPS if r[1] == name])
    assert (seg["Pro"]["n"], seg["Pro"]["reportable"]) == (47, True)
    assert (seg["Starter"]["n"], seg["Starter"]["reportable"]) == (27, False)
    assert seg["Enterprise"]["reportable"] is False


def _themes():
    return run("feedback-analyzer", "count_themes",
               responses=[{"text": r[2], "score": r[0], "segment": r[1]} for r in NPS],
               taxonomy={"templates": ["template", "templates"]})


def test_feedback_theme_tagging_precision_recall_vs_hand_labels():
    out = _themes()
    assert out["responses_with_comment"] == 67 and out["untagged"] == 3
    tp = fp = fn = 0
    for row in out["tagged_rows"]:
        truth, pred = NPS[row["i"]][3], set(row["themes"])
        tp, fp, fn = tp + len(pred & truth), fp + len(pred - truth), fn + len(truth - pred)
    # strict single-label truth; most remaining "FPs" are defensible second labels (e.g. mobile + missing_feature)
    assert tp / (tp + fp) >= 0.86 and tp / (tp + fn) >= 0.98
    by = {t["theme"]: t for t in out["themes"]}
    assert by["bugs"]["responses"] == 5 and by["bugs"]["by_band"] == {"detractor": 5}
    assert by["support"]["responses"] == 8 and by["templates"]["responses"] == 6
    assert "integrations" not in {t for r in out["tagged_rows"] if "export" in NPS[r["i"]][2].lower() for t in r["themes"]}


def test_feedback_drivers_by_hand():
    rows = _themes()["tagged_rows"]
    out = run("feedback-analyzer", "driver_analysis", tagged_rows=rows, min_n=5)
    commented = [r for r in NPS if r[2]]
    bug = [r[0] for r in commented if "bugs" in r[3]]
    rest = [r[0] for r in commented if "bugs" not in r[3]]
    d = {x["theme"]: x for x in out["drivers"]}
    assert d["bugs"]["gap"] == round(sum(bug) / len(bug) - sum(rest) / len(rest), 2) == -4.83
    assert d["bugs"]["detractor_share_pct"] == 25.0  # 5 of the 20 commented detractors
    assert out["negative_drivers"][:2] == ["bugs", "performance"]
    assert set(out["positive_drivers"]) == {"support", "templates", "usability"}


def test_feedback_fix_ranking_by_hand():
    fixes = [
        {"fix": "Fix CSV/PDF export crashes", "responses": 5, "severity": 3, "reach": 3, "effort": 1},
        {"fix": "Board load + drag performance", "responses": 14, "severity": 2, "reach": 3, "effort": 3},
        {"fix": "Simplify pricing tiers", "responses": 9, "severity": 2, "reach": 1, "effort": 1},
        {"fix": "Calendar + Slack + Salesforce integrations", "responses": 5, "severity": 2, "reach": 2, "effort": 3},
        {"fix": "Mobile app parity", "responses": 4, "severity": 1, "reach": 2, "effort": 3},
    ]
    out = run("feedback-analyzer", "prioritize_fixes", fixes=fixes, total_responses=67)
    hand = {f["fix"]: round(100 * f["responses"] / 67 * f["severity"] * f["reach"] / 9, 1) for f in fixes}
    assert {r["fix"]: r["priority"] for r in out["ranked"]} == hand
    assert [r["fix"] for r in out["ranked"]][:2] == ["Board load + drag performance", "Fix CSV/PDF export crashes"]


# ══════════════════════════════════════════════════════════════════════════════
# 3. roadmap-prioritizer — 12 items (RICE), Kano survey on 6 features, 36 person-week capacity
# ══════════════════════════════════════════════════════════════════════════════

RICE_ITEMS = [
    {"name": "Bulk CSV import", "reach": 4000, "impact": "medium", "confidence": 80, "effort": 3},
    {"name": "SSO (SAML)", "reach": 600, "impact": "massive", "confidence": 80, "effort": 6},
    {"name": "Dark mode", "reach": 9000, "impact": "minimal", "confidence": 100, "effort": 2},
    {"name": "Recurring tasks", "reach": 5000, "impact": "high", "confidence": 80, "effort": 4},
    {"name": "Gantt dependencies", "reach": 2500, "impact": "high", "confidence": 50, "effort": 8},
    {"name": "Slack notifications", "reach": 6000, "impact": "medium", "confidence": 80, "effort": 2},
    {"name": "AI task summaries", "reach": 8000, "impact": "medium", "confidence": 30, "effort": 6},
    {"name": "Mobile offline mode", "reach": 3000, "impact": "high", "confidence": 50, "effort": 10},
    {"name": "PDF export fix", "reach": 7000, "impact": "low", "confidence": 100, "effort": 1, "evidence": "5 NPS detractors + 38 tickets"},
    {"name": "Custom fields in exports", "reach": 3500, "impact": "medium", "confidence": 80, "effort": 1.5},
    {"name": "Audit log", "reach": 400, "impact": "high", "confidence": 80, "effort": 3},
    {"name": "Keyboard shortcuts", "reach": 2000, "impact": "low", "confidence": 80, "effort": 0.4},
]
_IMPACT = {"minimal": 0.25, "low": 0.5, "medium": 1, "high": 2, "massive": 3}

# Kano survey answers (functional, dysfunctional) per respondent; 12 respondents per feature
L,M,N,W,D="like","must-be","neutral","live-with","dislike"
KANO = {
 "SSO (SAML)":        [(N,D)]*5+[(M,D)]*3+[(L,D)]*2+[(N,N)]*2,
 "Dark mode":         [(L,N)]*6+[(L,W)]*2+[(N,N)]*3+[(L,D)]*1,
 "Recurring tasks":   [(L,D)]*6+[(L,W)]*2+[(N,D)]*2+[(N,N)]*2,
 "AI task summaries": [(L,N)]*4+[(N,N)]*3+[(D,L)]*3+[(L,L)]*2,
 "PDF export fix":    [(M,D)]*4+[(N,D)]*4+[(L,D)]*3+[(N,W)]*1,
 "Keyboard shortcuts":[(N,N)]*7+[(L,N)]*3+[(N,D)]*2,
}
# Published Kano evaluation table (Berger et al. 1993): rows functional, cols dysfunctional,
# both in the order like, must-be, neutral, live-with, dislike
_KANO_TABLE = {"like": "QAAAO", "must-be": "RIIIM", "neutral": "RIIIM", "live-with": "RIIIM", "dislike": "RRRRQ"}
_ORDER = ["like", "must-be", "neutral", "live-with", "dislike"]


def _kano(pairs):
    c = Counter(_KANO_TABLE[f][_ORDER.index(d)] for f, d in pairs)
    den = c["A"] + c["O"] + c["M"] + c["I"]
    top = max("MOAI", key=lambda k: (c[k], -"MOAI".index(k)))  # mode; ties M > O > A > I
    return top, round((c["A"] + c["O"]) / den, 2), round(-(c["O"] + c["M"]) / den, 2) + 0.0


def test_roadmap_rice_by_hand_with_flags_and_tiers():
    out = run("roadmap-prioritizer", "rice_score", items=RICE_ITEMS)
    hand = {i["name"]: round(i["reach"] * _IMPACT[i["impact"]] * i["confidence"] / 100 / i["effort"], 1) for i in RICE_ITEMS}
    assert {r["name"]: r["rice"] for r in out["ranked"]} == hand
    assert [r["name"] for r in out["ranked"]][:3] == ["PDF export fix", "Slack notifications", "Recurring tasks"]
    flags = {r["name"]: " ".join(r["flags"]) for r in out["ranked"]}
    assert "research spike" in flags["AI task summaries"]            # 30% confidence
    assert "no evidence" in flags["Dark mode"]                        # 100% without evidence
    assert flags["PDF export fix"] == ""                              # 100% with evidence is fine
    assert "bundle" in flags["Keyboard shortcuts"]                    # 0.4 weeks
    assert out["tiers"] == [["PDF export fix"], ["Slack notifications", "Recurring tasks", "Keyboard shortcuts", "Custom fields in exports"],
                            ["Dark mode", "Bulk CSV import"], ["AI task summaries", "Gantt dependencies", "Mobile offline mode", "SSO (SAML)", "Audit log"]]


def test_roadmap_kano_matches_published_table():
    out = run("roadmap-prioritizer", "kano_classify",
              features=[{"name": k, "responses": [{"functional": f, "dysfunctional": d} for f, d in v]} for k, v in KANO.items()])
    got = {f["name"]: (f["code"], f["better"], f["worse"]) for f in out["features"]}
    assert got == {k: _kano(v) for k, v in KANO.items()}
    assert {k: v[0] for k, v in got.items()} == {"SSO (SAML)": "M", "Dark mode": "A", "Recurring tasks": "O",
                                                  "AI task summaries": "A", "PDF export fix": "M", "Keyboard shortcuts": "I"}
    notes = {f["name"]: " ".join(f["notes"]) for f in out["features"]}
    assert "questionable" in notes["AI task summaries"] and "reverse" in notes["AI task summaries"]
    assert out["cut_candidates"] == ["Keyboard shortcuts"]


def test_roadmap_capacity_check_by_hand():
    items = [("PDF export fix", "must", 1), ("Custom fields in exports", "must", 1.5), ("SSO (SAML)", "must", 6),
             ("Slack notifications", "must", 2), ("Recurring tasks", "must", 4), ("Gantt dependencies", "must", 8),
             ("Keyboard shortcuts", "should", 0.4), ("Bulk CSV import", "should", 3), ("Audit log", "should", 3),
             ("Mobile offline mode", "should", 10), ("Dark mode", "could", 2), ("AI task summaries", "wont", 6)]
    out = run("roadmap-prioritizer", "capacity_check", capacity_weeks=36, items=[{"name": n, "moscow": m, "effort": e} for n, m, e in items])
    # 4 engineers × 12 weeks × 0.75 focus = 36; plannable = 36 × 0.8 = 28.8; Must = 22.5 / 36 = 62.5%
    assert out["plannable_weeks"] == 28.8 and out["must_pct_of_capacity"] == 62.5
    assert out["below_the_line"] == ["Audit log", "Mobile offline mode", "Dark mode"]
    assert "demote 0.9 weeks" in out["problems"][0] and "cut 12.1 weeks" in out["problems"][2]


def test_roadmap_wsjf_by_hand():
    out = run("roadmap-prioritizer", "wsjf_ice_score", items=[
        {"name": "SSO (SAML)", "business_value": 13, "time_criticality": 13, "risk_reduction": 5, "job_size": 8},
        {"name": "Audit log", "business_value": 5, "time_criticality": 8, "risk_reduction": 8, "job_size": 3},
        {"name": "Recurring tasks", "business_value": 8, "time_criticality": 3, "risk_reduction": 1, "job_size": 5}])
    assert [(r["name"], r["score"]) for r in out["ranked"]] == [("Audit log", 7.0), ("SSO (SAML)", round(31 / 8, 2)), ("Recurring tasks", 2.4)]


# ══════════════════════════════════════════════════════════════════════════════
# 4. interview-synthesizer — 6 interviews (3 SMB, 3 ENT) with recurring pains
# ══════════════════════════════════════════════════════════════════════════════

INTERVIEWS = """
Interview 1 — Dana, ops manager, 12-person agency (SMB)
We run everything out of the tool but reporting is the weak spot. Every Friday I spend about three hours rebuilding the client status report in Excel because the export loses all the formatting. I hate that part of my week. Honestly it's the most tedious thing I do. When we onboard a new client it takes two days to set up the boards, the templates only get us halfway. I just copy the last client's board and delete stuff.

Interview 2 — Marcus, founder, 8-person design studio (SMB)
The report thing drives me crazy. I export to Excel, fix the columns, paste in the charts, every single week. It's a waste of a Friday afternoon. Approvals are the other mess: clients approve designs over email and then nobody can find which version was approved. We pay $400/month and I still keep a spreadsheet of approvals on the side.

Interview 3 — Priya, PMO lead, 900-person insurer (ENT)
Our biggest problem is approvals. Legal and compliance sign off in email threads, and I cannot prove who approved what during an audit. That's a real risk for us. Setting up a new program takes weeks because permissions have to be configured board by board. It's painful and error-prone. I wish we could set permissions once per program.

Interview 4 — Tom, head of delivery, 400-person consultancy (ENT)
The weekly steering report is manual. My coordinators spend maybe 6 hours a week rebuilding it by hand from exports. Permissions are confusing too; we had a contractor see a client's budget last month. That was a nightmare to explain.

Interview 5 — Aisha, account director, 15-person agency (SMB)
Monday mornings I rebuild the client report manually, copy-paste from three boards into a slide deck. It's so tedious. If you built an AI assistant that summarised the week, I would probably use it. It would be great if the report just generated itself.

Interview 6 — Kenji, operations VP, 250-person software company (ENT)
Approvals are scattered across Slack and email and we lose track constantly. We're evaluating Monday.com because their approval flows look better. Last quarter a release slipped a week because an approval was sitting in someone's inbox.
"""
# Every sentence a researcher would pull as evidence (26), incl. one hypothetical
INTERVIEW_SIGNAL_SENTENCES = 26

SEG={"P1":"SMB","P2":"SMB","P5":"SMB","P3":"ENT","P4":"ENT","P6":"ENT"}
OBS=[
 ("P1","Rebuilds the weekly client status report in Excel every Friday","report-rebuild"),
 ("P1","Export to Excel loses the report formatting","report-rebuild"),
 ("P1","Copies the last client's board to onboard a new client","client-setup"),
 ("P1","New client board setup takes two days","client-setup"),
 ("P2","Rebuilds the weekly report in Excel from an export every week","report-rebuild"),
 ("P2","Pastes charts into the weekly report by hand","report-rebuild"),
 ("P2","Clients approve designs over email and the approved version gets lost","approvals"),
 ("P2","Keeps a side spreadsheet of client approvals","approvals"),
 ("P3","Legal and compliance approvals happen in email threads","approvals"),
 ("P3","Cannot prove who approved what during an audit","approvals"),
 ("P3","Permissions configured board by board for each new program","permissions"),
 ("P3","New program setup takes weeks because of permissions","permissions"),
 ("P4","Coordinators rebuild the weekly steering report by hand from exports","report-rebuild"),
 ("P4","Contractor saw a client budget because permissions are confusing","permissions"),
 ("P5","Rebuilds the weekly client report manually every Monday","report-rebuild"),
 ("P5","Copy-pastes from three boards into a slide deck for the report","report-rebuild"),
 ("P6","Approvals scattered across Slack and email threads","approvals"),
 ("P6","Release slipped a week waiting on an approval in an inbox","approvals"),
 ("P6","Evaluating Monday.com for its approval flows","switching"),
]


def test_interviews_extract_signals():
    out = run("interview-synthesizer", "extract_signals", notes=INTERVIEWS)
    assert out["interviews_detected"] == ["P1", "P2", "P3", "P4", "P5", "P6"]
    assert out["total_candidates"] == INTERVIEW_SIGNAL_SENTENCES
    hyp = [q for q in out["quotes"] if q["hypothetical"]]
    assert len(hyp) == 1 and hyp[0]["interview"] == "P5" and hyp[0]["score"] < 0
    assert any("$400/month" in q["quote"] and "money_frequency" in q["signals"] for q in out["quotes"])


def test_interviews_extract_signals_heldout_recall_is_partial():
    # Notes the patterns were never tuned on: 12 signal sentences a researcher would pull; the keyword
    # net finds 5 — which is why the playbook tells the AI to read every interview in full.
    notes = ("Session 1\nEvery quarter close is chaos. Our finance lead reconciles vendor bills line by line against the PO list, "
             "and it takes her most of a week. Last year we paid one invoice twice and never noticed. I'd love an alert for "
             "duplicate bills. Right now she keeps a checklist in Google Sheets.\n\nSession 2\nHonestly the approval chain is the "
             "bottleneck. A purchase over $5k needs three sign-offs and people are on holiday. I'd probably pay for something that "
             "auto-escalates. We already tried Coupa but it was overkill for us.\n\nSession 3\nOur reps forget to log calls. "
             "Pipeline reviews on Monday are guesswork because half the data isn't there. I end up pinging everyone on Slack before the meeting.")
    out = run("interview-synthesizer", "extract_signals", notes=notes)
    assert 5 <= out["total_candidates"] <= 12 and out["hypothetical_count"] == 1


def test_interviews_clusters_vs_ground_truth():
    out = run("interview-synthesizer", "cluster_observations",
              observations=[{"text": t, "interview": i, "segment": SEG[i]} for i, t, _ in OBS])
    truth = {t: g for _, t, g in OBS}
    label = {m: k for k, c in enumerate(out["clusters"]) for m in c["members"]}
    tp = fp = fn = 0
    for a, b in itertools.combinations(truth, 2):
        same_t, same_p = truth[a] == truth[b], label[a] == label[b]
        tp, fp, fn = tp + (same_t and same_p), fp + (same_p and not same_t), fn + (same_t and not same_p)
    p, r = tp / (tp + fp), tp / (tp + fn)
    assert 2 * p * r / (p + r) >= 0.85  # pairwise F1 (was 0.58 before the linking-word fix)
    report = next(c for c in out["clusters"] if "report" in c["keywords"])
    assert report["interviews"] == ["P1", "P2", "P4", "P5"] and report["size"] == 7


def test_interviews_tag_frequency_and_saturation_by_hand():
    out = run("interview-synthesizer", "tag_frequency", tagged=[{"interview": i, "tags": [g], "segment": SEG[i]} for i, _, g in OBS])
    ivs, mentions = defaultdict(set), Counter()
    for i, _, g in OBS:
        ivs[g].add(i)
        mentions[g] += 1
    got = {t["tag"]: t for t in out["tags"]}
    for g in ivs:
        assert (got[g]["interviews"], got[g]["mentions"]) == (len(ivs[g]), mentions[g])
    assert got["report-rebuild"]["by_segment"] == {"SMB": "3/3", "ENT": "1/3"} and got["report-rebuild"]["strength"] == "strong"
    assert got["approvals"]["strength"] == "strong" and got["permissions"]["strength"] == "moderate"
    order = ["P1", "P2", "P3", "P4", "P5", "P6"]
    sat = run("interview-synthesizer", "saturation_check", tags_per_interview=[sorted({g for i, _, g in OBS if i == p}) for p in order])
    assert [c["new_themes"] for c in sat["curve"]] == [2, 1, 1, 0, 0, 1]
    assert sat["saturated"] is False and sat["recommended_additional_interviews"] == 2


# ══════════════════════════════════════════════════════════════════════════════
# 5. prd-writer — half-finished "Client Approvals" PRD, then the rewritten PRD
# ══════════════════════════════════════════════════════════════════════════════

PRD_DRAFT = """
# PRD: Client Approvals

## Background
Agencies and PMOs approve deliverables over email today. In 6 customer interviews, 3 teams (Marcus's studio, Priya's insurer, Kenji's software company) said approvals get lost in inboxes; one release slipped a week waiting on an approval, and Priya cannot prove who approved what during an audit. We want approvals to live next to the work.

## Users
Primary: account managers and PMO leads who request sign-off. Secondary: external clients and internal legal/compliance approvers who give it.

## Goals
- Make approvals fast and easy for clients.
- Reduce time spent chasing approvals.

## Requirements
- Users can request approval on any task or file.
- The approver gets an email and can approve or reject without logging in.
- Approval history should be stored and exportable to PDF and/or CSV for audits.
- The approval page must load fast on mobile.
- Reminders are sent automatically, etc.
- Admins could configure multi-step approval chains.

## Success metrics
- Approval engagement goes up.
- Median time from request to decision: currently unknown, target 1 day, by Q4 2026.

## Design
Approve / Reject buttons on the task drawer, plus a lightweight approval page for guests.
"""

PRD_FINAL = """
# PRD: Client Approvals
## 1. Problem
Account managers and PMO leads need to get a deliverable signed off by a client or a compliance approver because work cannot ship without it, but today approvals happen in email and Slack threads, which costs a week of slip on at least one release (P6), a Friday afternoon of chasing per week (P2) and an audit risk because nobody can prove who approved which version (P3). Evidence: 3 of 6 interviews (SMB 1/3, ENT 2/3).
## 2. Users & jobs
Primary persona: agency account managers and PMO leads who request sign-off on a task or file. Secondary: external clients (no account) and internal legal or compliance approvers who give it. Explicitly NOT for: internal code review, purchase approvals, or HR sign-offs.
## 3. Goals / Non-goals
Goals: (G1) cut median request-to-decision time from 3.0 days to 1.0 day; (G2) give every approval an auditable record of approver, version and timestamp.
Non-goals: multi-currency purchase approvals; e-signature with legal effect (DocuSign-grade); approval chains longer than 3 steps in v1; Slack-native approve buttons in v1.
## 4. Success metrics
| Metric | Baseline | Target | By | Source |
| Median request-to-decision time (primary) | 3.0 days | 1.0 day | 90 days after launch | approvals_events table |
| Approvals decided without a reminder (leading) | n/a, new | 60% | 30 days after launch | approvals_events |
| Support tickets tagged approvals (guardrail) | 14/month | ≤ 14/month | 90 days after launch | Zendesk tag |
## 5. Requirements
| ID | Priority | Requirement | Acceptance test |
| FR-001 | MUST | A member must be able to request approval on any task or file and pick 1-3 approvers. | Given a task, when I click Request approval, then approvers receive the request within 60 s. |
| FR-002 | MUST | The approver must receive an email with a signed link valid for 14 days. | Link older than 14 days shows an expired page with a resend button. |
| FR-003 | MUST | A guest approver must be able to approve or reject without creating an account. | Decision is recorded with the approver's email and IP. |
| FR-004 | MUST | The system must store each decision with approver, version ID and UTC timestamp and never allow edits. | Audit log row cannot be modified via UI or API. |
| FR-005 | SHOULD | Admins should be able to export the approval log for a program to CSV. | CSV contains one row per decision. |
| FR-006 | SHOULD | The system should send a reminder 24 h and 72 h after an undecided request. | Reminder emails logged at +24 h and +72 h. |
| NFR-001 | MUST | The guest approval page must reach P95 load ≤ 2.0 s on a 4G connection. | Measured in synthetic monitoring. |
| FR-007 | COULD | Admins could configure 2-3 step sequential approval chains. | Step 2 is only notified after step 1 approves. |
## 6. User stories
As an account manager, I want to request sign-off from a client who has no account, so that the deliverable ships without an email chase. Given a file, when I request approval from client@example.com, then the client gets an email link and I see Pending.
As a compliance approver, I want an immutable approval log per program, so that I can prove who approved what during an audit. Given an approved deliverable, when I open its history, then I see approver, UTC timestamp and version.
## 7. UX & flows
Entry points: Request approval button on the task drawer and file preview. States: empty (no approvals yet, explain the feature), loading skeleton, pending with approver avatars, approved (green, version pinned), rejected (reason required), expired link page with resend, and error when the email bounces.
## 8. Edge cases & errors
1. Approver email bounces: show error on the task and let the requester change the address. 2. File changes after approval: approval stays pinned to the old version and the new version shows Needs re-approval. 3. Approver rejects without a reason: blocked, reason is required. 4. Two approvers decide at the same time: both recorded, the task shows the last decision and both rows in history.
## 9. Dependencies & constraints
Email service (Postmark) for signed links; security review for the guest link design; legal and privacy review of storing guest IP addresses under GDPR; file versioning service must expose stable version IDs.
## 10. Risks & mitigations
| Risk | Likelihood | Impact | Mitigation |
| Guest links forwarded to the wrong person | Medium | High | 14-day expiry, single-use, show approver email on the decision page |
| Clients ignore emails | Medium | Medium | reminders at 24 h and 72 h, requester can resend |
## 11. Rollout
Feature flag approvals_v1: 10% of Pro workspaces for 2 weeks, then 50%, then 100% including Enterprise. Kill switch disables guest links. Comms: in-app announcement, help article, email to admins.
## 12. Open questions
| # | Question | Owner | Needed by |
| 1 | Do Enterprise customers need SSO for internal approvers in v1? | PM | 2026-10-15 |
| 2 | Is guest IP storage acceptable under our DPA? | Legal | 2026-10-20 |
## Appendix
Research: interview synthesis (6 interviews, Sept 2026); NPS readout; competitor note: Monday.com approval flows.
"""


def test_prd_draft_audit():
    out = run("prd-writer", "check_completeness", prd_text=PRD_DRAFT)
    # present: problem 14 + requirements 14 (full); users 10, goals 10, metrics 12, ux 8 (thin → half, floored)
    assert out["score"] == 14 + 14 + 5 + 5 + 6 + 4 == 48
    assert [m["section"] for m in out["missing"]] == ["edge_cases", "dependencies", "risks", "rollout", "open_questions", "appendix"]
    assert "No explicit non-goals — add at least 3." in out["notes"]


def test_prd_requirement_lint_catches_planted_problems():
    reqs = ["Users can request approval on any task or file.",
            "The approver gets an email and can approve or reject without logging in.",
            "Approval history should be stored and exportable to PDF and/or CSV for audits.",
            "The approval page must load fast on mobile.",
            "Reminders are sent automatically, etc.",
            "Admins could configure multi-step approval chains."]
    out = run("prd-writer", "number_requirements", requirements=reqs)
    issues = [" ".join(r["issues"]) for r in out["requirements"]]
    assert "no modal verb" in issues[0]
    assert "compound" in issues[1] and "compound" in issues[2] and "and/or" in issues[2]
    assert "fast" in issues[3] and out["requirements"][3]["id"] == "NFR-001"
    assert "etc" in issues[4]
    assert issues[5] == ""  # a clean COULD requirement
    assert out["must_pct"] == 66.7


def test_prd_metrics_and_stories():
    m = run("prd-writer", "check_success_metrics", metrics=[
        {"name": "Approval engagement", "baseline": "", "target": "up", "timeframe": "", "source": ""},
        {"name": "Median time from approval request to decision", "baseline": "unknown", "target": "1 day", "timeframe": "by Q4 2026", "source": "", "type": "primary"}])
    assert any("vague metric name" in i for i in m["metrics"][0]["issues"])
    assert m["metrics"][1]["issues"] == ["no numeric baseline — measure current state first", "no measurement source (which dashboard/event/query?)"]
    assert m["notes"] == ["No guardrail metric — add at least one thing that must not get worse."]
    s = run("prd-writer", "lint_user_stories", stories=[
        {"story": "As a user, I want to approve files, so that files are approved.", "criteria": ["Approval should be easy"]},
        {"story": "As an account manager, I want to request sign-off on a deliverable from a client who has no account", "criteria": []},
        {"story": "As a compliance approver, I want an immutable approval log per program, so that I can prove who approved what during an audit.",
         "criteria": ["Given an approved deliverable, when I open its history, then I see approver name, timestamp (UTC) and the version approved."]}])
    iss = [" ".join(x["issues"]) for x in s["stories"]]
    assert "generic" in iss[0] and "restates" in iss[0] and "easy" in iss[0]
    assert "missing 'so that'" in iss[1] and "no acceptance criteria" in iss[1]
    assert iss[2] == ""


def test_prd_final_version_is_ready():
    out = run("prd-writer", "check_completeness", prd_text=PRD_FINAL)
    assert out["score"] == 100 and out["missing"] == [] and out["numbered_requirements"] == 8


# ══════════════════════════════════════════════════════════════════════════════
# 6. ux-writer — 24-string table (auth, settings, billing) with 15 planted problems and 5 decoys
# ══════════════════════════════════════════════════════════════════════════════

# (key, component, text) — string table for auth + settings + billing, with planted problems
STRINGS = [
 ("auth.title", "heading", "Sign in to Acme"),
 ("auth.cta", "button", "Log In"),                                   # P: log in vs sign in; Title Case
 ("auth.email.label", "label", "E-mail address"),                    # P: e-mail vs email
 ("auth.email.placeholder", "placeholder", "Enter your email address"),
 ("auth.forgot", "link", "Forgot password?"),
 ("auth.signup", "link", "New here? Create an account"),
 ("auth.error.creds", "error", "Error 401: Invalid credentials supplied."),   # P: code, jargon/blame 'invalid'
 ("auth.error.locked", "error", "Your account has been locked."),    # P: no next step
 ("nav.settings", "menu_item", "Settings"),
 ("settings.title", "heading", "Account Preferences"),               # P: preferences vs settings; Title Case
 ("settings.save", "button", "Save Your Changes!"),                  # P: title case, !, >3 words
 ("settings.delete", "button", "Remove account"),                    # P: remove vs delete
 ("settings.delete.confirm.title", "dialog_title", "Are you sure?"), # P: vague confirmation
 ("settings.delete.confirm.body", "dialog_body", "Deleting your account permanently erases all projects, files and invoices. This cannot be undone."),
 ("settings.delete.confirm.cta", "button", "Yes"),                   # P: generic button
 ("settings.delete.confirm.cancel", "button", "Cancel"),
 ("settings.logout", "button", "Logout"),                            # P: logout vs sign out; noun form
 ("settings.2fa.tooltip", "tooltip", "Two-factor authentication utilizes a time-based one-time password token generated by an authenticator application to verify your identity"),  # P: jargon, long, no period, grade
 ("billing.error.card", "error", "Oops! Something went wrong."),     # P: vague, oops, !
 ("billing.error.expired", "error", "Your card has expired. Update your card details to keep your plan."),  # good (decoy)
 ("billing.toast.saved", "toast", "Payment method updated."),        # good (decoy)
 ("billing.empty.title", "empty_state_title", "No invoices yet"),    # good (decoy)
 ("billing.empty.body", "empty_state_body", "Invoices appear here after your first payment. Download them as PDF for your records."),  # good
 ("billing.cta", "button", "Upgrade plan"),                          # good
]
UX_DECOYS = {"billing.error.expired", "billing.toast.saved", "billing.empty.title", "billing.empty.body", "billing.cta"}


def test_ux_microcopy_lint():
    out = run("ux-writer", "check_microcopy", strings=[{"key": k, "component": c, "text": t} for k, c, t in STRINGS])
    by = {r["key"]: " ".join(r["issues"]) for r in out["strings"]}
    assert "Title Case" in by["auth.cta"] and "Title Case" in by["settings.title"]
    assert "Title Case" in by["settings.save"] and "exclamation" in by["settings.save"]
    assert "vague confirmation" in by["settings.delete.confirm.title"]
    assert "generic button" in by["settings.delete.confirm.cta"]
    assert "noun used as a verb" in by["settings.logout"]
    assert "jargon: token" in by["settings.2fa.tooltip"] and "FK grade" in by["settings.2fa.tooltip"]
    assert "exclamation" in by["billing.error.card"]
    assert all(by[k] == "" for k in UX_DECOYS)


@pytest.mark.parametrize("key,score,what,how", [
    ("auth.error.creds", 10, False, False), ("auth.error.locked", 70, True, False),
    ("billing.error.card", 20, False, False), ("billing.error.expired", 100, True, True)])
def test_ux_error_messages(key, score, what, how):
    msg = next(t for k, _, t in STRINGS if k == key)
    out = run("ux-writer", "lint_error_message", message=msg)
    assert (out["score"], out["parts"]["what"], out["parts"]["how"]) == (score, what, how)
    if key == "auth.error.creds":
        assert any("error code" in i for i in out["issues"]) and any("blame" in i for i in out["issues"])


def test_ux_consistency():
    out = run("ux-writer", "check_consistency", strings=[t for _, _, t in STRINGS])
    c = {x["concept"]: x for x in out["terminology_conflicts"]}
    assert set(c) == {"sign in", "delete", "settings", "email", "sign in / sign out pair"}
    assert c["sign in"]["variants"] == {"sign in": 1, "log in": 1}
    assert c["email"]["variants"] == {"e-mail": 1, "email": 1} and c["email"]["standardise_on"] == "email"
    assert c["settings"]["standardise_on"] == "settings"
    assert out["title_case_examples"] == ["Log In", "Account Preferences", "Save Your Changes!"]


def test_ux_localisation_budget_vs_published_bands():
    out = run("ux-writer", "localization_expansion", text_value="Save changes", container_chars=16, locales=["de", "fr", "fi", "ja"])
    rows = {r["locale"]: r for r in out["locales"]}
    # W3C/IBM: 11-20 char strings reach 180-200% → de budget = 12 × (1 + 0.35 × 0.8 / 0.3) = 23
    assert rows["de"]["budget_chars"] == round(12 * (1 + 0.35 * 0.8 / 0.3)) == 23
    # real UI translations: "Änderungen speichern" (20), "Tallenna muutokset" (18), "Enregistrer les modifications" (29)
    assert out["overflow"] == ["de", "fi"] and out["at_risk"] == ["fr"] and rows["ja"]["fits_budget"] is True


# ══════════════════════════════════════════════════════════════════════════════
# 7. pitch-deck-coach — 12-slide seed deck with claim titles, dental-practice market, $2.5M raise
# ══════════════════════════════════════════════════════════════════════════════

DECK = [
 ("ChairTime — the AI front desk for independent dental practices", "Seed round · Oct 2026", "title"),
 ("Front desks lose 11 hours a week to phone scheduling", "- 11 h/week per practice on the phone (survey of 60 practices)\n- 18% of calls go unanswered at lunch\n- Every missed new-patient call is ~$1,200 of lifetime value", "problem"),
 ("Our AI books, confirms and fills cancellations 24/7", "Answers the phone, books into Dentrix/Open Dental, texts confirmations and back-fills cancellations from the waitlist.", "solution"),
 ("Traction: 38 practices, $15.2k MRR, 22% MoM growth", "- 38 paying practices\n- $15.2k MRR\n- 22% month-over-month for 6 months\n- 1.1% monthly logo churn", "traction"),
 ("Product demo", "Screenshots of the call log, the booking view and the cancellation back-fill flow.", "product"),
 ("A $12B dental software market", "Dental practice software is a $12B market growing 9% a year (Grand View Research). We only need 1% of it.", "market"),
 ("Why now: voice AI costs fell 90% since 2023", "Speech-to-text and LLM inference costs collapsed; practices now accept AI after 2025 staffing shortages.", "why_now"),
 ("Team: ex-Dentrix PM + ML lead from Google", "Ana (CEO) ran scheduling at Dentrix for 6 years. Raj (CTO) built speech models at Google.", "team"),
 ("Competition: Weave, NexHealth and doing nothing", "Weave and NexHealth sell phones and reminders, not an agent that books. Most practices still use a human and voicemail.", "competition"),
 ("Business model: $400/month per practice, 82% gross margin", "Flat $400/month per location. Gross margin 82% after inference and telephony. CAC payback 5 months.", "business_model"),
 ("The ask: $2.5M seed to reach $1M ARR", "Raising $2.5M on a $12M post-money SAFE.", "financials_ask"),
 ("Use of funds: 18 months, 3 AEs, 2 engineers", "- 55% go-to-market (3 AEs)\n- 35% product/engineering (2 engineers)\n- 10% ops and compliance (HIPAA audit)", "use_of_funds"),
]


def test_pitch_structure_with_ai_classification():
    out = run("pitch-deck-coach", "check_deck_structure", slide_titles=[t for t, _, _ in DECK], stage="seed", slide_types=[g for _, _, g in DECK])
    assert out["canonical_score"] == "12/12" and out["missing"] == []
    assert "market before why_now" in out["order_inversions"] and "traction before market" in out["order_inversions"]
    assert out["critical_order_problems"] == []


def test_pitch_structure_keyword_fallback_warns_instead_of_asserting_missing():
    out = run("pitch-deck-coach", "check_deck_structure", slide_titles=[t for t, _, _ in DECK], stage="seed")
    right = sum(m["canonical"] == DECK[m["slide"] - 1][2] for m in out["mapping"])
    assert right == 11  # was 10/12 with the problem slide reported "missing"
    assert out["problems"][0].startswith("1 slide(s) matched no section keyword")


def test_pitch_market_size_by_hand():
    out = run("pitch-deck-coach", "market_size", target_customers=135_000, annual_revenue_per_customer=4_800,
              serviceable_pct=35, capture_pct=3, top_down_tam=12_000_000_000, years=5)
    assert out["tam"] == 135_000 * 4_800 == 648_000_000
    assert out["sam"] == 226_800_000 and out["som"] == 6_804_000
    assert out["som_customers"] == round(135_000 * 0.35 * 0.03) == 1418 and out["customers_to_win_per_year"] == 283.5
    assert "under $1B" in out["flags"][0] and "5.4% of the top-down" in out["flags"][1]


def test_pitch_raise_math_by_hand():
    out = run("pitch-deck-coach", "raise_math", amount=2_500_000, valuation=12_000_000, valuation_is_post=True,
              option_pool_pct=10, monthly_burn=140_000, burn_growth_pct_per_month=3, start_date="2026-11-01", existing_cash=300_000)
    assert out["investor_pct"] == round(100 * 2.5 / 12, 2) == 20.83
    assert out["founders_and_existing_pct"] == 69.17 and out["effective_pre_money"] == 9_500_000 - 1_200_000
    # cumulative burn 140k × (1.03^m − 1)/0.03 = 2.8M  →  m = ln(1.6)/ln(1.03) = 15.90
    assert out["runway"]["months"] == round(math.log(1.6) / math.log(1.03), 1) == 15.9
    need = 140_000 * (1.03 ** 18 - 1) / 0.03
    assert f"${need:,.0f}" in out["flags"][1] and f"${need - 2_800_000:,.0f} more" in out["flags"][1]


def test_pitch_slide_density():
    out = run("pitch-deck-coach", "slide_density", slides=[{"title": t, "body": b} for t, b, _ in DECK])
    flagged = {s["slide"]: " ".join(s["issues"]) for s in out["slides"] if s["issues"]}
    assert set(flagged) == {5, 6, 9}
    assert "label" in flagged[5] and "1% of the market" in flagged[6]


def test_roadmap_final_plan_after_judgement_moves_fits():
    items = [("PDF export fix", "must", 1), ("Custom fields in exports", "must", 1.5), ("SSO (SAML)", "must", 6),
             ("Slack notifications", "must", 2), ("Recurring tasks", "must", 4), ("Keyboard shortcuts", "should", 0.4),
             ("Audit log", "should", 3), ("Gantt dependencies", "should", 8), ("Bulk CSV import", "could", 3),
             ("Dark mode", "could", 2), ("Mobile offline mode", "wont", 10), ("AI task summaries", "wont", 6)]
    out = run("roadmap-prioritizer", "capacity_check", capacity_weeks=36, items=[{"name": n, "moscow": m, "effort": e} for n, m, e in items])
    assert out["must_pct_of_capacity"] == round(100 * 14.5 / 36, 1) == 40.3
    assert out["problems"] == [] and out["below_the_line"] == ["Bulk CSV import", "Dark mode"]
    assert out["verdict"] == "Plan fits with contingency (Coulds are the buffer)"


# Machado 2009 severity-1.0 simulations computed by colorspacious 1.1.2 ("sRGB1+CVD", severity 100) — an
# independent published implementation — for the palette's fixed error/success/link/warning colours
COLORSPACIOUS = {
    "d73d3d": ("#6a613b", "#908238", "#ec003f"), "178841": ("#897c3b", "#7c7346", "#008578"),
    "2563eb": ("#0076f0", "#0064e8", "#00869d"), "b45309": ("#6f6100", "#877703", "#c63c47"),
}


def test_a11y_colour_blindness_simulation_matches_colorspacious():
    out = run("accessibility-checker", "simulate_color_blindness", colors=["#" + c for c in COLORSPACIOUS],
              pairs=[["#d73d3d", "#178841"], ["#2563eb", "#1f2937"], ["#b45309", "#178841"]])
    for row in out["simulated"]:
        assert (row["protanopia"], row["deuteranopia"], row["tritanopia"]) == COLORSPACIOUS[row["color"][1:]]
    # the fixed error red and success green both sit at ~4.5:1 on white, so they are luminance twins:
    # only hue separates them → WCAG 1.4.1 needs an icon/text cue
    pair = out["pairs"][0]
    assert pair["contrast_between"] == 1.0 and pair["collapses_for"] == ["achromatopsia"]
    assert out["pairs"][1]["collapses_for"] == []
