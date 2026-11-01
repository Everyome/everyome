**What it shows.** Every assembly in the run, with the numbers used to judge assemblies.

- **Size** should be close to the genome size you expect (from flow cytometry, k-mers or a relative). Much larger can mean both haplotypes were kept, or contamination; much smaller, missing sequence.
- **Contigs** and **N50**: fewer, longer contigs are better. N50 is the length such that half the assembly is in contigs at least that long; **L50** is how many contigs that takes.
- **Gaps (N)** are unknown bases, usually added when contigs are joined into scaffolds.
- Judge contiguity and completeness together: a very contiguous assembly that misses genes is not better.
