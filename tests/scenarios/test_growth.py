"""Growth category scenario evals (evals/growth.md) — replayable end-to-end checks.

Each test replays one realistic customer scenario through the agent's tools, exactly as the
customer's AI would call them, and asserts on values that were verified independently:
planted defects (recall), untouched correct elements (precision), and numbers recomputed with
textbook formulas / font metrics written here without importing any hundred code.
"""

import datetime as dt
import math
import os
import struct

import pytest

from hundred import registry


def run(slug, tool, **kwargs):
    return registry.get(slug).get_tool(tool).call(kwargs)


# ── independent references (no hundred imports) ──────────────────────────────

FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"  # metric-compatible with Arial


def liberation_width(s: str, px: float) -> float:
    """Advance width from the TTF's hmtx/cmap tables, parsed with struct only."""
    data = open(FONT, "rb").read()
    tables = {}
    for i in range(struct.unpack(">H", data[4:6])[0]):
        tag, _, off, ln = struct.unpack(">4sIII", data[12 + 16 * i : 28 + 16 * i])
        tables[tag.decode()] = off
    upem = struct.unpack(">H", data[tables["head"] + 18 : tables["head"] + 20])[0]
    nhm = struct.unpack(">H", data[tables["hhea"] + 34 : tables["hhea"] + 36])[0]
    adv = [struct.unpack(">H", data[tables["hmtx"] + 4 * i : tables["hmtx"] + 4 * i + 2])[0] for i in range(nhm)]
    c = tables["cmap"]
    sub = None
    for i in range(struct.unpack(">H", data[c + 2 : c + 4])[0]):
        pid, eid, off = struct.unpack(">HHI", data[c + 4 + 8 * i : c + 12 + 8 * i])
        if (pid, eid) == (3, 1):
            sub = c + off
    seg2 = struct.unpack(">H", data[sub + 6 : sub + 8])[0]
    seg = seg2 // 2
    ends = struct.unpack(f">{seg}H", data[sub + 14 : sub + 14 + seg2])
    starts = struct.unpack(f">{seg}H", data[sub + 16 + seg2 : sub + 16 + 2 * seg2])
    deltas = struct.unpack(f">{seg}h", data[sub + 16 + 2 * seg2 : sub + 16 + 3 * seg2])
    rpos = sub + 16 + 3 * seg2
    roffs = struct.unpack(f">{seg}H", data[rpos : rpos + seg2])

    def gid(cp):
        for i in range(seg):
            if starts[i] <= cp <= ends[i]:
                if roffs[i] == 0:
                    return (cp + deltas[i]) & 0xFFFF
                p = rpos + 2 * i + roffs[i] + 2 * (cp - starts[i])
                g = struct.unpack(">H", data[p : p + 2])[0]
                return (g + deltas[i]) & 0xFFFF if g else 0
        return 0

    return sum(adv[min(gid(ord(ch)), nhm - 1)] for ch in s) * px / upem


def phi(x):
    return 0.5 * math.erfc(-x / math.sqrt(2))


def z_quantile(p):
    lo, hi = -10.0, 10.0
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if phi(mid) < p else (lo, mid)
    return (lo + hi) / 2


def textbook_n_per_arm(p1, rel, alpha=0.05, power=0.8, arms=2):
    p2 = p1 * (1 + rel)
    a = alpha / (arms - 1)
    pb = (p1 + p2) / 2
    num = z_quantile(1 - a / 2) * math.sqrt(2 * pb * (1 - pb)) + z_quantile(power) * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    return math.ceil(num**2 / (p2 - p1) ** 2)


def shingle_set(text, n=3):
    import re

    ws = re.findall(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)*", text.lower())
    return {tuple(ws[i : i + n]) for i in range(len(ws) - n + 1)}


# ── scenario fixtures ─────────────────────────────────────────────────────────

PRODUCT_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ergo Pro Mesh Ergonomic Office Chair with Adjustable Lumbar Support, 4D Armrests and Headrest | SitWell Furniture Co.</title>
<meta name="description" content="Shop the Ergo Pro Mesh ergonomic office chair from SitWell. Adjustable lumbar support, 4D armrests, breathable mesh back, synchronized tilt, 12-year warranty, free shipping and 100-night trial on every order.">
<meta property="og:title" content="Ergo Pro Mesh Ergonomic Office Chair">
<meta property="og:description" content="Adjustable lumbar, 4D arms, 12-year warranty.">
<meta property="og:image" content="https://www.sitwell.com/img/ergo-pro-og.jpg">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Product","name":"Ergo Pro Mesh Ergonomic Office Chair","offers":{"@type":"Offer","price":"449.00","priceCurrency":"USD","availability":"https://schema.org/InStock"}}</script>
<script src="/js/theme.js"></script>
</head>
<body>
<header><a href="/"><img src="/img/logo.svg" alt="SitWell"></a>
<nav><a href="/chairs">Office chairs</a> <a href="/desks">Standing desks</a> <a href="/accessories">Accessories</a></nav></header>
<main>
<h1>Ergo Pro Mesh Ergonomic Office Chair</h1>
<p>The Ergo Pro Mesh is an ergonomic office chair built for eight-hour days. Its adjustable lumbar support follows the curve of your lower back, the breathable mesh keeps you cool, and 4D armrests move up, down, forward and sideways so your shoulders stay relaxed while you type.</p>
<img src="/img/ergo-pro-front.jpg" width="800" height="800">
<img src="/img/ergo-pro-side.jpg" width="800" height="800">
<img src="/img/ergo-pro-lumbar.jpg" width="800" height="800">
<img src="/img/divider.png" alt="" width="800" height="4">
<img src="/img/ergo-pro-armrest.jpg" alt="Ergo Pro 4D armrest adjusted forward" width="800" height="800">
<h1>Why Our Customers Love It</h1>
<p>Over 3,400 buyers rate the Ergo Pro 4.7 out of 5. Remote workers tell us the headrest finally stopped their neck ache, and gamers love the 135-degree recline with tilt lock. Every chair ships fully assembled in the continental US, so you can sit down five minutes after the box arrives.</p>
<h2>Features</h2>
<ul><li>Adjustable lumbar support with two-way depth control</li><li>4D armrests with soft polyurethane pads</li><li>Synchronized tilt with four lock positions and tension knob</li><li>Seat depth slider for users from 5'2" to 6'4"</li><li>Class 4 gas lift and nylon base rated to 300 lb</li></ul>
<h4>Dimensions</h4>
<p>Seat height 17.5 to 21.5 inches. Seat width 20 inches. Overall height 45 to 51 inches with headrest. Weight 42 pounds. The seat depth slides three inches so shorter and taller people both get the recommended two-to-four finger gap behind the knee.</p>
<h2>Warranty and returns</h2>
<p>We back the Ergo Pro with a 12-year warranty on the frame, mechanism and gas lift, and a 2-year warranty on mesh and foam. If it is not the right chair, return it within 100 nights for a full refund; we even pick it up. Read our <a href="/warranty">warranty terms</a> or <a href="javascript:void(0)">click here</a> to chat with a specialist.</p>
<h2>Compare ergonomic chairs</h2>
<p>Not sure which chair fits you? See how the Ergo Pro stacks up against the Ergo Lite and the Executive Leather in our <a href="/chairs/compare">chair comparison chart</a>, or read the independent <a href="https://www.bifma.org/page/standards" target="_blank">BIFMA X5.1 standard</a> our chairs are tested to. Our research summary on sitting posture draws on <a href="http://www.osha.gov/etools/computer-workstations/components/chairs">OSHA workstation guidance</a>.</p>
<p>Questions about sizing? <a href="/contact">Read more</a>.</p>
</main>
<footer><a href="/about">About SitWell</a> <a href="/shipping">Shipping</a> <a href="mailto:help@sitwell.com">help@sitwell.com</a></footer>
</body>
</html>
"""

SCHEMA_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Stride Trail 3 Running Shoe | Stride</title>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Stride Trail 3","image":["https://stride.com/img/trail3-side.jpg"],
 "brand":{"@type":"Brand","name":"Stride"},"sku":"TR3-M-10",
 "offers":{"@type":"Offer","price":"$129.99","priceCurrency":"USD","availability":"In Stock","priceValidUntil":"12/31/2026","url":"https://stride.com/trail-3"},
 "aggregateRating":{"@type":"AggregateRating","ratingValue":"4.6"},
 "review":[{"@type":"Review","reviewRating":{"@type":"Rating","ratingValue":"5"},"reviewBody":"Great grip on wet rock."},
           {"@type":"Review","author":{"@type":"Person","name":"Maya R."},"reviewRating":{"@type":"Rating","ratingValue":"4"},"reviewBody":"Runs half a size small."}]}
</script>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Stride Trail 3 Running Shoe","offers":{"@type":"Offer","price":"139.99","priceCurrency":"USD","availability":"https://schema.org/InStock"}}
</script>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[
 {"@type":"ListItem","position":0,"name":"Home","item":"https://stride.com/"},
 {"@type":"ListItem","position":1,"name":"Trail","item":"https://stride.com/trail"},
 {"@type":"ListItem","position":2,"name":"Stride Trail 3"}]}
</script>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Organization","name":"Stride","url":"https://stride.com","logo":"https://stride.com/logo.png","sameAs":["https://instagram.com/stride"]}
</script>
</head><body><h1>Stride Trail 3</h1><p>$129.99 · In stock · 4.6 stars from 212 reviews</p></body></html>
"""

