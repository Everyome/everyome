# Function annotation (InterProScan)

Finds known domains, families and sites in your proteins, and the GO terms they imply. InterProScan searches each
protein against InterPro's member databases (Pfam, PANTHER, CDD, SMART, PROSITE and others); InterPro groups their
matches into entries. Runs on any set of proteins: a handful of genes of interest, or a whole proteome, for example the
proteins predicted by Genome annotation.

## What you need

- **Proteins** as FASTA. Stop codons are removed for you.
- On the cluster: **Apptainer**, and **InterProScan's data folder** (a 6.6 GB download, larger once unpacked), once,
  in a shared place: ask IT. InterProScan runs in its official image, pinned by digest.
- The lookup of precalculated matches at EBI is **off**: it would send each sequence's checksum to EBI. Turn it on in
  the advanced settings only if that's acceptable for your data.

## Live session

1. **What was found**: proteins with matches, matches per database, the most common entries, and a searchable list.
2. **Look at a protein**: its domains along the sequence, database by database, with the InterPro entries and GO terms.
3. **GO terms** across all proteins, by aspect.
4. **Export**: protein_annotations.csv, domains.csv and go_terms.csv.

## Things to watch

- A match means similarity to a known domain, not proof of function in your organism.
- Some member databases (SignalP, TMHMM, Phobius) need separate licences and are not in the official image; they are
  simply not searched.
- A whole proteome takes hours; the run asks for 16 CPUs.

## References

- Jones P. et al. (2014). InterProScan 5. *Bioinformatics* 30:1236–1240. https://doi.org/10.1093/bioinformatics/btu031
- Blum M. et al. (2025). InterPro in 2025. *Nucleic Acids Research* 53:D444–D456. https://doi.org/10.1093/nar/gkae1082
- The Gene Ontology Consortium (2023). *Genetics* 224:iyad031. https://doi.org/10.1093/genetics/iyad031
