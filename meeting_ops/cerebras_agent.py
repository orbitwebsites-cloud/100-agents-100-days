"""The Meeting Ops agent loop on Cerebras (or any OpenAI-compatible endpoint).

Same agent, same tools, same connectors — a different brain. Cerebras serves
open models (Llama/Qwen) over the OpenAI chat-completions API with tool calling,
so we run a manual tool loop: ask the model, execute any tool calls it makes,
feed the results back, repeat until it's done.
"""

from openai import OpenAI

from agent_loop import run_openai_compatible

from . import config
from .prompts import SYSTEM_PROMPT
from .tools import OPENAI_TOOLS, dispatch


def run(transcript: str) -> None:
    """Run Meeting Ops over a transcript using the Cerebras backend."""
    client = OpenAI(api_key=config.CEREBRAS_API_KEY, base_url=config.CEREBRAS_BASE_URL)
    user_content = f"A meeting just ended. Here is the transcript:\n\n{transcript}"
    run_openai_compatible(
        client, config.CEREBRAS_MODEL, SYSTEM_PROMPT, OPENAI_TOOLS, dispatch, user_content, max_turns=8
    )
