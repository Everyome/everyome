"""Batch stages for the Sequence summary module.

Run by the job scripts as `python -m everyome.modules.tutorial.sequence_summary.steps <stage>`
inside the run folder; settings come from $EVERYOME_PARAMS.
  lengths  FASTA -> results/lengths.tsv (id, length), shorter sequences dropped
  gc       FASTA + lengths.tsv -> results/gc.tsv (id, length, gc)
"""
from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path


def read_fasta(path):
    """Yield (id, sequence) pairs; the id is the first word after '>'."""
    name, parts = None, []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line.startswith(">"):
                if name is not None:
                    yield name, "".join(parts)
                name, parts = (line[1:].split() or ["unnamed"])[0], []
            elif line:
                parts.append(line.upper())
    if name is not None:
        yield name, "".join(parts)


def gc_fraction(seq: str, count_n: bool) -> float:
    gc = seq.count("G") + seq.count("C")
    total = len(seq) if count_n else len(seq) - seq.count("N")
    return gc / total if total else 0.0


def lengths(params, res: Path):
    kept = dropped = 0
    with open(res / "lengths.tsv", "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["id", "length"])
        for name, seq in read_fasta(params["fasta"]):
            if len(seq) < params["min_length"]:
                dropped += 1
                continue
            w.writerow([name, len(seq)]); kept += 1
    print(f"kept {kept} sequences, left out {dropped} shorter than {params['min_length']} bases")


def gc(params, res: Path):
    keep = {r["id"] for r in csv.DictReader(open(res / "lengths.tsv"), delimiter="\t")}
    digits = int(params["rounding"])
    with open(res / "gc.tsv", "w", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["id", "length", "gc"])
        for name, seq in read_fasta(params["fasta"]):
            if name in keep:
                w.writerow([name, len(seq), round(gc_fraction(seq, params["count_n"]), digits)])
    print(f"GC content written for {len(keep)} sequences")


def main():
    stage = sys.argv[1]
    params = json.loads(Path(os.environ["EVERYOME_PARAMS"]).read_text())
    res = Path(os.environ["EVERYOME_RUN_DIR"]) / "results"
    res.mkdir(exist_ok=True)
    {"lengths": lengths, "gc": gc}[stage](params, res)


if __name__ == "__main__":
    main()
