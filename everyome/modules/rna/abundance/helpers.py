"""App-side helpers for RNA abundance (run on this computer, reading the cluster through the backend).

  tables  where nf-core/rnaseq writes its merged gene tables, by route (shared with the engine)
  scan    fill the samples table from the TPM table's header, with a group guessed from each name
"""
from __future__ import annotations

import re
import shlex

ROUTES = ("star_salmon", "star_rsem", "salmon", "kallisto", "hisat2")


def tables(results: str) -> list[tuple[str, str]]:
    """(TPM table, count table) candidates under an nf-core/rnaseq results folder, most likely first."""
    r = results.rstrip("/")
    out = []
    for route in ROUTES:
        tool = "rsem" if route == "star_rsem" else ("kallisto" if route == "kallisto" else "salmon")
        out.append((f"{r}/{route}/{tool}.merged.gene_tpm.tsv", f"{r}/{route}/{tool}.merged.gene_counts.tsv"))
    return out


def group_of(sample: str) -> str:
    # Intent: suggest a group from the name before its last _number (oral_2 -> oral); people check it.
    return re.sub(r"[_.-]?(rep)?\d+$", "", sample, flags=re.I) or sample


def scan(backend, path: str = "") -> dict:
    if not path:
        raise ValueError("Choose the nf-core/rnaseq results folder first.")
    for tpm, _ in tables(path):
        if backend.exists(tpm):
            rc, head, _ = backend.run(f"head -n 1 {shlex.quote(tpm)}", timeout=60)
            cols = head.rstrip("\n").split("\t")
            samples = [c for c in cols if c not in ("gene_id", "gene_name", "gene_symbol", "tx", "transcript_id")]
            rows = [{"sample": s, "group": group_of(s)} for s in samples]
            return {"rows": rows, "message": f"Found {len(rows)} samples in {tpm.split('/')[-2]}/{tpm.split('/')[-1]}. "
                                             "Check each sample's group: it was guessed from the name and colours the charts."}
    raise ValueError("No gene TPM table from nf-core/rnaseq was found there. Choose the pipeline's results folder "
                     "(it has a folder such as star_salmon or salmon inside).")
