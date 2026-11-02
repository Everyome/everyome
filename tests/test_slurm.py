"""Job naming and scripts: [<prefix>_]<user>_everyome_<module>_<stage>. The suite runs with the prefix Claude (conftest.py)."""
from everyome.core import slurm


def test_job_name():
    assert slurm.job_name("hh2891", "tutorial.sequence_summary", "01_lengths") == "Claude_hh2891_everyome_tutorial_sequence_summary_01_lengths"


def test_script_header():
    s = slurm.script("Claude_u_everyome_x_01", "/p/log.txt", {"cpus": 2, "mem": "3G", "time": "00:05:00", "partition": "short"}, ["echo hi"])
    assert s.startswith("#!/bin/bash\n#SBATCH --job-name=Claude_u_everyome_x_01\n")
    assert "#SBATCH --partition=short" in s and s.endswith("echo hi\n")


def test_no_prefix_by_default():
    """Without EVERYOME_JOB_PREFIX, job and process names start with the username (jobs are the user's own)."""
    import subprocess
    import sys
    env = {k: v for k, v in __import__("os").environ.items() if k != "EVERYOME_JOB_PREFIX"}
    code = ("from everyome.core import slurm; print(repr(slurm.JOB_PREFIX), slurm.job_name('hh2891', 'phylo.tree', '03_tree'), "
            "slurm.proc_name('hh2891', 'everyome_app'))")
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True).stdout.split()
    assert out == ["''", "hh2891_everyome_phylo_tree_03_tree", "hh2891_everyome_app"]
    env["EVERYOME_JOB_PREFIX"] = "bad prefix!"
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True).stdout.split()
    assert out[0] == "''"                      # an invalid prefix is ignored, never put into a job name
