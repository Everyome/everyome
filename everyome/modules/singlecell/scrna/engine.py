"""Live session for single-cell RNA-seq: load the matrix nf-core/scrnaseq made, then the shared single-cell steps.

The first step reads one of the pipeline's combined matrices (by default the one
with empty droplets and background removed by CellBender), uses gene symbols as
names, and adds each sample's condition and batch from the samples table.
Filtering (including the mitochondrial share), clustering, markers, naming and
export are shared with other single-cell modules (../cells.py).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import scanpy as sc
import scipy.sparse as spm

from ..cells import CellsEngine
from .helpers import matrix_paths

SYMBOLS = ("gene_symbols", "gene_symbol", "gene_names", "gene_name", "feature_name", "Symbol")


class Engine(CellsEngine):
    API = ("matrices", "load", "cells_per_sample") + CellsEngine.SHARED_API
    REPLAY = ("load",) + CellsEngine.SHARED_REPLAY
    STATUS_KEYS = ("loaded_from", "qc", "cluster_params")

    def _mito_pattern(self):
        return self.params.get("mito_genes") or ""

    # ---------------------------------------------------------------- load
    def matrices(self):
        return [{"kind": k, "path": p, "description": d, "exists": (self.dir / p).exists()} for k, p, d in matrix_paths(self.params)]

    def load(self, kind: str = ""):
        found = [m for m in self.matrices() if m["exists"]]
        if not found:
            raise FileNotFoundError("No cell-by-gene matrix from nf-core/scrnaseq was found in this run's results.")
        pick = next((m for m in found if m["kind"] == kind), None) if kind else found[0]
        if pick is None:
            raise ValueError(f"The pipeline did not make a {kind} matrix for this run.")
        return self._background(self._load, pick)

    def _load(self, pick):
        self._prog(15, "Reading the matrix")
        a = sc.read_h5ad(self.dir / pick["path"])
        a.X = spm.csr_matrix(a.X, dtype=np.float32)
        # Intent: people search and read gene symbols (CD3E), not ids (ENSG...); keep the ids alongside.
        col = next((c for c in SYMBOLS if c in a.var and a.var[c].astype(str).str.len().gt(0).all()), None)
        if col:
            a.var["gene_id"] = a.var_names.astype(str)
            a.var_names = a.var[col].astype(str).values
        a.var_names_make_unique()
        self._prog(45, "Adding sample details")
        meta = {}
        for r in self.params["samples"]:
            meta.setdefault(r["sample"], r)
        if "sample" not in a.obs:
            # Intent: per-sample barcodes are prefixed with the sample name when the pipeline joins samples.
            names = pd.Series(a.obs_names.astype(str))
            a.obs["sample"] = [next((s for s in meta if n.startswith(s + "_")), "unknown") for n in names]
        a.obs["sample"] = a.obs["sample"].astype(str)
        unknown = sorted(set(a.obs["sample"]) - set(meta))
        a = a[a.obs["sample"].isin(meta).values].copy()
        a.obs = a.obs[["sample"]].copy()
        a.obs["condition"] = [meta[s].get("condition") or "none" for s in a.obs["sample"]]
        if any(r.get("batch") for r in meta.values()):
            a.obs["batch"] = [meta[s].get("batch") or "none" for s in a.obs["sample"]]
        for c in a.obs.columns:
            a.obs[c] = a.obs[c].astype("category")
        self._prog(80, "Saving")
        a.write_h5ad(self._ckpt("loaded"))
        self.adata = a
        missing = sorted(set(meta) - set(a.obs["sample"]))
        info = {"kind": pick["kind"], "path": pick["path"], "cells": int(a.n_obs), "genes": int(a.n_vars),
                "samples": int(a.obs["sample"].nunique()), "missing": missing, "unknown": unknown, "symbols": bool(col)}
        self.state.update(step="loaded", loaded_from=info, annotations={})
        self._record("loaded the matrix", **info)

    def cells_per_sample(self):
        a = self.adata if self.adata is not None and self.state.get("step") == "loaded" else self._before_qc()
        return {str(k): int(v) for k, v in a.obs["sample"].value_counts().sort_index().items()}
