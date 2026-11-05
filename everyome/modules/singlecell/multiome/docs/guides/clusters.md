**What it shows.** Each cell placed by similarity, coloured by cluster or any label. **Cluster on** chooses the
measurement:

- **RNA and ATAC together** (weighted nearest neighbours): each cell leans on whichever measurement separates it from
  its neighbours best. Colour by **rna_weight** to see it: near 1, the RNA decided; near 0, the chromatin did. Types
  that differ only in chromatin (or only in RNA) still separate.
- **RNA only** or **ATAC only**: compare with the joint result to see what each measurement alone can tell apart.
- **Correct by batch, not by condition.** If each batch is also one condition, correcting by it removes the effect you
  want to find.
