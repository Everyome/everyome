"""Live session for imaging-based spatial data (10x Xenium, Vizgen MERSCOPE, Bruker CosMx): read each section's cells
and positions, then the shared single-cell steps (filter, cluster, markers, naming, export) and the shared spatial
steps (cells on the tissue, spatially variable genes, which cell types sit next to which).

Built on the Visium engine; only reading differs, and drawing thins very large sections to a fixed number of cells.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import scanpy as sc
import scipy.sparse as spm

from ..visium.engine import Engine as VisiumEngine, neighbours_dist
from .readers import UNITS, read

MAX_DRAWN = 40_000


class Engine(VisiumEngine):
    COUNT_LABELS = {"total_counts": "Transcripts per cell", "n_genes": "Genes per cell"}

    def _mito_pattern(self):
        return ""                                          # targeted panels rarely include mitochondrial genes

    def _qc_defaults(self, umis, genes):
        # Intent: panels measure hundreds of genes, not the whole transcriptome; cells have tens to hundreds of transcripts.
        return {"min_counts": 10, "max_counts": int(np.quantile(umis, .995)) + 1, "min_genes": 5, "max_genes": int(np.quantile(genes, .995)) + 1}

    def samples_info(self):
        return [{"sample": r["sample"], "outs": r["outs"], "platform": r.get("platform") or "", "condition": r.get("condition", ""),
                 "batch": r.get("batch", "")} for r in self.params["samples"]]

    def _load(self):
        parts, images, info = [], {}, []
        rows = self.params["samples"]
        for k, r in enumerate(rows):
            self._prog(5 + 70 * k // max(1, len(rows)), f"Reading {r['sample']}")
            a, platform = read(r["outs"], r.get("platform") or "")
            a.obs_names = [f"{r['sample']}_{b}" for b in a.obs_names]
            a.obs["sample"] = r["sample"]
            a.obs["condition"] = r.get("condition") or "none"
            if any(x.get("batch") for x in rows):
                a.obs["batch"] = r.get("batch") or "none"
            images[r["sample"]] = {"image": "", "scale": 1.0, "spot": None, "units": UNITS[platform]}
            n = np.asarray(a.X.sum(1)).ravel()
            info.append({"sample": r["sample"], "platform": platform, "cells": int(a.n_obs), "genes": int(a.n_vars),
                         "median_transcripts": float(np.median(n)) if a.n_obs else 0})
            parts.append(a)
        self._prog(80, "Joining sections")
        a = sc.concat(parts, join="outer", fill_value=0) if len(parts) > 1 else parts[0]
        a.X = spm.csr_matrix(a.X, dtype=np.float32)
        for c in ("sample", "condition", "batch"):
            if c in a.obs:
                a.obs[c] = a.obs[c].astype("category")
        a.uns["images"] = json.dumps(images)
        a.write_h5ad(self._ckpt("loaded"))
        self.adata = a
        self.state.update(step="loaded", loaded_from={"samples": info}, annotations={}, spatial_genes=None, neighbourhood=None)
        self._record("loaded imaging spatial output", samples=info)

    def tissue(self, sample: str, key: str = "total_counts"):
        """This section's cells in place (no image), coloured by a label, a gene or a QC measure; large sections thinned."""
        a = self.adata
        if sample not in set(a.obs["sample"].astype(str)):
            raise ValueError(f"No cells from {sample}.")
        m = (a.obs["sample"].astype(str) == sample).values
        idx = np.where(m)[0]
        if len(idx) > MAX_DRAWN:
            idx = np.sort(np.random.default_rng(1).choice(idx, MAX_DRAWN, replace=False))
        sub = np.zeros(len(m), bool)
        sub[idx] = True
        xy = a.obsm["spatial"][sub]
        lo = xy.min(0)
        xy = xy - lo + (xy.max(0) - lo) * 0.02             # Intent: start the drawing near 0,0 with a small margin
        w, h = (xy.max(0) * 1.02).tolist()
        r = float(np.median(neighbours_dist(xy)) / 2.2)
        return {"image": "", "width": w, "height": h, "x": np.round(xy[:, 0], 1).tolist(), "y": np.round(xy[:, 1], 1).tolist(),
                "r": round(r, 2), "spots": int(m.sum()), "drawn": int(sub.sum()), "colour": self._spot_colour(key, sub)}
