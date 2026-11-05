"""Draft methods section for an interaction prediction run, written from its record. The user edits it before use."""
from __future__ import annotations

from everyome.core.writeup import last, nextflow_cite, pipeline_name, setting, table

from ..structure.methods import METHOD


def methods(rec: dict) -> str:
    rows = table(rec, "proteins")
    hist = (rec.get("session") or {}).get("history", [])
    name, rev = pipeline_name(rec, "nf-core/proteinfold")
    modes = [m for m in str(setting(rec, "mode", "alphafold2")).split(",") if m]
    how = " and ".join(METHOD.get(m, m) for m in modes)
    preset = setting(rec, "alphafold2_model_preset", "multimer") if "alphafold2" in modes else None
    P = [f"Structures of {len(rows)} protein complex{'es' if len(rows) != 1 else ''} were predicted with {how}"
         + (f" ({preset} model preset; Evans et al., 2022)" if preset else "")
         + f" using {name} version {rev} (Ewels et al., 2020){nextflow_cite(rec)}, run through Everyome (version {rec['everyome']})."]
    sc = last(hist, "scored interfaces")
    if sc:
        P.append("For each pair of chains, interface residues were those with Cα atoms within 8 Å of the other chain. We report "
                 "their number of contacts, mean pLDDT and mean predicted aligned error, the predictor's ipTM (chain-wise where "
                 "available), and pDockQ (Bryant et al., 2022), computed from the interface pLDDT and contact count with Cα in "
                 "place of Cβ atoms. Interfaces with pDockQ of at least 0.5 or ipTM of at least 0.8 were read as likely, those "
                 "with pDockQ below 0.23 and ipTM below 0.6 as unlikely, and the rest as uncertain.")
        lines = [f"{c['id']} ({c['method']}): " + "; ".join(f"chains {q['a']}–{q['b']}, {q['contacts']} contacts, pDockQ {q['pdockq']:.2f}"
                                                             + (f", ipTM {q['iptm']:.2f}" if q.get("iptm") is not None else "")
                                                             + f" ({q['verdict']})" for q in c["pairs"]) for c in sc["complexes"]]
        if lines:
            P.append("Results: " + " ".join(l + "." for l in lines))
    return "\n\n".join(P) + "\n"
