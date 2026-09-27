"""Shared helpers for the content agents (underscore module: skipped by the registry).

Everything here is deterministic stdlib text plumbing the content agents share:
markdown stripping, link/heading/hashtag extraction, X's weighted character
count, platform limits, and the word lists (clichés, hedges, AI-tells) that
several editors lint against.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from ...core import ToolError
from ...lib import text

MAX_CHARS = 200_000

URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>()\[\]\"'`]{1,2000}", re.I)
MD_LINK_RE = re.compile(r"(?<!!)\[([^\]]{0,300})\]\(([^)\s]{1,2000})(?:\s+\"[^\"]{0,300}\")?\)")
MD_IMAGE_RE = re.compile(r"!\[([^\]]{0,300})\]\(([^)\s]{1,2000})(?:\s+\"[^\"]{0,300}\")?\)")
HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", re.M)
HASHTAG_RE = re.compile(r"(?<![\w&/])#([A-Za-z][\w]{0,99})")
MENTION_RE = re.compile(r"(?<![\w.])@([A-Za-z0-9_][\w.-]{0,49})")
STAGE_DIR_RE = re.compile(r"\[[^\]\n]{0,200}\]|\([A-Z][^)\n]{0,200}\)")

_EMOJI_RANGES = (
    (0x1F1E6, 0x1F1FF),
    (0x1F300, 0x1FAFF),
    (0x2600, 0x27BF),
    (0x2B00, 0x2BFF),
    (0x1F000, 0x1F2FF),
)
_EMOJI_MODIFIERS = {0xFE0F, 0xFE0E, 0x200D, 0x20E3} | set(range(0x1F3FB, 0x1F400))


def guard(value: str, what: str = "Text", limit: int = MAX_CHARS) -> str:
    """Reject empty or oversized text with a clean ToolError."""
    if not isinstance(value, str) or not value.strip():
        raise ToolError(f"{what} is empty.")
    if len(value) > limit:
        raise ToolError(f"{what} too long ({len(value):,} chars; max {limit:,}). Split it up.")
    return value


def is_emoji(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _EMOJI_RANGES)


def _is_regional(cp: int) -> bool:
    return 0x1F1E6 <= cp <= 0x1F1FF


def _is_emoji_trailer(cp: int) -> bool:
    """Code points that attach to the preceding emoji: VS15/16, skin tones, keycap, tag characters."""
    return cp in (0xFE0F, 0xFE0E, 0x20E3) or 0x1F3FB <= cp <= 0x1F3FF or 0xE0020 <= cp <= 0xE007F


def _graphemes(s: str):
    """Yield (cluster, is_emoji) for s, grouping emoji sequences the way X and phones render them:
    ZWJ sequences, skin tones, flags (regional-indicator pairs), keycaps and tag sequences are ONE emoji."""
    i, n = 0, len(s)
    while i < n:
        cp = ord(s[i])
        if _is_regional(cp):
            j = i + 2 if i + 1 < n and _is_regional(ord(s[i + 1])) else i + 1
            yield s[i:j], True
            i = j
            continue
        if s[i] in "0123456789#*":  # keycap: 1⃣ / 1️⃣
            j = i + 1
            if j < n and ord(s[j]) == 0xFE0F:
                j += 1
            if j < n and ord(s[j]) == 0x20E3:
                yield s[i:j + 1], True
                i = j + 1
                continue
        emoji = is_emoji(s[i]) or (i + 1 < n and ord(s[i + 1]) == 0xFE0F and cp > 0x7F)
        j = i + 1
        if emoji:
            while j < n:
                c2 = ord(s[j])
                if _is_emoji_trailer(c2):
                    j += 1
                elif c2 == 0x200D and j + 1 < n:
                    j += 2
                else:
                    break
        yield s[i:j], emoji
        i = j


def count_emoji(s: str) -> int:
    """Emoji as a reader sees them: 👨‍👩‍👧‍👦, 🇺🇸 and 👍🏽 are one each."""
    return sum(1 for _, e in _graphemes(s) if e)


# Bare domains X turns into t.co links (twitter-text extractUrlsWithoutProtocol): labels of
# [-a-z0-9] (plus Latin accents) ending in a known TLD, not glued to @ $ # or a preceding [-_./].
_BARE_DOMAIN_RE = re.compile(
    r"(?<![A-Za-z0-9@$#＠＃_./-])((?:[a-z0-9À-ÖØ-öø-ÿ-]+\.)+([a-z][a-z0-9-]*))(?![a-z0-9@+-])((?:/[^\s<>\"'`]*)?)",
    re.I,
)
_URL_TAIL = ".,;:!?'\"’”)]}…"


def _trim_url(u: str) -> str:
    """X doesn't count trailing sentence punctuation as part of a link ("see x.com/a." → the '.' is text)."""
    while u and u[-1] in _URL_TAIL:
        if u[-1] == ")" and u.count("(") >= u.count(")"):
            break
        u = u[:-1]
    return u


