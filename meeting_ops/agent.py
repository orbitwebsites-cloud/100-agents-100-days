"""The Meeting Ops agent loop.

Uses the Anthropic Tool Runner: we hand Claude the transcript and the tools,
and it drives the loop itself — deciding to file notes, create each task, and
draft the follow-up, calling tools until the post-meeting workflow is done.
"""

import anthropic

from agent_loop import run_anthropic

from . import config
from .prompts import SYSTEM_PROMPT
from .tools import ALL_TOOLS


def run(transcript: str) -> None:
    """Run Meeting Ops over a transcript, printing the agent's actions."""
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY / ant profile
    user_content = f"A meeting just ended. Here is the transcript:\n\n{transcript}"
    run_anthropic(client, config.MODEL, SYSTEM_PROMPT, ALL_TOOLS, user_content)
