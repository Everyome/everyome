"""Draft methods section for a bulk RNA-seq run, written from its record."""
from __future__ import annotations


def _last(history, action):
    hits = [h for h in history if h["action"] == action]
    return hits[-1] if hits else None


def methods(rec: dict) -> str:
    s = {x["id"]: x for x in rec["settings"]}
    samples = next((x["value"] for x in rec["inputs"] if x["id"] == "samples"), []) or []
    sw, hist = rec["software"], (rec.get("session") or {}).get("history", [])
    nf = (sw.get("tools") or {}).get("nextflow")
    nf_v = f" (Nextflow {nf.split()[-1]}; Di Tommaso et al., 2017)" if nf else " (Di Tommaso et al., 2017)"
    aligner = (s.get("aligner") or {}).get("value") or "star_salmon"
    genome = (s.get("genome") or {}).get("value") or str((s.get("fasta") or {}).get("value") or "").split("/")[-1] or "the reference genome"
    changed = [x for x in rec["settings"] if x["changed"] and x["id"] not in ("aligner", "genome", "fasta", "gtf", "gff")]
    conds = sorted({r.get("condition") for r in samples if r.get("condition")})
    pipe = rec.get("pipeline") or {}
    P = [f"RNA-seq libraries from {len(samples)} samples ({', '.join(conds)}) were processed with {pipe.get('pipeline', 'nf-core/rnaseq')} "
         f"version {pipe.get('revision', '')} "
         f"(Patel et al.; Ewels et al., 2020){nf_v}, run through Everyome (version {rec['everyome']}), using the "
         f"{aligner.replace('_', ' and ').replace('star', 'STAR').replace('salmon', 'Salmon').replace('rsem', 'RSEM').replace('hisat2', 'HISAT2').replace('bowtie2', 'Bowtie 2')} "
         f"route against {genome}."
         + (" Pipeline settings changed from their defaults: " + "; ".join(f"{x['id']} = {x['value']}" for x in changed) + "." if changed else
            " All other pipeline settings were left at their defaults.")]
    de = _last(hist, "compared conditions")
    if de:
        P.append(f"Gene-level counts were rounded to whole numbers and genes with fewer than {de['min_count']} reads in total across the "
                 f"compared samples were removed, leaving {de['genes_tested']:,} genes. Differential expression between {de['test']} "
                 f"and {de['reference']} ({len(de['samples'])} samples) was tested with DESeq2 (Love et al., 2014) as implemented in "
                 f"PyDESeq2 (version {de['pydeseq2']}; Muzellec et al., 2023), with the design ~ condition and {de['reference']} as the "
                 f"reference level. P values were adjusted with the Benjamini–Hochberg method; {de['up']:,} genes were higher and "
                 f"{de['down']:,} lower in {de['test']} at an adjusted P below {de['alpha']}.")
    ex = _last(hist, "exported results")
    if ex and ex.get("lfc"):
        P.append(f"Genes reported as changed also had an absolute log2 fold change of at least {ex['lfc']} ({ex['significant']:,} genes).")
    return "\n\n".join(P) + "\n"
