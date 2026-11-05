# High-resolution spatial (Visium HD, Stereo-seq, Curio)

Explores sequencing-based spatial transcriptomics at near-single-cell resolution, starting from each platform's own
output: **10x Visium HD** (Space Ranger), **STOmics Stereo-seq** (a GEM file) or **Curio Seeker** (an `.h5ad` of
beads). Each bin (or bead) has its whole-transcriptome counts and its position.

## What you need

- For each section: Space Ranger's **`outs`** for Visium HD (with `binned_outputs`), or the folder holding the
  Stereo-seq **GEM** file or the Curio **.h5ad**. *Find sections in the folder* finds them and sets the platform.
- Each section's **condition**, and a **batch** if sections were run on different days.
- A **bin size**: 8 µm (about one cell) is the usual start; 16 µm for more RNA per bin; 2 µm for fine structure.

## Live session

1. **Read the sections** at the chosen bin size.
2. **Filter bins** on UMIs, genes and the mitochondrial share.
3. **Integrate and cluster**, with Harmony across batches if asked.
4. **See it on the tissue**: bins in place, over the image for Visium HD, with spatially variable genes (Moran's I).
5. **Explore markers** and **Name clusters**.
6. **Which types are neighbours**: neighbourhood enrichment, as in the imaging module.
7. **Compare and export.**

## Things to watch

- **A bin is not a cell.** At 8 µm most bins hold one cell, but some split a cell and some catch two. Segmenting
  cells from Visium HD (for example with nuclei from the image) is not part of this first version.
- Sessions on whole Visium HD slides at 8 µm can need a lot of memory (the session asks for 64 GB).

## References

- Oliveira M.F. et al. (2025). Visium HD. *Nature Genetics* 57:1512–1523. https://doi.org/10.1038/s41588-025-02193-3
- Chen A. et al. (2022). Stereo-seq. *Cell* 185:1777–1792. https://doi.org/10.1016/j.cell.2022.04.003
- Rodriques S.G. et al. (2019). Slide-seq. *Science* 363:1463–1467. https://doi.org/10.1126/science.aaw1219
