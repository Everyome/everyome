"""The demo cluster: a folder on this computer plus a pretend Slurm.

<root>/
  projects/             where demo projects are saved
  data/<module id>/     each module's small demo dataset
  .bin/                 sbatch, squeue, sacct, scancel (fake_slurm.py)
  .slurm/               the pretend scheduler's job records
"""
from __future__ import annotations

import importlib
import shlex
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def example_data(data: Path, modules: dict) -> None:
    """Copy (or build, once) each module's example data into data/<module id>/."""
    for m in modules.values():
        if m.demo.get("data"):
            # Intent: refresh example data from the installed modules, never touching users' projects.
            shutil.copytree(m.dir / m.demo["data"], data / m.id, dirs_exist_ok=True)
        if m.demo.get("build") and not (data / m.id / ".demo_ready").exists():
            # Intent: modules whose example data is generated (too large to ship) build it once, here.
            mod, _, fn = m.demo["build"].partition(":")
            getattr(importlib.import_module(mod), fn)(data / m.id)
            (data / m.id / ".demo_ready").write_text("1")


def setup(root: Path, modules: dict) -> Path:
    """Create or refresh the demo cluster; returns the folder holding the fake Slurm commands."""
    (root / "projects").mkdir(parents=True, exist_ok=True)
    example_data(root / "data", modules)
    bin_dir = root / ".bin"
    bin_dir.mkdir(exist_ok=True)
    for cmd in ("sbatch", "squeue", "sacct", "scancel"):
        f = bin_dir / cmd
        f.write_text(f"#!/bin/bash\nexec {shlex.quote(sys.executable)} {shlex.quote(str(HERE / 'fake_slurm.py'))} {cmd} \"$@\"\n")
        f.chmod(0o755)
    return bin_dir
