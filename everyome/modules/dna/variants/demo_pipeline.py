"""Stand-in for nf-core/sarek on the demo cluster (no Nextflow, containers or reads to map there).

For each germline caller asked for and each sample, it writes what sarek writes, where it writes it: the caller's
per-sample VCF (variant_calling/<caller>/<sample>/), mosdepth's coverage summary, a placeholder MultiQC report and a
Nextflow trace. The calls are the demo's true variants (demo_data.py) as a caller would see them: true variants at
good depth and quality, a few missed, and a scattering of low-quality false calls that differ from caller to caller.
"""
from __future__ import annotations

import csv
import gzip
import json
import zlib
from pathlib import Path

import numpy as np

from everyome.core.demo import nfstub

from .demo_data import CHROMS, genome

# sarek tool name -> (output folder, file suffix)
CALLERS = {"haplotypecaller": ("haplotypecaller", "haplotypecaller.vcf.gz"), "deepvariant": ("deepvariant", "deepvariant.vcf.gz"),
           "freebayes": ("freebayes", "freebayes.vcf.gz"), "strelka": ("strelka", "strelka.variants.vcf.gz"),
           "mpileup": ("bcftools", "bcftools.vcf.gz")}
TASKS = {"haplotypecaller": "GATK4_HAPLOTYPECALLER", "deepvariant": "DEEPVARIANT_RUNDEEPVARIANT", "freebayes": "FREEBAYES",
         "strelka": "STRELKA_GERMLINE", "mpileup": "BCFTOOLS_MPILEUP"}
GT = {1: "0/1", 2: "1/1"}


def _header(caller: str, sample: str) -> str:
    return "\n".join([
        "##fileformat=VCFv4.2", f"##source={caller} (Everyome demo stand-in, not a real call set)",
        *[f"##contig=<ID={c},length={n}>" for c, n in CHROMS.items()],
        '##FILTER=<ID=PASS,Description="All filters passed">',
        '##FILTER=<ID=RefCall,Description="Genotyping model thinks this site is reference">',
        '##INFO=<ID=DP,Number=1,Type=Integer,Description="Read depth">',
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
        '##FORMAT=<ID=AD,Number=R,Type=Integer,Description="Reads supporting each allele">',
        '##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Read depth">',
        '##FORMAT=<ID=GQ,Number=1,Type=Integer,Description="Genotype quality">',
        "\t".join(["#CHROM", "POS", "ID", "REF", "ALT", "QUAL", "FILTER", "INFO", "FORMAT", sample])]) + "\n"


def calls(caller: str, sample: str, true: list[dict]) -> list[tuple]:
    """(chrom, pos, ref, alt, qual, filter, gt, ad_ref, ad_alt, dp, gq) as this caller would report them."""
    rng = np.random.default_rng(zlib.crc32(f"{caller}/{sample}".encode()))
    g, out = genome(), []
    for v in true:
        d = v["gt"].get(sample, 0)
        # Intent: each caller misses a few true variants, but never the mutant ones (keeps the demo's story clear).
        if d == 0 or (v["kind"] != "mutant" and rng.random() < 0.03):
            continue
        dp = int(rng.integers(15, 46))
        alt_reads = dp if d == 2 else int(rng.binomial(dp, 0.5))
        out.append((v["chrom"], v["pos"], v["ref"], v["alt"], round(float(rng.uniform(40, 900)), 1), "PASS", GT[d],
                    dp - alt_reads, alt_reads, dp, int(rng.integers(30, 100))))
    taken = {(v["chrom"], v["pos"]) for v in true}
    for _ in range(18):
        c = str(rng.choice(list(CHROMS)))
        pos = int(rng.integers(100, CHROMS[c] - 100))
        if (c, pos) in taken:
            continue
        ref = g[c][pos - 1]
        alt = str(rng.choice([b for b in "ACGT" if b != ref]))
        dp = int(rng.integers(3, 10))
        a = max(1, int(rng.binomial(dp, 0.3)))
        refcall = caller == "deepvariant" and rng.random() < 0.5
        out.append((c, pos, ref, alt, round(float(rng.uniform(2, 25)), 1), "RefCall" if refcall else "PASS",
                    "0/0" if refcall else "0/1", dp - a, a, dp, int(rng.integers(3, 21))))
    return sorted(out, key=lambda r: (r[0], r[1]))


def write_vcf(path: Path, caller: str, sample: str, rows: list[tuple]):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(f"{c}\t{p}\t.\t{r}\t{a}\t{q}\t{f}\tDP={dp}\tGT:AD:DP:GQ\t{gt}:{ar},{aa}:{dp}:{gq}\n"
                   for c, p, r, a, q, f, gt, ar, aa, dp, gq in rows)
    with gzip.GzipFile(path, "wb", mtime=0) as fh:
        fh.write((_header(caller, sample) + body).encode())


def main():
    run = nfstub.run_dir()
    _, nfp = nfstub.load(run)
    rows = list(csv.DictReader(open(nfp["input"])))
    samples = list(dict.fromkeys(r["sample"] for r in rows))
    tools = [t for t in str(nfp.get("tools") or "").split(",") if t]
    callers = [t for t in tools if t in CALLERS]
    for t in tools:
        if t not in CALLERS:
            print(f"{t}: the demo cluster only stands in for the germline callers ({', '.join(CALLERS)}); skipped.", flush=True)
    truth = Path(rows[0]["fastq_1"]).parent.parent / ".demo_truth" / "variants.json"
    true = json.loads(truth.read_text())
    out = Path(nfp["outdir"])
    trace = nfstub.Trace(run)
    nfstub.run_tasks(trace, "NFCORE_SAREK:SAREK", ["FASTQC", "BWAMEM1_MEM", "GATK4_MARKDUPLICATES", "MOSDEPTH", "SAMTOOLS_STATS"],
                     per_task=lambda t: samples)
    rng = np.random.default_rng(73)
    for s in samples:
        d = out / "reports" / "mosdepth" / s
        d.mkdir(parents=True, exist_ok=True)
        mean = round(float(rng.uniform(26, 34)), 2)
        (d / f"{s}.md.mosdepth.summary.txt").write_text(
            "chrom\tlength\tbases\tmean\tmin\tmax\n" + "".join(f"{c}\t{n}\t{int(n * mean)}\t{mean}\t0\t{int(mean * 3)}\n" for c, n in CHROMS.items())
            + f"total\t{sum(CHROMS.values())}\t{int(sum(CHROMS.values()) * mean)}\t{mean}\t0\t{int(mean * 3)}\n")
    for caller in callers:
        folder, suffix = CALLERS[caller]
        for s in samples:
            write_vcf(out / "variant_calling" / folder / s / f"{s}.{suffix}", caller, s, calls(caller, s, true))
            trace.task(f"NFCORE_SAREK:SAREK:{TASKS[caller]} ({s})")
    nfstub.run_tasks(trace, "NFCORE_SAREK:SAREK", ["BCFTOOLS_STATS", "VCFTOOLS_TSTV_COUNT", "MULTIQC"])
    nfstub.placeholder_report(out / "multiqc" / "multiqc_report.html", "MultiQC report",
                              "On a real cluster this is nf-core/sarek's full quality report: read quality, mapping, duplicates, coverage and variant statistics.")
    (out / "pipeline_info").mkdir(exist_ok=True)
    print(f"Demo stand-in for nf-core/sarek: {len(samples)} samples, callers {', '.join(callers)}", flush=True)


if __name__ == "__main__":
    main()
