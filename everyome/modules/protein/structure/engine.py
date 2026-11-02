"""Live session for structure prediction: what each method predicted, how confident it is, and which parts to keep.

Works on what nf-core/proteinfold wrote under <run>/results: every <method>/.../top_ranked_structures/<id>.pdb,
with the pLDDT, PAE and pTM tables beside it in <method>/.../<id>/. Methods that write no PAE (ESMFold) still
show the structure and pLDDT. Nothing is changed in results; exports go to results/final/.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from everyome.core.engine import BaseEngine

from . import structure as st

PAE_MAX_CELLS = 300          # Intent: send at most 300 x 300 PAE cells to the browser (averaged), whatever the protein's length


class Engine(BaseEngine):
    API = ("load", "predictions", "structure", "confidence", "compare", "export", "files")
    REPLAY = ("load", "export")

    def __init__(self, run_dir: str):
        super().__init__(run_dir)
        self.res = self.dir / "results"

    def status(self):
        return {**super().status(), "loaded": self.state.get("loaded"), "exported": self.state.get("exported")}

    # ---------------------------------------------------------------- finding what the pipeline made
    def _find(self) -> list[dict]:
        out = []
        for pdb in sorted(self.res.glob("**/top_ranked_structures/*.pdb")):
            rel = pdb.relative_to(self.res)
            if rel.parts[0] == "final":
                continue
            pid, method = pdb.stem, rel.parts[0]
            sub = "/".join(rel.parts[1:-2])           # e.g. alphafold2's split_msa_prediction
            d = pdb.parent.parent / pid
            find = lambda pat: next(iter(sorted(d.glob(pat))), None) if d.is_dir() else None
            pae = find(f"**/{pid}_0_pae.tsv") or find(f"**/{pid}_*_pae.tsv")
            out.append({"key": f"{method}/{pid}", "id": pid, "method": method, "variant": sub, "pdb": str(rel),
                        "plddt": str(find(f"{pid}_plddt.tsv").relative_to(self.res)) if find(f"{pid}_plddt.tsv") else None,
                        "pae": str(pae.relative_to(self.res)) if pae else None,
                        "ptm": str(find(f"{pid}_ptm.tsv").relative_to(self.res)) if find(f"{pid}_ptm.tsv") else None,
                        "iptm": str(find(f"{pid}_iptm.tsv").relative_to(self.res)) if find(f"{pid}_iptm.tsv") else None})
        return out

    def _get(self, key: str) -> dict:
        p = next((x for x in self._find() if x["key"] == key), None)
        if not p:
            raise ValueError(f"No prediction called {key} in this run's results.")
        return p

    def _pae(self, p: dict) -> np.ndarray | None:
        return np.array(st.read_table(self.res / p["pae"])) if p.get("pae") else None

    def _describe(self, p: dict) -> dict:
        s = st.read_pdb(self.res / p["pdb"])
        plddt = [r["plddt"] for r in s["residues"]]
        top = lambda f: st.scores(self.res / p[f]).get(0) if p.get(f) else None
        doms = st.domains(self._pae(p), plddt) if p.get("pae") else []
        return {**{k: p[k] for k in ("key", "id", "method", "variant", "pdb")}, "length": len(plddt), "chains": s["chains"],
                **st.summary(plddt), "ptm": top("ptm"), "iptm": top("iptm"), "has_pae": bool(p.get("pae")),
                "ranks": len(st.plddt_ranks(self.res / p["plddt"])) if p.get("plddt") else 1, "domains": doms}

    def load(self):
        """Read every prediction once and note it for the record."""
        preds = [self._describe(p) for p in self._find()]
        if not preds:
            raise ValueError("No predicted structures were found in this run's results. Check the pipeline log on the Run page.")
        self.state["loaded"] = {"predictions": len(preds), "proteins": len({p["id"] for p in preds}), "methods": sorted({p["method"] for p in preds})}
        self.state["step"] = "loaded"
        (self.out / "predictions.json").write_text(json.dumps(preds, indent=1))
        self._record("read the predicted structures", predictions=[{k: p[k] for k in ("id", "method", "length", "mean_plddt", "ptm", "iptm")}
                                                                     | {"confident": round(p["bands"]["very high"] + p["bands"]["confident"], 1),
                                                                        "domains": len(p["domains"])} for p in preds])
        return self.state["loaded"]

    def predictions(self):
        path = self.out / "predictions.json"
        if not path.exists():
            raise ValueError("Read the results first (the first step).")
        return json.loads(path.read_text())

    # ---------------------------------------------------------------- one structure
    def structure(self, key: str):
        """CA positions (centred), residues and pLDDT, for the 3D view."""
        p = self._get(key)
        s = st.read_pdb(self.res / p["pdb"])
        xyz = np.array([r["xyz"] for r in s["residues"]])
        xyz -= xyz.mean(0)
        doms = next((d["domains"] for d in self.predictions() if d["key"] == key), [])
        of = {}
        for d in doms:
            for a, b in d["ranges"]:
                for k in range(a, b + 1):
                    of[k] = d["name"]
        return {"key": key, "chains": s["chains"], "domains": doms,
                "residues": [{"chain": r["chain"], "num": r["num"], "aa": r["aa"], "plddt": round(r["plddt"], 1), "domain": of.get(i + 1, ""),
                              "xyz": [round(float(v), 2) for v in xyz[i]]} for i, r in enumerate(s["residues"])]}

    def confidence(self, key: str):
        """pLDDT along the sequence (every ranked model) and the PAE matrix (averaged down for long proteins)."""
        p = self._get(key)
        ranks = st.plddt_ranks(self.res / p["plddt"]) if p.get("plddt") else {"rank_0": [r["plddt"] for r in st.read_pdb(self.res / p["pdb"])["residues"]]}
        pae, out = self._pae(p), None
        if pae is not None:
            n = len(pae)
            step = max(1, -(-n // PAE_MAX_CELLS))
            m = n // step * step
            small = pae[:m, :m].reshape(m // step, step, m // step, step).mean((1, 3)) if step > 1 else pae
            out = {"n": n, "step": step, "max": round(float(pae.max()), 1), "cells": np.round(small, 1).tolist()}
        return {"key": key, "plddt": ranks, "pae": out}

    # ---------------------------------------------------------------- methods side by side
    def compare(self, id: str):
        """For one protein predicted by several methods: confidence and how far apart their structures are."""
        ps = [p for p in self._find() if p["id"] == id]
        if not ps:
            raise ValueError(f"No predictions for {id}.")
        S = {p["key"]: st.read_pdb(self.res / p["pdb"])["residues"] for p in ps}
        out = []
        keys = list(S)
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                ra, rb = S[a], S[b]
                if len(ra) != len(rb):
                    out.append({"a": a, "b": b, "rmsd": None, "note": "different lengths"})
                    continue
                A, B = np.array([r["xyz"] for r in ra]), np.array([r["xyz"] for r in rb])
                both = np.array([min(x["plddt"], y["plddt"]) >= 70 for x, y in zip(ra, rb)])
                # Intent: each domain superposed on its own shows whether the methods agree on the domains but not their arrangement.
                doms = next((d["domains"] for d in self.predictions() if d["key"] in (a, b) and d["domains"]), [])
                per = []
                for dm in doms:
                    ii = np.concatenate([np.arange(x - 1, y) for x, y in dm["ranges"]])
                    per.append({"name": dm["name"], "rmsd": round(st.kabsch_rmsd(A[ii], B[ii]), 2)})
                out.append({"a": a, "b": b, "rmsd": round(st.kabsch_rmsd(A, B), 2),
                            "rmsd_confident": round(st.kabsch_rmsd(A[both], B[both]), 2) if both.sum() >= 3 else None,
                            "confident_residues": int(both.sum()), "domains": per})
        return {"id": id, "pairs": out, "methods": [p["method"] for p in ps]}

    # ---------------------------------------------------------------- export
    def export(self, keys: list | None = None, min_plddt: float = 0, domains_only: bool = False):
        """Copy the chosen models to results/final/: whole, or only confident residues (or domains), with a summary table."""
        preds = {p["key"]: p for p in self.predictions()}
        keys = keys or list(preds)
        if not keys or any(k not in preds for k in keys):
            raise ValueError("Choose predictions from this run to export.")
        min_plddt = float(min_plddt or 0)
        d = self.res / "final"
        d.mkdir(exist_ok=True)
        files, kept = [], {}
        for k in keys:
            p = preds[k]
            res = st.read_pdb(self.res / p["pdb"])["residues"]
            in_dom = {i + 1 for dm in p["domains"] for a, b in dm["ranges"] for i in range(a - 1, b)}
            keep = {(r["chain"], r["num"]) for i, r in enumerate(res)
                    if r["plddt"] >= min_plddt and (not domains_only or i + 1 in in_dom)}
            trimmed = min_plddt > 0 or domains_only
            name = f"{p['id']}_{p['method']}{'_trimmed' if trimmed else ''}.pdb"
            note = (f"Predicted by {p['method']} via nf-core/proteinfold; exported by Everyome."
                    + (f" Residues with pLDDT below {min_plddt:g} removed." if min_plddt > 0 else "")
                    + (" Only confident domains kept." if domains_only else "") + " B-factors hold pLDDT.")
            n = st.write_pdb(d / name, self.res / p["pdb"], keep if trimmed else None, note)
            if n == 0:
                raise ValueError(f"No residues of {p['id']} ({p['method']}) pass those limits; lower them.")
            files.append(name)
            kept[k] = n
        with open(d / "predictions_summary.tsv", "w") as fh:
            fh.write("protein\tmethod\tresidues\tmean_pLDDT\tvery_high_%\tconfident_%\tlow_%\tvery_low_%\tpTM\tipTM\tdomains\texported_residues\n")
            for k in keys:
                p, b = preds[k], preds[k]["bands"]
                doms = "; ".join(f"{dm['name']} " + ",".join(f"{a}-{z}" for a, z in dm["ranges"]) for dm in p["domains"])
                fh.write(f"{p['id']}\t{p['method']}\t{p['length']}\t{p['mean_plddt']}\t{b['very high']}\t{b['confident']}\t{b['low']}\t{b['very low']}\t"
                         f"{'' if p['ptm'] is None else p['ptm']}\t{'' if p['iptm'] is None else p['iptm']}\t{doms}\t{kept[k]}\n")
        files.append("predictions_summary.tsv")
        self.state["exported"] = files
        self.state["step"] = "exported"
        self._record("exported structures", files=files, min_plddt=min_plddt, domains_only=bool(domains_only),
                     models=[{"id": preds[k]["id"], "method": preds[k]["method"], "residues": kept[k], "of": preds[k]["length"]} for k in keys])
        return {"files": files}

    def files(self):
        d = self.res / "final"
        return [{"name": f"final/{p.name}", "size": p.stat().st_size} for p in sorted(d.iterdir())] if d.is_dir() else []
