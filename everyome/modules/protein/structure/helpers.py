"""App-side helpers for structure prediction: find protein FASTA files, check settings before a run, summarise the results."""
from __future__ import annotations

import re
import shlex

FASTA = re.compile(r"\.(fa|fasta|faa)$", re.I)
# Methods that need large databases (hundreds of GB to TB). Without a reference data folder the pipeline would
# download them into the run, so a run is refused instead.
NEEDS_DB = {"alphafold2": "about 2.6 TB", "alphafold3": "about 630 GB", "colabfold": "about 1 TB (without the MSA server)",
            "rosettafold_all_atom": "about 2 TB", "helixfold3": "about 1.5 TB", "rosettafold2na": "about 800 GB"}


def scan(backend, path: str = "") -> dict:
    if not path:
        raise ValueError("Choose the folder first.")
    q = shlex.quote(path.rstrip("/"))
    rc, out, _ = backend.run(f"find {q} -maxdepth 2 -type f \\( -name '*.fa' -o -name '*.fasta' -o -name '*.faa' \\) 2>/dev/null | sort | head -500", timeout=120)
    files = [l for l in out.splitlines() if FASTA.search(l)]
    if not files:
        raise ValueError("No FASTA files (.fa, .fasta, .faa) found in that folder.")
    rows, multi = [], []
    for f in files:
        pid = re.sub(r"[^A-Za-z0-9_.-]+", "_", FASTA.sub("", f.rsplit("/", 1)[-1]))
        n = backend.read_text(f).count(">")
        if n > 1:
            multi.append(pid)
        rows.append({"id": pid, "fasta": f})
    msg = f"Found {len(rows)} FASTA files, one prediction each."
    if multi:
        msg += (f" {', '.join(multi)} hold{'s' if len(multi) == 1 else ''} several sequences: they are predicted together as a complex "
                "(choose a multimer model), or turn on Split FASTA to predict each sequence on its own.")
    return {"rows": rows, "message": msg}


def check(values: dict, demo: bool = False) -> list[str]:
    """Problems with the settings that would waste a large download or a GPU allocation; empty if none."""
    if demo:
        return []
    modes = [m for m in str(values.get("mode") or "alphafold2").split(",") if m]
    if values.get("use_msa_server") and "colabfold" in modes:
        modes.remove("colabfold")                      # the MSA server replaces ColabFold's local databases
    big = [m for m in modes if m in NEEDS_DB]
    if big and not str(values.get("db") or "").strip():
        return [f"{', '.join(big)} need{'s' if len(big) == 1 else ''} reference databases ({'; '.join(f'{m}: {NEEDS_DB[m]}' for m in big)}). "
                "Set Reference data folder to the folder your cluster keeps them in (ask IT), or choose esmfold, which needs only its model weights."]
    return []


def report(backend, run: dict) -> dict:
    d = f"{run['dir']}/results"
    rc, out, _ = backend.run(f"cd {shlex.quote(d)} 2>/dev/null && find . -path '*top_ranked_structures/*.pdb' -not -path './final/*' | sort | head -500", timeout=120)
    found = [l[2:] for l in out.splitlines() if l.startswith("./")] if rc == 0 else []
    rc, out, _ = backend.run(f"cd {shlex.quote(d)} 2>/dev/null && ls reports/*.html 2>/dev/null | head -100", timeout=60)
    return {"structures": found, "reports": [f"results/{l}" for l in out.split() if l.endswith(".html")]}
