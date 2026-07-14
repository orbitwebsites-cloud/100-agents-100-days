"""Shared tool-calling loops used by every agent in this repo.

Two backends, one shape: hand the model a system prompt, tools, and a
starting message, let it call tools until it's done, print what it says.
Each agent supplies its own system prompt, tools, and dispatch function —
this module just runs the loop.
"""

import json


def run_anthropic(
    client, model: str, system: str, tools: list, user_content: str, max_tokens: int = 4096,
    history: list[dict] | None = None,
) -> str:
    """Run an Anthropic Tool Runner loop, printing and returning the reply text."""
    messages = (history or []) + [{"role": "user", "content": user_content}]
    runner = client.beta.messages.tool_runner(
        model=model,
        max_tokens=max_tokens,
        system=system,
        tools=tools,
        messages=messages,
    )
    replies = []
    for message in runner:
        for block in message.content:
            if block.type == "text" and block.text.strip():
                print(f"\n🤖 {block.text.strip()}\n")
                replies.append(block.text.strip())
    return "\n\n".join(replies)


def _run_tool_calls(msg, dispatch, messages: list[dict]) -> None:
    """Execute each tool call on msg and append the tool results to messages."""
    for tc in msg.tool_calls:
        try:
            args = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        result = dispatch(tc.function.name, args)
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})


def run_openai_compatible(
    client,
    model: str,
    system: str,
    openai_tools: list,
    dispatch,
    user_content: str,
    max_tokens: int = 4096,
    max_turns: int = 8,
    history: list[dict] | None = None,
) -> str:
    """Run a manual tool loop over an OpenAI-compatible chat-completions API."""
    messages: list[dict] = [
        {"role": "system", "content": system},
        *(history or []),
        {"role": "user", "content": user_content},
    ]

    for _ in range(max_turns):
        resp = client.chat.completions.create(
            model=model, messages=messages, tools=openai_tools, max_tokens=max_tokens
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
            reply = (msg.content or "").strip()
            if reply:
                print(f"\n🤖 {reply}\n")
            return reply

        _run_tool_calls(msg, dispatch, messages)

    warning = "Reached the turn limit before the agent finished."
    print(f"\n⚠️  {warning}\n")
    return warning
