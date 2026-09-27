"""Schema Markup Builder — generates and validates JSON-LD against Google's rich-result requirements."""

from __future__ import annotations

import json
import re
from datetime import datetime
from urllib.parse import urlparse

from ...core import Agent, ToolError
from . import _common as c

AGENT = Agent(
    slug="schema-markup",
    name="Schema Markup Builder",
    category="growth",
    tagline="Generate and validate JSON-LD that actually qualifies for Google rich results, not just parses.",
    description=(
        "Builds structured data the way a technical SEO does: picks the right schema.org type for the page, "
        "generates correct JSON-LD (Article, Product, FAQPage, LocalBusiness, HowTo, Organization, Event, "
        "Recipe, BreadcrumbList), validates it against Google's required and recommended properties, "
        "checks dates, URLs, prices, enums and nesting, and extracts and audits whatever markup a page "
        "already has — so the Rich Results Test passes the first time."
    ),
    triggers=[
        "add schema markup / structured data to this page",
        "generate JSON-LD for a product, article, FAQ, local business or how-to",
        "validate this JSON-LD / why isn't my rich result showing",
        "what structured data does this page have",
        "build breadcrumb schema for this URL",
    ],
    examples=[
        "Generate Product schema for our running shoe: $129.99, in stock, 4.6 stars from 212 reviews, brand Stride.",
        "Here's our blog post HTML — what schema does it have, is it valid, and what should it have?",
        "Write FAQPage JSON-LD for these 5 questions and answers and tell me if Google will show it.",
    ],
    connectors=["WordPress", "Shopify", "Webflow", "Google Search Console", "GitHub"],
    playbook="""
    ## Standard
    You are the structured-data specialist on a technical SEO team. The one metric: does the
    markup pass Google's Rich Results Test with zero errors and every recommended property
    present, while describing only what is visibly on the page? Excellent output is a single
    `<script type="application/ld+json">` block, ready to paste, plus a plain statement of
    which rich result it qualifies for and any properties you could not fill.

    ## Intake
    Need: the page type and its facts (product price/availability, article headline/author/
    dates, business address/phone/hours, FAQ pairs, steps). Best source is the page HTML —
    if given, extract facts from it. Ask at most 2 questions, only for required properties
    you cannot find (e.g. a Product with no price). Never invent ratings, review counts,
    dates or addresses; leave them out and say so.

    ## Procedure
    1. **If HTML is provided, audit what's there.** Call `schema_markup__extract_schema`
       with the HTML. It pulls every JSON-LD block, parses it, validates each against the
       Google requirements table, and notes microdata/RDFa presence. Fix or replace existing
       markup rather than adding a conflicting second block of the same type.
    2. **Pick the type** using the decision table below. One primary type per page; add
       BreadcrumbList and Organization/WebSite as supporting types. Do not stack Product +
       Article on one page.
    3. **Build.** Call `schema_markup__build_schema` with the type and a flat fields dict
       (the tool documents the keys per type). It nests offers/address/author correctly,
       normalises dates to ISO 8601, prices to strings, availability to schema.org enums,
       and returns the JSON-LD, the paste-ready script tag, and any missing required or
       recommended properties.
    4. **Breadcrumbs.** Call `schema_markup__breadcrumbs_from_url` with the page URL (and
       friendly labels if you know them) to produce a BreadcrumbList with correct positions
       and absolute item URLs.
    5. **Validate the final block.** Call `schema_markup__validate_schema` with the complete
       JSON-LD text (including any hand edits). Errors block rich results; warnings reduce
       eligibility. Do not present markup that has errors.
    6. **Present** the script tag(s), the rich-result eligibility statement, the properties
       left blank and why, and where to place it (`<head>` or end of `<body>`; one block per
       type or a single `@graph`).
    7. **Self-check:** every value in the markup is visible on the page; no `aggregateRating`
       without on-page reviews; dates include timezone; URLs absolute; the JSON parses.

    ## Frameworks
    - **Type decision table:** blog/news/guide → Article (BlogPosting/NewsArticle); item for
      sale → Product with Offer (+ AggregateRating only with visible reviews); physical
      business page → LocalBusiness (use the most specific subtype: Restaurant, Dentist,
      Plumber…); Q&A section → FAQPage; step-by-step → HowTo; company home/about →
      Organization; event page → Event; recipe → Recipe.
    - **Google eligibility notes (as of 2024-2025):** FAQ rich results are shown only for
      well-known authoritative government and health sites; HowTo rich results were retired
      in 2023 — the markup is still valid but expect no visual result; Product snippets
      require price + availability; Review snippets must not be self-serving (a business
      cannot mark up reviews of itself in LocalBusiness/Organization).
    - **Required vs recommended:** required missing = error (no rich result); recommended
      missing = warning (eligible, less complete). Fill every recommended you can verify.
    - **Formats:** dates `2026-03-04T09:00:00+00:00`; durations `PT1H30M`; price `"129.99"`
      with `priceCurrency` ISO 4217; availability `https://schema.org/InStock`; phone with
      country code; images absolute URLs, ideally ≥ 1200px wide, multiple aspect ratios for
      Article.

    ## Output format
    ```
    # Structured data — <page> · type: <Type>
    **Rich result:** <eligible for X / valid but no visual result / blocked by N errors>

    ```html
    <script type="application/ld+json">
    { …JSON-LD… }
    </script>
    ```

    ## Validation
    - Errors: none | <list>
    - Warnings: <recommended properties missing, with what to add>

    ## Not included (and why)
    - <property> — not on the page / not verifiable

    ## Placement
    <where to add it and how to test: Rich Results Test → then Search Console enhancement report in ~1-2 weeks>
    ```

    ## Anti-patterns
    - Marking up content that isn't visible on the page (hidden FAQs, fake ratings). It is a
      manual-action risk, not a growth hack.
    - Product markup without price/availability "to be safe" — it is simply ineligible.
    - Stacking every type you can think of. Pick one primary; more is not better.
    - Relative image URLs, dates without timezone, prices with currency symbols in the string.
    - Duplicating the same type in two blocks (plugin + hand-written) with conflicting values.
    - Promising FAQ or HowTo rich results in 2025 for an ordinary commercial site.
    """,
)

