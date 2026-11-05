"""Live session for interaction prediction: the structure prediction steps (every prediction, the 3D view coloured by
confidence, PAE, methods side by side, export) plus interfaces: for every pair of chains in every complex, how many
residues touch, how confident the predictor is there, ipTM and pDockQ, and a plain-language verdict.

Works on what nf-core/proteinfold wrote under <run>/results for multimer predictions.
"""
from __future__ import annotations

import csv
import json

import numpy as np

from ..structure import structure as st
from ..structure.engine import Engine as StructureEngine
from . import interface as itf


class Engine(StructureEngine):
    API = StructureEngine.API + ("interfaces", "interface")
    REPLAY = StructureEngine.REPLAY + ("interfaces",)

    def _chainwise(self, p: dict) -> dict:
        """The pipeline's chain-wise ipTM ('A:B' → value), when it wrote one."""
        d = (self.res / p["pdb"]).parent.parent / p["id"]
        f = next(iter(sorted(d.glob(f"{p['id']}_chainwise_iptm.tsv"))), None) if d.is_dir() else None
        if not f:
            return {}
        out = {}
        for row in csv.reader(open(f), delimiter="\t"):
            if len(row) >= 2 and ":" in row[0]:
                try:
                    out[row[0]] = float(row[1])
                except ValueError:
                    pass
        return out

    def _measure(self, p: dict) -> dict:
        s = st.read_pdb(self.res / p["pdb"])
        xyz = np.array([r["xyz"] for r in s["residues"]])
        chains = [r["chain"] for r in s["residues"]]
        plddt = np.array([r["plddt"] for r in s["residues"]])
        iptm = st.scores(self.res / p["iptm"]).get(0) if p.get("iptm") else None
        cw = self._chainwise(p)
        pairs = itf.describe(xyz, chains, plddt, self._pae(p))
        for q in pairs:
            q["iptm"] = cw.get(f"{q['a']}:{q['b']}", cw.get(f"{q['b']}:{q['a']}", iptm if len(s["chains"]) == 2 else None))
            q["verdict"] = itf.verdict(q["pdockq"], q["iptm"])
        return {"key": p["key"], "id": p["id"], "method": p["method"], "chains": s["chains"], "iptm": iptm,
                "lengths": {c: chains.count(c) for c in s["chains"]}, "pairs": pairs}

    def interfaces(self):
        """Every complex's chain pairs, scored; single-chain predictions are listed apart."""
        out, single = [], []
        for p in self._find():
            m = self._measure(p)
            (out if len(m["chains"]) > 1 else single).append(m)
        (self.out / "interfaces.json").write_text(json.dumps(out, indent=1))
        self.state["interfaces"] = {"complexes": len(out), "pairs": sum(len(m["pairs"]) for m in out)}
        self._record("scored interfaces", complexes=[{"id": m["id"], "method": m["method"], "iptm": m["iptm"],
                                                       "pairs": [{k: q[k] for k in ("a", "b", "contacts", "interface_plddt", "pdockq", "iptm", "verdict")}
                                                                 for q in m["pairs"]]} for m in out])
        strip = lambda q: {k: v for k, v in q.items() if not k.startswith("index_")}
        return {"complexes": [{**m, "pairs": [strip(q) for q in m["pairs"]]} for m in out], "single": [m["key"] for m in single]}

    def interface(self, key: str, a: str, b: str):
        """One pair of chains: the residues at the interface on each side, and the PAE block between the two chains."""
        p = self._get(key)
        m = self._measure(p)
        q = next((x for x in m["pairs"] if {x["a"], x["b"]} == {a, b}), None)
        if q is None:
            raise ValueError(f"{key} has no chains {a} and {b}.")
        s = st.read_pdb(self.res / p["pdb"])
        res = s["residues"]
        side = lambda idx: [{"chain": res[i]["chain"], "num": res[i]["num"], "aa": res[i]["aa"], "plddt": round(res[i]["plddt"], 1)} for i in idx]
        pae = self._pae(p)
        block = None
        if pae is not None:
            ia = [i for i, r in enumerate(res) if r["chain"] == q["a"]]
            ib = [i for i, r in enumerate(res) if r["chain"] == q["b"]]
            sub = pae[np.ix_(ia, ib)]
            step = max(1, -(-max(sub.shape) // 150))
            sub = sub[: sub.shape[0] // step * step, : sub.shape[1] // step * step]
            small = sub.reshape(sub.shape[0] // step, step, sub.shape[1] // step, step).mean((1, 3)) if step > 1 else sub
            block = {"rows": q["a"], "cols": q["b"], "step": step, "cells": np.round(small, 1).tolist()}
        return {**{k: v for k, v in q.items() if not k.startswith("index_")}, "key": key,
                "side_a": side(q["index_a"]), "side_b": side(q["index_b"]), "pae_block": block,
                "interface": [i for i in q["index_a"] + q["index_b"]]}
