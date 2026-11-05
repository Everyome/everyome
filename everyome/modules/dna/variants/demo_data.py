"""Demo data for variant calling: a small made-up genome, reads for three wild-type and three mutant samples, and the
variants truly in them (kept in .demo_truth, for the demo stand-in and the tests).

<root>/genome/genome.fa
<root>/fastq/<sample>_R1.fastq.gz, _R2.fastq.gz   a few reads each (the demo pipeline does not read them)
<root>/.demo_truth/variants.json                   every true variant: position, alleles, genotype in each sample

Most variants are ordinary differences shared at random between the six animals. Ten, close together on chr2, are
homozygous in every mutant and absent from every wild type: what a mutation and the DNA linked to it look like.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np

CHROMS = {"chr1": 60_000, "chr2": 40_000}
SAMPLES = {"wt_1": "wt", "wt_2": "wt", "wt_3": "wt", "mut_1": "mut", "mut_2": "mut", "mut_3": "mut"}
TRANSITION = {"A": "G", "G": "A", "C": "T", "T": "C"}


def genome(seed: int = 70) -> dict[str, str]:
    rng = np.random.default_rng(seed)
    return {c: "".join(rng.choice(list("ACGT"), n)) for c, n in CHROMS.items()}


def truth(seed: int = 71) -> list[dict]:
    rng, g, out = np.random.default_rng(seed), genome(), []

    def alleles(c, pos):
        ref = g[c][pos - 1]
        if rng.random() < 0.85:
            # Intent: about two transitions per transversion, as in real genomes.
            alt = TRANSITION[ref] if rng.random() < 0.67 else str(rng.choice([b for b in "ACGT" if b not in (ref, TRANSITION[ref])]))
            return ref, alt
        n = int(rng.integers(1, 5))
        if rng.random() < 0.5:
            return ref, ref + "".join(rng.choice(list("ACGT"), n))         # insertion
        return g[c][pos - 1:pos + n], ref                                   # deletion

    for c, n in CHROMS.items():
        pos = int(rng.integers(200, 500))
        while pos < n - 200:
            if not (c == "chr2" and 18_000 <= pos <= 24_000):
                p = rng.uniform(0.1, 0.9)
                d = rng.binomial(2, p, len(SAMPLES))
                if d.sum() == 0:
                    d[int(rng.integers(len(SAMPLES)))] = 1
                ref, alt = alleles(c, pos)
                out.append({"chrom": c, "pos": pos, "ref": ref, "alt": alt, "kind": "shared", "gt": dict(zip(SAMPLES, map(int, d)))})
            pos += int(rng.integers(150, 450))
    for pos in sorted(rng.choice(np.arange(18_000, 24_000), 10, replace=False)):
        ref, alt = g["chr2"][pos - 1], TRANSITION[g["chr2"][pos - 1]]
        out.append({"chrom": "chr2", "pos": int(pos), "ref": ref, "alt": alt, "kind": "mutant",
                    "gt": {s: 2 if grp == "mut" else 0 for s, grp in SAMPLES.items()}})
    return sorted(out, key=lambda v: (v["chrom"], v["pos"]))


def build(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    (root / "genome").mkdir(exist_ok=True)
    g = genome()
    with open(root / "genome" / "genome.fa", "w") as fh:
        for c, s in g.items():
            fh.write(f">{c}\n" + "\n".join(s[i:i + 80] for i in range(0, len(s), 80)) + "\n")
    (root / "fastq").mkdir(exist_ok=True)
    rng = np.random.default_rng(72)
    for s in SAMPLES:
        for r in (1, 2):
            with gzip.GzipFile(root / "fastq" / f"{s}_R{r}.fastq.gz", "wb", mtime=0) as fh:
                for k in range(20):
                    c = str(rng.choice(list(CHROMS)))
                    i = int(rng.integers(0, CHROMS[c] - 150))
                    fh.write(f"@{s}.{k}/{r}\n{g[c][i:i + 150]}\n+\n{'I' * 150}\n".encode())
    t = root / ".demo_truth"
    t.mkdir(exist_ok=True)
    (t / "variants.json").write_text(json.dumps(truth()))
