"""Draft methods section for a variant-calling run, written from its record."""
from __future__ import annotations

from everyome.core.writeup import changed_settings, join_and, last, nextflow_cite, pipeline_name, setting, table

NAMES = {"haplotypecaller": "GATK HaplotypeCaller (McKenna et al., 2010)", "deepvariant": "DeepVariant (Poplin et al., 2018)",
         "freebayes": "FreeBayes (Garrison and Marth, 2012)", "strelka": "Strelka2", "mpileup": "bcftools mpileup (Danecek et al., 2021)",
         "bcftools": "bcftools mpileup (Danecek et al., 2021)"}
SHORT = {"haplotypecaller": "HaplotypeCaller", "deepvariant": "DeepVariant", "freebayes": "FreeBayes", "strelka": "Strelka2",
         "mpileup": "bcftools", "bcftools": "bcftools"}


def methods(rec: dict) -> str:
    rows, hist = table(rec, "samples"), (rec.get("session") or {}).get("history", [])
    samples = list(dict.fromkeys(r["sample"] for r in rows))
    groups = sorted({r.get("group") for r in rows if r.get("group")})
    pipe, rev = pipeline_name(rec, "nf-core/sarek")
    tools = [t for t in str(setting(rec, "tools", "") or "").split(",") if t]
    callers = [t for t in tools if t in NAMES]
    skip = str(setting(rec, "skip_tools", "") or "")
    genome = str(setting(rec, "fasta", "") or "").split("/")[-1] or "the reference genome"
    aligner = str(setting(rec, "aligner", "bwa-mem") or "bwa-mem")
    P = [f"DNA sequencing reads from {len(samples)} samples" + (f" ({join_and(groups)})" if groups else "")
         + f" were processed with {pipe} version {rev} (Garcia et al., 2020; Hanssen et al., 2024; Ewels et al., 2020)"
         + f"{nextflow_cite(rec)}, run through Everyome (version {rec['everyome']}). Reads were aligned to {genome} with "
         + ("BWA-MEM (Li, 2013)" if aligner == "bwa-mem" else aligner) + ", duplicate reads were marked, coverage was measured with "
         + "mosdepth (Pedersen and Quinlan, 2018), and germline variants were called in each sample with "
         + (join_and([NAMES[c] for c in callers]) if callers else "the pipeline's default caller") + "."
         + (" Base quality score recalibration was not run, as no set of known variant sites was used." if "baserecalibrator" in skip else "")
         + (" " + changed_settings(rec, exclude=("tools", "skip_tools", "fasta", "aligner")) if changed_settings(rec, exclude=("tools", "skip_tools", "fasta", "aligner")) else "")]
    f = last(hist, "filtered variants")
    if f:
        read = last(hist, "read the variant calls") or {}
        chosen = f["callers"] or read.get("callers") or callers
        names = join_and([SHORT.get(c, c) for c in chosen]) if chosen else "the callers"
        n = len(chosen)
        agree = "by" if n == 1 else "by both" if f["agree"] == n == 2 else "by all of" if f["agree"] == n else f"by at least {f['agree']} of"
        P.append(f"Calls were filtered in Everyome. A variant was kept when it was called {agree} {names} in at least one sample with a "
                 f"variant quality (QUAL) of at least {f['min_qual']:g}, a read depth of at least {f['min_dp']} and a genotype quality of "
                 f"at least {f['min_gq']}" + (", and passed the caller's own filters" if f["pass_only"] else "")
                 + {"snv": "; only single-nucleotide variants were kept", "indel": "; only insertions and deletions were kept"}.get(f["vtype"], "")
                 + (f"; only variants in {f['region']} were kept" if f["region"] else "")
                 + f". {f['kept']:,} of {f['total']:,} candidate variants remained ({f['snv']:,} single-nucleotide variants and {f['indel']:,} "
                 f"insertions or deletions" + (f"; transition/transversion ratio {f['titv']}" if f.get("titv") else "") + "). Each sample's "
                 "genotype was taken from the first of these callers that called the variant in that sample and passed the filters.")
    g = last(hist, "compared groups")
    if g:
        P.append(f"Variants separating {g['a']} ({join_and(g['samples_a'])}) from {g['b']} ({join_and(g['samples_b'])}) were those carried "
                 f"by every sample of one group and called in no sample of the other: {g['separating']:,} variants "
                 f"({g['carried_by_a']:,} carried by {g['a']}, {g['carried_by_b']:,} by {g['b']}).")
    ex = last(hist, "exported variants")
    if ex:
        P.append(f"The filtered variants ({ex['variants']:,}) were exported as a VCF file and a table.")
    return "\n\n".join(P) + "\n"
