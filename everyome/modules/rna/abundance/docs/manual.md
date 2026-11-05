# RNA abundance

Shows how much each gene is expressed across your samples, from the gene tables
nf-core/rnaseq writes. Use it to check samples, look up genes of interest, see
which genes dominate each tissue or stage, and find groups of genes that rise and
fall together across samples.

This module does **not** test whether a gene differs between two conditions. For
that, use **Differential expression (bulk RNA-seq)**, which runs DESeq2 with
replicates.

## What you need

- **The results folder of an nf-core/rnaseq run.** It has a folder such as
  `star_salmon`, `salmon` or `star_rsem` inside, with `*.merged.gene_tpm.tsv` and
  `*.merged.gene_counts.tsv`. A run of Everyome's Differential expression module
  has one: its `results` folder.
- On the cluster: nothing beyond Everyome. The live session runs on a compute
  node (one CPU, 8 GB).

## Samples table

*Read samples from the results* lists the samples in the pipeline's TPM table and
guesses a **group** from each name (`oral_2` → `oral`). Groups only colour the
charts and label the averages; correct them, or delete rows to leave samples out.

## Live session

1. **Check samples.** Genes detected and the top ten genes' share for each
   sample; principal components of the most variable genes; correlation between
   samples. Samples are compared on counts normalised for library size (DESeq2's
   median-of-ratios size factors), log-scaled.
2. **Look up genes.** Any gene's TPM in every sample, and the most expressed
   genes with their mean in each group.
3. **Find patterns.** The most variable genes, scaled to z-scores and grouped by
   k-means into clusters of co-expressed genes, shown as a heatmap and each
   cluster's average pattern. The clustering uses a fixed seed, so the same
   settings give the same clusters.
4. **Export.** `tpm.csv`, `normalised_log2.csv`, `samples.csv` and
   `gene_clusters.csv` in the run's results folder.

## Things to watch

- **TPM is a share.** If a few genes take a much larger share in one sample (for
  example mitochondrial transcripts), every other gene's TPM is lower there
  although nothing about it changed. The playground shows this.
- **Patterns are not tests.** Clusters describe these samples; with few
  replicates, some genes land in a cluster by chance.
- **Batch effects** (days, lanes, extraction kits) show in the sample checks
  first. If samples group by batch, keep that in mind for every later chart.

## References

- Patel H. et al. nf-core/rnaseq. https://doi.org/10.5281/zenodo.1400710
- Love M.I., Huber W., Anders S. (2014). DESeq2. *Genome Biology* 15:550. https://doi.org/10.1186/s13059-014-0550-8
- Wagner G.P., Kin K., Lynch V.J. (2012). Measurement of mRNA abundance using RNA-seq data. *Theory in Biosciences* 131:281–285. https://doi.org/10.1007/s12064-012-0162-3
