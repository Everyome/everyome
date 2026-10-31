"""Stand-in for nf-core/rnaseq on the demo cluster (no Nextflow or containers there).

Writes what the real pipeline writes that Everyome reads: the merged gene count
table in the aligner's folder, a placeholder MultiQC report, and a Nextflow
trace file so the progress view behaves as it would on a real cluster.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

TASKS = ["FASTQC", "TRIMGALORE", "STAR_GENOMEGENERATE", "STAR_ALIGN", "SALMON_QUANT", "SALMON_TX2GENE",
         "SALMON_TXIMPORT", "SAMTOOLS_SORT", "QUALIMAP_RNASEQ", "MULTIQC"]


def main():
    run = Path(os.environ["EVERYOME_RUN_DIR"])
    params = json.loads((run / "params.json").read_text())
    nfp = json.loads((run / "nf_params.json").read_text())
    pause = float(os.environ.get("EVERYOME_DEMO_PAUSE", "1"))
    samples = [r["sample"] for r in params["samples"]]
    truth = Path(params["samples"][0]["fastq_1"]).parent.parent / ".demo_truth"
    aligner = nfp.get("aligner", "star_salmon")
    trace = run / "trace.txt"
    trace.write_text("task_id\thash\tnative_id\tname\tstatus\texit\n")
    k = 0
    for t in TASKS:
        for s in (samples if t not in ("STAR_GENOMEGENERATE", "SALMON_TX2GENE", "SALMON_TXIMPORT", "MULTIQC") else [None]):
            k += 1
            name = f"NFCORE_RNASEQ:RNASEQ:{t}" + (f" ({s})" if s else "")
            with open(trace, "a") as fh:
                fh.write(f"{k}\tab/{k:06x}\t{1000 + k}\t{name}\tCOMPLETED\t0\n")
            print(f"[demo] {name}", flush=True)
        time.sleep(pause / len(TASKS))
    out = run / "results" / aligner
    out.mkdir(parents=True, exist_ok=True)
    # Intent: keep only the samples in this run, in the samplesheet's order.
    lines = (truth / "gene_counts.tsv").read_text().splitlines()
    head = lines[0].split("\t")
    keep = [0, 1] + [head.index(s) for s in samples if s in head]
    (out / "salmon.merged.gene_counts.tsv").write_text("\n".join("\t".join(l.split("\t")[i] for i in keep) for l in lines) + "\n")
    qc = run / "results" / "multiqc" / aligner
    qc.mkdir(parents=True, exist_ok=True)
    (qc / "multiqc_report.html").write_text("<!doctype html><title>MultiQC (demo)</title><body style='font-family:sans-serif'>"
                                            "<h1>MultiQC report (demo)</h1><p>On a real cluster this is nf-core/rnaseq's full quality report.</p></body>")
    shutil.copy(truth / "truth.json", run / "demo_truth.json")       # for tests: which genes truly changed
    print("[demo] pipeline finished", flush=True)


if __name__ == "__main__":
    main()