def _valid_host(host: str) -> bool:
    labels = host.rstrip(".").split(".")
    for lab in labels:
        if not lab or lab.startswith("-") or lab.endswith("-"):
            return False
        try:
            if len(lab.encode("idna")) > 63:
                return False
        except UnicodeError:
            return False
    return True


@lru_cache(maxsize=1)
def _tlds() -> frozenset:
    from ._tlds import CCTLDS, GTLDS

    return GTLDS | CCTLDS


def x_urls(s: str) -> list[tuple[int, int, str]]:
    """Links X would wrap in t.co (each weighs 23): http(s)/www URLs and bare domains with a real TLD."""
    found: list[tuple[int, int, str]] = []
    for m in URL_RE.finditer(s):
        u = _trim_url(m.group(0))
        host = re.sub(r"^(?:https?://)", "", u, flags=re.I).split("/")[0].split("?")[0].split("#")[0].split(":")[0]
        if u and _valid_host(host):
            found.append((m.start(), m.start() + len(u), u))
    tlds = _tlds()
    for m in _BARE_DOMAIN_RE.finditer(s):
        if any(a <= m.start() < b for a, b, _ in found):
            continue
        if m.group(2).lower() not in tlds or not _valid_host(m.group(1)):
            continue
        u = _trim_url(m.group(0))
        found.append((m.start(), m.start() + len(u), u))
    found.sort()
    return found


def x_length(s: str) -> int:
    """X's weighted length (twitter-text v3): text is NFC-normalised; every link (with or without
    http, e.g. example.com) = 23; every emoji sequence (ZWJ family, flag, skin tone, keycap) = 2;
    code points in U+0000-10FF, U+2000-200D, U+2010-201F, U+2032-2037 = 1; everything else = 2."""
    s = unicodedata.normalize("NFC", s)
    total, last, parts = 0, 0, []
    for a, b, _ in x_urls(s):
        parts.append(s[last:a])
        total += 23
        last = b
    parts.append(s[last:])
    for chunk, emoji in _graphemes("".join(parts)):
        if emoji:
            total += 2
            continue
        for ch in chunk:
            cp = ord(ch)
            total += 1 if (cp <= 4351 or 8192 <= cp <= 8205 or 8208 <= cp <= 8223 or 8242 <= cp <= 8247) else 2
    return total


def strip_markdown(md: str) -> str:
    """Plain prose from markdown: drops code, marks, tables; keeps link/image text."""
    s = re.sub(r"```.{0,100000}?```", " ", md, flags=re.S)
    s = re.sub(r"`([^`\n]{0,500})`", r"\1", s)
    s = MD_IMAGE_RE.sub(r"\1", s)
    s = MD_LINK_RE.sub(r"\1", s)
    s = re.sub(r"<[^>\n]{1,200}>", "", s)
    s = re.sub(r"^[ \t]{0,3}#{1,6}[ \t]+", "", s, flags=re.M)
    s = re.sub(r"^[ \t]{0,3}>[ \t]?", "", s, flags=re.M)
    s = re.sub(r"^[ \t]*(?:[-*+•→]|\d{1,3}[.)])[ \t]+", "", s, flags=re.M)
    s = re.sub(r"^[ \t]*(?:[-*_][ \t]*){3,}$", "", s, flags=re.M)
    s = re.sub(r"(\*\*|__)(.{1,500}?)\1", r"\2", s, flags=re.S)
    s = re.sub(r"(?<!\w)([*_])(?!\s)(.{1,300}?)(?<!\s)\1(?!\w)", r"\2", s)
    s = re.sub(r"^[ \t]*\|?(?:[ \t]*:?-{2,}:?[ \t]*\|)+[ \t]*:?-*:?[ \t]*\|?[ \t]*$", "", s, flags=re.M)
    s = s.replace("|", " ")
    return s