SNIPPET_ROWS = [
    {"url": "https://desklab.com/", "title": "DeskLab: Standing Desks Built for Small Spaces", "description": "Compact electric standing desks from 30\" wide. Free shipping, 10-year warranty and a 60-day home trial on every DeskLab desk."},
    {"url": "https://desklab.com/desks/compact-standing-desk", "title": "Compact Standing Desk 36\" – Dual Motor | DeskLab", "description": "The DeskLab Compact is a 36\" dual-motor standing desk that rises from 25\" to 50\" in 12 seconds. Ships in 2 days."},
    {"url": "https://desklab.com/desks/corner-standing-desk", "title": "Standing Desks | DeskLab", "description": "Shop DeskLab standing desks. Free shipping and 60-day returns."},
    {"url": "https://desklab.com/desks/kids-standing-desk", "title": "Standing Desks | DeskLab", "description": "Shop DeskLab standing desks. Free shipping and 60-day returns."},
    {"url": "https://desklab.com/desks/wall-mounted-desk", "title": "", "description": "Fold-down wall-mounted standing desk for studios and tiny apartments, from 24\" deep to flat in one motion."},
    {"url": "https://desklab.com/accessories/monitor-arm", "title": "Single Monitor Arm with Gas Spring for Standing Desks | DeskLab", "description": ""},
    {"url": "https://desklab.com/guides/standing-desk-height-calculator", "title": "Standing Desk Height Calculator: Find Your Ideal Desk and Monitor Height by Body Measurements | DeskLab", "description": "Enter your height to get the ideal standing and sitting desk height, keyboard height and monitor height, based on BIFMA ergonomics guidelines."},
    {"url": "https://desklab.com/guides/best-small-standing-desks", "title": "Best Small Standing Desks for Apartments (2026)", "description": "We tested 14 small standing desks for wobble, noise and speed. Here are the 6 we'd buy for apartments and home offices under 40 inches wide."},
    {"url": "https://desklab.com/blog/best-small-standing-desk-apartment", "title": "Best Small Standing Desk for Apartments 2026", "description": "Our picks for the best small standing desk for an apartment, with measurements, prices and what we'd skip."},
    {"url": "https://desklab.com/about", "title": "DeskLab", "description": "About us."},
    {"url": "https://desklab.com/warranty", "title": "Warranty and Returns Policy | DeskLab", "description": "Every DeskLab desk carries a 10-year frame and motor warranty and a 60-day home trial with free return pickup in the US."},
    {"url": "https://desklab.com/guides/standing-desk-benefits", "title": "Standing Desk Benefits: What 12 Studies Actually Show | DeskLab", "description": "Does a standing desk help your back, focus or calories burned? We summarise 12 peer-reviewed studies and tell you how long to stand each hour."},
]

NAP_LISTINGS = [
    {"source": "website", "name": "Rivera Family Plumbing, LLC", "address": "4410 Burnet Road, Suite 200, Austin, TX 78756", "phone": "(512) 555-0142", "website": "https://riveraplumbing.com"},
    {"source": "gbp", "name": "Rivera Family Plumbing", "address": "4410 Burnet Rd Ste 200, Austin, TX 78756", "phone": "512-555-0142", "website": "https://www.riveraplumbing.com/"},
    {"source": "yelp", "name": "Rivera Family Plumbing", "address": "4410 Burnet Rd #200, Austin, TX 78756-3321", "phone": "+1 512.555.0142", "website": "https://riveraplumbing.com"},
    {"source": "facebook", "name": "Rivera Plumbing Austin - Best Plumber", "address": "4410 Burnet Road Suite 200 Austin Texas 78756", "phone": "(512) 555-0142", "website": "https://riveraplumbing.com"},
    {"source": "bing", "name": "Rivera Family Plumbing", "address": "3100 N Lamar Blvd, Austin, TX 78705", "phone": "(512) 555-0142", "website": "https://riveraplumbing.com"},
    {"source": "apple", "name": "Rivera Family Plumbing", "address": "4410 Burnet Rd, Suite 200, Austin, TX 78756", "phone": "(512) 555-0199", "website": "https://riveraplumbing.com"},
    {"source": "yellowpages", "name": "Rivera Family Plumbing Inc.", "address": "4410 Burnet Rd., Ste. 200, Austin, TX 78756", "phone": "5125550142", "website": "http://riveraplumbing.com"},
    {"source": "angi", "name": "Rivera Family Plumbing", "address": "4410 Burnet Rd Suite 200, Austin, TX 78756", "phone": "(512) 555-0142", "website": "http://www.riveraplumbing.com"},
]

