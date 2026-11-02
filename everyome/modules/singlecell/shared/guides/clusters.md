**What it shows.** Each cell placed by similarity (UMAP), coloured by cluster or any label.

- **Resolution** sets how finely cells are split. More clusters is not more biology: check that each has its own markers.
- **Batch mixing** near 100% means batches interleave. Colour by batch: cell types should still separate, but not by batch.
- Distances between far-apart islands on a UMAP mean little; nearby structure is more trustworthy.
- **Correct by batch, not by condition.** Batch correction removes differences between the groups you name. If each
  batch (or sample, or section) is also one condition, correcting by it removes the very effect you want to find, such
  as a cell type or region present only in treated samples. Correct only by a column that cuts across conditions.
