"""Build the Visium demo data: two Space Ranger 'outs' folders for a toy skin section, where the truth is known.

<root> = <demo cluster>/data/spatial.visium/
  skin_control/outs/, skin_treated/outs/   each laid out as Space Ranger writes it:
    filtered_feature_bc_matrix/ (matrix.mtx.gz, barcodes.tsv.gz, features.tsv.gz)
    spatial/ (tissue_positions.csv, scalefactors_json.json, tissue_lowres_image.png)
  truth.json   each spot's true region, for tests

Four layers run across the tissue (epidermis, dermis, a hair follicle, muscle);
the treated section also has an immune infiltrate with an interferon response.
Spots near a boundary mix the neighbouring regions, as real 55 µm spots do.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import scipy.io as sio
import scipy.sparse as sp

REGIONS = {   # name: (marker genes, colour on the toy H&E image)
    "Epidermis": (["KRT14", "KRT5", "KRT1", "KRT10", "LOR"], (176, 92, 150)),
    "Dermis": (["COL1A1", "COL1A2", "DCN", "LUM", "PDGFRA"], (236, 176, 200)),
    "Hair follicle": (["KRT17", "SOX9", "LHX2", "KRT75", "TCHH"], (150, 80, 160)),
    "Muscle": (["ACTA2", "MYH11", "DES", "CNN1", "TAGLN"], (214, 120, 140)),
    "Immune infiltrate": (["PTPRC", "CD74", "ISG15", "IFIT1", "CXCL10"], (120, 70, 170)),
}
MITO = [f"MT-{g}" for g in ["ND1", "ND2", "CO1", "CO2", "ATP6", "CO3", "ND4", "ND5", "CYB"]]
N_OTHER, ROWS, COLS, LOWRES, SCALE = 800, 44, 70, 600, 0.1


def _region(xn: np.ndarray, yn: np.ndarray, treated: bool) -> np.ndarray:
    """Soft membership of each spot in each region (rows sum to 1); xn, yn run 0..1 across the tissue."""
    s = lambda d, w=0.025: 1 / (1 + np.exp(-d / w))          # smooth step: spots near a boundary mix both sides
    epi, mus = s(0.22 - yn), s(yn - 0.78)
    fol = np.exp(-(((xn - 0.35) / 0.07) ** 2 + ((yn - 0.42) / 0.16) ** 2)) * (1 - epi)
    # Intent: a patch big and distinct enough (about 130 spots, flat-topped) to come out as its own region on any platform.
    imm = np.minimum(1, 1.6 * np.exp(-(((xn - 0.7) / 0.13) ** 2 + ((yn - 0.5) / 0.13) ** 2))) * (1 - epi) if treated else np.zeros_like(xn)
    der = np.clip(1 - epi - mus - fol - imm, 0, None)
    w = np.stack([epi, der, fol, mus, imm], 1)
    return w / w.sum(1, keepdims=True)


def _image(path: Path, regions: np.ndarray, px: np.ndarray, inside, rng):
    from PIL import Image, ImageDraw, ImageFilter
    im = Image.new("RGB", (LOWRES, LOWRES), (246, 242, 240))
    d = ImageDraw.Draw(im)
    colours = np.array([c for _, c in REGIONS.values()], float)
    for (x, y), w, ok in zip(px, regions, inside):
        if ok:
            c = tuple(int(v) for v in np.clip(w @ colours + rng.normal(0, 8, 3), 0, 255))
            d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=c)
    im.filter(ImageFilter.GaussianBlur(2.5)).save(path)


def _sample(out: Path, name: str, treated: bool, depth: float, seed: int, genes: list[str], prof: np.ndarray) -> dict:
    rng = np.random.default_rng(seed)
    out.mkdir(parents=True, exist_ok=True)
    # Visium's grid: rows of spots, every other row shifted by half a spot.
    r, c = np.meshgrid(np.arange(ROWS), np.arange(COLS), indexing="ij")
    r, c = r.ravel(), c.ravel()
    x = (c + 0.5 * (r % 2) + 1.5) / (COLS + 2) * LOWRES
    y = (r + 1.5) / (ROWS + 2) * LOWRES * 0.92 + 20
    xn, yn = (x - x.min()) / np.ptp(x), (y - y.min()) / np.ptp(y)
    inside = ((xn - 0.5) / 0.48) ** 2 + ((yn - 0.5) / 0.47) ** 2 <= 1
    w = _region(xn, yn, treated)
    edge = inside & (((xn - 0.5) / 0.48) ** 2 + ((yn - 0.5) / 0.47) ** 2 > 0.82)
    bcs = ["".join(rng.choice(list("ACGT"), 16)) + "-1" for _ in range(len(r))]
    keep = np.where(inside)[0]
    P = w[keep] @ prof
    dmg = edge[keep] & (rng.random(len(keep)) < 0.35)          # damaged tissue at the cut edge: mitochondrial reads
    P[np.ix_(dmg, [genes.index(g) for g in MITO])] *= 12
    P /= P.sum(1, keepdims=True)
    lib = np.exp(rng.normal(np.log(depth), 0.35, len(keep)))
    lib[dmg] *= 0.4
    X = sp.csr_matrix(rng.poisson(P * lib[:, None]).astype(np.float32))
    m = out / "filtered_feature_bc_matrix"
    m.mkdir(exist_ok=True)
    with gzip.open(m / "matrix.mtx.gz", "wb") as fh:
        sio.mmwrite(fh, X.T.tocoo().astype(np.int64))           # genes in rows, spots in columns, as 10x writes it
    with gzip.open(m / "barcodes.tsv.gz", "wt") as fh:
        fh.write("".join(bcs[i] + "\n" for i in keep))
    with gzip.open(m / "features.tsv.gz", "wt") as fh:
        fh.write("".join(f"ENSDEMO{i:05d}\t{g}\tGene Expression\n" for i, g in enumerate(genes)))
    s = out / "spatial"
    s.mkdir(exist_ok=True)
    with open(s / "tissue_positions.csv", "w") as fh:
        fh.write("barcode,in_tissue,array_row,array_col,pxl_row_in_fullres,pxl_col_in_fullres\n")
        for i in range(len(r)):
            fh.write(f"{bcs[i]},{int(inside[i])},{r[i]},{c[i]},{y[i] / SCALE:.1f},{x[i] / SCALE:.1f}\n")
    (s / "scalefactors_json.json").write_text(json.dumps({"tissue_lowres_scalef": SCALE, "tissue_hires_scalef": SCALE * 3.33,
                                                          "spot_diameter_fullres": LOWRES / (COLS + 2) / SCALE * 0.62, "fiducial_diameter_fullres": 1.0}))
    _image(s / "tissue_lowres_image.png", w, np.c_[x, y], inside, rng)
    names = list(REGIONS)
    return {bcs[i]: {"region": names[int(np.argmax(w[i]))], "damaged": bool(d)} for i, d in zip(keep, dmg)}


def build(root: Path, seed: int = 9) -> Path:
    rng = np.random.default_rng(seed)
    root.mkdir(parents=True, exist_ok=True)
    named = [g for gs, _ in REGIONS.values() for g in gs]
    genes = named + MITO + [f"GENE{i:04d}" for i in range(N_OTHER)]
    base = np.exp(rng.normal(0, 1.0, len(genes))) * 0.3
    base[[genes.index(g) for g in MITO]] = 5
    prof = np.tile(base, (len(REGIONS), 1))
    for k, (gs, _) in enumerate(REGIONS.values()):
        prof[k, [genes.index(g) for g in gs]] *= 40
    truth = {"skin_control": _sample(root / "skin_control" / "outs", "skin_control", False, 4000, seed + 1, genes, prof),
             "skin_treated": _sample(root / "skin_treated" / "outs", "skin_treated", True, 2500, seed + 2, genes, prof)}
    (root / "truth.json").write_text(json.dumps(truth))
    return root
