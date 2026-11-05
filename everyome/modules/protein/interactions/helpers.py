"""App-side helpers for interaction prediction: find complex FASTA files (two or more chains each), check settings, report.

  scan    FASTA files in a folder; each with several sequences is one complex; single sequences are flagged
  check   the structure module's check (databases for the methods asked for)
  report  the structure module's report (structures and the pipeline's own reports)
"""
from __future__ import annotations

from ..structure.helpers import check, report  # noqa: F401  (re-exported for the manifest)
from ..structure.helpers import scan as _scan


def scan(backend, path: str = "") -> dict:
    r = _scan(backend, path)
    single = [row["id"] for row in r["rows"] if backend.read_text(row["fasta"]).count(">") < 2]
    rows = [row for row in r["rows"] if row["id"] not in single]
    if not rows:
        raise ValueError("Every FASTA file there holds a single sequence. For an interaction, put the chains of each complex "
                         "together in one FASTA file (one > line per chain); for single proteins, use Structure prediction.")
    msg = f"Found {len(rows)} complexes, one prediction each."
    if single:
        msg += f" Left out {', '.join(single)}: one sequence each (use Structure prediction for those)."
    return {"rows": rows, "message": msg}
