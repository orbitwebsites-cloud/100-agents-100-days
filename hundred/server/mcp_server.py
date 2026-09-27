"""The MCP endpoint customers paste into their AI.

Every request is resolved to an *access*: which license key sent it, whether
that license is paid up right now, and which agents it unlocks. ``tools/list``
only shows what the key owns; ``tools/call`` re-checks on every call, so a
declined card switches agents off mid-session, not at the next reconnect.

Two exposure modes:
  * direct — every owned agent's ``<agent>__start`` + its tools (best for a few agents)
  * router — three meta-tools (find / start / run) that reach every owned agent.
             Chosen automatically once a key owns more tools than DIRECT_TOOL_LIMIT,
             so All-Access works in clients that cap tool counts.
Both always include ``hundred_account``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import mcp_types as types
from mcp.server.lowlevel import Server

from .. import registry
from ..core import Agent, ToolError, render_result
from ..plans import Entitlement
from .settings import settings
from .store import License, Store

log = logging.getLogger("hundred.mcp")

READ_ONLY = types.ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True,
                                  open_world_hint=False)

INSTRUCTIONS = """\
This server gives you expert agents (sales, marketing, writing, SEO, ops, finance, engineering,
product, career, creator, e-commerce, legal). When the user's request matches an agent, call that
agent's `<agent>__start` tool FIRST (or `hundred_start` in router mode) and follow the operating
procedure it returns — including calling the agent's tools for any math, scoring, dates or limits.
Call `hundred_account` if the user asks about their plan or an agent says access is paused."""


@dataclass
class Access:
    license: License | None
    entitlement: Entitlement
    agents: list[Agent] = field(default_factory=list)
    mode: str = "direct"
    blocked_reason: str | None = None

    @property
    def key_hash(self) -> str | None:
        return self.license.key_hash if self.license else None


def extract_key(request: Any) -> str:
    if request is None:
        return ""
    scope_key = request.scope.get("hundred_key") if hasattr(request, "scope") else None
    if scope_key:
        return scope_key
    q = request.query_params.get("key") or request.query_params.get("api_key")
    if q:
        return q.strip()
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("x-hundred-key", "").strip()


def resolve_access(store: Store, request: Any) -> Access:
    key = extract_key(request)
    lic = store.by_key(key) if key else None
    blocked = None
    if key and lic is None:
        blocked = "That license key isn't recognised. Check the link, or get a new one."
    elif lic is not None and not lic.active:
        if lic.payment_failed or lic.status in ("past_due", "unpaid"):
            blocked = "Your last payment was declined, so your agents are paused."
        elif lic.status == "canceled":
            blocked = "Your subscription has ended."
        else:
            blocked = f"Your subscription is {lic.status}."
    ent = lic.entitlement() if lic else Entitlement()
    owned = [a for a in registry.all_agents().values() if ent.allows(a.slug)]

    params = request.query_params if request is not None else {}
    only = {s.strip() for s in (params.get("agents") or "").split(",") if s.strip()}
    if only:
        owned = [a for a in owned if a.slug in only]
    n_tools = sum(1 + len(a.tools) for a in owned)
    mode = params.get("mode") or ("router" if n_tools > settings.direct_tool_limit else "direct")
    if mode not in ("direct", "router"):
        mode = "direct"
    return Access(license=lic, entitlement=ent, agents=owned, mode=mode, blocked_reason=blocked)


# ── tool definitions ─────────────────────────────────────────
def _text(s: str, error: bool = False) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=s)], is_error=error)


def _start_tool(agent: Agent) -> types.Tool:
    return types.Tool(
        name=agent.start_tool_name,
        title=agent.name,
        description=agent.start_description(),
        input_schema={
            "type": "object",
            "properties": {"task": {"type": "string", "description": "The user's request, in their words."}},
        },
        annotations=READ_ONLY,
    )


def _agent_tools(agent: Agent) -> list[types.Tool]:
    return [
        types.Tool(
            name=agent.wire_name(t.name),
            description=f"[{agent.name}] {t.description}",
            input_schema=t.input_schema(),
            annotations=READ_ONLY,
        )
        for t in agent.tools
    ]


ACCOUNT_TOOL = types.Tool(
    name="hundred_account",
    title="Account & agents",
    description="Show the user's plan, whether access is active, which agents they own, and links to add "
    "agents or fix billing. Call when asked about the subscription or when an agent reports access paused.",
    input_schema={"type": "object", "properties": {}},
    annotations=READ_ONLY,
)

ROUTER_TOOLS = [
    types.Tool(
        name="hundred_find_agent",
        title="Find the right agent",
        description="Search the user's expert agents by what they want done (e.g. 'cold email', 'cash flow', "
        "'SQL'). Returns matching agents with their slugs. Call this first in router mode, then hundred_start.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "What the user wants done."}},
            "required": ["query"],
        },
        annotations=READ_ONLY,
    ),
    types.Tool(
        name="hundred_start",
        title="Start an agent",
        description="Load an expert agent's operating procedure and its tool schemas. Follow the procedure; "
        "call its tools via hundred_run.",
        input_schema={
            "type": "object",
            "properties": {
                "agent": {"type": "string", "description": "Agent slug from hundred_find_agent, e.g. 'cold-email'."},
                "task": {"type": "string", "description": "The user's request, in their words."},
            },
            "required": ["agent"],
        },
        annotations=READ_ONLY,
    ),
    types.Tool(
        name="hundred_run",
        title="Run an agent tool",
        description="Run one of an agent's tools (calculators, scorers, validators). Use the tool names and "
        "argument schemas returned by hundred_start.",
        input_schema={
            "type": "object",
            "properties": {
                "agent": {"type": "string", "description": "Agent slug, e.g. 'cold-email'."},
                "tool": {"type": "string", "description": "Tool name as listed by hundred_start (without prefix)."},
                "arguments": {"type": "object", "description": "Arguments matching the tool's schema."},
            },
            "required": ["agent", "tool"],
        },
        annotations=READ_ONLY,
    ),
]


def list_tools_for(access: Access) -> list[types.Tool]:
    tools = [ACCOUNT_TOOL]
    if access.mode == "router":
        return tools + ROUTER_TOOLS
    for agent in access.agents:
        tools.append(_start_tool(agent))
        tools.extend(_agent_tools(agent))
    return tools


# ── calling ──────────────────────────────────────────────────
def _fix_billing_message(access: Access) -> str:
    return (
        f"{access.blocked_reason} Tell the user: update the card at {settings.public_url}/account and access "
        "returns instantly (same link, nothing lost). Free agents keep working meanwhile."
    )


def _upsell(slug: str) -> str:
    agent = registry.get(slug)
    name = agent.name if agent else slug
    return (
        f"The user doesn't have {name} yet. It's $4.99/mo, or included in All-Access. Tell them they can add it "
        f"at {settings.public_url}/agents/{slug} — then it appears here automatically, no reinstall."
    )


def account_summary(access: Access) -> str:
    lic = access.license
    if lic is None:
        free = ", ".join(a.name for a in access.agents) or "none"
        lead = access.blocked_reason or "No license key on this connection."
        return (
            f"{lead} Free agents available: {free}.\n"
            f"Unlock the other {len(registry.all_agents()) - len(access.agents)} agents at "
            f"{settings.public_url}/pricing (7-day free trial)."
        )
    status = "ACTIVE" if lic.active else f"PAUSED — {access.blocked_reason}"
    owned = [a.name for a in access.agents]
    lines = [
        f"Plan: {lic.plan}  ·  Status: {status}",
        f"Agents on this connection ({len(owned)}): " + (", ".join(owned) if len(owned) <= 30 else
                                                          f"{', '.join(owned[:30])} … and {len(owned) - 30} more"),
        f"Mode: {access.mode}",
        f"Manage billing / update card: {settings.public_url}/account",
        f"Add agents: {settings.public_url}/pricing",
    ]
    return "\n".join(lines)


def find_agents(access: Access, query: str, limit: int = 8) -> list[dict]:
    terms = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 1]
    scored = []
    for a in access.agents:
        hay = " ".join([a.slug, a.name, a.tagline, a.description, " ".join(a.triggers), a.category]).lower()
        score = sum(hay.count(t) for t in terms) + sum(5 for t in terms if t in a.slug or t in a.name.lower())
        if score:
            scored.append((score, a))
    scored.sort(key=lambda x: -x[0])
    return [{"agent": a.slug, "name": a.name, "does": a.tagline} for _, a in scored[:limit]]


def start_payload(agent: Agent, task: str, router: bool) -> str:
    text = agent.briefing(task)
    if router and agent.tools:
        import json

        schemas = {t.name: {"description": t.description.split("\n\n")[0], "arguments": t.input_schema()}
                   for t in agent.tools}
        text += (
            "\n\n## Calling tools in this connection\n"
            f"Call `hundred_run` with agent=\"{agent.slug}\", tool=<name>, arguments=<object>. "
            "Where the procedure says `" + agent.prefix + "__<tool>`, use hundred_run with tool=<tool>.\n\n"
            "```json\n" + json.dumps(schemas, indent=1) + "\n```"
        )
    return text


def call_tool(store: Store, access: Access, name: str, arguments: dict[str, Any] | None) -> types.CallToolResult:
    arguments = arguments or {}
    if name == "hundred_account":
        return _text(account_summary(access))

    if name == "hundred_find_agent":
        found = find_agents(access, str(arguments.get("query", "")))
        if not found:
            return _text("No owned agent matches. Owned: " + ", ".join(a.slug for a in access.agents))
        return _text(render_result(found))

    # Resolve (agent, tool) for start/run/direct names.
    if name == "hundred_start":
        slug, tool_name = str(arguments.get("agent", "")), "start"
    elif name == "hundred_run":
        slug, tool_name = str(arguments.get("agent", "")), str(arguments.get("tool", ""))
        tool_name = tool_name.split("__")[-1]
        arguments = arguments.get("arguments") or {}
    elif "__" in name:
        prefix, tool_name = name.split("__", 1)
        slug = prefix.replace("_", "-")
    else:
        return _text(f"Unknown tool {name!r}.", error=True)

    agent = registry.get(slug)
    if agent is None:
        return _text(f"Unknown agent {slug!r}. Use hundred_find_agent to list agents.", error=True)
    if not agent.free:
        if access.blocked_reason:
            return _text(_fix_billing_message(access), error=True)
        if not access.entitlement.allows(slug):
            return _text(_upsell(slug), error=True)
        if access.key_hash and store.calls_today(access.key_hash) >= settings.daily_call_limit:
            return _text("Daily fair-use limit reached for this key; it resets at 00:00 UTC. "
                         f"Contact {settings.support_email} if you need more.", error=True)

    if access.key_hash:
        store.record_call(access.key_hash, slug)

    if tool_name == "start":
        return _text(start_payload(agent, str(arguments.get("task", "")), router=access.mode == "router"))

    tool = agent.get_tool(tool_name)
    if tool is None:
        return _text(f"{agent.name} has no tool {tool_name!r}. Tools: {', '.join(t.name for t in agent.tools)}",
                     error=True)
    try:
        return _text(render_result(tool.call(arguments)))
    except ToolError as e:
        return _text(str(e), error=True)
    except Exception:  # never leak internals to the client
        log.exception("tool %s crashed", name)
        return _text(f"{agent.name}/{tool_name} hit an internal error. It's been logged; try rephrasing the input.",
                     error=True)


# ── prompts: each owned agent doubles as a slash-command in clients that show prompts ──
def list_prompts_for(access: Access) -> list[types.Prompt]:
    return [
        types.Prompt(
            name=a.slug,
            title=a.name,
            description=a.tagline,
            arguments=[types.PromptArgument(name="task", description="What you want done", required=False)],
        )
        for a in access.agents
    ]


# ── server wiring ────────────────────────────────────────────
def build_server(store: Store) -> Server:
    async def on_list_tools(ctx, params):
        access = resolve_access(store, ctx.request)
        return types.ListToolsResult(tools=list_tools_for(access))

    async def on_call_tool(ctx, params: types.CallToolRequestParams):
        access = resolve_access(store, ctx.request)
        return call_tool(store, access, params.name, params.arguments)

    async def on_list_prompts(ctx, params):
        access = resolve_access(store, ctx.request)
        return types.ListPromptsResult(prompts=list_prompts_for(access))

    async def on_get_prompt(ctx, params: types.GetPromptRequestParams):
        access = resolve_access(store, ctx.request)
        agent = next((a for a in access.agents if a.slug == params.name), None)
        if agent is None:
            text = _upsell(params.name)
        elif access.blocked_reason and not agent.free:
            text = _fix_billing_message(access)
        else:
            task = (params.arguments or {}).get("task", "")
            text = start_payload(agent, task, router=access.mode == "router")
        return types.GetPromptResult(
            description=agent.tagline if agent else None,
            messages=[types.PromptMessage(role="user", content=types.TextContent(type="text", text=text))],
        )

    from .. import __version__

    return Server(
        "hundred",
        version=__version__,
        title=f"{settings.brand} — expert AI agents",
        instructions=INSTRUCTIONS,
        website_url=settings.public_url,
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
        on_list_prompts=on_list_prompts,
        on_get_prompt=on_get_prompt,
    )