KEYWORDS = [
    ["meal prep containers", 40500, 38, 1.2, None],
    ["Meal Prep Containers ", 40500, 38, 1.2, None],
    ["meal prep container", 6600, 35, 1.1, None],
    ["glass meal prep containers", 9900, 22, 1.4, None],
    ["best meal prep containers", 5400, 41, 1.6, "commercial"],
    ["best glass meal prep containers", 1300, 18, 1.5, "commercial"],
    ["meal prep containers vs tupperware", 210, 5, 0.3, "commercial"],
    ["buy meal prep containers bulk", 480, 12, 1.9, "transactional"],
    ["cheap meal prep containers", 880, 15, 1.3, "transactional"],
    ["meal prep container set price", 90, 8, 1.0, "transactional"],
    ["how to meal prep for the week", 12100, 45, 0.4, "informational"],
    ["meal prep ideas", 74000, 62, 0.6, "informational"],
    ["healthy meal prep ideas", 18100, 48, 0.5, "informational"],
    ["meal prep ideas for weight loss", 8100, 40, 0.7, "informational"],
    ["what is meal prep", 1900, 20, 0.2, "informational"],
    ["how long does meal prep last in the fridge", 2400, 12, 0.1, "informational"],
    ["meal prep in bulk", 320, 10, 0.4, "informational"],
    ["meal prep delivery near me", 22200, 30, 3.5, "local"],
    ["meal prep delivery in austin", 390, 20, 4.0, "local"],
    ["best meal prep app", 3600, 55, 2.1, "commercial"],
    ["meal prep planner app", 1000, 30, 1.8, "commercial|transactional"],
    ["preppal login", 260, 0, 0.0, "navigational"],
    ["preppal containers review", 170, 3, 0.5, "commercial"],
    ["freshly vs factor meal delivery", 2900, 33, 5.2, "commercial"],
    ["how to meal prep chicken", 6600, 35, 0.3, "informational"],
    ["meal prep chicken recipes", 9900, 40, 0.4, None],
    ["meal prep container dishwasher safe", 590, 9, 0.9, None],
    ["meal prep sunday", 1000, 25, 0.2, None],
]

PAGES = [
    {"id": "roof-austin", "text": "Planning a roof replacement in Austin? Most homeowners in Austin pay between $9,800 and $15,400 for a full roof replacement on a typical single-family home. Your final price depends on the size of the roof, the pitch, the material you choose and how many layers need to be torn off. Asphalt shingles are the most affordable option, while metal and tile cost more up front but last longer. Get free quotes from licensed roofers in Austin and compare prices before you sign. HomeQuote checks every contractor's license and insurance. "},
    {"id": "roof-dallas", "text": "Planning a roof replacement in Dallas? Most homeowners in Dallas pay between $9,500 and $14,900 for a full roof replacement on a typical single-family home. Your final price depends on the size of the roof, the pitch, the material you choose and how many layers need to be torn off. Asphalt shingles are the most affordable option, while metal and tile cost more up front but last longer. Get free quotes from licensed roofers in Dallas and compare prices before you sign. HomeQuote checks every contractor's license and insurance. "},
    {"id": "roof-houston", "text": "Planning a roof replacement in Houston? Most homeowners in Houston pay between $9,200 and $14,600 for a full roof replacement on a typical single-family home. Your final price depends on the size of the roof, the pitch, the material you choose and how many layers need to be torn off. Asphalt shingles are the most affordable option, while metal and tile cost more up front but last longer. Get free quotes from licensed roofers in Houston and compare prices before you sign. HomeQuote checks every contractor's license and insurance. "},
    {"id": "roof-plano", "text": "Planning a roof replacement in Plano? Most homeowners in Plano pay between $10,100 and $15,900 for a full roof replacement on a typical single-family home. Your final price depends on the size of the roof, the pitch, the material you choose and how many layers need to be torn off. Asphalt shingles are the most affordable option, while metal and tile cost more up front but last longer. Get free quotes from licensed roofers in Plano and compare prices before you sign. HomeQuote checks every contractor's license and insurance. "},
    {"id": "roof-waco", "text": "Planning a roof replacement in Waco? Most homeowners in Waco pay between $8,400 and $13,100 for a full roof replacement on a typical single-family home. Your final price depends on the size of the roof, the pitch, the material you choose and how many layers need to be torn off. Asphalt shingles are the most affordable option, while metal and tile cost more up front but last longer. Get free quotes from licensed roofers in Waco and compare prices before you sign. HomeQuote checks every contractor's license and insurance. "},
    {"id": "roof-frisco", "text": "Planning a roof replacement in Frisco? Most homeowners in Frisco pay between $10,400 and $16,200 for a full roof replacement on a typical single-family home. Your final price depends on the size of the roof, the pitch, the material you choose and how many layers need to be torn off. Asphalt shingles are the most affordable option, while metal and tile cost more up front but last longer. Get free quotes from licensed roofers in Frisco and compare prices before you sign. HomeQuote checks every contractor's license and insurance. "},
    {"id": "roof-san-antonio", "text": "San Antonio sits in hail alley: the city logged 14 severe hail days between 2021 and 2025, and after the 2024 storms permit filings for re-roofs jumped 38 percent. Bexar County requires a permit for any re-roof over 100 square feet, costing 180 to 450 dollars depending on valuation. Most local crews recommend Class 4 impact-resistant shingles here because several insurers discount premiums by up to 20 percent for them. Our 212 completed San Antonio jobs averaged 11,300 dollars, with Alamo Heights homes running higher because of steeper pitches and clay tile. Typical lead time in spring is five weeks. Median roof size in our local data is 24 squares, and 31 percent of jobs needed decking replacement at an average of 1,150 dollars extra."},
    {"id": "roof-el-paso", "text": "El Paso roofs fail from sun, not storms. With more than 300 sunny days a year, UV breaks down asphalt shingles years sooner than in humid Houston, so many El Paso homeowners choose elastomeric coatings on flat roofs or reflective cool-roof shingles. The city requires a building permit plus an inspection after tear-off. Across our 97 El Paso projects the average flat-roof recoat cost 4,900 dollars and a full pitched-roof replacement 10,200 dollars. Adobe and stucco homes in the Upper Valley often have parapet walls that add flashing work. Monsoon season from July to September is the busiest time to book, and prices rise roughly 8 percent."},
    {"id": "roof-round-rock", "text": "Round Rock is growing fast, and many subdivisions built between 2003 and 2008 are now hitting the 20-year mark for their original builder-grade shingles. HOA rules in Teravista and Forest Creek limit colors to approved palettes, so check your deed restrictions before choosing material. Williamson County does not require a permit for like-for-like re-roofing inside city limits, but the city does. Based on 64 local jobs, homeowners paid a median 12,700 dollars, and 3-tab to architectural upgrades added about 9 percent. Several insurers in the area now require roofs under 15 years old for replacement-cost coverage, which is driving demand."},
    {"id": "roof-austin-copy", "text": "Planning a roof replacement in Austin? Most homeowners in Austin pay between $9,800 and $15,400 for a full roof replacement on a typical single-family home. Your final price depends on the size of the roof, the pitch, the material you choose and how many layers need to be torn off. Asphalt shingles are the most affordable option, while metal and tile cost more up front but last longer. Get free quotes from licensed roofers in Austin and compare prices before you sign. HomeQuote checks every contractor's license and insurance. "},
]


