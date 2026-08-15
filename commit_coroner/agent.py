"""The Commit Coroner agent loop.

Uses the Anthropic Tool Runner: we hand Claude the failure report and the
tools, and it drives the investigation itself — pulling commit history,
reading diffs, naming a culprit, filing the report, and raising the alert.
"""

import anthropic

from . import config
from .prompts import SYSTEM_PROMPT
from .tools import ALL_TOOLS


def run(failure_report: str) -> None:
    """Run Commit Coroner over a CI failure report, printing the agent's actions."""
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY / ant profile

    runner = client.beta.messages.tool_runner(
        model=config.MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=ALL_TOOLS,
        messages=[
            {
                "role": "user",
                "content": f"A CI test just failed. Here is the failure report:\n\n{failure_report}",
            }
        ],
    )

    for message in runner:
        for block in message.content:
            if block.type == "text" and block.text.strip():
                print(f"\n🩺 {block.text.strip()}\n")
