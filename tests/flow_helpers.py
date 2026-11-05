"""Shared helpers for the end-to-end module tests (tests/test_*_flow.py): talk to the app's test client, wait for
background steps, and call a live session's engine. New flow tests import these instead of copying them."""
import time

import pytest
from fastapi.testclient import TestClient

from everyome.core import server


def ok(r):
    assert r.status_code == 200, r.text
    return r.json()


def wait(fn, timeout=600, every=0.5):  # generous: CI runners can be several times slower than a laptop
    end = time.time() + timeout
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(every)
    raise AssertionError("timed out")


def call(c, method, **kw):
    """Call the live session's engine (cluster session or, for local modules, the app itself)."""
    return ok(c.post(f"/api/s/call/{method}", json=kw))


def done(c):
    """True once the session's background step has finished; fails at once if it raised."""
    s = ok(c.get("/api/s/status"))
    assert not s["task"]["error"], s["task"]["error"]
    return not s["task"]["running"]


def follow(c, method, **kw):
    """Call an engine method that runs in the background and wait for it to finish."""
    r = call(c, method, **kw)
    wait(lambda: done(c), every=0.2)
    return r


@pytest.fixture()
def demo_client(tmp_path, monkeypatch):
    """A test client with its own demo cluster (and its own 'this computer' folder) under tmp_path."""
    monkeypatch.setenv("EVERYOME_DEMO_PAUSE", "0.1")
    server.S.demo_root = tmp_path / "demo_cluster"
    server.S.local_root = tmp_path / "Everyome"
    c = TestClient(server.app)
    yield c
    if server.S.run:
        c.post("/api/session/stop")
    c.post("/api/disconnect")