SCHEMA_CTX = "https://schema.org"
ARTICLE_TYPES = {"Article", "BlogPosting", "NewsArticle", "TechArticle"}
LOCAL_TYPES = {"LocalBusiness", "Restaurant", "Store", "Dentist", "Plumber", "Electrician", "Attorney", "Hotel", "MedicalClinic", "AutoRepair", "HairSalon", "Bakery", "Cafe", "BarOrPub", "GymOrFitnessCenter", "RealEstateAgent", "ProfessionalService", "HomeAndConstructionBusiness"}
SUPPORTED = ["Article", "BlogPosting", "NewsArticle", "Product", "FAQPage", "LocalBusiness", "HowTo", "Organization", "Event", "Recipe", "BreadcrumbList"]

REQUIREMENTS: dict[str, dict[str, list[str]]] = {
    # Google: "There are no required properties" for Article; these five are its recommended list.
    "Article": {"required": [], "recommended": ["author", "dateModified", "datePublished", "headline", "image"]},
    "Product": {"required": ["name"], "recommended": ["image", "description", "sku", "brand", "offers", "aggregateRating", "review", "url"]},
    "FAQPage": {"required": ["mainEntity"], "recommended": []},
    "LocalBusiness": {"required": ["name", "address"], "recommended": ["telephone", "url", "openingHoursSpecification", "geo", "priceRange"]},
    "HowTo": {"required": ["name", "step"], "recommended": ["image", "totalTime", "estimatedCost", "supply", "tool", "description"]},
    # Google: "There are no required properties" for Organization.
    "Organization": {"required": [], "recommended": ["name", "url", "logo", "sameAs", "contactPoint", "description", "address"]},
    "Event": {"required": ["name", "startDate", "location"], "recommended": ["endDate", "description", "image", "offers", "eventStatus", "eventAttendanceMode", "organizer", "performer"]},
    "Recipe": {"required": ["name", "image"], "recommended": ["author", "datePublished", "description", "prepTime", "cookTime", "totalTime", "recipeYield", "recipeIngredient", "recipeInstructions", "nutrition", "keywords", "recipeCategory", "recipeCuisine", "aggregateRating"]},
    "BreadcrumbList": {"required": ["itemListElement"], "recommended": []},
}
ELIGIBILITY = {
    "Article": "Article rich result (Top stories / article carousel on AMP-less pages depends on site).",
    "Product": "Product snippet (price, availability, rating) when offers are present.",
    "FAQPage": "Valid, but Google shows FAQ rich results only for authoritative government/health sites (since Aug 2023).",
    "LocalBusiness": "Knowledge panel / local business details.",
    "HowTo": "Valid markup; HowTo rich results were retired in Sept 2023 — expect no visual result.",
    "Organization": "Knowledge panel logo/sameAs signals; no standalone visual result.",
    "Event": "Event rich result in Search.",
    "Recipe": "Recipe rich result (card / carousel) when image and key times are present.",
    "BreadcrumbList": "Breadcrumb trail replaces the URL in the snippet.",
}
AVAILABILITY = {"instock": "InStock", "in stock": "InStock", "in_stock": "InStock", "outofstock": "OutOfStock", "out of stock": "OutOfStock", "out_of_stock": "OutOfStock", "preorder": "PreOrder", "pre-order": "PreOrder", "backorder": "BackOrder", "discontinued": "Discontinued", "limited": "LimitedAvailability", "soldout": "SoldOut", "sold out": "SoldOut", "online only": "OnlineOnly", "in store only": "InStoreOnly"}
STRUCTURAL_TYPES = {"Offer", "AggregateOffer", "Brand", "AggregateRating", "Review", "Rating", "Person", "ImageObject", "PostalAddress", "GeoCoordinates", "OpeningHoursSpecification", "Place", "VirtualLocation", "ContactPoint", "HowToStep", "HowToSupply", "HowToTool", "HowToSection", "HowToDirection", "MonetaryAmount", "NutritionInformation", "Question", "Answer", "ListItem", "WebPage", "WebSite", "PerformingGroup", "SearchAction", "EntryPoint", "Thing", "VideoObject", "PropertyValue", "QuantitativeValue", "Audience", "Country", "City"}
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?)?$")
ISO_DURATION = re.compile(r"^P(?!$)(\d+Y)?(\d+M)?(\d+W)?(\d+D)?(T(?=\d)(\d+H)?(\d+M)?(\d+S)?)?$")
CURRENCY = re.compile(r"^[A-Z]{3}$")
DAY_MAP = {"mo": "Monday", "tu": "Tuesday", "we": "Wednesday", "th": "Thursday", "fr": "Friday", "sa": "Saturday", "su": "Sunday"}


def _is_url(v) -> bool:
    if not isinstance(v, str):
        return False
    p = urlparse(v)
    return p.scheme in ("http", "https") and bool(p.netloc)


def _norm_type(t: str) -> str:
    t = (t or "").strip()
    if t in ARTICLE_TYPES:
        return t
    if t in LOCAL_TYPES:
        return t
    for s in SUPPORTED:
        if s.lower() == t.lower():
            return s
    raise ToolError(f"Unsupported schema_type {t!r}. Supported: {', '.join(SUPPORTED)} (or a LocalBusiness subtype such as Restaurant, Dentist, Plumber).")


