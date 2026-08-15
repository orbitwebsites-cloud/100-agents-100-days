"""Slack connector — pings the channel with the incident alert.

Live when SLACK_WEBHOOK_URL is set (an Incoming Webhook URL); dry-run otherwise.
"""

import requests

from .. import config


def post_alert(message: str) -> str:
    """Post the autopsy alert to Slack. Returns 'posted' or a dry-run id."""
    if not config.slack_live():
        print(f"   💬 [Slack · DRY-RUN] would post to #incidents:")
        for line in message.splitlines():
            print(f"      │ {line}")
        return "slack:dry-run://message/0"

    resp = requests.post(config.SLACK_WEBHOOK_URL, json={"text": message}, timeout=30)
    resp.raise_for_status()
    print("   💬 [Slack] posted alert to #incidents")
    return "posted"
