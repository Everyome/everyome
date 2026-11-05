"""Demo data for Hi-C: a small made-up genome (two chromosomes) with known A/B compartments and TADs, read files for
two samples, and the contacts a Hi-C library of that genome would give (made by the demo pipeline from truth()).

<root> = <demo cluster>/data/dna.hic/
  fastq/          placeholder reads: larva_1_R1/R2.fastq.gz, larva_2_R1/R2.fastq.gz
  genome/         genome.fa: A compartments are GC-rich, B compartments GC-poor, as in most genomes
  .demo_truth/    truth.json: compartments and TAD boundaries, for the tests
"""
from __future__ import annotations

import gzip
import json
import zlib
from pathlib import Path

import numpy as np

CHROMS = [("chr1", 2_000_000), ("chr2", 1_500_000)]
BASE = 10_000                     # the finest map the demo pipeline makes (bp per bin)
SAMPLES = ["larva_1", "larva_2"]


def truth(seed: int = 71) -> dict:
    """Compartments (A or B, in 80 kb steps) and TAD boundaries (in 20 kb steps) along each chromosome."""
    rng = np.random.default_rng(seed)
    comps, tads = {}, {}
    for c, n in CHROMS:
        segs, pos, kind = [], 0, "A" if c == "chr1" else "B"
        while pos < n:
            end = min(n, pos + int(rng.integers(3, 8)) * 80_000)
            if n - end < 160_000:
                end = n
            segs.append([pos, end, kind])
            pos, kind = end, "B" if kind == "A" else "A"
        comps[c] = segs
        # Intent: compartment edges are also TAD edges; inside each compartment, domains of 120–300 kb.
        b = set()
        for s, e, _ in segs:
            b.add(s)
            p = s + int(rng.integers(6, 16)) * 20_000
            while p < e - 100_000:
                b.add(p)
                p += int(rng.integers(6, 16)) * 20_000
        tads[c] = sorted(x for x in b if 0 < x < n)
    return {"chroms": CHROMS, "base": BASE, "compartments": comps, "boundaries": tads}


def compartment_of(t: dict, chrom: str, pos: int) -> str:
    return next(k for s, e, k in t["compartments"][chrom] if s <= pos < e)


def contacts(sample: str, t: dict | None = None):
    """Simulated contacts at BASE resolution (upper triangle): bin1, bin2, count. Contacts fall with distance, are
    richer inside a TAD and between bins of the same compartment, and each bin has its own bias (mappability, GC,
    cutting sites), which balancing removes. Two bins per chromosome are nearly unmappable."""
    t = t or truth()
    rng = np.random.default_rng(zlib.crc32(sample.encode()))
    b1s, b2s, cs, off = [], [], [], 0
    offs = []
    for c, n in CHROMS:
        nb = -(-n // BASE)
        mids = np.arange(nb) * BASE + BASE // 2
        comp = np.array([compartment_of(t, c, int(m)) == "A" for m in mids])
        tad = np.searchsorted(np.array(t["boundaries"][c]), mids, side="right")
        bias = rng.lognormal(0, 0.25, nb)
        bias[rng.choice(nb, 2, replace=False)] = 0.02
        i, j = np.triu_indices(nb)
        d = (j - i).astype(float)
        mu = 260.0 * (d + 1) ** -1.1
        mu *= np.where(tad[i] == tad[j], 2.4, 1.0)
        same = comp[i] == comp[j]
        mu *= np.where(same, np.where(comp[i], 1.6, 1.35), 0.6)
        mu *= bias[i] * bias[j]
        k = rng.poisson(mu)
        keep = k > 0
        b1s.append(i[keep] + off)
        b2s.append(j[keep] + off)
        cs.append(k[keep])
        offs.append((off, nb, bias))
        off += nb
    # Intent: a few contacts between the chromosomes, as in any real library.
    (o1, n1, bias1), (o2, n2, bias2) = offs
    i, j = np.meshgrid(np.arange(n1), np.arange(n2), indexing="ij")
    k = rng.poisson(0.04 * bias1[i] * bias2[j])
    keep = k > 0
    b1s.append(i[keep] + o1)
    b2s.append(j[keep] + o2)
    cs.append(k[keep])
    return np.concatenate(b1s), np.concatenate(b2s), np.concatenate(cs)


def _genome(t: dict, path: Path):
    rng = np.random.default_rng(70)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        for c, n in CHROMS:
            gc = np.zeros(n)
            for s, e, k in t["compartments"][c]:
                gc[s:e] = 0.45 if k == "A" else 0.37
            r = rng.random(n)
            at = np.where(rng.random(n) < 0.5, ord("A"), ord("T"))
            g = np.where(rng.random(n) < 0.5, ord("G"), ord("C"))
            s = np.where(r < gc, g, at).astype(np.uint8).tobytes().decode()
            fh.write(f">{c}\n" + "\n".join(s[i:i + 80] for i in range(0, n, 80)) + "\n")


def build(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for s in SAMPLES:
        for r in (1, 2):
            p = root / "fastq" / f"{s}_R{r}.fastq.gz"
            p.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(p, "wt") as f:
                f.write("@demo\nGATCGATC\n+\nIIIIIIII\n")
    t = truth()
    _genome(t, root / "genome" / "genome.fa")
    (root / ".demo_truth").mkdir(exist_ok=True)
    (root / ".demo_truth" / "truth.json").write_text(json.dumps(t))
    return root
