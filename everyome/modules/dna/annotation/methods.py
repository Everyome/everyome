"""Draft methods section for a genome annotation run, written from its record. The user edits it before use."""
from __future__ import annotations

from everyome.core.writeup import last, setting


def _v(rec: dict, name: str) -> str:
    c = next((x for x in rec.get("containers") or [] if x["name"] == name), None)
    if not c:
        return ""
    tag = c["image"].split(":")[1]
    return " " + (tag.split("_")[1].lstrip("v") if name == "helixer" and "_" in tag else tag.split("--")[0])


def methods(rec: dict) -> str:
    hist = (rec.get("session") or {}).get("history", [])
    lineage = setting(rec, "lineage", "invertebrate")
    bl = setting(rec, "busco_lineage", "")
    P = [f"Gene models were predicted from the genome sequence with Helixer{_v(rec, 'helixer')} (Stiehler et al., 2021; Holst et al., "
         f"2023) using its {lineage} lineage model on a GPU, run through Everyome (version {rec['everyome']}). Protein sequences were "
         f"extracted with gffread{_v(rec, 'gffread')} (Pertea and Pertea, 2020)"
         + (f", and their completeness assessed with BUSCO{_v(rec, 'busco')} (Manni et al., 2021) in protein mode against the {bl} "
            "lineage dataset." if bl else ".")]
    ov = last(hist, "read the gene models")
    if ov:
        P.append(f"The annotation contains {ov['genes']:,} genes ({ov['transcripts']:,} transcripts), with a median of {ov['median_exons']:g} "
                 f"exons per gene, a median gene length of {ov['median_gene_length']:,} bp and a median protein length of "
                 f"{ov['median_protein_length']:,} amino acids" + (f"; BUSCO: {ov['busco']}." if ov.get("busco") else "."))
    return "\n\n".join(P) + "\n"
