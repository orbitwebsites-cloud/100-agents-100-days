"""The agent contract every Hundred agent is built on.

An agent here is three things, delivered over MCP into whatever AI the customer
already uses (Claude, ChatGPT, Cursor, Gemini, ...):

1. A **playbook** — the expert operating procedure. The customer's AI fetches it
   at the start of the job and follows it. This is the product's brain; it is
   served only to paying keys and updated centrally, so every subscriber gets
   the improvement the moment we ship it.
2. **Tools** — deterministic Python functions that do the parts an LLM is bad
   at: math, scoring, validation, formatting, calendars, parsing. Each one is
   exposed as a real MCP tool with a JSON schema generated from its signature.
3. **Metadata** — name, category, tagline, triggers, examples. Drives the
   storefront, the catalog, and the tool descriptions the host AI routes on.

No LLM runs on our side: the customer's AI does the reasoning, we supply the
expertise and the tools. That keeps inference cost at zero and margin near 100%.

    AGENT = Agent(slug="cold-email", name="Cold Email Closer", ...)

    @AGENT.tool
    def score_subject_line(subject: str) -> dict:
        '''Score a cold-email subject line 0-100 ...'''
"""

from __future__ import annotations

import inspect
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, get_type_hints

from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model

SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,38}[a-z0-9]$")
TOOL_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")

CATEGORIES: dict[str, str] = {
    "sales": "Sales",
    "marketing": "Marketing",
    "content": "Content & Writing",
    "growth": "SEO & Growth",
    "ops": "Operations & Productivity",
    "finance": "Finance & Money",
    "engineering": "Engineering",
    "product": "Product & Design",
    "career": "Career & HR",
    "creator": "Creators & Personal",
    "ecommerce": "E-commerce",
    "legal": "Legal & Admin",
}


class ToolError(Exception):
    """Raise from a tool for a clean, user-facing error (no stack trace)."""


def _parse_docstring(doc: str) -> tuple[str, dict[str, str]]:
    """Split a Google-style docstring into (description, {param: description})."""
    doc = inspect.cleandoc(doc or "")
    if not doc:
        return "", {}
    parts = re.split(r"^\s*(Args|Arguments|Parameters|Returns|Raises|Examples?):\s*$", doc, flags=re.M)
    description = parts[0].strip()
    params: dict[str, str] = {}
    for header, body in zip(parts[1::2], parts[2::2]):
        if header not in ("Args", "Arguments", "Parameters"):
            continue
        current = None
        for line in body.splitlines():
            m = re.match(r"^\s{0,8}(\w+)(?:\s*\([^)]*\))?:\s*(.*)$", line)
            if m:
                current = m.group(1)
                params[current] = m.group(2).strip()
            elif current and line.strip():
                params[current] += " " + line.strip()
    return description, params


@dataclass
class AgentTool:
    """One deterministic function exposed as an MCP tool."""

    name: str
    fn: Callable[..., Any]
    description: str
    model: type[BaseModel]

    @classmethod
    def from_function(cls, fn: Callable[..., Any], name: str | None = None) -> "AgentTool":
        name = name or fn.__name__
        if not TOOL_RE.match(name):
            raise ValueError(f"tool name {name!r} must be snake_case, <=42 chars")
        description, param_docs = _parse_docstring(fn.__doc__ or "")
        if not description:
            raise ValueError(f"tool {name!r} needs a docstring — it's what the AI routes on")
        hints = get_type_hints(fn)
        fields: dict[str, Any] = {}
        for pname, param in inspect.signature(fn).parameters.items():
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                raise ValueError(f"tool {name!r}: *args/**kwargs are not supported")
            ann = hints.get(pname, Any)
            default = ... if param.default is inspect.Parameter.empty else param.default
            fields[pname] = (ann, Field(default, description=param_docs.get(pname)))
        model = create_model(  # type: ignore[call-overload]
            f"{name}_args", __config__=ConfigDict(extra="ignore"), **fields
        )
        return cls(name=name, fn=fn, description=description, model=model)

    def input_schema(self) -> dict[str, Any]:
        schema = self.model.model_json_schema()
        schema.pop("title", None)
        for prop in schema.get("properties", {}).values():
            prop.pop("title", None)
        schema.setdefault("properties", {})
        return schema

    def call(self, arguments: dict[str, Any] | None) -> Any:
        try:
            parsed = self.model.model_validate(arguments or {})
        except ValidationError as e:
            problems = "; ".join(
                f"{'.'.join(str(p) for p in err['loc']) or 'input'}: {err['msg']}" for err in e.errors()
            )
            raise ToolError(f"Invalid arguments for {self.name}: {problems}") from None
        kwargs = {k: getattr(parsed, k) for k in self.model.model_fields}
        return self.fn(**kwargs)


