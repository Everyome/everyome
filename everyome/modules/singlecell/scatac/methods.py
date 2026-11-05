"""Draft methods section for a single-cell ATAC-seq run, written from its record. The user edits it before use."""
from __future__ import annotations

from everyome.core.writeup import last, setting, table, version


def _chromap(rec: dict) -> str:
    c = next((x for x in rec.get("containers") or [] if x["name"] == "chromap"), None)
    return " " + c["image"].split(":")[1].split("--")[0] if c else ""


def methods(rec: dict) -> str:
    rows = table(rec, "samples")
    sw, hist = rec["software"], (rec.get("session") or {}).get("history", [])
    conds = sorted({r.get("condition") for r in rows if r.get("condition")})
    from_reads = [r for r in rows if not r.get("fragments")]
    genome = str(setting(rec, "genome", "")).split("/")[-1] or "the reference genome"
    P = [f"Single-cell ATAC-seq libraries from {len(rows)} samples" + (f" ({', '.join(conds)})" if conds else "")
         + f" were analysed with Everyome (version {rec['everyome']})."]
    if from_reads:
        wl = " against the kit's barcode whitelist" if setting(rec, "whitelist") else ""
        P[0] += (f" Reads were aligned to {genome} with Chromap{_chromap(rec)} (Zhang et al., 2021) using its ATAC-seq preset, "
                 f"which corrects cell barcodes{wl}, removes PCR duplicates and shifts reads for the Tn5 insertion, writing one "
                 "fragment per read pair.")
    if len(from_reads) < len(rows):
        P[0] += " For samples supplied as fragment files, those fragments were used as given."
    ld = last(hist, "read the fragments")
    if ld:
        P.append(f"Fragments were read with SnapATAC2{version(sw, 'snapatac2', 'Zhang et al., 2024')}; barcodes with at least "
                 f"{ld['min_fragments']:,} fragments were kept as cells ({ld['cells']:,} in total). For each cell, TSS enrichment was "
                 f"computed from the gene annotation, a tile matrix of {ld['bin_size']}-bp bins was built for clustering, and a gene "
                 "activity matrix (fragments over each gene body and 2 kb upstream) for markers.")
    flt = last(hist, "filtered cells")
    if flt:
        P.append(f"Cells with fewer than {flt['min_counts']:,} or at least {flt['max_counts']:,} fragments, or TSS enrichment below "
                 f"{flt['min_genes']} or at least {flt['max_genes']}, were removed, leaving {flt['cells_after']:,} of "
                 f"{flt['cells_before']:,} cells.")
    cl = last(hist, "clustered")
    if cl:
        batch = (f" Differences between batches (the {cl['batch_key']} label) were corrected with Harmony (Korsunsky et al., 2019) "
                 "on the spectral embedding." if cl.get("harmony") and cl.get("batch_mixing") is not None else "")
        P.append(f"The {int(cl['n_top_genes']) * 25:,} most variable tiles were used for a spectral embedding with "
                 f"{cl['n_pcs']} components (SnapATAC2).{batch} A {cl['n_neighbors']}-nearest-neighbour graph was used for "
                 f"Leiden clustering (Traag et al., 2019) at resolution {cl['resolution']}, giving {cl['clusters']} clusters, and "
                 f"for UMAP (minimum distance {cl['min_dist']}). Gene activity was normalised to 10,000 per cell and "
                 "log-transformed, and marker genes were ranked with the Wilcoxon rank-sum test in Scanpy"
                 f"{version(sw, 'scanpy', 'Wolf et al., 2018')}.")
    names = {h["cluster"]: h["name"] for h in hist if h["action"] == "named a cluster" and h.get("name")}
    if names:
        k, n = len(set(names.values())), len(names)
        P.append(f"Clusters were named from their marker genes' activity ({n} cluster{'s' if n > 1 else ''} named, as "
                 f"{k} cell type{'s' if k > 1 else ''}).")
    exp = last(hist, "exported results")
    if exp and exp.get("compared_by"):
        P.append(f"Cell-type proportions were compared descriptively by {exp['compared_by']}.")
    return "\n\n".join(P) + "\n"
