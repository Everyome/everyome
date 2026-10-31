"""Draft methods section for a SPLiT-seq (SPLiTscape) run, written from its record.

Uses the settings, software versions and the live-session decisions in order;
anything not done (for example, no atlas, or no clustering yet) is left out.
The user edits the draft before using it.
"""
from __future__ import annotations

import os


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


def methods(rec: dict) -> str:
    s = {x["id"]: x["value"] for x in rec["settings"]}
    inp = {x["id"]: x["value"] for x in rec["inputs"]}
    sw, hist = rec["software"], (rec.get("session") or {}).get("history", [])
    n_sub = len(inp.get("sublibraries") or [])
    genome = os.path.basename(inp.get("ref_fasta") or "") or "the reference genome"
    P = []

    P.append(
        f"SPLiT-seq libraries (Rosenberg et al., 2018) were processed with SPLiTscape (Horkan, 2026) in Everyome "
        f"(version {rec['everyome']}; module version {rec['module']['version']}). "
        f"Raw read quality was checked with FastQC{_v(sw, 'fastqc')}. Adapters were trimmed with cutadapt{_v(sw, 'cutadapt')} "
        f"({s['r1_adapter']} from read 1, {s['r2_adapter']} from read 2); read 1 shorter than {s['r1_min_len']} nt and read 2 shorter "
        f"than {s['r2_min_len']} nt were discarded, and read 2 was truncated to {s['r2_truncate']} nt. Read 2 sequences were kept only "
        f"if they matched the barcode anchor pattern {s['dephase_regex']}, read pairs were restored with pairfq_lite, and pairs were "
        f"converted to unaligned BAM with Picard{_v(sw, 'picard')}. Cell barcodes and UMIs were extracted and reads aligned to {genome} "
        f"with STAR{_v(sw, 'STAR')} using the Split-seq toolbox (expected cells {int(s['expected_cells']):,}), sequencing runs were merged per "
        f"sublibrary with samtools{_v(sw, 'samtools')}, and digital expression matrices were built counting coding, UTR and "
        f"{str(s['locus_function_list']).lower()} reads; barcodes with fewer than {s['min_genes_per_cell']} detected genes were not "
        f"counted as cells.")

    comb = _last(hist, "combined sublibraries")
    if comb:
        if comb.get("with_atlas"):
            P.append(f"Count matrices from {n_sub} sublibraries ({comb['experiment_cells']:,} cells) were combined with an existing "
                     f"atlas ({comb['atlas_cells']:,} cells) on shared genes in Scanpy{_v(sw, 'scanpy', 'Wolf et al., 2018')}.")
        else:
            P.append(f"Count matrices from {n_sub} sublibraries ({comb['experiment_cells']:,} cells) were combined in "
                     f"Scanpy{_v(sw, 'scanpy', 'Wolf et al., 2018')} and analysed without a reference atlas.")
    lab = _last(hist, "labelled cells")
    if lab and lab.get("columns"):
        sheet = " Samples sharing a sublibrary were assigned from their round-1 barcode wells." if lab.get("barcode_sheets") else ""
        P.append(f"Each cell was labelled by {_and(lab['columns'])} from its library.{sheet}")
    flt = _last(hist, "filtered cells")
    if flt:
        P.append(f"Cells with fewer than {flt['min_counts']:,} or at least {flt['max_counts']:,} UMIs, or fewer than {flt['min_genes']:,} or "
                 f"at least {flt['max_genes']:,} detected genes, were removed, leaving {flt['cells_after']:,} of {flt['cells_before']:,} cells.")
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
    return "\n\n".join(P) + "\n"
