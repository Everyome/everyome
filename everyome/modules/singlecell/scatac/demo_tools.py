"""Stand-in for chromap on the demo cluster: copies the fragments made with the demo data into the run.

The demo reads are placeholders; their fragments were simulated when the demo data were built (.demo_truth next to
the reads folder), with known cell types, so the session has real structure to find.
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path


def fragments(samples: list[dict], out: Path) -> None:
    pause = float(os.environ.get("EVERYOME_DEMO_PAUSE", "1"))
    for s in samples:
        truth = Path(s["read1"]).parent.parent / ".demo_truth" / f"{s['sample']}.fragments.tsv.gz"
        if not truth.exists():
            raise FileNotFoundError(f"No demo fragments for {s['sample']}; the demo has samples polyp_A and polyp_B.")
        time.sleep(pause / max(1, len(samples)))
        shutil.copy(truth, out / f"{s['sample']}.tsv.gz")
        print(f"[demo] {s['sample']}: fragments written (chromap stand-in)", flush=True)
