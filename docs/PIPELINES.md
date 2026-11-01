# Pipelines on your cluster

Some Everyome analyses run a published Nextflow pipeline (for example
nf-core/rnaseq) on your cluster. Everyome **ships those pipelines**: you do not
need to let the cluster download code from GitHub, and every lab using the same
version of Everyome runs exactly the same pipeline code.

## What ships, and what does not

| Part | Ships with Everyome? | Where it ends up on the cluster |
|---|---|---|
| The pipeline's code, at a pinned release | Yes (`everyome-pipelines`) | `<pipelines folder>/<pipeline>-<release>/` |
| Nextflow plugins the pipeline needs | Yes (`everyome-pipelines`) | `<pipelines folder>/plugins/` |
| Software containers (one per tool) | No: several GB per pipeline, each under its own licence | `<pipelines folder>/containers/`, downloaded once and shared |
| Nextflow, Java and Apptainer | No: installed by your IT team | the cluster's software |

Each pipeline and plugin is checked against the SHA-256 recorded in
`everyome/pipelines.lock.json`: on your computer before it is sent, and again
on the cluster after it arrives. A file that does not match is not used.

## Install

```bash
pip install "everyome[all]==<version>" "everyome-pipelines==<version>"
```

Use the same version for both. Without `everyome-pipelines`, pipeline analyses
say so when you press Run.

## What happens when you press Run

1. The *Check before submitting* window says which pipeline will be copied, how
   big it is, and where it goes.
2. Everyome copies the pipeline and its plugins to the pipelines folder, checks
   them there and unpacks them. This happens once per folder; later runs reuse it.
3. The pipeline's job runs that copy with Nextflow offline (`NXF_OFFLINE=true`,
   plugins from the folder). Nextflow downloads each container the first time a
   tool is needed, into the shared `containers/` folder.

The run record names the pipeline release and the SHA-256 of the exact code
that ran, and lists the containers the pipeline uses.

## Choosing the pipelines folder

On the Connect page, *Where pipelines are kept*:

- **Empty** (the default): `~/.everyome/pipelines` in your own home folder.
  Simple, but each person downloads the containers again.
- **A shared folder** (recommended for a lab or institute): ask IT for a folder
  everyone can read. Pipelines and containers are then downloaded once for
  everyone, and runs start faster. The folder needs a few tens of GB.

## Clusters without internet access

If compute nodes cannot reach the internet, Nextflow cannot download containers
during a run. Fill the shared `containers/` folder once from a computer that can,
with nf-core's own tool (https://nf-co.re/docs/nf-core-tools/pipelines/download):

```bash
pip install nf-core
nf-core pipelines download nf-core/rnaseq --revision 3.27.0 --container-system singularity \
    --container-cache-utilisation copy --compress none --outdir rnaseq-offline
```

Then copy the images from `rnaseq-offline/singularity-images/` into the
cluster's `<pipelines folder>/containers/`. Everyome's copy of the pipeline is
still the one that runs; only the containers come from the download. Repeat
for each pipeline you use (`nf-core/scrnaseq --revision 4.2.0`, and so on).

## Job names

Each job is named `<prefix>_<you>_everyome_<module>_<stage>`. Some
institutions require a prefix on every job; set it on the Connect page
(*Job name prefix*), or leave it empty to start names with your username.

## For maintainers: adding or updating a pipeline

```bash
python -m everyome.core.pipelines build nf-core/<name>@<release> --into pipelines/everyome_pipelines/bundles --update-lock
```

This downloads the release from GitHub and its plugins from the Nextflow plugin
registry (checked against the registry's SHA-512), leaves out documentation,
tests and CI files, packs it reproducibly and records the checksums. Commit the
lock file; bundles are rebuilt for each release (`docs/RELEASING.md`) and the
build stops if anything differs from the lock. Then point the module at the
release (`batch.revision`), copy its `nextflow_schema.json`, update the
module's notes and `pipelines/NOTICE.md`, and run the tests.
