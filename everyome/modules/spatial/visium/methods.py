"""Draft methods section for a Visium run, written from its record. The user edits it before use."""
from __future__ import annotations

from everyome.modules.singlecell.writeup import _last, _v, session_paragraphs


def methods(rec: dict) -> str:
    sw, hist = rec["software"], (rec.get("session") or {}).get("history", [])
    rows = next((x["value"] for x in rec["inputs"] if x["id"] == "samples"), []) or []
    conds = sorted({r.get("condition") for r in rows if r.get("condition")})
    P = [f"Spatial transcriptomics data from {len(rows)} 10x Genomics Visium section{'s' if len(rows) != 1 else ''}"
         + (f" ({', '.join(conds)})" if conds else "") + ", processed with Space Ranger, were analysed with the Visium module "
         f"(version {rec['module']['version']}) of Everyome (version {rec['everyome']}) in Scanpy{_v(sw, 'scanpy', 'Wolf et al., 2018')}."]
    ld = _last(hist, "loaded Space Ranger output")
    if ld:
        P[0] += " " + "; ".join(f"{s['sample']}: {s['spots']:,} spots under the tissue" for s in ld["samples"]) + "."
    P[0] += " Each spot was treated as one observation."
    P += session_paragraphs(hist, sw)
    sv = _last(hist, "found spatially variable genes")
    if sv:
        P.append(f"Spatially variable genes were ranked by Moran's I (Moran, 1950), computed for the {sv['genes_tested']:,} most variable genes "
                 f"on each section's six nearest spots and averaged over sections weighted by spot number; the top genes were {', '.join(sv['top'][:5])}.")
    return "\n\n".join(P) + "\n"
