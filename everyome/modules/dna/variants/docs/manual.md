# Variant and mutation calling

Finds single-nucleotide variants (SNVs) and small insertions and deletions
(indels) in DNA sequencing reads, against your own reference genome. nf-core/sarek
maps the reads, marks duplicates, measures coverage and calls variants in each
sample; a live session then filters the calls, shows where the callers agree,
shows any variant's genotype in every sample, and finds variants that separate
two groups of samples, for example a mutant line from its wild type.

This module calls **germline** variants: those an animal or line carries in every
cell. It does not look for somatic mutations in tumours, or for large structural
variants.

## What you need

- **Reads**: paired-end (or single-end) FASTQ files from whole-genome, exome or
  targeted sequencing, named like `<sample>_R1.fastq.gz` and `_R2.fastq.gz`.
  Lane numbers (`_L001`) are kept, so a sample sequenced on several lanes is
  merged by the pipeline.
- **Your reference genome** as a FASTA file (the *FASTA* setting). Everyome always
  uses your own genome and never the pipeline's built-in human references, so any
  species works.
- **For exomes or panels**: the targets as a BED file (*Intervals*), and turn on
  *Wes*. Without intervals, the whole genome is called, in chunks.
- On the cluster: Nextflow 25.10.4 or newer, Java and Apptainer. The pipeline's
  own jobs go to Slurm; the live session runs on one compute node (2 CPUs, 16 GB).

## Samples table

*Find samples in the reads folder* fills one row per sample and lane:

- **Individual**: the animal, line or clone the DNA came from. Usually the same as
  the sample; two samples from one individual (for example two tissues) share it.
- **Sample** and **Lane**: rows with the same sample are merged after mapping.
- **Group** (optional): only used in the live session, to find variants that
  separate two groups. It is guessed from the name (`mut_2` → `mut`); check it.

## Settings that matter

- **Tools**: which callers run. Everyome starts from `haplotypecaller,deepvariant`
  (GATK HaplotypeCaller and DeepVariant). Two callers that work differently let
  you keep only variants both find. `freebayes`, `strelka` and `mpileup`
  (bcftools) are also germline callers.
- **Skip tools**: Everyome starts from `baserecalibrator,haplotypecaller_filter`.
  Base quality recalibration and GATK's neural-network filter both need a set of
  known variant sites (*Dbsnp*, *Known indels*), which most species don't have.
  If you have them, set those files and clear *Skip tools*.
- Every other nf-core/sarek setting is in the form, with the pipeline's own help.

## The run

The pipeline writes, in the run's `results` folder:

- `variant_calling/<caller>/<sample>/<sample>.<caller>.vcf.gz`: each caller's calls
- `preprocessing/`: mapped, duplicate-marked reads (CRAM)
- `reports/`: coverage (mosdepth), mapping and variant statistics
- `multiqc/multiqc_report.html`: every quality check in one report

The Run page shows mean depth per sample and links the MultiQC report.

## Live session

1. **Check samples and callers.** Calls per caller and sample (SNVs, indels,
   transition/transversion ratio, one-copy and two-copy genotypes); how many
   callers found each variant; the spread of call quality and read depth.
2. **Filter variants.** Choose callers, how many must agree, the minimum call
   quality (QUAL), read depth and genotype quality (GQ), variant type and region.
   A variant is kept when enough callers called it, passing the filters, in at
   least one sample. Each sample's genotype comes from the first chosen caller
   that called it there; if a caller called it but the call failed the filters,
   the genotype shows as uncertain (?). Click a variant to see every caller's call
   and read counts in every sample.
3. **Compare groups.** Variants carried by every sample of one group and by no
   sample of the other, and where they fall along each chromosome. A cluster of
   separating variants points to a region linked to the difference, for example a
   mutation and the DNA inherited with it.
4. **Export.** `variants_filtered.vcf` (with the filters in its header),
   `variants_filtered.csv`, and the separating variants, in `results/final/`.

## Good to know

- Per-sample VCFs only list positions where the sample differs from the
  reference, so a sample with no call at a position is shown as not carrying the
  variant. Low coverage there would also give no call: check depth in the
  MultiQC report before trusting an absence.
- With few samples per group, some ordinary variants separate the groups by
  chance. A real linked region shows up as a cluster; scattered single variants
  are usually chance.
- The callers' original VCFs, with every annotation, stay in
  `results/variant_calling/`; use them for anything the session does not do,
  such as annotating effects on genes.
