"""App-side helpers for bulk RNA-seq (run on this computer, reading the cluster through the backend).

  scan       fill the samplesheet from a folder of FASTQ files
  report     after nf-core/rnaseq: which count table was made, samples and library sizes, the MultiQC report
  counts_paths  where nf-core/rnaseq writes the merged gene counts, by aligner (shared with the engine)
"""
from __future__ import annotations

import re
import shlex

PAIR = re.compile(r"^(?P<sample>.+?)(?:_S\d+)?(?:_L\d{3})?[._](?:R)?(?P<read>[12])(?:_001)?\.f(ast)?q\.gz$")


def counts_paths(values: dict) -> list[str]:
    """Candidate count tables (relative to the run folder), most likely first."""
    aligner = values.get("aligner") or "star_salmon"
    out = []
    if not values.get("skip_alignment"):
        out.append(f"results/{aligner}/rsem.merged.gene_counts.tsv" if aligner == "star_rsem" else f"results/{aligner}/salmon.merged.gene_counts.tsv")
    for pseudo in ([values.get("pseudo_aligner")] if values.get("pseudo_aligner") else []) + ["salmon", "kallisto"]:
        out.append(f"results/{pseudo}/{pseudo}.merged.gene_counts.tsv")
    return list(dict.fromkeys(out))


def scan(backend, path: str = "") -> dict:
    if not path:
        raise ValueError("Choose the reads folder first.")
    files = sorted(e.name for e in backend.listdir(path) if not e.is_dir)
    found = {}
    for n in files:
        m = PAIR.match(n)
        if m:
            found.setdefault(m.group("sample"), {})[m.group("read")] = f"{path.rstrip('/')}/{n}"
    if not found:
        raise ValueError("No FASTQ files named like <sample>_R1.fastq.gz (and _R2) were found in that folder.")
    rows = []
    for s, reads in found.items():
        # Intent: suggest a condition from the name before its last _number (control_1 -> control); people check it.
        cond = re.sub(r"[_.-]?(rep)?\d+$", "", s, flags=re.I) or s
        rows.append({"sample": s, "fastq_1": reads.get("1", ""), "fastq_2": reads.get("2", ""), "strandedness": "auto", "condition": cond})
    paired = sum(1 for r in rows if r["fastq_2"])
    return {"rows": rows, "message": f"Found {len(rows)} samples ({paired} paired-end). Check each sample's condition: "
                                     "it was guessed from the name and is what the comparison uses."}


def report(backend, run: dict) -> dict:
    d = run["dir"]
    counts = None
    for rel in counts_paths(run["values"]):
        if backend.exists(f"{d}/{rel}"):
            counts = rel
            break
    out = {"counts": counts, "multiqc": None, "samples": []}
    for rel in ("results/multiqc/" + (run["values"].get("aligner") or "star_salmon") + "/multiqc_report.html", "results/multiqc/multiqc_report.html"):
        if backend.exists(f"{d}/{rel}"):
            out["multiqc"] = rel
            break
    if counts:
        # Intent: sum each sample's column on the cluster, so only a few numbers come back.
        awk = ("NR==1{for(i=3;i<=NF;i++)h[i]=$i;next}{n++;for(i=3;i<=NF;i++){s[i]+=$i;if($i>0)g[i]++}}"
               "END{print n;for(i=3;i in h;i++)print h[i]\"\\t\"s[i]\"\\t\"g[i]}")
        rc, txt, _ = backend.run(f"awk -F'\\t' {shlex.quote(awk)} {shlex.quote(d + '/' + counts)}", timeout=300)
        lines = txt.strip().splitlines()
        if lines:
            out["genes"] = int(lines[0])
            out["samples"] = [{"sample": a, "reads": float(b), "genes": int(c or 0)} for a, b, c in (l.split("\t") for l in lines[1:])]
    return out
