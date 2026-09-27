"""Sign-in for AI apps (OAuth 2.1 with PKCE), so connecting is: paste one URL, sign in, ask.

Claude, ChatGPT, Cursor and VS Code all speak the MCP authorization spec: when
/mcp answers 401 they discover our authorization server, register themselves,
open our sign-in page, and store the token. The customer never sees a key.

Sign-in options on /connect:
  * email → 6-digit code → we attach the newest active subscription on that email,
    or connect the free agents if there is none (and the email becomes a lead);
  * or paste a license key from the welcome email (instant).

Tokens map to a license (``lic:<key hash>``) or to a free email (``free:<email>``),
and access still follows payment: a declined card pauses a token's paid agents
exactly as it does a key.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Any

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from .settings import settings
from .store import Store

SCOPE = "agents"
CODE_TTL = 300
PENDING_TTL = 1800
EMAIL_CODE_TTL = 600
EMAIL_CODE_ATTEMPTS = 5
ACCESS_TTL = 30 * 86400
REFRESH_TTL = 365 * 86400

SCHEMA = """
CREATE TABLE IF NOT EXISTS oauth_clients (client_id TEXT PRIMARY KEY, info TEXT NOT NULL, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS oauth_pending (req TEXT PRIMARY KEY, client_id TEXT NOT NULL, params TEXT NOT NULL,
    expires_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS oauth_codes (code_hash TEXT PRIMARY KEY, data TEXT NOT NULL, expires_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS oauth_tokens (token_hash TEXT PRIMARY KEY, kind TEXT NOT NULL, client_id TEXT NOT NULL,
    subject TEXT NOT NULL, scopes TEXT NOT NULL, resource TEXT, expires_at INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS oauth_tokens_subject ON oauth_tokens(subject);
CREATE TABLE IF NOT EXISTS email_codes (req TEXT PRIMARY KEY, email TEXT NOT NULL, code_hash TEXT NOT NULL,
    expires_at INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0);
"""


def _h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class HundredOAuth:
    """OAuthAuthorizationServerProvider backed by the license store."""

    def __init__(self, store: Store):
        self.store = store
        store._db.executescript(SCHEMA)

    # ── clients (dynamic registration) ───────────────────────
    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        row = self.store._exec("SELECT info FROM oauth_clients WHERE client_id=?", (client_id,)).fetchone()
        return OAuthClientInformationFull.model_validate_json(row[0]) if row else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self.store._exec("INSERT OR REPLACE INTO oauth_clients VALUES (?,?,?)",
                         (client_info.client_id, client_info.model_dump_json(), int(time.time())))

    # ── authorize: park the request, send the user to our sign-in page ──
    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        req = secrets.token_urlsafe(24)
        self.store._exec("DELETE FROM oauth_pending WHERE expires_at < ?", (int(time.time()),))
        self.store._exec("INSERT INTO oauth_pending VALUES (?,?,?,?)",
                         (req, client.client_id, params.model_dump_json(), int(time.time()) + PENDING_TTL))
        return f"{settings.public_url}/connect?req={req}"

    def pending(self, req: str) -> tuple[OAuthClientInformationFull, AuthorizationParams] | None:
        row = self.store._exec("SELECT client_id, params, expires_at FROM oauth_pending WHERE req=?", (req,)).fetchone()
        if not row or row[2] < time.time():
            return None
        info = self.store._exec("SELECT info FROM oauth_clients WHERE client_id=?", (row[0],)).fetchone()
        if not info:
            return None
        return OAuthClientInformationFull.model_validate_json(info[0]), AuthorizationParams.model_validate_json(row[1])

    def complete(self, req: str, subject: str) -> str:
        """Finish sign-in for ``subject``; returns the client redirect URL carrying the code."""
        found = self.pending(req)
        if found is None:
            raise AuthorizeError("invalid_request", "This sign-in link expired. Start again from your AI app.")
        client, params = found
        code = secrets.token_urlsafe(32)
        data = AuthorizationCode(
            code=code, scopes=params.scopes or [SCOPE], expires_at=time.time() + CODE_TTL, client_id=client.client_id,
            code_challenge=params.code_challenge, redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly, resource=params.resource,
            subject=subject,
        )
        self.store._exec("INSERT INTO oauth_codes VALUES (?,?,?)", (_h(code), data.model_dump_json(), int(data.expires_at)))
        self.store._exec("DELETE FROM oauth_pending WHERE req=?", (req,))
        return construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state)

    # ── codes and tokens ─────────────────────────────────────
    async def load_authorization_code(self, client: OAuthClientInformationFull, authorization_code: str):
        row = self.store._exec("SELECT data FROM oauth_codes WHERE code_hash=?", (_h(authorization_code),)).fetchone()
        if not row:
            return None
        code = AuthorizationCode.model_validate_json(row[0])
        if code.client_id != client.client_id or code.expires_at < time.time():
            return None
        return code

    def _issue(self, client_id: str, subject: str, scopes: list[str], resource: str | None) -> OAuthToken:
        access, refresh = "hnd_at_" + secrets.token_urlsafe(32), "hnd_rt_" + secrets.token_urlsafe(32)
        now = int(time.time())
        for token, kind, ttl in ((access, "access", ACCESS_TTL), (refresh, "refresh", REFRESH_TTL)):
            self.store._exec("INSERT INTO oauth_tokens VALUES (?,?,?,?,?,?,?)",
                             (_h(token), kind, client_id, subject, " ".join(scopes), resource, now + ttl))
        return OAuthToken(access_token=access, token_type="Bearer", expires_in=ACCESS_TTL, refresh_token=refresh,
                          scope=" ".join(scopes))

    async def exchange_authorization_code(self, client, authorization_code: AuthorizationCode) -> OAuthToken:
        gone = self.store._exec("DELETE FROM oauth_codes WHERE code_hash=?", (_h(authorization_code.code),))
        if gone.rowcount == 0:
            raise TokenError("invalid_grant", "authorization code already used")
        return self._issue(client.client_id, authorization_code.subject or "", authorization_code.scopes,
                           authorization_code.resource)

    def _token_row(self, token: str, kind: str):
        row = self.store._exec("SELECT client_id, subject, scopes, resource, expires_at FROM oauth_tokens "
                               "WHERE token_hash=? AND kind=?", (_h(token), kind)).fetchone()
        if not row or row[4] < time.time():
            return None
        return row

    async def load_refresh_token(self, client, refresh_token: str) -> RefreshToken | None:
        row = self._token_row(refresh_token, "refresh")
        if not row or row[0] != client.client_id:
            return None
        return RefreshToken(token=refresh_token, client_id=row[0], subject=row[1], scopes=row[2].split(),
                            resource=row[3], expires_at=row[4])

    async def exchange_refresh_token(self, client, refresh_token: RefreshToken, scopes: list[str]) -> OAuthToken:
        self.store._exec("DELETE FROM oauth_tokens WHERE token_hash=?", (_h(refresh_token.token),))  # rotate
        return self._issue(client.client_id, refresh_token.subject or "", scopes or refresh_token.scopes,
                           refresh_token.resource)

    async def load_access_token(self, token: str) -> AccessToken | None:
        row = self._token_row(token, "access")
        if not row:
            return None
        return AccessToken(token=token, client_id=row[0], subject=row[1], scopes=row[2].split(), resource=row[3],
                           expires_at=row[4])

    async def revoke_token(self, token) -> None:
        self.store._exec("DELETE FROM oauth_tokens WHERE token_hash=?", (_h(token.token),))

    # ── synchronous lookup for the MCP request path ──────────
    def subject_for(self, bearer: str) -> str | None:
        row = self._token_row(bearer, "access")
        return row[1] if row else None

    # ── email codes ──────────────────────────────────────────
    def start_email_code(self, req: str, email: str) -> str:
        code = f"{secrets.randbelow(1_000_000):06d}"
        self.store._exec("INSERT OR REPLACE INTO email_codes VALUES (?,?,?,?,0)",
                         (req, email.lower().strip(), _h(req + code), int(time.time()) + EMAIL_CODE_TTL))
        return code

    def check_email_code(self, req: str, code: str) -> str | None:
        """Returns the verified email, or None (wrong, expired, or too many attempts)."""
        row = self.store._exec("SELECT email, code_hash, expires_at, attempts FROM email_codes WHERE req=?",
                               (req,)).fetchone()
        if not row or row[2] < time.time() or row[3] >= EMAIL_CODE_ATTEMPTS:
            return None
        if not hmac.compare_digest(row[1], _h(req + code.strip())):
            self.store._exec("UPDATE email_codes SET attempts = attempts + 1 WHERE req=?", (req,))
            return None
        self.store._exec("DELETE FROM email_codes WHERE req=?", (req,))
        return row[0]


def subject_for_email(store: Store, email: str) -> str:
    """Newest active subscription on this email, else the free tier (and a new lead)."""
    for lic in store.by_email(email):
        if lic.active:
            return f"lic:{lic.key_hash}"
    for lic in store.by_email(email):  # paused/canceled: attach anyway so they see the fix-billing message
        return f"lic:{lic.key_hash}"
    store.add_lead(email, "oauth-connect")
    return f"free:{email.lower().strip()}"


def subject_from_bearer(store: Store, bearer: str) -> str | None:
    """Sync lookup for the MCP request path: the subject an access token was issued to."""
    try:
        row = store._exec("SELECT subject, expires_at FROM oauth_tokens WHERE token_hash=? AND kind='access'",
                          (_h(bearer),)).fetchone()
    except Exception:  # table not created yet (oauth never initialised)
        return None
    return row[0] if row and row[1] >= time.time() else None


def subject_for_key(store: Store, key: str) -> str | None:
    lic = store.by_key(key)
    return f"lic:{lic.key_hash}" if lic else None
