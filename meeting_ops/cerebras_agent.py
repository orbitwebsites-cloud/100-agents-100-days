"""The Meeting Ops agent loop on Cerebras (or any OpenAI-compatible endpoint).

Same agent, same tools, same connectors — a different brain. Cerebras serves
open models over the OpenAI chat-completions API with tool calling,
so we run a manual tool loop: ask the model, execute any tool calls it makes,
feed the results back, repeat until it's done.
"""

import json

from openai import OpenAI

from . import config
from .prompts import SYSTEM_PROMPT
from .tools import OPENAI_TOOLS, dispatch

MAX_TURNS = 8  # safety cap so a confused model can't loop forever


def run(transcript: str) -> None:
    """Run Meeting Ops over a transcript using the Cerebras backend."""
    client = OpenAI(api_key=config.CEREBRAS_API_KEY, base_url=config.CEREBRAS_BASE_URL)

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"A meeting just ended. Here is the transcript:\n\n{transcript}"},
    ]

    for _ in range(MAX_TURNS):
        resp = client.chat.completions.create(
            model=config.CEREBRAS_MODEL,
            messages=messages,
            tools=OPENAI_TOOLS,
            max_tokens=4096,
        )
        msg = resp.choices[0].message

        # Record the assistant turn (portable dict form).
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
