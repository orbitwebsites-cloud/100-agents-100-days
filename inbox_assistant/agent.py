"""The Inbox Assistant agent loop (Anthropic Tool Runner).

Same shape as Meeting Ops: hand Claude the question and the tools, and it
drives the loop itself — searching, and archiving when explicitly asked —
until it has a grounded answer.
"""

import anthropic

from agent_loop import run_anthropic

from . import config
from .prompts import SYSTEM_PROMPT
from .tools import ALL_TOOLS


def ask(question: str) -> None:
    """Ask the Inbox Assistant a question, printing its answer (and tool use)."""
    client = anthropic.Anthropic()
    run_anthropic(client, config.MODEL, SYSTEM_PROMPT, ALL_TOOLS, question, max_tokens=2048)
