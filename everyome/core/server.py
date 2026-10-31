"""Local app server. For now it only serves the start page and a health check."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from everyome import __version__

STATIC = Path(__file__).resolve().parents[1] / "static"

app = FastAPI(title="Everyome", version=__version__)


@app.get("/api/health")
def health():
    # Intent: lets tests and the launcher check the server is up.
    return {"name": "Everyome", "version": __version__, "ok": True}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")
