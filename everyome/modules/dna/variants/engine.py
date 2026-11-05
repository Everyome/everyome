"""Live session for variant calling: what each caller found in each sample, filters (quality, depth, genotype quality,
how many callers agree, type, region), any variant's genotype in every sample, variants that separate two groups,
and export of the filtered set.

Reads the per-sample VCFs nf-core/sarek wrote (results/variant_calling/<caller>/<sample>/) into one table of
variant × caller × sample, cached in session/ so a restarted session opens quickly. Every choice that changes a
result is recorded in order for the write-up.
"""
from __future__ import annotations

import csv
import gzip
import json
import re

import numpy as np

from everyome.core.engine import BaseEngine

from .helpers import vcf_files

TRANSITIONS = {("A", "G"), ("G", "A"), ("C", "T"), ("T", "C")}
DEFAULTS = {"callers": [], "agree": 1, "min_qual": 30.0, "min_dp": 10, "min_gq": 20, "pass_only": True, "vtype": "all", "region": ""}
CALLER_NAMES = {"haplotypecaller": "GATK HaplotypeCaller", "deepvariant": "DeepVariant", "freebayes": "FreeBayes",
                "strelka": "Strelka2", "bcftools": "bcftools", "mpileup": "bcftools"}


def _int(x, missing=-1):
    try:
        return int(x)
    except (TypeError, ValueError):
        return missing


def read_vcf(path):
    """Contigs, sample names and records: (chrom, pos, ref, alt, qual, passed, [(dose, dp, gq, ad_ref, ad_alt) per sample]).
    Multi-allelic sites are split, one record per alternative allele; dose counts copies of that allele (-1 missing)."""
    contigs, samples, recs = [], [], []
    with gzip.open(path, "rt") as fh:
        for line in fh:
            if line.startswith("##contig=<ID="):
                contigs.append(line[13:].split(",")[0].rstrip(">\n"))
                continue
            if line.startswith("#CHROM"):
                samples = line.rstrip("\n").split("\t")[9:]
                continue
            if line.startswith("#") or not line.strip():
                continue
            f = line.rstrip("\n").split("\t")
            alts = f[4].split(",")
            qual = float(f[5]) if f[5] not in (".", "") else 0.0
            passed = f[6] in ("PASS", ".")
            keys = f[8].split(":") if len(f) > 8 else []
            calls = [dict(zip(keys, c.split(":"))) for c in f[9:]]
            for k, alt in enumerate(alts, 1):
                if alt in ("*", ".", "<NON_REF>", "<*>"):
                    continue
                per = []
                for c in calls:
                    gt = re.split(r"[/|]", c.get("GT", "."))
                    dose = -1 if "." in gt else sum(1 for a in gt if a == str(k))
                    ad = (c.get("AD") or "").split(",")
                    per.append((dose, _int(c.get("DP")), _int(c.get("GQ")), _int(ad[0]) if ad[0] else -1, _int(ad[k]) if len(ad) > k else -1))
                recs.append((f[0], int(f[1]), f[3], alt, qual, passed, per))
    return contigs, samples, recs


def vtype(ref: str, alt: str) -> str:
    return "snv" if len(ref) == len(alt) == 1 else "indel" if len(ref) != len(alt) else "other"


def parse_region(region: str):
    """'chr2', 'chr2:18000-24000' or '' -> (chrom, start, end) or None."""
    region = (region or "").strip().replace(",", "")
    if not region:
        return None
    m = re.fullmatch(r"([^:\s]+)(?::(\d+)-(\d+))?", region)
    if not m:
        raise ValueError("Region should look like chr2 or chr2:18000-24000.")
    return m.group(1), int(m.group(2) or 0), int(m.group(3) or 10**12)


