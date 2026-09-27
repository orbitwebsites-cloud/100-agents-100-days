"""Programmatic SEO tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("programmatic-seo")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_plan_combinations_counts_and_validates_templates():
    out = call("plan_combinations", dimensions={"tool": ["CRM", "Email tool", "crm"], "industry": ["dental", "legal"], "city": ["Austin", "Boston", "São Paulo"]}, title_template="Best {tool} for {industry} in {city} (2026)", url_template="/{tool}/{city}/", sample=4)
    assert out["total_pages"] == 12
    assert out["per_dimension"] == {"tool": 2, "industry": 2, "city": 3}
    assert out["biggest_multiplier"] == "city"
    assert any("industry" in t and "not used" in t for t in out["template_issues"])
    assert any("duplicate values" in w for w in out["warnings"])
    assert out["samples"][0]["title"] == "Best CRM for dental in Austin (2026)"
    assert out["samples"][0]["url"] == "/crm/austin/"
    assert len(out["samples"]) == 4
    big = call("plan_combinations", dimensions={"a": [str(i) for i in range(400)], "b": [str(i) for i in range(300)]})
    assert big["total_pages"] == 120000 and big["tier"] == "very large" and big["sitemaps_needed"] == 3
    with pytest.raises(ToolError):
        call("plan_combinations", dimensions={"a": []})
    with pytest.raises(ToolError):
        call("plan_combinations", dimensions={"a": ["x"]}, title_template="{a}", sample=0)


def test_slugify_batch_transliterates_and_finds_collisions():
    out = call("slugify_batch", items=["Café Crème & Co.", "cafe creme and co", "The Best of 2026!", "123", "São Paulo dentists — cosmetic & general — top rated list 2026 edition"], max_length=40)
    slugs = [s["slug"] for s in out["slugs"]]
    assert slugs[:4] == ["cafe-creme-and-co", "cafe-creme-and-co", "the-best-of-2026", "123"]
    assert slugs[4] == "sao-paulo-dentists-cosmetic-and-general" and len(slugs[4]) <= 40
    assert out["collisions"] == [{"slug": "cafe-creme-and-co", "inputs": ["Café Crème & Co.", "cafe creme and co"]}]
    assert "digits only — add a word" in out["slugs"][3]["issues"]
    assert any("truncated" in i for i in out["slugs"][4]["issues"])
    stop = call("slugify_batch", items=["The Best of 2026"], drop_stopwords=True)
    assert stop["slugs"][0]["slug"] == "best-2026"
    with pytest.raises(ToolError):
        call("slugify_batch", items=[])
    with pytest.raises(ToolError):
        call("slugify_batch", items=["x"], max_length=5)


def test_near_duplicates_measures_boilerplate_and_clusters():
    base = "Best plumbers in {c}. We compared 40 plumbers in {c} on price, response time and reviews. Call today for a free quote in {c}. Our rating method is transparent and updated monthly."
    pages = [{"id": c, "text": base.format(c=c)} for c in ["Austin", "Boston", "Denver", "Miami"]]
    pages.append({"id": "Nome", "text": "Plumbers in Nome. Average price $180, 3 licensed plumbers, winter freeze issues common. Response time 2 days. Local codes require permit for water heater. " * 3})
    pages.append({"id": "Austin-copy", "text": base.format(c="Austin") + " Extra line."})
    out = call("near_duplicates", pages=pages)
    assert out["passes_gate"] is False
    assert out["boilerplate_ratio"] > 0.5
    assert out["median_unique_share"] < 0.4
    assert out["duplicate_clusters"] == [["Austin", "Austin-copy"]]
    assert out["near_duplicate_pairs"][0]["similarity"] > 0.8
    assert "Nome" in out["thin_pages"]
    unique = call("near_duplicates", pages=[{"id": "a", "text": "alpha beta gamma delta epsilon zeta eta theta " * 5}, {"id": "b", "text": "one two three four five six seven eight nine " * 5}])
    assert unique["passes_gate"] is True and unique["boilerplate_ratio"] == 0.0
    with pytest.raises(ToolError):
        call("near_duplicates", pages=[{"id": "a", "text": "x"}])
    with pytest.raises(ToolError):
        call("near_duplicates", pages=[{"id": "a", "text": "x y z"}, {"id": "b", "text": "   "}])


def test_linking_architecture():
    out = call("linking_architecture", page_count=12000, links_per_hub=100)
    assert out["hub_levels"] == [120, 2]
    assert out["total_hub_pages"] == 122
    # home → 2 top hubs → 120 leaf hubs → page = 3 clicks (the playbook's ≤ 3 rule)
    assert out["click_depth_from_home"] == 3 and out["depth_ok"]
    via_categories = call("linking_architecture", page_count=12000, links_per_hub=100, existing_authority_pages=5)
    assert via_categories["hub_levels"] == [120] and via_categories["click_depth_from_home"] == 3
    assert out["sitemaps"] == 1
    assert out["rollout"] == {"phase_1_pages": 1200, "phase_1_gate": "≥ 60% indexed and impressions on ≥ 30% of pages at 4 weeks", "remaining_pages": 10800, "weeks": 8, "pages_per_week": 1350}
    small = call("linking_architecture", page_count=80)
    assert small["hub_levels"] == [] and small["click_depth_from_home"] == 1
    huge = call("linking_architecture", page_count=2_000_000, links_per_hub=50)
    assert huge["sitemaps"] == 40 and huge["depth_ok"] is False
    with pytest.raises(ToolError):
        call("linking_architecture", page_count=0)
