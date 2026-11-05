"""Demo data for multiome (RNA and ATAC from the same cells): what Cell Ranger ARC writes for two samples, the joint
cell-by-feature matrix ('outs/filtered_feature_bc_matrix', genes and peaks together).

Four cell types, built so that only both measurements together tell all four apart: two differ only in their RNA,
two only in their open chromatin. .demo_truth/cell_types.json gives every cell's true type.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import scipy.io as sio
import scipy.sparse as sp

TYPES = ["epidermis", "gastrodermis", "cnidocyte", "neuron"]
SAMPLES = {"polyp_A": "control", "polyp_B": "treated"}
CELLS = 260
N_GENES, N_PEAKS = 400, 1200
MITO = ["mt-co1", "mt-nd1", "mt-cytb"]


def build(root: Path):
    rng = np.random.default_rng(21)
    genes = [f"g{i:04d}" for i in range(N_GENES - len(MITO))] + MITO
    # Intent: RNA separates epidermis | gastrodermis | (cnidocyte + neuron); chromatin separates cnidocyte | neuron |
    # (epidermis + gastrodermis). Only both together tell all four apart.
    gprof = np.tile(rng.lognormal(0, 1.0, size=N_GENES), (len(TYPES), 1))
    pprof = np.tile(rng.lognormal(-0.5, 0.6, size=N_PEAKS), (len(TYPES), 1))
    rna_markers = {"epid": ([0], range(0, 25)), "gast": ([1], range(25, 50)), "cnne": ([2, 3], range(50, 75))}
    for prefix, (types, rows) in rna_markers.items():
        gprof[np.ix_(types, list(rows))] *= 8
        for j, g in enumerate(rows):
            genes[g] = f"{prefix}{j + 1}"
    for t, rows in {2: range(0, 80), 3: range(80, 160)}.items():
        pprof[t, list(rows)] *= 10
    peaks = []
    for i in range(N_PEAKS):
        c = "chr1" if i < N_PEAKS // 2 else "chr2"
        s = 10_000 + (i % (N_PEAKS // 2)) * 1_500
        peaks.append(f"{c}:{s}-{s + 500}")
    cell_types = {}
    for si, (sample, cond) in enumerate(SAMPLES.items()):
        out = root / sample / "outs" / "filtered_feature_bc_matrix"
        out.mkdir(parents=True, exist_ok=True)
        types = np.arange(CELLS) % len(TYPES)
        bcs = ["".join(rng.choice(list("ACGT"), 16)) + "-1" for _ in range(CELLS)]
        lib_r = np.exp(rng.normal(np.log(2500), 0.3, CELLS))
        lib_a = np.exp(rng.normal(np.log(4000), 0.3, CELLS))
        gp = gprof[types] / gprof[types].sum(1, keepdims=True)
        mito = np.array([genes.index(m) for m in MITO])
        gp[:, mito] *= 2
        gp /= gp.sum(1, keepdims=True)
        pp = pprof[types] / pprof[types].sum(1, keepdims=True)
        X = sp.hstack([sp.csr_matrix(rng.poisson(gp * lib_r[:, None])), sp.csr_matrix(rng.poisson(pp * lib_a[:, None]))]).tocsr()
        with gzip.open(out / "matrix.mtx.gz", "wb") as fh:
            sio.mmwrite(fh, X.T.tocoo().astype(np.int64))    # features in rows, cells in columns, as 10x writes it
        with gzip.open(out / "barcodes.tsv.gz", "wt") as fh:
            fh.write("".join(b + "\n" for b in bcs))
        with gzip.open(out / "features.tsv.gz", "wt") as fh:
            fh.write("".join(f"DEMO{i:05d}\t{g}\tGene Expression\tchr1\t{100 * i}\t{100 * i + 90}\n" for i, g in enumerate(genes)))
            fh.write("".join(f"{p}\t{p}\tPeaks\t{p.split(':')[0]}\t{p.split(':')[1].split('-')[0]}\t{p.split('-')[1]}\n" for p in peaks))
        cell_types.update({f"{sample}#{b}": TYPES[t] for b, t in zip(bcs, types)})
    truth = root / ".demo_truth"
    truth.mkdir(parents=True, exist_ok=True)
    (truth / "cell_types.json").write_text(json.dumps(cell_types))
