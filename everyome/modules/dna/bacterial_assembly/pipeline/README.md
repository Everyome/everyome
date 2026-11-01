# Pinned pipeline files

`nextflow_schema.json` and `schema_input.json` are copied unchanged from
nf-core/bacass release 2.6.1 (https://github.com/nf-core/bacass/tree/2.6.1),
MIT licence (see `LICENSE-nf-core-bacass`). Everyome builds the settings forms
from `nextflow_schema.json`, so every pipeline parameter can be changed. The
pipeline itself ships in `everyome-pipelines` (pinned in `everyome/pipelines.lock.json`).

To move to a newer release: rebuild the bundle with `--update-lock`, copy both
files from that release's tag, update `revision` in `module.yaml`, check the output
paths the explorer reads (`../explorer.py`), and run the tests.
