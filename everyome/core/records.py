"""Run records and the write-ups made from them (docs/PLAN.md section 5).

build() gathers everything about one run into <run>/record/record.json:
inputs (size and checksum), every setting (and whether it differs from the
default), the cluster jobs, software versions, the live-session decisions in
order, the results and the references. write() then makes, in <run>/record/:

  protocol.md       lab-book protocol: what was run, on what, how, and what was decided
  methods.md        a draft methods section (the module writes it from the record)
  methods_edited.md the user's edited version, if they saved one
  references.txt / references.bib
  rerun/            what `python -m everyome.core.rerun` needs to repeat the run

Only the cluster username is recorded about the person; no other personal data.
"""
from __future__ import annotations

import importlib
import json
import re
import shlex
import time

from everyome import __version__

from . import slurm
from .manifest import Manifest

CHECKSUM_LIMIT = 2 * 1024 ** 3          # Intent: checksum files up to 2 GB; record size only above that
EVERYOME_CITE = {"text": f"Horkan H.R. (2026). Everyome: every -ome, for everyone. Version {__version__}.",
                 "url": "https://github.com/Everyome/everyome"}
FOLDER_LIST_MAX = 500



def _pipeline_record(m) -> dict:
    """Which pipeline ran: release, and the checksum of the exact code and plugins Everyome installed."""
    from . import pipelines
    e = pipelines.lock().get(pipelines.key(m.nextflow["pipeline"], str(m.nextflow["revision"])), {})
    return {**{k: m.nextflow.get(k) for k in ("pipeline", "revision", "profile")}, "source": e.get("source"),
            "code_sha256": e.get("sha256"), "plugins": [f"{p['id']} {p['version']}" for p in e.get("plugins", [])],
            "containers": e.get("containers", [])}

def _file_info(backend, path: str) -> dict:
    q = shlex.quote(path)
    cmd = (f"if [ -f {q} ]; then s=$(wc -c < {q} | tr -d ' '); echo \"file $s\"; "
           f"if [ \"$s\" -le {CHECKSUM_LIMIT} ]; then (sha256sum {q} 2>/dev/null || shasum -a 256 {q}) | cut -d' ' -f1; fi; "
           f"elif [ -d {q} ]; then echo dir; else echo missing; fi")
    rc, out, _ = backend.run(cmd, timeout=1800)
    lines = out.split()
    if not lines or lines[0] == "missing":
        return {"kind": "missing"}
    if lines[0] == "file":
        return {"kind": "file", "size": int(lines[1]), "sha256": lines[2] if len(lines) > 2 else None}
    entries = backend.listdir(path)
    files = [e for e in entries if not e.is_dir]
    return {"kind": "folder", "files": len(files), "size": sum(e.size for e in files),
            "listing": [{"name": e.name, "size": e.size, "dir": e.is_dir} for e in entries[:FOLDER_LIST_MAX]]}


def _software(backend, conn: dict, m: Manifest) -> dict:
    pkgs = list(dict.fromkeys(["everyome", *m.requires, "numpy", "pandas", "scipy"]))
    # Intent: modules list import names (Bio, primer3); look versions up under their installed package names.
    script = ("import importlib.metadata as md, json, sys\nout = {'python': sys.version.split()[0]}\ndists = md.packages_distributions()\n"
              f"for p in {pkgs!r}:\n    try: out[p] = md.version(dists.get(p, [p])[0])\n    except Exception: out[p] = None\nprint(json.dumps(out))")
    rc, out, _ = backend.run(f"{shlex.quote(conn['python'])} -c {shlex.quote(script)}", timeout=120)
    try:
        python = json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        python = {}
    tools = {}
    for t in m.tools:
        rc, out, err = backend.run(f"bash -c {shlex.quote(t['version'])} 2>&1 | head -n 1", timeout=60)
        line = (out or err).strip()
        tools[t["name"]] = None if (not line or "not found" in line or "No such file" in line) else line
    return {"python": python, "tools": tools}


def _read_json(backend, path: str):
    try:
        return json.loads(backend.read_text(path))
    except (FileNotFoundError, ValueError):
        return None


