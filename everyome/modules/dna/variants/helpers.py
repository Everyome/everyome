"""App-side helpers for variant calling (run on this computer, reading the cluster through the backend).

  scan       fill the samples table from a folder of FASTQ files
  report     after nf-core/sarek: which variant files each caller wrote, mean coverage per sample, the MultiQC report
  vcf_files  where sarek writes each caller's per-sample VCF (shared with the engine)
"""
from __future__ import annotations

import re
import shlex
from pathlib import Path

PAIR = re.compile(r"^(?P<sample>.+?)(?:_S\d+)?(?:_(?P<lane>L\d{3}))?[._](?:R)?(?P<read>[12])(?:_001)?\.f(ast)?q\.gz$")

# Intent: per-sample germline calls; gVCFs and genome VCFs (every position) are left out, and a filtered file wins
# over the unfiltered one from the same caller.
SKIP = (".g.vcf.gz", ".genome.vcf.gz", ".tbi")


def pick_vcfs(names: list[str]) -> dict[tuple[str, str], str]:
    """{(caller, sample): path} from paths ending in variant_calling/<caller>/<sample>/<file>.vcf.gz."""
    out = {}
    for n in sorted(names):
        parts = n.split("/")
        if len(parts) < 4 or n.endswith(SKIP) or parts[-2] == "joint_variant_calling":
            continue
        key = (parts[-3], parts[-2])
        prev = out.get(key)
        if prev is None or (".filtered." in n and ".filtered." not in prev) or (".norm." in prev and ".norm." not in n):
            out[key] = n
    return out


def vcf_files(results: Path) -> dict[tuple[str, str], Path]:
    """{(caller, sample): VCF} in a run's results folder."""
    return {k: Path(v) for k, v in pick_vcfs([str(f) for f in results.glob("variant_calling/*/*/*.vcf.gz")]).items()}


def scan(backend, path: str = "") -> dict:
    if not path:
        raise ValueError("Choose the reads folder first.")
    files = sorted(e.name for e in backend.listdir(path) if not e.is_dir)
    found = {}
    for n in files:
        m = PAIR.match(n)
        if m:
            found.setdefault((m.group("sample"), m.group("lane") or "L001"), {})[m.group("read")] = f"{path.rstrip('/')}/{n}"
    if not found:
        raise ValueError("No FASTQ files named like <sample>_R1.fastq.gz (and _R2) were found in that folder.")
    rows = []
    for (s, lane), reads in found.items():
        # Intent: suggest a group from the name before its last _number (mut_1 -> mut); people check it.
        group = re.sub(r"[_.-]?(rep)?\d+$", "", s, flags=re.I) or s
        rows.append({"patient": s, "sample": s, "lane": lane, "fastq_1": reads.get("1", ""), "fastq_2": reads.get("2", ""), "group": group})
    samples = len({r["sample"] for r in rows})
    return {"rows": rows, "message": f"Found {samples} samples ({len(rows)} lanes). Check each sample's group: it was guessed "
                                     "from the name and is only used in the live session."}


def report(backend, run: dict) -> dict:
    d = run["dir"]
    out = {"vcfs": [], "coverage": [], "multiqc": None}
    rc, txt, _ = backend.run(f"cd {shlex.quote(d)} && ls -1 results/variant_calling/*/*/*.vcf.gz 2>/dev/null", timeout=120)
    found = pick_vcfs(txt.split())
    out["vcfs"] = [{"caller": c, "sample": s, "path": p} for (c, s), p in sorted(found.items())]
    # Intent: mosdepth's summary has one 'total' line per sample: read only those few numbers back.
    rc, txt, _ = backend.run(f"cd {shlex.quote(d)} && grep -H '^total' results/reports/mosdepth/*/*.mosdepth.summary.txt 2>/dev/null", timeout=120)
    for line in txt.splitlines():
        f, rest = line.split(":", 1)
        cols = rest.split("\t")
        if len(cols) >= 4:
            out["coverage"].append({"sample": f.split("/")[-2], "mean": float(cols[3])})
    if backend.exists(f"{d}/results/multiqc/multiqc_report.html"):
        out["multiqc"] = "results/multiqc/multiqc_report.html"
    return out
