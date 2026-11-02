# Pinned pipeline files

`nextflow_schema.json` and `schema_input.json` are copied unchanged from
nf-core/proteinfold release 2.0.0 (https://github.com/nf-core/proteinfold/tree/2.0.0),
MIT licence (see `LICENSE-nf-core-proteinfold`). Everyome builds the settings forms
from `nextflow_schema.json`, so every pipeline parameter can be changed. The
pipeline itself ships in `everyome-pipelines` (pinned in `everyome/pipelines.lock.json`).

The prediction methods' model weights and databases are not part of the pipeline and
come under their own licences (for example, AlphaFold 3's weights must be requested
from Google DeepMind). See the module's manual.

To move to a newer release: rebuild the bundle with `--update-lock`, copy both
files from that release's tag, update `revision` in `module.yaml`, check the output
paths the explorer reads (`../engine.py`), and run the tests.
