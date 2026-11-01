"""Live session shared by the genome assembly modules: compare assemblies, look at contigs and genes, choose one, export.

Works on whatever the pipeline wrote under <run>/results: it finds every assembly
(FASTA) and works out its statistics itself (size, contigs, N50, GC, gaps), reads
BUSCO completeness from BUSCO's short summaries, and matches each gene annotation
(GFF) to the assembly whose contigs it describes. So the same session serves
nf-core/genomeassembler and nf-core/bacass, and any assembly stage they add.

Pure Python (no heavy packages): it can run on any cluster Python with Everyome.
Statistics are cached in <run>/session/assemblies.json.
"""
from __future__ import annotations

import gzip
import json
import re
import shutil
from pathlib import Path

from everyome.core.engine import BaseEngine

FASTA = re.compile(r"\.(fa|fasta|fna|fas)(\.gz)?$", re.I)
GFF = re.compile(r"\.gff3?(\.gz)?$", re.I)
# Intent: folders that hold reads, QC working files, references or gene sequences, not assemblies.
SKIP = {"reads", "prepare", "fastp", "trim", "trimmed", "porechop", "filtlong", "nanoplot", "pycoqc", "fastqc", "kraken2", "kmerfinder",
        "qc", "busco", "quast", "merqury", "multiqc", "pipeline_info", "work", "reference", "references", "genomeqc_samplesheet",
        "report", "report_files", "jellyfish", "meryl", "alignments", "mapping", "prokka", "bakta", "dfast", "gfa2_fasta"}
GENE_SKIP = {"reads", "work", "pipeline_info", "reference", "references", "multiqc", "busco", "quast"}
STAGES = [("scaffold", ("scaffold", "ragtag", "links", "longstitch", "yahs")), ("polished", ("polish", "pilon", "medaka", "dorado", "racon", "nanopolish")),
          ("assembly", ("assembly", "flye", "hifiasm", "unicycler", "dragonflye", "canu", "miniasm", "raven", "megahit", "autocycler", "spades"))]
# Assemblers first, then polishers, then scaffolders: the order tools act on an assembly.
TOOLS = ["flye", "hifiasm", "unicycler", "dragonflye", "canu", "miniasm", "raven", "megahit", "autocycler", "spades",
         "racon", "medaka", "nanopolish", "dorado", "pilon", "ragtag", "links", "longstitch", "yahs"]

def _open(path: Path):
    return gzip.open(path, "rt") if str(path).endswith(".gz") else open(path)


def fasta_stats(path: Path) -> dict:
    """Per-contig lengths, GC and N counts, read once (streamed, so large genomes are fine)."""
    contigs, name, n, gc, ns = [], None, 0, 0, 0
    with _open(path) as fh:
        for line in fh:
            if line.startswith(">"):
                if name is not None:
                    contigs.append((name, n, gc, ns))
                name, n, gc, ns = line[1:].split()[0] if line[1:].split() else f"seq{len(contigs) + 1}", 0, 0, 0
            else:
                s = line.strip().upper()
                n += len(s); gc += s.count("G") + s.count("C"); ns += s.count("N")
    if name is not None:
        contigs.append((name, n, gc, ns))
    contigs.sort(key=lambda c: -c[1])
    lengths = [c[1] for c in contigs]
    total = sum(lengths)
    return {"contigs": [{"name": c[0], "length": c[1], "gc": round(c[2] / max(1, c[1] - c[3]), 4), "ns": c[3]} for c in contigs],
            "total": total, "n": len(lengths), "largest": lengths[0] if lengths else 0,
            "gc": round(sum(c[2] for c in contigs) / max(1, total - sum(c[3] for c in contigs)), 4), "ns": sum(c[3] for c in contigs),
            **nx(lengths, total)}


def nx(lengths: list[int], total: int) -> dict:
    """N50 and L50 (and N90), from lengths sorted longest first."""
    out, acc, i = {}, 0, 0
    for target, key in ((0.5, "50"), (0.9, "90")):
        while i < len(lengths) and acc < target * total:
            acc += lengths[i]; i += 1
        out["n" + key], out["l" + key] = (lengths[i - 1], i) if i else (0, 0)
    return out


