"""Shared live-session steps for single-cell modules: filter cells, cluster, markers, name clusters, compare, export.

Generalised from SPLiTscape part 2 (Helen R Horkan PhD). A module's engine
subclasses CellsEngine and supplies the first step, which builds the
"before filtering" checkpoint (SPLiT-seq: combine and label sublibraries;
10x: load the pipeline's matrix). Everything after that is shared, so both
modules filter, cluster and annotate cells in the same way.

Holds the current AnnData in memory and checkpoints every step to
<run>/session/, so a session can stop and resume.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scanpy as sc
import scipy.sparse as spm

from everyome.core.engine import BaseEngine

PIPE = Path(__file__).resolve().parent / "splitseq" / "workflow" / "python"
sys.path.insert(0, str(PIPE))


def _pipeline(name):
    """Import a SPLiTscape pipeline stage module (file names start with digits)."""
    spec = importlib.util.spec_from_file_location(name.replace(".py", "").lstrip("0123456789_"), PIPE / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


integ_mod = _pipeline("12_integrate_cluster.py")
report_mod = _pipeline("14_marker_reports.py")

PALETTE = ["#C2A24A", "#6E1B2B", "#32203A", "#8F7529", "#A83B50", "#5A5260", "#DFC684", "#0E8F8A", "#B9AEC0",
           "#9C7A3C", "#3A3143", "#93283C", "#CBA75A", "#6B2118", "#7C6A85", "#E0B3A0", "#4F6D7A", "#B58A6A"]
MAX_POINTS = 80000


def mito_share(a, pattern: str) -> np.ndarray | None:
    """Percent of each cell's counts from mitochondrial genes (names matching pattern), or None if there are none."""
    if not pattern:
        return None
    mt = a.var_names.str.match(pattern)
    if not mt.any():
        return None
    tot = np.asarray(a.X.sum(1)).ravel()
    return 100 * np.asarray(a[:, mt].X.sum(1)).ravel() / np.maximum(tot, 1)


