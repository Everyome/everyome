"""Toy genomes for the assembly demos, where the truth is known.

A genome has chromosomes (or plasmids), repeat families placed at known spots and
genes. An assembly is made by breaking the genome where the reads could not
cross: at every repeat copy longer than the reads, and at a few coverage gaps.
Genes are then lifted onto the contigs (whole genes only), and BUSCO-style
completeness is worked out from a subset of genes treated as single-copy markers:
complete if a contig holds the whole gene and read errors did not break it,
fragmented if split or broken by errors, missing if its contig was lost.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np

PRODUCTS = ["DNA polymerase III subunit alpha", "Elongation factor Tu", "30S ribosomal protein S12", "ATP synthase subunit beta",
            "Chaperonin GroEL", "RNA polymerase sigma factor", "Glutamine synthetase", "Cell division protein FtsZ",
            "ABC transporter ATP-binding protein", "Two-component sensor histidine kinase", "Transcriptional regulator, LysR family",
            "Outer membrane protein A", "Ferredoxin", "Thioredoxin", "Peptidyl-prolyl cis-trans isomerase", "Heat shock protein 70",
            "Histone H3", "Actin", "Tubulin alpha chain", "Myosin light chain", "Zinc finger protein", "Kinesin-like protein",
            "Ubiquitin-conjugating enzyme E2", "Serine/threonine-protein kinase", "WD repeat-containing protein"]


def _seq(rng, n: int, gc: float) -> str:
    p = [(1 - gc) / 2, gc / 2, gc / 2, (1 - gc) / 2]
    return "".join(np.array(list("ACGT"))[rng.choice(4, n, p=p)])


def genome(seed: int, chroms: list[tuple[str, int, float]], repeats: list[tuple[str, int, int, str]], gene_every: int,
           busco_share: float = 0.12) -> dict:
    """chroms: (name, length, GC); repeats: (family, length, copies, where: 'any' or a chromosome name)."""
    rng = np.random.default_rng(seed)
    seqs = {c: list(_seq(rng, n, gc)) for c, n, gc in chroms}
    placed = []
    for fam, length, copies, where in repeats:
        unit = _seq(rng, length, 0.45)
        for _ in range(copies):
            for _try in range(200):
                c = where if where != "any" else chroms[int(rng.integers(0, len(chroms)))][0]
                if len(seqs[c]) < length * 3:
                    break
                s = int(rng.integers(length, len(seqs[c]) - 2 * length))
                if all(p["chrom"] != c or s + length + 2000 < p["start"] or s > p["end"] + 2000 for p in placed):
                    seqs[c][s:s + length] = unit
                    placed.append({"family": fam, "chrom": c, "start": s, "end": s + length, "length": length})
                    break
    genes, k = [], 0
    for c, n, _ in chroms:
        pos = int(rng.integers(200, gene_every))
        while pos < n - 3500:
            length = int(rng.integers(300, 3000))
            if not any(p["chrom"] == c and pos < p["end"] and pos + length > p["start"] for p in placed):
                k += 1
                known = rng.random() < 0.7               # Intent: about 30% of genes have no known function, as in real genomes
                genes.append({"id": f"gene{k:05d}", "chrom": c, "start": pos, "end": pos + length, "strand": "+-"[int(rng.integers(0, 2))],
                              "name": f"g{k}" if known else "", "product": PRODUCTS[k % len(PRODUCTS)] if known else "hypothetical protein",
                              "busco": bool(rng.random() < busco_share)})
            pos += length + int(rng.integers(gene_every // 3, gene_every))
    return {"seqs": {c: "".join(s) for c, s in seqs.items()}, "repeats": placed, "genes": genes,
            "lengths": {c: n for c, n, _ in chroms}}


def breaks(g: dict, seed: int, read_length: int, gaps: int, skip: tuple[str, ...] = ()) -> dict[str, list[int]]:
    """Where an assembly breaks: in the middle of every repeat copy at least as long as the reads, plus random gaps."""
    rng = np.random.default_rng(seed)
    out = {c: [] for c in g["seqs"] if c not in skip}
    for r in g["repeats"]:
        if r["chrom"] in out and r["length"] >= read_length:
            out[r["chrom"]].append((r["start"] + r["end"]) // 2)
    chroms = list(out)
    weights = np.array([g["lengths"][c] for c in chroms], float)
    for _ in range(gaps):
        c = chroms[int(rng.choice(len(chroms), p=weights / weights.sum()))]
        out[c].append(int(rng.integers(1000, g["lengths"][c] - 1000)))
    return {c: sorted(v) for c, v in out.items()}


def contigs(g: dict, cuts: dict[str, list[int]], name, min_length: int = 200) -> list[dict]:
    """Split each kept chromosome at its cuts; name(i, chrom, whole) gives each contig's name."""
    out = []
    for c, pos in cuts.items():
        edges = [0] + pos + [g["lengths"][c]]
        for a, b in zip(edges, edges[1:]):
            if b - a >= min_length:
                out.append({"chrom": c, "start": a, "end": b, "whole": len(edges) == 2})
    out.sort(key=lambda x: -(x["end"] - x["start"]))
    for i, x in enumerate(out, 1):
        x["name"] = name(i, x["chrom"], x["whole"])
        x["seq"] = g["seqs"][x["chrom"]][x["start"]:x["end"]]
    return out


