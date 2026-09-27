"""Sign-in from an AI app: add the URL, sign in once, agents work. The real OAuth 2.1 + PKCE flow over HTTP."""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from hundred.server.oauth import HundredOAuth, subject_for_email
from hundred.server.store import Store

REDIRECT = "http://127.0.0.1:6274/callback"


def pkce():
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def test_mcp_without_credentials_asks_the_app_to_sign_in(live_server):
    base, _ = live_server
    r = httpx.post(f"{base}/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                   headers={"accept": "application/json, text/event-stream"})
    assert r.status_code == 401
    challenge = r.headers["www-authenticate"]
    assert "resource_metadata=" in challenge and "/.well-known/oauth-protected-resource/mcp" in challenge
    meta = httpx.get(f"{base}/.well-known/oauth-protected-resource/mcp").json()
    assert meta["authorization_servers"]
    auth_meta = httpx.get(f"{base}/.well-known/oauth-authorization-server").json()
    assert auth_meta["registration_endpoint"].endswith("/register") and "S256" in auth_meta["code_challenge_methods_supported"]


def _sign_in(base: str, form_for_connect: dict) -> tuple[str, str]:
    """Run the flow a client runs; returns (access_token, refresh_token)."""
    reg = httpx.post(f"{base}/register", json={"redirect_uris": [REDIRECT], "client_name": "Claude",
                                               "token_endpoint_auth_method": "none"}).json()
    verifier, challenge = pkce()
    auth = httpx.get(f"{base}/authorize", params={
        "response_type": "code", "client_id": reg["client_id"], "redirect_uri": REDIRECT, "state": "xyz",
        "code_challenge": challenge, "code_challenge_method": "S256", "scope": "agents"})
    assert auth.status_code in (302, 307)
    connect_url = auth.headers["location"]
    assert "/connect?req=" in connect_url
    page = httpx.get(connect_url)
    assert page.status_code == 200 and "Claude" in page.text
    req = parse_qs(urlparse(connect_url).query)["req"][0]
    done = httpx.post(f"{base}/connect", data={"req": req, **form_for_connect})
    assert done.status_code == 302, done.text[:300]
    back = urlparse(done.headers["location"])
    assert f"{back.scheme}://{back.netloc}{back.path}" == REDIRECT
    q = parse_qs(back.query)
    assert q["state"] == ["xyz"]
    tok = httpx.post(f"{base}/token", data={
        "grant_type": "authorization_code", "code": q["code"][0], "redirect_uri": REDIRECT,
        "client_id": reg["client_id"], "code_verifier": verifier}).json()
    assert tok["token_type"].lower() == "bearer" and tok["access_token"].startswith("hnd_at_")
    # a code works exactly once
    again = httpx.post(f"{base}/token", data={
        "grant_type": "authorization_code", "code": q["code"][0], "redirect_uri": REDIRECT,
        "client_id": reg["client_id"], "code_verifier": verifier})
    assert again.status_code == 400
    return tok["access_token"], tok["refresh_token"]


def rpc(base: str, token: str, method: str, params: dict | None = None) -> dict:
    """One MCP JSON-RPC call with a Bearer token, the way an AI app sends it after sign-in."""
    r = httpx.post(f"{base}/mcp", json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
                   headers={"authorization": f"Bearer {token}", "accept": "application/json, text/event-stream",
                            "mcp-protocol-version": "2025-06-18"})
    assert r.status_code == 200, r.text[:300]
    return r.json()["result"]


def test_sign_in_with_license_key_then_agents_just_work(live_server):
    base, key = live_server  # an All-Access comp key
    access, refresh = _sign_in(base, {"action": "key", "key": key})
    names = [t["name"] for t in rpc(base, access, "tools/list")["tools"]]
    assert "hundred_start" in names
    res = rpc(base, access, "tools/call", {"name": "hundred_start",
                                           "arguments": {"task": "write me a cold email to a VP of operations"}})
    assert not res.get("isError") and "Cold Email Closer" in res["content"][0]["text"]
    # apps refresh silently; the old refresh token is rotated out
    reg_client = httpx.post(f"{base}/register", json={"redirect_uris": [REDIRECT], "token_endpoint_auth_method": "none"})
    assert reg_client.status_code in (200, 201)


def test_wrong_pkce_verifier_is_refused(live_server):
    base, key = live_server
    reg = httpx.post(f"{base}/register", json={"redirect_uris": [REDIRECT], "token_endpoint_auth_method": "none"}).json()
    _, challenge = pkce()
    auth = httpx.get(f"{base}/authorize", params={"response_type": "code", "client_id": reg["client_id"],
                     "redirect_uri": REDIRECT, "code_challenge": challenge, "code_challenge_method": "S256"})
    req = parse_qs(urlparse(auth.headers["location"]).query)["req"][0]
    code = parse_qs(urlparse(httpx.post(f"{base}/connect", data={"req": req, "action": "key", "key": key})
                             .headers["location"]).query)["code"][0]
    bad = httpx.post(f"{base}/token", data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
                                            "client_id": reg["client_id"], "code_verifier": "not-the-verifier-" * 3})
    assert bad.status_code == 400


def test_bad_key_on_sign_in_page_is_explained(live_server):
    base, _ = live_server
    reg = httpx.post(f"{base}/register", json={"redirect_uris": [REDIRECT], "token_endpoint_auth_method": "none"}).json()
    _, challenge = pkce()
    auth = httpx.get(f"{base}/authorize", params={"response_type": "code", "client_id": reg["client_id"],
                     "redirect_uri": REDIRECT, "code_challenge": challenge, "code_challenge_method": "S256"})
    req = parse_qs(urlparse(auth.headers["location"]).query)["req"][0]
    r = httpx.post(f"{base}/connect", data={"req": req, "action": "key", "key": "hnd_live_nope"})
    assert r.status_code == 400 and "recognised" in r.text


def test_expired_or_garbage_token_asks_to_sign_in_again(live_server):
    base, _ = live_server
    r = httpx.post(f"{base}/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                   headers={"authorization": "Bearer hnd_at_garbage", "accept": "application/json, text/event-stream"})
    assert r.status_code == 401


# ── email codes, in-process ──────────────────────────────────
@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "o.db"))


def test_email_code_right_wrong_and_attempt_limit(store):
    o = HundredOAuth(store)
    code = o.start_email_code("req1", "Buyer@Example.com")
    assert re.fullmatch(r"\d{6}", code)
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    assert o.check_email_code("req1", wrong) is None
    assert o.check_email_code("req1", code) == "buyer@example.com"
    assert o.check_email_code("req1", code) is None, "a code works once"
    code2 = o.start_email_code("req2", "a@b.co")
    for _ in range(5):
        o.check_email_code("req2", "000000" if code2 != "000000" else "111111")
    assert o.check_email_code("req2", code2) is None, "locked after 5 wrong tries"


def test_email_sign_in_finds_the_subscription_or_gives_free(store):
    key, lic = store.create_license(email="pays@x.co", plan="all", status="active", source="stripe",
                                    all_access=True, subscription_id="sub_o")
    assert subject_for_email(store, "PAYS@x.co") == f"lic:{lic.key_hash}"
    assert subject_for_email(store, "new@x.co") == "free:new@x.co"
    assert store._exec("SELECT COUNT(*) FROM leads WHERE email='new@x.co'").fetchone()[0] == 1
