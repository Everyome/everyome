"""Draft methods section for a multiome run, written from its record. The user edits it before use."""
from __future__ import annotations

from everyome.core.writeup import last, table, version

HOW = {"joint": "on both measurements together, using weighted nearest neighbours (Hao et al., 2021) as implemented in muon",
       "rna": "on the RNA only", "atac": "on the open chromatin only"}


def methods(rec: dict) -> str:
    rows = table(rec, "samples")
    sw, hist = rec["software"], (rec.get("session") or {}).get("history", [])
    conds = sorted({r.get("condition") for r in rows if r.get("condition")})
    P = [f"Single-cell multiome libraries (gene expression and chromatin accessibility from the same nuclei) from {len(rows)} samples"
         + (f" ({', '.join(conds)})" if conds else "")
         + f" were processed with Cell Ranger ARC and analysed with Everyome (version {rec['everyome']})."]
    ld = last(hist, "read the multiome matrices")
    if ld:
        P.append(f"Each sample's filtered gene and peak matrices were read; cells with fewer than {ld['min_atac']:,} ATAC counts in "
                 f"peaks were left out, leaving {ld['cells']:,} cells, {ld['genes']:,} genes and {ld['peaks']:,} peaks.")
    flt = last(hist, "filtered cells")
    if flt:
        mito = f", or more than {flt['max_mito']:g}% of UMIs from mitochondrial genes" if flt.get("max_mito") is not None else ""
        P.append(f"Cells with fewer than {flt['min_counts']:,} or at least {flt['max_counts']:,} RNA UMIs, or fewer than "
                 f"{flt['min_genes']:,} or at least {flt['max_genes']:,} detected genes{mito}, were removed, leaving "
                 f"{flt['cells_after']:,} of {flt['cells_before']:,} cells.")
    cl = last(hist, "clustered")
    if cl:
        mode = cl.get("mode", "joint")
        parts = []
        if mode in ("rna", "joint"):
            parts.append(f"RNA counts were normalised to 10,000 per cell and log-transformed, and the {int(cl['n_top_genes']):,} most "
                         f"variable genes were scaled and reduced to {cl['n_pcs']} principal components")
        if mode in ("atac", "joint"):
            parts.append(f"peak counts were transformed by TF-IDF and reduced by latent semantic indexing (Cusanovich et al., 2015) to "
                         f"{cl['n_pcs']} components, leaving out the first, which follows sequencing depth")
        batch = (f" Batches (the {cl['batch_key']} label) were corrected with Harmony (Korsunsky et al., 2019)."
                 if cl.get("harmony") and cl.get("batch_mixing") is not None else "")
        weight = (f" On average, cells weighted their RNA at {cl['rna_weight']:.2f} and their chromatin at {1 - cl['rna_weight']:.2f}."
                  if cl.get("rna_weight") is not None else "")
        text = "; ".join(parts)
        P.append(text[:1].upper() + text[1:] + "." + batch + f" Cells were clustered {HOW[mode]}{version(sw, 'muon', 'Bredikhin et al., 2022') if mode == 'joint' else ''}: "
                 f"a {cl['n_neighbors']}-nearest-neighbour graph, Leiden clustering (Traag et al., 2019) at resolution {cl['resolution']} "
                 f"({cl['clusters']} clusters) and UMAP (minimum distance {cl['min_dist']}).{weight} Marker genes were ranked on the RNA "
                 f"with the Wilcoxon rank-sum test in Scanpy{version(sw, 'scanpy', 'Wolf et al., 2018')}.")
    names = {h["cluster"]: h["name"] for h in hist if h["action"] == "named a cluster" and h.get("name")}
    if names:
        k, n = len(set(names.values())), len(names)
        P.append(f"Clusters were named from their marker genes ({n} cluster{'s' if n > 1 else ''} named, as {k} cell type{'s' if k > 1 else ''}).")
    exp = last(hist, "exported results")
    if exp and exp.get("compared_by"):
        P.append(f"Cell-type proportions were compared descriptively by {exp['compared_by']}.")
    return "\n\n".join(P) + "\n"
