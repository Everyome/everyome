"""Runs of batch modules: settings -> job scripts -> a chain of Slurm jobs.

<project>/runs/<run_id>/
  run.json        module, version, who, when, every input and setting, job ids
  params.json     the inputs and settings the stage commands read
  jobs/           the exact scripts submitted (shown to the user before Run)
  logs/           one log per stage
  results/        what the stages write

Each stage waits for the one before (afterok), so a whole run goes in with one
click and runs unattended. Scripts are written and shown first; they are only
submitted when the user confirms.
"""
from __future__ import annotations

import json
import shlex
import time

from . import projects, slurm
from .manifest import Manifest, check_values


def create(backend, project: dict, m: Manifest, values: dict, resources: dict, demo: bool = False) -> dict:
    """Check the settings and write a new run folder; nothing is submitted."""
    vals, errors = check_values(m, values)
    if errors:
        raise ValueError(" ".join(errors.values()))
    rid = f"{m.id.split('.')[-1]}_{time.strftime('%Y%m%d-%H%M%S')}"
    d = f"{project['dir']}/runs/{rid}"
    run = {"id": rid, "dir": d, "module": m.id, "module_version": m.version, "created": time.strftime("%Y-%m-%d %H:%M:%S"),
           "user": project["user"], "values": vals,
           # Intent: inputs are always the user's own files; only settings have meaningful defaults.
           "defaults_changed": sorted(f.id for f in m.params if vals.get(f.id) != f.default),
           "resources": {**m.resources, **{k: v for k, v in resources.items() if v}}, "jobs": {}, "demo": demo}
    backend.run(f"mkdir -p {shlex.quote(d)}/jobs {shlex.quote(d)}/logs {shlex.quote(d)}/results")
    backend.write_text(f"{d}/params.json", json.dumps(vals, indent=1))
    for name, text in pipeline_files(run, m).items():
        backend.write_text(f"{d}/{name}", text)
    save(backend, run)
    project.setdefault("runs", []).append({"id": rid, "module": m.id, "created": run["created"]})
    projects.save(backend, project)
    return run


def save(backend, run: dict) -> None:
    backend.write_text(f"{run['dir']}/run.json", json.dumps(run, indent=1))


def load(backend, project: dict, rid: str) -> dict:
    return json.loads(backend.read_text(f"{project['dir']}/runs/{rid}/run.json"))


# ------------------------------------------------------------------ Nextflow pipelines
def pipeline_files(run: dict, m: Manifest) -> dict[str, str]:
    """For a Nextflow module: the samplesheet, the pipeline's parameter file and the cluster config."""
    if not m.nextflow:
        return {}
    nf, d, v = m.nextflow, run["dir"], run["values"]
    sheet = nf["samplesheet"]
    rows = v.get(sheet["from"]) or []
    csv = ",".join(sheet["columns"]) + "\n" + "".join(",".join(str(r.get(c, "")) for c in sheet["columns"]) + "\n" for r in rows)
    # Intent: pass only what differs from the pipeline's own defaults, so the pipeline decides the rest.
    params = {f.id: v[f.id] for f in m.params if f.pipeline and v.get(f.id) not in (None, "") and v.get(f.id) != f.default}
    params.update({sheet["param"]: f"{d}/samplesheet.csv", "outdir": f"{d}/results"})
    res, user = run["resources"], run["user"]
    prefix = slurm.job_name(user, m.id, "")
    config = "\n".join([
        f"// Written by Everyome for run {run['id']}: how the pipeline's own tasks go to Slurm.",
        "process.executor = 'slurm'",
        *([f"process.queue = '{res['partition']}'"] if res.get("partition") else []),
        "executor {",
        "    queueSize = 50",
        "    // Stowers policy: every job carries Claude and the username",
        f"    jobName = {{ '{prefix}' + task.process.tokenize(':')[-1] }}",
        "}", ""])
    return {"samplesheet.csv": csv, "nf_params.json": json.dumps(params, indent=1), "nextflow.config": config}


def nextflow_command(run: dict, m: Manifest, python: str) -> str:
    nf, d = m.nextflow, run["dir"]
    if run.get("demo"):
        # Intent: no Nextflow or containers on the demo cluster; the module writes the same outputs instead.
        return f"{shlex.quote(python)} -m {nf['demo']}"
    q = shlex.quote
    return (f"nextflow run {q(nf['pipeline'])} -r {q(str(nf['revision']))} -profile {q(nf['profile'])} -ansi-log false "
            f"-c {q(d + '/nextflow.config')} -params-file {q(d + '/nf_params.json')} -work-dir {q(d + '/work')} "
            f"-with-trace {q(d + '/trace.txt')} -resume")