def paragraphs(s: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", s.strip()) if p.strip()]


def sections(md: str) -> list[dict]:
    """Split markdown into heading-delimited sections. The preamble (before any heading) has level 0."""
    out: list[dict] = []
    current = {"level": 0, "title": "(intro)", "line": 1, "lines": []}
    in_code = False
    for n, line in enumerate(md.splitlines(), 1):
        if line.strip().startswith("```"):
            in_code = not in_code
        m = None if in_code else HEADING_RE.match(line)
        if m:
            out.append(current)
            current = {"level": len(m.group(1)), "title": m.group(2).strip(), "line": n, "lines": []}
        else:
            current["lines"].append(line)
    out.append(current)
    result = []
    for sec in out:
        body = "\n".join(sec["lines"]).strip()
        if sec["level"] == 0 and not body:
            continue
        plain = strip_markdown(body)
        result.append({
            "level": sec["level"],
            "title": sec["title"],
            "line": sec["line"],
            "body": body,
            "words": len(text.words(plain)),
        })
    return result


def links(md: str) -> list[dict]:
    """Every link in markdown or plain text: anchor, url, and whether it was a naked URL."""
    found: list[dict] = []
    spans: list[tuple[int, int]] = []
    for m in MD_LINK_RE.finditer(md):
        found.append({"anchor": m.group(1).strip(), "url": m.group(2).strip(), "naked": False, "pos": m.start()})
        spans.append(m.span())
    for m in MD_IMAGE_RE.finditer(md):
        spans.append(m.span())
    for m in URL_RE.finditer(md):
        if any(a <= m.start() < b for a, b in spans):
            continue
        url = m.group(0).rstrip(".,;:!?")
        found.append({"anchor": "", "url": url, "naked": True, "pos": m.start()})
        spans.append((m.start(), m.start() + len(url)))
    # bare domains (acme.com/pricing) that LinkedIn, X and most email clients auto-link
    for m in _BARE_DOMAIN_RE.finditer(md):
        if any(a <= m.start() < b for a, b in spans) or m.group(2).lower() not in WEB_TLDS:
            continue
        found.append({"anchor": "", "url": _trim_url(m.group(0)), "naked": True, "pos": m.start()})
    found.sort(key=lambda d: d["pos"])
    return found


WEB_TLDS = frozenset(
    "com org net edu gov io co ai dev app me tv fm us uk ca de fr es it nl eu au in jp ly gg so to "
    "xyz info biz blog news site online store shop tech page link club design studio email"
    .split()
)


def domain_of(url: str) -> str:
    m = re.match(r"(?:https?://)?(?:www\.)?([^/?#:]+)", url, re.I)
    return m.group(1).lower() if m else ""


def mmss(seconds: float) -> str:
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def spoken_words(script: str) -> list[str]:
    """Words an audience would hear: stage directions in [brackets] / (Capitalised parens) removed."""
    return text.words(STAGE_DIR_RE.sub(" ", strip_markdown(script)))


def proper_nouns(s: str) -> list[str]:
    """Capitalised words that are not sentence/line-initial and not ALL CAPS — names, products, places."""
    out: list[str] = []
    for chunk in re.split(r"[.!?:\n]+", s):
        ws = text.words(chunk)
        for w in ws[1:]:
            if w[:1].isupper() and not w.isupper() and w.lower() not in text.STOPWORDS and w.lower() != "i":
                out.append(w)
    return out


def pct(part: float, whole: float, nd: int = 1) -> float:
    return round(100.0 * part / whole, nd) if whole else 0.0


# ── word lists ────────────────────────────────────────────────────────────────

CLICHES = [
    "at the end of the day", "think outside the box", "low-hanging fruit", "move the needle",
    "game changer", "game-changer", "paradigm shift", "best of breed", "cutting edge", "cutting-edge",
    "state of the art", "state-of-the-art", "in today's fast-paced world", "in this day and age",
    "it goes without saying", "needless to say", "last but not least", "the fact of the matter",
    "when all is said and done", "tip of the iceberg", "leave no stone unturned", "level playing field",
    "win-win", "synergy", "circle back", "touch base", "hit the ground running", "push the envelope",
    "take it to the next level", "perfect storm", "the elephant in the room", "only time will tell",
    "few and far between", "in a nutshell", "the bottom line", "world-class", "best-in-class",
    "next-generation", "revolutionary", "disruptive", "holistic", "no-brainer", "one-stop shop",
    "secret sauce", "value-add", "at scale", "boil the ocean", "drink the kool-aid", "table stakes",
    "sea change", "quantum leap", "silver bullet", "north star", "double down", "unpack", "deep dive",
    "on the same page", "reinvent the wheel", "moving forward", "going forward", "bandwidth",
    "ducks in a row", "peel back the onion", "trusted partner", "thought leader", "in the weeds",
]

AI_TELLS = [
    "delve", "delves", "delving", "tapestry", "testament to", "in today's fast-paced", "ever-evolving",
    "landscape", "navigate the complexities", "navigating the complexities", "it's important to note",
    "it is important to note", "it's worth noting", "it is worth noting", "in conclusion",
    "unlock the power", "unlock", "elevate", "seamless", "seamlessly", "robust", "leverage", "leveraging",
    "embark", "journey", "realm", "beacon", "vibrant", "bustling", "crucial", "pivotal", "paramount",
    "game-changing", "revolutionize", "cutting-edge", "foster", "harness", "underscore", "underscores",
    "in the realm of", "a myriad of", "myriad", "plethora", "furthermore", "moreover", "additionally",
    "comprehensive", "holistic", "dive into", "let's dive in", "look no further", "whether you're",
    "in an era", "at its core", "not only", "the world of", "treasure trove", "ultimately",
]

HEDGES = [
    "very", "really", "quite", "rather", "somewhat", "just", "actually", "basically", "literally",
    "kind of", "sort of", "a bit", "a little", "pretty much", "truly", "extremely", "incredibly",
    "absolutely", "essentially", "simply", "definitely", "certainly", "totally", "highly", "fairly",
    "perhaps", "maybe", "arguably", "seemingly", "in my opinion", "i think", "i feel", "i believe",
    "it seems", "virtually", "practically", "generally", "usually", "typically", "in general",
    "to some extent", "more or less", "for the most part", "in a sense", "possibly", "probably",
]

SPAM_WORDS = [
    "free", "guarantee", "guaranteed", "act now", "$$$", "100%", "winner", "urgent", "click here",
    "buy now", "limited time", "no obligation", "risk-free", "risk free", "cash", "earn money",
    "make money", "million", "no cost", "order now", "prize", "congratulations", "double your",
    "exclusive deal", "lowest price", "once in a lifetime", "unbelievable", "cheap", "discount",
    "don't miss", "dont miss", "last chance", "apply now", "credit", "loan", "miracle", "amazing",
]

GENERIC_ANCHORS = {"here", "click here", "this", "link", "this link", "read more", "more", "learn more", "website", "page", "url"}

WEAK_PRAISE = [
    "great", "amazing", "awesome", "fantastic", "wonderful", "excellent", "incredible", "love it",
    "easy to use", "user-friendly", "intuitive", "seamless", "game changer", "game-changer",
    "best in class", "best-in-class", "top notch", "top-notch", "highly recommend", "very happy",
    "really helpful", "super helpful", "life saver", "lifesaver", "no-brainer", "must-have",
]

VAGUE_QUANTIFIERS = [
    "significantly", "dramatically", "substantially", "massively", "hugely", "vastly", "a lot",
    "many", "numerous", "several", "countless", "a number of", "a ton of", "tons of", "huge",
    "massive", "enormous", "considerable", "considerably", "greatly", "immensely", "exponentially",
    "a great deal", "plenty of", "lots of", "big", "major", "notable", "noticeable", "improved",
]


@lru_cache(maxsize=64)
def phrase_pattern(phrases: tuple[str, ...]) -> re.Pattern:
    """One compiled alternation for a phrase list (longest first), whole-word, case-insensitive."""
    alts = sorted({p.lower() for p in phrases if p}, key=len, reverse=True)
    return re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(a) for a in alts) + r")(?![\w-])", re.I)


