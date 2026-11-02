**What it shows.** How consistently the data back each branch (each group on the tree).

- **UFBoot** (ultrafast bootstrap): the share of resampled alignments that contain the group. Trust it from
  **95%**; it runs higher than the ordinary bootstrap.
- **SH-aLRT**: a test of whether the branch fits the data better than its alternatives. Trust it from **80%**.
- A group with both is well supported. Low support does not mean the group is wrong, only that these data
  cannot tell; very short branches often have low support.
- Support says nothing about whether the model or the alignment was right: a well-supported group can still
  be wrong if, for example, two fast-evolving sequences are drawn together (long-branch attraction).
