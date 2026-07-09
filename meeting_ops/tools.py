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
