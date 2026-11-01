"""Shared methods text for single-cell modules: filtering, clustering, markers, naming and comparison.

Written from the live session's decisions in order (cells.py records them); each
module writes its own opening paragraphs (how reads became a matrix) and adds these.
Kept free of heavy imports, because records are written in the app.
"""
from __future__ import annotations


def _last(history, prefix):
    hits = [h for h in history if h["action"].startswith(prefix)]
    return hits[-1] if hits else None


def _v(sw, name, cite=""):
    """ (version X; Author, year), or just the citation, or nothing."""
    v = sw.get("python", {}).get(name) or sw.get("tools", {}).get(name)
    if v:
        # Intent: tools often print their own name first ("samtools 1.21"); keep only the version.
        v = v.split()[-1] if v.lower().startswith(name.lower()) else v
    parts = [f"version {v}" if v else "", cite]
    inside = "; ".join(p for p in parts if p)
    return f" ({inside})" if inside else ""


def _and(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def session_paragraphs(hist: list, sw: dict) -> list[str]:
    P = []
    flt = _last(hist, "filtered cells")
    if flt:
        mito = f", or more than {flt['max_mito']:g}% of UMIs from mitochondrial genes" if flt.get("max_mito") is not None else ""
        P.append(f"Cells with fewer than {flt['min_counts']:,} or at least {flt['max_counts']:,} UMIs, or fewer than {flt['min_genes']:,} or "
                 f"at least {flt['max_genes']:,} detected genes{mito}, were removed, leaving {flt['cells_after']:,} of {flt['cells_before']:,} cells.")
    cl = _last(hist, "clustered")
    if cl:
        batch = (f" Differences between batches (the {cl['batch_key']} label) were corrected with Harmony{_v(sw, 'harmonypy', 'Korsunsky et al., 2019')}."
                 if cl.get("harmony") and cl.get("batch_mixing") is not None else "")
        P.append(f"Counts were normalised to 10,000 per cell and log-transformed, and the {int(cl['n_top_genes']):,} most variable genes were "
                 f"scaled and reduced by principal component analysis.{batch} A neighbour graph ({cl['n_neighbors']} neighbours, "
                 f"{cl['n_pcs']} components) was used for UMAP (minimum distance {cl['min_dist']}) and Leiden clustering"
                 f"{_v(sw, 'leidenalg', 'Traag et al., 2019')} at resolution {cl['resolution']}, giving {cl['clusters']} clusters. "
                 f"Marker genes were ranked with the Wilcoxon rank-sum test; genes with Benjamini–Hochberg adjusted P < 0.05 and "
                 f"positive log fold change were considered markers.")
    names = {}
    for h in hist:
        if h["action"] == "named a cluster" and h.get("name"):
            names[h["cluster"]] = h["name"]
    if names:
        k, n = len(set(names.values())), len(names)
        P.append(f"Clusters were named from their marker genes ({n} cluster{'s' if n > 1 else ''} named, as {k} cell type{'s' if k > 1 else ''}).")
    exp = _last(hist, "exported results")
    if exp and exp.get("compared_by"):
        P.append(f"Cell-type proportions were compared descriptively by {exp['compared_by']}.")
    return P