def build(backend, conn: dict, project: dict, run: dict, m: Manifest) -> dict:
    """Gather the record for one run (reads the cluster through the backend)."""
    v = run["values"]
    inputs = []
    for f in m.inputs:
        val = v.get(f.id)
        info = _file_info(backend, val) if f.type in ("file", "folder") and val else None
        inputs.append({"id": f.id, "label": f.label, "type": f.type, "value": val, "info": info})
    settings = [{"id": f.id, "label": f.label, "value": v.get(f.id), "default": f.default, "changed": v.get(f.id) != f.default}
                for f in m.params]
    st = slurm.states(backend, run.get("jobs", {})) if run.get("jobs") else {}
    stages = [{"id": s.id, "name": s.name, "title": s.title, **({k: st[s.id].get(k) for k in ("job", "state", "elapsed", "node")} if s.id in st else {"state": "not run"})}
              for s in m.stages]
    state = _read_json(backend, f"{run['dir']}/session/state.json")
    try:
        results = [{"name": e.name, "size": e.size} for e in backend.listdir(f"{run['dir']}/results") if not e.is_dir]
    except FileNotFoundError:
        results = []
    return {
        "record_version": 1, "created": time.strftime("%Y-%m-%d %H:%M:%S"), "everyome": __version__,
        "module": {"id": m.id, "name": m.name, "version": m.version, "suite": m.suite},
        "pipeline": _pipeline_record(m) if m.nextflow else None,
        "run": {"id": run["id"], "created": run.get("created"), "submitted": run.get("submitted"), "user": run.get("user"),
                "demo": bool(run.get("demo")), "project": project["name"], "dir": run["dir"]},
        "computer": "demo cluster" if conn.get("mode") == "demo" else conn.get("host", ""),
        "inputs": inputs, "settings": settings, "resources": run.get("resources", {}), "stages": stages,
        "software": _software(backend, conn, m),
        "session": {"history": state.get("history", []), "calls": state.get("calls", [])} if state else None,
        "results": results, "citations": [EVERYOME_CITE, *m.cite],
    }


# ------------------------------------------------------------------ write-ups
def _size(n) -> str:
    n = n or 0
    return f"{n / 1e9:.1f} GB" if n > 1e9 else f"{n / 1e6:.1f} MB" if n > 1e6 else f"{n / 1e3:.0f} KB" if n > 1e3 else f"{n} B"


def _val(v) -> str:
    if isinstance(v, list) and v and isinstance(v[0], dict):
        return "; ".join(", ".join(str(x) for x in r.values()) for r in v)
    if isinstance(v, bool):
        return "yes" if v else "no"
    return "(empty)" if v in (None, "") else str(v)


def _cell(v) -> str:
    return _val(v).replace("|", "/").replace("\n", " ")     # Intent: keep table cells simple for every Markdown reader


def _plain(v) -> str:
    """A value as people would write it in a lab book."""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:.3g}"
    if isinstance(v, int):
        return f"{v:,}" if abs(v) >= 10000 else str(v)
    if isinstance(v, dict):
        return "; ".join(f"{k} ({', '.join(f'{a} {_plain(b)}' for a, b in x.items())})" if isinstance(x, dict) else f"{k}: {_plain(x)}"
                         for k, x in v.items())
    if isinstance(v, list):
        return ", ".join(_plain(x) for x in v)
    return str(v)


def _details(d: dict) -> str:
    return "; ".join(f"{k.replace('_', ' ')}: {_plain(v)}" for k, v in d.items()
                     if k not in ("at", "action") and v not in (None, "", [], {}))


