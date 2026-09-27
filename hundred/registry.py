"""Discovers every agent under hundred/agents/<category>/<agent>.py.

Each agent module defines a module-level ``AGENT``. Dropping a new file in the
right folder is all it takes to ship a new agent — the storefront, catalog,
MCP server and billing all read from here.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from functools import lru_cache

from .core import Agent

log = logging.getLogger("hundred.registry")

# Modules that failed to import. Production skips them (one bad agent must not
# take the whole server down); tests assert this stays empty.
LOAD_ERRORS: dict[str, str] = {}


@lru_cache(maxsize=1)
def all_agents() -> dict[str, Agent]:
    from . import agents as pkg

    found: dict[str, Agent] = {}
    for info in pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + "."):
        if info.ispkg or info.name.rsplit(".", 1)[-1].startswith("_"):
            continue
        try:
            module = importlib.import_module(info.name)
        except Exception as e:  # noqa: BLE001
            LOAD_ERRORS[info.name] = f"{type(e).__name__}: {e}"
            log.error("skipping agent module %s: %s", info.name, e)
            continue
        agent = getattr(module, "AGENT", None)
        if not isinstance(agent, Agent):
            continue
        if agent.slug in found:
            raise RuntimeError(f"duplicate agent slug {agent.slug!r} in {info.name}")
        expected_category = info.name.split(".")[-2]
        if agent.category != expected_category:
            raise RuntimeError(f"{info.name}: category {agent.category!r} != folder {expected_category!r}")
        found[agent.slug] = agent
    return dict(sorted(found.items(), key=lambda kv: (kv[1].category, kv[1].name)))


def get(slug: str) -> Agent | None:
    return all_agents().get(slug)


def by_category() -> dict[str, list[Agent]]:
    out: dict[str, list[Agent]] = {}
    for agent in all_agents().values():
        out.setdefault(agent.category, []).append(agent)
    return out


def free_slugs() -> set[str]:
    return {a.slug for a in all_agents().values() if a.free}
