# Genome annotation (Helixer)

Predicts the genes of a eukaryotic genome from its sequence alone. **Helixer** reads the genome with a deep-learning
model trained on a lineage (invertebrates, vertebrates, land plants or fungi) and writes gene models (GFF3); no RNA-seq
or protein evidence is needed. **gffread** writes each predicted protein, and **BUSCO** checks how many genes expected
in every member of your lineage are there.

## What you need

- The **genome** as FASTA, for example from Genome assembly.
- On the cluster: **Apptainer**, a **GPU partition** (Helixer runs on a GPU; ask IT for its name), and a shared folder
  with **Helixer's lineage models** (a few hundred MB, fetched once). For BUSCO without internet, a folder of BUSCO's
  lineage datasets.
- The **lineage model** closest to your organism: *invertebrate* for cnidarians, insects, molluscs, worms.

## On the cluster

1. **Predict genes** (Helixer, on one GPU).
2. **Write the proteins** (gffread).
3. **Check completeness** (BUSCO on the proteins; skipped without a lineage dataset).

## Live session

1. **The gene models**: counts, exons per gene, gene and protein lengths, genes per sequence, BUSCO.
2. **Look at genes**: search, the exon structure, the protein.
3. **Export**: annotation.gff3, proteins.faa (ready for Function annotation) and genes.csv.

## Things to watch

- Helixer was trained on other genomes; for a lineage far from its training data, expect more errors. Check genes you
  care about against RNA-seq.
- Gene names here are identifiers; Function annotation adds what each protein looks like.
- BRAKER and other evidence-based pipelines need licensed GeneMark and are not included.

## References

- Stiehler F. et al. (2021). Helixer. *Bioinformatics* 36:5291–5298. https://doi.org/10.1093/bioinformatics/btaa1044
- Holst F. et al. (2023). Helixer gene models with HelixerPost. *bioRxiv*. https://doi.org/10.1101/2023.02.06.527280
- Pertea G., Pertea M. (2020). GffRead. *F1000Research* 9:304. https://doi.org/10.12688/f1000research.23297.2
- Manni M. et al. (2021). BUSCO. *Molecular Biology and Evolution* 38:4647–4654. https://doi.org/10.1093/molbev/msab199
