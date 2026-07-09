"""Linear connector — turns each action item into a real issue.

Live when LINEAR_API_KEY + LINEAR_TEAM_ID are set; dry-run otherwise.
"""

import requests

from .. import config

LINEAR_API = "https://api.linear.app/graphql"

_MUTATION = """
mutation IssueCreate($input: IssueCreateInput!) {
  issueCreate(input: $input) {
    success
    issue { identifier url title }
  }
}
"""


def create_issue(title: str, description: str = "", assignee: str = "") -> str:
    """Create a Linear issue. Returns the issue identifier/URL or a dry-run id."""
    if not config.linear_live():
        who = f" → {assignee}" if assignee else ""
        print(f"   ✅ [Linear · DRY-RUN] would create task: {title!r}{who}")
        if description:
            print(f"      │ {description}")
        return "linear:dry-run://ENG-000"

    body = description
    if assignee:
        body = (f"Owner (from transcript): {assignee}\n\n{description}").strip()

    resp = requests.post(
        LINEAR_API,
        headers={
            "Authorization": config.LINEAR_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "query": _MUTATION,
            "variables": {
                "input": {
                    "teamId": config.LINEAR_TEAM_ID,
                    "title": title,
                    "description": body,
                }
            },
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()["data"]["issueCreate"]
    issue = data["issue"]
    print(f"   ✅ [Linear] created {issue['identifier']}: {issue['url']}")
    return f"{issue['identifier']} — {issue['url']}"
