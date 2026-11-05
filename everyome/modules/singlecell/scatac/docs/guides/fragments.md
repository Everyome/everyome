**What happens.** Every barcode with at least this many fragments becomes a cell. For each, SnapATAC2 counts
fragments, works out **TSS enrichment** (how much more signal sits at gene starts than 2 kb away) and the lengths of
its fragments. Two tables are kept: open chromatin in tiles across the genome (for clustering) and **gene activity**,
fragments over each gene and 2 kb upstream (for markers).

- Keep this first cut loose: the next step sets the real thresholds while you watch the distributions.
- Larger tiles give fewer, fuller features; 500 bp suits most data.
