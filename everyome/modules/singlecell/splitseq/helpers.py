"""App-side helpers for the SPLiT-seq module (run on this computer, reading the cluster through the backend).

  scan       find sublibraries and runs from <sublib>_<run>_R1/R2.fq.gz names (fills the Sublibraries table)
  qc_report  read-level QC written by stages 05, 07 and 08, for the Run page
"""
from __future__ import annotations

import csv
import io
import shlex

from .stage import FASTQ


def scan(backend, path: str = "") -> dict:
    if not path:
        raise ValueError("Choose the raw reads folder first.")
    names = [e.name for e in backend.listdir(path) if not e.is_dir]
    stems = sorted({m.group("stem") for n in names if (m := FASTQ.match(n))})
    if not stems:
        raise ValueError("No paired FASTQ files (*_R1.fq.gz / *_R2.fq.gz) found in that folder.")
    # Intent: find where the sublibrary name ends and the run begins, by finding the split
    # that gives every sublibrary the same set of runs (as SPLiTscape did).
    best = None
    for k in range(1, max(len(s.split("_")) for s in stems)):
        subs = sorted({"_".join(s.split("_")[:k]) for s in stems})
        runs = sorted({"_".join(s.split("_")[k:]) for s in stems if len(s.split("_")) > k})
        if runs and len(subs) * len(runs) == len(stems) and len(subs) > 1:
            best = (subs, runs)
            break
    if not best:
        best = (sorted({s.rsplit("_", 1)[0] for s in stems}), sorted({s.rsplit("_", 1)[-1] for s in stems}))
    subs, runs = best
    return {"rows": [{"sublibrary": s, "library_id": f"lib_01_{i + 1}"} for i, s in enumerate(subs)],
            "message": f"Found {len(stems)} read pairs: {len(subs)} sublibraries × {len(runs)} runs ({', '.join(runs)}). "
                       "Check the library IDs: they become part of every cell's name."}


def _tsv(backend, path):
    try:
        return list(csv.DictReader(io.StringIO(backend.read_text(path)), delimiter="\t"))
    except FileNotFoundError:
        return None


def qc_report(backend, run: dict) -> dict:
    qc = f"{run['dir']}/reads/qc"
    out = {}
    num = lambda rows, keys: [{k: (float(v) if k in keys else v) for k, v in r.items()} for r in rows]
    reads = _tsv(backend, f"{qc}/unaligned_read_counts.tsv")
    if reads:
        out["reads"] = num(reads, {"reads"})
    regions = _tsv(backend, f"{qc}/region_counts.tsv")
    if regions:
        out["regions"] = num(regions, {"reads", "fraction"})
    dge = _tsv(backend, f"{qc}/dge_summary.tsv")
    if dge:
        out["dge"] = num(dge, {"cells", "genic_reads", "umis", "reads_per_umi"})
    knees = {}
    for row in run["values"]["sublibraries"]:
        name = row["sublibrary"]
        rc, txt, _ = backend.run(f"head -n 60000 {shlex.quote(run['dir'] + f'/reads/{name}/{name}_merged_elbow.tsv')} 2>/dev/null")
        vals = sorted((int(line.split("\t")[0]) for line in txt.splitlines() if line and line.split("\t")[0].isdigit()), reverse=True)
        if vals:
            # Intent: thin to ~300 points on a log rank scale for plotting.
            idx = sorted({min(len(vals) - 1, int(round(10 ** (k / 60)))) - 1 for k in range(0, 60 * 5)} - {-1})
            knees[name] = [[i + 1, vals[i]] for i in idx if i < len(vals)]
    if knees:
        out["knee"] = knees
    return out
