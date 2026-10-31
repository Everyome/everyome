"""Run one SPLiTscape read-processing stage (01–08) for an Everyome run.

Called by each job as `python -m everyome.modules.singlecell.splitseq.stage <id> <name>`
inside the run folder. Writes <run>/config/reads.env from the run's settings,
then runs the SPLiTscape bash stage (or, on the demo cluster, a stand-in that
writes the same output files).
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = {"01": "01_read_preprocessing.sh", "02": "01_read_preprocessing.sh", "03": "01_read_preprocessing.sh",
           "04": "01_read_preprocessing.sh", "05": "01_read_preprocessing.sh",
           "06": "02_align_merge_dge.sh", "07": "02_align_merge_dge.sh", "08": "02_align_merge_dge.sh"}
# Everyome setting id -> reads.env key (the names the SPLiTscape bash stages use).
SETTINGS = {"r1_adapter": "R1_ADAPTER", "r1_min_len": "R1_MIN_LEN", "r2_adapter": "R2_ADAPTER", "r2_min_len": "R2_MIN_LEN",
            "r2_truncate": "R2_TRUNCATE", "dephase_regex": "DEPHASE_REGEX", "expected_cells": "EXPECTED_CELLS",
            "min_genes_per_cell": "MIN_GENES_PER_CELL", "locus_function_list": "LOCUS_FUNCTION_LIST"}
FASTQ = re.compile(r"^(?P<stem>.+)_R(?P<read>[12])\.f(ast)?q\.gz$")


def runs_for(names: list[str], sublibs: list[str]) -> list[str]:
    """Sequencing runs shared by every sublibrary, from <sublib>_<run>_R1/R2.fq.gz names."""
    pairs = {}
    for n in names:
        m = FASTQ.match(n)
        if m:
            pairs.setdefault(m.group("stem"), set()).add(m.group("read"))
    per = {}
    for s in sublibs:
        per[s] = sorted(stem[len(s) + 1:] for stem, reads in pairs.items() if stem.startswith(s + "_") and reads == {"1", "2"})
        if not per[s]:
            raise ValueError(f"No paired reads ({s}_<run>_R1.fq.gz and _R2.fq.gz) found for sublibrary {s}.")
    first = per[sublibs[0]]
    for s, r in per.items():
        if r != first:
            raise ValueError(f"Sublibrary {s} has runs {', '.join(r)} but {sublibs[0]} has {', '.join(first)}; every sublibrary needs the same runs.")
    return first


def reads_env(params: dict, run_dir: str, user: str, runs: list[str]) -> str:
    q = lambda v: shlex.quote(str(v))
    lines = ["# Written by Everyome (SPLiT-seq module). Change settings in the app, not here.",
             f"PIPELINE_USER={q(user)}",
             f"SUBLIBS=({' '.join(q(r['sublibrary']) for r in params['sublibraries'])})",
             f"RUNS=({' '.join(q(r) for r in runs)})",
             f"RAW_DIR={q(params['raw_dir'])}", f"REF_FASTA={q(params['ref_fasta'])}", f"STAR_INDEX={q(params['star_index'])}",
             f"SPLITSEQ_TOOLBOX={q(params['toolbox'])}", f"PAIRFQ={q(params['pairfq'])}",
             f"WORK_DIR={q(run_dir + '/work')}", f"OUT_DIR={q(run_dir + '/reads')}", "KEEP_INTERMEDIATES=0",
             "MAX_PARALLEL=4", "EDIT_DISTANCE=1", "READ_MQ=0", "UMI_STATS_MIN_GENES=9", 'JAVA_HOME_OVERRIDE=""',
             # Intent: threads follow the CPUs the job asked for, so the two can never disagree.
             f"THREADS={q(os.environ.get('EVERYOME_CPUS', '8'))}"]
    lines += [f"{key}={q(params[pid])}" for pid, key in SETTINGS.items()]
    return "\n".join(lines) + "\n"


def main(sid: str, name: str):
    run_dir = os.environ["EVERYOME_RUN_DIR"]
    params = json.loads(Path(os.environ["EVERYOME_PARAMS"]).read_text())
    run = json.loads((Path(run_dir) / "run.json").read_text())
    subs = [r["sublibrary"] for r in params["sublibraries"]]
    runs = runs_for(os.listdir(params["raw_dir"]), subs)
    cfg = Path(run_dir) / "config" / "reads.env"
    cfg.parent.mkdir(exist_ok=True)
    cfg.write_text(reads_env(params, run_dir, run["user"], runs))
    if os.environ.get("EVERYOME_DEMO"):
        from . import mock_stage
        mock_stage.main(sid, params, run_dir, subs, runs)
        return
    os.environ["CONFIG_FILE"] = str(cfg)
    script = HERE / "workflow" / "reads" / SCRIPTS[sid]
    os.execvp("bash", ["bash", str(script), name])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
