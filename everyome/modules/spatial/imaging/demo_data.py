"""Demo data for imaging spatial: two Xenium-style sections ('outs' with cell_feature_matrix/ and cells.csv.gz), a
120-gene panel with negative control probes, and four cell types arranged in rings (outer epidermis, then gastrodermis,
then a muscle layer, with a core of neurons), plus an immune patch only in the treated section.

.demo_truth/cell_types.json gives every cell's true type; markers.json each type's planted marker genes.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import scipy.io as sio
import scipy.sparse as sp

TYPES = ["epidermis", "gastrodermis", "muscle", "neuron", "immune"]
SECTIONS = {"section_control": False, "section_treated": True}
N_GENES, N_MARKERS = 120, 12
CONTROLS = [f"NegControlProbe_{i:02d}" for i in range(6)]


def build(root: Path):
    rng = np.random.default_rng(31)
    genes = [f"p{i:03d}" for i in range(N_GENES)]
    base = rng.lognormal(-1.0, 0.8, size=N_GENES)
    prof = np.tile(base, (len(TYPES), 1))
    markers = {}
    for k, t in enumerate(TYPES):
        rows = list(range(k * N_MARKERS, (k + 1) * N_MARKERS))
        prof[k, rows] *= 15
        for j, g in enumerate(rows):
            genes[g] = f"{t[:4]}{j + 1}"
        markers[t] = [genes[g] for g in rows]
    truth = {}
    for name, treated in SECTIONS.items():
        n = 3000
        # Intent: cells scattered over a disc of radius 1000 µm, at roughly even density.
        r = 1000 * np.sqrt(rng.random(n))
        th = rng.random(n) * 2 * np.pi
        x, y = 1200 + r * np.cos(th), 1200 + r * np.sin(th)
        t = np.select([r > 820, r > 560, r > 330], [0, 1, 2], 3)
        if treated:                                       # an immune patch in one sector of the gastrodermis
            patch = (np.hypot(x - 1750, y - 1200) < 180)
            t = np.where(patch, 4, t)
        lib = np.exp(rng.normal(np.log(120), 0.35, n))
        P = prof[t] / prof[t].sum(1, keepdims=True)
        X = rng.poisson(P * lib[:, None])
        Xc = rng.poisson(0.05, size=(n, len(CONTROLS)))   # control probes: background only
        M = sp.csr_matrix(np.hstack([X, Xc]))
        out = root / name / "outs"
        m = out / "cell_feature_matrix"
        m.mkdir(parents=True, exist_ok=True)
        ids = [f"{name[8:11]}{i:05d}-1" for i in range(n)]
        with gzip.open(m / "matrix.mtx.gz", "wb") as fh:
            sio.mmwrite(fh, M.T.tocoo().astype(np.int64))
        with gzip.open(m / "barcodes.tsv.gz", "wt") as fh:
            fh.write("".join(i + "\n" for i in ids))
        with gzip.open(m / "features.tsv.gz", "wt") as fh:
            fh.write("".join(f"DEMO{j:04d}\t{g}\tGene Expression\n" for j, g in enumerate(genes)))
            fh.write("".join(f"{c}\t{c}\tNegative Control Probe\n" for c in CONTROLS))
        with gzip.open(out / "cells.csv.gz", "wt") as fh:
            fh.write("cell_id,x_centroid,y_centroid,transcript_counts,cell_area\n")
            fh.write("".join(f"{i},{a:.2f},{b:.2f},{int(c)},{rng.uniform(40, 90):.1f}\n" for i, a, b, c in zip(ids, x, y, X.sum(1))))
        (out / "experiment.xenium").write_text(json.dumps({"run_name": name, "panel_name": "Everyome demo panel"}))
        truth.update({f"{name}_{i}": TYPES[k] for i, k in zip(ids, t)})
    d = root / ".demo_truth"
    d.mkdir(parents=True, exist_ok=True)
    (d / "cell_types.json").write_text(json.dumps(truth))
    (d / "markers.json").write_text(json.dumps(markers))
