"""Server settings, all from the environment (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    public_url: str = os.getenv("PUBLIC_URL", "http://localhost:8000").rstrip("/")
    brand: str = os.getenv("BRAND_NAME", "Hundred")
    database_path: str = os.getenv("DATABASE_PATH", "hundred.db")

    stripe_secret_key: str = os.getenv("STRIPE_SECRET_KEY", "")
    stripe_webhook_secret: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    trial_days: int = _int("TRIAL_DAYS", 7)

    resend_api_key: str = os.getenv("RESEND_API_KEY", "")
    email_from: str = os.getenv("EMAIL_FROM", "Hundred <agents@example.com>")
    support_email: str = os.getenv("SUPPORT_EMAIL", "support@example.com")

    # Abuse / key-sharing guard: tool calls per key per UTC day.
    daily_call_limit: int = _int("DAILY_CALL_LIMIT", 3000)
    # Above this many tools, a connection switches to router mode (3 meta-tools)
    # so clients with tool caps (Cursor ~40) keep working with All-Access.
    direct_tool_limit: int = _int("DIRECT_TOOL_LIMIT", 40)

    @property
    def stripe_live(self) -> bool:
        return bool(self.stripe_secret_key)

    @property
    def mcp_url(self) -> str:
        return f"{self.public_url}/mcp"


settings = Settings()
