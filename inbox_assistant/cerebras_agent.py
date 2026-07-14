"""The Inbox Assistant agent loop on Cerebras (or any OpenAI-compatible endpoint).

Same agent, same tools, different brain — a manual tool loop over the
OpenAI-style chat-completions API, matching Meeting Ops's Cerebras backend.
"""

import json

from openai import OpenAI

from . import config
from .prompts import SYSTEM_PROMPT
from .tools import OPENAI_TOOLS, dispatch

MAX_TURNS = 6


def ask(question: str) -> None:
    """Ask the Inbox Assistant a question using the Cerebras backend."""
    client = OpenAI(api_key=config.CEREBRAS_API_KEY, base_url=config.CEREBRAS_BASE_URL)

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    for _ in range(MAX_TURNS):
        resp = client.chat.completions.create(
            model=config.CEREBRAS_MODEL,
            messages=messages,
            tools=OPENAI_TOOLS,
            max_tokens=2048,
        )
        msg = resp.choices[0].message

        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in (msg.tool_calls or [])
                ],
            }
        )

        if not msg.tool_calls:
            if msg.content and msg.content.strip():
                print(f"\n🤖 {msg.content.strip()}\n")
            return

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = dispatch(tc.function.name, args)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    print("\n⚠️  Reached the turn limit before the agent finished.\n")
