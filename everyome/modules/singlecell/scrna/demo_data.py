"""Build the single-cell RNA-seq demo data: four 10x-style samples of a toy blood-like tissue.

<root> = <demo cluster>/data/singlecell.scrna/
  fastq/         placeholder reads, 10x names (<sample>_S1_L001_R1_001.fastq.gz, _R2_)
  genome/        placeholder genome and GTF
  .demo_truth/   the matrices the demo pipeline 'produces' (nf-core/scrnaseq 4.x layout and naming):
                 combined_raw_matrix.h5ad (every barcode) and combined_cellbender_filter_matrix.h5ad (cells only),
                 plus truth.json (each cell's true type, which cells are damaged or doublets)

The truth is known, so tests can check that the session finds the cell types:
six types with well-known markers, interferon-responding monocytes only in treated
samples, a batch effect between the two days, 5% damaged cells (high mitochondrial
share), 4% doublets and, in the raw matrix, empty droplets.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import scipy.sparse as sp

SAMPLES = [("ctrl_1", "control", "day1"), ("ctrl_2", "control", "day2"), ("treated_1", "treated", "day1"), ("treated_2", "treated", "day2")]
TYPES = {   # name: (markers, share in control, share in treated)
    "T cells": (["CD3E", "CD3D", "IL7R", "TRAC", "LTB"], .38, .34),
    "B cells": (["CD79A", "MS4A1", "CD79B", "BANK1", "IGHM"], .18, .16),
    "NK cells": (["NKG7", "GNLY", "PRF1", "KLRD1", "GZMB"], .12, .10),
    "Monocytes": (["LYZ", "CD14", "S100A8", "S100A9", "FCN1"], .24, .14),
    "Dendritic cells": (["FCER1A", "CLEC10A", "CD1C", "HLA-DQA1", "CST3"], .08, .06),
    "IFN-responding monocytes": (["ISG15", "IFIT1", "IFIT3", "MX1", "RSAD2"], 0.0, .20),
}
N_OTHER, CELLS, EMPTY = 1500, 650, 1200
MITO = [f"MT-{g}" for g in ["ND1", "ND2", "CO1", "CO2", "ATP8", "ATP6", "CO3", "ND3", "ND4L", "ND4", "ND5", "ND6", "CYB"]]


def _profiles(rng, genes):
    base = np.exp(rng.normal(0, 1.1, len(genes))) * 0.3
    idx = {g: i for i, g in enumerate(genes)}
    base[[idx[g] for g in MITO]] = 6.0                     # healthy cells: a few percent mitochondrial
    prof = {}
    for t, (markers, _, _) in TYPES.items():
        p = base.copy()
        p[[idx[g] for g in markers]] *= 25
        if t == "IFN-responding monocytes":                 # still monocytes, plus the interferon response
            p[[idx[g] for g in TYPES["Monocytes"][0]]] *= 18
        prof[t] = p
    return prof, idx


def build(root: Path, seed: int = 5) -> Path:
    rng = np.random.default_rng(seed)
    root.mkdir(parents=True, exist_ok=True)
    named = [g for m, _, _ in TYPES.values() for g in m]
    genes = named + MITO + [f"GENE{i:04d}" for i in range(N_OTHER)]
    prof, idx = _profiles(rng, genes)
    batch_shift = {"day1": np.ones(len(genes)), "day2": np.exp(rng.normal(0, .1, len(genes)))}   # a moderate batch effect Harmony can correct
    mito_cols = [idx[g] for g in MITO]
    types = list(TYPES)
    blocks, obs = [], []
    for sample, cond, day in SAMPLES:
        share = np.array([TYPES[t][1 if cond == "control" else 2] for t in types])
        t_idx = rng.choice(len(types), CELLS, p=share / share.sum())
        lib = np.exp(rng.normal(np.log(3000), .4, CELLS))
        P = np.array([prof[types[k]] for k in t_idx]) * batch_shift[day]
        kind = np.array(["cell"] * CELLS, dtype=object)
        dbl = rng.random(CELLS) < .04                        # doublets: two cells' RNA, about twice the molecules
        P[dbl] += np.array([prof[types[k]] for k in rng.choice(len(types), dbl.sum())]) * batch_shift[day]
        lib[dbl] *= 1.9
        kind[dbl] = "doublet"
        dmg = (~dbl) & (rng.random(CELLS) < .05)            # damaged: cytoplasmic RNA lost, mitochondrial RNA left
        P[np.ix_(dmg, mito_cols)] *= 14
        lib[dmg] *= .35
        kind[dmg] = "damaged"
        P /= P.sum(1, keepdims=True)
        X = rng.poisson(P * lib[:, None])
        # Empty droplets: a little ambient RNA (the average profile), far fewer molecules.
        amb = P.mean(0)
        E = rng.poisson(amb * np.exp(rng.normal(np.log(25), .6, EMPTY))[:, None])
        blocks += [sp.csr_matrix(X, dtype=np.float32), sp.csr_matrix(E, dtype=np.float32)]
        bc = lambda n: ["".join(rng.choice(list("ACGT"), 16)) for _ in range(n)]
        obs += [{"barcode": f"{sample}_{b}", "sample": sample, "truth": types[k], "kind": kd} for b, k, kd in zip(bc(CELLS), t_idx, kind)]
        obs += [{"barcode": f"{sample}_{b}", "sample": sample, "truth": "", "kind": "empty"} for b in bc(EMPTY)]
    o = pd.DataFrame(obs).set_index("barcode")
    var = pd.DataFrame({"gene_symbols": genes}, index=[f"ENSDEMOG{i:07d}" for i in range(len(genes))])
    raw = ad.AnnData(X=sp.vstack(blocks).tocsr(), obs=o[["sample"]].astype("category"), var=var)
    truth = root / ".demo_truth"; truth.mkdir(exist_ok=True)
    raw.write_h5ad(truth / "combined_raw_matrix.h5ad")
    cells = (o["kind"] != "empty").values
    raw[cells].copy().write_h5ad(truth / "combined_cellbender_filter_matrix.h5ad")
    (truth / "truth.json").write_text(json.dumps({"cells": o[cells][["truth", "kind"]].to_dict(orient="index")}))
    fq = root / "fastq"; fq.mkdir(exist_ok=True)
    for i, (s, _, _) in enumerate(SAMPLES):
        for r in ("R1", "R2"):
            with gzip.open(fq / f"{s}_S{i + 1}_L001_{r}_001.fastq.gz", "wt") as f:
                f.write("@demo\nACGT\n+\nIIII\n")
    g = root / "genome"; g.mkdir(exist_ok=True)
    (g / "genome.fa").write_text(">demo\nACGTACGT\n")
    (g / "genes.gtf").write_text('demo\tdemo\tgene\t1\t8\t.\t+\t.\tgene_id "ENSDEMOG0000000"; gene_name "CD3E";\n')
    return root
