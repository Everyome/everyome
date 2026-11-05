# everyome-pipelines

The Nextflow pipelines that Everyome modules use (nf-core/rnaseq 3.27.0,
nf-core/scrnaseq 4.2.0, nf-core/genomeassembler 2.0.1, nf-core/bacass 2.6.1, nf-core/proteinfold 2.0.0,
nf-core/sarek 3.11.0, nf-core/hic 2.1.0, nf-core/riboseq 2.0.0 and nf-core/atacseq 2.1.2), with the Nextflow plugins they need, pinned to exact
releases and checked by SHA-256. Install it next to Everyome:

```bash
pip install "everyome[all]==<version>"   # the pipelines package comes with it, at the same version
```

When you press Run, Everyome copies the pipeline to your cluster once, checks
it there, and runs that copy offline. See Everyome's `docs/PIPELINES.md`.

Building (maintainers): `python -m everyome.core.pipelines build --into pipelines/everyome_pipelines/bundles`,
then `python -m build pipelines`. The build fails if anything fetched differs from the pinned checksums.
