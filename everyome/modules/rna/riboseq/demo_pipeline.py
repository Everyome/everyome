"""Stand-in for nf-core/riboseq on the demo cluster (no Nextflow or containers there).

Writes what the real pipeline writes that Everyome reads, where it writes it, for the demo transcriptome
(demo_data.py): in-frame P-site and RNA-seq counts per gene, riboWaltz's P-site offsets and per-footprint P-site tables
(with the 3-nucleotide rhythm, stronger for some read lengths than others), the ORF catalogue and Ribo-TISH's
predictions, anota2seq's tables when the run has a contrasts file, a placeholder MultiQC report and a trace file.
"""
from __future__ import annotations

import csv
import json
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

from everyome.core.demo import nfstub

from .engine import classify, pairs_of, te_table
from .helpers import ANOTA, CATALOGUE_DIR, COUNTS, MULTIQC, RIBOTISH, RIBOWALTZ

TASKS = ["FQ_LINT", "TRIMGALORE", "SORTMERNA", "STAR_ALIGN", "SAMTOOLS_SORT", "RIBOTISH_QUALITY", "RIBOWALTZ", "PLASTID_PSITE",
         "RIBOTISH_PREDICT", "RIBOCODE", "ORF_CATALOGUE", "SALMON_QUANT", "INFRAME_PSITE_COUNT", "ANOTA2SEQ", "MULTIQC"]
PER_SAMPLE = {"FQ_LINT", "TRIMGALORE", "SORTMERNA", "STAR_ALIGN", "SAMTOOLS_SORT", "RIBOTISH_QUALITY", "RIBOWALTZ", "PLASTID_PSITE",
              "RIBOTISH_PREDICT", "SALMON_QUANT"}
READS = 3000                       # footprints per Ribo-seq library in the demo P-site tables
# Intent: how sharply each footprint length keeps the reading frame once its P-site offset is applied.
PHASE = {28: (.72, .15, .13), 29: (.75, .13, .12), 30: (.72, .15, .13), 31: (.66, .18, .16), 27: (.55, .25, .2), 32: (.55, .25, .2),
         34: (.34, .33, .33)}


