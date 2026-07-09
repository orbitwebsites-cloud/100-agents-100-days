"""Notion connector — files the meeting notes as a real page.

Live when NOTION_API_KEY + NOTION_DATABASE_ID are set; dry-run otherwise.
"""

import requests

from .. import config

NOTION_API = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"


def _markdown_to_blocks(markdown: str) -> list[dict]:
    """Minimal markdown → Notion blocks. Handles headings and bullets."""
    blocks: list[dict] = []
    for line in markdown.splitlines():
        text = line.strip()
        if not text:
            continue
        if text.startswith("## "):
            blocks.append(_block("heading_2", text[3:]))
        elif text.startswith("# "):
            blocks.append(_block("heading_1", text[2:]))
        elif text.startswith(("- ", "* ")):
            blocks.append(_block("bulleted_list_item", text[2:]))
        else:
            blocks.append(_block("paragraph", text))
    return blocks


def _block(kind: str, content: str) -> dict:
    return {
        "object": "block",
        "type": kind,
        kind: {"rich_text": [{"type": "text", "text": {"content": content[:2000]}}]},
    }


def create_page(title: str, summary_markdown: str) -> str:
    """Create a Notion page for the meeting. Returns a page URL or dry-run id."""
    if not config.notion_live():
        print(f"   📝 [Notion · DRY-RUN] would file page: {title!r}")
        for line in summary_markdown.splitlines():
            if line.strip():
                print(f"      │ {line}")
        return "notion:dry-run://page/meeting-notes"

    resp = requests.post(
        NOTION_API,
        headers={
            "Authorization": f"Bearer {config.NOTION_API_KEY}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
        json={
            "parent": {"database_id": config.NOTION_DATABASE_ID},
            "properties": {
                "title": {"title": [{"text": {"content": title}}]},
            },
            "children": _markdown_to_blocks(summary_markdown),
        },
        timeout=30,
    )
    resp.raise_for_status()
    url = resp.json().get("url", "notion://page")
    print(f"   📝 [Notion] filed page: {url}")
    return url
