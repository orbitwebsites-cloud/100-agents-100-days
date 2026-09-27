"""Memory (agents remember across chats) and recipes (agents work in sequence)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from hundred import memory, recipes, registry
from hundred.server.mcp_server import call_tool, resolve_access
from hundred.server.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "m.db"))


def req(key: str = "", **query):
    params = dict(query)
    if key:
        params["key"] = key
    return SimpleNamespace(query_params=params, headers={}, scope={})


def mem(store, key, **args):
    res = call_tool(store, resolve_access(store, req(key)), "hundred_memory", args)
    return res.is_error, res.content[0].text


def licensed(store, **kw):
    kw.setdefault("plan", "all")
    kw.setdefault("status", "active")
    kw.setdefault("all_access", True)
    key, lic = store.create_license(email="m@x.co", source="stripe", subscription_id=kw.pop("sub", "sub_m"), **kw)
    return key, lic


# ── memory ──────────────────────────────────────────────────
def test_save_get_list_delete_roundtrip(store):
    key, _ = licensed(store)
    profile = {"avg_sentence_words": 12.4, "banned": ["leverage"], "signature": ["receipts"]}
    assert mem(store, key, action="save", name="brand-voice/fernhill", value=profile, note="voice profile")[0] is False
    err, out = mem(store, key, action="get", name="brand-voice/fernhill")
    assert not err and json.loads(out)["value"] == profile
    listing = json.loads(mem(store, key, action="list", prefix="brand-voice/")[1])
    assert listing["count"] == 1 and listing["items"][0]["note"] == "voice profile"
    assert "Deleted" in mem(store, key, action="delete", name="brand-voice/fernhill")[1]
    assert "Nothing saved" in mem(store, key, action="get", name="brand-voice/fernhill")[1]


def test_keys_never_see_each_others_memory(store):
    a, _ = licensed(store, sub="sub_a")
    b, _ = licensed(store, sub="sub_b")
    mem(store, a, action="save", name="lead-qualifier/icp", value={"weights": [1, 2]})
    assert "Nothing saved" in mem(store, b, action="get", name="lead-qualifier/icp")[1]
    assert json.loads(mem(store, b, action="list")[1])["count"] == 0


def test_no_key_gets_a_clear_upgrade_message(store):
    err, out = mem(store, "", action="save", name="x/y", value=1)
    assert err and "license key" in out


def test_limits_and_name_rules(store):
    key, _ = licensed(store)
    assert "limit" in mem(store, key, action="save", name="big/one", value="x" * (memory.MAX_VALUE_BYTES + 10))[1]
    assert "lowercase" in mem(store, key, action="save", name="Bad Name!", value=1)[1]
    assert "needs a value" in mem(store, key, action="save", name="ok/name")[1]


def test_entry_cap(store, monkeypatch):
    monkeypatch.setattr(memory, "MAX_ENTRIES", 2)
    key, _ = licensed(store)
    mem(store, key, action="save", name="a/1", value=1)
    mem(store, key, action="save", name="a/2", value=2)
    err, out = mem(store, key, action="save", name="a/3", value=3)
    assert err and "full" in out
    assert mem(store, key, action="save", name="a/2", value=22)[0] is False, "overwriting an entry is allowed"


def test_declined_card_is_read_only_not_lost(store):
    key, lic = licensed(store)
    mem(store, key, action="save", name="fitness/log", value={"squat_1rm": 140})
    store.update_subscription(lic.subscription_id, payment_failed=True)
    assert json.loads(mem(store, key, action="get", name="fitness/log")[1])["value"]["squat_1rm"] == 140
    err, out = mem(store, key, action="save", name="fitness/log", value={"squat_1rm": 145})
    assert err and "declined" in out and "readable" in out
    assert mem(store, key, action="delete", name="fitness/log")[0] is False


def test_delete_everything_needs_confirmation(store):
    key, _ = licensed(store)
    mem(store, key, action="save", name="a/1", value=1)
    err, out = mem(store, key, action="delete", name="*")
    assert err and "confirm" in out
    assert "deleted" in mem(store, key, action="delete", name="*", confirm=True)[1]
    assert json.loads(mem(store, key, action="list")[1])["count"] == 0


def test_memory_survives_lost_key_recovery(store):
    key, lic = licensed(store)
    mem(store, key, action="save", name="study/bio", value={"cards": 300})
    new_key = store.rotate_key_for_subscription(lic.subscription_id)
    assert json.loads(mem(store, new_key, action="get", name="study/bio")[1])["value"] == {"cards": 300}
    assert "isn't recognised" in call_tool(store, resolve_access(store, req(key)), "hundred_account", {}).content[0].text


def test_every_briefing_tells_the_ai_about_memory_and_recipes():
    for agent in registry.all_agents().values():
        b = agent.briefing()
        assert "hundred_memory" in b and "hundred_recipes" in b
    assert "study/" in registry.get("study-coach").briefing()


# ── recipes ─────────────────────────────────────────────────
def test_every_recipe_step_is_a_real_agent():
    slugs = set(registry.all_agents())
    for r in recipes.RECIPES:
        assert len(r.steps) >= 3
        assert all(s.agent in slugs for s in r.steps), r.slug
    assert all(s in slugs for s in memory.HINTS)


@pytest.mark.parametrize("goal,expected", [
    ("we're launching a new product next month", "launch-product"),
    ("I just finished a discovery call", "after-sales-call"),
    ("monthly close and board update", "month-end-numbers"),
    ("production outage last night", "handle-an-incident"),
    ("hiring our first engineer", "hire-someone"),
])
def test_recipe_search(goal, expected):
    assert recipes.find(goal)[0].slug == expected


def test_recipe_plan_marks_owned_steps_and_upsells_the_rest(store):
    key, _ = licensed(store, plan="single", all_access=False, agents=["sales-call-debrief"])
    access = resolve_access(store, req(key))
    out = json.loads(call_tool(store, access, "hundred_recipes", {"recipe": "after-sales-call"}).content[0].text)
    assert [s["owned"] for s in out["steps"]] == [True, False, False]
    assert out["missing_agents"] == ["Follow-Up Machine", "Pipeline Forecaster"] and "All-Access" in out["upgrade"]
    assert "hundred_memory" in out["how_to_run"]
    listing = json.loads(call_tool(store, access, "hundred_recipes", {"goal": "sales call"}).content[0].text)
    assert listing[0]["recipe"] == "after-sales-call" and listing[0]["owned_steps"] == "1/3"
