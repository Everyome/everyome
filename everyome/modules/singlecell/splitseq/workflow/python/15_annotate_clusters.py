"""Stage 15 — transfer cluster identities and colours; compare groups.

Input : preprocessed.h5ad, cluster identity sheet (Cluster, Broad_Type, Hex, ...)
Output: annotated.h5ad (obs Broad_Type; uns <layer>_colors / _colors_sorted / _sorted)
        <results_dir>/composition/broad_type_counts.csv      cells per type × group
        <results_dir>/composition/broad_type_fractions.csv   same, as fractions
        figures: UMAPs by palette columns and broad type, composition bars

"""
from __future__ import annotations

from matplotlib.pyplot import rc_context
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scanpy as sc

import common


def load_identities(path, n_clusters: int, cols: dict) -> pd.DataFrame:
    """Identity sheet indexed by cluster ID (as string), in the sheet's row order."""
    df = pd.read_excel(path, index_col="Cluster")
    df.index = df.index.astype(str)
    if len(df) != n_clusters:
        raise ValueError(f"identity sheet has {len(df)} rows but the clustering has {n_clusters} clusters")
    missing = [c for c in cols.values() if c not in df.columns]
    if missing:
        raise ValueError(f"identity sheet lacks columns {missing}")
    return df


def apply_identities(adata, layer: str, ident: pd.DataFrame, cols: dict) -> dict[str, str]:
    bt, hx = cols["broad_type"], cols["hex"]
    clusters = list(adata.obs[layer].cat.categories)
    unknown = set(clusters) - set(ident.index)
    if unknown:
        raise ValueError(f"clusters missing from identity sheet: {sorted(unknown, key=int)}")

    # Intent: cluster colours in category order (what Scanpy reads), plus the
    # sheet's own display order for ordered plots.
    adata.uns[f"{layer}_colors"] = np.array(ident.loc[clusters, hx])
    adata.uns[f"{layer}_colors_sorted"] = np.array(ident[hx])
    adata.uns[f"{layer}_sorted"] = np.array(ident.index)

    adata.obs[bt] = adata.obs[layer].astype(str).map(ident[bt]).astype("category")
    type_colors = ident.groupby(bt, sort=False)[hx].first().to_dict()
    adata.uns[f"{bt}_colors"] = np.array([type_colors[t] for t in adata.obs[bt].cat.categories])
    return type_colors


def composition_tables(adata, type_col: str, group_col: str):
    counts = pd.crosstab(adata.obs[type_col], adata.obs[group_col])
    counts["All"] = counts.sum(axis=1)
    return counts, counts / counts.sum(axis=0)


def bar_plot(series: pd.Series, colors: dict, title: str, ylabel: str, path):
    s = series.sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(15, 6))
    ax.bar(s.index, s.values, color=[colors.get(t, "grey") for t in s.index])
    ax.grid(False)
    ax.set(xlabel="Broad type", ylabel=ylabel, title=title)
    ax.tick_params(axis="x", rotation=90)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main():
    cfg = common.start("15_annotate", __doc__)
    an = cfg["annotate"]
    layer, cols, group = cfg["clustering_layer"], an["identity_columns"], an["group_column"]
    adata = common.read_h5ad(cfg, "preprocessed")

    # --- Metadata UMAPs with fixed palettes ----------------------------------
    for column, palette in an["palettes"].items():
        cats = adata.obs[column].cat.categories
        adata.uns[f"{column}_colors"] = [palette.get(c, "#D0D0D0") for c in cats]
        for value in cats:
            with rc_context({"figure.figsize": (12, 12)}):
                sc.pl.umap(adata, color=column, groups=[value], title=f"{column}: {value}",
                           size=10, frameon=False, add_outline=True, save=f"_{column}_{value}.png")

    # --- Identities and colours --------------------------------------------------
    ident = load_identities(cfg.path("cluster_identities"), adata.obs[layer].nunique(), cols)
    type_colors = apply_identities(adata, layer, ident, cols)
    with rc_context({"figure.figsize": (12, 12)}):
        sc.pl.umap(adata, color=layer, legend_loc="on data", legend_fontoutline=3, size=10,
                   frameon=False, title=f"Clustering layer {layer}", save=f"_{layer}_coloured.png")
        sc.pl.umap(adata, color=cols["broad_type"], size=10, frameon=False,
                   title="Broad types", save="_broad_types.png")

    # --- Composition per group -----------------------------------------------------
    counts, fractions = composition_tables(adata, cols["broad_type"], group)
    comp_dir = cfg.results_dir / "composition"
    comp_dir.mkdir(exist_ok=True)
    counts.to_csv(comp_dir / "broad_type_counts.csv")
    fractions.to_csv(comp_dir / "broad_type_fractions.csv")
    for g in counts.columns:
        n = int(counts[g].sum())
        if g != "All" and n < an["min_cells_warning"]:
            common.log.warning("%s = %s has only %d cells; its composition is not interpretable", group, g, n)
        bar_plot(counts[g], type_colors, f"Cells per broad type: {g} (n={n})", "Cells",
                 cfg.figures_dir / f"composition_counts_{g}.png")
        bar_plot(fractions[g], type_colors, f"Fraction per broad type: {g} (n={n})", "Fraction of cells",
                 cfg.figures_dir / f"composition_fraction_{g}.png")

    common.write_h5ad(adata, cfg, "annotated")


if __name__ == "__main__":
    main()
