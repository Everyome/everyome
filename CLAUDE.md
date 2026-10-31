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
| `everyome/core/` | Backends, scheduler, projects, runs, module loader, local server |
| `everyome/modules/` | First-party modules, one folder each with `module.yaml` |
| `everyome/static/` | Frontend (vanilla JS), shared viewers, themes |
| `tests/` | Unit tests and end-to-end demo flows |
| `docs/PLAN.md` | Design plan and phases |

The source for porting is SPLiTscape in `~/Desktop/helomics` (`app/splitscape_app/`).

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
- **Design:** Gothic Cream is the default theme; every theme passes WCAG AA in light and dark.
- **Licence:** not yet chosen (MIT or BSD-3, pending Stowers tech transfer); don't add one.
- Comments state intent; keep UI text plain-language and written for biologists.
- Literature references include a DOI or URL.
