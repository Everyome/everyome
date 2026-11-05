"""App-side helpers for cell types in spots (run on this computer, reading the cluster through the backend).

  scan     each section's Space Ranger output folder, as for Visium
  report   after the run: cell types learnt, spots mapped, and the two training curves (for the Run page)
"""
from __future__ import annotations

import shlex

from everyome.modules.spatial.visium import helpers as visium


def scan(backend, path: str = "") -> dict:
    found = visium.scan(backend, path)
    return {"rows": [{"sample": r["sample"], "outs": r["outs"]} for r in found["rows"]],
            "message": f"Found {len(found['rows'])} sections. Delete any you don't want mapped."}


def _curve(backend, path: str) -> list[list[float]]:
    rc, txt, _ = backend.run(f"cat {shlex.quote(path)} 2>/dev/null", timeout=60)
    out = []
    for line in txt.splitlines()[1:]:
        a, b = (line.split(",") + [""])[:2]
        try:
            out.append([float(a), float(b)])
        except ValueError:
            continue
    return out


def report(backend, run: dict) -> dict:
    d = f"{run['dir']}/results"
    out = {"types": [], "spots": 0, "reference_curve": _curve(backend, f"{d}/reference/training.csv"),
           "mapping_curve": _curve(backend, f"{d}/cell2location/training.csv")}
    rc, txt, _ = backend.run(f"head -1 {shlex.quote(d + '/cell2location/abundance_mean.csv')} 2>/dev/null && "
                             f"wc -l < {shlex.quote(d + '/cell2location/abundance_mean.csv')}", timeout=60)
    lines = txt.splitlines()
    if len(lines) >= 2:
        out["types"] = lines[0].split(",")[2:]
        out["spots"] = int(lines[1].strip()) - 1
    return out
