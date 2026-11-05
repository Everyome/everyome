"""Live session for multiome (RNA and ATAC from the same cells): read Cell Ranger ARC's joint matrices, filter cells,
cluster on RNA, ATAC or both together (weighted nearest neighbours), then the shared single-cell steps on the RNA.

load     each sample's 'filtered_feature_bc_matrix' (folder or .h5): genes and peaks; cells with too few ATAC
         counts are left out; the RNA becomes the session's matrix, the peaks are kept beside it
qc       the shared filter view on the RNA (UMIs, genes, mitochondrial share)
cluster  RNA: normalise, variable genes, PCA. ATAC: TF-IDF and LSI (the first component, which tracks depth, is
         dropped). Joint: muon's weighted nearest neighbours, which learns per cell how much to trust each. Then
         Leiden and UMAP, and markers on the RNA
"""
from __future__ import annotations

import gzip
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import scanpy as sc
import scipy.io as sio
import scipy.sparse as sp

from ..cells import CellsEngine

MODES = {"joint": "RNA and ATAC together (weighted nearest neighbours)", "rna": "RNA only", "atac": "ATAC only"}


def read_arc(outs: Path, sample: str) -> tuple[ad.AnnData, ad.AnnData]:
    """(RNA, peaks) for one sample from Cell Ranger ARC's 'outs' folder (the folder or the .h5 matrix)."""
    outs = Path(outs)
    h5, mtx = outs / "filtered_feature_bc_matrix.h5", outs / "filtered_feature_bc_matrix"
    if h5.is_file():
        a = sc.read_10x_h5(h5, gex_only=False)
        kind = a.var["feature_types"].astype(str).values
        X, names, ids, bcs = a.X.tocsr(), a.var_names.astype(str).values, a.var.get("gene_ids", a.var_names).astype(str).values, a.obs_names
    elif mtx.is_dir():
        X = sio.mmread(gzip.open(mtx / "matrix.mtx.gz")).T.tocsr()
        f = pd.read_csv(mtx / "features.tsv.gz", sep="\t", header=None)
        kind, names, ids = f[2].astype(str).values, f[1].astype(str).values, f[0].astype(str).values
        bcs = pd.read_csv(mtx / "barcodes.tsv.gz", header=None)[0].astype(str).values
    else:
        raise FileNotFoundError(f"{outs} has no filtered_feature_bc_matrix (.h5 or folder). Choose Cell Ranger ARC's 'outs' folder.")
    obs = pd.DataFrame(index=[f"{sample}#{b}" for b in bcs])
    g, p = kind == "Gene Expression", kind == "Peaks"
    if not g.any() or not p.any():
        raise ValueError(f"{outs} doesn't have both genes and peaks; is it a Cell Ranger ARC (multiome) output?")
    rna = ad.AnnData(X[:, g].astype(np.float32), obs=obs.copy(), var=pd.DataFrame({"gene_id": ids[g]}, index=names[g]))
    rna.var_names_make_unique()
    peaks = ad.AnnData(X[:, p].astype(np.float32), obs=obs.copy(), var=pd.DataFrame(index=ids[p]))
    return rna, peaks


def lsi(X, n_comps: int) -> np.ndarray:
    """TF-IDF and truncated SVD of a cell-by-peak matrix (latent semantic indexing), first component dropped."""
    from sklearn.decomposition import TruncatedSVD
    X = sp.csr_matrix(X)
    tf = sp.diags(1 / np.maximum(np.asarray(X.sum(1)).ravel(), 1)) @ X
    idf = np.log1p(X.shape[0] / np.maximum(np.asarray((X > 0).sum(0)).ravel(), 1))
    m = (tf @ sp.diags(idf)).tocsr()
    m.data = np.log1p(m.data * 1e4)
    comps = TruncatedSVD(n_components=min(n_comps + 1, min(m.shape) - 1), random_state=0).fit_transform(m)[:, 1:]
    return (comps - comps.mean(0)) / np.maximum(comps.std(0), 1e-9)


