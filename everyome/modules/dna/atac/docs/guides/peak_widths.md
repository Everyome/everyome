**What it shows.** How wide the consensus peaks are.

- ATAC-seq open sites are mostly a few hundred bases: the gap between nucleosomes where a factor binds, plus the reads
  around it. Most peaks should be 200–1,000 bp.
- Many very wide peaks (several kb) can mean peaks merged across neighbouring sites, broad-peak mode, or regions of
  artefactual signal (repeats, unplaced contigs). A blacklist removes the worst of these.
