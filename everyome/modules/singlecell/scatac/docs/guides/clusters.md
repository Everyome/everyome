**What it shows.** Each cell placed by similarity of its open chromatin (UMAP of the spectral embedding), coloured by
cluster or any label.

- Clustering uses the most variable genome tiles, not genes: cell types differ in which regions are open.
- **Resolution** sets how finely cells are split. Check that each cluster has its own markers before trusting it.
- **Correct by batch, not by condition.** If each batch is also one condition, correcting by it removes the effect you
  want to find.
