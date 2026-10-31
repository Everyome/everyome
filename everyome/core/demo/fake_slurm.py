"""A tiny stand-in for Slurm, used by the demo cluster.

Implements the subset Everyome uses (carried over from SPLiTscape):
  sbatch [--parsable] [--dependency=afterok:ID[:ID]] [--job-name=..] [--output=..] script
  squeue -h -j IDS -o "%i %T %N"
  sacct  -n -P -j IDS -o JobID,State,Elapsed
  scancel ID [ID ...]

Jobs run as background processes; state lives in $FAKE_SLURM_HOME.
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

HOME = Path(os.environ.get("FAKE_SLURM_HOME", Path.home() / ".fake_slurm"))
JOBS = HOME / "jobs"


def _load(jid):
    return json.loads((JOBS / f"{jid}.json").read_text())


def _save(job):
    tmp = JOBS / f"{job['id']}.json.tmp"
    tmp.write_text(json.dumps(job))
    tmp.replace(JOBS / f"{job['id']}.json")


def _directives(script: str) -> dict:
    out = {}
    for line in Path(script).read_text().splitlines():
        m = re.match(r"#SBATCH\s+--([\w-]+)(?:[= ](.+))?", line.strip())
        if m:
            out[m.group(1)] = (m.group(2) or "").strip()
    return out


def sbatch(args):
    JOBS.mkdir(parents=True, exist_ok=True)
    opts, script = {}, None
    for a in args:
        if a.startswith("--"):
            k, _, v = a[2:].partition("=")
            opts[k] = v
        else:
            script = a
    if not script:
        sys.exit("sbatch: no script given")
    opts = {**_directives(script), **opts}
    counter = HOME / "counter"
    jid = int(counter.read_text()) + 1 if counter.exists() else 1001
    counter.write_text(str(jid))
    deps = []
    if opts.get("dependency", "").startswith("afterok:"):
        deps = [int(x) for x in opts["dependency"][8:].split(":") if x]
    out = opts.get("output", str(Path.cwd() / f"slurm-{jid}.out")).replace("%j", str(jid))
    job = {"id": jid, "name": opts.get("job-name", Path(script).name), "script": str(Path(script).resolve()),
           "cwd": str(Path.cwd()), "output": out, "deps": deps, "state": "PENDING", "start": None, "end": None,
           "node": socket.gethostname(), "pid": None}
    _save(job)
    # Intent: detach a runner that waits for dependencies, then executes the script.
    subprocess.Popen([sys.executable, __file__, "_run", str(jid)], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=os.environ.copy())
    print(jid if "parsable" in opts else f"Submitted batch job {jid}")


def _run(jid):
    job = _load(jid)
    while True:
        states = [_load(d)["state"] for d in job["deps"]]
        if any(s in ("FAILED", "CANCELLED", "TIMEOUT") for s in states):
            job = _load(jid); job.update(state="CANCELLED", reason="DependencyNeverSatisfied", end=time.time()); _save(job); return
        if all(s == "COMPLETED" for s in states):
            break
        if _load(jid)["state"] == "CANCELLED":
            return
        time.sleep(0.5)
    job = _load(jid)
    if job["state"] == "CANCELLED":
        return
    Path(job["output"]).parent.mkdir(parents=True, exist_ok=True)
    with open(job["output"], "w") as log:
        env = dict(os.environ, SLURM_JOB_ID=str(jid), SLURMD_NODENAME=job["node"])
        p = subprocess.Popen(["bash", job["script"]], cwd=job["cwd"], stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
        job.update(state="RUNNING", start=time.time(), pid=p.pid); _save(job)
        rc = p.wait()
    job = _load(jid)
    if job["state"] != "CANCELLED":
        job.update(state="COMPLETED" if rc == 0 else "FAILED", end=time.time(), exit=rc); _save(job)


def _ids(args):
    for i, a in enumerate(args):
        if a == "-j" and i + 1 < len(args):
            return [int(x) for x in args[i + 1].split(",") if x]
        if a.startswith("--jobs="):
            return [int(x) for x in a[7:].split(",") if x]
    return sorted(int(p.stem) for p in JOBS.glob("*.json")) if JOBS.exists() else []


def _elapsed(job):
    if not job["start"]:
        return "00:00:00"
    s = int((job["end"] or time.time()) - job["start"])
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def squeue(args):
    for jid in _ids(args):
        try:
            j = _load(jid)
        except FileNotFoundError:
            continue
        if j["state"] in ("PENDING", "RUNNING"):
            print(f"{jid} {j['state']} {j['node'] if j['state'] == 'RUNNING' else '(None)'}")


def sacct(args):
    for jid in _ids(args):
        try:
            j = _load(jid)
        except FileNotFoundError:
            continue
        print(f"{jid}|{j['state']}|{_elapsed(j)}")


def scancel(args):
    for a in args:
        if not a.isdigit():
            continue
        j = _load(int(a))
        if j["state"] in ("PENDING", "RUNNING"):
            if j.get("pid"):
                try:
                    os.killpg(j["pid"], 15)
                except ProcessLookupError:
                    pass
            j.update(state="CANCELLED", end=time.time()); _save(j)


if __name__ == "__main__":
    cmd, rest = sys.argv[1], sys.argv[2:]
    {"sbatch": sbatch, "squeue": squeue, "sacct": sacct, "scancel": scancel,
     "_run": lambda a: _run(int(a[0]))}[cmd](rest)
