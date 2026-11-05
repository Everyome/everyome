**What it shows.** Every predicted ORF, with its gene, class, length in amino acids and position.

- Filter by class to see, for example, every **uORF**, or type a gene name to see all ORFs on one gene.
- Each ORF was called because its footprints follow its own reading frame, not just because reads cover it.
- The pipeline's ORF catalogue (`orf_predictions/catalogue`) says which callers found each ORF; the exported
  `orfs.csv` keeps those columns.