def _family(t: str) -> str:
    if t in ARTICLE_TYPES:
        return "Article"
    if t in LOCAL_TYPES:
        return "LocalBusiness"
    return t


def _date(v, name: str, warnings: list[str]) -> str | None:
    if v in (None, ""):
        return None
    s = str(v).strip()
    if ISO_DATE.match(s):
        return s
    for fmt in ("%Y-%m-%d %H:%M", "%d/%m/%Y", "%m/%d/%Y", "%B %d, %Y", "%d %B %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ToolError(f"{name}: cannot parse date {s!r}; use ISO 8601 like 2026-03-04T09:00:00+00:00.")


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v not in (None, "", [], {})}


def _hours(spec: list) -> list[dict]:
    out = []
    for h in spec:
        if not isinstance(h, dict):
            raise ToolError("opening_hours entries must be dicts like {'days': ['Mo','Tu'], 'opens': '09:00', 'closes': '17:00'}.")
        days = [DAY_MAP.get(str(x)[:2].lower(), str(x)) for x in (h.get("days") or [])]
        for t in (h.get("opens"), h.get("closes")):
            if not re.match(r"^\d{2}:\d{2}$", str(t or "")):
                raise ToolError(f"opening_hours opens/closes must be HH:MM (got {t!r}).")
        out.append({"@type": "OpeningHoursSpecification", "dayOfWeek": days, "opens": h["opens"], "closes": h["closes"]})
    return out