def write_fasta(path: Path, ctgs: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with (gzip.open(path, "wt") if path.suffix == ".gz" else open(path, "w")) as fh:
        for x in ctgs:
            fh.write(f">{x['name']}\n")
            for i in range(0, len(x["seq"]), 80):
                fh.write(x["seq"][i:i + 80] + "\n")
    return path


def lift(g: dict, ctgs: list[dict]) -> tuple[list[dict], list[str]]:
    """Genes moved onto contig coordinates; genes not wholly inside one contig are reported as unmapped."""
    lifted, unmapped = [], []
    for gene in g["genes"]:
        x = next((c for c in ctgs if c["chrom"] == gene["chrom"] and c["start"] <= gene["start"] and gene["end"] <= c["end"]), None)
        if x is None:
            unmapped.append(gene["id"])
        else:
            lifted.append({**gene, "seqid": x["name"], "start": gene["start"] - x["start"] + 1, "end": gene["end"] - x["start"]})
    return lifted, unmapped


def write_gff(path: Path, genes: list[dict], source: str, ctgs: list[dict] | None = None) -> Path:
    """GFF3 with gene and CDS features; with ctgs, the sequences follow after ##FASTA (as Prokka writes it)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        fh.write("##gff-version 3\n")
        for x in ctgs or []:
            fh.write(f"##sequence-region {x['name']} 1 {len(x['seq'])}\n")
        for gene in genes:
            col = f"{gene['seqid']}\t{source}\t%s\t{gene['start']}\t{gene['end']}\t.\t{gene['strand']}\t%s\t"
            fh.write(col % ("gene", ".") + f"ID={gene['id']}" + (f";Name={gene['name']}" if gene["name"] else "") + "\n")
            fh.write(col % ("CDS", "0") + f"ID={gene['id']}_cds;Parent={gene['id']};product={gene['product']}\n")
        if ctgs:
            fh.write("##FASTA\n")
            for x in ctgs:
                fh.write(f">{x['name']}\n{x['seq']}\n")
    return path


def busco(g: dict, ctgs: list[dict], error_rate: float, seed: int) -> dict:
    """Completeness of the marker genes in this assembly. error_rate: share of contained markers broken by read errors."""
    rng = np.random.default_rng(seed)
    markers = [x for x in g["genes"] if x["busco"]]
    kept = {c["chrom"] for c in ctgs}
    c = f = m = 0
    for gene in markers:
        whole = any(x["chrom"] == gene["chrom"] and x["start"] <= gene["start"] and gene["end"] <= x["end"] for x in ctgs)
        if gene["chrom"] not in kept:
            m += 1
        elif whole and rng.random() >= error_rate:
            c += 1
        else:
            f += 1
    return {"n": len(markers), "complete": c, "fragmented": f, "missing": m}


def write_busco(path: Path, b: dict, lineage: str) -> Path:
    """A BUSCO short summary (JSON), with the one-line summary BUSCO itself writes."""
    pct = lambda k: round(100 * b[k] / max(1, b["n"]), 1)
    line = f"C:{pct('complete')}%[S:{pct('complete')}%,D:0.0%],F:{pct('fragmented')}%,M:{pct('missing')}%,n:{b['n']}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"lineage_dataset": {"name": lineage}, "results": {"one_line_summary": line, "Complete percentage": pct("complete")}}))
    return path


def placeholder_reads(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt") as f:
        f.write("@demo\nACGT\n+\nIIII\n")
    return path
