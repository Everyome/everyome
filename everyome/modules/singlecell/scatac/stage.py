"""Run the cluster stage of single-cell ATAC-seq for an Everyome run: reads to fragments.

Called by the job as `python -m everyome.modules.singlecell.scatac.stage fragments` inside the run folder. For each
sample, chromap (in the container pinned in module.yaml, by digest) indexes the genome once, aligns the read pairs,
corrects the cell barcodes and writes one fragment per read pair, with PCR duplicates removed and Tn5's offset
applied. Samples that already have a fragments file (for example from Cell Ranger ATAC) are copied as they are.
On the demo cluster, where chromap is not installed, the fragments made with the demo data are copied instead.

results/fragments/<sample>.tsv.gz    chromosome, start, end, cell barcode, read count
"""
from __future__ import annotations

import gzip
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from everyome.core import containers
from everyome.core.manifest import load

HERE = Path(__file__).resolve().parent


def binds(params: dict, run_dir: str) -> list[str]:
    files = [params.get("genome"), params.get("whitelist")] + [r.get(k) for r in params["samples"] for k in ("read1", "read2", "barcodes")]
    return [run_dir, *sorted({str(Path(f).parent) for f in files if f})]


def tool(name: str, args: list[str], params: dict, run_dir: str, **kw):
    """Run a tool in its pinned container; its output goes to the stage log."""
    m = load(HERE / "module.yaml")
    cmd = containers.command(m.containers[name], Path(os.environ["EVERYOME_CONTAINERS"]), args, binds(params, run_dir))
    print("$", " ".join(shlex.quote(c) for c in cmd), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def chromap_args(params: dict, sample: dict, index: Path, out: Path, cpus: int) -> list[str]:
    """The chromap command for one sample (its --preset atac sets fragment output, Tn5 shift and duplicate removal)."""
    return ["chromap", "--preset", "atac", "-x", str(index), "-r", params["genome"],
            "-1", sample["read1"], "-2", sample["read2"], "-b", sample["barcodes"],
            *(["--barcode-whitelist", params["whitelist"]] if params.get("whitelist") else []),
            "-t", str(cpus), "-o", str(out), *shlex.split(params.get("chromap_extra") or "")]


def fragments(params: dict, run_dir: str, res: Path, cpus: int) -> None:
    out = res / "fragments"
    out.mkdir(exist_ok=True)
    todo = [s for s in params["samples"] if not s.get("fragments")]
    for s in params["samples"]:
        if s.get("fragments"):
            print(f"{s['sample']}: using the fragments file given ({s['fragments']})", flush=True)
            shutil.copy(s["fragments"], out / f"{s['sample']}.tsv.gz")
        elif not all(s.get(k) for k in ("read1", "read2", "barcodes")):
            raise ValueError(f"Sample {s['sample']} needs either a fragments file or all three read files (read 1, read 2 and the barcode read).")
    if not todo:
        return
    if os.environ.get("EVERYOME_DEMO"):
        from . import demo_tools
        demo_tools.fragments(todo, out)
        return
    index = res / "genome.index"
    if not index.exists():
        tool("chromap", ["chromap", "-i", "-r", params["genome"], "-o", str(index)], params, run_dir)
    for s in todo:
        plain = out / f"{s['sample']}.tsv"
        tool("chromap", chromap_args(params, s, index, plain, cpus), params, run_dir)
        # Intent: SnapATAC2 and most tools read gzip-compressed fragments; keep only the compressed file.
        with open(plain, "rb") as src, gzip.open(out / f"{s['sample']}.tsv.gz", "wb") as dst:
            shutil.copyfileobj(src, dst)
        plain.unlink()
        print(f"{s['sample']}: fragments written", flush=True)


STAGES = {"fragments": fragments}


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