class CellsEngine(BaseEngine):
    SHARED_API = ("qc_data", "qc_preview", "qc_apply", "cluster", "cluster_summary", "embedding", "colour", "genes",
                  "markers", "dotplot", "annotate", "composition", "export", "files")
    SHARED_REPLAY = ("qc_apply", "cluster", "annotate", "export")
    GROUP = "sample"          # obs column the QC histograms are split by
    SAMPLE = "sample"         # obs column for "cells kept per sample"
    HIDDEN = ("cluster",)     # obs columns not offered for batch correction or comparison
    BEFORE_QC = "loaded"      # checkpoint the first step writes
    CHECKPOINTS = ("clustered", "filtered", "loaded")
    STATUS_KEYS = ("qc", "cluster_params")
    QC_LOW = (20, 10)         # lowest edge of the two QC histograms (counts, features per cell)

    def __init__(self, run_dir: str):
        super().__init__(run_dir)
        self.state.setdefault("annotations", {})
        self.adata = None
        self._sample = None
        self._resume()

    # ---------------------------------------------------------------- state
    def _ckpt(self, name):
        return self.out / f"{name}.h5ad"

    def _resume(self):
        for name in self.CHECKPOINTS:
            if self._ckpt(name).exists():
                self.adata = sc.read_h5ad(self._ckpt(name))
                return

    def status(self):
        a = self.adata
        return {**super().status(), "cells": int(a.n_obs) if a is not None else 0, "genes": int(a.n_vars) if a is not None else 0,
                "obs_columns": [c for c in a.obs.columns if a.obs[c].dtype.name == "category"] if a is not None else [],
                "hidden_columns": list(self.HIDDEN), "annotations": self.state.get("annotations", {}), "clusters": self._clusters(),
                **{k: self.state.get(k) for k in self.STATUS_KEYS}}

    def _clusters(self):
        a = self.adata
        if a is None or "cluster" not in a.obs:
            return []
        counts = a.obs["cluster"].value_counts()
        return [{"id": c, "cells": int(counts[c])} for c in a.obs["cluster"].cat.categories]

    def _mito_pattern(self) -> str:
        return ""

    # ---------------------------------------------------------------- filter cells
    def _before_qc(self):
        return sc.read_h5ad(self._ckpt(self.BEFORE_QC))

    def _metrics(self, a):
        umis = np.asarray(a.X.sum(1)).ravel()
        genes = np.asarray((a.X > 0).sum(1)).ravel()
        return umis, genes, mito_share(a, self._mito_pattern())

    def qc_data(self):
        a = self._before_qc()
        umis, genes, mito = self._metrics(a)
        lo_u, lo_g = self.QC_LOW
        edges = np.linspace(np.log10(lo_u), np.log10(max(umis.max(), lo_u * 5) * 1.1), 61)
        gedges = np.linspace(np.log10(lo_g), np.log10(max(genes.max(), lo_g * 5) * 1.1), 61)
        medges = np.linspace(0, 100, 51)
        out = {"umi_edges": (10 ** edges).round(1).tolist(), "gene_edges": (10 ** gedges).round(1).tolist(), "groups": {},
               "mito_edges": medges.tolist() if mito is not None else None}
        grp = a.obs[self.GROUP].astype("category")
        for g in grp.cat.categories:
            m = (grp == g).values
            out["groups"][str(g)] = {"umi": np.histogram(np.log10(np.maximum(umis[m], lo_u)), edges)[0].tolist(),
                                     "gene": np.histogram(np.log10(np.maximum(genes[m], lo_g)), gedges)[0].tolist(),
                                     **({"mito": np.histogram(mito[m], medges)[0].tolist()} if mito is not None else {})}
        # Scatter sample for the genes-vs-UMIs plot.
        idx = np.random.default_rng(0).choice(a.n_obs, min(6000, a.n_obs), replace=False)
        out["scatter"] = {"umi": umis[idx].astype(int).tolist(), "gene": genes[idx].astype(int).tolist(),
                          "group": grp.values[idx].astype(str).tolist()}
        default = self._qc_defaults(umis, genes)
        if mito is not None:
            default["max_mito"] = 20.0
            out["scatter"]["mito"] = np.round(mito[idx], 2).tolist()
        out["thresholds"] = {**default, **self.state.get("qc", {})}
        return out

    def _qc_defaults(self, umis, genes):
        return {"min_counts": 50, "max_counts": int(np.quantile(umis, .99)) + 1, "min_genes": 50, "max_genes": int(np.quantile(genes, .99)) + 1}

    def _keep(self, a, t):
        umis, genes, mito = self._metrics(a)
        keep = (umis >= t["min_counts"]) & (umis < t["max_counts"]) & (genes >= t["min_genes"]) & (genes < t["max_genes"])
        if mito is not None and t.get("max_mito") is not None:
            keep &= mito <= float(t["max_mito"])
        return keep, mito

    def qc_preview(self, min_counts, max_counts, min_genes, max_genes, max_mito=None):
        a = self.adata if self.state.get("step") == self.BEFORE_QC else self._before_qc()
        keep, _ = self._keep(a, dict(min_counts=min_counts, max_counts=max_counts, min_genes=min_genes, max_genes=max_genes, max_mito=max_mito))
        per = pd.DataFrame({"u": a.obs[self.SAMPLE].astype(str).values, "k": keep}).groupby("u", observed=True)["k"].agg(["sum", "count"])
        return {"kept": int(keep.sum()), "total": int(a.n_obs),
                "per_sample": [{"sample": i, "kept": int(r["sum"]), "total": int(r["count"])} for i, r in per.iterrows()]}

    def qc_apply(self, min_counts, max_counts, min_genes, max_genes, max_mito=None):
        t = {"min_counts": int(min_counts), "max_counts": int(max_counts), "min_genes": int(min_genes), "max_genes": int(max_genes)}
        if max_mito is not None:
            t["max_mito"] = float(max_mito)
        return self._background(self._qc_apply, t)

    def _qc_apply(self, t):
        self._prog(30, "Filtering cells")
        a = self._before_qc()
        before = int(a.n_obs)
        keep, mito = self._keep(a, t)
        if mito is not None:
            a.obs["pct_mito"] = mito
        a = a[keep].copy()
        sc.pp.calculate_qc_metrics(a, percent_top=None, log1p=False, inplace=True)
        a.write_h5ad(self._ckpt("filtered"))
        self.adata = a
        self.state.update(step="filtered", qc=t)
        self._record("filtered cells", **t, cells_before=before, cells_after=int(a.n_obs))

    # ---------------------------------------------------------------- integrate and cluster
    def cluster(self, **params):
        return self._background(self._cluster, params)

    def _cluster(self, p):
        a = sc.read_h5ad(self._ckpt("filtered"))
        self._prog(8, "Normalising"); sc.pp.normalize_total(a, target_sum=1e4); sc.pp.log1p(a)
        self._prog(15, "Finding variable genes"); sc.pp.highly_variable_genes(a, n_top_genes=min(int(p["n_top_genes"]), a.n_vars - 1))
        a.raw = a; a = a[:, a.var["highly_variable"]].copy()
        self._prog(25, "Scaling and PCA"); sc.pp.scale(a, max_value=10)
        npc = min(int(p["n_pcs"]), a.n_vars - 1, a.n_obs - 1)
        sc.tl.pca(a, n_comps=min(50, a.n_vars - 1), svd_solver="arpack", random_state=0)
        rep = "X_pca"
        key = p.get("batch_key")
        if key and key in a.obs and a.obs[key].nunique() > 1 and p.get("harmony", True):
            self._prog(40, "Correcting batches (Harmony)")
            integ_mod.harmony(a, key, 0); rep = "X_pca_harmony"
        self._prog(55, "Building neighbour graph"); sc.pp.neighbors(a, n_neighbors=int(p["n_neighbors"]), n_pcs=npc, use_rep=rep, random_state=0)
        self._prog(65, "UMAP layout"); sc.tl.umap(a, min_dist=p.get("min_dist", .3), random_state=0)
        self._prog(80, "Leiden clustering"); sc.tl.leiden(a, resolution=p["resolution"], key_added="cluster", random_state=0)
        self._prog(88, "Ranking marker genes"); sc.tl.rank_genes_groups(a, "cluster", method="wilcoxon", key_added="markers")
        a.uns["pca_variance_ratio"] = a.uns["pca"]["variance_ratio"].tolist()
        # Batch mixing: share of neighbours from another batch, relative to chance.
        if key and key in a.obs:
            b = a.obs[key].astype(str).values; conn = a.obsp["connectivities"].tocoo()
            other = (b[conn.row] != b[conn.col]).mean(); pk = pd.Series(b).value_counts(normalize=True).values
            a.uns["batch_mixing"] = float(min(1, other / max(1e-9, 1 - (pk ** 2).sum())))
        a.write_h5ad(self._ckpt("clustered"))
        self.adata = a; self._sample = None
        self.state.update(step="clustered", cluster_params=p, annotations={})
        self._record("clustered", **p, clusters=int(a.obs["cluster"].nunique()), batch_mixing=a.uns.get("batch_mixing"))

    def cluster_summary(self):
        a = self.adata
        return {"clusters": self._clusters(), "pca_variance": a.uns.get("pca_variance_ratio", []),
                "batch_mixing": a.uns.get("batch_mixing"), "params": self.state.get("cluster_params")}

    # ---------------------------------------------------------------- display
    def _idx(self):
        if self._sample is None or len(self._sample) > self.adata.n_obs:
            n = self.adata.n_obs
            self._sample = np.sort(np.random.default_rng(1).choice(n, min(n, MAX_POINTS), replace=False))
        return self._sample

    def embedding(self):
        i = self._idx()
        return {"n_total": int(self.adata.n_obs), "xy": np.round(self.adata.obsm["X_umap"][i], 3).ravel().tolist()}

    def _gene_name(self, gene: str) -> str:
        """A readable name for a gene id, when the module has one (SPLiT-seq: from its annotation table)."""
        return ""

    def colour(self, key):
        a, i = self.adata, self._idx()
        if key == "annotation":
            names = self.state.get("annotations", {})
            vals = a.obs["cluster"].astype(str).map(lambda c: names.get(c, {}).get("name") or "Unannotated").values[i]
            cats = sorted(set(vals), key=lambda x: (x == "Unannotated", x))
            colmap = {}
            for c, v in names.items():
                if v.get("name"):
                    colmap.setdefault(v["name"], v.get("color"))
            return {"kind": "cat", "categories": cats, "colors": [colmap.get(c) or "#B9AEC0" for c in cats],
                    "codes": [cats.index(v) for v in vals], "userColours": True}
        if key in a.obs:
            s = a.obs[key]
            if s.dtype.name != "category" and np.issubdtype(s.dtype, np.number):
                v = s.values[i].astype(float)
                return {"kind": "num", "values": np.round(v, 3).tolist(), "max": float(v.max() or 1), "gene": key, "label": ""}
            cats = list(s.cat.categories) if s.dtype.name == "category" else sorted(s.astype(str).unique())
            codes = pd.Categorical(s.astype(str), categories=[str(c) for c in cats]).codes[i]
            return {"kind": "cat", "categories": [str(c) for c in cats], "colors": [PALETTE[k % len(PALETTE)] for k in range(len(cats))], "codes": codes.tolist()}
        if a.raw is not None and key in a.raw.var_names:
            v = a.raw[:, key].X
            v = np.asarray(v.toarray() if spm.issparse(v) else v).ravel()[i]
            return {"kind": "num", "values": np.round(v, 3).tolist(), "max": float(v.max() or 1), "gene": key, "label": self._gene_name(key)}
        raise KeyError(f"'{key}' is not a column or gene")

    def _search_names(self, q: str, names, hits: list, n: int) -> list:
        """Extra genes whose readable name matches q (modules with gene names add these)."""
        return hits

    def genes(self, q, n=15):
        names = self.adata.raw.var_names if self.adata.raw is not None else self.adata.var_names
        hits = [g for g in names if q.lower() in g.lower()][:n]
        hits = self._search_names(q, names, hits, n)
        return [{"gene": g, "name": self._gene_name(g)} for g in hits]

    # ---------------------------------------------------------------- markers
    def markers(self, cluster, n=25):
        df = report_mod.marker_frame(self.adata, "markers", str(cluster))
        df = df[(df["pvals_adj"] < .05) & (df["logfoldchanges"] > 0)].head(n)
        a = self.adata
        cl = (a.obs["cluster"] == str(cluster)).values
        out = []
        for _, r in df.iterrows():
            x = a.raw[:, r["names"]].X
            x = np.asarray(x.toarray() if spm.issparse(x) else x).ravel() > 0
            out.append({"gene": r["names"], "name": self._gene_name(r["names"]), "logfc": round(float(r["logfoldchanges"]), 2),
                        "padj": float(r["pvals_adj"]), "pct_in": round(float(x[cl].mean()) * 100, 1), "pct_out": round(float(x[~cl].mean()) * 100, 1)})
        return out

    def dotplot(self, genes, groupby="cluster"):
        a = self.adata
        genes = [g for g in genes if g in a.raw.var_names]
        X = a.raw[:, genes].X
        X = X.toarray() if spm.issparse(X) else np.asarray(X)
        groups = list(a.obs[groupby].cat.categories)
        frac, mean = [], []
        for g in groups:
            sub = X[(a.obs[groupby] == g).values]
            frac.append(((sub > 0).mean(0)).round(3).tolist())
            with np.errstate(invalid="ignore"):
                mean.append(np.nan_to_num((sub.sum(0) / np.maximum((sub > 0).sum(0), 1))).round(3).tolist())
        return {"genes": genes, "names": [self._gene_name(g) for g in genes], "groups": [str(g) for g in groups], "frac": frac, "mean": mean}

    # ---------------------------------------------------------------- name clusters
    def annotate(self, cluster, name, color):
        self.state.setdefault("annotations", {})[str(cluster)] = {"name": name.strip(), "color": color}
        self._record("named a cluster", cluster=str(cluster), name=name.strip(), color=color)
        return self.state["annotations"]

    def composition(self, group):
        a = self.adata
        names = self.state.get("annotations", {})
        lab = a.obs["cluster"].astype(str).map(lambda c: names.get(c, {}).get("name") or "Unannotated")
        ct = pd.crosstab(lab, a.obs[group].astype(str))
        fr = ct / ct.sum(0)
        colmap = {v["name"]: v.get("color") for v in names.values() if v.get("name")}
        return {"types": list(ct.index), "groups": list(ct.columns), "counts": ct.values.tolist(), "fractions": fr.round(4).values.tolist(),
                "colors": [colmap.get(t, "#D6CBB6") for t in ct.index], "group_sizes": ct.sum(0).astype(int).tolist()}

    # ---------------------------------------------------------------- export
    def export(self, group):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", str(group)) or group not in self.adata.obs:
            raise ValueError(f"'{group}' is not a column of the data.")
        return self._background(self._export, group)

    def _export(self, group):
        a = self.adata
        d = self.dir / "results"; d.mkdir(exist_ok=True)
        names = self.state.get("annotations", {})
        self._prog(20, "Writing annotated object")
        a.obs["annotation"] = a.obs["cluster"].astype(str).map(lambda c: names.get(c, {}).get("name") or "Unannotated").astype("category")
        a.uns["annotation_colors"] = [next((v["color"] for v in names.values() if v.get("name") == c), "#D6CBB6") for c in a.obs["annotation"].cat.categories]
        a.write_h5ad(d / "annotated.h5ad")
        self._prog(50, "Writing tables")
        comp = self.composition(group)
        pd.DataFrame(comp["counts"], index=comp["types"], columns=comp["groups"]).to_csv(d / f"composition_counts_by_{group}.csv")
        pd.DataFrame(comp["fractions"], index=comp["types"], columns=comp["groups"]).to_csv(d / f"composition_fractions_by_{group}.csv")
        with pd.ExcelWriter(d / "markers_by_cluster.xlsx") as xw:
            for c in a.obs["cluster"].cat.categories:
                pd.DataFrame(self.markers(c, n=200)).to_excel(xw, sheet_name=f"Cluster {c}"[:31], index=False)
        self._prog(80, "Drawing figures")
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 7))
        sc.pl.umap(a, color="annotation", ax=ax, show=False, frameon=False, title="Annotated cell types")
        fig.savefig(d / "umap_annotation.png", dpi=200, bbox_inches="tight"); plt.close(fig)
        files = sorted(p.name for p in d.iterdir())
        self.state.update(step="exported", exported=files)
        self._record("exported results", compared_by=group, files=files)

    def files(self):
        d = self.dir / "results"
        return [{"name": p.name, "size": p.stat().st_size} for p in sorted(d.iterdir()) if p.is_file()] if d.exists() else []
