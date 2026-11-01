"""Repeat a run from its rerun bundle (<run>/record/rerun/), on the cluster, as the user.

  python -m everyome.core.rerun BUNDLE NEW_RUN_DIR              write the job scripts and show them
  python -m everyome.core.rerun BUNDLE NEW_RUN_DIR --submit     also submit them as one afterok chain
  python -m everyome.core.rerun BUNDLE NEW_RUN_DIR --session    after the jobs finish: replay the live-session steps

The new run gets its own folder, so the original is never touched. Jobs are
submitted only when the person running this command asks for it with --submit.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from . import modules, runs, slurm
from .backends import LocalBackend
from .manifest import check_values
from .session import load_engine


def _say(msg):
    print(msg, flush=True)


def prepare(bundle: Path, new: Path, submit: bool) -> dict:
    info = json.loads((bundle / "run.json").read_text())
    found, _ = modules.available()
    m = found.get(info["module"])
    if not m:
        sys.exit(f"Module {info['module']} is not installed with this Everyome.")
    if m.version != info.get("module_version"):
        _say(f"Note: the original run used {m.id} version {info.get('module_version')}; this Everyome has version {m.version}.")
    vals, errors = check_values(m, info["values"])
    if errors:
        sys.exit("The recorded settings no longer fit this module: " + " ".join(errors.values()))
    if (new / "run.json").exists():
        run = json.loads((new / "run.json").read_text())
        if run.get("rerun_of") != info["id"]:
            sys.exit(f"{new} already holds a different run. Choose an empty folder.")
        if run.get("jobs"):
            sys.exit(f"The jobs for {new} were already submitted.")
    else:
        for sub in ("jobs", "logs", "results"):
            (new / sub).mkdir(parents=True, exist_ok=True)
        run = {"id": new.name, "dir": str(new), "module": m.id, "module_version": m.version, "rerun_of": info["id"],
               "created": time.strftime("%Y-%m-%d %H:%M:%S"), "user": os.environ.get("USER", "user"), "values": vals,
               "defaults_changed": sorted(f.id for f in m.params if vals.get(f.id) != f.default),
               "resources": info.get("resources", {}), "jobs": {}, "demo": bool(info.get("demo")),
               "job_prefix": info.get("job_prefix", "Claude"), "pipelines_dir": info.get("pipelines_dir", "")}
        (new / "params.json").write_text(json.dumps(vals, indent=1))
        for name, text in runs.pipeline_files(run, m).items():
            (new / name).write_text(text)
        (new / "run.json").write_text(json.dumps(run, indent=1))
    if not m.stages:
        _say("This module has no cluster stages; go straight to --session.")
        return run
    scripts = runs.preview(run, m, sys.executable)
    for s in scripts:
        Path(s["path"]).write_text(s["script"])
        _say(f"--- stage {s['stage']} · {s['title']}\n{s['path']}")
    if submit and m.nextflow and not run.get("demo"):
        from . import pipelines
        k = pipelines.key(m.nextflow["pipeline"], str(m.nextflow["revision"]))
        if not pipelines.installed(LocalBackend(new), run["pipelines_dir"], k):
            sys.exit(f"{k} is not installed in {run['pipelines_dir']} on this cluster. Open the run in the Everyome app and press Run, "
                     "or ask whoever set up Everyome here.")
    if submit:
        jobs = runs.submit(LocalBackend(new), run, m, sys.executable)
        _say("Submitted: " + ", ".join(f"stage {k} as job {v}" for k, v in jobs.items()))
    else:
        _say("\nNothing submitted. Read the scripts above, then run again with --submit to send them.")
    return run


def replay(bundle: Path, new: Path) -> None:
    calls = json.loads((bundle / "session_calls.json").read_text())
    run = json.loads((new / "run.json").read_text())
    found, _ = modules.available()
    m = found[run["module"]]
    if m.stages:
        st = runs.status(LocalBackend(new), run, m)
        if not st["done"]:
            sys.exit("The cluster stages of the new run have not all finished yet. Try again when they have.")
    eng = load_engine(m.engine, str(new))
    for k, c in enumerate(calls, 1):
        _say(f"{k}/{len(calls)} {c['method']}")
        getattr(eng, c["method"])(**c["args"])
        while eng.task["running"]:
            time.sleep(0.2)
        if eng.task.get("error"):
            sys.exit(f"Step {k} ({c['method']}) failed: {eng.task['error']}")
        eng._log_call(c["method"], c["args"])
    _say(f"Replayed {len(calls)} live-session steps into {new}.")


def main():
    ap = argparse.ArgumentParser(description="Repeat an Everyome run from its rerun bundle.")
    ap.add_argument("bundle", help="the run's record/rerun folder")
    ap.add_argument("new_run_dir", help="an empty folder for the repeated run")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--submit", action="store_true", help="submit the job scripts (as you)")
    g.add_argument("--session", action="store_true", help="replay the live-session steps once the jobs have finished")
    a = ap.parse_args()
    try:
        import setproctitle
        setproctitle.setproctitle(f"{slurm.JOB_PREFIX}_{os.environ.get('USER', 'user')}_everyome_rerun")
    except ImportError:
        pass
    bundle, new = Path(a.bundle).resolve(), Path(a.new_run_dir).resolve()
    if a.session:
        replay(bundle, new)
    else:
        prepare(bundle, new, a.submit)


if __name__ == "__main__":
    main()
