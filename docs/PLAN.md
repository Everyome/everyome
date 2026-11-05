# Everyome — design plan

*Every -ome, for everyone.*

Created by **Helen R Horkan PhD** (Stowers Institute). Everyome grows out of
SPLiTscape; SPLiTscape stays a named module with its own citation.

Status (2026-10-31): phase 0 done except the external items (domain, PyPI at version 1, licence and trademark);
phase 1 code done and tested on the demo cluster — see the notes under section 9.

---

## 1. What Everyome is

A free, open-source platform that lets biologists run omics analyses through a
simple GUI, while every parameter stays visible and editable. It runs on the
user's own computer or on their own Slurm cluster account over SSH, so there is
no server to install and no data leaves their institution.

Every module comes with the three things a non-computational user needs to
trust a result: a manual, a playground to see what each setting does, and
guides that explain how to read the output. Every run produces a lab-book
protocol and an editable methods section.

### Principles

1. **Nothing hidden.** Every parameter has a form field, a default, a range and
   a plain-language explanation.
2. **Explain as you go.** QC metrics, plots and tables carry "how to read this"
   notes written for biologists.
3. **Reproducible by default.** Every run records exact inputs, parameters,
   tool versions and containers, and can be rerun from that record.
4. **Your account, your click.** Jobs are submitted only when the user presses
   Run, under their own account. No auto-submission.
5. **Stand on community pipelines.** Wrap well-tested pipelines (nf-core,
   Snakemake) for heavy batch work; spend our effort on the interactive,
   exploratory and explanatory layer.
6. **Accessible.** Every theme passes WCAG AA in light and dark (as today).

### Decisions so far

