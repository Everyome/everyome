"""Stand-ins for cell2location on the demo cluster: they write the files the real stages write. The reference signatures
are the reference's own mean expression per cell type; the spot abundances are the demo's true make-up of each spot
with a little estimation noise (see demo_data.py)."""
from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
import pandas as pd


def _pause():
    time.sleep(float(os.environ.get("EVERYOME_DEMO_PAUSE", "1")) / 2)


def _curve(path: Path, rounds: int, start: float, end: float, seed: int):
    rng = np.random.default_rng(seed)
    r = np.linspace(1, rounds, 200).round().astype(int)
    loss = end + (start - end) * np.exp(-r / (rounds / 8)) + rng.normal(0, (start - end) * 0.004, len(r))
    pd.DataFrame({"round": r, "loss": loss.round(1)}).to_csv(path, index=False)


def reference(params: dict, out: Path) -> None:
    import anndata as ad
    _pause()
    a = ad.read_h5ad(params["reference"])
    labels = params.get("labels_key") or "cell_type"
    if labels not in a.obs:
        raise ValueError(f"The reference has no column '{labels}' in its cell table. Its columns: {', '.join(map(str, a.obs.columns))}.")
    X = a.X.toarray() if hasattr(a.X, "toarray") else np.asarray(a.X)
    types = sorted(a.obs[labels].astype(str).unique())
    sig = pd.DataFrame({t: X[(a.obs[labels].astype(str) == t).values].mean(0) for t in types}, index=a.var_names)
    sig.round(4).to_csv(out / "signatures.csv", index_label="gene")
    _curve(out / "training.csv", int(params.get("reference_epochs") or 250), 9.0e6, 2.1e6, 1)
    print(f"[demo] cell2location reference stand-in: {len(types)} cell types", flush=True)


def map_spots(params: dict, out: Path) -> None:
    _pause()
    truth = pd.read_csv(Path(params["reference"]).parent / ".demo_truth" / "spots.csv")
    names = [r["sample"] for r in params["samples"]]
    truth = truth[truth["sample"].isin(names)].reset_index(drop=True)
    types = [c for c in truth.columns if c not in ("sample", "barcode", "cells")]
    rng = np.random.default_rng(2)
    mean = truth[types].to_numpy() * truth[["cells"]].to_numpy() * np.exp(rng.normal(0, 0.15, (len(truth), len(types))))
    # Intent: a type that is truly absent still gets a small estimate, as a real model gives.
    mean += rng.gamma(1, 0.03, mean.shape)
    for kind, v in (("mean", mean), ("q05", mean * 0.72)):
        df = pd.DataFrame(v, columns=types)
        df.insert(0, "barcode", truth["barcode"])
        df.insert(0, "sample", truth["sample"])
        df.to_csv(out / f"abundance_{kind}.csv", index=False, float_format="%.4f")
    _curve(out / "training.csv", int(params.get("mapping_epochs") or 30000), 4.0e7, 1.1e7, 2)
    print(f"[demo] cell2location mapping stand-in: {len(truth)} spots, {len(types)} cell types", flush=True)
