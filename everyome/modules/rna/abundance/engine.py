"""Live session for RNA abundance: how much each gene is expressed in each sample, how samples relate, and which
genes share a pattern across samples. No two-group test (that is the differential expression module).

Reads the merged gene tables nf-core/rnaseq wrote (TPM, and counts for normalising). Every choice that changes a
result is recorded in order for the write-up.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from everyome.core.engine import BaseEngine

from .helpers import tables


def size_factors(counts: pd.DataFrame) -> pd.Series:
    """DESeq2's median-of-ratios size factors (samples are columns)."""
    logs = np.log(counts.replace(0, np.nan))
    ref = logs.mean(axis=1)
    ok = ref.notna() & np.isfinite(ref)
    return np.exp((logs[ok].sub(ref[ok], axis=0)).median(axis=0))


def kmeans(x: np.ndarray, k: int, seed: int = 0, iters: int = 100) -> np.ndarray:
    """Plain k-means (k-means++ start, fixed seed, so a rerun gives the same clusters)."""
    rng = np.random.default_rng(seed)
    centres = [x[rng.integers(len(x))]]
    for _ in range(1, k):
        d = np.min([((x - c) ** 2).sum(axis=1) for c in centres], axis=0)
        centres.append(x[rng.choice(len(x), p=d / d.sum())] if d.sum() > 0 else x[rng.integers(len(x))])
    centres = np.array(centres)
    labels = np.zeros(len(x), dtype=int)
    for _ in range(iters):
        new = ((x[:, None, :] - centres[None]) ** 2).sum(axis=2).argmin(axis=1)
        if (new == labels).all() and _:
            break
        labels = new
        centres = np.array([x[labels == j].mean(axis=0) if (labels == j).any() else centres[j] for j in range(k)])
    # Intent: number clusters by the sample where they peak, so the order is stable and readable.
    order = np.argsort([int(np.argmax(c)) * 1000 - c.max() for c in centres])
    remap = {int(o): i for i, o in enumerate(order)}
    return np.array([remap[int(l)] for l in labels])


