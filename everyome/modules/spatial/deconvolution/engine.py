"""Live session for cell types in spots: how well the models trained, each cell type on the tissue, the main type in
every spot, which cell types live together, each type's signature genes, and export.

Reads what the cell2location stages wrote (results/reference/, results/cell2location/) and, for drawing, each
section's spot positions and tissue image from its Space Ranger folder. Every choice that changes a result is recorded
in order for the write-up.
"""
from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from everyome.core.engine import BaseEngine
from everyome.modules.singlecell.cells import PALETTE
from everyome.modules.spatial.visium.engine import POS_COLS, POSITIONS, neighbours_dist

MEASURES = {"mean": "cells (mean estimate)", "q05": "cells (cautious estimate, 5% quantile)", "share": "share of the spot"}


def positions(outs: Path) -> tuple[pd.DataFrame, dict]:
    """In-tissue spot positions (full-resolution pixels) and the image to draw them on, from a Space Ranger folder."""
    sp = Path(outs) / "spatial"
    f = next((sp / n for n in POSITIONS if (sp / n).is_file()), None)
    if f is None:
        raise FileNotFoundError(f"{sp} has no tissue_positions file.")
    if f.suffix == ".parquet":
        pos = pd.read_parquet(f)
    else:
        pos = pd.read_csv(f, header=0 if f.name == "tissue_positions.csv" else None)
        if f.name != "tissue_positions.csv":
            pos.columns = POS_COLS
    pos = pos[pos["in_tissue"] == 1].set_index("barcode")
    scale = json.loads((sp / "scalefactors_json.json").read_text())
    image = next((sp / n for n in ("tissue_lowres_image.png", "tissue_hires_image.png") if (sp / n).is_file()), None)
    meta = {"image": str(image) if image else "", "spot": float(scale.get("spot_diameter_fullres", 0)) or None,
            "scale": scale.get("tissue_lowres_scalef" if image and "lowres" in image.name else "tissue_hires_scalef", 1.0)}
    return pos, meta


