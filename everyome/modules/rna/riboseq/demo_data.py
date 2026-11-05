"""Build the Ribo-seq demo data: three control and three treated biological samples, each with a Ribo-seq library and
the matched RNA-seq library, on a made-up transcriptome where the truth is known.

<root> = <demo cluster>/data/rna.riboseq/
  fastq/                      placeholder reads: <condition>_<rep>_ribo_R1.fastq.gz, <condition>_<rep>_rna_R1/_R2.fastq.gz
  genome/genome.fa, genes.gtf placeholder reference
  .demo_truth/truth.json      genes, their transcripts, planted ORFs, P-site offsets, and which genes truly change
                              translational efficiency (TE) or only their mRNA
  .demo_truth/counts.tsv      the counts the demo pipeline 'produces' (in-frame P-sites for Ribo-seq, reads for RNA-seq)

Every Ribo-seq library shares its biological variation with the RNA-seq library from the same sample (its pair), as in a
real experiment; that is why TE is computed within pairs.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np

CONDITIONS = ("control", "treated")
REPS = (1, 2, 3)
N_GENES, N_TE, N_RNA = 1500, 50, 50          # genes; planted TE up (and down); planted mRNA-only changes (up and down)
TE_FOLD, RNA_FOLD = 2.5, 3.0
# Intent: footprint lengths and the P-site offset (from the 5' end) riboWaltz would find for each.
LENGTHS = {25: 0.02, 26: 0.04, 27: 0.08, 28: 0.18, 29: 0.25, 30: 0.2, 31: 0.12, 32: 0.06, 33: 0.03, 34: 0.02}
OFFSETS = {25: 11, 26: 11, 27: 12, 28: 12, 29: 12, 30: 12, 31: 13, 32: 13, 33: 13, 34: 14}


def samples() -> list[dict]:
    out = []
    for c in CONDITIONS:
        for r in REPS:
            for t in ("ribo", "rna"):
                out.append({"sample": f"{c}_{r}_{t}", "type": "riboseq" if t == "ribo" else "rnaseq", "pair": f"{c}_{r}", "condition": c})
    return out


def truth(seed: int = 17) -> dict:
    rng = np.random.default_rng(seed)
    genes = []
    kind = np.array(["none"] * N_GENES, dtype=object)
    idx = rng.permutation(np.arange(200, N_GENES))           # Intent: the first 200 genes stay unchanged, for ORF examples.
    kind[idx[:N_TE]], kind[idx[N_TE:2 * N_TE]] = "te_up", "te_down"
    kind[idx[2 * N_TE:2 * N_TE + N_RNA]], kind[idx[2 * N_TE + N_RNA:2 * N_TE + 2 * N_RNA]] = "rna_up", "rna_down"
    names = {"te_up": "teup", "te_down": "tedown", "rna_up": "rnaup", "rna_down": "rnadown"}
    count = {k: 0 for k in names}
    for g in range(N_GENES):
        utr5, cds, utr3 = int(rng.integers(60, 400)), 3 * int(rng.integers(100, 700)), int(rng.integers(80, 500))
        k = kind[g]
        if k in names:
            count[k] += 1
            name = f"{names[k]}{count[k]}"
        else:
            name = f"gene{g + 1}"
        genes.append({"id": f"RIBODEMO{g + 1:05d}", "name": name, "tx": f"RIBODEMOT{g + 1:05d}", "kind": k,
                      "utr5": utr5, "cds": cds, "utr3": utr3, "chrom": f"demo{1 + g % 4}", "start": 10_000 + 6_000 * (g // 4),
                      "strand": "+" if g % 2 == 0 else "-",
                      "rna": float(np.exp(rng.normal(4.6, 1.3))), "te": float(np.exp(rng.normal(0, 0.45)))})
    # Intent: every gene's CDS is translated; some 5' leaders carry a translated uORF, a few 3' ends a dORF.
    orfs = []
    for g in genes:
        orfs.append({"gene": g["id"], "tx": g["tx"], "class": "canonical_cds", "start": g["utr5"], "end": g["utr5"] + g["cds"]})
    for i in rng.choice(N_GENES, 60, replace=False):
        g = genes[i]
        if g["utr5"] < 120:
            continue
        a = int(rng.integers(5, g["utr5"] - 90))
        orfs.append({"gene": g["id"], "tx": g["tx"], "class": "uORF", "start": a, "end": a + 3 * int(rng.integers(8, 28))})
    for i in rng.choice(N_GENES, 15, replace=False):
        g = genes[i]
        if g["utr3"] < 150:
            continue
        a = g["utr5"] + g["cds"] + int(rng.integers(10, 40))
        orfs.append({"gene": g["id"], "tx": g["tx"], "class": "dORF", "start": a, "end": a + 3 * int(rng.integers(10, 30))})
    for o in orfs:
        o["aa"] = (o["end"] - o["start"]) // 3 - 1
    return {"genes": genes, "orfs": orfs, "offsets": OFFSETS, "lengths": LENGTHS,
            "te_up": [g["id"] for g in genes if g["kind"] == "te_up"], "te_down": [g["id"] for g in genes if g["kind"] == "te_down"],
            "rna_up": [g["id"] for g in genes if g["kind"] == "rna_up"], "rna_down": [g["id"] for g in genes if g["kind"] == "rna_down"],
            "uorf_genes": sorted({o["gene"] for o in orfs if o["class"] == "uORF"})}


def counts(t: dict, seed: int = 18) -> tuple[list[str], np.ndarray]:
    """Counts for every library: RNA-seq reads per gene, Ribo-seq in-frame P-sites per gene."""
    rng = np.random.default_rng(seed)
    rows = samples()
    rna = np.array([g["rna"] for g in t["genes"]])
    te = np.array([g["te"] for g in t["genes"]])
    kind = np.array([g["kind"] for g in t["genes"]])
    out = np.zeros((len(rna), len(rows)))
    bio = {}
    for j, r in enumerate(rows):
        treated = r["condition"] == "treated"
        rfold = np.where(kind == "rna_up", RNA_FOLD, np.where(kind == "rna_down", 1 / RNA_FOLD, 1.0)) if treated else 1.0
        tfold = np.where(kind == "te_up", TE_FOLD, np.where(kind == "te_down", 1 / TE_FOLD, 1.0)) if treated else 1.0
        # Intent: the biological sample's own variation, shared by its Ribo-seq and RNA-seq libraries.
        shared = bio.setdefault(r["pair"], rng.lognormal(0, 0.25, len(rna)))
        depth = rng.uniform(0.75, 1.3)
        if r["type"] == "rnaseq":
            mu = rna * rfold * shared * depth * rng.lognormal(0, 0.08, len(rna))
        else:
            mu = 0.6 * rna * rfold * te * tfold * shared * depth * rng.lognormal(0, 0.12, len(rna))
        out[:, j] = rng.poisson(mu)
    return [r["sample"] for r in rows], out


def build(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    t = truth()
    names, mat = counts(t)
    d = root / ".demo_truth"
    d.mkdir(exist_ok=True)
    (d / "truth.json").write_text(json.dumps(t))
    with open(d / "counts.tsv", "w") as fh:
        fh.write("gene_id\tgene_name\t" + "\t".join(names) + "\n")
        for g, row in zip(t["genes"], mat):
            fh.write(f"{g['id']}\t{g['name']}\t" + "\t".join(f"{v:.0f}" for v in row) + "\n")
    fq = root / "fastq"
    fq.mkdir(exist_ok=True)
    for r in samples():
        for read in (("R1",) if r["type"] == "riboseq" else ("R1", "R2")):
            with gzip.open(fq / f"{r['sample']}_{read}.fastq.gz", "wt") as f:
                f.write("@demo\nACGTACGTACGTACGTACGTACGTACGTA\n+\nIIIIIIIIIIIIIIIIIIIIIIIIIIIII\n")
    g = root / "genome"
    g.mkdir(exist_ok=True)
    (g / "genome.fa").write_text(">demo1\nACGTACGT\n")
    (g / "genes.gtf").write_text('demo1\tdemo\tgene\t1\t8\t.\t+\t.\tgene_id "RIBODEMO00001"; gene_name "gene1";\n')
    return root
