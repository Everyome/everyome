"""App-side helper for alignment and tree building: what the stages made, for the Run page."""
from __future__ import annotations

import re

from .engine import parse_iqtree


def report(backend, run: dict) -> dict:
    d = f"{run['dir']}/results"

    def text(name):
        try:
            return backend.read_text(f"{d}/{name}")
        except FileNotFoundError:
            return ""
    aln = text("alignment.fasta")
    width = len("".join(aln.split(">", 2)[1].splitlines()[1:])) if aln.count(">") else 0
    cols = text("trim_columns.txt")
    kept = len(re.findall(r"\d+", cols.split("\t", 1)[-1])) if cols else None
    rep = parse_iqtree(text("tree.iqtree"))
    return {"sequences": aln.count(">"), "columns": width, "kept": kept, "model": rep.get("best_model") or rep.get("model"),
            "selected_by": rep.get("criterion") if rep.get("best_model") else None, "log_likelihood": rep.get("log_likelihood"),
            "tree": bool(text("tree.treefile")), "report": "results/tree.iqtree" if rep.get("model") else None}
