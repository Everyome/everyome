"""App-side helper for imaging spatial data: find each section's instrument output folder and which instrument made it.

  scan   folders inside the chosen one that hold Xenium, MERSCOPE or CosMx output
"""
from __future__ import annotations

import re
import shlex

MARKERS = {"cell_feature_matrix.h5": "xenium", "cell_feature_matrix": "xenium", "experiment.xenium": "xenium",
           "cell_by_gene.csv": "merscope"}


def scan(backend, path: str = "") -> dict:
    if not path:
        raise ValueError("Choose the folder first.")
    q = shlex.quote(path.rstrip("/"))
    names = " -o ".join(f"-name {shlex.quote(n)}" for n in [*MARKERS, "*exprMat_file.csv*"])
    rc, out, _ = backend.run(f"find {q} -maxdepth 4 \\( {names} \\) 2>/dev/null | sort | head -200", timeout=120)
    found = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        folder, name = line.rsplit("/", 1)
        found.setdefault(folder, MARKERS.get(name, "cosmx" if "exprMat_file" in name else ""))
    if not found:
        raise ValueError("No Xenium, MERSCOPE or CosMx output found. Choose a folder containing each section's output folder.")
    rows = []
    for folder, platform in sorted(found.items()):
        parts = folder.rstrip("/").split("/")
        name = parts[-2] if parts[-1] == "outs" and len(parts) > 1 else parts[-1]
        name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
        rows.append({"sample": name, "outs": folder, "platform": platform, "condition": "", "batch": ""})
    kinds = sorted({r["platform"] for r in rows})
    return {"rows": rows, "message": f"Found {len(rows)} sections ({', '.join(kinds)}). Fill in each section's condition, "
                                     "and a batch if sections were run on different days or slides."}
