"""Live session for 10x Visium: read Space Ranger's output, then the shared single-cell steps, plus tissue views.

Each spot is treated like a cell: filtering, clustering, markers, naming and
export are shared with the single-cell modules (../../singlecell/cells.py).
What is spatial: every spot keeps its place on the tissue image, so any result
can be shown on the tissue, and genes whose expression follows the tissue's
layout (spatially variable genes) are found with Moran's I.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import numpy as np
import pandas as pd
import scanpy as sc
import scipy.sparse as spm

from everyome.modules.singlecell.cells import PALETTE, CellsEngine

POSITIONS = ["tissue_positions.csv", "tissue_positions_list.csv", "tissue_positions.parquet"]
POS_COLS = ["barcode", "in_tissue", "array_row", "array_col", "pxl_row_in_fullres", "pxl_col_in_fullres"]


def read_spaceranger(outs: Path) -> tuple[sc.AnnData, dict]:
    """Spots under the tissue, with their positions, from a Space Ranger 'outs' folder (or a Visium HD binned folder)."""
    outs = Path(outs)
    if (outs / "filtered_feature_bc_matrix.h5").is_file():
        a = sc.read_10x_h5(outs / "filtered_feature_bc_matrix.h5")
    elif (outs / "filtered_feature_bc_matrix").is_dir():
        a = sc.read_10x_mtx(outs / "filtered_feature_bc_matrix", var_names="gene_symbols", cache=False)
    else:
        raise FileNotFoundError(f"{outs} has no filtered_feature_bc_matrix (.h5 or folder). Choose Space Ranger's 'outs' folder.")
    a.var_names_make_unique()
    sp = outs / "spatial"
    pos_file = next((sp / f for f in POSITIONS if (sp / f).is_file()), None)
    if pos_file is None:
        raise FileNotFoundError(f"{sp} has no tissue_positions file.")
    if pos_file.suffix == ".parquet":
        pos = pd.read_parquet(pos_file)
    else:
        pos = pd.read_csv(pos_file, header=0 if pos_file.name == "tissue_positions.csv" else None)
        if pos_file.name != "tissue_positions.csv":
            pos.columns = POS_COLS
    pos = pos.set_index("barcode")
    pos = pos[pos["in_tissue"] == 1]
    keep = a.obs_names.isin(pos.index)
    a = a[keep].copy()
    pos = pos.loc[a.obs_names]
    a.obs["array_row"], a.obs["array_col"] = pos["array_row"].values, pos["array_col"].values
    # Intent: x across, y down, in full-resolution image pixels (as Space Ranger gives them).
    a.obsm["spatial"] = pos[["pxl_col_in_fullres", "pxl_row_in_fullres"]].to_numpy(float)
    scale = json.loads((sp / "scalefactors_json.json").read_text())
    image = next((sp / f for f in ("tissue_lowres_image.png", "tissue_hires_image.png") if (sp / f).is_file()), None)
    meta = {"image": str(image) if image else "", "scale": scale.get("tissue_lowres_scalef" if image and "lowres" in image.name else "tissue_hires_scalef", 1.0),
            "spot": float(scale.get("spot_diameter_fullres", 0)) or None}
    return a, meta


def morans_i(X: np.ndarray, W: spm.csr_matrix) -> np.ndarray:
    """Moran's I for each column of X on a row-standardised neighbour graph W: near 1 when neighbours are alike, near 0 when random."""
    Z = X - X.mean(0)
    num = (Z * (W @ Z)).sum(0)
    den = (Z ** 2).sum(0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, 0.0)


def neighbours(xy: np.ndarray, k: int = 6) -> spm.csr_matrix:
    """Each spot's k nearest spots (Visium spots have six neighbours), row-standardised."""
    from scipy.spatial import cKDTree
    k = min(k, len(xy) - 1)
    _, idx = cKDTree(xy).query(xy, k=k + 1)
    rows = np.repeat(np.arange(len(xy)), k)
    return spm.csr_matrix((np.full(rows.size, 1.0 / k), (rows, idx[:, 1:].ravel())), shape=(len(xy), len(xy)))


