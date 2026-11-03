"""Helpers for the end-to-end tests: wait for a run's jobs, and run `python -m everyome.core.rerun` the way a
user would on the cluster (here: the demo cluster)."""
import os
import subprocess
import sys
import time


def rerun(demo_root, bundle, new_dir, flag=None):
    env = dict(os.environ, PATH=f"{demo_root}/.bin{os.pathsep}{os.environ['PATH']}", FAKE_SLURM_HOME=f"{demo_root}/.slurm")
    args = [sys.executable, "-m", "everyome.core.rerun", str(bundle), str(new_dir)] + ([flag] if flag else [])
    return subprocess.run(args, env=env, capture_output=True, text=True, timeout=600)


def rerun_until_session_replayed(demo_root, bundle, new_dir, timeout=600):
    """--session refuses until the repeated jobs finish; keep trying, as a user would."""
    end = time.time() + timeout
    while time.time() < end:
        p = rerun(demo_root, bundle, new_dir, "--session")
        if p.returncode == 0:
            return p
        assert "have not all finished" in (p.stderr + p.stdout), p.stderr + p.stdout
        time.sleep(1)
    raise AssertionError("repeated jobs did not finish")


# Intent: Slurm states that mean a stage stopped without finishing (the app flags the first three the same way).
STOPPED = {"FAILED", "TIMEOUT", "OUT_OF_MEMORY", "CANCELLED", "NODE_FAIL", "BOOT_FAIL", "PREEMPTED", "DEADLINE"}


def wait_for_run(client, timeout=600, every=0.5):
    """Wait until every stage of the current run has COMPLETED.

    A failed stage never becomes "done", so stop as soon as one has stopped and name it, rather than waiting out
    the timeout; on a real timeout, say how far each stage got (slow runner, or stuck?)."""
    end, states = time.time() + timeout, {}
    while time.time() < end:
        r = client.get("/api/run/status")
        assert r.status_code == 200, r.text
        st = r.json()
        states = {k: v.get("state") for k, v in st["stages"].items()}
        stopped = {k: s for k, s in states.items() if s in STOPPED}
        assert not stopped, f"stage(s) stopped: {stopped}; all stages: {states}"
        if st["done"]:
            return st
        time.sleep(every)
    raise AssertionError(f"run not finished after {timeout} s; stages: {states}")
