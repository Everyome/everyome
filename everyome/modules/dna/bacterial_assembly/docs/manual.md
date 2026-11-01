# Bacterial genome assembly and annotation

Builds and annotates the genomes of bacterial isolates (and other small genomes)
from **Illumina reads, long reads (Nanopore or PacBio), or both**. Two parts:

1. **On the cluster:** nf-core/bacass (release 2.6.1) checks and trims the reads,
   assembles them with the assemblers you choose, polishes long-read assemblies,
   checks each assembly (QUAST, BUSCO) and finds its genes (Prokka or Bakta).
2. **In a live session:** compare the assemblies side by side, look at contigs
   (chromosome and plasmids) and genes, choose the final assembly and export it.

For larger genomes (plants, animals, fungi), use *Genome assembly (PacBio,
Nanopore, Illumina)*.

## Which reads, which assembly type

| You have | Assembly type | What to expect |
|---|---|---|
| Illumina reads only | `short` | Accurate, but in tens to hundreds of pieces: short reads cannot cross rRNA operons or insertion sequences. |
| Long reads only | `long` | Usually the whole chromosome in one piece; polished with Medaka. Small plasmids are often missed. |
| Both | `hybrid` (default) | The best of both: complete replicons from long reads, accuracy from short reads. |

*Assembly type* applies to the whole run, so put isolates with the same kind of
reads in one run.

## Isolates

One row per isolate: Illumina read 1 and 2, long reads, and the genome size if
you know it (for example `4.6m`). *Find isolates in the reads folder* matches
files by isolate name: `isolate1_R1.fastq.gz`, `isolate1_R2.fastq.gz` and
`isolate1_ont.fastq.gz` become one row.

## Pipeline settings

Every setting nf-core/bacass accepts is on the settings page; only settings you
change are passed to the pipeline. Everyome starts from settings the pipeline
accepts as they stand:

| Setting | Everyome's starting value | Why |
|---|---|---|
| Assembly type | `hybrid` | The pipeline has none; choose `short` or `long` to match your reads. |
| Assembler | `unicycler` | Works for all three types. List several, separated by commas, to compare them in one run: `unicycler,megahit` (short), `flye,canu,raven` (long), `unicycler,dragonflye` (hybrid). |
| Skip kraken2, Skip kmerfinder | on | Contamination screening needs databases you download first. To screen, download a Kraken2 database (https://benlangmead.github.io/aws-indexes/k2) and a KmerFinder database, set *Kraken2db* and *Kmerfinderdb*, and turn these off. |

Other common settings: *Annotation tool* (`prokka`, or `bakta` with its database
in *Baktadb*), *Busco lineage* (`bacteria_odb10` by default; a narrower lineage
says more), *Polish method* for long reads.

On the cluster you need **Nextflow**, **Java** and **Apptainer** (ask IT). The
pipeline ships with Everyome (`everyome-pipelines`): pressing Run copies
nf-core/bacass to your cluster once and checks it; its software containers and
BUSCO's gene sets are downloaded the first time they are needed (see
`docs/PIPELINES.md`). The pipeline's tasks are named with your username,
`everyome` and the module, so you can find them in `squeue`.

## Live session

1. **Compare assemblies.** Size, contigs, N50, GC and BUSCO for every isolate and
   assembler, with Nx curves and BUSCO bars.
2. **Look at contigs.** The chromosome and plasmids stand out by length and often
   by GC content; scattered short contigs with unusual GC may be contamination.
3. **Look at genes.** How many genes, how many have a known product, their
   lengths, and a searchable table.
4. **Choose and export.** Copies the chosen assembly and its genes to
   `results/final/`, with a table comparing every assembly.

## Things to watch

- **Genome size**: most bacteria are 2–7 Mb. Much larger usually means
  contamination or a mixed culture: check the contigs' GC.
- **Plasmids**: compare assemblers. If only some find a small plasmid, it is
  probably real (long-read libraries often lose small fragments).
- **Completeness**: BUSCO above about 95% (bacteria_odb10) is expected for a good
  bacterial assembly.

## References

- nf-core/bacass. https://doi.org/10.5281/zenodo.2669428
- Ewels P.A. et al. (2020). The nf-core framework for community-curated bioinformatics pipelines. *Nature Biotechnology* 38:276–278. https://doi.org/10.1038/s41587-020-0439-x
- Wick R.R. et al. (2017). Unicycler: resolving bacterial genome assemblies from short and long sequencing reads. *PLoS Computational Biology* 13:e1005595. https://doi.org/10.1371/journal.pcbi.1005595
- Kolmogorov M. et al. (2019). Assembly of long, error-prone reads using repeat graphs. *Nature Biotechnology* 37:540–546. https://doi.org/10.1038/s41587-019-0072-8
- Seemann T. (2014). Prokka: rapid prokaryotic genome annotation. *Bioinformatics* 30:2068–2069. https://doi.org/10.1093/bioinformatics/btu153
- Schwengers O. et al. (2021). Bakta: rapid and standardized annotation of bacterial genomes via alignment-free sequence identification. *Microbial Genomics* 7:000685. https://doi.org/10.1099/mgen.0.000685
- Manni M. et al. (2021). BUSCO update. *Molecular Biology and Evolution* 38:4647–4654. https://doi.org/10.1093/molbev/msab199
- Gurevich A. et al. (2013). QUAST: quality assessment tool for genome assemblies. *Bioinformatics* 29:1072–1075. https://doi.org/10.1093/bioinformatics/btt086
