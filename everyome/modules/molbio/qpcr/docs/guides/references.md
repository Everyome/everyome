**What it shows.** geNorm M for each target measured in every sample. M is the average spread of a gene's expression
relative to the others; a gene that changes with your treatment gets a high M.

- geNorm drops the least steady gene, recalculates, and repeats; the last two left are the steadiest pair.
- An M below about 0.5 is good for similar samples; below 1 is acceptable for more varied ones (different tissues,
  time points).
- Use two or three steady references rather than one; Everyome normalises to their geometric mean.
- A gene you study should not be a reference, even if it looks steady here.