def protocol(rec: dict) -> str:
    r, mod = rec["run"], rec["module"]
    L = [f"# Protocol: {mod['name']}, run {r['id']}", "",
         f"- **Date of record:** {rec['created']}",
         f"- **Analyst (cluster username):** {r['user']}",
         f"- **Project:** {r['project']}",
         f"- **Run created:** {r['created']}" + (f"; jobs submitted {r['submitted']}" if r.get("submitted") else ""),
         f"- **Where it ran:** {rec['computer']}" + (" (practice data, not real results)" if r["demo"] else ""),
         f"- **Software:** Everyome {rec['everyome']}, module {mod['id']} version {mod['version']}",
         *([f"- **Pipeline:** {rec['pipeline']['pipeline']} release {rec['pipeline']['revision']}, profile {rec['pipeline']['profile']}"
            + (f" (code shipped with Everyome, SHA-256 `{rec['pipeline']['code_sha256'][:16]}…`; plugins {', '.join(rec['pipeline']['plugins'])})" if rec['pipeline'].get("code_sha256") else "")]
           if rec.get("pipeline") else []),
         f"- **Run folder:** `{r['dir']}`", "", "## Inputs", "", "| Input | Path | Size | SHA-256 |", "|---|---|---|---|"]
    for i in rec["inputs"]:
        info = i.get("info") or {}
        if i["type"] == "table":
            L.append(f"| {i['label']} | {_cell(i['value'])} | | |")
        elif info.get("kind") == "file":
            L.append(f"| {i['label']} | `{i['value']}` | {_size(info['size'])} | {('`' + info['sha256'][:16] + '…`') if info.get('sha256') else 'not computed (large file)'} |")
        elif info.get("kind") == "folder":
            L.append(f"| {i['label']} | `{i['value']}` | {info['files']} files, {_size(info['size'])} | |")
        elif info.get("kind") == "missing":
            L.append(f"| {i['label']} | `{i['value']}` | **not found when recorded** | |")
        else:
            L.append(f"| {i['label']} | {_cell(i['value'])} | | |")
    L += ["", "## Settings", "", "| Setting | Value | Default |", "|---|---|---|"]
    L += [f"| {s['label']} | {'**' + _cell(s['value']) + '**' if s['changed'] else _cell(s['value'])} | {_cell(s['default'])} |" for s in rec["settings"]]
    L += ["", "Values in **bold** were changed from the default.", ""]
    if rec["stages"]:
        res = rec["resources"]
        L += ["## Cluster jobs", "", f"Resources per job: {res.get('cpus', '?')} CPUs, {res.get('mem', '?')} memory, time limit {res.get('time', '?')}"
              + (f", partition {res['partition']}" if res.get("partition") else "") + ".", "",
              "| Stage | Step | Job | State | Time | Node |", "|---|---|---|---|---|---|"]
        L += [f"| {s['id']} | {s['title']} | {s.get('job') or ''} | {s.get('state', '')} | {s.get('elapsed') or ''} | {s.get('node') or ''} |" for s in rec["stages"]]
        L.append("")
    if rec["session"] and rec["session"]["history"]:
        L += ["## Live-session steps", "", "In the order they were done:", ""]
        L += [f"{k}. **{h['action'].capitalize()}** ({h['at']}). {_details(h)}" for k, h in enumerate(rec["session"]["history"], 1)]
        L.append("")
    sw = rec["software"]
    L += ["## Software versions", "", "| Software | Version |", "|---|---|"]
    L += [f"| {k} | {v or 'not found'} |" for k, v in sw.get("python", {}).items()]
    L += [f"| {k} | {v or 'not found on the cluster'} |" for k, v in sw.get("tools", {}).items()]
    L += ["", "## Results", ""]
    L += [f"- `{x['name']}` ({_size(x['size'])})" for x in rec["results"]] or ["No result files yet."]
    L += ["", "## How to repeat this run", "",
          "The folder `record/rerun/` holds the exact settings, job scripts and live-session steps. On the cluster, run:", "",
          "```", f"python -m everyome.core.rerun {r['dir']}/record/rerun <new run folder> --submit", "```", "",
          "and, once its jobs have finished, the same command with `--session` instead of `--submit` to replay the live-session steps.", "",
          "## References", ""]
    L += [f"- {c['text']}" + (f" {c['url']}" if c.get("url") else "") for c in rec["citations"]]
    return "\n".join(L) + "\n"


