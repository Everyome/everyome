"""Stage 14 — per-cluster marker tables (Excel) and marker UMAP sheets (PDF).

Input : preprocessed.h5ad, DIAMOND/NCBI gene annotation table
Output: <results_dir>/marker_reports/
          <layer>_markers_wilcoxon_significant.xlsx  all genes with p < cutoff and logFC > 0
          wilcoxon/<layer>_markers_top<N>.xlsx         top N wilcoxon genes per cluster
          logreg/<layer>_markers_top<N>.xlsx           top N logreg genes per cluster
          wilcoxon/umap_<layer>_cluster_<c>.pdf        cluster + 15 consensus markers
          logreg/umap_<layer>_cluster_<c>.pdf          cluster + top 15 logreg markers
        One sheet / PDF per cluster. Each gene gets a readable name from DIAMOND.

"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import scanpy as sc
import seaborn as sns

import common

UMAP_CMAP = sns.blend_palette(["lightgrey", "xkcd:blurple"], as_cmap=True)


# --- Gene annotation ----------------------------------------------------------

class DiamondAnnotator:
    """Pick the most informative description for a gene from DIAMOND/NCBI hits.

    best_hit(gene):    preferred-species DIAMOND hit, else the first hit
                       without an uninformative word, else
                       "no informative hits: <first hit>", or "not in Diamond".
    ncbi_label(gene):  NCBI name if it mentions the preferred NCBI species,
                       else the first informative DIAMOND hit, else the first
                       NCBI name, or "other RNA" when the gene has no rows.
                       
    """

    def __init__(self, table: pd.DataFrame, cfg: dict):
        self.cfg = cfg
        self.words = [w.lower() for w in cfg["uninformative_words"]]
        self.groups = {g: df.reset_index(drop=True) for g, df in table.groupby("gene_id", sort=False)}

    @classmethod
    def from_file(cls, path: Path, cfg: dict):
        table = pd.read_csv(path, sep="\t", usecols=cfg["diamond_columns"])
        table.columns = cfg["diamond_names"]
        common.log.info("DIAMOND table: %d rows, %d genes", len(table), table["gene_id"].nunique())
        return cls(table, cfg)

    def _informative(self, text) -> bool:
        return isinstance(text, str) and not any(w in text.lower() for w in self.words)

    def _preferred(self, rows: pd.DataFrame, column: str, species: str):
        if not species:                       # Everyome: no preferred species chosen
            return None
        hits = rows[rows[column].str.contains(species, na=False, regex=False)]
        if hits.empty:
            return None
        if self.cfg["preferred_hit_order"] == "alphabetical":
            hits = hits.sort_values(column)
        return hits[column].iloc[0]

    def _first_informative_match(self, rows: pd.DataFrame):
        for text in rows["match"]:
            if self._informative(text):
                return text
        return None

    def best_hit(self, gene: str) -> str:
        rows = self.groups.get(gene)
        if rows is None:
            return "not in Diamond"
        hit = self._preferred(rows, "match", self.cfg["preferred_species"])
        if hit is not None:
            return hit
        hit = self._first_informative_match(rows)
        return hit if hit is not None else f"no informative hits: {rows['match'].iloc[0]}"

    def ncbi_label(self, gene: str) -> str:
        rows = self.groups.get(gene)
        if rows is None:
            return "other RNA"
        hit = self._preferred(rows, "ncbi_name", self.cfg["preferred_species_ncbi"])
        if hit is not None:
            return hit
        hit = self._first_informative_match(rows)
        return hit if hit is not None else str(rows["ncbi_name"].iloc[0])

    def annotate(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["diamond"] = df["names"].map(self.best_hit)
        df["ncbi_name"] = df["names"].map(self.ncbi_label)
        return df


# --- Marker extraction ----------------------------------------------------------

def marker_frame(adata, key: str, cluster: str) -> pd.DataFrame:
    """Ranked markers of one cluster from uns[key], with whatever fields exist."""
    res = adata.uns[key]
    fields = [f for f in ["names", "logfoldchanges", "pvals", "pvals_adj", "scores"] if f in res]
    return pd.DataFrame({f: pd.DataFrame(res[f])[cluster] for f in fields})


def significant_up(df: pd.DataFrame, pval_cutoff: float) -> pd.DataFrame:
    """Upregulated, nominally significant markers, in rank order."""
    return df[(df["pvals"] < pval_cutoff) & (df["logfoldchanges"] > 0)]


def write_workbook(path: Path, frames: dict[str, pd.DataFrame]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path) as writer:
        for cluster, df in frames.items():
            df.reset_index(drop=True).to_excel(writer, sheet_name=f"Cluster {cluster}")
    common.log.info("wrote %s", path)


# --- PDF sheets -----------------------------------------------------------------

def marker_sheet(adata, layer: str, cluster: str, genes: list[str], n_genes: int,
                 annot: DiamondAnnotator | None = None):
    """4×4 grid: the cluster highlighted, then up to `n_genes` marker UMAPs.

    Panel titles show the gene ID and, if an annotator is given, its DIAMOND hit.
    """
    fig, axs = plt.subplots(4, 4, figsize=(15, 15))
    axs = axs.ravel()
    sc.pl.umap(adata, color=layer, groups=[cluster], legend_loc="on data", na_in_legend=False,
               size=5, legend_fontsize=7, title=f"{layer} cluster {cluster}", show=False, ax=axs[0])
    genes = genes[:n_genes]
    for ax, gene in zip(axs[1:], genes):
        title = gene if annot is None else f"{gene}\n{annot.best_hit(gene)[:40]}"
        sc.pl.umap(adata, color=gene, title=title, color_map=UMAP_CMAP, show=False, ax=ax)
    for ax in axs[1 + len(genes):]:
        ax.axis("off")
    fig.tight_layout()
    return fig


def save_sheet(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, format="pdf")
    plt.close(fig)


# --- Main -----------------------------------------------------------------------

def main():
    cfg = common.start("14_reports", __doc__)
    rp = cfg["reports"]
    layer = cfg["clustering_layer"]
    out = cfg.results_dir / "marker_reports"
    wil_key, lr_key = f"rank_genes_groups_{layer}", f"rank_genes_groups_logreg_{layer}"

    adata = common.read_h5ad(cfg, "preprocessed")
    annot = DiamondAnnotator.from_file(cfg.path("diamond_table"), rp)
    clusters = list(adata.obs[layer].cat.categories)
    has_logreg = lr_key in adata.uns

    sig, top_wil, top_lr = {}, {}, {}
    for c in clusters:
        wil = marker_frame(adata, wil_key, c)
        sig[c] = annot.annotate(significant_up(wil, rp["pval_cutoff"]))
        top_wil[c] = annot.annotate(wil.head(rp["top_n_table"]))
        if has_logreg:
            top_lr[c] = annot.annotate(marker_frame(adata, lr_key, c).head(rp["top_n_table"]))
        common.log.info("cluster %s: %d significant upregulated markers", c, len(sig[c]))

    write_workbook(out / f"{layer}_markers_wilcoxon_significant.xlsx", sig)
    write_workbook(out / "wilcoxon" / f"{layer}_markers_top{rp['top_n_table']}.xlsx", top_wil)
    if has_logreg:
        write_workbook(out / "logreg" / f"{layer}_markers_top{rp['top_n_table']}.xlsx", top_lr)
    else:
        common.log.warning("%s not found; logreg outputs skipped", lr_key)

    for c in clusters:
        # Intent: consensus markers = significant wilcoxon genes also in the logreg top pool.
        wil_genes = sig[c]["names"]
        if has_logreg:
            pool = set(marker_frame(adata, lr_key, c)["names"].head(rp["pdf_logreg_pool"]))
            wil_genes = wil_genes[wil_genes.isin(pool)]
        save_sheet(marker_sheet(adata, layer, c, wil_genes.tolist(), rp["pdf_genes"], annot),
                   out / "wilcoxon" / f"umap_{layer}_cluster_{c}.pdf")
        if has_logreg:
            lr_genes = marker_frame(adata, lr_key, c)["names"].head(rp["pdf_genes"]).tolist()
            save_sheet(marker_sheet(adata, layer, c, lr_genes, rp["pdf_genes"], annot),
                       out / "logreg" / f"umap_{layer}_cluster_{c}.pdf")


if __name__ == "__main__":
    main()
