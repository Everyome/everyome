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

import importlib
import json
import shlex
import time

from . import containers, pipelines, projects, slurm
from .manifest import Manifest, check_values


def create(backend, project: dict, m: Manifest, values: dict, resources: dict, demo: bool = False, site: dict | None = None) -> dict:
    """Check the settings and write a new run folder; nothing is submitted."""
    vals, errors = check_values(m, values)
    if errors:
        raise ValueError(" ".join(errors.values()))
    if m.check:
        # Intent: a module can refuse settings that would waste a large download or a GPU allocation.
        mod, _, fn = m.check.partition(":")
        problems = getattr(importlib.import_module(mod), fn)(vals, demo)
        if problems:
            raise ValueError(" ".join(problems))
    rid = f"{m.id.split('.')[-1]}_{time.strftime('%Y%m%d-%H%M%S')}"
    d = f"{project['dir']}/runs/{rid}"
    run = {"id": rid, "dir": d, "module": m.id, "module_version": m.version, "created": time.strftime("%Y-%m-%d %H:%M:%S"),
           "user": project["user"], "values": vals,
           # Intent: inputs are always the user's own files; only settings have meaningful defaults.
           "defaults_changed": sorted(f.id for f in m.params if vals.get(f.id) != f.default),
           "resources": {**m.resources, **{k: v for k, v in resources.items() if v}}, "jobs": {}, "demo": demo,
           # Intent: a run keeps the site settings it was made with, so its scripts and reruns stay the same.
           "job_prefix": (site or {}).get("job_prefix", slurm.JOB_PREFIX), "pipelines_dir": (site or {}).get("pipelines_dir", "")}
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
    sep, empty, fname = sheet.get("sep", ","), sheet.get("empty", ""), sheet.get("name", "samplesheet.csv")

    def cell(r, c):
        if isinstance(c, str):
            v = r.get(c, "")
        elif "value" in c:
            v = c["value"]
        elif "if_filled" in c:
            v = "true" if str(r.get(c["if_filled"], "")).strip() else "false"
        else:
            v = r.get(c["from"], "")
        return str(v) if str(v).strip() else empty
    names = [c if isinstance(c, str) else c["name"] for c in sheet["columns"]]
    # Intent: optional columns nobody filled in are left out, so the pipeline uses its own setting for them.
    keep = [i for i, c in enumerate(sheet["columns"]) if not (isinstance(c, dict) and c.get("drop_if_empty") and not any(str(r.get(c["from"], "")).strip() for r in rows))]
    csv = sep.join(names[i] for i in keep) + "\n" + "".join(sep.join(cell(r, sheet["columns"][i]) for i in keep) + "\n" for r in rows)
    # Intent: pass only what differs from the pipeline's own defaults, so the pipeline decides the rest.
    base = lambda f: nf.get("upstream", {}).get(f.id, f.default)
    params = {f.id: v[f.id] for f in m.params if f.pipeline and v.get(f.id) not in (None, "") and v.get(f.id) != base(f)}
    params.update({sheet["param"]: f"{d}/{fname}", "outdir": f"{d}/results"})
    res, user = run["resources"], run["user"]
    prefix = slurm.job_name(user, m.id, "", run.get("job_prefix", slurm.JOB_PREFIX))
    gpu = nf.get("gpu") or {}
    gpu_part = str(v.get(gpu.get("partition", ""), "") or "").strip() if gpu else ""
    config = "\n".join([
        f"// Written by Everyome for run {run['id']}: how the pipeline's own tasks go to Slurm.",
        "process.executor = 'slurm'",
        *([f"process.queue = '{res['partition']}'"] if res.get("partition") else []),
        # Intent: Slurm ignores Nextflow's accelerator setting, so GPU tasks ask for their GPUs themselves,
        # on the GPU partition when one is given.
        *(["process {", f"    withLabel: '{gpu['label']}' {{",
           *([f"        queue = '{gpu_part}'"] if gpu_part else []),
           "        clusterOptions = { task.accelerator ? \"--gres=gpu:${task.accelerator.request}\" : '--gres=gpu:1' }",
           "    }", "}"] if gpu and v.get(gpu["param"]) else []),
        "executor {",
        "    queueSize = 50",
        "    // Job names carry the job-name prefix and the username, so everyone can see whose job it is",
        f"    jobName = {{ '{prefix}' + task.process.tokenize(':')[-1] }}",
        "}", ""])
    return {fname: csv, "nf_params.json": json.dumps(params, indent=1), "nextflow.config": config}


def nextflow_command(run: dict, m: Manifest, python: str) -> str:
    nf, d = m.nextflow, run["dir"]
    if run.get("demo"):
        # Intent: no Nextflow or containers on the demo cluster; the module writes the same outputs instead.
        return f"{shlex.quote(python)} -m {nf['demo']}"
    q = shlex.quote
    # Intent: run the copy Everyome installed (pinned and checked), never a download from GitHub.
    where = pipelines.remote_dir(run["pipelines_dir"], pipelines.key(nf["pipeline"], str(nf["revision"])))
    gpu = nf.get("gpu") or {}
    # Intent: the pipeline's GPU profile goes with the GPU setting (it gives GPU tasks their GPU and container flags).
    profile = nf["profile"] + (f",{gpu['profile']}" if gpu and run["values"].get(gpu["param"]) else "")
    return (f"nextflow run {q(where)} -profile {q(profile)} -ansi-log false "
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
            # Intent: processes inside the job carry the same name prefix as the job itself.
            f"export EVERYOME_JOB_PREFIX={shlex.quote(run.get('job_prefix', slurm.JOB_PREFIX))}",
            # Intent: on the demo cluster, modules stand in for tools that are not installed there.
            *(["export EVERYOME_DEMO=1"] if run.get("demo") else []),
            *(pipelines.environment(run["pipelines_dir"]) if m.nextflow and not run.get("demo") else []),
            *(containers.environment(run["pipelines_dir"]) if m.containers and not run.get("demo") else []),
            # Intent: module commands name the cluster's Python as {python}; nothing else is substituted.
            nextflow_command(run, m, python) if m.nextflow else stage.run.replace("{python}", shlex.quote(python)),
            f'echo "[$(date)] stage {stage.id} done"']
    return slurm.script(slurm.job_name(run["user"], m.id, f"{stage.id}_{stage.name}", run.get("job_prefix", slurm.JOB_PREFIX)),
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
