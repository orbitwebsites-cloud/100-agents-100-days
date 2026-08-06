"""The Lead Scout agent loop on Cerebras (or any OpenAI-compatible endpoint).

Same agent, same tools, same audit engine — a different brain. Manual tool
loop: ask the model, execute the tool calls it makes, feed the results back,
repeat until it's done.
"""

import json

from openai import OpenAI

from . import config, tools
from .prompts import system_prompt

MAX_TURNS = 10  # safety cap so a confused model can't loop forever


def run(lead: dict) -> None:
    """Work one lead using the Cerebras backend."""
    tools.set_lead(lead)
    client = OpenAI(api_key=config.CEREBRAS_API_KEY, base_url=config.CEREBRAS_BASE_URL)

    messages: list[dict] = [
        {"role": "system", "content": system_prompt(config.AGENCY_NAME)},
        {
            "role": "user",
            "content": (
                "A new lead just came in. Work it.\n\n"
                f"Name: {lead.get('name', '')}\n"
                f"Email: {lead.get('email', '')}\n"
                f"Company: {lead.get('company', '')}\n"
                f"Website: {lead.get('website', '')}"
            ),
        },
    ]

    for _ in range(MAX_TURNS):
        resp = client.chat.completions.create(
            model=config.CEREBRAS_MODEL,
            messages=messages,
            tools=tools.OPENAI_TOOLS,
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
                print(f"\n🤖 {msg.content.strip()}\n")
            return

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = tools.dispatch(tc.function.name, args)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    print("\n⚠️  Reached the turn limit before the agent finished.\n")
