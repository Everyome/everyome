"""Starting and reaching interactive sessions (the app side of session.py).

A session is one Slurm job running everyome.core.session for one run. The app
finds it through <run>/session/session.json, opens an SSH tunnel to its node,
and forwards the GUI's requests with the session token.
"""
from __future__ import annotations

import json
import shlex

import httpx

from . import slurm
from .manifest import Manifest
from .session import TOKEN_HEADER

RESOURCES = {"cpus": 4, "mem": "16G", "time": "08:00:00"}


def script(run: dict, m: Manifest, conn: dict) -> str:
    d = run["dir"]
    res = {**RESOURCES, **m.resources.get("session", {}), "partition": conn.get("partition", "")}
    body = [f"rm -f {shlex.quote(d + '/session/session.json')}",
            f"exec {shlex.quote(conn['python'])} -m everyome.core.session --run {shlex.quote(d)} "
            f"--engine {shlex.quote(m.engine)} --bind {conn.get('bind', '0.0.0.0')} --idle 60"]
    return slurm.script(slurm.job_name(run["user"], m.id, "session"), f"{d}/logs/session.log", res, body)


def start(backend, run: dict, m: Manifest, conn: dict) -> int:
    """Submit the session job, or reuse one that is already queued or running. Called only from the user's click."""
    if run.get("session_job"):
        st = slurm.states(backend, {"s": run["session_job"]}).get("s", {}).get("state")
        if st in ("PENDING", "RUNNING"):
            return run["session_job"]
    path = f"{run['dir']}/jobs/session.sbatch"
    backend.write_text(path, script(run, m, conn))
    backend.run(f"mkdir -p {shlex.quote(run['dir'])}/session")
    return slurm.submit(backend, path, run["dir"])


def connect(backend, run: dict) -> dict | None:
    """Tunnel to a running session; None while it is still starting."""
    try:
        info = json.loads(backend.read_text(f"{run['dir']}/session/session.json"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    lport = backend.tunnel(info["host"], info["port"])
    return {"url": f"http://127.0.0.1:{lport}", "token": info["token"], "node": info["host"], "run": run["id"]}


def ping(sess: dict) -> dict | None:
    try:
        r = httpx.get(sess["url"] + "/status", headers={TOKEN_HEADER: sess["token"]}, timeout=5)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError:
        return None


def stop(backend, run: dict, sess: dict | None) -> None:
    if sess:
        try:
            httpx.post(sess["url"] + "/stop", headers={TOKEN_HEADER: sess["token"]}, timeout=5)
        except httpx.HTTPError:
            pass
    if run.get("session_job"):
        slurm.cancel(backend, [run["session_job"]])
