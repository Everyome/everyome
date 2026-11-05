"""Live session for Ribo-seq: does each library show the 3-nucleotide rhythm of translating ribosomes, which open
reading frames are translated, and which genes change translational efficiency (TE) between conditions.

Reads what nf-core/riboseq writes (paths in helpers.py):
  psites/ribowaltz/<sample>.psite_offset.tsv, <sample>.psite.tsv     P-site offsets by read length; one row per footprint
  orf_predictions/catalogue/*.catalogue.tsv (or Ribo-TISH's tables)   translated ORFs, with their class (uORF, dORF, ...)
  quantification/inframe_psite/gene_counts.tsv                        in-frame P-sites (Ribo-seq) and reads (RNA-seq) per gene
  translational_efficiency/anota2seq/<contrast>.*.anota2seq.results.tsv   when the run had a contrasts file

The session's own TE comparison works without anota2seq: within each Ribo-seq/RNA-seq pair, log2 TE is the log of
normalised in-frame P-sites over normalised RNA-seq reads; conditions are compared with a moderated t-test (each gene's
variance pulled towards the typical gene's, as limma does) and Benjamini–Hochberg adjustment. Exports go to results/final/.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

import numpy as np
import pandas as pd

from everyome.core.engine import BaseEngine
from everyome.modules.rna.abundance.engine import size_factors

from .helpers import ANOTA, CATALOGUE_DIR, COUNTS, MULTIQC, RIBOTISH, RIBOWALTZ

MAX_READS = 2_000_000          # Intent: periodicity is clear from a sample of footprints; cap memory on big libraries.
START_WIN, STOP_WIN = (-24, 60), (-60, 24)
PRIOR_DF = 4.0                 # Intent: how strongly each gene's variance is pulled towards the typical gene's.


def window(pos: pd.Series, lo: int, hi: int) -> list[int]:
    """Footprints at each position from lo to hi (a metagene profile around the start or stop codon)."""
    return pos[pos.between(lo, hi)].value_counts().reindex(range(lo, hi + 1), fill_value=0).astype(int).tolist()


def bh(p: np.ndarray) -> np.ndarray:
    """Benjamini–Hochberg adjusted P values."""
    p = np.asarray(p, float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order] * n / np.arange(1, n + 1)
    adj = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(adj, 1)
    return out


def moderated_t(a: np.ndarray, b: np.ndarray, d0: float = PRIOR_DF) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Difference of means (a − b, genes × replicates), moderated t and two-sided P.

    Each gene's pooled variance is shrunk towards the median variance of all genes with d0 prior degrees of freedom
    (a simple form of limma's empirical Bayes moderation), which steadies the test when there are few replicates.
    """
    from scipy import stats
    na, nb = a.shape[1], b.shape[1]
    if na < 2 or nb < 2:
        raise ValueError("Each condition needs at least two pairs (Ribo-seq with its RNA-seq) to compare.")
    diff = a.mean(axis=1) - b.mean(axis=1)
    df = na + nb - 2
    s2 = (a.var(axis=1, ddof=1) * (na - 1) + b.var(axis=1, ddof=1) * (nb - 1)) / df
    s0 = float(np.median(s2[np.isfinite(s2)])) or 1e-6
    post = (d0 * s0 + df * s2) / (d0 + df)
    t = diff / np.sqrt(post * (1 / na + 1 / nb))
    return diff, t, 2 * stats.t.sf(np.abs(t), df + d0)


def read_counts(path) -> tuple[pd.DataFrame, pd.Series]:
    """Count table (genes × samples) and gene names, from nf-core's gene_id / gene_name / samples layout."""
    t = pd.read_csv(path, sep="\t")
    t = t.set_index(t.columns[0])
    t.index = t.index.astype(str)
    name_col = next((c for c in ("gene_name", "gene_symbol", "Symbol") if c in t.columns), None)
    names = t[name_col].astype(str) if name_col else pd.Series(t.index, index=t.index)
    return t.select_dtypes("number").astype(float), names


