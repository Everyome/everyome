"""Draft methods section for a high-resolution spatial run, written from its record. The user edits it before use."""
from __future__ import annotations

from everyome.core.writeup import join_and, last

from ...singlecell.writeup import session_paragraphs

PLATFORM = {"visium_hd": "10x Genomics Visium HD", "stereo": "STOmics Stereo-seq", "curio": "Curio Seeker"}


def methods(rec: dict) -> str:
    sw, hist = rec["software"], (rec.get("session") or {}).get("history", [])
    ld = last(hist, "loaded high-resolution spatial output")
    P = []
    if ld:
        s, b = ld["samples"], ld["bin_um"]
        plats = join_and(sorted({PLATFORM.get(x["platform"], x["platform"]) for x in s}))
        how = {"visium_hd": f"Space Ranger's {b}-µm bins", "stereo": f"DNB spots summed into {b}-µm square bins",
               "curio": "beads as given"}
        used = join_and(sorted({how[x["platform"]] for x in s}))
        P.append(f"{len(s)} tissue section{'s' if len(s) > 1 else ''} profiled with {plats} were analysed with Everyome "
                 f"(version {rec['everyome']}), using {used} ({sum(x['bins'] for x in s):,} in total). Each bin was treated as one observation.")
    P += [p.replace(" cells", " bins").replace("cells ", "bins ") for p in session_paragraphs(hist, sw)]
    sv = last(hist, "found spatially variable genes")
    if sv:
        P.append(f"Spatially variable genes were ranked by Moran's I (Moran, 1950) on each section's six nearest bins, across "
                 f"{sv['genes_tested']:,} candidate genes.")
    nh = last(hist, "compared neighbourhoods")
    if nh:
        P.append(f"Neighbourhood enrichment between {'named types' if nh['by'] == 'annotation' else 'clusters'} was computed on each "
                 f"bin's {nh['k']} nearest neighbours, against {nh['permutations']} random permutations of the labels within each "
                 "section (as in Squidpy; Palla et al., 2022).")
    return "\n\n".join(P) + "\n"
