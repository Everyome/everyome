"""App-side helper for multiome: find each sample's Cell Ranger ARC output folder.

  scan   folders inside the chosen one that hold ARC output ('outs' with a joint filtered matrix, folder or .h5)
"""
from __future__ import annotations

import re
import shlex


def scan(backend, path: str = "") -> dict:
    if not path:
        raise ValueError("Choose the folder first.")
    q = shlex.quote(path.rstrip("/"))
    # Intent: ARC's 'outs' holds filtered_feature_bc_matrix (a folder or .h5) next to atac_fragments.tsv.gz; look a few levels down.
    rc, out, _ = backend.run(f"find {q} -maxdepth 4 \\( -name 'filtered_feature_bc_matrix.h5' -o -name 'filtered_feature_bc_matrix' \\) "
                             "2>/dev/null | sort | head -100", timeout=120)
    outs = sorted({l.rsplit("/filtered_feature_bc_matrix", 1)[0] for l in out.splitlines() if l.strip()})
    if not outs:
        raise ValueError("No Cell Ranger ARC output found. Choose a folder containing each sample's 'outs' folder "
                         "(with filtered_feature_bc_matrix).")
    rows = []
    for o in outs:
        parts = o.rstrip("/").split("/")
        name = parts[-2] if parts[-1] == "outs" and len(parts) > 1 else parts[-1]
        name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
        rows.append({"sample": name, "outs": o, "condition": "", "batch": ""})
    return {"rows": rows, "message": f"Found {len(rows)} samples. Fill in each sample's condition, and a batch if samples were prepared on different days."}