class Engine(BaseEngine):
    API = ("overview", "tissue", "together", "signature", "export", "files")
    REPLAY = ("together", "export")

    def __init__(self, run_dir: str):
        super().__init__(run_dir)
        self.res = self.dir / "results"
        c2l = self.res / "cell2location"
        if not (c2l / "abundance_mean.csv").exists():
            raise FileNotFoundError("No cell abundances in this run's results. Check the stage logs on the Run page.")
        self.mean = pd.read_csv(c2l / "abundance_mean.csv")
        self.q05 = pd.read_csv(c2l / "abundance_q05.csv") if (c2l / "abundance_q05.csv").exists() else self.mean.copy()
        self.types = [c for c in self.mean.columns if c not in ("sample", "barcode")]
        sig = self.res / "reference" / "signatures.csv"
        self.sig = pd.read_csv(sig, index_col=0) if sig.exists() else None
        self.outs = {r["sample"]: r["outs"] for r in self.params.get("samples") or []}
        self._images = {}

    def _values(self, measure: str) -> pd.DataFrame:
        if measure not in MEASURES:
            raise ValueError(f"Measure should be one of {', '.join(MEASURES)}.")
        if measure == "share":
            m = self.mean[self.types]
            return m.div(m.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
        return (self.q05 if measure == "q05" else self.mean)[self.types]

    def _curve(self, path: Path) -> list:
        if not path.exists():
            return []
        d = pd.read_csv(path)
        return d[["round", "loss"]].round(1).values.tolist()

    def _colours(self) -> dict:
        return {t: PALETTE[i % len(PALETTE)] for i, t in enumerate(self.types)}

    # ---------------------------------------------------------------- API
    def overview(self):
        m = self.mean[self.types]
        total = m.sum(axis=1)
        dom = m.idxmax(axis=1)
        sections = [{"sample": s, "spots": int((self.mean["sample"] == s).sum())} for s in dict.fromkeys(self.mean["sample"])]
        per = []
        for t in self.types:
            row = {"type": t, "cells": round(float(m[t].sum()), 1), "dominant_spots": int((dom == t).sum())}
            for s in sections:
                row[s["sample"]] = round(float(m.loc[self.mean["sample"] == s["sample"], t].sum()), 1)
            per.append(row)
        edges = list(range(0, int(max(10, np.ceil(total.max() / 2) * 2)) + 2, 2))
        info = {"sections": [s["sample"] for s in sections], "types": self.types, "spots": int(len(m))}
        if self.state.get("overview") != info:
            self.state["overview"] = info
            self._record("read the cell-type abundances", **info, cells=round(float(total.sum()), 1))
        return {**info, "per_section": sections, "per_type": per, "colours": self._colours(),
                "cells_hist": {"edges": edges, "counts": np.histogram(total, edges)[0].tolist()},
                "median_cells": round(float(total.median()), 1), "expected": self.params.get("cells_per_spot", 30),
                "reference_curve": self._curve(self.res / "reference" / "training.csv"),
                "mapping_curve": self._curve(self.res / "cell2location" / "training.csv")}

    def _image(self, sample: str) -> tuple[pd.DataFrame, dict]:
        if sample not in self._images:
            if sample not in self.outs:
                raise ValueError(f"No section called {sample}.")
            pos, meta = positions(Path(self.outs[sample]))
            uri, w, h = "", 0, 0
            if meta["image"]:
                from PIL import Image
                with Image.open(meta["image"]) as im:
                    w, h = im.size
                uri = "data:image/png;base64," + base64.b64encode(Path(meta["image"]).read_bytes()).decode()
            self._images[sample] = (pos, {**meta, "uri": uri, "width": w, "height": h})
        return self._images[sample]

    def tissue(self, sample: str, key: str = "dominant", measure: str = "mean"):
        """The section's spots on its image, coloured by one cell type, by the main type, or by total cells."""
        pos, img = self._image(sample)
        rows = (self.mean["sample"] == sample).values
        bc = self.mean.loc[rows, "barcode"].values
        ok = np.isin(bc, pos.index)
        bc = bc[ok]
        xy = pos.loc[bc, ["pxl_col_in_fullres", "pxl_row_in_fullres"]].to_numpy(float) * img["scale"]
        if not img["uri"]:
            img = {**img, "width": float(xy[:, 0].max() * 1.05), "height": float(xy[:, 1].max() * 1.05)}
        r = (img["spot"] or 0) * img["scale"] / 2 or float(np.median(neighbours_dist(xy)) / 2.2)
        vals = self._values(measure).loc[rows].iloc[ok]
        if key == "dominant":
            dom = vals.idxmax(axis=1).values
            col = self._colours()
            colour = {"kind": "cat", "categories": self.types, "colors": [col[t] for t in self.types], "codes": [self.types.index(t) for t in dom]}
        else:
            v = vals.sum(axis=1).to_numpy() if key == "total" else vals[key].to_numpy() if key in self.types else None
            if v is None:
                raise ValueError(f"No cell type called {key}.")
            colour = {"kind": "num", "values": np.round(v, 3).tolist(), "max": float(v.max() or 1),
                      "gene": "All cell types" if key == "total" else key, "label": MEASURES[measure]}
        return {"image": img["uri"], "width": img["width"], "height": img["height"], "x": np.round(xy[:, 0], 1).tolist(),
                "y": np.round(xy[:, 1], 1).tolist(), "r": round(float(r), 2), "spots": int(len(bc)), "colour": colour}

    def _corr(self, measure: str, min_cells: float):
        v = self._values(measure)
        keep = self.mean[self.types].sum(axis=1) >= min_cells
        return np.nan_to_num(np.corrcoef(v[keep].to_numpy().T)), keep

    def together(self, measure: str = "share", min_cells: float = 0.5):
        """How cell types vary together across spots: correlation of their values over every spot where any is present."""
        c, keep = self._corr(measure, float(min_cells))
        # Intent: order cell types so that those found together sit next to each other.
        from scipy.cluster.hierarchy import leaves_list, linkage
        from scipy.spatial.distance import squareform
        d = np.clip(1 - c, 0, 2)
        np.fill_diagonal(d, 0)
        order = leaves_list(linkage(squareform(d, checks=False), "average")) if len(self.types) > 2 else np.arange(len(self.types))
        types = [self.types[i] for i in order]
        mat = c[np.ix_(order, order)]
        pairs = sorted(((self.types[i], self.types[j], round(float(c[i, j]), 3)) for i in range(len(self.types)) for j in range(i + 1, len(self.types))),
                       key=lambda p: -p[2])
        self.state["together"] = {"measure": measure, "min_cells": float(min_cells)}
        self._record("compared cell types across spots", measure=measure, min_cells=float(min_cells), spots=int(keep.sum()),
                     top=[list(p) for p in pairs[:3]])
        return {"types": types, "corr": np.round(mat, 3).tolist(), "pairs": [list(p) for p in pairs], "spots": int(keep.sum()), "measure": measure}

    def signature(self, cell_type: str, n: int = 15):
        if self.sig is None:
            raise ValueError("No reference signatures were found in the results.")
        if cell_type not in self.sig.columns:
            raise ValueError(f"No cell type called {cell_type}.")
        s = self.sig[cell_type]
        spec = s / self.sig.sum(axis=1).replace(0, np.nan)
        top = spec[s >= s.median()].sort_values(ascending=False).head(int(n))
        return {"type": cell_type, "genes": [{"gene": g, "expression": round(float(s[g]), 3), "specificity": round(float(top[g]), 3)} for g in top.index]}

    def export(self):
        out = self.res / "final"
        out.mkdir(exist_ok=True)
        shutil.copy(self.res / "cell2location" / "abundance_mean.csv", out / "cell_abundance_mean.csv")
        if (self.res / "cell2location" / "abundance_q05.csv").exists():
            shutil.copy(self.res / "cell2location" / "abundance_q05.csv", out / "cell_abundance_q05.csv")
        share = self._values("share")
        pd.concat([self.mean[["sample", "barcode"]], share.round(4)], axis=1).to_csv(out / "cell_type_shares.csv", index=False)
        dom = pd.DataFrame({"sample": self.mean["sample"], "barcode": self.mean["barcode"], "main_type": share.idxmax(axis=1),
                            "share": share.max(axis=1).round(4), "cells": self.mean[self.types].sum(axis=1).round(2)})
        dom.to_csv(out / "main_cell_type.csv", index=False)
        t = self.state.get("together")
        if t:
            c, _ = self._corr(t["measure"], t["min_cells"])
            pd.DataFrame(np.round(c, 4), index=self.types, columns=self.types).to_csv(out / "cell_types_together.csv")
        files = sorted(p.name for p in out.iterdir())
        self._record("exported cell-type tables", files=files)
        return {"files": files}

    def files(self):
        out = self.res / "final"
        return [{"name": f"final/{f.name}", "size": f.stat().st_size} for f in sorted(out.glob("*"))] if out.exists() else []
