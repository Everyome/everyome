"""Stage 11 — remove low-quality and outlier cells.

Input : fully_labelled.h5ad
Output: sliced.h5ad (raw counts, filtered; also the input for pseudobulk work)
        figures: qc_violin_before.png, qc_violin_after.png, qc_scatter_*.png

"""
from __future__ import annotations

import scanpy as sc

import common

QC_KEYS = ["n_genes_by_counts", "total_counts"]


def qc_metrics(adata, mito_prefix):
    qc_vars = []
    if mito_prefix:
        adata.var["mt"] = adata.var_names.str.startswith(mito_prefix)
        qc_vars = ["mt"]
    sc.pp.calculate_qc_metrics(adata, qc_vars=qc_vars, percent_top=None, log1p=False, inplace=True)
    return QC_KEYS + (["pct_counts_mt"] if mito_prefix else [])


def plot_qc(adata, keys, tag):
    sc.pl.violin(adata, keys, jitter=0.4, multi_panel=True, log=True, save=f"_qc_{tag}.png")
    sc.pl.scatter(adata, x="total_counts", y="n_genes_by_counts", save=f"_qc_{tag}.png")
    sc.pl.highest_expr_genes(adata, n_top=20, save=f"_qc_{tag}.png")


def main():
    cfg = common.start("11_qc", __doc__)
    qc = cfg["qc"]
    adata = common.read_h5ad(cfg, "fully_labelled")

    # Intent: drop barcodes with too few UMIs or genes (one pass is enough).
    sc.pp.filter_cells(adata, min_counts=qc["min_counts"])
    sc.pp.filter_cells(adata, min_genes=qc["min_genes"])
    keys = qc_metrics(adata, qc["mito_prefix"])
    plot_qc(adata, keys, "before")

    # Intent: remove high-complexity outliers (strict "<").
    n0 = adata.n_obs
    keep = (adata.obs["n_genes_by_counts"] < qc["max_genes"]) & (adata.obs["total_counts"] < qc["max_counts"])
    adata = adata[keep].copy()
    common.log.info("upper-bound filter removed %d of %d cells", n0 - adata.n_obs, n0)

    qc_metrics(adata, qc["mito_prefix"])
    plot_qc(adata, keys, "after")
    common.log_counts(adata)
    common.write_h5ad(adata, cfg, "sliced")


if __name__ == "__main__":
    main()
