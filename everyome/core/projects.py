"""Projects: one folder per experiment, holding every run of every module.

<projects_root>/<name>/
  everyome_project.json      name, owner, created, list of runs
  runs/<run_id>/             one folder per run (see runs.py)
"""
from __future__ import annotations

import json
import re
import shlex
import time

FILE = "everyome_project.json"


def clean_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", (name or "").strip()).strip("_.")


def create(backend, root: str, name: str, user: str) -> dict:
    name = clean_name(name)
    if not name:
        raise ValueError("Give the project a name.")
    d = f"{root.rstrip('/')}/{name}"
    if backend.exists(f"{d}/{FILE}"):
        raise ValueError(f"A project called {name} already exists.")
    p = {"name": name, "dir": d, "created": time.strftime("%Y-%m-%d %H:%M"), "user": user, "runs": []}
    backend.run(f"mkdir -p {shlex.quote(d)}/runs")
    save(backend, p)
    return p


def save(backend, p: dict) -> None:
    backend.write_text(f"{p['dir']}/{FILE}", json.dumps(p, indent=1))


def load(backend, d: str) -> dict:
    return json.loads(backend.read_text(f"{d.rstrip('/')}/{FILE}"))


def listing(backend, root: str) -> list[dict]:
    rc, out, _ = backend.run(f"for f in {shlex.quote(root)}/*/{FILE}; do [ -f \"$f\" ] && echo \"$f\"; done")
    res = []
    for f in out.split():
        try:
            p = json.loads(backend.read_text(f))
            res.append({"name": p["name"], "dir": p["dir"], "created": p.get("created"), "runs": len(p.get("runs", []))})
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass
    return res
