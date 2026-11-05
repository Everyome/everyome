"""Live session for single-cell ATAC-seq: read each sample's fragments with SnapATAC2, check cell quality (fragments
and TSS enrichment), cluster on genome tiles, then the shared single-cell steps on gene activity scores.

load     fragments → cells (SnapATAC2), with fragments per cell, TSS enrichment and fragment sizes; a tile matrix
         (500 bp bins, for clustering) and a gene activity matrix (fragments over each gene and 2 kb upstream, for
         markers and naming) are kept side by side
qc       the shared filter view, on fragments per cell and TSS enrichment
cluster  most variable tiles → spectral embedding → (Harmony) → neighbours → Leiden and UMAP (SnapATAC2)
then     markers on gene activity, naming, comparison and export, shared with the other single-cell modules
"""
from __future__ import annotations

from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import scanpy as sc

from ..cells import CellsEngine
from .helpers import chrom_sizes


class Engine(CellsEngine):
    API = ("load", "load_summary") + CellsEngine.SHARED_API
    REPLAY = ("load",) + CellsEngine.SHARED_REPLAY
    STATUS_KEYS = ("loaded_from", "qc", "cluster_params")
    QC_LOW = (100, 0.5)

    def _metrics(self, a):
        return a.obs["n_fragment"].values.astype(float), a.obs["tsse"].values.astype(float), None

    def _qc_defaults(self, frags, tsse):
        # Intent: common starting points (ENCODE asks for TSS enrichment of at least 4 to 6 in good libraries).
        return {"min_counts": 1000, "max_counts": int(np.quantile(frags, .99)) + 1, "min_genes": 4, "max_genes": int(np.ceil(tsse.max())) + 1}

    # ---------------------------------------------------------------- load
    def load(self, min_fragments: int = 500, bin_size: int = 500):
        return self._background(self._load, int(min_fragments), int(bin_size))

    def _load(self, min_fragments, bin_size):
        import snapatac2 as snap
        sizes = chrom_sizes(self.params["genome"])
        gtf = Path(self.params["annotation"])
        tiles, genes, frag_sizes = [], [], {}
        rows = self.params["samples"]
        for i, r in enumerate(rows):
            s = r["sample"]
            path = self.dir / "results" / "fragments" / f"{s}.tsv.gz"
            if not path.exists():
                raise FileNotFoundError(f"No fragments for {s}. Did the cluster stage finish for every sample?")
            self._prog(5 + 60 * i / len(rows), f"Reading {s}")
            a = snap.pp.import_fragments(str(path), chrom_sizes=sizes, sorted_by_barcode=False,
                                         min_num_fragments=min_fragments, n_jobs=1)
            snap.metrics.tsse(a, gtf, n_jobs=1)
            snap.metrics.frag_size_distr(a, n_jobs=1)
            frag_sizes[s] = np.asarray(a.uns["frag_size_distr"]).tolist()
            snap.pp.add_tile_matrix(a, bin_size=bin_size, n_jobs=1)
            g = snap.pp.make_gene_matrix(a, gtf)
            for x in (a, g):
                x.obs_names = [f"{s}#{b}" for b in x.obs_names]
                x.obs["sample"] = s
                x.obs["condition"] = r.get("condition") or "none"
                if any(q.get("batch") for q in rows):
                    x.obs["batch"] = r.get("batch") or "none"
            g.obs["n_fragment"] = a.obs["n_fragment"].values
            g.obs["tsse"] = a.obs["tsse"].values
            # Intent: keep only what the later steps need; SnapATAC2's in-memory objects carry fragments too.
            tiles.append(ad.AnnData(X=a.X, obs=a.obs[[c for c in ("sample", "condition", "batch") if c in a.obs]].copy(),
                                    var=pd.DataFrame(index=a.var_names)))
            genes.append(g)
        self._prog(70, "Combining samples")
        t = ad.concat(tiles, join="outer")
        g = ad.concat(genes, join="outer")
        for c in ("sample", "condition", "batch"):
            if c in g.obs:
                g.obs[c] = g.obs[c].astype("category")
                t.obs[c] = t.obs[c].astype("category")
        g.uns["frag_size_distr"] = frag_sizes
        self._prog(85, "Saving")
        t.write_h5ad(self.out / "tiles.h5ad")
        g.write_h5ad(self._ckpt("loaded"))
        self.adata = g
        info = {"cells": int(g.n_obs), "genes": int(g.n_vars), "tiles": int(t.n_vars), "bin_size": bin_size,
                "min_fragments": min_fragments, "samples": int(g.obs["sample"].nunique())}
        self.state.update(step="loaded", loaded_from=info, annotations={})
        self._record("read the fragments", **info)

    def load_summary(self):
        a = self.adata if self.adata is not None and self.state.get("step") == "loaded" else self._before_qc()
        per = a.obs.groupby("sample", observed=True).agg(cells=("tsse", "size"), median_fragments=("n_fragment", "median"),
                                                         median_tsse=("tsse", "median"))
        return {"samples": [{"sample": str(s), "cells": int(r.cells), "median_fragments": int(r.median_fragments),
                             "median_tsse": round(float(r.median_tsse), 1)} for s, r in per.iterrows()],
                "frag_sizes": a.uns.get("frag_size_distr", {})}

    # ---------------------------------------------------------------- cluster (on tiles)
    def _cluster(self, p):
        import snapatac2 as snap
        g = sc.read_h5ad(self._ckpt("filtered"))
        self._prog(8, "Reading tiles")
        t = sc.read_h5ad(self.out / "tiles.h5ad")[g.obs_names].copy()
        self._prog(20, "Choosing the most variable tiles")
        snap.pp.select_features(t, n_features=int(p["n_top_genes"]) * 25, n_jobs=1, verbose=False)
        self._prog(35, "Spectral embedding")
        npc = min(int(p["n_pcs"]), t.n_obs - 2)
        snap.tl.spectral(t, n_comps=npc, random_state=0, num_threads=1)
        rep = "X_spectral"
        key = p.get("batch_key")
        if key and key in t.obs and t.obs[key].nunique() > 1 and p.get("harmony", True):
            self._prog(50, "Correcting batches (Harmony)")
            snap.pp.harmony(t, batch=key, use_rep=rep, key_added="X_spectral_harmony", n_jobs=1)
            rep = "X_spectral_harmony"
        self._prog(60, "Building neighbour graph")
        snap.pp.knn(t, n_neighbors=int(p["n_neighbors"]), use_rep=rep, random_state=0)
        self._prog(70, "Leiden clustering")
        snap.tl.leiden(t, resolution=float(p["resolution"]), random_state=0)
        self._prog(78, "UMAP layout")
        snap.tl.umap(t, use_rep=rep, random_state=0, min_dist=float(p.get("min_dist", .3)))
        # Intent: the shared steps (markers, naming, comparison) read gene activity; carry the layout and clusters over.
        g.obsm["X_umap"] = np.asarray(t.obsm["X_umap"])
        order = pd.Series(t.obs["leiden"].astype(str).values).value_counts().index
        rename = {c: str(i) for i, c in enumerate(order)}
        g.obs["cluster"] = pd.Categorical([rename[c] for c in t.obs["leiden"].astype(str)], categories=[str(i) for i in range(len(order))])
        self._prog(85, "Ranking marker genes")
        g.layers["counts"] = g.X.copy()
        sc.pp.normalize_total(g, target_sum=1e4)
        sc.pp.log1p(g)
        g.raw = g
        sc.tl.rank_genes_groups(g, "cluster", method="wilcoxon", key_added="markers")
        g.uns["pca_variance_ratio"] = []
        if key and key in g.obs:
            from scipy.sparse import coo_matrix
            conn = coo_matrix(t.obsp["distances"]) if "distances" in t.obsp else None
            if conn is not None and conn.nnz:
                b = g.obs[key].astype(str).values
                other = (b[conn.row] != b[conn.col]).mean()
                pk = pd.Series(b).value_counts(normalize=True).values
                g.uns["batch_mixing"] = float(min(1, other / max(1e-9, 1 - (pk ** 2).sum())))
        g.write_h5ad(self._ckpt("clustered"))
        self.adata = g
        self._sample = None
        self.state.update(step="clustered", cluster_params=p, annotations={})
        self._record("clustered", **p, clusters=int(g.obs["cluster"].nunique()), batch_mixing=g.uns.get("batch_mixing"))
