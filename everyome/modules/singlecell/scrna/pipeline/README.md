# Pinned pipeline files

`nextflow_schema.json` and `schema_input.json` are copied unchanged from
nf-core/scrnaseq release 4.2.0 (https://github.com/nf-core/scrnaseq/tree/4.2.0),
MIT licence (see `LICENSE-nf-core-scrnaseq`). Everyome builds the settings forms
from `nextflow_schema.json`, so every pipeline parameter can be changed.

To move to a newer release: copy both files from that release's tag, update
`revision` in `module.yaml`, check the output paths in `helpers.py`
(`matrix_paths`) against the release's `docs/output.md`, and run the tests.
