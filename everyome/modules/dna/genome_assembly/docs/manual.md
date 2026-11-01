# Genome assembly (PacBio, Nanopore, Illumina)

Builds a genome sequence from long reads, and lets you compare different ways of
doing it before choosing one. Two parts:

1. **On the cluster:** nf-core/genomeassembler (release 2.0.1) assembles the
   reads, polishes and scaffolds the assemblies, checks them (BUSCO, QUAST and,
   with Illumina reads, Merqury) and, if you give a related annotated genome,
   lifts its genes over.
2. **In a live session:** compare every assembly side by side, look at contigs
   and genes, choose the final assembly and export it.

For **bacteria** and other small genomes, or if you only have Illumina reads,
use *Bacterial genome assembly and annotation* instead: it assembles short
reads, long reads or both, and finds genes from scratch.

## What you need

- **Long reads**, at least one kind:
  - **PacBio HiFi** (`.fastq.gz`): about 15 kb, very accurate. 20–30× coverage is typical.
  - **Oxford Nanopore** (`.fastq.gz`): longer (often 20–100 kb) but with more errors per read. 30× or more.
- **Illumina reads** (optional, `_R1`/`_R2.fastq.gz`): used to **polish** the
  assembly (fix small errors, Pilon) and to measure its accuracy (Merqury).
  They cannot be assembled on their own here.
- **A related, annotated genome** (optional): its FASTA (*Ref fasta*) and genes
  (*Ref gff*, GFF3). Turn on *Lift annotations* to copy its genes onto your assembly.
- **An expected genome size** (*Genome size*, for example `750k`, `1.2g`) helps the assemblers.
- On the cluster: **Nextflow**, **Java** and **Apptainer** (ask IT). The pipeline
  itself ships with Everyome (`everyome-pipelines`): pressing Run copies
  nf-core/genomeassembler to your cluster once and checks it. Its software
  containers and BUSCO's gene sets are downloaded the first time they are
  needed. See `docs/PIPELINES.md`, including for clusters without internet
  access (BUSCO also accepts a local copy of its data, *Busco db*).

## Assemblies to make

Each row of the table is one assembly. *Suggest assemblies from the reads folder*
finds Nanopore files (named with `ont` or `nanopore`), HiFi files (`hifi`,
`ccs` or `pacbio`) and Illumina pairs, and suggests:

| Row | Strategy | Assembler | What it does |
|---|---|---|---|
| `_ont` | single | flye | Nanopore reads alone; polished with Medaka (and Pilon with Illumina reads) |
| `_hifi` | single | hifiasm | HiFi reads alone |
| `_hybrid` | hybrid | hifiasm | Both together: HiFi accuracy with Nanopore reach (hifiasm's ultra-long mode) |
| `_scaffold` | scaffold | flye_hifiasm | Each assembled on its own, then the Nanopore assembly is used to join the HiFi contigs (RagTag) |

Edit, remove or add rows: every row is assembled, so one run compares them all.
**Polishing**: `pilon` (Illumina reads), `medaka` (Nanopore reads), or both in
order (`medaka+pilon`).

## Pipeline settings

Every setting nf-core/genomeassembler accepts is on the settings page. Only
settings you change are passed to the pipeline. Everyome turns **BUSCO** and
**QUAST** on (the pipeline leaves them off). Common ones:

| Setting | What it changes |
|---|---|
| Genome size | Expected size; helps Flye. |
| Flye mode | `--nano-hq` for recent Nanopore reads (default), `--nano-raw` for older ones, `--pacbio-hifi` if Flye assembles HiFi reads. |
| Busco lineage | The gene set BUSCO looks for: `auto_euk` chooses one, or name it (for example `embryophyta_odb10` for plants). |
| Merqury | Measures accuracy with Illumina k-mers. |
| Scaffold … | Extra scaffolding with long reads (LINKS, LongStitch), Hi-C (YaHS) or a reference (RagTag). |
| Lift annotations | Copy genes from the related genome (needs *Ref fasta* and *Ref gff*). |

The pipeline's own tasks are sent to Slurm by Nextflow, each named with your
username, `everyome` and the module, so you can find them in `squeue`.

## Live session

1. **Compare assemblies.** Size, contigs, N50, L50, GC, gaps and BUSCO for every
   assembly, Nx curves and BUSCO bars.
2. **Look at contigs.** The largest contigs, and GC against length to spot
   contamination, plasmids or organelles.
3. **Look at genes.** Lifted-over genes: how many, how many could not be placed,
   their lengths, and a searchable table.
4. **Choose and export.** Pick the final assembly and say why. It is copied to
   `results/final/` with its genes and a table comparing every assembly.

## Things to watch

- **Heterozygous or polyploid genomes**: this pipeline does not separate
  haplotypes. An assembly much larger than expected, with many duplicated BUSCO
  genes, may contain both copies.
- **Contamination**: check contigs with unusual GC or coverage before publishing.
- **Lifted genes are not new annotation**: genes your organism has but the
  relative lacks are not found. De novo gene annotation will be its own tool.

## References

- nf-core/genomeassembler. https://doi.org/10.5281/zenodo.14986998
- Ewels P.A. et al. (2020). The nf-core framework for community-curated bioinformatics pipelines. *Nature Biotechnology* 38:276–278. https://doi.org/10.1038/s41587-020-0439-x
- Cheng H. et al. (2021). Haplotype-resolved de novo assembly using phased assembly graphs with hifiasm. *Nature Methods* 18:170–175. https://doi.org/10.1038/s41592-020-01056-5
- Kolmogorov M. et al. (2019). Assembly of long, error-prone reads using repeat graphs. *Nature Biotechnology* 37:540–546. https://doi.org/10.1038/s41587-019-0072-8
- Alonge M. et al. (2022). Automated assembly scaffolding using RagTag elevates a new tomato system for high-throughput genome editing. *Genome Biology* 23:258. https://doi.org/10.1186/s13059-022-02823-7
- Walker B.J. et al. (2014). Pilon: an integrated tool for comprehensive microbial variant detection and genome assembly improvement. *PLoS ONE* 9:e112963. https://doi.org/10.1371/journal.pone.0112963
- Shumate A., Salzberg S.L. (2021). Liftoff: accurate mapping of gene annotations. *Bioinformatics* 37:1639–1643. https://doi.org/10.1093/bioinformatics/btaa1016
- Manni M. et al. (2021). BUSCO update. *Molecular Biology and Evolution* 38:4647–4654. https://doi.org/10.1093/molbev/msab199
- Gurevich A. et al. (2013). QUAST: quality assessment tool for genome assemblies. *Bioinformatics* 29:1072–1075. https://doi.org/10.1093/bioinformatics/btt086
