"""Draft methods section for a structure prediction run, written from its record. The user edits it before use."""
from __future__ import annotations

from everyome.core.writeup import last as _last

METHOD = {"alphafold2": "AlphaFold2 (Jumper et al., 2021)", "alphafold3": "AlphaFold 3 (Abramson et al., 2024)",
          "colabfold": "ColabFold (Mirdita et al., 2022)", "esmfold": "ESMFold (Lin et al., 2023)", "boltz": "Boltz",
          "rosettafold_all_atom": "RoseTTAFold All-Atom", "helixfold3": "HelixFold3", "rosettafold2na": "RoseTTAFold2NA"}




def methods(rec: dict) -> str:
    s = {x["id"]: x["value"] for x in rec["settings"]}
    hist = (rec.get("session") or {}).get("history", [])
    rows = next((x["value"] for x in rec["inputs"] if x["id"] == "proteins"), []) or []
    pipe, sw = rec.get("pipeline") or {}, rec["software"]
    nf = (sw.get("tools") or {}).get("nextflow")
    modes = [m for m in str(s.get("mode") or "alphafold2").split(",") if m]
    how = " and ".join(METHOD.get(m, m) for m in modes)
    detail = []
    if "alphafold2" in modes:
        detail.append(f"AlphaFold2 used the {s.get('alphafold2_model_preset')} model preset ({s.get('alphafold2_mode')} mode, "
                      f"{'full' if s.get('full_dbs') or s.get('alphafold2_full_dbs') else 'reduced'} databases, templates released up to {s.get('alphafold2_max_template_date')})")
    if "colabfold" in modes:
        detail.append(f"ColabFold used the {s.get('colabfold_model_preset')} model with {s.get('colabfold_num_recycles')} recycles"
                      + (" and multiple sequence alignments from the ColabFold MMseqs2 server" if s.get("use_msa_server") else ""))
    if "esmfold" in modes:
        detail.append(f"ESMFold used the {s.get('esmfold_model_preset')} model with {s.get('esmfold_num_recycles')} recycles")
    P = [f"Structures of {len(rows)} protein{'s' if len(rows) != 1 else ''} or complex{'es' if len(rows) != 1 else ''} were predicted with {how}, "
         f"run through {pipe.get('pipeline', 'nf-core/proteinfold')} version {pipe.get('revision', '')} (Ewels et al., 2020)"
         + (f" in Nextflow {nf.split()[-1]} (Di Tommaso et al., 2017)" if nf else " in Nextflow (Di Tommaso et al., 2017)")
         + f"{' on GPUs' if s.get('use_gpu') else ''}, through Everyome (version {rec['everyome']})."
         + (" " + "; ".join(detail) + "." if detail else "")]
    ld = _last(hist, "read the predicted structures")
    if ld:
        parts = []
        for p in ld["predictions"]:
            t = f"{p['id']} ({p['method']}): mean pLDDT {p['mean_plddt']:.1f}, {p['confident']:.0f}% of residues with pLDDT ≥ 70"
            if p.get("ptm") is not None:
                t += f", pTM {p['ptm']:.2f}"
            if p.get("iptm") is not None:
                t += f", ipTM {p['iptm']:.2f}"
            parts.append(t)
        P.append("Model confidence was assessed from the per-residue pLDDT and, where available, the predicted aligned error (PAE) and "
                 "pTM of the top-ranked model: " + "; ".join(parts) + ". Confidently placed domains were defined in Everyome as stretches "
                 "of at least five residues with pLDDT ≥ 70, joined where the mean PAE between them was below 5 Å (at least 20 residues in total).")
    ex = _last(hist, "exported structures")
    if ex:
        trim = (f"; residues with pLDDT below {ex['min_plddt']:g} were removed" if ex["min_plddt"] else "") + ("; only confident domains were kept" if ex["domains_only"] else "")
        P.append(f"The top-ranked models of " + ", ".join(f"{m['id']} ({m['method']}, {m['residues']} of {m['of']} residues)" for m in ex["models"])
                 + f" were exported{trim}.")
    return "\n\n".join(P) + "\n"
