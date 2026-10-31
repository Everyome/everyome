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
| Audience | Any lab, any Slurm cluster, plus local runs on a laptop. Stowers/Cerebro is one configuration. |
| Relation to SPLiTscape | New umbrella; SPLiTscape becomes the first single-cell module, attribution and citation kept |
| Licence | MIT or BSD-3 (confirm with Stowers tech transfer) |
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
| 7 | Community registry (off) | Registry repo, CI checks, signing, loader verification, review checklist | A test module goes through review in a dry run; registry stays disabled |
| 8 | Suite roll-out | Add modules suite by suite (section 2), each with demo data and learning material | — ongoing |

Phases 5 and 6 can run alongside 4 once phase 3 is done.

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

- **Stowers IT** (already open for SPLiTscape): SSH-key logins from laptops,
  port forwarding to compute nodes, partition/time limits for sessions, a shared
  install location. New for Everyome: Apptainer, Java and Nextflow availability
  on Cerebro; GPU partition access for the protein suite.
- **Stowers tech transfer**: licence choice and trademark search for
  "Everyome".
- **Testing gaps carried over**: real Slurm on Cerebro, real FASTQ data, Windows.

---

## 11. Risks

| Risk | Mitigation |
|---|---|
| Scope: seven suites is years of work | Prove the core with three very different modules (SPLiTscape, bulk RNA, primers) before widening |
| Wrapped pipelines change underneath us | Pin revisions and container digests; upgrade deliberately with tests |
| Users misread results | Interpretation guides, sensible defaults, warnings on unusual settings |
| Malicious community modules | Registry off at launch; review, signing, pinning (section 7) |
| Cluster diversity outside Stowers | Scheduler interface, readiness checks, site config file |
| Generated methods text contains errors | Always generated from the run record; user must review before export |
| Restrictive licences on some tools or model weights | Manifest declares licences; core shows them before first run |

---

## 12. Open questions

1. **Job names outside Stowers.** Stowers policy requires
   `Claude_<user>_..._<stage>`. Proposal: a site setting for the job-name
   prefix, defaulting to `Claude_<user>_everyome_<module>_<stage>` in the
   Stowers configuration, so other institutions can set their own.
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
