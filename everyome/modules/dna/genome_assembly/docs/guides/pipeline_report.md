**What it shows.** The assemblies nf-core/genomeassembler wrote for each row of your table, and its report.

- Each row can produce several assemblies: the first assembly, then polished or scaffolded versions. The live session compares all of them.
- The report collects QUAST (size, contigs, N50), BUSCO (completeness) and, with Illumina reads, Merqury (accuracy, as a QV: 40 means one error in 10,000 bases).
