"""Environment configuration and the dry-run switch.

Every connector reads its keys from here. If a connector's keys are missing,
it runs in DRY-RUN mode: it prints exactly what it would have done and returns
a fake id. That means the whole agent works end-to-end with nothing but an
ANTHROPIC_API_KEY — you wire up Notion and Linear when you're ready.
"""

import os

from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-opus-4-8"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

LINEAR_API_KEY = os.getenv("LINEAR_API_KEY")
LINEAR_TEAM_ID = os.getenv("LINEAR_TEAM_ID")


def notion_live() -> bool:
    return bool(NOTION_API_KEY and NOTION_DATABASE_ID)


def linear_live() -> bool:
    return bool(LINEAR_API_KEY and LINEAR_TEAM_ID)
