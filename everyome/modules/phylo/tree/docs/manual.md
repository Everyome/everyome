# Alignment and tree building

Works out how a set of DNA or protein sequences are related, as a tree. Three
cluster stages align the sequences, remove the parts of the alignment that
cannot be trusted, and build a maximum-likelihood tree with branch support. A
live session then lets you check the alignment and explore the tree.

## What you need

- **Sequences** in one FASTA file: DNA or protein, at least four, one per
  species, gene or sample. They do not need to be aligned. Each sequence's name
  is the first word of its `>` line, so make those words different; characters
  that trees cannot hold (spaces, brackets, commas, colons) become `_`.
- Optionally, a **table about the sequences** (CSV or tab-separated): the first
  column is the sequence name, the others are anything you want to colour the
  tree by, such as species group, habitat or gene family.
- **Apptainer** (or Singularity) on the cluster. Nothing else needs installing:
  each tool runs in its own container.

## The stages

1. **Align (MAFFT).** Lines up the sequences so that each column holds
   positions that share an ancestor. *Alignment strategy* chooses how hard MAFFT
   works: `auto` decides by the size of the data; `linsi` is the most accurate
   for up to about 200 sequences. Turn on *Sequences are already aligned* to
   skip this stage.
2. **Trim (trimAl).** Removes columns that are mostly gaps or poorly aligned,
   which add noise rather than signal. `automated1` is trimAl's recommendation for
   maximum-likelihood trees. Trimming can remove useful signal too: if it
   removes more than about half the columns, try `gappyout` or no trimming.
3. **Build the tree (IQ-TREE).** With the model set to `MFP`, ModelFinder tests
   models of how sequences change and picks the best by BIC; IQ-TREE then searches
   for the maximum-likelihood tree. Branch support comes from 1,000 ultrafast
   bootstrap replicates (UFBoot) and 1,000 SH-aLRT replicates. An *outgroup*
   (sequences known to sit outside the group you study) roots the tree; you can
   also root it later.

### Pinned containers

MAFFT 7.525, trimAl 1.5.1 and IQ-TREE 3.1.4 run in BioContainers images pinned by
their SHA-256 digest, so every cluster runs exactly the same builds and the run
record names them. The first run pulls the images into the shared pipelines
folder (`<pipelines folder>/containers`, set when you connect); later runs reuse
them. If the cluster's compute nodes cannot reach the internet, IT (or you) can
fill that folder in advance from a login node:

```
python -m everyome.core.containers pull phylo.tree --into <pipelines folder>/containers
```

## Live session

1. **Check the alignment.** The alignment, with the columns trimming removed
   shown pale, and a table of sequences. Sequences that are mostly gaps after
   trimming (partial sequences) or very different from the rest are flagged:
   they are not removed, but they are the first place to look if the tree looks
   wrong.
2. **Model and support.** The model the tree was built with (and, with
   ModelFinder, the models it compared), and how strongly the data support the
   tree's branches.
3. **Explore the tree.** Root it at its midpoint, on an outgroup, or on any
   branch you click; collapse groups to a triangle; colour the names by a column
   of your table. The **Groups** table says whether each value of that column
   forms one group (a clade) on the tree, with that group's support.
4. **Export.** The rooted tree (Newick, with support), the figure (SVG), and
   tables of the sequences and groups, in `results/final/`.

Everything you do in the session is noted in the run record, so the lab-book
protocol and the methods draft say how the tree was rooted and drawn.

## Reading a tree

- Only the **branching order** and **branch lengths** carry information. Turning
  a group around its branch point (or ladderizing) changes nothing.
- A tree from IQ-TREE has **no root** until you give it one. The root decides
  which groups are "ancestral": choose an outgroup you know sits outside, or use
  the midpoint if you have none (it assumes roughly equal rates of change).
- **Branch length** is the expected number of changes per site. A very long
  branch can be a fast-evolving gene, a poor sequence or a contaminant.
- **Support** is how consistently the data back a group. IQ-TREE's rule of thumb:
  trust a group with SH-aLRT ≥ 80% and UFBoot ≥ 95%.

## The demo

One gene simulated in 22 cnidarians (sea anemones, corals, hydroids, jellyfish,
box jellyfish and stalked jellyfish) and two bilaterians (human and fruit fly) as
the outgroup. The species are real; the sequences are not. The simulation adds
insertions and deletions (so the sequences need aligning) and makes one sequence
(*Morbakka virulenta*) a fragment. One branch is very short, so the place of the
stalked jellyfish (Staurozoa) is weakly supported. The table gives each species'
class and whether it has a free-swimming medusa: colour by it to see that the
classes each form a group, but medusae do not (they were lost more than once).

On the demo cluster, quick stand-ins replace the three tools: the true alignment
for MAFFT, a simple gap rule for trimAl, and a neighbour-joining tree with
ordinary bootstrap for IQ-TREE (its model table is illustrative).

## References

- Katoh K., Standley D.M. (2013). MAFFT multiple sequence alignment software version 7. *Molecular Biology and Evolution* 30:772–780. https://doi.org/10.1093/molbev/mst010
- Capella-Gutiérrez S., Silla-Martínez J.M., Gabaldón T. (2009). trimAl. *Bioinformatics* 25:1972–1973. https://doi.org/10.1093/bioinformatics/btp348
- Wong T.K.F. et al. (2025). IQ-TREE 3: phylogenomic inference software using complex evolutionary models. EcoEvoRxiv. https://doi.org/10.32942/X2P62N
- Minh B.Q. et al. (2020). IQ-TREE 2. *Molecular Biology and Evolution* 37:1530–1534. https://doi.org/10.1093/molbev/msaa015
- Kalyaanamoorthy S. et al. (2017). ModelFinder. *Nature Methods* 14:587–589. https://doi.org/10.1038/nmeth.4285
- Hoang D.T. et al. (2018). UFBoot2. *Molecular Biology and Evolution* 35:518–522. https://doi.org/10.1093/molbev/msx281
- Guindon S. et al. (2010). PhyML 3.0 (SH-aLRT). *Systematic Biology* 59:307–321. https://doi.org/10.1093/sysbio/syq010
