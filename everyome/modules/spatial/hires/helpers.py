"""App-side helper for high-resolution spatial data: find each section's output and which platform made it.

  scan   folders inside the chosen one that hold Visium HD (binned_outputs), Stereo-seq (a .gem file) or Curio (.h5ad) output
"""
from __future__ import annotations

import re
import shlex


def scan(backend, path: str = "") -> dict:
    if not path:
        raise ValueError("Choose the folder first.")
    q = shlex.quote(path.rstrip("/"))
    rc, out, _ = backend.run(f"find {q} -maxdepth 4 \\( -name binned_outputs -o -name '*.gem' -o -name '*.gem.gz' -o -name '*anndata.h5ad' \\) "
                             "2>/dev/null | sort | head -200", timeout=120)
    found = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        folder, name = line.rsplit("/", 1)
        found.setdefault(folder, "visium_hd" if name == "binned_outputs" else "stereo" if ".gem" in name else "curio")
    if not found:
        raise ValueError("No Visium HD, Stereo-seq or Curio output found. Choose a folder containing each section's output folder.")
    rows = []
    for folder, platform in sorted(found.items()):
        parts = folder.rstrip("/").split("/")
        name = parts[-2] if parts[-1] == "outs" and len(parts) > 1 else parts[-1]
        rows.append({"sample": re.sub(r"[^A-Za-z0-9_.-]+", "_", name), "outs": folder, "platform": platform, "condition": "", "batch": ""})
    return {"rows": rows, "message": f"Found {len(rows)} sections. Fill in each section's condition, and a batch if sections were run on different days."}
