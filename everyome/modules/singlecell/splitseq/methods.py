"""Draft methods section for a SPLiT-seq (SPLiTscape) run, written from its record.

Uses the settings, software versions and the live-session decisions in order;
anything not done (for example, no atlas, or no clustering yet) is left out.
The user edits the draft before using it.
"""
from __future__ import annotations

import os

from ..writeup import _and, _last, _v, session_paragraphs


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
    P += session_paragraphs(hist, sw)
    return "\n\n".join(P) + "\n"
