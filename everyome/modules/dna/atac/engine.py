"""Live session for ATAC-seq: check the libraries (peaks, FRiP, principal components), see where the peaks lie
relative to genes, compare two groups for regions that open or close (DESeq2, as PyDESeq2), look at any region, and
export.

Reads what nf-core/atacseq wrote (paths in helpers.py): the consensus peaks' featureCounts table, each library's
peaks and qc tables, and the run's GTF for the nearest gene. bigWig coverage is drawn when pyBigWig is installed.
Each step is checkpointed to <run>/session/ and recorded in order for the write-up; exports go to results/final/.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from everyome.core.engine import BaseEngine
from everyome.modules.rna.abundance.engine import size_factors

from . import helpers


def read_gtf_tss(path) -> pd.DataFrame:
    """One row per gene: chromosome, TSS (1-based), strand and name, from the GTF's gene lines (transcripts if none)."""
    rows = {"gene": [], "transcript": []}
    for line in open(path):
        if line.startswith("#"):
            continue
        f = line.rstrip("\n").split("\t")
        if len(f) < 9 or f[2] not in rows:
            continue
        a = {k: v.strip('"') for k, _, v in (p.strip().partition(" ") for p in f[8].split(";") if p.strip())}
        gid = a.get("gene_id", "")
        rows[f[2]].append({"chrom": f[0], "start": int(f[3]), "end": int(f[4]), "strand": f[6], "gene_id": gid,
                           "gene": a.get("gene_name") or gid, "tss": int(f[3]) if f[6] != "-" else int(f[4])})
    # Intent: some GTFs have no gene lines; then each gene's first transcript stands in for it.
    df = pd.DataFrame(rows["gene"] or rows["transcript"], columns=["chrom", "start", "end", "strand", "gene_id", "gene", "tss"])
    return df.drop_duplicates("gene_id").sort_values(["chrom", "tss"]).reset_index(drop=True)


