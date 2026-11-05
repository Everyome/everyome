"""Draft methods section for an imaging spatial run, written from its record. The user edits it before use."""
from __future__ import annotations

from everyome.core.writeup import join_and, last

from ...singlecell.writeup import session_paragraphs

PLATFORM = {"xenium": "10x Genomics Xenium", "merscope": "Vizgen MERSCOPE", "cosmx": "Bruker CosMx"}


def methods(rec: dict) -> str:
    sw, hist = rec["software"], (rec.get("session") or {}).get("history", [])
    ld = last(hist, "loaded imaging spatial output")
    P = []
    if ld:
        s = ld["samples"]
        plats = join_and(sorted({PLATFORM.get(x["platform"], x["platform"]) for x in s}))
        P.append(f"{len(s)} tissue section{'s' if len(s) > 1 else ''} imaged on {plats} ({sum(x['cells'] for x in s):,} segmented cells; "
                 f"{max(x['genes'] for x in s):,}-gene panel) were analysed with Everyome (version {rec['everyome']}). Cell-by-gene "
                 "counts and cell centroids were read from the instrument's output; control probes were excluded. Each segmented "
                 "cell was treated as one observation.")
    # Intent: filtering, clustering, markers and naming are written the same way as for single-cell RNA-seq, with
    # transcripts in place of UMIs.
    P += [p.replace("UMIs", "transcripts") for p in session_paragraphs(hist, sw)]
    sv = last(hist, "found spatially variable genes")
    if sv:
        P.append(f"Spatially variable genes were ranked by Moran's I (Moran, 1950) on each section's six nearest cells, "
                 f"across {sv['genes_tested']:,} candidate genes.")
    nh = last(hist, "compared neighbourhoods")
    if nh:
        P.append(f"Neighbourhood enrichment between {'named cell types' if nh['by'] == 'annotation' else 'clusters'} was computed "
                 f"on each cell's {nh['k']} nearest neighbours, as z-scores against {nh['permutations']} random permutations "
                 "of the labels within each section (as in Squidpy; Palla et al., 2022).")
    return "\n\n".join(P) + "\n"
