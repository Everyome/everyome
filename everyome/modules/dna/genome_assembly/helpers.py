"""App-side helpers for genome assembly (run on this computer, reading the cluster through the backend).

  scan    suggest assemblies from a folder of reads: one per read type, plus hybrid and scaffolded ones when both
          long-read types are there; Illumina reads are added to every row for polishing and checking
  report  after nf-core/genomeassembler: the assemblies it wrote and its HTML report
"""
from __future__ import annotations

import re
import shlex

READS = re.compile(r"\.(fastq|fq)(\.gz)?$", re.I)
ONT = re.compile(r"(^|[_.-])(ont|nanopore|promethion|minion|gridion|nano)([_.-]|$)", re.I)
HIFI = re.compile(r"(^|[_.-])(hifi|ccs|pacbio|revio|sequel|pb)([_.-]|$)", re.I)
PAIR = re.compile(r"^(?P<base>.+?)(?:_S\d+)?(?:_L\d{3})?[._]R?(?P<read>[12])(?:_001)?\.f(ast)?q(\.gz)?$", re.I)


def scan(backend, path: str = "") -> dict:
    if not path:
        raise ValueError("Choose the reads folder first.")
    files = sorted(e.name for e in backend.listdir(path) if not e.is_dir and READS.search(e.name))
    full = lambda n: f"{path.rstrip('/')}/{n}"
    ont = [f for f in files if ONT.search(f)]
    hifi = [f for f in files if HIFI.search(f) and f not in ont]
    pairs = {}
    for f in files:
        m = PAIR.match(f)
        if m and f not in ont + hifi:
            pairs.setdefault(m.group("base"), {})[m.group("read")] = full(f)
    short = next(iter(pairs.values()), {})
    if not ont and not hifi:
        raise ValueError("No long reads found. Name Nanopore files with 'ont' or 'nanopore', and PacBio HiFi files with 'hifi' or 'ccs' "
                         "(for example sample_ont.fastq.gz). Illumina reads alone cannot be assembled here; for bacteria, use "
                         "Bacterial genome assembly and annotation.")
    base = re.split(r"[_.-](ont|nanopore|hifi|ccs|pacbio)", (ont + hifi)[0], flags=re.I)[0] or "genome"
    s1, s2 = short.get("1", ""), short.get("2", "")
    pol = lambda long_only_ont: ("medaka+pilon" if s1 else "medaka") if long_only_ont else ("pilon" if s1 else "")
    row = lambda name, o, h, strategy, assembler, polish: {"sample": f"{base}_{name}", "ontreads": full(o) if o else "", "hifireads": full(h) if h else "",
                                                          "short_1": s1, "short_2": s2, "strategy": strategy, "assembler": assembler, "polish": polish}
    rows = []
    if ont:
        rows.append(row("ont", ont[0], "", "single", "flye", pol(True)))
    if hifi:
        rows.append(row("hifi", "", hifi[0], "single", "hifiasm", pol(False)))
    if ont and hifi:
        rows.append(row("hybrid", ont[0], hifi[0], "hybrid", "hifiasm", pol(False)))
        rows.append(row("scaffold", ont[0], hifi[0], "scaffold", "flye_hifiasm", pol(False)))
    msg = (f"Suggested {len(rows)} assemblies to compare: " + ", ".join(r["sample"] for r in rows) + "."
           + (" Illumina reads were added to each, to polish and check them." if s1 else " No Illumina reads found; adding them improves accuracy.")
           + (" Only the first file of each kind was used; join lanes into one file per read type first." if len(ont) > 1 or len(hifi) > 1 or len(pairs) > 1 else ""))
    return {"rows": rows, "message": msg}


def report(backend, run: dict) -> dict:
    d = f"{run['dir']}/results"
    rc, out, _ = backend.run(f"cd {shlex.quote(d)} 2>/dev/null && find . -type f \\( -name '*.fa' -o -name '*.fa.gz' -o -name '*.fasta' -o -name '*.fasta.gz' \\) "
                             "| grep -Ev '/(QC|reads|prepare|reference|report)/' | sort | head -200", timeout=120)
    found = [l[2:] for l in out.splitlines() if l.startswith("./")] if rc == 0 else []
    html = "results/report/report.html" if backend.exists(f"{d}/report/report.html") else None
    return {"assemblies": found, "report": html}