@AGENT.tool
def build_schema(schema_type: str, fields: dict) -> dict:
    """Generate valid JSON-LD for a page type from a flat dict of facts, nesting sub-objects and normalising formats.

    Keys by type — Article/BlogPosting/NewsArticle: headline, description, image (str or list), author_name,
    author_url, date_published, date_modified, publisher_name, publisher_logo, url. Product: name, description,
    image, brand, sku, gtin, url, price, currency, availability, price_valid_until, rating_value, review_count,
    condition. FAQPage: faqs=[{question, answer}]. LocalBusiness (or subtype): name, description, url, telephone,
    image, price_range, street, city, region, postal_code, country, latitude, longitude, opening_hours=[{days,
    opens, closes}], same_as=[urls]. HowTo: name, description, image, total_time (ISO 8601 or minutes),
    estimated_cost, currency, supplies=[str], tools=[str], steps=[{name, text, image, url}]. Organization: name,
    url, logo, description, same_as, telephone, email. Event: name, description, image, start_date, end_date,
    location_name, street, city, region, postal_code, country, online_url, organizer_name, organizer_url,
    performer_name, price, currency, ticket_url, status, attendance_mode. Recipe: name, image, description,
    author_name, date_published, prep_time, cook_time, total_time, yield, ingredients, instructions, category,
    cuisine, keywords, calories, rating_value, review_count. Unknown keys pass through as-is.

    Args:
        schema_type: One of Article, BlogPosting, NewsArticle, Product, FAQPage, LocalBusiness (or a subtype like Restaurant), HowTo, Organization, Event, Recipe.
        fields: Flat dict of facts for the page, using the keys listed above.
    """
    t = _norm_type(schema_type)
    if not isinstance(fields, dict) or not fields:
        raise ToolError("fields must be a non-empty dict of page facts.")
    if len(json.dumps(fields, default=str)) > 100_000:
        raise ToolError("fields too large (100k chars max).")
    f = dict(fields)
    warnings: list[str] = []
    fam = _family(t)
    ld: dict = {"@context": SCHEMA_CTX, "@type": t}

    def take(*keys):
        for k in keys:
            if k in f:
                return f.pop(k)
        return None

    def minutes_to_iso(v):
        if v in (None, ""):
            return None
        s = str(v).strip()
        if ISO_DURATION.match(s):
            return s
        try:
            m = int(float(s))
        except ValueError:
            raise ToolError(f"Duration {s!r} must be ISO 8601 (PT1H30M) or minutes.") from None
        return f"PT{m // 60}H{m % 60}M" if m >= 60 else f"PT{m}M"

    if fam == "Article":
        headline = take("headline", "title", "name")
        ld["headline"] = headline
        if headline and len(str(headline)) > 110:
            warnings.append("headline over 110 characters — Google truncates; shorten.")
        ld["description"] = take("description")
        img = take("image", "images")
        ld["image"] = img if isinstance(img, list) else ([img] if img else None)
        ld["datePublished"] = _date(take("date_published", "datePublished"), "date_published", warnings)
        ld["dateModified"] = _date(take("date_modified", "dateModified"), "date_modified", warnings)
        an = take("author_name", "author")
        if an:
            ld["author"] = _clean({"@type": take("author_type") or "Person", "name": an, "url": take("author_url")})
        pn = take("publisher_name", "publisher")
        if pn:
            logo = take("publisher_logo")
            ld["publisher"] = _clean({"@type": "Organization", "name": pn, "logo": {"@type": "ImageObject", "url": logo} if logo else None})
        url = take("url")
        if url:
            ld["mainEntityOfPage"] = {"@type": "WebPage", "@id": url}
    elif fam == "Product":
        ld["name"] = take("name", "title")
        ld["description"] = take("description")
        img = take("image", "images")
        ld["image"] = img if isinstance(img, list) else ([img] if img else None)
        brand = take("brand")
        if brand:
            ld["brand"] = {"@type": "Brand", "name": brand}
        ld["sku"] = take("sku")
        ld["gtin13"] = take("gtin", "gtin13")
        ld["url"] = take("url")
        price = take("price")
        if price is not None:
            ps = re.sub(r"[^\d.]", "", str(price))
            if not ps:
                raise ToolError(f"price {price!r} is not numeric.")
            cur = str(take("currency", "priceCurrency") or "USD").upper()
            if not CURRENCY.match(cur):
                raise ToolError(f"currency {cur!r} must be an ISO 4217 code like USD.")
            avail_raw = str(take("availability") or "in stock").strip()
            avail = AVAILABILITY.get(avail_raw.lower(), avail_raw.split("/")[-1])
            if avail not in set(AVAILABILITY.values()):
                raise ToolError(f"availability {avail_raw!r} not recognised; use in stock / out of stock / preorder / backorder / sold out / discontinued.")
            cond = str(take("condition") or "").strip().lower()
            cond_map = {"new": "NewCondition", "used": "UsedCondition", "refurbished": "RefurbishedCondition", "damaged": "DamagedCondition"}
            if cond and cond not in cond_map:
                raise ToolError("condition must be new, used, refurbished or damaged.")
            offer = _clean(
                {
                    "@type": "Offer",
                    "price": ps,
                    "priceCurrency": cur,
                    "availability": f"{SCHEMA_CTX}/{avail}",
                    "url": ld.get("url"),
                    "priceValidUntil": _date(take("price_valid_until"), "price_valid_until", warnings),
                    "itemCondition": (f"{SCHEMA_CTX}/{cond_map[cond]}" if cond else None),
                }
            )
            ld["offers"] = offer
        else:
            warnings.append("No price → no Offer; Product snippets require price + availability.")
        rv, rc = take("rating_value", "ratingValue"), take("review_count", "reviewCount")
        if rv is not None:
            try:
                rvf = float(rv)
            except (TypeError, ValueError):
                raise ToolError("rating_value must be a number.") from None
            if not 0 < rvf <= 5:
                raise ToolError("rating_value must be between 0 and 5 (default bestRating 5).")
            if not rc or int(rc) <= 0:
                raise ToolError("review_count must be a positive integer when rating_value is given.")
            ld["aggregateRating"] = {"@type": "AggregateRating", "ratingValue": str(rvf), "reviewCount": str(int(rc)), "bestRating": "5"}
    elif fam == "FAQPage":
        faqs = take("faqs", "questions", "mainEntity")
        if not isinstance(faqs, list) or not faqs:
            raise ToolError("FAQPage needs faqs=[{'question': str, 'answer': str}, ...].")
        ents = []
        for i, q in enumerate(faqs, 1):
            if not isinstance(q, dict) or not q.get("question") or not q.get("answer"):
                raise ToolError(f"faqs[{i}] needs both 'question' and 'answer'.")
            ents.append({"@type": "Question", "name": str(q["question"]).strip(), "acceptedAnswer": {"@type": "Answer", "text": str(q["answer"]).strip()}})
        ld["mainEntity"] = ents
        warnings.append(ELIGIBILITY["FAQPage"])
    elif fam == "LocalBusiness":
        ld["name"] = take("name")
        ld["description"] = take("description")
        ld["url"] = take("url")
        ld["telephone"] = take("telephone", "phone")
        img = take("image", "images")
        ld["image"] = img if isinstance(img, list) else ([img] if img else None)
        ld["priceRange"] = take("price_range", "priceRange")
        addr = _clean({"@type": "PostalAddress", "streetAddress": take("street", "streetAddress"), "addressLocality": take("city", "addressLocality"), "addressRegion": take("region", "state", "addressRegion"), "postalCode": take("postal_code", "postalCode", "zip"), "addressCountry": take("country", "addressCountry")})
        if len(addr) > 1:
            ld["address"] = addr
            for k in ("streetAddress", "addressLocality", "postalCode", "addressCountry"):
                if k not in addr:
                    warnings.append(f"address.{k} missing — Google wants a complete PostalAddress.")
        lat, lng = take("latitude", "lat"), take("longitude", "lng", "lon")
        if lat is not None and lng is not None:
            ld["geo"] = {"@type": "GeoCoordinates", "latitude": float(lat), "longitude": float(lng)}
        oh = take("opening_hours", "openingHoursSpecification")
        if oh:
            ld["openingHoursSpecification"] = _hours(oh)
        sa = take("same_as", "sameAs")
        if sa:
            ld["sameAs"] = sa if isinstance(sa, list) else [sa]
    elif fam == "HowTo":
        ld["name"] = take("name", "title")
        ld["description"] = take("description")
        img = take("image")
        ld["image"] = img
        ld["totalTime"] = minutes_to_iso(take("total_time", "totalTime"))
        cost = take("estimated_cost", "estimatedCost")
        if cost is not None:
            ld["estimatedCost"] = {"@type": "MonetaryAmount", "currency": str(take("currency") or "USD").upper(), "value": str(cost)}
        sup = take("supplies", "supply")
        if sup:
            ld["supply"] = [{"@type": "HowToSupply", "name": s} for s in (sup if isinstance(sup, list) else [sup])]
        tools = take("tools", "tool")
        if tools:
            ld["tool"] = [{"@type": "HowToTool", "name": s} for s in (tools if isinstance(tools, list) else [tools])]
        steps = take("steps", "step")
        if not isinstance(steps, list) or not steps:
            raise ToolError("HowTo needs steps=[{'name': str, 'text': str}, ...].")
        out_steps = []
        for i, s in enumerate(steps, 1):
            if isinstance(s, str):
                s = {"text": s}
            if not isinstance(s, dict) or not s.get("text"):
                raise ToolError(f"steps[{i}] needs 'text'.")
            out_steps.append(_clean({"@type": "HowToStep", "position": i, "name": s.get("name"), "text": s["text"], "image": s.get("image"), "url": s.get("url")}))
        ld["step"] = out_steps
        warnings.append(ELIGIBILITY["HowTo"])
    elif fam == "Organization":
        ld["name"] = take("name")
        ld["url"] = take("url")
        ld["logo"] = take("logo")
        ld["description"] = take("description")
        sa = take("same_as", "sameAs")
        if sa:
            ld["sameAs"] = sa if isinstance(sa, list) else [sa]
        tel, email = take("telephone", "phone"), take("email")
        if tel or email:
            ld["contactPoint"] = _clean({"@type": "ContactPoint", "telephone": tel, "email": email, "contactType": take("contact_type") or "customer service"})
    elif fam == "Event":
        ld["name"] = take("name")
        ld["description"] = take("description")
        ld["image"] = take("image")
        ld["startDate"] = _date(take("start_date", "startDate"), "start_date", warnings)
        ld["endDate"] = _date(take("end_date", "endDate"), "end_date", warnings)
        mode = str(take("attendance_mode") or ("online" if f.get("online_url") and not f.get("street") else "offline")).lower()
        ld["eventAttendanceMode"] = f"{SCHEMA_CTX}/" + {"online": "OnlineEventAttendanceMode", "offline": "OfflineEventAttendanceMode", "mixed": "MixedEventAttendanceMode"}.get(mode, "OfflineEventAttendanceMode")
        status = str(take("status") or "scheduled").lower()
        ld["eventStatus"] = f"{SCHEMA_CTX}/" + {"scheduled": "EventScheduled", "cancelled": "EventCancelled", "canceled": "EventCancelled", "postponed": "EventPostponed", "rescheduled": "EventRescheduled", "online": "EventMovedOnline"}.get(status, "EventScheduled")
        online = take("online_url")
        addr = _clean({"@type": "PostalAddress", "streetAddress": take("street"), "addressLocality": take("city"), "addressRegion": take("region"), "postalCode": take("postal_code"), "addressCountry": take("country")})
        place = _clean({"@type": "Place", "name": take("location_name", "venue"), "address": addr if len(addr) > 1 else None})
        if online and len(place) > 1:
            ld["location"] = [{"@type": "VirtualLocation", "url": online}, place]
        elif online:
            ld["location"] = {"@type": "VirtualLocation", "url": online}
        elif len(place) > 1:
            ld["location"] = place
        on = take("organizer_name", "organizer")
        if on:
            ld["organizer"] = _clean({"@type": "Organization", "name": on, "url": take("organizer_url")})
        pn = take("performer_name", "performer")
        if pn:
            ld["performer"] = {"@type": "PerformingGroup", "name": pn}
        price = take("price")
        if price is not None:
            ld["offers"] = _clean({"@type": "Offer", "price": re.sub(r"[^\d.]", "", str(price)) or "0", "priceCurrency": str(take("currency") or "USD").upper(), "url": take("ticket_url"), "availability": f"{SCHEMA_CTX}/InStock"})
    elif fam == "Recipe":
        ld["name"] = take("name", "title")
        img = take("image", "images")
        ld["image"] = img if isinstance(img, list) else ([img] if img else None)
        ld["description"] = take("description")
        an = take("author_name", "author")
        if an:
            ld["author"] = {"@type": "Person", "name": an}
        ld["datePublished"] = _date(take("date_published"), "date_published", warnings)
        ld["prepTime"] = minutes_to_iso(take("prep_time"))
        ld["cookTime"] = minutes_to_iso(take("cook_time"))
        ld["totalTime"] = minutes_to_iso(take("total_time"))
        ld["recipeYield"] = take("yield", "servings")
        ing = take("ingredients", "recipeIngredient")
        ld["recipeIngredient"] = ing if isinstance(ing, list) else ([ing] if ing else None)
        ins = take("instructions", "steps")
        if ins:
            ld["recipeInstructions"] = [{"@type": "HowToStep", "text": (s["text"] if isinstance(s, dict) else str(s))} for s in (ins if isinstance(ins, list) else [ins])]
        ld["recipeCategory"] = take("category")
        ld["recipeCuisine"] = take("cuisine")
        kw = take("keywords")
        ld["keywords"] = ", ".join(kw) if isinstance(kw, list) else kw
        cal = take("calories")
        if cal is not None:
            ld["nutrition"] = {"@type": "NutritionInformation", "calories": f"{cal} calories" if str(cal).replace('.', '').isdigit() else str(cal)}
        rv, rc = take("rating_value"), take("review_count")
        if rv is not None and rc:
            ld["aggregateRating"] = {"@type": "AggregateRating", "ratingValue": str(rv), "ratingCount": str(int(rc))}
    elif fam == "BreadcrumbList":
        raise ToolError("Use schema_markup__breadcrumbs_from_url for BreadcrumbList.")
    ld.update({k: v for k, v in f.items() if v not in (None, "")})  # pass-through
    ld = _clean(ld)
    report = _validate_obj(ld)
    warnings = list(dict.fromkeys(warnings + report["warnings"]))
    script = "<script type=\"application/ld+json\">\n" + json.dumps(ld, indent=2, ensure_ascii=False) + "\n</script>"
    return {
        "type": t,
        "jsonld": ld,
        "script_tag": script,
        "errors": report["errors"],
        "warnings": warnings,
        "missing_recommended": report["missing_recommended"],
        "eligibility": ELIGIBILITY.get(fam, ""),
        "verdict": ("Valid — no errors." if not report["errors"] else f"{len(report['errors'])} error(s) block rich results.") + (f" {len(report['missing_recommended'])} recommended propert(y/ies) missing." if report["missing_recommended"] else ""),
    }


