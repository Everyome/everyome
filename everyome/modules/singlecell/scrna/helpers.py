"""App-side helpers for single-cell RNA-seq (run on this computer, reading the cluster through the backend).

  scan          fill the samples table from a folder of FASTQ files (10x names included)
  report        after nf-core/scrnaseq: which cell-by-gene matrices were made, and the MultiQC report
  matrix_paths  where nf-core/scrnaseq 4.x writes the combined matrices (shared with the engine)
"""
from __future__ import annotations

import re

# 10x: <sample>_S1_L001_R1_001.fastq.gz; also <sample>_R1.fastq.gz. Index reads (I1, I2) are not needed.
READ = re.compile(r"^(?P<sample>.+?)(?:_S\d+)?(?:_L(?P<lane>\d{3}))?[._]R(?P<read>[12])(?:_001)?\.f(ast)?q\.gz$")
KINDS = [("cellbender_filter", "Empty droplets and background removed by CellBender (recommended)"),
         ("filtered", "Cells called by the aligner"),
         ("raw", "Every barcode, including empty droplets")]


def matrix_paths(values: dict) -> list[tuple[str, str, str]]:
    """(kind, path relative to the run folder, description) for each combined matrix, best first."""
    aligner = values.get("aligner") or "simpleaf"
    return [(k, f"results/{aligner}/mtx_conversions/combined_{k}_matrix.h5ad", d) for k, d in KINDS]


def scan(backend, path: str = "") -> dict:
    if not path:
        raise ValueError("Choose the reads folder first.")
    files = sorted(e.name for e in backend.listdir(path) if not e.is_dir)
    found = {}
    for n in files:
        m = READ.match(n)
        if m:
            found.setdefault((m.group("sample"), m.group("lane") or ""), {})[m.group("read")] = f"{path.rstrip('/')}/{n}"
    if not found:
        raise ValueError("No FASTQ files named like <sample>_S1_L001_R1_001.fastq.gz (or <sample>_R1.fastq.gz) were found in that folder.")
    rows = []
    for (s, _lane), reads in sorted(found.items()):
        # Intent: suggest a condition from the name before its last _number (control_1 -> control); people check it.
        cond = re.sub(r"[_.-]?(rep)?\d+$", "", s, flags=re.I) or s
        rows.append({"sample": s, "fastq_1": reads.get("1", ""), "fastq_2": reads.get("2", ""), "expected_cells": "", "condition": cond, "batch": ""})
    lanes = len(rows) - len({r["sample"] for r in rows})
    return {"rows": rows, "message": f"Found {len({r['sample'] for r in rows})} samples in {len(rows)} pairs of files"
                                     + (f" ({lanes} extra lanes, combined by sample name)" if lanes else "")
                                     + ". Check each sample's condition (guessed from the name) and fill in batch if samples were prepared on different days."}


def report(backend, run: dict) -> dict:
    d = run["dir"]
    out = {"matrices": [], "multiqc": None}
    for kind, rel, desc in matrix_paths(run["values"]):
        if backend.exists(f"{d}/{rel}"):
            out["matrices"].append({"kind": kind, "path": rel, "description": desc})
    if backend.exists(f"{d}/results/multiqc/multiqc_report.html"):
        out["multiqc"] = "results/multiqc/multiqc_report.html"
    return out
