**What it shows.** What nf-core/riboseq counted for each library, the lengths of the ribosome footprints, and the full
quality report.

- **Ribo-seq bars are in-frame P-sites**, so they are smaller than the RNA-seq read counts. Compare libraries of one type.
- **Footprints should be mostly 28–32 nt**, the stretch of mRNA a ribosome protects. A broad spread or a peak below 25 nt
  points to over-digestion or degraded RNA.
- The **MultiQC report** has every check: read quality, trimming, how much was ribosomal RNA (removed), alignment rate.
  Ribo-seq libraries often lose most reads to rRNA; what matters is how many footprints are left.
