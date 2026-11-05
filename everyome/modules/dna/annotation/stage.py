"""Run one stage of genome annotation for an Everyome run.

Called by each job as `python -m everyome.modules.dna.annotation.stage <predict|proteins|busco>` inside the run folder.
Helixer, gffread and BUSCO run in the images pinned in module.yaml (by digest). Helixer needs a GPU and its lineage
models, which live in a shared folder bound where Helixer looks for them. On the demo cluster, stand-ins write the
same files for the demo genome.

results/
  annotation.gff3     Helixer's gene models (gene, mRNA, exon, CDS, UTR)
  proteins.faa        one protein per transcript (gffread)
  busco/              BUSCO's completeness check on the proteins (when a lineage dataset is set)
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from everyome.core import containers
from everyome.core.manifest import load

HERE = Path(__file__).resolve().parent


def tool(name: str, args: list[str], binds: list[str]):
    m = load(HERE / "module.yaml")
    cmd = containers.command(m.containers[name], Path(os.environ["EVERYOME_CONTAINERS"]), args, binds)
    print("$", " ".join(shlex.quote(c) for c in cmd), flush=True)
    return subprocess.run(cmd, check=True)


def helixer_args(params: dict, res: Path) -> list[str]:
    return ["Helixer.py", "--fasta-path", params["genome"], "--lineage", params.get("lineage") or "invertebrate",
            "--gff-output-path", str(res / "annotation.gff3"), "--species", params.get("species") or "genome",
            *shlex.split(params.get("helixer_extra") or "")]


def predict(params: dict, run_dir: str, res: Path, cpus: int) -> None:
    if os.environ.get("EVERYOME_DEMO"):
        from . import demo_tools
        demo_tools.predict(Path(params["genome"]), res)
        return
    models = params.get("models_dir") or ""
    if not models or not Path(models).is_dir():
        raise ValueError("Set Helixer models folder to the shared folder holding Helixer's lineage models (ask IT, or see the manual).")
    # Intent: Helixer looks for its models under ~/.local/share/Helixer/models; bind the shared folder there.
    target = str(Path.home() / ".local/share/Helixer/models")
    tool("helixer", helixer_args(params, res), [run_dir, str(Path(params["genome"]).parent), f"{models}:{target}"])


def proteins(params: dict, run_dir: str, res: Path, cpus: int) -> None:
    if os.environ.get("EVERYOME_DEMO"):
        from . import demo_tools
        demo_tools.proteins(res)
        return
    tool("gffread", ["gffread", "-y", str(res / "proteins.faa"), "-g", params["genome"], str(res / "annotation.gff3")],
         [run_dir, str(Path(params["genome"]).parent)])


def busco(params: dict, run_dir: str, res: Path, cpus: int) -> None:
    lineage = (params.get("busco_lineage") or "").strip()
    if not lineage:
        print("No BUSCO lineage set: completeness check skipped.", flush=True)
        return
    if os.environ.get("EVERYOME_DEMO"):
        from . import demo_tools
        demo_tools.busco(res, lineage)
        return
    data = params.get("busco_dir") or ""
    args = ["busco", "-i", str(res / "proteins.faa"), "-m", "proteins", "-l", lineage, "-o", "busco", "--out_path", str(res),
            "-c", str(cpus), "-f", *(["--offline", "--download_path", data] if data else [])]
    tool("busco", args, [run_dir, *([data] if data else [])])


STAGES = {"predict": predict, "proteins": proteins, "busco": busco}


def main(name: str) -> None:
    run_dir = os.environ["EVERYOME_RUN_DIR"]
    params = json.loads(Path(os.environ["EVERYOME_PARAMS"]).read_text())
    res = Path(run_dir) / "results"
    res.mkdir(exist_ok=True)
    try:
        STAGES[name](params, run_dir, res, int(os.environ.get("EVERYOME_CPUS", "1")))
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr, flush=True)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: {Path(e.cmd[0]).name} stopped with exit code {e.returncode}; see the lines above.", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1])
