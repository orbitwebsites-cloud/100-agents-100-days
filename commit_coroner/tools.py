"""The agent's tools — git forensics evidence-gathering plus the two actions.

The model isn't handed a diff and asked to guess. It has to call
`list_suspect_commits`, then `inspect_commit` on the ones it's suspicious of,
before it's allowed to accuse anyone — same as a real investigation. Only
after it has evidence does it file the report and raise the alert.
"""

from anthropic import beta_tool

from .connectors import git_forensics, github, slack


@beta_tool
def list_suspect_commits(file_path: str, limit: int = 8) -> str:
    """List the most recent real commits that touched the failing file.

    Call this first, on the file named in the stack trace, to see who has
    touched it recently and might have introduced the regression.

    Args:
        file_path: Path (relative to repo root) of the file from the traceback.
        limit: How many recent commits to pull. Default 8.
    """
    return git_forensics.recent_commits_touching(file_path, limit)


@beta_tool
def inspect_commit(sha: str, file_path: str = "") -> str:
    """Pull the real diff for a commit so you can read exactly what it changed.

    Call this on any commit from `list_suspect_commits` you're suspicious of,
    before naming it as the culprit. Never accuse a commit you haven't inspected.

    Args:
        sha: The commit SHA to inspect.
        file_path: Optionally scope the diff to just this file.
    """
    return git_forensics.commit_diff(sha, file_path)


@beta_tool
def file_autopsy_report(title: str, body_markdown: str) -> str:
    """Open a GitHub issue with the completed autopsy report.

    Call this exactly once, after you've inspected at least one commit. The
    report must name a specific culprit commit (sha + subject) with your
    reasoning, or state plainly that the evidence was inconclusive.

    Args:
        title: e.g. "Autopsy: test_checkout_total fails as of a1b2c3d".
        body_markdown: Sections: "## Failure", "## Suspects examined",
            "## Verdict" (culprit sha + why, or inconclusive), "## Suggested fix".
    """
    return github.open_issue(title, body_markdown)


@beta_tool
def raise_incident_alert(message: str) -> str:
    """Post a short incident alert to Slack.

    Call this exactly once, after filing the report, so the team sees it
    immediately instead of finding it in a GitHub notification pile.

    Args:
        message: 2-4 lines: what broke, the named culprit (or "inconclusive"),
            and a link placeholder to the filed report.
    """
    return slack.post_alert(message)


ALL_TOOLS = [list_suspect_commits, inspect_commit, file_autopsy_report, raise_incident_alert]


# ── Provider-agnostic tool interface (Cerebras / OpenAI-compatible backend) ──

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_suspect_commits",
            "description": "List recent real commits that touched the failing file. Call first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path from the traceback."},
                    "limit": {"type": "integer", "description": "How many commits. Default 8."},
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_commit",
            "description": "Pull the real diff for a commit before accusing it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sha": {"type": "string", "description": "Commit SHA to inspect."},
                    "file_path": {"type": "string", "description": "Optionally scope to one file."},
                },
                "required": ["sha"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_autopsy_report",
            "description": "Open a GitHub issue with the completed autopsy report. Call once.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body_markdown": {
                        "type": "string",
                        "description": "## Failure / ## Suspects examined / ## Verdict / ## Suggested fix",
                    },
                },
                "required": ["title", "body_markdown"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "raise_incident_alert",
            "description": "Post a short incident alert to Slack. Call once, after filing the report.",
            "parameters": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
        },
    },
]


def dispatch(name: str, args: dict) -> str:
    """Execute a tool call by name — the same connectors the Anthropic tools use."""
    if name == "list_suspect_commits":
        return git_forensics.recent_commits_touching(args["file_path"], args.get("limit", 8))
    if name == "inspect_commit":
        return git_forensics.commit_diff(args["sha"], args.get("file_path", ""))
    if name == "file_autopsy_report":
        return github.open_issue(args["title"], args["body_markdown"])
    if name == "raise_incident_alert":
        return slack.post_alert(args["message"])
    return f"Error: unknown tool {name!r}"
