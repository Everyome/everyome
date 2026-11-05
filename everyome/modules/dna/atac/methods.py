"""Draft methods section for an ATAC-seq run, written from its record. The user edits it before use."""
from __future__ import annotations

from everyome.core.writeup import changed_settings, last, nextflow_cite, pipeline_name, setting, table


def methods(rec: dict) -> str:
    rows = table(rec, "libraries")
    hist = (rec.get("session") or {}).get("history", [])
    libs = {(r.get("group"), str(r.get("replicate"))) for r in rows}
    groups = sorted({g for g, _ in libs})
    pipe, rev = pipeline_name(rec, "nf-core/atacseq")
    aligner = {"bwa": "BWA-MEM (Li and Durbin, 2009)", "bowtie2": "Bowtie 2", "chromap": "Chromap", "star": "STAR"}.get(
        setting(rec, "aligner", "bwa"), setting(rec, "aligner", "bwa"))
    genome = setting(rec, "genome") or str(setting(rec, "fasta", "") or "").split("/")[-1] or "the reference genome"
    # Intent: read the value itself; False is a real choice here (broad peaks), not a missing setting.
    narrow = next((x["value"] for x in rec["settings"] if x["id"] == "narrow_peak"), True)
    gsize = setting(rec, "macs_gsize")
    other = changed_settings(rec, exclude=("fasta", "gtf", "gff", "genome", "macs_gsize", "aligner", "narrow_peak"),
                             lead="Pipeline settings changed from their defaults: ")
    P = [f"ATAC-seq libraries ({len(libs)} libraries from {len(groups)} groups: {', '.join(groups)}) were processed with {pipe} "
         f"version {rev} (Patel et al.; Ewels et al., 2020){nextflow_cite(rec)}, run through Everyome (version {rec['everyome']}). "
         f"Reads were trimmed with Trim Galore and aligned to {genome} with {aligner}; libraries were merged, duplicates were "
         "marked with Picard, and duplicate, multi-mapping, unpaired and mitochondrial reads were removed. Peaks were called in "
         f"each library with MACS2 (Zhang et al., 2008) in {'narrow' if narrow else 'broad'}-peak mode"
         + (f" with an effective genome size of {float(gsize):,.0f} bp" if gsize else "")
         + ", the peaks of all libraries were merged into one consensus set, and reads in each consensus peak were counted with "
           "featureCounts (Liao et al., 2014)."
         + (" " + other if other else " All other pipeline settings were left at their defaults.")]
    P.append("Libraries were compared on consensus-peak counts normalised for library size (DESeq2's median-of-ratios size "
             "factors; Love et al., 2014) and log-scaled, using principal components of the most variable peaks and Pearson "
             "correlation between libraries. Each consensus peak was assigned the nearest gene by distance from the peak centre "
             "to the gene's transcription start site in the run's annotation.")
    da = last(hist, "compared groups")
    if da:
        P.append(f"Consensus peaks with fewer than {da['min_count']} reads in total across the compared libraries were removed, "
                 f"leaving {da['peaks_tested']:,} peaks. Differential accessibility between {da['test']} and {da['reference']} "
                 f"({len(da['libraries'])} libraries) was tested with DESeq2 as implemented in PyDESeq2 (version {da['pydeseq2']}; "
                 f"Muzellec et al., 2023), with the design ~ group and {da['reference']} as the reference level. P values were "
                 f"adjusted with the Benjamini–Hochberg method; {da['opening']:,} peaks were more accessible and {da['closing']:,} "
                 f"less accessible in {da['test']} at an adjusted P below {da['alpha']}.")
    ex = last(hist, "exported results")
    if ex and ex.get("lfc") and ex.get("significant") is not None:
        P.append(f"Peaks reported as changed also had an absolute log2 fold change of at least {ex['lfc']} ({ex['significant']:,} peaks).")
    return "\n\n".join(P) + "\n"
