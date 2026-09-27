"""Live test: plug the agents into a real model and see whether it uses them properly.

This is the customer's experience with a real AI on the other end: the model gets exactly
the tools an MCP client would list, a realistic request, and nothing else. We grade what
it does, not what it says:

  routed     it started the agent we'd expect for that request
  used_tool  it ran at least one of that agent's tools (the math/validation we sell)
  recovered  every tool error was followed by a successful retry
  answered   it finished with a non-empty reply to the user

Works with any OpenAI-compatible chat API:

  OPENROUTER_API_KEY=... python -m hundred.live_eval --provider openrouter --model openai/gpt-5-mini
  OPENAI_API_KEY=...     python -m hundred.live_eval --provider openai --model gpt-5-mini

Spend is capped (--budget, default $1.00): the run stops before any call once the running
total reaches the cap. Prices come from usage.cost (OpenRouter) or from OpenRouter's public
price list, and a model with no known price is refused unless --price-in/--price-out are given.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

import httpx

from . import registry
from .plans import Entitlement
from .server.mcp_server import INSTRUCTIONS, Access, call_tool, list_tools_for, pick_agent
from .server.store import Store

PROVIDERS = {
    "openai": {"base": "https://api.openai.com/v1", "key": "OPENAI_API_KEY"},
    "openrouter": {"base": "https://openrouter.ai/api/v1", "key": "OPENROUTER_API_KEY"},
}
PRICE_LIST_URL = "https://openrouter.ai/api/v1/models"
MAX_TURNS = 10


@dataclass(frozen=True)
class Scenario:
    id: str
    prompt: str
    agents: tuple[str, ...]  # any of these counts as the right agent
    needs_tool: bool = True


# Realistic requests with real data in them, the way customers actually type.
SCENARIOS: list[Scenario] = [
    Scenario("cold-email", "Write me a 3-email cold sequence to VPs of Operations at mid-size logistics companies. "
             "We sell route-optimization software that cuts fuel cost ~12%. Subject for email 1: 'Quick question "
             "about your fuel spend!!!' — is that subject any good?", ("cold-email",)),
    Scenario("ab-test", "My A/B test: control had 2,400 visitors and 120 signups, variant had 2,380 visitors and 151 "
             "signups. Is the variant a real winner or noise?", ("ab-test-analyst", "growth-experiments", "store-cro")),
    Scenario("runway", "We have $420k in the bank, burn is $38k/month and growing 3% a month, revenue is $9k MRR "
             "growing 8% a month. How many months of runway do we actually have?",
             ("cashflow-forecaster", "startup-model", "investor-update")),
    Scenario("regex", "I need a regex that matches US ZIP codes, both 12345 and 12345-6789, and nothing else. "
             "Test it on: 90210, 12345-6789, 1234, 123456, 12345-678.", ("regex-builder",)),
    Scenario("stack-trace", "Getting this in prod, what's going on?\n\nTraceback (most recent call last):\n"
             "  File \"app/api/orders.py\", line 88, in create_order\n    total = compute_total(cart)\n"
             "  File \"app/billing/totals.py\", line 41, in compute_total\n    return sum(i.price * i.qty for i in "
             "cart.items) - cart.discount.amount\nAttributeError: 'NoneType' object has no attribute 'amount'",
             ("bug-hunter",)),
    Scenario("meeting", "Turn this into action items with owners and dates (today is Monday Sept 28 2026):\n"
             "Priya: I'll send the revised pricing deck by Thursday.\nMarcus: I can get the Stripe migration done "
             "end of next week.\nPriya: Someone needs to email the three churned accounts — Dana, can you take that "
             "tomorrow?\nDana: Yep.", ("meeting-ops",)),
    Scenario("reorder", "I sell about 14 units a day of my best SKU, supplier lead time is 21 days, and demand "
             "swings with a standard deviation of 4 units/day. I want 95% service level. When should I reorder?",
             ("inventory-planner",)),
    Scenario("salary", "I got two offers. A: $148k base, 10% bonus, $80k RSUs over 4 years. B: $135k base, no bonus, "
             "0.15% equity at a Series A valued at $60M, 4-year vest with 1-year cliff. Which is better and what "
             "should I counter with?", ("salary-negotiator",)),
    Scenario("seo-meta", "Write a title tag and meta description for my page about 'best standing desks for small "
             "apartments' and tell me if they'll get truncated in Google.", ("meta-writer", "seo-auditor")),
    Scenario("x-thread", "Turn this into an X thread: We grew our newsletter from 0 to 25,000 subscribers in 11 "
             "months with zero ad spend. The three things that worked were cross-promos with 40 similar newsletters, "
             "a free template library that required an email, and posting the best issue excerpts on LinkedIn "
             "every weekday. The thing that didn't work was giveaways — they brought 6,000 subscribers who never "
             "opened.", ("x-thread-builder", "content-repurposer")),
    Scenario("macros", "I'm 31, male, 180 lb, 5'10\", lift 4x a week, desk job. I want to lose fat slowly without "
             "losing strength. What should my calories and macros be?", ("fitness-coach", "meal-planner")),
    Scenario("sql", "Why is this slow and what index would help?\nSELECT * FROM orders o JOIN customers c ON c.id = "
             "o.customer_id WHERE o.status = 'pending' AND o.created_at > now() - interval '7 days' ORDER BY "
             "o.created_at DESC;", ("sql-wizard",)),
    Scenario("contract", "Review this clause for me: 'This Agreement shall automatically renew for successive "
             "one-year terms unless either party gives written notice of non-renewal at least ninety (90) days "
             "prior to the end of the then-current term. Provider's total liability shall not exceed the fees paid "
             "in the one (1) month preceding the claim.' Our term started March 1 2026.",
             ("contract-reviewer", "freelance-contract", "vendor-evaluator")),
    Scenario("rice", "Prioritize these with RICE: Dark mode (reach 4000/qtr, impact 1, confidence 80%, effort 2 "
             "person-months); SSO (reach 300, impact 3, confidence 90%, effort 4); CSV export (reach 1500, impact 2, "
             "confidence 70%, effort 1).", ("roadmap-prioritizer",)),
    Scenario("pipeline", "My Q4 pipeline: Acme $80k in Proposal, Globex $45k in Discovery, Initech $120k in "
             "Negotiation, Umbrella $30k in Proposal. Quota is $150k. Am I going to make it?",
             ("pipeline-forecaster",)),
    Scenario("contrast", "Is white text (#FFFFFF) on my brand orange (#F97316) accessible for body text? If not, "
             "what's the closest orange that passes?", ("accessibility-checker",)),
    Scenario("tax", "I'm a freelancer in the US, expect about $95k net self-employment income this year, single, "
             "no other income. How much should my quarterly estimated tax payments be and when are they due?",
             ("freelance-tax",)),
    Scenario("pricing", "My product costs $11.40 to make, shipping is $6.20, Shopify + payment fees are about 3.2%, "
             "and I want a 45% contribution margin. What should I charge?", ("ecom-pricing", "unit-economics",
                                                                             "pricing-strategist")),
    Scenario("okr", "Check my OKR: Objective: Improve the product. KR1: Launch dark mode. KR2: Make onboarding "
             "better. KR3: Increase activation.", ("okr-coach",)),
    Scenario("no-agent", "What's the capital of Australia?", (), needs_tool=False),
]


@dataclass
class Result:
    scenario: str
    model: str
    mode: str
    routed: bool = False
    used_tool: bool = False
    recovered: bool = True
    answered: bool = False
    started: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    tool_errors: list[str] = field(default_factory=list)
    turns: int = 0
    cost: float = 0.0
    error: str = ""
    answer: str = ""

    @property
    def passed(self) -> bool:
        return self.routed and self.used_tool and self.recovered and self.answered and not self.error


class BudgetExceeded(Exception):
    pass


class Meter:
    """Running spend with a hard cap, checked before every paid call."""

    def __init__(self, budget: float, price_in: float | None, price_out: float | None):
        self.budget, self.spent = budget, 0.0
        self.price_in, self.price_out = price_in, price_out  # $ per 1M tokens

    def check(self) -> None:
        if self.spent >= self.budget:
            raise BudgetExceeded(f"budget ${self.budget:.2f} reached (spent ${self.spent:.4f})")

    def add(self, usage: dict[str, Any]) -> float:
        cost = usage.get("cost")
        if cost is None:
            cost = (usage.get("prompt_tokens", 0) * (self.price_in or 0)
                    + usage.get("completion_tokens", 0) * (self.price_out or 0)) / 1e6
        self.spent += float(cost)
        return float(cost)


def price_for(model: str, provider: str, fetch: Callable[[], list[dict]] | None = None) -> tuple[float, float] | None:
    """$ per 1M input/output tokens from OpenRouter's public price list."""
    try:
        catalog = fetch() if fetch else httpx.get(PRICE_LIST_URL, timeout=20).json()["data"]
    except Exception:
        return None
    wanted = model if provider == "openrouter" or "/" in model else f"openai/{model}"
    for m in catalog:
        if m.get("id") == wanted:
            p = m.get("pricing") or {}
            return float(p.get("prompt", 0)) * 1e6, float(p.get("completion", 0)) * 1e6
    return None


