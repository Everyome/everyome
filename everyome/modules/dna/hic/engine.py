"""Live session for Hi-C: check each library, look at contact maps at any resolution, see how contacts fall with
distance, A/B compartments along each chromosome, and TAD boundaries; export the tracks.

Reads what nf-core/hic wrote under the run's results/ (helpers.py lists the paths): balanced maps (.cool, .mcool),
HiC-Pro's statistics and the compartment eigenvectors. Compartment signs are set from the genome's GC content; TAD
boundaries are called here from an insulation score, with HiCExplorer's own calls (if the pipeline made them) shown
for comparison. Maps are read with h5py (cool.py), a band or a region at a time, so large genomes fit in memory.
Every choice that changes a result is recorded in order for the write-up; exports go to results/final/.
"""
from __future__ import annotations

import csv
import gzip
import json
import re
from pathlib import Path

import numpy as np

from everyome.core.engine import BaseEngine

from . import cool
from .helpers import read_stats

MAX_MAP = 400          # bins per side of a drawn map
MAX_EIG = 6000         # bins per chromosome for the compartment eigenvector


def _num(v, d=4):
    return None if v is None or not np.isfinite(v) else round(float(v), d)


class Engine(BaseEngine):
    API = ("overview", "contact_map", "decay", "compartments", "compartment_track", "tads", "tad_track", "export", "files")
    REPLAY = ("compartments", "tads", "export")

    def __init__(self, run_dir: str):
        super().__init__(run_dir)
        self.res = self.dir / "results"
        rows = self.params.get("samples") or []
        self.maps = {s: self._find_maps(s) for s in dict.fromkeys(r["sample"] for r in rows)}
        self.maps = {s: m for s, m in self.maps.items() if m}
        if not self.maps:
            raise FileNotFoundError("No contact maps (.cool or .mcool) were found in this run's results. Check the pipeline log on the Run page.")
        self.samples = list(self.maps)
        self._cools = {}
        first = self.cool(self.samples[0], self.resolutions()[0])
        self.chroms = list(zip(first.chroms, first.lengths))

    # ---------------------------------------------------------------- finding files
    def _find_maps(self, s: str) -> dict:
        """{resolution: (file, resolution inside an .mcool or None)}; a balanced single-resolution map wins."""
        d, out = self.res / "contact_maps" / "cool", {}
        if (d / f"{s}.mcool").exists():
            out.update({r: (d / f"{s}.mcool", r) for r in cool.resolutions(d / f"{s}.mcool")})
        for f in sorted(d.glob(f"{s}.*_balanced.cool")) if d.exists() else []:
            m = re.fullmatch(re.escape(s) + r"\.(\d+)_balanced\.cool", f.name)
            if m:
                out[int(m.group(1))] = (f, None)
        return out

    def cool(self, sample: str, res: int) -> cool.Cool:
        key = (sample, int(res))
        if key not in self._cools:
            if sample not in self.maps or int(res) not in self.maps[sample]:
                raise ValueError(f"No {int(res):,} bp map for {sample}.")
            path, r = self.maps[sample][int(res)]
            self._cools[key] = cool.Cool(path, r)
        return self._cools[key]

    def resolutions(self) -> list[int]:
        return sorted(set.intersection(*(set(m) for m in self.maps.values())))

    def _near(self, target) -> int:
        rs = self.resolutions()
        try:
            t = int(str(target).split(",")[0])
        except ValueError:
            return rs[0]
        return min(rs, key=lambda r: (abs(np.log(r / t)), r))

    def _stats(self, s: str) -> dict:
        d = self.res / "hicpro" / "stats" / s
        texts = {k: "".join(f.read_text() for f in sorted(d.glob(f"*{k}"))) for k in ("pairstat", "RSstat", "mergestat")} if d.exists() else {}
        return {"sample": s, **read_stats(texts)}

    def status(self):
        return {**super().status(), "samples": self.samples, "compartments": self.state.get("compartments"), "tads": self.state.get("tads")}

    # ---------------------------------------------------------------- overview and maps
    def overview(self):
        stats = [self._stats(s) for s in self.samples]
        comp_files = sorted({int(m.group(1)) for f in (self.res / "compartments").glob("*.cis.vecs.tsv")
                             for m in [re.search(r"\.(\d+)_compartments\.cis\.vecs\.tsv$", f.name)] if m}) if (self.res / "compartments").exists() else []
        info = {"samples": self.samples, "resolutions": self.resolutions(),
                "valid_pairs": {x["sample"]: x["unique"] for x in stats}}
        if self.state.get("overview") != info:
            self.state["overview"] = info
            self._record("read the contact maps", **info)
        p = self.params
        return {**info, "stats": stats, "chroms": [{"name": c, "length": n} for c, n in self.chroms],
                "compartment_files": comp_files, "fasta": bool(self._fasta()),
                "suggest": {"map": self._near(p.get("res_zoomify") or 5000), "decay": self._near(p.get("res_dist_decay") or 1_000_000),
                            "compartments": self._near(comp_files[0] if comp_files else p.get("res_compartments") or 250_000),
                            "tads": self._near(p.get("res_tads") or 40_000)}}

    def contact_map(self, sample: str, chrom: str, start: int = 0, end: int | None = None, res: int | None = None, balanced: bool = True):
        n = dict(self.chroms).get(chrom)
        if n is None:
            raise ValueError(f"No chromosome called {chrom}.")
        start, end = max(0, int(start or 0)), min(n, int(end or n))
        if end <= start:
            raise ValueError("The end must be after the start.")
        res = int(res) if res else next((r for r in self.resolutions() if (end - start) / r <= 250), self.resolutions()[-1])
        C = self.cool(sample, res)
        lo, _ = C.chrom_bins(chrom)
        a, b = lo + start // res, lo + -(-end // res)
        if b - a > MAX_MAP:
            raise ValueError(f"That region is {b - a:,} bins at {res:,} bp. Zoom in or choose a coarser resolution (at most {MAX_MAP} bins a side).")
        m = C.matrix(a, b, balanced=balanced and C.weight is not None)
        with np.errstate(divide="ignore", invalid="ignore"):
            lg = np.where(m > 0, np.log10(m), np.nan)
        fin = lg[np.isfinite(lg)]
        out = {"sample": sample, "chrom": chrom, "res": res, "start": (a - lo) * res, "end": min(n, (b - lo) * res), "balanced": bool(balanced and C.weight is not None),
               "values": [[_num(v, 3) for v in row] for row in lg],
               "lo": _num(np.percentile(fin, 2), 3) if len(fin) else 0, "hi": _num(np.percentile(fin, 99.5), 3) if len(fin) else 1}
        tads = self._load("tads")
        if tads:
            out["boundaries"] = [x["pos"] for x in tads["samples"].get(sample, {}).get(chrom, {}).get("boundaries", []) if out["start"] <= x["pos"] <= out["end"]]
        return out

    def decay(self, res: int | None = None):
        res = int(res) if res else self._near(self.params.get("res_dist_decay") or 1_000_000)
        curves, slopes = {}, {}
        shortest = min(n for _, n in self.chroms)
        for s in self.samples:
            C, ds, ps = self.cool(s, res), [], []
            for c, _ in self.chroms:
                d, p = C.decay(c)
                ds.append(d)
                ps.append(p)
            d, p = np.concatenate(ds), np.concatenate(ps)
            # Intent: average over chromosomes in log-spaced distance bins, as a contact probability (sums to 1).
            edges = np.unique(np.geomspace(res, d.max() + res, 40).astype(int))
            k = np.digitize(d, edges)
            pts = [(float(np.exp(np.log(d[k == j]).mean())), float(np.nanmean(p[k == j]))) for j in np.unique(k)]
            pts = [(x, y) for x, y in pts if np.isfinite(y) and y > 0]
            tot = sum(y for _, y in pts) or 1
            curves[s] = [[round(x), y / tot] for x, y in pts]
            sel = [(x, y) for x, y in pts if 2 * res <= x <= shortest / 4]
            slopes[s] = round(float(np.polyfit(np.log10([x for x, _ in sel]), np.log10([y for _, y in sel]), 1)[0]), 2) if len(sel) >= 3 else None
        info = {"res": res, "slopes": slopes, "range": [2 * res, shortest // 4]}
        if self.state.get("decay") != info:
            self.state["decay"] = info
            self._record("measured distance decay", **info)
        return {**info, "curves": curves}

    # ---------------------------------------------------------------- compartments
    def _fasta(self) -> str:
        f = self.params.get("fasta") or ""
        return f if f and Path(f).exists() else ""

    def _gc(self, res: int) -> dict | None:
        """GC content of each bin of the genome, from the FASTA (cached in the session folder)."""
        cache = self.out / f"gc_{res}.json"
        if cache.exists():
            return json.loads(cache.read_text())
        f = self._fasta()
        if not f:
            return None
        out, name, parts = {}, None, []

        def flush():
            if name is not None:
                s = np.frombuffer("".join(parts).upper().encode(), dtype=np.uint8)
                nb = -(-len(s) // res)
                gc = np.isin(s, [ord("G"), ord("C")]).astype(float)
                acgt = np.isin(s, [ord("A"), ord("C"), ord("G"), ord("T")]).astype(float)
                pad = nb * res - len(s)
                g, a = np.pad(gc, (0, pad)).reshape(nb, res).sum(1), np.pad(acgt, (0, pad)).reshape(nb, res).sum(1)
                out[name] = [_num(x) for x in np.where(a > res / 4, g / np.maximum(a, 1), np.nan)]
        with (gzip.open(f, "rt") if f.endswith(".gz") else open(f)) as fh:
            for line in fh:
                if line.startswith(">"):
                    flush()
                    name, parts = line[1:].split()[0], []
                else:
                    parts.append(line.strip())
            flush()
        cache.write_text(json.dumps(out))
        return out

    def _pipeline_vecs(self, sample: str, res: int) -> dict | None:
        f = self.res / "compartments" / f"{sample}.{res}_compartments.cis.vecs.tsv"
        if not f.exists():
            return None
        out = {}
        for r in csv.DictReader(open(f), delimiter="\t"):
            out.setdefault(r["chrom"], []).append(float(r["E1"]) if r.get("E1") not in (None, "", "nan", "NaN") else np.nan)
        return {c: np.array(v) for c, v in out.items()}

    def compartments(self, res: int | None = None):
        res = int(res) if res else self._near(self.params.get("res_compartments") or 250_000)
        return self._background(self._compartments, res)

    def _compartments(self, res: int):
        self._prog(5, "Reading the genome's GC content…")
        gc = self._gc(res)
        tracks, a_share, flipped, sources = {}, {}, {}, set()
        for k, s in enumerate(self.samples):
            self._prog(10 + 85 * k // len(self.samples), f"Compartments for {s}…")
            given = self._pipeline_vecs(s, res)
            sources.add("pipeline" if given else "session")
            tracks[s], flipped[s] = {}, []
            C = None if given else self.cool(s, res)
            for c, n in self.chroms:
                if given and c in given:
                    e = given[c]
                elif C is not None:
                    lo, hi = C.chrom_bins(c)
                    if hi - lo > MAX_EIG:
                        continue
                    e = cool.eigenvector(C.matrix(lo, hi))
                else:
                    continue
                if gc and c in gc:
                    g = np.array([np.nan if v is None else v for v in gc[c]])[:len(e)]
                    ok = np.isfinite(e[:len(g)]) & np.isfinite(g)
                    # Intent: the eigenvector's sign is arbitrary; make it rise with GC (A = open, GC-rich).
                    if ok.sum() > 2 and np.corrcoef(e[:len(g)][ok], g[ok])[0, 1] < 0:
                        e = -e
                        flipped[s].append(c)
                tracks[s][c] = [_num(v) for v in e]
            vals = np.array([v for t in tracks[s].values() for v in t if v is not None])
            a_share[s] = round(100 * float((vals > 0).mean()), 1) if len(vals) else None
        info = {"res": res, "source": "pipeline" if sources == {"pipeline"} else "session" if sources == {"session"} else "mixed",
                "oriented": "gc" if gc else "none", "a_share": a_share}
        (self.out / "compartments.json").write_text(json.dumps({**info, "samples": tracks, "flipped": flipped}))
        self.state["compartments"] = info
        self._record("called compartments", **info)

    def compartment_track(self):
        c = self._load("compartments")
        if not c:
            raise ValueError("Call compartments first.")
        return c

    # ---------------------------------------------------------------- TADs
    def tads(self, res: int | None = None, window: int = 5, min_strength: float = 0.2):
        res = int(res) if res else self._near(self.params.get("res_tads") or 40_000)
        window, min_strength = int(window), float(min_strength)
        if not 2 <= window <= 50:
            raise ValueError("The window should be between 2 and 50 bins.")
        return self._background(self._tads, res, window, min_strength)

    def _hicexplorer(self, sample: str, res: int) -> dict:
        f = self.res / "tads" / "hicExplorer" / f"{sample}.{res}_balanced_hicfindtads_boundaries.bed"
        out = {}
        for line in open(f) if f.exists() else []:
            p = line.split("\t")
            if len(p) >= 3 and p[1].isdigit():
                out.setdefault(p[0], []).append((int(p[1]) + int(p[2])) // 2)
        return out

    def _tads(self, res: int, window: int, min_strength: float):
        result, counts, sizes, agree = {}, {}, {}, {}
        for k, s in enumerate(self.samples):
            self._prog(5 + 90 * k // len(self.samples), f"Insulation for {s}…")
            C, hx, result[s] = self.cool(s, res), self._hicexplorer(s, res), {}
            all_sizes, near, total_hx = [], 0, 0
            for c, n in self.chroms:
                lo, hi = C.chrom_bins(c)
                score = cool.insulation(C.band(lo, hi, 2 * window), window)
                bs = [{"pos": i * res + res // 2, "strength": round(st, 3)} for i, st in cool.boundaries(score, min_strength)]
                edges = [0] + [b["pos"] for b in bs] + [n]
                all_sizes += [b - a for a, b in zip(edges, edges[1:])]
                theirs = hx.get(c, [])
                total_hx += len(theirs)
                near += sum(1 for p in theirs if any(abs(p - b["pos"]) <= res for b in bs))
                result[s][c] = {"score": [_num(v, 3) for v in score], "boundaries": bs, "hicexplorer": theirs}
            counts[s] = sum(len(v["boundaries"]) for v in result[s].values())
            sizes[s] = int(np.median(all_sizes)) if all_sizes else None
            agree[s] = round(100 * near / total_hx, 1) if total_hx else None
        info = {"res": res, "window": window, "window_bp": window * res, "min_strength": min_strength,
                "boundaries": counts, "median_size": sizes, "hicexplorer_agree": agree}
        (self.out / "tads.json").write_text(json.dumps({**info, "samples": result}))
        self.state["tads"] = info
        self._record("called TAD boundaries", **info)

    def tad_track(self, sample: str, chrom: str):
        t = self._load("tads")
        if not t:
            raise ValueError("Find TAD boundaries first.")
        x = t["samples"].get(sample, {}).get(chrom)
        if x is None:
            raise ValueError(f"No TADs for {sample} on {chrom}.")
        return {**{k: t[k] for k in ("res", "window", "min_strength")}, "sample": sample, "chrom": chrom, **x}

    def _load(self, name: str) -> dict | None:
        f = self.out / f"{name}.json"
        return json.loads(f.read_text()) if f.exists() else None

    # ---------------------------------------------------------------- export
    def export(self):
        out = self.res / "final"
        out.mkdir(exist_ok=True)
        files = []
        with open(out / "libraries.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            keys = ["pairs", "valid", "unique", "valid_pct", "duplicates_pct", "cis_pct", "long_pct"]
            w.writerow(["sample", "read_pairs", "valid_pairs", "valid_pairs_without_duplicates", "valid_percent", "duplicate_percent",
                        "cis_percent", "cis_over_20kb_percent"])
            for s in self.samples:
                st = self._stats(s)
                w.writerow([s] + ["" if st[k] is None else st[k] for k in keys])
        files.append("libraries.csv")
        dec = self.state.get("decay") or {}
        curves = self.decay(dec["res"])["curves"] if dec else self.decay()["curves"]
        with open(out / "distance_decay.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["sample", "distance_bp", "contact_probability"])
            for s, pts in curves.items():
                w.writerows([s, x, f"{y:.6g}"] for x, y in pts)
        files.append("distance_decay.csv")
        comp = self._load("compartments")
        if comp:
            r = comp["res"]
            for s, tr in comp["samples"].items():
                name = f"{s}_compartments_{r}.bedgraph"
                with open(out / name, "w") as fh:
                    fh.write(f'track type=bedGraph name="{s} compartments (E1, {r} bp; positive = A)"\n')
                    for c, n in self.chroms:
                        for i, v in enumerate(tr.get(c, [])):
                            if v is not None:
                                fh.write(f"{c}\t{i * r}\t{min(n, (i + 1) * r)}\t{v}\n")
                files.append(name)
        tads = self._load("tads")
        if tads:
            r = tads["res"]
            for s, by in tads["samples"].items():
                b_name, d_name = f"{s}_tad_boundaries_{r}.bed", f"{s}_tads_{r}.bed"
                with open(out / b_name, "w") as fb, open(out / d_name, "w") as fd:
                    for c, n in self.chroms:
                        bs = by.get(c, {}).get("boundaries", [])
                        for k, b in enumerate(bs):
                            fb.write(f"{c}\t{b['pos'] - r // 2}\t{b['pos'] + r // 2}\tboundary_{c}_{k + 1}\t{b['strength']}\n")
                        edges = [0] + [b["pos"] for b in bs] + [n]
                        for k, (a, b) in enumerate(zip(edges, edges[1:])):
                            fd.write(f"{c}\t{a}\t{b}\tTAD_{c}_{k + 1}\n")
                files += [b_name, d_name]
        self._record("exported results", files=files)
        return {"files": files}

    def files(self):
        out = self.res / "final"
        return [{"name": f"final/{f.name}", "size": f.stat().st_size} for f in sorted(out.glob("*"))] if out.exists() else []
