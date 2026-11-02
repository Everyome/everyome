# Structure prediction

Predicts the 3D structure of proteins, or protein complexes, from their
sequences, with nf-core/proteinfold on your cluster's GPUs. Then a live session
shows each predicted structure coloured by how confident the prediction is,
which parts are placed reliably relative to each other, and how different
methods compare; and exports whole models or only their confident parts.

## What you need

- **Sequences**: one FASTA file per prediction. A file with one sequence predicts
  one protein; a file with several sequences predicts them together as a complex
  (choose a multimer model). Point *Sequences folder* at a folder of FASTA files
  and press *Find FASTA files* to fill in the table.
- **GPUs** on the cluster, and the name of the GPU partition (ask IT). Predictions
  on CPUs are possible (turn off *Use GPU*) but take hours to days per protein.
- **Reference data** for the method you choose (*Reference data folder*):

| Method | Needs | Notes |
|---|---|---|
| `alphafold2` (default) | about 2.6 TB of databases and model weights | the most widely used; PAE and pTM for every model |
| `colabfold` | about 1 TB, or none with *Use MSA server* | faster searches; the MSA server sends your sequences to an external service, so only use it for sequences you may share |
| `esmfold` | model weights only (a few GB) | fastest, no sequence search; less accurate for proteins with few relatives; no PAE |
| `alphafold3`, `boltz`, `rosettafold_all_atom`, `helixfold3`, `rosettafold2na` | their own databases and weights | complexes with nucleic acids or small molecules; AlphaFold 3's weights must be requested from Google DeepMind and are for non-commercial use |

  Clusters that run structure prediction usually keep these databases in one
  shared folder. Everyome refuses a run that would download the large databases
  into your run folder: set *Reference data folder*, or choose `esmfold`.
- Nextflow 25.10.2 or newer, Java and Apptainer on the cluster.

## The pipeline

*Prediction methods* (`mode`) can list several methods separated by commas
(for example `alphafold2,esmfold`) to predict each protein with each and
compare them. Every other setting of nf-core/proteinfold is under the settings,
grouped by method. Everyome starts with *Use GPU* on; the prediction steps then
go to the *GPU partition* and ask Slurm for one GPU each.

## Live session

1. **Predictions.** Every structure the pipeline made: its length, mean pLDDT,
   how much of it is confidently predicted, pTM (and ipTM for complexes), and
   the confident domains Everyome found.
2. **Look at a structure.** The structure in 3D (drag to turn, scroll to zoom),
   coloured by pLDDT, by domain or by chain; pLDDT along the sequence for every
   ranked model; and the predicted aligned error (PAE) as a heat map with the
   domains marked.
3. **Compare methods.** When a protein was predicted by more than one method:
   their confidence side by side and how far apart their structures are (RMSD
   after superposition, over all residues and over confidently predicted ones).
4. **Export.** The top-ranked models as PDB files, whole or with only residues
   above a pLDDT you choose (or only the confident domains), for example to
   design constructs, as a search model for molecular replacement, or for
   figures; plus a summary table.

Everything you choose is noted in the run record, so the protocol and the
methods draft say which models were exported and how they were trimmed.

## Reading a prediction

- **pLDDT** (0–100) is the predictor's confidence in each residue's local
  structure: above 90 very high, 70–90 confident (backbone usually right), 50–70
  low, below 50 very low. Long stretches below 50 are often disordered in reality.
- **PAE** (Å) is the expected error in the position of one residue when the model
  is superposed on another. Low PAE within a block means the block is confidently
  shaped; high PAE between two blocks means their relative position is uncertain,
  even if each is confident on its own.
- **pTM** (0–1) scores the whole fold; **ipTM** the interfaces in a complex
  (above about 0.8 suggests a confident interface; below 0.6 a likely wrong one).
- A confident prediction is still a prediction. Check it against what is known
  (mutations, crosslinks, homologues with structures) before relying on it.

## The demo

Three made-up proteins: *twodomain* (two confident domains joined by a flexible
linker, with floppy ends), *hairpin* (a compact two-helix protein, confident
everywhere) and *disordered* (mostly disordered, with one short helix). On the
demo cluster a stand-in replaces the pipeline. Set *Prediction methods* to
`alphafold2,esmfold` to try the comparison: the stand-in ESMFold places the two
domains of *twodomain* differently, as the PAE warns could happen.

## References

- nf-core/proteinfold. https://doi.org/10.5281/zenodo.7629996
- Jumper J. et al. (2021). Highly accurate protein structure prediction with AlphaFold. *Nature* 596:583–589. https://doi.org/10.1038/s41586-021-03819-2
- Lin Z. et al. (2023). Evolutionary-scale prediction of atomic-level protein structure with a language model. *Science* 379:1123–1130. https://doi.org/10.1126/science.ade2574
- Mirdita M. et al. (2022). ColabFold: making protein folding accessible to all. *Nature Methods* 19:679–682. https://doi.org/10.1038/s41592-022-01488-1
- Abramson J. et al. (2024). Accurate structure prediction of biomolecular interactions with AlphaFold 3. *Nature* 630:493–500. https://doi.org/10.1038/s41586-024-07487-w
- Kabsch W. (1976). A solution for the best rotation to relate two sets of vectors. *Acta Crystallographica* A32:922–923. https://doi.org/10.1107/S0567739476001873
