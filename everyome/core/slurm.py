"""Slurm, the scheduler Everyome supports first. Every call runs through a backend.

Jobs are only ever submitted from a user action (pressing Run), under the
user's own account. Nothing here submits on its own.
"""
from __future__ import annotations

import re
import shlex

# Intent: job names say who made them: <prefix>_<user>_everyome_<module>_<stage>. The prefix is a site
# setting (some institutions require one); the default follows the policy of the site Everyome was built at.
JOB_PREFIX = "Claude"
PREFIX_OK = re.compile(r"[A-Za-z0-9_-]{0,32}")


def job_name(user: str, module_id: str, stage: str, prefix: str = JOB_PREFIX) -> str:
    """<prefix>_<user>_everyome_<module>_<stage> (no prefix: <user>_everyome_...), with characters Slurm dislikes replaced."""
    clean = lambda s: re.sub(r"[^A-Za-z0-9_-]+", "_", s)
    head = "_".join(filter(None, [clean(prefix), clean(user), "everyome", clean(module_id)]))
    return f"{head}_{clean(stage)}"


def script(name: str, log: str, resources: dict, body: list[str]) -> str:
    """A batch script with the #SBATCH header Everyome uses for every job."""
    head = ["#!/bin/bash", f"#SBATCH --job-name={name}", f"#SBATCH --output={log}",
            f"#SBATCH --cpus-per-task={resources.get('cpus', 1)}", f"#SBATCH --mem={resources.get('mem', '4G')}",
            f"#SBATCH --time={resources.get('time', '01:00:00')}"]
    if resources.get("partition"):
        head.append(f"#SBATCH --partition={resources['partition']}")
    return "\n".join(head + body) + "\n"


def submit(backend, path: str, cwd: str, after: int | None = None) -> int:
    """Submit one script; `after` makes it wait for that job to succeed (afterok)."""
    dep = f"--dependency=afterok:{after} " if after else ""
    rc, out, err = backend.run(f"cd {shlex.quote(cwd)} && sbatch --parsable {dep}{shlex.quote(path)}")
    if rc:
        raise RuntimeError(f"sbatch failed: {err.strip() or out.strip()}")
    return int(out.strip().split(";")[0])


def states(backend, ids: dict[str, int]) -> dict[str, dict]:
    """State per key from squeue (live) and sacct (finished)."""
    if not ids:
        return {}
    joined = ",".join(str(i) for i in ids.values())
    found = {}
    rc, out, _ = backend.run(f"sacct -n -P -j {joined} -o JobID,State,Elapsed 2>/dev/null")
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) >= 3 and parts[0].isdigit():
            found[int(parts[0])] = {"state": parts[1].split()[0], "elapsed": parts[2]}
    rc, out, _ = backend.run(f"squeue -h -j {joined} -o '%i %T %N' 2>/dev/null")
    for line in out.splitlines():
        parts = line.split()
        if parts and parts[0].isdigit():
            found.setdefault(int(parts[0]), {}).update(state=parts[1], node=parts[2] if len(parts) > 2 else "")
    return {k: {"job": jid, **found.get(jid, {"state": "UNKNOWN"})} for k, jid in ids.items()}


def cancel(backend, ids) -> None:
    ids = list(ids)
    if ids:
        backend.run("scancel " + " ".join(str(i) for i in ids))
