"""Shared fixtures."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time

import pytest

from hundred.server.store import Store


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    port = _free_port()
    db = tmp_path_factory.mktemp("srv") / "live.db"
    env = {**os.environ, "DATABASE_PATH": str(db), "PUBLIC_URL": f"http://127.0.0.1:{port}", "STRIPE_SECRET_KEY": "",
           "STRIPE_WEBHOOK_SECRET": "whsec_test"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "hundred.server.app:app", "--port", str(port)],
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    key, _ = Store(str(db)).create_license(email="e2e@x.co", plan="all", status="active", source="comp",
                                           all_access=True)
    yield f"http://127.0.0.1:{port}", key
    proc.terminate()
    proc.wait(timeout=10)
