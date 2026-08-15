"""GitHub connector — files the autopsy report as a real issue.

Live when GITHUB_TOKEN + GITHUB_REPO ("owner/repo") are set; dry-run otherwise.
"""

import requests

from .. import config

GITHUB_API = "https://api.github.com"


def open_issue(title: str, body: str, labels: list[str] | None = None) -> str:
    """Open a GitHub issue with the autopsy report. Returns the issue URL or a dry-run id."""
    labels = labels or ["regression", "commit-coroner"]

    if not config.github_live():
        print(f"   🔬 [GitHub · DRY-RUN] would open issue: {title!r}")
        for line in body.splitlines():
            print(f"      │ {line}")
        print(f"      │ labels: {', '.join(labels)}")
        return "github:dry-run://issues/0"

    resp = requests.post(
        f"{GITHUB_API}/repos/{config.GITHUB_REPO}/issues",
        headers={
            "Authorization": f"Bearer {config.GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
        json={"title": title, "body": body, "labels": labels},
        timeout=30,
    )
    resp.raise_for_status()
    url = resp.json().get("html_url", "github://issue")
    print(f"   🔬 [GitHub] opened issue: {url}")
    return url
