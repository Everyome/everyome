"""qPCR analysis on this computer: read a plate export, check replicates and controls, estimate efficiencies,
rank reference genes, and work out fold changes between groups.

Relative quantities follow Hellemans et al. (2007): efficiency-corrected, normalised to the geometric mean of the
reference genes, with geNorm M values (Vandesompele et al., 2002) to judge how steady the references are. Every
choice is recorded in order, so the run can be written up and repeated exactly.
"""
from __future__ import annotations

import csv
import io
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from everyome.core.engine import BaseEngine

# Intent: column names used by common instruments (QuantStudio, Bio-Rad CFX, LightCycler, Rotor-Gene) and by hand.
ALIASES = {
    "well": ["well position", "well", "pos", "position"],
    "sample": ["sample name", "sample", "name"],
    "target": ["target name", "target", "detector", "gene", "assay", "detector name"],
    "cq": ["cq", "ct", "cт", "cp", "crt", "c(t)"],
    "task": ["task", "content", "type", "sample type"],
    "quantity": ["quantity", "starting quantity (sq)", "sq", "starting quantity", "concentration"],
}
NO_CQ = {"", "undetermined", "n/a", "na", "nan", "no ct", "no cq", "-", "none"}
# Intent: names people often give reference genes; only a first guess, the user confirms them.
REF_GUESS = re.compile(r"^(ef1a|eef1a\w*|gapdh|actb|actin|b-?actin|18s|rpl\w*|rps\w*|tbp|hprt\w*|ubc|ubq\w*|tub\w*|ppia|b2m|ywhaz|sdha)$", re.I)
CONTROL_GUESS = re.compile(r"^(control|ctrl|ctl|wt|wild.?type|mock|untreated|vehicle|dmso)$", re.I)


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def _task(v, quantity, sample) -> str:
    t = _norm(v) if v is not None and str(v) != "nan" else ""
    if t.startswith(("std", "standard")):
        return "standard"
    if t.startswith(("ntc", "no template", "neg")) or _norm(sample) in ("ntc", "h2o", "water", "no template"):
        return "ntc"
    if not t and quantity is not None and not (isinstance(quantity, float) and math.isnan(quantity)):
        return "standard"
    return "unknown"


def _well_key(w: str):
    m = re.fullmatch(r"([A-Pa-p])0*(\d+)", str(w).strip())
    return (m.group(1).upper(), int(m.group(2))) if m else ("Z", 999)


def read_plate(path: Path) -> pd.DataFrame:
    """One row per well: well, sample, target, task, quantity, cq (NaN when no amplification)."""
    if path.suffix.lower() in (".xlsx", ".xls"):
        raw = pd.read_excel(path, header=None, dtype=str).fillna("").values.tolist()
    else:
        text = path.read_text(errors="replace")
        delim = "\t" if text.count("\t") > text.count(",") else ("," if text.count(",") >= text.count(";") else ";")
        raw = list(csv.reader(io.StringIO(text), delimiter=delim))
    # Intent: instrument exports start with run details; the table begins at the first row naming a Cq/Ct column.
    head = next((i for i, row in enumerate(raw) if {_norm(c) for c in row} & set(ALIASES["cq"])), None)
    if head is None:
        raise ValueError(f"Couldn't find a Cq or Ct column in {path.name}. The table needs columns for well, sample, target and Cq.")
    cols = [_norm(c) for c in raw[head]]
    pick = {}
    for key, names in ALIASES.items():
        pick[key] = next((cols.index(n) for n in names if n in cols), None)
    missing = [k for k in ("sample", "target", "cq") if pick[k] is None]
    if missing:
        raise ValueError(f"{path.name} has no column for {', '.join(missing)} (found: {', '.join(c for c in cols if c)}).")
    rows = []
    for n, row in enumerate(raw[head + 1:]):
        if not any(str(c).strip() for c in row):
            continue
        get = lambda k: row[pick[k]] if pick[k] is not None and pick[k] < len(row) else ""  # noqa: E731
        sample, target = str(get("sample")).strip(), str(get("target")).strip()
        if not target:
            continue
        cq_s = _norm(get("cq"))
        try:
            cq = float("nan") if cq_s in NO_CQ else float(cq_s.replace(",", "."))
        except ValueError:
            raise ValueError(f"Row {head + n + 2}: '{get('cq')}' is not a Cq value.") from None
        q_s = str(get("quantity")).strip().replace(",", ".")
        try:
            quantity = float(q_s) if q_s else float("nan")
        except ValueError:
            quantity = float("nan")
        well = str(get("well")).strip() or f"row{n + 1}"
        rows.append({"well": well, "sample": sample, "target": target, "task": _task(get("task"), quantity, sample),
                     "quantity": quantity, "cq": cq})
    if not rows:
        raise ValueError(f"{path.name} has a header but no wells.")
    df = pd.DataFrame(rows)
    if df["well"].duplicated().any():          # Intent: some exports repeat wells across plates; keep them apart.
        df["well"] = df["well"] + "#" + df.groupby("well").cumcount().add(1).astype(str)
    return df


