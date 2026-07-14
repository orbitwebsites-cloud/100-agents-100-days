"""The Inbox Assistant agent loop on Cerebras (or any OpenAI-compatible endpoint).

Same agent, same tools, different brain — a manual tool loop over the
OpenAI-style chat-completions API, matching Meeting Ops's Cerebras backend.
"""

from openai import OpenAI

from agent_loop import run_openai_compatible

from . import config
from .prompts import SYSTEM_PROMPT
from .tools import OPENAI_TOOLS, dispatch


def ask(question: str) -> None:
    """Ask the Inbox Assistant a question using the Cerebras backend."""
    client = OpenAI(api_key=config.CEREBRAS_API_KEY, base_url=config.CEREBRAS_BASE_URL)
    run_openai_compatible(
        client, config.CEREBRAS_MODEL, SYSTEM_PROMPT, OPENAI_TOOLS, dispatch, question,
        max_tokens=2048, max_turns=6,
    )
