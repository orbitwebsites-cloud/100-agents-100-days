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

import functools
import logging
import re
from collections import Counter
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
agent's `<agent>__start` tool FIRST (or `hundred_start` with the user's words, which picks the agent for you) and follow the operating
procedure it returns — including calling the agent's tools for any math, scoring, dates or limits.
If `hundred_memory` is listed, use it to recall saved context before a job and to save what the user wants kept; use
`hundred_recipes` when a job needs several agents in sequence. Call `hundred_account` if the user asks about
their plan or an agent says access is paused."""


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
    lic, blocked = None, None
    if key.startswith("hnd_at_"):  # OAuth access token from "sign in" in the AI app
        from .oauth import subject_from_bearer

        subject = subject_from_bearer(store, key) or ""
        if subject.startswith("lic:"):
            lic = store.by_key_hash(subject[4:])
        elif not subject.startswith("free:"):
            blocked = "Your sign-in expired. Reconnect Hundred in your AI app's connector settings."
    elif key:
        lic = store.by_key(key)
        if lic is None:
            blocked = "That license key isn't recognised. Check the link, or get a new one."
    if not blocked and lic is not None and not lic.active:
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

MEMORY_TOOL = types.Tool(
    name="hundred_memory",
    title="Agent memory",
    description="Save and recall small notes for the user's agents across chats: brand voice profiles, ICP "
    "weights, training logs, flashcard state, last week's numbers. Actions: list (optional prefix), get, save "
    "(name + JSON value + short note), delete (name, or '*' with confirm=true to erase everything). Stored per "
    "license key; save only what the user agrees to keep, never secrets.",
    input_schema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "get", "save", "delete"], "description": "What to do."},
            "name": {"type": "string", "description": "Memory name, lowercase with / . - _ (e.g. 'brand-voice/acme')."},
            "value": {"description": "JSON value to save (object, list, string or number), up to 48 KB."},
            "note": {"type": "string", "description": "One line describing what this is, shown in list."},
            "prefix": {"type": "string", "description": "For list: only names starting with this."},
            "confirm": {"type": "boolean", "description": "Required true to delete everything with name '*'."},
        },
        "required": ["action"],
    },
    annotations=types.ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=True,
                                      open_world_hint=False),
)

RECIPES_TOOL = types.Tool(
    name="hundred_recipes",
    title="Multi-agent recipes",
    description="Chain several expert agents for a bigger job (launch a product, after a sales call, month-end "
    "numbers, hire someone, ship a feature, raise a round…). Pass `goal` to find recipes, or `recipe` to get the "
    "ordered steps: which agent does what and what it hands to the next.",
    input_schema={
        "type": "object",
        "properties": {
            "goal": {"type": "string", "description": "What the user is trying to get done."},
            "recipe": {"type": "string", "description": "A recipe slug from a previous call, for its full plan."},
        },
    },
    annotations=READ_ONLY,
)

ROUTER_TOOLS = [
    types.Tool(
        name="hundred_find_agent",
        title="Find the right agent",
        description="Search all expert agents by what the user wants done (e.g. 'cold email', 'cash flow', "
        "'SQL'). Returns the best matches with their slugs and whether the user has each one.",
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
        description="START HERE for any work request: writing, sales, marketing, SEO, finance, legal, code, "
        "product, hiring, e-commerce, fitness, travel, study. Pass the user's words as `task` and this picks the "
        "right expert agent and returns its procedure and tools (or pass `agent` to choose one). Follow the "
        "procedure; call the agent's tools directly or via hundred_run.",
        input_schema={
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "The user's request, in their words."},
                "agent": {"type": "string", "description": "Optional agent slug, e.g. 'cold-email'. Omit to auto-pick."},
            },
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
    # Memory needs a license key; don't offer a tool that can only fail (models call it first and stall).
    tools = [ACCOUNT_TOOL, MEMORY_TOOL, RECIPES_TOOL] if access.license else [ACCOUNT_TOOL, RECIPES_TOOL]
    if access.mode == "router":
        return tools + ROUTER_TOOLS
    tools += [t for t in ROUTER_TOOLS if t.name in ("hundred_find_agent", "hundred_start")]
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


_STOP = frozenset("a an and are as at be by can do for from have i in is it me my of on or our please the this "
                  "to we what with you your need want help make get give some".split())


def _stem(word: str) -> str:
    w = word.lower()
    for suffix in ("ations", "ation", "ings", "ing", "ies", "ers", "er", "es", "ed", "ly", "s"):
        if len(w) - len(suffix) >= 3 and w.endswith(suffix):
            return w[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return w


_CODE_LINE = re.compile(r"(\t| {2,})\S")
_FILE_PATH = re.compile(r"[\w.~-]*(?:[/\\][\w.~-]+)+\.\w{1,5}\b")


def _intent_text(text_: str) -> str:
    """Drop what the user pasted (indented code, file paths, traceback boilerplate) and keep what they asked.

    Otherwise `app/api/orders.py` routes a stack trace to the API designer and `cart.discount` to e-commerce.
    """
    lines = text_.splitlines()
    prose = [ln for ln in lines if not _CODE_LINE.match(ln)]
    if prose and len(prose) < len(lines):
        text_ = "\n".join(prose)
    text_ = re.sub(r"\(most recent call (?:last|first)\)", " ", _FILE_PATH.sub(" ", text_))
    return re.sub(r"([a-z])(Error|Exception|Warning)\b", r"\1 \2", text_)  # AttributeError → Attribute Error


def _stems(text_: str) -> list[str]:
    text_ = _intent_text(text_)
    return [_stem(t) for t in re.findall(r"[a-z0-9]+", text_.lower()) if len(t) > 1 and t not in _STOP]


@functools.lru_cache(maxsize=1)
def _agent_index() -> list[tuple[Agent, set[str], Counter]]:
    out = []
    for a in registry.all_agents().values():
        title = set(_stems(f"{a.slug.replace('-', ' ')} {a.name}"))
        body = Counter(_stems(" ".join([a.tagline, a.description, " ".join(a.triggers), " ".join(a.examples),
                                        a.category])))
        out.append((a, title, body))
    return out


def rank_agents(query: str) -> list[tuple[float, Agent]]:
    """Rank every agent for a request on stemmed words; rare words ("regex", "squat") outweigh common ones."""
    import math

    terms = list(dict.fromkeys(_stems(query)))
    index = _agent_index()
    n = len(index)
    df = {t: sum(1 for _, ti, bo in index if t in ti or t in bo) for t in terms}
    scored = []
    for a, title, body in index:
        score = sum(math.log(1 + n / df[t]) * ((3 if t in title else 0) + min(body[t], 3)) for t in terms if df[t])
        if score:
            scored.append((score, a))
    scored.sort(key=lambda x: -x[0])
    return scored


def find_agents(access: Access, query: str, limit: int = 8) -> list[dict]:
    """Best agents for a request across the whole library, marking which ones this connection has."""
    owned = {a.slug for a in access.agents}
    return [{"agent": a.slug, "name": a.name, "does": a.tagline, "owned": a.slug in owned}
            for _, a in rank_agents(query)[:limit]]


def pick_agent(access: Access, task: str) -> tuple[Agent | None, Agent | None]:
    """(agent to run, better agent the user doesn't own). Prefers an owned agent that fits nearly as well."""
    owned = {a.slug for a in access.agents}
    ranked = rank_agents(task)
    if not ranked:
        return None, None
    best_score, best = ranked[0]
    if best.slug in owned:
        return best, None
    for score, a in ranked[1:6]:
        if a.slug in owned and score >= 0.6 * best_score:
            return a, best
    return None, best


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

    if name == "hundred_memory":
        return memory_call(store, access, arguments)

    if name == "hundred_recipes":
        return recipes_call(access, arguments)

    if name == "hundred_find_agent":
        found = find_agents(access, str(arguments.get("query", "")))
        if not found:
            return _text("No owned agent matches. Owned: " + ", ".join(a.slug for a in access.agents))
        return _text(render_result(found))

    # Resolve (agent, tool) for start/run/direct names.
    note = ""
    if name == "hundred_start":
        slug, tool_name = str(arguments.get("agent", "")).strip(), "start"
        if not slug:
            task = str(arguments.get("task", ""))
            pick, better = pick_agent(access, task)
            if pick is None:
                if better is None:
                    return _text("No agent matches that request. Ask the user for a bit more detail, or answer "
                                 "normally. hundred_find_agent lists what's available.")
                return _text(_upsell(better.slug) + " Meanwhile, help the user as best you can without it.")
            slug = pick.slug
            if better is not None:
                note = (f"(Picked {pick.name}, which the user has. {better.name} fits this request best; "
                        f"mention it once: {settings.public_url}/agents/{better.slug})\n\n")
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
        return _text(note + start_payload(agent, str(arguments.get("task", "")), router=access.mode == "router"))

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


# ── memory + recipes ─────────────────────────────────────────
def memory_call(store: Store, access: Access, args: dict[str, Any]) -> types.CallToolResult:
    import json
    import re as _re

    from .. import memory

    if access.license is None:
        msg = ("Memory is part of every paid plan and needs a license key on this connection. "
               f"Free agents work without one. Plans: {settings.public_url}/pricing")
        if str(args.get("action", "")).strip() in ("list", "get"):  # a recall isn't a failure: nothing is saved
            return _text("Nothing saved. " + msg + " Carry on with the job without saved context.")
        return _text(msg, error=True)
    kh = access.license.key_hash
    action = str(args.get("action", "")).strip()
    name = str(args.get("name", "")).strip().lower()
    if action == "list":
        items = store.memory_list(kh, str(args.get("prefix", "")).strip().lower())
        return _text(render_result({"count": len(items), "limit": memory.MAX_ENTRIES, "items": items}))
    if action in ("get", "save", "delete") and not name:
        return _text(f"'{action}' needs a name.", error=True)
    if action == "get":
        item = store.memory_get(kh, name)
        return _text(render_result(item) if item else f"Nothing saved under {name!r}. Use action 'list' to see names.")
    if action == "delete":
        if name == "*":
            if args.get("confirm") is not True:
                return _text("Deleting all memory needs confirm=true. Ask the user first.", error=True)
            store.memory_delete(kh, "*")
            return _text("All saved memory for this key was deleted.")
        return _text(f"Deleted {name!r}." if store.memory_delete(kh, name) else f"Nothing saved under {name!r}.")
    if action == "save":
        if access.blocked_reason:
            return _text(_fix_billing_message(access) + " Saved memory stays readable and deletable meanwhile.",
                         error=True)
        if not _re.match(memory.NAME_RE, name):
            return _text("Names use lowercase letters, digits and / . - _ (max 120 chars), e.g. 'brand-voice/acme'.",
                         error=True)
        if "value" not in args:
            return _text("'save' needs a value.", error=True)
        blob = json.dumps(args["value"], ensure_ascii=False)
        if len(blob.encode()) > memory.MAX_VALUE_BYTES:
            return _text(f"That value is {len(blob.encode()):,} bytes; the limit is {memory.MAX_VALUE_BYTES:,}. "
                         "Save a summary or split it by topic.", error=True)
        if store.memory_get(kh, name) is None and store.memory_count(kh) >= memory.MAX_ENTRIES:
            return _text(f"Memory is full ({memory.MAX_ENTRIES} entries). Delete old entries first.", error=True)
        store.memory_save(kh, name, args["value"], str(args.get("note", ""))[:200])
        return _text(f"Saved {name!r} ({len(blob.encode()):,} bytes). It will be here in future chats.")
    return _text("action must be one of: list, get, save, delete.", error=True)


def recipes_call(access: Access, args: dict[str, Any]) -> types.CallToolResult:
    from .. import recipes

    owned = {a.slug for a in access.agents}
    slug = str(args.get("recipe", "")).strip()
    if slug:
        recipe = recipes.BY_SLUG.get(slug)
        if recipe is None:
            return _text(f"No recipe {slug!r}. Recipes: {', '.join(recipes.BY_SLUG)}", error=True)
        out = recipes.plan(recipe, owned)
        if out["missing_agents"]:
            out["upgrade"] = (f"The user doesn't have {', '.join(out['missing_agents'])} yet. Skip those steps and say so, "
                              f"or tell them All-Access covers every step: {settings.public_url}/pricing")
        return _text(render_result(out))
    found = recipes.find(str(args.get("goal", "")))
    return _text(render_result([
        {"recipe": r.slug, "name": r.name, "goal": r.goal,
         "chain": " → ".join(registry.get(s.agent).name if registry.get(s.agent) else s.agent for s in r.steps),
         "owned_steps": f"{sum(s.agent in owned for s in r.steps)}/{len(r.steps)}"}
        for r in found
    ]))


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