def generic_methods(rec: dict) -> str:
    """Fallback methods text for modules that do not write their own."""
    mod, changed = rec["module"], [s for s in rec["settings"] if s["changed"]]
    text = (f"Data were analysed with the {mod['name']} module (version {mod['version']}) of Everyome "
            f"(version {rec['everyome']}; Horkan, 2026).")
    if changed:
        text += " Settings changed from their defaults: " + "; ".join(f"{s['label'].lower()}, {_val(s['value'])}" for s in changed) + "."
    return text + "\n"


def methods(rec: dict, m: Manifest) -> str:
    if m.methods:
        mod, _, fn = m.methods.partition(":")
        return getattr(importlib.import_module(mod), fn)(rec)
    return generic_methods(rec)


def _bibkey(text: str, seen: set) -> str:
    author = re.match(r"\s*([A-Za-z]+)", text)
    year = re.search(r"\((\d{4})\)", text)
    key = f"{(author.group(1) if author else 'ref').lower()}{year.group(1) if year else ''}"
    k, n = key, 1
    while k in seen:
        n += 1; k = f"{key}{chr(96 + n)}"
    seen.add(k)
    return k


def references(rec: dict) -> tuple[str, str]:
    txt = "\n".join(f"{c['text']}" + (f" {c['url']}" if c.get("url") else "") for c in rec["citations"]) + "\n"
    seen, bib = set(), []
    for c in rec["citations"]:
        doi = re.search(r"doi\.org/(.+)$", c.get("url") or "")
        fields = [f"  note = {{{c['text']}}}"]
        if doi:
            fields.append(f"  doi = {{{doi.group(1)}}}")
        if c.get("url"):
            fields.append(f"  url = {{{c['url']}}}")
        bib.append(f"@misc{{{_bibkey(c['text'], seen)},\n" + ",\n".join(fields) + "\n}")
    return txt, "\n\n".join(bib) + "\n"


def write(backend, rec: dict, m: Manifest, run: dict) -> dict:
    """Write record.json and the write-ups into <run>/record/, plus the rerun bundle."""
    d = f"{run['dir']}/record"
    txt, bib = references(rec)
    files = {"record.json": json.dumps(rec, indent=1), "protocol.md": protocol(rec), "methods.md": methods(rec, m),
             "references.txt": txt, "references.bib": bib}
    for name, body in files.items():
        backend.write_text(f"{d}/{name}", body)
    # Rerun bundle: settings, the scripts that ran, and the live-session calls to replay.
    rr = f"{d}/rerun"
    backend.write_text(f"{rr}/run.json", json.dumps({k: run[k] for k in ("id", "module", "module_version", "values", "resources", "created", "user", "demo") if k in run}, indent=1))
    backend.write_text(f"{rr}/session_calls.json", json.dumps((rec["session"] or {}).get("calls", []), indent=1))
    backend.run(f"mkdir -p {shlex.quote(rr)}/jobs && cp {shlex.quote(run['dir'])}/jobs/*.sbatch {shlex.quote(rr)}/jobs/ 2>/dev/null; true")
    backend.write_text(f"{rr}/README.md", RERUN_README.format(module=m.id, version=m.version, run=run["id"], dir=rr))
    return {"files": sorted(files) + ["rerun/"], "dir": d}


RERUN_README = """# Repeating run {run}

Module {module}, version {version}. Made by Everyome.

This folder holds everything needed to repeat the run with Everyome installed:

- `run.json`: the module, its version, every input and setting, and the cluster resources
- `session_calls.json`: the live-session steps, in order, with their exact settings
- `jobs/`: the job scripts that ran originally (for reference)

To repeat it, on the cluster, with the Python that has Everyome:

```
python -m everyome.core.rerun {dir} /path/to/new/run/folder             # writes the job scripts and shows them
python -m everyome.core.rerun {dir} /path/to/new/run/folder --submit    # also submits them (as you)
python -m everyome.core.rerun {dir} /path/to/new/run/folder --session   # after the jobs finish: replays the live session
```

The new run gets its own folder, so the original is never overwritten.
"""
