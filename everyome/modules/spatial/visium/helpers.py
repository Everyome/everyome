"""App-side helper for Visium: find each section's Space Ranger output folder.

  scan   folders inside the chosen one that hold Space Ranger output ('outs' with a filtered matrix and a spatial folder)
"""
from __future__ import annotations

import re
import shlex


def scan(backend, path: str = "") -> dict:
    if not path:
        raise ValueError("Choose the folder first.")
    q = shlex.quote(path.rstrip("/"))
    # Intent: look a few levels down for Space Ranger's tell-tale spatial/scalefactors_json.json.
    rc, out, _ = backend.run(f"find {q} -maxdepth 5 -path '*spatial/scalefactors_json.json' 2>/dev/null | sort | head -100", timeout=120)
    outs = sorted({l.rsplit("/spatial/", 1)[0] for l in out.splitlines() if l.strip()})
    if not outs:
        raise ValueError("No Space Ranger output found. Choose a folder containing each section's 'outs' folder (with spatial/scalefactors_json.json).")
    rows = []
    for o in outs:
        parts = o.rstrip("/").split("/")
        name = parts[-2] if parts[-1] == "outs" and len(parts) > 1 else parts[-1]
        name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
        cond = re.sub(r"[_.-]?(rep)?\d+$", "", name, flags=re.I) or name
        cond = cond.split("_")[-1] if "_" in cond else cond
        rows.append({"sample": name, "outs": o, "condition": cond, "batch": ""})
    return {"rows": rows, "message": f"Found {len(rows)} sections. Check each condition (guessed from the folder name) and add batches if sections came from different days or slides."}
