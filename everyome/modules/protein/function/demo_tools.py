"""Stand-in for InterProScan on the demo cluster: writes the TSV and JSON InterProScan would write for the demo
proteins (their planted domains; see demo_data.py), in InterProScan's own column order."""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from .demo_data import GO, matches


def _fasta(path: Path) -> dict[str, str]:
    out, name = {}, None
    for line in path.read_text().splitlines():
        if line.startswith(">"):
            name = line[1:].split()[0]
            out[name] = ""
        elif name:
            out[name] += line.strip()
    return out


def interproscan(fasta: Path, res: Path) -> None:
    time.sleep(float(os.environ.get("EVERYOME_DEMO_PAUSE", "1")))
    seqs, known = _fasta(fasta), matches()
    rows, js = [], []
    for pid, seq in seqs.items():
        md5 = hashlib.md5(seq.encode()).hexdigest()
        hits = known.get(pid, [])
        for db, acc, desc, start, end, ipr, iname, go in hits:
            score = f"{1e-25 * (1 + (start % 7)):.1E}"
            gos = "|".join(f"{g}(InterPro)" for g in go.split("|")) if go else "-"
            rows.append("\t".join([pid, md5, str(len(seq)), db, acc, desc, str(start), str(end), score, "T", "04-11-2026", ipr, iname, gos, "-"]))
        js.append({"xref": [{"id": pid}], "md5": md5, "sequence": seq,
                   "matches": [{"signature": {"accession": h[1], "description": h[2], "signatureLibraryRelease": {"library": h[0].upper()},
                                              "entry": {"accession": h[5], "name": h[6], "goXRefs": [{"id": g, "name": GO[g][0], "category": GO[g][1]}
                                                                                    for g in h[7].split("|") if g]}},
                                "locations": [{"start": h[3], "end": h[4]}]} for h in hits]})
    (res / "interproscan.tsv").write_text("\n".join(rows) + "\n")
    (res / "interproscan.json").write_text(json.dumps({"interproscan-version": "demo", "results": js}, indent=1))
    print(f"[demo] InterProScan stand-in: {len(rows)} matches in {len(seqs)} proteins", flush=True)
