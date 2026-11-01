# Single-cell RNA-seq (10x and similar)

Takes droplet single-cell RNA-seq (10x Genomics Chromium, and similar
chemistries) from reads to named cell types. Two parts:

1. **On the cluster:** nf-core/scrnaseq (release 4.2.0) finds each read's cell
   barcode and molecule (UMI), counts molecules per gene per cell, removes empty
   droplets and background RNA (CellBender), and writes a quality report (MultiQC).
2. **In a live session:** load the cells, filter out damaged cells and doublets,
   correct for batches, cluster, find marker genes, name cell types and compare
   their proportions between conditions. These steps are the same as in the
   SPLiT-seq module.

## What you need

- **Reads** (`.fastq.gz`): read 1 holds the cell barcode and UMI, read 2 the
  cDNA. Index reads (I1, I2) are not needed. Samples sequenced on several lanes
  can be listed once per lane under the same sample name.
- **The chemistry** (*Protocol*): `10XV3` is set to start with; use `10XV2`,
  `10XV4` or `10XV1` for other kits (it is on the kit and in your sequencing
  facility's report). Only Cell Ranger can detect it itself (`auto`).
- **A reference genome:** an iGenomes name (*Genome*), or your own FASTA (*Fasta*)
  and annotation (*Gtf*), under *Reference genome options*.
- On the cluster: **Nextflow**, **Java** and **Apptainer** (ask IT). The pipeline
  itself ships with Everyome (`everyome-pipelines`): pressing Run copies nf-core/scrnaseq
  to your cluster once and checks it; its software containers are downloaded the
  first time they are needed. See `docs/PIPELINES.md`, including for clusters
  without internet access. CellBender runs
  much faster on a GPU; ask IT whether one is available.

## Samples table

One row per sample (or per lane): its name, read 1, read 2, optionally how many
cells you expected, its **condition** (what you will compare) and its **batch**
(for example the day it was prepared). *Find samples in the reads folder* fills
the table from 10x file names (`<sample>_S1_L001_R1_001.fastq.gz`) and guesses
each condition from the name. Check conditions and fill in batches: the live
session corrects for batch and compares by condition.

## Pipeline settings

Every setting nf-core/scrnaseq accepts is on the settings page, in the pipeline's
own groups. Only settings you change are passed to the pipeline. Common ones:

| Setting | What it changes |
|---|---|
| Aligner | `simpleaf` (alevin-fry, default) is fast and light; `star` (STARsolo), `kallisto` and `cellranger` are alternatives. Cell Ranger needs its own reference. |
| Protocol | The 10x chemistry (see above). |
| Skip cellbender | Leave out empty-droplet and background removal (then start from the aligner's matrix). |
| Remove doublets | simpleaf only: removes likely doublets during counting. |
| Barcode whitelist | Only for non-10x chemistries: the list of valid cell barcodes. |

The pipeline's own tasks are sent to Slurm by Nextflow, each named
with your username, `everyome` and the module (`…_<you>_everyome_singlecell_scrna_<task>`),
so you can find them in `squeue`. Only one job (the pipeline
itself) is submitted when you press Run; it then submits the rest.

## Live session

1. **Load the cells.** Choose a matrix (CellBender's, by default). Gene symbols
   replace gene ids, and each cell gets its sample's condition and batch.
   Check the cells per sample.
2. **Filter cells.** Thresholds on molecules (UMIs) and genes per cell remove
   near-empty barcodes and likely doublets; a threshold on the **mitochondrial
   share** removes damaged cells. *Mitochondrial genes* (a setting) says which
   genes count: `MT-` for human, `mt-` for mouse.
3. **Integrate and cluster.** Normalise, find variable genes, correct batches
   with Harmony, build a neighbour graph, draw a UMAP and cluster (Leiden).
4. **Explore markers.** The genes that set each cluster apart, and a dotplot.
5. **Name clusters.** Give each cluster a cell-type name and a colour.
6. **Compare and export.** Cell-type proportions by condition (or any label),
   and the annotated data (`annotated.h5ad`), tables, a marker workbook and a
   UMAP figure in `results/`.

## Things to watch

- **Batch and condition together.** If every treated sample was prepared on one
  day and every control on another, no method can separate the two. Spread
  conditions across batches when you plan the experiment.
- **Proportions are descriptive.** Testing a change in cell-type proportions
  needs several biological replicates per condition and a compositional method.
- **Clusters are not cell types.** Name clusters from several markers together;
  two clusters may be one type, and a small cluster may be doublets.

## References

- Peltzer A. et al. nf-core/scrnaseq. https://doi.org/10.5281/zenodo.3568187
- Ewels P.A. et al. (2020). The nf-core framework for community-curated bioinformatics pipelines. *Nature Biotechnology* 38:276–278. https://doi.org/10.1038/s41587-020-0439-x
- He D. et al. (2022). Alevin-fry unlocks rapid, accurate and memory-frugal quantification of single-cell RNA-seq data. *Nature Methods* 19:316–322. https://doi.org/10.1038/s41592-022-01408-3
- Fleming S.J. et al. (2023). Unsupervised removal of systematic background noise from droplet-based single-cell experiments using CellBender. *Nature Methods* 20:1323–1335. https://doi.org/10.1038/s41592-023-01943-7
- Wolf F.A., Angerer P., Theis F.J. (2018). SCANPY: large-scale single-cell gene expression data analysis. *Genome Biology* 19:15. https://doi.org/10.1186/s13059-017-1382-0
- Korsunsky I. et al. (2019). Fast, sensitive and accurate integration of single-cell data with Harmony. *Nature Methods* 16:1289–1296. https://doi.org/10.1038/s41592-019-0619-0
- Traag V.A., Waltman L., van Eck N.J. (2019). From Louvain to Leiden: guaranteeing well-connected communities. *Scientific Reports* 9:5233. https://doi.org/10.1038/s41598-019-41695-z
- Luecken M.D., Theis F.J. (2019). Current best practices in single-cell RNA-seq analysis: a tutorial. *Molecular Systems Biology* 15:e8746. https://doi.org/10.15252/msb.20188746
