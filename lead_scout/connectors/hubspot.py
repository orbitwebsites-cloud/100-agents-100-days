"""HubSpot connector — writes the audit back onto the lead's record.

Live when HUBSPOT_ACCESS_TOKEN is set; dry-run otherwise. Two actions: attach
the audit as a note on the contact, and open a deal so the lead lands in the
pipeline instead of dying in an inbox.
"""

import time

import requests

from .. import config

NOTES_API = "https://api.hubapi.com/crm/v3/objects/notes"
DEALS_API = "https://api.hubapi.com/crm/v3/objects/deals"

# HubSpot association type ids for the default CRM schema.
NOTE_TO_CONTACT = 202
DEAL_TO_CONTACT = 3


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {config.HUBSPOT_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def _associations(to_id: str, type_id: int) -> list[dict]:
    return [
        {
            "to": {"id": to_id},
            "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": type_id}],
        }
    ]


def log_audit(contact_id: str, headline: str, body_markdown: str) -> str:
    """Attach the audit findings to the contact as a note."""
    if not config.hubspot_live():
        print(f"   📋 [HubSpot · DRY-RUN] would log audit note on contact {contact_id}: {headline!r}")
        for line in body_markdown.splitlines():
            if line.strip():
                print(f"      │ {line}")
        return "hubspot:dry-run://note/audit"

    resp = requests.post(
        NOTES_API,
        headers=_headers(),
        json={
            "properties": {
                "hs_note_body": f"<b>{headline}</b><br/><br/>"
                + body_markdown.replace("\n", "<br/>"),
                "hs_timestamp": int(time.time() * 1000),
            },
            "associations": _associations(contact_id, NOTE_TO_CONTACT),
        },
        timeout=30,
    )
    resp.raise_for_status()
    note_id = resp.json().get("id", "?")
    print(f"   📋 [HubSpot] logged audit note {note_id} on contact {contact_id}")
    return f"note:{note_id}"


def create_deal(contact_id: str, name: str, amount: str = "", stage: str = "appointmentscheduled") -> str:
    """Open a deal for the lead so it enters the pipeline."""
    if not config.hubspot_live():
        value = f" · {amount}" if amount else ""
        print(f"   💼 [HubSpot · DRY-RUN] would open deal {name!r}{value} on contact {contact_id}")
        return "hubspot:dry-run://deal/000"

    props = {"dealname": name, "dealstage": stage, "pipeline": "default"}
    if amount:
        digits = "".join(c for c in amount if c.isdigit())
        if digits:
            props["amount"] = digits

    resp = requests.post(
        DEALS_API,
        headers=_headers(),
        json={"properties": props, "associations": _associations(contact_id, DEAL_TO_CONTACT)},
        timeout=30,
    )
    resp.raise_for_status()
    deal_id = resp.json().get("id", "?")
    print(f"   💼 [HubSpot] opened deal {deal_id}: {name}")
    return f"deal:{deal_id}"
