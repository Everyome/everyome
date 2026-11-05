**What it shows.** Which variant files the pipeline wrote, the mean read depth of each sample, and the full quality report.

- **Depth** matters most: about 15× or more gives confident genotypes; 30× is typical for whole genomes. A sample far
  below the others will have fewer calls and more uncertain genotypes.
- The **MultiQC report** has every check: read quality, mapping rate, duplicates, coverage and variant statistics.
  Look first at the mapping rate (usually above 90% against the right genome) and at any sample flagged in red.
