# Cell types in spots (cell2location)

A 10x Visium spot is 55 µm across and usually covers several cells, often of
different types. This module estimates which cell types make up each spot, and
how many cells of each, by comparing the spots with a single-cell reference in
which cell types are already named. It uses cell2location (Kleshchevnikov et al.,
2022) on the cluster's GPUs, then a live session shows the cell types on the
tissue.

## What you need

- **Space Ranger output** for each section: its `outs` folder (as for the Visium
  module).
- **A single-cell reference** as an `.h5ad` file: single-cell or single-nucleus
  RNA-seq of the same tissue, with **raw counts** and each cell's type in a column
  of the cell table (for example `cell_type`). An export from Everyome's
  Single-cell RNA-seq or SPLiT-seq modules works, if it kept raw counts. Use the
  same kind of gene names (symbols or IDs) as Space Ranger.
- **On the cluster**: a GPU (the *GPU partition* setting), and cell2location
  installed in Everyome's Python there. No maintained container image exists, so
  IT installs it once with `pip install "everyome[deconvolution]"` in the shared
  Everyome environment (it brings PyTorch, scvi-tools and Pyro; a few GB).

## Settings that matter

- **Cell type column** (and **Batch column**, if the reference pools samples).
- **Expected cells per spot**: about how many nuclei sit under one spot. Count a
  few spots on the H&E image. The authors suggest 30 for many tissues; sparse
  tissue may have 5–10. It guides the estimates rather than fixing them.
- **Detection alpha**: how much sensitivity may vary between spots. 20 suits most
  data; 200 when sensitivity is very even.
- **Training rounds** (advanced): 250 for the reference and 30,000 for the
  mapping, as the authors suggest. Check on the training curves that both have
  flattened.

## The run

Two stages, each on one GPU:

1. **Learn each cell type's expression** from the reference (cell2location's
   regression model, after the authors' gene filter). Writes
   `results/reference/signatures.csv`.
2. **Map cell types to spots**, all sections together, each as its own batch.
   Writes `results/cell2location/abundance_mean.csv` and `abundance_q05.csv`
   (cells of each type per spot) and `spots.h5ad` (everything cell2location
   estimated).

## Live session

1. **Check the mapping.** Both training curves (they should flatten), cells per
   spot against what you expected, and each cell type's total cells and the
   number of spots where it is the main type, per section.
2. **Cell types on the tissue.** Colour the spots by one cell type, by the main
   type, or by all cells; show the mean estimate, the cautious estimate (5%
   quantile) or each type's share of the spot. Choosing a cell type also lists its
   signature genes from the reference.
3. **Which cell types live together.** Correlation between cell types across
   spots: types that rise and fall together share a place in the tissue.
4. **Export.** Abundance tables, shares, the main type of each spot and the
   correlations, in `results/final/`.

## Good to know

- A cell type missing from the reference can't be found; its cells are shared
  out among the most similar types that are there. If a region of the tissue is
  poorly explained, check the reference covers it.
- Very similar cell types (for example two fibroblast states) are hard to tell
  apart within a spot. Their sum is more reliable than either alone.
- Use the cautious estimate (5% quantile) when you need to be sure a cell type is
  really present in a spot.
