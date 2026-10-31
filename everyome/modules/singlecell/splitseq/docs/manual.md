# SPLiT-seq (SPLiTscape)

Takes SPLiT-seq sublibraries from raw reads to annotated cell types. Use it on
your data alone, for example to build the first atlas for your organism or a
standalone dataset, or merge in an existing atlas or dataset if you have one.
Merging is optional and never needed to carry on. Created by **Helen R Horkan
PhD** (Stowers Institute) as SPLiTscape. If you use it, adapt its code, or reuse
its text or figures, please cite SPLiTscape.

## What you need

- **Paired reads** named `<sublibrary>_<run>_R1.fq.gz` and `_R2.fq.gz`, every
  sublibrary sequenced in the same runs.
- **A genome FASTA and a STAR index** for your organism.
- **The Split-seq toolbox** (`Split-seq_pipeline.sh`) and **pairfq_lite**. Neither is on conda; ask IT for the shared copies.
- Optionally, **an atlas or other dataset to merge in**, in 10x format (`matrix.mtx.gz`, `features.tsv.gz`, `barcodes.tsv.gz`). Leave it out to analyse your data on its own.
- Optionally, **a DIAMOND-style annotation table** that gives genes readable names.
- If samples share a sublibrary, **a round-1 barcode sheet** (Excel: well barcode, value).

## Part 1 · Reads to count matrix (cluster jobs)

1. **Check raw read quality**: FastQC on every raw file.
2. **Trim adapters and fix R2 length**: cutadapt removes adapters, drops short reads and truncates R2 so the barcode anchor sits at a fixed position.
3. **Keep R2 reads in the right register**: keeps reads whose anchor matches the *Dephasing pattern*.
4. **Restore read pairs**: pairfq puts R1 and R2 back in step after R2 filtering.
5. **Package pairs as unaligned BAM**: Picard FastqToSam, and counts read pairs per run.
6. **Extract barcodes, align and tag**: the Split-seq toolbox and STAR. Needs the most memory (64G by default).
7. **Merge runs and see where reads land**: one BAM per sublibrary, plus the share of reads in coding, UTR, intronic and intergenic regions.
8. **Count molecules per gene per cell**: one count matrix per sublibrary; barcodes with fewer genes than *Minimum genes per cell* are not counted as cells.

When all eight finish, the Run page shows **quality checks**:

| Check | What to look for |
|---|---|
| Read pairs per run | Runs of the same sublibrary should scale with sequencing depth. |
| Where reads land | Coding plus UTR is the usable mRNA signal; sublibraries should look alike. |
| Cells and saturation | Reads per UMI above about 10 means more sequencing adds few new molecules. |
| Knee plot | Real cells form the plateau on the left; the drop marks where background begins. |

## Part 2 · Matrix to cell types (live session)

1. **Combine and label.** Combines your sublibraries. If you gave an atlas or other dataset, you can tick a box to merge it in on shared genes; leave it unticked to work with your data alone. Then you describe each library (batch, condition, any other column). Use `from_barcodes` when samples share a sublibrary and are told apart by their round-1 well, and upload the barcode sheet.
2. **Filter cells.** Lower thresholds remove near-empty barcodes; upper thresholds remove likely doublets. The page shows how many cells each sample keeps as you move them.
3. **Integrate and cluster.** Normalises, finds variable genes, corrects batches with Harmony, builds a neighbour graph, draws a UMAP and finds Leiden clusters. *Batch mixing* near 100% means batches are interleaved; check that cell types still separate when you colour by batch.
4. **Explore markers.** The genes that set each cluster apart, with readable names from the annotation table, and a dot plot of the top markers.
5. **Name clusters.** Give each cluster a cell-type name and colour. Clusters with the same name count as one type.
6. **Compare and export.** Cell-type proportions by group, and an export of the annotated data, composition tables, a marker workbook and a UMAP figure.

Every choice you make in the session is saved after each step and recorded in
order, so a new session picks up where you left off.

## Settings

| Setting | Default | What it changes |
|---|---|---|
| R1 adapter | AGATCGGAAGAG | TruSeq adapter trimmed from the cDNA read. |
| Shortest R1 kept | 60 | Shorter reads are dropped after trimming. |
| R2 adapter | CTGTCTCTTATA | Nextera / Tn5 adapter trimmed from the barcode read. |
| Shortest R2 kept | 94 | Must cover the UMI and all barcode rounds. |
| R2 length after trimming | 100 | Fixes the anchor's distance from the read end. |
| Dephasing pattern | ATTCG..............$ | Anchor plus the exact number of bases to the read end. |
| Expected cells | 25000 | Passed to the Split-seq toolbox. |
| Minimum genes per cell | 50 | Barcodes below this are not counted as cells. |
| Extra regions to count | INTRONIC | Count intronic reads as well as coding and UTR. |
| Preferred species for gene names | (empty) | When a gene has several matches, prefer one naming this species. |
| Preferred species for NCBI names | (empty) | The same, for NCBI names. |

Jobs use the CPUs you set under *Cluster resources* (8 by default); the stages
use that many threads.

## Building a first atlas

With no atlas to merge, your own sublibraries become the reference: filter,
cluster and name cell types as usual, then export. The exported
`annotated.h5ad` can be merged into later experiments as their atlas.

## Try it on toy data

The **Playground** (under *Learn*) runs simplified filtering, clustering,
markers and composition on a toy dataset in your browser, with scenarios that
show what each setting does.

## Things to watch

- **Library IDs** must look like `lib_01_1`; they become part of every cell's name.
- **Proportions are descriptive.** Testing a difference between conditions needs biological replicates and a compositional method.
- **Small groups** (fewer than 50 cells) give unstable proportions.

## References

- Rosenberg A.B. et al. (2018). Single-cell profiling of the developing mouse brain and spinal cord with split-pool barcoding. *Science* 360:176–182. https://doi.org/10.1126/science.aam8999
- Wolf F.A., Angerer P., Theis F.J. (2018). SCANPY: large-scale single-cell gene expression data analysis. *Genome Biology* 19:15. https://doi.org/10.1186/s13059-017-1382-0
- Korsunsky I. et al. (2019). Fast, sensitive and accurate integration of single-cell data with Harmony. *Nature Methods* 16:1289–1296. https://doi.org/10.1038/s41592-019-0619-0
- Traag V.A., Waltman L., van Eck N.J. (2019). From Louvain to Leiden: guaranteeing well-connected communities. *Scientific Reports* 9:5233. https://doi.org/10.1038/s41598-019-41695-z
