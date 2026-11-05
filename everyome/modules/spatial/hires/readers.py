"""Readers for high-resolution sequencing-based spatial platforms: each returns bins (or beads) × genes with positions in
obsm['spatial'] and drawing details (image, scale), from the files the platform's software writes.

  visium_hd  10x Visium HD: Space Ranger's binned_outputs/square_<N>um folder for the chosen bin size (with the image)
  stereo     STOmics Stereo-seq: a GEM table (geneID, x, y, MIDCount) summed into square bins; positions in DNB units
  curio      Curio Seeker: the AnnData file it writes (beads with obsm['spatial'], in µm)
"""
from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np
import pandas as pd
import scanpy as sc
import scipy.sparse as sp

from ..visium.engine import read_spaceranger

DNB_UM = 0.5             # Stereo-seq: one DNB spot every 500 nm


def detect(folder: Path) -> str:
    f = Path(folder)
    if (f / "binned_outputs").is_dir() or f.name.startswith("square_"):
        return "visium_hd"
    if next(f.glob("*.gem*"), None):
        return "stereo"
    if next(f.glob("*anndata.h5ad"), None) or next(f.glob("*.h5ad"), None):
        return "curio"
    return ""


def bins_available(folder: str) -> list[int]:
    f = Path(folder) / "binned_outputs"
    return sorted(int(p.name[7:10]) for p in f.glob("square_*um") if p.is_dir()) if f.is_dir() else []


def read_visium_hd(f: Path, bin_um: int) -> tuple[sc.AnnData, dict]:
    folder = f if f.name.startswith("square_") else f / "binned_outputs" / f"square_{bin_um:03d}um"
    if not folder.is_dir():
        have = ", ".join(f"{b} µm" for b in bins_available(str(f))) or "none"
        raise FileNotFoundError(f"No {bin_um} µm bins in {f} (bins there: {have}).")
    a, meta = read_spaceranger(folder)
    return a, {**meta, "units": "px"}


def read_stereo(f: Path, bin_um: int) -> tuple[sc.AnnData, dict]:
    gem = next(f.glob("*.gem*"))
    opener = gzip.open if gem.suffix == ".gz" else open
    with opener(gem, "rt") as fh:
        skip = 0
        for line in fh:                                   # Intent: GEM files start with '#' comment lines
            if not line.startswith("#"):
                break
            skip += 1
    d = pd.read_csv(gem, sep="\t", skiprows=skip, compression="gzip" if gem.suffix == ".gz" else None)
    count = "MIDCount" if "MIDCount" in d else ("MIDCounts" if "MIDCounts" in d else "UMICount")
    size = max(1, int(round(bin_um / DNB_UM)))
    bx, by = d["x"] // size, d["y"] // size
    key = bx.astype(str) + "_" + by.astype(str)
    cells, ci = np.unique(key, return_inverse=True)
    genes, gi = np.unique(d["geneID"].astype(str), return_inverse=True)
    X = sp.csr_matrix((d[count].to_numpy(np.float32), (ci, gi)), shape=(len(cells), len(genes)))
    a = sc.AnnData(X, obs=pd.DataFrame(index=[f"bin{bin_um}_{c}" for c in cells]), var=pd.DataFrame(index=genes))
    xy = np.array([c.split("_") for c in cells], dtype=float)
    a.obsm["spatial"] = (xy + 0.5) * size * DNB_UM       # bin centres, in µm
    return a, {"image": "", "scale": 1.0, "spot": None, "units": "µm"}


def read_curio(f: Path, bin_um: int) -> tuple[sc.AnnData, dict]:
    h5 = next(f.glob("*anndata.h5ad"), None) or next(f.glob("*.h5ad"))
    a = sc.read_h5ad(h5)
    if "spatial" not in a.obsm:
        if {"x", "y"} <= set(a.obs.columns):
            a.obsm["spatial"] = a.obs[["x", "y"]].to_numpy(float)
        else:
            raise ValueError(f"{h5.name} has no bead positions (obsm['spatial'], or x and y columns).")
    a.X = sp.csr_matrix(a.raw.X if a.raw is not None else a.X, dtype=np.float32)
    return a, {"image": "", "scale": 1.0, "spot": None, "units": "µm"}


READERS = {"visium_hd": read_visium_hd, "stereo": read_stereo, "curio": read_curio}


def read(folder: str, platform: str = "", bin_um: int = 8) -> tuple[sc.AnnData, dict, str]:
    f = Path(folder)
    platform = platform or detect(f)
    if platform not in READERS:
        raise ValueError(f"Couldn't tell which platform made {f}. Choose Space Ranger's 'outs' (Visium HD), the folder with the "
                         "Stereo-seq GEM file, or the folder with Curio Seeker's .h5ad; or set the platform in the table.")
    a, meta = READERS[platform](f, int(bin_um))
    a.var_names_make_unique()
    return a, meta, platform
