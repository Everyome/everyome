# everyome-pipelines

The Nextflow pipelines that Everyome modules use (nf-core/rnaseq 3.27.0,
nf-core/scrnaseq 4.2.0, nf-core/genomeassembler 2.0.1 and nf-core/bacass 2.6.1), with the Nextflow plugins they need, pinned to exact
releases and checked by SHA-256. Install it next to Everyome:

```bash
pip install "everyome[all]==0.1.0a2" "everyome-pipelines==0.1.0a2"
```

When you press Run, Everyome copies the pipeline to your cluster once, checks
it there, and runs that copy offline. See Everyome's `docs/PIPELINES.md`.

Building (maintainers): `python -m everyome.core.pipelines build --into pipelines/everyome_pipelines/bundles`,
then `python -m build pipelines`. The build fails if anything fetched differs from the pinned checksums.
