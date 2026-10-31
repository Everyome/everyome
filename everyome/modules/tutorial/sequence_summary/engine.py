"""Interactive engine for the Sequence summary module: explore and filter by GC content."""
from __future__ import annotations

import csv

from everyome.core.engine import BaseEngine


class Engine(BaseEngine):
    API = ("summary", "histogram", "set_gc_range", "export")

    def __init__(self, run_dir: str):
        super().__init__(run_dir)
        self.rows = [{"id": r["id"], "length": int(r["length"]), "gc": float(r["gc"])}
                     for r in csv.DictReader(open(self.dir / "results" / "gc.tsv"), delimiter="\t")]

    def _kept(self):
        lo, hi = self.state.get("gc_range", [0.0, 1.0])
        return [r for r in self.rows if lo <= r["gc"] <= hi]

    def status(self):
        return {**super().status(), "gc_range": self.state.get("gc_range", [0.0, 1.0]), "sequences": len(self.rows)}

    def summary(self):
        n, k = len(self.rows), self._kept()
        mean = lambda xs: round(sum(xs) / len(xs), 3) if xs else 0
        return {"sequences": n, "kept": len(k), "mean_length": mean([r["length"] for r in self.rows]),
                "mean_gc": mean([r["gc"] for r in self.rows]), "gc_range": self.state.get("gc_range", [0.0, 1.0])}

    def histogram(self, field: str = "gc", bins: int = 20):
        if field not in ("gc", "length"):
            raise ValueError("Choose gc or length.")
        vals = [r[field] for r in self.rows]
        lo, hi = (0.0, 1.0) if field == "gc" else (0, max(vals or [1]))
        width = (hi - lo) / bins or 1
        counts = [0] * bins
        for v in vals:
            counts[min(bins - 1, int((v - lo) / width))] += 1
        return {"field": field, "edges": [lo + i * width for i in range(bins + 1)], "counts": counts}

    def set_gc_range(self, lo: float, hi: float):
        lo, hi = float(lo), float(hi)
        if not 0 <= lo <= hi <= 1:
            raise ValueError("The GC range must run from a lower to a higher value between 0 and 1.")
        self.state["gc_range"] = [lo, hi]
        self.state["step"] = "filtered"
        self._record("set GC range", low=lo, high=hi, kept=len(self._kept()))
        return self.summary()

    def export(self):
        return self._background(self._export)

    def _export(self):
        rows = self._kept()
        self._prog(30, "Writing the filtered table")
        with open(self.dir / "results" / "gc_filtered.tsv", "w", newline="") as fh:
            w = csv.writer(fh, delimiter="\t")
            w.writerow(["id", "length", "gc"])
            w.writerows([r["id"], r["length"], r["gc"]] for r in rows)
        self.state["step"] = "exported"
        self._record("exported", file="gc_filtered.tsv", rows=len(rows))
        self._prog(100, "Saved results/gc_filtered.tsv")
