**What it shows.** How far each consensus peak's centre is from the nearest gene's transcription start site (TSS), in
the run's GTF.

- Promoters (within about 1 kb of a TSS) are open in most cells, so a good ATAC-seq library has a large share of
  peaks there, often 20–50%. A very low share suggests a noisy library or a GTF that doesn't match the genome.
- Peaks far from any gene are often enhancers. The nearest gene is a guess for which gene a distal peak controls.