class Engine(CellsEngine):
    API = ("load", "load_summary") + CellsEngine.SHARED_API
    REPLAY = ("load",) + CellsEngine.SHARED_REPLAY
    STATUS_KEYS = ("loaded_from", "qc", "cluster_params")

    def _mito_pattern(self):
        return self.params.get("mito_genes") or ""

    # ---------------------------------------------------------------- load
    def load(self, min_atac: int = 500):
        return self._background(self._load, int(min_atac))

    def _load(self, min_atac):
        rows = self.params["samples"]
        rnas, peaks = [], []
        for i, r in enumerate(rows):
            self._prog(5 + 60 * i / len(rows), f"Reading {r['sample']}")
            rna, pk = read_arc(Path(r["outs"]), r["sample"])
            n_atac = np.asarray(pk.X.sum(1)).ravel()
            keep = n_atac >= min_atac
            rna, pk = rna[keep].copy(), pk[keep].copy()
            rna.obs["atac_counts"] = n_atac[keep]
            for x in (rna, pk):
                x.obs["sample"] = r["sample"]
                x.obs["condition"] = r.get("condition") or "none"
                if any(q.get("batch") for q in rows):
                    x.obs["batch"] = r.get("batch") or "none"
            rnas.append(rna)
            peaks.append(pk)
        self._prog(75, "Combining samples")
        rna, pk = ad.concat(rnas, join="outer", merge="first"), ad.concat(peaks, join="outer")
        for c in ("sample", "condition", "batch"):
            if c in rna.obs:
                rna.obs[c] = rna.obs[c].astype("category")
        pk.write_h5ad(self.out / "peaks.h5ad")
        rna.write_h5ad(self._ckpt("loaded"))
        self.adata = rna
        info = {"cells": int(rna.n_obs), "genes": int(rna.n_vars), "peaks": int(pk.n_vars), "min_atac": min_atac,
                "samples": int(rna.obs["sample"].nunique())}
        self.state.update(step="loaded", loaded_from=info, annotations={})
        self._record("read the multiome matrices", **info)

    def load_summary(self):
        a = self.adata if self.adata is not None and self.state.get("step") == "loaded" else self._before_qc()
        umis = np.asarray(a.X.sum(1)).ravel()
        df = pd.DataFrame({"sample": a.obs["sample"].astype(str).values, "umis": umis, "atac": a.obs["atac_counts"].values})
        per = df.groupby("sample").agg(cells=("umis", "size"), median_umis=("umis", "median"), median_atac=("atac", "median"))
        return {"samples": [{"sample": s, "cells": int(r.cells), "median_umis": int(r.median_umis), "median_atac": int(r.median_atac)}
                            for s, r in per.iterrows()]}

    # ---------------------------------------------------------------- cluster
    def _cluster(self, p):
        import muon as mu
        mode = p.get("mode") or "joint"
        if mode not in MODES:
            raise ValueError(f"Choose how to cluster: {', '.join(MODES)}.")
        g = sc.read_h5ad(self._ckpt("filtered"))
        key = p.get("batch_key")
        harmony = bool(key and key in g.obs and g.obs[key].nunique() > 1 and p.get("harmony", True))
        npc, nn = int(p["n_pcs"]), int(p["n_neighbors"])
        r = None
        if mode in ("rna", "joint"):
            self._prog(10, "RNA: normalising and PCA")
            r = g.copy()
            sc.pp.normalize_total(r, target_sum=1e4); sc.pp.log1p(r)
            sc.pp.highly_variable_genes(r, n_top_genes=min(int(p["n_top_genes"]), r.n_vars - 1))
            r = r[:, r.var["highly_variable"]].copy(); sc.pp.scale(r, max_value=10)
            sc.tl.pca(r, n_comps=min(npc, r.n_vars - 1, r.n_obs - 1), svd_solver="arpack", random_state=0)
            rep = "X_pca"
            if harmony:
                sc.external.pp.harmony_integrate(r, key, basis="X_pca", adjusted_basis="X_pca_harmony", verbose=False)
                rep = "X_pca_harmony"
            sc.pp.neighbors(r, n_neighbors=nn, use_rep=rep, random_state=0)
        a = None
        if mode in ("atac", "joint"):
            self._prog(35, "ATAC: TF-IDF and LSI")
            a = sc.read_h5ad(self.out / "peaks.h5ad")[g.obs_names].copy()
            a.obsm["X_lsi"] = lsi(a.X, npc)
            rep = "X_lsi"
            if harmony:
                a.obs[key] = g.obs[key].values
                sc.external.pp.harmony_integrate(a, key, basis="X_lsi", adjusted_basis="X_lsi_harmony", verbose=False)
                rep = "X_lsi_harmony"
            sc.pp.neighbors(a, n_neighbors=nn, use_rep=rep, random_state=0)
        self._prog(55, "Neighbours" + (" (weighted nearest neighbours)" if mode == "joint" else ""))
        if mode == "joint":
            obj = mu.MuData({"rna": r, "atac": a})
            mu.pp.neighbors(obj, n_neighbors=nn, random_state=0)
            self._prog(70, "Leiden clustering"); mu.tl.leiden(obj, resolution=float(p["resolution"]), random_state=0)
            self._prog(80, "UMAP layout"); mu.tl.umap(obj, min_dist=float(p.get("min_dist", .3)), random_state=0)
            labels, umap = obj.obs["leiden"].astype(str).values, np.asarray(obj.obsm["X_umap"])
            weights = obj.obs["rna:mod_weight"].values
            conn = obj.obsp["connectivities"]
        else:
            obj = r if mode == "rna" else a
            self._prog(70, "Leiden clustering"); sc.tl.leiden(obj, resolution=float(p["resolution"]), key_added="leiden", random_state=0,
                                                               flavor="igraph", n_iterations=2, directed=False)
            self._prog(80, "UMAP layout"); sc.tl.umap(obj, min_dist=float(p.get("min_dist", .3)), random_state=0)
            labels, umap, weights, conn = obj.obs["leiden"].astype(str).values, obj.obsm["X_umap"], None, obj.obsp["connectivities"]
        # Intent: the shared steps read the RNA; carry the layout and clusters over, numbered by size.
        order = pd.Series(labels).value_counts().index
        rename = {c: str(i) for i, c in enumerate(order)}
        g.obsm["X_umap"] = np.asarray(umap)
        g.obs["cluster"] = pd.Categorical([rename[c] for c in labels], categories=[str(i) for i in range(len(order))])
        if weights is not None:
            g.obs["rna_weight"] = np.round(weights, 3)
        self._prog(88, "Ranking marker genes")
        sc.pp.normalize_total(g, target_sum=1e4); sc.pp.log1p(g)
        g.raw = g
        sc.tl.rank_genes_groups(g, "cluster", method="wilcoxon", key_added="markers")
        if key and key in g.obs:
            c = sp.coo_matrix(conn)
            b = g.obs[key].astype(str).values
            if c.nnz:
                other = (b[c.row] != b[c.col]).mean()
                pk = pd.Series(b).value_counts(normalize=True).values
                g.uns["batch_mixing"] = float(min(1, other / max(1e-9, 1 - (pk ** 2).sum())))
        g.write_h5ad(self._ckpt("clustered"))
        self.adata = g
        self._sample = None
        self.state.update(step="clustered", cluster_params=p, annotations={})
        self._record("clustered", **{**p, "mode": mode}, clusters=int(g.obs["cluster"].nunique()), batch_mixing=g.uns.get("batch_mixing"),
                     rna_weight=round(float(np.mean(weights)), 3) if weights is not None else None)
