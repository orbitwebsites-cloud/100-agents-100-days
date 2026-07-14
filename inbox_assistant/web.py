"""A tiny local chat window for the Inbox Assistant.

Same agent, same tools — just a browser tab instead of a terminal. One page,
one endpoint: POST a question, get back the answer the agent produced by
calling search_emails / get_order_status / archive_email.
"""

from flask import Flask, jsonify, render_template, request

from . import config

app = Flask(__name__)


def _backend():
    prov = config.provider()
    if prov == "cerebras":
        from . import cerebras_agent as backend
        return backend, config.CEREBRAS_MODEL, "cerebras"
    if prov == "anthropic":
        from . import agent as backend
        return backend, config.MODEL, "anthropic"
    return None, None, None


@app.get("/")
def index():
    _, model, prov = _backend()
    brain = f"{prov} ({model})" if prov else "no model key set"
    mode = "gmail: live" if config.gmail_live() else "gmail: dry-run (sample inbox)"
    return render_template("chat.html", brain=brain, mode=mode)


@app.post("/api/ask")
def api_ask():
    question = (request.get_json(silent=True) or {}).get("question", "").strip()
    if not question:
        return jsonify(answer="Ask me something first."), 400

    backend, _, prov = _backend()
    if backend is None:
        return jsonify(
            answer="No model key set. Add CEREBRAS_API_KEY or ANTHROPIC_API_KEY to .env and restart."
        ), 200

    answer = backend.ask(question)
    return jsonify(answer=answer or "(no answer)")


def run(host: str = "127.0.0.1", port: int = 5050, debug: bool = False) -> None:
    app.run(host=host, port=port, debug=debug)
