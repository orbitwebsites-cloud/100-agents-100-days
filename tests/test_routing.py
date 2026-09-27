"""Type anything and it works: hundred_start picks the agent from the user's words."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from hundred.server.mcp_server import call_tool, resolve_access
from hundred.server.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "r.db"))


def access_for(store, **lic):
    if not lic:
        return resolve_access(store, SimpleNamespace(query_params={}, headers={}, scope={}))
    key, _ = store.create_license(email="r@x.co", status="active", source="comp", **lic)
    return resolve_access(store, SimpleNamespace(query_params={"key": key}, headers={}, scope={}))


@pytest.mark.parametrize("task,expected", [
    ("write me a cold email to a VP of operations", "Cold Email Closer"),
    ("forecast our cash for the next 13 weeks", "Cash Flow Forecaster"),
    ("is this contract safe to sign? it auto-renews", "Contract Reviewer"),
    ("my A/B test: 480 vs 540 conversions, is it significant", "A/B Test Analyst"),
    ("turn this meeting transcript into tasks", "Meeting Ops"),
    ("plan my workouts, I squat 100kg for 5", "Fitness Coach"),
])
def test_auto_pick_with_all_access(store, task, expected):
    access = access_for(store, plan="all", all_access=True)
    res = call_tool(store, access, "hundred_start", {"task": task})
    assert not res.is_error and f"# {expected} — operating procedure" in res.content[0].text


def test_free_user_gets_the_free_agent_or_a_clear_upgrade(store):
    access = access_for(store)
    ok = call_tool(store, access, "hundred_start", {"task": "summarize this meeting transcript"})
    assert not ok.is_error and "Meeting Ops" in ok.content[0].text
    up = call_tool(store, access, "hundred_start", {"task": "write a cold email sequence"})
    assert "Cold Email Closer" in up.content[0].text and "$4.99" in up.content[0].text


def test_owned_near_match_is_used_and_the_better_agent_is_mentioned(store):
    access = access_for(store, plan="single", agents=["linkedin-prospector"])
    res = call_tool(store, access, "hundred_start", {"task": "write a linkedin post about our launch"})
    text = res.content[0].text
    assert not res.is_error and "LinkedIn Prospector — operating procedure" in text and "LinkedIn Ghostwriter" in text


def test_a_poor_fit_is_not_forced_the_better_agent_is_offered(store):
    access = access_for(store, plan="single", agents=["email-campaign"])
    text = call_tool(store, access, "hundred_start", {"task": "write a cold email sequence for prospects"}).content[0].text
    assert "Cold Email Closer" in text and "$4.99" in text


def test_search_marks_owned(store):
    access = access_for(store, plan="single", agents=["seo-auditor"])
    import json

    found = json.loads(call_tool(store, access, "hundred_find_agent", {"query": "audit my page's seo"}).content[0].text)
    assert found[0]["agent"] == "seo-auditor" and found[0]["owned"] is True
    assert any(not f["owned"] for f in found)
