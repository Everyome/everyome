**What it shows.** Genes ordered by how significant their change in translational efficiency is.

- **TE log2FC** is the change in footprints per mRNA: 1 means twice as efficiently translated, −1 half.
- **Adj. P** is adjusted for testing thousands of genes (Benjamini–Hochberg). Below the threshold you chose, the change
  is unlikely to be chance alone.
- The test compares log2 TE (footprints over mRNA within each pair) between conditions with a moderated t-test, which
  borrows strength across genes when there are few replicates.
