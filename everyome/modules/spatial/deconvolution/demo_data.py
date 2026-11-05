"""Demo data for cell types in spots: the Visium demo's two toy skin sections, a single-cell reference of the same five
cell types, and the true make-up of every spot (kept in .demo_truth, for the demo stand-in and the tests).

<root>/visium/skin_control/outs/, skin_treated/outs/   Space Ranger layout (from the Visium demo's builder)
<root>/reference.h5ad                                   1,250 cells with raw counts and obs['cell_type']
<root>/.demo_truth/spots.csv                            per spot: section, barcode, cells under it, share of each type

Each region of the toy skin is made of one cell type, and spots near a boundary mix the neighbouring types, so the
shares are known exactly. The treated section has immune cells; the control section has none.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from everyome.modules.spatial.visium.demo_data import MITO, N_OTHER, REGIONS, SCALE, _region, _sample

TYPES = {"Epidermis": "Keratinocytes", "Dermis": "Fibroblasts", "Hair follicle": "Follicle cells", "Muscle": "Smooth muscle cells",
         "Immune infiltrate": "Immune cells"}


def profiles(seed: int = 9):
    """Genes and each cell type's mean expression (as the Visium demo makes them)."""
    rng = np.random.default_rng(seed)
    named = [g for gs, _ in REGIONS.values() for g in gs]
    genes = named + MITO + [f"GENE{i:04d}" for i in range(N_OTHER)]
    base = np.exp(rng.normal(0, 1.0, len(genes))) * 0.3
    base[[genes.index(g) for g in MITO]] = 5
    prof = np.tile(base, (len(REGIONS), 1))
    for k, (gs, _) in enumerate(REGIONS.values()):
        prof[k, [genes.index(g) for g in gs]] *= 40
    return genes, prof


def _shares(outs, treated: bool) -> pd.DataFrame:
    """Each in-tissue spot's true share of each cell type, from its position (the same map the section was drawn from)."""
    pos = pd.read_csv(outs / "spatial" / "tissue_positions.csv")
    x, y = pos["pxl_col_in_fullres"].to_numpy() * SCALE, pos["pxl_row_in_fullres"].to_numpy() * SCALE
    xn, yn = (x - x.min()) / np.ptp(x), (y - y.min()) / np.ptp(y)
    w = _region(xn, yn, treated)
    df = pd.DataFrame(w, columns=list(TYPES.values()))
    df.insert(0, "barcode", pos["barcode"].values)
    return df[pos["in_tissue"].to_numpy() == 1].reset_index(drop=True)


def build(root):
    import anndata as ad
    import scipy.sparse as sp
    root.mkdir(parents=True, exist_ok=True)
    genes, prof = profiles()
    rows = []
    for name, treated, depth, seed in (("skin_control", False, 4000, 10), ("skin_treated", True, 2500, 11)):
        outs = root / "visium" / name / "outs"
        _sample(outs, name, treated, depth, seed, genes, prof)
        s = _shares(outs, treated)
        s.insert(0, "sample", name)
        s.insert(2, "cells", np.random.default_rng(seed + 100).poisson(6, len(s)) + 2)
        rows.append(s)
    t = root / ".demo_truth"
    t.mkdir(exist_ok=True)
    pd.concat(rows).to_csv(t / "spots.csv", index=False)
    # The reference: 250 cells of each type, each a noisy draw from its type's profile.
    rng = np.random.default_rng(12)
    X, labels = [], []
    for k, name in enumerate(TYPES.values()):
        p = prof[k] * rng.gamma(5, 1 / 5, (250, len(genes)))
        p /= p.sum(1, keepdims=True)
        lib = np.exp(rng.normal(np.log(3000), 0.4, 250))
        X.append(rng.poisson(p * lib[:, None]))
        labels += [name] * 250
    a = ad.AnnData(sp.csr_matrix(np.vstack(X).astype(np.float32)),
                   obs=pd.DataFrame({"cell_type": pd.Categorical(labels)}, index=[f"cell{i:05d}" for i in range(len(labels))]),
                   var=pd.DataFrame(index=genes))
    a.write_h5ad(root / "reference.h5ad")
