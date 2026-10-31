"""SPLiTscape part 2 as an Everyome engine: stages 09–15 as interactive steps.

Merging with an existing atlas or dataset is optional: without one, the
sublibraries are analysed on their own (for example, to build a first atlas).

Runs inside the live session on a compute node. Holds the current AnnData in
memory and checkpoints every step to <run>/session/, so a session can stop and
resume. Reuses the pipeline's own functions (workflow/python) where they exist,
and records every decision in order for the run's write-up.
Ported from SPLiTscape (Helen R Horkan PhD).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import scanpy as sc
import scipy.sparse as spm

from everyome.core.engine import BaseEngine

PIPE = Path(__file__).resolve().parent / "workflow" / "python"
sys.path.insert(0, str(PIPE))


def _pipeline(name):
    """Import a pipeline stage module (file names start with digits)."""
    spec = importlib.util.spec_from_file_location(name.replace(".py", "").lstrip("0123456789_"), PIPE / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


label_mod = _pipeline("10_label_cells.py")
integ_mod = _pipeline("12_integrate_cluster.py")
report_mod = _pipeline("14_marker_reports.py")

PALETTE = ["#C2A24A", "#6E1B2B", "#32203A", "#8F7529", "#A83B50", "#5A5260", "#DFC684", "#0E8F8A", "#B9AEC0",
           "#9C7A3C", "#3A3143", "#93283C", "#CBA75A", "#6B2118", "#7C6A85", "#E0B3A0", "#4F6D7A", "#B58A6A"]
MAX_POINTS = 80000
CELL_ID = r"(?P<experiment>[A-Za-z0-9]+)_(?P<library>lib_\d+_\d+)_(?P<barcode>[ACGTN]+)$"


def _read_dge(path):
    df = pd.read_csv(path, sep="\t", index_col=0)
    return ad.AnnData(X=spm.csr_matrix(df.values.T.astype(np.float32)), obs=pd.DataFrame(index=df.columns), var=pd.DataFrame(index=df.index))


class Engine(BaseEngine):
    API = ("merge", "libraries", "label", "unique_counts", "qc_data", "qc_preview", "qc_apply", "cluster", "cluster_summary",
           "embedding", "colour", "genes", "markers", "dotplot", "annotate", "composition", "export", "files")

    def __init__(self, run_dir: str):
        super().__init__(run_dir)
        self.state.setdefault("annotations", {})
        self.adata = None
        self._annot = None
        self._sample = None
        # Intent: gene-name preferences are run settings now, not built-in Hydra defaults.
        self.diamond_cfg = {"diamond_columns": [1, 6, 7], "diamond_names": ["gene_id", "match", "ncbi_name"],
                            "preferred_species": self.params.get("preferred_species", ""),
                            "preferred_species_ncbi": self.params.get("preferred_species_ncbi", ""),
                            "uninformative_words": ["hypothetical", "uncharacterized", "unnamed"], "preferred_hit_order": "file"}
        self._resume()

    # ---------------------------------------------------------------- state
    def _ckpt(self, name):
        return self.out / f"{name}.h5ad"

    def _resume(self):
        for name in ["clustered", "filtered", "labelled", "combined"]:
            if self._ckpt(name).exists():
                self.adata = sc.read_h5ad(self._ckpt(name))
                return

    def status(self):
        a = self.adata
        return {**super().status(), "cells": int(a.n_obs) if a is not None else 0, "genes": int(a.n_vars) if a is not None else 0,
                "obs_columns": [c for c in a.obs.columns if a.obs[c].dtype.name == "category"] if a is not None else [],
                "annotations": self.state.get("annotations", {}), "clusters": self._clusters(),
                **{k: self.state.get(k) for k in ["experiment", "merged", "library_table", "label_columns", "sheets", "qc", "cluster_params"]}}

    def _clusters(self):
        a = self.adata
        if a is None or "cluster" not in a.obs:
            return []
        counts = a.obs["cluster"].value_counts()
        return [{"id": c, "cells": int(counts[c])} for c in a.obs["cluster"].cat.categories]

    # ---------------------------------------------------------------- 09 combine (and optionally merge)
    def merge(self, experiment="expt", include_atlas=True, atlas_prefix="atlas"):
        if not str(experiment).isalnum():
            raise ValueError("Use letters and digits only for the experiment name (it becomes part of every cell's name).")
        if experiment == atlas_prefix:
            raise ValueError(f"Choose an experiment name other than '{atlas_prefix}'.")
        use_atlas = bool(include_atlas) and bool(self.params.get("atlas_dir"))
        return self._background(self._merge, experiment, use_atlas, atlas_prefix)

    def _merge(self, experiment, use_atlas, atlas_prefix):
        rows, parts, g = self.params["sublibraries"], [], self.params["min_genes_per_cell"]
        for k, sl in enumerate(rows):
            name = sl["sublibrary"]
            self._prog(10 + 30 * k // max(1, len(rows)), f"Reading {name}")
            m = _read_dge(self.dir / "reads" / name / f"{name}_G{g}_matrix.txt.gz")
            m = m[np.asarray((m.X > 0).sum(1)).ravel() >= g]
            m.obs_names = [f"{experiment}_{sl['library_id']}_{b}" for b in m.obs_names]
            parts.append(m)
        others = []
        if use_atlas:
            self._prog(50, "Reading the atlas or dataset to merge in")
            atlas = sc.read_10x_mtx(self.params["atlas_dir"], var_names="gene_symbols", cache=False)
            atlas.var_names_make_unique()
            if not all(f"{atlas_prefix}_lib_" in n for n in atlas.obs_names[:50]):
                atlas.obs_names = [f"{atlas_prefix}_{n}" for n in atlas.obs_names]
            atlas.var = pd.DataFrame(index=atlas.var_names)
            others = [atlas]
        self._prog(75, "Joining on shared genes" if use_atlas else "Combining sublibraries")
        a = ad.concat(parts + others, join="outer", fill_value=0) if len(parts + others) > 1 else parts[0].copy()
        a.X = spm.csr_matrix(a.X)
        a.write_h5ad(self._ckpt("combined"))
        self.adata = a
        merged = {"cells": int(a.n_obs), "genes": int(a.n_vars), "experiment_cells": int(sum(x.n_obs for x in parts)),
                  "atlas_cells": int(sum(x.n_obs for x in others)), "with_atlas": use_atlas}
        self.state.update(step="merged", experiment=experiment, merged=merged)
        self._record("combined sublibraries" + (" and merged in an atlas" if use_atlas else " (no atlas)"),
                     experiment=experiment, min_genes_per_cell=g, atlas=self.params.get("atlas_dir") if use_atlas else None, **merged)

    # ---------------------------------------------------------------- 10 label
    def libraries(self):
        if not self._ckpt("combined").exists():
            return []
        a = sc.read_h5ad(self._ckpt("combined"), backed="r")
        parts = a.obs_names.to_series().str.extract(CELL_ID)
        return parts.groupby(["library", "experiment"]).size().reset_index(name="cells").to_dict(orient="records")

    def label(self, table: dict, columns: list[str], sheets: dict[str, str]):
        return self._background(self._label, table, columns, sheets)

    def _label(self, table, columns, sheets):
        self._prog(20, "Applying library table")
        a = sc.read_h5ad(self._ckpt("combined"))
        cfg = {"labelling": {"cell_id_regex": CELL_ID, "columns": columns, "libraries": table, "barcode_sheets": sheets,
                             "unique_id": ["Experiment", "Library"] + columns}}
        a.obs = label_mod.build_obs(a, cfg)
        a.write_h5ad(self._ckpt("labelled"))
        self.adata = a
        self.state.update(step="labelled", label_columns=columns, library_table=table, sheets=sheets)
        self._record("labelled cells", columns=columns, libraries=table, barcode_sheets=sheets)

    def unique_counts(self):
        a = self.adata
        return a.obs["Unique"].value_counts().sort_index().to_dict() if a is not None and "Unique" in a.obs else {}

    # ---------------------------------------------------------------- 11 QC
    def _labelled(self):
        return sc.read_h5ad(self._ckpt("labelled"))

    def qc_data(self):
        a = self._labelled()
        umis = np.asarray(a.X.sum(1)).ravel()
        genes = np.asarray((a.X > 0).sum(1)).ravel()
        edges = np.linspace(np.log10(20), np.log10(max(umis.max(), 100) * 1.1), 61)
        gedges = np.linspace(np.log10(10), np.log10(max(genes.max(), 50) * 1.1), 61)
        out = {"umi_edges": (10 ** edges).round(1).tolist(), "gene_edges": (10 ** gedges).round(1).tolist(), "groups": {}}
        for grp in a.obs["Experiment"].cat.categories:
            m = (a.obs["Experiment"] == grp).values
            out["groups"][grp] = {"umi": np.histogram(np.log10(np.maximum(umis[m], 20)), edges)[0].tolist(),
                                  "gene": np.histogram(np.log10(np.maximum(genes[m], 10)), gedges)[0].tolist()}
        # Scatter sample for the genes-vs-UMIs plot.
        idx = np.random.default_rng(0).choice(a.n_obs, min(6000, a.n_obs), replace=False)
        out["scatter"] = {"umi": umis[idx].astype(int).tolist(), "gene": genes[idx].astype(int).tolist(),
                          "group": a.obs["Experiment"].values[idx].astype(str).tolist()}
        out["thresholds"] = self.state.get("qc", {"min_counts": 50, "max_counts": int(np.quantile(umis, .99)) + 1,
                                                    "min_genes": 50, "max_genes": int(np.quantile(genes, .99)) + 1})
        return out

    def qc_preview(self, min_counts, max_counts, min_genes, max_genes):
        a = self.adata if self.state.get("step") == "labelled" else self._labelled()
        umis = np.asarray(a.X.sum(1)).ravel(); genes = np.asarray((a.X > 0).sum(1)).ravel()
        keep = (umis >= min_counts) & (umis < max_counts) & (genes >= min_genes) & (genes < max_genes)
        per = pd.DataFrame({"u": a.obs["Unique"].values, "k": keep}).groupby("u", observed=True)["k"].agg(["sum", "count"])
        return {"kept": int(keep.sum()), "total": int(a.n_obs),
                "per_sample": [{"sample": i, "kept": int(r["sum"]), "total": int(r["count"])} for i, r in per.iterrows()]}

    def qc_apply(self, min_counts, max_counts, min_genes, max_genes):
        t = {"min_counts": int(min_counts), "max_counts": int(max_counts), "min_genes": int(min_genes), "max_genes": int(max_genes)}
        return self._background(self._qc_apply, t)

    def _qc_apply(self, t):
        self._prog(30, "Filtering cells")
        a = self._labelled()
        before = int(a.n_obs)
        sc.pp.filter_cells(a, min_counts=t["min_counts"]); sc.pp.filter_cells(a, min_genes=t["min_genes"])
        sc.pp.calculate_qc_metrics(a, percent_top=None, log1p=False, inplace=True)
        a = a[(a.obs["n_genes_by_counts"] < t["max_genes"]) & (a.obs["total_counts"] < t["max_counts"])].copy()
        a.write_h5ad(self._ckpt("filtered"))
        self.adata = a
        self.state.update(step="filtered", qc=t)
        self._record("filtered cells", **t, cells_before=before, cells_after=int(a.n_obs))

    # ---------------------------------------------------------------- 12 cluster
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
            cats = list(s.cat.categories) if s.dtype.name == "category" else sorted(s.astype(str).unique())
            codes = pd.Categorical(s.astype(str), categories=[str(c) for c in cats]).codes[i]
            return {"kind": "cat", "categories": [str(c) for c in cats], "colors": [PALETTE[k % len(PALETTE)] for k in range(len(cats))], "codes": codes.tolist()}
        if a.raw is not None and key in a.raw.var_names:
            v = a.raw[:, key].X
            v = np.asarray(v.toarray() if spm.issparse(v) else v).ravel()[i]
            return {"kind": "num", "values": np.round(v, 3).tolist(), "max": float(v.max() or 1), "gene": key, "label": self._annotator().best_hit(key) if self._annotator() else ""}
        raise KeyError(f"'{key}' is not a column or gene")

    def _annotator(self):
        if self._annot is None:
            path = self.params.get("annotation_table")
            self._annot = report_mod.DiamondAnnotator.from_file(Path(path), self.diamond_cfg) if path and Path(path).exists() else False
        return self._annot or None

    def genes(self, q, n=15):
        names = self.adata.raw.var_names if self.adata.raw is not None else self.adata.var_names
        hits = [g for g in names if q.lower() in g.lower()][:n]
        ann = self._annotator()
        if ann and len(hits) < n:
            for g, rows in ann.groups.items():
                if len(hits) >= n:
                    break
                if g in names and g not in hits and rows["match"].astype(str).str.contains(q, case=False, regex=False).any():
                    hits.append(g)
        return [{"gene": g, "name": ann.best_hit(g) if ann else ""} for g in hits]

    # ---------------------------------------------------------------- 13–14 markers
    def markers(self, cluster, n=25):
        df = report_mod.marker_frame(self.adata, "markers", str(cluster))
        df = df[(df["pvals_adj"] < .05) & (df["logfoldchanges"] > 0)].head(n)
        ann = self._annotator()
        a = self.adata
        cl = (a.obs["cluster"] == str(cluster)).values
        out = []
        for _, r in df.iterrows():
            x = a.raw[:, r["names"]].X
            x = np.asarray(x.toarray() if spm.issparse(x) else x).ravel() > 0
            out.append({"gene": r["names"], "name": ann.best_hit(r["names"]) if ann else "", "logfc": round(float(r["logfoldchanges"]), 2),
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
        ann = self._annotator()
        return {"genes": genes, "names": [ann.best_hit(g) if ann else "" for g in genes], "groups": [str(g) for g in groups], "frac": frac, "mean": mean}

    # ---------------------------------------------------------------- 15 annotate
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

    def export(self, group):
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
