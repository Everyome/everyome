# Translation (Ribo-seq)

Measures translation from ribosome profiling (Ribo-seq): sequencing the short
stretches of mRNA that ribosomes protect from nuclease. With matched RNA-seq
from the same samples, it separates changes in translation from changes in
mRNA. Everyome runs **nf-core/riboseq** 2.0.0 on the cluster, then a live
session checks the data, shows the translated open reading frames (ORFs) and
compares translational efficiency between conditions.

## What you need

- **Ribo-seq FASTQ files** (usually single-end), and for translational
  efficiency, **RNA-seq from the same biological samples** (one RNA-seq library
  per Ribo-seq library). TI-seq libraries (harringtonine or lactimidomycin, which
  stop ribosomes at start codons) can be added; they help the ORF callers find
  start codons.
- **A genome FASTA and a GTF annotation** (Ensembl or GENCODE style). Footprints
  are counted on annotated coding sequences, so the annotation matters.
- On the cluster: Nextflow 25.10.4 or newer, Apptainer, and the
  `everyome-pipelines` package (see the installation guide). The pipeline's
  head job runs for up to four days and sends its tasks to Slurm.

## Samples table

*Find samples in the reads folder* reads names like
`control_1_ribo_R1.fastq.gz` and `control_1_rna_R1.fastq.gz` and guesses:

- **Type**: `riboseq` if the name has *ribo*, *rpf* or *fp*; `tiseq` for *tis*,
  *harr* or *ltm*; otherwise `rnaseq`.
- **Pair**: the name without the type word (`control_1`), when that links one
  Ribo-seq library to one RNA-seq library. Pairs are what make translational
  efficiency meaningful: both libraries come from the same cells.
- **Condition**: the pair name without its replicate number (`control`).

Check every guess. The table goes to the pipeline as its samplesheet, with the
pair and condition columns included.

## Pipeline settings worth knowing

- **contrasts**: a CSV file asking the pipeline to test translational efficiency
  with anota2seq. Everyome writes one from the samples table when you leave this
  empty and the table has pairs and at least two conditions: each other condition
  against the first one listed. To choose the comparisons yourself, give your own
  file, for example:

  ```
  id,variable,reference,target,batch,pair
  treated_vs_control,condition,control,treated,,pair
  ```

  `variable` is the samples-table column that holds the groups (`condition`),
  `reference` and `target` are two of its values, and `pair` names the column
  linking Ribo-seq and RNA-seq libraries. Leave it empty to skip the pipeline's
  own TE test; the live session's comparison works either way.
- **remove_ribo_rna** (on by default) removes rRNA reads with SortMeRNA. The
  default rRNA databases are SILVA-derived; commercial users need a SILVA
  licence.
- **with_umi** and the UMI settings, if your library kit adds UMIs.
- **run_ribotricer**, **run_price**, **run_rpbp**: extra ORF callers (slower).
  Ribo-TISH and RiboCode run by default.

## Live session

1. **Check periodicity.** For every Ribo-seq library: the share of P-sites in
   coding sequences that fall in frame 0, footprints by length with the P-site
   offset riboWaltz chose, and P-sites around start and stop codons coloured by
   frame. Good libraries show a clear 3-nucleotide rhythm.
2. **Look at ORFs.** The ORF catalogue (or Ribo-TISH's predictions): counts by
   class (annotated CDS, uORF, dORF and others), lengths, and a searchable list.
3. **Compare translation.** Choose two conditions. For every gene with enough
   counts, Everyome normalises Ribo-seq and RNA-seq counts separately (DESeq2's
   median-of-ratios size factors), computes log2 TE within each pair, and tests
   RNA-seq, Ribo-seq and TE changes with a moderated t-test (each gene's variance
   is pulled towards the typical gene's, as limma does) with Benjamini–Hochberg
   adjustment. Genes are classed as *translation* (TE changes), *buffering* (TE
   offsets an mRNA change), *mRNA abundance* (mRNA and footprints move together)
   or *unchanged*. If the pipeline ran anota2seq for the same comparison, the
   session shows how many genes both called.
4. **Export.** `periodicity.csv`, `orfs.csv` and the TE table in
   `results/final/`.

## Things to watch

- **Periodicity first.** Counts and ORF calls depend on correct P-sites. A
  library with weak periodicity is noisier, whatever its depth.
- **TE needs pairs.** Comparing Ribo-seq from one set of samples with RNA-seq from
  another mixes biological variation into TE. Make both libraries from the same
  lysate when you can.
- **Few replicates.** With two or three pairs per condition, only clear changes
  are found. The moderated test helps but cannot replace replicates.
- **Short ORFs** are easy to call by chance; prefer those found by more than one
  caller and in more than one sample (the pipeline's `orf_min_callers` and
  `orf_min_samples` settings).
- The session's TE test and anota2seq use different models (anota2seq regresses
  footprints on mRNA), so they agree on clear cases but not on every gene.

## References

- Manning J. et al. nf-core/riboseq. https://doi.org/10.5281/zenodo.10966364
- Lauria F. et al. (2018). riboWaltz. *PLoS Computational Biology* 14:e1006169. https://doi.org/10.1371/journal.pcbi.1006169
- Zhang P. et al. (2017). Ribo-TISH. *Nature Communications* 8:1749. https://doi.org/10.1038/s41467-017-01981-8
- Xiao Z. et al. (2018). RiboCode. *Nucleic Acids Research* 46:e61. https://doi.org/10.1093/nar/gky179
- Oertlin C. et al. (2019). anota2seq. *Nucleic Acids Research* 47:e70. https://doi.org/10.1093/nar/gkz223
- Smyth G.K. (2004). Moderated t-statistics (limma). *Statistical Applications in Genetics and Molecular Biology* 3:3. https://doi.org/10.2202/1544-6115.1027
- Ingolia N.T. et al. (2009). Genome-wide analysis in vivo of translation with nucleotide resolution using ribosome profiling. *Science* 324:218–223. https://doi.org/10.1126/science.1168978
