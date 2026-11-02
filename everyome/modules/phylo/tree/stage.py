"""Run one stage of alignment and tree building for an Everyome run.

Called by each job as `python -m everyome.modules.phylo.tree.stage <align|trim|tree>` inside the run folder.
MAFFT, trimAl and IQ-TREE run in the containers pinned in module.yaml (by digest), so every cluster runs the
same builds. On the demo cluster, where they are not installed, small Python stand-ins write the same files.

results/
  sequences.fasta      the input, with names made safe for trees (names.tsv maps them back)
  alignment.fasta      MAFFT (or the input itself if it was already aligned)
  trimmed.fasta        trimAl; trim_columns.txt lists the alignment columns it kept
  tree.*               IQ-TREE: tree.treefile (the tree with support), tree.iqtree (report), tree.log
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from everyome.core import containers
from everyome.core.manifest import load

HERE = Path(__file__).resolve().parent
SAFE = re.compile(r"[^A-Za-z0-9_.|-]+")
MAFFT = {"auto": ["--auto"], "linsi": ["--localpair", "--maxiterate", "1000"], "ginsi": ["--globalpair", "--maxiterate", "1000"],
         "einsi": ["--genafpair", "--maxiterate", "1000", "--ep", "0"], "fftns2": ["--retree", "2"]}
TRIMAL = {"automated1": ["-automated1"], "gappyout": ["-gappyout"], "strict": ["-strict"], "strictplus": ["-strictplus"]}
DNA = set("ACGTUNRYSWKMBDHV-?.")


def read_fasta(path: Path) -> list[tuple[str, str]]:
    out, name, seq = [], None, []
    for line in path.read_text().splitlines():
        if line.startswith(">"):
            if name is not None:
                out.append((name, "".join(seq)))
            name, seq = line[1:].strip(), []
        elif line.strip():
            if name is None:
                raise ValueError(f"{path.name} is not FASTA: it should start with a '>' line.")
            seq.append(re.sub(r"\s+", "", line))
    if name is not None:
        out.append((name, "".join(seq)))
    return out


def write_fasta(path: Path, recs: list[tuple[str, str]]) -> None:
    path.write_text("".join(f">{n}\n" + "\n".join(s[i:i + 80] for i in range(0, len(s), 80)) + "\n" for n, s in recs))


def seq_type(recs, chosen: str) -> str:
    if chosen in ("dna", "protein"):
        return chosen
    letters = "".join(s for _, s in recs).upper()
    return "dna" if letters and sum(c in DNA for c in letters) / len(letters) > 0.9 else "protein"


def clean_names(recs) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Tree-safe names (first word, odd characters as _) and the mapping back to the original headers."""
    names, out = {}, []
    for header, s in recs:
        n = SAFE.sub("_", header.split()[0] if header.split() else "seq").strip("_") or "seq"
        if n in names:
            raise ValueError(f"Two sequences would both be called {n} ({names[n]!r} and {header!r}). Give each sequence a different first word.")
        names[n] = header
        out.append((n, s))
    return out, [(n, h) for n, h in names.items()]


def tip_names(text: str, res: Path) -> list[str]:
    """Names typed by a person (comma-separated tree names, or whole original headers) as the tree's names."""
    p = res / "names.tsv"
    back = {h: n for n, h in (r.split("\t", 1) for r in p.read_text().splitlines()[1:] if "\t" in r)} if p.is_file() else {}
    out = []
    for x in (x.strip() for x in (text or "").split(",")):
        if x:
            out.append(back.get(x) or SAFE.sub("_", x.split()[0]).strip("_"))
    return out


def binds(params: dict, run_dir: str) -> list[str]:
    return [run_dir, *(str(Path(params[k]).parent) for k in ("sequences",) if params.get(k))]


