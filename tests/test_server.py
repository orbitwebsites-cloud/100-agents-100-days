"""Licensing, billing and MCP access: the money path.

The promise to customers: agents work while the subscription is paid, switch off
the moment a card declines, and come back the moment payment succeeds.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from hundred import plans, registry
from hundred.server import billing
from hundred.server.mcp_server import call_tool, list_tools_for, resolve_access
from hundred.server.store import Store

FREE = next(a for a in registry.all_agents().values() if a.free)
PAID = [a for a in registry.all_agents().values() if not a.free]


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def req(key: str = "", **query):
    params = dict(query)
    if key:
        params["key"] = key
    return SimpleNamespace(query_params=params, headers={}, scope={})


def sub(sub_id="sub_1", status="trialing", lookup="hundred_single_monthly", agents=(), categories=(), plan="single"):
    return {
        "id": sub_id,
        "status": status,
        "customer": "cus_1",
        "metadata": {"plan": plan, **billing.pack_list("agents", list(agents)),
                     **billing.pack_list("categories", list(categories))},
        "items": {"data": [{"price": {"lookup_key": lookup}, "current_period_end": 1_900_000_000}]},
    }


def event(etype, obj, eid=None):
    event.n = getattr(event, "n", 0) + 1
    return {"id": eid or f"evt_{event.n}", "type": etype, "data": {"object": obj}}


# ── plans ────────────────────────────────────────────────────
def test_pick5_requires_exactly_five():
    with pytest.raises(plans.PlanError):
        plans.validate_selection(plans.PLANS["pick5"], [a.slug for a in PAID[:2]], [])


def test_single_quantity_is_agent_count():
    slugs = [a.slug for a in PAID[:3]]
    agents, cats, qty = plans.validate_selection(plans.PLANS["single"], slugs, [])
    assert qty == len(set(slugs)) and cats == []


def test_unknown_agent_rejected():
    with pytest.raises(plans.PlanError):
        plans.validate_selection(plans.PLANS["single"], ["not-a-real-agent"], [])


def test_metadata_packing_roundtrip_long_lists():
    values = [f"agent-number-{i}" for i in range(80)]
    packed = billing.pack_list("agents", values)
    assert all(len(v) <= 500 for v in packed.values()) and len(packed) > 1
    assert billing.unpack_list("agents", packed) == values


def test_entitlement_from_prices():
    ent = plans.entitlement_from_items(["hundred_all_monthly"], [], [])
    assert all(ent.allows(a.slug) for a in registry.all_agents().values())
    ent = plans.entitlement_from_items(["hundred_single_monthly"], [PAID[0].slug], [])
    assert ent.allows(PAID[0].slug) and ent.allows(FREE.slug)
    assert not any(ent.allows(a.slug) for a in PAID[1:])


# ── webhook lifecycle ────────────────────────────────────────
def provision(store, **kw):
    s = sub(**kw)
    checkout = {"id": "cs_1", "mode": "subscription", "subscription": s["id"],
                "customer_details": {"email": "Buyer@Example.com"}}
    assert billing.handle_event(store, event("checkout.session.completed", checkout), fetch=lambda _id: s) == "provisioned"
    key = store.take_reveal("cs_1")
    assert key and key.startswith("hnd_")
    assert store.take_reveal("cs_1") is None, "key is revealed exactly once"
    return key, s


def test_checkout_provisions_license_with_trial_access(store):
    key, _ = provision(store, agents=[PAID[0].slug])
    lic = store.by_key(key)
    assert lic.email == "buyer@example.com" and lic.status == "trialing" and lic.active
    assert lic.entitlement().allows(PAID[0].slug)


def test_card_decline_cuts_access_and_payment_restores_it(store):
    key, s = provision(store, status="active", agents=[PAID[0].slug])
    paid_tool = PAID[0].start_tool_name
    assert not call_tool(store, resolve_access(store, req(key)), paid_tool, {}).is_error

    invoice = {"id": "in_1", "parent": {"subscription_details": {"subscription": s["id"]}}}
    assert billing.handle_event(store, event("invoice.payment_failed", invoice), fetch=lambda _id: s) == "access-cut"
    access = resolve_access(store, req(key))
    blocked = call_tool(store, access, paid_tool, {})
    assert blocked.is_error and "declined" in blocked.content[0].text
    assert not call_tool(store, access, FREE.start_tool_name, {}).is_error, "free agents keep working"

    billing.handle_event(store, event("invoice.paid", {"id": "in_1", "subscription": s["id"]}), fetch=lambda _id: s)
    assert not call_tool(store, resolve_access(store, req(key)), paid_tool, {}).is_error


def test_subscription_status_past_due_also_blocks(store):
    key, s = provision(store, status="active", agents=[PAID[0].slug])
    billing.handle_event(store, event("customer.subscription.updated", {"id": s["id"]}),
                         fetch=lambda _id: {**s, "status": "past_due"})
    assert not store.by_key(key).active


def test_cancel_turns_off(store):
    key, s = provision(store, status="active", agents=[PAID[0].slug])
    billing.handle_event(store, event("customer.subscription.deleted", {"id": s["id"]}))
    assert store.by_key(key).status == "canceled"
    assert call_tool(store, resolve_access(store, req(key)), PAID[0].start_tool_name, {}).is_error


def test_upgrade_changes_entitlement(store):
    key, s = provision(store, status="active", agents=[PAID[0].slug])
    upgraded = sub(status="active", lookup="hundred_all_monthly", plan="all")
    billing.handle_event(store, event("customer.subscription.updated", {"id": s["id"]}), fetch=lambda _id: upgraded)
    lic = store.by_key(key)
    assert lic.all_access and all(lic.entitlement().allows(a.slug) for a in PAID)


def test_duplicate_events_are_ignored(store):
    key, s = provision(store, status="active", agents=[PAID[0].slug])
    ev = event("invoice.payment_failed", {"id": "in_2", "subscription": s["id"]}, eid="evt_dupe")
    assert billing.handle_event(store, ev, fetch=lambda _id: s) == "access-cut"
    assert billing.handle_event(store, ev, fetch=lambda _id: s) == "duplicate"


def test_failed_processing_can_be_retried(store):
    def boom(_id):
        raise RuntimeError("stripe down")

    ev = event("checkout.session.completed", {"id": "cs_9", "mode": "subscription", "subscription": "sub_9"},
               eid="evt_retry")
    with pytest.raises(RuntimeError):
        billing.handle_event(store, ev, fetch=boom)
    assert billing.handle_event(store, ev, fetch=lambda _id: sub(sub_id="sub_9", agents=[PAID[0].slug])) == "provisioned"


# ── MCP exposure ─────────────────────────────────────────────
def test_no_key_sees_only_free_agents(store):
    access = resolve_access(store, req())
    assert {a.slug for a in access.agents} == registry.free_slugs()
    if PAID:
        res = call_tool(store, access, PAID[0].start_tool_name, {})
        assert res.is_error and "$4.99" in res.content[0].text


def test_unknown_key_is_reported(store):
    access = resolve_access(store, req("hnd_live_bogus"))
    assert access.blocked_reason and "isn't recognised" in call_tool(store, access, "hundred_account", {}).content[0].text


def test_router_mode_for_big_bundles(store):
    key, _ = store.create_license(email="a@b.co", plan="all", status="active", source="comp", all_access=True)
    access = resolve_access(store, req(key))
    total = sum(1 + len(a.tools) for a in access.agents)
    names = [t.name for t in list_tools_for(access)]
    if total > 40:
        assert names == ["hundred_account", "hundred_find_agent", "hundred_start", "hundred_run"]
    focused = resolve_access(store, req(key, agents=FREE.slug))
    assert focused.mode == "direct" and FREE.start_tool_name in [t.name for t in list_tools_for(focused)]


def test_router_run_executes_tool(store):
    key, _ = store.create_license(email="a@b.co", plan="all", status="active", source="comp", all_access=True)
    access = resolve_access(store, req(key, mode="router"))
    tool = FREE.tools[0]
    res = call_tool(store, access, "hundred_run", {"agent": FREE.slug, "tool": "nope"})
    assert res.is_error and tool.name in res.content[0].text
    start = call_tool(store, access, "hundred_start", {"agent": FREE.slug, "task": "hi"})
    assert "hundred_run" in start.content[0].text and "operating procedure" in start.content[0].text


def test_every_tool_description_and_schema_is_valid(store):
    key, _ = store.create_license(email="a@b.co", plan="all", status="active", source="comp", all_access=True)
    access = resolve_access(store, req(key, mode="direct"))
    tools = list_tools_for(access)
    assert len({t.name for t in tools}) == len(tools)
    for t in tools:
        assert len(t.name) <= 64 and t.input_schema["type"] == "object"


def test_daily_fair_use_limit(store, monkeypatch):
    import dataclasses

    from hundred.server import mcp_server

    monkeypatch.setattr(mcp_server, "settings", dataclasses.replace(mcp_server.settings, daily_call_limit=2))
    key, _ = store.create_license(email="a@b.co", plan="all", status="active", source="comp", all_access=True)
    access = resolve_access(store, req(key, mode="direct"))
    target = PAID[0].start_tool_name
    assert not call_tool(store, access, target, {}).is_error
    assert not call_tool(store, access, target, {}).is_error
    res = call_tool(store, access, target, {})
    assert res.is_error and "fair-use" in res.content[0].text


# ── the real HTTP server, end to end ─────────────────────────
def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    port = _free_port()
    db = tmp_path_factory.mktemp("srv") / "live.db"
    env = {**os.environ, "DATABASE_PATH": str(db), "PUBLIC_URL": f"http://127.0.0.1:{port}", "STRIPE_SECRET_KEY": "",
           "STRIPE_WEBHOOK_SECRET": "whsec_test"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "hundred.server.app:app", "--port", str(port)],
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    key, _ = Store(str(db)).create_license(email="e2e@x.co", plan="all", status="active", source="comp",
                                           all_access=True)
    yield f"http://127.0.0.1:{port}", key
    proc.terminate()
    proc.wait(timeout=10)


def test_http_pages(live_server):
    import httpx

    base, _ = live_server
    assert httpx.get(f"{base}/").status_code == 200
    assert httpx.get(f"{base}/agents/{FREE.slug}").status_code == 200
    assert httpx.get(f"{base}/agents/nope").status_code == 404
    assert len(httpx.get(f"{base}/catalog.json").json()["agents"]) == len(registry.all_agents())
    assert httpx.post(f"{base}/stripe/webhook", content=b"{}", headers={"stripe-signature": "bad"}).status_code == 400


def test_http_mcp_end_to_end(live_server):
    import anyio
    from mcp import Client

    base, key = live_server

    async def run():
        async with Client(f"{base}/k/{key}/mcp?mode=router") as c:
            names = [t.name for t in (await c.list_tools()).tools]
            assert "hundred_run" in names
            res = await c.call_tool("hundred_start", {"agent": FREE.slug, "task": "test"})
            assert not res.is_error
        async with Client(f"{base}/mcp") as c:  # no key → free agents only
            names = [t.name for t in (await c.list_tools()).tools]
            assert FREE.start_tool_name in names
            assert all(not n.startswith(PAID[0].prefix + "__") for n in names) if PAID else True

    anyio.run(run)


@pytest.mark.parametrize(
    "query,expected",
    [
        ("regex email validation", "regex-builder"),
        ("forecast my cash for 13 weeks", "cashflow-forecaster"),
        ("is my A/B test significant", "ab-test-analyst"),
        ("reorder point for my SKUs", "inventory-planner"),
        ("what does this stack trace mean", "bug-hunter"),
        ("summarize this meeting transcript", "meeting-ops"),
    ],
)
def test_router_finds_the_right_agent(query, expected):
    from hundred.plans import Entitlement
    from hundred.server.mcp_server import Access, find_agents

    access = Access(license=None, entitlement=Entitlement(all_access=True), agents=list(registry.all_agents().values()))
    assert find_agents(access, query)[0]["agent"] == expected
