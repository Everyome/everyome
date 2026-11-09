# Everyome — project brief for Claude Code

Everyome (*every -ome, for everyone*) is a free, open-source omics platform: a simple
GUI where every parameter stays editable, running locally or on the user's own Slurm
account over SSH. Created by **Helen R Horkan PhD** (Stowers Institute); keep the
attribution and "please cite" wording everywhere.

The design is in `docs/PLAN.md`. Read it before structural changes and keep it
current when decisions change.

## Layout

| Path | What |
|---|---|
| `everyome/core/backends.py` | `SSHBackend` (system ssh, key-only, ControlMaster) and `LocalBackend` (this computer; demo cluster when given fake Slurm) |
| `everyome/core/slurm.py` | sbatch/squeue/sacct/scancel, job naming, script headers |
| `everyome/core/manifest.py` | `module.yaml` spec v1: fields, stages, steps; value checking |
| `everyome/core/modules.py` | Finds modules: first-party, then reviewed community ones (when switched on), then an author's unreviewed folder (`EVERYOME_DEV_MODULES`) |
| `everyome/core/community.py` | Community loader: two off-switches (`BUILD_ENABLED`, `~/.everyome/community.json`), signed index, checksum and signature checks, safe unpacking, withdrawals |
| `everyome/registry/` | Registry tools: `checks.py` (automated checks), `bundle.py` (pack, sign, verify, approve, index), `python -m everyome.registry` |
| `registry-template/` | Starting point for the separate `everyome-modules` registry repo (not created yet) |
| `tests/fixtures/community_kmer/` | Test community module used by the registry dry run |
| `everyome/core/projects.py`, `runs.py` | Project folders; runs (params, job scripts, afterok chain, status, logs) |
| `everyome/core/engine.py`, `session.py`, `sessions.py` | Interactive engines (base class), the compute-node session server, and the app side (start, tunnel, ping, stop) |
| `everyome/suites.yaml`, `everyome/core/suites.py` | The suites, their tools (ready = has a module; otherwise planned), and the data-type and aim rules behind "Find the right analysis". A module's `suite` must be one of these ids and it must be listed as a tool |
| `everyome/core/nfschema.py` | Every parameter in a Nextflow pipeline's `nextflow_schema.json` becomes a field (its groups, defaults, choices; hidden ones under Advanced) |
| `everyome/core/records.py`, `rerun.py` | Run record (inputs with checksums, settings, jobs, versions, session steps) and the write-ups made from it: protocol, methods, references, rerun bundle. `python -m everyome.core.rerun BUNDLE NEW_DIR [--submit / --session]` repeats a run; the user runs it |
| `everyome/modules/spatial/visium/` | 10x Visium from Space Ranger output (live session only): reader, tissue view, spatially variable genes (Moran's I); filtering to export reuse `singlecell/cells.py` and `shared/cells_ui.js` (with the words spot and region) |
| `everyome/modules/protein/structure/` | Structure prediction: nf-core/proteinfold 2.0.0 (pinned; `batch.gpu` routes GPU tasks; `batch.check` = `helpers.check` refuses database-heavy methods without a reference folder), `structure.py` (PDB, pLDDT/PAE tables, Kabsch RMSD, domains from PAE), `engine.py` (predictions, structure, confidence, compare, export), canvas 3D view in `ui.js`; `demo_pipeline.py` stands in on the demo cluster |
| `everyome/modules/phylo/tree/` | Alignment and tree building: stages `stage.py` (MAFFT, trimAl, IQ-TREE in pinned containers; `demo_tools.py` stands in on the demo cluster), `newick.py` (read, write, re-root keeping support on its branch, midpoint, ladderize), `engine.py` (alignment check, model table, tree view and export), `demo_data.py` (simulated gene in 24 species) |
| `everyome/core/containers.py` | Containers for staged modules, pinned by digest in `batch.containers`; pulled once into `<pipelines folder>/containers`; `python -m everyome.core.containers pull` fills it in advance |
| `everyome/modules/dna/` | DNA suite: `genome_assembly/` (nf-core/genomeassembler 2.0.1) and `bacterial_assembly/` (nf-core/bacass 2.6.1) share `explorer.py` (finds assemblies, stats, BUSCO, genes; choose and export), `shared/assembly_ui.js`, guides and playground; `demo_genome.py` makes toy genomes with known repeats |
| `everyome/core/pipelines.py`, `everyome/pipelines.lock.json`, `pipelines/` | Shipped Nextflow pipelines: pinned bundles (code + plugins, SHA-256), built into the separate `everyome-pipelines` package; installed on the cluster when Run is pressed and run offline (`docs/PIPELINES.md`) |
| `everyome/core/server.py` | Local FastAPI app; `/api/s/*` is proxied to the session with its token |
| `everyome/core/shortcut.py` | `everyome --shortcut`: the desktop icon (Everyome.app on macOS, .desktop on Linux) and its background launcher; Quit in the app (`/api/quit`) stops it |
| `everyome/core/demo/` | Demo cluster setup and `fake_slurm.py` |
| `everyome/modules/<suite>/<name>/` | A module: `module.yaml`, stage code, engine, `ui.js`, `docs/manual.md`, `demo/` |
| `everyome/modules/molbio/primers/` | Primer design (a local module): Primer3 via primer3-py, Biopython for GenBank and restriction sites, synthetic demo plasmid |
| `everyome/modules/molbio/qpcr/` | qPCR analysis (a local module): reads instrument exports (QuantStudio, CFX, LightCycler, plain CSV/Excel; header rows skipped), replicate and NTC checks, standard-curve efficiencies, stepwise geNorm, efficiency-corrected NRQ (qbase) or 2^-ΔΔCq, Welch t + BH; made-up 384-well demo plate with planted answers |
| `everyome/modules/dna/annotation/` | Genome annotation: staged Helixer (GPU; models folder bound at ~/.local/share/Helixer/models) → gffread → BUSCO, images pinned by digest; stages can ask for `gpus` and take `partition_from` a setting |
| `everyome/modules/dna/variants/` | Variant calling: nf-core/sarek 3.11.0 germline (`batch.fixed` always sends `genome: null`, `igenomes_ignore: true`, so the user's FASTA is used; BQSR and the HaplotypeCaller filter skipped by default); engine reads every caller's per-sample VCF into a variant × caller × sample table (cached in session/), filters, caller agreement, group-separating variants, filtered VCF export |
| `everyome/modules/dna/atac/` | ATAC-seq: nf-core/atacseq 2.1.2 (pipeline 'sample' is the group, replicates numbered; narrow peaks by default; `check` refuses runs without macs_gsize/read_length; nf-validation pinned to 1.1.3 via `pipelines.UNVERSIONED`); engine reads consensus featureCounts, per-library peaks and FRiP, nearest TSS from the GTF; PyDESeq2 differential accessibility; region view (pyBigWig coverage if installed) |
| `everyome/modules/dna/hic/` | 3D genome (Hi-C): nf-core/hic 2.1.0 (`fixed` genome as for sarek; `check` refuses runs without an enzyme or sites); `cool.py` reads and writes .cool/.mcool with h5py (ICE, distance decay, eigenvector, insulation); session shows maps, decay, GC-oriented compartments and insulation TAD boundaries alongside HiCExplorer's |
| `everyome/modules/rna/riboseq/` | Ribo-seq: nf-core/riboseq 2.0.0; `batch.derived` writes anota2seq's contrasts file from the samples table unless the user gives one; session checks periodicity (riboWaltz P-sites), ORFs (catalogue or Ribo-TISH) and translational efficiency (paired log2 TE, moderated t; reads anota2seq's results too) |
| `everyome/modules/protein/function/` | Function annotation: staged InterProScan 5.78-109.0 (official image pinned by digest; data folder bound at /opt/interproscan/data; EBI lookup off by default) → TSV/JSON; session for overview, domain architecture, GO terms, export |
| `everyome/modules/protein/interactions/` | Interaction prediction: proteinfold with multimer defaults (schema from ../structure); structure Engine subclass + `interface.py` (Cα contacts, pDockQ, verdict); reuses the structure views via `E.proteinViews` |
| `everyome/modules/spatial/deconvolution/` | Cell types in spots: two staged GPU steps run cell2location 0.1.5 in Everyome's own Python (`deconvolution` extra, not in `all`; no maintained image exists), `demo_tools.py` stands in; session draws with `E.spatial(...).tissueSvg` (per-type abundance, main type, signatures, correlation between types) |
| `everyome/modules/spatial/hires/` | High-resolution spatial: Visium HD bins (via the Visium reader), Stereo-seq GEM summed into bins, Curio .h5ad; Visium engine subclass with a bin-size choice and thinned drawing over the image |
| `everyome/modules/spatial/imaging/` | Imaging spatial (Xenium, MERSCOPE, CosMx readers in `readers.py`); Visium engine subclass without an image, thinned drawing; shared spatial views in `spatial/shared/spatial_ui.js` (tissue, spatial genes, neighbourhood enrichment, also used by Visium) |
| `everyome/modules/singlecell/multiome/` | Multiome: reads Cell Ranger ARC outs (genes + peaks); CellsEngine on the RNA with clustering on RNA, ATAC (TF-IDF/LSI) or both (muon WNN); `words.modes` adds the choice to the shared cluster view |
| `everyome/modules/singlecell/scatac/` | Single-cell ATAC: staged chromap (pinned container) reads → fragments, then a SnapATAC2 session (tiles for clustering, gene activity for the shared CellsEngine markers/naming/export) |
| `everyome/modules/rna/abundance/` | RNA abundance: reads an nf-core/rnaseq results folder (TPM and counts); live session for sample checks, gene look-up and k-means expression patterns; no cluster stages |
| `everyome/modules/rna/bulk_de/` | Bulk RNA-seq: nf-core/rnaseq 3.27.0 (pinned; schemas in `pipeline/`) for reads to counts, then a PyDESeq2 live session; `demo_pipeline.py` stands in for Nextflow on the demo cluster |
| `everyome/modules/singlecell/cells.py`, `shared/`, `writeup.py` | Shared single-cell live session (filter incl. mitochondrial share, Harmony, Leiden, markers, naming, composition, export), its views (`shared/cells_ui.js`), guides, playground and methods text; used by SPLiT-seq and 10x |
| `everyome/modules/singlecell/scrna/` | Single-cell RNA-seq (10x and similar): nf-core/scrnaseq 4.2.0 (pinned; `batch.defaults` sets protocol 10XV3), then load a combined matrix and the shared steps; `demo_pipeline.py` stands in for Nextflow |
| `everyome/modules/singlecell/splitseq/` | SPLiTscape as a module: `workflow/` (the SPLiTscape bash and Python stages), `stage.py` (writes `reads.env` from settings, runs a stage or its demo stand-in), `helpers.py` (folder scan, read-QC report), `engine.py` (part 2), `ui.js`, `demo_data.py` |
| `everyome/static/` | App shell (`app.js`: home page, suite pages, views, shared viewers, markdown), `app.css`, `themes.json`, fonts |
| `design/themes/` | 68 cnidarian themes; `python design/themes/export_app_themes.py` regenerates `everyome/static/themes.json` |
| `tests/` | Manifest, Slurm naming, and an end-to-end demo flow (real session process) |
| `docs/PLAN.md` | Design plan and phases |

The source for porting is SPLiTscape in `~/Desktop/helomics` (`app/splitscape_app/`).

## Learning layer (every module)

A module is listed only with a manual (`learn.manual`) and example data
(`demo.data` or `demo.build`). Each also has a playground (`learn.playground`;
new ones use `Everyome.makePlayground({controls, defaults, presets, render})`) and
"how to read this" guides (`learn.guides: {name: docs/guides/<name>.md}`) placed
in its views with `H.guide("name")`. `tests/test_learning.py` checks every module
has all of them and that views and guides match.

## Writing a module

Copy `everyome/modules/tutorial/sequence_summary/`. Stage commands are bash lines
in `module.yaml` (`{python}` is the cluster's Python), run inside the run folder
with `$EVERYOME_PARAMS` (settings as JSON) and `$EVERYOME_RUN_DIR`. An interactive
engine subclasses `BaseEngine`, lists callable methods in `API`, and records
decisions with `_record()`. `ui.js` registers views with
`Everyome.registerViews(id, {stepId: async el => ...})` and calls the engine with
`Everyome.call(method, args)`. Other manifest hooks: `type: table` inputs (with
`columns`, optional `pattern`) and `fill` from a module `helpers` function;
`batch.report` (shown on the Run page via the `report` view); `demo.build`
(generates demo data once); `requires` (Python packages checked on the cluster);
`tools` (version commands recorded in the run record); `methods`
(function writing the draft methods text from the record); engines list in
`REPLAY` the calls that change the analysis, which are logged with their
arguments so `rerun --session` can replay them; `kind: [local]` modules run their engine inside the app (no job, no tunnel)
and need "This computer" or the demo cluster; "This computer" mode keeps
projects in `~/Everyome` (`EVERYOME_LOCAL_ROOT` moves it). `seqMap()` is the
shared plasmid/sequence map. `batch.engine: nextflow` (pipeline, pinned revision, bundled schema,
samplesheet from a table input, profile, skip list, demo stand-in, demo_values):
one head job runs the pipeline with a generated `nextflow.config` that names
every task `[<prefix>_]<user>_everyome_<module>_<task>`; only changed settings go in
`nf_params.json`; `learn.playground` (scripts loaded in order that define an object with `mount`,
`presetsHtml`, `applyPreset`, plus lede, intro, caveats and credit text).
Stages see `$EVERYOME_CPUS`, and `$EVERYOME_DEMO=1` on the demo cluster.

## Running

Python 3.10 or newer (3.9 is end-of-life and no longer on GitHub's Ubuntu runners);
CI tests 3.10 and 3.12 on Linux and macOS, plus a Linux job that runs the browser tests (any change to the
screens should keep `tests/test_browser.py` passing: no page errors, dialogs open once and close).

```bash
pip install -e ".[dev]" && everyome     # http://127.0.0.1:8777
pytest          # the SPLiT-seq end-to-end test is skipped without the singlecell extra
pytest tests/test_browser.py   # the screens in headless Chromium: .[browser] + python -m playwright install chromium
EVERYOME_DEMO_PAUSE=0.3 everyome   # faster pretend stages on the demo cluster
```

## Rules to keep

- **Stowers HPC policy:** Claude never submits sbatch jobs on Cerebro. The app submits
  only when the user clicks Run, under their own account. Don't add auto-submission.
- **Process naming:** jobs Everyome submits are the user's own (they press Run), so by default they have no
  prefix: `<user>_everyome_<module>_<stage>`. A site can set one (Connect page, or `EVERYOME_JOB_PREFIX`).
  Anything Claude itself starts here (tests, the demo app, scripts) must include `Claude` and the username:
  the test suite sets `EVERYOME_JOB_PREFIX=Claude` (`tests/conftest.py`), the preview launcher does too, and
  ad-hoc scripts are named `claude_<user>_*`.
- **Community modules** stay disabled (`BUILD_ENABLED = False`); switching on is Helen's
  decision. Every submission is reviewed against `docs/REVIEW_CHECKLIST.md`. Don't create the
  registry repo or add trusted keys without asking.
- **Data governance:** no PII/PHI in code or logs; never store passwords or keys.
- **Design:** House Style 1: Creation (the Entacmaea theme) in light mode is the default for new users; House Style 2: Creator is Gothic Cream, the SPLiTscape style. The logo is the Growth rings mark (`docs/brand/`; the app draws it in the active theme's colours with `ringsMark()` in `app.js`); every theme passes WCAG AA in light and dark. The app always opens on the home page.
- **Licence:** GPL-3.0-or-later (chosen 2026-11-03 on Stowers' advice; replaces MIT, which still covers 0.1.0a1 on PyPI). Copyright Helen R Horkan, who may also license her own code to others separately; outside contributions are GPL only. Third-party files keep their licences, listed in `THIRD_PARTY_NOTICES.md`.
- **Version:** one place, `everyome/__init__.py` (and `CITATION.cff`, `install.sh`, `pipelines/pyproject.toml`, the `pipelines` extra in `pyproject.toml`). On PyPI: 0.1.0a7 (2026-11-05, every listed module except molecular biology). 0.1.0a6 put Everyome in the Mac Dock. 0.1.0a5 added the desktop icon and Quit button. 0.1.0a4 was the first release by Trusted Publishing. Releases: pushing a `v…` tag runs `.github/workflows/release.yml` (Trusted Publishing, no tokens); a maintainer approves the upload in the `pypi` environment. Claude never approves it or uploads; steps in `docs/RELEASING.md`.
- Comments state intent; keep UI text plain-language and written for biologists.
- Literature references include a DOI or URL.