def build_reviews():
    """40 dated reviews: 24×5, 8×4, 3×3, 2×2, 3×1 (sum 168, avg 4.2); 6 in the last 90 days, 9 in the prior 90."""
    last90 = [("2026-09-20", 5), ("2026-09-02", 5), ("2026-08-15", 4), ("2026-07-28", 1), ("2026-07-10", 5), ("2026-07-01", 5)]
    prior90 = [("2026-06-20", 5), ("2026-06-05", 5), ("2026-05-28", 4), ("2026-05-15", 2), ("2026-05-02", 5), ("2026-04-22", 5), ("2026-04-15", 3), ("2026-04-08", 5), ("2026-04-01", 5)]
    order = [5, 4, 5, 5, 1, 5, 4, 5, 3, 5, 5, 4, 5, 2, 5, 4, 5, 5, 1, 5, 4, 3, 5, 4, 5]
    older = [((dt.date(2024, 10, 1) + dt.timedelta(days=21 * i)).isoformat(), r) for i, r in enumerate(order)]
    return [{"date": d, "rating": r} for d, r in older + prior90 + last90]


# ── 1. SEO Auditor vs Screaming Frog (single-page on-page audit) ──────────────

URL = "https://www.sitwell.com/products/ergo_pro_mesh_chair?variant=41872"


def test_seo_auditor_finds_all_12_planted_defects_without_false_alarms():
    audit = run("seo-auditor", "audit_page", html=PRODUCT_HTML, url=URL, keyword="ergonomic office chair")
    outline = run("seo-auditor", "heading_outline", html=PRODUCT_HTML)
    links = run("seo-auditor", "link_audit", html=PRODUCT_HTML, base_url=URL)
    issues = {(i["element"], i["severity"]): i for i in audit["issues"]}
    probs = [p["problem"] for p in links["problems"]]
    found = {
        "missing canonical (param URL → high)": ("canonical", "high") in issues,
        "canonical fix is the clean URL": 'href="https://www.sitwell.com/products/ergo_pro_mesh_chair"' in issues[("canonical", "high")]["fix"],
        "two H1s": audit["inventory"]["h1"] == ["Ergo Pro Mesh Ergonomic Office Chair", "Why Our Customers Love It"] and ("h1", "medium") in issues,
        "3 images without alt (decorative alt='' not counted)": audit["inventory"]["images_missing_alt"] == 3 and audit["inventory"]["images_empty_alt"] == 1,
        "title over 600px": ("title", "medium") in issues and audit["inventory"]["title_px"] > 600,
        "description over limit": ("meta description", "low") in issues and audit["inventory"]["description_chars"] == 208,
        "H2→H4 skip": any(p["problem"] == "skips from H2 to H4" for p in outline["problems"]),
        "generic anchors": ("links", "low") in issues and "click here" in issues[("links", "low")]["problem"] and "Read more" in issues[("links", "low")]["problem"],
        "javascript: href": "non-crawlable href" in probs,
        "target=_blank without noopener": "target=_blank without rel=noopener" in probs,
        "http link on https page": "http link on https page" in probs,
        "no lang attribute": ("html", "low") in issues,
        "URL underscores + parameters": ("url", "low") in issues and "underscores" in issues[("url", "low")]["problem"] and "query parameters" in issues[("url", "low")]["problem"],
    }
    assert all(found.values()), [k for k, v in found.items() if not v]
    # precision: nothing flagged on the elements that are correct
    elements = {i["element"] for i in audit["issues"]}
    for ok in ("robots", "mobile", "social", "structured data", "content", "headings"):
        assert ok not in elements, ok
    assert audit["indexable"] is True and audit["inventory"]["viewport"] is True and audit["inventory"]["jsonld_blocks"] == 1
    # the 9th audit issue is real but unplanted: the header logo <img> has no width/height (Screaming Frog's "Missing Size Attributes")
    extra = [i for i in audit["issues"] if i["element"] == "images" and "width/height" in i["problem"]]
    assert len(extra) == 1 and extra[0]["current"] == "/img/logo.svg"
    assert len(audit["issues"]) == 9 and len(outline["problems"]) == 2 and len(links["problems"]) == 4
    assert audit["score"] == 60


def test_seo_auditor_pixel_widths_match_arial_metrics():
    audit = run("seo-auditor", "audit_page", html=PRODUCT_HTML, url=URL, keyword="ergonomic office chair")
    assert audit["inventory"]["title_px"] == pytest.approx(1083.4, abs=0.5)  # Liberation Sans hmtx reference
    if os.path.exists(FONT):
        assert audit["inventory"]["title_px"] == pytest.approx(liberation_width(audit["inventory"]["title"], 20), rel=0.002)


# ── 2. Meta Writer vs Yoast SEO Premium (+ Screaming Frog titles/descriptions tabs) ─


