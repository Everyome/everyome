"""Stand-in for nf-core/proteinfold on the demo cluster (no Nextflow, GPUs, databases or model weights there).

For each protein in the samplesheet and each method asked for, it writes what the real pipeline writes, where it
writes it: the top-ranked structure (PDB, pLDDT in the B-factor column), the pLDDT table for each ranked model,
and, for methods that make them, the PAE and pTM tables. The 'predictions' are the demo's own structures (see
demo_data.py), changed the way the methods tend to differ: ESMFold is a little less confident, makes no PAE here,
and places the two domains of twodomain differently.
"""
from __future__ import annotations

import csv
import json
import os
import time
import zlib
from pathlib import Path

import numpy as np

from .demo_data import truth

THREE = {"A": "ALA", "R": "ARG", "N": "ASN", "D": "ASP", "C": "CYS", "Q": "GLN", "E": "GLU", "G": "GLY", "H": "HIS", "I": "ILE",
         "L": "LEU", "K": "LYS", "M": "MET", "F": "PHE", "P": "PRO", "S": "SER", "T": "THR", "W": "TRP", "Y": "TYR", "V": "VAL"}
PTM = {"twodomain": 0.58, "hairpin": 0.86, "disordered": 0.29}
NO_PAE = {"esmfold"}


def _pdb(path: Path, seq: str, xyz: np.ndarray, plddt: np.ndarray, method: str) -> None:
    lines = [f"REMARK   1 DEMO PREDICTION ({method.upper()} STAND-IN), NOT A REAL MODEL"]
    for i, (aa, p, b) in enumerate(zip(seq, xyz, plddt), 1):
        lines.append(f"ATOM  {i:5d}  CA  {THREE.get(aa, 'GLY')} A{i:4d}    {p[0]:8.3f}{p[1]:8.3f}{p[2]:8.3f}  1.00{b:6.2f}           C")
    path.write_text("\n".join(lines + ["TER", "END"]) + "\n")


def _pae(regions: list[str], plddt: np.ndarray, rng, between: float) -> np.ndarray:
    n = len(regions)
    r = np.array(regions)
    same = (r[:, None] == r[None, :]) & (r[:, None] != "flexible")
    sep = np.abs(np.subtract.outer(np.arange(n), np.arange(n))) / n
    low = 1.2 + 3.0 * sep + (100 - np.add.outer(plddt, plddt) / 2) * 0.08
    floppy = 16 + 12 * (1 - np.minimum.outer(plddt, plddt) / 100) + rng.normal(0, 1.5, (n, n))
    out = np.where(same, low, np.where((r[:, None] == "flexible") | (r[None, :] == "flexible"), floppy, between + rng.normal(0, 2, (n, n))))
    out = np.clip(out + rng.normal(0, 0.3, (n, n)), 0.25, 31.75)
    np.fill_diagonal(out, 0.25)
    return out


def _rotate_second_domain(xyz: np.ndarray, regions: list[str], deg: float) -> np.ndarray:
    """Swing everything after the linker about the linker's start (a different domain arrangement)."""
    out = xyz.copy()
    first = regions.index("β-sheet domain") if "β-sheet domain" in regions else None
    if first is None:
        return out
    pivot = xyz[first - 22]
    a = np.deg2rad(deg)
    R = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    out[first - 11:] = (xyz[first - 11:] - pivot) @ R.T + pivot
    return out


def main():
    run = Path(os.environ["EVERYOME_RUN_DIR"])
    nfp = json.loads((run / "nf_params.json").read_text())
    rows = list(csv.DictReader(open(nfp["input"])))
    methods = [m for m in str(nfp.get("mode", "alphafold2")).split(",") if m]
    out = Path(nfp["outdir"])
    pause = float(os.environ.get("EVERYOME_DEMO_PAUSE", "1"))
    trace = run / "trace.txt"
    trace.write_text("task_id\thash\tnative_id\tname\tstatus\texit\n")
    known, k = truth(), 0
    for method in methods:
        base = out / method / (nfp.get("alphafold2_mode", "split_msa_prediction") if method == "alphafold2" else "")
        (base / "top_ranked_structures").mkdir(parents=True, exist_ok=True)
        for row in rows:
            pid = row["id"]
            if pid not in known:
                print(f"{pid}: the demo cluster can only 'predict' the demo proteins ({', '.join(known)}); skipped.", flush=True)
                continue
            time.sleep(pause / 2)
            p, rng = known[pid], np.random.default_rng(zlib.crc32(f"{pid}/{method}".encode()))
            xyz, plddt = p["xyz"].copy(), p["plddt"].copy()
            if method == "esmfold":
                xyz = _rotate_second_domain(xyz, p["regions"], 60) + rng.normal(0, 0.4, xyz.shape)
                plddt = np.clip(plddt - 6 + rng.normal(0, 2, len(plddt)), 10, 98)
            elif method != "alphafold2":
                xyz = xyz + rng.normal(0, 0.3, xyz.shape)
                plddt = np.clip(plddt + rng.normal(0, 1.5, len(plddt)), 10, 98.5)
            d = base / pid
            d.mkdir(exist_ok=True)
            _pdb(base / "top_ranked_structures" / f"{pid}.pdb", p["seq"], xyz, plddt, method)
            nranks = 1 if method == "esmfold" else 5
            ranks = [plddt] + [np.clip(plddt - 1.5 * r + rng.normal(0, 1, len(plddt)), 10, 98.5) for r in range(1, nranks)]
            (d / f"{pid}_plddt.tsv").write_text("Positions\t" + "\t".join(f"rank_{r}" for r in range(nranks)) + "\n" +
                                                "".join(f"{i}\t" + "\t".join(f"{x[i]:.2f}" for x in ranks) + "\n" for i in range(len(plddt))))
            if method not in NO_PAE:
                (d / "paes").mkdir(exist_ok=True)
                for r in range(2):
                    pae = _pae(p["regions"], ranks[r], rng, 21 + 2 * r)
                    (d / "paes" / f"{pid}_{r}_pae.tsv").write_text("".join("\t".join(f"{v:.4f}" for v in row_) + "\n" for row_ in pae))
                (d / f"{pid}_ptm.tsv").write_text("".join(f"{r}\t{PTM[pid] - 0.02 * r:.3f}\n" for r in range(nranks)))
            (out / "reports").mkdir(exist_ok=True)
            (out / "reports" / f"{pid}_{method}_report.html").write_text(f"<html><body><p>Demo placeholder for the {method} report of {pid}.</p></body></html>")
            k += 1
            with open(trace, "a") as fh:
                fh.write(f"{k}\tab/{k:06x}\t{1000 + k}\tNFCORE_PROTEINFOLD:{method.upper()}:RUN_{method.upper()} ({pid})\tCOMPLETED\t0\n")
    (out / "pipeline_info").mkdir(exist_ok=True)
    (out / "pipeline_info" / "params.json").write_text(json.dumps(nfp, indent=1))
    print(f"Demo stand-in for nf-core/proteinfold: {k} predictions ({', '.join(methods)})", flush=True)


if __name__ == "__main__":
    main()
