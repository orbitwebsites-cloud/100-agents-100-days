"""Shared helpers for the SEO & Growth agents (skipped by the registry).

- ``parse_html`` — a stdlib ``html.parser`` page model (title, metas, headings,
  links, images, canonical, JSON-LD, visible text) used by the SEO auditor,
  meta writer, schema builder and local SEO agents.
- ``tokens`` — a light stemmer + stopword filter for keyword clustering and
  near-duplicate detection.
- ``arial_width`` — Arial/Helvetica advance widths for SERP pixel estimates.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urlparse

from ...core import ToolError
from ...lib import text as _text

MAX_HTML = 400_000

# ── HTML page model ───────────────────────────────────────────


@dataclass
class Page:
    title: str = ""
    title_count: int = 0
    lang: str = ""
    charset: str = ""
    metas: dict[str, str] = field(default_factory=dict)  # name/property (lowercased) -> content
    headings: list[dict] = field(default_factory=list)  # {"level": int, "text": str}
    links: list[dict] = field(default_factory=list)  # {"href", "text", "rel", "target"}
    images: list[dict] = field(default_factory=list)  # {"src", "alt"(None if missing), "width", "height", "loading"}
    canonical: list[str] = field(default_factory=list)
    hreflang: list[dict] = field(default_factory=list)
    jsonld: list[str] = field(default_factory=list)
    text: str = ""
    paragraphs: list[str] = field(default_factory=list)
    iframes: int = 0
    forms: int = 0
    has_viewport: bool = False
    inline_scripts: int = 0
    external_scripts: int = 0
    html_len: int = 0

    @property
    def h1s(self) -> list[str]:
        return [h["text"] for h in self.headings if h["level"] == 1]

    @property
    def description(self) -> str:
        return self.metas.get("description", "")

    @property
    def robots(self) -> str:
        return self.metas.get("robots", "")


_SKIP_TAGS = {"script", "style", "noscript", "template", "svg"}
_BLOCK_TAGS = {"p", "div", "li", "br", "tr", "td", "th", "section", "article", "header", "footer", "blockquote", "pre", "h1", "h2", "h3", "h4", "h5", "h6"}


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.page = Page()
        self._skip_depth = 0
        self._in_title = False
        self._heading: dict | None = None
        self._link: dict | None = None
        self._jsonld = False
        self._script_buf: list[str] = []
        self._text: list[str] = []
        self._para: list[str] | None = None
        self._in_head = False

    # helpers
    def _attr(self, attrs, key):
        for k, v in attrs:
            if k and k.lower() == key:
                return (v or "").strip()
        return None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        p = self.page
        if tag in _SKIP_TAGS:
            if tag == "script":
                typ = (self._attr(attrs, "type") or "").lower()
                if "ld+json" in typ:
                    self._jsonld = True
                    self._script_buf = []
                elif self._attr(attrs, "src"):
                    p.external_scripts += 1
                else:
                    p.inline_scripts += 1
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "head":
            self._in_head = True
        elif tag == "html":
            p.lang = self._attr(attrs, "lang") or ""
        elif tag == "title":
            self._in_title = True
            p.title_count += 1
        elif tag == "meta":
            name = (self._attr(attrs, "name") or self._attr(attrs, "property") or self._attr(attrs, "http-equiv") or "").lower()
            content = self._attr(attrs, "content") or ""
            charset = self._attr(attrs, "charset")
            if charset:
                p.charset = charset
            if name:
                if name == "viewport":
                    p.has_viewport = True
                if name not in p.metas:
                    p.metas[name] = content
                else:
                    p.metas[name + "#dup"] = content
        elif tag == "link":
            rel = (self._attr(attrs, "rel") or "").lower().split()
            href = self._attr(attrs, "href") or ""
            if "canonical" in rel:
                p.canonical.append(href)
            if "alternate" in rel and self._attr(attrs, "hreflang"):
                p.hreflang.append({"hreflang": self._attr(attrs, "hreflang"), "href": href})
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._heading = {"level": int(tag[1]), "text": ""}
            self._text.append("\n")
        elif tag == "a":
            self._link = {"href": self._attr(attrs, "href") or "", "text": "", "rel": (self._attr(attrs, "rel") or "").lower(), "target": self._attr(attrs, "target") or ""}
        elif tag == "img":
            alt = self._attr(attrs, "alt")
            p.images.append(
                {
                    "src": self._attr(attrs, "src") or self._attr(attrs, "data-src") or "",
                    "alt": alt,  # None means attribute missing
                    "width": self._attr(attrs, "width"),
                    "height": self._attr(attrs, "height"),
                    "loading": (self._attr(attrs, "loading") or "").lower(),
                }
            )
            if self._link is not None and alt:
                self._link["text"] += " " + alt
        elif tag == "iframe":
            p.iframes += 1
        elif tag == "form":
            p.forms += 1
        elif tag == "p":
            self._para = []
        if tag in _BLOCK_TAGS:
            self._text.append("\n")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.lower() not in ("br", "img", "meta", "link", "input", "hr"):
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            if tag == "script" and self._jsonld:
                self.page.jsonld.append("".join(self._script_buf).strip())
                self._jsonld = False
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag == "head":
            self._in_head = False
        elif tag == "title":
            self._in_title = False
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self._heading:
            self._heading["text"] = _ws(self._heading["text"])
            self.page.headings.append(self._heading)
            self._heading = None
        elif tag == "a" and self._link is not None:
            self._link["text"] = _ws(self._link["text"])
            self.page.links.append(self._link)
            self._link = None
        elif tag == "p" and self._para is not None:
            para = _ws(" ".join(self._para))
            if para:
                self.page.paragraphs.append(para)
            self._para = None
        if tag in _BLOCK_TAGS:
            self._text.append("\n")

    def handle_data(self, data):
        if self._jsonld:
            self._script_buf.append(data)
            return
        if self._skip_depth:
            return
        if self._in_title:
            self.page.title += data
            return
        if self._in_head:
            return
        if self._heading is not None:
            self._heading["text"] += data
        if self._link is not None:
            self._link["text"] += data
        if self._para is not None:
            self._para.append(data)
        self._text.append(data)


def _ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def parse_html(html: str) -> Page:
    """Parse an HTML document into a Page model. Raises ToolError on empty/oversized input."""
    if not html or not html.strip():
        raise ToolError("HTML is empty. Paste the page source (view-source or a fetched document).")
    if len(html) > MAX_HTML:
        raise ToolError(f"HTML too large ({len(html):,} chars; max {MAX_HTML:,}). Strip inline scripts/styles or send only <head> + <body> content.")
    parser = _PageParser()
    parser.feed(html)
    parser.close()
    page = parser.page
    page.title = _ws(page.title)
    page.html_len = len(html)
    raw = "".join(parser._text)
    lines = [_ws(line) for line in raw.split("\n")]
    page.text = "\n".join(line for line in lines if line)
    return page


# ── URL helpers ───────────────────────────────────────────────


def host_of(url: str) -> str:
    try:
        h = (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""
    return h[4:] if h.startswith("www.") else h


def is_internal(href: str, base_host: str) -> bool | None:
    """True/False for http links, None for non-navigational (mailto, tel, #, javascript)."""
    h = href.strip()
    if not h or h.startswith("#"):
        return None
    low = h.lower()
    if low.startswith(("mailto:", "tel:", "javascript:", "data:", "sms:")):
        return None
    if low.startswith(("http://", "https://", "//")):
        return host_of(h if not h.startswith("//") else "https:" + h) == base_host if base_host else False
    return True  # relative


# ── tokens / stemming ─────────────────────────────────────────

_SUFFIXES = ("ational", "ization", "ities", "ness", "ment", "ings", "ing", "ies", "ers", "ed", "s", "ly", "er")
_EXTRA_STOP = frozenset("best top vs versus near me for to in on of the a an and or with without how what why when where is are".split())


def stem(word: str) -> str:
    """Light suffix stripper: enough to make 'softwares', 'reviewing' and 'review' collide."""
    w = word.lower()
    if len(w) <= 3:
        return w
    if w.endswith(("sses", "xes", "zes", "ches", "shes")) and len(w) >= 6:
        return w[:-2]
    for suf in _SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[: -len(suf)]
            if suf == "ies":
                w += "y"
            break
    return w


def tokens(s: str, keep_stop: bool = False) -> list[str]:
    out = []
    for w in _text.words(s):
        lw = w.lower()
        if not keep_stop and (lw in _text.STOPWORDS or lw in _EXTRA_STOP):
            continue
        out.append(stem(lw))
    return out


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def shingles(s: str, n: int = 3) -> set[tuple[str, ...]]:
    ws = [w.lower() for w in _text.words(s)]
    if len(ws) < n:
        return {tuple(ws)} if ws else set()
    return {tuple(ws[i : i + n]) for i in range(len(ws) - n + 1)}


# ── slugify ───────────────────────────────────────────────────

_SLUG_STOP = frozenset("a an the of and or to in on for with at by from".split())


def slugify(value: str, max_len: int = 60, drop_stopwords: bool = False) -> str:
    s = unicodedata.normalize("NFKD", str(value))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("&", " and ").replace("+", " plus ").replace("@", " at ")
    s = re.sub(r"['’]", "", s.lower())
    parts = [p for p in re.split(r"[^a-z0-9]+", s) if p]
    if drop_stopwords:
        kept = [p for p in parts if p not in _SLUG_STOP]
        parts = kept or parts
    slug = "-".join(parts)
    if len(slug) > max_len:
        cut = slug[:max_len]
        slug = cut[: cut.rfind("-")] if "-" in cut else cut
    return slug.strip("-")


# ── Arial / Helvetica advance widths (per 1000 em units) ──────

_ARIAL: dict[str, int] = {
    " ": 278, "!": 278, '"': 355, "#": 556, "$": 556, "%": 889, "&": 667, "'": 191, "(": 333, ")": 333,
    "*": 389, "+": 584, ",": 278, "-": 333, ".": 278, "/": 278, "0": 556, "1": 556, "2": 556, "3": 556,
    "4": 556, "5": 556, "6": 556, "7": 556, "8": 556, "9": 556, ":": 278, ";": 278, "<": 584, "=": 584,
    ">": 584, "?": 556, "@": 1015, "A": 667, "B": 667, "C": 722, "D": 722, "E": 667, "F": 611, "G": 778,
    "H": 722, "I": 278, "J": 500, "K": 667, "L": 556, "M": 833, "N": 722, "O": 778, "P": 667, "Q": 778,
    "R": 722, "S": 667, "T": 611, "U": 722, "V": 667, "W": 944, "X": 667, "Y": 667, "Z": 611, "[": 278,
    "\\": 278, "]": 278, "^": 469, "_": 556, "`": 333, "a": 556, "b": 556, "c": 500, "d": 556, "e": 556,
    "f": 278, "g": 556, "h": 556, "i": 222, "j": 222, "k": 500, "l": 222, "m": 833, "n": 556, "o": 556,
    "p": 556, "q": 556, "r": 333, "s": 500, "t": 278, "u": 556, "v": 500, "w": 722, "x": 500, "y": 500,
    "z": 500, "{": 334, "|": 260, "}": 334, "~": 584, "–": 556, "—": 1000, "•": 350, "©": 737,
    "®": 737, "™": 1000, "€": 556, "£": 556, "¥": 556, "…": 1000, "‘": 222, "’": 222, "“": 333, "”": 333,
    "«": 556, "»": 556, "°": 400, "·": 278, "×": 584, "→": 1000,
}


def char_width(ch: str, px: float) -> float:
    if ch in _ARIAL:
        u = _ARIAL[ch]
    else:
        cat = unicodedata.category(ch)
        base = unicodedata.normalize("NFKD", ch)[:1]
        if base in _ARIAL:
            u = _ARIAL[base]
        elif cat.startswith("L"):  # CJK and other letters are wide
            u = 1000 if unicodedata.east_asian_width(ch) in ("W", "F") else 556
        elif cat.startswith("N"):
            u = 556
        elif cat.startswith("S"):  # symbols, emoji
            u = 1000
        elif cat.startswith("M"):
            u = 0
        else:
            u = 278
    return u * px / 1000.0


def text_width(s: str, px: float) -> float:
    return round(sum(char_width(c, px) for c in s), 1)


def fit_prefix(s: str, px: float, limit_px: float) -> str:
    """Longest prefix of ``s`` that fits in ``limit_px`` (breaking at a word boundary when possible)."""
    total = 0.0
    for i, c in enumerate(s):
        total += char_width(c, px)
        if total > limit_px:
            cut = s[:i]
            if " " in cut:
                cut = cut[: cut.rfind(" ")]
            return cut.rstrip()
    return s
