"""Stand-in for stages 01–08 on the demo cluster (carried over from SPLiTscape).

Sleeps a moment and writes the same output files the real stage writes, so the
progress and QC views behave exactly as on a real cluster. The demo data's
.demo_truth folder (next to the raw reads) holds the matrices stage 08 "produces".
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

import numpy as np


def main(sid: str, params: dict, run_dir: str, subs: list[str], runs: list[str]):
    truth = Path(params["raw_dir"]).parent / ".demo_truth"
    out, qc = Path(run_dir) / "reads", Path(run_dir) / "reads" / "qc"
    qc.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(sid))
    pause = float(os.environ.get("EVERYOME_DEMO_PAUSE", "1"))
    for k in range(4):
        print(f"  working... {25 * (k + 1)}%", flush=True)
        time.sleep(pause / 4)

    if sid == "01":
        (qc / "fastqc_raw").mkdir(exist_ok=True)
        for s in subs:
            for r in runs:
                for rd in ("R1", "R2"):
                    (qc / "fastqc_raw" / f"{s}_{r}_{rd}_fastqc.html").write_text("<html><body>Demo FastQC report</body></html>")
    elif sid == "05":
        lines = ["sublib\trun\treads"]
        for s in subs:
            for r in runs:
                lines.append(f"{s}\t{r}\t{int(rng.normal(4.2e7, 4e6))}")
        (qc / "unaligned_read_counts.tsv").write_text("\n".join(lines) + "\n")
    elif sid == "06":
        for s in subs:
            (out / s).mkdir(parents=True, exist_ok=True)
            for r in runs:
                (out / s / f"{s}_{r}_gft.bam").write_bytes(b"demo")
    elif sid == "07":
        lines = ["sublib\tlocus_function\treads\tfraction"]
        for s in subs:
            fr = dict(CODING=.25 + rng.normal(0, .01), **{"CODING,UTR": .02, "UTR": .015, "INTRONIC": .08, "INTERGENIC": .085})
            fr["NO_XF"] = 1 - sum(fr.values())
            tot = int(rng.normal(3.8e7, 2e6))
            for k, v in sorted(fr.items(), key=lambda kv: -kv[1]):
                lines.append(f"{s}\t{k}\t{int(v * tot)}\t{v:.4f}")
            lines.append(f"{s}\tTOTAL\t{tot}\t1.0000")
            (out / s / f"{s}_merged.bam").write_bytes(b"demo")
        (qc / "region_counts.tsv").write_text("\n".join(lines) + "\n")
    elif sid == "08":
        info = json.loads((truth / "info.json").read_text())
        lines = ["sublib\tcells\tgenic_reads\tumis\treads_per_umi"]
        for s, sm in zip(subs, info["summary"]):
            src = truth / f"sublib_{subs.index(s) + 1}_G50_matrix.txt.gz"
            (out / s).mkdir(parents=True, exist_ok=True)
            shutil.copy(src, out / s / f"{s}_G{params['min_genes_per_cell']}_matrix.txt.gz")
            reads = int(sm["umis"] * rng.uniform(20, 30))
            lines.append(f"{s}\t{sm['cells']}\t{reads}\t{sm['umis']}\t{reads / sm['umis']:.2f}")
            # Knee data: real cells then a long tail of background barcodes.
            cells = np.sort(rng.lognormal(9.3, .6, sm["cells"]))[::-1]
            bg = np.sort(rng.lognormal(4.2, 1.1, 40000))[::-1]
            vals = np.sort(np.concatenate([cells, bg]))[::-1].astype(int)
            (out / s / f"{s}_merged_elbow.tsv").write_text("\n".join(f"{v}\tBC{i}" for i, v in enumerate(vals)) + "\n")
        (qc / "dge_summary.tsv").write_text("\n".join(lines) + "\n")
    print("  done", flush=True)
