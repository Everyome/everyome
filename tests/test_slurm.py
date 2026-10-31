"""Job naming and scripts follow the Stowers rule: Claude_<user>_everyome_<module>_<stage>."""
from everyome.core import slurm


def test_job_name():
    assert slurm.job_name("hh2891", "tutorial.sequence_summary", "01_lengths") == "Claude_hh2891_everyome_tutorial_sequence_summary_01_lengths"


def test_script_header():
    s = slurm.script("Claude_u_everyome_x_01", "/p/log.txt", {"cpus": 2, "mem": "3G", "time": "00:05:00", "partition": "short"}, ["echo hi"])
    assert s.startswith("#!/bin/bash\n#SBATCH --job-name=Claude_u_everyome_x_01\n")
    assert "#SBATCH --partition=short" in s and s.endswith("echo hi\n")
