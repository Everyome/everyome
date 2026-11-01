"""Draft methods section for a single-cell RNA-seq run, written from its record.

The pipeline paragraph comes from the settings; the rest from the live session's
decisions in order (shared with other single-cell modules). The user edits it.
"""
from __future__ import annotations

from ..writeup import _last, _v, session_paragraphs

ALIGNERS = {"simpleaf": "simpleaf (alevin-fry; He et al., 2022)", "star": "STARsolo", "kallisto": "kallisto | bustools",
            "cellranger": "Cell Ranger", "cellrangerarc": "Cell Ranger ARC", "cellrangermulti": "Cell Ranger multi"}
MATRICES = {"cellbender_filter": "after removing empty droplets and ambient RNA with CellBender (Fleming et al., 2023)",
            "filtered": "as filtered by the aligner", "raw": "including every barcode (no empty-droplet removal)"}


def methods(rec: dict) -> str:
    s = {x["id"]: x for x in rec["settings"]}
    val = lambda k, d=None: (s.get(k) or {}).get("value") or d
    samples = next((x["value"] for x in rec["inputs"] if x["id"] == "samples"), []) or []
    sw, hist = rec["software"], (rec.get("session") or {}).get("history", [])
    nf = (sw.get("tools") or {}).get("nextflow")
    nf_v = f" (Nextflow {nf.split()[-1]}; Di Tommaso et al., 2017)" if nf else " (Di Tommaso et al., 2017)"
    pipe = rec.get("pipeline") or {}
    names = sorted({r["sample"] for r in samples})
    conds = sorted({r.get("condition") for r in samples if r.get("condition")})
    genome = val("genome") or str(val("fasta", "")).split("/")[-1] or "the reference genome"
    aligner = val("aligner", "simpleaf")
    changed = [x for x in rec["settings"] if x["changed"] and x["id"] not in ("aligner", "genome", "fasta", "gtf", "protocol", "mito_genes")]
    P = [f"Single-cell RNA-seq libraries from {len(names)} samples" + (f" ({', '.join(conds)})" if conds else "")
         + f" were processed with {pipe.get('pipeline', 'nf-core/scrnaseq')} version {pipe.get('revision', '')} (Peltzer et al.; Ewels et al., 2020)"
         + f"{nf_v}, run through Everyome (version {rec['everyome']}). Reads were quantified against {genome} with "
         + f"{ALIGNERS.get(aligner, aligner)} for the {val('protocol', 'auto')} chemistry."
         + (" Pipeline settings changed from their defaults: " + "; ".join(f"{x['id']} = {x['value']}" for x in changed) + "." if changed
            else " All other pipeline settings were left at their defaults.")]
    ld = _last(hist, "loaded the matrix")
    if ld:
        mito = f" Mitochondrial genes were those whose names match '{val('mito_genes')}'." if val("mito_genes") else ""
        P.append(f"The combined cell-by-gene matrix {MATRICES.get(ld['kind'], '')} ({ld['cells']:,} barcodes, {ld['genes']:,} genes) was "
                 f"analysed in Scanpy{_v(sw, 'scanpy', 'Wolf et al., 2018')}" + (", with genes named by their symbols" if ld.get("symbols") else "")
                 + "." + mito)
    P += session_paragraphs(hist, sw)
    return "\n\n".join(P) + "\n"
