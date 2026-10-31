"""Build the bulk RNA-seq demo data: six samples (three control, three treated) and a toy genome.

<root> = <demo cluster>/data/rna.bulk_de/
  fastq/                 placeholder paired reads, <sample>_R1.fastq.gz / _R2.fastq.gz
  genome/genome.fa, genome/genes.gtf   placeholder reference
  .demo_truth/gene_counts.tsv          the counts the demo pipeline 'produces' (nf-core salmon layout)
  .demo_truth/truth.json               which genes truly go up or down
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np

SAMPLES = [("control_1", "control"), ("control_2", "control"), ("control_3", "control"),
           ("treated_1", "treated"), ("treated_2", "treated"), ("treated_3", "treated")]
N_GENES, N_UP, N_DOWN = 3000, 120, 120


def build(root: Path, seed: int = 11) -> Path:
    rng = np.random.default_rng(seed)
    root.mkdir(parents=True, exist_ok=True)
    genes = [f"ENSDEMO{i:07d}" for i in range(N_GENES)]
    names = [f"gene{i + 1}" for i in range(N_GENES)]
    # Intent: realistic spread of expression, with a few genes truly changing 3-fold up or down when treated.
    base = np.exp(rng.normal(4.0, 1.8, N_GENES))
    fold = np.ones(N_GENES)
    up = rng.choice(N_GENES, N_UP, replace=False)
    down = rng.choice(np.setdiff1d(np.arange(N_GENES), up), N_DOWN, replace=False)
    fold[up] = 3.0
    fold[down] = 1 / 3.0
    disp = 0.05 + 1 / np.sqrt(base + 1)                # negative-binomial dispersion, larger for low counts
    cols = {}
    for s, cond in SAMPLES:
        depth = rng.uniform(0.7, 1.3)
        mu = base * depth * (fold if cond == "treated" else 1)
        p = 1 / (1 + mu * disp)
        cols[s] = rng.negative_binomial(1 / disp, p).astype(float)
    truth = root / ".demo_truth"; truth.mkdir(exist_ok=True)
    with open(truth / "gene_counts.tsv", "w") as fh:
        fh.write("gene_id\tgene_name\t" + "\t".join(s for s, _ in SAMPLES) + "\n")
        for i in range(N_GENES):
            fh.write(f"{genes[i]}\t{names[i]}\t" + "\t".join(f"{cols[s][i]:.3f}" for s, _ in SAMPLES) + "\n")
    (truth / "truth.json").write_text(json.dumps({"up": [genes[i] for i in up], "down": [genes[i] for i in down]}))
    fq = root / "fastq"; fq.mkdir(exist_ok=True)
    for s, _ in SAMPLES:
        for r in ("R1", "R2"):
            with gzip.open(fq / f"{s}_{r}.fastq.gz", "wt") as f:
                f.write("@demo\nACGT\n+\nIIII\n")
    g = root / "genome"; g.mkdir(exist_ok=True)
    (g / "genome.fa").write_text(">demo\nACGTACGT\n")
    (g / "genes.gtf").write_text('demo\tdemo\tgene\t1\t8\t.\t+\t.\tgene_id "ENSDEMO0000000"; gene_name "gene1";\n')
    return root
