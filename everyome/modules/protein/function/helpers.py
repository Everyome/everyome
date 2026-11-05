"""App-side helper for protein function annotation: what the cluster stage made (Run page)."""
from __future__ import annotations

import shlex


def report(backend, run: dict) -> dict:
    d = f"{run['dir']}/results"
    rc, out, _ = backend.run(f"cd {shlex.quote(d)} 2>/dev/null && wc -l interproscan.tsv 2>/dev/null; grep -c '>' proteins.fasta 2>/dev/null", timeout=60)
    lines = out.split()
    matches = int(lines[0]) if lines and lines[0].isdigit() else 0
    proteins = int(lines[-1]) if len(lines) > 1 and lines[-1].isdigit() else 0
    return {"tsv": "results/interproscan.tsv" if matches else None, "matches": matches, "proteins": proteins}
