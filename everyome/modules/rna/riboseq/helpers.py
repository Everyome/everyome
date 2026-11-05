"""App-side helpers for Ribo-seq (run on this computer, reading the cluster through the backend).

  scan     fill the samples table from a folder of FASTQ files, guessing each library's type, pair and condition
  report   after nf-core/riboseq: the count table, footprints counted per library, read lengths, ORFs and the MultiQC report

Paths are where nf-core/riboseq 2.0.0 writes its results (relative to the results folder); the engine uses them too.
"""
from __future__ import annotations

import re
import shlex

COUNTS = "quantification/inframe_psite/gene_counts.tsv"
RIBOWALTZ = "psites/ribowaltz"
CATALOGUE_DIR = "orf_predictions/catalogue"
RIBOTISH = "orf_predictions/ribotish_all/allsamples_pred.txt"
ANOTA = "translational_efficiency/anota2seq"
MULTIQC = "multiqc/multiqc_report.html"

PAIR = re.compile(r"^(?P<sample>.+?)(?:_S\d+)?(?:_L\d{3})?[._](?:R)?(?P<read>[12])(?:_001)?\.f(ast)?q\.gz$")
# Intent: words people put in library names to say what a library is (checked in this order).
TYPES = (("tiseq", {"tis", "tiseq", "harr", "harringtonine", "ltm", "lactimidomycin"}),
         ("riboseq", {"ribo", "riboseq", "rpf", "fp", "footprint", "footprints"}),
         ("rnaseq", {"rna", "rnaseq", "total", "mrna", "input"}))
WORDS = set().union(*(w for _, w in TYPES))


def _tokens(sample: str) -> list[str]:
    return [t for t in re.split(r"[_.-]", sample) if t]


def type_of(sample: str) -> str:
    low = {t.lower() for t in _tokens(sample)}
    return next((t for t, words in TYPES if low & words), "rnaseq")


def strip_type(sample: str) -> str:
    """The biological sample a library came from: its name without the library-type word (control_1_ribo -> control_1)."""
    return "_".join(t for t in _tokens(sample) if t.lower() not in WORDS) or sample


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
        base = strip_type(s)
        cond = re.sub(r"[_.-]?(rep)?\d+$", "", base, flags=re.I) or base
        rows.append({"sample": s, "fastq_1": reads.get("1", ""), "fastq_2": reads.get("2", ""), "strandedness": "auto",
                     "type": type_of(s), "pair": base, "condition": cond})
    # Intent: a pair only means something when it links a Ribo-seq library to an RNA-seq one.
    kinds = {}
    for r in rows:
        kinds.setdefault(r["pair"], set()).add(r["type"])
    for r in rows:
        if not {"riboseq", "rnaseq"} <= kinds[r["pair"]]:
            r["pair"] = ""
    n = {t: sum(1 for r in rows if r["type"] == t) for t in ("riboseq", "rnaseq", "tiseq")}
    paired = len({r["pair"] for r in rows if r["pair"]})
    return {"rows": rows, "message": f"Found {n['riboseq']} Ribo-seq, {n['rnaseq']} RNA-seq and {n['tiseq']} TI-seq libraries; "
                                     f"{paired} Ribo-seq/RNA-seq pairs. Check type, pair and condition: they were guessed from the names."}


def report(backend, run: dict) -> dict:
    d = f"{run['dir']}/results"
    out = {"counts": None, "multiqc": MULTIQC if backend.exists(f"{d}/{MULTIQC}") else None, "libraries": [], "lengths": {}, "orfs": None}
    if out["multiqc"]:
        out["multiqc"] = f"results/{MULTIQC}"
    if backend.exists(f"{d}/{COUNTS}"):
        out["counts"] = f"results/{COUNTS}"
        # Intent: sum each library's column on the cluster, so only a few numbers come back.
        awk = ("NR==1{for(i=3;i<=NF;i++)h[i]=$i;next}{n++;for(i=3;i<=NF;i++)s[i]+=$i}"
               "END{print n;for(i=3;i in h;i++)print h[i]\"\\t\"s[i]}")
        rc, txt, _ = backend.run(f"awk -F'\\t' {shlex.quote(awk)} {shlex.quote(d + '/' + COUNTS)}", timeout=300)
        lines = txt.strip().splitlines()
        if lines:
            out["genes"] = int(lines[0])
            types = {r["sample"]: r.get("type", "") for r in run["values"].get("samples") or []}
            out["libraries"] = [{"sample": a, "counted": float(b), "type": types.get(a, "")} for a, b in (l.split("\t") for l in lines[1:])]
    if backend.exists(f"{d}/{RIBOWALTZ}"):
        # Intent: riboWaltz's offset table has each read length's share of footprints: the read-length distribution.
        for e in backend.listdir(f"{d}/{RIBOWALTZ}"):
            if e.name.endswith(".psite_offset.tsv"):
                rows = [l.split("\t") for l in backend.read_text(f"{d}/{RIBOWALTZ}/{e.name}").splitlines()]
                head = rows[0] if rows else []
                if "length" in head and "total_percentage" in head:
                    i, j = head.index("length"), head.index("total_percentage")
                    out["lengths"][e.name[:-len(".psite_offset.tsv")]] = {int(r[i]): float(r[j]) for r in rows[1:] if len(r) > j}
    if backend.exists(f"{d}/{CATALOGUE_DIR}"):
        cat = sorted(e.name for e in backend.listdir(f"{d}/{CATALOGUE_DIR}") if e.name.endswith(".catalogue.tsv"))
        if cat:
            rc, txt, _ = backend.run(f"tail -n +2 {shlex.quote(d + '/' + CATALOGUE_DIR + '/' + cat[0])} | wc -l", timeout=120)
            out["orfs"] = int(txt.strip() or 0)
    return out


def contrasts(values: dict) -> str:
    """The contrasts file nf-core/riboseq needs to test translational efficiency with anota2seq, made from the samples
    table: each other condition against the first one listed, with Ribo-seq and RNA-seq libraries linked by pair.
    Empty (no file) when there are fewer than two conditions or no pairs; a contrasts file the user gives wins."""
    rows = values.get("samples") or []
    conds = list(dict.fromkeys(r.get("condition") for r in rows if r.get("condition")))
    if len(conds) < 2 or not any(str(r.get("pair") or "").strip() for r in rows):
        return ""
    ref = conds[0]
    return "id,variable,reference,target,batch,pair\n" + "".join(f"{t}_vs_{ref},condition,{ref},{t},,pair\n" for t in conds[1:])
