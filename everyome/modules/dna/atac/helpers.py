"""App-side helpers for ATAC-seq (run on this computer, reading the cluster through the backend), and the output paths
nf-core/atacseq 2.1.2 writes, shared with the engine.

  scan     fill the libraries table from a folder of FASTQ files
  check    refuse settings with which the pipeline would skip peak calling
  report   after nf-core/atacseq: peaks and FRiP per library, the consensus peaks, the MultiQC report
"""
from __future__ import annotations

import re
import shlex

PAIR = re.compile(r"^(?P<lib>.+?)(?:_S\d+)?(?:_L\d{3})?[._](?:R)?(?P<read>[12])(?:_001)?\.f(ast)?q\.gz$")
REP = re.compile(r"^(?P<group>.+?)[_.-]?(?:replicate|rep)?[_.-]?(?P<rep>\d+)$", re.I)


def peak_kind(values: dict) -> str:
    return "narrow_peak" if values.get("narrow_peak") else "broad_peak"


def peak_dir(values: dict) -> str:
    """Folder of per-library peaks (relative to the run folder); qc/ and consensus/ are inside it."""
    return f"results/{values.get('aligner') or 'bwa'}/merged_library/macs2/{peak_kind(values)}"


def consensus_counts(values: dict) -> str:
    return f"{peak_dir(values)}/consensus/consensus_peaks.mLb.clN.featureCounts.txt"


def peak_file(values: dict, lib: str) -> str:
    return f"{peak_dir(values)}/{lib}.mLb.clN_peaks.{'narrowPeak' if values.get('narrow_peak') else 'broadPeak'}"


def bigwig(values: dict, lib: str) -> str:
    return f"results/{values.get('aligner') or 'bwa'}/merged_library/bigwig/{lib}.mLb.clN.bigWig"


def multiqc(values: dict) -> str:
    return f"results/multiqc/{peak_kind(values)}/multiqc_report.html"


def libraries(values: dict) -> list[dict]:
    """One entry per library, as the pipeline names them (<group>_REP<n>); repeated rows are one library."""
    out = {}
    for r in values.get("libraries") or []:
        lib = f"{r['group']}_REP{int(r['replicate'])}"
        out.setdefault(lib, {"library": lib, "group": r["group"], "replicate": int(r["replicate"])})
    return list(out.values())


def read_mqc(text: str) -> dict[str, float]:
    """A MultiQC custom-content table (# header lines, then id<TAB>value) as {id: value}."""
    out = {}
    for line in text.splitlines():
        f = line.strip().split("\t")
        if line.startswith("#") or len(f) < 2:
            continue
        try:
            out[f[0]] = float(f[1])
        except ValueError:
            continue
    return out


def scan(backend, path: str = "") -> dict:
    if not path:
        raise ValueError("Choose the reads folder first.")
    files = sorted(e.name for e in backend.listdir(path) if not e.is_dir)
    found = {}
    for n in files:
        m = PAIR.match(n)
        if m:
            found.setdefault(m.group("lib"), {})[m.group("read")] = f"{path.rstrip('/')}/{n}"
    if not found:
        raise ValueError("No FASTQ files named like <group>_rep1_R1.fastq.gz (and _R2) were found in that folder.")
    rows, seen = [], {}
    for lib, reads in found.items():
        # Intent: guess group and replicate from the name (polyp_rep2 -> polyp, 2); people check them.
        m = REP.match(lib)
        group = m.group("group").rstrip("_.-") if m else lib
        rep = int(m.group("rep")) if m else 0
        seen[group] = seen.get(group, 0) + 1
        rows.append({"group": group, "replicate": str(rep or seen[group]), "fastq_1": reads.get("1", ""), "fastq_2": reads.get("2", "")})
    paired = sum(1 for r in rows if r["fastq_2"])
    groups = sorted({r["group"] for r in rows})
    return {"rows": rows, "message": f"Found {len(rows)} libraries ({paired} paired-end) in {len(groups)} groups ({', '.join(groups)}). "
                                     "Check each group and replicate: they were guessed from the names and are what the comparison uses."}


def check(values: dict, demo: bool = False) -> list[str]:
    problems = []
    if not values.get("genome"):
        if not values.get("fasta") or not (values.get("gtf") or values.get("gff")):
            problems.append("Set the genome FASTA and its GTF (or choose an iGenomes genome).")
        # Intent: without a genome size MACS2 is skipped for non-iGenomes references, and there would be no peaks to explore.
        if not values.get("macs_gsize") and not values.get("read_length"):
            problems.append("Set the effective genome size (macs_gsize), for example about the genome's length without "
                            "long runs of N, or set the read length so the pipeline can work it out.")
    if len({r["group"] for r in values.get("libraries") or []}) < 1:
        problems.append("Add at least one library.")
    return problems


def report(backend, run: dict) -> dict:
    d, v = run["dir"], run["values"]
    libs = libraries(v)
    out = {"kind": peak_kind(v), "libraries": [], "consensus": None, "consensus_peaks": 0, "multiqc": None}
    qc = {}
    pd = f"{d}/{peak_dir(v)}/qc"
    if backend.exists(pd):
        for e in backend.listdir(pd):
            if e.name.endswith(".FRiP_mqc.tsv") or e.name.endswith(".count_mqc.tsv"):
                key = "frip" if "FRiP" in e.name else "peaks"
                for lib, val in read_mqc(backend.read_text(f"{pd}/{e.name}")).items():
                    qc.setdefault(lib.replace(".mLb.clN_peaks", "").replace(".mLb.clN", ""), {})[key] = val
    for l in libs:
        q = qc.get(l["library"], {})
        out["libraries"].append({**l, "peaks": int(q["peaks"]) if "peaks" in q else None, "frip": q.get("frip")})
    if backend.exists(f"{d}/{consensus_counts(v)}"):
        out["consensus"] = consensus_counts(v)
        rc, txt, _ = backend.run(f"grep -vc '^#' {shlex.quote(d + '/' + consensus_counts(v))}", timeout=120)
        out["consensus_peaks"] = max(0, int(txt.strip() or 1) - 1)
    if backend.exists(f"{d}/{multiqc(v)}"):
        out["multiqc"] = multiqc(v)
    return out