def openai_tools(access: Access) -> list[dict]:
    return [{"type": "function", "function": {"name": t.name, "description": t.description or "",
                                               "parameters": t.input_schema}} for t in list_tools_for(access)]


def all_access() -> Access:
    agents = list(registry.all_agents().values())
    return Access(license=None, entitlement=Entitlement(all_access=True), agents=agents, mode="router")


def pick5_access(scn: Scenario, seed: int = 7) -> Access:
    """A Pick-5 customer in direct mode: the expected agent plus four unrelated ones."""
    everything = list(registry.all_agents().values())
    mine = [registry.get(scn.agents[0])] if scn.agents else []
    others = [a for a in everything if a.slug not in scn.agents]
    random.Random(f"{seed}:{scn.id}").shuffle(others)
    agents = mine + others[: 5 - len(mine)]
    return Access(license=None, entitlement=Entitlement(agents=frozenset(a.slug for a in agents)),
                  agents=agents, mode="direct")


def _agent_of(access: Access, name: str, args: dict[str, Any]) -> tuple[str, str]:
    """(agent slug, tool) a call resolves to; tool 'start' for starts, '' for account/memory/etc."""
    if name == "hundred_start":
        slug = str(args.get("agent") or "").strip()
        if not slug:
            pick, _ = pick_agent(access, str(args.get("task", "")))
            slug = pick.slug if pick else ""
        return slug, "start"
    if name == "hundred_run":
        return str(args.get("agent", "")), str(args.get("tool", "")).split("__")[-1]
    if "__" in name:
        prefix, tool = name.split("__", 1)
        return prefix.replace("_", "-"), tool
    return "", ""