def _validate_obj(obj: dict, path: str = "") -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    missing_rec: list[str] = []
    t = obj.get("@type")
    if isinstance(t, list):
        t = t[0] if t else None
    if not t:
        errors.append(f"{path or 'root'}: missing @type")
        return {"errors": errors, "warnings": warnings, "missing_recommended": missing_rec, "type": None}
    fam = _family(str(t))
    req = REQUIREMENTS.get(fam)
    if req is None:
        if str(t) not in STRUCTURAL_TYPES and not path:
            warnings.append(f"@type {t} has no Google rich-result definition here; validated structurally only.")
    else:
        for k in req["required"]:
            if k not in obj or obj[k] in ("", None, [], {}):
                errors.append(f"{t}: required property '{k}' missing")
        for k in req["recommended"]:
            if k not in obj or obj[k] in ("", None, [], {}):
                missing_rec.append(k)
    # formats
    for k, v in obj.items():
        if k.startswith("@"):
            continue
        if k in ("datePublished", "dateModified", "startDate", "endDate", "priceValidUntil", "validFrom") and isinstance(v, str):
            if not ISO_DATE.match(v):
                errors.append(f"{t}.{k}: '{v}' is not ISO 8601 (YYYY-MM-DD or full datetime with offset)")
            elif "T" in v and not re.search(r"(Z|[+-]\d{2}:?\d{2})$", v):
                warnings.append(f"{t}.{k}: datetime has no timezone offset")
        if k in ("totalTime", "prepTime", "cookTime", "performTime") and isinstance(v, str) and not ISO_DURATION.match(v):
            errors.append(f"{t}.{k}: '{v}' is not an ISO 8601 duration (e.g. PT30M)")
        if k in ("url", "logo", "sameAs", "image") or k == "@id":
            vals = v if isinstance(v, list) else [v]
            for x in vals:
                if isinstance(x, str) and not _is_url(x):
                    errors.append(f"{t}.{k}: '{x[:60]}' must be an absolute http(s) URL")
        if k == "price":
            if not re.match(r"^\d+(\.\d+)?$", str(v)):
                errors.append(f"{t}.price: '{v}' must be a plain number (no currency symbol)")
        if k == "priceCurrency" and not CURRENCY.match(str(v)):
            errors.append(f"{t}.priceCurrency: '{v}' must be ISO 4217 (e.g. USD)")
        if k == "availability" and not str(v).split("/")[-1] in set(AVAILABILITY.values()):
            errors.append(f"{t}.availability: '{v}' is not a schema.org ItemAvailability value")
        if k == "ratingValue":
            try:
                rv = float(v)
                best = float(obj.get("bestRating", 5))
                if not 0 < rv <= best:
                    errors.append(f"{t}.ratingValue {rv} outside 0-{best:g}")
            except (TypeError, ValueError):
                errors.append(f"{t}.ratingValue must be numeric")
        if k in ("reviewCount", "ratingCount"):
            try:
                if int(v) <= 0:
                    errors.append(f"{t}.{k} must be > 0")
            except (TypeError, ValueError):
                errors.append(f"{t}.{k} must be an integer")
        if k == "headline" and isinstance(v, str) and len(v) > 110:
            warnings.append("Article.headline over 110 chars — will be truncated")
        if k == "telephone" and isinstance(v, str) and not v.strip().startswith("+"):
            warnings.append(f"{t}.telephone should start with a country code")
        # recurse into nested objects
        children = v if isinstance(v, list) else [v]
        for i, ch in enumerate(children):
            if isinstance(ch, dict) and "@type" in ch:
                sub = _validate_obj(ch, f"{path + '.' if path else ''}{k}[{i}]" if isinstance(v, list) else f"{path + '.' if path else ''}{k}")
                errors += sub["errors"]
                warnings += sub["warnings"]
    # type-specific structure
    if fam == "FAQPage":
        me = obj.get("mainEntity") or []
        if not isinstance(me, list):
            me = [me]
        for i, q in enumerate(me):
            if not isinstance(q, dict) or q.get("@type") != "Question" or not q.get("name"):
                errors.append(f"FAQPage.mainEntity[{i}]: must be a Question with 'name'")
            elif not isinstance(q.get("acceptedAnswer"), dict) or not q["acceptedAnswer"].get("text"):
                errors.append(f"FAQPage.mainEntity[{i}]: Question needs acceptedAnswer.text")
        if len(me) < 2:
            warnings.append("FAQPage with fewer than 2 questions is unusual")
    if fam == "HowTo":
        steps = obj.get("step") or []
        for i, s in enumerate(steps if isinstance(steps, list) else [steps]):
            if not isinstance(s, dict) or not s.get("text"):
                errors.append(f"HowTo.step[{i}]: HowToStep needs 'text'")
    if fam == "BreadcrumbList":
        items = obj.get("itemListElement") or []
        for i, it in enumerate(items):
            if not isinstance(it, dict) or it.get("@type") != "ListItem":
                errors.append(f"BreadcrumbList.itemListElement[{i}] must be a ListItem")
                continue
            if it.get("position") != i + 1:
                errors.append(f"BreadcrumbList.itemListElement[{i}]: position should be {i + 1}, got {it.get('position')}")
            if not it.get("name"):
                errors.append(f"BreadcrumbList.itemListElement[{i}]: missing name")
            if i < len(items) - 1 and not it.get("item"):
                errors.append(f"BreadcrumbList.itemListElement[{i}]: non-final items need 'item' URL")
    if fam == "Product":
        if not any(k in obj for k in ("offers", "review", "aggregateRating")):
            errors.append("Product: needs at least one of offers, review or aggregateRating for a rich result")
        offers = obj.get("offers")
        for o in offers if isinstance(offers, list) else ([offers] if offers else []):
            if isinstance(o, dict):
                if o.get("@type") == "AggregateOffer":
                    for k in ("lowPrice", "priceCurrency"):
                        if k not in o:
                            errors.append(f"Product.offers (AggregateOffer): missing {k}")
                else:
                    ps = o.get("priceSpecification") if isinstance(o.get("priceSpecification"), dict) else {}
                    if "price" not in o and "price" not in ps:
                        errors.append("Product.offers: missing price")
                    if "priceCurrency" not in o and "priceCurrency" not in ps:
                        warnings.append("Product.offers.priceCurrency missing — recommended for product snippets, required for merchant listings")
                if "availability" not in o:
                    warnings.append("Product.offers.availability missing — recommended for product snippets")
    if t == "AggregateRating":
        if obj.get("ratingValue") in (None, ""):
            errors.append("AggregateRating: required property 'ratingValue' missing")
        if obj.get("ratingCount") in (None, "") and obj.get("reviewCount") in (None, ""):
            errors.append("AggregateRating: needs ratingCount or reviewCount")
        if not path and "itemReviewed" not in obj:
            errors.append("AggregateRating: top-level rating needs itemReviewed")
    if t == "Review":
        if not obj.get("author"):
            errors.append(f"{path or 'Review'}: Review needs an author (Person or Organization with name)")
        rr = obj.get("reviewRating")
        if not isinstance(rr, dict) or rr.get("ratingValue") in (None, ""):
            errors.append(f"{path or 'Review'}: Review needs reviewRating.ratingValue")
        if not path and "itemReviewed" not in obj:
            errors.append("Review: top-level review needs itemReviewed")
    if fam in ("LocalBusiness", "Organization") and ("review" in obj or "aggregateRating" in obj):
        warnings.append(f"{t}: self-serving reviews/ratings on LocalBusiness/Organization are ignored by Google (and against guidelines)")
    if fam == "Article":
        a = obj.get("author")
        if isinstance(a, dict) and not a.get("name"):
            errors.append("Article.author needs a name")
        if isinstance(a, str):
            warnings.append("Article.author should be a Person/Organization object with name (and url)")
    if fam == "Event":
        loc = obj.get("location")
        locs = loc if isinstance(loc, list) else ([loc] if loc else [])
        for l in locs:
            if isinstance(l, dict) and l.get("@type") == "Place" and not l.get("address"):
                errors.append("Event.location (Place) needs an address")
    return {"errors": errors, "warnings": warnings, "missing_recommended": missing_rec, "type": t}


