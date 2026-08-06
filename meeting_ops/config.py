"""Environment configuration and the dry-run switch.

Every connector reads its keys from here. If a connector's keys are missing,
it runs in DRY-RUN mode: it prints exactly what it would have done and returns
a fake id. That means the whole agent works end-to-end with nothing but an
ANTHROPIC_API_KEY — you wire up Notion and Linear when you're ready.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# ── Model provider ───────────────────────────────────────────
# Two ways to run the agent's brain:
#   • Anthropic (claude-opus-4-8) — set ANTHROPIC_API_KEY
#   • Cerebras (free tier — GPT-OSS/Qwen/Gemma) — set CEREBRAS_API_KEY
# Whichever key is present wins; Cerebras takes priority if both are set.
MODEL = "claude-opus-4-8"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
CEREBRAS_BASE_URL = os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1")
# Check https://inference-docs.cerebras.ai for the current model list — override
# with CEREBRAS_MODEL in .env. Pick a model that supports tool calling.
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "gpt-oss-120b")

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

LINEAR_API_KEY = os.getenv("LINEAR_API_KEY")
LINEAR_TEAM_ID = os.getenv("LINEAR_TEAM_ID")


def provider() -> str | None:
    """Which model backend to use, based on which key is set."""
    if CEREBRAS_API_KEY:
        return "cerebras"
    if ANTHROPIC_API_KEY:
        return "anthropic"
    return None


def notion_live() -> bool:
    return bool(NOTION_API_KEY and NOTION_DATABASE_ID)


def linear_live() -> bool:
    return bool(LINEAR_API_KEY and LINEAR_TEAM_ID)