Chat = Callable[[list[dict], list[dict]], dict]


def run_scenario(scn: Scenario, chat: Chat, access: Access, store: Store, meter: Meter, model: str,
                 instructions: bool = True) -> Result:
    res = Result(scenario=scn.id, model=model, mode=access.mode)
    tools = openai_tools(access)
    messages: list[dict] = [{"role": "system", "content": INSTRUCTIONS}] if instructions else []
    messages.append({"role": "user", "content": scn.prompt})
    pending_error = False
    try:
        for _ in range(MAX_TURNS):
            meter.check()
            reply = chat(messages, tools)
            res.turns += 1
            res.cost += meter.add(reply.get("usage") or {})
            msg = reply["choices"][0]["message"]
            calls = msg.get("tool_calls") or []
            messages.append({k: v for k, v in msg.items() if k in ("role", "content", "tool_calls")})
            if not calls:
                res.answer = (msg.get("content") or "").strip()
                res.answered = bool(res.answer)
                break
            for call in calls:
                fn = call["function"]
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = None
                if not isinstance(args, dict):
                    out, is_error = "Arguments must be a JSON object.", True
                else:
                    result = call_tool(store, access, fn["name"], args)
                    out, is_error = result.content[0].text, bool(result.is_error)
                    slug, tool = _agent_of(access, fn["name"], args)
                    if tool == "start" and slug:
                        res.started.append(slug)
                    elif tool and not is_error:
                        res.tools.append(f"{slug}/{tool}")
                        if slug in scn.agents:
                            res.used_tool = True
                label = fn["name"] + ("" if not isinstance(args, dict) or "tool" not in args else f":{args['tool']}")
                if is_error:
                    res.tool_errors.append(f"{label}: {out[:160]}")
                    pending_error = True
                elif tool:
                    pending_error = False
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": out})
    except BudgetExceeded:
        raise
    except Exception as exc:  # provider/network errors are a result, not a crash
        res.error = f"{type(exc).__name__}: {exc}"[:400]

    res.recovered = not pending_error
    started_or_ran = set(res.started) | {t.split("/")[0] for t in res.tools}
    if scn.agents:
        res.routed = bool(started_or_ran & set(scn.agents))
    else:  # off-topic request: the right move is to answer without starting a paid agent
        res.routed = not res.started
        res.used_tool = True
    if not scn.needs_tool:
        res.used_tool = True
    return res


def http_chat(provider: str, model: str, key: str, max_out: int = 4000) -> Chat:
    conf = PROVIDERS[provider]
    headers = {"Authorization": f"Bearer {key}"}
    if provider == "openrouter":
        headers |= {"HTTP-Referer": "https://agents.klippdstudio.com", "X-Title": "Hundred live eval"}
    client = httpx.Client(base_url=conf["base"], headers=headers, timeout=120)

    def chat(messages: list[dict], tools: list[dict]) -> dict:
        body: dict[str, Any] = {"model": model, "messages": messages, "tools": tools}
        if provider == "openrouter":
            body |= {"max_tokens": max_out, "usage": {"include": True}}
        else:
            body["max_completion_tokens"] = max_out
        for attempt in range(3):
            r = client.post("/chat/completions", json=body)
            if r.status_code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"{r.status_code} {r.text[:300]}")
            data = r.json()
            if "choices" not in data:
                raise RuntimeError(json.dumps(data)[:300])
            return data
        raise RuntimeError("provider kept failing")

    return chat