def _psites(t: dict, weight: np.ndarray, sample: str, out: Path):
    rng = np.random.default_rng(zlib.crc32(sample.encode()))
    genes, lengths = t["genes"], {int(k): v for k, v in t["lengths"].items()}
    offsets = {int(k): v for k, v in t["offsets"].items()}
    uorf = {}
    for o in t["orfs"]:
        if o["class"] == "uORF":
            uorf.setdefault(o["gene"], o)
    L = np.array(list(lengths))
    p = np.array(list(lengths.values()))
    rows = []
    for gi, ln in zip(rng.choice(len(genes), READS, p=weight / weight.sum()), rng.choice(L, READS, p=p / p.sum())):
        g, ln = genes[gi], int(ln)
        cs, ce = g["utr5"] + 1, g["utr5"] + g["cds"]                 # first base of the start codon, last of the stop codon
        where = rng.random()
        if where < 0.86:
            # Intent: ribosomes pause at the start codon, so a few footprints sit exactly there.
            k = 0 if rng.random() < 0.06 else int(rng.integers(0, g["cds"] // 3))
            ps = cs + 3 * k + int(rng.choice(3, p=PHASE.get(ln, (.42, .3, .28))))
        elif where < 0.96:
            o = uorf.get(g["id"])
            ps = (o["start"] + 1 + 3 * int(rng.integers(0, (o["end"] - o["start"]) // 3))) if o else int(rng.integers(1, cs))
        else:
            ps = int(rng.integers(ce + 1, ce + g["utr3"]))
        e5 = ps - offsets[ln]
        region = "cds" if cs <= ps <= ce else ("5utr" if ps < cs else "3utr")
        rows.append((g["tx"], e5, ps, e5 + ln - 1, ln, cs, ce, ps - cs, ps - ce, region))
    with open(out / f"{sample}.psite.tsv", "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["transcript", "end5", "psite", "end3", "length", "cds_start", "cds_stop", "psite_from_start", "psite_from_stop", "psite_region"])
        w.writerows(rows)
    seen = pd.Series([r[4] for r in rows]).value_counts(normalize=True)
    with open(out / f"{sample}.psite_offset.tsv", "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["length", "total_percentage", "start_percentage", "around_start", "offset_from_5", "offset_from_3",
                    "corrected_offset_from_5", "corrected_offset_from_3", "sample"])
        for ln in sorted(lengths):
            o = offsets[ln]
            w.writerow([ln, round(100 * float(seen.get(ln, 0)), 3), round(100 * float(seen.get(ln, 0)), 3), "T", o, ln - o - 1, o, ln - o - 1, sample])


def _orfs(t: dict, res: Path):
    by = {g["id"]: g for g in t["genes"]}
    (res / CATALOGUE_DIR).mkdir(parents=True, exist_ok=True)
    with open(res / CATALOGUE_DIR / "riboseq.catalogue.tsv", "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["orf_id", "chrom", "start", "end", "strand", "gene_id", "transcript_id", "orf_class", "aa_length", "is_smorf",
                    "orf_type_native", "called_by_ribotish", "called_by_ribocode", "score_ribotish", "score_ribocode"])
        for i, o in enumerate(t["orfs"], 1):
            g = by[o["gene"]]
            native = {"canonical_cds": "annotated", "uORF": "uORF", "dORF": "dORF"}[o["class"]]
            w.writerow([f"orf_{i:08d}", g["chrom"], g["start"] + o["start"], g["start"] + o["end"], g["strand"], g["id"], g["tx"], o["class"],
                        o["aa"], str(o["aa"] <= 100).lower(), native, 1, int(o["class"] != "dORF"), 0.001, 0.92 if o["class"] != "dORF" else ""])
    (res / RIBOTISH).parent.mkdir(parents=True, exist_ok=True)
    with open(res / RIBOTISH, "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["Gid", "Tid", "Symbol", "GeneType", "GenomePos", "StartCodon", "Start", "Stop", "TisType", "RiboPvalue", "AALen"])
        for o in t["orfs"]:
            g = by[o["gene"]]
            tis = {"canonical_cds": "Annotated", "uORF": "5'UTR", "dORF": "3'UTR"}[o["class"]]
            w.writerow([g["id"], g["tx"], g["name"], "protein_coding", f"{g['chrom']}:{g['start'] + o['start']}-{g['start'] + o['end']}:{g['strand']}",
                        "ATG", o["start"], o["end"], tis, 1e-4, o["aa"]])


def _anota(contrasts: str, rows: list[dict], counts: pd.DataFrame, res: Path):
    """anota2seq's tables for each contrast. Demo only: the numbers come from the session's own moderated t-test."""
    (res / ANOTA).mkdir(parents=True, exist_ok=True)
    for c in csv.DictReader(open(contrasts)):
        var = c["variable"]
        rr = [{**r, "condition": r.get(var, r.get("condition", ""))} for r in rows]
        t = te_table(counts, pairs_of(rr), c["target"], c["reference"])
        t["class"] = classify(t, 0.05)
        for part, key in (("translation", "te"), ("total_mRNA", "rna"), ("translated_mRNA", "ribo")):
            pd.DataFrame({"apvSlope": 1.0, "apvEff": t[f"{key}_log2fc"].round(5), "apvRvmP": t[f"{key}_p"],
                          "apvRvmPAdj": t[f"{key}_padj"], "singleRegMode": np.where(t["class"] == "unchanged", "none", t["class"])},
                         index=t.index.rename("gene_id")).to_csv(res / ANOTA / f"{c['id']}.{part}.anota2seq.results.tsv", sep="\t")


def main():
    run = nfstub.run_dir()
    _, nfp = nfstub.load(run)
    rows = list(csv.DictReader(open(nfp["input"])))
    names = [r["sample"] for r in rows]
    truth_dir = Path(rows[0]["fastq_1"]).parent.parent / ".demo_truth"
    t = json.loads((truth_dir / "truth.json").read_text())
    trace = nfstub.Trace(run)
    nfstub.run_tasks(trace, "NFCORE_RIBOSEQ:RIBOSEQ", TASKS, lambda k: names if k in PER_SAMPLE else [None])
    res = Path(nfp["outdir"])
    # Intent: keep only this run's libraries, in the samplesheet's order.
    full = pd.read_csv(truth_dir / "counts.tsv", sep="\t").set_index("gene_id")
    keep = [s for s in names if s in full.columns]
    (res / COUNTS).parent.mkdir(parents=True, exist_ok=True)
    full[["gene_name", *keep]].to_csv(res / COUNTS, sep="\t")
    (res / RIBOWALTZ).mkdir(parents=True, exist_ok=True)
    for r in rows:
        if r["type"] in ("riboseq", "tiseq") and r["sample"] in full.columns:
            _psites(t, full[r["sample"]].values.astype(float) + 1, r["sample"], res / RIBOWALTZ)
    _orfs(t, res)
    if nfp.get("contrasts"):
        _anota(nfp["contrasts"], rows, full[keep].astype(float), res)
    nfstub.placeholder_report(res / MULTIQC, "MultiQC report", "On a real cluster this is nf-core/riboseq's full quality report.")
    (res / "pipeline_info").mkdir(exist_ok=True)
    print(f"[demo] nf-core/riboseq stand-in finished: {len(names)} libraries", flush=True)


if __name__ == "__main__":
    main()
