# Everyome

*Every -ome, for everyone.*

Created by **Helen R Horkan PhD** (Stowers Institute). If you use Everyome, adapt its
code, or reuse its text or figures, please cite it (see `CITATION.cff`).

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

The core is in place (phase 1 of [`docs/PLAN.md`](docs/PLAN.md)): connect to a
cluster or the built-in demo cluster, create projects, choose an analysis, fill
in its settings, check the exact job scripts, submit them, follow the jobs, and
explore the results in a live session. Every run then gets a lab-book
protocol, a draft methods section to edit, its references, and a bundle that
repeats it exactly.

Modules so far:
- **SPLiT-seq (SPLiTscape)**, single cell: SPLiT-seq sublibraries from raw reads
  to annotated cell types, on their own (for example, to build a first atlas) or
  merged with an existing atlas or dataset. Includes a playground.
- **Sequence summary**, getting started: a small worked example of how every
  module runs.

## Try it

```bash
pip install -e ".[test,singlecell]"
everyome            # opens http://127.0.0.1:8777
pytest
```

Choose **Demo cluster** to try everything on your own computer, with example
data and a pretend job scheduler. Demo data lives in `~/.everyome/demo_cluster`;
delete that folder to start fresh.

## Licence

To be confirmed (MIT or BSD-3) with Stowers tech transfer.
