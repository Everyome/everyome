"""Draft methods section for an RNA abundance run, written from its record. The user edits it before use."""
from __future__ import annotations

from everyome.core.writeup import last, table


def methods(rec: dict) -> str:
    rows = table(rec, "samples")
    hist = (rec.get("session") or {}).get("history", [])
    groups = sorted({r.get("group") for r in rows if r.get("group")})
    P = [f"Gene-level abundances (transcripts per million, TPM) and counts for {len(rows)} samples"
         + (f" ({', '.join(groups)})" if groups else "")
         + " were taken from the merged gene tables written by nf-core/rnaseq (Patel et al.; Ewels et al., 2020) and explored "
           f"in Everyome (version {rec['everyome']})."]
    p = last(hist, "found expression patterns")
    norm = (p or {}).get("normalised", "log2 of size-factor-normalised counts")
    P.append(f"Samples were compared on {norm}"
             + (" (size factors by DESeq2's median-of-ratios method; Love et al., 2014)" if "size-factor" in norm else "")
             + ", using principal components of the 500 most variable genes and Pearson correlation between samples.")
    if p:
        P.append(f"Genes reaching at least {p['min_tpm']:g} TPM in one or more samples were ranked by variance, and the "
                 f"{p['n_genes']:,} most variable were scaled to z-scores across samples and grouped into {p['k']} clusters "
                 f"by k-means (k-means++ initialisation, fixed seed); cluster sizes were {', '.join(str(n) for n in p['sizes'])}.")
    return "\n\n".join(P) + "\n"
