"""Environment configuration and the dry-run switch.

Same deal as Agent #1: every connector reads its keys from here, and a
connector with missing keys runs in DRY-RUN mode — it prints exactly what it
would have done and returns a fake id. The *audit* is never dry-run: it always
hits the real website, because that's the part that makes this an agent.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# ── Model provider ───────────────────────────────────────────
# Two ways to run the agent's brain:
#   • Anthropic (claude-opus-5) — set ANTHROPIC_API_KEY
#   • Cerebras (free tier — GPT-OSS/Qwen/Gemma) — set CEREBRAS_API_KEY
# Whichever key is present wins; Cerebras takes priority if both are set.
MODEL = "claude-opus-5"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
CEREBRAS_BASE_URL = os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1")
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "gpt-oss-120b")

# ── HubSpot — the trigger source and where findings get written ──
HUBSPOT_ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN")

# ── PageSpeed Insights — optional real Lighthouse scores ──
# Without a key the audit still measures load time itself; with one you also
# get Google's own performance score for the prospect's site.
PAGESPEED_API_KEY = os.getenv("PAGESPEED_API_KEY")

# ── Agency details, used to write the pitch in your voice ──
AGENCY_NAME = os.getenv("AGENCY_NAME", "Orbit Websites")
AGENCY_SENDER = os.getenv("AGENCY_SENDER", "orbitwebsites@gmail.com")

# How often the watcher polls for new leads, in seconds.
POLL_INTERVAL = int(os.getenv("SCOUT_POLL_INTERVAL", "300"))


def provider() -> str | None:
    """Which model backend to use, based on which key is set."""
    if CEREBRAS_API_KEY:
        return "cerebras"
    if ANTHROPIC_API_KEY:
        return "anthropic"
    return None


def available_models() -> list[str]:
    """Model ids this key can actually reach, newest-looking first.

    Cerebras rotates its lineup, so a hardcoded default eventually 404s. Ask the
    endpoint instead of guessing.
    """
    import requests

    if not CEREBRAS_API_KEY:
        return []
    resp = requests.get(
        f"{CEREBRAS_BASE_URL.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {CEREBRAS_API_KEY}"},
        timeout=30,
    )
    resp.raise_for_status()
    return sorted(m["id"] for m in resp.json().get("data", []))


def hubspot_live() -> bool:
    return bool(HUBSPOT_ACCESS_TOKEN)


def pagespeed_live() -> bool:
    return bool(PAGESPEED_API_KEY)
