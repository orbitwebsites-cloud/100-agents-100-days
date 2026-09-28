"""The live-model harness, driven by a scripted fake model (no network, no spend)."""

from __future__ import annotations

import json

import pytest

from hundred import live_eval as le
from hundred.server.store import Store

AB = next(s for s in le.SCENARIOS if s.id == "ab-test")
OFF_TOPIC = next(s for s in le.SCENARIOS if s.id == "no-agent")


def call(name, args, cid="c1"):
    return {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def scripted(*steps, cost=0.001):
    """Each step is a list of tool calls, or a string for the final answer."""
    it = iter(steps)

    def chat(messages, tools):
        chat.seen_tools = [t["function"]["name"] for t in tools]
        step = next(it)
        msg = {"role": "assistant", "content": step} if isinstance(step, str) else \
            {"role": "assistant", "content": None, "tool_calls": step}
        return {"choices": [{"message": msg}], "usage": {"cost": cost}}

    return chat


def meter(budget=1.0):
    return le.Meter(budget, None, None)


def test_router_happy_path_passes():
    chat = scripted(
        [call("hundred_start", {"task": AB.prompt})],
        [call("hundred_run", {"agent": "ab-test-analyst", "tool": "significance_test",
                              "arguments": {"control_visitors": 2400, "control_conversions": 120,
                                            "variant_visitors": 2380, "variant_conversions": 151}})],
        "The variant wins.",
    )
    r = le.run_scenario(AB, chat, le.all_access(), Store(":memory:"), meter(), "fake")
    assert chat.seen_tools[-1] == "hundred_run"
    assert r.started == ["ab-test-analyst"], r
    assert r.passed, r
    assert r.turns == 3 and r.cost == pytest.approx(0.003)


def test_tool_error_then_fix_counts_as_recovered_but_unfixed_does_not():
    bad = call("hundred_run", {"agent": "ab-test-analyst", "tool": "significance_test", "arguments": {"x": 1}})
    good = call("hundred_run", {"agent": "ab-test-analyst", "tool": "significance_test",
                                "arguments": {"control_visitors": 2400, "control_conversions": 120,
                                              "variant_visitors": 2380, "variant_conversions": 151}})
    start = call("hundred_start", {"agent": "ab-test-analyst", "task": "x"})
    fixed = le.run_scenario(AB, scripted([start], [bad], [good], "ok"), le.all_access(), Store(":memory:"), meter(), "f")
    assert fixed.tool_errors and fixed.recovered and fixed.passed
    broken = le.run_scenario(AB, scripted([start], [bad], "ok"), le.all_access(), Store(":memory:"), meter(), "f")
    assert not broken.recovered and not broken.used_tool and not broken.passed


def test_wrong_agent_fails_routing():
    chat = scripted([call("hundred_start", {"agent": "cold-email", "task": "x"})], "done")
    r = le.run_scenario(AB, chat, le.all_access(), Store(":memory:"), meter(), "f")
    assert not r.routed and not r.passed


def test_off_topic_should_not_start_an_agent():
    ok = le.run_scenario(OFF_TOPIC, scripted("Canberra."), le.all_access(), Store(":memory:"), meter(), "f")
    assert ok.passed
    meddled = le.run_scenario(OFF_TOPIC, scripted([call("hundred_start", {"agent": "cold-email", "task": "x"})],
                                                  "Canberra."), le.all_access(), Store(":memory:"), meter(), "f")
    assert not meddled.passed


def test_pick5_is_direct_and_contains_the_expected_agent():
    access = le.pick5_access(AB)
    assert access.mode == "direct" and len(access.agents) == 5 and access.agents[0].slug == "ab-test-analyst"
    names = [t["function"]["name"] for t in le.openai_tools(access)]
    assert "ab_test_analyst__significance_test" in names and len(names) <= 64


def test_budget_is_a_hard_stop():
    m = meter(budget=0.0015)
    chat = scripted([call("hundred_start", {"task": AB.prompt})], [call("hundred_start", {"task": AB.prompt})],
                    "x", cost=0.001)
    with pytest.raises(le.BudgetExceeded):
        le.run_scenario(AB, chat, le.all_access(), Store(":memory:"), m, "f")
    assert m.spent == pytest.approx(0.002)  # two calls made, the third was refused


def test_token_pricing_and_price_lookup():
    m = le.Meter(1, price_in=0.25, price_out=2.0)
    assert m.add({"prompt_tokens": 1_000_000, "completion_tokens": 500_000}) == pytest.approx(1.25)
    catalog = [{"id": "openai/gpt-5-mini", "pricing": {"prompt": "0.00000025", "completion": "0.000002"}}]
    assert le.price_for("gpt-5-mini", "openai", fetch=lambda: catalog) == pytest.approx((0.25, 2.0))
    assert le.price_for("nope", "openai", fetch=lambda: catalog) is None


def test_provider_errors_become_results():
    def boom(messages, tools):
        raise RuntimeError("400 bad schema")

    r = le.run_scenario(AB, boom, le.all_access(), Store(":memory:"), meter(), "f")
    assert "bad schema" in r.error and not r.passed


def test_every_scenario_names_real_agents():
    from hundred import registry

    for s in le.SCENARIOS:
        assert all(registry.get(a) for a in s.agents), s.id


def test_report_renders():
    r = le.run_scenario(OFF_TOPIC, scripted("Canberra."), le.all_access(), Store(":memory:"), meter(), "m")
    text = le.report([r], 0.001, 1.0)
    assert "| m | router | **1/1**" in text


def test_find_key_by_prefix_whatever_the_name():
    env = {"gpt_key": "sk-proj-abc", "my router": "'sk-or-v1-xyz' ", "ANTHROPIC_API_KEY": "sk-ant-1", "X": "hello"}
    assert le.find_key("openrouter", env) == ("my router", "sk-or-v1-xyz")
    assert le.find_key("openai", env) == ("gpt_key", "sk-proj-abc")
    assert le.find_key("openrouter", {"OPENROUTER_API_KEY": " sk-or-1 ", "z": "sk-or-2"}) == ("OPENROUTER_API_KEY", "sk-or-1")
    assert le.find_key("openrouter", {"gpt_key": "sk-proj-abc"}) == ("", "")
