"""Where new leads come from — the agent's trigger.

Live when HUBSPOT_ACCESS_TOKEN is set: polls HubSpot for recently-created
contacts that carry a website, and hands over the ones we haven't worked yet.
Without a token it reads the bundled sample leads instead, so the poll loop and
the whole agent are demoable before you connect an account.

A lead is a dict: {id, name, email, company, website}.
"""

import json
from pathlib import Path

import requests

from . import config, state

HUBSPOT_SEARCH = "https://api.hubapi.com/crm/v3/objects/contacts/search"
SAMPLE_LEADS = Path(__file__).resolve().parent.parent / "samples" / "sample_leads.json"

# The contact properties we need to pitch someone.
PROPERTIES = ["firstname", "lastname", "email", "company", "website", "createdate"]


def _from_hubspot(limit: int) -> list[dict]:
    resp = requests.post(
        HUBSPOT_SEARCH,
        headers={
            "Authorization": f"Bearer {config.HUBSPOT_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "sorts": [{"propertyName": "createdate", "direction": "DESCENDING"}],
            "properties": PROPERTIES,
            "limit": limit,
        },
        timeout=30,
    )
    resp.raise_for_status()

    leads = []
    for row in resp.json().get("results", []):
        p = row.get("properties") or {}
        name = " ".join(x for x in (p.get("firstname"), p.get("lastname")) if x).strip()
        leads.append(
            {
                "id": str(row["id"]),
                "name": name or p.get("email") or "there",
                "email": p.get("email") or "",
                "company": p.get("company") or "",
                "website": p.get("website") or "",
            }
        )
    return leads


def _from_samples() -> list[dict]:
    if not SAMPLE_LEADS.exists():
        return []
    return json.loads(SAMPLE_LEADS.read_text(encoding="utf-8"))


def fetch_new(limit: int = 10, include_seen: bool = False) -> list[dict]:
    """Leads we haven't worked yet, newest first.

    This is the trigger: nothing happens unless a lead the agent has never seen
    shows up with a website on it.
    """
    leads = _from_hubspot(limit) if config.hubspot_live() else _from_samples()

    fresh = []
    for lead in leads:
        if not lead.get("website"):
            continue  # nothing to audit — not a lead this agent can work
        if not include_seen and state.already_seen(lead["id"]):
            continue
        fresh.append(lead)
    return fresh