class Engine(CellsEngine):
    API = ("samples_info", "load", "spots_per_sample", "tissue", "spatial_genes", "neighbourhood") + CellsEngine.SHARED_API
    REPLAY = ("load", "spatial_genes", "neighbourhood") + CellsEngine.SHARED_REPLAY
    STATUS_KEYS = ("loaded_from", "qc", "cluster_params", "spatial_genes", "neighbourhood")
    COUNT_LABELS = {"total_counts": "UMIs per spot", "n_genes": "Genes per spot"}

    def __init__(self, run_dir: str):
        super().__init__(run_dir)
        self._images = {}

    def _mito_pattern(self):
        return self.params.get("mito_genes") or ""

    # ---------------------------------------------------------------- load
    def samples_info(self):
        return [{"sample": r["sample"], "outs": r["outs"], "condition": r.get("condition", ""), "batch": r.get("batch", "")} for r in self.params["samples"]]

    def load(self):
        return self._background(self._load)

    def _load(self):
        parts, images, info = [], {}, []
        rows = self.params["samples"]
        for k, r in enumerate(rows):
            self._prog(5 + 70 * k // max(1, len(rows)), f"Reading {r['sample']}")
            a, meta = read_spaceranger(Path(r["outs"]))
            a.obs_names = [f"{r['sample']}_{b}" for b in a.obs_names]
            a.obs["sample"] = r["sample"]
            a.obs["condition"] = r.get("condition") or "none"
            if any(x.get("batch") for x in rows):
                a.obs["batch"] = r.get("batch") or "none"
            images[r["sample"]] = meta
            umi = np.asarray(a.X.sum(1)).ravel()
            info.append({"sample": r["sample"], "spots": int(a.n_obs), "genes": int(a.n_vars), "median_umi": float(np.median(umi)) if a.n_obs else 0})
            parts.append(a)
        self._prog(80, "Joining samples")
        a = sc.concat(parts, join="outer", fill_value=0) if len(parts) > 1 else parts[0]
        a.X = spm.csr_matrix(a.X, dtype=np.float32)
        for c in ("sample", "condition", "batch"):
            if c in a.obs:
                a.obs[c] = a.obs[c].astype("category")
        a.uns["images"] = json.dumps(images)                 # Intent: a string survives the h5ad checkpoint unchanged
        a.write_h5ad(self._ckpt("loaded"))
        self.adata = a
        self.state.update(step="loaded", loaded_from={"samples": info}, annotations={}, spatial_genes=None)
        self._record("loaded Space Ranger output", samples=info)

    def spots_per_sample(self):
        a = self.adata if self.adata is not None and self.state.get("step") == "loaded" else self._before_qc()
        return {str(k): int(v) for k, v in a.obs["sample"].value_counts().sort_index().items()}

    # ---------------------------------------------------------------- the tissue
    def _image(self, sample: str) -> dict:
        if sample not in self._images:
            meta = json.loads(self.adata.uns["images"])[sample]
            uri, w, h = "", 0, 0
            if meta["image"] and Path(meta["image"]).is_file():
                from PIL import Image
                with Image.open(meta["image"]) as im:
                    w, h = im.size
                uri = "data:image/png;base64," + base64.b64encode(Path(meta["image"]).read_bytes()).decode()
            self._images[sample] = {**meta, "uri": uri, "width": w, "height": h}
        return self._images[sample]

    def tissue(self, sample: str, key: str = "total_counts"):
        """The tissue image with this sample's spots, coloured by a label, a gene or a QC measure."""
        a = self.adata
        if sample not in set(a.obs["sample"].astype(str)):
            raise ValueError(f"No spots from {sample}.")
        m = (a.obs["sample"].astype(str) == sample).values
        img = self._image(sample)
        xy = a.obsm["spatial"][m] * img["scale"]
        if not img["uri"]:                                    # no image: draw spots on a blank area of the right size
            img = {**img, "width": float(xy[:, 0].max() * 1.05), "height": float(xy[:, 1].max() * 1.05)}
        r = (img["spot"] or 0) * img["scale"] / 2 or float(np.median(neighbours_dist(xy)) / 2.2)
        out = {"image": img["uri"], "width": img["width"], "height": img["height"], "x": np.round(xy[:, 0], 1).tolist(),
               "y": np.round(xy[:, 1], 1).tolist(), "r": round(float(r), 2), "spots": int(m.sum())}
        return {**out, "colour": self._spot_colour(key, m)}

    def _spot_colour(self, key: str, m: np.ndarray) -> dict:
        a = self.adata
        if key in ("total_counts", "n_genes"):
            # Intent: counts per spot from the measures saved at filtering; before that, from the raw counts themselves.
            col = {"total_counts": "total_counts", "n_genes": "n_genes_by_counts"}[key]
            if col in a.obs:
                v = a.obs[col].values[m].astype(float)
            else:
                v = np.asarray(a.X[m].sum(1)).ravel() if key == "total_counts" else np.asarray((a.X[m] > 0).sum(1)).ravel()
            return {"kind": "num", "values": np.round(v, 1).tolist(), "max": float(v.max() or 1), "gene": self.COUNT_LABELS[key], "label": ""}
        if key == "annotation":
            names = self.state.get("annotations", {})
            vals = a.obs["cluster"].astype(str).map(lambda c: names.get(c, {}).get("name") or "Unannotated").values
            cats = sorted(set(vals), key=lambda x: (x == "Unannotated", x))
            col = {v["name"]: v.get("color") for v in names.values() if v.get("name")}
            sub = vals[m]
            return {"kind": "cat", "categories": cats, "colors": [col.get(c) or "#B9AEC0" for c in cats], "codes": [cats.index(x) for x in sub], "userColours": True}
        if key in a.obs:
            s = a.obs[key]
            if s.dtype.name != "category" and np.issubdtype(s.dtype, np.number):
                v = s.values[m].astype(float)
                return {"kind": "num", "values": np.round(v, 3).tolist(), "max": float(v.max() or 1), "gene": key, "label": ""}
            cats = [str(c) for c in (s.cat.categories if s.dtype.name == "category" else sorted(s.astype(str).unique()))]
            return {"kind": "cat", "categories": cats, "colors": [PALETTE[i % len(PALETTE)] for i in range(len(cats))],
                    "codes": pd.Categorical(s.astype(str).values[m], categories=cats).codes.tolist()}
        src = a.raw if a.raw is not None else a
        if key in src.var_names:
            v = src[:, key].X
            v = np.asarray(v.toarray() if spm.issparse(v) else v).ravel()[m]
            if a.raw is None:
                v = np.log1p(v)
            return {"kind": "num", "values": np.round(v, 3).tolist(), "max": float(v.max() or 1), "gene": key, "label": ""}
        raise KeyError(f"'{key}' is not a label or gene")

    # ---------------------------------------------------------------- spatially variable genes
    def spatial_genes(self, n_genes: int = 2000, top: int = 40):
        return self._background(self._spatial_genes, int(n_genes), int(top))

    def _spatial_genes(self, n_genes, top):
        a = self.adata
        self._prog(10, "Preparing expression")
        if a.raw is not None:
            X, names = a.raw.X, a.raw.var_names
        else:
            b = a.copy(); sc.pp.normalize_total(b, target_sum=1e4); sc.pp.log1p(b); X, names = b.X, b.var_names
        X = X.toarray() if spm.issparse(X) else np.asarray(X)
        detected = (X > 0).mean(0)
        cand = np.argsort(-X.var(0) * (detected > 0.02))[:min(n_genes, X.shape[1])]
        scores = np.zeros(len(cand))
        samples = a.obs["sample"].astype(str).values
        for k, s in enumerate(sorted(set(samples))):
            self._prog(20 + 70 * k // max(1, len(set(samples))), f"Moran's I in {s}")
            m = samples == s
            if m.sum() > 10:
                scores += morans_i(X[m][:, cand], neighbours(a.obsm["spatial"][m])) * m.sum()
        scores /= len(samples)
        order = np.argsort(-scores)[:top]
        res = [{"gene": str(names[cand[i]]), "morans_i": round(float(scores[i]), 3), "detected": round(float(detected[cand[i]]) * 100, 1)} for i in order]
        self.state["spatial_genes"] = res
        self._record("found spatially variable genes", genes_tested=int(len(cand)), top=[r["gene"] for r in res[:10]],
                     method="Moran's I on each sample's six nearest spots")


    # ---------------------------------------------------------------- neighbourhoods
    def neighbourhood(self, by: str = "annotation", k: int = 10, permutations: int = 200):
        return self._background(self._neighbourhood, by, int(k), int(permutations))

    def _neighbourhood(self, by, k, permutations):
        """How often each pair of types are neighbours, against labels shuffled within each section (z-scores)."""
        a = self.adata
        if "cluster" not in a.obs:
            raise ValueError("Cluster first.")
        names = self.state.get("annotations", {})
        lab = a.obs["cluster"].astype(str)
        if by == "annotation":
            lab = lab.map(lambda c: names.get(c, {}).get("name") or f"cluster {c}")
        groups = sorted(set(lab))
        codes = pd.Categorical(lab, categories=groups).codes
        samples = a.obs["sample"].astype(str).values
        rng = np.random.default_rng(0)
        pairs, perms = np.zeros((len(groups), len(groups))), np.zeros((permutations, len(groups), len(groups)))
        for s in sorted(set(samples)):
            m = np.where(samples == s)[0]
            if len(m) <= k:
                continue
            from scipy.spatial import cKDTree
            _, idx = cKDTree(a.obsm["spatial"][m]).query(a.obsm["spatial"][m], k=k + 1)
            src, dst = np.repeat(np.arange(len(m)), k), idx[:, 1:].ravel()
            c = codes[m]
            np.add.at(pairs, (c[src], c[dst]), 1)
            self._prog(10, f"Shuffling labels in {s}")
            for p in range(permutations):
                sh = rng.permutation(c)
                np.add.at(perms[p], (sh[src], sh[dst]), 1)
        sd = perms.std(0)
        z = np.where(sd > 0, (pairs - perms.mean(0)) / np.where(sd > 0, sd, 1), 0.0)
        # Intent: z-scores grow with the number of cells; the ratio to chance (log2) is the size of the effect.
        ratio = np.log2((pairs + 1) / (perms.mean(0) + 1))
        res = {"groups": groups, "z": np.round(z, 1).tolist(), "log2_ratio": np.round(ratio, 2).tolist(), "by": by, "k": k,
               "permutations": permutations}
        self.state["neighbourhood"] = res
        self._record("compared neighbourhoods", by=by, k=k, permutations=permutations, groups=len(groups))


def neighbours_dist(xy: np.ndarray) -> np.ndarray:
    from scipy.spatial import cKDTree
    d, _ = cKDTree(xy).query(xy, k=2)
    return d[:, 1]