def _parse_jsonld(text: str) -> list[dict]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ToolError(f"JSON does not parse: {e.msg} at line {e.lineno} col {e.colno}.") from None
    if isinstance(data, list):
        objs = data
    elif isinstance(data, dict) and "@graph" in data:
        objs = data["@graph"] if isinstance(data["@graph"], list) else [data["@graph"]]
        if "@context" not in data:
            raise ToolError("@graph document is missing @context.")
        for o in objs:
            if isinstance(o, dict):
                o.setdefault("@context", data["@context"])
    elif isinstance(data, dict):
        objs = [data]
    else:
        raise ToolError("JSON-LD must be an object or an array of objects.")
    return [o for o in objs if isinstance(o, dict)]


@AGENT.tool
def validate_schema(jsonld: str) -> dict:
    """Validate JSON-LD text against Google's rich-result requirements: parse, @context/@type, required and recommended properties, formats, nesting.

    Accepts a single object, an array, or an @graph document. Returns errors (block rich results),
    warnings (reduce eligibility), missing recommended properties per object, and eligibility notes.

    Args:
        jsonld: The JSON-LD text (with or without the surrounding script tag).
    """
    s = (jsonld or "").strip()
    if not s:
        raise ToolError("jsonld is empty.")
    if len(s) > 200_000:
        raise ToolError("jsonld too large (200k chars max).")
    s = re.sub(r"^\s*<script[^>]*>|</script>\s*$", "", s, flags=re.I).strip()
    objs = _parse_jsonld(s)
    if not objs:
        raise ToolError("No JSON-LD objects found.")
    results, all_err, all_warn = [], [], []
    for i, o in enumerate(objs):
        ctx = str(o.get("@context", ""))
        errs = []
        if "schema.org" not in ctx:
            errs.append(f"object[{i}]: @context must be https://schema.org (got {ctx or 'none'!r})")
        elif ctx.startswith("http://"):
            all_warn.append(f"object[{i}]: use https://schema.org as @context")
        r = _validate_obj(o)
        errs += r["errors"]
        fam = _family(str(r["type"])) if r["type"] else None
        results.append({"index": i, "type": r["type"], "errors": errs, "warnings": r["warnings"], "missing_recommended": r["missing_recommended"], "eligibility": ELIGIBILITY.get(fam or "", "no Google rich result for this type")})
        all_err += errs
        all_warn += r["warnings"]
    types = [str(r["type"]) for r in results]
    dup_types = sorted({t for t in types if types.count(t) > 1})
    if dup_types:
        all_warn.append(f"Duplicate top-level types: {', '.join(dup_types)} — merge into one block per type.")
    return {
        "objects": results,
        "error_count": len(all_err),
        "warning_count": len(all_warn),
        "errors": all_err,
        "warnings": all_warn,
        "verdict": ("Passes: no errors." if not all_err else f"{len(all_err)} error(s) — fix before shipping.") + (f" {len(all_warn)} warning(s)." if all_warn else ""),
    }