def tool(name: str, args: list[str], params: dict, run_dir: str, **kw):
    """Run a tool in its pinned container; its output goes to the stage log."""
    m = load(HERE / "module.yaml")
    cmd = containers.command(m.containers[name], Path(os.environ["EVERYOME_CONTAINERS"]), args, binds(params, run_dir))
    print("$", " ".join(shlex.quote(c) for c in cmd), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def align(params: dict, run_dir: str, res: Path, cpus: int) -> None:
    recs = read_fasta(Path(params["sequences"]))
    if len(recs) < 4:
        raise ValueError(f"A tree needs at least 4 sequences; {params['sequences']} has {len(recs)}.")
    recs, names = clean_names(recs)
    write_fasta(res / "sequences.fasta", recs)
    (res / "names.tsv").write_text("name\toriginal\n" + "".join(f"{n}\t{h}\n" for n, h in names))
    kind = seq_type(recs, params["seq_type"])
    (res / "sequence_type.txt").write_text(kind + "\n")
    print(f"{len(recs)} sequences ({'DNA' if kind == 'dna' else 'protein'}), {min(len(s) for _, s in recs)}–{max(len(s) for _, s in recs)} letters long", flush=True)
    if params["already_aligned"]:
        if len({len(s) for _, s in recs}) != 1:
            raise ValueError("'Already aligned' is on, but the sequences are not all the same length. Turn it off to align them with MAFFT.")
        shutil.copy(res / "sequences.fasta", res / "alignment.fasta")
        print("Already aligned: MAFFT skipped.")
        return
    if os.environ.get("EVERYOME_DEMO"):
        from . import demo_tools
        demo_tools.align(res, Path(params["sequences"]))
        return
    args = ["mafft", *MAFFT[params["mafft_strategy"]], "--thread", str(cpus), "--amino" if kind == "protein" else "--nuc",
            *shlex.split(params.get("mafft_extra") or ""), str(res / "sequences.fasta")]
    with open(res / "alignment.fasta", "w") as out:
        tool("mafft", args, params, run_dir, stdout=out)


def trim(params: dict, run_dir: str, res: Path, cpus: int) -> None:
    method = params["trim_method"]
    if method == "none":
        shutil.copy(res / "alignment.fasta", res / "trimmed.fasta")
        n = len(read_fasta(res / "alignment.fasta")[0][1])
        (res / "trim_columns.txt").write_text("#ColumnsMap\t" + ", ".join(map(str, range(n))) + "\n")
        print("Trimming turned off: the whole alignment is used.")
        return
    if os.environ.get("EVERYOME_DEMO"):
        from . import demo_tools
        demo_tools.trim(res, method, params["min_present"])
        return
    how = ["-gt", str(params["min_present"])] if method == "gap_threshold" else TRIMAL[method]
    args = ["trimal", "-in", str(res / "alignment.fasta"), "-out", str(res / "trimmed.fasta"), "-fasta", *how, "-colnumbering",
            *shlex.split(params.get("trimal_extra") or "")]
    with open(res / "trim_columns.txt", "w") as out:
        tool("trimal", args, params, run_dir, stdout=out)


def tree(params: dict, run_dir: str, res: Path, cpus: int) -> None:
    kind = (res / "sequence_type.txt").read_text().strip()
    recs = read_fasta(res / "trimmed.fasta")
    if not recs or not recs[0][1]:
        raise ValueError("Trimming removed every column. Choose a gentler trimming method, or turn trimming off.")
    empty = [n for n, s in recs if not s.strip("-?.Xx")]
    if empty:
        print(f"Warning: after trimming these sequences have no letters left: {', '.join(empty)}. Their place in the tree means nothing.", flush=True)
    boot, alrt = int(params["bootstrap"]), int(params["alrt"])
    if 0 < boot < 1000:
        raise ValueError(f"Ultrafast bootstrap needs at least 1000 replicates (or 0 to turn it off); the settings ask for {boot}.")
    outgroup = tip_names(params.get("outgroup"), res)
    if os.environ.get("EVERYOME_DEMO"):
        from . import demo_tools
        demo_tools.tree(res, kind, params["model"], boot, alrt, int(params["seed"]), outgroup)
        return
    args = ["iqtree3", "-s", str(res / "trimmed.fasta"), "--seqtype", "DNA" if kind == "dna" else "AA", "-m", params["model"],
            "--prefix", str(res / "tree"), "-T", str(cpus), "--seed", str(params["seed"]),
            *(["-B", str(boot)] if boot else []), *(["--alrt", str(alrt)] if alrt else []),
            *(["-o", ",".join(outgroup)] if outgroup else []), *shlex.split(params.get("iqtree_extra") or "")]
    tool("iqtree", args, params, run_dir)


STAGES = {"align": align, "trim": trim, "tree": tree}


def main(name: str) -> None:
    run_dir = os.environ["EVERYOME_RUN_DIR"]
    params = json.loads(Path(os.environ["EVERYOME_PARAMS"]).read_text())
    res = Path(run_dir) / "results"
    res.mkdir(exist_ok=True)
    try:
        STAGES[name](params, run_dir, res, int(os.environ.get("EVERYOME_CPUS", "1")))
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        # Intent: a plain message at the end of the log, not a traceback, for problems with the input.
        print(f"ERROR: {e}", file=sys.stderr, flush=True)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: {Path(e.cmd[0]).name} stopped with exit code {e.returncode}; see the lines above.", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1])
