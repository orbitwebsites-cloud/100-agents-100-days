"""Schema Markup Builder tools."""

import json

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("schema-markup")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_build_product_nests_offer_and_normalises():
    out = call("build_schema", schema_type="Product", fields={"name": "Stride Runner", "price": "$129.99", "currency": "usd", "availability": "in stock", "brand": "Stride", "rating_value": 4.6, "review_count": 212, "url": "https://stride.com/runner", "condition": "new"})
    ld = out["jsonld"]
    assert ld["@context"] == "https://schema.org" and ld["@type"] == "Product"
    assert ld["offers"] == {"@type": "Offer", "price": "129.99", "priceCurrency": "USD", "availability": "https://schema.org/InStock", "url": "https://stride.com/runner", "itemCondition": "https://schema.org/NewCondition"}
    assert ld["brand"] == {"@type": "Brand", "name": "Stride"}
    assert ld["aggregateRating"]["reviewCount"] == "212"
    assert out["errors"] == []
    assert "image" in out["missing_recommended"]
    assert out["script_tag"].startswith('<script type="application/ld+json">')
    json.loads(out["script_tag"].split(">", 1)[1].rsplit("<", 1)[0])


def test_build_article_parses_dates_and_flags_missing():
    out = call("build_schema", schema_type="BlogPosting", fields={"headline": "How to brew", "image": "https://x.com/a.jpg", "date_published": "March 4, 2026", "author_name": "Ana", "url": "https://x.com/brew"})
    ld = out["jsonld"]
    assert ld["datePublished"] == "2026-03-04"
    assert ld["author"] == {"@type": "Person", "name": "Ana"}
    assert ld["mainEntityOfPage"]["@id"] == "https://x.com/brew"
    assert "dateModified" in out["missing_recommended"]
    assert out["errors"] == []


def test_build_local_business_hours_and_faq_and_howto():
    lb = call("build_schema", schema_type="Restaurant", fields={"name": "Cafe", "street": "1 Main St", "city": "Austin", "postal_code": "78701", "country": "US", "telephone": "+1-512-555-0100", "opening_hours": [{"days": ["Mo", "Tu"], "opens": "09:00", "closes": "17:00"}]})
    assert lb["jsonld"]["openingHoursSpecification"][0]["dayOfWeek"] == ["Monday", "Tuesday"]
    assert lb["jsonld"]["address"]["addressLocality"] == "Austin"
    assert lb["errors"] == []
    faq = call("build_schema", schema_type="FAQPage", fields={"faqs": [{"question": "Q1", "answer": "A1"}, {"question": "Q2", "answer": "A2"}]})
    assert len(faq["jsonld"]["mainEntity"]) == 2 and faq["jsonld"]["mainEntity"][0]["acceptedAnswer"]["text"] == "A1"
    assert "authoritative" in faq["eligibility"]
    ht = call("build_schema", schema_type="HowTo", fields={"name": "Fix", "steps": ["Do a", {"name": "B", "text": "Do b"}], "total_time": 90})
    assert ht["jsonld"]["totalTime"] == "PT1H30M"
    assert ht["jsonld"]["step"][1] == {"@type": "HowToStep", "position": 2, "name": "B", "text": "Do b"}


def test_build_schema_rejects_bad_input():
    with pytest.raises(ToolError):
        call("build_schema", schema_type="Spaceship", fields={"name": "x"})
    with pytest.raises(ToolError):
        call("build_schema", schema_type="Product", fields={"name": "x", "price": "abc"})
    with pytest.raises(ToolError):
        call("build_schema", schema_type="Product", fields={"name": "x", "rating_value": 7, "review_count": 3})
    with pytest.raises(ToolError):
        call("build_schema", schema_type="FAQPage", fields={"faqs": [{"question": "q"}]})
    with pytest.raises(ToolError):
        call("build_schema", schema_type="Article", fields={"headline": "h", "date_published": "yesterday"})


