"""Demo data for RNA abundance: what nf-core/rnaseq writes for nine samples (three tissues, three replicates each),
with groups of genes that rise in one tissue, so the patterns step has something real to find.

Writes <root>/results/star_salmon/salmon.merged.gene_{counts,tpm}.tsv and <root>/.demo_truth/patterns.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

TISSUES = ["oral", "aboral", "tentacle"]
N_GENES = 2000


def build(root: Path):
    rng = np.random.default_rng(11)
    samples = [f"{t}_{r}" for t in TISSUES for r in (1, 2, 3)]
    tissue = np.repeat(np.arange(len(TISSUES)), 3)
    base = rng.lognormal(mean=3.0, sigma=1.6, size=N_GENES)          # typical expression of each gene
    length = rng.integers(600, 6000, size=N_GENES)                   # transcript length, bp
    # Intent: three blocks of 60 genes, each four times higher in one tissue; the rest vary only by chance.
    pattern = np.full(N_GENES, -1)
    for k in range(len(TISSUES)):
        pattern[100 + 60 * k: 160 + 60 * k] = k
    fold = np.ones((N_GENES, len(samples)))
    for k in range(len(TISSUES)):
        rows = np.where(pattern == k)[0]
        fold[np.ix_(rows, np.where(tissue == k)[0])] = 4.0
    depth = rng.uniform(0.7, 1.3, size=len(samples))                 # library size differences
    mu = base[:, None] * fold * depth[None, :] * (length[:, None] / 2000)
    # Intent: biological variation between replicates (log-normal) on top of counting noise (Poisson).
    counts = rng.poisson(mu * rng.lognormal(0, 0.15, size=mu.shape)).astype(float)
    rate = counts / length[:, None]
    tpm = rate / rate.sum(axis=0, keepdims=True) * 1e6

    ids = [f"DEMO{g:05d}" for g in range(N_GENES)]
    names = [f"gene{g}" for g in range(N_GENES)]
    for k, t in enumerate(TISSUES):              # Intent: readable names for the planted genes, findable in the gene step.
        for j, g in enumerate(np.where(pattern == k)[0]):
            names[g] = f"{t}{j + 1}"
    out = root / "results" / "star_salmon"
    out.mkdir(parents=True, exist_ok=True)
    for fname, mat, fmt in (("salmon.merged.gene_counts.tsv", counts, "{:.0f}"), ("salmon.merged.gene_tpm.tsv", tpm, "{:.3f}")):
        lines = ["gene_id\tgene_name\t" + "\t".join(samples)]
        lines += [f"{ids[g]}\t{names[g]}\t" + "\t".join(fmt.format(v) for v in mat[g]) for g in range(N_GENES)]
        (out / fname).write_text("\n".join(lines) + "\n")
    truth = root / ".demo_truth"
    truth.mkdir(exist_ok=True)
    (truth / "patterns.json").write_text(json.dumps({t: [ids[g] for g in np.where(pattern == k)[0]] for k, t in enumerate(TISSUES)}))
