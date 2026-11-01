"""Stand-in for nf-core/scrnaseq on the demo cluster (no Nextflow or containers there).

Writes what the real pipeline writes that Everyome reads: the combined matrices
in mtx_conversions, a placeholder MultiQC report, and a Nextflow trace file so
the progress view behaves as it would on a real cluster.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

TASKS = ["FASTQC", "GFFREAD_TRANSCRIPTOME", "SIMPLEAF_INDEX", "SIMPLEAF_QUANT", "QCATCH", "CELLBENDER_REMOVEBACKGROUND",
         "ANNDATA_BARCODES", "MTX_TO_H5AD", "CONCAT_H5AD", "MULTIQC"]
ONCE = {"GFFREAD_TRANSCRIPTOME", "SIMPLEAF_INDEX", "CONCAT_H5AD", "MULTIQC"}


def main():
    run = Path(os.environ["EVERYOME_RUN_DIR"])
    params = json.loads((run / "params.json").read_text())
    nfp = json.loads((run / "nf_params.json").read_text())
    pause = float(os.environ.get("EVERYOME_DEMO_PAUSE", "1"))
    samples = list(dict.fromkeys(r["sample"] for r in params["samples"]))
    truth = Path(params["samples"][0]["fastq_1"]).parent.parent / ".demo_truth"
    aligner = nfp.get("aligner", "simpleaf")
    trace = run / "trace.txt"
    trace.write_text("task_id\thash\tnative_id\tname\tstatus\texit\n")
    k = 0
    for t in TASKS:
        for s in ([None] if t in ONCE else samples):
            k += 1
            name = f"NFCORE_SCRNASEQ:SCRNASEQ:{t}" + (f" ({s})" if s else "")
            with open(trace, "a") as fh:
                fh.write(f"{k}\tab/{k:06x}\t{1000 + k}\t{name}\tCOMPLETED\t0\n")
            print(f"[demo] {name}", flush=True)
        time.sleep(pause / len(TASKS))
    out = run / "results" / aligner / "mtx_conversions"
    out.mkdir(parents=True, exist_ok=True)
    import anndata as ad
    for kind in ("raw", "cellbender_filter"):
        if kind == "cellbender_filter" and nfp.get("skip_cellbender"):
            continue
        a = ad.read_h5ad(truth / f"combined_{kind}_matrix.h5ad")
        # Intent: keep only the samples in this run.
        a[a.obs["sample"].isin(samples).values].copy().write_h5ad(out / f"combined_{kind}_matrix.h5ad")
    qc = run / "results" / "multiqc"
    qc.mkdir(parents=True, exist_ok=True)
    (qc / "multiqc_report.html").write_text("<!doctype html><title>MultiQC (demo)</title><body style='font-family:sans-serif'>"
                                            "<h1>MultiQC report (demo)</h1><p>On a real cluster this is nf-core/scrnaseq's full quality report.</p></body>")
    shutil.copy(truth / "truth.json", run / "demo_truth.json")       # for tests: each cell's true type
    print("[demo] pipeline finished", flush=True)


if __name__ == "__main__":
    main()
