**What it shows.** How many peaks nf-core/atacseq called in each library, the fraction of each library's reads that
fall in its peaks (FRiP), and the full quality report.

- Replicates should have broadly similar peak numbers. A library with far fewer peaks may be under-sequenced or noisy.
- The **MultiQC report** has every check. For ATAC-seq look first at the **fragment-size plot**: a good library shows a
  peak below 100 bp (open DNA between nucleosomes) and smaller peaks near 200 and 400 bp (one and two nucleosomes).
  Also check the duplication rate and the share of mitochondrial reads.
