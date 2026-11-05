"""Demo data for genome annotation: a small made-up genome (two chromosomes) and the gene models a predictor would
find in it (kept in .demo_truth, for the demo stand-ins and the tests).

<root>/genome.fa
<root>/.demo_truth/genes.json   per gene: chromosome, strand, exons [(start, end)], CDS phase-free, a protein
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

CHROMS = {"chr1": 160_000, "chr2": 120_000}
AA = list("ACDEFGHIKLMNPQRSTVWY")


def truth(seed: int = 61) -> list[dict]:
    rng = np.random.default_rng(seed)
    genes, k = [], 0
    for c, n in CHROMS.items():
        pos = 3_000
        while pos < n - 12_000:
            k += 1
            nex = int(rng.choice([1, 2, 3, 4, 5, 6, 8], p=[.12, .14, .18, .18, .16, .12, .10]))
            exons, p = [], pos
            for e in range(nex):
                L = int(rng.integers(90, 420))
                exons.append((p, p + L - 1))
                p += L + int(rng.integers(80, 1500))
            cds_len = sum(b - a + 1 for a, b in exons) // 3
            genes.append({"id": f"demo_{c}_{k:05d}", "chrom": c, "strand": "+" if rng.random() < .5 else "-", "exons": exons,
                          "protein": "M" + "".join(rng.choice(AA, max(30, cds_len - 1)))})
            pos = p + int(rng.integers(1_500, 9_000))
    return genes


def build(root: Path):
    rng = np.random.default_rng(60)
    root.mkdir(parents=True, exist_ok=True)
    with open(root / "genome.fa", "w") as fh:
        for c, n in CHROMS.items():
            s = "".join(rng.choice(list("ACGT"), n))
            fh.write(f">{c}\n" + "\n".join(s[i:i + 80] for i in range(0, n, 80)) + "\n")
    t = root / ".demo_truth"
    t.mkdir(exist_ok=True)
    (t / "genes.json").write_text(json.dumps(truth()))
