"""The Everyome app server that runs on the user's computer.

Serves the interface, holds the connection, lists modules, creates runs from
their manifests, shows the exact job scripts before anything is submitted,
submits them when the user presses Run, starts interactive sessions and
forwards requests to them through the tunnel.
Nothing secret is stored: SSH keys stay with ssh, session tokens stay in memory.
"""
from __future__ import annotations

import importlib
import json
import re
import shlex
import sys
from pathlib import Path

import httpx
from fastapi import Body, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from everyome import __version__

from . import demo, modules, projects, records, runs, sessions, slurm, suites
from .backends import LocalBackend, SSHBackend, describe_ssh_error
from .session import TOKEN_HEADER

STATIC = Path(__file__).resolve().parents[1] / "static"
HOME = Path.home() / ".everyome"
SETTINGS_FILE = HOME / "settings.json"


class AppState:
    def __init__(self):
        self.backend = None
        self.conn = {}            # connection settings (no secrets)
        self.demo = False
        self.project = None       # mirrors everyome_project.json
        self.run = None           # mirrors the open run's run.json
        self.session = None       # {"url", "token", "node", "run"}
        self.demo_root = HOME / "demo_cluster"
        self.modules, self.module_problems = modules.discover()
        self.suites = suites.load()
        self.module_problems += suites.check(self.suites, self.modules)


S = AppState()
app = FastAPI(title="Everyome", version=__version__)


@app.middleware("http")
async def revalidate_static(request: Request, call_next):
    # Intent: after an update, browsers must fetch the new app files rather than reuse old copies.
    resp = await call_next(request)
    if not request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


def _need_backend():
    if not S.backend:
        raise HTTPException(400, "Not connected yet.")
    return S.backend


def _need_project():
    if not S.project:
        raise HTTPException(400, "Open or create a project first.")
    return S.project


def _need_run():
    if not S.run:
        raise HTTPException(400, "Start or open a run first.")
    return S.run


def _module(mid: str):
    if mid not in S.modules:
        raise HTTPException(404, f"No module called {mid}.")
    return S.modules[mid]


def _function(spec: str):
    mod, _, fn = spec.partition(":")
    return getattr(importlib.import_module(mod), fn)


def _load_settings():
    try:
        return json.loads(SETTINGS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


@app.get("/api/health")
def health():
    # Intent: lets tests and the launcher check the server is up.
    return {"name": "Everyome", "version": __version__, "ok": True}


# ------------------------------------------------------------------ connection
@app.get("/api/state")
def state():
    return {"connected": bool(S.backend), "label": S.backend.label if S.backend else None, "demo": S.demo,
            "conn": S.conn, "saved": _load_settings(), "project": S.project, "run": S.run,
            "session": bool(S.session), "version": __version__}


@app.post("/api/connect")
def connect(b: dict = Body(...)):
    if S.backend:
        S.backend.close()
    S.session, S.project, S.run = None, None, None
    if b.get("mode") == "demo":
        bin_dir = demo.setup(S.demo_root, S.modules)
        S.backend, S.demo = LocalBackend(S.demo_root, bin_dir, label="demo cluster"), True
        root = str(S.demo_root)
        S.conn = {"mode": "demo", "user": S.backend.user, "python": sys.executable,
                  "projects_root": f"{root}/projects", "data_root": f"{root}/data", "partition": "", "bind": "127.0.0.1"}
    else:
        need = ["host", "user", "python", "projects_root"]
        missing = [k for k in need if not b.get(k)]
        if missing:
            raise HTTPException(400, "Please fill in: " + ", ".join(missing))
        be = SSHBackend(b["host"], b["user"], int(b.get("port") or 22))
        rc, out, err = be.run("echo ok && hostname", timeout=30)
        if rc:
            raise HTTPException(400, describe_ssh_error(err))
        S.backend, S.demo = be, False
        S.conn = {k: b.get(k, "") for k in ["mode", "host", "user", "port", "python", "projects_root", "data_root", "partition"]}
        S.conn["bind"] = "0.0.0.0"
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps({k: S.conn[k] for k in S.conn if k != "bind"}, indent=1))
    return {"label": S.backend.label, "checks": checks()}