def trace_summary(backend, run: dict) -> dict:
    """Progress of a Nextflow run from its trace file (tasks are listed as they finish)."""
    try:
        lines = backend.read_text(f"{run['dir']}/trace.txt").splitlines()
    except FileNotFoundError:
        return {"started": False}
    head = lines[0].split("\t") if lines else []
    rows = [dict(zip(head, l.split("\t"))) for l in lines[1:] if l.strip()]
    by = {}
    for r in rows:
        by[r.get("status", "")] = by.get(r.get("status", ""), 0) + 1
    return {"started": True, "tasks": len(rows), "completed": by.get("COMPLETED", 0) + by.get("CACHED", 0),
            "failed": by.get("FAILED", 0) + by.get("ABORTED", 0), "recent": [r.get("name", "") for r in rows[-5:]][::-1]}


def stage_script(run: dict, m: Manifest, stage, python: str) -> str:
    d = run["dir"]
    res = {**run["resources"], **stage.resources}
    body = ["set -euo pipefail", f'echo "[$(date)] {m.id} stage {stage.id} ({stage.name}) on $(hostname)"',
            f"cd {shlex.quote(d)}",
            f"export EVERYOME_RUN_DIR={shlex.quote(d)}", f"export EVERYOME_PARAMS={shlex.quote(d + '/params.json')}",
            f"export EVERYOME_STAGE={shlex.quote(stage.id)}", f"export EVERYOME_CPUS={int(res.get('cpus', 1))}",
            # Intent: on the demo cluster, modules stand in for tools that are not installed there.
            *(["export EVERYOME_DEMO=1"] if run.get("demo") else []),
            # Intent: module commands name the cluster's Python as {python}; nothing else is substituted.
            nextflow_command(run, m, python) if m.nextflow else stage.run.replace("{python}", shlex.quote(python)),
            f'echo "[$(date)] stage {stage.id} done"']
    return slurm.script(slurm.job_name(run["user"], m.id, f"{stage.id}_{stage.name}"),
                        f"{d}/logs/{stage.id}_{stage.name}.log", res, body)


def preview(run: dict, m: Manifest, python: str, start_at: str | None = None) -> list[dict]:
    """The exact scripts that Run would submit, for the user to read first."""
    todo = _from(m, start_at)
    return [{"stage": s.id, "title": s.title, "path": f"{run['dir']}/jobs/{s.id}_{s.name}.sbatch",
             "script": stage_script(run, m, s, python)} for s in todo]


def submit(backend, run: dict, m: Manifest, python: str, start_at: str | None = None) -> dict:
    """Write the scripts and submit them as one afterok chain. Called only from the user's Run."""
    prev, ids = None, {}
    for item in preview(run, m, python, start_at):
        backend.write_text(item["path"], item["script"])
        prev = slurm.submit(backend, item["path"], run["dir"], after=prev)
        ids[item["stage"]] = prev
    # Intent: a re-run from a later stage keeps the earlier stages' finished jobs.
    earlier = [s.id for s in m.stages][:len(m.stages) - len(_from(m, start_at))]
    keep = {k: v for k, v in run.get("jobs", {}).items() if k in earlier}
    run["jobs"] = {**keep, **ids}
    run["submitted"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save(backend, run)
    return run["jobs"]


def status(backend, run: dict, m: Manifest) -> dict:
    st = slurm.states(backend, run.get("jobs", {}))
    done = bool(st) and all(st.get(s.id, {}).get("state") == "COMPLETED" for s in m.stages)
    return {"stages": st, "done": done}


def cancel(backend, run: dict) -> None:
    slurm.cancel(backend, run.get("jobs", {}).values())


def log_tail(backend, run: dict, m: Manifest, sid: str, n: int = 80) -> str:
    st = next((s for s in m.stages if s.id == sid), None)
    if not st:
        raise ValueError(f"No stage {sid} in {m.name}.")
    rc, out, _ = backend.run(f"tail -n {int(n)} {shlex.quote(run['dir'] + f'/logs/{st.id}_{st.name}.log')} 2>/dev/null")
    return out


def _from(m: Manifest, start_at: str | None):
    if not start_at:
        return list(m.stages)
    ids = [s.id for s in m.stages]
    if start_at not in ids:
        raise ValueError(f"No stage {start_at} in {m.name}.")
    return m.stages[ids.index(start_at):]
