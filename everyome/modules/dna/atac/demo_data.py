"""Demo data for ATAC-seq: six libraries (polyp and planula, three replicates each) on a small made-up genome, with
open sites of which some truly open or close between the two groups.

<root> = <demo cluster>/data/dna.atac/
  fastq/                      placeholder paired reads, <group>_rep<n>_R1.fastq.gz / _R2.fastq.gz
  genome/genome.fa, genes.gtf a small genome (two chromosomes) and its genes
  .demo_truth/sites.json      every open site: position, width, how open, fold change in planula, reads per library
  .demo_truth/frip.json       each library's fraction of reads in peaks
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np

CHROMS = {"chr1": 1_200_000, "chr2": 900_000}
GROUPS = ["polyp", "planula"]
REPS = 3
N_SITES, N_UP, N_DOWN = 900, 70, 70
CALL_AT = 18          # reads (scaled to a typical library) above which the demo 'caller' finds a site in a library


def genes(seed: int = 21) -> list[dict]:
    """One gene about every 9 kb on each chromosome: name, strand, start, end (1-based, as in GTF)."""
    rng = np.random.default_rng(seed)
    out, k = [], 0
    for c, n in CHROMS.items():
        pos = 4_000
        while pos < n - 8_000:
            k += 1
            L = int(rng.integers(1_500, 6_000))
            out.append({"id": f"DEMOG{k:04d}", "name": f"atg{k}", "chrom": c, "strand": "+" if rng.random() < .5 else "-",
                        "start": pos, "end": pos + L})
            pos += L + int(rng.integers(2_500, 7_000))
    return out


def libraries() -> list[str]:
    return [f"{g}_REP{r}" for g in GROUPS for r in range(1, REPS + 1)]


def build(root: Path, seed: int = 22) -> Path:
    rng = np.random.default_rng(seed)
    root.mkdir(parents=True, exist_ok=True)
    gs = genes()
    tss = [(g["chrom"], g["start"] if g["strand"] == "+" else g["end"]) for g in gs]
    # Intent: about 40% of open sites sit at promoters (within 500 bp of a TSS), the rest in introns and between genes.
    sites, used = [], set()
    while len(sites) < N_SITES:
        if rng.random() < 0.4:
            c, t = tss[int(rng.integers(len(tss)))]
            centre = t + int(rng.normal(0, 200))
        else:
            c = "chr1" if rng.random() < CHROMS["chr1"] / sum(CHROMS.values()) else "chr2"
            centre = int(rng.integers(2_000, CHROMS[c] - 2_000))
        w = int(np.clip(rng.lognormal(np.log(380), 0.45), 150, 2_000))
        key = (c, centre // 1_500)
        if key in used:                       # Intent: keep sites apart so each one is a separate peak
            continue
        used.add(key)
        sites.append({"chrom": c, "start": centre - w // 2, "end": centre + w // 2})
    sites.sort(key=lambda s: (s["chrom"], s["start"]))
    base = np.exp(rng.normal(3.4, 1.0, N_SITES))           # how open each site is (reads in a typical library)
    fold = np.ones(N_SITES)
    up = rng.choice(N_SITES, N_UP, replace=False)
    down = rng.choice(np.setdiff1d(np.arange(N_SITES), up), N_DOWN, replace=False)
    fold[up], fold[down] = 4.0, 0.25
    disp = 0.04 + 0.6 / np.sqrt(base + 1)                    # negative-binomial dispersion, larger for weak sites
    counts, depth = {}, {}
    for lib in libraries():
        depth[lib] = float(rng.uniform(0.7, 1.4))
        mu = base * depth[lib] * (fold if lib.startswith("planula") else 1)
        counts[lib] = rng.negative_binomial(1 / disp, 1 / (1 + mu * disp)).tolist()
    for i, s in enumerate(sites):
        s.update(base=round(float(base[i]), 3), fold=float(fold[i]), counts={lib: int(counts[lib][i]) for lib in libraries()})
    # Intent: one library is noisier (more background), so its FRiP is low; its peaks are still in the right places.
    frip = {lib: round(float(rng.uniform(0.28, 0.42)), 4) for lib in libraries()}
    frip["polyp_REP3"] = 0.16
    truth = root / ".demo_truth"; truth.mkdir(exist_ok=True)
    (truth / "sites.json").write_text(json.dumps({"sites": sites, "depth": depth, "call_at": CALL_AT,
                                                  "up": [i for i in range(N_SITES) if fold[i] > 1], "down": [i for i in range(N_SITES) if fold[i] < 1]}))
    (truth / "frip.json").write_text(json.dumps(frip))
    fq = root / "fastq"; fq.mkdir(exist_ok=True)
    for g in GROUPS:
        for r in range(1, REPS + 1):
            for rd in ("R1", "R2"):
                with gzip.open(fq / f"{g}_rep{r}_{rd}.fastq.gz", "wt") as f:
                    f.write("@demo\nACGT\n+\nIIII\n")
    gd = root / "genome"; gd.mkdir(exist_ok=True)
    with open(gd / "genome.fa", "w") as fh:
        for c, n in CHROMS.items():
            s = "".join(rng.choice(list("ACGT"), n))
            fh.write(f">{c}\n" + "\n".join(s[i:i + 80] for i in range(0, n, 80)) + "\n")
    with open(gd / "genes.gtf", "w") as fh:
        for g in gs:
            a = f'gene_id "{g["id"]}"; gene_name "{g["name"]}";'
            fh.write(f"{g['chrom']}\tdemo\tgene\t{g['start']}\t{g['end']}\t.\t{g['strand']}\t.\t{a}\n")
            fh.write(f"{g['chrom']}\tdemo\ttranscript\t{g['start']}\t{g['end']}\t.\t{g['strand']}\t.\t{a} transcript_id \"{g['id']}.1\";\n")
            fh.write(f"{g['chrom']}\tdemo\texon\t{g['start']}\t{g['end']}\t.\t{g['strand']}\t.\t{a} transcript_id \"{g['id']}.1\";\n")
    return root
