# Single-cell ATAC-seq

Finds cell types from open chromatin, one cell at a time. Two parts:

1. **On the cluster:** chromap aligns each sample's reads to your genome, corrects the cell barcodes, removes PCR
   duplicates and writes one **fragment** per read pair (a piece of DNA the Tn5 enzyme cut out of open chromatin).
   Already have fragments (for example `atac_fragments.tsv.gz` from Cell Ranger ATAC)? Give those and this step only
   copies them.
2. **In a live session:** SnapATAC2 reads the fragments; you remove poor cells, cluster cells on their open chromatin,
   find marker genes from gene activity, name the clusters and compare conditions.

Works with any genome you have as FASTA and GTF; nothing is tied to human or mouse.

## What you need

- **Reads** for each sample: read 1, read 2 and the read holding the cell barcode. For 10x Genomics ATAC kits the files
  are `_R1_`, `_R3_` (the two genomic reads) and `_R2_` (the 16-base barcode); *Find samples in the reads folder* sets
  them that way. Or a **fragments file** per sample instead.
- **The genome** (FASTA) and its **gene annotation** (GTF or GFF3), with matching chromosome names.
- Optional: your kit's **barcode whitelist** (for 10x ATAC, `737K-cratac-v1.txt`). Without it, barcodes are taken as
  read, so more junk barcodes appear; they fall below the thresholds in the filtering step.
- On the cluster: **Apptainer**. chromap runs in a container pinned by its digest, pulled once into the shared
  pipelines folder.

## Live session

1. **Read the fragments.** Barcodes with enough fragments become cells; each gets its fragment count, TSS enrichment
   and fragment sizes. The fragment size ladder is a quick check of each library.
2. **Filter cells.** Thresholds on fragments and TSS enrichment, with the distributions and how many cells each sample
   keeps.
3. **Integrate and cluster.** The most variable genome tiles, a spectral embedding, Harmony across batches if asked,
   Leiden clusters and a UMAP.
4. **Explore markers**, **Name clusters**, **Compare and export**: as in the other single-cell modules, on gene
   activity scores.

## Things to watch

- **TSS enrichment** is the best single quality measure: below about 4, most of a cell's fragments are background.
- **Gene activity is indirect.** Open chromatin over a gene suggests, but does not prove, that it is expressed.
- Peaks (called per cluster with MACS) are not part of this first version; the tile matrix stands in for them.

## References

- Zhang K. et al. (2024). SnapATAC2. *Nature Methods* 21:217–227. https://doi.org/10.1038/s41592-023-02139-9
- Zhang H. et al. (2021). Chromap. *Nature Communications* 12:6566. https://doi.org/10.1038/s41467-021-26865-w
- Buenrostro J.D. et al. (2015). Single-cell chromatin accessibility. *Nature* 523:486–490. https://doi.org/10.1038/nature14590
