"""The audit engine — real measurements against a real website.

This module is the reason Lead Scout is an agent and not a prompt. Every number
in here comes from actually fetching the prospect's site: the clock on the
request, the bytes on the wire, the certificate on the socket, the status code
on each link. A language model cannot know any of it without going and looking.

`audit_site()` returns a plain dict: measured metrics, a list of findings with
severities, and a 0-100 score. The agent's job is to turn that into a pitch.
"""

from __future__ import annotations

import re
import socket
import ssl
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests

from . import config

UA = "Mozilla/5.0 (compatible; LeadScout/1.0; +https://github.com/orbitwebsites-cloud/100-agents-100-days)"
TIMEOUT = 20
LINK_TIMEOUT = 8
MAX_LINKS_CHECKED = 10

# Severity → points knocked off the 100-point score.
WEIGHTS = {"critical": 18, "warning": 8, "note": 3}


@dataclass
class Finding:
    """One thing wrong with the site, with the evidence that proves it."""

    severity: str  # critical | warning | note
    code: str
    message: str
    evidence: str = ""


@dataclass
class Audit:
    """Everything measured about one website."""

    url: str
    final_url: str = ""
    reachable: bool = False
    error: str = ""
    status_code: int = 0
    ttfb_ms: int = 0
    load_ms: int = 0
    page_bytes: int = 0
    https: bool = False
    ssl_days_left: int | None = None
    title: str = ""
    meta_description: str = ""
    h1_count: int = 0
    images_total: int = 0
    images_missing_alt: int = 0
    has_viewport: bool = False
    has_og_image: bool = False
    has_favicon: bool = False
    has_form: bool = False
    has_phone_link: bool = False
    has_email_link: bool = False
    has_analytics: bool = False
    render_blocking_scripts: int = 0
    robots_txt: bool = False
    sitemap_xml: bool = False
    platform: str = "unknown"
    links_checked: int = 0
    broken_links: list[str] = field(default_factory=list)
    pagespeed_score: int | None = None
    score: int = 0
    findings: list[Finding] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── helpers ──────────────────────────────────────────────────


def normalize_url(url: str) -> str:
    """Accept 'acme.com' as readily as 'https://acme.com/'."""
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return url


