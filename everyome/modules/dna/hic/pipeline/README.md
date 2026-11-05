# Pinned pipeline files

`nextflow_schema.json` and `schema_input.json` are copied unchanged from
nf-core/hic release 2.1.0 (https://github.com/nf-core/hic/tree/2.1.0),
MIT licence (see `LICENSE-nf-core-hic`). Everyome builds the settings forms
from `nextflow_schema.json`, so every pipeline parameter can be changed. The
pipeline itself ships in `everyome-pipelines` (pinned in `everyome/pipelines.lock.json`).

To move to a newer release: rebuild the bundle with `--update-lock`, copy both
files from that release's tag, update `revision` in `module.yaml`, check the output
paths the session reads (`../helpers.py` lists them; `../engine.py` finds the maps,
compartments and TADs), and run the tests.
