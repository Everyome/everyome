"""Predicted protein structures: read them, compare them, and find the parts that can be trusted.

Every structure predictor nf-core/proteinfold runs writes a PDB file with the per-residue confidence (pLDDT,
0–100) in the B-factor column, a table of pLDDT for each ranked model and, for most methods, the predicted
aligned error (PAE): the expected error in Å at residue j when the model is superposed on residue i.
Pure Python with numpy, so it runs on any cluster Python with Everyome.
"""
from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np

THREE = {"ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
         "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
         "SEC": "U", "PYL": "O", "MSE": "M"}
# pLDDT bands as AlphaFold reports them.
BANDS = [("very high", 90, 101), ("confident", 70, 90), ("low", 50, 70), ("very low", 0, 50)]


def _open(path: Path):
    return gzip.open(path, "rt") if str(path).endswith(".gz") else open(path)


def read_pdb(path: Path) -> dict:
    """One entry per residue (first model only): chain, number, amino acid, CA position and pLDDT (from the B-factor)."""
    res, seen = [], set()
    with _open(path) as fh:
        for line in fh:
            if line.startswith("ENDMDL"):
                break
            if not line.startswith(("ATOM", "HETATM")) or line[12:16].strip() != "CA":
                continue
            chain, num, ins = line[21].strip() or "A", int(line[22:26]), line[26].strip()
            if (chain, num, ins) in seen:
                continue                                   # alternate locations: keep the first
            seen.add((chain, num, ins))
            res.append({"chain": chain, "num": num, "aa": THREE.get(line[17:20].strip(), "X"),
                        "xyz": [float(line[30:38]), float(line[38:46]), float(line[46:54])],
                        "plddt": float(line[60:66]) if line[60:66].strip() else 0.0})
    if not res:
        raise ValueError(f"{path.name} has no residues (no CA atoms).")
    # Intent: some methods write pLDDT as 0–1; show it on the usual 0–100 scale.
    if max(r["plddt"] for r in res) <= 1.0:
        for r in res:
            r["plddt"] *= 100
    return {"residues": res, "chains": list(dict.fromkeys(r["chain"] for r in res))}


def read_table(path: Path) -> list[list[float]]:
    rows = []
    for line in path.read_text().splitlines():
        parts = line.split()
        try:
            rows.append([float(x) for x in parts])
        except ValueError:
            continue                                       # a header line
    return rows


def plddt_ranks(path: Path) -> dict:
    """{rank_0: [...], rank_1: [...]} from <id>_plddt.tsv (first column is the position)."""
    lines = path.read_text().splitlines()
    head = lines[0].split("\t")[1:] if lines else []
    cols = list(zip(*[[float(x) for x in l.split("\t")[1:]] for l in lines[1:] if l.strip()])) if len(lines) > 1 else []
    return {h: [round(v, 2) for v in c] for h, c in zip(head, cols)}


def scores(path: Path) -> dict[int, float]:
    """{rank: score} from a pTM or ipTM table (rank, score per line)."""
    out = {}
    for line in path.read_text().splitlines():
        p = line.split()
        if len(p) >= 2:
            try:
                out[int(float(p[0]))] = float(p[1])
            except ValueError:
                pass
    return out


def summary(plddt: list[float]) -> dict:
    n = max(1, len(plddt))
    return {"mean_plddt": round(sum(plddt) / n, 1),
            "bands": {name: round(100 * sum(lo <= v < hi for v in plddt) / n, 1) for name, lo, hi in BANDS}}


def kabsch_rmsd(a: np.ndarray, b: np.ndarray, weights: np.ndarray | None = None) -> float:
    """RMSD between two sets of matched points after the best superposition (Kabsch, 1976)."""
    w = np.ones(len(a)) if weights is None else weights
    w = w / w.sum()
    ca, cb = (a * w[:, None]).sum(0), (b * w[:, None]).sum(0)
    A, B = a - ca, b - cb
    H = (A * w[:, None]).T @ B
    U, S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1, 1, d]) @ U.T
    diff = (A @ R.T) - B
    return float(np.sqrt((w * (diff ** 2).sum(1)).sum()))


def domains(pae: np.ndarray, plddt: list[float], min_plddt: float = 70, max_pae: float = 5.0, min_len: int = 20) -> list[dict]:
    """Confidently placed regions that move as one unit: confident residues joined where their PAE to each other is low.

    A simple, transparent rule rather than graph clustering: confident stretches are found first, then neighbouring
    stretches are merged when the mean PAE between them (both ways) is below max_pae.
    """
    n = len(plddt)
    ok = [v >= min_plddt for v in plddt]
    runs, i = [], 0
    while i < n:
        if ok[i]:
            j = i
            while j + 1 < n and ok[j + 1]:
                j += 1
            if j - i + 1 >= 5:
                runs.append([(i, j)])
            i = j + 1
        else:
            i += 1
    idx = lambda g: np.concatenate([np.arange(a, b + 1) for a, b in g])
    merged = True
    while merged and len(runs) > 1:
        merged, best = False, None
        for x in range(len(runs)):
            for y in range(x + 1, len(runs)):
                ix, iy = idx(runs[x]), idx(runs[y])
                m = (pae[np.ix_(ix, iy)].mean() + pae[np.ix_(iy, ix)].mean()) / 2
                if m < max_pae and (best is None or m < best[0]):
                    best = (m, x, y)
        if best:
            _, x, y = best
            runs[x] = sorted(runs[x] + runs[y])
            del runs[y]
            merged = True
    out = []
    for g in runs:
        ii = idx(g)
        if len(ii) < min_len:
            continue
        within = pae[np.ix_(ii, ii)].mean()
        out.append({"ranges": [[a + 1, b + 1] for a, b in g], "residues": int(len(ii)), "mean_plddt": round(float(np.mean([plddt[k] for k in ii])), 1),
                    "mean_pae_within": round(float(within), 1)})
    out.sort(key=lambda d: d["ranges"][0][0])
    for k, d in enumerate(out, 1):
        d["name"] = f"D{k}"
    return out


def write_pdb(path: Path, src: Path, keep: set[tuple[str, int]] | None = None, header: str = "") -> int:
    """Copy a PDB, keeping only residues in keep (chain, number) if given; returns the residues written."""
    n, last = 0, None
    with _open(src) as fh, open(path, "w") as out:
        if header:
            out.write("".join(f"REMARK 250 {l}\n" for l in header.splitlines()))
        for line in fh:
            if line.startswith(("ATOM", "HETATM", "ANISOU", "TER")) and len(line) > 26:
                key = (line[21].strip() or "A", int(line[22:26]))
                if keep is not None and key not in keep:
                    continue
                if line.startswith("ATOM") and key != last:
                    n, last = n + 1, key
            out.write(line)
    return n
