"""App-side helpers for bacterial assembly (run on this computer, reading the cluster through the backend).

  scan    one row per isolate from a folder of reads: Illumina pairs and long reads, matched by isolate name
  report  after nf-core/bacass: the assemblies and annotations it wrote, and its MultiQC report
"""
from __future__ import annotations

import re
import shlex

READS = re.compile(r"\.(fastq|fq)(\.gz)?$", re.I)
LONG = re.compile(r"[_.-](ont|nanopore|pacbio|hifi|ccs|long|minion|gridion|promethion)([_.-]|\.f)", re.I)
PAIR = re.compile(r"^(?P<base>.+?)(?:_S\d+)?(?:_L\d{3})?[._]R?(?P<read>[12])(?:_001)?\.f(ast)?q(\.gz)?$", re.I)


def scan(backend, path: str = "") -> dict:
    if not path:
        raise ValueError("Choose the reads folder first.")
    files = sorted(e.name for e in backend.listdir(path) if not e.is_dir and READS.search(e.name))
    full = lambda n: f"{path.rstrip('/')}/{n}"
    found = {}
    for f in files:
        m = LONG.search(f)
        if m:
            found.setdefault(f[:m.start()], {})["long"] = full(f)
            continue
        m = PAIR.match(f)
        if m:
            found.setdefault(m.group("base"), {})["short_" + m.group("read")] = full(f)
    if not found:
        raise ValueError("No reads found. Illumina files should end in _R1/_R2.fastq.gz; name long reads with ont, nanopore, pacbio or long "
                         "(for example isolate1_ont.fastq.gz).")
    rows = [{"sample": s, "short_1": r.get("short_1", ""), "short_2": r.get("short_2", ""), "long": r.get("long", ""), "genome_size": ""}
            for s, r in sorted(found.items())]
    kinds = {("hybrid" if r["short_1"] and r["long"] else "short" if r["short_1"] else "long") for r in rows}
    advice = (f"Set Assembly type to {kinds.pop()}." if len(kinds) == 1 else
              "Isolates have different kinds of reads; one run uses one Assembly type, so split them into runs (or leave out reads).")
    return {"rows": rows, "message": f"Found {len(rows)} isolates. {advice} Add each genome size (for example 4.6m) if you know it."}


def report(backend, run: dict) -> dict:
    d = f"{run['dir']}/results"
    rc, out, _ = backend.run(f"cd {shlex.quote(d)} 2>/dev/null && find . -type f \\( -name '*.fa' -o -name '*.fa.gz' -o -name '*.fasta' -o -name '*.fasta.gz' "
                             "-o -name '*.gff' -o -name '*.gff3' \\) | grep -Ev '/(trimming|QC_|Kraken|kmerfinder|reference)' | sort | head -200", timeout=120)
    found = [l[2:] for l in out.splitlines() if l.startswith("./")] if rc == 0 else []
    mqc = "results/multiqc/multiqc_report.html" if backend.exists(f"{d}/multiqc/multiqc_report.html") else None
    return {"assemblies": [f for f in found if not f.endswith((".gff", ".gff3"))], "annotations": [f for f in found if f.endswith((".gff", ".gff3"))], "multiqc": mqc}
