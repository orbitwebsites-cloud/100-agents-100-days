"""A tiny local chat window for the Inbox Assistant.

Same agent, same tools — just a browser tab instead of a terminal. One page,
one endpoint: POST a question, get back the answer the agent produced by
calling search_emails / get_order_status / archive_email.
"""

import logging
import os
import secrets

from flask import Flask, jsonify, render_template, request
from flask_wtf.csrf import CSRFProtect

from . import config

app = Flask(__name__)
# Random per-startup key is fine for this single-process local demo.
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)
csrf = CSRFProtect(app)

log = logging.getLogger(__name__)

MAX_QUESTION_LEN = 4000
MAX_HISTORY_ENTRIES = 20
MAX_HISTORY_CONTENT_LEN = 4000


def _backend():
    prov = config.provider()
    if prov == "cerebras":
        from . import cerebras_agent as backend
        return backend, config.CEREBRAS_MODEL, "cerebras"
    if prov == "anthropic":
        from . import agent as backend
        return backend, config.MODEL, "anthropic"
    return None, None, None


@app.after_request
def _security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'"
    )
    return response


@app.get("/")
def index():
    _, model, prov = _backend()
    brain = f"{prov} ({model})" if prov else "no model key set"
    mode = "gmail: live" if config.gmail_live() else "gmail: dry-run (sample inbox)"
    return render_template("chat.html", brain=brain, mode=mode)


def _clean_history(raw):
    """Keep only well-formed {role, content} entries, dropping/trimming the rest."""
    if not isinstance(raw, list):
        return []
    cleaned = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        role = entry.get("role")
        content = entry.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        cleaned.append({"role": role, "content": content[:MAX_HISTORY_CONTENT_LEN]})
    return cleaned[-MAX_HISTORY_ENTRIES:]


@app.post("/api/ask")
def api_ask():
    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    if not question:
        return jsonify(answer="Ask me something first."), 400
    if len(question) > MAX_QUESTION_LEN:
        return jsonify(answer="Question is too long."), 400

    history = _clean_history(payload.get("history"))

    backend, _, _ = _backend()
    if backend is None:
        return jsonify(
            answer="No model key set. Add CEREBRAS_API_KEY or ANTHROPIC_API_KEY to .env and restart."
        ), 200

    try:
        answer = backend.ask(question, history=history or None)
    except Exception:
        log.exception("backend.ask failed")
        return jsonify(answer="Something went wrong answering that question."), 500

    return jsonify(answer=answer or "(no answer)")


def run(host: str = "127.0.0.1", port: int = 5050) -> None:
    app.run(host=host, port=port)