def gff_genes(path: Path) -> tuple[list[dict], dict, set]:
    """Genes (or CDS when a file has no gene features), counts of every feature type, and the sequence names used."""
    genes, cds, counts, seqids = [], [], {}, set()
    with _open(path) as fh:
        for line in fh:
            if line.startswith("##FASTA"):
                break                                    # Prokka appends the sequences after this line
            if line.startswith("#") or not line.strip():
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) < 9:
                continue
            seqids.add(f[0])
            counts[f[2]] = counts.get(f[2], 0) + 1
            if f[2] in ("gene", "CDS"):
                attr = dict(kv.split("=", 1) for kv in f[8].split(";") if "=" in kv)
                row = {"id": attr.get("ID") or attr.get("locus_tag") or attr.get("Name", ""), "name": attr.get("Name") or attr.get("gene", ""),
                       "product": attr.get("product", ""), "seqid": f[0], "start": int(f[3]), "end": int(f[4]), "strand": f[6],
                       "length": int(f[4]) - int(f[3]) + 1}
                row["parent"] = attr.get("Parent", "")
                (genes if f[2] == "gene" else cds).append(row)
    # Intent: products usually sit on the CDS (or mRNA) lines; give each gene its child's product and name.
    kids = {}
    for x in cds:
        kids.setdefault(x["parent"].split(",")[0], x)
    for gene in genes:
        kid = kids.get(gene["id"]) or kids.get(f"{gene['id']}.t1") or {}
        gene["product"] = gene["product"] or kid.get("product", "")
    return (genes or cds), counts, seqids


def _stage(parts: tuple[str, ...], name: str) -> tuple[str, list[str]]:
    """(stage, tools in the order they acted), from an assembly's folders and file name."""
    low = [p.lower() for p in parts] + [name.lower()]
    tools = [t for t in TOOLS if any(re.search(rf"(^|[^a-z]){t}([^a-z]|$)", p) for p in low)]
    # Intent: the stage comes from folder names only; file names mislead (Unicycler's assembly is "scaffolds.fa").
    folders = low[:-1]
    stage = next((s for s, keys in STAGES if any(k in p for p in folders for k in keys)), "assembly")
    return stage, tools

