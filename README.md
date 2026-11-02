<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/brand/everyome_stacked-tagline_dark.svg">
    <img alt="Everyome: free, open, for everyone. Learn as you explore." src="docs/brand/everyome_stacked-tagline_light.svg" width="500">
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
- **Spatial transcriptomics (10x Visium)**, spatial: from Space Ranger's output,
  see every spot on the tissue image, find tissue regions, their markers and
  spatially variable genes, and compare regions between conditions.
- **Structure prediction**, protein: nf-core/proteinfold (AlphaFold2, ESMFold,
  ColabFold, AlphaFold 3, Boltz and more) on the cluster's GPUs; see each
  structure coloured by confidence with its predicted aligned error and domains,
  compare methods, and export whole or trimmed models.
- **Alignment and tree building**, phylogenetics: MAFFT, trimAl and IQ-TREE in
  containers pinned by digest; check the alignment, then root, collapse and colour
  the tree by your own table, and export a figure.
- **Genome assembly (PacBio, Nanopore, Illumina)**, DNA: nf-core/genomeassembler
  builds genomes from long reads, polished with Illumina reads and with genes
  lifted from a relative; compare strategies side by side and choose one.
- **Bacterial genome assembly and annotation**, DNA: nf-core/bacass assembles
  Illumina, long or hybrid reads and finds genes (Prokka or Bakta).
- **Bulk RNA-seq differential expression**, RNA: nf-core/rnaseq turns reads into
  gene counts on the cluster, then DESeq2 compares conditions in a live session.
- **Primer design**, molecular biology: Primer3 primers on a plasmid map, with
  checks for your own primers. Runs on your computer; no cluster needed.
- **Sequence summary**, getting started: a small worked example of how every
  module runs.

## Install

**New to the command line?** The [step-by-step install guide](docs/INSTALL.md) walks you through
opening a terminal, installing conda, and starting Everyome. If you already use Python:

```bash
pip install "everyome==0.1.0a2"          # the app and the tutorial
pip install "everyome[all]==0.1.0a2"     # every analysis, with the pipelines it runs on clusters
everyome                                 # opens http://127.0.0.1:8777
```

Analyses that run a Nextflow pipeline on your cluster (bulk and single-cell
RNA-seq, genome assembly, protein structure prediction) use the pipelines
package, `everyome-pipelines`, at the same version as Everyome; `everyome[all]`
includes it, or add it with `pip install "everyome[pipelines]==0.1.0a2"`. Everyome
ships the pipelines, so your cluster never downloads code from GitHub; see
[`docs/PIPELINES.md`](docs/PIPELINES.md), including for clusters without internet.

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

See [`CONTRIBUTING.md`](CONTRIBUTING.md). A community module registry is built in
but switched off; every module submitted to it will be reviewed by a maintainer
before anyone is offered it. Authors can write and try modules now
([`docs/MODULE_AUTHORS.md`](docs/MODULE_AUTHORS.md)).

## Develop

```bash
git clone https://github.com/Everyome/everyome && cd everyome
pip install -e ".[test,all]"
pytest
```

## Acknowledgements

Everyome was created by Helen R Horkan PhD (Stowers Institute for Medical
Research). Much of its code and documentation was written with Claude
(Anthropic; https://www.anthropic.com/claude), an AI assistant, through Claude
Code (https://claude.com/claude-code), under her direction. It is built on
nf-core, Nextflow, BioContainers and many open-source scientific tools and
libraries; [`ACKNOWLEDGEMENTS.md`](ACKNOWLEDGEMENTS.md) thanks each of them and
gives the references to cite.

## Licence

MIT (see `LICENSE`). Fonts, UMAP-JS and the nf-core pipelines and schemas that
ship with Everyome keep their own licences; see `THIRD_PARTY_NOTICES.md`.
