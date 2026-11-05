"""Shared pieces for the demo cluster's stand-ins for nf-core pipelines (each module's demo_pipeline.py).

A stand-in writes what the real pipeline writes that Everyome reads, plus a Nextflow trace file so the progress view
behaves as it would on a real cluster. These helpers keep the trace format and the pacing identical everywhere.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

HEADER = "task_id\thash\tnative_id\tname\tstatus\texit\n"


def run_dir() -> Path:
    return Path(os.environ["EVERYOME_RUN_DIR"])


def load(run: Path) -> tuple[dict, dict]:
    """The run's Everyome values (params.json) and the pipeline parameters it was given (nf_params.json)."""
    return json.loads((run / "params.json").read_text()), json.loads((run / "nf_params.json").read_text())


def pause() -> float:
    """Seconds a whole demo run should take (tests set EVERYOME_DEMO_PAUSE small)."""
    return float(os.environ.get("EVERYOME_DEMO_PAUSE", "1"))


class Trace:
    """A Nextflow trace.txt that grows one COMPLETED task at a time, as on a real cluster."""

    def __init__(self, run: Path):
        self.path, self.k = run / "trace.txt", 0
        self.path.write_text(HEADER)

    def task(self, name: str):
        self.k += 1
        with open(self.path, "a") as fh:
            fh.write(f"{self.k}\tab/{self.k:06x}\t{1000 + self.k}\t{name}\tCOMPLETED\t0\n")
        print(f"[demo] {name}", flush=True)


def placeholder_report(path: Path, title: str, text: str):
    """A stand-in for the pipeline's own HTML report (MultiQC or similar)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"<!doctype html><title>{title} (demo)</title><body style='font-family:sans-serif'>"
                    f"<h1>{title} (demo)</h1><p>{text}</p></body>")


def run_tasks(trace: Trace, prefix: str, tasks: list, per_task=None):
    """Write each task (or one per item of per_task(task), for per-sample tasks), pacing the whole run."""
    p = pause()
    for t in tasks:
        items = per_task(t) if per_task else [None]
        for s in items:
            trace.task(f"{prefix}:{t}" + (f" ({s})" if s else ""))
        time.sleep(p / len(tasks))
