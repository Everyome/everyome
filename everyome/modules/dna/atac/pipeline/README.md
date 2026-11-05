# Pinned pipeline files

`nextflow_schema.json` and `schema_input.json` are copied unchanged from
nf-core/atacseq release 2.1.2 (https://github.com/nf-core/atacseq/tree/2.1.2),
MIT licence (see `LICENSE-nf-core-atacseq`). Everyome builds the settings forms
from `nextflow_schema.json`, so every pipeline parameter can be changed. The
pipeline itself ships in `everyome-pipelines` (pinned in `everyome/pipelines.lock.json`).

To move to a newer release: rebuild the bundle with `--update-lock`, copy both
files from that release's tag, update `revision` in `module.yaml`, check the output
paths the helpers and engine read (`../helpers.py`: peaks, FRiP, consensus counts,
bigWigs, MultiQC), and run the tests.
