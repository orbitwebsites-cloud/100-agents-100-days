"""The Commit Coroner agent loop on Cerebras (or any OpenAI-compatible endpoint).

Same agent, same tools, same connectors — a different brain. Manual tool loop:
ask the model, execute any tool calls it makes, feed results back, repeat
until the investigation is closed.
"""

import json

from openai import OpenAI

from . import config
from .prompts import SYSTEM_PROMPT
from .tools import OPENAI_TOOLS, dispatch

MAX_TURNS = 10  # a real investigation needs a couple extra turns over Meeting Ops


def run(failure_report: str) -> None:
    """Run Commit Coroner over a CI failure report using the Cerebras backend."""
    client = OpenAI(api_key=config.CEREBRAS_API_KEY, base_url=config.CEREBRAS_BASE_URL)

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"A CI test just failed. Here is the failure report:\n\n{failure_report}",
        },
    ]

    for _ in range(MAX_TURNS):
        resp = client.chat.completions.create(
            model=config.CEREBRAS_MODEL,
            messages=messages,
            tools=OPENAI_TOOLS,
            max_tokens=4096,
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
                print(f"\n🩺 {msg.content.strip()}\n")
            return

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = dispatch(tc.function.name, args)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    print("\n⚠️  Reached the turn limit before the investigation closed.\n")
