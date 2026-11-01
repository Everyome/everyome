"""Primer design on this computer: read a sequence, choose a target, run Primer3, check primers, export.

Runs inside the Everyome app (a local module), on the run folder. Every choice
is recorded in order, so the run can be written up and repeated exactly.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

import primer3
from Bio import SeqIO
from Bio.Restriction import Analysis, RestrictionBatch
from Bio.Seq import Seq

from everyome.core.engine import BaseEngine

FASTA_EXT = {".fa", ".fasta", ".fna", ".fas", ".txt"}
COMPLEMENT = str.maketrans("ACGTN", "TGCAN")


def revcomp(s: str) -> str:
    return s.upper().translate(COMPLEMENT)[::-1]


def _label(f) -> str:
    for k in ("label", "gene", "product", "note", "standard_name"):
        if f.qualifiers.get(k):
            return str(f.qualifiers[k][0])
    return f.type


class Engine(BaseEngine):
    API = ("sequence_info", "set_target", "design", "check_primers", "export", "files")
    REPLAY = ("set_target", "design", "check_primers", "export")

    def __init__(self, run_dir: str):
        super().__init__(run_dir)
        p = self.params
        rec = None
        if p.get("sequence_file"):
            path = Path(p["sequence_file"])
            fmt = "fasta" if path.suffix.lower() in FASTA_EXT else "genbank"
            try:
                rec = SeqIO.read(path, fmt)
            except ValueError:
                rec = SeqIO.read(path, "fasta" if fmt == "genbank" else "genbank")
        elif p.get("sequence_text"):
            text = p["sequence_text"]
            name = "pasted sequence"
            if text.lstrip().startswith(">"):
                name = text.lstrip()[1:].splitlines()[0].split()[0] or name
                text = "\n".join(text.lstrip().splitlines()[1:])
            bases = re.sub(r"[^ACGTNacgtn]", "", text)
            if not bases:
                raise ValueError("The pasted text has no DNA bases (A, C, G, T or N).")
            rec = type("Rec", (), {"seq": Seq(bases), "id": name, "features": [], "annotations": {}})()
        if rec is None:
            raise ValueError("Give a sequence file or paste a sequence.")
        self.seq = str(rec.seq).upper()
        self.name = rec.id
        topo = p.get("topology") or "auto"
        self.circular = (rec.annotations.get("topology") == "circular") if topo == "auto" else topo == "circular"
        self.features = [{"start": int(f.location.start) + 1, "end": int(f.location.end), "strand": f.location.strand or 1,
                          "label": _label(f), "type": f.type} for f in rec.features if f.type not in ("source", "primer_bind")]
        self.state.setdefault("target", None)

    def status(self):
        return {**super().status(), "name": self.name, "length": len(self.seq), "circular": self.circular,
                "target": self.state.get("target"), "designed": len(self.state.get("pairs", []))}

    # ---------------------------------------------------------------- sequence
    def _sites(self):
        names = [n for n in re.split(r"[\s,]+", self.params.get("enzymes") or "") if n]
        try:
            batch = RestrictionBatch(names)
        except ValueError as e:
            raise ValueError(f"Unknown enzyme name in the map settings ({e}).")
        hits = Analysis(batch, Seq(self.seq), linear=not self.circular).full()
        return sorted(({"name": str(e), "pos": ps[0]} for e, ps in hits.items() if len(ps) == 1), key=lambda x: x["pos"])

    def sequence_info(self):
        gc = (self.seq.count("G") + self.seq.count("C")) / max(1, len(self.seq) - self.seq.count("N"))
        return {"name": self.name, "length": len(self.seq), "circular": self.circular, "gc": round(gc * 100, 1),
                "features": self.features, "sites": self._sites(), "target": self.state.get("target"),
                "pairs": self.state.get("pairs", []), "chosen": self.state.get("chosen")}

    def set_target(self, start: int, length: int, label: str = ""):
        start, length = int(start), int(length)
        if start < 1 or length < 1 or start + length - 1 > len(self.seq):
            raise ValueError(f"The region must lie within the sequence (1–{len(self.seq)}).")
        self.state["target"] = {"start": start, "length": length, "end": start + length - 1, "label": label}
        self._record("chose the region to amplify", start=start, end=start + length - 1, length=length, label=label)
        return self.state["target"]

    # ---------------------------------------------------------------- design
    def _globals(self) -> dict:
        p = self.params
        g = {"PRIMER_PRODUCT_SIZE_RANGE": [[int(p["product_min"]), int(p["product_max"])]], "PRIMER_NUM_RETURN": int(p["num_return"]),
             "PRIMER_MIN_SIZE": int(p["size_min"]), "PRIMER_OPT_SIZE": int(p["size_opt"]), "PRIMER_MAX_SIZE": int(p["size_max"]),
             "PRIMER_MIN_TM": float(p["tm_min"]), "PRIMER_OPT_TM": float(p["tm_opt"]), "PRIMER_MAX_TM": float(p["tm_max"]),
             "PRIMER_MIN_GC": float(p["gc_min"]), "PRIMER_MAX_GC": float(p["gc_max"]), "PRIMER_GC_CLAMP": int(p["gc_clamp"]),
             "PRIMER_MAX_POLY_X": int(p["max_poly_x"]), "PRIMER_SALT_MONOVALENT": float(p["mv_conc"]),
             "PRIMER_SALT_DIVALENT": float(p["dv_conc"]), "PRIMER_DNTP_CONC": float(p["dntp_conc"]), "PRIMER_DNA_CONC": float(p["dna_conc"])}
        for line in (p.get("extra_primer3") or "").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            k, sep, v = line.partition("=")
            k, v = k.strip(), v.strip()
            if not sep or not k.startswith("PRIMER_"):
                raise ValueError(f"'{line}' is not a Primer3 setting (expected PRIMER_NAME=value).")
            try:
                g[k] = int(v) if re.fullmatch(r"-?\d+", v) else float(v)
            except ValueError:
                g[k] = v
        return g

    def design(self):
        t = self.state.get("target")
        p = self.params
        if t and t["length"] + 2 * int(p["size_min"]) > int(p["product_max"]):
            need = t["length"] + 2 * int(p["size_min"])
            raise ValueError(f"The region is {t['length']} bases, so with primers either side the product must be at least {need} bases, "
                             f"but the longest product allowed is {p['product_max']}. Choose a shorter region, or start a new run "
                             f"with a larger 'Longest product'.")
        seq_args = {"SEQUENCE_ID": self.name, "SEQUENCE_TEMPLATE": self.seq}
        if t:
            seq_args["SEQUENCE_TARGET"] = [t["start"] - 1, t["length"]]
        g = self._globals()
        try:
            r = primer3.bindings.design_primers(seq_args, g)
        except (OSError, ValueError, KeyError) as e:
            raise ValueError(f"Primer3 could not run with these settings: {e}")
        pairs = []
        for i in range(r.get("PRIMER_PAIR_NUM_RETURNED", 0)):
            l0, ll = r[f"PRIMER_LEFT_{i}"]
            r0, rl = r[f"PRIMER_RIGHT_{i}"]
            pairs.append({"n": i + 1, "left": r[f"PRIMER_LEFT_{i}_SEQUENCE"], "right": r[f"PRIMER_RIGHT_{i}_SEQUENCE"],
                          "left_start": l0 + 1, "left_end": l0 + ll, "right_start": r0 - rl + 2, "right_end": r0 + 1,
                          "left_tm": round(r[f"PRIMER_LEFT_{i}_TM"], 1), "right_tm": round(r[f"PRIMER_RIGHT_{i}_TM"], 1),
                          "left_gc": round(r[f"PRIMER_LEFT_{i}_GC_PERCENT"], 1), "right_gc": round(r[f"PRIMER_RIGHT_{i}_GC_PERCENT"], 1),
                          "product": r[f"PRIMER_PAIR_{i}_PRODUCT_SIZE"], "penalty": round(r[f"PRIMER_PAIR_{i}_PENALTY"], 2),
                          "dimer": round(r[f"PRIMER_PAIR_{i}_COMPL_ANY_TH"], 1), "end_dimer": round(r[f"PRIMER_PAIR_{i}_COMPL_END_TH"], 1),
                          "left_hairpin": round(r.get(f"PRIMER_LEFT_{i}_HAIRPIN_TH", 0), 1), "right_hairpin": round(r.get(f"PRIMER_RIGHT_{i}_HAIRPIN_TH", 0), 1)})
        why = {k.replace("PRIMER_", "").replace("_EXPLAIN", "").lower(): r[k] for k in ("PRIMER_LEFT_EXPLAIN", "PRIMER_RIGHT_EXPLAIN", "PRIMER_PAIR_EXPLAIN") if k in r}
        self.state.update(step="designed", pairs=pairs, explain=why, chosen=1 if pairs else None,
                          primer3=getattr(primer3, "__version__", None) or _version("primer3-py"))
        self._record("designed primers", pairs=len(pairs), target=t, settings={k: v for k, v in g.items() if k != "PRIMER_NUM_RETURN"})
        return {"pairs": pairs, "explain": why}

    # ---------------------------------------------------------------- check
    def check_primers(self, left: str, right: str = "", name: str = "my primers"):
        left, right = re.sub(r"\s", "", left).upper(), re.sub(r"\s", "", right).upper()
        if not re.fullmatch(r"[ACGTN]{6,}", left) or (right and not re.fullmatch(r"[ACGTN]{6,}", right)):
            raise ValueError("Primers should be at least 6 bases of A, C, G, T (or N).")
        p = self.params
        cond = {"mv_conc": float(p["mv_conc"]), "dv_conc": float(p["dv_conc"]), "dntp_conc": float(p["dntp_conc"]), "dna_conc": float(p["dna_conc"])}

        def one(s):
            hp, hd = primer3.calc_hairpin(s, **cond), primer3.calc_homodimer(s, **cond)
            fwd, rev = self.seq.find(s), self.seq.find(revcomp(s))
            return {"seq": s, "length": len(s), "tm": round(primer3.calc_tm(s, **cond), 1),
                    "gc": round(100 * (s.count("G") + s.count("C")) / len(s), 1),
                    "hairpin_dg": round(hp.dg / 1000, 2) if hp.structure_found else 0.0,
                    "self_dimer_dg": round(hd.dg / 1000, 2) if hd.structure_found else 0.0,
                    "binds_at": fwd + 1 if fwd >= 0 else None, "binds_reverse_at": rev + 1 if rev >= 0 else None}
        out = {"left": one(left)}
        if right:
            out["right"] = one(right)
            het = primer3.calc_heterodimer(left, right, **cond)
            out["pair_dimer_dg"] = round(het.dg / 1000, 2) if het.structure_found else 0.0
            lf, rr = out["left"]["binds_at"], out["right"]["binds_reverse_at"]
            out["product"] = (rr + len(right) - lf) if lf and rr and rr >= lf else None
        self.state.setdefault("checked", []).append({"name": name, **out})
        self._record("checked primers", name=name, left=left, right=right or None, left_tm=out["left"]["tm"],
                     right_tm=out.get("right", {}).get("tm"), product=out.get("product"))
        return out

    # ---------------------------------------------------------------- export
    def export(self, chosen: list[int] | None = None, prefix: str = ""):
        pairs = self.state.get("pairs", [])
        if not pairs:
            raise ValueError("Design primers first.")
        chosen = [int(c) for c in (chosen or [pairs[0]["n"]])]
        prefix = re.sub(r"[^A-Za-z0-9_.-]+", "_", prefix or self.name)[:30]
        d = self.dir / "results"
        with open(d / "primer_pairs.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(pairs[0]))
            w.writeheader(); w.writerows(pairs)
        rows = []
        for p in pairs:
            if p["n"] in chosen:
                rows += [{"name": f"{prefix}_{p['n']}_F", "sequence": p["left"], "length": len(p["left"]), "tm": p["left_tm"]},
                         {"name": f"{prefix}_{p['n']}_R", "sequence": p["right"], "length": len(p["right"]), "tm": p["right_tm"]}]
        with open(d / "order_sheet.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["name", "sequence", "length", "tm"])
            w.writeheader(); w.writerows(rows)
        self._genbank(d / f"{prefix}_with_primers.gb", [p for p in pairs if p["n"] in chosen], prefix)
        files = sorted(x.name for x in d.iterdir())
        self.state.update(step="exported", exported=files, chosen=chosen[0])
        self._record("exported primers", chosen=chosen, order=[r["name"] for r in rows], files=files)
        return {"files": files, "order": rows}

    def _genbank(self, path: Path, pairs: list[dict], prefix: str):
        from Bio.SeqFeature import FeatureLocation, SeqFeature
        from Bio.SeqRecord import SeqRecord
        rec = SeqRecord(Seq(self.seq), id=self.name[:16], name=self.name[:16], description=f"{self.name} with primers designed by Everyome")
        rec.annotations.update(molecule_type="DNA", topology="circular" if self.circular else "linear")
        for f in self.features:
            rec.features.append(SeqFeature(FeatureLocation(f["start"] - 1, f["end"], strand=f["strand"]), type=f["type"], qualifiers={"label": [f["label"]]}))
        for p in pairs:
            rec.features.append(SeqFeature(FeatureLocation(p["left_start"] - 1, p["left_end"], strand=1), type="primer_bind", qualifiers={"label": [f"{prefix}_{p['n']}_F"]}))
            rec.features.append(SeqFeature(FeatureLocation(p["right_start"] - 1, p["right_end"], strand=-1), type="primer_bind", qualifiers={"label": [f"{prefix}_{p['n']}_R"]}))
        SeqIO.write(rec, path, "genbank")

    def files(self):
        d = self.dir / "results"
        return [{"name": p.name, "size": p.stat().st_size} for p in sorted(d.iterdir()) if p.is_file()]


def _version(dist: str):
    from importlib.metadata import PackageNotFoundError, version
    try:
        return version(dist)
    except PackageNotFoundError:
        return None
