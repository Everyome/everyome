**What it does.** Keeps a variant when enough of the chosen callers called it, in at least one sample, with a call that
passes every threshold.

- **QUAL**: confidence that the variant exists. **Depth**: reads in that sample. **GQ**: confidence in the genotype
  (one copy or two), also on a log scale.
- **Called by at least**: 2 of 2 callers is strict and clean; 1 keeps everything either caller found.
- **Ti/Tv** after filtering should move towards 2 (for SNVs in most animals): a sign the filters removed mostly errors.
- Each sample's genotype comes from the first chosen caller that called it and passed; **?** means a caller called it
  there but the call failed the filters (too few reads, low confidence).