def report(results: list[Result], spent: float, budget: float, note: str = "") -> str:
    lines = ["# Live model run", "", f"_{dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC · spent "
             f"${spent:.4f} of ${budget:.2f} budget_", ""]
    if note:
        lines += [note, ""]
    by_model: dict[tuple[str, str], list[Result]] = {}
    for r in results:
        by_model.setdefault((r.model, r.mode), []).append(r)
    lines += ["| Model | Mode | Passed | Routed | Used a tool | Recovered | Answered | Cost |", "|---|---|---|---|---|---|---|---|"]
    for (model, mode), rs in by_model.items():
        n = len(rs)
        lines.append(f"| {model} | {mode} | **{sum(r.passed for r in rs)}/{n}** | {sum(r.routed for r in rs)}/{n} | "
                     f"{sum(r.used_tool for r in rs)}/{n} | {sum(r.recovered for r in rs)}/{n} | "
                     f"{sum(r.answered for r in rs)}/{n} | ${sum(r.cost for r in rs):.4f} |")
    lines += ["", "## Every scenario", "", "| Model | Mode | Scenario | Pass | Started | Tools run | Errors | Turns |",
              "|---|---|---|---|---|---|---|---|"]
    for r in results:
        errs = "; ".join(r.tool_errors)[:200] or r.error[:200]
        lines.append(f"| {r.model} | {r.mode} | {r.scenario} | {'✅' if r.passed else '❌'} | "
                     f"{', '.join(r.started) or '—'} | {', '.join(r.tools) or '—'} | {errs.replace('|', '/') or '—'} "
                     f"| {r.turns} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", choices=sorted(PROVIDERS), required=True)
    ap.add_argument("--model", action="append", required=True, help="repeat for several models")
    ap.add_argument("--mode", choices=["router", "pick5", "both"], default="both",
                    help="router = All-Access (6 meta-tools); pick5 = direct tools for 5 agents")
    ap.add_argument("--scenario", action="append", help="run only these scenario ids")
    ap.add_argument("--budget", type=float, default=1.00, help="hard cap in US$ for the whole run")
    ap.add_argument("--price-in", type=float, help="$ per 1M input tokens if the model isn't on the price list")
    ap.add_argument("--price-out", type=float, help="$ per 1M output tokens")
    ap.add_argument("--no-instructions", action="store_true", help="simulate clients that ignore server instructions")
    ap.add_argument("--out", default="evals/live", help="where to write the report")
    ap.add_argument("--key-env", help="env var holding the API key (default OPENAI_API_KEY / OPENROUTER_API_KEY)")
    args = ap.parse_args(argv)

    key_env = args.key_env or PROVIDERS[args.provider]["key"]
    key = os.environ.get(key_env, "").strip()
    if not key:
        print(f"Set {key_env} in the environment first.", file=sys.stderr)
        return 2
    scenarios = [s for s in SCENARIOS if not args.scenario or s.id in args.scenario]
    modes = ["router", "pick5"] if args.mode == "both" else [args.mode]

    results: list[Result] = []
    spent_total, stopped = 0.0, ""
    for model in args.model:
        prices = (args.price_in, args.price_out) if args.price_in is not None else price_for(model, args.provider)
        if prices is None and args.provider != "openrouter":
            print(f"No known price for {model}; pass --price-in/--price-out.", file=sys.stderr)
            return 2
        meter = Meter(args.budget - spent_total, *(prices or (None, None)))
        chat = http_chat(args.provider, model, key)
        try:
            for mode in modes:
                for scn in scenarios:
                    if mode == "pick5" and not scn.agents:
                        continue
                    store = Store(":memory:")
                    access = all_access() if mode == "router" else pick5_access(scn)
                    r = run_scenario(scn, chat, access, store, meter, model, instructions=not args.no_instructions)
                    results.append(r)
                    print(f"{'PASS' if r.passed else 'FAIL'}  {model:<32} {mode:<6} {scn.id:<12} "
                          f"${r.cost:.4f}  total ${spent_total + meter.spent:.4f}", flush=True)
        except BudgetExceeded as e:
            stopped = f"**Stopped early:** {e}."
        spent_total += meter.spent
        if stopped:
            break

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M")
    (out / f"{stamp}-{args.provider}.md").write_text(report(results, spent_total, args.budget, stopped))
    (out / f"{stamp}-{args.provider}.json").write_text(json.dumps([asdict(r) | {"passed": r.passed} for r in results],
                                                                  indent=1))
    print(f"\nSpent ${spent_total:.4f}. Report: {out}/{stamp}-{args.provider}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
