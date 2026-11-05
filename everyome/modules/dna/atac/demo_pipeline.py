"""Stand-in for nf-core/atacseq on the demo cluster (no Nextflow or containers there).

Writes what the real pipeline writes that Everyome reads, where it writes it: each library's peaks (MACS2
narrowPeak/broadPeak), the FRiP and peak-count tables in qc/, the consensus peaks and their featureCounts table, a
placeholder MultiQC report, and a Nextflow trace. A library 'calls' a demo site when it has enough reads there, plus a
few chance peaks of its own, so peak sets differ between libraries as they do in real data. No bigWigs are written.
"""
from __future__ import annotations

import csv
import json
import zlib
from pathlib import Path

import numpy as np

from everyome.core.demo import nfstub

from . import helpers
from .demo_data import CHROMS

TASKS = ["FASTQC", "TRIMGALORE", "BWA_MEM", "PICARD_MERGESAMFILES", "PICARD_MARKDUPLICATES", "BAMTOOLS_FILTER",
         "BEDTOOLS_GENOMECOV", "MACS2_CALLPEAK", "FRIP_SCORE", "MACS2_CONSENSUS", "SUBREAD_FEATURECOUNTS", "DESEQ2_QC", "MULTIQC"]
PER_LIB = {"FASTQC", "TRIMGALORE", "BWA_MEM", "PICARD_MARKDUPLICATES", "BAMTOOLS_FILTER", "BEDTOOLS_GENOMECOV", "MACS2_CALLPEAK", "FRIP_SCORE"}


def main():
    run = nfstub.run_dir()
    params, nfp = nfstub.load(run)
    rows = list(csv.DictReader(open(nfp["input"])))
    truth_dir = Path(rows[0]["fastq_1"]).parent.parent / ".demo_truth"
    truth = json.loads((truth_dir / "sites.json").read_text())
    frip = json.loads((truth_dir / "frip.json").read_text())
    libs = list(dict.fromkeys(f"{r['sample']}_REP{int(r['replicate'])}" for r in rows))
    known = [l for l in libs if l in truth["depth"]]
    for l in libs:
        if l not in known:
            print(f"{l}: the demo cluster only has reads for the demo libraries ({', '.join(truth['depth'])}); skipped.", flush=True)
    nfstub.run_tasks(nfstub.Trace(run), "NFCORE_ATACSEQ:ATACSEQ", TASKS, lambda t: known if t in PER_LIB else [None])

    sites, call_at = truth["sites"], truth["call_at"]
    pdir = run / helpers.peak_dir(params)
    (pdir / "qc").mkdir(parents=True, exist_ok=True)
    (pdir / "consensus").mkdir(parents=True, exist_ok=True)
    ext = "narrowPeak" if params.get("narrow_peak") else "broadPeak"
    called, noise = {}, {}
    for lib in known:
        rng = np.random.default_rng(zlib.crc32(lib.encode()))
        d = truth["depth"][lib]
        called[lib] = [i for i, s in enumerate(sites) if s["counts"][lib] / d >= call_at]
        # Intent: a few chance peaks of this library alone, away from the real sites (as background noise gives).
        noise[lib] = []
        while len(noise[lib]) < 12:
            c = "chr1" if rng.random() < 0.57 else "chr2"
            a = int(rng.integers(3_000, CHROMS[c] - 3_000))
            if all(s["chrom"] != c or s["end"] < a - 1_500 or s["start"] > a + 1_700 for s in sites):
                noise[lib].append({"chrom": c, "start": a, "end": a + int(rng.integers(160, 320))})
        peaks = [(sites[i], sites[i]["counts"][lib]) for i in called[lib]] + [(n, int(call_at * d)) for n in noise[lib]]
        peaks.sort(key=lambda p: (p[0]["chrom"], p[0]["start"]))
        with open(pdir / f"{lib}.mLb.clN_peaks.{ext}", "w") as fh:
            for k, (s, n) in enumerate(peaks, 1):
                fe = n / d / 6                                      # fold enrichment over a flat background
                p = min(300.0, 2 + n / d / 3)
                fh.write(f"{s['chrom']}\t{s['start']}\t{s['end']}\t{lib}.mLb.clN_peak_{k}\t{int(min(1000, p * 10))}\t.\t"
                         f"{fe:.3f}\t{p:.3f}\t{max(0.0, p - 1.5):.3f}" + (f"\t{(s['end'] - s['start']) // 2}\n" if ext == "narrowPeak" else "\n"))
        (pdir / "qc" / f"{lib}.mLb.clN_peaks.FRiP_mqc.tsv").write_text(
            "#id: 'mlib_frip_score'\n#section_name: 'MERGED LIB: MACS2 peak FRiP score'\n#plot_type: 'bargraph'\n"
            f"{lib}\t{frip[lib]}\n")
        (pdir / "qc" / f"{lib}.mLb.clN_peaks.count_mqc.tsv").write_text(
            "#id: 'mlib_peak_count'\n#section_name: 'MERGED LIB: MACS2 peak count'\n#plot_type: 'bargraph'\n"
            f"{lib}.mLb.clN_peaks\t{len(peaks)}\n")

    # Consensus: every site called in at least one library (min_reps_consensus 1), counted in every library.
    union = sorted({i for l in known for i in called[l]})
    cons = [(sites[i], {l: sites[i]["counts"][l] for l in known}, i) for i in union]
    for l in known:
        rng = np.random.default_rng(zlib.crc32(("bg/" + l).encode()))
        for n in noise[l]:
            cons.append((n, {m: int(call_at * truth["depth"][m]) if m == l else int(rng.poisson(4 * truth["depth"][m])) for m in known}, None))
    cons.sort(key=lambda c: (c[0]["chrom"], c[0]["start"]))
    with open(pdir / "consensus" / "consensus_peaks.mLb.clN.featureCounts.txt", "w") as fh, \
            open(pdir / "consensus" / "consensus_peaks.mLb.clN.bed", "w") as bed:
        fh.write('# Program:featureCounts v2.0.1; Command:"featureCounts" "-F" "SAF" "-O" "--fracOverlap" "0.2" (demo stand-in)\n')
        fh.write("Geneid\tChr\tStart\tEnd\tStrand\tLength\t" + "\t".join(f"{l}.mLb.clN.sorted.bam" for l in known) + "\n")
        for k, (s, c, _) in enumerate(cons, 1):
            fh.write(f"Interval_{k}\t{s['chrom']}\t{s['start'] + 1}\t{s['end']}\t+\t{s['end'] - s['start']}\t" + "\t".join(str(c[l]) for l in known) + "\n")
            bed.write(f"{s['chrom']}\t{s['start']}\t{s['end']}\tInterval_{k}\t.\t+\n")
    # For tests: which consensus intervals are the sites that truly open or close.
    up, down = set(truth["up"]), set(truth["down"])
    (run / "demo_truth.json").write_text(json.dumps({
        "up": [f"Interval_{k}" for k, (_, _, i) in enumerate(cons, 1) if i in up],
        "down": [f"Interval_{k}" for k, (_, _, i) in enumerate(cons, 1) if i in down]}))
    nfstub.placeholder_report(run / helpers.multiqc(params), "MultiQC report",
                              "On a real cluster this is nf-core/atacseq's full quality report.")
    print(f"[demo] nf-core/atacseq stand-in: {len(known)} libraries, {len(cons)} consensus peaks", flush=True)


if __name__ == "__main__":
    main()
