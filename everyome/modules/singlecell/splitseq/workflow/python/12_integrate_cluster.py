"""Stage 12 — normalise, integrate batches, embed, cluster and rank markers.

Input : sliced.h5ad (raw counts)
Output: preprocessed.h5ad with
        .raw            log-normalised expression of all genes (used for markers/plots)
        .X              scaled highly variable genes
        obsm            X_pca, X_pca_harmony, X_umap
        obs             leiden_<res> for each resolution
        uns             rank_genes_groups[_logreg]_leiden_<res>
        figures: umap_leiden_<res>.png, pca_variance_ratio.png, marker rank plots

"""
from __future__ import annotations

from matplotlib.pyplot import rc_context
import scanpy as sc
import harmonypy
import numpy as np

import common


def marker_key(method: str, layer: str) -> str:
    """uns key for a marker result (wilcoxon has no method suffix)."""
    return f"rank_genes_groups_{layer}" if method == "wilcoxon" else f"rank_genes_groups_{method}_{layer}"


def harmony(adata, key: str, random_state: int) -> None:
    """Harmony on X_pca -> obsm['X_pca_harmony'].

    Calls harmonypy directly (same as sce.pp.harmony_integrate) but accepts
    either output orientation, since newer harmonypy releases transposed Z_corr.
    """
    out = harmonypy.run_harmony(adata.obsm["X_pca"], adata.obs, key, random_state=random_state)
    z = np.asarray(out.Z_corr)
    adata.obsm["X_pca_harmony"] = z if z.shape[0] == adata.n_obs else z.T


def main():
    cfg = common.start("12_integrate", __doc__)
    p = cfg["integrate"]
    adata = common.read_h5ad(cfg, "sliced")

    # Intent: library-size normalise to 10k UMIs, then log1p.
    sc.pp.normalize_total(adata, target_sum=p["target_sum"])
    sc.pp.log1p(adata)

    # Intent: keep all genes in .raw for markers; model on highly variable genes.
    sc.pp.highly_variable_genes(adata, n_top_genes=p["n_top_genes"])
    sc.pl.highly_variable_genes(adata, save=".png")
    adata.raw = adata
    adata = adata[:, adata.var["highly_variable"]].copy()
    common.log.info("%d highly variable genes", adata.n_vars)

    # Intent: z-score genes, reduce to PCs, then remove batch effects with Harmony.
    sc.pp.scale(adata)
    sc.tl.pca(adata, svd_solver="arpack", n_comps=p["n_pcs_compute"], random_state=p["random_state"])
    sc.pl.pca_variance_ratio(adata, n_pcs=p["n_pcs_compute"], log=True, save=".png")
    harmony(adata, p["harmony_key"], p["random_state"])

    # Intent: neighbour graph on the corrected PCs drives both UMAP and Leiden.
    sc.pp.neighbors(adata, n_neighbors=p["n_neighbors"], n_pcs=p["n_pcs_neighbors"],
                    use_rep="X_pca_harmony", random_state=p["random_state"])
    sc.tl.umap(adata, min_dist=p["umap_min_dist"], spread=p["umap_spread"], random_state=p["random_state"])
    sc.pl.umap(adata, color=p["harmony_key"], save=f"_{p['harmony_key']}.png")

    for res in p["leiden_resolutions"]:
        layer = f"leiden_{res}"
        sc.tl.leiden(adata, resolution=res, key_added=layer, random_state=p["random_state"])
        common.log.info("%s: %d clusters", layer, adata.obs[layer].nunique())
        with rc_context({"figure.figsize": (15, 15)}):
            sc.pl.umap(adata, color=layer, legend_loc="on data", title=layer, size=50,
                       frameon=False, save=f"_{layer}.png")

        # Intent: rank genes per cluster vs rest (uses .raw, i.e. all genes).
        for method in p["marker_methods"]:
            key = marker_key(method, layer)
            sc.tl.rank_genes_groups(adata, layer, method=method, key_added=key)
            sc.pl.rank_genes_groups(adata, key=key, n_genes=10, sharey=False, save=f"_{method}.png")

    common.write_h5ad(adata, cfg, "preprocessed")


if __name__ == "__main__":
    main()
