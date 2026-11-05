"""App-side helpers for Hi-C (run on this computer, reading the cluster through the backend).

  scan     fill the samples table from a folder of FASTQ files
  check    refuse settings that would make nf-core/hic stop straight away (no enzyme, no genome)
  report   after nf-core/hic: each sample's read pairs and valid pairs (HiC-Pro's statistics), the maps made, MultiQC
  read_stats  HiC-Pro's statistics files as numbers (shared with the session engine)

nf-core/hic 2.1.0 writes (under the run's results/):
  hicpro/stats/<sample>/   <sample>.mpairstat, <sample>.mRSstat, <sample>_allValidPairs.mergestat
  contact_maps/cool/       <sample>.<res>_balanced.cool for each resolution, and <sample>.mcool (for HiGlass)
  compartments/            <sample>.<res>_compartments.cis.vecs.tsv (cooltools eigs-cis)
  tads/insulation/, tads/hicExplorer/   insulation scores and TADs
  multiqc/multiqc_report.html
"""
from __future__ import annotations

import re
import shlex

PAIR = re.compile(r"^(?P<sample>.+?)(?:_S\d+)?(?:_L\d{3})?[._](?:R)?(?P<read>[12])(?:_001)?\.f(ast)?q\.gz$")


def scan(backend, path: str = "") -> dict:
    if not path:
        raise ValueError("Choose the reads folder first.")
    found = {}
    for e in backend.listdir(path):
        m = PAIR.match(e.name) if not e.is_dir else None
        if m:
            found.setdefault(m.group("sample"), {})[m.group("read")] = f"{path.rstrip('/')}/{e.name}"
    rows = [{"sample": s, "fastq_1": r.get("1", ""), "fastq_2": r.get("2", "")} for s, r in sorted(found.items())]
    if not rows:
        raise ValueError("No FASTQ files named like <sample>_R1.fastq.gz and _R2.fastq.gz were found in that folder.")
    single = [r["sample"] for r in rows if not r["fastq_2"]]
    return {"rows": rows, "message": f"Found {len(rows)} samples." + (
        f" Hi-C needs both reads of each pair; these have only read 1: {', '.join(single)}." if single else "")}


def check(vals: dict, demo: bool) -> list[str]:
    out = []
    if not (vals.get("digestion") or vals.get("restriction_site") or vals.get("dnase")):
        out.append("Choose the restriction enzyme the library was made with (Digestion), or give its restriction and "
                   "ligation sites, or turn on DNase mode for protocols without an enzyme.")
    if not vals.get("fasta"):
        out.append("Give the genome as a FASTA file.")
    if any(not r.get("fastq_2") for r in vals.get("samples") or []):
        out.append("Every sample needs both reads of each pair (read 1 and read 2).")
    return out


def read_stats(texts: dict[str, str]) -> dict:
    """Numbers from HiC-Pro's statistics files, given their text by kind (pairstat, RSstat, mergestat)."""
    nums = {}
    for kind, txt in texts.items():
        for line in (txt or "").splitlines():
            f = line.split("\t")
            if len(f) >= 2 and not line.startswith("#") and f[1].strip().lstrip("-").isdigit():
                nums[f"{kind}:{f[0]}"] = int(f[1])
    g = lambda k: nums.get(k)
    total = g("pairstat:Total_pairs_processed")
    valid = g("mergestat:valid_interaction")
    rmdup = g("mergestat:valid_interaction_rmdup")
    cis, trans = g("mergestat:cis_interaction"), g("mergestat:trans_interaction")
    pct = lambda a, b: round(100 * a / b, 1) if a is not None and b else None
    return {"pairs": total, "reported": g("pairstat:Reported_pairs"), "valid": valid, "unique": rmdup,
            "aligned_pct": pct(g("pairstat:Reported_pairs"), total), "valid_pct": pct(valid, total),
            "duplicates_pct": pct((valid or 0) - (rmdup or 0), valid) if rmdup is not None else None,
            "cis_pct": pct(cis, (cis or 0) + (trans or 0)), "long_pct": pct(g("mergestat:cis_longRange"), cis),
            "dangling_pct": pct(g("RSstat:Dangling_end_pairs"), g("RSstat:Valid_interaction_pairs")),
            "cis": cis, "trans": trans, "short": g("mergestat:cis_shortRange"), "long": g("mergestat:cis_longRange")}


def report(backend, run: dict) -> dict:
    d = run["dir"] + "/results"
    samples = list(dict.fromkeys(r["sample"] for r in run["values"].get("samples") or []))
    out = {"samples": [], "maps": [], "multiqc": "results/multiqc/multiqc_report.html" if backend.exists(f"{d}/multiqc/multiqc_report.html") else None}
    for s in samples:
        texts = {}
        for kind in ("pairstat", "RSstat", "mergestat"):
            rc, txt, _ = backend.run(f"cat {shlex.quote(d)}/hicpro/stats/{shlex.quote(s)}/*{kind} 2>/dev/null", timeout=60)
            texts[kind] = txt
        out["samples"].append({"sample": s, **read_stats(texts)})
    if backend.exists(f"{d}/contact_maps/cool"):
        out["maps"] = sorted(e.name for e in backend.listdir(f"{d}/contact_maps/cool") if e.name.endswith((".cool", ".mcool")))
    for k, sub in (("compartments", "compartments"), ("tads", "tads/hicExplorer")):
        out[k] = backend.exists(f"{d}/{sub}")
    return out