@dataclass
class Agent:
    """A sellable agent: playbook + tools + storefront metadata."""

    slug: str
    name: str
    category: str
    tagline: str
    description: str
    playbook: str
    triggers: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    connectors: list[str] = field(default_factory=list)
    free: bool = False
    tools: list[AgentTool] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not SLUG_RE.match(self.slug):
            raise ValueError(f"bad agent slug {self.slug!r}")
        if self.category not in CATEGORIES:
            raise ValueError(f"{self.slug}: unknown category {self.category!r}")

    # ── registration ──────────────────────────────────────────
    def tool(self, fn: Callable[..., Any] | None = None, *, name: str | None = None):
        """Decorator: expose a function as one of this agent's MCP tools."""

        def register(f: Callable[..., Any]) -> Callable[..., Any]:
            t = AgentTool.from_function(f, name=name)
            if any(existing.name == t.name for existing in self.tools):
                raise ValueError(f"{self.slug}: duplicate tool {t.name!r}")
            self.tools.append(t)
            return f

        return register(fn) if fn is not None else register

    # ── naming on the wire ────────────────────────────────────
    @property
    def prefix(self) -> str:
        return self.slug.replace("-", "_")

    def wire_name(self, tool_name: str) -> str:
        return f"{self.prefix}__{tool_name}"

    @property
    def start_tool_name(self) -> str:
        return self.wire_name("start")

    def get_tool(self, name: str) -> AgentTool | None:
        return next((t for t in self.tools if t.name == name), None)

    # ── what the host AI sees ─────────────────────────────────
    def start_description(self) -> str:
        when = "; ".join(self.triggers[:6]) if self.triggers else self.tagline
        return (
            f"[{self.name}] {self.tagline} CALL THIS FIRST whenever the user wants: {when}. "
            "Returns the expert operating procedure and output format to follow, plus this "
            "agent's tool list. Pass the user's request as `task`."
        )

    def briefing(self, task: str = "") -> str:
        """The playbook plus a tool manifest, formatted for the host AI."""
        lines = [
            f"# {self.name} — operating procedure",
            "",
            "You are now running as this agent. Follow the procedure below exactly; it overrides "
            "your default style for this task. Use the listed tools for anything they cover — "
            "never do their math or scoring in your head.",
        ]
        if task:
            lines += ["", f"**User's task:** {task}"]
        lines += ["", inspect.cleandoc(self.playbook).strip(), ""]
        if self.tools:
            lines += ["## Your tools", ""]
            for t in self.tools:
                first = t.description.split("\n\n")[0].replace("\n", " ")
                lines.append(f"- `{self.wire_name(t.name)}` — {first}")
        if self.connectors:
            lines += [
                "",
                "## Other connectors",
                "If the user's AI has these connected, use them to act, not just advise: "
                + ", ".join(self.connectors)
                + ". If not, produce the output ready to paste.",
            ]
        return "\n".join(lines)

    def summary(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "category": self.category,
            "category_name": CATEGORIES[self.category],
            "tagline": self.tagline,
            "description": self.description,
            "triggers": self.triggers,
            "examples": self.examples,
            "connectors": self.connectors,
            "free": self.free,
            "tools": [t.name for t in self.tools],
        }


def render_result(value: Any) -> str:
    """Turn a tool's return value into the text the host AI reads."""
    if isinstance(value, str):
        return value
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)
