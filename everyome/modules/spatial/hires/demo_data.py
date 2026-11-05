"""Demo data for high-resolution spatial: two Visium HD-style sections (Space Ranger 'outs' with binned_outputs at 8 and
16 µm), over a tissue with four bands of cell types and, in the treated section, an immune patch.

At 8 µm a bin is about one cell; at 16 µm, four bins are summed, so bins at band edges mix two types.
.demo_truth/markers.json gives each type's planted marker genes.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import scipy.io as sio
import scipy.sparse as sp

TYPES = ["epidermis", "gastrodermis", "muscle", "neuron", "immune"]
SECTIONS = {"hd_control": False, "hd_treated": True}
GRID = 90                 # 8-µm bins per side: a 720 µm square
UM_PER_PX = 0.25          # full-resolution image pixels
LOWRES = 600              # the low-resolution image's size in pixels
N_GENES, N_MARKERS = 300, 15


def _write(out: Path, X, bcs, rows, cols, xpx, ypx, genes, scalef, image):
    m = out / "filtered_feature_bc_matrix"
    m.mkdir(parents=True, exist_ok=True)
    with gzip.open(m / "matrix.mtx.gz", "wb") as fh:
        sio.mmwrite(fh, sp.csr_matrix(X).T.tocoo().astype(np.int64))
    with gzip.open(m / "barcodes.tsv.gz", "wt") as fh:
        fh.write("".join(b + "\n" for b in bcs))
    with gzip.open(m / "features.tsv.gz", "wt") as fh:
        fh.write("".join(f"DEMO{i:05d}\t{g}\tGene Expression\n" for i, g in enumerate(genes)))
    s = out / "spatial"
    s.mkdir(exist_ok=True)
    with open(s / "tissue_positions.csv", "w") as fh:
        fh.write("barcode,in_tissue,array_row,array_col,pxl_row_in_fullres,pxl_col_in_fullres\n")
        fh.write("".join(f"{b},1,{r},{c},{y:.1f},{x:.1f}\n" for b, r, c, x, y in zip(bcs, rows, cols, xpx, ypx)))
    (s / "scalefactors_json.json").write_text(json.dumps({"tissue_lowres_scalef": scalef, "tissue_hires_scalef": scalef * 3,
                                                          "microns_per_pixel": UM_PER_PX}))
    image.save(s / "tissue_lowres_image.png")


def build(root: Path):
    from PIL import Image, ImageDraw
    rng = np.random.default_rng(41)
    genes = [f"g{i:04d}" for i in range(N_GENES)]
    prof = np.tile(rng.lognormal(-0.5, 1.0, size=N_GENES), (len(TYPES), 1))
    markers = {}
    for k, t in enumerate(TYPES):
        rows = list(range(k * N_MARKERS, (k + 1) * N_MARKERS))
        prof[k, rows] *= 12
        for j, g in enumerate(rows):
            genes[g] = f"{t[:4]}{j + 1}"
        markers[t] = [genes[g] for g in rows]
    full_px = GRID * 8 / UM_PER_PX
    scalef = LOWRES / full_px
    for name, treated in SECTIONS.items():
        r, c = np.meshgrid(np.arange(GRID), np.arange(GRID), indexing="ij")
        r, c = r.ravel(), c.ravel()
        # Intent: four horizontal bands, wavy so their edges cut through bins; an immune patch in the treated section.
        wave = 4 * np.sin(c / 9)
        t = np.digitize(r + wave, [GRID * 0.25, GRID * 0.5, GRID * 0.75])
        if treated:
            t = np.where(np.hypot(r - GRID * 0.38, c - GRID * 0.7) < 9, 4, t)
        lib = np.exp(rng.normal(np.log(60), 0.4, len(r)))
        P = prof[t] / prof[t].sum(1, keepdims=True)
        X8 = rng.poisson(P * lib[:, None])
        xpx, ypx = (c + 0.5) * 8 / UM_PER_PX, (r + 0.5) * 8 / UM_PER_PX
        img = Image.new("RGB", (LOWRES, LOWRES), (246, 238, 240))
        d = ImageDraw.Draw(img)
        shade = [(236, 200, 214), (226, 214, 228), (214, 196, 204), (200, 188, 214), (190, 160, 190)]
        for i in range(len(r)):                         # Intent: a pale "stain" so the picture reads as tissue
            x0, y0 = xpx[i] * scalef, ypx[i] * scalef
            d.rectangle([x0 - 3, y0 - 3, x0 + 3, y0 + 3], fill=shade[t[i]])
        out = root / name / "outs" / "binned_outputs"
        _write(out / "square_008um", X8, [f"s_008um_{a:05d}_{b:05d}-1" for a, b in zip(r, c)], r, c, xpx, ypx, genes, scalef, img)
        # 16 µm: sum each 2 × 2 block of 8-µm bins.
        r2, c2 = r // 2, c // 2
        key = r2 * GRID + c2
        uniq, inv = np.unique(key, return_inverse=True)
        X16 = sp.csr_matrix((np.ones(len(r)), (inv, np.arange(len(r)))), shape=(len(uniq), len(r))) @ sp.csr_matrix(X8)
        rr, cc = uniq // GRID, uniq % GRID
        _write(out / "square_016um", X16, [f"s_016um_{a:05d}_{b:05d}-1" for a, b in zip(rr, cc)], rr, cc,
               (cc + 0.5) * 16 / UM_PER_PX, (rr + 0.5) * 16 / UM_PER_PX, genes, scalef, img)
    truth = root / ".demo_truth"
    truth.mkdir(parents=True, exist_ok=True)
    (truth / "markers.json").write_text(json.dumps(markers))
