"""The Lead Scout agent loop.

Uses the Anthropic Tool Runner: we hand Claude the lead and the tools, and it
drives the loop itself — auditing the site, reading the real numbers back,
writing the CRM note, opening the deal, drafting the pitch.
"""

import anthropic

from . import config, tools
from .prompts import system_prompt


def run(lead: dict) -> None:
    """Work one lead, printing the agent's actions."""
    tools.set_lead(lead)
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY

    runner = client.beta.messages.tool_runner(
        model=config.MODEL,
        # Thinking is on by default on Opus 5 and shares this budget with the
        # response, so leave headroom — a tight cap truncates mid-pitch.
        max_tokens=16000,
        system=system_prompt(config.AGENCY_NAME),
        tools=tools.ALL_TOOLS,
        messages=[
            {
                "role": "user",
                "content": (
                    "A new lead just came in. Work it.\n\n"
                    f"Name: {lead.get('name', '')}\n"
                    f"Email: {lead.get('email', '')}\n"
                    f"Company: {lead.get('company', '')}\n"
                    f"Website: {lead.get('website', '')}"
                ),
            }
        ],
    )

    for message in runner:
        for block in message.content:
            if block.type == "text" and block.text.strip():
                print(f"\n🤖 {block.text.strip()}\n")
