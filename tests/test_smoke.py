"""Smoke tests: the package imports and the local server answers."""
from fastapi.testclient import TestClient

import everyome
from everyome.core.server import app


def test_version():
    # Intent: the version lives in one place and is a valid release number.
    import re
    assert re.fullmatch(r"\d+\.\d+\.\d+((a|b|rc)\d+)?", everyome.__version__)


def test_health():
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"name": "Everyome", "version": everyome.__version__, "ok": True}


def test_start_page_keeps_attribution():
    # Intent: the creator credit must stay on the first page users see.
    r = TestClient(app).get("/")
    assert r.status_code == 200
    assert "Helen R Horkan" in r.text and "Every -ome, for everyone" in r.text
