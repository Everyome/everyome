"""Draft methods section for a genome assembly run, written from its record. The user edits it before use."""
from __future__ import annotations

from everyome.core.writeup import nextflow_cite

from ..writeup import assembly_paragraphs

STRATEGY = {"single": "a single read type", "hybrid": "Nanopore and HiFi reads together (hifiasm in ultra-long mode)",
            "scaffold": "Nanopore and HiFi reads assembled separately, one scaffolded onto the other with RagTag (Alonge et al., 2022)"}
ASSEMBLER = {"flye": "Flye (Kolmogorov et al., 2019)", "hifiasm": "hifiasm (Cheng et al., 2021)"}


def methods(rec: dict) -> str:
    s = {x["id"]: x for x in rec["settings"]}
    val = lambda k, d=None: (s.get(k) or {}).get("value") or d
    rows = next((x["value"] for x in rec["inputs"] if x["id"] == "assemblies"), []) or []
    pipe, sw = rec.get("pipeline") or {}, rec["software"]
    nf_v = nextflow_cite(rec)
    P = [f"Genomes were assembled with {pipe.get('pipeline', 'nf-core/genomeassembler')} version {pipe.get('revision', '')} (Ewels et al., 2020){nf_v}, "
         f"run through Everyome (version {rec['everyome']}). {len(rows)} assembl{'y was' if len(rows) == 1 else 'ies were'} made:"]
    for r in rows:
        reads = " and ".join(x for x, k in (("Oxford Nanopore", "ontreads"), ("PacBio HiFi", "hifireads"), ("Illumina", "short_1")) if r.get(k))
        names = " and ".join(ASSEMBLER.get(a, a) for a in r["assembler"].split("_"))
        pol = r.get("polish") or ""
        polish = (" and polished with " + " followed by ".join({"medaka": "Medaka", "pilon": "Pilon (Walker et al., 2014) using the Illumina reads",
                                                                "dorado": "Dorado"}[p] for p in pol.split("+"))) if pol else ""
        P[0] += f" {r['sample']} from {reads} reads, using {STRATEGY.get(r['strategy'], r['strategy'])} with {names}{polish};"
    P[0] = P[0].rstrip(";") + "."
    qc = [x for x, k in (("BUSCO (Manni et al., 2021)", "busco"), ("QUAST (Gurevich et al., 2013)", "quast"), ("Merqury", "merqury")) if val(k)]
    if qc:
        lineage = val("busco_lineage", "auto_euk")
        P.append("Assemblies were assessed with " + ", ".join(qc) + (f" (BUSCO lineage {lineage})" if val("busco") else "") + ".")
    if val("lift_annotations"):
        ref = str(val("ref_gff", "")).split("/")[-1] or "a related genome"
        P.append(f"Gene models were transferred from {ref} with Liftoff (Shumate and Salzberg, 2021).")
    changed = [x for x in rec["settings"] if x["changed"] and x["id"] not in ("busco", "quast", "lift_annotations", "ref_fasta", "ref_gff", "busco_lineage")]
    if changed:
        P.append("Other pipeline settings changed from their defaults: " + "; ".join(f"{x['id']} = {x['value']}" for x in changed) + ".")
    P += assembly_paragraphs((rec.get("session") or {}).get("history", []))
    return "\n\n".join(P) + "\n"
