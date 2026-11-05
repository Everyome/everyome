**What it shows.** The most variable genes (after leaving out genes that never reach the minimum TPM), each scaled to
its own average (a z-score: 0 is the gene's average, +2 is two standard deviations above it), then grouped by k-means
into clusters of genes that rise and fall together across the samples.

- Each row of the heatmap is a gene, each column a sample. The key under the heatmap shows which colour is above the
  gene's average and which below; the strip on the left shows each gene's cluster.
- Clusters are a summary, not a test. k-means always returns the number of clusters you ask for; try a few values and
  keep the one where clusters look distinct.
- Genes clustered together are co-expressed in these samples. That suggests, but does not show, shared regulation or
  function.
