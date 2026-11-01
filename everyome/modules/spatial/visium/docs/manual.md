# Spatial transcriptomics (10x Visium)

Explores 10x Genomics Visium sections: gene expression measured in spots laid out
across a tissue section, each spot in its place on the tissue image. Starts from
the output of 10x's Space Ranger, which your sequencing facility usually runs (or
you run on the cluster), so this module needs no pipeline: everything happens in
a live session.

## What you need

- **Space Ranger output** for each section: its `outs` folder, containing
  `filtered_feature_bc_matrix.h5` (or the `filtered_feature_bc_matrix/` folder)
  and `spatial/` (tissue positions, scale factors and the tissue images).
- **Visium HD**: point the table at a binned folder, for example
  `binned_outputs/square_016um`, which has the same layout. 16 µm bins are a good
  start; 8 µm bins are many more and need more memory.
- A Python environment on the cluster with the single-cell packages (the same as
  the other single-cell modules).

## Sections

One row per section: its name, its `outs` folder, its **condition** (what you will
compare) and, if sections were prepared on different days or slides, its
**batch**. *Find sections in the folder* looks through the folder you choose for
Space Ranger outputs and names each section after its folder.

## Live session

1. **Load the sections.** Spots under the tissue, their counts and the tissue
   image; a thumbnail of each section coloured by UMIs per spot.
2. **Filter spots.** Thresholds on molecules (UMIs) and genes per spot remove
   spots with too little RNA (often at folds or tears), and a threshold on the
   **mitochondrial share** removes damaged tissue. *Mitochondrial genes* (a
   setting) says which genes count: `MT-` for human, `mt-` for mouse.
3. **Find tissue regions.** Spots are normalised, corrected for batch (Harmony,
   by the column you choose, for example the section) and clustered (Leiden), as
   for single cells.
4. **See it on the tissue.** Any cluster, gene or quality measure on the tissue
   image, and the **spatially variable genes**: genes whose expression is similar
   in neighbouring spots, ranked by Moran's I.
5. **Explore markers.** The genes that set each cluster of spots apart.
6. **Name regions.** Give each cluster a region name and colour.
7. **Compare and export.** Region proportions by condition (or any label), and
   the annotated data (`annotated.h5ad`, with spot positions in `obsm["spatial"]`),
   tables, a marker workbook and a figure in `results/`.

## Things to watch

- **A spot is not a cell.** Visium spots are 55 µm across and usually hold
  several cells, so each spot's expression is a mixture. Clusters are tissue
  regions (niches), not cell types; to estimate cell types within spots, use a
  single-cell reference and a deconvolution method.
- **Quality follows the tissue.** Folds, tears, edges and uneven
  permeabilisation change UMIs per spot. Check *UMIs per spot* on the tissue
  before reading a cluster as biology.
- **Sections are the replicates.** Comparing conditions needs several sections
  (ideally from different animals or patients) per condition; spots within one
  section are not independent.

## References

- Ståhl P.L. et al. (2016). Visualization and analysis of gene expression in tissue sections by spatial transcriptomics. *Science* 353:78–82. https://doi.org/10.1126/science.aaf2403
- Wolf F.A., Angerer P., Theis F.J. (2018). SCANPY: large-scale single-cell gene expression data analysis. *Genome Biology* 19:15. https://doi.org/10.1186/s13059-017-1382-0
- Korsunsky I. et al. (2019). Fast, sensitive and accurate integration of single-cell data with Harmony. *Nature Methods* 16:1289–1296. https://doi.org/10.1038/s41592-019-0619-0
- Traag V.A., Waltman L., van Eck N.J. (2019). From Louvain to Leiden: guaranteeing well-connected communities. *Scientific Reports* 9:5233. https://doi.org/10.1038/s41598-019-41695-z
- Moran P.A.P. (1950). Notes on continuous stochastic phenomena. *Biometrika* 37:17–23. https://doi.org/10.1093/biomet/37.1-2.17
- Palla G. et al. (2022). Squidpy: a scalable framework for spatial omics analysis. *Nature Methods* 19:171–178. https://doi.org/10.1038/s41592-021-01358-2
