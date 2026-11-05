**What it shows.** For each sample, how many variants one caller found, and how many several callers found.

- Callers work differently (GATK HaplotypeCaller reassembles reads; DeepVariant reads them as images with a neural
  network), so they make **different mistakes**. A variant both find is very likely real.
- Variants only one caller finds are a mix of real variants in hard places (repeats, low depth) and false calls.
  Requiring agreement in the next step removes most false calls at the cost of a few real ones.
