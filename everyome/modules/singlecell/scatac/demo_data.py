"""Demo data for single-cell ATAC-seq: a small made-up genome with genes, placeholder reads for two samples, and the
fragments a real run would make from them (kept in .demo_truth; the demo stage copies them into the run).

Four cell types, each with its own set of open promoters (marker genes named after the type), plus open chromatin
around every gene's start (so TSS enrichment is realistic) and background fragments across the genome.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np

CHROMS = {"chr1": 1_200_000, "chr2": 800_000}
TYPES = ["epidermis", "gastrodermis", "cnidocyte", "neuron"]
SAMPLES = {"polyp_A": ("control", "b1"), "polyp_B": ("treated", "b1")}
CELLS = 280            # per sample
N_MARKERS = 25         # genes per type


def genes():
    out = []
    for c, L in CHROMS.items():
        for i, s in enumerate(range(5_000, L - 10_000, 10_000)):
            out.append((c, s, s + 4_000, "+" if i % 2 == 0 else "-"))
    return out


def _gtf(path: Path, gs, names):
    with open(path, "w") as f:
        for (c, s, e, st), n in zip(gs, names):
            attrs = f'gene_id "{n}"; gene_name "{n}";'
            f.write(f"{c}\tdemo\tgene\t{s + 1}\t{e}\t.\t{st}\t.\t{attrs}\n")
            f.write(f'{c}\tdemo\ttranscript\t{s + 1}\t{e}\t.\t{st}\t.\t{attrs} transcript_id "{n}.1";\n')
            f.write(f'{c}\tdemo\texon\t{s + 1}\t{e}\t.\t{st}\t.\t{attrs} transcript_id "{n}.1";\n')


def build(root: Path):
    rng = np.random.default_rng(5)
    root.mkdir(parents=True, exist_ok=True)
    gs = genes()
    names = [f"g{i:04d}" for i in range(len(gs))]
    marker = {k: rng.choice(len(gs), N_MARKERS, replace=False) for k in range(len(TYPES))}
    for k, t in enumerate(TYPES):            # Intent: readable marker names, findable in the markers step.
        for j, g in enumerate(marker[k]):
            names[g] = f"{t[:4]}{j + 1}"
    ref = root / "reference"
    ref.mkdir(exist_ok=True)
    with open(ref / "genome.fa", "w") as f:
        for c, L in CHROMS.items():
            seq = "".join(rng.choice(list("ACGT"), L))
            f.write(f">{c}\n" + "\n".join(seq[i:i + 80] for i in range(0, L, 80)) + "\n")
    (ref / "genome.fa.fai").write_text("".join(f"{c}\t{L}\t0\t80\t81\n" for c, L in CHROMS.items()))
    _gtf(ref / "genes.gtf", gs, names)

    reads = root / "fastq"
    reads.mkdir(exist_ok=True)
    truth = root / ".demo_truth"
    truth.mkdir(exist_ok=True)
    tss = np.array([s if st == "+" else e for _, s, e, st in gs])
    chrom_of = np.array([c for c, *_ in gs])
    cell_types = {}
    for si, sample in enumerate(SAMPLES):
        for r in ("R1", "R2", "R3"):    # Intent: named as 10x delivers ATAC reads (R2 is the barcode read).
            with gzip.open(reads / f"{sample}_{r}.fastq.gz", "wt") as fh:
                fh.write(f"@{sample}_read1\nACGTACGTACGTACGTACGT\n+\nIIIIIIIIIIIIIIIIIIII\n")
        rows = []
        for cell in range(CELLS):
            k = cell % len(TYPES)
            bc = f"{'ACGT'[si]}{cell:07d}"
            cell_types[f"{sample}#{bc}"] = TYPES[k]
            n = int(rng.integers(1200, 3500))
            kind = rng.choice(3, size=n, p=[0.40, 0.25, 0.35])        # any TSS, own markers, background
            g = np.where(kind == 1, marker[k][rng.integers(N_MARKERS, size=n)], rng.integers(len(gs), size=n))
            chrom = np.where(kind == 2, rng.choice(list(CHROMS), size=n), chrom_of[g])
            start = np.where(kind == 2, rng.integers(0, min(CHROMS.values()) - 1_000, size=n),
                             tss[g] + rng.normal(0, 250, size=n).astype(int))
            # Intent: a realistic ladder: short fragments from open chromatin, then one and two nucleosomes, plus a tail.
            band = rng.choice(4, size=n, p=[0.52, 0.30, 0.13, 0.05])
            size = np.select([band == 0, band == 1, band == 2],
                             [rng.normal(65, 22, n), rng.normal(195, 26, n), rng.normal(385, 34, n)],
                             rng.exponential(250, n) + 100).astype(int).clip(25, 1000)
            start = np.maximum(start, 0)
            rows += [(c, int(s), int(s + z), bc) for c, s, z in zip(chrom, start, size)]
        rows.sort()
        with gzip.open(truth / f"{sample}.fragments.tsv.gz", "wt") as fh:
            fh.writelines(f"{c}\t{s}\t{e}\t{b}\t1\n" for c, s, e, b in rows)
    (truth / "cell_types.json").write_text(json.dumps(cell_types))
    (truth / "markers.json").write_text(json.dumps({t: [names[g] for g in marker[k]] for k, t in enumerate(TYPES)}))