def test_meta_writer_site_audit_recall_and_precision():
    out = run("meta-writer", "audit_snippets", rows=SNIPPET_ROWS)
    assert [g["urls"] for g in out["duplicate_titles"]] == [["https://desklab.com/desks/corner-standing-desk", "https://desklab.com/desks/kids-standing-desk"]]
    assert len(out["duplicate_descriptions"]) == 1
    near = out["near_duplicate_titles"]
    assert len(near) == 1 and {near[0]["a"]["url"], near[0]["b"]["url"]} == {"https://desklab.com/guides/best-small-standing-desks", "https://desklab.com/blog/best-small-standing-desk-apartment"}
    flagged = {(p["url"].rsplit("/", 1)[-1], p["issue"].split(" ")[0] + " " + p["issue"].split(" ")[1]) for p in out["problems"]}
    assert ("wall-mounted-desk", "missing title") in flagged
    assert ("monitor-arm", "missing description") in flagged
    assert any(u == "standing-desk-height-calculator" and "title" in i for u, i in flagged)
    assert any(u == "about" and "brand/generic" in p["issue"] for p in out["problems"] for u in [p["url"].rsplit("/", 1)[-1]])
    # precision: the 6 clean rows are never mentioned
    clean = {"https://desklab.com/", "https://desklab.com/desks/compact-standing-desk", "https://desklab.com/warranty", "https://desklab.com/guides/standing-desk-benefits"}
    assert not clean & {p["url"] for p in out["problems"]}


def test_meta_writer_recommended_snippet_fits_and_widths_match_font():
    t = 'Standing Desk for Small Spaces: 9 Picks Under 40" (2026)'
    d = 'Find a standing desk for small spaces that fits: 9 compact sit-stand desks from 30" wide, tested for wobble at full height. Compare sizes and prices.'
    st = run("meta-writer", "score_title", title=t, keyword="standing desk for small spaces", brand="DeskLab")
    sd = run("meta-writer", "score_description", description=d, keyword="standing desk for small spaces", title=t)
    assert st["fits_desktop"] and st["keyword_position"] == 0 and st["score"] >= 80
    assert sd["fits_desktop"] and 120 <= sd["chars"] <= 156 and sd["score"] >= 80  # Yoast's green band is 120-156 chars
    too_long = run("meta-writer", "score_title", title="Standing Desk for Small Spaces: 9 Compact Picks (2026) | DeskLab", keyword="standing desk for small spaces", brand="DeskLab")
    assert too_long["px"] == pytest.approx(606.5, abs=0.5) and not too_long["fits_desktop"]
    if os.path.exists(FONT):
        samples = [(r["title"], 20) for r in SNIPPET_ROWS if r["title"]] + [(r["description"], 14) for r in SNIPPET_ROWS if r["description"]]
        samples += [("Café Crème — Paris’s “Best” Brûlée Guide…", 20), ("100% Free SEO Checklist [Template] © 2026 ™", 20), ("W" * 36, 20), ("i" * 45, 20)]
        for s, px in samples:
            prev = run("meta-writer", "serp_preview", title=s) if px == 20 else run("meta-writer", "serp_preview", title="x", description=s)
            got = prev["title"]["desktop"]["px"] if px == 20 else prev["description"]["desktop"]["px"]
            assert got == pytest.approx(liberation_width(" ".join(s.split()), px), rel=0.002), s


# ── 3. Schema Markup vs Rank Math PRO schema / Google Rich Results requirements ─


def test_schema_extract_finds_all_7_planted_errors_and_no_false_errors():
    out = run("schema-markup", "extract_schema", html=SCHEMA_HTML)
    b = out["blocks"]
    product_errors = " | ".join(b[0]["objects"][0]["errors"])
    for needle in ("'$129.99' must be a plain number", "'In Stock' is not a schema.org ItemAvailability", "'12/31/2026' is not ISO 8601", "needs ratingCount or reviewCount", "review[0]: Review needs an author"):
        assert needle in product_errors, needle
    assert len(b[0]["objects"][0]["errors"]) == 5  # review[1] has an author → not flagged
    assert out["conflicting_values"] == ["Product.name: 'Stride Trail 3' vs 'Stride Trail 3 Running Shoe'", "Product.offers.price: '129.99' vs '139.99'"]
    crumbs = b[2]["objects"][0]["errors"]
    assert crumbs[0] == "BreadcrumbList.itemListElement[0]: position should be 1, got 0"
    assert not any("non-final items need 'item'" in e for e in crumbs)  # last crumb without item is allowed by Google
    assert b[1]["objects"][0]["errors"] == [] and b[3]["objects"][0]["errors"] == []  # 2nd Product + Organization are valid
    assert out["error_count"] == 8


def google_product_snippet_ok(ld):
    """Google product-snippet rules, re-stated independently from developers.google.com."""
    import re

    errs = []
    if not ld.get("name"):
        errs.append("name")
    if not any(k in ld for k in ("offers", "review", "aggregateRating")):
        errs.append("offers|review|aggregateRating")
    off = ld.get("offers") or {}
    if off and not re.fullmatch(r"\d+(\.\d+)?", str(off.get("price", ""))):
        errs.append("offers.price")
    if off.get("availability") and not off["availability"].startswith("https://schema.org/"):
        errs.append("availability enum")
    if off.get("priceValidUntil") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", off["priceValidUntil"]):
        errs.append("priceValidUntil")
    ar = ld.get("aggregateRating")
    if ar and (not ar.get("ratingValue") or not (ar.get("ratingCount") or ar.get("reviewCount"))):
        errs.append("aggregateRating")
    return errs


def test_schema_rebuilt_markup_passes_google_rules():
    built = run("schema-markup", "build_schema", schema_type="Product", fields={"name": "Stride Trail 3", "image": ["https://stride.com/img/trail3-side.jpg"], "brand": "Stride", "sku": "TR3-M-10", "url": "https://stride.com/trail-3", "price": "$129.99", "currency": "USD", "availability": "in stock", "price_valid_until": "12/31/2026", "rating_value": 4.6, "review_count": 212, "condition": "new"})
    assert built["errors"] == [] and google_product_snippet_ok(built["jsonld"]) == []
    assert built["jsonld"]["offers"]["price"] == "129.99" and built["jsonld"]["offers"]["priceValidUntil"] == "2026-12-31"
    crumbs = run("schema-markup", "breadcrumbs_from_url", url="https://stride.com/trail/trail-3", labels={"trail": "Trail", "trail-3": "Stride Trail 3"})
    items = crumbs["jsonld"]["itemListElement"]
    assert [i["position"] for i in items] == [1, 2, 3] and all("item" in i for i in items[:-1]) and crumbs["errors"] == []
    # Article / Organization have no required properties per Google: missing ones are never errors
    art = run("schema-markup", "validate_schema", jsonld='{"@context":"https://schema.org","@type":"BlogPosting","headline":"How to lace trail shoes"}')
    assert art["error_count"] == 0


# ── 4. Local SEO vs BrightLocal (Citation Tracker NAP audit, Reputation Manager) ─


