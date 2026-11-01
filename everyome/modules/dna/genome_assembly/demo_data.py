"""Build the genome assembly demo data: reads for a toy three-chromosome genome and a related, annotated reference.

<root> = <demo cluster>/data/dna.assembly/
  reads/        placeholder reads: plant_ont.fastq.gz, plant_hifi.fastq.gz, plant_R1/R2.fastq.gz (Illumina)
  reference/    related.fa and related.gff3: a 'related species' to lift genes from (here the true genome)
The demo pipeline rebuilds the same genome (truth()) and assembles it as each read type would.
"""
from __future__ import annotations

from pathlib import Path

from .. import demo_genome as dg

# Intent: repeats of three sizes, so each read type stops at a different set of them:
# Illumina (short) at all, HiFi (~15 kb) at the 18 kb and 30 kb families, Nanopore (~40 kb reads) at none.
CHROMS = [("chr1", 300_000, 0.40), ("chr2", 250_000, 0.41), ("chr3", 200_000, 0.39)]
REPEATS = [("LTR_retrotransposon", 18_000, 3, "any"), ("DNA_transposon", 8_000, 6, "any"), ("segmental_duplication", 30_000, 2, "any")]


def truth() -> dict:
    return dg.genome(3, CHROMS, REPEATS, gene_every=2500, busco_share=0.4)


def build(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for n in ("plant_ont.fastq.gz", "plant_hifi.fastq.gz", "plant_R1.fastq.gz", "plant_R2.fastq.gz"):
        dg.placeholder_reads(root / "reads" / n)
    g = truth()
    whole = [{"name": c, "chrom": c, "start": 0, "end": n, "seq": g["seqs"][c]} for c in g["seqs"] for n in [g["lengths"][c]]]
    dg.write_fasta(root / "reference" / "related.fa", whole)
    dg.write_gff(root / "reference" / "related.gff3", [{**x, "seqid": x["chrom"], "start": x["start"] + 1} for x in g["genes"]], "demo")
    return root
