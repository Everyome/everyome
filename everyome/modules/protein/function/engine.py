"""Live session for protein function annotation: what InterProScan found in each protein (domains and families from
each member database, grouped into InterPro entries), the GO terms they imply, search, and tables to export.

Reads results/interproscan.tsv (matches) and, for GO term names, results/interproscan.json; results/proteins.fasta
lists every protein, so proteins with no match are counted too.
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from everyome.core.engine import BaseEngine

COLS = ["protein", "md5", "length", "database", "accession", "description", "start", "end", "score", "status", "date",
        "interpro", "interpro_name", "go", "pathways"]
ASPECT = {"MOLECULAR_FUNCTION": "molecular function", "BIOLOGICAL_PROCESS": "biological process", "CELLULAR_COMPONENT": "cellular component",
          "F": "molecular function", "P": "biological process", "C": "cellular component"}


def read_fasta_lengths(path: Path) -> dict[str, int]:
    out, name = {}, None
    for line in path.read_text().splitlines():
        if line.startswith(">"):
            name = line[1:].split()[0]
            out[name] = 0
        elif name:
            out[name] += len(line.strip())
    return out


def read_tsv(path: Path) -> list[dict]:
    rows = []
    for r in csv.reader(open(path), delimiter="\t"):
        if len(r) < 11:
            continue
        r = r + ["-"] * (len(COLS) - len(r))
        d = dict(zip(COLS, r))
        d["start"], d["end"] = int(d["start"]), int(d["end"])
        d["go"] = [g.split("(")[0] for g in d["go"].split("|") if g and g != "-"]
        for k in ("interpro", "interpro_name", "description", "pathways"):
            d[k] = "" if d[k] == "-" else d[k]
        rows.append(d)
    return rows


def go_names(path: Path) -> dict[str, tuple[str, str]]:
    """GO id → (name, aspect) from InterProScan's JSON (entries' goXRefs)."""
    if not path.exists():
        return {}
    out = {}
    for res in json.loads(path.read_text()).get("results", []):
        for m in res.get("matches", []):
            for g in ((m.get("signature") or {}).get("entry") or {}).get("goXRefs") or []:
                out[g["id"]] = (g.get("name", ""), ASPECT.get(g.get("category", ""), g.get("category", "")))
    return out


class Engine(BaseEngine):
    API = ("overview", "protein", "go_terms", "search", "export", "files")
    REPLAY = ("export",)

    def __init__(self, run_dir: str):
        super().__init__(run_dir)
        self.res = self.dir / "results"
        tsv = self.res / "interproscan.tsv"
        if not tsv.exists():
            raise FileNotFoundError("No InterProScan results in this run. Check the stage log on the Run page.")
        self.lengths = read_fasta_lengths(self.res / "proteins.fasta")
        self.rows = read_tsv(tsv)
        self.go = go_names(self.res / "interproscan.json")
        self.by = defaultdict(list)
        for r in self.rows:
            self.by[r["protein"]].append(r)

    def _protein_go(self, pid: str) -> list[str]:
        return sorted({g for r in self.by.get(pid, []) for g in r["go"]})

    def overview(self):
        n = len(self.lengths)
        with_match = sum(1 for p in self.lengths if self.by.get(p))
        with_ipr = sum(1 for p in self.lengths if any(r["interpro"] for r in self.by.get(p, [])))
        with_go = sum(1 for p in self.lengths if self._protein_go(p))
        entries = Counter()
        for p, rs in self.by.items():
            for e in {(r["interpro"], r["interpro_name"]) for r in rs if r["interpro"]}:
                entries[e] += 1
        dbs = Counter(r["database"] for r in self.rows)
        info = {"proteins": n, "with_match": with_match, "with_interpro": with_ipr, "with_go": with_go, "matches": len(self.rows),
                "databases": dict(dbs.most_common())}
        if self.state.get("overview") != info:
            self.state["overview"] = info
            self._record("read InterProScan results", **info)
        return {**info, "top_entries": [{"entry": e, "name": nm, "proteins": c} for (e, nm), c in entries.most_common(25)],
                "proteins_list": [{"id": p, "length": L, "matches": len(self.by.get(p, [])),
                                   "entries": sorted({r["interpro_name"] or r["description"] for r in self.by.get(p, [])})}
                                  for p, L in self.lengths.items()]}

    def protein(self, id: str):
        if id not in self.lengths:
            raise ValueError(f"No protein called {id}.")
        rs = sorted(self.by.get(id, []), key=lambda r: (r["start"], r["database"]))
        return {"id": id, "length": self.lengths[id],
                "matches": [{k: r[k] for k in ("database", "accession", "description", "start", "end", "score", "interpro", "interpro_name")}
                            for r in rs],
                "go": [{"id": g, "name": self.go.get(g, ("", ""))[0], "aspect": self.go.get(g, ("", ""))[1]} for g in self._protein_go(id)]}

    def go_terms(self):
        count = defaultdict(set)
        for r in self.rows:
            for g in r["go"]:
                count[g].add(r["protein"])
        return [{"id": g, "name": self.go.get(g, ("", ""))[0], "aspect": self.go.get(g, ("", ""))[1], "proteins": sorted(ps)}
                for g, ps in sorted(count.items(), key=lambda kv: (-len(kv[1]), kv[0]))]

    def search(self, q: str):
        q = (q or "").strip().lower()
        if len(q) < 2:
            return []
        hits = set()
        for p in self.lengths:
            if q in p.lower():
                hits.add(p)
        for r in self.rows:
            if any(q in str(r[k]).lower() for k in ("accession", "description", "interpro", "interpro_name")) or any(q in g.lower() for g in r["go"]):
                hits.add(r["protein"])
        return sorted(hits)[:200]

    def export(self):
        out = self.res / "tables"
        out.mkdir(exist_ok=True)
        with open(out / "protein_annotations.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["protein", "length", "interpro_entries", "descriptions", "go_terms"])
            for p, L in self.lengths.items():
                rs = self.by.get(p, [])
                w.writerow([p, L, ";".join(sorted({r["interpro"] for r in rs if r["interpro"]})),
                            ";".join(sorted({r["interpro_name"] or r["description"] for r in rs})), ";".join(self._protein_go(p))])
        with open(out / "domains.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["protein", "database", "accession", "description", "start", "end", "score", "interpro", "interpro_name"])
            for r in self.rows:
                w.writerow([r[k] for k in ("protein", "database", "accession", "description", "start", "end", "score", "interpro", "interpro_name")])
        with open(out / "go_terms.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["go_id", "name", "aspect", "n_proteins", "proteins"])
            for t in self.go_terms():
                w.writerow([t["id"], t["name"], t["aspect"], len(t["proteins"]), ";".join(t["proteins"])])
        files = sorted(f.name for f in out.iterdir())
        self._record("exported annotation tables", files=files)
        return {"files": files}

    def files(self):
        out = self.res / "tables"
        return [{"name": f"tables/{f.name}", "size": f.stat().st_size} for f in sorted(out.glob("*"))] if out.exists() else []
