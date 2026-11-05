"""Run the cluster stage of protein function annotation for an Everyome run: InterProScan on every protein.

Called by the job as `python -m everyome.modules.protein.function.stage annotate` inside the run folder. The protein
FASTA is cleaned first (stop codons and spaces removed; InterProScan refuses them), then InterProScan (in the image
pinned in module.yaml, by digest) searches every member database it has data for, with the run's data folder bound
where the image expects it. The lookup of precalculated matches at EBI is off unless the run turns it on: it sends
each sequence's checksum to EBI. On the demo cluster, a stand-in writes the same files for the demo proteins.

results/
  proteins.fasta        the cleaned input (names shortened to their first word)
  interproscan.tsv      one line per match: protein, database, signature, positions, score, InterPro entry, GO terms
  interproscan.json     the same, in InterProScan's JSON (for other tools)
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

from everyome.core import containers
from everyome.core.manifest import load

HERE = Path(__file__).resolve().parent
IMAGE_DATA = "/opt/interproscan/data"


def clean(src: Path, dst: Path) -> int:
    """Write a FASTA InterProScan accepts; returns the number of proteins."""
    out, n, name, seq = [], 0, None, []
    def flush():
        nonlocal n
        if name:
            s = re.sub(r"[^A-Za-z]", "", "".join(seq)).upper()
            if s:
                out.append(f">{name}\n" + "\n".join(s[i:i + 60] for i in range(0, len(s), 60)))
                n += 1
    for line in src.read_text().splitlines():
        if line.startswith(">"):
            flush()
            name, seq = re.sub(r"[^A-Za-z0-9_.|-]", "_", line[1:].split()[0]) if line[1:].strip() else f"protein{n + 1}", []
        else:
            seq.append(line.strip())
    flush()
    if not n:
        raise ValueError(f"{src} has no protein sequences.")
    dst.write_text("\n".join(out) + "\n")
    return n


def interproscan_args(params: dict, fasta: Path, res: Path, cpus: int) -> list[str]:
    args = ["/opt/interproscan/interproscan.sh", "-i", str(fasta), "-f", "TSV,JSON", "-b", str(res / "interproscan"),
            "-cpu", str(cpus), "-T", str(res / "interproscan_tmp")]
    if params.get("goterms", True):
        args.append("-goterms")
    if params.get("pathways", True):
        args.append("-pa")
    if params.get("applications"):
        args += ["-appl", ",".join(a.strip() for a in re.split(r"[\s,]+", params["applications"]) if a.strip())]
    if not params.get("lookup"):
        args.append("-dp")                                 # no precalculated lookup: nothing about the proteins leaves the cluster
    return args + shlex.split(params.get("interproscan_extra") or "")


def annotate(params: dict, run_dir: str, res: Path, cpus: int) -> None:
    n = clean(Path(params["proteins"]), res / "proteins.fasta")
    print(f"{n} proteins to annotate", flush=True)
    if os.environ.get("EVERYOME_DEMO"):
        from . import demo_tools
        demo_tools.interproscan(res / "proteins.fasta", res)
        return
    data = params.get("data_dir") or ""
    if not data or not Path(data).is_dir():
        raise ValueError("Set InterProScan data folder to the folder holding InterProScan's data (ask IT, or see the manual).")
    m = load(HERE / "module.yaml")
    cmd = containers.command(m.containers["interproscan"], Path(os.environ["EVERYOME_CONTAINERS"]),
                             interproscan_args(params, res / "proteins.fasta", res, cpus), [run_dir, f"{data}:{IMAGE_DATA}"])
    print("$", " ".join(shlex.quote(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True)


def main(name: str) -> None:
    run_dir = os.environ["EVERYOME_RUN_DIR"]
    params = json.loads(Path(os.environ["EVERYOME_PARAMS"]).read_text())
    res = Path(run_dir) / "results"
    res.mkdir(exist_ok=True)
    try:
        {"annotate": annotate}[name](params, run_dir, res, int(os.environ.get("EVERYOME_CPUS", "1")))
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr, flush=True)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: InterProScan stopped with exit code {e.returncode}; see the lines above.", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1])
