"""Draft methods section for a bacterial assembly run, written from its record. The user edits it before use."""
from __future__ import annotations

from everyome.core.writeup import nextflow_cite

from ..writeup import assembly_paragraphs

ASM = {"unicycler": "Unicycler (Wick et al., 2017)", "flye": "Flye (Kolmogorov et al., 2019)", "megahit": "MEGAHIT", "canu": "Canu",
       "raven": "Raven", "miniasm": "Miniasm and Racon", "dragonflye": "Dragonflye", "autocycler": "Autocycler"}
KIND = {"short": "Illumina reads", "long": "long reads", "hybrid": "Illumina and long reads together (hybrid assembly)"}
ANN = {"prokka": "Prokka (Seemann, 2014)", "bakta": "Bakta (Schwengers et al., 2021)", "dfast": "DFAST", "liftoff": "Liftoff"}


def methods(rec: dict) -> str:
    s = {x["id"]: x for x in rec["settings"]}
    val = lambda k, d=None: (s.get(k) or {}).get("value") if (s.get(k) or {}).get("value") not in (None, "") else d
    rows = next((x["value"] for x in rec["inputs"] if x["id"] == "isolates"), []) or []
    pipe, sw = rec.get("pipeline") or {}, rec["software"]
    nf_v = nextflow_cite(rec)
    asms = [a.strip() for a in str(val("assembler", "unicycler")).split(",") if a.strip()]
    kind = val("assembly_type", "hybrid")
    P = [f"Genomes of {len(rows)} isolate{'s' if len(rows) != 1 else ''} ({', '.join(r['sample'] for r in rows)}) were assembled from {KIND.get(kind, kind)} "
         f"with {pipe.get('pipeline', 'nf-core/bacass')} version {pipe.get('revision', '')} (Ewels et al., 2020){nf_v}, run through Everyome "
         f"(version {rec['everyome']}), using " + " and ".join(ASM.get(a, a) for a in asms) + "."]
    if kind == "long" and not val("skip_polish"):
        P[0] += f" Long-read assemblies were polished with {'Medaka' if val('polish_method', 'medaka') == 'medaka' else 'Nanopolish'}."
    qc = [] if val("skip_busco") else [f"BUSCO (Manni et al., 2021; lineage {val('busco_lineage', 'bacteria_odb10')})"]
    P.append("Assemblies were assessed with QUAST (Gurevich et al., 2013)" + (" and " + qc[0] if qc else "") + "."
             + ("" if val("skip_annotation") else f" Genes were annotated with {ANN.get(val('annotation_tool', 'prokka'), val('annotation_tool', 'prokka'))}."))
    screens = [x for x, k in (("Kraken2", "skip_kraken2"), ("KmerFinder", "skip_kmerfinder")) if not val(k)]
    if screens:
        P.append("Reads were screened for contamination with " + " and ".join(screens) + ".")
    changed = [x for x in rec["settings"] if x["changed"] and x["id"] not in ("assembly_type", "assembler", "skip_kraken2", "skip_kmerfinder")]
    if changed:
        P.append("Other pipeline settings changed from their defaults: " + "; ".join(f"{x['id']} = {x['value']}" for x in changed) + ".")
    P += assembly_paragraphs((rec.get("session") or {}).get("history", []))
    return "\n\n".join(P) + "\n"
