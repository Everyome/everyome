# Third-party material in Everyome

Everyome itself is under the GNU General Public License, version 3 or later (`LICENSE`). It ships the following
material from others, each under its own licence, with the licence text next to it.

| What | Where | Licence |
|---|---|---|
| Fonts (Fontsource builds of open-source typefaces) | `everyome/static/fonts/` | SIL Open Font License 1.1; one `*-LICENSE` file per family |
| UMAP-JS (used by the single-cell playground) | `everyome/modules/singlecell/shared/playground/umap-js.min.js` | Apache License 2.0; `UMAP-JS-LICENSE` in the same folder |
| nf-core/rnaseq 3.27.0 parameter and samplesheet schemas | `everyome/modules/rna/bulk_de/pipeline/` | MIT; `LICENSE-nf-core-rnaseq` in the same folder |
| nf-core/scrnaseq 4.2.0 parameter and samplesheet schemas | `everyome/modules/singlecell/scrna/pipeline/` | MIT; `LICENSE-nf-core-scrnaseq` in the same folder |
| nf-core/genomeassembler 2.0.1 parameter and samplesheet schemas | `everyome/modules/dna/genome_assembly/pipeline/` | MIT; `LICENSE-nf-core-genomeassembler` in the same folder |
| nf-core/bacass 2.6.1 parameter and samplesheet schemas | `everyome/modules/dna/bacterial_assembly/pipeline/` | MIT; `LICENSE-nf-core-bacass` in the same folder |
| nf-core/proteinfold 2.0.0 parameter and samplesheet schemas | `everyome/modules/protein/structure/pipeline/` | MIT; `LICENSE-nf-core-proteinfold` in the same folder |

Everyome runs, but does not include, other tools (for example nf-core/rnaseq,
Nextflow, STAR, Salmon, cutadapt, Scanpy, Harmony, PyDESeq2). Each analysis
lists the tools it uses and how to cite them in its manual and in each run's
write-up.
