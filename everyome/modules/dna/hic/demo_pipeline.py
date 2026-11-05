"""Stand-in for nf-core/hic on the demo cluster (no Nextflow, Bowtie 2 or containers there).

For each sample it writes what the real pipeline writes, where it writes it: HiC-Pro's statistics, balanced contact
maps at each resolution asked for (<sample>.<res>_balanced.cool), the multi-resolution map (<sample>.mcool),
compartments (cooltools eigs-cis: <sample>.<res>_compartments.cis.vecs.tsv, without a phasing track, so the sign
of each chromosome is arbitrary, as on a real run), insulation scores and HiCExplorer TADs. The contacts are the demo
genome's (demo_data.py), so the tests know the truth.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from everyome.core.demo import nfstub

from . import cool
from .demo_data import BASE, CHROMS, compartment_of, contacts, truth

TASKS = ["BOWTIE2_ALIGN", "TRIM_READS", "BOWTIE2_ALIGN_TRIMMED", "MERGE_BOWTIE2", "COMBINE_MATES", "GET_VALID_INTERACTION",
         "MERGE_VALID_INTERACTION", "MERGE_STATS", "HICPRO2PAIRS", "COOLER_CLOAD", "COOLER_BALANCE", "COOLER_ZOOMIFY",
         "HIC_PLOT_DIST_VS_COUNTS", "COOLTOOLS_EIGSCIS", "COOLTOOLS_INSULATION", "HIC_FIND_TADS", "MULTIQC"]


def _res(nfp: dict, key: str, default: str) -> list[int]:
    out = []
    for r in str(nfp.get(key, default) or "").split(","):
        r = r.strip()
        if r.isdigit() and int(r) % BASE == 0:
            out.append(int(r))
        elif r:
            print(f"[demo] {key}: {r} is not a multiple of the demo's {BASE:,} bp bins; skipped.", flush=True)
    return out


def _stats(d: Path, s: str, total: int, cis: int, trans: int, short: int, long: int):
    d.mkdir(parents=True, exist_ok=True)
    dup = int(total * 0.08)
    (d / f"{s}_allValidPairs.mergestat").write_text(
        f"valid_interaction\t{total + dup}\nvalid_interaction_rmdup\t{total}\ntrans_interaction\t{trans}\ncis_interaction\t{cis}\n"
        f"cis_shortRange\t{short}\ncis_longRange\t{long}\n")
    valid = total + dup
    de, rl, sc, se, fi = int(valid * .09), int(valid * .02), int(valid * .01), int(valid * .03), int(valid * .02)
    (d / f"{s}.mRSstat").write_text(
        f"## Hi-C processing\nValid_interaction_pairs\t{valid}\nValid_interaction_pairs_FF\t{valid // 4}\nValid_interaction_pairs_RR\t{valid // 4}\n"
        f"Valid_interaction_pairs_RF\t{valid // 4}\nValid_interaction_pairs_FR\t{valid - 3 * (valid // 4)}\nDangling_end_pairs\t{de}\n"
        f"Religation_pairs\t{rl}\nSelf_Cycle_pairs\t{sc}\nSingle-end_pairs\t{se}\nFiltered_pairs\t{fi}\nDumped_pairs\t0\n")
    reported = valid + de + rl + sc + se + fi
    processed = int(reported / 0.78)
    pct = lambda v: f"{100 * v / processed:.3f}"
    un, lq = int(processed * .12), int(processed * .05)
    (d / f"{s}.mpairstat").write_text(
        f"Total_pairs_processed\t{processed}\t100.000\nUnmapped_pairs\t{un}\t{pct(un)}\nLow_qual_pairs\t{lq}\t{pct(lq)}\n"
        f"Unique_paired_alignments\t{reported}\t{pct(reported)}\nMultiple_pairs_alignments\t{processed - reported - un - lq}\t"
        f"{pct(processed - reported - un - lq)}\nReported_pairs\t{reported}\t{pct(reported)}\n")


def main():
    run = nfstub.run_dir()
    _, nfp = nfstub.load(run)
    out = Path(nfp["outdir"])
    samples = list(dict.fromkeys(r["sample"] for r in csv.DictReader(open(nfp["input"]))))
    maps = sorted(set(_res(nfp, "bin_size", "1000000,500000") + _res(nfp, "res_tads", "40000,20000")
                      + _res(nfp, "res_compartments", "250000") + _res(nfp, "res_dist_decay", "1000000")))
    zoom = (_res(nfp, "res_zoomify", "5000") or [BASE])[0]
    trace, t = nfstub.Trace(run), truth()
    nfstub.run_tasks(trace, "NFCORE_HIC:HIC", TASKS, lambda task: samples if task != "MULTIQC" else [None])
    for s in samples:
        b1, b2, c = contacts(s, t)
        coold = out / "contact_maps" / "cool"
        coold.mkdir(parents=True, exist_ok=True)
        for res in maps:
            x1, x2, xc = (b1, b2, c) if res == BASE else cool.coarsen(CHROMS, BASE, res // BASE, b1, b2, c)
            cool.write_cool(coold / f"{s}.{res}_balanced.cool", CHROMS, res, x1, x2, xc)
        factors = [k for k in (1, 2, 4, 8, 16, 32) if zoom * k <= 320_000]
        if not nfp.get("skip_mcool"):
            x1, x2, xc = (b1, b2, c) if zoom == BASE else cool.coarsen(CHROMS, BASE, zoom // BASE, b1, b2, c)
            cool.write_mcool(coold / f"{s}.mcool", CHROMS, zoom, factors, x1, x2, xc)
        tot = cool.Cool(coold / f"{s}.mcool", zoom).totals() if (coold / f"{s}.mcool").exists() else {"cis": int(c.sum()), "trans": 0, "short": 0, "long": 0}
        _stats(out / "hicpro" / "stats" / s, s, tot["cis"] + tot["trans"], tot["cis"], tot["trans"], tot["short"], tot["long"])
        if not nfp.get("skip_compartments"):
            for res in _res(nfp, "res_compartments", "250000"):
                C, rows = cool.Cool(coold / f"{s}.{res}_balanced.cool"), []
                for k, (ch, _) in enumerate(CHROMS):
                    lo, hi = C.chrom_bins(ch)
                    # Intent: without a phasing track the eigenvector's sign is arbitrary. Orient it from the truth,
                    # then turn chr2 the wrong way round, so the demo shows why Everyome orients it by GC content.
                    a = np.array([compartment_of(t, ch, i * res + res // 2) == "A" for i in range(hi - lo)], float)
                    e = cool.eigenvector(C.matrix(lo, hi), phase=a)
                    e = -e if k == 1 else e
                    for i, v in enumerate(e):
                        rows.append(f"{ch}\t{i * res}\t{min((i + 1) * res, CHROMS[k][1])}\t{C.weight[lo + i]:.6g}\t{'' if np.isnan(v) else f'{v:.6f}'}\t\t")
                d = out / "compartments"
                d.mkdir(exist_ok=True)
                (d / f"{s}.{res}_compartments.cis.vecs.tsv").write_text("chrom\tstart\tend\tweight\tE1\tE2\tE3\n" + "\n".join(rows) + "\n")
                (d / f"{s}.{res}_compartments.cis.lam.txt").write_text("\tlam1\tlam2\tlam3\n")
        if not nfp.get("skip_tads"):
            for res in _res(nfp, "res_tads", "40000,20000"):
                C = cool.Cool(coold / f"{s}.{res}_balanced.cool")
                ins, dom, bnd = ["chrom\tstart\tend\tis_bad_bin\tlog2_insulation_score_5\tboundary_strength_5\tis_boundary_5"], [], []
                for ch, n in CHROMS:
                    lo, hi = C.chrom_bins(ch)
                    sc = cool.insulation(C.band(lo, hi, 10), 5)
                    strong = dict(cool.boundaries(sc, 0.2))
                    for i, v in enumerate(sc):
                        ins.append(f"{ch}\t{i * res}\t{min((i + 1) * res, n)}\t{'True' if np.isnan(C.weight[lo + i]) else 'False'}\t"
                                   f"{'' if np.isnan(v) else f'{v:.5f}'}\t{f'{strong[i]:.5f}' if i in strong else ''}\t{i in strong}")
                    # Intent: HiCExplorer's own calls, made here from the truth (one bin off at times), as a second opinion.
                    rng = np.random.default_rng(res + len(ch))
                    edges = [0] + [b + res * int(rng.integers(-1, 2)) for b in t["boundaries"][ch]] + [n]
                    for k, (a, b) in enumerate(zip(edges, edges[1:])):
                        dom.append(f"{ch}\t{a}\t{b}\tID_{ch}_{k}\t0.5\t.")
                    bnd += [f"{ch}\t{b - res // 2}\t{b + res // 2}\tB{k}\t1.0\t." for k, b in enumerate(edges[1:-1])]
                ins_d, hx = out / "tads" / "insulation", out / "tads" / "hicExplorer"
                ins_d.mkdir(parents=True, exist_ok=True)
                hx.mkdir(parents=True, exist_ok=True)
                (ins_d / f"{s}.{res}_balanced_insulation.tsv").write_text("\n".join(ins) + "\n")
                (hx / f"{s}.{res}_balanced_hicfindtads_domains.bed").write_text("\n".join(dom) + "\n")
                (hx / f"{s}.{res}_balanced_hicfindtads_boundaries.bed").write_text("\n".join(bnd) + "\n")
    nfstub.placeholder_report(out / "multiqc" / "multiqc_report.html", "MultiQC report",
                              "On a real cluster this is nf-core/hic's full quality report (mapping, pairing and valid-pair statistics).")
    (out / "pipeline_info").mkdir(exist_ok=True)
    (run / "demo_truth.json").write_text(json.dumps(t))
    print(f"Demo stand-in for nf-core/hic: {len(samples)} samples, maps at {', '.join(f'{r:,}' for r in maps)} bp", flush=True)


if __name__ == "__main__":
    main()
