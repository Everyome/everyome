**TPM (transcripts per million)** is a gene's share of a sample's transcripts, corrected for gene length: of every
million transcripts in that sample, about this many came from this gene.

- TPM is good for comparing **one gene across samples** and **genes within a sample**, roughly.
- It is not a test: small differences between samples can be noise. With replicates, look at whether a group's
  replicates agree before reading anything into a difference.
- Because TPM is a share, a few very highly expressed genes changing pushes every other gene's TPM the other way.
  The playground shows this.