@AGENT.tool
def extract_schema(html: str) -> dict:
    """Pull every JSON-LD block out of a page's HTML, validate each, and report microdata/RDFa presence.

    Args:
        html: The raw HTML source of the page.
    """
    page = c.parse_html(html)
    blocks = []
    types_found = []
    parsed_objs: list[dict] = []
    total_err = 0
    for i, raw in enumerate(page.jsonld):
        if not raw.strip():
            blocks.append({"index": i, "parse_error": "empty script block", "objects": []})
            continue
        try:
            objs = _parse_jsonld(raw)
        except ToolError as e:
            blocks.append({"index": i, "parse_error": str(e), "objects": []})
            total_err += 1
            continue
        vals = []
        for o in objs:
            parsed_objs.append(o)
            r = _validate_obj(o)
            types_found.append(str(r["type"]))
            vals.append({"type": r["type"], "errors": r["errors"], "warnings": r["warnings"], "missing_recommended": r["missing_recommended"]})
            total_err += len(r["errors"])
        blocks.append({"index": i, "objects": vals, "raw_chars": len(raw)})
    microdata = len(re.findall(r"\bitemscope\b", html, re.I))
    rdfa = len(re.findall(r"\btypeof\s*=", html, re.I))
    recs = []
    fams = {_family(t) for t in types_found}
    if not page.jsonld:
        recs.append("No JSON-LD found — add the primary type for this page.")
    if "BreadcrumbList" not in fams:
        recs.append("Add BreadcrumbList.")
    if "Organization" not in fams and "WebSite" not in types_found:
        recs.append("Add Organization (site-wide) for brand signals.")
    if microdata and page.jsonld:
        recs.append(f"{microdata} microdata itemscope(s) alongside JSON-LD — consolidate to JSON-LD to avoid conflicting values.")
    dup = sorted({t for t in types_found if types_found.count(t) > 1})
    conflicts = _conflicts(parsed_objs, dup)
    if dup:
        recs.append(f"Duplicate types across blocks: {', '.join(dup)}." + (" Conflicting values: " + "; ".join(conflicts) + " — keep one block (usually the plugin's) and delete the other." if conflicts else ""))
    return {
        "jsonld_blocks": len(page.jsonld),
        "types": types_found,
        "blocks": blocks,
        "microdata_itemscopes": microdata,
        "rdfa_typeof": rdfa,
        "error_count": total_err,
        "conflicting_values": conflicts,
        "recommendations": recs,
        "verdict": (f"{len(page.jsonld)} JSON-LD block(s), types: {', '.join(types_found) or 'none'}; {total_err} error(s)."),
    }