def find_phrases(s: str, phrases: list[str]) -> list[dict]:
    """Case-insensitive whole-word matches of each phrase, with positions and counts (single pass)."""
    if not phrases:
        return []
    counts: dict[str, int] = {}
    first: dict[str, int] = {}
    for m in phrase_pattern(tuple(phrases)).finditer(s):
        p = m.group(0).lower()
        counts[p] = counts.get(p, 0) + 1
        first.setdefault(p, m.start())
    hits = [{"phrase": p, "count": n, "first_at": first[p]} for p, n in counts.items()]
    hits.sort(key=lambda h: (-h["count"], h["first_at"]))
    return hits


# Hedge words that are not hedges in these fixed phrases ("a habit rather than a tool").
HEDGE_EXCEPTIONS = {"rather": re.compile(r"\s+than\b", re.I), "just": re.compile(r"\s+(?:cause|deserts)\b", re.I)}


def find_hedges(s: str) -> list[dict]:
    """find_phrases for HEDGES, minus fixed phrases where the word isn't hedging ("rather than")."""
    hits = find_phrases(s, HEDGES)
    out = []
    for h in hits:
        exc = HEDGE_EXCEPTIONS.get(h["phrase"])
        if not exc:
            out.append(h)
            continue
        n, first = 0, None
        for m in phrase_pattern((h["phrase"],)).finditer(s):
            if not exc.match(s, m.end()):
                n += 1
                first = m.start() if first is None else first
        if n:
            out.append({"phrase": h["phrase"], "count": n, "first_at": first})
    return out


