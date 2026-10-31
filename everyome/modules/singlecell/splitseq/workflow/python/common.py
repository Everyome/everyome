"""Shared helpers for the Scanpy stages (10–15).

Every stage script does:

    cfg = common.start("10_label")      # load config, name process, set up Scanpy
    ...
    common.write_h5ad(adata, cfg, "fully_labelled")
"""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

import scanpy as sc
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

# File names of the checkpoints passed between stages.
CHECKPOINTS = {
    "fully_labelled": "fully_labelled.h5ad",   # stage 10 -> 11
    "sliced": "sliced.h5ad",                   # stage 11 -> 12 (raw counts; also for pseudobulk)
    "preprocessed": "preprocessed.h5ad",       # stage 12 -> 13, 14, 15
    "annotated": "annotated.h5ad",             # stage 15 output
}

log = logging.getLogger("pipeline")


class Config(dict):
    """Dict with attribute access and repo-relative path resolution."""

    def __getattr__(self, key):
        try:
            value = self[key]
        except KeyError as err:
            raise AttributeError(key) from err
        return Config(value) if isinstance(value, dict) else value

    def path(self, key: str) -> Path:
        """Resolve an entry of `paths:` against the repo root."""
        p = Path(self["paths"][key])
        return p if p.is_absolute() else REPO_ROOT / p

    @property
    def results_dir(self) -> Path:
        return self.path("results_dir")

    @property
    def figures_dir(self) -> Path:
        return self.path("figures_dir")


def _name_process(cfg: Config, step: str) -> None:
    """Name the process Claude_<user>_<step> (needs the optional setproctitle)."""
    user = cfg.get("user") or os.environ.get("PIPELINE_USER") or os.environ.get("USER", "unknown")
    title = f"Claude_{user}_{step}"
    try:
        import setproctitle

        setproctitle.setproctitle(title)
    except ImportError:
        log.debug("setproctitle not installed; process title not set (%s)", title)


def start(step: str, description: str | None = None) -> Config:
    """Parse --config, load YAML, name the process and configure Scanpy."""
    parser = argparse.ArgumentParser(description=description or step)
    parser.add_argument("--config", default=str(REPO_ROOT / "config" / "analysis.yaml"))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%F %T")
    with open(args.config) as fh:
        cfg = Config(yaml.safe_load(fh))

    _name_process(cfg, step)
    cfg.results_dir.mkdir(parents=True, exist_ok=True)
    cfg.figures_dir.mkdir(parents=True, exist_ok=True)

    # Intent: same Scanpy settings in every stage; figures go to one folder.
    sc.settings.verbosity = 2
    sc.settings.figdir = str(cfg.figures_dir)
    sc.settings.autoshow = False
    sc.settings.set_figure_params(dpi=80, dpi_save=150, transparent=True)  # 150 = Scanpy default
    log.info("stage %s | config %s", step, args.config)
    return cfg


def resolve(path) -> Path:
    """Absolute paths as given; relative paths against the repo root."""
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


def checkpoint(cfg: Config, name: str) -> Path:
    return cfg.results_dir / CHECKPOINTS[name]


def read_h5ad(cfg: Config, name: str):
    path = checkpoint(cfg, name)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found — run the stage that writes '{name}' first")
    adata = sc.read_h5ad(path)
    log.info("read %s: %d cells x %d genes", path.name, adata.n_obs, adata.n_vars)
    return adata


def write_h5ad(adata, cfg: Config, name: str) -> Path:
    path = checkpoint(cfg, name)
    adata.write_h5ad(path)
    log.info("wrote %s: %d cells x %d genes", path.name, adata.n_obs, adata.n_vars)
    return path


def log_counts(adata, column: str = "Unique") -> None:
    """Log cells per value of an obs column (the old `value_counts()` cells)."""
    if column in adata.obs:
        for key, n in adata.obs[column].value_counts().items():
            log.info("  %-50s %7d", key, n)
