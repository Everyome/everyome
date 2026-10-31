# Bulk RNA-seq differential expression

Finds genes whose expression changes between conditions, for example control
and treated. Two parts:

1. **On the cluster:** nf-core/rnaseq (release 3.27.0) turns your reads into gene
   counts, with a full quality report (MultiQC).
2. **In a live session:** check the samples, compare conditions with DESeq2,
   explore the results and export them.

## What you need

- **Paired or single-end reads** (`.fastq.gz`), one or more files per sample.
- **A reference genome:** either an iGenomes name (*Genome*), or your own FASTA
  (*Fasta*) and annotation (*Gtf* or *Gff*). Set these under *Reference genome options*.
- **At least two samples per condition**; three or more is much better.
- On the cluster: **Nextflow**, **Java** and **Apptainer** (ask IT). The pipeline
  downloads its software as containers the first time it runs.

## Samples table

One row per sample: its name, read 1 and read 2 files (leave read 2 empty for
single-end), strandedness (`auto` lets the pipeline work it out) and its
**condition**. *Find samples in the reads folder* fills the table from file
names and guesses each condition from the name (`control_1` → `control`).
Check the conditions: they decide what is compared.

## Pipeline settings

Every setting nf-core/rnaseq accepts is on the settings page, in the pipeline's
own groups, with its default and description. Settings the pipeline treats as
specialist are under *Advanced*. Only settings you change are passed to the
pipeline. Common ones:

| Setting | What it changes |
|---|---|
| Aligner | `star_salmon` (default) aligns with STAR and counts with Salmon; `star_rsem`, `hisat2` and `bowtie2_salmon` are alternatives. |
| Pseudo aligner | Also runs Salmon or kallisto directly on the reads. |
| Trimmer | Trim Galore (default) or fastp. |
| Skip … | Leave out steps you do not need, such as some quality checks. |
| Remove ribosomal RNA | Filters rRNA reads before alignment. |

The pipeline's own tasks are sent to Slurm by Nextflow, each named
`Claude_<you>_everyome_rna_bulk_de_<task>`. Only one job (the pipeline itself)
is submitted when you press Run; it then submits the rest.

## Live session

1. **Check samples.** Reads and detected genes per sample, a principal component
   plot and a sample-correlation heatmap. Replicates should sit close together;
   a sample far from its group may be mislabelled or failed.
2. **Compare conditions.** Choose the condition to test and the reference.
   Genes with fewer than *Minimum total count* reads are removed first, then
   DESeq2 (PyDESeq2) fits each gene and tests the difference.
3. **Explore results.** Volcano and MA plots, a searchable table, and each
   gene's normalised counts per sample.
4. **Export.** All genes, the significant genes, normalised counts and a
   volcano plot, saved in `results/differential_expression/`.

## Reading the results

| Column | Meaning |
|---|---|
| log2 fold change | 1 means twice as much in the tested condition; −1 means half. |
| Adjusted P | Corrected for testing thousands of genes (Benjamini–Hochberg). Below 0.05 is the usual cut-off. |
| Base mean | Average normalised count across samples; very low values give noisy fold changes. |

- **Few replicates** make variance estimates shaky; treat small fold changes with care.
- **A sample far from its replicates** in the PCA can drive false results; check it before comparing.
- **Significant is not the same as large.** Use a fold-change cut-off as well if only big changes matter.

## References

- Patel H. et al. nf-core/rnaseq. https://doi.org/10.5281/zenodo.1400710
- Ewels P.A. et al. (2020). The nf-core framework for community-curated bioinformatics pipelines. *Nature Biotechnology* 38:276–278. https://doi.org/10.1038/s41587-020-0439-x
- Love M.I., Huber W., Anders S. (2014). Moderated estimation of fold change and dispersion for RNA-seq data with DESeq2. *Genome Biology* 15:550. https://doi.org/10.1186/s13059-014-0550-8
- Muzellec B. et al. (2023). PyDESeq2: a python package for bulk RNA-seq differential expression analysis. *Bioinformatics* 39:btad547. https://doi.org/10.1093/bioinformatics/btad547