def pairs_of(rows: list[dict]) -> list[dict]:
    """Ribo-seq/RNA-seq pairs: by the pair column, or else in order within each condition (as nf-core/riboseq does)."""
    ribo = [r for r in rows if r.get("type") == "riboseq"]
    rna = [r for r in rows if r.get("type") == "rnaseq"]
    out = []
    if all(r.get("pair") for r in ribo + rna):
        by = {r["pair"]: r for r in rna}
        out = [{"pair": r["pair"], "ribo": r["sample"], "rna": by[r["pair"]]["sample"], "condition": r.get("condition", "")}
               for r in ribo if r["pair"] in by]
    else:
        for c in dict.fromkeys(r.get("condition", "") for r in ribo):
            a, b = [r for r in ribo if r.get("condition", "") == c], [r for r in rna if r.get("condition", "") == c]
            out += [{"pair": f"{c}_{i + 1}", "ribo": x["sample"], "rna": y["sample"], "condition": c} for i, (x, y) in enumerate(zip(a, b))]
    return out


def te_table(counts: pd.DataFrame, pairs: list[dict], test: str, reference: str, min_count: float = 10,
             d0: float = PRIOR_DF) -> pd.DataFrame:
    """Per gene: log2 fold changes of RNA-seq, Ribo-seq and TE (test against reference), moderated-t P values and a class."""
    use = [p for p in pairs if p["condition"] in (test, reference) and p["ribo"] in counts.columns and p["rna"] in counts.columns]
    a = [p for p in use if p["condition"] == test]
    b = [p for p in use if p["condition"] == reference]
    if not a or not b:
        raise ValueError(f"No complete Ribo-seq/RNA-seq pairs for {test if not a else reference}.")
    ribo, rna = counts[[p["ribo"] for p in use]], counts[[p["rna"] for p in use]]
    # Intent: keep genes with enough footprints and reads to say anything (mean over the compared libraries).
    keep = (ribo.mean(axis=1) >= min_count) & (rna.mean(axis=1) >= min_count)
    ribo, rna = ribo[keep], rna[keep]
    if len(ribo) < 10:
        raise ValueError("Too few genes pass the count filter; lower the minimum count.")
    lr = np.log2(ribo / size_factors(ribo) + 1)
    ln = np.log2(rna / size_factors(rna) + 1)
    te = pd.DataFrame(lr.values - ln.values, index=lr.index, columns=[p["pair"] for p in use])
    lr.columns = ln.columns = te.columns
    A, B = [p["pair"] for p in a], [p["pair"] for p in b]
    out = pd.DataFrame(index=te.index)
    for key, m in (("rna", ln), ("ribo", lr), ("te", te)):
        d, t, pv = moderated_t(m[A].values, m[B].values, d0)
        out[f"{key}_log2fc"], out[f"{key}_p"], out[f"{key}_padj"] = d, pv, bh(pv)
    out["mean_ribo"], out["mean_rna"] = ribo.mean(axis=1), rna.mean(axis=1)
    return out


def classify(r: pd.DataFrame, alpha: float) -> pd.Series:
    """Like anota2seq's modes: translation (TE changes), buffering (TE offsets an mRNA change), mRNA abundance (both move)."""
    te_sig, rna_sig = r["te_padj"] < alpha, r["rna_padj"] < alpha
    opposite = np.sign(r["te_log2fc"]) != np.sign(r["rna_log2fc"])
    return pd.Series(np.where(te_sig & rna_sig & opposite, "buffering", np.where(te_sig, "translation",
                                                                                   np.where(rna_sig, "mRNA abundance", "unchanged"))), index=r.index)


def orf_class(native: str) -> str:
    """One vocabulary for ORF types from any caller (Ribo-TISH's TisType, RiboCode's ORF_type, the catalogue's class)."""
    n = (native or "").lower().replace("'", "")
    for key, label in (("canonical", "canonical_cds"), ("annotated", "canonical_cds"), ("uoorf", "uoORF"), ("overlap_uorf", "uoORF"),
                       ("uorf", "uORF"), ("5utr", "uORF"), ("doorf", "doORF"), ("dorf", "dORF"), ("3utr", "dORF"),
                       ("internal", "intORF"), ("intorf", "intORF"), ("truncated", "variant"), ("extended", "variant"),
                       ("novel", "novel"), ("noncoding", "novel")):
        if key in n:
            return label
    return n or "other"


