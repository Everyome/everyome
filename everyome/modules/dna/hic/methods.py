"""Draft methods section for a Hi-C run, written from its record."""
from __future__ import annotations

from statistics import median

from everyome.core.writeup import changed_settings, join_and, last, nextflow_cite, pipeline_name, setting, table

ENZYMES = {"hindiii": "HindIII", "dpnii": "DpnII", "mboi": "MboI", "arima": "the Arima two-enzyme mix (DpnII and HinfI)"}


def _kb(bp) -> str:
    return f"{bp / 1e6:g} Mb" if bp >= 1e6 else f"{bp / 1e3:g} kb"


def methods(rec: dict) -> str:
    hist = (rec.get("session") or {}).get("history", [])
    samples = list(dict.fromkeys(r["sample"] for r in table(rec, "samples")))
    pipe, rev = pipeline_name(rec, "nf-core/hic")
    genome = str(setting(rec, "fasta", "") or "").split("/")[-1] or "the genome"
    if setting(rec, "dnase"):
        lib = "DNase Hi-C (no restriction enzyme)"
    elif setting(rec, "digestion"):
        lib = f"{ENZYMES.get(setting(rec, 'digestion'), setting(rec, 'digestion'))} digestion"
    else:
        lib = f"digestion at {setting(rec, 'restriction_site', 'the given restriction site')}"
    other = changed_settings(rec, exclude=("fasta", "digestion", "restriction_site", "ligation_site", "dnase", "min_mapq", "keep_dups"))
    P = [f"Hi-C libraries from {len(samples)} sample{'s' if len(samples) != 1 else ''} ({', '.join(samples)}) were processed with "
         f"{pipe} version {rev} (Servant et al.; Ewels et al., 2020){nextflow_cite(rec)}, run through Everyome (version {rec['everyome']}). "
         f"Read pairs were aligned to {genome} with Bowtie 2 (Langmead and Salzberg, 2012) in HiC-Pro's two-step mode, keeping "
         f"alignments with a mapping quality of at least {setting(rec, 'min_mapq', 10)}; valid ligation products for {lib} were kept "
         f"and {'duplicates were kept' if setting(rec, 'keep_dups') else 'duplicate pairs removed'} (HiC-Pro; Servant et al., 2015). "
         f"Contact maps were built and balanced by iterative correction with cooler (Imakaev et al., 2012; Abdennur and Mirny, 2020)."
         + (" " + other if other else "")]
    ov = last(hist, "read the contact maps")
    if ov and any(ov["valid_pairs"].values()):
        v = [x for x in ov["valid_pairs"].values() if x]
        P.append(f"Libraries gave {min(v):,}" + (f" to {max(v):,}" if max(v) != min(v) else "") + " valid read pairs after duplicate removal.")
    dec = last(hist, "measured distance decay")
    if dec and any(x is not None for x in dec["slopes"].values()):
        sl = [x for x in dec["slopes"].values() if x is not None]
        P.append(f"Contact probability against genomic distance was measured on balanced {_kb(dec['res'])} maps; between "
                 f"{_kb(dec['range'][0])} and {_kb(dec['range'][1])} it fell with a log–log slope of {min(sl)}"
                 + (f" to {max(sl)}" if max(sl) != min(sl) else "") + ".")
    comp = last(hist, "called compartments")
    if comp:
        where = ("computed by the pipeline with cooltools eigs-cis" if comp["source"] == "pipeline"
                 else "computed in the session in the same way as cooltools eigs-cis")
        sign = (" Its sign was set on each chromosome so that positive values (A compartment) go with higher GC content of the genome."
                if comp["oriented"] == "gc" else " Its sign was left as computed (no genome sequence was available to orient it).")
        shares = [f"{v}% of the bins in {s}" for s, v in comp["a_share"].items() if v is not None]
        P.append(f"A/B compartments were taken from the first eigenvector of each chromosome's observed/expected correlation map at "
                 f"{_kb(comp['res'])} ({where}; Lieberman-Aiden et al., 2009; Open2C et al., 2024).{sign}"
                 + (f" The A compartment covered {join_and(shares)}." if shares else ""))
    td = last(hist, "called TAD boundaries")
    if td:
        n = [v for v in td["boundaries"].values()]
        med = [v for v in td["median_size"].values() if v]
        txt = (f"TAD boundaries were called from a diamond insulation score (Crane et al., 2015) on balanced {_kb(td['res'])} maps, "
               f"with a window of {td['window']} bins ({_kb(td['window_bp'])}), as troughs at least {td['min_strength']} (log2) below the "
               f"neighbouring peaks: {min(n):,}" + (f" to {max(n):,}" if max(n) != min(n) else "") + " boundaries per sample"
               + (f", with a median domain size of {_kb(int(median(med)))}" if med else "") + ".")
        ag = [v for v in td["hicexplorer_agree"].values() if v is not None]
        if ag:
            txt += (f" For comparison, {min(ag)}" + (f"–{max(ag)}" if max(ag) != min(ag) else "") +
                    "% of the boundaries HiCExplorer's hicFindTADs called in the pipeline (Ramírez et al., 2018) lay within one bin of these.")
        P.append(txt)
    ex = last(hist, "exported results")
    if ex:
        P.append("Compartment tracks (bedGraph), TAD boundaries and domains (BED), distance-decay curves and library statistics were "
                 "exported for further analysis.")
    return "\n\n".join(P) + "\n"

