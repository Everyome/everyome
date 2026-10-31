"""Stage 13 — exploratory plots of clusters, samples and known marker genes.

Input : preprocessed.h5ad
Output: figures only (no data changes):
        QC violins per cluster / sample / batch, marker heatmap + matrixplot,
        UMAPs highlighting each value of each metadata column, one UMAP per
        known marker, a known-marker dotplot, and focus-gene plots on a
        chosen subset of cells.

"""
from __future__ import annotations

from matplotlib.pyplot import rc_context
import matplotlib.pyplot as plt
import scanpy as sc

import common

QC_KEYS = ["n_genes", "total_counts", "n_counts"]


def safe_name(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text)


def present(adata, genes: dict[str, str]) -> dict[str, str]:
    """Keep markers whose gene ID exists in .raw; warn about the rest."""
    names = adata.raw.var_names if adata.raw is not None else adata.var_names
    missing = {k: v for k, v in genes.items() if v not in names}
    for label, gid in missing.items():
        common.log.warning("marker %s (%s) not in matrix; skipped", label, gid)
    return {k: v for k, v in genes.items() if k not in missing}


def main():
    cfg = common.start("13_markers", __doc__)
    layer = cfg["clustering_layer"]
    mk = cfg["markers"]
    adata = common.read_h5ad(cfg, "preprocessed")

    # --- Cluster overview and per-group QC --------------------------------------
    with rc_context({"figure.figsize": (12, 12)}):
        sc.pl.umap(adata, color=layer, legend_loc="on data", legend_fontoutline=2,
                   title=f"Clustering layer {layer}", size=5, frameon=False, save=f"_{layer}_overview.png")
    with rc_context({"figure.figsize": (15, 5)}):
        for key in QC_KEYS:
            sc.pl.violin(adata, keys=key, groupby=layer, jitter=False, save=f"_{key}_by_{layer}.png")
    # Intent: QC per metadata column, to spot one library driving a cluster.
    for group in cfg["labelling"]["columns"] + ["Unique"]:
        sc.pl.violin(adata, keys=QC_KEYS, groupby=group, log=True, jitter=False,
                     multi_panel=True, rotation=90, save=f"_qc_by_{group}.png")

    key = f"rank_genes_groups_{layer}"
    sc.pl.rank_genes_groups_heatmap(adata, n_genes=4, key=key, save=f"_{layer}.png")
    sc.pl.rank_genes_groups_matrixplot(adata, n_genes=4, key=key, save=f"_{layer}.png")

    # --- Where each sample type sits on the shared UMAP -------------------------
    for column in cfg["labelling"]["columns"]:
        for value in adata.obs[column].cat.categories:
            with rc_context({"figure.figsize": (10, 10)}):
                sc.pl.umap(adata, color=column, groups=[value], title=value, size=10,
                           frameon=False, save=f"_{column}_{safe_name(value)}.png")

    # --- Known markers -----------------------------------------------------------
    known = present(adata, mk["known"])
    for label, gid in known.items():
        with rc_context({"figure.figsize": (10, 10)}):
            sc.pl.umap(adata, color=gid, title=label, color_map=plt.cm.Reds, size=10,
                       frameon=False, save=f"_marker_{safe_name(label)}.png")
    sc.pl.dotplot(adata, list(known.values()), groupby=layer, dendrogram=True,
                  swap_axes=True, cmap=plt.cm.Reds, save=f"_known_markers_{layer}.png")

    # --- Focus genes, all cells vs aggregate cells only -------------------------
    sub = mk["focus_subset"]
    subset = adata[adata.obs[sub["column"]] == sub["value"]].copy()
    common.log.info("focus subset %s == %s: %d cells", sub["column"], sub["value"], subset.n_obs)
    for label in mk["focus_genes"]:
        gid = known.get(label)
        if gid is None:
            continue
        tag = safe_name(label)
        with rc_context({"figure.figsize": (10, 10)}):
            sc.pl.umap(subset, color=gid, title=f"{label} ({sub['value']})", color_map=plt.cm.Reds,
                       size=10, frameon=False, save=f"_focus_{tag}_{sub['value']}.png")
        sc.pl.dotplot(adata, gid, groupby=layer, dendrogram=True, swap_axes=True,
                      cmap=plt.cm.Reds, save=f"_focus_{tag}_all.png")
        sc.pl.dotplot(subset, gid, groupby=layer, dendrogram=True, swap_axes=True,
                      cmap=plt.cm.Reds, save=f"_focus_{tag}_{sub['value']}.png")


if __name__ == "__main__":
    main()