def _group_of(sample: str) -> str:
    """A first guess at a sample's group: its name without a trailing replicate number (control_2 -> control)."""
    return re.sub(r"[\s_.-]*(rep|r|bio)?\d+$", "", sample, flags=re.I) or sample


def _bh(p: list) -> list:
    """Benjamini–Hochberg adjusted p-values (None stays None)."""
    idx = [i for i, v in enumerate(p) if v is not None]
    out = [None] * len(p)
    if not idx:
        return out
    vals = np.array([p[i] for i in idx])
    order = np.argsort(vals)
    adj = vals[order] * len(vals) / np.arange(1, len(vals) + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1].clip(max=1)
    for rank, j in enumerate(order):
        out[idx[j]] = float(adj[rank])
    return out


def _r(v, n=3):
    return None if v is None or (isinstance(v, float) and not math.isfinite(v)) else round(float(v), n)


class Engine(BaseEngine):
    API = ("overview", "plate", "exclude", "efficiencies", "references", "set_references", "set_groups", "expression", "export", "files")
    REPLAY = ("exclude", "set_references", "set_groups", "export")

    def __init__(self, run_dir: str):
        super().__init__(run_dir)
        if not self.params.get("results_file"):
            raise ValueError("Choose the qPCR results file exported from your instrument.")
        self.path = Path(self.params["results_file"])
        self.df = read_plate(self.path)
        self.unknowns = self.df[self.df.task == "unknown"]
        self.targets = sorted(self.df.target.unique(), key=str.lower)
        self.samples = sorted(self.unknowns["sample"].unique(), key=str.lower)
        st = self.state
        st.setdefault("excluded", [])
        if "groups" not in st:
            st["groups"] = {s: _group_of(s) for s in self.samples}
        if "control" not in st:
            gs = sorted(set(st["groups"].values()), key=str.lower)
            st["control"] = (self.params.get("control_group") or "").strip() or next((g for g in gs if CONTROL_GUESS.match(g)), gs[0] if gs else None)
        if "references" not in st:
            given = [g for g in re.split(r"[\s,;]+", self.params.get("reference_genes") or "") if g]
            st["references"] = [g for g in given if g in self.targets] or [t for t in self.targets if REF_GUESS.match(t)]

    def status(self):
        return {**super().status(), "file": self.path.name, "wells": len(self.df), "targets": len(self.targets), "samples": len(self.samples)}

    # ---------------------------------------------------------------- helpers
    def _kept(self) -> pd.DataFrame:
        return self.df[~self.df.well.isin(self.state["excluded"])]

    def _assumed(self) -> float:
        return float(self.params.get("default_efficiency") or 100) / 100

    def _effs(self) -> dict:
        """Amplification efficiency (as a fraction, 1.0 = doubling each cycle) for each target."""
        out = {}
        method = self.params.get("method") or "efficiency"
        std = self._kept()
        std = std[(std.task == "standard") & std.cq.notna() & (std.quantity > 0)]
        for t in self.targets:
            d = std[std.target == t]
            row = {"target": t, "points": int(len(d)), "dilutions": int(d.quantity.nunique()), "slope": None, "intercept": None,
                   "r2": None, "efficiency": self._assumed(), "source": "assumed"}
            if d.quantity.nunique() >= 3:
                fit = stats.linregress(np.log10(d.quantity.to_numpy()), d.cq.to_numpy())
                eff = 10 ** (-1 / fit.slope) - 1 if fit.slope < 0 else float("nan")
                row.update(slope=_r(fit.slope), intercept=_r(fit.intercept), r2=_r(fit.rvalue ** 2, 4),
                           measured=_r(eff, 4), points_xy=[[_r(math.log10(q), 4), _r(c)] for q, c in zip(d.quantity, d.cq)])
                if method == "efficiency" and math.isfinite(eff) and eff > 0:
                    row.update(efficiency=_r(eff, 4), source="standard curve")
            out[t] = row
        return out

    def _sample_cq(self) -> pd.DataFrame:
        """Mean Cq of the kept technical replicates for each sample and target (samples × targets)."""
        k = self._kept()
        k = k[(k.task == "unknown") & k.cq.notna()]
        return k.groupby(["sample", "target"]).cq.mean().unstack().reindex(index=self.samples, columns=self.targets)

    def _rq(self) -> pd.DataFrame:
        """Efficiency-corrected relative quantity of each target in each sample, against the target's mean Cq."""
        cq, effs = self._sample_cq(), self._effs()
        return pd.DataFrame({t: (1 + effs[t]["efficiency"]) ** (cq[t].mean() - cq[t]) for t in self.targets})

    # ---------------------------------------------------------------- the plate
    def overview(self):
        d = self.df
        return {"file": self.path.name, "wells": int(len(d)), "targets": self.targets, "samples": self.samples,
                "standards": int((d.task == "standard").sum()), "ntc": int((d.task == "ntc").sum()),
                "no_cq": int(d[d.task == "unknown"].cq.isna().sum()), "excluded": self.state["excluded"],
                "groups": self.state["groups"], "control": self.state["control"], "references": self.state["references"],
                "method": self.params.get("method") or "efficiency"}

    def plate(self):
        """Every well for the plate view, replicate sets with their spread, and the no-template controls."""
        sd_max, ntc_min = float(self.params.get("replicate_sd") or 0.3), float(self.params.get("ntc_cutoff") or 35)
        excl = set(self.state["excluded"])
        wells = [{"well": r.well, "sample": r.sample, "target": r.target, "task": r.task, "cq": _r(r.cq, 2), "excluded": r.well in excl}
                 for r in self.df.itertuples()]
        reps = []
        for (s, t, task), g in self.df[self.df.task != "ntc"].groupby(["sample", "target", "task"], sort=False):
            kept = g[~g.well.isin(excl) & g.cq.notna()]
            sd = float(kept.cq.std()) if len(kept) > 1 else None
            # Intent: suggest the replicate furthest from the median of the others, for sets that spread too far.
            odd = None
            if sd is not None and sd > sd_max and len(kept) >= 3:
                med = kept.cq.median()
                odd = kept.loc[(kept.cq - med).abs().idxmax(), "well"]
            reps.append({"sample": s, "target": t, "task": task, "wells": g.well.tolist(), "cq": [_r(v, 2) for v in g.cq],
                         "mean": _r(kept.cq.mean(), 2) if len(kept) else None, "sd": _r(sd, 3), "flag": bool(sd is not None and sd > sd_max),
                         "suggest": odd, "missing": int(g.cq.isna().sum())})
        ntc = self.df[self.df.task == "ntc"]
        ntcs = [{"well": r.well, "target": r.target, "cq": _r(r.cq, 2),
                 "verdict": "clean" if math.isnan(r.cq) else ("late signal" if r.cq >= ntc_min else "contaminated")} for r in ntc.itertuples()]
        keys = [_well_key(w["well"]) for w in wells]
        size = 384 if any(r > "H" and r != "Z" for r, _ in keys) or any(12 < c < 999 for _, c in keys) else 96
        return {"wells": wells, "replicates": reps, "ntc": ntcs, "size": size, "replicate_sd": sd_max, "ntc_cutoff": ntc_min,
                "flagged": sum(r["flag"] for r in reps)}

    def exclude(self, wells: list[str], include: bool = False):
        known = set(self.df.well)
        bad = [w for w in wells if w not in known]
        if bad:
            raise ValueError(f"No well called {', '.join(bad)} on this plate.")
        cur = set(self.state["excluded"])
        cur = cur - set(wells) if include else cur | set(wells)
        self.state["excluded"] = sorted(cur, key=_well_key)
        self._record("included wells again" if include else "left out wells", wells=sorted(wells, key=_well_key))
        return {"excluded": self.state["excluded"]}

    # ---------------------------------------------------------------- efficiency
    def efficiencies(self):
        return {"targets": list(self._effs().values()), "assumed": self._assumed(), "method": self.params.get("method") or "efficiency"}

    # ---------------------------------------------------------------- reference genes
    def references(self):
        """geNorm ranking (Vandesompele et al., 2002) of every target measured in all samples: drop the least steady
        gene (highest M) one at a time; the last two left are the steadiest pair. Also the M of the chosen references."""
        rq = np.log2(self._rq()).dropna(axis=1, how="any")

        def m_values(genes):
            return {j: float(np.mean([np.std(rq[j] - rq[k], ddof=1) for k in genes if k != j])) for j in genes}
        left, ranking = list(rq.columns), []
        while len(left) > 2:
            m = m_values(left)
            worst = max(left, key=lambda g: (m[g], g))
            ranking.append({"target": worst, "m": _r(m[worst], 3), "left": len(left)})
            left.remove(worst)
        if len(left) == 2:
            m = m_values(left)
            ranking += [{"target": g, "m": _r(m[g], 3), "left": 2} for g in sorted(left)]
        ranking.reverse()                                               # Intent: steadiest first
        chosen = self.state["references"]
        pair = None
        if len(chosen) >= 2 and all(c in rq for c in chosen):
            pair = _r(float(np.mean(list(m_values(chosen).values()))), 3)
        return {"genes": [{**g, "rank": i + 1, "chosen": g["target"] in chosen} for i, g in enumerate(ranking)],
                "chosen": chosen, "chosen_m": pair, "groups": self.state["groups"], "control": self.state["control"]}

    def set_references(self, genes: list[str]):
        bad = [g for g in genes if g not in self.targets]
        if bad:
            raise ValueError(f"No target called {', '.join(bad)} on this plate.")
        if not genes:
            raise ValueError("Choose at least one reference gene (two or more is better).")
        self.state["references"] = list(genes)
        self._record("chose reference genes", genes=list(genes))
        return {"references": self.state["references"]}

    def set_groups(self, groups: dict[str, str], control: str):
        unknown = [s for s in groups if s not in self.samples]
        if unknown:
            raise ValueError(f"No sample called {', '.join(unknown)} on this plate.")
        g = {**self.state["groups"], **{s: str(v).strip() or s for s, v in groups.items()}}
        if control not in g.values():
            raise ValueError(f"No group called {control}.")
        self.state.update(groups=g, control=control)
        self._record("set the groups", groups=g, control=control)
        return {"groups": g, "control": control}

    # ---------------------------------------------------------------- expression
    def _expression(self):
        refs = self.state["references"]
        if not refs:
            raise ValueError("Choose the reference genes first (step 3).")
        rq = self._rq()
        missing = [r for r in refs if rq[r].isna().any()]
        if missing:
            raise ValueError(f"Reference gene {', '.join(missing)} has no Cq in some samples, so those samples can't be normalised.")
        norm = np.exp(np.log(rq[refs]).mean(axis=1))                   # geometric mean of the references
        nrq = rq.div(norm, axis=0)
        groups, control = self.state["groups"], self.state["control"]
        ctrl = [s for s in self.samples if groups[s] == control]
        if not ctrl:
            raise ValueError(f"No samples are in the control group ({control}).")
        log2 = np.log2(nrq)
        base = log2.loc[ctrl].mean()                                    # Intent: control samples average to a fold change of 1
        rel = log2 - base
        others = [g for g in dict.fromkeys(groups[s] for s in self.samples) if g != control]
        rows = []
        for g in others:
            mem = [s for s in self.samples if groups[s] == g]
            ps = []
            block = []
            for t in [t for t in self.targets if t not in refs]:
                a, b = rel.loc[mem, t].dropna(), rel.loc[ctrl, t].dropna()
                diff = float(a.mean() - b.mean()) if len(a) and len(b) else float("nan")
                p = lo = hi = None
                if len(a) >= 2 and len(b) >= 2:
                    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
                    se = math.sqrt(va + vb)
                    if se > 0:
                        df = (va + vb) ** 2 / (va ** 2 / (len(a) - 1) + vb ** 2 / (len(b) - 1))
                        p = float(stats.ttest_ind(a, b, equal_var=False).pvalue)
                        q = stats.t.ppf(0.975, df) * se
                        lo, hi = diff - q, diff + q
                ps.append(p)
                block.append({"group": g, "target": t, "n": int(len(a)), "n_control": int(len(b)), "log2_fc": _r(diff),
                              "fold_change": _r(2 ** diff), "ci_low": _r(2 ** lo) if lo is not None else None,
                              "ci_high": _r(2 ** hi) if hi is not None else None, "p": _r(p, 5)})
            for row, adj in zip(block, _bh(ps)):
                row["p_adj"] = _r(adj, 5)
            rows += block
        return nrq, rel, rows, ctrl

    def expression(self):
        nrq, rel, rows, ctrl = self._expression()
        groups = self.state["groups"]
        points = [{"sample": s, "group": groups[s], "target": t, "log2_rel": _r(rel.loc[s, t])}
                  for s in self.samples for t in self.targets if t not in self.state["references"] and pd.notna(rel.loc[s, t])]
        return {"comparisons": rows, "points": points, "control": self.state["control"], "references": self.state["references"],
                "groups": list(dict.fromkeys(groups[s] for s in self.samples))}

    # ---------------------------------------------------------------- export
    def export(self):
        nrq, rel, rows, _ = self._expression()
        d = self.dir / "results"
        groups = self.state["groups"]
        pd.DataFrame(self.plate()["replicates"]).drop(columns=["suggest"]).to_csv(d / "replicates.csv", index=False)
        eff = pd.DataFrame(self._effs().values()).drop(columns=["points_xy"], errors="ignore")
        eff.to_csv(d / "efficiencies.csv", index=False)
        long = nrq.stack().rename("nrq").reset_index().rename(columns={"level_0": "sample", "level_1": "target"})
        long.insert(1, "group", long["sample"].map(groups))
        long["log2_relative_to_control"] = [rel.loc[s, t] for s, t in zip(long["sample"], long["target"])]
        long.round(5).to_csv(d / "relative_expression.csv", index=False)
        pd.DataFrame(rows).to_csv(d / "fold_changes.csv", index=False)
        ex = self.df[self.df.well.isin(self.state["excluded"])][["well", "sample", "target", "cq"]]
        ex.to_csv(d / "excluded_wells.csv", index=False)
        files = sorted(x.name for x in d.iterdir())
        self.state.update(step="exported", exported=files)
        self._record("exported results", files=files, control=self.state["control"], references=self.state["references"],
                     excluded=self.state["excluded"])
        return {"files": files}

    def files(self):
        d = self.dir / "results"
        return [{"name": p.name, "size": p.stat().st_size} for p in sorted(d.iterdir()) if p.is_file()]
