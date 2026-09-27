"""Transactional email: license keys, dunning, access restored.

Live through Resend when RESEND_API_KEY is set; otherwise dry-run (prints the
email) — same pattern as the Meeting Ops connectors.
"""

from __future__ import annotations

import logging

import requests

from .settings import settings

log = logging.getLogger("hundred.email")


def send(to: str, subject: str, text: str) -> str:
    if not settings.resend_api_key:
        log.warning("[email · DRY-RUN] to=%s subject=%r\n%s", to, subject, text)
        return "email:dry-run"
    resp = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json={"from": settings.email_from, "to": [to], "subject": subject, "text": text,
              "reply_to": settings.support_email},
        timeout=15,
    )
    if resp.status_code >= 300:
        log.error("email send failed %s: %s", resp.status_code, resp.text[:300])
        return "email:failed"
    return resp.json().get("id", "email:sent")


def connect_instructions(key: str) -> str:
    url = f"{settings.mcp_url}?key={key}"
    return f"""Your MCP link (keep it private — it's your key):

  {url}

Add it once to the AI you already use:

  • Claude (claude.ai / Desktop): Settings → Connectors → Add custom connector → paste the link.
  • ChatGPT: Settings → Apps & Connectors → Advanced → Developer mode → Create → paste the link.
  • Claude Code:  claude mcp add --transport http hundred "{url}"
  • Cursor / Windsurf / VS Code: add to your MCP config:
      {{"mcpServers": {{"hundred": {{"url": "{url}"}}}}}}

Then just ask for what you need ("write a cold email sequence for…") — your AI
will pick the right agent. Full setup guide: {settings.public_url}/setup
"""


def send_welcome(to: str, key: str, plan_name: str) -> str:
    return send(
        to,
        f"Your {settings.brand} agents are ready",
        f"Welcome to {settings.brand} — {plan_name}.\n\n{connect_instructions(key)}\n"
        f"Manage billing anytime: {settings.public_url}/account\n",
    )


def send_payment_failed(to: str) -> str:
    return send(
        to,
        f"Action needed: your card was declined — {settings.brand} agents paused",
        "Your latest payment didn't go through, so your agents are paused.\n\n"
        f"Update your card here and access comes back instantly: {settings.public_url}/account\n\n"
        "Nothing is lost — your key and your agents stay exactly as they were.\n",
    )


def send_restored(to: str) -> str:
    return send(
        to,
        f"You're back — {settings.brand} agents restored",
        "Payment received. Your agents are live again, same link as before.\n",
    )


def send_canceled(to: str) -> str:
    return send(
        to,
        f"Your {settings.brand} subscription has ended",
        "Your subscription ended and your agents are now off. The free agents keep working.\n\n"
        f"Come back anytime: {settings.public_url}/pricing\n",
    )
