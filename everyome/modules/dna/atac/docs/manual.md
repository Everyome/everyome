# Chromatin accessibility (ATAC-seq)

Finds the open chromatin in your samples. ATAC-seq cuts DNA where it is not
wrapped around nucleosomes or packed away, so reads pile up at open regions:
promoters, enhancers and other places where proteins can reach the DNA.
nf-core/atacseq turns the reads into peaks (the open regions) and counts reads
in them; the live session checks the libraries, compares groups, and shows any
region of the genome.

## What you need

- **Paired-end (or single-end) ATAC-seq FASTQ files**, one or more per library.
- **A genome FASTA and its GTF.** Any species works. Use the same genome version
  for both.
- **The effective genome size** (`macs_gsize`) for MACS2. For human, mouse, fly,
  worm and yeast the pipeline knows it if you choose an iGenomes genome. **For
  any other species you must set it**, or the pipeline skips peak calling and
  there is nothing to explore; Everyome stops you before submitting. A good
  value is the genome's length without long runs of N (the mappable part); for a
  450 Mb genome with few gaps, about 4.0e8. Alternatively set the read length
  and the pipeline works it out.
- On the cluster: Nextflow, Java and Apptainer (see the install guide). The
  pipeline's containers are pulled once into the shared folder.

## Libraries table

*Find libraries in the reads folder* lists the FASTQ pairs and guesses a
**group** and **replicate** from each name (`polyp_rep2_R1.fastq.gz` → polyp,
2). The pipeline names each library `<group>_REP<replicate>`; replicates of one
group are what the comparison uses. Two rows with the same group and replicate
(the same library on two lanes, say) are joined as one library.

## Settings worth knowing

- **narrow_peak.** Everyome calls narrow peaks, because ATAC-seq open sites are
  mostly sharp. The pipeline's own default is broad peaks; switch back for broad
  marks.
- **mito_name.** The mitochondrial sequence's name in your FASTA (for example
  `chrM` or `MT`). Mitochondrial DNA is very open and can take half the reads;
  set this so they are removed before peak calling.
- **min_reps_consensus.** How many replicates of a group must call a peak for it
  to join the consensus set. The default, 1, keeps every peak.
- **blacklist.** A BED of regions known to collect artefactual reads. Use one if
  your species has one.

## What the pipeline does

Trims adapters (Trim Galore), aligns with BWA-MEM, merges the runs of each
library, marks duplicates (Picard), removes duplicates, multi-mapping, unpaired
and mitochondrial reads, makes bigWig coverage tracks, calls peaks in each
library with MACS2, merges every library's peaks into one consensus set, counts
reads in it (featureCounts), and gathers every quality check in a MultiQC
report. The Run page shows peaks and FRiP for each library and opens the report.

## Live session

1. **Check libraries.** Peaks, fraction of reads in peaks (FRiP), median peak
   width and reads in the consensus peaks for each library; principal
   components and correlation of the consensus counts, normalised for library
   size (DESeq2's size factors) and log-scaled.
2. **Where the peaks are.** Peak widths, and how far each peak lies from the
   nearest gene's transcription start site (from the GTF). In most tissues a
   large share of strong open sites are promoters.
3. **Compare groups.** DESeq2 (PyDESeq2) tests each consensus peak for a
   difference in reads between two groups, with replicates. Peaks *more open* in
   the test group have a positive log2 fold change. Volcano plot and a table with
   each peak's nearest gene; click a peak to see it.
4. **Look at a region.** A peak or gene and the region around it: each library's
   peaks (or its coverage, when the pipeline's bigWigs can be read; this needs
   the `pyBigWig` package in the session), the consensus peaks coloured by the
   comparison, and genes.
5. **Export.** Consensus peaks with counts and nearest genes, normalised counts,
   the libraries' groups, and the comparison's tables and BED in
   `results/final`.

## Things to watch

- **FRiP.** ENCODE asks for at least 20% of reads in peaks, ideally 30% or more.
  A library well below its replicates is noisy: its peaks are fewer and its
  counts weaker. Check its PCA position before trusting a comparison.
- **The nearest gene is a guess.** Enhancers can act on genes far away, skipping
  the nearest one. Treat the nearest gene as a lead.
- **Accessibility is not activity.** An open region can be bound by a repressor.
  Combine with RNA-seq to see whether nearby genes change too.
- **Batch effects** (preparation day, Tn5 batch, cell number) show in the library
  checks first, and ATAC-seq is sensitive to them.

## References

- Patel H. et al. nf-core/atacseq. https://doi.org/10.5281/zenodo.2634132
- Buenrostro J.D. et al. (2013). Transposition of native chromatin for fast and sensitive epigenomic profiling of open chromatin, DNA-binding proteins and nucleosome position. *Nature Methods* 10:1213–1218. https://doi.org/10.1038/nmeth.2688
- Zhang Y. et al. (2008). Model-based analysis of ChIP-Seq (MACS). *Genome Biology* 9:R137. https://doi.org/10.1186/gb-2008-9-9-r137
- Liao Y., Smyth G.K., Shi W. (2014). featureCounts. *Bioinformatics* 30:923–930. https://doi.org/10.1093/bioinformatics/btt656
- Love M.I., Huber W., Anders S. (2014). DESeq2. *Genome Biology* 15:550. https://doi.org/10.1186/s13059-014-0550-8
- Landt S.G. et al. (2012). ChIP-seq guidelines and practices of the ENCODE and modENCODE consortia. *Genome Research* 22:1813–1831. https://doi.org/10.1101/gr.136184.111
