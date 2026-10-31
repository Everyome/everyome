"""Smoke tests: the package imports and the local server answers."""
from fastapi.testclient import TestClient

import everyome
from everyome.core.server import app


def test_version():
    assert everyome.__version__ == "0.0.1"


def test_health():
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"name": "Everyome", "version": everyome.__version__, "ok": True}


def test_start_page_keeps_attribution():
    # Intent: the creator credit must stay on the first page users see.
    r = TestClient(app).get("/")
    assert r.status_code == 200
    assert "Helen R Horkan" in r.text and "Every -ome, for everyone" in r.text
