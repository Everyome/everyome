"""App-side helpers for single-cell ATAC-seq (run on this computer, reading the cluster through the backend).

  scan         fill the samples table from a folder of reads (R1, R2 and the barcode read) or fragments files
  report       after the cluster stage: each sample's fragments file and its size
  chrom_sizes  chromosome lengths from a genome FASTA (its .fai index if there is one); shared with the engine
"""
from __future__ import annotations

import re
from pathlib import Path

READ = re.compile(r"^(?P<sample>.+?)(?:_S\d+)?(?:_L\d{3})?[._](?P<read>R1|R2|R3|I2)(?:_001)?\.f(ast)?q\.gz$")
FRAG = re.compile(r"^(?P<sample>.+?)[._]?(atac_)?fragments\.tsv\.gz$")


def chrom_sizes(fasta: str) -> dict[str, int]:
    fai = Path(fasta + ".fai")
    if fai.exists():
        return {l.split("\t")[0]: int(l.split("\t")[1]) for l in fai.read_text().splitlines() if l.strip()}
    sizes, name, n = {}, None, 0
    with open(fasta) as f:
        for line in f:
            if line.startswith(">"):
                if name:
                    sizes[name] = n
                name, n = line[1:].split()[0], 0
            else:
                n += len(line.strip())
    if name:
        sizes[name] = n
    return sizes


def scan(backend, path: str = "") -> dict:
    if not path:
        raise ValueError("Choose the reads folder first.")
    files = sorted(e.name for e in backend.listdir(path) if not e.is_dir)
    found = {}
    for n in files:
        full = f"{path.rstrip('/')}/{n}"
        m = READ.match(n)
        if m:
            found.setdefault(m.group("sample"), {})[m.group("read")] = full
            continue
        m = FRAG.match(n)
        if m:
            found.setdefault(m.group("sample"), {})["fragments"] = full
    if not found:
        raise ValueError("No reads named like <sample>_R1.fastq.gz (with R2 and the barcode read R3 or I2), "
                         "and no <sample>_fragments.tsv.gz files, were found in that folder.")
    rows = []
    for s, f in found.items():
        cond = re.sub(r"[_.-]?(rep)?[0-9A-Z]$", "", s) or s
        # Intent: 10x names ATAC reads R1 (genomic), R2 (the 16-base barcode) and R3 (genomic); others keep R1/R2 genomic
        # and deliver the barcode as I2.
        if "R3" in f:
            r2, bc = f["R3"], f.get("R2", "")
        else:
            r2, bc = f.get("R2", ""), f.get("I2", "")
        rows.append({"sample": s, "read1": f.get("R1", ""), "read2": r2, "barcodes": bc, "fragments": f.get("fragments", ""),
                     "condition": cond, "batch": ""})
    return {"rows": rows, "message": f"Found {len(rows)} samples. Check which file holds the cell barcodes: it is the "
                                     "short read (16 bases for 10x). Check each condition too; it was guessed from the name."}


def report(backend, run: dict) -> dict:
    d = run["dir"]
    out = []
    for r in run["values"]["samples"]:
        p = f"{d}/results/fragments/{r['sample']}.tsv.gz"
        size = next((e.size for e in backend.listdir(f"{d}/results/fragments") if e.name == f"{r['sample']}.tsv.gz"), None) \
            if backend.exists(f"{d}/results/fragments") else None
        out.append({"sample": r["sample"], "path": p, "size": size})
    return {"fragments": out}
