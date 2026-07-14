"""The Inbox Assistant agent loop (Anthropic Tool Runner).

Same shape as Meeting Ops: hand Claude the question and the tools, and it
drives the loop itself — searching, and archiving when explicitly asked —
until it has a grounded answer.
"""

import anthropic

from . import config
from .prompts import SYSTEM_PROMPT
from .tools import ALL_TOOLS


def ask(question: str) -> None:
    """Ask the Inbox Assistant a question, printing its answer (and tool use)."""
    client = anthropic.Anthropic()

    runner = client.beta.messages.tool_runner(
        model=config.MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        tools=ALL_TOOLS,
        messages=[{"role": "user", "content": question}],
    )

    for message in runner:
        for block in message.content:
            if block.type == "text" and block.text.strip():
                print(f"\n🤖 {block.text.strip()}\n")
