"""Stand-in for nf-core/genomeassembler on the demo cluster (no Nextflow or containers there).

For each row of the samplesheet it 'assembles' the demo genome as those reads
would: Nanopore reads (long) cross every repeat, HiFi reads (shorter, accurate)
stop at the longest repeats, hybrid assembly takes the best of both, and
scaffolding joins one assembly onto the other. Uncorrected Nanopore errors break
some genes; Medaka and Pilon polishing repair most of them. Files go where the
real pipeline writes them, with BUSCO summaries and, if asked, lifted-over genes.
"""
from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path

from .. import demo_genome as dg
from .demo_data import truth

READ = {"ont": (40_000, 2, 0.08), "hifi": (15_000, 1, 0.005)}      # read length, coverage gaps, gene-breaking error rate
POLISHED = {"medaka": 0.03, "pilon": 0.005, "dorado": 0.02}


def _name(tool, sample):
    return {"flye": lambda i, c, w: f"contig_{i}", "hifiasm": lambda i, c, w: f"ptg{i:06d}l",
            "ragtag": lambda i, c, w: f"ptg{i:06d}l_RagTag"}[tool]


def main():
    run = Path(os.environ["EVERYOME_RUN_DIR"])
    nfp = json.loads((run / "nf_params.json").read_text())
    rows = list(csv.DictReader(open(nfp["input"])))
    pause = float(os.environ.get("EVERYOME_DEMO_PAUSE", "1"))
    g = truth()
    trace = run / "trace.txt"
    trace.write_text("task_id\thash\tnative_id\tname\tstatus\texit\n")
    lift = bool(nfp.get("lift_annotations")) and nfp.get("ref_gff")
    lineage = "eukaryota_odb10" if nfp.get("busco_lineage", "auto_euk") == "auto_euk" else nfp["busco_lineage"]
    k = 0
    for i, r in enumerate(rows):
        s, res = r["sample"], run / "results" / r["sample"]
        has = {"ont": bool(r.get("ontreads")), "hifi": bool(r.get("hifireads"))}
        strategy, assembler = r.get("strategy", "single"), r.get("assembler", "hifiasm")
        tasks = []
        if strategy == "single":
            kind = ("ont" if has["ont"] else "hifi") if assembler == "flye" else ("hifi" if has["hifi"] else "ont")
            cuts = dg.breaks(g, 10 + i, READ[kind][0], READ[kind][1])
            ctgs, err = dg.contigs(g, cuts, _name(assembler, s)), READ[kind][2]
            out = res / "assembly" / assembler / (f"{s}.assembly.fa.gz" if assembler == "flye" else f"{s}.asm.bp.p_ctg.fa.gz")
            tasks.append(assembler.upper())
        elif strategy == "hybrid":                         # hifiasm --ul: HiFi accuracy, Nanopore reach
            ctgs, err = dg.contigs(g, dg.breaks(g, 10 + i, READ["ont"][0], 1), _name("hifiasm", s)), READ["hifi"][2]
            out = res / "assembly" / "hifiasm" / f"{s}.asm.bp.p_ctg.fa.gz"
            tasks.append("HIFIASM_UL")
        else:                                              # scaffold: assemble each, join ONT onto HiFi
            a_ont, a_hifi = (assembler.split("_") + ["hifiasm"])[:2]
            c_ont, c_hifi = dg.breaks(g, 10 + i, READ["ont"][0], 2), dg.breaks(g, 20 + i, READ["hifi"][0], 1)
            for tool, cuts, sub in ((a_ont, c_ont, "ont"), (a_hifi, c_hifi, "hifi")):
                dg.write_fasta(res / "assembly" / tool / (f"{s}_{sub}.assembly.fa.gz" if tool == "flye" else f"{s}_{sub}.asm.bp.p_ctg.fa.gz"),
                               dg.contigs(g, cuts, _name(tool, s)))
            # Intent: a break survives scaffolding only where both assemblies break at the same place.
            both = {c: [p for p in c_hifi[c] if any(abs(p - q) < 2000 for q in c_ont[c])] for c in c_hifi}
            ctgs, err = dg.contigs(g, both, _name("ragtag", s)), READ["hifi"][2]
            out = res / "assembly" / "ragtag" / f"{s}_assembly_scaffold" / f"{s}_assembly_scaffold.fasta"
            tasks += [a_ont.upper(), a_hifi.upper(), "RAGTAG_SCAFFOLD"]
        dg.write_fasta(out, ctgs)
        stage_files = [("assembly", out, err)]
        for step in filter(None, (r.get("polish") or "").split("+")):
            err = min(err, POLISHED[step])
            p = res / "polish" / step / (f"{s}_{step}.fasta" if step == "pilon" else f"{s}_{step}.fa.gz")
            dg.write_fasta(p, ctgs)
            stage_files.append((step, p, err))
            tasks.append(step.upper())
        for stage, path, e in stage_files:
            if nfp.get("busco"):
                dg.write_busco(res / "QC" / "BUSCO" / f"short_summary.specific.{lineage}.{s}_{stage}.json", dg.busco(g, ctgs, e, 100 + i), lineage)
        if lift:
            stage, path, _ = stage_files[-1]
            genes, unmapped = dg.lift(g, ctgs)
            base = path.parent if stage != "assembly" else res / "assembly"
            dg.write_gff(base / f"{s}_{stage}.gff3", genes, "Liftoff")
            (base / f"{s}_{stage}.unmapped.txt").write_text("".join(u + "\n" for u in unmapped))
            tasks.append("LIFTOFF")
        tasks += ["BUSCO", "QUAST"] if nfp.get("busco") else []
        for t in tasks:
            k += 1
            with open(trace, "a") as fh:
                fh.write(f"{k}\tab/{k:06x}\t{1000 + k}\tNFCORE_GENOMEASSEMBLER:GENOMEASSEMBLER:{t} ({s})\tCOMPLETED\t0\n")
            print(f"[demo] {t} ({s})", flush=True)
        time.sleep(pause / max(1, len(rows)))
    (run / "results" / "report").mkdir(parents=True, exist_ok=True)
    (run / "results" / "report" / "report.html").write_text("<!doctype html><title>genomeassembler report (demo)</title><body style='font-family:sans-serif'>"
                                                            "<h1>Assembly report (demo)</h1><p>On a real cluster this is nf-core/genomeassembler's report.</p></body>")
    (run / "demo_truth.json").write_text(json.dumps({"chromosomes": g["lengths"], "genes": len(g["genes"])}))
    print("[demo] pipeline finished", flush=True)


if __name__ == "__main__":
    main()
