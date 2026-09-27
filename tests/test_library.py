"""Quality gates every agent in the library must pass."""

import re

import pytest

from hundred import registry
from hundred.core import CATEGORIES

AGENTS = list(registry.all_agents().values())
IDS = [a.slug for a in AGENTS]


def test_every_agent_module_imports():
    assert registry.LOAD_ERRORS == {}


def test_library_is_big():
    assert len(AGENTS) >= 1


@pytest.mark.parametrize("agent", AGENTS, ids=IDS)
def test_agent_metadata(agent):
    assert agent.category in CATEGORIES
    assert 20 <= len(agent.tagline) <= 140, "tagline: one crisp sentence"
    assert len(agent.description) >= 120
    assert len(agent.triggers) >= 4
    assert len(agent.examples) >= 3


@pytest.mark.parametrize("agent", AGENTS, ids=IDS)
def test_agent_playbook_quality(agent):
    pb = agent.playbook
    words = len(re.findall(r"\w+", pb))
    assert words >= 450, f"playbook too thin ({words} words)"
    for section in ("## Procedure", "## Output format", "## Anti-patterns"):
        assert section in pb, f"missing {section}"
    for t in agent.tools:
        assert f"{agent.prefix}__{t.name}" in pb, f"playbook never tells the AI when to call {t.name}"


@pytest.mark.parametrize("agent", AGENTS, ids=IDS)
def test_agent_tools(agent):
    assert 3 <= len(agent.tools) <= 7
    for t in agent.tools:
        assert len(agent.wire_name(t.name)) <= 64
        assert len(t.description) >= 40
        schema = t.input_schema()
        for name, prop in schema["properties"].items():
            assert prop.get("description"), f"{t.name}.{name} has no Args: description"


def test_tool_names_unique_on_the_wire():
    names = [a.wire_name(t.name) for a in AGENTS for t in a.tools]
    assert len(names) == len(set(names))
