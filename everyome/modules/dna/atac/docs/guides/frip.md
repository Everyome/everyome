**What it shows.** For each library: peaks called, the fraction of reads in peaks (**FRiP**), the median peak width and
the reads counted in the consensus peaks.

- **FRiP** is the signal-to-noise of the library. ENCODE asks for at least 20%, ideally 30% or more. Below 20% (marked low) the
  library has a lot of background: fewer peaks are found and weak sites are missed.
- One low library among good replicates can still be used, but check that it sits with its group in the principal
  components; if it doesn't, consider leaving it out of the comparison.