class Engine(BaseEngine):
    API = ("overview", "periodicity", "orfs", "te", "results", "gene", "export", "files")
    REPLAY = ("te", "export")

    def __init__(self, run_dir: str):
        super().__init__(run_dir)
        self.res = self.dir / "results"
        self.final = self.res / "final"
        self.rows = self.params.get("samples") or []
        f = self.res / COUNTS
        if not f.exists():
            raise FileNotFoundError(f"No gene counts in this run's results ({COUNTS}). Check the pipeline log on the Run page.")
        self.counts, self.names = read_counts(f)
        self.pairs = pairs_of(self.rows)
        self.conditions = list(dict.fromkeys(p["condition"] for p in self.pairs))
        self._psites, self._orfs, self._te = {}, None, None

    def status(self):
        return {**super().status(), "conditions": self.conditions, "pairs": self.pairs, "te": self.state.get("te"),
                "demo": bool(self.run.get("demo"))}

    def _label(self, g):
        n = self.names.get(g, g)
        return n if n == g else f"{n} ({g})"

    # ---------------------------------------------------------------- overview and periodicity
    def overview(self):
        libs = []
        for r in self.rows:
            s = r["sample"]
            libs.append({"sample": s, "type": r.get("type", ""), "condition": r.get("condition", ""), "pair": r.get("pair", ""),
                         "counted": float(self.counts[s].sum()) if s in self.counts.columns else None})
        return {"counts_file": COUNTS, "genes": int(len(self.counts)), "libraries": libs, "pairs": self.pairs,
                "periodicity_samples": self._psite_samples(), "multiqc": MULTIQC if (self.res / MULTIQC).exists() else None,
                "anota2seq": self._anota_contrasts()}

    def _psite_samples(self) -> list[str]:
        d = self.res / RIBOWALTZ
        return sorted(p.name[:-len(".psite.tsv")] for p in d.glob("*.psite.tsv")) if d.exists() else []

    def _psite(self, sample: str) -> dict:
        if sample in self._psites:
            return self._psites[sample]
        d = self.res / RIBOWALTZ
        f = d / f"{sample}.psite.tsv"
        if not f.exists():
            raise ValueError(f"No P-site table for {sample}.")
        cols = ["length", "psite_from_start", "psite_from_stop", "psite_region"]
        t = pd.read_csv(f, sep="\t", usecols=cols, nrows=MAX_READS)
        cds = t[t["psite_region"] == "cds"]
        frame = cds["psite_from_start"] % 3
        by_len = []
        for L, grp in cds.groupby("length"):
            fr = (grp["psite_from_start"] % 3).value_counts(normalize=True).reindex([0, 1, 2], fill_value=0)
            by_len.append({"length": int(L), "reads": int((t["length"] == L).sum()), "frames": [round(float(v), 3) for v in fr]})
        offsets = {}
        of = d / f"{sample}.psite_offset.tsv"
        if of.exists():
            o = pd.read_csv(of, sep="\t")
            col = "corrected_offset_from_5" if "corrected_offset_from_5" in o.columns else "offset_from_5"
            offsets = {int(L): int(v) for L, v in zip(o["length"], o[col])}
        for b in by_len:
            b["offset"] = offsets.get(b["length"])
        out = {"sample": sample, "reads": int(len(t)), "capped": len(t) >= MAX_READS,
               "frames": [round(float(v), 3) for v in frame.value_counts(normalize=True).reindex([0, 1, 2], fill_value=0)],
               "regions": {k: round(float(v), 3) for k, v in t["psite_region"].value_counts(normalize=True).items()},
               "by_length": by_len,
               "start": {"x": list(range(START_WIN[0], START_WIN[1] + 1)), "y": window(t["psite_from_start"], *START_WIN)},
               "stop": {"x": list(range(STOP_WIN[0], STOP_WIN[1] + 1)), "y": window(t["psite_from_stop"], *STOP_WIN)}}
        self._psites[sample] = out
        return out

    def periodicity(self, sample: str = ""):
        names = self._psite_samples()
        if not names:
            return {"samples": [], "message": "No riboWaltz P-site tables in this run (it may have been skipped)."}
        summary = [{"sample": s, "frame0": self._psite(s)["frames"][0], "reads": self._psite(s)["reads"]} for s in names]
        info = {s["sample"]: s["frame0"] for s in summary}
        if self.state.get("periodicity") != info:
            self.state["periodicity"] = info
            self._record("checked periodicity", frame0=info,
                         offsets={s: {b["length"]: b["offset"] for b in self._psite(s)["by_length"]} for s in names})
        return {"samples": names, "summary": summary, "detail": self._psite(sample if sample in names else names[0])}

    # ---------------------------------------------------------------- ORFs
    def _load_orfs(self) -> pd.DataFrame:
        if self._orfs is not None:
            return self._orfs
        cat = sorted((self.res / CATALOGUE_DIR).glob("*.catalogue.tsv")) if (self.res / CATALOGUE_DIR).exists() else []
        if cat:
            t = pd.read_csv(cat[0], sep="\t")
            src = "the ORF catalogue (" + ", ".join(c[len("called_by_"):] for c in t.columns if c.startswith("called_by_")) + ")"
            t["class"] = [orf_class(x) for x in t.get("orf_class", t.get("orf_type_native", pd.Series([""] * len(t))))]
            t = t.rename(columns={"aa_length": "aa", "orf_id": "id", "gene_id": "gene", "transcript_id": "transcript"})
        elif (self.res / RIBOTISH).exists():
            t = pd.read_csv(self.res / RIBOTISH, sep="\t")
            src = "Ribo-TISH"
            t["class"] = [orf_class(x) for x in t["TisType"]]
            t = t.rename(columns={"AALen": "aa", "Gid": "gene", "Tid": "transcript"})
            t["id"] = [f"{tid}:{a}-{b}" for tid, a, b in zip(t["transcript"], t["Start"], t["Stop"])]
        else:
            raise FileNotFoundError("No ORF predictions in this run's results (Ribo-TISH and the ORF catalogue were not found).")
        t["gene"] = t["gene"].astype(str)
        t["gene_name"] = [self.names.get(g, g) for g in t["gene"]]
        t.attrs["source"] = src
        self._orfs = t
        return t

    def orfs(self, cls: str = "", q: str = "", n: int = 300):
        t = self._load_orfs()
        classes = t["class"].value_counts()
        info = {"orfs": int(len(t)), "classes": {k: int(v) for k, v in classes.items()}, "source": t.attrs["source"]}
        if self.state.get("orfs") != info:
            self.state["orfs"] = info
            self._record("read the ORF predictions", **info)
        sel = t
        if cls:
            sel = sel[sel["class"] == cls]
        if q:
            low = q.lower()
            sel = sel[sel["gene"].str.lower().str.contains(low, regex=False) | sel["gene_name"].str.lower().str.contains(low, regex=False)]
        aa = t.groupby("class")["aa"].median()
        cols = [c for c in ("id", "gene", "gene_name", "transcript", "class", "aa", "chrom", "start", "end", "strand") if c in sel.columns]
        return {**info, "median_aa": {k: float(v) for k, v in aa.items()}, "shown": int(min(len(sel), int(n))), "matching": int(len(sel)),
                "rows": sel[cols].head(int(n)).replace({np.nan: None}).to_dict("records")}

    # ---------------------------------------------------------------- translational efficiency
    def _anota_contrasts(self) -> list[str]:
        d = self.res / ANOTA
        return sorted(p.name.split(".translation.")[0] for p in d.glob("*.translation.anota2seq.results.tsv")) if d.exists() else []

    def _anota(self, test: str, reference: str):
        """The pipeline's anota2seq 'translation' result for this comparison, if it made one."""
        for c in self._anota_contrasts():
            parts = re.split(r"_vs_", c)
            if len(parts) == 2 and parts == [test, reference]:
                t = pd.read_csv(self.res / ANOTA / f"{c}.translation.anota2seq.results.tsv", sep="\t")
                return c, t.set_index(t.columns[0])
        return None, None

    def te(self, test: str, reference: str, min_count: float = 10, alpha: float = 0.05):
        if test == reference or test not in self.conditions or reference not in self.conditions:
            raise ValueError("Choose two different conditions that both have Ribo-seq/RNA-seq pairs.")
        r = te_table(self.counts, self.pairs, test, reference, float(min_count))
        alpha = float(alpha)
        r["class"] = classify(r, alpha)
        self._te = r
        pairs = [p["pair"] for p in self.pairs if p["condition"] in (test, reference)]
        sig = r["class"].isin(["translation", "buffering"])
        info = {"test": test, "reference": reference, "min_count": float(min_count), "alpha": alpha, "prior_df": PRIOR_DF,
                "pairs": pairs, "genes_tested": int(len(r)),
                "up": int((sig & (r["te_log2fc"] > 0)).sum()), "down": int((sig & (r["te_log2fc"] < 0)).sum()),
                "classes": {k: int(v) for k, v in r["class"].value_counts().items()}}
        c, an = self._anota(test, reference)
        if an is not None and "apvRvmPAdj" in an.columns:
            a_sig = set(an.index[an["apvRvmPAdj"] < alpha].astype(str))
            ours = set(r.index[sig])
            info["anota2seq"] = {"contrast": c, "significant": len(a_sig), "both": len(a_sig & ours)}
        self.state["te"] = info
        self._record("compared translational efficiency", **info)
        return info

    def _need_te(self) -> pd.DataFrame:
        if self._te is None:
            p = self.state.get("te")
            if not p:
                raise ValueError("Compare two conditions first.")
            self.te(p["test"], p["reference"], p["min_count"], p["alpha"])
        return self._te

    def results(self, cls: str = "", n: int = 300):
        r = self._need_te()
        sel = r if not cls else r[r["class"] == cls]
        sel = sel.sort_values("te_padj", kind="stable").head(int(n))
        rows = [{"gene": g, "label": self._label(g), "class": c, "rna": round(float(a), 3), "ribo": round(float(b), 3),
                 "te": round(float(t), 3), "padj": float(p)} for g, c, a, b, t, p in
                zip(sel.index, sel["class"], sel["rna_log2fc"], sel["ribo_log2fc"], sel["te_log2fc"], sel["te_padj"])]
        # Intent: every gene for the scatter (RNA-seq change against Ribo-seq change), compactly.
        return {**self.state["te"], "rows": rows,
                "points": {"gene": list(r.index), "rna": r["rna_log2fc"].round(3).tolist(), "ribo": r["ribo_log2fc"].round(3).tolist(),
                           "class": r["class"].tolist()}}

    def gene(self, q: str):
        q = (q or "").strip()
        if not q:
            raise ValueError("Type a gene name or ID.")
        hits = [g for g in self.counts.index if g == q or self.names.get(g) == q]
        if not hits:
            low = q.lower()
            hits = [g for g in self.counts.index if low in g.lower() or low in str(self.names.get(g, "")).lower()][:20]
            if not hits:
                raise ValueError(f"No gene matches '{q}'.")
            if len(hits) > 1:
                return {"choices": [{"id": g, "label": self._label(g)} for g in hits]}
        g = hits[0]
        ribo = self.counts[[p["ribo"] for p in self.pairs]]
        rna = self.counts[[p["rna"] for p in self.pairs]]
        nr, nn = ribo.loc[g] / size_factors(ribo).values, rna.loc[g] / size_factors(rna).values
        pairs = [{"pair": p["pair"], "condition": p["condition"], "ribo": round(float(a), 1), "rna": round(float(b), 1),
                  "log2_te": round(float(np.log2(a + 1) - np.log2(b + 1)), 3)} for p, a, b in zip(self.pairs, nr.values, nn.values)]
        out = {"id": g, "label": self._label(g), "pairs": pairs}
        if self._te is not None and g in self._te.index:
            x = self._te.loc[g]
            out["te"] = {"class": x["class"], "te_log2fc": round(float(x["te_log2fc"]), 3), "padj": float(x["te_padj"]),
                         "rna_log2fc": round(float(x["rna_log2fc"]), 3), "ribo_log2fc": round(float(x["ribo_log2fc"]), 3)}
        try:
            o = self._load_orfs()
            out["orfs"] = o.loc[o["gene"] == g, [c for c in ("id", "class", "aa", "start", "end") if c in o.columns]].replace({np.nan: None}).to_dict("records")
        except FileNotFoundError:
            out["orfs"] = []
        return out

    # ---------------------------------------------------------------- export
    def export(self):
        self.final.mkdir(exist_ok=True)
        written = []
        names = self._psite_samples()
        if names:
            with open(self.final / "periodicity.csv", "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["sample", "read_length", "reads", "frame0", "frame1", "frame2", "psite_offset"])
                for s in names:
                    for b in self._psite(s)["by_length"]:
                        w.writerow([s, b["length"], b["reads"], *b["frames"], b["offset"] if b["offset"] is not None else ""])
            written.append("periodicity.csv")
        try:
            o = self._load_orfs()
            o.drop(columns=[c for c in o.columns if c.startswith("score_")]).to_csv(self.final / "orfs.csv", index=False)
            written.append("orfs.csv")
        except FileNotFoundError:
            pass
        if self.state.get("te"):
            r = self._need_te()
            p = self.state["te"]
            t = r.copy()
            t.insert(0, "gene_name", [self.names.get(g, g) for g in t.index])
            t.rename_axis("gene_id").round(6).to_csv(self.final / f"te_{p['test']}_vs_{p['reference']}.csv")
            written.append(f"te_{p['test']}_vs_{p['reference']}.csv")
        self._record("exported results", files=written)
        return {"files": written}

    def files(self):
        return [{"name": f"final/{f.name}", "size": f.stat().st_size} for f in sorted(self.final.glob("*"))] if self.final.exists() else []
