#!/usr/bin/env python3
"""Lead Scout, in a browser.

    py -m pip install -r requirements.txt
    py web.py            → open http://localhost:5000

Two things live here. `/api/audit` runs the audit engine on its own — no model,
no API key, results in seconds. `/api/run` turns the agent loose on a lead and
streams what it does, line by line, so you can watch it work instead of reading
a wall of terminal output afterwards.
"""

import json
import queue
import sys
import threading
import webbrowser
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, send_from_directory

from lead_scout import audit as audit_engine
from lead_scout import config, leads, state

app = Flask(__name__)
OUT_DIR = Path(__file__).parent / "out"

# The agent backends print their actions. We capture stdout to stream them to
# the browser — which means only one run at a time. Fine for a local tool.
_run_lock = threading.Lock()


class _QueueWriter:
    """A stdout stand-in that pushes each finished line onto a queue."""

    def __init__(self, q: queue.Queue):
        self.q = q
        self._buf = ""

    def write(self, text: str) -> int:
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self.q.put(line)
        return len(text)

    def flush(self) -> None:
        if self._buf:
            self.q.put(self._buf)
            self._buf = ""


def _sse(event: str, **data) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ── pages ────────────────────────────────────────────────────


@app.route("/")
def index():
    prov = config.provider()
    return render_template(
        "index.html",
        provider=prov or "",
        model=(config.CEREBRAS_MODEL if prov == "cerebras" else config.MODEL),
        hubspot_live=config.hubspot_live(),
        agency=config.AGENCY_NAME,
    )


@app.route("/out/<path:filename>")
def onepager(filename):
    """Serve the generated one-pagers so they open in a tab."""
    return send_from_directory(OUT_DIR, filename)


# ── api ──────────────────────────────────────────────────────


@app.route("/api/audit", methods=["POST"])
def api_audit():
    """Run just the audit engine. No model, no key, no CRM."""
    url = (request.json or {}).get("url", "").strip()
    if not url:
        return jsonify({"error": "Enter a website address."}), 400
    return jsonify(audit_engine.audit_site(url))


@app.route("/api/leads")
def api_leads():
    """The lead queue — HubSpot when it's connected, samples when it isn't."""
    pending = leads.fetch_new(include_seen=True)
    worked = set(state.load()["seen_ids"])
    for lead in pending:
        lead["worked"] = lead["id"] in worked
    return jsonify({"source": "HubSpot" if config.hubspot_live() else "samples", "leads": pending})


@app.route("/api/run")
def api_run():
    """Turn the agent loose on one lead, streaming its actions as they happen."""
    lead = {
        "id": request.args.get("id") or f"web:{request.args.get('url', '')}",
        "name": request.args.get("name", "") or "there",
        "email": request.args.get("email", ""),
        "company": request.args.get("company", ""),
        "website": request.args.get("url", "").strip(),
    }

    def stream():
        if not lead["website"]:
            yield _sse("error", message="Enter a website address.")
            return

        prov = config.provider()
        if prov is None:
            yield _sse(
                "error",
                message=(
                    "No model key set. Add CEREBRAS_API_KEY (free) or ANTHROPIC_API_KEY "
                    "to your .env file — or use Audit only, which needs no key."
                ),
            )
            return

        if not _run_lock.acquire(blocking=False):
            yield _sse("error", message="Already working a lead — let that one finish first.")
            return

        try:
            if prov == "cerebras":
                from lead_scout import cerebras_agent as backend
            else:
                from lead_scout import agent as backend

            q: queue.Queue = queue.Queue()
            done = threading.Event()
            failure: list[str] = []

            def work():
                original = sys.stdout
                sys.stdout = _QueueWriter(q)
                try:
                    backend.run(lead)
                except Exception as exc:  # surface it in the browser, don't 500
                    failure.append(f"{type(exc).__name__}: {exc}")
                finally:
                    sys.stdout.flush()
                    sys.stdout = original
                    done.set()

            threading.Thread(target=work, daemon=True).start()
            yield _sse("start", website=lead["website"], provider=prov)

            while not (done.is_set() and q.empty()):
                try:
                    yield _sse("line", text=q.get(timeout=0.4))
                except queue.Empty:
                    yield ": keepalive\n\n"

            if failure:
                yield _sse("error", message=failure[0])
                return

            state.mark_seen(lead["id"])
            newest = max(OUT_DIR.glob("*.html"), key=lambda p: p.stat().st_mtime, default=None)
            yield _sse("done", onepager=(f"/out/{newest.name}" if newest else None))
        finally:
            _run_lock.release()

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/reset", methods=["POST"])
def api_reset():
    """Forget which leads were worked — for a clean second take."""
    state.reset()
    return jsonify({"ok": True})


if __name__ == "__main__":
    print("\n  Lead Scout  →  http://localhost:5000\n")
    threading.Timer(1.0, lambda: webbrowser.open("http://localhost:5000")).start()
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
