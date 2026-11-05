# 3D genome architecture (Hi-C)

Hi-C measures which parts of the genome touch each other in the nucleus. This module runs
**nf-core/hic** on your read pairs, which aligns them to your genome, keeps the valid ligation
products and builds balanced contact maps at several resolutions. A live session then lets you
check each library, look at the maps, see how contacts fall with distance, find open (A) and
closed (B) compartments, and find the boundaries of topologically associating domains (TADs).

It works with any genome you have as a FASTA file; nothing is downloaded.

## What you need

- **Paired-end Hi-C reads**, one pair of FASTQ files per sample (or per lane), named like
  `<sample>_R1.fastq.gz` and `<sample>_R2.fastq.gz`.
- **The genome** as a FASTA file. The pipeline builds the Bowtie 2 index and the restriction
  fragments itself (or give a ready index with *Bwt2 index* to save time).
- **The enzyme** the library was made with (*Digestion*: HindIII, DpnII, MboI or Arima), or its
  restriction and ligation sites, or *DNase* mode for protocols without an enzyme (such as Micro-C).
- On the cluster: Nextflow 25.10.4 or newer and Apptainer. The pipeline's own jobs need up to
  16 CPUs and 128 GB; the live session needs two CPUs and 16 GB.

## Samples table

*Find samples in the reads folder* pairs up read 1 and read 2 by name. Rows with the same
sample name (for example several lanes) are merged into one map. Hi-C needs both reads of
every pair, so single-end files are refused.

## Pipeline settings

Every setting nf-core/hic accepts is on the settings page, in the pipeline's own groups. Only
settings you change are passed to the pipeline. The ones most worth a look:

| Setting | What it changes |
|---|---|
| Digestion | The enzyme: sets the restriction and ligation sites. Required unless you give the sites or use DNase mode. |
| Bin size | The resolutions of the maps the pipeline makes (comma separated, in bp). Defaults 1 Mb and 500 kb. |
| Res zoomify | The finest resolution of the multi-resolution `.mcool` map (default 5 kb); coarser ones are made from it. |
| Res compartments | The resolution for compartments (default 250 kb). |
| Res tads | Resolutions for insulation and HiCExplorer TADs (default 40 kb and 20 kb). |
| Res dist decay | The resolution for the distance-decay plot (default 1 Mb). |
| Min mapq | Minimum mapping quality for a read to count (default 10). |

The defaults suit genomes of a few hundred megabases and up. For a small genome (tens of
megabases), use finer maps for compartments (50–100 kb) and TADs (5–10 kb). Everyome's
session can use any resolution the pipeline made, and makes the `.mcool` resolutions
available for the map viewer.

The pipeline's tasks are sent to Slurm by Nextflow, each named with your username, `everyome`
and the module, so you can find them in `squeue`. Only one job (the pipeline itself) is
submitted when you press Run; it then submits the rest.

## Live session

1. **Check libraries.** Read pairs, valid pairs, duplicates, the share of contacts within
   chromosomes and over 20 kb, and contact probability against distance with its slope.
2. **Look at contact maps.** Any region of any chromosome at any resolution, balanced or raw.
   Zoom and move along the chromosome; TAD boundaries are marked once found.
3. **Compartments.** The first eigenvector of each chromosome's map (from the pipeline when it
   made one at that resolution, otherwise computed in the session in the same way), turned so
   that positive (A) goes with higher GC content.
4. **TAD boundaries.** An insulation score at the resolution and window you choose; boundaries
   are its dips. HiCExplorer's own boundaries from the pipeline are shown for comparison.
5. **Export.** Library statistics, distance-decay curves, compartment tracks (bedGraph) and TAD
   boundaries and domains (BED), in `results/final/`. The balanced maps themselves are in
   `results/contact_maps/cool/` (open the `.mcool` in HiGlass, or with cooler or cooltools).

## Reading the results

- **Coverage limits resolution.** A map is only as fine as its contacts allow; if most bins
  have only a few contacts, go coarser.
- **Compartment signs** follow GC content. In most genomes A is GC-rich, but check against
  genes or expression in an unusual genome.
- **TADs are not one thing.** Different callers and windows give different boundaries; strong
  boundaries are found by all of them. Compare samples with the same settings.
- **Assembly errors show up on the map** as off-diagonal blocks or a broken diagonal. A Hi-C
  map is also the standard check of a new assembly's scaffolding.

## References

- Servant N. et al. nf-core/hic. https://doi.org/10.5281/zenodo.2669512
- Ewels P.A. et al. (2020). The nf-core framework for community-curated bioinformatics pipelines. *Nature Biotechnology* 38:276–278. https://doi.org/10.1038/s41587-020-0439-x
- Servant N. et al. (2015). HiC-Pro: an optimized and flexible pipeline for Hi-C data processing. *Genome Biology* 16:259. https://doi.org/10.1186/s13059-015-0831-x
- Abdennur N., Mirny L.A. (2020). Cooler: scalable storage for Hi-C data and other genomically labeled arrays. *Bioinformatics* 36:311–316. https://doi.org/10.1093/bioinformatics/btz540
- Open2C et al. (2024). Cooltools: enabling high-resolution Hi-C analysis in Python. *PLoS Computational Biology* 20:e1012067. https://doi.org/10.1371/journal.pcbi.1012067
- Imakaev M. et al. (2012). Iterative correction of Hi-C data reveals hallmarks of chromosome organization. *Nature Methods* 9:999–1003. https://doi.org/10.1038/nmeth.2148
- Lieberman-Aiden E. et al. (2009). Comprehensive mapping of long-range interactions reveals folding principles of the human genome. *Science* 326:289–293. https://doi.org/10.1126/science.1181369
- Crane E. et al. (2015). Condensin-driven remodelling of X chromosome topology during dosage compensation. *Nature* 523:240–244. https://doi.org/10.1038/nature14450
- Ramírez F. et al. (2018). High-resolution TADs reveal DNA sequences underlying genome organization in flies. *Nature Communications* 9:189. https://doi.org/10.1038/s41467-017-02525-w
