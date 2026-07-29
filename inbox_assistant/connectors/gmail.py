"""Gmail connector — reads the inbox, archives messages.

Dry-run by default, same as before: without a token file (see
`GMAIL_TOKEN_FILE` in config.py), fetch_recent() serves the bundled sample
inbox and archive() just prints what it would do. Run
`python run_inbox.py --gmail-auth` once, with a Google Cloud OAuth client
secrets file at `GMAIL_CREDENTIALS_FILE`, to switch this connector to a real
Gmail inbox — the ingestion worker and agent tools don't change either way,
only this file does.

The googleapiclient / google-auth imports are deliberately deferred into the
functions that need them: importing this module (or running in dry-run) must
never require those packages to be installed.
"""

import base64
import json
from datetime import datetime, timezone
from email.utils import parseaddr

from .. import config


def _load_credentials():
    """Load stored OAuth credentials, refreshing them if expired."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = Credentials.from_authorized_user_file(str(config.GMAIL_TOKEN_FILE), config.GMAIL_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        config.GMAIL_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return creds


def authorize() -> None:
    """Run the local OAuth consent flow and save the token file.

    Requires a Google Cloud OAuth client secrets JSON at
    `GMAIL_CREDENTIALS_FILE` (Desktop app credentials work fine). Opens a
    browser for consent, then writes the refreshable token to
    `GMAIL_TOKEN_FILE`.
    """
    if not config.GMAIL_CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            f"No OAuth client secrets file at {config.GMAIL_CREDENTIALS_FILE}. "
            "Create an OAuth Desktop client in Google Cloud Console, download the "
            "JSON, and save it there (or point GMAIL_CREDENTIALS_FILE at it)."
        )

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(config.GMAIL_CREDENTIALS_FILE), config.GMAIL_SCOPES)
    creds = flow.run_local_server(port=0)
    config.GMAIL_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.GMAIL_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    print(f"✅ Gmail authorized. Token saved to {config.GMAIL_TOKEN_FILE}")


def _get_service():
    from googleapiclient.discovery import build

    return build("gmail", "v1", credentials=_load_credentials())


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _decode_part(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def _extract_body(payload: dict) -> str:
    """Walk a Gmail API message payload for the first text/plain (or text/html) part."""
    if payload.get("mimeType", "").startswith("text/") and payload.get("body", {}).get("data"):
        return _decode_part(payload["body"]["data"])
    for part in payload.get("parts", []) or []:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return _decode_part(part["body"]["data"])
    for part in payload.get("parts", []) or []:
        body = _extract_body(part)
        if body:
            return body
    return ""


def parse_message(raw: dict) -> dict:
    """Convert a Gmail API `messages.get(format="full")` resource into our raw-email shape.

    Pure function — no API calls — so it's testable against a plain dict
    fixture without needing googleapiclient installed.
    """
    payload = raw.get("payload", {})
    headers = payload.get("headers", [])
    _, sender_addr = parseaddr(_header(headers, "From"))
    received_at = datetime.fromtimestamp(
        int(raw["internalDate"]) / 1000, tz=timezone.utc
    ).isoformat()
    return {
        "message_id": raw["id"],
        "received_at": received_at,
        "from": sender_addr or _header(headers, "From"),
        "subject": _header(headers, "Subject"),
        "body": _extract_body(payload),
    }


def fetch_recent(limit: int = 50) -> list[dict]:
    """Return recent raw emails as dicts with from/subject/body/received_at."""
    if not config.gmail_live():
        print(f"   📬 [Gmail · DRY-RUN] reading bundled sample inbox ({config.SAMPLE_INBOX.name})")
        emails = json.loads(config.SAMPLE_INBOX.read_text(encoding="utf-8"))
        return emails[:limit]

    service = _get_service()
    listing = service.users().messages().list(userId="me", labelIds=["INBOX"], maxResults=limit).execute()
    ids = [m["id"] for m in listing.get("messages", [])]
    emails = []
    for message_id in ids:
        raw = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        emails.append(parse_message(raw))
    return emails


def archive_message(message_id: str) -> str:
    """Archive a message in Gmail (remove INBOX label). Returns a status string."""
    if not config.gmail_live():
        print(f"   🗄️  [Gmail · DRY-RUN] would archive message {message_id}")
        return f"gmail:dry-run://archived/{message_id}"

    service = _get_service()
    service.users().messages().modify(userId="me", id=message_id, body={"removeLabelIds": ["INBOX"]}).execute()
    return f"gmail://archived/{message_id}"