def test_local_nap_finds_3_real_mismatches_and_ignores_formatting():
    out = run("local-seo", "nap_consistency", listings=NAP_LISTINGS)
    assert sorted((m["source"], m["field"]) for m in out["mismatches"]) == [("apple", "phone"), ("bing", "address"), ("facebook", "name")]
    assert "keyword-stuffed" in next(m for m in out["mismatches"] if m["source"] == "facebook")["note"]
    assert out["canonical"]["phone"] == "(512) 555-0142"
    ok = {t["source"] for t in out["table"] if t["status"] == "ok"}
    assert ok == {"website", "gbp", "yelp", "yellowpages", "angi"}  # Texas/TX, #200/Suite 200, ZIP+4, +1 and LLC/Inc are cosmetic
    assert out["consistency_pct"] == 62  # 5 of 8 sources clean


def test_local_review_math_matches_hand_calculation():
    out = run("local-seo", "review_stats", reviews=build_reviews(), target_rating=4.5, today="2026-09-27")
    n, total = 40, 168
    k_true = math.ceil((4.5 * n - total) / (5 - 4.5))
    k_disp = next(k for k in range(100) if round((total + 5 * k) / (n + k) + 1e-9, 1) >= 4.5)
    assert (k_true, k_disp) == (24, 19)
    assert out["average"] == 4.2 and out["five_star_reviews_needed_for_target"] == k_true
    assert out["five_star_reviews_needed_for_displayed_target"] == k_disp
    assert out["velocity_per_month_last_90d"] == 2.0 and out["velocity_per_month_prior_90d"] == 3.0 and out["trend"] == "slowing"
    assert out["velocity_per_month_all_time"] == round(40 / ((dt.date(2026, 9, 27) - dt.date(2024, 10, 1)).days / 30.44), 2)
    assert out["reviews_last_12_months"] == 22 and out["months_to_target_at_current_velocity_if_all_5_star"] == 12.0


def test_local_review_reply_lint_catches_all_6_planted_problems():
    review = "Tech showed up 3 hours late and was rude when I asked about the price. He fixed the leak under the sink but charged 80 dollars more than the quote."
    bad = ("Hi Mark, thank you for your feedback. We're sorry you had a bad experience. Actually, our technicians are always courteous and the price "
           "difference was explained on invoice #48213. We'd like to offer you a 20% discount on your next service if you update your review.")
    good = ("Mark, I'm sorry. Arriving three hours late without a call is on us, and a technician being short with you when you asked about price is not "
            "how we run things. You should also have been told before any charge above the quote. I'm the owner, and I'd like to go through the bill "
            "with you and make it right. Please call me directly at (512) 555-0142 or email ana@riveraplumbing.com.")
    b = run("local-seo", "review_response_lint", review=review, rating=2, response=bad, reviewer_name="Mark", business_keywords=["plumbing", "Austin"])
    text = " | ".join(b["issues"])
    for needle in ("Template phrase", "Defensive", "personal/account", "Incentive", "No ownership", "No offline next step"):
        assert needle in text, needle
    assert b["blocking"] and not b["passes"]
    g = run("local-seo", "review_response_lint", review=review, rating=2, response=good, reviewer_name="Mark", business_keywords=["plumbing", "Austin"])
    assert g["passes"] and g["issues"] == []


def test_local_gbp_score_is_the_weighted_sum():
    out = run("local-seo", "gbp_completeness", profile={"primary_category": "Plumber", "secondary_categories": [], "name_clean": True, "address_or_service_area": "4410 Burnet Rd Ste 200, Austin, TX 78756", "phone": "(512) 555-0142", "website": "https://riveraplumbing.com", "hours": True, "description": "Family-owned plumbers in Austin since 1998.", "photos": 6, "services_or_products": 3, "attributes": 4, "posts_days_since_last": 45, "qa_seeded": False, "reviews_count": 40, "review_response_rate": 0.55})
    assert out["score"] == 15 + 8 + 6 + 5 + 4 + 8 + 4 + 6
    assert [m["field"] for m in out["missing"][:2]] == ["photos", "services_or_products"]


# ── 5. Keyword Strategist vs Semrush Keyword Strategy Builder / Ahrefs KE ─────


def test_keyword_intent_matches_hand_labels():
    rows = run("keyword-strategist", "classify_intent", keywords=[k[0] for k in KEYWORDS], brands=["PrepPal"])["rows"]
    labelled = [(r, k[4]) for r, k in zip(rows, KEYWORDS) if k[4]]
    wrong = [(r["keyword"], r["intent"], gt) for r, gt in labelled if r["intent"] not in gt.split("|")]
    assert len(labelled) == 21 and wrong == []
    by = {r["keyword"]: r for r in rows}
    nouns = ["meal prep containers", "meal prep container", "glass meal prep containers", "meal prep container dishwasher safe", "meal prep sunday"]
    assert all(by[k]["confidence"] < 0.6 for k in nouns)  # bare product nouns are surfaced for judgement, not guessed
    assert by["meal prep chicken recipes"]["intent"] == "informational"


def test_keyword_clusters_are_single_intent_pages():
    out = run("keyword-strategist", "cluster_keywords", keywords=[k[0] for k in KEYWORDS], volumes=[k[1] for k in KEYWORDS])
    assert out["duplicates_merged"] == ["Meal Prep Containers"]
    assert sum(c["total_volume"] for c in out["clusters"]) == sum(k[1] for k in KEYWORDS) - 40500
    gt = {k[0].strip().lower(): k[4] for k in KEYWORDS if k[4]}
    for c in out["clusters"]:  # no page mixes two confidently-labelled intents
        intents = {gt[m.lower()] for m in c["members"] if m.lower() in gt}
        assert len({i.split("|")[0] for i in intents}) <= 1 or intents == {"commercial", "commercial|transactional"}, c
    home = {m: c["head"] for c in out["clusters"] for m in c["members"]}
    assert home["meal prep ideas"] != home["meal prep containers"]
    assert home["meal prep delivery near me"] == home["meal prep delivery in austin"]
    assert home["how to meal prep chicken"] == home["meal prep chicken recipes"]
    trans = next(c for c in out["clusters"] if c["intent"] == "transactional" and "cheap meal prep containers" in c["members"])
    assert set(trans["members"]) == {"cheap meal prep containers", "buy meal prep containers bulk", "meal prep container set price"}


