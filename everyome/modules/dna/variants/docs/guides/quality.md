**What it shows.** How confident the callers are (QUAL) and how many reads cover each call.

- **QUAL** is the caller's confidence that a variant is there at all, on a log scale (30 means about 1 in 1,000 that it
  is wrong). True variants at good depth mostly score well above 30; a pile of calls near 0–20 is mostly noise.
- **Depth** is the reads covering the call in that sample. Below about 10 reads, a one-copy variant is easily missed or
  mistaken for two copies.
- These shapes suggest where to put the filters in the next step.
