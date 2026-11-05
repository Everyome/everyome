# Interaction prediction

Predicts how proteins fit together, and how likely they are to bind as predicted, from their sequences. Each complex
is predicted by nf-core/proteinfold's multimer models (AlphaFold2-Multimer by default; ColabFold multimer, Boltz and
others can be chosen) on the cluster's GPUs. The live session scores every interface and shows it.

## What you need

- **One FASTA file per complex**, with every chain of the complex (one `>` line per chain; for a homodimer, the same
  sequence twice). *Find complexes in the folder* lists the files with two or more chains.
- On the cluster: **Nextflow**, **Java**, **Apptainer**, a **GPU partition**, and the methods' **reference
  databases** (AlphaFold2 about 2.6 TB, ColabFold about 1 TB) in a shared folder: ask IT, as for Structure
  prediction. Without them, a run is refused before anything is submitted.
- The ColabFold MSA server would send sequences off site, so it stays off unless you turn it on.

## Live session

1. **Interfaces.** Every pair of chains: contacts, interface pLDDT and PAE, ipTM, pDockQ and a plain reading. Click a
   row to see the interface in 3D (interface residues highlighted), the residues on each side, and the predicted error
   between the chains.
2. **Predictions**, **Look at a structure**, **Compare methods**, **Export**: as in Structure prediction.

## Things to watch

- **Predicted is not proven.** Use the scores to rank candidates and to plan experiments.
- Large complexes (several chains, thousands of residues) need a lot of GPU memory; predict pairs first.
- pDockQ uses Cα atoms here (its paper used Cβ); the numbers are very close.

## References

- Evans R. et al. (2022). AlphaFold-Multimer. *bioRxiv*. https://doi.org/10.1101/2021.10.04.463034
- Bryant P., Pozzati G., Elofsson A. (2022). pDockQ. *Nature Communications* 13:1265. https://doi.org/10.1038/s41467-022-28865-w
- nf-core/proteinfold. https://doi.org/10.5281/zenodo.7629996