| Topic | Decision |
|---|---|
| Name | Everyome |
| Audience | Any lab, any Slurm cluster, plus local runs on a laptop. The first test cluster is one configuration among many. |
| Relation to SPLiTscape | New umbrella; SPLiTscape becomes the first single-cell module, attribution and citation kept |
| Licence | GPL-3.0-or-later (chosen 2026-11-03 with the host institution's advice) |
| Batch engine | Wrap nf-core / Snakemake pipelines |
| Community modules | Built in, **switched off** at launch; every submission reviewed before acceptance |

### Where Everyome sits

Galaxy is the closest existing platform: open source, GUI-driven, widely used
(Galaxy Community 2024, https://doi.org/10.1093/nar/gkae410). Everyome differs
in that it needs no Galaxy server: it drives the user's existing cluster account
over SSH, makes interactive exploration (not just batch tools) the centre of each
module, and ships learning material and publication-ready methods with every
run. The README should say this plainly.

---

## 2. Suites and first modules

A suite is just a label in module manifests, so new suites cost nothing in the
core. Candidate engines below must each be checked for release status and
maturity before we commit to them.

| Suite | First modules (in rough order) | Candidate batch engine | Interactive part (our value) |
|---|---|---|---|
| **Single cell** | SPLiT-seq (port of SPLiTscape); 10x scRNA-seq; scATAC; multiome | SPLiTscape stages 01–08; nf-core/scrnaseq | Filter, integrate, cluster, markers, annotate (SPLiTscape part 2, generalised) |
| **RNA** | Bulk differential expression; Ribo-seq; RNA abundance | nf-core/rnaseq, nf-core/differentialabundance, nf-core/riboseq | DE explorer: volcano, MA, heatmaps, gene sets |
| **DNA** | Variant/mutation calling; chromatin accessibility; 3D genome; assembly; annotation | nf-core/sarek, nf-core/atacseq, nf-core/hic, assembly/annotation pipelines (to evaluate) | Variant table and filters; genome browser; contact-map viewer |
| **Spatial** | Visium-style; probe-based imaging; single-cell spatial | nf-core/spatialvi, others to evaluate | Tissue overlay viewer, spatial clusters, neighbourhoods |
| **Protein** | Structure prediction; interaction prediction; function | nf-core/proteinfold (needs GPUs) | Structure viewer with confidence colouring; interface view |
| **Molecular biology** | Primer design; plasmid map and cloning simulation; digests | Local Python (Biopython, pydna, primer3-py) | Plasmid map editor; primer table |
| **Phylogenetics** | Align → trim → model → tree | MAFFT, trimAl, IQ-TREE / RAxML-NG (Snakemake or nf-core if available) | Tree viewer: re-root, collapse, colour by metadata |

---

## 3. Architecture

SPLiTscape already has the right shape; Everyome generalises it.

```
 Laptop                                     Cluster (user's own account)
┌───────────────────────────────┐          ┌───────────────────────────────────┐
│ Browser GUI (vanilla JS)       │          │ Batch runs: Slurm jobs            │
│  forms built from manifests    │   SSH    │  - Nextflow/Snakemake head job    │
│  shared viewers                │◄────────►│  - or simple staged bash jobs     │
│ Local server (FastAPI)         │ (key     │ Interactive session job           │
│  core: backends, projects,     │  only)   │  - module's interactive engine    │
│  runs, records, module loader  │          │  - checkpoints to project folder  │
│  local runner (molbio etc.)    │  tunnel  │ Apptainer containers              │
└───────────────────────────────┘          └───────────────────────────────────┘
```

### 3.1 Core (from SPLiTscape)

| Core component | Comes from | Change needed |
|---|---|---|
| Backends: local, SSH (BatchMode, ControlMaster), demo | `app/splitscape_app/cluster.py` | Make `LocalBackend` a first-class "run on this computer" option, not only the demo |
| Scheduler adapter | Slurm calls in `part1.py` | Pull into a `Scheduler` interface (Slurm first; leaves room for others) |
| Projects and file browsing | `server.py` `/api/project/*`, `/api/ls`, `/api/scan` | Project holds many runs of many modules |
| Run chain submission and status | `part1.py` `submit_chain`, `job_states`, `cancel`, `log_tail` | Driven by the module manifest instead of hard-coded `STAGES` |
| Interactive session | `server.py` `_session_script`, `analysis/server.py`, `session.json` | Session hosts whichever module engine is open |
| Checkpointed engine | `analysis/engine.py` | Becomes a base class; SPLiTscape engine subclasses it |
| Forms | `part1.py` `SETTINGS` + `/api/settings_schema` | Generated from manifest / `nextflow_schema.json` |
| Navigation | `app.js` `PAGES`, `VIEWS` | Sidebar built from the open module's steps |
| Themes and house style | `design/themes/`, `app.css`, `COL` / `PALETTE` | Unchanged; shared by all modules |
| Manuals and playground | `docs/_build_manual.py`, `play_core.js`, `play_ui.js` | Turned into a per-module docs template |
| Demo cluster and fake Slurm | `demo/` | Each module adds its own small demo dataset |

### 3.2 Three kinds of module

| Kind | Runs where | Examples | How |
|---|---|---|---|
| `local` | User's computer, in the app's own Python | Primer design, plasmid maps | Function call; results shown immediately |
| `batch` | Cluster Slurm jobs | nf-core/rnaseq, SPLiTscape 01–08, IQ-TREE | Chain of jobs or one Nextflow/Snakemake head job |
| `interactive` | Cluster session job (or locally for small data) | SPLiTscape part 2, DE explorer, tree viewer | Engine served through the SSH tunnel, checkpointed |

A module can combine kinds: SPLiTscape is `batch` (part 1) followed by
`interactive` (part 2).

### 3.3 Shared viewers (in core, reusable by any module)

Embedding/scatter plot (from SPLiTscape), bar/stacked/histogram/line charts
(already in `app.js`), dot plot, heatmap, volcano/MA plot, genome browser track,
contact map, plasmid map, phylogenetic tree, protein structure, tissue image
overlay. Each takes theme colours from `COL` / `PALETTE`.

### 3.4 Software on the cluster

Pipelines run their tools in containers, normally Apptainer on clusters
(Kurtzer et al. 2017, https://doi.org/10.1371/journal.pone.0177459). A site
needs Apptainer, Java and Nextflow (Di Tommaso et al. 2017,
https://doi.org/10.1038/nbt.3820) and/or Snakemake (Mölder et al. 2021,
https://doi.org/10.12688/f1000research.29032.2). The "readiness checks" page
already used by SPLiTscape grows to check these per module.

---

## 4. The module manifest

Each module is a folder with a `module.yaml`, its engine code, demo data and
docs. The core reads the manifest to build forms, the sidebar, job scripts and
the run record. The spec is versioned from day one (`spec: 1`) so community
modules don't break when the core changes.

> This sketch is the first design (2026-10-30). The format as built differs in places: `batch.schema` and a
> `samplesheet` block instead of `params_schema`, guides as a name-to-file map, `methods:` as a Python function,
> `licence: same as Everyome`. To start a new module, copy a working `module.yaml` of the same kind
> (for example `everyome/modules/dna/genome_assembly/module.yaml` or `everyome/modules/phylo/tree/module.yaml`).

```yaml
spec: 1
id: rna.bulk_de
name: Bulk RNA-seq differential expression
suite: rna
version: 0.1.0
authors: ["Helen R Horkan"]
licence: MIT
cite:
  - text: "Ewels et al. 2020, The nf-core framework"
    url: https://doi.org/10.1038/s41587-020-0439-x
kind: [batch, interactive]

inputs:
  - id: samplesheet
    type: table            # core shows a sheet editor with validation
    columns: [sample, fastq_1, fastq_2, condition]
  - id: genome
    type: reference        # chosen from the reference library

batch:
  engine: nextflow
  pipeline: nf-core/rnaseq
  revision: "x.y.z"        # pinned; never "latest"
  params_schema: nextflow_schema.json   # forms come from here
  profile: apptainer
  resources: {head_mem: 4G, head_time: "48:00:00"}

interactive:
  engine: everyome_rna.de.Engine
  steps:                    # becomes the sidebar
    - {id: design,  title: "Choose comparisons"}
    - {id: qc,      title: "Check samples"}
    - {id: results, title: "Explore results"}
    - {id: export,  title: "Export"}

learn:
  manual: docs/manual.md
  playground: docs/playground.js
  guides:                   # "how to read this" cards keyed by output
    - {for: qc.pca,        file: guides/pca.md}
    - {for: results.volcano, file: guides/volcano.md}

methods:
  template: methods.md.j2   # filled from the run record (section 5)

demo:
  data: demo/               # small dataset for the demo cluster and CI
```

For hand-written batch modules (like SPLiTscape stages 01–08), `batch.engine:
staged` lists stages and settings directly, replacing today's `STAGES` and
`SETTINGS` lists in `part1.py`.

---

## 5. Reproducibility: run record, protocol, methods

Every run writes a **run record** (`runs/<run_id>/record.json`) into the project:

| Field | Source |
|---|---|
| Module id and version, manifest spec | Manifest |
| Every parameter value, marking which differ from defaults | Forms |
| Input files with size and checksum | Core |
| Pipeline name and pinned revision; container images by digest | Manifest, Nextflow |
| Tool versions | Nextflow `pipeline_info/` software versions, or engine report |
| Job ids, nodes, start/end times, exit states | Scheduler |
| Interactive decisions in order (thresholds, cluster names, …) | Engine state log (SPLiTscape keeps the current step and annotations today; the full ordered history is new) |
| Who ran it | Cluster username only (no other personal data) |

From the record the core generates four exports:

1. **Rerun bundle** — params file, samplesheet and the exact command, so the run
   can be repeated without the GUI.
2. **Lab-book protocol** — a dated, step-by-step account: what was run, on what
   data, with which settings, what QC showed, which decisions were made and
   where outputs are. Markdown and DOCX/PDF, ready to paste into an ELN.
3. **Methods section** — publication-style prose filled from the module's
   `methods.md.j2` template, with tool versions and non-default parameters
   written in, and a reference list (with DOIs) for every tool used. Opened in
   an editor so the user can adjust it; edits saved alongside the record.
   (Recent nf-core pipelines already produce a methods description in their
   MultiQC report; use it as a starting point where it exists.)
4. **Citation list** — Everyome, the module, the pipeline and every tool, as
   BibTeX and as formatted text.

---

## 6. Learning layer (every module)

| Piece | What it is | Builds on |
|---|---|---|
| **Manual** | Per step: what it does, why, inputs/outputs, settings, how to read the output, example figures | `docs/_build_manual.py`, `splitscape.html` + mobile version |
| **Playground** | Toy data in the browser; move a setting and watch the result change | `docs/play_core.js`, `play_ui.js` |
| **Interpretation guides** | Short "how to read this" cards attached to each QC metric, plot and table, with good/bad examples and what to do next | New; shown inline next to the output |
| **Demo data** | Small dataset that runs end to end on the demo cluster | `demo/make_demo.py` |

The manifest's `learn` block wires these in; the core refuses to list a module
in the catalogue without a manual and demo data.

---

## 7. Community modules (built, switched off)

Modules run code on users' cluster accounts, so a malicious or careless module
could read or damage their data. The registry is therefore off by default and
gated by review.

**At launch**

- Registry code exists but is disabled by a setting that only the install's
  config can change (not a per-user toggle).
- Only first-party modules shipped in the Everyome repository load.
- Developers can load a module from a local folder with a clear "unreviewed
  module" warning, for building and testing only.

**When switched on**

1. Submission is a pull request to a separate `everyome-modules` registry repo.
2. Automated checks: manifest validates against the spec; licence is
   OSI-approved; containers pinned by digest; pipeline revisions pinned; demo
   data runs end to end in CI; no network access outside declared sources.
3. Human review by at least one maintainer: reads the code and job scripts,
   checks the science and the learning material.
4. Accepted modules are published as signed, version-pinned releases; the app
   verifies the signature before loading.
5. Before any run, the app shows exactly what will be submitted (job scripts,
   containers). SPLiTscape doesn't do this yet; the core should for every module.
6. A maintainer can revoke a version; the app warns users who have it.

Also needed before switching on: `CONTRIBUTING.md`, a code of conduct, a
module-author guide and a review checklist.

---

## 8. Repository layout

```
everyome/
  core/           backends, scheduler, projects, runs, records, module loader, server
  static/         app shell, shared viewers, themes
  modules/
    singlecell/splitseq/     SPLiTscape (module.yaml, engine, workflow/, docs/, demo/)
    rna/bulk_de/
    molbio/primers/
  docs/           platform manual, module-author guide, spec reference
  design/themes/  unchanged
tests/            core unit tests; end-to-end demo flows per module
```

SPLiTscape's `workflow/`, `config/` templates and manuals move under
`modules/singlecell/splitseq/`; its README, `CITATION.cff` and "please cite"
wording move with it.

---

## 9. Phases

Each phase ends with a check you can see working.

| # | Phase | Main work | Done when |
|---|---|---|---|
| 0 | Groundwork | Reserve GitHub org, domain, PyPI name; confirm licence and trademark with tech transfer; new repo with CI | Empty `everyome` package installs and CI is green |
| 1 | Core extraction | Pull backends, scheduler, projects, sessions, themes out of SPLiTscape into `everyome.core`; define manifest spec v1 and module loader | Core runs with a "hello" test module on local, demo and SSH backends |
| 2 | SPLiTscape as a module | Port `part1.py` stages/settings to a manifest; engine subclasses the core engine; move Hydra-specific defaults (`DIAMOND_CFG` in `engine.py`) into module config | Full SPLiTscape demo flow passes in the headless browser, same as today |
| 3 | Run records and exports | Record, rerun bundle, lab-book protocol, methods editor, citations | SPLiTscape demo run exports all four, and the rerun bundle reproduces it |
| 4 | Batch engine + bulk RNA | Nextflow runner (head job, progress from trace, resume); forms from `nextflow_schema.json`; bulk DE module with DE explorer | Bulk RNA demo runs end to end on the demo cluster and a real test on a small public dataset |
| 5 | Local modules | Local runner; primer design module with plasmid map viewer | Primer design works with no cluster connected |
| 6 | Learning layer | Generalise manual/playground builder; interpretation-guide cards; catalogue rule (no manual → not listed) | All three modules have manual, playground, guides |
| 7 | Community registry (off) | Registry repo, CI checks, signing, loader verification, review checklist | A test module goes through review in a dry run; registry stays disabled ✓ |
| 8 | Suite roll-out | Add modules suite by suite (section 2), each with demo data and learning material | — ongoing |

Phases 5 and 6 can run alongside 4 once phase 3 is done.

### Spatial suite: imaging spatial (2026-11-04)

Xenium, MERSCOPE and CosMx straight from instrument output, read with small pandas/scanpy readers (no spatialdata
dependency; control probes dropped). Subclass of the Visium engine; tissue view without an image, thinned to 40,000
cells for drawing only. New for all spatial modules (Visium too): neighbourhood enrichment, labels shuffled within each
section, z-scores plus log2 ratio to chance (the heatmap colours by the ratio; z-scores grow with cell numbers).
Visium's tissue view moved to `spatial/shared/spatial_ui.js`. Not in this version: re-segmentation (nf-core/sopa needs
Nextflow 25.10.4 and is a later option), transcript-level views, image overlays.

### Single cell suite: multiome (2026-11-04)

Starts from Cell Ranger ARC's `outs` (not bundled: 10x EULA), like Visium starts from Space Ranger. `kind:
[interactive]`. CellsEngine on the RNA (shared filtering, markers, naming, export); clustering adds a choice (shared
cluster view, `words.modes`): RNA (PCA), ATAC (TF-IDF + LSI, first component dropped) or joint (muon WNN, per-cell
modality weights kept as `rna_weight`). Demo built so RNA alone separates two types cleanly and joint all four; the
flow test checks both. Not in this version: peak-to-gene links, motif analysis.

### Single cell suite: scATAC-seq (2026-11-04)

No released nf-core pipeline exists for scATAC (checked 2026-11-04), so the cluster part is one staged step: chromap
0.3.2 (MIT, BioContainers image pinned by digest) with its ATAC preset writes fragments per sample; samples can give
fragments instead (Cell Ranger ATAC output; Cell Ranger itself is not bundled: 10x EULA). The session builds on
CellsEngine: SnapATAC2 reads fragments (TSS enrichment, fragment sizes), keeps a 500-bp tile matrix for clustering
(spectral embedding, optional Harmony, Leiden, UMAP) and a gene activity matrix as X, so the shared markers, naming,
comparison and export views work unchanged. cells_ui.js gained `words` for the counted and measured quantities.
Not in this version: per-cluster peaks (MACS3) and motif enrichment.

### RNA suite: RNA abundance (2026-11-04)

Expression across samples without a two-group test (Helen, 2026-11-04). Starts from an nf-core/rnaseq results folder
(any route: star_salmon, salmon, star_rsem, kallisto), so it works after the Differential expression module or a run
made elsewhere. Live session only (`kind: [interactive]`, 1 CPU, 8 GB): samples compared on log2 of
median-of-ratios-normalised counts (falls back to log2 TPM + 1 without a count table); PCA and correlation; any
gene's TPM; most expressed genes; the most variable genes as z-scores, clustered with k-means (k-means++, fixed
seed, clusters numbered by the sample where they peak) so reruns are identical. nf-core/differentialabundance
(contrasts, R reports) was considered and left out: it needs Nextflow 25.10.4 and duplicates the DE module.

### Protein suite: structure prediction (2026-11-01)

With this, every suite has at least one tool (Helen's release gate).

- **Structure prediction**, `protein.structure`: nf-core/proteinfold 2.0.0 (needs
  Nextflow 25.10.2 or newer), shipped and pinned like the other pipelines. Every
  method it offers can be chosen, several at once; AlphaFold2 is the default
  (the pipeline's own). Proteins come from a folder of FASTA files (one
  prediction per file; several sequences in a file make a complex).
- **GPUs** (new in the core, `batch.gpu`): when *Use GPU* is on, the run adds the
  pipeline's `gpu` profile, and the generated Nextflow config sends tasks labelled
  `process_gpu` to the *GPU partition* with `--gres=gpu:N` in `clusterOptions`
  (Slurm ignores Nextflow's `accelerator` setting).
- **A module check before a run** (new in the core, `batch.check`): the module
  refuses AlphaFold2, ColabFold and the other database-heavy methods when no
  reference data folder is set, rather than letting the pipeline download
  hundreds of GB to TB into the run folder.
- Live session: every prediction (pLDDT bands, pTM, ipTM, confident domains from
  pLDDT and PAE by a simple, documented rule); one structure in a small canvas 3D
  view (Cα trace coloured by pLDDT, domain or chain), pLDDT along the sequence for
  every ranked model, and the PAE map with domains marked; methods compared by
  RMSD (all, confident residues, and each domain on its own, Kabsch); export of
  whole or trimmed models (by pLDDT or to the domains) and a summary table.
- The lock's container scan now reads double-quoted names too, so the lists now
  include the prediction images (and a few images missed before in the
  single-cell and genome assembly pipelines). Code checksums are unchanged.
- Demo: three made-up proteins (two domains on a linker; a compact hairpin; a
  disordered protein); the stand-in pipeline writes the real output layout, and
  its ESMFold places the second domain differently. Test in
  `tests/test_protein_flow.py`, including an exact repeat.
- Playground: a two-domain protein whose true order, packing, linker and loose
  ends you set; shows pLDDT, PAE, domains found and pTM.
- Not yet: a real GPU run (GPU routing, Apptainer `--nv`, databases); complexes
  with nucleic acids or ligands (YAML or JSON inputs for AlphaFold 3 and Boltz);
  Foldseek results in the session; side chains in the viewer.

### Phylogenetics suite: alignment and tree building (2026-11-01)

- **Alignment and tree building**, `phylo.tree`: three cluster stages, MAFFT
  7.525 (align), trimAl 1.5.1 (trim) and IQ-TREE 3.1.4 (ModelFinder, maximum
  likelihood, UFBoot and SH-aLRT), then a live session. No Nextflow: a staged
  module whose tools run in containers.
- **Containers pinned by digest** (new in the core, `core/containers.py`): a staged
  module lists `batch.containers` as `repository:tag@sha256:<digest>`; the manifest
  refuses a tag without a digest. Jobs pull each image once into
  `<pipelines folder>/containers` (shared with the Nextflow pipelines) and run the
  tool with `apptainer exec`; the run record and methods name each image and
  digest. `python -m everyome.core.containers pull` fills the folder in advance
  for clusters without internet on compute nodes.
- Live session: check the alignment (trimmed columns shown, partial or divergent
  sequences flagged, never removed); the model table and support histograms; the
  tree viewer (root at midpoint, on an outgroup or on a clicked branch; support
  moves with its branch; collapse, ladderize, cladogram; colour by the user's
  table, with a check of whether each value forms one clade); export of the
  rooted Newick, an SVG figure with legend, and tip and group tables.
- Demo: one gene simulated in 22 cnidarians and two bilaterian outgroups (real
  species, simulated sequences, insertions and deletions, one partial sequence,
  one weakly supported branch); quick stand-ins replace the three tools on the
  demo cluster. Test in `tests/test_phylo_flow.py`, including the real tool
  commands (not run) and an exact repeat.
- Playground: six species, neighbour joining with bootstrap; alignment length,
  short inner branches, long-branch attraction and corrected distances.
- Not yet: a real cluster run (Apptainer pulling by digest; IQ-TREE 3's `iqtree3`
  command in the image), RAxML-NG, partitioned (multi-gene) analyses, circular
  tree layout.

### Spatial suite: 10x Visium (2026-11-01)

- **Spatial transcriptomics (10x Visium)**, `spatial.visium`: starts from Space
  Ranger's `outs` folders (what facilities hand back), so it is a live session
  only, with no pipeline. nf-core/spatialvi has no release to pin yet.
- Spots go through the shared single-cell steps (filter with the mitochondrial
  share, Harmony, Leiden, markers, naming, composition, export). The shared views
  now take a module's words, so they say spot and region here.
- New: a reader for Space Ranger output (`.h5` or matrix folder; positions as
  csv, older headerless csv or Visium HD parquet; scale factors and image), the
  tissue view (spots on the tissue image, coloured by cluster, region, gene or
  quality, adjustable opacity), and spatially variable genes by Moran's I on each
  section's six nearest spots.
- Demo: two toy skin sections in Space Ranger's layout (four layers; an immune
  infiltrate only in the treated one; damaged spots at the cut edge); test in
  `tests/test_visium_flow.py`, including an exact repeat.
- Playground: what a spot records (spot size, depth, sharp or soft boundaries,
  pattern or none), with Moran's I.
- Not yet: real Visium data; Visium HD tested only by format (binned folders read
  like standard ones); deconvolution of cell types within spots.

### DNA suite: genome assembly and annotation (2026-10-31)

Two modules sharing one live session (`dna/explorer.py`, `dna/shared/`):

- **Genome assembly (PacBio, Nanopore, Illumina)**, `dna.assembly`: nf-core/genomeassembler
  2.0.1. One table row per assembly, so one run compares strategies: Nanopore
  alone (Flye), HiFi alone (hifiasm), both together (hifiasm hybrid), or each
  assembled and scaffolded onto the other (RagTag); Illumina reads polish (Pilon)
  and check (Merqury). Genes are lifted over from a related genome (Liftoff).
  Everyome turns BUSCO and QUAST on. Illumina-only assembly is not possible here.
- **Bacterial genome assembly and annotation**, `dna.bacterial`: nf-core/bacass
  2.6.1. Illumina, long reads or hybrid; several assemblers per run to compare;
  genes by Prokka or Bakta. Starts from settings the pipeline accepts
  (assembly type hybrid, Unicycler; contamination screening off until databases
  are given): bacass's own assembler default lists every assembler, which no
  assembly type accepts.
- **Explorer:** finds every assembly either pipeline writes (any stage:
  assembly, polished, scaffold), computes its statistics itself (size, contigs,
  N50/L50/N90, GC, gaps), reads BUSCO short summaries and pairs gene annotations
  by contig names, sample and tool. Views: compare (table, Nx curves, BUSCO
  bars), contigs (lengths, GC against length), genes (summary, lengths,
  search), choose and export (`results/final/`, with a comparison table and the
  reason in the record). Pure Python, so any cluster Python with Everyome runs it.
- **Core additions:** samplesheet columns can be renamed, derived (true/false from
  another column), fixed, or dropped when empty, with any separator and empty
  value (bacass reads a TSV with NA); tables can require one of several columns per row.
- **Demo:** toy genomes with repeats of known sizes, so each strategy breaks where
  real reads would: three chromosomes for the eukaryote (scaffolding recovers
  all three; Nanopore errors lower BUSCO until polished), and a bacterium with a
  chromosome and two plasmids (short reads break at rRNA operons and insertion
  sequences; most long-read assemblers lose the small plasmid; Unicycler hybrid
  recovers all three). Tests: `tests/test_assembly_flow.py`.
- **De novo eukaryotic gene annotation** is left for its own tool: no released
  nf-core pipeline (genomeannotator is archived), and BRAKER3 depends on GeneMark,
  whose licence restricts redistribution.
- **Not yet run with real Nextflow or data**; check output paths against real
  runs (`explorer.py` reads by pattern, not fixed paths).

### Shipped pipelines and job-name prefix (2026-10-31)

- **Pipelines ship with Everyome** instead of being fetched from GitHub at run
  time. `everyome/pipelines.lock.json` pins each pipeline release and its Nextflow
  plugins by SHA-256 (and lists its containers); `python -m everyome.core.pipelines
  build` makes reproducible bundles (docs, tests and CI files left out) that go
  in a separate package, `everyome-pipelines` (`pipelines/`; about 28 MB, mostly
  nf-core/scrnaseq's 10x barcode lists). A module can only use a pipeline in the lock.
- **Pressing Run** copies the bundle to the site's pipelines folder (checked on
  both sides; once per folder), then the head job runs that copy with
  `NXF_OFFLINE=true`, the shipped plugins, and a shared container folder beside it.
  The *Check before submitting* window says what will be copied and where.
  Reruns use the copy already on the cluster. The record gives the code's SHA-256,
  plugins and container list.
- **Containers** are not shipped (GBs, separate licences): Nextflow downloads
  them once into the shared folder; air-gapped sites fill it with
  `nf-core pipelines download` (docs/PIPELINES.md).
- **Job-name prefix** (open question 1, resolved): a site setting on the Connect
  page, saved with the connection and stored in each run; default `Claude`, which
  the first test site requires; empty means names start with the username.
- Tested: bundles build reproducibly from GitHub and the plugin registry; both
  real bundles install into a cluster-style folder; tampered or missing files are
  refused; Run installs then submits (`tests/test_pipelines.py`). **Not yet run
  with real Nextflow**: whether offline mode finds the shipped plugins and still
  pulls containers on a cluster with internet must be confirmed on a real cluster.

### Phase 8 notes: single-cell RNA-seq (2026-10-31)

First roll-out module: **Single-cell RNA-seq (10x and similar)**, `singlecell.scrna`.

- **Cluster part:** nf-core/scrnaseq **4.2.0** (pinned; schema in `pipeline/`).
  Every pipeline setting is on the settings page. A module can now start a
  pipeline parameter from its own default (`batch.defaults`): here `protocol` is
  `10XV3`, because the default aligner (simpleaf) cannot detect the chemistry;
  the pipeline's own default (`auto`) is kept so the parameter file stays complete.
- **Live session:** load one of the pipeline's combined matrices (CellBender's
  by default), use gene symbols, add condition and batch from the samples
  table, then the same filter, cluster, markers, naming and export steps as
  SPLiT-seq, plus a **mitochondrial share** filter (setting: *Mitochondrial genes*).
- **Shared single-cell code:** SPLiT-seq's part 2 was split into
  `singlecell/cells.py` (engine), `singlecell/shared/cells_ui.js` (views),
  `singlecell/writeup.py` (methods text), shared guides and the playground in
  `singlecell/shared/`. A module's `interactive.ui` may now list several files
  (shared views first). Both modules' tests pass unchanged in what they check.
- **Demo:** four 10x-style samples of a toy blood-like tissue (six cell types with
  well-known markers, interferon-responding monocytes only in treated samples,
  a moderate day-to-day batch effect, damaged cells, doublets, empty droplets).
  `tests/test_scrna_flow.py` checks the session finds every type's markers,
  removes the damaged cells, mixes batches after Harmony, sees the treated-only
  type, writes the methods, and that the rerun bundle reproduces the composition.
- **Not yet checked on real data or a real cluster** (as for bulk RNA): output
  paths follow nf-core/scrnaseq 4.2.0's documentation (`results/<aligner>/mtx_conversions/combined_<kind>_matrix.h5ad`);
  confirm on a small public 10x dataset on a real cluster, including whether an empty
  *Expected cells* column is accepted by the pipeline.

### Phase 7 notes (2026-10-31)

Built and dry-run tested; **the registry stays switched off** (`BUILD_ENABLED =
False` in `everyome/core/community.py`, and a site must also set `"enabled": true`
in `~/.everyome/community.json`; both locks must be open).

- **Scope for now:** community modules are local only (`kind: [local]`). Cluster
  modules would need their code installed on each cluster; left for later.
- **Automated checks** (`everyome/registry/checks.py`, `python -m everyome.registry
  check`): manifest valid, id `community.<name>`, code only in its own package
  `everyome_c_community_<name>`, open-source licence and LICENSE file, manual,
  example data, playground and guides, tests, source only (no binaries, archives
  or hidden files), under 20 MB. Warnings for a human: network imports, running
  programs, `eval`/`exec`, environment and home-folder access, credential-like
  strings, browser web requests. The checks never run the module's code.
- **Signing:** OpenSSH (`ssh-keygen -Y sign/verify`, namespace `everyome-module`);
  no new dependency, maintainers use their own SSH keys. Reproducible archives
  (same files, same bytes) so a checksum can be checked by anyone.
- **Registry layout and tools:** `approve` (check, pack, sign, record reviewer),
  `index` (build and sign), `revoke`. Template for the separate registry repo in
  `registry-template/`, with a CI workflow that runs on `pull_request` only (no
  secrets or write token for submitted code). The repo itself is not created yet.
- **Loader:** verifies the index signature against the site's trusted keys every
  time it is read, the archive's SHA-256 and signature, unpacks only ordinary
  files inside its folder, re-runs the checks, and stops offering withdrawn
  versions. Modules show **Community · reviewed** (with the reviewer and date).
- **Authors** can load their own folder with `EVERYOME_DEV_MODULES`; it shows as
  **Unreviewed** and is never fetched from anywhere.
- **Dry run** (`tests/test_registry.py`): a test module (`tests/fixtures/community_kmer`,
  a k-mer spectrum) is checked, approved, signed, indexed, installed and run in
  the app with its record and methods; a tampered archive, an index signed by an
  unknown key, a withdrawn version and unsafe archives (path escape, absolute
  paths, symlinks, hidden files) are all refused; with the switch off nothing loads.
- Docs: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `docs/MODULE_AUTHORS.md`,
  `docs/REVIEW_CHECKLIST.md`.
- Before switching on: create the registry repo, name maintainers and their keys,
  a contact address for conduct reports, and decide whether the switch should
  also be settable by a site-wide (not per-user) config.

### Phase 6 notes (2026-10-31)

- **Guides:** 26 short "how to read this" notes (tutorial 3, SPLiT-seq 11, bulk
  RNA 8, primers 4), each a fold-out next to the chart or table it explains: what
  it shows, what good looks like, what to do if it does not.
- **Playground builder** (`Everyome.makePlayground`): controls, presets and a
  render function; new playgrounds for bulk RNA (a simulated experiment scored
  against the truth: power, false discoveries, misses; moderated t-test as a
  stand-in for DESeq2), primers (melting temperature with the same
  nearest-neighbour model as Primer3, checked to match it exactly) and the
  tutorial (why short sequences give noisy GC; mixed organisms).
- **Catalogue rule:** a module without a manual and example data is not listed.
  A test keeps every module complete (manual, example data, playground, guides,
  and views and guides that match).
- Checked in the browser: each playground's scenarios behave as their
  descriptions say. Two were first wrong and fixed: the bulk RNA playground's
  test was too weak and its genes too lowly expressed (three replicates found
  nothing); the primer playground used a textbook Tm formula about 8 °C below
  Primer3.

### Phase 5 notes (2026-10-31)

- **Local modules run in the app.** `kind: [local]` modules run their engine in
  the Everyome app process: no job, no session, no tunnel. Their calls, logging,
  records and reruns work exactly like cluster modules.
- **"This computer" mode** (a third choice on Connect) needs no cluster. Projects
  and example data live in `~/Everyome`. Cluster modules are shown but
  disabled there, with a note to connect to a cluster or the demo.
- **Shared sequence map** (`seqMap`): circular for plasmids, linear otherwise,
  with features, single-cut restriction sites, primers and a highlighted region.
- **New module `molbio.primers`** (0.1.0): reads GenBank, FASTA or pasted
  sequences; you choose the region; Primer3 (primer3-py) suggests pairs, with the
  common settings as fields and any other Primer3 setting as `NAME=value` lines.
  You can check your own primers (Tm, GC, hairpin, self- and pair-dimer ΔG, where
  they bind, product size) and export all pairs, an order sheet and a GenBank
  file with the primers added. The demo plasmid is synthetic and labelled as such.
- Records now find versions by installed package name, so `primer3`/`Bio` report
  primer3-py and Biopython versions. Tested with no cluster connected, in pytest
  and the browser, including an exact repeat from the rerun bundle.

**Not done yet:** local modules can't be used while connected to a real cluster
over SSH (their files would be on the cluster). For now, switch to "This
computer". Products crossing the origin of a circular plasmid aren't designed.

### Phase 4 notes (2026-10-31)

New module `rna.bulk_de` (0.1.0): nf-core/rnaseq **3.27.0** turns reads into gene
counts on the cluster, then a live session checks samples (library sizes, PCA,
sample correlation), compares two conditions with DESeq2 via PyDESeq2, explores
results (volcano, MA, searchable table, per-gene counts) and exports them.

- **Nextflow engine** in the core: the module names a pipeline, a pinned
  release and the pipeline's own `nextflow_schema.json` (bundled, MIT, from that
  release). All 123 analysis parameters become editable fields in the pipeline's
  groups (specialist ones under *Advanced*); only changed values reach the
  pipeline. One head job runs `nextflow run … -r 3.27.0 -profile apptainer
  -resume`; a generated `nextflow.config` sends the pipeline's tasks to Slurm,
  each named `<user>_everyome_rna_bulk_de_<task>` (with the site's prefix, if any). Progress comes from the
  trace file; the MultiQC report opens sandboxed from the Run page.
- The samplesheet is a table filled from a reads folder (condition guessed from
  sample names, then checked by the user); extra columns stay out of the CSV.
- Records name the pipeline release and profile; methods text covers the
  pipeline, any changed settings, filtering, the DESeq2 design and the results.
- Tested on the demo cluster (a stand-in writes the pipeline's outputs): DESeq2
  recovers the planted changes with few false calls, and a rerun from the bundle
  reproduces the significant-gene table exactly.

**Not done from the "done when":** a real run on a small public dataset. This
Mac has no Nextflow, Java runtime or Apptainer, so the pipeline has not run for
real anywhere yet. That needs a cluster with those three (the first test cluster, once IT
confirms) and a small public dataset such as nf-core's own test data.

Also fixed: a colour helper (`hexRgb`) missing since Phase 2, which broke the
SPLiT-seq dot plot and colour-by-gene, and the new correlation heatmap. Nothing
tests the browser code automatically yet, which is how it slipped through.

### Phase 3 notes (2026-10-31)

Every run now has a **Record and write-up** page. *Build the record* gathers the
inputs (size and SHA-256 checksum up to 2 GB), every setting against its
default, the cluster jobs, software versions (Python packages from the
module's `requires`, command-line tools from its `tools`), the live-session
steps in order, the results and the references, into `record/record.json`. From
it Everyome writes `protocol.md` (shown, downloadable, printable to PDF),
`methods.md` (a draft each module writes; the user's edits are saved separately
as `methods_edited.md`), `references.txt` / `.bib`, and `rerun/`.

`python -m everyome.core.rerun record/rerun NEW_DIR --submit` writes and submits
the same job scripts into a new folder (the user runs it; without `--submit` it
only writes and shows them); `--session` then replays the logged session calls.
Tested on the demo cluster: repeating the tutorial run and the SPLiT-seq run
gives identical results (filter, clusters, names, composition tables).

Not done yet: DOCX export (print to PDF covers sharing for now), container
digests (nothing runs in containers until the Nextflow engine in phase 4), and
checksums of files inside input folders (folders list names and sizes).

### Phase 2 notes (2026-10-31)

SPLiTscape is now the module `singlecell.splitseq` (version 1.0.0). The SPLiTscape
bash and Python stages are copied unchanged except one fix: with no preferred
species set, gene names fall back to the most informative match. The original
SPLiTscape repository is untouched.

- Settings come from the manifest; `stage.py` writes `reads.env` per run and
  finds the sequencing runs from the reads folder. Threads follow the job's CPUs.
- The Hydra and Hydractinia name preferences (`DIAMOND_CFG`) are now two
  settings, empty by default.
- The engine reads the count matrices named by *Minimum genes per cell*
  (SPLiTscape always read `G50`), and records each decision in order.
- Core additions this needed: table inputs filled by a module helper (folder
  scan), a batch report hook (read QC), file upload into the run, a check that
  the cluster's Python has the module's packages, generated demo data, and
  shared viewers (embedding map, log histograms, stacked bars, knee plot, dot plot).
- Tested end to end on the demo cluster in pytest (about a minute) and in the
  browser. Not yet run on real reads or on a real cluster.
- Follow-up (same day): the SPLiTscape playground is back, as the module's
  Playground page under *Learn* (theme-aware, runs in the browser, UMAP-JS under
  Apache 2.0). Merging with an atlas or other dataset is now optional at both
  points: the input can be left empty, and the Combine step has a tick box. With
  no atlas the sublibraries are analysed on their own, for example to build a
  first atlas or a standalone dataset.

### Phase 1 notes (2026-10-31)

Built: backends, Slurm calls, projects, staged runs with a script preview before
submitting, interactive sessions (generic `BaseEngine`, token-guarded session
server, tunnel and proxy), manifest spec v1 with value checking, module loader
with community modules switched off, demo cluster, and the GUI shell with forms
built from manifests. Test module: `tutorial.sequence_summary` (two stages, one
interactive step, manual, demo data). Tested end to end on the demo cluster, in
pytest and in the browser.

Differences from section 4: `inputs` and `params` share one field schema
(types text, int, float, bool, choice, file, folder); the batch engine so far is
`staged` (Nextflow arrives in phase 4); stage commands are bash lines with
`{python}`; a module may ship its own views as `interactive.ui`.

Added after the plan: a home page that explains Everyome, shows every suite as a
box (ready, or "in progress" with its planned tools), and a "Find the right
analysis" form. People choose their data types and aims; simple rules in
`everyome/suites.yaml` rank the tools that fit, and once a data type is named
only tools that can use it are suggested. Answers are not stored or sent anywhere.

Not yet done from the phase 1 "done when": the SSH backend is carried over
unchanged from SPLiTscape (where it was tested against a local sshd) but has
not been re-tested in Everyome; local-only modules (`kind: local`) are defined
in the spec but have no runner until phase 5.

---

## 10. Prerequisites outside the code

- **Cluster IT at the first test site** (already open for SPLiTscape): SSH-key logins from laptops,
  port forwarding to compute nodes, partition/time limits for sessions, a shared
  install location. New for Everyome: Apptainer, Java and Nextflow availability
  on that cluster; GPU partition access for the protein suite.
- **Tech transfer at the host institution**: licence choice and trademark search for
  "Everyome".
- **Testing gaps carried over**: real Slurm on a production cluster, real FASTQ data, Windows.

---

## 11. Risks

| Risk | Mitigation |
|---|---|
| Scope: seven suites is years of work | Prove the core with three very different modules (SPLiTscape, bulk RNA, primers) before widening |
| Wrapped pipelines change underneath us | Pin revisions and container digests; upgrade deliberately with tests |
| Users misread results | Interpretation guides, sensible defaults, warnings on unusual settings |
| Malicious community modules | Registry off at launch; review, signing, pinning (section 7) |
| Cluster diversity across institutions | Scheduler interface, readiness checks, site config file |
| Generated methods text contains errors | Always generated from the run record; user must review before export |
| Restrictive licences on some tools or model weights | Manifest declares licences; core shows them before first run |

---

## 12. Open questions

1. **Job names across institutions.** Resolved: the prefix in
   `<prefix>_<user>_everyome_<module>_<stage>` is a site setting (default `Claude`).
2. **Repository.** New repo now, or restructure this one and rename later?
3. **Funding and maintainers** for long-term upkeep once other labs depend on it.
4. **Which second module?** Bulk RNA DE is proposed; confirm.
5. **Reference library.** Shared, versioned genomes/annotations per site, or per
   project?

---

## References

- Galaxy Community (2024). The Galaxy platform for accessible, reproducible, and collaborative data analyses: 2024 update. *Nucleic Acids Res.* https://doi.org/10.1093/nar/gkae410
- Ewels P. A. et al. (2020). The nf-core framework for community-curated bioinformatics pipelines. *Nat. Biotechnol.* https://doi.org/10.1038/s41587-020-0439-x
- Di Tommaso P. et al. (2017). Nextflow enables reproducible computational workflows. *Nat. Biotechnol.* https://doi.org/10.1038/nbt.3820
- Mölder F. et al. (2021). Sustainable data analysis with Snakemake. *F1000Research.* https://doi.org/10.12688/f1000research.29032.2
- Kurtzer G. M., Sochat V., Bauer M. W. (2017). Singularity: Scientific containers for mobility of compute. *PLoS ONE.* https://doi.org/10.1371/journal.pone.0177459
