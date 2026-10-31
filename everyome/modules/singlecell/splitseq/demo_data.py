"""Build the SPLiT-seq demo data (carried over from the SPLiTscape demo cluster).

<root> = <demo cluster>/data/singlecell.splitseq/
  raw/                 placeholder FASTQs for 2 sublibraries x 2 runs
  atlas_10x/           a toy reference atlas (10x format)
  sheets/              round-1 barcode sheet (well -> condition)
  refs/                placeholder genome, STAR index, toolbox, pairfq
  refs/annotation.tsv  toy DIAMOND-style gene annotation
  .demo_truth/         the matrices the demo stage 08 'produces'
"""
from __future__ import annotations

import gzip
import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.io as sio
import scipy.sparse as sp

TYPES = ["Stem cells", "Progenitors", "Neurons", "Gland cells", "Epithelium A", "Epithelium B", "Muscle", "Nematocytes"]
N_GENES = 3000
MARKER_NAMES = ["PIWI-like protein 1", "Myc-like transcription factor", "ELAV-like protein", "Mucin-like protein",
                "Keratin-like protein", "Tight junction protein", "Myosin heavy chain", "Nematocyst outer wall antigen"]


def _bc(r, n):
    return "".join(r.choice("ACGT") for _ in range(n))


def _profiles(rng):
    base = np.exp(rng.normal(0, 1.0, N_GENES)) * 0.4
    markers = [list(range(20 + t * 25, 20 + t * 25 + 25)) for t in range(len(TYPES))]
    markers[5] = markers[4][:15] + markers[5][:10]          # epithelia A and B overlap
    prof = np.tile(base, (len(TYPES), 1))
    for t, gs in enumerate(markers):
        prof[t, gs] *= 10
    return prof, markers


def _cells(rng, prof, n, comp, lib_mean, batch_shift):
    types = rng.choice(len(TYPES), size=n, p=np.array(comp) / sum(comp))
    pos = rng.random(n)
    P = prof[types].copy()
    prog = types == 1                                         # progenitors: stem -> neuron continuum
    P[prog] = (1 - pos[prog, None]) * prof[0] + pos[prog, None] * prof[2] + prof[1] * 0.6
    P *= batch_shift
    P /= P.sum(1, keepdims=True)
    lib = np.exp(np.log(lib_mean) + rng.normal(0, 0.35, n))
    return rng.poisson(P * lib[:, None]), types