def test_keyword_opportunity_scores_follow_the_published_formula():
    judged = {"meal prep containers": "transactional", "meal prep container": "transactional", "glass meal prep containers": "transactional", "meal prep container dishwasher safe": "transactional", "meal prep chicken recipes": "informational", "meal prep sunday": "informational"}
    rows, seen = [], set()
    for k, v, kd, cpc, gt in KEYWORDS:
        n = " ".join(k.split()).lower()
        if n not in seen:
            seen.add(n)
            rows.append({"keyword": n, "volume": v, "difficulty": kd, "cpc": cpc, "intent": gt.split("|")[0] if gt else judged.get(n, "informational")})
    out = run("keyword-strategist", "score_opportunities", rows=rows, site_stage="new", current_positions={"how to meal prep chicken": 14})
    w = {"transactional": 1.4, "commercial": 1.2, "local": 1.2, "informational": 0.8, "navigational": 0.3}
    for r in out["ranked"]:
        exp = 25 * math.log10(r["volume"] + 10) * w[r["intent"]] * (1 - r["difficulty"] / 100) ** 2 * (1 + min(r["cpc"], 10) / 10)
        exp *= 1.5 if r["keyword"] == "how to meal prep chicken" else 1
        assert r["score"] == pytest.approx(exp, abs=0.11), r["keyword"]
    expected_qw = {r["keyword"] for r in rows if r["difficulty"] <= 30 and r["volume"] >= 100 and r["intent"] != "navigational"}
    assert set(out["quick_wins"]) == expected_qw and "preppal login" not in expected_qw
    assert out["ranked"][0]["keyword"] == "glass meal prep containers" and out["striking_distance"] == ["how to meal prep chicken"]


def test_keyword_gap_counts():
    out = run("keyword-strategist", "keyword_gap", ours=["meal prep containers", "meal prep container set price", "preppal login", "preppal containers review"], competitors={
        "prepnaturals": ["glass meal prep containers", "best glass meal prep containers", "meal prep containers vs tupperware", "Meal Prep Container Dishwasher Safe", "how to meal prep for the week"],
        "bentgo": ["meal prep container", "best meal prep containers", "meal prep containers dishwasher safe", "glass meal prep container", "bento box for adults"]})
    assert out["gap_count"] == 7
    assert sorted(k.lower() for k in out["high_confidence_gap"]) == ["glass meal prep containers", "meal prep container dishwasher safe"]
    assert out["overlap"]["bentgo"]["shared"] == 1 and out["overlap"]["prepnaturals"]["shared"] == 0


# ── 6. Growth Experiment Lab vs GrowthBook (frequentist engine, SRM, power) ──


def test_experiment_sizing_matches_textbook_formula():
    s = run("growth-experiments", "sample_size", baseline_rate=3.2, mde_relative=10, weekly_traffic=8000)
    assert s["visitors_per_arm"] == textbook_n_per_arm(0.032, 0.10) == 49777
    assert s["weeks_needed"] == math.ceil(2 * 49777 / 8000) == 13 and s["mde_detectable_in_8_weeks_pct"] == 12.5
    three = run("growth-experiments", "sample_size", baseline_rate=0.032, mde_relative=0.25, weekly_traffic=8000, variants=3)
    assert three["visitors_per_arm"] == textbook_n_per_arm(0.032, 0.25, arms=3)
    assert textbook_n_per_arm(0.10, 0.20) == 3841  # the classic 10%→12% table value (no continuity correction)
    assert run("growth-experiments", "sample_size", baseline_rate=0.10, mde_relative=0.20)["visitors_per_arm"] == 3841


def test_experiment_evaluation_matches_hand_computed_z_ci_srm():
    n1, x1, n2, x2 = 10412, 331, 10388, 372
    out = run("growth-experiments", "evaluate_result", control_visitors=n1, control_conversions=x1, variant_visitors=n2, variant_conversions=x2, planned_visitors_per_arm=10000)
    p1, p2 = x1 / n1, x2 / n2
    pp = (x1 + x2) / (n1 + n2)
    z = (p2 - p1) / math.sqrt(pp * (1 - pp) * (1 / n1 + 1 / n2))
    assert out["z"] == pytest.approx(z, abs=0.001) and out["p_value"] == pytest.approx(math.erfc(abs(z) / math.sqrt(2)), abs=1e-5)
    se_rel = math.sqrt((p2 * (1 - p2) / n2) / p1**2 + p2**2 * (p1 * (1 - p1) / n1) / p1**4)
    rel = p2 / p1 - 1
    zc = z_quantile(0.975)
    assert out["ci_95_relative_pct"] == [round(100 * (rel - zc * se_rel), 2), round(100 * (rel + zc * se_rel), 2)]
    assert out["decision"] == "inconclusive"
    srm = run("growth-experiments", "evaluate_result", control_visitors=50000, control_conversions=1600, variant_visitors=48200, variant_conversions=1700)
    chi = (50000 - 49100) ** 2 / 49100 * 2
    assert srm["srm"]["chi_square"] == pytest.approx(chi, abs=0.001) and srm["decision"] == "invalid"
    peek = run("growth-experiments", "evaluate_result", control_visitors=4100, control_conversions=120, variant_visitors=4080, variant_conversions=160, planned_visitors_per_arm=49777)
    assert peek["p_value"] < 0.05 and peek["decision"] == "inconclusive"


def test_experiment_backlog_ice_and_sprint():
    exps = [("Social proof bar on signup page", 6, 7, 9, "signup", 4), ("Remove credit card from trial", 9, 8, 4, "signup", 6), ("Onboarding checklist", 7, 5, 5, "onboarding", 5),
            ("Annual plan default toggle", 5, 6, 9, "pricing", 3), ("Exit-intent discount", 4, 4, 8, "pricing", 3), ("Rewrite hero headline", 8, 3, 10, "homepage", 2)]
    out = run("growth-experiments", "score_experiments", experiments=[{"name": n, "impact": i, "confidence": c, "ease": e, "surface": s} for n, i, c, e, s, _ in exps])
    assert [r["score"] for r in out["ranked"]] == sorted((i * c * e for _, i, c, e, _, _ in exps), reverse=True)
    plan = run("growth-experiments", "plan_sprint", experiments=[{"name": n, "score": i * c * e, "weeks": w, "surface": s} for n, i, c, e, s, w in exps], parallel_slots=2, horizon_weeks=12)
    sched = {x["name"]: x for x in plan["schedule"]}
    assert sched["Remove credit card from trial"]["start_week"] == 5  # waits for the signup-surface test to finish
    for a in plan["schedule"]:
        for b in plan["schedule"]:
            if a is not b and a["surface"] == b["surface"]:
                assert a["end_week"] < b["start_week"] or b["end_week"] < a["start_week"]
    assert [u["name"] for u in plan["unscheduled"]] == ["Exit-intent discount"]


# ── 7. Referral Program Designer vs ReferralCandy (program design) ───────────