@app.get("/api/checks")
def checks():
    """Plain-language readiness checks shown on the Connect screen."""
    be, c = _need_backend(), S.conn
    out = []

    def chk(name, cmd, bad_hint):
        rc, so, se = be.run(cmd, timeout=30)
        out.append({"name": name, "ok": rc == 0, "detail": (so.strip().splitlines() or [""])[-1][:120] if rc == 0 else bad_hint})
    chk("Logged in", "whoami", "Could not run commands.")
    chk("Scheduler available", "command -v sbatch && command -v squeue", "Slurm commands (sbatch, squeue) were not found.")
    chk("Everyome installed for that Python", f"{shlex.quote(c['python'])} -c 'import everyome; print(\"everyome\", everyome.__version__)'",
        "That Python cannot import Everyome. Ask IT for the shared install, or install it in your own environment.")
    chk("Projects folder writable", f"mkdir -p {shlex.quote(c['projects_root'])} && test -w {shlex.quote(c['projects_root'])} && echo {shlex.quote(c['projects_root'])}",
        "Cannot write to the projects folder.")
    return out


@app.post("/api/disconnect")
def disconnect():
    if S.backend:
        S.backend.close()
    S.backend, S.project, S.run, S.session, S.conn, S.demo = None, None, None, None, {}, False
    return {"ok": True}


@app.get("/api/ls")
def ls(path: str):
    try:
        entries = _need_backend().listdir(path)
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))
    return {"path": path.rstrip("/") or "/", "parent": str(Path(path).parent),
            "entries": [{"name": e.name, "dir": e.is_dir, "size": e.size} for e in entries if not e.name.startswith(".")]}


# ------------------------------------------------------------------ suites and suggestions (no connection needed)
@app.get("/api/suites")
def suite_list():
    return suites.public(S.suites, S.modules)


@app.post("/api/suggest")
def suggest(b: dict = Body(default={})):
    # Intent: answers are used for this reply only; nothing is stored or sent elsewhere.
    return {"suggestions": suites.suggest(S.suites, S.modules, b.get("data") or [], b.get("aims") or [])}


# ------------------------------------------------------------------ modules
@app.get("/api/modules")
def module_list():
    return {"modules": [m.as_dict() for m in S.modules.values()], "problems": S.module_problems,
            "community": modules.COMMUNITY_ENABLED}


@app.get("/api/modules/{mid}")
def module_detail(mid: str):
    return _module(mid).as_dict()


@app.get("/api/modules/{mid}/manual")
def module_manual(mid: str):
    m = _module(mid)
    if not m.learn.get("manual"):
        raise HTTPException(404, "This module has no manual yet.")
    return {"markdown": (m.dir / m.learn["manual"]).read_text()}


@app.get("/api/modules/{mid}/playground/{n}")
def module_playground_script(mid: str, n: int):
    # Intent: serve only the scripts the manifest lists for the playground, by position.
    m = _module(mid)
    scripts = m.learn.get("playground", {}).get("scripts", [])
    if not 0 <= n < len(scripts):
        raise HTTPException(404, "No such playground script.")
    return Response((m.dir / scripts[n]).read_text(), media_type="text/javascript")


@app.get("/api/modules/{mid}/ui.js")
def module_ui(mid: str):
    # Intent: serve only the file the manifest names, from inside that module's folder.
    m = _module(mid)
    if not m.ui:
        raise HTTPException(404, "This module has no views of its own.")
    return Response((m.dir / m.ui).read_text(), media_type="text/javascript")


@app.post("/api/modules/{mid}/helpers/{name}")
def module_helper(mid: str, name: str, b: dict = Body(default={})):
    """Run a helper a module declares (for example, scanning a folder to fill a table)."""
    m, be = _module(mid), _need_backend()
    if name not in m.helpers:
        raise HTTPException(404, f"{m.name} has no helper called {name}.")
    try:
        return _function(m.helpers[name])(be, **b)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(400, str(e))


@app.get("/api/modules/{mid}/check")
def module_check(mid: str):
    """Can the cluster's Python import what this module needs?"""
    m, be = _module(mid), _need_backend()
    missing = []
    # Intent: a pipeline module also needs Nextflow on the cluster (not on the demo, which stands in for it).
    if m.nextflow and not S.demo:
        for cmd in ("nextflow", "java"):
            if be.run(f"command -v {cmd}", timeout=60)[0]:
                missing.append(f"{cmd} (command)")
    for pkg in m.requires:
        rc, _, _ = be.run(f"{shlex.quote(S.conn['python'])} -c {shlex.quote('import ' + pkg)}", timeout=120)
        if rc:
            missing.append(pkg)
    return {"requires": m.requires, "missing": missing}


