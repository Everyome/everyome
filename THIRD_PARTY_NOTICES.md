# Third-party material in Everyome

Everyome itself is under the GNU General Public License, version 3 or later (`LICENSE`). It ships the following
material from others, each under its own licence, with the licence text next to it.

| What | Where | Licence |
|---|---|---|
| Fonts (Fontsource builds of open-source typefaces) | `everyome/static/fonts/` | SIL Open Font License 1.1; one `*-LICENSE` file per family |
| UMAP-JS (used by the single-cell playground) | `everyome/modules/singlecell/shared/playground/umap-js.min.js` | Apache License 2.0; `UMAP-JS-LICENSE` in the same folder |
| nf-core/rnaseq 3.27.0 parameter and samplesheet schemas | `everyome/modules/rna/bulk_de/pipeline/` | MIT; `LICENSE-nf-core-rnaseq` in the same folder |

Everyome runs, but does not include, other tools (for example nf-core/rnaseq,
Nextflow, STAR, Salmon, cutadapt, Scanpy, Harmony, PyDESeq2). Each analysis
lists the tools it uses and how to cite them in its manual and in each run's
write-up.