class Engine(BaseEngine):
    API = ("overview", "sample_qc", "gene", "top_genes", "patterns", "export", "files")
    REPLAY = ("patterns", "export")

    def __init__(self, run_dir: str):
        super().__init__(run_dir)
        self.res = self.dir / "results"          # Intent: what the user downloads; session/ holds the checkpoints.
        res = self.params.get("results_dir") or ""
        found = next(((t, c) for t, c in tables(res) if Path(t).exists()), None)
        if not found:
            raise FileNotFoundError("No gene TPM table from nf-core/rnaseq was found in the results folder.")
        self.tpm_file, self.counts_file = found
        tpm = pd.read_csv(self.tpm_file, sep="\t").set_index("gene_id")
        name_col = next((c for c in ("gene_name", "gene_symbol") if c in tpm.columns), None)
        self.names = tpm[name_col].astype(str) if name_col else pd.Series(tpm.index, index=tpm.index)
        rows = self.params.get("samples") or [{"sample": s, "group": ""} for s in tpm.select_dtypes("number").columns]
        self.missing = [r["sample"] for r in rows if r["sample"] not in tpm.columns]
        keep = [r["sample"] for r in rows if r["sample"] in tpm.columns]
        if len(keep) < 2:
            raise ValueError("Fewer than two of the listed samples are in the TPM table.")
        self.tpm = tpm[keep].astype(float)
        self.group = pd.Series({r["sample"]: r.get("group") or r["sample"] for r in rows}).reindex(keep)
        counts = pd.read_csv(self.counts_file, sep="\t").set_index("gene_id")[keep] if Path(self.counts_file).exists() else None
        if counts is not None:
            # Intent: compare samples on normalised counts (DESeq2's size factors), as the DE module does.
            c = counts.round()
            c = c[c.sum(axis=1) >= 10]
            self.norm = np.log2(c / size_factors(c) + 1)
            self.norm_kind = "log2 of size-factor-normalised counts"
        else:
            self.norm = np.log2(self.tpm[self.tpm.sum(axis=1) > 0] + 1)
            self.norm_kind = "log2(TPM + 1)"

    def status(self):
        return {**super().status(), "samples": list(self.tpm.columns), "groups": sorted(set(self.group)),
                "patterns": self.state.get("patterns"), "missing": self.missing}

    def _label(self, g):
        n = self.names.get(g, g)
        return n if n == g else f"{n} ({g})"

    # ---------------------------------------------------------------- samples
    def overview(self):
        t = self.tpm
        return {"tpm_file": self.tpm_file, "genes": int(t.shape[0]), "missing": self.missing, "normalised": self.norm_kind,
                "samples": [{"sample": s, "group": self.group[s], "detected": int((t[s] >= 1).sum()),
                             "top10_share": round(float(t[s].nlargest(10).sum() / 1e4), 1)} for s in t.columns]}

    def sample_qc(self, n_genes: int = 500):
        n = self.norm
        top = n.loc[n.var(axis=1).sort_values(ascending=False).index[:min(int(n_genes), len(n))]]
        x = (top.T - top.T.mean()).values
        u, sv, _ = np.linalg.svd(x, full_matrices=False)
        var = sv ** 2 / (sv ** 2).sum()
        pcs = u * sv
        return {"samples": list(n.columns), "groups": list(self.group[n.columns]),
                "pc1": pcs[:, 0].round(3).tolist(), "pc2": (pcs[:, 1] if pcs.shape[1] > 1 else np.zeros(len(pcs))).round(3).tolist(),
                "var": [round(float(v) * 100, 1) for v in var[:2]], "corr": np.round(np.corrcoef(n.T.values), 3).tolist(),
                "n_genes": int(len(top))}

    # ---------------------------------------------------------------- genes
    def gene(self, q: str):
        q = (q or "").strip()
        if not q:
            raise ValueError("Type a gene name or ID.")
        hits = [g for g in self.tpm.index if g == q or self.names.get(g) == q]
        if not hits:
            low = q.lower()
            hits = [g for g in self.tpm.index if low in g.lower() or low in str(self.names.get(g, "")).lower()][:20]
            if not hits:
                raise ValueError(f"No gene matches '{q}'.")
            if len(hits) > 1:
                return {"choices": [{"id": g, "label": self._label(g)} for g in hits]}
        g = hits[0]
        return {"id": g, "label": self._label(g),
                "values": [{"sample": s, "group": self.group[s], "tpm": round(float(self.tpm.at[g, s]), 2)} for s in self.tpm.columns]}

    def top_genes(self, n: int = 30):
        mean = self.tpm.mean(axis=1).sort_values(ascending=False).head(int(n))
        return [{"id": g, "label": self._label(g), "mean_tpm": round(float(v), 1),
                 "by_group": {k: round(float(self.tpm.loc[g, self.group.index[self.group == k]].mean()), 1) for k in sorted(set(self.group))}}
                for g, v in mean.items()]

    # ---------------------------------------------------------------- patterns
    def patterns(self, n_genes: int = 500, k: int = 4, min_tpm: float = 1.0):
        """Cluster the most variable genes by their pattern across samples (z-scores), with k-means."""
        n_genes, k = int(n_genes), int(k)
        if not 2 <= k <= 12:
            raise ValueError("Choose between 2 and 12 clusters.")
        expressed = self.tpm.index[(self.tpm.max(axis=1) >= float(min_tpm))]
        n = self.norm.loc[self.norm.index.intersection(expressed)]
        top = n.loc[n.var(axis=1).sort_values(ascending=False).index[:min(n_genes, len(n))]]
        z = top.sub(top.mean(axis=1), axis=0).div(top.std(axis=1).replace(0, 1), axis=0)
        labels = kmeans(z.values, k)
        clusters = pd.Series(labels, index=z.index)
        pd.DataFrame({"gene_name": [self.names.get(g, g) for g in z.index], "cluster": labels + 1}, index=z.index).rename_axis("gene_id") \
            .to_csv(self.res / "gene_clusters.csv")
        info = {"n_genes": int(len(z)), "k": k, "min_tpm": float(min_tpm), "normalised": self.norm_kind,
                "sizes": [int((labels == j).sum()) for j in range(k)]}
        self.state["patterns"] = info
        self._record("found expression patterns", **info)
        order = clusters.sort_values(kind="stable").index
        # Intent: send at most 300 rows to draw; the full list is in gene_clusters.csv.
        step = max(1, len(order) // 300)
        shown = order[::step]
        return {**info, "samples": list(z.columns), "groups": list(self.group[z.columns]),
                "profiles": [z[labels == j].mean(axis=0).round(3).tolist() for j in range(k)],
                "heat": {"genes": [self._label(g) for g in shown], "cluster": [int(clusters[g]) + 1 for g in shown],
                         "z": z.loc[shown].round(2).values.tolist()},
                "members": [[self._label(g) for g in clusters.index[clusters == j][:15]] for j in range(k)]}

    # ---------------------------------------------------------------- export
    def export(self):
        tpm = self.tpm.copy()
        tpm.insert(0, "gene_name", [self.names.get(g, g) for g in tpm.index])
        tpm.to_csv(self.res / "tpm.csv")
        self.norm.to_csv(self.res / "normalised_log2.csv")
        self.group.rename("group").rename_axis("sample").to_csv(self.res / "samples.csv")
        files = [f.name for f in sorted(self.res.glob("*.csv"))]
        self._record("exported tables", files=files)
        return {"files": files}

    def files(self):
        return [{"name": f.name, "size": f.stat().st_size} for f in sorted(self.res.glob("*")) if f.is_file()]
