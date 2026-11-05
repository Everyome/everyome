**What it shows.** How many predicted ORFs fall in each class, and their typical length.

- **canonical_cds**: the annotated coding sequence of a gene.
- **uORF**: a short ORF in the 5' leader, before the main start codon (**uoORF**: one that overlaps the main start).
  uORFs often lower their gene's translation by catching ribosomes first.
- **dORF**: in the 3' trailer, after the stop codon. **intORF**: inside the CDS in another frame. **variant**: an
  N-terminally extended or truncated version of the main ORF. **novel**: on transcripts without an annotated CDS.
- Short ORFs (smORFs, under 100 amino acids) are easy to call by chance; prefer those found by more than one caller.