def build(root: Path, seed: int = 7) -> Path:
    rng, r = np.random.default_rng(seed), random.Random(seed)
    root.mkdir(parents=True, exist_ok=True)
    prof, markers = _profiles(rng)
    genes = [f"LOC1306{i:05d}" for i in range(N_GENES)]

    # --- reference atlas: 3 libraries, control animals, its own batch ---------
    atlas_X, atlas_ids = [], []
    for k, lib in enumerate(["lib_02_1", "lib_02_2", "lib_03_1"]):
        shift = np.exp(rng.normal(0, 0.12, N_GENES))
        X, _ = _cells(rng, prof, 1400, [12, 14, 12, 12, 16, 14, 12, 8], 900, shift)
        atlas_X.append(X)
        atlas_ids += [f"atlas_{lib}_{_bc(r, 24)}" for _ in range(len(X))]
    A = sp.csr_matrix(np.vstack(atlas_X).T.astype(np.int32))
    adir = root / "atlas_10x"; adir.mkdir(parents=True, exist_ok=True)
    with gzip.open(adir / "matrix.mtx.gz", "wb") as f: sio.mmwrite(f, A)
    with gzip.open(adir / "features.tsv.gz", "wt") as f: f.writelines(f"{g}\t{g}\tGene Expression\n" for g in genes)
    with gzip.open(adir / "barcodes.tsv.gz", "wt") as f: f.writelines(c + "\n" for c in atlas_ids)

    # --- experiment: 2 sublibraries, 48 wells -> control / treated ------------
    wells = [_bc(r, 8) for _ in range(48)]
    cond = ["control"] * 24 + ["treated"] * 24
    sdir = root / "sheets"; sdir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({0: wells, 1: cond}).to_excel(sdir / "round1_condition.xlsx", header=False, index=False)
    truth = root / ".demo_truth"; truth.mkdir(exist_ok=True)
    exp_shift = np.exp(rng.normal(0, 0.2, N_GENES))
    response = list(range(260, 272))
    summary = []
    for s, sub in enumerate(["sublib_1", "sublib_2"]):
        cols, mats = [], []
        for c, comp in [("control", [12, 14, 12, 12, 16, 14, 12, 8]), ("treated", [10, 24, 10, 10, 14, 10, 10, 12])]:
            shift = exp_shift.copy()
            if c == "treated":
                shift[response] *= 4
            X, _ = _cells(rng, prof, 520, comp, 700, shift)
            idx = [i for i, w in enumerate(cond) if w == c]
            cols += [wells[r.choice(idx)] + _bc(r, 16) for _ in range(len(X))]
            mats.append(X)
        X = np.vstack(mats)
        # Intent: realistic contaminants — 5% doublets, 4% near-empty barcodes.
        n = len(X)
        dbl = X[rng.integers(0, n, n // 20)] + X[rng.integers(0, n, n // 20)]
        low = rng.poisson(np.tile(prof.mean(0) / prof.mean(0).sum() * 80, (n // 25, 1)))
        X = np.vstack([X, dbl, low]); cols += [wells[r.randrange(48)] + _bc(r, 16) for _ in range(len(dbl) + len(low))]
        keep = (X > 0).sum(1) >= 50
        X, cols = X[keep], [c for c, k in zip(cols, keep) if k]
        df = pd.DataFrame(X.T, index=pd.Index(genes, name="GENE"), columns=cols)
        df = df.loc[df.sum(axis=1) > 0]
        df.to_csv(truth / f"{sub}_G50_matrix.txt.gz", sep="\t", compression="gzip")
        summary.append({"sublib": sub, "cells": X.shape[0], "umis": int(X.sum())})

    # --- placeholders so the folder browser looks like a real project --------
    raw = root / "raw"; raw.mkdir(parents=True, exist_ok=True)
    for sub in ["sublib_1", "sublib_2"]:
        for run in ["run_1", "run_2"]:
            for rd in ["R1", "R2"]:
                with gzip.open(raw / f"{sub}_{run}_{rd}.fq.gz", "wt") as f:
                    f.write("@demo\nACGT\n+\nIIII\n")
    refs = root / "refs"; (refs / "star_index").mkdir(parents=True, exist_ok=True)
    (refs / "genome.fasta").write_text(">demo\nACGT\n")
    (refs / "star_index" / "SA").write_text("demo")
    (refs / "splitseq_toolbox").mkdir(exist_ok=True)
    (refs / "splitseq_toolbox" / "Split-seq_pipeline.sh").write_text("#!/bin/bash\necho demo\n")
    (refs / "pairfq_lite").write_text("#!/bin/bash\necho demo\n")
    rows = []
    for t, gs in enumerate(markers):
        for k, g in enumerate(gs):
            # Intent: every marker gets a readable name; a few are uninformative, as in real tables.
            hit = f"{MARKER_NAMES[t]} [Hydra vulgaris]" if k == 0 else (f"hypothetical protein {k}" if k % 5 == 4 else f"{MARKER_NAMES[t]} family member {k} [Hydra vulgaris]")
            rows.append(["q", genes[g], 90, 300, 1e-50, 400, hit, f"{MARKER_NAMES[t]}-like"])
    for g in range(len(TYPES) * 25 + 20, N_GENES, 7):
        rows.append(["q", genes[g], 60, 200, 1e-10, 100, r.choice(["uncharacterized protein", "actin [Nematostella vectensis]", "ribosomal protein L7"]), "uncharacterized protein"])
    pd.DataFrame(rows, columns=["qseqid", "gene_id", "pident", "length", "evalue", "bitscore", "match", "ncbi_name"]) \
      .to_csv(refs / "annotation.tsv", sep="\t", index=False)
    (truth / "info.json").write_text(json.dumps({"summary": summary, "markers": {TYPES[t]: genes[gs[0]] for t, gs in enumerate(markers)}}))
    return root


if __name__ == "__main__":
    import sys
    print(build(Path(sys.argv[1])))
