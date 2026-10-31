"""Live session for bulk RNA-seq: check samples, compare conditions with DESeq2 (PyDESeq2), explore and export.

Reads the merged gene counts that nf-core/rnaseq wrote for the run. Each step
is checkpointed to <run>/session/ and recorded in order for the write-up.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from everyome.core.engine import BaseEngine

from .helpers import counts_paths


def size_factors(counts: pd.DataFrame) -> pd.Series:
    """DESeq2's median-of-ratios size factors (samples are columns)."""
    logs = np.log(counts.replace(0, np.nan))
    ref = logs.mean(axis=1)
    ok = ref.notna() & np.isfinite(ref)
    return np.exp((logs[ok].sub(ref[ok], axis=0)).median(axis=0))


class Engine(BaseEngine):
    API = ("overview", "sample_qc", "run_de", "results", "volcano", "ma", "gene", "export", "files")
    REPLAY = ("run_de", "export")

    def __init__(self, run_dir: str):
        super().__init__(run_dir)
        path = next((self.dir / p for p in counts_paths(self.params) if (self.dir / p).exists()), None)
        if path is None:
            raise FileNotFoundError("No gene count table from nf-core/rnaseq was found in this run's results.")
        self.counts_file = str(path.relative_to(self.dir))
        df = pd.read_csv(path, sep="\t")
        df = df.set_index(df.columns[0])
        self.gene_names = df.iloc[:, 0].astype(str) if df.columns[0] in ("gene_name", "gene_symbol") else pd.Series(df.index, index=df.index)
        num = df.select_dtypes("number")
        # Intent: salmon gives estimated counts; DESeq2 needs whole numbers.
        self.counts = num.round().astype(int)
        meta = {r["sample"]: r for r in self.params["samples"]}
        self.missing = [s for s in meta if s not in self.counts.columns]
        self.counts = self.counts[[s for s in meta if s in self.counts.columns]]
        self.meta = pd.DataFrame({"condition": [meta[s]["condition"] for s in self.counts.columns]}, index=self.counts.columns)
        self._res = None

    def status(self):
        return {**super().status(), "samples": list(self.counts.columns), "conditions": sorted(self.meta["condition"].unique()),
                "de": self.state.get("de"), "missing": self.missing}

    # ---------------------------------------------------------------- check samples
    def overview(self):
        c = self.counts
        return {"counts_file": self.counts_file, "genes": int(c.shape[0]), "missing": self.missing,
                "samples": [{"sample": s, "condition": self.meta.loc[s, "condition"], "reads": int(c[s].sum()), "genes": int((c[s] > 0).sum())}
                            for s in c.columns]}

    def sample_qc(self, n_genes: int = 500):
        c = self.counts[self.counts.sum(axis=1) >= 10]
        norm = np.log2(c / size_factors(c) + 1)
        top = norm.loc[norm.var(axis=1).sort_values(ascending=False).index[:min(n_genes, len(norm))]]
        x = (top.T - top.T.mean()).values
        u, sv, _ = np.linalg.svd(x, full_matrices=False)
        var = sv ** 2 / (sv ** 2).sum()
        pcs = u * sv
        corr = np.corrcoef(norm.T.values)
        return {"samples": list(c.columns), "conditions": list(self.meta["condition"]),
                "pc1": pcs[:, 0].round(3).tolist(), "pc2": (pcs[:, 1] if pcs.shape[1] > 1 else np.zeros(len(pcs))).round(3).tolist(),
                "var": [round(float(v) * 100, 1) for v in var[:2]], "corr": np.round(corr, 3).tolist(), "n_genes": int(len(top))}

    # ---------------------------------------------------------------- compare
    def run_de(self, test: str, reference: str, alpha: float = 0.05, min_count: int = 10):
        conds = set(self.meta["condition"])
        if test not in conds or reference not in conds or test == reference:
            raise ValueError("Choose two different conditions to compare.")
        for c in (test, reference):
            if (self.meta["condition"] == c).sum() < 2:
                raise ValueError(f"'{c}' has fewer than two samples; DESeq2 needs replicates to estimate variation.")
        return self._background(self._run_de, test, reference, float(alpha), int(min_count))

    def _run_de(self, test, reference, alpha, min_count):
        from pydeseq2.dds import DeseqDataSet
        from pydeseq2.ds import DeseqStats
        import pydeseq2
        self._prog(10, "Preparing counts")
        keep = self.meta.index[self.meta["condition"].isin([test, reference])]
        c = self.counts[keep]
        c = c[c.sum(axis=1) >= min_count]
        self._prog(25, "Fitting size factors and dispersions")
        dds = DeseqDataSet(counts=c.T, metadata=self.meta.loc[keep], design="~condition", quiet=True)
        dds.deseq2()
        self._prog(75, "Testing each gene")
        st = DeseqStats(dds, contrast=["condition", test, reference], alpha=alpha, quiet=True)
        st.summary()
        res = st.results_df.copy()
        res.insert(0, "gene_name", self.gene_names.reindex(res.index).values)
        res.index.name = "gene_id"
        res.to_csv(self.out / "de_results.csv")
        pd.DataFrame(dds.layers["normed_counts"], index=dds.obs_names, columns=dds.var_names).T.to_csv(self.out / "normalized_counts.csv")
        self._res = res
        sig = res[res["padj"] < alpha]
        de = {"test": test, "reference": reference, "alpha": alpha, "min_count": min_count, "genes_tested": int(len(res)),
              "up": int((sig["log2FoldChange"] > 0).sum()), "down": int((sig["log2FoldChange"] < 0).sum()),
              "samples": list(keep), "pydeseq2": pydeseq2.__version__}
        self.state.update(step="tested", de=de)
        self._record("compared conditions", **de)

    def _results(self):
        if self._res is None:
            path = self.out / "de_results.csv"
            if not path.exists():
                raise ValueError("Compare conditions first.")
            self._res = pd.read_csv(path, index_col=0)
        return self._res

    # ---------------------------------------------------------------- explore
    def results(self, padj: float = 0.05, lfc: float = 0.0, q: str = "", n: int = 200):
        r = self._results()
        sig = r[(r["padj"] < padj) & (r["log2FoldChange"].abs() >= lfc)]
        view = r
        if q:
            view = r[r.index.str.contains(q, case=False, regex=False) | r["gene_name"].astype(str).str.contains(q, case=False, regex=False)]
        else:
            view = sig
        view = view.sort_values("padj").head(int(n))
        rows = [{"gene": g, "name": str(x["gene_name"]), "base_mean": round(float(x["baseMean"]), 1), "lfc": round(float(x["log2FoldChange"]), 3),
                 "padj": None if pd.isna(x["padj"]) else float(x["padj"])} for g, x in view.iterrows()]
        return {"up": int((sig["log2FoldChange"] > 0).sum()), "down": int((sig["log2FoldChange"] < 0).sum()), "rows": rows}

    def volcano(self, padj: float = 0.05, lfc: float = 0.0, max_points: int = 6000):
        r = self._results().dropna(subset=["padj"])
        sig = (r["padj"] < padj) & (r["log2FoldChange"].abs() >= lfc)
        # Intent: keep every significant gene; thin the rest so the plot stays quick.
        ns = r[~sig]
        if len(ns) > max_points:
            ns = ns.sample(max_points, random_state=0)
        pts = pd.concat([ns, r[sig]])
        y = -np.log10(pts["padj"].clip(lower=1e-300))
        return {"x": pts["log2FoldChange"].round(3).tolist(), "y": y.round(3).tolist(),
                "sig": [int(np.sign(v)) if s else 0 for v, s in zip(pts["log2FoldChange"], sig.reindex(pts.index))],
                "gene": pts.index.tolist(), "name": pts["gene_name"].astype(str).tolist()}

    def ma(self, padj: float = 0.05):
        r = self._results().dropna(subset=["log2FoldChange"])
        return {"x": np.log10(r["baseMean"] + 1).round(3).tolist(), "y": r["log2FoldChange"].round(3).tolist(),
                "sig": [bool(p < padj) if not pd.isna(p) else False for p in r["padj"]]}

    def gene(self, gene: str):
        path = self.out / "normalized_counts.csv"
        if not path.exists():
            raise ValueError("Compare conditions first.")
        norm = pd.read_csv(path, index_col=0)
        if gene not in norm.index:
            raise ValueError(f"{gene} was not tested (too few counts).")
        v = norm.loc[gene]
        return {"gene": gene, "name": str(self.gene_names.get(gene, gene)),
                "values": [{"sample": s, "condition": self.meta.loc[s, "condition"], "count": round(float(v[s]), 1)} for s in v.index]}

    # ---------------------------------------------------------------- export
    def export(self, padj: float = 0.05, lfc: float = 0.0):
        self._results()
        return self._background(self._export, float(padj), float(lfc))

    def _export(self, padj, lfc):
        de, r = self.state["de"], self._results()
        d = self.dir / "results" / "differential_expression"
        d.mkdir(parents=True, exist_ok=True)
        name = f"{de['test']}_vs_{de['reference']}"
        self._prog(20, "Writing tables")
        r.sort_values("padj").to_csv(d / f"de_{name}_all_genes.csv")
        sig = r[(r["padj"] < padj) & (r["log2FoldChange"].abs() >= lfc)].sort_values("padj")
        sig.to_csv(d / f"de_{name}_significant.csv")
        pd.read_csv(self.out / "normalized_counts.csv", index_col=0).to_csv(d / "normalized_counts.csv")
        self._prog(60, "Drawing the volcano plot")
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        rr = r.dropna(subset=["padj"])
        s = (rr["padj"] < padj) & (rr["log2FoldChange"].abs() >= lfc)
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.scatter(rr["log2FoldChange"][~s], -np.log10(rr["padj"][~s].clip(lower=1e-300)), s=4, c="#B9AEC0", lw=0)
        ax.scatter(rr["log2FoldChange"][s], -np.log10(rr["padj"][s].clip(lower=1e-300)), s=6, c="#6E1B2B", lw=0)
        ax.set_xlabel(f"log2 fold change ({de['test']} vs {de['reference']})"); ax.set_ylabel("-log10 adjusted P")
        ax.set_title(f"{len(sig)} genes with adjusted P < {padj}" + (f" and |log2FC| ≥ {lfc}" if lfc else ""))
        fig.savefig(d / f"volcano_{name}.png", dpi=200, bbox_inches="tight"); plt.close(fig)
        files = sorted(p.name for p in d.iterdir())
        self.state.update(step="exported", exported=files)
        self._record("exported results", padj=padj, lfc=lfc, significant=int(len(sig)), files=files)
        self._prog(100, f"Saved to results/differential_expression ({len(files)} files)")

    def files(self):
        d = self.dir / "results" / "differential_expression"
        return [{"name": f"differential_expression/{p.name}", "size": p.stat().st_size} for p in sorted(d.iterdir())] if d.exists() else []
