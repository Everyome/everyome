"""Live session for high-resolution sequencing-based spatial data (Visium HD, Stereo-seq, Curio Seeker): read each
section at the chosen bin size, then the shared single-cell steps and the shared spatial steps (bins on the tissue,
spatially variable genes, neighbourhoods).

Built on the Visium engine; reading differs, and drawing thins very large sections (Visium HD at 8 µm has hundreds of
thousands of bins) to a fixed number for the picture only.
"""
from __future__ import annotations

import json

import numpy as np
import scanpy as sc
import scipy.sparse as spm

from ..visium.engine import Engine as VisiumEngine, neighbours_dist
from .readers import read

MAX_DRAWN = 40_000


class Engine(VisiumEngine):
    COUNT_LABELS = {"total_counts": "UMIs per bin", "n_genes": "Genes per bin"}

    def samples_info(self):
        return [{"sample": r["sample"], "outs": r["outs"], "platform": r.get("platform") or "", "condition": r.get("condition", ""),
                 "batch": r.get("batch", "")} for r in self.params["samples"]]

    def _qc_defaults(self, umis, genes):
        # Intent: small bins hold little RNA; start low and let people raise it while watching.
        return {"min_counts": 20, "max_counts": int(np.quantile(umis, .999)) + 1, "min_genes": 10, "max_genes": int(np.quantile(genes, .999)) + 1}

    def load(self, bin_um: int = 0):
        return self._background(self._load, int(bin_um or self.params.get("bin_um") or 8))

    def _load(self, bin_um=8):
        parts, images, info = [], {}, []
        rows = self.params["samples"]
        for k, r in enumerate(rows):
            self._prog(5 + 70 * k // max(1, len(rows)), f"Reading {r['sample']}")
            a, meta, platform = read(r["outs"], r.get("platform") or "", bin_um)
            a.obs_names = [f"{r['sample']}_{b}" for b in a.obs_names]
            a.obs["sample"] = r["sample"]
            a.obs["condition"] = r.get("condition") or "none"
            if any(x.get("batch") for x in rows):
                a.obs["batch"] = r.get("batch") or "none"
            images[r["sample"]] = meta
            n = np.asarray(a.X.sum(1)).ravel()
            info.append({"sample": r["sample"], "platform": platform, "bins": int(a.n_obs), "genes": int(a.n_vars),
                         "median_umi": float(np.median(n)) if a.n_obs else 0})
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
        self.state.update(step="loaded", loaded_from={"samples": info, "bin_um": bin_um}, annotations={}, spatial_genes=None, neighbourhood=None)
        self._record("loaded high-resolution spatial output", samples=info, bin_um=bin_um)

    def tissue(self, sample: str, key: str = "total_counts"):
        """This section's bins in place (over the tissue image when there is one), coloured by anything; large sections thinned."""
        a = self.adata
        if sample not in set(a.obs["sample"].astype(str)):
            raise ValueError(f"No bins from {sample}.")
        m = (a.obs["sample"].astype(str) == sample).values
        idx = np.where(m)[0]
        if len(idx) > MAX_DRAWN:
            idx = np.sort(np.random.default_rng(1).choice(idx, MAX_DRAWN, replace=False))
        sub = np.zeros(len(m), bool)
        sub[idx] = True
        img = self._image(sample)
        xy = a.obsm["spatial"][sub] * img["scale"]
        if img["uri"]:
            w, h = img["width"], img["height"]
        else:
            lo = xy.min(0)
            xy = xy - lo + (xy.max(0) - lo) * 0.02
            w, h = (xy.max(0) * 1.02).tolist()
        r = float(np.median(neighbours_dist(xy)) / 2.2)    # spacing of the drawn bins, so thinned sections stay readable
        return {"image": img["uri"], "width": w, "height": h, "x": np.round(xy[:, 0], 1).tolist(), "y": np.round(xy[:, 1], 1).tolist(),
                "r": round(min(r, max(w, h) / 50), 2), "spots": int(m.sum()), "drawn": int(sub.sum()), "colour": self._spot_colour(key, sub)}
