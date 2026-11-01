"""SPLiTscape part 2 as an Everyome engine: stages 09–15 as interactive steps.

Merging with an existing atlas or dataset is optional: without one, the
sublibraries are analysed on their own (for example, to build a first atlas).

This file holds the SPLiT-seq steps (combine sublibraries, label cells) and gene
names from a DIAMOND-style annotation table; filtering, clustering, markers,
naming and export are shared with other single-cell modules (../cells.py).
Ported from SPLiTscape (Helen R Horkan PhD).
"""
from __future__ import annotations

from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
import scanpy as sc
import scipy.sparse as spm

from ..cells import CellsEngine, _pipeline, report_mod

label_mod = _pipeline("10_label_cells.py")
CELL_ID = r"(?P<experiment>[A-Za-z0-9]+)_(?P<library>lib_\d+_\d+)_(?P<barcode>[ACGTN]+)$"


def _read_dge(path):
    df = pd.read_csv(path, sep="\t", index_col=0)
    return ad.AnnData(X=spm.csr_matrix(df.values.T.astype(np.float32)), obs=pd.DataFrame(index=df.columns), var=pd.DataFrame(index=df.index))


class Engine(CellsEngine):
    API = ("merge", "libraries", "label", "unique_counts") + CellsEngine.SHARED_API
    REPLAY = ("merge", "label") + CellsEngine.SHARED_REPLAY
    GROUP, SAMPLE, HIDDEN = "Experiment", "Unique", ("Unique", "cluster")
    BEFORE_QC = "labelled"
    CHECKPOINTS = ("clustered", "filtered", "labelled", "combined")
    STATUS_KEYS = ("experiment", "merged", "library_table", "label_columns", "sheets", "qc", "cluster_params")

    def __init__(self, run_dir: str):
        self._annot = None
        super().__init__(run_dir)
        # Intent: gene-name preferences are run settings now, not built-in Hydra defaults.
        self.diamond_cfg = {"diamond_columns": [1, 6, 7], "diamond_names": ["gene_id", "match", "ncbi_name"],
                            "preferred_species": self.params.get("preferred_species", ""),
                            "preferred_species_ncbi": self.params.get("preferred_species_ncbi", ""),
                            "uninformative_words": ["hypothetical", "uncharacterized", "unnamed"], "preferred_hit_order": "file"}

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

    # ---------------------------------------------------------------- gene names (DIAMOND-style annotation table)
    def _annotator(self):
        if self._annot is None:
            path = self.params.get("annotation_table")
            self._annot = report_mod.DiamondAnnotator.from_file(Path(path), self.diamond_cfg) if path and Path(path).exists() else False
        return self._annot or None

    def _gene_name(self, gene):
        ann = self._annotator()
        return ann.best_hit(gene) if ann else ""

    def _search_names(self, q, names, hits, n):
        ann = self._annotator()
        if ann and len(hits) < n:
            for g, rows in ann.groups.items():
                if len(hits) >= n:
                    break
                if g in names and g not in hits and rows["match"].astype(str).str.contains(q, case=False, regex=False).any():
                    hits.append(g)
        return hits
