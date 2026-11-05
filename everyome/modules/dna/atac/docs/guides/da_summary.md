**What it shows.** How many consensus peaks have more (or fewer) reads in the test group than the reference, at the
adjusted P you chose.

- **More open** means more reads in the test group: the chromatin there is more accessible. **Less open** means fewer.
- DESeq2 estimates each peak's variation from the replicates, so with two or three replicates per group only clear,
  consistent changes are found.
- The adjusted P controls the share of false calls among the peaks reported (for example 5% at 0.05), not the chance
  that any one peak is wrong.
