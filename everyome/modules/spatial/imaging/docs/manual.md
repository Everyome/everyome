# Imaging spatial (Xenium, MERSCOPE, CosMx)

Explores single-cell spatial transcriptomics from imaging platforms, starting from the instrument's own output:
**10x Xenium**, **Vizgen MERSCOPE** or **Bruker (NanoString) CosMx**. Each cell has its transcript counts for the
panel's genes and its position in the tissue.

## What you need

- For each section, the instrument's output folder: Xenium's `outs`, or the MERSCOPE or CosMx export with the
  cell-by-gene and cell metadata tables. *Find sections in the folder* finds them and sets the platform.
- Each section's **condition**, and a **batch** if sections were run on different days or slides.

## Live session

1. **Read the sections.** Counts and positions for every cell; control probes are left out.
2. **Filter cells.** Thresholds on transcripts and genes per cell (much lower than in single-cell RNA-seq).
3. **Integrate and cluster.** As in the single-cell RNA module, with Harmony across batches if asked.
4. **See it on the tissue.** Every cell in place, coloured by cluster, name, gene or quality; and the genes whose
   expression is most similar in neighbouring cells (Moran's I).
5. **Explore markers** and **Name cell types**.
6. **Which cell types are neighbours.** How often each pair of types sit next to each other compared with shuffled
   labels (neighbourhood enrichment, as in Squidpy).
7. **Compare and export.**

## Things to watch

- **Panels are targeted.** Clusters and markers can only use the genes on the panel; a type the panel doesn't cover
  can't appear.
- **Segmentation decides what a cell is.** Merged or split cells look like odd types or doublets; check suspicious
  clusters on the tissue.
- CosMx positions are in pixels; distances are still comparable within a slide.

## References

- Janesick A. et al. (2023). Xenium. *Nature Communications* 14:8353. https://doi.org/10.1038/s41467-023-43458-x
- Chen K.H. et al. (2015). MERFISH. *Science* 348:aaa6090. https://doi.org/10.1126/science.aaa6090
- He S. et al. (2022). CosMx spatial molecular imaging. *Nature Biotechnology* 40:1794–1806. https://doi.org/10.1038/s41587-022-01483-z
- Palla G. et al. (2022). Squidpy. *Nature Methods* 19:171–178. https://doi.org/10.1038/s41592-021-01358-2