def test_validate_schema_finds_format_and_required_errors():
    bad = '<script type="application/ld+json">{"@context":"https://schema.org","@type":"Product","name":"X","offers":{"@type":"Offer","price":"$12","priceCurrency":"usd"}}</script>'
    out = call("validate_schema", jsonld=bad)
    assert out["error_count"] == 2
    assert any("plain number" in e for e in out["errors"])
    assert any("ISO 4217" in e for e in out["errors"])
    assert any("availability" in w for w in out["warnings"])
    graph = json.dumps({"@context": "https://schema.org", "@graph": [{"@type": "Article", "headline": "H", "image": "https://a.com/i.jpg", "datePublished": "2026-01-01T09:00:00"}, {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 2, "name": "Home", "item": "https://a.com/"}]}]})
    g = call("validate_schema", jsonld=graph)
    assert g["errors"] == ["BreadcrumbList.itemListElement[0]: position should be 1, got 2"]
    assert any("timezone" in w for w in g["warnings"])
    assert g["objects"][0]["missing_recommended"] == ["author", "dateModified"]


def test_google_required_properties_match_docs():
    # Article and Organization have no required properties per Google; missing ones are warnings only.
    art = call("validate_schema", jsonld='{"@context":"https://schema.org","@type":"Article","headline":"H"}')
    assert art["errors"] == []
    assert set(art["objects"][0]["missing_recommended"]) == {"author", "dateModified", "datePublished", "image"}
    org = call("validate_schema", jsonld='{"@context":"https://schema.org","@type":"Organization","name":"Acme"}')
    assert org["errors"] == []
    # AggregateRating needs ratingCount or reviewCount; a nested Review needs author + reviewRating.
    prod = call("validate_schema", jsonld=json.dumps({"@context": "https://schema.org", "@type": "Product", "name": "X", "aggregateRating": {"@type": "AggregateRating", "ratingValue": "4.5"}, "review": [{"@type": "Review", "reviewBody": "ok"}]}))
    assert any("ratingCount or reviewCount" in e for e in prod["errors"])
    assert any("needs an author" in e for e in prod["errors"])
    assert any("reviewRating.ratingValue" in e for e in prod["errors"])
    # Offer without priceCurrency: a warning for product snippets, not an error.
    off = call("validate_schema", jsonld='{"@context":"https://schema.org","@type":"Product","name":"X","offers":{"@type":"Offer","price":"5","availability":"https://schema.org/InStock"}}')
    assert off["errors"] == [] and any("priceCurrency" in w for w in off["warnings"])


def test_validate_schema_bad_input():
    with pytest.raises(ToolError):
        call("validate_schema", jsonld="{not json")
    with pytest.raises(ToolError):
        call("validate_schema", jsonld="")


def test_extract_schema_from_html():
    html = ('<html><head><script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization","name":"A","url":"https://a.com"}</script>'
            '<script type="application/ld+json">{bad</script></head><body><div itemscope itemtype="https://schema.org/Thing"></div></body></html>')
    out = call("extract_schema", html=html)
    assert out["jsonld_blocks"] == 2
    assert out["types"] == ["Organization"]
    assert out["blocks"][1]["parse_error"].startswith("JSON does not parse")
    assert out["microdata_itemscopes"] == 1
    assert "Add BreadcrumbList." in out["recommendations"]
    with pytest.raises(ToolError):
        call("extract_schema", html="")


def test_breadcrumbs_from_url():
    out = call("breadcrumbs_from_url", url="https://example.com/blog/seo/title-tags.html", labels={"blog": "Blog"})
    items = out["jsonld"]["itemListElement"]
    assert out["trail"] == "Home › Blog › SEO › Title Tags"
    assert [i["position"] for i in items] == [1, 2, 3, 4]
    assert items[1]["item"] == "https://example.com/blog"
    assert "item" not in items[-1]
    assert out["errors"] == []
    with pytest.raises(ToolError):
        call("breadcrumbs_from_url", url="/relative/path")
