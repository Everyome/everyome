"""Build the bacterial assembly demo data: reads for two isolates of a toy bacterium.

<root> = <demo cluster>/data/dna.bacterial/
  reads/   isolate1_R1/R2.fastq.gz, isolate1_ont.fastq.gz, isolate2_R1/R2.fastq.gz, isolate2_ont.fastq.gz (placeholders)
The demo pipeline rebuilds the genome (truth()) and assembles it as each assembler would.
"""
from __future__ import annotations

from pathlib import Path

from .. import demo_genome as dg

# Intent: one chromosome and two plasmids, with rRNA operons (5 kb) and insertion sequences (1.3 kb): the repeats that
# break short-read assemblies of bacteria. The small plasmid is what long-read assemblers often miss.
CHROMS = [("chromosome", 900_000, 0.50), ("plasmid_A", 48_000, 0.46), ("plasmid_B", 6_000, 0.41)]
REPEATS = [("rRNA_operon", 5_000, 5, "chromosome"), ("IS_element", 1_300, 10, "chromosome"), ("IS_element_p", 1_300, 2, "plasmid_A")]


def truth() -> dict:
    return dg.genome(5, CHROMS, REPEATS, gene_every=300, busco_share=0.2)


def build(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for iso in ("isolate1", "isolate2"):
        for n in ("_R1.fastq.gz", "_R2.fastq.gz", "_ont.fastq.gz"):
            dg.placeholder_reads(root / "reads" / f"{iso}{n}")
    return root
