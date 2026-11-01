"""Stand-in for nf-core/bacass on the demo cluster (no Nextflow or containers there).

For each isolate and each assembler asked for, it 'assembles' the demo bacterium
as that assembler would with the run's read type: short reads stop at every rRNA
operon and insertion sequence; long reads cross them but most long-read
assemblers lose the small plasmid; Unicycler's hybrid assembly recovers all three
replicons. Long-read assemblies are polished (Medaka) unless polishing is off.
Files go where nf-core/bacass writes them, with BUSCO summaries and Prokka or
Bakta annotations.
"""
from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path

from .. import demo_genome as dg
from .demo_data import truth

FOLDER = {"unicycler": ("Unicycler", "{id}.scaffolds.fa"), "megahit": ("MEGAHIT", "{id}.contigs.fa.gz"), "flye": ("Flye", "{id}.assembly.fasta.gz"),
          "canu": ("Canu", "{id}.contigs.fasta.gz"), "raven": ("Raven", "{id}.fasta.gz"), "miniasm": ("Miniasm", "{id}.consensus.fasta.gz"),
          "dragonflye": ("Dragonflye", "{id}.fa"), "autocycler": ("Autocycler", "{id}/consensus_assembly.fasta")}


def model(assembler: str, kind: str):
    """(read length, coverage gaps, gene-breaking error rate, replicons lost) for this assembler and read type."""
    if kind == "short":
        return (300, 8 if assembler == "megahit" else 4, 0.0, ())
    if kind == "hybrid":
        return (60_000, 0, 0.0, () if assembler == "unicycler" else ("plasmid_B",))
    return (30_000, 0, 0.06, () if assembler in ("canu", "autocycler") else ("plasmid_B",))


def main():
    run = Path(os.environ["EVERYOME_RUN_DIR"])
    nfp = json.loads((run / "nf_params.json").read_text())
    rows = list(csv.DictReader(open(nfp["input"]), delimiter="\t"))
    pause = float(os.environ.get("EVERYOME_DEMO_PAUSE", "1"))
    kind = nfp.get("assembly_type", "hybrid")
    assemblers = [a.strip() for a in nfp.get("assembler", "unicycler").split(",") if a.strip()]
    tool = nfp.get("annotation_tool", "prokka")
    g, res = truth(), run / "results"
    trace = run / "trace.txt"
    trace.write_text("task_id\thash\tnative_id\tname\tstatus\texit\n")
    k = 0
    for i, r in enumerate(rows):
        for j, asm in enumerate(assemblers):
            aid = f"{r['ID']}-{asm}"
            length, gaps, err, lost = model(asm, kind)
            ctgs = dg.contigs(g, dg.breaks(g, 30 + 10 * i + j, length, gaps, skip=lost),
                              lambda n, c, whole: f"{n}" if asm == "unicycler" else f"contig_{n}" if whole is False else f"contig_{n}")
            folder, pattern = FOLDER[asm]
            dg.write_fasta(res / folder / pattern.format(id=aid), ctgs)
            final, stage = aid, "assembly"
            tasks = [asm.upper()]
            if kind == "long" and not nfp.get("skip_polish"):
                dg.write_fasta(res / "Medaka" / f"{aid}_polished_genome.fa", ctgs)
                err, final, stage = 0.01, aid, "medaka"
                tasks.append("MEDAKA")
            if not nfp.get("skip_busco"):
                dg.write_busco(res / "busco" / f"short_summary.specific.bacteria_odb10.{aid}_{stage}.json", dg.busco(g, ctgs, err, 50 + 10 * i + j), "bacteria_odb10")
                tasks.append("BUSCO")
            if not nfp.get("skip_annotation"):
                genes, _ = dg.lift(g, ctgs)
                genes = [{**x, "id": f"{r['ID'].upper()}_{n:05d}"} for n, x in enumerate(genes, 1)]
                if tool == "bakta":
                    dg.write_gff(res / "Bakta" / final / f"{final}.gff3", genes, "Bakta")
                else:
                    dg.write_gff(res / "Prokka" / final / f"{final}.gff", genes, "Prokka", ctgs)
                tasks.append(tool.upper())
            for t in tasks:
                k += 1
                with open(trace, "a") as fh:
                    fh.write(f"{k}\tab/{k:06x}\t{1000 + k}\tNFCORE_BACASS:BACASS:{t} ({aid})\tCOMPLETED\t0\n")
                print(f"[demo] {t} ({aid})", flush=True)
        time.sleep(pause / max(1, len(rows)))
    (res / "multiqc").mkdir(parents=True, exist_ok=True)
    (res / "multiqc" / "multiqc_report.html").write_text("<!doctype html><title>MultiQC (demo)</title><body style='font-family:sans-serif'>"
                                                         "<h1>MultiQC report (demo)</h1><p>On a real cluster this is nf-core/bacass's quality report.</p></body>")
    (run / "demo_truth.json").write_text(json.dumps({"replicons": g["lengths"], "genes": len(g["genes"])}))
    print("[demo] pipeline finished", flush=True)


if __name__ == "__main__":
    main()
