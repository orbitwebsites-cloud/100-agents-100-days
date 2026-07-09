"""The agent's tools.

These are what make Meeting Ops an agent and not a prompt: the model doesn't
just *describe* the notes, tasks, and email — it *takes the actions* by calling
these tools, which reach into Notion, Linear, and Gmail. The Tool Runner runs
the loop; each function below is one thing the agent can actually do.
"""

from anthropic import beta_tool

from .connectors import gmail, linear, notion


@beta_tool
def file_meeting_notes(title: str, summary_markdown: str) -> str:
    """File the meeting summary as a page in Notion.

    Call this exactly once, after you've read the transcript, to record what
    the meeting was about and what was decided.

    Args:
        title: A short, specific page title, e.g. "Product Sync — Jul 13".
        summary_markdown: The summary in markdown. Use a "## Summary" section
            of 2-4 sentences and a "## Decisions" bulleted list.
    """
    return notion.create_page(title, summary_markdown)


@beta_tool
def create_task(title: str, description: str = "", assignee: str = "") -> str:
    """Create a Linear task for one action item from the meeting.

    Call this once per action item. An action item is something a specific
    person committed to doing. Do not create tasks for vague discussion.

    Args:
        title: The task as an imperative, e.g. "Wire up checkout error states".
        description: One or two sentences of context from the transcript.
        assignee: The name of the person who owns it, if stated.
    """
    return linear.create_issue(title, description, assignee)


@beta_tool
def draft_followup_email(to: str, subject: str, body: str) -> str:
    """Draft a follow-up email to the attendees.

    Call this exactly once, at the end, summarizing outcomes and listing who
    owns what. Write it in a warm, concise voice — ready to send after a glance.

    Args:
        to: Comma-separated attendee names or emails.
        subject: A specific subject line referencing the meeting.
        body: The email body. Open with a one-line recap, then a short
            "Action items" list of owner → task, then a brief sign-off.
    """
    return gmail.create_draft(to, subject, body)


ALL_TOOLS = [file_meeting_notes, create_task, draft_followup_email]


# ── Provider-agnostic tool interface (used by the Cerebras/OpenAI backend) ──
# The Anthropic Tool Runner reads the @beta_tool functions above. OpenAI-style
# APIs (Cerebras) need JSON schemas + a manual dispatch — same connectors.

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "file_meeting_notes",
            "description": "File the meeting summary as a page in Notion. Call once.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short, specific page title."},
                    "summary_markdown": {
                        "type": "string",
                        "description": "Markdown with a '## Summary' (2-4 sentences) and '## Decisions' bullets.",
                    },
                },
                "required": ["title", "summary_markdown"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a Linear task for one action item. Call once per action item.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "The task as an imperative."},
                    "description": {"type": "string", "description": "One or two sentences of context."},
                    "assignee": {"type": "string", "description": "Name of the owner, if stated."},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_followup_email",
            "description": "Draft the follow-up email to attendees. Call once, at the end.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Comma-separated attendee names or emails."},
                    "subject": {"type": "string", "description": "Specific subject line."},
                    "body": {"type": "string", "description": "Recap line, then owner → task list, then sign-off."},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
]


def dispatch(name: str, args: dict) -> str:
    """Execute a tool call by name — the same connectors the Anthropic tools use."""
    if name == "file_meeting_notes":
        return notion.create_page(args["title"], args["summary_markdown"])
    if name == "create_task":
        return linear.create_issue(
            args.get("title", ""), args.get("description", ""), args.get("assignee", "")
        )
    if name == "draft_followup_email":
        return gmail.create_draft(args["to"], args["subject"], args["body"])
    return f"Error: unknown tool {name!r}"
