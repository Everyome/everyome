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
| `everyome/core/modules.py` | Finds first-party modules; community registry switched off |
| `everyome/core/projects.py`, `runs.py` | Project folders; runs (params, job scripts, afterok chain, status, logs) |
| `everyome/core/engine.py`, `session.py`, `sessions.py` | Interactive engines (base class), the compute-node session server, and the app side (start, tunnel, ping, stop) |
| `everyome/suites.yaml`, `everyome/core/suites.py` | The suites, their tools (ready = has a module; otherwise planned), and the data-type and aim rules behind "Find the right analysis". A module's `suite` must be one of these ids and it must be listed as a tool |
| `everyome/core/server.py` | Local FastAPI app; `/api/s/*` is proxied to the session with its token |
| `everyome/core/demo/` | Demo cluster setup and `fake_slurm.py` |
| `everyome/modules/<suite>/<name>/` | A module: `module.yaml`, stage code, engine, `ui.js`, `docs/manual.md`, `demo/` |
| `everyome/static/` | App shell (`app.js`: home page, suite pages, views, shared viewers, markdown), `app.css`, `themes.json`, fonts |
| `design/themes/` | 67 cnidarian themes; `python design/themes/export_app_themes.py` regenerates `everyome/static/themes.json` |
| `tests/` | Manifest, Slurm naming, and an end-to-end demo flow (real session process) |
| `docs/PLAN.md` | Design plan and phases |

The source for porting is SPLiTscape in `~/Desktop/helomics` (`app/splitscape_app/`).

## Writing a module

Copy `everyome/modules/tutorial/sequence_summary/`. Stage commands are bash lines
in `module.yaml` (`{python}` is the cluster's Python), run inside the run folder
with `$EVERYOME_PARAMS` (settings as JSON) and `$EVERYOME_RUN_DIR`. An interactive
engine subclasses `BaseEngine`, lists callable methods in `API`, and records
decisions with `_record()`. `ui.js` registers views with
`Everyome.registerViews(id, {stepId: async el => ...})` and calls the engine with
`Everyome.call(method, args)`.

## Running

Python 3.10 or newer (3.9 is end-of-life and no longer on GitHub's Ubuntu runners);
CI tests 3.10 and 3.12 on Linux and macOS.

```bash
pip install -e ".[test]" && everyome     # http://127.0.0.1:8777
pytest
```

## Rules to keep

- **Stowers HPC policy:** Claude never submits sbatch jobs on Cerebro. The app submits
  only when the user clicks Run, under their own account. Don't add auto-submission.
- **Process naming:** all Claude-created processes/jobs include `Claude` and the
  username: `Claude_<user>_everyome_<module>_<stage>`.
- **Community modules** stay disabled until review, signing and pinning are in place
  (`docs/PLAN.md` section 7).
- **Data governance:** no PII/PHI in code or logs; never store passwords or keys.
- **Design:** Nematostella in light mode is the default for new users (Gothic Cream remains the house style); every theme passes WCAG AA in light and dark. The app always opens on the home page.
- **Licence:** not yet chosen (MIT or BSD-3, pending Stowers tech transfer); don't add one.
- Comments state intent; keep UI text plain-language and written for biologists.
- Literature references include a DOI or URL.
