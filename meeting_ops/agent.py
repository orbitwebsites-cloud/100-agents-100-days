"""The Meeting Ops agent loop.

Uses the Anthropic Tool Runner: we hand Claude the transcript and the tools,
and it drives the loop itself — deciding to file notes, create each task, and
draft the follow-up, calling tools until the post-meeting workflow is done.
"""

import anthropic

from . import config
from .tools import ALL_TOOLS

SYSTEM_PROMPT = """\
You are Meeting Ops, an agent that runs the entire post-meeting workflow.

You are given the transcript of a meeting that just ended. Do all of the following,
using your tools — do not just describe the work, take the actions:

1. Call `file_meeting_notes` ONCE to file a clean summary + decisions to Notion.
2. Call `create_task` once for EACH concrete action item — something a specific
   person committed to. Set the assignee to whoever owns it. Skip vague chatter.
3. Call `draft_followup_email` ONCE to draft a follow-up to the attendees, with a
   one-line recap and an owner → task list.

Be precise and grounded strictly in the transcript. Do not invent action items,
owners, dates, or decisions that were not actually stated. When you have taken all
the actions, reply with a one-line confirmation of what you did.\
"""


def run(transcript: str) -> None:
    """Run Meeting Ops over a transcript, printing the agent's actions."""
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY / ant profile

    runner = client.beta.messages.tool_runner(
        model=config.MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=ALL_TOOLS,
        messages=[
            {
                "role": "user",
                "content": f"A meeting just ended. Here is the transcript:\n\n{transcript}",
            }
        ],
    )

    for message in runner:
        for block in message.content:
            if block.type == "text" and block.text.strip():
                print(f"\n🤖 {block.text.strip()}\n")
