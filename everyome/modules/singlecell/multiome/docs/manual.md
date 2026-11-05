# Multiome (RNA and ATAC together)

Explores 10x Multiome experiments, where every nucleus has both its RNA and its open chromatin measured. Starts from
the output of **Cell Ranger ARC** (which you run, or your sequencing core runs; it is 10x's software and is not
included with Everyome).

## What you need

- For each sample, Cell Ranger ARC's **`outs`** folder, with `filtered_feature_bc_matrix` (a folder or `.h5` file)
  holding genes and peaks together. *Find samples in the folder* finds them.
- Each sample's **condition**, and a **batch** if samples were prepared on different days.

## Live session

1. **Read the matrices.** Genes and peaks for every cell; cells with too little ATAC signal are left out.
2. **Filter cells** on the RNA: UMIs, genes and the mitochondrial share, as in the single-cell RNA module.
3. **Integrate and cluster.** Choose to cluster on **RNA and ATAC together** (weighted nearest neighbours, as in
   Seurat's WNN, here from muon), on RNA only or on ATAC only. RNA: normalised, variable genes, PCA. ATAC: TF-IDF and
   LSI. Harmony corrects batches in each, if asked. Then Leiden clusters and a UMAP.
4. **Explore markers**, **Name clusters**, **Compare and export**: as in the other single-cell modules, on the RNA.

## Things to watch

- Try all three clustering choices. If ATAC only separates two populations that RNA only merges, they differ in their
  chromatin; the joint result should keep them apart.
- **rna_weight** (a colour option after joint clustering) shows which measurement each cell leaned on.
- Peak-level results (which regions open in each cluster, linked to nearby genes) are not part of this first
  version; export the annotated cells and peaks to go further.

## References

- Bredikhin D., Kats I., Stegle O. (2022). MUON. *Genome Biology* 23:42. https://doi.org/10.1186/s13059-021-02577-8
- Hao Y. et al. (2021). Integrated analysis of multimodal single-cell data (WNN). *Cell* 184:3573–3587. https://doi.org/10.1016/j.cell.2021.04.048
- Cusanovich D.A. et al. (2015). TF-IDF and LSI for single-cell ATAC. *Science* 348:910–914. https://doi.org/10.1126/science.aab1601
