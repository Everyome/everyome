"""Run `python -m everyome.core.rerun` the way a user would on the cluster (here: the demo cluster)."""
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