def nearest_tss(peaks: pd.DataFrame, genes: pd.DataFrame) -> pd.DataFrame:
    """Each peak's nearest gene (by TSS) and its signed distance from the peak centre (upstream negative)."""
    out = pd.DataFrame({"nearest_gene": "", "distance_to_tss": np.nan}, index=peaks.index)
    if genes.empty:
        return out
    mid = ((peaks["start"] + peaks["end"]) // 2).to_numpy()
    for c, g in genes.groupby("chrom"):
        on = (peaks["chr"] == c).to_numpy()
        if not on.any():
            continue
        t = g["tss"].to_numpy()
        i = np.clip(np.searchsorted(t, mid[on]), 1, len(t)) - 1
        j = np.clip(i + 1, 0, len(t) - 1)
        best = np.where(np.abs(mid[on] - t[j]) < np.abs(mid[on] - t[i]), j, i)
        d = mid[on] - t[best]
        d = np.where(g["strand"].to_numpy()[best] == "-", -d, d)
        out.loc[on, "nearest_gene"] = g["gene"].to_numpy()[best]
        out.loc[on, "distance_to_tss"] = d
    return out


def read_peaks(path) -> pd.DataFrame:
    cols = ["chr", "start", "end", "name", "score", "strand", "signal", "p", "q"]
    df = pd.read_csv(path, sep="\t", header=None, comment="#")
    df = df.iloc[:, :9]
    df.columns = cols[:df.shape[1]]
    return df


class Engine(BaseEngine):
    API = ("overview", "sample_qc", "peaks", "run_da", "results", "volcano", "locus", "export", "files")
    REPLAY = ("run_da", "export")

    def __init__(self, run_dir: str):
        super().__init__(run_dir)
        self.res = self.dir / "results" / "final"
        v = self.params
        path = self.dir / helpers.consensus_counts(v)
        if not path.exists():
            raise FileNotFoundError("No consensus peak counts from nf-core/atacseq were found in this run's results. "
                                    "Check the pipeline log: peak calling is skipped when no genome size is set.")
        self.counts_file = helpers.consensus_counts(v)
        df = pd.read_csv(path, sep="\t", comment="#").set_index("Geneid")
        self.peaks_df = df[["Chr", "Start", "End"]].rename(columns={"Chr": "chr", "Start": "start", "End": "end"})
        self.peaks_df["start"] -= 1                                  # Intent: featureCounts is 1-based; keep BED-style 0-based starts
        num = df.iloc[:, 5:]
        num.columns = [Path(c).name.split(".mLb.")[0] for c in num.columns]
        libs = helpers.libraries(v)
        self.missing = [l["library"] for l in libs if l["library"] not in num.columns]
        keep = [l["library"] for l in libs if l["library"] in num.columns]
        if len(keep) < 2:
            raise ValueError("Fewer than two of the listed libraries are in the consensus counts.")
        self.counts = num[keep].round().astype(int)
        self.meta = pd.DataFrame({"group": [l["group"] for l in libs if l["library"] in keep]}, index=keep)
        gtf = v.get("gtf") or ""
        self.genes = read_gtf_tss(gtf) if gtf and Path(gtf).exists() else pd.DataFrame(columns=["chrom", "start", "end", "strand", "gene_id", "gene", "tss"])
        self.annot = nearest_tss(self.peaks_df, self.genes)
        self._res = None

    def status(self):
        return {**super().status(), "libraries": list(self.counts.columns), "groups": sorted(self.meta["group"].unique()),
                "da": self.state.get("da"), "missing": self.missing, "has_genes": not self.genes.empty}

    def _norm(self) -> pd.DataFrame:
        c = self.counts[self.counts.sum(axis=1) >= 10]
        return np.log2(c / size_factors(c) + 1)

    # ---------------------------------------------------------------- check libraries
    def overview(self):
        v, pdir = self.params, self.dir / helpers.peak_dir(self.params)
        qc = {}
        for f in sorted((pdir / "qc").glob("*_mqc.tsv")) if (pdir / "qc").exists() else []:
            key = "frip" if "FRiP" in f.name else "peaks"
            for lib, val in helpers.read_mqc(f.read_text()).items():
                qc.setdefault(lib.replace(".mLb.clN_peaks", "").replace(".mLb.clN", ""), {})[key] = val
        rows = []
        for lib in self.counts.columns:
            pf = self.dir / helpers.peak_file(v, lib)
            widths = read_peaks(pf).pipe(lambda p: p["end"] - p["start"]) if pf.exists() else pd.Series(dtype=float)
            q = qc.get(lib, {})
            rows.append({"library": lib, "group": self.meta.loc[lib, "group"], "peaks": int(len(widths)) if len(widths) else q.get("peaks"),
                         "frip": q.get("frip"), "median_width": int(widths.median()) if len(widths) else None,
                         "in_consensus": int(self.counts[lib].sum())})
        return {"counts_file": self.counts_file, "consensus_peaks": int(len(self.counts)), "missing": self.missing,
                "kind": helpers.peak_kind(v), "libraries": rows}

    def sample_qc(self, n_peaks: int = 1000):
        n = self._norm()
        top = n.loc[n.var(axis=1).sort_values(ascending=False).index[:min(int(n_peaks), len(n))]]
        x = (top.T - top.T.mean()).values
        u, sv, _ = np.linalg.svd(x, full_matrices=False)
        var = sv ** 2 / (sv ** 2).sum()
        pcs = u * sv
        return {"libraries": list(n.columns), "groups": list(self.meta.loc[n.columns, "group"]),
                "pc1": pcs[:, 0].round(3).tolist(), "pc2": (pcs[:, 1] if pcs.shape[1] > 1 else np.zeros(len(pcs))).round(3).tolist(),
                "var": [round(float(v) * 100, 1) for v in var[:2]], "corr": np.round(np.corrcoef(n.T.values), 3).tolist(),
                "n_peaks": int(len(top))}

    # ---------------------------------------------------------------- where the peaks are
    def peaks(self):
        w = (self.peaks_df["end"] - self.peaks_df["start"]).to_numpy()
        w_edges = [0, 200, 300, 400, 500, 750, 1000, 1500, 2000, 5000, 10**9]
        out = {"consensus_peaks": int(len(w)), "median_width": int(np.median(w)) if len(w) else 0,
               "widths": {"labels": ["<200", "200–300", "300–400", "400–500", "500–750", "750–1,000", "1–1.5 kb", "1.5–2 kb", "2–5 kb", "≥5 kb"],
                          "counts": np.histogram(w, w_edges)[0].tolist()},
               "per_chrom": self.peaks_df["chr"].value_counts().head(40).to_dict(), "has_genes": not self.genes.empty}
        if not self.genes.empty:
            d = self.annot["distance_to_tss"].abs().dropna().to_numpy()
            edges = [0, 500, 1_000, 5_000, 20_000, 100_000, np.inf]
            out["tss"] = {"labels": ["≤500 bp", "0.5–1 kb", "1–5 kb", "5–20 kb", "20–100 kb", ">100 kb"],
                          "counts": np.histogram(d, edges)[0].tolist(), "promoter_share": round(float((d <= 1_000).mean() * 100), 1) if len(d) else 0,
                          "genes": int(len(self.genes))}
        if self.state.get("peaks_seen") != out["consensus_peaks"]:
            self.state["peaks_seen"] = out["consensus_peaks"]
            self._record("summarised the peaks", consensus_peaks=out["consensus_peaks"], median_width=out["median_width"],
                         promoter_share=(out.get("tss") or {}).get("promoter_share"))
        return out

    # ---------------------------------------------------------------- compare groups
    def run_da(self, test: str, reference: str, alpha: float = 0.05, min_count: int = 10):
        groups = set(self.meta["group"])
        if test not in groups or reference not in groups or test == reference:
            raise ValueError("Choose two different groups to compare.")
        for g in (test, reference):
            if (self.meta["group"] == g).sum() < 2:
                raise ValueError(f"'{g}' has fewer than two libraries; DESeq2 needs replicates to estimate variation.")
        return self._background(self._run_da, test, reference, float(alpha), int(min_count))

    def _run_da(self, test, reference, alpha, min_count):
        import pydeseq2
        from pydeseq2.dds import DeseqDataSet
        from pydeseq2.ds import DeseqStats
        self._prog(10, "Preparing counts")
        keep = self.meta.index[self.meta["group"].isin([test, reference])]
        c = self.counts[keep]
        c = c[c.sum(axis=1) >= min_count]
        self._prog(25, "Fitting size factors and dispersions")
        meta = self.meta.loc[keep].rename(columns={"group": "condition"})
        dds = DeseqDataSet(counts=c.T, metadata=meta, design="~condition", quiet=True)
        dds.deseq2()
        self._prog(75, "Testing each peak")
        st = DeseqStats(dds, contrast=["condition", test, reference], alpha=alpha, quiet=True)
        st.summary()
        res = st.results_df.copy()
        res = self.peaks_df.join(self.annot).loc[res.index].join(res)
        res.index.name = "peak"
        res.to_csv(self.out / "da_results.csv")
        pd.DataFrame(dds.layers["normed_counts"], index=dds.obs_names, columns=dds.var_names).T.rename_axis("peak").to_csv(self.out / "normalised_counts.csv")
        self._res = res
        sig = res[res["padj"] < alpha]
        da = {"test": test, "reference": reference, "alpha": alpha, "min_count": min_count, "peaks_tested": int(len(res)),
              "opening": int((sig["log2FoldChange"] > 0).sum()), "closing": int((sig["log2FoldChange"] < 0).sum()),
              "libraries": list(keep), "pydeseq2": pydeseq2.__version__}
        self.state.update(step="tested", da=da)
        self._record("compared groups", **da)

    def _results(self):
        if self._res is None:
            path = self.out / "da_results.csv"
            if not path.exists():
                raise ValueError("Compare groups first.")
            self._res = pd.read_csv(path, index_col=0)
        return self._res

    def results(self, padj: float = 0.05, lfc: float = 0.0, q: str = "", n: int = 200):
        r = self._results()
        sig = r[(r["padj"] < padj) & (r["log2FoldChange"].abs() >= lfc)]
        if q:
            ql = q.lower()
            view = r[r.index.str.lower().str.contains(ql, regex=False) | r["nearest_gene"].fillna("").astype(str).str.lower().str.contains(ql, regex=False)]
        else:
            view = sig
        view = view.sort_values("padj").head(int(n))
        rows = [{"peak": p, "chr": x["chr"], "start": int(x["start"]), "end": int(x["end"]),
                 "gene": "" if pd.isna(x["nearest_gene"]) else str(x["nearest_gene"]),
                 "distance": None if pd.isna(x["distance_to_tss"]) else int(x["distance_to_tss"]),
                 "base_mean": round(float(x["baseMean"]), 1), "lfc": round(float(x["log2FoldChange"]), 3),
                 "padj": None if pd.isna(x["padj"]) else float(x["padj"])} for p, x in view.iterrows()]
        return {"opening": int((sig["log2FoldChange"] > 0).sum()), "closing": int((sig["log2FoldChange"] < 0).sum()), "rows": rows}

    def volcano(self, padj: float = 0.05, lfc: float = 0.0, max_points: int = 6000):
        r = self._results().dropna(subset=["padj"])
        sig = (r["padj"] < padj) & (r["log2FoldChange"].abs() >= lfc)
        ns = r[~sig]
        if len(ns) > max_points:                       # Intent: keep every significant peak; thin the rest
            ns = ns.sample(max_points, random_state=0)
        pts = pd.concat([ns, r[sig]])
        return {"x": pts["log2FoldChange"].round(3).tolist(), "y": (-np.log10(pts["padj"].clip(lower=1e-300))).round(3).tolist(),
                "sig": [int(np.sign(v)) if s else 0 for v, s in zip(pts["log2FoldChange"], sig.reindex(pts.index))],
                "peak": pts.index.tolist(), "gene": pts["nearest_gene"].fillna("").astype(str).tolist()}

    # ---------------------------------------------------------------- look at a region
    def locus(self, q: str = "", chrom: str = "", start: int = 0, end: int = 0, pad: int = 5_000):
        """A window of the genome: each library's peaks (height = MACS2 signal), the consensus peaks (with the
        comparison's result if there is one), genes, and bigWig coverage when pyBigWig can read it."""
        q = (q or "").strip()
        if q:
            if q in self.peaks_df.index:
                p = self.peaks_df.loc[q]
                chrom, start, end = p["chr"], int(p["start"]), int(p["end"])
            else:
                hit = self.genes[(self.genes["gene"].str.lower() == q.lower()) | (self.genes["gene_id"].str.lower() == q.lower())]
                if hit.empty:
                    raise ValueError(f"No peak or gene called {q}.")
                g = hit.iloc[0]
                chrom, start, end = g["chrom"], int(g["start"]), int(g["end"])
        if not chrom:
            raise ValueError("Type a peak (Interval_…) or gene name, or a region.")
        start, end = max(0, int(start) - int(pad)), int(end) + int(pad)
        inwin = lambda df, c, a, b: df[(df[c] == chrom) & (df[b] > start) & (df[a] < end)]
        cons = inwin(self.peaks_df, "chr", "start", "end")
        da = self._results() if (self.out / "da_results.csv").exists() else None
        tracks = []
        for lib in self.counts.columns:
            pf = self.dir / helpers.peak_file(self.params, lib)
            pk = inwin(read_peaks(pf), "chr", "start", "end") if pf.exists() else pd.DataFrame(columns=["start", "end", "signal"])
            tracks.append({"library": lib, "group": self.meta.loc[lib, "group"],
                           "peaks": [{"start": int(r["start"]), "end": int(r["end"]), "signal": round(float(r["signal"]), 2)} for _, r in pk.iterrows()],
                           "coverage": self._coverage(lib, chrom, start, end)})
        genes = inwin(self.genes, "chrom", "start", "end")
        return {"chrom": chrom, "start": start, "end": end, "tracks": tracks,
                "consensus": [{"peak": p, "start": int(r["start"]), "end": int(r["end"]),
                               "lfc": None if da is None or p not in da.index else round(float(da.loc[p, "log2FoldChange"]), 2),
                               "padj": None if da is None or p not in da.index or pd.isna(da.loc[p, "padj"]) else float(da.loc[p, "padj"])}
                              for p, r in cons.iterrows()],
                "genes": [{"gene": r["gene"], "start": int(r["start"]), "end": int(r["end"]), "strand": r["strand"]} for _, r in genes.iterrows()]}

    def _coverage(self, lib, chrom, start, end, bins: int = 200):
        f = self.dir / helpers.bigwig(self.params, lib)
        if not f.exists():
            return None
        try:
            import pyBigWig
        except ImportError:
            return None
        with pyBigWig.open(str(f)) as bw:
            if chrom not in bw.chroms():
                return None
            vals = bw.stats(chrom, start, min(end, bw.chroms()[chrom]), nBins=bins, type="mean")
        return [round(v or 0.0, 3) for v in vals]

    # ---------------------------------------------------------------- export
    def export(self, padj: float = 0.05, lfc: float = 0.0):
        self.res.mkdir(parents=True, exist_ok=True)
        peaks = self.peaks_df.join(self.annot).join(self.counts)
        peaks.index.name = "peak"
        peaks.to_csv(self.res / "consensus_peaks_counts.csv")
        self._norm().rename_axis("peak").to_csv(self.res / "normalised_log2.csv")
        self.meta.rename_axis("library").to_csv(self.res / "libraries.csv")
        sig_n = None
        if (self.out / "da_results.csv").exists():
            da, r = self.state["da"], self._results()
            name = f"{da['test']}_vs_{da['reference']}"
            r.sort_values("padj").to_csv(self.res / f"da_{name}_all_peaks.csv")
            sig = r[(r["padj"] < padj) & (r["log2FoldChange"].abs() >= lfc)].sort_values("padj")
            sig.to_csv(self.res / f"da_{name}_significant.csv")
            sig[["chr", "start", "end"]].assign(name=sig.index, score=0, strand=".").to_csv(
                self.res / f"da_{name}_significant.bed", sep="\t", header=False, index=False)
            sig_n = int(len(sig))
        files = sorted(f.name for f in self.res.iterdir())
        self.state.update(exported=files)
        self._record("exported results", padj=float(padj), lfc=float(lfc), significant=sig_n, files=files)
        return {"files": files}

    def files(self):
        return [{"name": f"final/{f.name}", "size": f.stat().st_size} for f in sorted(self.res.glob("*"))] if self.res.exists() else []