def context(s: str, pos: int, width: int = 40) -> str:
    start, end = max(0, pos - width), min(len(s), pos + width)
    snippet = s[start:end].replace("\n", " ")
    return ("…" if start else "") + snippet + ("…" if end < len(s) else "")


# ── platform reference data (used by repurposer, thread builder, ghostwriter) ──

PLATFORMS: dict[str, dict] = {
    "x": {"name": "X (Twitter) post", "max_chars": 280, "count": "weighted (URL=23, emoji/CJK=2)", "sweet_spot": "70-200 chars", "hashtags": "0-1", "links": "in a reply or last post of a thread", "media": "image 16:9 or 4:5; video ≤ 2:20"},
    "x_premium": {"name": "X long post (Premium)", "max_chars": 25000, "count": "weighted", "sweet_spot": "≤ 1,000 chars — only the first ~280 show before 'Show more'", "hashtags": "0-1", "links": "anywhere", "media": "same as X"},
    "linkedin": {"name": "LinkedIn post", "max_chars": 3000, "count": "plain", "sweet_spot": "900-1,500 chars; hook in first ~210 chars (fold)", "hashtags": "3-5, at the end", "links": "in first comment or at the end", "media": "carousel PDF, single image 1:1 or 4:5"},
    "linkedin_article": {"name": "LinkedIn article", "max_chars": 125000, "count": "plain", "sweet_spot": "1,000-2,000 words", "hashtags": "n/a", "links": "anywhere", "media": "cover 1200x644"},
    "threads": {"name": "Threads post", "max_chars": 500, "count": "plain", "sweet_spot": "100-300 chars", "hashtags": "1 topic tag", "links": "allowed inline", "media": "up to 20 images/videos"},
    "bluesky": {"name": "Bluesky post", "max_chars": 300, "count": "graphemes", "sweet_spot": "100-250 chars", "hashtags": "0-2", "links": "inline (add link card)", "media": "4 images; video ≤ 60s"},
    "mastodon": {"name": "Mastodon post", "max_chars": 500, "count": "plain (URL=23)", "sweet_spot": "100-400 chars", "hashtags": "2-4 (CamelCase for screen readers)", "links": "inline", "media": "4 attachments"},
    "instagram": {"name": "Instagram caption", "max_chars": 2200, "count": "plain", "sweet_spot": "first 125 chars show before '…more'; 150-300 chars total", "hashtags": "3-5 (max 30)", "links": "not clickable — 'link in bio'", "media": "4:5 image, 1080x1350; Reels 9:16"},
    "facebook": {"name": "Facebook post", "max_chars": 63206, "count": "plain", "sweet_spot": "40-80 words; fold at ~480 chars", "hashtags": "0-2", "links": "inline (link preview)", "media": "1200x630 link image"},
    "tiktok": {"name": "TikTok caption", "max_chars": 4000, "count": "plain", "sweet_spot": "≤ 150 chars; keywords for search", "hashtags": "3-5", "links": "not clickable", "media": "9:16 video 1080x1920"},
    "youtube_title": {"name": "YouTube title", "max_chars": 100, "count": "plain", "sweet_spot": "≤ 60-70 chars (truncates in sidebar)", "hashtags": "n/a", "links": "n/a", "media": "thumbnail 1280x720"},
    "youtube_description": {"name": "YouTube description", "max_chars": 5000, "count": "plain", "sweet_spot": "first ~150 chars show above 'Show more'; chapters from 0:00", "hashtags": "≤ 3 shown above title", "links": "inline", "media": "n/a"},
    "youtube_community": {"name": "YouTube community post", "max_chars": 4000, "count": "plain", "sweet_spot": "≤ 300 chars", "hashtags": "0-2", "links": "inline", "media": "image, poll, quiz"},
    "pinterest": {"name": "Pinterest pin", "max_chars": 500, "count": "plain", "sweet_spot": "title ≤ 100 chars (40 visible); description 100-300", "hashtags": "n/a (keywords instead)", "links": "destination link field", "media": "2:3 image 1000x1500"},
    "reddit": {"name": "Reddit post", "max_chars": 40000, "count": "plain", "sweet_spot": "title ≤ 300 chars; body 150-400 words; no self-promo", "hashtags": "none", "links": "inline (subreddit rules apply)", "media": "per subreddit"},
    "email_subject": {"name": "Email subject line", "max_chars": 78, "count": "plain", "sweet_spot": "30-50 chars (mobile shows ~35-40)", "hashtags": "none", "links": "none", "media": "n/a"},
    "newsletter": {"name": "Newsletter issue", "max_chars": 102000, "count": "plain (Gmail clips ~102 KB HTML)", "sweet_spot": "600-1,200 words (3-5 min read)", "hashtags": "none", "links": "5-15 with descriptive anchors", "media": "≤ 600px wide images"},
    "blog": {"name": "Blog post", "max_chars": 0, "count": "n/a", "sweet_spot": "1,200-2,000 words for search intent; 600-900 for opinion", "hashtags": "none", "links": "2-5 internal, 2-4 external per 1,000 words", "media": "hero + one image per H2"},
    "short_video_script": {"name": "Short-form video script (Reels/Shorts/TikTok)", "max_chars": 0, "count": "spoken words", "sweet_spot": "≤ 60s ≈ 130-160 words; hook in first 1-2s", "hashtags": "3-5 in caption", "links": "n/a", "media": "9:16"},
    "podcast_notes": {"name": "Podcast show notes", "max_chars": 4000, "count": "plain (Apple)", "sweet_spot": "150-300 words + timestamps", "hashtags": "none", "links": "inline", "media": "3000x3000 art"},
}

PLATFORM_ALIASES = {
    "twitter": "x", "x.com": "x", "tweet": "x", "li": "linkedin", "ig": "instagram", "insta": "instagram",
    "fb": "facebook", "yt": "youtube_title", "youtube": "youtube_description", "shorts": "short_video_script",
    "reels": "short_video_script", "tiktok_script": "short_video_script", "email": "email_subject",
    "subject": "email_subject", "medium": "blog", "substack": "newsletter", "beehiiv": "newsletter",
}


def platform_key(name: str) -> str:
    k = (name or "").strip().lower().replace(" ", "_").replace("-", "_")
    k = PLATFORM_ALIASES.get(k, k)
    if k not in PLATFORMS:
        raise ToolError(f"Unknown platform {name!r}. Known: {', '.join(sorted(PLATFORMS))}.")
    return k