class Engine(BaseEngine):
    API = ("assemblies", "nx_curves", "contigs", "genes", "choose", "export", "files")
    REPLAY = ("choose", "export")

    def __init__(self, run_dir: str):
        super().__init__(run_dir)
        self.res = self.dir / "results"
        self.cache_path = self.out / "assemblies.json"
        self.found = json.loads(self.cache_path.read_text()) if self.cache_path.exists() else None

    def status(self):
        return {**super().status(), "chosen": self.state.get("chosen"), "assemblies": len(self._found())}

    # ---------------------------------------------------------------- finding what the pipeline made
    def _samples(self) -> list[str]:
        rows = next((v for v in self.params.values() if isinstance(v, list) and v and isinstance(v[0], dict)), [])
        return sorted({str(r.get("sample") or r.get("ID") or "") for r in rows} - {""}, key=len, reverse=True)

    def _sample_of(self, rel: Path) -> str:
        text = "/".join(rel.parts)
        return next((s for s in self._samples() if s in text.split("/") or Path(rel.name).name.startswith(s)), rel.parts[0])

    def _found(self) -> list[dict]:
        if self.found is None:
            self.found = self._discover()
            self.cache_path.write_text(json.dumps(self.found))
        return self.found

    def _discover(self) -> list[dict]:
        if not self.res.is_dir():
            return []
        out, seen = [], set()
        for path in sorted(self.res.rglob("*")):
            rel = path.relative_to(self.res)
            if not path.is_file() or not FASTA.search(path.name) or {p.lower() for p in rel.parts[:-1]} & SKIP:
                continue
            st = fasta_stats(path)
            if not st["n"]:
                continue
            sample = self._sample_of(rel)
            # Intent: classify by folders and file name without the sample's own name (a sample may be called "x_scaffold").
            strip = lambda t: t.replace(sample, "")
            stage, tools = _stage(tuple(strip(p) for p in rel.parts[:-1]), strip(path.name))
            tool = tools[-1] if tools else ""
            sig = (sample, stage, tuple(tools), st["total"], st["n"], st["n50"])
            if sig in seen:                                   # the same assembly written twice (plain and compressed)
                continue
            seen.add(sig)
            aid = re.sub(r"[^A-Za-z0-9]+", "_", f"{sample}_{stage}_{'_'.join(tools)}").strip("_")
            while any(a["id"] == aid for a in out):
                aid += "_b"
            out.append({"id": aid, "sample": sample, "stage": stage, "tool": tool, "path": str(rel), "tools": tools, "label": f"{sample} · {stage}" + (f" ({' + '.join(tools)})" if tools else ""),
                        **{k: v for k, v in st.items() if k != "contigs"}, "contig_list": st["contigs"][:2000]})
        busco, genes = self._busco(), self._gffs()
        rank = {"assembly": 0, "polished": 1, "scaffold": 2}
        word = lambda w, k: re.search(rf"(^|[_.-]){re.escape(w)}([_.-]|$)", k.replace(".json", "")) is not None
        for a in out:
            # BUSCO names each summary after the assembly it checked: its sample, its tools, and "assembly" for a first assembly.
            mine = {k: b for k, b in busco.items() if a["sample"] in k}
            if a["stage"] != "polished":
                # Intent: an unpolished assembly's summary does not name a polisher.
                mine = {k: b for k, b in mine.items() if not any(word(t, k) for t in ("pilon", "medaka", "dorado", "racon", "nanopolish"))}
            fits = [k for k in mine if a["tool"] and word(a["tool"], k)]
            if not fits:
                fits = [k for k in mine if word("assembly", k) or word(a["stage"], k)]
                first = [x for x in out if x["sample"] == a["sample"] and x["stage"] != "polished"]
                if first and max(first, key=lambda x: rank[x["stage"]]) is not a:
                    fits = []
            a["busco"] = mine[sorted(fits, key=len)[0]] if fits else None
            names = {c["name"] for c in a["contig_list"]}
            # Intent: an annotation belongs to the same sample's assembly whose contig names it uses.
            ok = [g for g in genes if a["sample"] in g["path"] and g["seqids"] & names]
            # Several assemblers can name contigs alike (contig_1, ...), so the annotation naming this assembly's tools wins.
            score = lambda g: (sum(re.search(rf"(^|[^a-z]){t}([^a-z]|$)", g["path"].lower()) is not None for t in a["tools"]), len(g["seqids"] & names))
            a["annotation"] = max(ok, key=score)["path"] if ok else None
        # A sample's annotation whose contig names match nothing (some annotators rename contigs) goes to its most finished assembly.
        for smp in {a["sample"] for a in out}:
            mine = [a for a in out if a["sample"] == smp]
            if not any(a["annotation"] for a in mine):
                g = next((g for g in genes if smp in g["path"]), None)
                if g:
                    max(mine, key=lambda x: rank[x["stage"]])["annotation"] = g["path"]
        return out

    def _busco(self) -> dict:
        out = {}
        for p in self.res.rglob("short_summary*.json"):
            try:
                d = json.loads(p.read_text())
            except ValueError:
                continue
            line = (d.get("results") or {}).get("one_line_summary") or d.get("one_line_summary", "")
            m = re.search(r"C:([\d.]+)%\[S:([\d.]+)%,D:([\d.]+)%\],F:([\d.]+)%,M:([\d.]+)%,n:(\d+)", line)
            if m:
                c, s, dup, f, miss, n = m.groups()
                lineage = (d.get("lineage_dataset") or {}).get("name", "")
                out[p.name] = {"complete": float(c), "single": float(s), "duplicated": float(dup), "fragmented": float(f), "missing": float(miss),
                               "markers": int(n), "lineage": lineage}
        return out

    def _gffs(self) -> list[dict]:
        out = []
        for p in sorted(self.res.rglob("*")):
            rel = p.relative_to(self.res)
            if p.is_file() and GFF.search(p.name) and not ({x.lower() for x in rel.parts[:-1]} & GENE_SKIP):
                genes, counts, seqids = gff_genes(p)
                out.append({"path": str(rel), "seqids": seqids, "genes": len(genes)})
        return out

    def _get(self, aid: str) -> dict:
        a = next((x for x in self._found() if x["id"] == aid), None)
        if a is None:
            raise ValueError(f"No assembly called {aid}.")
        return a

    # ---------------------------------------------------------------- views
    def assemblies(self):
        keys = ("id", "sample", "stage", "tool", "label", "path", "total", "n", "largest", "n50", "l50", "n90", "gc", "ns", "busco", "annotation")
        return [{k: a.get(k) for k in keys} for a in self._found()]

    def nx_curves(self, ids: list[str] | None = None):
        """For each assembly, contig length (y) against the share of the genome in contigs at least that long (x)."""
        out = []
        for a in self._found():
            if ids and a["id"] not in ids:
                continue
            acc, pts = 0, []
            for c in a["contig_list"]:
                pts.append([round(100 * acc / a["total"], 2), c["length"]])
                acc += c["length"]
                pts.append([round(100 * acc / a["total"], 2), c["length"]])
            out.append({"id": a["id"], "label": a["label"], "points": pts[:4000]})
        return out

    def contigs(self, id: str, n: int = 200):
        a = self._get(id)
        return {"label": a["label"], "total": a["total"], "contigs": a["contig_list"][:int(n)], "count": a["n"]}

    def genes(self, id: str, q: str = "", n: int = 200):
        a = self._get(id)
        if not a.get("annotation"):
            return {"annotation": None}
        genes, counts, _ = gff_genes(self.res / a["annotation"])
        hits = [g for g in genes if not q or q.lower() in f"{g['id']} {g['name']} {g['product']}".lower()]
        lengths = [g["length"] for g in genes]
        edges = [0, 300, 600, 900, 1200, 1500, 2000, 3000, 5000, 10000, 10 ** 9]
        hist = [sum(1 for x in lengths if lo <= x < hi) for lo, hi in zip(edges, edges[1:])]
        unmapped = next(iter(sorted((self.res / a["annotation"]).parent.glob("*unmapped*.txt"))), None)
        return {"annotation": a["annotation"], "counts": counts, "genes": len(genes), "matches": len(hits), "rows": hits[:int(n)],
                "hist": {"edges": edges[:-1], "counts": hist}, "with_name": sum(1 for g in genes if g["name"] or (g["product"] and "hypothetical" not in g["product"].lower())),
                "unmapped": sum(1 for line in open(unmapped) if line.strip()) if unmapped else None,
                "per_contig": sorted(((s, sum(1 for g in genes if g["seqid"] == s)) for s in {g["seqid"] for g in genes}), key=lambda x: -x[1])[:30]}

    # ---------------------------------------------------------------- decide and export
    def choose(self, id: str, reason: str = ""):
        a = self._get(id)
        self.state["chosen"] = id
        self.state["step"] = "chosen"
        self._record("chose the final assembly", id=id, label=a["label"], path=a["path"], total=a["total"], contigs=a["n"], n50=a["n50"],
                     busco=(a.get("busco") or {}).get("complete"), lineage=(a.get("busco") or {}).get("lineage"), annotation=a.get("annotation"),
                     reason=reason.strip())
        return {"chosen": id}

    def export(self):
        if not self.state.get("chosen"):
            raise ValueError("Choose the final assembly first.")
        a = self._get(self.state["chosen"])
        d = self.res / "final"
        d.mkdir(exist_ok=True)
        src = self.res / a["path"]
        dst = d / f"{a['sample']}_final_assembly.fa"
        with _open(src) as fh, open(dst, "w") as out:
            shutil.copyfileobj(fh, out)
        files = [dst.name]
        if a.get("annotation"):
            g = d / f"{a['sample']}_final_annotation.gff3"
            with _open(self.res / a["annotation"]) as fh, open(g, "w") as out:
                shutil.copyfileobj(fh, out)
            files.append(g.name)
        cols = ("label", "path", "total", "n", "largest", "n50", "l50", "n90", "gc", "ns")
        with open(d / "assembly_comparison.tsv", "w") as fh:
            fh.write("\t".join(cols + ("busco_complete", "busco_lineage", "chosen")) + "\n")
            for x in self._found():
                b = x.get("busco") or {}
                fh.write("\t".join(str(x.get(c, "")) for c in cols) + f"\t{b.get('complete', '')}\t{b.get('lineage', '')}\t{'yes' if x['id'] == a['id'] else ''}\n")
        files.append("assembly_comparison.tsv")
        self.state["step"] = "exported"
        self._record("exported the final assembly", files=files)
        return {"files": files}

    def files(self):
        d = self.res / "final"
        return [{"name": f"final/{p.name}", "size": p.stat().st_size} for p in sorted(d.iterdir())] if d.is_dir() else []