# ------------------------------------------------------------------ projects
@app.get("/api/projects")
def project_list():
    return projects.listing(_need_backend(), S.conn["projects_root"])


@app.post("/api/project/create")
def project_create(b: dict = Body(...)):
    try:
        S.project = projects.create(_need_backend(), S.conn["projects_root"], b.get("name", ""), S.conn["user"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    S.run, S.session = None, None
    return S.project


@app.post("/api/project/open")
def project_open(b: dict = Body(...)):
    try:
        S.project = projects.load(_need_backend(), b["dir"])
    except FileNotFoundError:
        raise HTTPException(404, "That project could not be found.")
    S.run, S.session = None, None
    return S.project


# ------------------------------------------------------------------ runs
@app.post("/api/run/create")
def run_create(b: dict = Body(...)):
    p, be, m = _need_project(), _need_backend(), _module(b.get("module", ""))
    res = {**(b.get("resources") or {}), "partition": (b.get("resources") or {}).get("partition") or S.conn.get("partition", "")}
    try:
        S.run = runs.create(be, p, m, b.get("values") or {}, res, demo=S.demo)
    except ValueError as e:
        raise HTTPException(400, str(e))
    S.session = None
    return S.run


@app.post("/api/run/open")
def run_open(b: dict = Body(...)):
    try:
        S.run = runs.load(_need_backend(), _need_project(), b["id"])
    except FileNotFoundError:
        raise HTTPException(404, "That run could not be found.")
    S.session = None
    return S.run


@app.get("/api/run/report")
def run_report():
    """The module's summary of finished batch stages (for example, read QC)."""
    r = _need_run()
    m = _module(r["module"])
    if not m.report:
        raise HTTPException(404, "This analysis has no batch report.")
    return _function(m.report)(_need_backend(), r)


@app.post("/api/run/upload")
async def run_upload(file: UploadFile = File(...)):
    """Save a small file (for example, a barcode sheet) into the run folder."""
    r = _need_run()
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", file.filename or "upload")
    path = f"{r['dir']}/uploads/{name}"
    S.backend.write_bytes(path, await file.read())
    return {"path": path, "name": name}


# ------------------------------------------------------------------ record and write-ups
RECORD_FILES = ("record.json", "protocol.md", "methods.md", "methods_edited.md", "references.txt", "references.bib")


def _record_text(name):
    try:
        return S.backend.read_text(f"{S.run['dir']}/record/{name}")
    except FileNotFoundError:
        return None


@app.post("/api/run/record")
def record_build():
    """Gather the run's record (inputs, settings, jobs, versions, session steps) and write the write-ups."""
    r, be = _need_run(), _need_backend()
    rec = records.build(be, S.conn, _need_project(), r, _module(r["module"]))
    out = records.write(be, rec, _module(r["module"]), r)
    return {**out, **record_get()}


@app.get("/api/run/record")
def record_get():
    r = _need_run()
    rec = _record_text("record.json")
    edited = _record_text("methods_edited.md")
    return {"exists": rec is not None, "created": json.loads(rec)["created"] if rec else None, "dir": f"{r['dir']}/record",
            "protocol": _record_text("protocol.md"), "methods": edited or _record_text("methods.md"), "methods_edited": edited is not None,
            "references": _record_text("references.txt")}


@app.post("/api/run/methods")
def methods_save(b: dict = Body(...)):
    """Save the user's edited methods text next to the generated draft (which is kept)."""
    r = _need_run()
    S.backend.write_text(f"{r['dir']}/record/methods_edited.md", str(b.get("text", "")))
    return {"ok": True}


@app.post("/api/run/methods/reset")
def methods_reset():
    r = _need_run()
    S.backend.run(f"rm -f {shlex.quote(r['dir'] + '/record/methods_edited.md')}")
    return record_get()


@app.get("/api/run/record/file")
def record_file(name: str):
    if name not in RECORD_FILES:
        raise HTTPException(404, "No such record file.")
    _need_run()
    text = _record_text(name)
    if text is None:
        raise HTTPException(404, "Build the record first.")
    kind = "application/json" if name.endswith(".json") else "text/plain; charset=utf-8"
    return Response(text, media_type=kind, headers={"content-disposition": f'attachment; filename="{S.run["id"]}_{name}"'})


@app.post("/api/run/close")
def run_close():
    """Leave the open run (it stays in the project); used before starting a new one."""
    S.run, S.session = None, None
    return {"ok": True}


@app.post("/api/run/preview")
def run_preview(b: dict = Body(default={})):
    r = _need_run()
    try:
        return {"scripts": runs.preview(r, _module(r["module"]), S.conn["python"], b.get("start_at"))}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/run/submit")
def run_submit(b: dict = Body(default={})):
    r, be = _need_run(), _need_backend()
    try:
        jobs = runs.submit(be, r, _module(r["module"]), S.conn["python"], b.get("start_at"))
    except (RuntimeError, ValueError) as e:
        raise HTTPException(400, str(e))
    return {"jobs": jobs}


@app.get("/api/run/status")
def run_status():
    r = _need_run()
    st = runs.status(_need_backend(), r, _module(r["module"]))
    if st["done"] != r.get("done"):
        r["done"] = st["done"]
        runs.save(S.backend, r)
    return st


@app.get("/api/run/progress")
def run_progress():
    """For Nextflow modules: how many of the pipeline's tasks have finished."""
    return runs.trace_summary(_need_backend(), _need_run())


@app.get("/api/run/file")
def run_file(path: str):
    """A file from inside the run folder (for example, the MultiQC report)."""
    r = _need_run()
    if not path or path.startswith("/") or ".." in path.split("/"):
        raise HTTPException(400, "Give a path inside the run folder.")
    try:
        data = S.backend.read_bytes(f"{r['dir']}/{path}")
    except FileNotFoundError:
        raise HTTPException(404, "That file is not there (yet).")
    name = path.split("/")[-1]
    if name.endswith(".html"):
        # Intent: reports run their own scripts; sandbox them so they cannot reach the app or its API.
        return Response(data, media_type="text/html", headers={"Content-Security-Policy": "sandbox allow-scripts allow-popups"})
    return Response(data, media_type="application/octet-stream", headers={"content-disposition": f'attachment; filename="{name}"'})


@app.post("/api/run/cancel")
def run_cancel():
    runs.cancel(_need_backend(), _need_run())
    return {"ok": True}


@app.get("/api/run/log")
def run_log(stage: str):
    r = _need_run()
    try:
        return {"log": runs.log_tail(_need_backend(), r, _module(r["module"]), stage)}
    except ValueError as e:
        raise HTTPException(400, str(e))


# ------------------------------------------------------------------ interactive session
@app.post("/api/session/start")
def session_start():
    r, be = _need_run(), _need_backend()
    m = _module(r["module"])
    if "interactive" not in m.kind:
        raise HTTPException(400, "This module has no interactive steps.")
    if "batch" in m.kind and not r.get("done"):
        raise HTTPException(400, "The cluster stages have not finished yet.")
    try:
        r["session_job"] = sessions.start(be, r, m, S.conn)
    except RuntimeError as e:
        raise HTTPException(400, f"Could not start the session: {e}")
    S.session = None
    runs.save(be, r)
    return {"job": r["session_job"]}


@app.get("/api/session/status")
def session_status():
    r, be = _need_run(), _need_backend()
    if not r.get("session_job"):
        return {"state": "NONE"}
    st = slurm.states(be, {"s": r["session_job"]}).get("s", {}).get("state", "UNKNOWN")
    if st != "RUNNING":
        S.session = None
        return {"state": st}
    if not S.session or S.session.get("run") != r["id"]:
        S.session = sessions.connect(be, r)
        if not S.session:
            return {"state": "STARTING"}
    info = sessions.ping(S.session)
    if info is None:
        return {"state": "STARTING"}
    return {"state": "READY", "node": S.session["node"], "engine": info}


@app.post("/api/session/stop")
def session_stop():
    sessions.stop(_need_backend(), _need_run(), S.session)
    S.session = None
    return {"ok": True}


@app.api_route("/api/s/{path:path}", methods=["GET", "POST"])
async def session_proxy(path: str, request: Request):
    """Forward GUI requests to the interactive session, adding its token."""
    if not S.session:
        raise HTTPException(409, "The session is not running. Start it first.")
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.request(request.method, f"{S.session['url']}/{path}", params=request.query_params,
                                 content=await request.body(),
                                 headers={TOKEN_HEADER: S.session["token"], "content-type": request.headers.get("content-type", "application/json")})
    return Response(r.content, status_code=r.status_code, media_type=r.headers.get("content-type"),
                    headers={k: v for k, v in r.headers.items() if k.lower() == "content-disposition"})


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
