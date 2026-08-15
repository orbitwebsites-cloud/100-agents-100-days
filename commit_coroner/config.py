"""Environment configuration and the dry-run switch.

Same philosophy as every agent in this build: missing keys mean a connector
runs in DRY-RUN and prints exactly what it would have done. Git forensics
needs no key at all — it reads the repo that's already on disk.
"""

import os

from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-opus-4-8"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
CEREBRAS_BASE_URL = os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1")
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "llama-3.3-70b")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")  # "owner/repo"

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")


def provider() -> str | None:
    """Which model backend to use, based on which key is set."""
    if CEREBRAS_API_KEY:
        return "cerebras"
    if ANTHROPIC_API_KEY:
        return "anthropic"
    return None


def github_live() -> bool:
    return bool(GITHUB_TOKEN and GITHUB_REPO)


def slack_live() -> bool:
    return bool(SLACK_WEBHOOK_URL)