def _text_between(html: str, pattern: str) -> str:
    m = re.search(pattern, html, re.I | re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def _ssl_days_left(host: str) -> int | None:
    """Days until the TLS certificate expires. None if we can't read one."""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                cert = tls.getpeercert()
        expires = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(
            tzinfo=timezone.utc
        )
        return (expires - datetime.now(timezone.utc)).days
    except Exception:
        return None


def _detect_platform(html: str, headers: dict) -> str:
    """Best-effort guess at what the site is built on — shapes the pitch."""
    blob = html[:200_000].lower()
    powered = str(headers.get("x-powered-by", "")).lower()
    checks = [
        ("WordPress", "wp-content" in blob or "wp-includes" in blob),
        ("Shopify", "cdn.shopify.com" in blob),
        ("Wix", "wix.com" in blob or "wixstatic" in blob),
        ("Squarespace", "squarespace" in blob),
        ("Webflow", "webflow" in blob),
        ("GoDaddy Website Builder", "godaddy" in blob and "websitebuilder" in blob),
        ("Next.js", "__next_data__" in blob or "next.js" in powered),
    ]
    for name, hit in checks:
        if hit:
            return name
    return "unknown"


def _head_or_get(url: str) -> int:
    """Status code for a link. Some servers refuse HEAD, so fall back to GET."""
    try:
        r = requests.head(url, timeout=LINK_TIMEOUT, allow_redirects=True, headers={"User-Agent": UA})
        if r.status_code in (403, 405, 501):
            r = requests.get(
                url, timeout=LINK_TIMEOUT, allow_redirects=True, headers={"User-Agent": UA}, stream=True
            )
        return r.status_code
    except requests.RequestException:
        return 0


def _pagespeed(url: str) -> int | None:
    """Google's own Lighthouse performance score, if a key is configured."""
    if not config.pagespeed_live():
        return None
    try:
        r = requests.get(
            "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
            params={"url": url, "strategy": "mobile", "key": config.PAGESPEED_API_KEY},
            timeout=60,
        )
        r.raise_for_status()
        score = r.json()["lighthouseResult"]["categories"]["performance"]["score"]
        return int(round(score * 100))
    except Exception:
        return None


# ── the audit ────────────────────────────────────────────────


def audit_site(url: str, check_links: bool = True) -> dict:
    """Fetch a website and measure it. Returns the audit as a plain dict."""
    a = Audit(url=normalize_url(url))
    if not a.url:
        a.error = "No URL given."
        return a.to_dict()

    session = requests.Session()
    session.headers["User-Agent"] = UA

    started = time.perf_counter()
    try:
        resp = session.get(a.url, timeout=TIMEOUT, allow_redirects=True)
    except requests.RequestException as exc:
        a.error = f"{type(exc).__name__}: {exc}"
        a.findings.append(
            Finding("critical", "unreachable", "The site did not respond at all.", a.error)
        )
        a.score = 0
        return a.to_dict()

    a.load_ms = int((time.perf_counter() - started) * 1000)
    a.ttfb_ms = int(resp.elapsed.total_seconds() * 1000)
    a.reachable = True
    a.status_code = resp.status_code
    a.final_url = resp.url
    a.page_bytes = len(resp.content)
    a.https = resp.url.lower().startswith("https://")

    html = resp.text
    parsed = urlparse(a.final_url)
    host = parsed.hostname or ""

    # ── what's on the page ──
    a.title = _text_between(html, r"<title[^>]*>(.*?)</title>")
    a.meta_description = _text_between(
        html, r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']'
    )
    a.h1_count = len(re.findall(r"<h1\b", html, re.I))
    img_tags = re.findall(r"<img\b[^>]*>", html, re.I)
    a.images_total = len(img_tags)
    a.images_missing_alt = sum(
        1 for tag in img_tags if not re.search(r'\balt\s*=\s*["\'][^"\']+["\']', tag, re.I)
    )
    a.has_viewport = bool(re.search(r'<meta[^>]+name=["\']viewport["\']', html, re.I))
    a.has_og_image = bool(re.search(r'property=["\']og:image["\']', html, re.I))
    a.has_favicon = bool(re.search(r'rel=["\'][^"\']*icon[^"\']*["\']', html, re.I))
    a.has_form = bool(re.search(r"<form\b", html, re.I))
    a.has_phone_link = bool(re.search(r'href=["\']tel:', html, re.I))
    a.has_email_link = bool(re.search(r'href=["\']mailto:', html, re.I))
    a.has_analytics = bool(
        re.search(r"googletagmanager|google-analytics|gtag\(|plausible|fathom|posthog", html, re.I)
    )
    a.render_blocking_scripts = len(
        [t for t in re.findall(r"<script\b[^>]*>", html, re.I) if not re.search(r"\b(async|defer|type=[\"']module)", t, re.I) and "src=" in t.lower()]
    )
    a.platform = _detect_platform(html, resp.headers)

    if a.https and host:
        a.ssl_days_left = _ssl_days_left(host)

    # ── the crawlable extras ──
    root = f"{parsed.scheme}://{parsed.netloc}"
    for path, attr in (("/robots.txt", "robots_txt"), ("/sitemap.xml", "sitemap_xml")):
        try:
            r = session.get(root + path, timeout=LINK_TIMEOUT)
            setattr(a, attr, r.status_code == 200 and len(r.content) > 0)
        except requests.RequestException:
            setattr(a, attr, False)

    # ── broken internal links ──
    if check_links:
        seen: list[str] = []
        for href in re.findall(r'<a\b[^>]+href=["\']([^"\']+)["\']', html, re.I):
            if href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            link = urljoin(a.final_url, href)
            if urlparse(link).netloc != parsed.netloc:
                continue
            if link not in seen:
                seen.append(link)
            if len(seen) >= MAX_LINKS_CHECKED:
                break
        for link in seen:
            code = _head_or_get(link)
            a.links_checked += 1
            if code == 0 or code >= 400:
                a.broken_links.append(f"{link} → {code or 'no response'}")

    a.pagespeed_score = _pagespeed(a.final_url)

    _grade(a)
    return a.to_dict()


def _grade(a: Audit) -> None:
    """Turn measurements into findings, then findings into a 0-100 score."""
    add = a.findings.append

    if a.status_code >= 400:
        add(Finding("critical", "http_error", f"The homepage returns HTTP {a.status_code}.", a.final_url))

    if not a.https:
        add(Finding("critical", "no_https", "The site is not served over HTTPS.", a.final_url))
    elif a.ssl_days_left is not None and a.ssl_days_left < 0:
        add(Finding("critical", "ssl_expired", "The SSL certificate has expired.", f"{a.ssl_days_left} days"))
    elif a.ssl_days_left is not None and a.ssl_days_left < 21:
        add(Finding("warning", "ssl_expiring", f"The SSL certificate expires in {a.ssl_days_left} days.", ""))

    if a.load_ms > 4000:
        add(Finding("critical", "slow", f"The homepage took {a.load_ms/1000:.1f}s to load.", f"TTFB {a.ttfb_ms}ms"))
    elif a.load_ms > 2500:
        add(Finding("warning", "sluggish", f"The homepage took {a.load_ms/1000:.1f}s to load.", f"TTFB {a.ttfb_ms}ms"))

    if a.page_bytes > 3_000_000:
        add(Finding("warning", "heavy", f"The homepage HTML alone is {a.page_bytes/1_000_000:.1f}MB.", ""))

    if not a.has_viewport:
        add(Finding("critical", "not_mobile", "No mobile viewport tag — the site is not responsive.", ""))

    if not a.has_form and not a.has_email_link and not a.has_phone_link:
        add(Finding("critical", "no_contact", "No contact form, phone link, or email link on the homepage.", ""))
    elif not a.has_form:
        add(Finding("warning", "no_form", "No contact form on the homepage — visitors have to work to reach them.", ""))

    if a.broken_links:
        add(Finding("critical", "broken_links", f"{len(a.broken_links)} broken link(s) on the homepage.", "; ".join(a.broken_links[:3])))

    if not a.title:
        add(Finding("critical", "no_title", "The homepage has no <title> tag.", ""))
    elif len(a.title) > 65:
        add(Finding("note", "long_title", f"The title tag is {len(a.title)} characters — Google truncates it.", a.title))

    if not a.meta_description:
        add(Finding("warning", "no_meta_description", "No meta description — Google writes their search snippet for them.", ""))

    if a.h1_count == 0:
        add(Finding("warning", "no_h1", "No H1 heading on the homepage.", ""))
    elif a.h1_count > 1:
        add(Finding("note", "many_h1", f"{a.h1_count} H1 headings — should be one.", ""))

    if a.images_total and a.images_missing_alt:
        share = a.images_missing_alt / a.images_total
        sev = "warning" if share > 0.5 else "note"
        add(Finding(sev, "missing_alt", f"{a.images_missing_alt} of {a.images_total} images have no alt text.", "accessibility + image SEO"))

    if a.render_blocking_scripts >= 5:
        add(Finding("warning", "render_blocking", f"{a.render_blocking_scripts} render-blocking scripts in the HTML.", ""))

    if not a.has_analytics:
        add(Finding("warning", "no_analytics", "No analytics installed — they can't see their own traffic.", ""))

    if not a.has_og_image:
        add(Finding("note", "no_og_image", "No Open Graph image — links to the site preview blank when shared.", ""))

    if not a.robots_txt:
        add(Finding("note", "no_robots", "No robots.txt.", ""))
    if not a.sitemap_xml:
        add(Finding("note", "no_sitemap", "No sitemap.xml — slower and less complete indexing.", ""))

    if a.pagespeed_score is not None and a.pagespeed_score < 50:
        add(Finding("critical", "pagespeed", f"Google PageSpeed (mobile) scores the site {a.pagespeed_score}/100.", ""))

    penalty = sum(WEIGHTS.get(f.severity, 0) for f in a.findings)
    a.score = max(0, min(100, 100 - penalty))


def format_report(audit: dict) -> str:
    """Human-readable audit, for the terminal and the demo."""
    lines = [f"🔍 {audit['url']}"]
    if not audit["reachable"]:
        lines.append(f"   ✗ unreachable — {audit['error']}")
        return "\n".join(lines)

    lines += [
        f"   score            : {audit['score']}/100",
        f"   load             : {audit['load_ms']/1000:.2f}s  (TTFB {audit['ttfb_ms']}ms)",
        f"   page weight      : {audit['page_bytes']/1000:.0f} KB",
        f"   platform         : {audit['platform']}",
        f"   https            : {audit['https']}"
        + (f"  (cert expires in {audit['ssl_days_left']}d)" if audit["ssl_days_left"] is not None else ""),
        f"   mobile viewport  : {audit['has_viewport']}",
        f"   contact form     : {audit['has_form']}",
        f"   analytics        : {audit['has_analytics']}",
        f"   links checked    : {audit['links_checked']}  broken: {len(audit['broken_links'])}",
    ]
    if audit["pagespeed_score"] is not None:
        lines.append(f"   pagespeed mobile : {audit['pagespeed_score']}/100")
    lines.append("   findings:")
    icons = {"critical": "🔴", "warning": "🟡", "note": "⚪"}
    for f in audit["findings"]:
        lines.append(f"     {icons.get(f['severity'], '·')} {f['message']}")
    return "\n".join(lines)
