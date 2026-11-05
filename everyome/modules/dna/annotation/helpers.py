"""App-side helper for genome annotation: what the cluster stages made (Run page)."""
from __future__ import annotations

import shlex


def report(backend, run: dict) -> dict:
    d = f"{run['dir']}/results"
    rc, out, _ = backend.run(f"cd {shlex.quote(d)} 2>/dev/null && (grep -c $'\\tgene\\t' annotation.gff3 || echo 0); "
                             "(grep -c '>' proteins.faa 2>/dev/null || echo 0); cat busco/short_summary*.json 2>/dev/null | head -c 2000", timeout=60)
    parts = out.split("\n", 2)
    genes = int(parts[0]) if parts and parts[0].strip().isdigit() else 0
    proteins = int(parts[1]) if len(parts) > 1 and parts[1].strip().isdigit() else 0
    busco = ""
    if len(parts) > 2 and "one_line_summary" in parts[2]:
        import json
        try:
            busco = json.loads(parts[2])["results"]["one_line_summary"]
        except (ValueError, KeyError):
            busco = ""
    return {"gff": "results/annotation.gff3" if genes else None, "genes": genes, "proteins": proteins, "busco": busco}
