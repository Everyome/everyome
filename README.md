<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Everyome/everyome/main/docs/brand/everyome_stacked-tagline_dark.svg">
    <img alt="Everyome: free, open, for everyone. Learn as you explore." src="https://raw.githubusercontent.com/Everyome/everyome/main/docs/brand/everyome_stacked-tagline_light.svg" width="500">
  </picture>
</p>

# Everyome

*Every -ome, for everyone.*

Created by **Helen R Horkan PhD** (Stowers Institute). If you use Everyome, adapt its
code, or reuse its text or figures, please cite it (see [`CITATION.cff`](https://github.com/Everyome/everyome/blob/main/CITATION.cff)).

Everyome is a free, open-source platform for omics analysis. It gives biologists a
simple point-and-click interface while keeping every setting visible and editable.
It runs on your own computer or on your own Slurm cluster account over SSH, so
your data stays where it is.

Suites: DNA, RNA, single cell, spatial, protein, molecular biology and
phylogenetics, each with at least one ready tool. Every module comes with a
manual, a playground, guides to reading its output, and a lab-book protocol and
methods section for every run.

Everyome grows out of SPLiTscape (SPLiT-seq reads to annotated cell atlases),
which becomes its first single-cell module and keeps its own citation.

## Status

The core is in place (phase 1 of [`docs/PLAN.md`](https://github.com/Everyome/everyome/blob/main/docs/PLAN.md)): connect to a
cluster or the built-in demo cluster, create projects, choose an analysis, fill
in its settings, check the exact job scripts, submit them, follow the jobs, and
explore the results in a live session. Every run then gets a lab-book
protocol, a draft methods section to edit, its references, and a bundle that
repeats it exactly. Every analysis comes with a manual, a playground to try it on
toy data, and "how to read this" guides next to its charts.

Modules so far:
- **SPLiT-seq (SPLiTscape)**, single cell: SPLiT-seq sublibraries from raw reads
  to annotated cell types, on their own (for example, to build a first atlas) or
  merged with an existing atlas or dataset. Includes a playground.
- **Single-cell RNA-seq (10x and similar)**, single cell: nf-core/scrnaseq
  counts cells on the cluster and removes empty droplets; a live session then
  filters, clusters, finds markers and names and compares cell types.
- **Single-cell ATAC-seq**, single cell: chromap turns reads into fragments on the
  cluster; a live session filters cells on TSS enrichment, clusters them on open
  chromatin (SnapATAC2) and names them from gene activity.
- **Multiome (RNA and ATAC together)**, single cell: from Cell Ranger ARC's output,
  clusters cells on RNA, open chromatin or both (weighted nearest neighbours).
- **Spatial transcriptomics (10x Visium)**, spatial: from Space Ranger's output,
  see every spot on the tissue image, find tissue regions, their markers and
  spatially variable genes, and compare regions between conditions.
- **Imaging spatial (Xenium, MERSCOPE, CosMx)**, spatial: from the instrument's
  output, cell types in place on the tissue, spatially variable genes and which
  cell types are neighbours.
- **High-resolution spatial (Visium HD, Stereo-seq, Curio)**, spatial: bins at
  2, 8 or 16 µm, cell types on the tissue image, spatially variable genes and
  neighbourhoods.
- **Cell types in spots (cell2location)**, spatial: maps a labelled single-cell
  reference onto Visium sections on the cluster's GPUs; each cell type on the
  tissue, the main type per spot, and which types live together.
- **Structure prediction**, protein: nf-core/proteinfold (AlphaFold2, ESMFold,
  ColabFold, AlphaFold 3, Boltz and more) on the cluster's GPUs; see each
  structure coloured by confidence with its predicted aligned error and domains,
  compare methods, and export whole or trimmed models.
- **Interaction prediction**, protein: nf-core/proteinfold multimer models; every
  interface scored (ipTM, pDockQ, interface confidence) with a plain reading.
- **Function annotation (InterProScan)**, protein: domains, families and GO terms
  for any set of proteins, each protein's domain architecture, and tables.
- **Alignment and tree building**, phylogenetics: MAFFT, trimAl and IQ-TREE in
  containers pinned by digest; check the alignment, then root, collapse and colour
  the tree by your own table, and export a figure.
- **Genome assembly (PacBio, Nanopore, Illumina)**, DNA: nf-core/genomeassembler
  builds genomes from long reads, polished with Illumina reads and with genes
  lifted from a relative; compare strategies side by side and choose one.
- **Bacterial genome assembly and annotation**, DNA: nf-core/bacass assembles
  Illumina, long or hybrid reads and finds genes (Prokka or Bakta).
- **Genome annotation (Helixer)**, DNA: gene models from the genome sequence alone,
  on a GPU; proteins and BUSCO completeness; ready for Function annotation.
- **Variant and mutation calling**, DNA: nf-core/sarek maps reads to your own
  genome and calls germline variants with two callers; filter the calls, see
  where callers agree, and find variants that separate two groups of samples.
- **3D genome architecture (Hi-C)**, DNA: nf-core/hic turns read pairs into
  balanced contact maps; browse the maps, see contacts fall with distance, and
  find A/B compartments and domain (TAD) boundaries.
- **Bulk RNA-seq differential expression**, RNA: nf-core/rnaseq turns reads into
  gene counts on the cluster, then DESeq2 compares conditions in a live session.
- **RNA abundance**, RNA: from an nf-core/rnaseq results folder, how much each
  gene is expressed in each sample, sample checks, and groups of co-expressed genes.
- **Primer design**, molecular biology: Primer3 primers on a plasmid map, with
  checks for your own primers. Runs on your computer; no cluster needed.
- **Sequence summary**, getting started: a small worked example of how every
  module runs.

## Install

**One line, on macOS or Linux.** Open a terminal, paste this and press Return:

```bash
curl -fsSL https://raw.githubusercontent.com/Everyome/everyome/main/install.sh | bash
```

It installs conda (Miniforge) if you don't have it, makes an `everyome` environment
and installs Everyome with every analysis, all inside your home folder; no
administrator rights needed. It also adds an **Everyome icon** (in the Dock on
a Mac; the app menu and desktop on Linux), so after that one line you never need
the terminal: open the icon, and stop Everyome with **Quit** in the app.
[Read the script](https://github.com/Everyome/everyome/blob/main/install.sh) first if you like; it is short.

**New to the command line?** The [step-by-step install guide](https://github.com/Everyome/everyome/blob/main/docs/INSTALL.md) walks you through
opening a terminal, installing conda, and starting Everyome. If you already use Python:

```bash
pip install "everyome==0.1.0a6"          # the app and the tutorial
pip install "everyome[all]==0.1.0a6"     # every analysis, with the pipelines it runs on clusters
everyome                                 # opens http://127.0.0.1:8777
```

Analyses that run a Nextflow pipeline on your cluster (bulk and single-cell
RNA-seq, genome assembly, protein structure prediction) use the pipelines
package, `everyome-pipelines`, at the same version as Everyome; `everyome[all]`
includes it, or add it with `pip install "everyome[pipelines]==0.1.0a6"`. Everyome
ships the pipelines, so your cluster never downloads code from GitHub; see
[`docs/PIPELINES.md`](https://github.com/Everyome/everyome/blob/main/docs/PIPELINES.md), including for clusters without internet.

Naming the version installs this early release of Everyome while everything it
needs comes from normal, stable releases. (Avoid `pip install --pre`: it would
also pull in unfinished versions of other packages.) Everyome needs Python 3.10
or newer and runs on macOS and Linux. It is tested on Python 3.10 and 3.12, and
3.13 and 3.14 should work; Python 3.15 is not supported yet, because some of the
scientific packages it uses do not install there. Choose **Demo
cluster** to try everything on your own computer, with example data and a
pretend job scheduler; demo data lives in `~/.everyome/demo_cluster` (delete it
to start fresh). To use your own cluster, Everyome also needs to be installed in
a Python environment there (ask IT for a shared one), and the readiness checks
tell you what is missing.

## Contributing

See [`CONTRIBUTING.md`](https://github.com/Everyome/everyome/blob/main/CONTRIBUTING.md). A community module registry is built in
but switched off; every module submitted to it will be reviewed by a maintainer
before anyone is offered it. Authors can write and try modules now
([`docs/MODULE_AUTHORS.md`](https://github.com/Everyome/everyome/blob/main/docs/MODULE_AUTHORS.md)).

## Develop

```bash
git clone https://github.com/Everyome/everyome && cd everyome
pip install -e ".[dev]"
pytest
# the screens in a real browser, too:
pip install -e ".[browser]" && python -m playwright install chromium
pytest tests/test_browser.py
```

## Acknowledgements

Everyome was created and written by Helen R Horkan PhD (Stowers Institute for
Medical Research). It brings together her own analyses, starting with
SPLiTscape, and pipelines and tools written by other people (nf-core, Nextflow,
BioContainers and many open-source scientific tools), which it runs as their
authors released them, under their own licences. Please cite those tools as
well as Everyome; each run's methods section lists exactly which it used.
Helen used Claude (Anthropic; https://www.anthropic.com/claude) as a coding
assistant while building it.
[`ACKNOWLEDGEMENTS.md`](https://github.com/Everyome/everyome/blob/main/ACKNOWLEDGEMENTS.md)
says what is whose, thanks each project and gives the references to cite.

## Licence

Copyright (C) 2026 Helen R Horkan.

Everyome is free software: you can redistribute it and/or modify it under the
terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version (see `LICENSE`). It comes with no warranty.

Fonts, UMAP-JS and the nf-core pipelines and schemas that ship with Everyome keep
their own licences; see `THIRD_PARTY_NOTICES.md`.