def _conflicts(objs: list[dict], dup_types: list[str]) -> list[str]:
    """Compare same-type objects on the values Google reads most (name, price, currency, availability, rating)."""
    out = []

    def facts(o: dict) -> dict:
        f = {"name": o.get("name") or o.get("headline")}
        off = o.get("offers")
        off = off[0] if isinstance(off, list) and off else off
        if isinstance(off, dict):
            price = re.sub(r"[^\d.]", "", str(off.get("price") or off.get("lowPrice") or ""))
            avail = re.sub(r"[\s_-]", "", str(off.get("availability") or "").split("/")[-1]).lower()
            f.update({"offers.price": price or None, "offers.priceCurrency": off.get("priceCurrency"), "offers.availability": avail or None})
        ar = o.get("aggregateRating")
        if isinstance(ar, dict):
            f["aggregateRating.ratingValue"] = ar.get("ratingValue")
        return {k: str(v) for k, v in f.items() if v not in (None, "")}

    for t in dup_types:
        group = [facts(o) for o in objs if str(o.get("@type")) == t]
        keys = set().union(*group) if group else set()
        for k in sorted(keys):
            vals = sorted({g[k] for g in group if k in g})
            if len(vals) > 1:
                out.append(f"{t}.{k}: {' vs '.join(repr(v) for v in vals)}")
    return out


@AGENT.tool
def breadcrumbs_from_url(url: str, site_name: str = "Home", labels: dict[str, str] | None = None) -> dict:
    """Build a BreadcrumbList JSON-LD from a URL path with correct positions, absolute item URLs and humanised names.

    Args:
        url: The page's absolute URL, e.g. https://example.com/blog/seo/title-tags.
        site_name: Name for the first (home) crumb.
        labels: Optional {path segment: display label} overrides, e.g. {"seo": "SEO Guides"}.
    """
    u = url.strip()
    if not _is_url(u):
        raise ToolError("url must be absolute, e.g. https://example.com/blog/post.")
    p = urlparse(u)
    segs = [s for s in p.path.split("/") if s]
    if len(segs) > 12:
        raise ToolError("URL has more than 12 path segments — unlikely to be a real page path.")
    base = f"{p.scheme}://{p.netloc}"
    labels = {k.lower(): v for k, v in (labels or {}).items()}
    items = [{"@type": "ListItem", "position": 1, "name": site_name, "item": base + "/"}]
    path = ""
    for i, seg in enumerate(segs, 2):
        path += "/" + seg
        name = labels.get(seg.lower())
        if not name:
            clean = re.sub(r"\.(html?|php|aspx?)$", "", seg)
            clean = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", clean)
            name = " ".join(w.capitalize() if w.lower() not in ("and", "or", "of", "the", "a", "in", "for", "to") or j == 0 else w.lower() for j, w in enumerate(re.split(r"[-_+]+", clean) if clean else [seg]))
            name = re.sub(r"\b(Seo|Faq|Api|Crm|Ai|Ux|Ui)\b", lambda m: m.group(0).upper(), name)
        item = {"@type": "ListItem", "position": i, "name": name}
        if i < len(segs) + 1:
            item["item"] = base + path + ("/" if u.rstrip("/").endswith(seg) and u.endswith("/") else "")
        items.append(item)
    ld = {"@context": SCHEMA_CTX, "@type": "BreadcrumbList", "itemListElement": items}
    report = _validate_obj(ld)
    return {
        "jsonld": ld,
        "script_tag": "<script type=\"application/ld+json\">\n" + json.dumps(ld, indent=2, ensure_ascii=False) + "\n</script>",
        "trail": " › ".join(i["name"] for i in items),
        "depth": len(items),
        "errors": report["errors"],
        "note": "Names are derived from URL slugs — replace any that don't match the visible breadcrumb on the page." if not labels else "",
    }
