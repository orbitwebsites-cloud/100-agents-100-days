"""Accessibility Checker — exact WCAG 2.x contrast math, HTML structure lint, target sizes, and colour fixes."""

from __future__ import annotations

import re
from html.parser import HTMLParser

from ...core import Agent, ToolError
from ._common import check_rows, check_text

AGENT = Agent(
    slug="accessibility-checker",
    name="Accessibility Checker",
    category="product",
    tagline="Exact WCAG contrast ratios, a real HTML structure audit, and the nearest passing colour — not vibes.",
    description=(
        "Audits interfaces the way an accessibility specialist does before a WCAG 2.2 AA sign-off: computes "
        "contrast with the exact relative-luminance formula (black on white = 21:1) for text, large text and "
        "UI components; lints HTML for heading-order skips, missing/empty alt, unlabeled form fields, empty "
        "links and buttons, missing lang, positive tabindex and duplicate IDs; checks touch-target size against "
        "2.5.5/2.5.8; and computes the closest colour that passes so designers get a fix, not just a fail."
    ),
    triggers=[
        "check colour contrast / WCAG contrast ratio",
        "accessibility audit of this HTML / page / component",
        "is this accessible / does this meet WCAG AA",
        "review alt text and heading structure",
        "fix this colour so it passes contrast",
        "are these buttons big enough for touch targets",
    ],
    examples=[
        "Does #767676 text on #FFFFFF pass AA for body text? And for 18px bold?",
        "Here's the HTML of our sign-up page — run an accessibility audit.",
        "Our brand blue #3B82F6 fails on white. Give me the nearest shade that passes AA at 4.5:1.",
    ],
    connectors=["GitHub", "Figma", "Notion", "Linear", "Jira"],
    playbook="""
    ## Standard
    You are an accessibility specialist doing pre-release WCAG 2.2 AA audits. Excellent work is
    exact (ratios to two decimals, criteria cited by number), prioritised (blockers for screen-reader
    and keyboard users first), and constructive (every fail ships with a fix). The one metric that
    matters is **can a keyboard-only and a screen-reader user complete the core task** — everything
    else is ordered behind that.

    ## Intake
    Proceed with what you have. Ask (max 3) only if needed: (1) target level (default AA), (2) the
    core task on the page (to prioritise), (3) font size/weight for text colours (if not given,
    assume body text < 18pt regular and say so). Never eyeball contrast — always compute it.

    ## Procedure
    1. **Compute every colour pair.** Call `accessibility_checker__contrast_ratio` for each
       foreground/background pair (text, placeholders, icons, borders of inputs, focus rings). It
       implements the WCAG 2.x relative-luminance formula exactly and reports pass/fail for
       1.4.3 (AA: 4.5:1 normal, 3:1 large ≥ 18pt or 14pt bold), 1.4.6 (AAA: 7:1 / 4.5:1), and
       1.4.11 non-text contrast (3:1 for UI components and graphical objects). Placeholder text is
       text — it must pass too. Alpha channels: flatten onto the background first.
    2. **Fix failing colours.** Call `accessibility_checker__suggest_color` with the failing pair
       and the target ratio. It walks the foreground darker/lighter in small steps to find the
       nearest hue-preserving shade that passes and reports the delta, so the designer keeps the
       brand hue. Offer both the foreground fix and the background fix.
    3. **Audit the markup.** Call `accessibility_checker__lint_html` with the HTML. It checks:
       heading order (no skipped levels, exactly one h1), images without alt / with filename alt /
       decorative images not marked alt="", form controls without labels (label[for], aria-label,
       aria-labelledby), empty links and buttons, links with "click here"/"read more" text,
       missing <html lang>, positive tabindex, duplicate ids, missing page <title>, iframes without
       title, tables without headers, and autoplay media. Each finding cites the WCAG criterion.
    4. **Check targets.** Call `accessibility_checker__target_size` with the interactive elements'
       sizes and spacing. 2.5.8 (AA, WCAG 2.2) needs 24×24 CSS px or equivalent spacing; 2.5.5
       (AAA) 44×44. Icon-only buttons are the usual offenders.
    5. **Keyboard and screen-reader walkthrough (by reasoning).** Trace the core task: is every
       control reachable by Tab in a logical order? Is focus visible (2.4.7, 2.4.11)? Do custom
       widgets have roles, names and states (4.1.2)? Are errors announced and described (3.3.1,
       3.3.3)? Is there a skip link (2.4.1)? Does content reflow at 320px / 400% zoom (1.4.10)?
       State what you could verify from the code and what needs a manual test with NVDA/VoiceOver.
    6. **Prioritise:** Blocker (task impossible for a group) → Major (task possible with serious
       difficulty) → Minor (annoyance / best practice). Report blockers first, with element,
       criterion, fix.
    7. **Deliver** in the output format. If GitHub/Linear/Jira is connected, open one issue per
       blocker with the fix; otherwise output ready to paste.

    ## Frameworks
    - **WCAG 2.2 POUR:** Perceivable, Operable, Understandable, Robust — group findings this way.
    - **Contrast formula:** L = 0.2126 R + 0.7152 G + 0.0722 B with sRGB linearisation
      (c ≤ 0.04045 → c/12.92, else ((c+0.055)/1.055)^2.4); ratio = (L1 + 0.05)/(L2 + 0.05).
    - **Large text:** ≥ 18pt (24px) regular or ≥ 14pt (18.66px) bold.
    - **Accessible name computation:** aria-labelledby > aria-label > native label/alt/content >
      title. Check in that order.
    - **Severity:** Blocker = fails 1.1.1, 1.3.1 (forms), 2.1.1, 2.4.3, 4.1.2 on the core task;
      Major = contrast fails on body text, missing focus indicator; Minor = heading skips on
      non-core content, redundant alt.

    ## Output format
    ```
    # Accessibility audit — <page/component> — target WCAG 2.2 AA
    **Verdict:** <n> blockers · <n> major · <n> minor — <can a keyboard/screen-reader user complete the core task? yes/no>

    ## Blockers
    | # | Element | Criterion | Problem | Fix |
    ## Major
    | # | Element | Criterion | Problem | Fix |
    ## Minor
    …
    ## Contrast table
    | Pair | Ratio | Normal text | Large text | UI (3:1) | Nearest passing |
    | #767676 on #FFF | 4.54:1 | AA pass | AAA fail | pass | — |

    ## Needs manual testing
    - <what to test with NVDA / VoiceOver / keyboard-only, and why>
    ## Scope note
    Automated checks find roughly 30-40% of WCAG issues; this audit is not a conformance certificate.
    ```

    ## Anti-patterns
    - "Looks readable to me." Compute it; #777 on white fails AA by a hair (4.48:1).
    - alt text that repeats the caption or says "image of". Describe function, or alt="" if decorative.
    - Fixing contrast by making everything black. Use the nearest passing shade and keep hierarchy.
    - Treating aria-* as a fix for div-buttons. Use <button>; ARIA is the last resort.
    - Reporting 60 issues with equal weight. Blockers first; three fixed blockers beat 60 listed minors.
    - Ignoring focus visibility and target size — they're where real keyboard/touch users fail.
    """,
)

HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
RGB_RE = re.compile(r"^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*([0-9.]+)\s*)?\)$", re.I)
NAMED = {"black": "#000000", "white": "#ffffff", "red": "#ff0000", "green": "#008000", "blue": "#0000ff", "gray": "#808080", "grey": "#808080", "yellow": "#ffff00", "orange": "#ffa500", "purple": "#800080", "navy": "#000080", "silver": "#c0c0c0"}


def parse_color(value: str) -> tuple[int, int, int, float]:
    """Parse #rgb/#rgba/#rrggbb/#rrggbbaa/rgb()/rgba()/named into (r, g, b, alpha)."""
    s = str(value).strip().lower()
    s = NAMED.get(s, s)
    m = HEX_RE.match(s)
    if m:
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return r, g, b, a
    m = RGB_RE.match(s)
    if m:
        r, g, b = (int(m.group(i)) for i in (1, 2, 3))
        if max(r, g, b) > 255:
            raise ToolError(f"rgb component out of range in {value!r}.")
        a = float(m.group(4)) if m.group(4) else 1.0
        return r, g, b, max(0.0, min(1.0, a))
    raise ToolError(f"Unrecognised colour {value!r}. Use #rrggbb, #rgb, rgb(r,g,b) or a basic colour name.")


def _lin(c: int) -> float:
    v = c / 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def ratio(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    l1, l2 = luminance(fg), luminance(bg)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


def flatten(fg: tuple[int, int, int, float], bg: tuple[int, int, int]) -> tuple[int, int, int]:
    r, g, b, a = fg
    if a >= 1:
        return r, g, b
    return tuple(round(a * c + (1 - a) * bc) for c, bc in zip((r, g, b), bg))  # type: ignore[return-value]


def hexstr(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _is_large(font_px: float, bold: bool) -> bool:
    return font_px >= 24 or (bold and font_px >= 18.66)


@AGENT.tool
def contrast_ratio(foreground: str, background: str, font_px: float = 16.0, bold: bool = False) -> dict:
    """Exact WCAG 2.x contrast ratio between two colours with AA/AAA and non-text (3:1) verdicts.

    Accepts hex (#rgb, #rrggbb, #rrggbbaa), rgb()/rgba() and basic names. Alpha in the foreground is
    flattened onto the background first. Black on white returns 21.0.

    Args:
        foreground: Text/icon colour, e.g. "#767676".
        background: Background colour, e.g. "#ffffff".
        font_px: Font size in CSS px (default 16) — decides whether the large-text threshold applies.
        bold: True if the text is bold (≥ 700) — lowers the large-text threshold to 18.66px.
    """
    fg = parse_color(foreground)
    bg4 = parse_color(background)
    if not isinstance(font_px, (int, float)) or font_px <= 0 or font_px > 400:
        raise ToolError("font_px must be a positive number of CSS pixels (≤ 400).")
    bg = (bg4[0], bg4[1], bg4[2]) if bg4[3] >= 1 else flatten(bg4, (255, 255, 255))
    fgf = flatten(fg, bg)
    r = ratio(fgf, bg)
    r2 = round(r, 2)
    large = _is_large(float(font_px), bool(bold))
    aa_needed = 3.0 if large else 4.5
    aaa_needed = 4.5 if large else 7.0
    verdict = ("AAA" if r >= aaa_needed else "AA" if r >= aa_needed else "FAIL")
    return {
        "ratio": r2,
        "ratio_text": f"{r2}:1",
        "foreground": hexstr(fgf) + (" (flattened)" if fg[3] < 1 else ""),
        "background": hexstr(bg),
        "luminance": {"foreground": round(luminance(fgf), 4), "background": round(luminance(bg), 4)},
        "text_size": "large" if large else "normal",
        "aa_normal_text": r >= 4.5,
        "aa_large_text": r >= 3.0,
        "aaa_normal_text": r >= 7.0,
        "aaa_large_text": r >= 4.5,
        "non_text_ui": r >= 3.0,
        "this_text": {"aa": r >= aa_needed, "aaa": r >= aaa_needed, "needed_aa": aa_needed, "needed_aaa": aaa_needed},
        "verdict": f"{r2}:1 — {verdict} for {'large' if large else 'normal'} text (needs {aa_needed}:1 AA / {aaa_needed}:1 AAA)",
        "criteria": "WCAG 1.4.3 (AA), 1.4.6 (AAA), 1.4.11 (non-text 3:1)",
    }


@AGENT.tool
def suggest_color(foreground: str, background: str, target_ratio: float = 4.5, adjust: str = "foreground") -> dict:
    """Find the nearest shade of the foreground (or background) that reaches the target contrast ratio.

    Walks lightness toward black or white in 1% steps keeping the hue, and reports both directions
    where possible so the designer can choose.

    Args:
        foreground: Current text/icon colour.
        background: Current background colour.
        target_ratio: Required ratio: 4.5 (AA text), 3 (large text / UI), 7 (AAA).
        adjust: "foreground" (default) or "background" — which colour to change.
    """
    fg4, bg4 = parse_color(foreground), parse_color(background)
    if not isinstance(target_ratio, (int, float)) or not 1.0 <= target_ratio <= 21.0:
        raise ToolError("target_ratio must be between 1 and 21.")
    which = str(adjust).strip().lower()
    if which not in {"foreground", "background"}:
        raise ToolError("adjust must be 'foreground' or 'background'.")
    bg = (bg4[0], bg4[1], bg4[2])
    fg = flatten(fg4, bg)
    current = ratio(fg, bg)
    if current >= target_ratio:
        return {"already_passes": True, "current_ratio": round(current, 2), "target_ratio": target_ratio, "suggestion": hexstr(fg if which == "foreground" else bg), "verdict": f"Already {round(current, 2)}:1 ≥ {target_ratio}:1"}
    fixed, other = (fg, bg) if which == "foreground" else (bg, fg)

    def walk(toward: tuple[int, int, int]) -> tuple[tuple[int, int, int], float, int] | None:
        for step in range(1, 101):
            t = step / 100
            cand = tuple(round(c + (tc - c) * t) for c, tc in zip(fixed, toward))  # type: ignore[assignment]
            r = ratio(cand, other)  # type: ignore[arg-type]
            if r >= target_ratio:
                return cand, r, step  # type: ignore[return-value]
        return None

    darker, lighter = walk((0, 0, 0)), walk((255, 255, 255))
    options = []
    for label, res in (("darker", darker), ("lighter", lighter)):
        if res:
            cand, r, step = res
            options.append({"direction": label, "color": hexstr(cand), "ratio": round(r, 2), "change_pct": step})
    if not options:
        raise ToolError("No shade of that colour reaches the target ratio against the other colour — change the other colour too.")
    best = min(options, key=lambda o: o["change_pct"])
    return {
        "already_passes": False,
        "current_ratio": round(current, 2),
        "target_ratio": target_ratio,
        "adjusted": which,
        "suggestion": best["color"],
        "options": options,
        "verdict": f"{hexstr(fixed)} → {best['color']} ({best['direction']} by {best['change_pct']}%) reaches {best['ratio']}:1",
    }


class _Auditor(HTMLParser):
    HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.findings: list[dict] = []
        self.headings: list[int] = []
        self.ids: dict[str, int] = {}
        self.has_lang = False
        self.has_title = False
        self.title_text = ""
        self.html_seen = False
        self.labels_for: set[str] = set()
        self.controls: list[dict] = []
        self.stack: list[tuple[str, dict, list[str]]] = []
        self.images = 0
        self.tables: list[dict] = []
        self.in_title = False
        self.line = 1
        self.skip_link_candidate = False
        self.first_link_seen = False
        self.label_depth = 0

    def _add(self, sev: str, crit: str, el: str, problem: str, fix: str) -> None:
        self.findings.append({"severity": sev, "criterion": crit, "element": el[:120], "problem": problem, "fix": fix})

    def handle_starttag(self, tag: str, attrs_list: list) -> None:
        attrs = {k.lower(): (v if v is not None else "") for k, v in attrs_list}
        el = f"<{tag}" + (f" id={attrs['id']!r}" if attrs.get("id") else "") + ">"
        if tag == "html":
            self.html_seen = True
            if attrs.get("lang", "").strip():
                self.has_lang = True
        if tag == "title":
            self.in_title = True
            self.has_title = True
        if "id" in attrs and attrs["id"]:
            self.ids[attrs["id"]] = self.ids.get(attrs["id"], 0) + 1
        if tag in self.HEADINGS:
            self.headings.append(int(tag[1]))
        if tag == "img":
            self.images += 1
            alt = attrs.get("alt")
            role = attrs.get("role", "")
            if alt is None and role != "presentation" and "aria-hidden" not in attrs:
                self._add("blocker", "1.1.1", f"<img src={attrs.get('src', '')[:40]!r}>", "no alt attribute", "add alt describing the image's function, or alt=\"\" if decorative")
            elif alt and re.search(r"\.(png|jpe?g|gif|svg|webp)$|^(image|photo|picture|img|icon|graphic)( of)?$", alt.strip(), re.I):
                self._add("major", "1.1.1", f"<img alt={alt!r}>", "alt is a filename or 'image of'", "describe what the image conveys, not that it is an image")
            elif alt and len(alt) > 150:
                self._add("minor", "1.1.1", f"<img alt={alt[:30]!r}…>", f"alt is {len(alt)} chars", "keep alt ≤ 150 chars; move detail to surrounding text or longdesc")
        if tag in {"input", "select", "textarea"}:
            itype = attrs.get("type", "text").lower()
            if not (tag == "input" and itype in {"hidden", "submit", "button", "reset", "image"}):
                self.controls.append({"tag": tag, "id": attrs.get("id", ""), "aria": bool(attrs.get("aria-label") or attrs.get("aria-labelledby")), "title": bool(attrs.get("title")), "in_label": self.label_depth > 0, "type": itype, "placeholder": attrs.get("placeholder", "")})
            if tag == "input" and itype == "image" and not attrs.get("alt"):
                self._add("blocker", "1.1.1", "<input type=image>", "image button without alt", "add alt with the button's action")
        if tag == "label":
            self.label_depth += 1
            if attrs.get("for"):
                self.labels_for.add(attrs["for"])
        if tag == "iframe" and not attrs.get("title"):
            self._add("major", "4.1.2", el, "iframe without title", "add title describing the embedded content")
        if "tabindex" in attrs:
            try:
                if int(attrs["tabindex"]) > 0:
                    self._add("major", "2.4.3", el, f"positive tabindex={attrs['tabindex']}", "use tabindex=0/-1 and fix DOM order instead")
            except ValueError:
                pass
        if tag in {"video", "audio"} and "autoplay" in attrs and "muted" not in attrs:
            self._add("major", "1.4.2", el, "media autoplays with sound", "remove autoplay or add controls and muted")
        if tag == "table":
            self.tables.append({"th": 0, "el": el})
        if tag == "th" and self.tables:
            self.tables[-1]["th"] += 1
        if tag in {"div", "span"} and attrs.get("onclick") and attrs.get("role") not in {"button", "link"}:
            self._add("blocker", "4.1.2", el, "clickable div/span without role", "use <button> or <a>; if not possible add role, tabindex=0 and key handlers")
        if tag in {"a", "button"}:
            self.stack.append((tag, attrs, []))
            if tag == "a" and not self.first_link_seen:
                self.first_link_seen = True
                self.skip_link_candidate = attrs.get("href", "").startswith("#")
        if tag == "html" or tag == "body":
            pass

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_text += data
        if self.stack:
            self.stack[-1][2].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag == "label" and self.label_depth:
            self.label_depth -= 1
        if tag in {"a", "button"} and self.stack and self.stack[-1][0] == tag:
            _, attrs, texts = self.stack.pop()
            name = " ".join(texts).strip() or attrs.get("aria-label", "").strip() or attrs.get("title", "").strip()
            el = f"<{tag} href={attrs.get('href', '')[:30]!r}>" if tag == "a" else "<button>"
            if not name and "aria-labelledby" not in attrs:
                self._add("blocker", "2.4.4" if tag == "a" else "4.1.2", el, f"{tag} has no accessible name (empty or icon-only)", "add visible text or aria-label")
            elif tag == "a" and re.fullmatch(r"(click here|here|read more|more|learn more|link|this)\.?", name, re.I):
                self._add("minor", "2.4.4", el, f"link text {name!r} is not descriptive", "say where the link goes: 'Read the pricing FAQ'")
            if tag == "a" and attrs.get("target") == "_blank" and "new" not in name.lower():
                self._add("minor", "3.2.5", el, "opens new window without warning", "add '(opens in new tab)' to the link text or aria-label")


@AGENT.tool
def lint_html(html: str) -> dict:
    """Audit HTML for WCAG structure issues: headings, alt text, form labels, names, lang, tabindex, ids, tables.

    Each finding cites the criterion and a fix; findings are ordered blocker → major → minor.

    Args:
        html: The page or component markup (fragment or full document; up to 200k chars).
    """
    body = check_text(html, "html")
    p = _Auditor()
    try:
        p.feed(body)
        p.close()
    except Exception as e:  # pragma: no cover - defensive against parser edge cases
        raise ToolError(f"Could not parse HTML: {e}") from None
    f = p.findings
    full_doc = p.html_seen
    if full_doc and not p.has_lang:
        f.append({"severity": "major", "criterion": "3.1.1", "element": "<html>", "problem": "no lang attribute", "fix": 'add <html lang="en">'})
    if full_doc and (not p.has_title or not p.title_text.strip()):
        f.append({"severity": "major", "criterion": "2.4.2", "element": "<title>", "problem": "missing or empty page title", "fix": "add a unique, descriptive <title>"})
    h1s = p.headings.count(1)
    if p.headings:
        if h1s == 0:
            f.append({"severity": "major", "criterion": "1.3.1", "element": "headings", "problem": "no <h1>", "fix": "make the page's main heading an <h1>"})
        elif h1s > 1:
            f.append({"severity": "minor", "criterion": "1.3.1", "element": "headings", "problem": f"{h1s} <h1> elements", "fix": "keep one h1; demote the others"})
        prev = None
        for lvl in p.headings:
            if prev is not None and lvl > prev + 1:
                f.append({"severity": "minor", "criterion": "1.3.1", "element": f"<h{lvl}>", "problem": f"heading level skips from h{prev} to h{lvl}", "fix": f"use h{prev + 1} or restructure"})
            prev = lvl
    elif full_doc:
        f.append({"severity": "major", "criterion": "1.3.1", "element": "headings", "problem": "no headings at all", "fix": "add an h1 and section headings"})
    for c in p.controls:
        labelled = c["aria"] or (c["id"] and c["id"] in p.labels_for) or c["in_label"] or c["title"]
        if not labelled:
            el = f"<{c['tag']}" + (f" type={c['type']}" if c["tag"] == "input" else "") + (f" id={c['id']!r}" if c["id"] else "") + ">"
            fix = "add <label for=id> or aria-label" + (" — a placeholder is not a label" if c["placeholder"] else "")
            f.append({"severity": "blocker", "criterion": "1.3.1 / 4.1.2", "element": el, "problem": "form control has no label", "fix": fix})
    for i, n in p.ids.items():
        if n > 1:
            f.append({"severity": "major", "criterion": "4.1.1", "element": f"id={i!r}", "problem": f"duplicate id ({n}×)", "fix": "ids must be unique — labels and aria references break otherwise"})
    for t in p.tables:
        if t["th"] == 0:
            f.append({"severity": "major", "criterion": "1.3.1", "element": t["el"], "problem": "data table without <th> headers", "fix": "add <th scope=col/row> for header cells (or role=presentation if layout)"})
    if full_doc and not p.skip_link_candidate and p.first_link_seen:
        f.append({"severity": "minor", "criterion": "2.4.1", "element": "page", "problem": "no skip link as first focusable element", "fix": 'add <a href="#main" class="skip-link">Skip to content</a>'})
    order = {"blocker": 0, "major": 1, "minor": 2}
    f.sort(key=lambda x: order[x["severity"]])
    counts = {k: sum(1 for x in f if x["severity"] == k) for k in order}
    return {
        "findings": f,
        "counts": counts,
        "stats": {"headings": p.headings, "images": p.images, "form_controls": len(p.controls), "full_document": full_doc},
        "verdict": f"{counts['blocker']} blocker(s), {counts['major']} major, {counts['minor']} minor" + (" — fix blockers before anything else" if counts["blocker"] else ""),
        "manual_checks": ["keyboard-only walkthrough of the core task (2.1.1, 2.4.3, 2.4.7)", "screen-reader pass with NVDA or VoiceOver (4.1.2 names/roles/states)", "400% zoom / 320px reflow (1.4.10)", "colour is not the only cue (1.4.1)"],
        "scope_note": "Automated lint catches roughly a third of WCAG issues; not a conformance statement.",
    }


@AGENT.tool
def target_size(targets: list[dict]) -> dict:
    """Check interactive elements against WCAG 2.5.8 (24×24 AA) and 2.5.5 (44×44 AAA) target sizes.

    Args:
        targets: List of {"name": str, "width": px, "height": px, "spacing": px gap to nearest other target (optional), "inline": bool (optional, text links in a sentence are exempt)}.
    """
    rows = check_rows(targets, "targets")
    out, aa_fail, aaa_fail = [], 0, 0
    for i, raw in enumerate(rows):
        if not isinstance(raw, dict):
            raise ToolError(f"targets[{i}] must be an object with name, width, height.")
        try:
            w, h = float(raw.get("width")), float(raw.get("height"))
        except (TypeError, ValueError):
            raise ToolError(f"targets[{i}] needs numeric width and height in px.") from None
        if w <= 0 or h <= 0:
            raise ToolError(f"targets[{i}]: width and height must be positive.")
        spacing = float(raw.get("spacing", 0) or 0)
        inline = bool(raw.get("inline", False))
        short = min(w, h)
        # 2.5.8: 24x24, or the target's 24px-diameter circle doesn't intersect another target's (spacing offset)
        aa = inline or short >= 24 or (short + spacing >= 24 and spacing > 0)
        aaa = inline or short >= 44
        issues = []
        if not aa:
            issues.append(f"{w:g}×{h:g}px < 24×24 (2.5.8 AA) — enlarge to 24px or add {24 - short:g}px spacing")
        if not aaa and not inline:
            issues.append(f"< 44×44 (2.5.5 AAA) — recommended for primary mobile actions")
        aa_fail += not aa
        aaa_fail += not aaa
        out.append({"name": str(raw.get("name", f"target {i + 1}")), "width": w, "height": h, "spacing": spacing, "aa_2_5_8": aa, "aaa_2_5_5": aaa, "issues": issues})
    return {"targets": out, "aa_failures": aa_fail, "aaa_failures": aaa_fail, "verdict": f"{len(out) - aa_fail}/{len(out)} meet 2.5.8 (AA); {len(out) - aaa_fail}/{len(out)} meet 2.5.5 (AAA)"}
