"""Draft methods section for a Ribo-seq run, written from its record. The user edits it before use."""
from __future__ import annotations

from everyome.core.writeup import changed_settings, last, nextflow_cite, pipeline_name, setting, table, version

from .helpers import contrasts


def methods(rec: dict) -> str:
    rows = table(rec, "samples")
    hist = (rec.get("session") or {}).get("history", [])
    pipe, rev = pipeline_name(rec, "nf-core/riboseq")
    n = {t: sum(1 for r in rows if r.get("type") == t) for t in ("riboseq", "rnaseq", "tiseq")}
    conds = sorted({r.get("condition") for r in rows if r.get("condition")})
    genome = setting(rec, "genome") or str(setting(rec, "fasta", "") or "").split("/")[-1] or "the reference genome"
    libs = f"{n['riboseq']} Ribo-seq and {n['rnaseq']} matched RNA-seq libraries" + (f" and {n['tiseq']} TI-seq libraries" if n["tiseq"] else "")
    # Intent: with no contrasts file given, Everyome wrote one from the samples table (each condition against the first).
    made = [line.split(",") for line in contrasts({"samples": rows}).splitlines()[1:]]
    P = [f"Ribosome profiling data ({libs}; conditions {', '.join(conds)}) were processed with {pipe} version {rev} "
         f"(Manning et al.; Ewels et al., 2020){nextflow_cite(rec)}, run through Everyome (version {rec['everyome']}), against {genome}. "
         "Reads were trimmed, ribosomal RNA reads removed, and reads aligned with STAR (Dobin et al., 2013); P-site offsets for each "
         "footprint length were determined with riboWaltz (Lauria et al., 2018) and Plastid (Dunn and Weissman, 2016), translated "
         "open reading frames were predicted with Ribo-TISH (Zhang et al., 2017) and RiboCode (Xiao et al., 2018) and merged into one "
         "catalogue, and genes were quantified as in-frame P-sites (Ribo-seq) and reads (RNA-seq)."
         + (" Translational efficiency was also tested by the pipeline with anota2seq (Oertlin et al., 2019) for the contrasts "
            "in the supplied contrasts file." if setting(rec, "contrasts") else
            f" Translational efficiency was also tested by the pipeline with anota2seq (Oertlin et al., 2019), comparing "
            f"{', '.join(c[3] for c in made)} with {made[0][2]}, with each Ribo-seq library paired with its RNA-seq library." if made else "")
         + (" " + changed_settings(rec, exclude=("genome", "fasta", "gtf", "contrasts")) if changed_settings(rec, exclude=("genome", "fasta", "gtf", "contrasts")) else "")]
    p = last(hist, "checked periodicity")
    if p and p.get("frame0"):
        f = [v * 100 for v in p["frame0"].values()]
        P.append(f"Three-nucleotide periodicity was checked in Everyome from riboWaltz's P-site positions: in coding sequences, "
                 f"{min(f):.0f}–{max(f):.0f}% of P-sites fell in the annotated reading frame (frame 0) across the {len(f)} libraries.")
    o = last(hist, "read the ORF predictions")
    if o:
        cl = o.get("classes", {})
        P.append(f"The ORF predictions ({o['source']}) held {o['orfs']:,} ORFs: "
                 + ", ".join(f"{v:,} {k.replace('canonical_cds', 'annotated coding sequences')}" for k, v in sorted(cl.items(), key=lambda kv: -kv[1])) + ".")
    te = last(hist, "compared translational efficiency")
    if te:
        sw = rec.get("software") or {}
        P.append(f"Translational efficiency (TE) between {te['test']} and {te['reference']} ({len(te['pairs'])} Ribo-seq/RNA-seq pairs) was "
                 f"compared in Everyome. Genes with a mean of at least {te['min_count']:g} in-frame P-sites and {te['min_count']:g} RNA-seq "
                 f"reads were kept ({te['genes_tested']:,} genes). Ribo-seq and RNA-seq counts were normalised separately with "
                 "median-of-ratios size factors (Love et al., 2014), and log2 TE was computed within each pair as the difference of "
                 "log2(normalised count + 1). RNA-seq, Ribo-seq and TE changes were each tested with a moderated t-test, each gene's "
                 f"variance shrunk towards the median gene variance with {te['prior_df']:g} prior degrees of freedom (after Smyth, 2004)"
                 f"{version(sw, 'scipy')}, and P values adjusted with the Benjamini–Hochberg method. At an adjusted P below {te['alpha']}, "
                 f"TE was higher in {te['test']} for {te['up']:,} genes and lower for {te['down']:,}; genes whose TE change offset an mRNA "
                 "change were classed as buffered, and genes whose mRNA and footprints changed together as changing in mRNA abundance.")
        a = te.get("anota2seq")
        if a:
            P.append(f"anota2seq's translation analysis for the same contrast called {a['significant']:,} genes, {a['both']:,} of them also "
                     "called here.")
    return "\n\n".join(P) + "\n"
