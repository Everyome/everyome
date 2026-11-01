# Everyome

*Every -ome, for everyone.*

Created by **Helen R Horkan PhD** (Stowers Institute). If you use Everyome, adapt its
code, or reuse its text or figures, please cite it (see [`CITATION.cff`](https://github.com/Everyome/everyome/blob/main/CITATION.cff)).

Everyome is a free, open-source platform for omics analysis. It gives biologists a
simple point-and-click interface while keeping every setting visible and editable.
It runs on your own computer or on your own Slurm cluster account over SSH, so
your data stays where it is.

Planned suites: DNA, RNA, single cell, spatial, protein, molecular biology and
phylogenetics. Every module will come with a manual, a playground, guides to
reading its output, and a lab-book protocol and methods section for every run.

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
- **Bulk RNA-seq differential expression**, RNA: nf-core/rnaseq turns reads into
  gene counts on the cluster, then DESeq2 compares conditions in a live session.
- **Primer design**, molecular biology: Primer3 primers on a plasmid map, with
  checks for your own primers. Runs on your computer; no cluster needed.
- **Sequence summary**, getting started: a small worked example of how every
  module runs.

## Install

```bash
pip install "everyome==0.1.0a1"          # the app and the tutorial
pip install "everyome[all]==0.1.0a1"     # plus SPLiT-seq and bulk RNA-seq (Scanpy, PyDESeq2, ...)
everyome                              # opens http://127.0.0.1:8777
```

Naming the version installs this early release of Everyome while everything it
needs comes from normal, stable releases. (Avoid `pip install --pre`: it would
also pull in unfinished versions of other packages.) Everyome needs Python 3.10
or newer and runs on macOS and Linux. Choose **Demo
cluster** to try everything on your own computer, with example data and a
pretend job scheduler; demo data lives in `~/.everyome/demo_cluster` (delete it
to start fresh). To use your own cluster, Everyome also needs to be installed in
a Python environment there (ask IT for a shared one), and the readiness checks
tell you what is missing.

## Develop

```bash
git clone https://github.com/Everyome/everyome && cd everyome
pip install -e ".[test,all]"
pytest
```

## Licence

MIT (see `LICENSE`). Fonts, UMAP-JS and the nf-core/rnaseq schemas that ship
with Everyome keep their own licences; see `THIRD_PARTY_NOTICES.md`.
