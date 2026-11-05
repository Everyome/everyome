"""Readers for imaging-based spatial platforms: each returns cells × genes (raw counts, control probes left out) with
each cell's position in obsm['spatial'], from the files the instrument's software writes.

  xenium    10x Xenium 'outs': cell_feature_matrix (.h5 or folder) and cells (.parquet or .csv.gz); positions in µm
  merscope  Vizgen MERSCOPE: cell_by_gene.csv and cell_metadata.csv; positions in µm
  cosmx     Bruker (NanoString) CosMx: *exprMat_file.csv and *metadata_file.csv; positions in pixels (global)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import scanpy as sc
import scipy.sparse as sp

# Intent: control probes and codewords measure background, not genes; leave them out of the analysis.
CONTROL = ("NegControl", "Negative", "BLANK", "Blank-", "Unassigned", "Deprecated", "NegPrb", "SystemControl", "antisense", "Intergenic")
UNITS = {"xenium": "µm", "merscope": "µm", "cosmx": "px"}


def _genes_only(names) -> np.ndarray:
    return np.array([not any(str(n).startswith(c) for c in CONTROL) for n in names])


def detect(folder: Path) -> str:
    f = Path(folder)
    if (f / "cell_feature_matrix.h5").exists() or (f / "cell_feature_matrix").is_dir() or (f / "experiment.xenium").exists():
        return "xenium"
    if (f / "cell_by_gene.csv").exists():
        return "merscope"
    if next(f.glob("*exprMat_file.csv*"), None):
        return "cosmx"
    return ""


def read_xenium(f: Path) -> sc.AnnData:
    if (f / "cell_feature_matrix.h5").exists():
        a = sc.read_10x_h5(f / "cell_feature_matrix.h5")
    elif (f / "cell_feature_matrix").is_dir():
        a = sc.read_10x_mtx(f / "cell_feature_matrix", var_names="gene_symbols", cache=False)
    else:
        raise FileNotFoundError(f"{f} has no cell_feature_matrix (.h5 or folder).")
    cells_file = next((f / n for n in ("cells.parquet", "cells.csv.gz", "cells.csv") if (f / n).exists()), None)
    if cells_file is None:
        raise FileNotFoundError(f"{f} has no cells.parquet or cells.csv.gz (cell positions).")
    cells = pd.read_parquet(cells_file) if cells_file.suffix == ".parquet" else pd.read_csv(cells_file)
    cells["cell_id"] = cells["cell_id"].astype(str)
    cells = cells.set_index("cell_id").reindex(a.obs_names.astype(str))
    a.obsm["spatial"] = cells[["x_centroid", "y_centroid"]].to_numpy(float)
    if "cell_area" in cells:
        a.obs["cell_area"] = cells["cell_area"].to_numpy(float)
    return a


def read_merscope(f: Path) -> sc.AnnData:
    counts = pd.read_csv(f / "cell_by_gene.csv", index_col=0)
    meta = pd.read_csv(f / "cell_metadata.csv", index_col=0)
    counts.index, meta.index = counts.index.astype(str), meta.index.astype(str)
    keep = _genes_only(counts.columns)
    meta = meta.reindex(counts.index)
    a = sc.AnnData(sp.csr_matrix(counts.loc[:, keep].to_numpy(np.float32)), obs=pd.DataFrame(index=counts.index),
                   var=pd.DataFrame(index=counts.columns[keep].astype(str)))
    a.obsm["spatial"] = meta[["center_x", "center_y"]].to_numpy(float)
    if "volume" in meta:
        a.obs["cell_volume"] = meta["volume"].to_numpy(float)
    return a


def read_cosmx(f: Path) -> sc.AnnData:
    expr_file, meta_file = next(f.glob("*exprMat_file.csv*")), next(f.glob("*metadata_file.csv*"))
    expr, meta = pd.read_csv(expr_file), pd.read_csv(meta_file)
    key = lambda d: d["fov"].astype(str) + "_" + d["cell_ID"].astype(str)
    expr.index, meta.index = key(expr), key(meta)
    expr = expr[expr["cell_ID"] != 0]                      # cell 0 holds transcripts outside any cell
    genes = [c for c in expr.columns if c not in ("fov", "cell_ID")]
    keep = np.array(genes)[_genes_only(genes)]
    meta = meta.reindex(expr.index)
    a = sc.AnnData(sp.csr_matrix(expr[keep].to_numpy(np.float32)), obs=pd.DataFrame(index=expr.index), var=pd.DataFrame(index=keep))
    a.obsm["spatial"] = meta[["CenterX_global_px", "CenterY_global_px"]].to_numpy(float)
    a.obs["fov"] = meta["fov"].astype(str).values
    return a


READERS = {"xenium": read_xenium, "merscope": read_merscope, "cosmx": read_cosmx}


def read(folder: str, platform: str = "") -> tuple[sc.AnnData, str]:
    f = Path(folder)
    platform = platform or detect(f)
    if platform not in READERS:
        raise ValueError(f"Couldn't tell which instrument made {f}. Choose its output folder (Xenium 'outs', or the MERSCOPE "
                         "or CosMx export folder), or set the platform in the table.")
    a = READERS[platform](f)
    a.var_names_make_unique()
    ok = np.isfinite(a.obsm["spatial"]).all(1)
    return a[ok].copy(), platform