def test_referral_economics_and_k_factor_by_hand():
    econ = run("referral-program", "reward_economics", arpu_monthly=29, gross_margin_pct=70, monthly_churn_pct=4, paid_cac=180, referrer_reward=50, referee_reward=50)
    ltv = 29 * 0.7 / 0.04
    assert econ["ltv"] == pytest.approx(ltv) and ltv == pytest.approx(507.5) and econ["payback_months"] == round(100 / 20.3, 2) and econ["reward_ceiling"]["recommended_max_total"] == round(ltv / 3, 2)
    viral = run("referral-program", "viral_coefficient", invites_per_user=1.8, invite_conversion_rate=12, seed_users=2000, cycle_time_days=10, horizon_days=90)
    k = 1.8 * 0.12
    assert viral["k_factor"] == round(k, 3) and viral["amplification"] == round(1 / (1 - k), 2)
    assert viral["cycles_in_horizon"] == 9 and viral["users_at_horizon"] == round(2000 * sum(k**i for i in range(10)))
    funnel = run("referral-program", "referral_funnel", active_users=2000, share_rate=8, invites_per_sharer=3.2, invite_click_rate=25, click_signup_rate=15, signup_qualified_rate=40)
    q = 2000 * 0.08 * 3.2 * 0.25 * 0.15 * 0.40
    assert funnel["funnel"]["qualified"] == round(q, 1) and funnel["implied_k"] == round(q / 2000, 3)
    ups = {u["step"]: u["lift_to_top_of_range_adds"] for u in funnel["upside_by_step"]}
    assert ups["click_signup_rate"] == round(q * 0.35 / 0.15 - q) and funnel["fix_first"] == "click_signup_rate"
    cmp = run("referral-program", "compare_rewards", structures=[
        {"name": "one-sided $100 cash", "referrer_reward": 100, "expected_conversion": 0.08},
        {"name": "two-sided $50/$50 credit", "referrer_reward": 50, "referee_reward": 50, "expected_conversion": 0.12},
        {"name": "two-sided $30/$30 at signup", "referrer_reward": 30, "referee_reward": 30, "expected_conversion": 0.14, "paid_on": "signup", "signup_to_paid": 0.4}], ltv=507.5, paid_cac=180, contribution_per_month=20.3)
    assert cmp["recommended"] == "two-sided $50/$50 credit"  # the signup-paid option has higher raw net but fails payback + fraud guardrails


# ── 8. Programmatic SEO vs Screaming Frog (duplicates, URL issues) + Google sitemap limits ─


def test_programmatic_plan_and_slugs_catch_planted_problems():
    plan = run("programmatic-seo", "plan_combinations", dimensions={"service": ["Roof Replacement", "Water Heater Installation", "Kitchen Remodel", "Bathroom Remodel", "Fence Installation", "Deck Building", "HVAC Repair", "Roof Replacement"], "city": ["Austin", "Dallas", "Houston", "San Antonio", "Fort Worth", "El Paso", "Plano", "Waco", "Round Rock", "Cedar Park", "", "Georgetown", "Frisco"]},
                title_template="{service} Cost in {city}, TX (2026 Prices) | HomeQuote", url_template="/cost/{service}/", sample=6)
    assert plan["total_pages"] == 7 * 12
    assert any("['city'] not used" in t for t in plan["template_issues"])
    w = " ".join(plan["warnings"])
    assert "duplicate values ['roof replacement']" in w and "1 empty value" in w
    over = [s for s in plan["samples"] if s["title_px"] > 600]
    if os.path.exists(FONT):
        assert len(over) == sum(1 for s in plan["samples"] if liberation_width(s["title"], 20) > 600) == 3
    slugs = run("programmatic-seo", "slugify_batch", items=["Winston-Salem", "Winston Salem", "St. Louis", "Coeur d'Alene", "Cañon City", "Kitchen & Bath Remodel", "Kitchen and Bath Remodel", "Roof Replacement (Asphalt Shingle, Metal, Tile and Slate Roofs Including Tear-Off and Disposal)"])
    assert sorted(c["slug"] for c in slugs["collisions"]) == ["kitchen-and-bath-remodel", "winston-salem"]
    by = {r["input"]: r for r in slugs["slugs"]}
    assert by["Cañon City"]["slug"] == "canon-city" and by["Coeur d'Alene"]["slug"] == "coeur-dalene" and by["St. Louis"]["issues"] == []
    assert len(by["Roof Replacement (Asphalt Shingle, Metal, Tile and Slate Roofs Including Tear-Off and Disposal)"]["slug"]) <= 60


def test_programmatic_near_duplicate_gate_matches_independent_shingles():
    out = run("programmatic-seo", "near_duplicates", pages=PAGES)
    assert out["passes_gate"] is False
    assert out["duplicate_clusters"] == [["roof-austin", "roof-austin-copy"]]
    sh = {p["id"]: shingle_set(p["text"]) for p in PAGES}
    freq = {}
    for s in sh.values():
        for g in s:
            freq[g] = freq.get(g, 0) + 1
    boiler = {g for g, n in freq.items() if n >= max(2, len(PAGES) / 2)}
    share = {pid: len(s - boiler) / len(s) for pid, s in sh.items()}
    for p in out["per_page"]:
        assert p["unique_share"] == pytest.approx(share[p["id"]], abs=0.001)
    template_pages = ["roof-austin", "roof-dallas", "roof-houston", "roof-plano", "roof-waco", "roof-frisco"]
    assert all(share[t] < 0.3 for t in template_pages) and all(share[r] == 1.0 for r in ("roof-san-antonio", "roof-el-paso", "roof-round-rock"))
    # the city-swap pages sit under the 0.8 pair threshold (like Screaming Frog's 90% minhash default) — the unique-share gate is what catches them
    jac = len(sh["roof-austin"] & sh["roof-dallas"]) / len(sh["roof-austin"] | sh["roof-dallas"])
    assert 0.5 < jac < 0.8 and out["median_unique_share"] < 0.4


def test_programmatic_architecture_depth_and_sitemaps():
    arch = run("programmatic-seo", "linking_architecture", page_count=84, links_per_hub=100)
    assert arch["hub_levels"] == [] and arch["click_depth_from_home"] == 1 and arch["sitemaps"] == 1
    big = run("programmatic-seo", "linking_architecture", page_count=120_000, links_per_hub=100)
    # home → 12 hubs → 1,200 hubs → pages; Google: ≤ 50,000 URLs per sitemap
    assert big["hub_levels"] == [1200, 12] and big["click_depth_from_home"] == 3 and big["sitemaps"] == math.ceil(120_000 / 50_000) == 3
