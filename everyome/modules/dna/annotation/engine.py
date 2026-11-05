"""Live session for genome annotation: what the gene models look like (counts, exons per gene, gene and protein
lengths, genes per sequence), how complete they are (BUSCO), any gene's structure and protein, and export.

Reads results/annotation.gff3 (Helixer's gene / mRNA / exon / CDS features), results/proteins.faa and, if BUSCO ran,
results/busco/short_summary*.json. Exports go to results/final/.
"""
from __future__ import annotations

import csv
import json
import shutil
from collections import defaultdict

import numpy as np

from everyome.core.engine import BaseEngine


def read_gff(path) -> dict:
    """Genes with their transcripts' exons and CDS (gene → mRNA → exon/CDS, by Parent)."""
    genes, tx_of, parts = {}, {}, defaultdict(lambda: {"exon": [], "CDS": []})
    for line in open(path):
        if line.startswith("#") or not line.strip():
            if line.startswith("##FASTA"):
                break
            continue
        f = line.rstrip("\n").split("\t")
        if len(f) < 9:
            continue
        a = dict(kv.split("=", 1) for kv in f[8].split(";") if "=" in kv)
        if f[2] == "gene":
            genes[a["ID"]] = {"id": a["ID"], "seqid": f[0], "start": int(f[3]), "end": int(f[4]), "strand": f[6], "transcripts": []}
        elif f[2] in ("mRNA", "transcript"):
            tx_of[a["ID"]] = a.get("Parent", "")
        elif f[2] in ("exon", "CDS"):
            for p in a.get("Parent", "").split(","):
                parts[p][f[2]].append((int(f[3]), int(f[4])))
    for tid, gid in tx_of.items():
        if gid in genes:
            genes[gid]["transcripts"].append({"id": tid, "exons": sorted(parts[tid]["exon"]), "cds": sorted(parts[tid]["CDS"])})
    return genes


def read_fasta(path) -> dict[str, str]:
    out, name = {}, None
    for line in open(path):
        if line.startswith(">"):
            name = line[1:].split()[0]
            out[name] = []
        elif name:
            out[name].append(line.strip())
    return {k: "".join(v) for k, v in out.items()}


def hist(values, edges) -> list[int]:
    return np.histogram(np.clip(values, edges[0], edges[-1] - 1e-9), edges)[0].tolist() if len(values) else [0] * (len(edges) - 1)


class Engine(BaseEngine):
    API = ("overview", "genes", "gene", "export", "files")
    REPLAY = ("export",)

    def __init__(self, run_dir: str):
        super().__init__(run_dir)
        self.res = self.dir / "results"
        if not (self.res / "annotation.gff3").exists():
            raise FileNotFoundError("No gene models in this run's results. Check the stage log on the Run page.")
        self.g = read_gff(self.res / "annotation.gff3")
        self.prot = read_fasta(self.res / "proteins.faa") if (self.res / "proteins.faa").exists() else {}

    def _busco(self):
        f = next(iter(sorted((self.res / "busco").glob("short_summary*.json"))), None) if (self.res / "busco").exists() else None
        if not f:
            return None
        r = json.loads(f.read_text())
        res = r.get("results", {})
        get = lambda *ks: next((res[k] for k in ks if k in res), None)
        return {"lineage": (r.get("lineage_dataset") or {}).get("name", ""), "line": res.get("one_line_summary", ""),
                "complete": get("Complete percentage", "Complete"), "single": get("Single copy percentage"),
                "duplicated": get("Multi copy percentage"), "fragmented": get("Fragmented percentage"), "missing": get("Missing percentage")}

    def overview(self):
        gs = list(self.g.values())
        exons = [len(g["transcripts"][0]["exons"]) for g in gs if g["transcripts"]]
        glen = [g["end"] - g["start"] + 1 for g in gs]
        plen = [len(s.rstrip("*.")) for s in self.prot.values()]
        per_seq = defaultdict(int)
        for g in gs:
            per_seq[g["seqid"]] += 1
        ex_edges, g_edges, p_edges = list(range(1, 22)), list(np.geomspace(100, max(glen + [200]) * 1.01, 31)), list(range(0, 2050, 50))
        info = {"genes": len(gs), "transcripts": sum(len(g["transcripts"]) for g in gs), "proteins": len(self.prot),
                "median_exons": float(np.median(exons)) if exons else 0, "single_exon": int(sum(1 for e in exons if e == 1)),
                "median_gene_length": int(np.median(glen)) if glen else 0, "median_protein_length": int(np.median(plen)) if plen else 0}
        busco = self._busco()
        if self.state.get("overview") != info:
            self.state["overview"] = info
            self._record("read the gene models", **info, busco=busco["line"] if busco else None)
        return {**info, "busco": busco, "per_seq": dict(sorted(per_seq.items(), key=lambda kv: -kv[1])[:40]),
                "exon_hist": {"edges": ex_edges, "counts": hist(exons, ex_edges)},
                "gene_hist": {"edges": [round(x) for x in g_edges], "counts": hist(glen, g_edges)},
                "protein_hist": {"edges": p_edges, "counts": hist(plen, p_edges)}}

    def genes(self, q: str = "", seqid: str = "", n: int = 200):
        q = (q or "").lower()
        out = []
        for g in self.g.values():
            if (q and q not in g["id"].lower()) or (seqid and g["seqid"] != seqid):
                continue
            t = g["transcripts"][0] if g["transcripts"] else {"exons": [], "cds": []}
            out.append({"id": g["id"], "seqid": g["seqid"], "start": g["start"], "end": g["end"], "strand": g["strand"],
                        "exons": len(t["exons"]), "protein": len(self.prot.get(t.get("id", ""), "").rstrip("*."))})
            if len(out) >= int(n):
                break
        return out

    def gene(self, id: str):
        g = self.g.get(id)
        if not g:
            raise ValueError(f"No gene called {id}.")
        t = g["transcripts"][0] if g["transcripts"] else {"id": "", "exons": [], "cds": []}
        return {**{k: g[k] for k in ("id", "seqid", "start", "end", "strand")}, "transcript": t["id"], "exons": t["exons"], "cds": t["cds"],
                "transcripts": len(g["transcripts"]), "protein": self.prot.get(t["id"], "")}

    def export(self):
        out = self.res / "final"
        out.mkdir(exist_ok=True)
        shutil.copy(self.res / "annotation.gff3", out / "annotation.gff3")
        if (self.res / "proteins.faa").exists():
            shutil.copy(self.res / "proteins.faa", out / "proteins.faa")
        with open(out / "genes.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["gene", "sequence", "start", "end", "strand", "transcripts", "exons", "protein_length"])
            for g in self.g.values():
                t = g["transcripts"][0] if g["transcripts"] else {"id": "", "exons": []}
                w.writerow([g["id"], g["seqid"], g["start"], g["end"], g["strand"], len(g["transcripts"]), len(t["exons"]),
                            len(self.prot.get(t["id"], "").rstrip("*."))])
        files = sorted(f.name for f in out.iterdir())
        self._record("exported the annotation", files=files)
        return {"files": files}

    def files(self):
        out = self.res / "final"
        return [{"name": f"final/{f.name}", "size": f.stat().st_size} for f in sorted(out.glob("*"))] if out.exists() else []