class Engine(BaseEngine):
    API = ("overview", "apply_filters", "variants", "variant", "groups", "export", "files")
    REPLAY = ("apply_filters", "groups", "export")

    def __init__(self, run_dir: str):
        super().__init__(run_dir)
        self.res = self.dir / "results"
        self.vcfs = vcf_files(self.res)
        if not self.vcfs:
            raise FileNotFoundError("No variant calls (VCF files) were found in this run's results. Check the pipeline log on the Run page.")
        rows = self.params.get("samples") or []
        self.group_of = {r["sample"]: (r.get("group") or "") for r in rows}
        self._load()

    # ---------------------------------------------------------------- reading
    def _load(self):
        sig = [[str(p.relative_to(self.res)), p.stat().st_size, int(p.stat().st_mtime)] for p in self.vcfs.values()]
        cache, meta = self.out / "variants.npz", self.out / "variants_index.json"
        if cache.exists() and meta.exists() and json.loads(meta.read_text()).get("files") == sig:
            z = np.load(cache)
            for k in z.files:
                setattr(self, k, z[k])
            m = json.loads(meta.read_text())
            self.callers, self.samples, self.contigs = m["callers"], m["samples"], m["contigs"]
            return
        parsed, contigs = {}, []
        for (caller, folder_sample), path in self.vcfs.items():
            cs, names, recs = read_vcf(path)
            contigs += [c for c in cs if c not in contigs]
            parsed[(caller, folder_sample)] = (names or [folder_sample], recs)
        self.callers = sorted({c for c, _ in parsed}, key=lambda c: (list(CALLER_NAMES).index(c) if c in CALLER_NAMES else 99, c))
        listed = [s for s in dict.fromkeys(self.group_of)]
        found = list(dict.fromkeys(n for names, _ in parsed.values() for n in names))
        self.samples = [s for s in listed if s in found] + [s for s in found if s not in listed]
        keys = sorted({(r[0], r[1], r[2], r[3]) for _, recs in parsed.values() for r in recs},
                      key=lambda k: (contigs.index(k[0]) if k[0] in contigs else len(contigs), k[0], k[1], k[2], k[3]))
        contigs += [k[0] for k in keys if k[0] not in contigs]
        index = {k: i for i, k in enumerate(keys)}
        V, C, S = len(keys), len(self.callers), len(self.samples)
        self.dose = np.full((V, C, S), -2, np.int8)          # -2: no record in this caller's file for this sample
        self.dp, self.gq = np.full((V, C, S), -1, np.int32), np.full((V, C, S), -1, np.int32)
        self.adr, self.ada = np.full((V, C, S), -1, np.int32), np.full((V, C, S), -1, np.int32)
        self.qual, self.passed = np.zeros((V, C, S), np.float32), np.zeros((V, C, S), bool)
        for (caller, _), (names, recs) in parsed.items():
            c = self.callers.index(caller)
            cols = [self.samples.index(n) for n in names]
            for chrom, pos, ref, alt, q, ok, per in recs:
                i = index[(chrom, pos, ref, alt)]
                for s, (dose, dp, gq, ar, aa) in zip(cols, per):
                    self.dose[i, c, s], self.dp[i, c, s], self.gq[i, c, s] = dose, dp, gq
                    self.adr[i, c, s], self.ada[i, c, s], self.qual[i, c, s], self.passed[i, c, s] = ar, aa, q, ok
        self.chrom = np.array([k[0] for k in keys], dtype=str)
        self.pos = np.array([k[1] for k in keys], dtype=np.int64)
        self.ref = np.array([k[2] for k in keys], dtype=str)
        self.alt = np.array([k[3] for k in keys], dtype=str)
        self.contigs = contigs
        np.savez_compressed(cache, **{k: getattr(self, k) for k in ("dose", "dp", "gq", "adr", "ada", "qual", "passed", "chrom", "pos", "ref", "alt")})
        meta.write_text(json.dumps({"files": sig, "callers": self.callers, "samples": self.samples, "contigs": self.contigs}))

    def _types(self):
        return np.array([vtype(r, a) for r, a in zip(self.ref, self.alt)])

    def _titv(self, keep) -> float | None:
        snv = keep & (np.char.str_len(self.ref) == 1) & (np.char.str_len(self.alt) == 1)
        ti = sum(1 for r, a in zip(self.ref[snv], self.alt[snv]) if (r, a) in TRANSITIONS)
        tv = int(snv.sum()) - ti
        return round(ti / tv, 2) if tv else None

    # ---------------------------------------------------------------- filters
    def _filters(self) -> dict:
        return {**DEFAULTS, **self.state.get("filters", {})}

    def _apply(self, f: dict):
        """(kept variants, valid calls [V, C, S], consensus genotype [V, S]: dose, 0 not called, -1 uncertain)."""
        sel = [self.callers.index(c) for c in (f["callers"] or self.callers) if c in self.callers]
        if not sel:
            raise ValueError("Choose at least one caller.")
        valid = ((self.dose >= 1) & (self.qual >= f["min_qual"]) & (self.dp >= f["min_dp"]) & (self.gq >= f["min_gq"])
                 & (self.passed | (not f["pass_only"])))[:, sel, :]
        n_callers = valid.any(axis=2).sum(axis=1)
        keep = n_callers >= int(f["agree"])
        t = f["vtype"]
        if t in ("snv", "indel"):
            keep &= self._types() == t
        reg = parse_region(f["region"])
        if reg:
            keep &= (self.chrom == reg[0]) & (self.pos >= reg[1]) & (self.pos <= reg[2])
        # Intent: each sample's genotype comes from the first chosen caller that called it and passed the filters.
        dose = self.dose[:, sel, :]
        first = np.where(valid.any(axis=1), np.argmax(valid, axis=1), -1)
        cons = np.where(first >= 0, np.take_along_axis(dose, np.maximum(first, 0)[:, None, :], axis=1)[:, 0, :], 0).astype(int)
        uncertain = (first < 0) & (dose >= 1).any(axis=1)
        cons[uncertain] = -1
        return keep, valid, cons, sel

    def _summary(self, keep, cons):
        types = self._types()
        return {"kept": int(keep.sum()), "total": int(len(keep)), "snv": int((keep & (types == "snv")).sum()),
                "indel": int((keep & (types == "indel")).sum()), "titv": self._titv(keep),
                "per_sample": [{"sample": s, "het": int(((cons[:, j] == 1) & keep).sum()), "hom": int(((cons[:, j] == 2) & keep).sum()),
                                "uncertain": int(((cons[:, j] == -1) & keep).sum())} for j, s in enumerate(self.samples)]}

    # ---------------------------------------------------------------- API
    def overview(self):
        types = self._types()
        per = []
        for c, caller in enumerate(self.callers):
            for s, sample in enumerate(self.samples):
                called = (self.dose[:, c, s] >= 1) & self.passed[:, c, s]
                per.append({"caller": caller, "sample": sample, "variants": int(called.sum()), "snv": int((called & (types == "snv")).sum()),
                            "indel": int((called & (types == "indel")).sum()), "titv": self._titv(called),
                            "het": int((called & (self.dose[:, c, s] == 1)).sum()), "hom": int((called & (self.dose[:, c, s] == 2)).sum())})
        called = (self.dose >= 1) & self.passed
        agree = [{"sample": s, "by": [int((called[:, :, j].sum(axis=1) == k).sum()) for k in range(1, len(self.callers) + 1)]}
                 for j, s in enumerate(self.samples)]
        edges = [0, 5, 10, 20, 30, 50, 100, 200, 500, 1e9]
        qual = {c: np.histogram(self.qual[:, k, :][self.dose[:, k, :] >= 1], edges)[0].tolist() for k, c in enumerate(self.callers)}
        dp_edges = list(range(0, 62, 4))
        depth = {s: np.histogram(np.clip(self.dp[:, :, j][self.dose[:, :, j] >= 1], 0, 59), dp_edges)[0].tolist() for j, s in enumerate(self.samples)}
        coverage = {}
        for s in self.samples:
            f = next(iter(sorted((self.res / "reports" / "mosdepth" / s).glob("*.mosdepth.summary.txt"))), None) if (self.res / "reports" / "mosdepth" / s).exists() else None
            for line in (f.read_text().splitlines() if f else []):
                if line.startswith("total\t"):
                    coverage[s] = float(line.split("\t")[3])
        info = {"callers": self.callers, "samples": self.samples, "variants": int(len(self.pos))}
        if self.state.get("overview") != info:
            self.state["overview"] = info
            self._record("read the variant calls", **info, files=len(self.vcfs))
        return {**info, "caller_names": {c: CALLER_NAMES.get(c, c) for c in self.callers},
                "groups": {s: self.group_of.get(s, "") for s in self.samples}, "per": per, "agree": agree,
                "qual_hist": {"edges": ["0", "5", "10", "20", "30", "50", "100", "200", "500+"], "counts": qual},
                "dp_hist": {"edges": dp_edges, "counts": depth}, "coverage": coverage, "filters": self._filters()}

    def apply_filters(self, callers=None, agree: int = 1, min_qual: float = 30, min_dp: int = 10, min_gq: int = 20,
                      pass_only: bool = True, vtype: str = "all", region: str = ""):
        f = {"callers": [c for c in (callers or []) if c in self.callers], "agree": max(1, int(agree)), "min_qual": float(min_qual),
             "min_dp": int(min_dp), "min_gq": int(min_gq), "pass_only": bool(pass_only), "vtype": vtype if vtype in ("snv", "indel") else "all",
             "region": (region or "").strip()}
        if f["agree"] > len(f["callers"] or self.callers):
            raise ValueError(f"Only {len(f['callers'] or self.callers)} callers are chosen, so no variant can be called by {f['agree']}.")
        keep, _, cons, _ = self._apply(f)
        out = self._summary(keep, cons)
        self.state["filters"] = f
        self.state.pop("groups", None)          # Intent: a group comparison belongs to the filters it was made with.
        self._record("filtered variants", **f, kept=out["kept"], total=out["total"], snv=out["snv"], indel=out["indel"], titv=out["titv"])
        return {**out, "filters": f}

    def variants(self, offset: int = 0, n: int = 100, only: str = ""):
        f = self._filters()
        keep, valid, cons, sel = self._apply(f)
        idx = np.flatnonzero(keep)
        if only == "separating" and self.state.get("groups"):
            idx = np.array(self.state["groups"]["indices"], dtype=int)
        types = self._types()
        rows = []
        for i in idx[int(offset):int(offset) + int(n)]:
            rows.append({"i": int(i), "chrom": str(self.chrom[i]), "pos": int(self.pos[i]), "ref": str(self.ref[i]), "alt": str(self.alt[i]),
                         "type": str(types[i]), "qual": round(float(self.qual[i, sel, :].max()), 1),
                         "callers": [self.callers[c] for k, c in enumerate(sel) if valid[i, k].any()],
                         "gt": [int(x) for x in cons[i]]})
        return {"total": int(len(idx)), "offset": int(offset), "rows": rows, "samples": self.samples}

    def variant(self, i: int):
        i = int(i)
        if not 0 <= i < len(self.pos):
            raise ValueError("No such variant.")
        calls = []
        for c, caller in enumerate(self.callers):
            for s, sample in enumerate(self.samples):
                if self.dose[i, c, s] == -2:
                    continue
                calls.append({"caller": caller, "sample": sample, "dose": int(self.dose[i, c, s]), "dp": int(self.dp[i, c, s]),
                              "gq": int(self.gq[i, c, s]), "ref_reads": int(self.adr[i, c, s]), "alt_reads": int(self.ada[i, c, s]),
                              "qual": round(float(self.qual[i, c, s]), 1), "passed": bool(self.passed[i, c, s])})
        return {"i": i, "chrom": str(self.chrom[i]), "pos": int(self.pos[i]), "ref": str(self.ref[i]), "alt": str(self.alt[i]),
                "type": vtype(str(self.ref[i]), str(self.alt[i])), "calls": calls, "samples": self.samples, "callers": self.callers}

    def groups(self, a: str, b: str):
        sa = [j for j, s in enumerate(self.samples) if self.group_of.get(s) == a]
        sb = [j for j, s in enumerate(self.samples) if self.group_of.get(s) == b]
        if not sa or not sb or a == b:
            raise ValueError("Choose two different groups, each with at least one sample (groups come from the samples table).")
        keep, _, cons, _ = self._apply(self._filters())
        ca, cb = cons[:, sa], cons[:, sb]
        # Intent: a variant separates the groups when every sample of one carries it and no sample of the other does
        # (uncertain genotypes count as neither, so they never separate).
        sep = keep & (((ca >= 1).all(axis=1) & (cb == 0).all(axis=1)) | ((cb >= 1).all(axis=1) & (ca == 0).all(axis=1)))
        idx = np.flatnonzero(sep)
        in_a = int(((ca >= 1).all(axis=1) & sep).sum())
        # Where they fall: separating variants per window along each chromosome (a cluster points to a linked region).
        windows = []
        for c in self.contigs:
            on = self.chrom == c
            if not on.any():
                continue
            end = int(self.pos[on].max()) + 1
            size = max(1000, int(np.ceil(end / 40 / 1000) * 1000))
            edges = list(range(0, end + size, size))
            windows.append({"chrom": c, "size": size, "all": np.histogram(self.pos[on & keep], edges)[0].tolist(),
                            "separating": np.histogram(self.pos[on & sep], edges)[0].tolist()})
        self.state["groups"] = {"a": a, "b": b, "indices": [int(i) for i in idx]}
        self._record("compared groups", a=a, b=b, samples_a=[self.samples[j] for j in sa], samples_b=[self.samples[j] for j in sb],
                     separating=int(len(idx)), carried_by_a=in_a, carried_by_b=int(len(idx)) - in_a)
        return {"a": a, "b": b, "separating": int(len(idx)), "carried_by_a": in_a, "carried_by_b": int(len(idx)) - in_a,
                "kept": int(keep.sum()), "windows": windows}

    def export(self):
        f = self._filters()
        keep, valid, cons, sel = self._apply(f)
        out = self.res / "final"
        out.mkdir(exist_ok=True)
        gt = {-1: "./.", 0: "0/0", 1: "0/1", 2: "1/1"}
        callers = [self.callers[c] for c in sel]
        head = ["##fileformat=VCFv4.2", "##source=Everyome (filtered from nf-core/sarek calls)",
                f"##everyome_filters={json.dumps(f, sort_keys=True)}",
                *[f"##contig=<ID={c}>" for c in self.contigs],
                '##INFO=<ID=CALLERS,Number=.,Type=String,Description="Callers that called this variant and passed the filters">',
                '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype (from the first chosen caller that called it; ./. when no call passed the filters)">',
                "\t".join(["#CHROM", "POS", "ID", "REF", "ALT", "QUAL", "FILTER", "INFO", "FORMAT", *self.samples])]
        with open(out / "variants_filtered.vcf", "w") as fh:
            fh.write("\n".join(head) + "\n")
            for i in np.flatnonzero(keep):
                by = [callers[k] for k in range(len(sel)) if valid[i, k].any()]
                fh.write("\t".join([str(self.chrom[i]), str(self.pos[i]), ".", str(self.ref[i]), str(self.alt[i]),
                                    f"{float(self.qual[i, sel, :].max()):.1f}", "PASS", "CALLERS=" + ",".join(by), "GT",
                                    *[gt[int(x)] for x in cons[i]]]) + "\n")
        types = self._types()
        with open(out / "variants_filtered.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["chrom", "pos", "ref", "alt", "type", "qual", "callers", *self.samples])
            for i in np.flatnonzero(keep):
                w.writerow([self.chrom[i], self.pos[i], self.ref[i], self.alt[i], types[i], f"{float(self.qual[i, sel, :].max()):.1f}",
                            ";".join(callers[k] for k in range(len(sel)) if valid[i, k].any()), *[gt[int(x)] for x in cons[i]]])
        g = self.state.get("groups")
        if g:
            with open(out / f"separating_{g['a']}_vs_{g['b']}.csv", "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["chrom", "pos", "ref", "alt", "type", *self.samples])
                for i in g["indices"]:
                    w.writerow([self.chrom[i], self.pos[i], self.ref[i], self.alt[i], types[i], *[gt[int(x)] for x in cons[i]]])
        files = sorted(p.name for p in out.iterdir())
        self._record("exported variants", files=files, variants=int(keep.sum()))
        return {"files": files, "variants": int(keep.sum())}

    def files(self):
        out = self.res / "final"
        return [{"name": f"final/{f.name}", "size": f.stat().st_size} for f in sorted(out.glob("*"))] if out.exists() else []
