**What happens.** For each section, Everyome reads the cell-by-gene counts and each cell's centre from the
instrument's output, and leaves out control probes (negative controls, blank codewords), which measure background.

- **Xenium**: `cell_feature_matrix` and `cells.parquet` (or `cells.csv.gz`) in the `outs` folder; positions in µm.
- **MERSCOPE**: `cell_by_gene.csv` and `cell_metadata.csv`; positions in µm.
- **CosMx**: the `exprMat_file` and `metadata_file` tables; positions in pixels across the whole slide.
- Cells come from the instrument's own segmentation. If cells look merged or split, re-segmenting (outside Everyome)
  is the fix; filtering only removes the worst.
