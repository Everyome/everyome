# Pinned pipeline files

`nextflow_schema.json` and `schema_input.json` are copied unchanged from
nf-core/rnaseq release 3.27.0 (https://github.com/nf-core/rnaseq/tree/3.27.0),
MIT licence (see `LICENSE-nf-core-rnaseq`). Everyome builds the settings forms
from `nextflow_schema.json`, so every pipeline parameter can be changed.

To move to a newer release: copy both files from that release's tag, update
`revision` in `module.yaml`, and run the tests.
