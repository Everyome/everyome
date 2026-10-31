"""Interactive session server, started by a Slurm job on a compute node.

Loads the module's engine for one run, writes <run>/session/session.json with
host, port and a random token (mode 600). The desktop app reads it over SSH,
opens a tunnel, and sends the token with every request, so other users on the
node cannot use the session. Stops itself after `--idle` minutes without requests.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import secrets
import socket
import threading
import time
from pathlib import Path

import uvicorn
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

TOKEN_HEADER = "x-everyome-token"


def load_engine(spec: str, run_dir: str):
    mod, _, cls = spec.partition(":")
    return getattr(importlib.import_module(mod), cls)(run_dir)


def create_app(run_dir: str, engine_spec: str, token: str, idle_minutes: float) -> FastAPI:
    app = FastAPI(title="Everyome session")
    eng = load_engine(engine_spec, run_dir)
    last = {"t": time.time()}

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.headers.get(TOKEN_HEADER) != token:
            return JSONResponse({"detail": "bad token"}, status_code=403)
        last["t"] = time.time()
        try:
            return await call_next(request)
        except (KeyError, ValueError, RuntimeError, FileNotFoundError) as e:
            return JSONResponse({"detail": str(e)}, status_code=400)

    def watchdog():
        while True:
            time.sleep(30)
            if time.time() - last["t"] > idle_minutes * 60 and not eng.task["running"]:
                os._exit(0)
    threading.Thread(target=watchdog, daemon=True).start()

    @app.get("/status")
    def status():
        return eng.status()

    @app.post("/call/{method}")
    def call(method: str, b: dict = Body(default={})):
        # Intent: only the methods the engine lists in API can be called from the GUI.
        if method not in eng.API:
            raise HTTPException(404, f"No action called {method}.")
        out = getattr(eng, method)(**b)
        if method in eng.REPLAY:
            eng._log_call(method, b)       # Intent: only calls that were accepted are replayed
        return out

    @app.get("/download")
    def download(name: str):
        res = (Path(run_dir) / "results").resolve()
        path = (res / name).resolve()
        if path.parent != res or not path.exists():
            raise HTTPException(404)
        return FileResponse(path, filename=name)

    @app.post("/stop")
    def stop():
        threading.Timer(0.5, lambda: os._exit(0)).start()
        return {"stopping": True}

    return app


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="run folder")
    ap.add_argument("--engine", required=True, help="package.module:ClassName")
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--idle", type=float, default=60, help="minutes without requests before stopping")
    a = ap.parse_args()
    try:
        import setproctitle
        setproctitle.setproctitle(f"Claude_{os.environ.get('USER', 'user')}_everyome_session")
    except ImportError:
        pass
    with socket.socket() as s:
        s.bind((a.bind if a.bind != "0.0.0.0" else "", 0)); port = s.getsockname()[1]
    token = secrets.token_urlsafe(24)
    sess = Path(a.run) / "session" / "session.json"
    sess.parent.mkdir(parents=True, exist_ok=True)
    app = create_app(a.run, a.engine, token, a.idle)
    info = {"host": socket.gethostname() if a.bind != "127.0.0.1" else "127.0.0.1", "port": port, "token": token,
            "pid": os.getpid(), "job": os.environ.get("SLURM_JOB_ID"), "started": time.time()}
    # Intent: create the file private from the start, so the token is never world-readable.
    fd = os.open(sess, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump(info, fh)
    uvicorn.run(app, host=a.bind, port=port, log_level="warning")


if __name__ == "__main__":
    main()
