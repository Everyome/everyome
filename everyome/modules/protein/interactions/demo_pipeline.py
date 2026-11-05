"""Stand-in for nf-core/proteinfold's multimer predictions on the demo cluster (no Nextflow, GPUs or databases there).

For each complex in the samplesheet and each method asked for, it writes what the real pipeline writes, where it
writes it: the top-ranked two-chain structure (pLDDT in the B-factor column), the pLDDT table, the PAE, pTM, ipTM and
chain-wise ipTM tables. The 'predictions' are the demo's own complexes (demo_data.py).
"""
from __future__ import annotations

import csv
import zlib
from pathlib import Path

import numpy as np

from everyome.core.demo import nfstub

from ..structure.demo_pipeline import THREE
from .demo_data import truth


def _pdb(path: Path, seqs: list[str], xyz: np.ndarray, chains: list[str], plddt: np.ndarray, method: str) -> None:
    lines, k, seq = [f"REMARK   1 DEMO PREDICTION ({method.upper()} STAND-IN), NOT A REAL MODEL"], 0, "".join(seqs)
    num = {}
    for i, (aa, p, b, ch) in enumerate(zip(seq, xyz, plddt, chains), 1):
        num[ch] = num.get(ch, 0) + 1
        k += 1
        lines.append(f"ATOM  {k:5d}  CA  {THREE.get(aa, 'GLY')} {ch}{num[ch]:4d}    {p[0]:8.3f}{p[1]:8.3f}{p[2]:8.3f}  1.00{b:6.2f}           C")
    path.write_text("\n".join(lines + ["TER", "END"]) + "\n")


def _pae(chains: list[str], plddt: np.ndarray, between: float, rng) -> np.ndarray:
    c = np.array(chains)
    same = c[:, None] == c[None, :]
    within = 1.0 + (100 - np.add.outer(plddt, plddt) / 2) * 0.08
    out = np.where(same, within, between) + rng.normal(0, 0.6, (len(c), len(c)))
    out = np.clip(out, 0.25, 31.75)
    np.fill_diagonal(out, 0.25)
    return out


def main():
    run = nfstub.run_dir()
    _, nfp = nfstub.load(run)
    rows = list(csv.DictReader(open(nfp["input"])))
    methods = [m for m in str(nfp.get("mode", "alphafold2")).split(",") if m]
    out = Path(nfp["outdir"])
    trace, known = nfstub.Trace(run), truth()
    for method in methods:
        base = out / method / (nfp.get("alphafold2_mode", "split_msa_prediction") if method == "alphafold2" else "")
        (base / "top_ranked_structures").mkdir(parents=True, exist_ok=True)
        for row in rows:
            pid = row["id"]
            if pid not in known:
                print(f"{pid}: the demo cluster can only 'predict' the demo complexes ({', '.join(known)}); skipped.", flush=True)
                continue
            p, rng = known[pid], np.random.default_rng(zlib.crc32(f"{pid}/{method}".encode()))
            d = base / pid
            d.mkdir(exist_ok=True)
            _pdb(base / "top_ranked_structures" / f"{pid}.pdb", p["seqs"], p["xyz"], p["chains"], p["plddt"], method)
            (d / f"{pid}_plddt.tsv").write_text("Positions\trank_0\n" + "".join(f"{i}\t{v:.2f}\n" for i, v in enumerate(p["plddt"])))
            (d / "paes").mkdir(exist_ok=True)
            between = 4.5 if pid == "binder" else 26.0
            (d / "paes" / f"{pid}_0_pae.tsv").write_text("".join("\t".join(f"{v:.3f}" for v in r) + "\n"
                                                               for r in _pae(p["chains"], p["plddt"], between, rng)))
            (d / f"{pid}_ptm.tsv").write_text(f"0\t{p['ptm']:.3f}\n")
            (d / f"{pid}_iptm.tsv").write_text(f"0\t{p['iptm']:.3f}\n")
            (d / f"{pid}_chainwise_iptm.tsv").write_text(f"chains\trank_0\nA:B\t{p['iptm']:.3f}\nB:A\t{p['iptm'] - 0.01:.3f}\n")
            trace.task(f"NFCORE_PROTEINFOLD:{method.upper()}:RUN_{method.upper()} ({pid})")
            nfstub.placeholder_report(out / "reports" / f"{pid}_{method}_report.html", f"{method} report for {pid}",
                                      "On a real cluster this is the pipeline's own report.")
    (out / "pipeline_info").mkdir(exist_ok=True)
    print(f"Demo stand-in for nf-core/proteinfold (multimer): {len(rows)} complexes ({', '.join(methods)})", flush=True)


if __name__ == "__main__":
    main()
