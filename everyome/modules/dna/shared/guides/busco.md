**What it shows.** BUSCO looks for genes expected in a single copy in every genome of a lineage (for example all eukaryotes or all bacteria), and reports how many it finds.

- **Complete** above about 95% is good for most genomes. **Fragmented** genes are found only in part, often because read errors break them: polishing usually helps. **Missing** genes may be truly absent, or sit in sequence the assembly lost.
- A high share of **duplicated** complete genes (in the pipeline's report) can mean both haplotypes were kept, or contamination with a related organism.
- Use the most specific lineage that fits your organism; a broad one has fewer genes and says less.
