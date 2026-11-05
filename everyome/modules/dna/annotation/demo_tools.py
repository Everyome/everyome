"""Stand-ins for Helixer, gffread and BUSCO on the demo cluster: they write the files the real tools write, for the
demo genome's genes (see demo_data.py)."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .demo_data import truth


def _pause():
    time.sleep(float(os.environ.get("EVERYOME_DEMO_PAUSE", "1")) / 3)


def predict(genome: Path, res: Path) -> None:
    _pause()
    lines = ["##gff-version 3"]
    for g in truth():
        a, b = g["exons"][0][0], g["exons"][-1][1]
        col = f"{g['chrom']}\tHelixerPost\t%s\t%d\t%d\t.\t{g['strand']}\t%s\t%s"
        lines.append(col % ("gene", a, b, ".", f"ID={g['id']}"))
        lines.append(col % ("mRNA", a, b, ".", f"ID={g['id']}.1;Parent={g['id']}"))
        for i, (s, e) in enumerate(g["exons"], 1):
            lines.append(col % ("exon", s, e, ".", f"ID={g['id']}.1.exon.{i};Parent={g['id']}.1"))
            lines.append(col % ("CDS", s, e, "0", f"ID={g['id']}.1.CDS.{i};Parent={g['id']}.1"))
    (res / "annotation.gff3").write_text("\n".join(lines) + "\n")
    print(f"[demo] Helixer stand-in: {len(truth())} genes", flush=True)


def proteins(res: Path) -> None:
    _pause()
    (res / "proteins.faa").write_text("".join(f">{g['id']}.1\n{g['protein']}\n" for g in truth()))
    print("[demo] gffread stand-in: proteins written", flush=True)


def busco(res: Path, lineage: str) -> None:
    _pause()
    d = res / "busco"
    d.mkdir(exist_ok=True)
    s = {"C": 86.4, "S": 83.9, "D": 2.5, "F": 5.3, "M": 8.3, "n": 954}
    line = f"C:{s['C']}%[S:{s['S']}%,D:{s['D']}%],F:{s['F']}%,M:{s['M']}%,n:{s['n']}"
    (d / f"short_summary.specific.{lineage}.busco.json").write_text(json.dumps({
        "lineage_dataset": {"name": lineage}, "results": {"one_line_summary": line, "Complete percentage": s["C"],
        "Single copy percentage": s["S"], "Multi copy percentage": s["D"], "Fragmented percentage": s["F"],
        "Missing percentage": s["M"], "n_markers": s["n"]}}))
    print(f"[demo] BUSCO stand-in: {line}", flush=True)
