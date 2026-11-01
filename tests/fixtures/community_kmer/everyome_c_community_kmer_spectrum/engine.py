"""Count k-mers in a FASTA file and summarise how often each occurs."""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from everyome.core.engine import BaseEngine


def read_fasta(path: Path) -> list[str]:
    seqs, cur = [], []
    for line in Path(path).read_text().splitlines():
        if line.startswith(">"):
            if cur:
                seqs.append("".join(cur))
            cur = []
        else:
            cur.append(line.strip().upper())
    if cur:
        seqs.append("".join(cur))
    return seqs


def count(seqs: list[str], k: int) -> Counter:
    c = Counter()
    for s in seqs:
        for i in range(len(s) - k + 1):
            kmer = s[i:i + k]
            if "N" not in kmer:
                c[kmer] += 1
    return c


class Engine(BaseEngine):
    API = ("spectrum", "export")
    REPLAY = ("export",)

    def __init__(self, run_dir: str):
        super().__init__(run_dir)
        self.k = int(self.params.get("k", 5))
        self.counts = count(read_fasta(self.params["fasta"]), self.k)

    def spectrum(self):
        hist = Counter(self.counts.values())
        return {"k": self.k, "distinct": len(self.counts), "total": sum(self.counts.values()),
                "occurrences": sorted(hist), "kmers": [hist[n] for n in sorted(hist)]}

    def export(self):
        with open(self.dir / "results" / "kmers.tsv", "w", newline="") as fh:
            w = csv.writer(fh, delimiter="\t")
            w.writerow(["kmer", "count"])
            w.writerows(self.counts.most_common())
        self._record("exported", file="kmers.tsv", kmers=len(self.counts))
        return {"file": "kmers.tsv"}


def methods(rec: dict) -> str:
    st = {x["id"]: x["value"] for x in rec["settings"]}
    return (f"K-mers of length {st['k']} were counted with the K-mer spectrum community module "
            f"(version {rec['module']['version']}) of Everyome (version {rec['everyome']}).\n")
